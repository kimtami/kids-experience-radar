from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
import math
import re
from typing import Any
from urllib.parse import urlencode

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


@dataclass(frozen=True, slots=True)
class KywaCenter:
    code: str
    slug: str
    source_slug: str
    name: str
    region: str


KYWA_CENTERS: tuple[KywaCenter, ...] = (
    KywaCenter("2", "nyc", "central", "국립중앙청소년수련원", "충청남도 천안시"),
    KywaCenter("3", "pnyc", "pyeongchang", "국립평창청소년수련원", "강원특별자치도 평창군"),
    KywaCenter("4", "nysc", "space", "국립청소년우주센터", "전라남도 고흥군"),
    KywaCenter("6", "nyac", "bio", "국립청소년바이오생명센터", "전북특별자치도 김제시"),
    KywaCenter("7", "nyoc", "ocean", "국립청소년해양센터", "경상북도 영덕군"),
    KywaCenter("8", "nyfc", "future_environment", "국립청소년미래환경센터", "경상북도 봉화군"),
    KywaCenter("13", "nyec", "ecology", "국립청소년생태센터", "부산광역시"),
)


class KywaCampSource(Source):
    """Collect public camp-list facts without entering the reservation flow."""

    LIST_URL = "https://booking.kywa.or.kr/reservation/campReservationList.do"
    LIST_ENDPOINT = (
        "https://booking.kywa.or.kr/reservation/ajax/campReservationList.do"
    )
    DETAIL_URL = "https://booking.kywa.or.kr/reservation/campReservationView.do"
    PROGRAM_TYPES = "3101,3131,3151"
    TYPE_NAMES = {
        "3101": "특성화캠프",
        "3131": "가족캠프",
        "3151": "기획캠프",
    }
    STATUS_NAMES = {
        "3201": "모집준비",
        "3202": "접수중",
        "3209": "캠프종료",
    }
    PUBLIC_RAW_FIELDS = frozenset(
        {
            "center_code",
            "program_number",
            "program_type_code",
            "program_type",
            "status_code",
            "audience",
            "event_start",
            "event_end",
            "apply_start",
            "apply_end",
            "price_won",
            "capacity",
            "registered_count",
            "waiting_capacity",
            "phone",
        }
    )

    def __init__(self, center_code: str) -> None:
        try:
            self.center = next(
                center for center in KYWA_CENTERS if center.code == center_code
            )
        except StopIteration as exc:
            raise ValueError(f"unknown KYWA center: {center_code}") from exc
        self.info = SourceInfo(
            source_id=f"kywa_{self.center.source_slug}_camp_programs",
            name=f"{self.center.name} 공개 캠프",
            owner="한국청소년활동진흥원",
            source_type="public_json",
            official_url=f"{self.LIST_URL}?center={self.center.slug}",
            license_code=None,
            enabled_by_default=False,
            policy_status="reviewed_public_json",
            notes=(
                "Public camp-list JSON only after a runtime robots check. "
                "The crawler never fetches login, application, payment, waiting-list, "
                "or reservation-submission endpoints; the public detail URL is stored only."
            ),
        )

    @classmethod
    def all_sources(cls) -> list[KywaCampSource]:
        return [cls(center.code) for center in KYWA_CENTERS]

    @staticmethod
    def _safe_code(value: object | None) -> str | None:
        text = clean_text(value)
        if not text or not re.fullmatch(r"[0-9A-Za-z_-]{1,80}", text):
            return None
        return text

    @staticmethod
    def _safe_int(value: object | None) -> int | None:
        if value in (None, "") or isinstance(value, bool):
            return None
        try:
            parsed = int(float(str(value).replace(",", "").strip()))
        except (TypeError, ValueError, OverflowError):
            return None
        return parsed if math.isfinite(parsed) and parsed >= 0 else None

    @classmethod
    def parse_page(cls, payload: object) -> tuple[list[dict[str, Any]], int]:
        if not isinstance(payload, Mapping):
            raise RuntimeError("KYWA camp response must be a JSON object")
        raw_rows = payload.get("resultList")
        pagination = payload.get("paginationInfo")
        if not isinstance(raw_rows, list) or not isinstance(pagination, Mapping):
            raise RuntimeError("KYWA camp response structure changed")
        rows = [dict(row) for row in raw_rows if isinstance(row, Mapping)]
        raw_total_pages = pagination.get("totalPageCount")
        try:
            total_pages = max(0, int(str(raw_total_pages)))
        except (TypeError, ValueError) as exc:
            raise RuntimeError("KYWA camp pagination is malformed") from exc
        if raw_rows and not rows:
            raise RuntimeError("KYWA camp response contains no valid rows")
        return rows, total_pages

    @classmethod
    def _public_raw(cls, row: Mapping[str, object]) -> dict[str, object]:
        program_type_code = clean_text(row.get("pgm_gb"))
        facts: dict[str, object | None] = {
            "center_code": clean_text(row.get("center_cd")),
            "program_number": clean_text(row.get("pgm_no")),
            "program_type_code": program_type_code,
            "program_type": cls.TYPE_NAMES.get(program_type_code or ""),
            "status_code": clean_text(row.get("state_gb")),
            "audience": clean_text(row.get("enter_nm")),
            "event_start": clean_text(row.get("open_from")),
            "event_end": clean_text(row.get("open_to")),
            "apply_start": clean_text(row.get("receive_from")),
            "apply_end": clean_text(row.get("receive_to")),
            "price_won": cls._safe_int(row.get("enter_amt")),
            "capacity": cls._safe_int(row.get("target_cnt")),
            "registered_count": cls._safe_int(row.get("ing_cnt")),
            "waiting_capacity": cls._safe_int(row.get("wait_cnt")),
            "phone": clean_text(row.get("mng_tel")),
        }
        return {
            key: value
            for key, value in facts.items()
            if key in cls.PUBLIC_RAW_FIELDS and value is not None
        }

    def _map_row(self, row: Mapping[str, object]) -> Event | None:
        center_code = self._safe_code(row.get("center_cd"))
        program_number = self._safe_code(row.get("pgm_no"))
        program_type = self._safe_code(row.get("pgm_gb"))
        title = clean_text(row.get("pgm_nm"))
        if (
            center_code != self.center.code
            or not program_number
            or not program_type
            or not title
        ):
            return None

        audience = clean_text(row.get("enter_nm"))
        age_min, age_max, age_text = parse_age_range(audience)
        price_won = self._safe_int(row.get("enter_amt"))
        price_value = f"{price_won:,}원" if price_won is not None else None
        price_min, price_text = parse_price(price_value)
        status_code = clean_text(row.get("state_gb"))
        detail_url = f"{self.DETAIL_URL}?{urlencode({'pgm_no': program_number, 'center_cd': center_code, 'pgm_gb': program_type})}"
        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=f"{center_code}:{program_number}:{program_type}",
            title=title,
            detail_url=detail_url,
            provider_name=self.center.name,
            category=self.TYPE_NAMES.get(program_type, "청소년 캠프"),
            event_start=parse_datetime(row.get("open_from")),
            event_end=parse_datetime(row.get("open_to"), end_of_day=True),
            apply_start=parse_datetime(row.get("receive_from")),
            apply_end=parse_datetime(row.get("receive_to"), end_of_day=True),
            status=self.STATUS_NAMES.get(status_code or "", status_code),
            age_text=age_text,
            age_min=age_min,
            age_max=age_max,
            price_text=price_text,
            price_min=price_min,
            venue_name=self.center.name,
            region=self.center.region,
            phone=clean_text(row.get("mng_tel")),
            child_relevance_score=child_relevance(title, age_text),
            fetched_at=datetime.now(KST),
            raw=self._public_raw(row),
        )

    @staticmethod
    def _child_candidate(event: Event) -> bool:
        text = f"{event.title} {event.age_text or ''}".casefold()
        if any(
            token in event.title.casefold()
            for token in ("숙소 이용", "숙소개방", "객실 이용", "생활관 이용")
        ):
            return False
        child_tokens = ("초등", "어린이", "아동", "가족", "키즈", "보호자")
        return any(token in text for token in child_tokens)

    @staticmethod
    def _overlaps(event: Event, window: CrawlWindow) -> bool:
        if event.event_start is None and event.event_end is None:
            return True
        start = event.event_start or event.event_end
        end = event.event_end or event.event_start
        assert start is not None and end is not None
        return start <= window.end and end >= window.start

    def crawl(self, client: PoliteHttpClient, window: CrawlWindow) -> Iterable[Event]:
        client.assert_html_allowed(self.info.official_url)
        for page in range(1, window.max_pages + 1):
            payload = client.post_json(
                self.LIST_ENDPOINT,
                data={
                    "multi_center_cd": self.center.code,
                    "multi_pgm_gb": self.PROGRAM_TYPES,
                    "pageIndex": page,
                },
            )
            rows, total_pages = self.parse_page(payload)
            for row in rows:
                event = self._map_row(row)
                if (
                    event is not None
                    and self._child_candidate(event)
                    and self._overlaps(event, window)
                ):
                    yield event
            if not rows or page >= total_pages:
                break


__all__ = ["KYWA_CENTERS", "KywaCampSource"]
