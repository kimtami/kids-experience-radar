from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
import re
from typing import Any
from urllib.parse import urlparse

from ..http import PoliteHttpClient
from ..models import CrawlWindow, Event
from ..normalizers import (
    KST,
    child_relevance,
    clean_text,
    parse_age_range,
    parse_datetime,
    parse_price,
)
from .base import Source, SourceInfo


class GgcGyeonggiCultureSource(Source):
    """Collect child-relevant possibilities from GGC's documented public API."""

    ENDPOINT = "https://ggc.ggcf.kr/open/json/playongoing"
    OPEN_API_URL = "https://ggc.ggcf.kr/openAPI"
    PAGE_SIZE = 100
    PUBLIC_RAW_FIELDS = frozenset(
        {
            "writer",
            "subject",
            "category",
            "href",
            "startdate",
            "enddate",
            "enddate:",
            "address",
            "intime",
            "incost",
            "inquiry",
            "inarea",
            "homepage",
            "created",
        }
    )
    CHILD_TOKENS = (
        "초등",
        "어린이",
        "아동",
        "가족",
        "키즈",
        "자녀",
        "청소년",
        "유소년",
        "영유아",
        "꿈나무",
    )
    POSSIBILITY_TOKENS = (
        "체험",
        "워크숍",
        "공방",
        "만들기",
        "탐방",
        "해설",
        "생태",
        "과학",
        "창작",
        "캠프",
        "교실",
    )
    ADULT_ONLY_TOKENS = (
        "성인 대상",
        "성인 도슨트",
        "성인만",
        "전문가 과정",
        "교원 연수",
        "교사 연수",
    )

    def __init__(self) -> None:
        self.info = SourceInfo(
            source_id="ggc_gyeonggi_child_events",
            name="지지씨 경기도 어린이·교육·체험 가능 행사",
            owner="경기문화재단",
            source_type="open_api",
            official_url=self.OPEN_API_URL,
            license_code="TERMS-REVIEW-REQUIRED",
            enabled_by_default=True,
            policy_status="approved_api",
            notes=(
                "Official documented public Open API; keyless low-frequency GET. "
                "API linkage is documented, but downstream reuse terms and attribution "
                "must be reviewed; data is not represented as MIT-licensed. "
                "Reads list metadata only and never calls reservation, application, "
                "payment, login, or queue endpoints. Broad education possibilities are "
                "stored with a low child score unless the public text has child evidence."
            ),
        )

    @staticmethod
    def parse_page(payload: object) -> list[dict[str, Any]]:
        if not isinstance(payload, Mapping):
            raise RuntimeError("GGC Open API malformed response: expected object")
        if "INFO" not in payload or "DATA" not in payload:
            raise RuntimeError("GGC Open API malformed response: missing INFO or DATA")
        info = clean_text(payload.get("INFO"))
        if info not in {"0", "OK", "ok", "success"}:
            raise RuntimeError(f"GGC Open API error: INFO={info or 'unknown'}")
        data = payload.get("DATA")
        if not isinstance(data, list) or any(
            not isinstance(row, Mapping) for row in data
        ):
            raise RuntimeError("GGC Open API malformed response: DATA is not an object array")
        return [dict(row) for row in data]

    @classmethod
    def _public_haystack(cls, row: Mapping[str, Any]) -> str:
        return " ".join(
            value
            for field in (
                "subject",
                "category",
                "inarea",
                "address",
                "intime",
                "incost",
            )
            if (value := clean_text(row.get(field)))
        ).casefold()

    @classmethod
    def _is_child_possibility(cls, row: Mapping[str, Any]) -> bool:
        haystack = cls._public_haystack(row)
        # A dedicated first-party GGCF connector handles this venue's richer
        # event/education pages and prevents cross-feed duplicates.
        if "경기,장" in haystack.replace(" ", "") or "컬처라운지경기,장" in haystack.replace(" ", ""):
            return False
        has_child_evidence = any(token in haystack for token in cls.CHILD_TOKENS)
        if not has_child_evidence and any(
            token in haystack for token in cls.ADULT_ONLY_TOKENS
        ):
            return False
        category = (clean_text(row.get("category")) or "").casefold()
        return (
            has_child_evidence
            or category == "교육"
            or any(token in haystack for token in cls.POSSIBILITY_TOKENS)
        )

    @staticmethod
    def _canonical_detail_url(value: object | None) -> tuple[str, str] | None:
        url = clean_text(value)
        if not url:
            return None
        parsed = urlparse(url)
        match = re.fullmatch(r"/cultureEvents/view/([0-9a-fA-F]{24})", parsed.path)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "ggc.ggcf.kr"
            or parsed.params
            or parsed.query
            or parsed.fragment
            or match is None
        ):
            return None
        return url, match.group(1).casefold()

    @staticmethod
    def _age_hint(haystack: str) -> str | None:
        if "초등" in haystack:
            return "초등학생"
        if "어린이" in haystack:
            return "어린이"
        if "아동" in haystack:
            return "아동"
        if "가족" in haystack or "자녀" in haystack:
            return "가족"
        if any(token in haystack for token in ("청소년", "유소년")):
            return "청소년"
        if "영유아" in haystack:
            return "영유아"
        return None

    @staticmethod
    def _region(address: str | None) -> str:
        if not address:
            return "경기도"
        match = re.match(r"(경기도)\s+([^\s]+(?:시|군))", address)
        return " ".join(match.groups()) if match else "경기도"

    @staticmethod
    def _overlaps(event: Event, window: CrawlWindow) -> bool:
        if event.event_start is None and event.event_end is None:
            return True
        start = event.event_start or event.event_end
        end = event.event_end or event.event_start
        assert start is not None and end is not None
        return start <= window.end and end >= window.start

    def _map_row(self, row: dict[str, Any]) -> Event | None:
        detail = self._canonical_detail_url(row.get("href"))
        title = clean_text(row.get("subject"))
        if detail is None or not title:
            return None
        detail_url, external_id = detail
        haystack = self._public_haystack(row)
        age_text = self._age_hint(haystack)
        age_min, age_max, _ = parse_age_range(age_text)
        price_min, price_text = parse_price(row.get("incost"))
        address = clean_text(row.get("address"))
        venue = clean_text(row.get("inarea"))
        timing = clean_text(row.get("intime"))
        description = f"운영시간: {timing}" if timing else None
        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=external_id,
            title=title,
            detail_url=detail_url,
            provider_name=venue or clean_text(row.get("writer")),
            category=clean_text(row.get("category")),
            description=description,
            event_start=parse_datetime(row.get("startdate")),
            event_end=parse_datetime(
                row.get("enddate:") or row.get("enddate"), end_of_day=True
            ),
            apply_start=None,
            apply_end=None,
            status=None,
            age_text=age_text,
            age_min=age_min,
            age_max=age_max,
            price_text=price_text,
            price_min=price_min,
            venue_name=venue,
            address=address,
            region=self._region(address),
            latitude=None,
            longitude=None,
            image_url=None,
            phone=clean_text(row.get("inquiry")),
            is_online="온라인" in haystack,
            child_relevance_score=child_relevance(title, age_text, description),
            license_code=self.info.license_code,
            fetched_at=datetime.now(KST),
            raw={
                field: row[field]
                for field in self.PUBLIC_RAW_FIELDS
                if field in row
            },
        )

    def crawl(
        self, client: PoliteHttpClient, window: CrawlWindow
    ) -> Iterable[Event]:
        client.assert_html_allowed(self.ENDPOINT)
        for page in range(window.max_pages):
            payload = client.get_json(
                self.ENDPOINT,
                params={"page": page, "perpage": self.PAGE_SIZE},
            )
            rows = self.parse_page(payload)
            for row in rows:
                if not self._is_child_possibility(row):
                    continue
                event = self._map_row(row)
                if event is not None and self._overlaps(event, window):
                    yield event
            if len(rows) < self.PAGE_SIZE:
                break


__all__ = ["GgcGyeonggiCultureSource"]
