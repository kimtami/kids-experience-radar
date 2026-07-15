from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, time
import re
from typing import Any
from urllib.parse import urlencode, urlparse

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


class GyeonggiLibraryProgramSource(Source):
    """Collect child and family programs from Gyeonggi Library's public JSON."""

    LIST_ENDPOINT = "https://www.library.kr/api/homepageprogramlist"
    DETAIL_ENDPOINT = "https://www.library.kr/api/homepageprogramdetail"
    LIST_PAGE_URL = "https://www.library.kr/ggl/community/events/program-list"
    DETAIL_PAGE_BASE = (
        "https://www.library.kr/ggl/community/events/program-detail"
    )
    MANAGE_CODE = "141674"
    PAGE_SIZE = 100
    ADDRESS = "경기도 수원시 영통구 도청로 40"
    REQUIRED_PROGRAM_FIELDS = frozenset(
        {
            "REC_KEY",
            "PROGRAM_TITLE",
            "PROGRAM_START_DATE",
            "PROGRAM_END_DATE",
            "PROGRAM_STATUS",
            "PROGRAM_FEE",
            "MATERIAL_COST_YN",
            "ONLY_OFFLINE_YN",
            "ONLINE_CLOSED",
        }
    )
    YN_FIELDS = ("MATERIAL_COST_YN", "ONLY_OFFLINE_YN", "ONLINE_CLOSED")
    MAX_PUBLIC_TEXT_LENGTH = 100_000
    PUBLIC_RAW_FIELDS = frozenset(
        {
            "REC_KEY",
            "PROGRAM_TITLE",
            "PROGRAM_TARGET",
            "PROGRAM_FACILITY_NAME",
            "PROGRAM_START_DATE",
            "PROGRAM_END_DATE",
            "PROGRAM_START_TIME",
            "PROGRAM_END_TIME",
            "PROGRAM_APPLY_START_DATE",
            "PROGRAM_APPLY_END_DATE",
            "PROGRAM_STATUS",
            "PROGRAM_DAYS",
            "PROGRAM_FEE",
            "MATERIAL_COST_YN",
            "MATERIAL_COST",
            "PROGRAM_SUB_CATEGORY_DESC",
            "RECRUITMENT_PERSONNEL_CNT",
            "ONLINE_RECRUITMENT_CNT",
            "NOW_ONLINE_APPLY_CNT",
            "WAITING_PERSONNEL_CNT",
            "NOW_ONLINE_WAITING_CNT",
            "ONLY_OFFLINE_YN",
            "ONLINE_CLOSED",
            "THUMBNAIL_PATH",
        }
    )
    CHILD_TOKENS = (
        "초등",
        "어린이",
        "아동",
        "유아",
        "가족",
        "보호자",
        "자녀",
        "키즈",
        "청소년",
        "중학생",
        "고등학생",
    )
    STATUS_TEXT = {
        "1": "접수중",
        "2": "대기접수",
        "3": "접수마감",
        "4": "종료",
        "5": "접수예정",
        "6": "추첨대기 접수",
    }

    def __init__(self) -> None:
        self.info = SourceInfo(
            source_id="gyeonggi_library_programs",
            name="경기도서관 어린이·가족 프로그램",
            owner="경기도서관",
            source_type="public_json",
            official_url=self.LIST_PAGE_URL,
            license_code=None,
            enabled_by_default=False,
            policy_status="reviewed_first_party_public_json",
            notes=(
                "First-party JSON used by the public Nuxt list and detail pages. "
                "Reads program metadata only; never calls checkparticipants, login, "
                "program-apply, reservation, applicant, payment, or queue paths. "
                "Unlicensed description prose is inspected transiently but not stored."
            ),
        )

    @staticmethod
    def parse_list_page(payload: object) -> tuple[list[dict[str, Any]], int]:
        if not isinstance(payload, Mapping):
            raise RuntimeError("Gyeonggi Library list malformed response: expected object")
        if str(payload.get("RESULT_CODE")) != "200":
            raise RuntimeError(
                "Gyeonggi Library list error: "
                f"RESULT_CODE={payload.get('RESULT_CODE', 'missing')}"
            )
        rows = payload.get("RESULT_LIST")
        if not isinstance(rows, list) or any(
            not isinstance(row, Mapping) for row in rows
        ):
            raise RuntimeError(
                "Gyeonggi Library list malformed response: RESULT_LIST is not an object array"
            )
        total_raw = payload.get("TOTAL_COUNT")
        try:
            total_count = int(str(total_raw))
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "Gyeonggi Library list malformed response: invalid TOTAL_COUNT"
            ) from exc
        if total_count < 0:
            raise RuntimeError(
                "Gyeonggi Library list malformed response: negative TOTAL_COUNT"
            )
        parsed_rows = [dict(row) for row in rows]
        for row in parsed_rows:
            GyeonggiLibraryProgramSource._validate_consumed_fields(
                row, context="list"
            )
            missing = sorted(
                field
                for field in GyeonggiLibraryProgramSource.REQUIRED_PROGRAM_FIELDS
                if field not in row or clean_text(row.get(field)) is None
            )
            if missing:
                raise RuntimeError(
                    "Gyeonggi Library list malformed response: missing required "
                    f"program fields {', '.join(missing)}"
                )
            GyeonggiLibraryProgramSource._validate_flags(
                row, context="list"
            )
        return parsed_rows, total_count

    @staticmethod
    def parse_detail(
        payload: object, *, expected_rec_key: str
    ) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise RuntimeError("Gyeonggi Library detail malformed response: expected object")
        if str(payload.get("RESULT_CODE")) != "100":
            raise RuntimeError(
                "Gyeonggi Library detail error: "
                f"RESULT_CODE={payload.get('RESULT_CODE', 'missing')}"
            )
        raw_detail = payload.get("RESULT_DATA")
        if not isinstance(raw_detail, Mapping):
            raise RuntimeError(
                "Gyeonggi Library detail malformed response: RESULT_DATA is not an object"
            )
        detail = dict(raw_detail)
        GyeonggiLibraryProgramSource._validate_consumed_fields(
            detail, context="detail"
        )
        actual_rec_key = str(detail.get("REC_KEY", ""))
        if not expected_rec_key.isdigit() or actual_rec_key != expected_rec_key:
            raise RuntimeError(
                "Gyeonggi Library detail malformed response: REC_KEY mismatch"
            )
        missing = sorted(
            field
            for field in GyeonggiLibraryProgramSource.REQUIRED_PROGRAM_FIELDS
            if field not in detail or clean_text(detail.get(field)) is None
        )
        if missing:
            raise RuntimeError(
                "Gyeonggi Library detail malformed response: missing required "
                f"program fields {', '.join(missing)}"
            )
        GyeonggiLibraryProgramSource._validate_flags(
            detail, context="detail"
        )
        return detail

    @classmethod
    def _validate_consumed_fields(
        cls, row: Mapping[str, Any], *, context: str
    ) -> None:
        for field in cls.PUBLIC_RAW_FIELDS | {"PROGRAM_DESC", "PROGRAM_DESC_TEXT"}:
            if field not in row or row[field] is None:
                continue
            value = row[field]
            if isinstance(value, bool) or not isinstance(value, (str, int, float)):
                raise RuntimeError(
                    f"Gyeonggi Library {context} malformed response: "
                    f"non-scalar {field}"
                )
            if isinstance(value, str) and len(value) > cls.MAX_PUBLIC_TEXT_LENGTH:
                raise RuntimeError(
                    f"Gyeonggi Library {context} malformed response: "
                    f"oversized {field}"
                )

    @classmethod
    def _validate_flags(
        cls, row: Mapping[str, Any], *, context: str
    ) -> None:
        for field in cls.YN_FIELDS:
            value = clean_text(row.get(field))
            if value not in {"Y", "N"}:
                raise RuntimeError(
                    f"Gyeonggi Library {context} malformed response: invalid {field}"
                )

        material_text = clean_text(row.get("MATERIAL_COST"))
        material_flag = clean_text(row.get("MATERIAL_COST_YN"))
        if material_text is None:
            if material_flag == "Y":
                raise RuntimeError(
                    f"Gyeonggi Library {context} malformed response: "
                    "missing MATERIAL_COST while MATERIAL_COST_YN=Y"
                )
            return
        compact_material = re.sub(r"[,\s원]", "", material_text)
        if not compact_material.isdigit():
            raise RuntimeError(
                f"Gyeonggi Library {context} malformed response: invalid MATERIAL_COST"
            )
        if material_flag == "N" and int(compact_material) != 0:
            raise RuntimeError(
                f"Gyeonggi Library {context} malformed response: "
                "nonzero MATERIAL_COST while MATERIAL_COST_YN=N"
            )

    @classmethod
    def _is_child_program(cls, row: Mapping[str, Any]) -> bool:
        target = (clean_text(row.get("PROGRAM_TARGET")) or "").casefold()
        target = target.replace("어린이집", "")
        adult_only_target = any(
            token in target
            for token in ("성인", "교사", "교원", "강사", "전문가", "직원")
        ) and not any(token in target for token in cls.CHILD_TOKENS)
        if adult_only_target:
            return False
        haystack = " ".join(
            text
            for field in ("PROGRAM_TITLE", "PROGRAM_TARGET", "PROGRAM_DESC_TEXT")
            if (text := clean_text(row.get(field)))
        ).casefold()
        # "어린이집 교사" is an adult-professional audience, not a child audience.
        haystack = haystack.replace("어린이집", "")
        return any(token in haystack for token in cls.CHILD_TOKENS)

    @staticmethod
    def _positive_int_text(value: object | None, *, field: str) -> str:
        text = clean_text(value)
        if text is None or not text.isdigit() or int(text) <= 0:
            raise RuntimeError(
                f"Gyeonggi Library program malformed response: invalid {field}"
            )
        return text

    @staticmethod
    def _date_time(
        date_value: object | None,
        time_value: object | None,
        *,
        field: str,
        end_of_day: bool = False,
    ) -> datetime:
        date_part = parse_datetime(date_value)
        if date_part is None:
            raise RuntimeError(
                f"Gyeonggi Library program malformed response: invalid {field}"
            )
        time_text = clean_text(time_value)
        if time_text:
            match = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", time_text)
            if match is None:
                raise RuntimeError(
                    f"Gyeonggi Library program malformed response: invalid {field} time"
                )
            return datetime.combine(
                date_part.date(),
                time(int(match.group(1)), int(match.group(2))),
                tzinfo=KST,
            )
        return datetime.combine(
            date_part.date(), time.max if end_of_day else time.min, tzinfo=KST
        )

    @staticmethod
    def _age(value: object | None) -> tuple[int | None, int | None, str | None]:
        text = clean_text(value)
        if text is None:
            return None, None, None
        compact_range = re.search(
            r"(?<!\d)(\d{1,2})\s*(?:~|[-–])\s*(\d{1,2})\s*세",
            text,
        )
        if compact_range:
            first, last = (int(part) for part in compact_range.groups())
            return min(first, last), max(first, last), text
        return parse_age_range(text)

    @staticmethod
    def _price(row: Mapping[str, Any]) -> tuple[int | None, str | None]:
        fee = clean_text(row.get("PROGRAM_FEE"))
        if fee is None:
            price_text = None
        else:
            compact = re.sub(r"[,\s원]", "", fee)
            if compact.isdigit():
                amount = int(compact)
                price_text = "무료" if amount == 0 else f"{amount:,}원"
            else:
                price_text = fee

        material = clean_text(row.get("MATERIAL_COST"))
        material_enabled = clean_text(row.get("MATERIAL_COST_YN")) == "Y"
        if material_enabled and material:
            compact_material = re.sub(r"[,\s원]", "", material)
            if compact_material.isdigit() and int(compact_material) > 0:
                material_text = f"재료비 {int(compact_material):,}원 별도"
                price_text = (
                    f"{price_text} ({material_text})" if price_text else material_text
                )
        return parse_price(price_text)

    @classmethod
    def _status(cls, row: Mapping[str, Any]) -> str:
        code = clean_text(row.get("PROGRAM_STATUS"))
        if code not in cls.STATUS_TEXT:
            raise RuntimeError(
                "Gyeonggi Library program malformed response: unknown PROGRAM_STATUS"
            )
        status = cls.STATUS_TEXT[code]
        if clean_text(row.get("ONLY_OFFLINE_YN")) == "Y":
            return f"{status} · 오프라인 접수"
        if clean_text(row.get("ONLINE_CLOSED")) == "Y" and code in {"1", "2", "6"}:
            return "접수마감"
        return status

    @staticmethod
    def _phone(description: str | None) -> str | None:
        if not description:
            return None
        match = re.search(
            r"(?<!\d)(0\d{1,2})[-\s]?(\d{3,4})[-\s]?(\d{4})(?!\d)",
            description,
        )
        if match is None or match.group(1).startswith("01"):
            return None
        return "-".join(match.groups())

    @staticmethod
    def _image_url(value: object | None) -> str | None:
        url = clean_text(value)
        if not url:
            return None
        parsed = urlparse(url)
        if (
            parsed.scheme == "https"
            and parsed.netloc == "hcms.kdot.cloud"
            and parsed.path.startswith("/upload/")
            and not parsed.params
            and not parsed.query
            and not parsed.fragment
        ):
            return url
        return None

    @staticmethod
    def _overlaps(event: Event, window: CrawlWindow) -> bool:
        start = event.event_start or event.event_end
        end = event.event_end or event.event_start
        if start is None or end is None:
            return True
        return start <= window.end and end >= window.start

    @staticmethod
    def _policy_target(endpoint: str, params: Mapping[str, object]) -> str:
        return f"{endpoint}?{urlencode(params)}"

    @classmethod
    def _list_row_overlaps(
        cls, row: Mapping[str, Any], window: CrawlWindow
    ) -> bool:
        start = cls._date_time(
            row.get("PROGRAM_START_DATE"),
            row.get("PROGRAM_START_TIME"),
            field="PROGRAM_START_DATE",
        )
        end = cls._date_time(
            row.get("PROGRAM_END_DATE"),
            row.get("PROGRAM_END_TIME"),
            field="PROGRAM_END_DATE",
            end_of_day=True,
        )
        if end < start:
            raise RuntimeError(
                "Gyeonggi Library program malformed response: event end before start"
            )
        return start <= window.end and end >= window.start

    def _map_program(self, row: Mapping[str, Any]) -> Event:
        external_id = self._positive_int_text(row.get("REC_KEY"), field="REC_KEY")
        title = clean_text(row.get("PROGRAM_TITLE"))
        if title is None:
            raise RuntimeError(
                "Gyeonggi Library program malformed response: missing PROGRAM_TITLE"
            )
        description = clean_text(
            row.get("PROGRAM_DESC") or row.get("PROGRAM_DESC_TEXT")
        )
        target = clean_text(row.get("PROGRAM_TARGET"))
        age_min, age_max, age_text = self._age(target)
        price_min, price_text = self._price(row)
        event_start = self._date_time(
            row.get("PROGRAM_START_DATE"),
            row.get("PROGRAM_START_TIME"),
            field="PROGRAM_START_DATE",
        )
        event_end = self._date_time(
            row.get("PROGRAM_END_DATE"),
            row.get("PROGRAM_END_TIME"),
            field="PROGRAM_END_DATE",
            end_of_day=True,
        )
        if event_end < event_start:
            raise RuntimeError(
                "Gyeonggi Library program malformed response: event end before start"
            )
        apply_start = parse_datetime(row.get("PROGRAM_APPLY_START_DATE"))
        apply_end = parse_datetime(row.get("PROGRAM_APPLY_END_DATE"))
        if row.get("PROGRAM_APPLY_START_DATE") and apply_start is None:
            raise RuntimeError(
                "Gyeonggi Library program malformed response: invalid application start"
            )
        if row.get("PROGRAM_APPLY_END_DATE") and apply_end is None:
            raise RuntimeError(
                "Gyeonggi Library program malformed response: invalid application end"
            )
        if apply_start and apply_end and apply_end < apply_start:
            raise RuntimeError(
                "Gyeonggi Library program malformed response: application end before start"
            )

        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=external_id,
            title=title,
            detail_url=f"{self.DETAIL_PAGE_BASE}/{external_id}",
            provider_name="경기도서관",
            category=clean_text(row.get("PROGRAM_SUB_CATEGORY_DESC"))
            or "도서관 프로그램",
            # The unlicensed prose is inspected transiently for child relevance
            # and a public institutional phone, but is not copied into storage.
            description=None,
            event_start=event_start,
            event_end=event_end,
            apply_start=apply_start,
            apply_end=apply_end,
            status=self._status(row),
            age_text=age_text,
            age_min=age_min,
            age_max=age_max,
            price_text=price_text,
            price_min=price_min,
            venue_name=clean_text(row.get("PROGRAM_FACILITY_NAME")) or "경기도서관",
            address=self.ADDRESS,
            region="경기도 수원시",
            latitude=None,
            longitude=None,
            image_url=self._image_url(row.get("THUMBNAIL_PATH")),
            phone=self._phone(description),
            is_online=False,
            # Reaching this mapper means the dedicated source filter found
            # explicit child/family evidence.  Keep that evidence above the
            # store's default nearby-query floor even when the shared scorer
            # does not yet know a source-specific token such as "자녀".
            child_relevance_score=max(
                0.55, child_relevance(title, age_text, description)
            ),
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
        expected_total: int | None = None
        seen_list_ids: set[str] = set()
        for page_number in range(1, max(1, window.max_pages) + 1):
            list_params: dict[str, object] = {
                "manage_code": self.MANAGE_CODE,
                "search_type": "all",
                "search_text": "",
                "program_status": "0",
                "user_key": "",
                "display": self.PAGE_SIZE,
                "page_no": page_number,
                "orderby_item": "STATUS_PROGRAM_DATE",
                "orderby": "ASC",
            }
            client.assert_html_allowed(
                self._policy_target(self.LIST_ENDPOINT, list_params)
            )
            payload = client.post_json(
                self.LIST_ENDPOINT,
                params=list_params,
            )
            rows, total_count = self.parse_list_page(payload)
            if expected_total is None:
                expected_total = total_count
            elif total_count != expected_total:
                raise RuntimeError(
                    "Gyeonggi Library list malformed response: TOTAL_COUNT changed "
                    "during pagination"
                )

            remaining = expected_total - len(seen_list_ids)
            expected_page_size = min(self.PAGE_SIZE, max(0, remaining))
            if len(rows) != expected_page_size:
                direction = "short" if len(rows) < expected_page_size else "oversized"
                raise RuntimeError(
                    "Gyeonggi Library list malformed response: "
                    f"{direction} page {page_number}; expected "
                    f"{expected_page_size} rows, received {len(rows)}"
                )

            page_ids: list[str] = []
            for row in rows:
                external_id = self._positive_int_text(
                    row.get("REC_KEY"), field="REC_KEY"
                )
                if external_id in seen_list_ids or external_id in page_ids:
                    raise RuntimeError(
                        "Gyeonggi Library list malformed response: duplicate REC_KEY "
                        f"{external_id} during pagination"
                    )
                page_ids.append(external_id)
            seen_list_ids.update(page_ids)

            for list_row in rows:
                # The list already exposes authoritative dates.  Filter the
                # requested window before reading details so a daily run only
                # makes detail requests for relevant current/upcoming records.
                if not self._list_row_overlaps(list_row, window):
                    continue
                external_id = self._positive_int_text(
                    list_row.get("REC_KEY"), field="REC_KEY"
                )
                detail_params: dict[str, object] = {"rec_key": external_id}
                client.assert_html_allowed(
                    self._policy_target(self.DETAIL_ENDPOINT, detail_params)
                )
                detail_payload = client.post_json(
                    self.DETAIL_ENDPOINT,
                    params=detail_params,
                )
                detail = self.parse_detail(
                    detail_payload, expected_rec_key=external_id
                )
                merged = {**list_row, **detail}
                if not self._is_child_program(merged):
                    continue
                event = self._map_program(merged)
                if self._overlaps(event, window):
                    yield event
            if len(seen_list_ids) == expected_total:
                break
        if expected_total is not None and len(seen_list_ids) != expected_total:
            raise RuntimeError(
                "Gyeonggi Library list incomplete: max_pages exhausted with "
                f"{len(seen_list_ids)} of {expected_total} rows"
            )


__all__ = ["GyeonggiLibraryProgramSource"]
