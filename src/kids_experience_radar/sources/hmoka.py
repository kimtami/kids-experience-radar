from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
import re
from typing import Any
from urllib.parse import quote

from ..http import PoliteHttpClient
from ..models import CrawlWindow, Event
from ..normalizers import (
    KST,
    child_relevance,
    clean_text,
    parse_age_range,
    parse_date_range,
    parse_price,
)
from ..policy import explicit_source_approval
from .base import Source, SourceInfo


class HmokaProgramSource(Source):
    """Read the four public H-MOKA education list feeds.

    The source deliberately retains only public list facts. It does not call any
    reservation, login, applicant, or application-detail endpoint.
    """

    PROGRAM_TYPES = ("exhibition", "theme1", "theme2", "theme3")
    PAGE_SIZE = 100
    LIST_URL = "https://www.hmoka.org/programs/exhibition/list.do?st_cd=480"
    DATA_URL = "https://www.hmoka.org/programs/{program_type}/data.do"
    DETAIL_URL = (
        "https://www.hmoka.org/programs/{program_type}/view.do"
        "?st_cd=480&edu_seq={edu_seq}"
    )
    VENUE = "현대어린이책미술관"

    def __init__(self) -> None:
        self.info = SourceInfo(
            source_id="hmoka_programs",
            name="현대어린이책미술관 체험·교육",
            owner="현대어린이책미술관",
            source_type="public_json",
            official_url=self.LIST_URL,
            license_code=None,
            enabled_by_default=False,
            policy_status="review_required_public_json",
            notes=(
                "Public list form POST only; facts-only whitelist and low-frequency "
                "collection. No reservation, login, or applicant endpoint. Re-enable "
                "only after policy review."
            ),
        )

    def crawl(
        self,
        client: PoliteHttpClient,
        window: CrawlWindow,
    ) -> Iterable[Event]:
        client.assert_html_allowed(self.DATA_URL.format(program_type="exhibition"))
        seen: set[str] = set()
        for program_type in self.PROGRAM_TYPES:
            endpoint = self.DATA_URL.format(program_type=program_type)
            for page in range(1, max(1, window.max_pages) + 1):
                payload = client.post_json(
                    endpoint,
                    data={
                        "st_cd": "480",
                        "page": page,
                        "rows": self.PAGE_SIZE,
                        "searchEduName": "",
                        "searchOnlineCode": "",
                    },
                )
                rows, response_page, total = self.parse_page(payload)
                for row in rows:
                    external_id = clean_text(row.get("edu_seq"))
                    if external_id is None or external_id in seen:
                        continue
                    event = self._map_row(row, program_type)
                    if event is None:
                        continue
                    seen.add(external_id)
                    if self._overlaps_window(event, window):
                        yield event

                if not rows or response_page * self.PAGE_SIZE >= total:
                    break

    def available(self) -> tuple[bool, str | None]:
        return explicit_source_approval(self.info.source_id)

    @staticmethod
    def parse_page(payload: object) -> tuple[list[dict[str, Any]], int, int]:
        if not isinstance(payload, Mapping):
            raise RuntimeError("H-MOKA malformed response: expected an object")
        if "contentList" not in payload:
            raise RuntimeError("H-MOKA malformed response: missing contentList")
        content = payload.get("contentList")
        if not isinstance(content, list):
            raise RuntimeError("H-MOKA malformed response: contentList is not an array")

        rows = [dict(row) for row in content if isinstance(row, Mapping)]
        page = HmokaProgramSource._non_negative_int(payload.get("page"), default=1)
        total = HmokaProgramSource._non_negative_int(
            payload.get("total"), default=len(rows)
        )
        return rows, max(1, page), total

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
    def _is_child_target(target: str | None) -> bool:
        if not target:
            return True
        compact = re.sub(r"\s+", "", target)
        without_childcare = compact.replace("어린이집", "")
        explicit_child = any(
            marker in without_childcare
            for marker in ("어린이", "아동", "유아", "가족", "보호자동반")
        )
        adult_only_markers = ("성인", "교사", "교원", "전문가", "강사")
        if any(marker in compact for marker in adult_only_markers):
            return explicit_child
        return True

    @staticmethod
    def _age(target: str | None) -> tuple[int | None, int | None, str | None]:
        if not target:
            return None, None, None
        normalized = target.replace("–", "-").replace("~", "-")

        ranges: list[tuple[int, int]] = []
        for match in re.finditer(
            r"(\d{1,2})\s*세\s*-\s*초(?:등)?\s*([1-6])",
            normalized,
        ):
            ranges.append((int(match.group(1)), int(match.group(2)) + 6))
        for match in re.finditer(
            r"초(?:등)?\s*([1-6])\s*-\s*(?:초(?:등)?\s*)?([1-6])(?:\s*학년)?",
            normalized,
        ):
            first, last = (int(value) + 6 for value in match.groups())
            ranges.append((min(first, last), max(first, last)))
        for match in re.finditer(
            r"(?<![초등])(\d{1,2})\s*(?:세)?\s*-\s*(\d{1,2})\s*세",
            normalized,
        ):
            first, last = (int(value) for value in match.groups())
            ranges.append((min(first, last), max(first, last)))
        if ranges:
            return min(first for first, _ in ranges), max(last for _, last in ranges), target

        bounds: list[int] = []
        for mixed in re.finditer(
            r"(?<![초등])(\d{1,2})\s*세?\s*-\s*초(?:등)?\s*([1-6])",
            normalized,
        ):
            bounds.extend((int(mixed.group(1)), int(mixed.group(2)) + 6))

        for grades in re.finditer(
            r"초(?:등)?\s*([1-6])\s*-\s*(?:초(?:등)?\s*)?([1-6])"
            r"(?:\s*학년|\s*년)?",
            normalized,
        ):
            bounds.extend(int(value) + 6 for value in grades.groups())

        for ages in re.finditer(
            r"(\d{1,2})\s*(?:세)?\s*-\s*(\d{1,2})\s*세",
            normalized,
        ):
            bounds.extend(int(value) for value in ages.groups())

        if bounds:
            return min(bounds), max(bounds), target

        minimum_grade = re.search(
            r"초(?:등)?\s*([1-6])\s*(?:학년)?\s*이상",
            normalized,
        )
        if minimum_grade:
            return int(minimum_grade.group(1)) + 6, 12, target

        single_age = re.fullmatch(r"\s*(\d{1,2})\s*세\s*", normalized)
        if single_age:
            age = int(single_age.group(1))
            return age, age, target

        return parse_age_range(target)

    @staticmethod
    def _price(value: object) -> tuple[int | None, str | None]:
        text = clean_text(value)
        if text is None:
            return None, None
        compact = re.sub(r"[,\s원]", "", text)
        if compact.isdigit():
            amount = int(compact)
            return amount, "무료" if amount == 0 else f"{amount:,}원"
        return parse_price(text)

    @staticmethod
    def _status(row: Mapping[str, Any]) -> str | None:
        online = clean_text(row.get("online_yn"))
        status = clean_text(row.get("status"))
        if online == "N":
            return clean_text(row.get("online_code_name")) or "온라인 신청 없음"
        if status == "C":
            return "신청마감"
        if status == "U":
            return "신청 예정"
        if status:
            return "신청 가능"
        return None

    def _map_row(
        self,
        row: dict[str, Any],
        program_type: str,
    ) -> Event | None:
        external_id = clean_text(row.get("edu_seq"))
        title = clean_text(row.get("edu_name"))
        target = clean_text(row.get("edu_target_name"))
        if external_id is None or title is None or not self._is_child_target(target):
            return None

        period = clean_text(row.get("time"))
        place = clean_text(row.get("place_name"))
        event_start, event_end = parse_date_range(period)
        age_min, age_max, age_text = self._age(target)
        price_min, price_text = self._price(row.get("edu_charge"))
        status = self._status(row)
        detail_url = self.DETAIL_URL.format(
            program_type=program_type,
            edu_seq=quote(external_id, safe=""),
        )
        venue_name = (
            self.VENUE
            if place is None or self.VENUE in place
            else f"{self.VENUE} · {place}"
        )

        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=external_id,
            title=title,
            detail_url=detail_url,
            provider_name=self.VENUE,
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
            venue_name=venue_name,
            address="경기도 성남시 분당구 판교역로146번길 20 현대백화점 판교점 5층",
            region="경기도 성남시 분당구",
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


HyundaiChildrensBooksMuseumSource = HmokaProgramSource
HmokaProgramsSource = HmokaProgramSource

__all__ = [
    "HmokaProgramSource",
    "HmokaProgramsSource",
    "HyundaiChildrensBooksMuseumSource",
]
