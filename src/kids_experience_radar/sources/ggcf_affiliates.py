from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
import re
from typing import Any
from urllib.parse import urlparse

from ..http import PoliteHttpClient
from ..models import CrawlWindow, Event
from ..normalizers import KST, child_relevance, clean_text, parse_age_range, parse_datetime, parse_price
from .base import Source, SourceInfo


class GgcfAffiliateProgramSource(Source):
    """Read the foundation-wide public event/education aggregate lists."""

    API_URLS = {
        "events": "https://www.ggcf.kr/api/events",
        "edus": "https://www.ggcf.kr/api/edus",
        "exhibitions": "https://www.ggcf.kr/api/exhibitions",
    }
    PUBLIC_RAW_FIELDS = frozenset(
        {
            "id",
            "title",
            "summary",
            "href",
            "place",
            "progress",
            "progress_start",
            "progress_finish",
            "application_start",
            "application_finish",
            "affiliationName",
            "affiliation_code",
            "display",
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
        "유아",
        "꿈나무",
    )
    POSSIBILITY_TOKENS = (
        "체험",
        "만들기",
        "워크숍",
        "공방",
        "교육프로그램",
        "캠프",
        "탐험",
        "놀이",
        "창작",
        "방학",
        "과학",
        "생태",
    )
    ADULT_ONLY_TOKENS = (
        "성인 대상",
        "성인 문화",
        "전문가 과정",
        "교원 연수",
        "교사 연수",
        "문화기획자",
    )
    AFFILIATION_REGIONS = {
        "경기문화재단": "경기도",
        "경기역사문화유산원": "경기도 광주시",
        "경기도박물관": "경기도 용인시",
        "경기도미술관": "경기도 안산시",
        "백남준아트센터": "경기도 용인시",
        "실학박물관": "경기도 남양주시",
        "전곡선사박물관": "경기도 연천군",
        "경기도어린이박물관": "경기도 용인시",
        "경기북부어린이박물관": "경기도 동두천시",
        "경기창작캠퍼스": "경기도 안산시",
        "경기상상캠퍼스": "경기도 수원시",
        "경기문화예술교육지원센터": "경기도 수원시",
    }
    AFFILIATION_ADDRESSES = {
        "경기문화재단": "경기도 수원시 팔달구 인계로 178",
        "경기역사문화유산원": "경기도 수원시 팔달구 인계로 178",
        "경기도박물관": "경기도 용인시 기흥구 상갈로 6",
        "경기도미술관": "경기도 안산시 단원구 동산로 268",
        "백남준아트센터": "경기도 용인시 기흥구 백남준로 10",
        "실학박물관": "경기도 남양주시 조안면 다산로747번길 16",
        "전곡선사박물관": "경기도 연천군 전곡읍 평화로443번길 2",
        "경기도어린이박물관": "경기도 용인시 기흥구 상갈로 6",
        "경기북부어린이박물관": "경기도 동두천시 평화로2910번길 46",
        "경기창작캠퍼스": "경기도 안산시 단원구 선감로 101-19",
        "경기상상캠퍼스": "경기도 수원시 권선구 서둔로 166",
        "경기문화예술교육지원센터": "경기도 수원시 권선구 서둔로 166",
    }
    PLACE_ADDRESS_OVERRIDES = (
        ("광명시민회관", "경기도 광명시 시청로 20"),
        ("남한산성역사문화관", "경기도 광주시 남한산성면 남한산성로 812"),
        ("천안홍대용과학관", "충청남도 천안시 동남구 수신면 장산서길 113"),
    )
    PLACE_REGIONS = (
        ("수원", "경기도 수원시"),
        ("용인", "경기도 용인시"),
        ("안산", "경기도 안산시"),
        ("남양주", "경기도 남양주시"),
        ("연천", "경기도 연천군"),
        ("동두천", "경기도 동두천시"),
        ("광명", "경기도 광명시"),
        ("남한산성", "경기도 광주시"),
        ("천안", "충청남도 천안시"),
    )

    def __init__(self) -> None:
        self.info = SourceInfo(
            source_id="ggcf_affiliate_child_programs",
            name="경기문화재단 산하기관 어린이·체험 프로그램",
            owner="경기문화재단",
            source_type="reviewed_public_json",
            official_url="https://www.ggcf.kr/edus",
            license_code=None,
            enabled_by_default=False,
            policy_status="reviewed_public_json",
            notes=(
                "Foundation-wide official public JSON result lists with runtime robots "
                "checks. Reads factual list metadata only; no detail fetch, reservation, "
                "application, login, payment, queue, or external booking request. The "
                "dedicated 경기,장 connector owns that venue to prevent duplicates."
            ),
        )

    @staticmethod
    def parse_page(payload: object) -> tuple[list[dict[str, Any]], int]:
        if not isinstance(payload, Mapping):
            raise RuntimeError("GGCF affiliate API malformed response: expected object")
        rows = payload.get("list")
        if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
            raise RuntimeError("GGCF affiliate API malformed response: invalid list")
        try:
            last_page = int(payload.get("last_page"))
        except (TypeError, ValueError) as exc:
            raise RuntimeError("GGCF affiliate API malformed response: invalid last_page") from exc
        if last_page < 1:
            raise RuntimeError("GGCF affiliate API malformed response: invalid last_page")
        return [dict(row) for row in rows], last_page

    @staticmethod
    def _haystack(row: Mapping[str, Any]) -> str:
        return " ".join(
            value
            for field in ("title", "summary", "place", "affiliationName")
            if (value := clean_text(row.get(field)))
        ).casefold()

    @classmethod
    def _candidate(cls, row: Mapping[str, Any]) -> bool:
        if clean_text(row.get("display")) == "none":
            return False
        haystack = cls._haystack(row)
        normalized = re.sub(r"[^0-9a-z가-힣]+", "", haystack)
        if "컬처라운지경기장" in normalized:
            return False
        has_child = any(token in haystack for token in cls.CHILD_TOKENS)
        if not has_child and any(token in haystack for token in cls.ADULT_ONLY_TOKENS):
            return False
        return has_child or any(token in haystack for token in cls.POSSIBILITY_TOKENS)

    @staticmethod
    def _canonical_detail(value: object | None, content_type: str) -> tuple[str, str] | None:
        raw = clean_text(value)
        if not raw:
            return None
        parsed = urlparse(raw)
        hostname = (parsed.hostname or "").casefold()
        match = re.fullmatch(rf"/{re.escape(content_type)}/(\d{{1,20}})/?", parsed.path)
        if (
            parsed.scheme != "https"
            or not (hostname == "ggcf.kr" or hostname.endswith(".ggcf.kr"))
            or match is None
        ):
            return None
        canonical = f"https://{hostname}/{content_type}/{match.group(1)}"
        return canonical, match.group(1)

    @classmethod
    def _region(cls, row: Mapping[str, Any]) -> str:
        place = clean_text(row.get("place")) or ""
        for marker, region in cls.PLACE_REGIONS:
            if marker in place:
                return region
        affiliation = clean_text(row.get("affiliationName")) or ""
        return cls.AFFILIATION_REGIONS.get(affiliation, "경기도")

    @classmethod
    def _address(cls, row: Mapping[str, Any]) -> str | None:
        place = clean_text(row.get("place")) or ""
        if any(marker in place for marker in ("온라인", "각 학교", "각 기관")):
            return None
        # A mixed multi-venue record cannot be represented by one safe point.
        if "천안홍대용과학관" in place and "다산박물관" in place:
            return None
        for marker, address in cls.PLACE_ADDRESS_OVERRIDES:
            if marker in place:
                return address
        affiliation = clean_text(row.get("affiliationName")) or ""
        return cls.AFFILIATION_ADDRESSES.get(affiliation)

    @staticmethod
    def _age_hint(haystack: str) -> str | None:
        for marker, label in (
            ("초등", "초등학생"),
            ("어린이", "어린이"),
            ("아동", "아동"),
            ("가족", "가족"),
            ("청소년", "청소년"),
            ("유아", "유아"),
        ):
            if marker in haystack:
                return label
        return None

    @staticmethod
    def _overlaps(event: Event, window: CrawlWindow) -> bool:
        if event.event_start is None and event.event_end is None:
            return True
        start = event.event_start or event.event_end
        end = event.event_end or event.event_start
        assert start is not None and end is not None
        return start <= window.end and end >= window.start

    def _map(self, row: dict[str, Any], content_type: str) -> Event | None:
        detail = self._canonical_detail(row.get("href"), content_type)
        title = clean_text(row.get("title"))
        if detail is None or not title:
            return None
        detail_url, detail_id = detail
        summary = clean_text(row.get("summary"))
        haystack = self._haystack(row)
        age_text = self._age_hint(haystack)
        age_min, age_max, _ = parse_age_range(age_text)
        price_min, price_text = parse_price(summary)
        provider = clean_text(row.get("affiliationName")) or self.info.owner
        place = clean_text(row.get("place"))
        api_id = clean_text(row.get("id")) or detail_id
        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=f"{content_type}:{api_id}",
            title=title,
            detail_url=detail_url,
            provider_name=provider,
            category={
                "events": "행사·체험",
                "edus": "교육·체험",
                "exhibitions": "전시·체험",
            }[content_type],
            description=summary,
            event_start=parse_datetime(row.get("progress_start")),
            event_end=parse_datetime(row.get("progress_finish"), end_of_day=True),
            apply_start=parse_datetime(row.get("application_start")),
            apply_end=parse_datetime(row.get("application_finish"), end_of_day=True),
            status=clean_text(row.get("progress")),
            age_text=age_text,
            age_min=age_min,
            age_max=age_max,
            price_text=price_text,
            price_min=price_min,
            venue_name=place,
            address=self._address(row),
            region=self._region(row),
            latitude=None,
            longitude=None,
            image_url=None,
            phone=None,
            is_online="온라인" in haystack,
            child_relevance_score=child_relevance(title, age_text, summary),
            license_code=self.info.license_code,
            fetched_at=datetime.now(KST),
            raw={
                field: row[field]
                for field in self.PUBLIC_RAW_FIELDS
                if field in row
            },
        )

    def crawl(self, client: PoliteHttpClient, window: CrawlWindow) -> Iterable[Event]:
        for content_type in ("events", "edus", "exhibitions"):
            api_url = self.API_URLS[content_type]
            client.assert_html_allowed(api_url)
            for page in range(1, window.max_pages + 1):
                payload = client.get_json(
                    api_url,
                    params={"progress": "soon", "limit": 100, "page": page},
                )
                rows, last_page = self.parse_page(payload)
                for row in rows:
                    if not self._candidate(row):
                        continue
                    event = self._map(row, content_type)
                    if event is not None and self._overlaps(event, window):
                        yield event
                if page >= last_page:
                    break


__all__ = ["GgcfAffiliateProgramSource"]
