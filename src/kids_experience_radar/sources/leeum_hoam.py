from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
import math
import re
from typing import Any
from urllib.parse import quote

from ..http import PoliteHttpClient
from ..models import CrawlWindow, Event
from ..normalizers import KST, child_relevance, clean_text, parse_price, parse_datetime
from ..policy import explicit_source_approval
from .base import Source, SourceInfo


class LeeumHoamProgramSource(Source):
    """Read the public Leeum/Hoam unified education-program list JSON."""

    ENDPOINT = "https://www.leeumhoam.org/leeum/edu/program/list"
    LIST_URL = "https://www.leeumhoam.org/leeum/edu/program"
    DETAIL_URL = "https://www.leeumhoam.org/leeum/edu/program/{pro_id}"
    PAGE_SIZE = 100

    def __init__(self) -> None:
        self.info = SourceInfo(
            source_id="leeum_hoam_programs",
            name="리움·호암미술관 어린이 교육",
            owner="삼성문화재단",
            source_type="public_json",
            official_url=self.LIST_URL,
            license_code=None,
            enabled_by_default=False,
            policy_status="review_required_public_json",
            notes=(
                "Unified public list JSON only; facts-only whitelist and low-frequency "
                "collection. No program-detail body, image, reservation, login, or "
                "applicant endpoint. Re-enable only after policy review."
            ),
        )

    def crawl(
        self,
        client: PoliteHttpClient,
        window: CrawlWindow,
    ) -> Iterable[Event]:
        client.assert_html_allowed(self.ENDPOINT)
        seen: set[str] = set()
        for requested_page in range(1, max(1, window.max_pages) + 1):
            payload = client.get_json(
                self.ENDPOINT,
                params={
                    "view": "list",
                    "status[]": [1, 2],
                    "type1": 102,
                    "keyword": "",
                    "startDate": "",
                    "endDate": "",
                    "limit": self.PAGE_SIZE,
                    "found": "LM",
                    "page": requested_page,
                },
            )
            rows, response_page, max_page, _ = self.parse_page(payload)
            for row in rows:
                external_id = clean_text(row.get("proId"))
                if external_id is None or external_id in seen:
                    continue
                event = self._map_row(row)
                if event is None:
                    continue
                seen.add(external_id)
                if self._overlaps_window(event, window):
                    yield event

            if not rows or response_page >= max_page:
                break

    def available(self) -> tuple[bool, str | None]:
        return explicit_source_approval(self.info.source_id)

    @staticmethod
    def parse_page(
        payload: object,
    ) -> tuple[list[dict[str, Any]], int, int, int]:
        if not isinstance(payload, Mapping):
            raise RuntimeError("Leeum/Hoam malformed response: expected an object")
        if "list" not in payload:
            raise RuntimeError("Leeum/Hoam malformed response: missing list")
        content = payload.get("list")
        if not isinstance(content, list):
            raise RuntimeError("Leeum/Hoam malformed response: list is not an array")
        paging = payload.get("paging", {})
        if not isinstance(paging, Mapping):
            raise RuntimeError("Leeum/Hoam malformed response: paging is not an object")

        rows = [dict(row) for row in content if isinstance(row, Mapping)]
        total = LeeumHoamProgramSource._non_negative_int(
            payload.get("total", paging.get("totalCount")),
            default=len(rows),
        )
        page = max(
            1,
            LeeumHoamProgramSource._non_negative_int(
                paging.get("page"),
                default=1,
            ),
        )
        inferred_max = max(1, math.ceil(total / LeeumHoamProgramSource.PAGE_SIZE))
        max_page = max(
            1,
            LeeumHoamProgramSource._non_negative_int(
                paging.get("maxPage"),
                default=inferred_max,
            ),
        )
        return rows, page, max_page, total

    @staticmethod
    def _non_negative_int(value: object, *, default: int) -> int:
        try:
            return max(0, int(str(value).strip()))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _overlaps_window(event: Event, window: CrawlWindow) -> bool:
        if event.event_start is None and event.event_end is None:
            return True
        start = event.event_start or event.event_end
        end = event.event_end or event.event_start
        assert start is not None and end is not None
        return start <= window.end and end >= window.start

    @staticmethod
    def _target(title: str, row: Mapping[str, Any]) -> str | None:
        published = clean_text(row.get("homeTarget"))
        if published:
            return published

        grade = re.search(
            r"초(?:등(?:학교)?)?\s*[1-6]\s*(?:~|[-–])\s*[1-6]\s*학년",
            title,
        )
        if grade:
            return clean_text(grade.group(0))
        single_grade = re.search(
            r"초(?:등(?:학교)?)?\s*[1-6]\s*학년",
            title,
        )
        if single_grade:
            return clean_text(single_grade.group(0))
        for marker in ("어린이", "아동", "가족", "유아", "키즈"):
            if marker in title:
                return marker
        return None

    @staticmethod
    def _age(target: str | None) -> tuple[int | None, int | None, str | None]:
        if target is None:
            return None, None, None
        grade_range = re.search(
            r"초(?:등(?:학교)?)?\s*([1-6])\s*(?:~|[-–])\s*([1-6])",
            target,
        )
        if grade_range:
            first, last = (int(value) + 6 for value in grade_range.groups())
            return min(first, last), max(first, last), target
        single_grade = re.search(
            r"초(?:등(?:학교)?)?\s*([1-6])\s*학년",
            target,
        )
        if single_grade:
            age = int(single_grade.group(1)) + 6
            return age, age, target
        return None, None, target

    @staticmethod
    def _is_child_program(title: str, target: str | None) -> bool:
        haystack = f"{title} {target or ''}"
        return any(
            marker in haystack
            for marker in ("어린이", "아동", "초등", "키즈", "가족", "유아")
        )

    @staticmethod
    def _price(row: Mapping[str, Any]) -> tuple[int | None, str | None]:
        income = clean_text(row.get("income"))
        if income:
            compact = re.sub(r"[,\s원]", "", income)
            if compact.isdigit():
                amount = int(compact)
                return amount, "무료" if amount == 0 else f"{amount:,}원"
            parsed, rendered = parse_price(income)
            if rendered:
                return parsed, rendered

        free_type = clean_text(row.get("applyFreeType"))
        if free_type and any(token in free_type for token in ("무료", "유료", "원")):
            parsed, rendered = parse_price(free_type)
            return parsed, rendered or free_type
        return None, None

    @staticmethod
    def _status(row: Mapping[str, Any]) -> str | None:
        published = clean_text(row.get("statusName"))
        if published:
            return published
        status = clean_text(row.get("status"))
        return {
            "1": "신청중",
            "2": "신청예정",
            "3": "신청마감",
        }.get(status or "", status)

    def _map_row(self, row: dict[str, Any]) -> Event | None:
        external_id = clean_text(row.get("proId"))
        title = clean_text(row.get("title"))
        if external_id is None or title is None:
            return None
        target = self._target(title, row)
        if not self._is_child_program(title, target):
            return None

        start_text = clean_text(row.get("programStartDate"))
        end_text = clean_text(row.get("programEndDate"))
        event_start = parse_datetime(start_text)
        event_end = parse_datetime(end_text, end_of_day=True)
        period = (
            f"{start_text}~{end_text}"
            if start_text and end_text
            else start_text or end_text
        )
        place = (
            clean_text(row.get("placeDesc"))
            or clean_text(row.get("place"))
            or ("호암미술관" if "호암" in title else "리움미술관")
        )
        is_hoam = "호암" in f"{title} {place}"
        address = (
            "경기도 용인시 처인구 포곡읍 에버랜드로562번길 38"
            if is_hoam
            else "서울특별시 용산구 이태원로55길 60-16"
        )
        region = "경기도 용인시 처인구" if is_hoam else "서울특별시 용산구"
        age_min, age_max, age_text = self._age(target)
        price_min, price_text = self._price(row)
        status = self._status(row)
        detail_url = self.DETAIL_URL.format(pro_id=quote(external_id, safe=""))

        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=external_id,
            title=title,
            detail_url=detail_url,
            provider_name="리움·호암미술관",
            category="체험·교육",
            description=None,
            event_start=event_start,
            event_end=event_end,
            apply_start=None,
            apply_end=None,
            status=status,
            age_text=age_text,
            age_min=age_min,
            age_max=age_max,
            price_text=price_text,
            price_min=price_min,
            venue_name=place,
            address=address,
            region=region,
            latitude=None,
            longitude=None,
            image_url=None,
            phone=None,
            is_online=False,
            child_relevance_score=child_relevance(title, age_text),
            license_code=self.info.license_code,
            fetched_at=datetime.now(KST),
            raw={
                "title": title,
                "period": period,
                "target": target,
                "place": place,
                "price": price_text,
                "status": status,
                "official_url": detail_url,
            },
        )


LeeumHoamEducationSource = LeeumHoamProgramSource
LeeumHoamProgramsSource = LeeumHoamProgramSource

__all__ = [
    "LeeumHoamEducationSource",
    "LeeumHoamProgramSource",
    "LeeumHoamProgramsSource",
]
