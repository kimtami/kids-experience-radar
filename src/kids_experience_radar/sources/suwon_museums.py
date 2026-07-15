from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time
import math
import re
from typing import Any
from urllib.parse import urlencode

from bs4 import BeautifulSoup, NavigableString, Tag

from ..http import PoliteHttpClient
from ..models import CrawlWindow, Event
from ..normalizers import KST, child_relevance, clean_text, parse_age_range, parse_price
from .base import Source, SourceInfo


@dataclass(slots=True, frozen=True)
class SuwonMuseumConfig:
    museum_code: str
    source_id: str
    museum_name: str
    address: str


SUWON_MUSEUM_CONFIGS = (
    SuwonMuseumConfig(
        museum_code="SW",
        source_id="suwon_museum_child_programs",
        museum_name="수원박물관",
        address="경기도 수원시 영통구 창룡대로 265",
    ),
    SuwonMuseumConfig(
        museum_code="GG",
        source_id="suwon_gwanggyo_museum_child_programs",
        museum_name="수원광교박물관",
        address="경기도 수원시 영통구 광교로 182",
    ),
    SuwonMuseumConfig(
        museum_code="HS",
        source_id="suwon_hwaseong_museum_child_programs",
        museum_name="수원화성박물관",
        address="경기도 수원시 팔달구 창룡대로 21",
    ),
)


