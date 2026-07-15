from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
import re
from typing import Any
from urllib.parse import urljoin

from ..http import PoliteHttpClient
from ..models import CrawlWindow, Event
from ..normalizers import KST, child_relevance, clean_text, parse_age_range, parse_datetime
from ..policy import explicit_source_approval
from .base import Source, SourceInfo


class KimchikanSource(Source):
    """Read children's class programs and schedules from Museum Kimchikan."""

    PROGRAMS_ENDPOINT = "https://kimchikan.com/rsv/programs"
    CALENDAR_ENDPOINT = "https://kimchikan.com/rsv/schedules/calendar"
    RESERVATION_PAGE = "https://kimchikan.com/rsv"
    ADDRESS = "서울특별시 종로구 인사동길 35-4"

    def __init__(self) -> None:
        self.info = SourceInfo(
            source_id="museum_kimchikan_children",
            name="뮤지엄김치간 어린이김치학교",
            owner="뮤지엄김치간",
            source_type="public_json_api",
            official_url=self.RESERVATION_PAGE,
            license_code=None,
            enabled_by_default=False,
            policy_status="reviewed_public_json",
            notes=(
                "Public JSON; robots.txt Allow: /. Read-only GET access is limited to the "
                "program list and schedule calendar. No booking, login, or individual "
                "application API is called."
            ),
        )

    def available(self) -> tuple[bool, str | None]:
        return explicit_source_approval(self.info.source_id)

    def crawl(self, client: PoliteHttpClient, window: CrawlWindow) -> Iterable[Event]:
        program_payload = client.get_json(
            self.PROGRAMS_ENDPOINT,
            params={"page": 1, "size": 50, "keyword": "어린이", "language": "ko"},
        )
        for program in self.parse_programs(program_payload):
            if not self._is_child_program(program):
                continue
            program_code = clean_text(program.get("programCode"))
            if not program_code:
                continue

            schedule_payload = client.get_json(
                self.CALENDAR_ENDPOINT,
                params={
                    "programCode": program_code,
                    "start": window.start.date().isoformat(),
                    "end": window.end.date().isoformat(),
                },
            )
            for schedule in self.parse_schedules(schedule_payload):
                # The live calendar sometimes returns FullCalendar display/background
                # summaries. Those are not individual sessions and carry no schSeq.
                if clean_text(schedule.get("schSeq")) is None:
                    continue
                event = self._map_schedule(program, schedule)
                if event is not None:
                    yield event

    @classmethod
    def parse_programs(cls, payload: object) -> list[dict[str, Any]]:
        return cls._parse_records(payload, identity_key="programCode")

    @classmethod
    def parse_schedules(cls, payload: object) -> list[dict[str, Any]]:
        return cls._parse_records(payload, identity_key="schSeq")

    @classmethod
    def _parse_records(
        cls,
        payload: object,
        *,
        identity_key: str,
    ) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [dict(row) for row in payload if isinstance(row, Mapping)]
        if not isinstance(payload, Mapping):
            raise RuntimeError("Kimchikan malformed response: expected an object or list")

        cls._raise_response_error(payload)
        if identity_key in payload:
            return [dict(payload)]

        for key in ("content", "data", "items", "schedules"):
            if key not in payload:
                continue
            value = payload.get(key)
            if value in (None, ""):
                return []
            if isinstance(value, list):
                return [dict(row) for row in value if isinstance(row, Mapping)]
            if isinstance(value, Mapping):
                if identity_key in value:
                    return [dict(value)]
                return cls._parse_records(value, identity_key=identity_key)
            raise RuntimeError(f"Kimchikan malformed response: {key} is not an object or list")
        return []

    @staticmethod
    def _raise_response_error(payload: Mapping[str, object]) -> None:
        success = payload.get("success")
        status = payload.get("status")
        try:
            status_code = int(str(status).strip()) if status is not None else None
        except (TypeError, ValueError):
            status_code = None

        if success is False:
            message = clean_text(payload.get("message") or payload.get("error")) or "unknown error"
            raise RuntimeError(f"Kimchikan API error: {message}")
        if status_code is not None and status_code >= 400:
            message = clean_text(payload.get("error") or payload.get("message")) or "unknown error"
            raise RuntimeError(f"Kimchikan API error {status_code}: {message}")
        if payload.get("error") not in (None, "", False):
            message = clean_text(payload.get("error")) or "unknown error"
            raise RuntimeError(f"Kimchikan API error: {message}")

    @classmethod
    def _is_child_program(cls, program: Mapping[str, object]) -> bool:
        text_parts = [
            clean_text(program.get("programName")),
            clean_text(program.get("programContent")),
        ]
        for info in cls._mapping_list(program.get("infoList")):
            text_parts.extend(
                (
                    clean_text(info.get("infoTitle")),
                    clean_text(info.get("parsedInfoContent") or info.get("infoContent")),
                )
            )
        text = " ".join(part for part in text_parts if part)
        if any(token in text for token in ("어린이", "아동", "초등", "키즈", "가족")):
            return True
        age_min, age_max, _ = cls._age_details(program)
        return age_min is not None and age_max is not None and age_max <= 18

    def _map_schedule(
        self,
        program: Mapping[str, object],
        schedule: Mapping[str, object],
    ) -> Event | None:
        program_code = clean_text(program.get("programCode"))
        schedule_sequence = clean_text(schedule.get("schSeq"))
        title = clean_text(program.get("programName"))
        if not program_code or not schedule_sequence or not title:
            return None

        age_min, age_max, age_text = self._age_details(program)
        description = self._description(program)
        guardian_fee = self._int_value(program.get("guardianFee")) or 0
        price_text = "어린이 무료"
        if guardian_fee > 0:
            price_text += f" · 보호자 입장료 1인 {guardian_fee:,}원"

        remain = self._int_value(schedule.get("remainCnt"))
        if self._truthy(schedule.get("isClosed")) or (remain is not None and remain <= 0):
            status = "마감"
        elif remain is not None:
            status = f"예약 가능 · 잔여 {remain}명"
        else:
            status = "예약 가능"

        image_path = clean_text(program.get("programPhoto"))
        image_url = urljoin("https://kimchikan.com/", image_path) if image_path else None

        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=f"{program_code}{schedule_sequence}",
            title=title,
            detail_url=self.RESERVATION_PAGE,
            provider_name="뮤지엄김치간",
            category="체험·교육",
            description=description,
            event_start=self._schedule_datetime(schedule.get("schDate"), schedule.get("startTime")),
            event_end=self._schedule_datetime(schedule.get("schDate"), schedule.get("endTime")),
            apply_start=parse_datetime(schedule.get("openDatetime")),
            apply_end=None,
            status=status,
            age_text=age_text,
            age_min=age_min,
            age_max=age_max,
            price_text=price_text,
            price_min=0,
            venue_name="뮤지엄김치간",
            address=self.ADDRESS,
            region="서울특별시",
            latitude=None,
            longitude=None,
            image_url=image_url,
            child_relevance_score=child_relevance(title, age_text, description),
            license_code=self.info.license_code,
            fetched_at=datetime.now(KST),
            raw={"program": dict(program), "schedule": dict(schedule)},
        )

    @classmethod
    def _age_details(
        cls,
        program: Mapping[str, object],
    ) -> tuple[int | None, int | None, str | None]:
        age_text: str | None = None
        for info in cls._mapping_list(program.get("infoList")):
            title = clean_text(info.get("infoTitle")) or ""
            if "대상" in title or "연령" in title or "나이" in title:
                age_text = clean_text(info.get("parsedInfoContent") or info.get("infoContent"))
                if age_text:
                    break

        for detail in cls._mapping_list(program.get("targetDetailsList")):
            age_min = cls._positive_int(detail.get("minApplyAge"))
            age_max = cls._positive_int(detail.get("maxApplyAge"))
            if age_min is not None or age_max is not None:
                rendered = age_text
                if rendered is None and age_min is not None and age_max is not None:
                    rendered = f"{age_min}~{age_max}세"
                return age_min, age_max, rendered

        candidates = [age_text, clean_text(program.get("programName"))]
        for candidate in candidates:
            if not candidate:
                continue
            match = re.search(r"(?:\[)?(\d{1,2})\s*(?:~|[-–])\s*(\d{1,2})\s*(?:세|\])", candidate)
            if match:
                return int(match.group(1)), int(match.group(2)), age_text or candidate

        combined = " ".join(candidate for candidate in candidates if candidate)
        return parse_age_range(combined)

    @classmethod
    def _description(cls, program: Mapping[str, object]) -> str | None:
        parts: list[str] = []
        content = clean_text(program.get("programContent"))
        if content:
            parts.append(content)
        for info in cls._mapping_list(program.get("infoList")):
            title = clean_text(info.get("infoTitle"))
            value = clean_text(info.get("parsedInfoContent") or info.get("infoContent"))
            if title and value:
                parts.append(f"{title}: {value}")
            elif value:
                parts.append(value)
        min_count = cls._int_value(program.get("minCnt"))
        max_count = cls._int_value(program.get("maxCnt"))
        if min_count is not None and max_count is not None and not any("정원:" in part for part in parts):
            parts.append(f"정원: 최소 {min_count}명 ~ 최대 {max_count}명")
        return " · ".join(parts) or None

    @staticmethod
    def _mapping_list(value: object) -> list[Mapping[str, object]]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
        if isinstance(value, Mapping):
            return [value]
        return []

    @staticmethod
    def _schedule_datetime(date_value: object, time_value: object) -> datetime | None:
        date_text = clean_text(date_value)
        time_text = clean_text(time_value)
        if not date_text:
            return None
        if not time_text:
            return parse_datetime(date_text)
        if re.fullmatch(r"\d{4}", time_text):
            time_text = f"{time_text[:2]}:{time_text[2:]}"
        elif re.fullmatch(r"\d{6}", time_text):
            time_text = f"{time_text[:2]}:{time_text[2:4]}:{time_text[4:]}"
        return parse_datetime(f"{date_text}T{time_text}")

    @staticmethod
    def _truthy(value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        text = clean_text(value)
        return (text or "").casefold() in {"y", "yes", "true", "1", "closed", "마감"}

    @staticmethod
    def _int_value(value: object) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(str(value).replace(",", "").strip())
        except (TypeError, ValueError):
            return None

    @classmethod
    def _positive_int(cls, value: object) -> int | None:
        parsed = cls._int_value(value)
        return parsed if parsed is not None and parsed > 0 else None


MuseumKimchikanSource = KimchikanSource