class SuwonMuseumProgramSource(Source):
    """Read public program facts from Suwon's three municipal museums.

    The site uses a POST request as a read-only list query. This connector only
    calls that public list and public information-detail pages. It never calls
    login, reservation, application, payment, capacity-action, or queue paths.
    """

    LIST_PAGE_URL = "https://rmuseum.suwon.go.kr/progrm/progrmList.do"
    LIST_ENDPOINT = "https://rmuseum.suwon.go.kr/progrm/progrmAjaxList.do"
    DETAIL_ENDPOINT = "https://rmuseum.suwon.go.kr/progrm/progrmDetail.do"
    PAGE_SIZE_FALLBACK = 10
    DETAIL_LABELS = {
        "프로그램명": "program_name",
        "진행일시": "program_period",
        "접수일시": "application_period",
        "장소": "venue",
        "참가대상": "audience",
        "접수방법": "application_method",
        "접수방식": "application_type",
        "참가비": "price",
        "문의처": "contact",
    }
    PUBLIC_RAW_FIELDS = frozenset(
        {
            "museum_code",
            "program_sequence",
            "program_name",
            "program_period",
            "application_period",
            "list_status",
            "venue",
            "audience",
            "price",
            "contact",
            "application_method",
            "application_type",
        }
    )
    CHILD_TOKENS = ("어린이", "초등", "아동", "가족", "유아", "키즈")
    POSSIBILITY_TOKENS = ("교육", "체험", "방학", "주말", "만들기", "놀이")
    ADULT_ONLY_TOKENS = ("성인교육", "성인 대상", "전문가", "교사 연수")

    def __init__(self, config: SuwonMuseumConfig) -> None:
        self.config = config
        self.info = SourceInfo(
            source_id=config.source_id,
            name=f"{config.museum_name} 어린이·가족 프로그램",
            owner="수원특례시 박물관사업소",
            source_type="reviewed_public_json_html",
            official_url=(
                f"{self.LIST_PAGE_URL}?"
                f"{urlencode({'searchMuseumCd': config.museum_code, 'searchTabType': 'ING'})}"
            ),
            license_code=None,
            enabled_by_default=False,
            policy_status="reviewed_public_list_html",
            notes=(
                "Official public read-only POST list and information-detail GET with "
                "runtime robots checks. Only whitelisted program facts are retained; "
                "masked participant rows present elsewhere on the detail page are not "
                "parsed. No login, reservation, application, payment, or queue path."
            ),
        )

    @staticmethod
    def _positive_int(value: object | None) -> int | None:
        try:
            parsed = int(str(value).strip())
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    @classmethod
    def parse_page(cls, payload: object) -> tuple[list[dict[str, Any]], int]:
        if not isinstance(payload, Mapping):
            raise RuntimeError("Suwon museum list malformed response: expected object")
        raw_rows = payload.get("dataList")
        if not isinstance(raw_rows, list) or any(
            not isinstance(row, Mapping) for row in raw_rows
        ):
            raise RuntimeError("Suwon museum list malformed response: invalid dataList")
        rows = [dict(row) for row in raw_rows]

        pagination = payload.get("paginationInfo")
        total_pages: int | None = None
        if isinstance(pagination, Mapping):
            total_pages = cls._positive_int(pagination.get("totalPageCount"))
        if total_pages is None:
            total_count = cls._positive_int(payload.get("totalCnt")) or len(rows)
            page_size = len(rows) or cls.PAGE_SIZE_FALLBACK
            total_pages = max(1, math.ceil(total_count / page_size))
        return rows, total_pages

    @staticmethod
    def _normalized_label(value: object | None) -> str | None:
        text = clean_text(value)
        if not text:
            return None
        return re.sub(r"[\s:：]+", "", text)

    @classmethod
    def _sibling_value(cls, node: Tag) -> str | None:
        sibling = node.next_sibling
        while sibling is not None:
            if isinstance(sibling, NavigableString):
                value = clean_text(sibling)
            elif isinstance(sibling, Tag):
                value = clean_text(sibling.get_text(" ", strip=True))
            else:
                value = None
            if value:
                return value[:1000]
            sibling = sibling.next_sibling

        parent = node.parent
        if isinstance(parent, Tag):
            parent_text = clean_text(parent.get_text(" ", strip=True))
            label_text = clean_text(node.get_text(" ", strip=True))
            if parent_text and label_text and parent_text.startswith(label_text):
                value = clean_text(parent_text[len(label_text) :])
                if value:
                    return value[:1000]
        return None

    @classmethod
    def parse_detail_html(cls, html: str) -> dict[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        facts: dict[str, str] = {}
        for node in soup.find_all(("dt", "th", "strong", "em", "span", "p", "div")):
            label = cls._normalized_label(node.get_text(" ", strip=True))
            field = cls.DETAIL_LABELS.get(label or "")
            if field is None or field in facts:
                continue
            value = cls._sibling_value(node)
            if value:
                facts[field] = value
        if not facts.get("program_name"):
            raise RuntimeError(
                "Suwon museum detail structure changed: program name not found"
            )
        return facts

    @staticmethod
    def _extract_times(text: str) -> list[time]:
        found: list[tuple[int, time]] = []
        for match in re.finditer(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)", text):
            found.append((match.start(), time(int(match.group(1)), int(match.group(2)))))
        for match in re.finditer(
            r"(?:(오전|오후)\s*)?(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분)?",
            text,
        ):
            hour = int(match.group(2))
            minute = int(match.group(3) or 0)
            marker = match.group(1)
            if marker == "오후" and hour < 12:
                hour += 12
            elif marker == "오전" and hour == 12:
                hour = 0
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                found.append((match.start(), time(hour, minute)))
        found.sort(key=lambda item: item[0])
        return [value for _, value in found]

    @classmethod
    def parse_period(
        cls,
        value: object | None,
        *,
        open_ended_single: bool = False,
    ) -> tuple[datetime | None, datetime | None]:
        text_value = clean_text(value)
        if not text_value:
            return None, None
        normalized_value = re.sub(
            r"(20\d{2})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일?",
            r"\1.\2.\3",
            text_value,
        )
        date_matches = list(
            re.finditer(
                r"(20\d{2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{1,2})",
                normalized_value,
            )
        )
        if not date_matches:
            return None, None
        try:
            dates = [date(*(int(part) for part in match.groups())) for match in date_matches]
        except ValueError:
            return None, None

        if len(dates) == 1:
            suffix = normalized_value[date_matches[0].end() :]
            shorthand = re.search(
                r"(?:~|～|/)\s*(\d{1,2})\s*[./-]\s*(\d{1,2})",
                suffix,
            )
            if shorthand:
                try:
                    dates.append(
                        date(dates[0].year, int(shorthand.group(1)), int(shorthand.group(2)))
                    )
                except ValueError:
                    pass

            same_month_day = re.search(r"(?:,|/)\s*(\d{1,2})\s*일", suffix)
            if len(dates) == 1 and same_month_day:
                try:
                    dates.append(
                        date(dates[0].year, dates[0].month, int(same_month_day.group(1)))
                    )
                except ValueError:
                    pass

        times = cls._extract_times(normalized_value)
        start_time = times[0] if times else time.min
        start = datetime.combine(dates[0], start_time, tzinfo=KST)
        if len(dates) >= 2:
            end_time = times[-1] if len(times) >= 2 else time.max
            return start, datetime.combine(dates[-1], end_time, tzinfo=KST)
        if len(times) >= 2:
            return start, datetime.combine(dates[0], times[-1], tzinfo=KST)
        if open_ended_single:
            return start, None
        return start, datetime.combine(dates[0], time.max, tzinfo=KST)

    @staticmethod
    def _canonical_detail(museum_code: str, sequence: str) -> str:
        return (
            f"{SuwonMuseumProgramSource.DETAIL_ENDPOINT}?"
            f"{urlencode({'museumCd': museum_code, 'progrmSeq': sequence, 'searchTabType': 'ING'})}"
        )

    @classmethod
    def _potential_child(cls, title: str, audience: str | None = None) -> bool:
        text = f"{title} {audience or ''}".casefold()
        has_child = any(token in text for token in cls.CHILD_TOKENS)
        if not has_child and any(token in text for token in cls.ADULT_ONLY_TOKENS):
            return False
        if audience:
            return has_child or any(
                token in text for token in ("청소년", "전체", "누구나")
            )
        return has_child or any(token in text for token in cls.POSSIBILITY_TOKENS)

    @classmethod
    def _list_candidate(cls, title: str, audience: object | None = None) -> bool:
        """Keep ambiguous rows until the public detail supplies the audience."""
        text = f"{title} {clean_text(audience) or ''}".casefold()
        has_child = any(token in text for token in cls.CHILD_TOKENS)
        return has_child or not any(token in text for token in cls.ADULT_ONLY_TOKENS)

    @staticmethod
    def _status(value: object | None) -> str | None:
        text = clean_text(value)
        if not text:
            return None
        compact = re.sub(r"\s+", "", text)
        for status in ("접수대기", "접수중", "접수마감", "마감", "종료"):
            if status in compact:
                return status
        return text[:80]

    @staticmethod
    def _phone(value: str | None) -> str | None:
        if not value:
            return None
        match = re.search(r"0\d{1,2}[-.)\s]+\d{3,4}[-.\s]+\d{4}", value)
        return clean_text(match.group(0)) if match else clean_text(value)

    @staticmethod
    def _overlaps(event: Event, window: CrawlWindow) -> bool:
        start = event.event_start or event.event_end
        end = event.event_end or event.event_start
        if start is None and end is None:
            start = event.apply_start or event.apply_end
            end = event.apply_end or event.apply_start
        if start is None or end is None:
            return True
        return start <= window.end and end >= window.start

    def _map(self, row: Mapping[str, Any], detail: Mapping[str, str]) -> Event | None:
        sequence = clean_text(row.get("progrmSeq"))
        title = clean_text(detail.get("program_name") or row.get("progrmNm"))
        if not sequence or not re.fullmatch(r"\d{1,20}", sequence) or not title:
            return None
        audience = clean_text(detail.get("audience") or row.get("partcptTrget"))
        if not self._potential_child(title, audience):
            return None

        list_event = self.parse_period(row.get("progrsDtCn"))
        detail_event = self.parse_period(detail.get("program_period"))
        event_start = detail_event[0] or list_event[0]
        event_end = detail_event[1] or list_event[1]

        list_application = self.parse_period(
            row.get("rceptDtCn"), open_ended_single=True
        )
        detail_application = self.parse_period(
            detail.get("application_period"), open_ended_single=True
        )
        apply_start = detail_application[0] or list_application[0]
        apply_end = list_application[1] or detail_application[1]

        age_min, age_max, age_text = parse_age_range(audience)
        price_min, price_text = parse_price(detail.get("price"))
        venue = clean_text(detail.get("venue"))
        application_method = clean_text(detail.get("application_method"))
        application_type = clean_text(detail.get("application_type"))
        description_parts = [
            f"접수방법: {application_method}" if application_method else None,
            f"접수방식: {application_type}" if application_type else None,
        ]
        raw = {
            "museum_code": self.config.museum_code,
            "program_sequence": sequence,
            "program_name": title,
            "program_period": clean_text(
                detail.get("program_period") or row.get("progrsDtCn")
            ),
            "application_period": clean_text(
                row.get("rceptDtCn") or detail.get("application_period")
            ),
            "list_status": self._status(row.get("btnRceptSttusCd")),
            "venue": venue,
            "audience": audience,
            "price": price_text,
            "contact": clean_text(detail.get("contact")),
            "application_method": application_method,
            "application_type": application_type,
        }
        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=sequence,
            title=title,
            detail_url=self._canonical_detail(self.config.museum_code, sequence),
            provider_name=self.config.museum_name,
            category="박물관 교육·체험",
            description=" · ".join(part for part in description_parts if part) or None,
            event_start=event_start,
            event_end=event_end,
            apply_start=apply_start,
            apply_end=apply_end,
            status=self._status(row.get("btnRceptSttusCd")),
            age_text=age_text,
            age_min=age_min,
            age_max=age_max,
            price_text=price_text,
            price_min=price_min,
            venue_name=venue or self.config.museum_name,
            address=self.config.address,
            region="경기도 수원시",
            latitude=None,
            longitude=None,
            image_url=None,
            phone=self._phone(detail.get("contact")),
            is_online="온라인" in f"{title} {venue or ''}",
            child_relevance_score=child_relevance(title, age_text, audience),
            license_code=self.info.license_code,
            fetched_at=datetime.now(KST),
            raw=raw,
        )

    def crawl(self, client: PoliteHttpClient, window: CrawlWindow) -> Iterable[Event]:
        client.assert_html_allowed(self.LIST_ENDPOINT)
        seen: set[str] = set()
        for page in range(1, window.max_pages + 1):
            payload = client.post_json(
                self.LIST_ENDPOINT,
                data={
                    "pageIndex": page,
                    "museumCd": self.config.museum_code,
                    "searchTabType": "ING",
                },
            )
            rows, total_pages = self.parse_page(payload)
            for row in rows:
                museum_code = clean_text(row.get("museumCd"))
                sequence = clean_text(row.get("progrmSeq"))
                title = clean_text(row.get("progrmNm"))
                if (
                    museum_code != self.config.museum_code
                    or not sequence
                    or sequence in seen
                    or not re.fullmatch(r"\d{1,20}", sequence)
                    or not title
                    or not self._list_candidate(title, row.get("partcptTrget"))
                ):
                    continue
                detail_url = self._canonical_detail(museum_code, sequence)
                client.assert_html_allowed(detail_url)
                detail = self.parse_detail_html(client.get_text(detail_url))
                event = self._map(row, detail)
                seen.add(sequence)
                if event is not None and self._overlaps(event, window):
                    yield event
            if page >= total_pages or not rows:
                break


def builtin_suwon_museum_sources() -> list[SuwonMuseumProgramSource]:
    return [SuwonMuseumProgramSource(config) for config in SUWON_MUSEUM_CONFIGS]


__all__ = [
    "SUWON_MUSEUM_CONFIGS",
    "SuwonMuseumConfig",
    "SuwonMuseumProgramSource",
    "builtin_suwon_museum_sources",
]
