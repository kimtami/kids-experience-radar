from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
import hashlib
import os
from typing import Any
from urllib.parse import quote_plus, unquote

from ..http import PoliteHttpClient
from ..models import CrawlWindow, Event
from ..normalizers import KST, child_relevance, clean_text, parse_datetime, safe_float
from .base import Source, SourceInfo


class TourApiFestivalSource(Source):
    """Collect Korean festival records from the official TourAPI 4.0 API."""

    ENDPOINT = "https://apis.data.go.kr/B551011/KorService2/searchFestival2"
    PORTAL_SEARCH_URL = "https://korean.visitkorea.or.kr/search/search_list.do"
    PAGE_SIZE = 100
    SUCCESS_CODES = {"", "0", "00", "0000", "INFO-000"}

    def __init__(self) -> None:
        self.info = SourceInfo(
            source_id="tour_api_festivals",
            name="TourAPI 4.0 국문 축제",
            owner="한국관광공사",
            source_type="open_api",
            official_url="https://www.data.go.kr/data/15101578/openapi.do",
            license_code="OPEN-DATA-NO-RESTRICTION",
            requires_key="DATA_GO_KR_SERVICE_KEY",
            enabled_by_default=False,
            notes=(
                "Official JSON API. The response has no stable event homepage/detail URL, "
                "so detail_url points to the official VisitKorea search results for the title. "
                "Image reuse conditions must be checked per record."
            ),
        )

    @property
    def service_key(self) -> str:
        return unquote(os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip())

    def available(self) -> tuple[bool, str | None]:
        if not self.service_key:
            return False, "DATA_GO_KR_SERVICE_KEY is not set"
        return True, None

    def crawl(self, client: PoliteHttpClient, window: CrawlWindow) -> Iterable[Event]:
        if not self.service_key:
            raise RuntimeError("DATA_GO_KR_SERVICE_KEY is required")

        for page in range(1, window.max_pages + 1):
            params: dict[str, object] = {
                "serviceKey": self.service_key,
                "MobileOS": "ETC",
                "MobileApp": "KidsExperienceRadar",
                "_type": "json",
                "eventStartDate": window.start.strftime("%Y%m%d"),
                "eventEndDate": window.end.strftime("%Y%m%d"),
                "numOfRows": self.PAGE_SIZE,
                "pageNo": page,
            }
            payload = client.get_json(self.ENDPOINT, params=params)
            rows, total = self.parse_page(payload)
            if not rows:
                break

            for row in rows:
                yield self._map_row(row)

            if page * self.PAGE_SIZE >= total:
                break

    @classmethod
    def parse_page(cls, payload: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
        if not isinstance(payload, Mapping):
            raise RuntimeError("TourAPI malformed response: expected an object")

        response: object = payload.get("response")
        if not isinstance(response, Mapping):
            response = payload if "header" in payload or "body" in payload else None
        if not isinstance(response, Mapping):
            service_error = payload.get("OpenAPI_ServiceResponse")
            if isinstance(service_error, Mapping):
                message = cls._service_error_message(service_error)
                raise RuntimeError(f"TourAPI error: {message}")
            raise RuntimeError("TourAPI malformed response: missing response object")

        header = response.get("header")
        if not isinstance(header, Mapping):
            header = {}
        result_code = clean_text(
            header.get("resultCode")
            or header.get("resultcode")
            or response.get("resultCode")
        )
        if result_code is not None and result_code not in cls.SUCCESS_CODES:
            message = clean_text(
                header.get("resultMsg")
                or header.get("resultmsg")
                or response.get("resultMsg")
            ) or "unknown error"
            raise RuntimeError(f"TourAPI error {result_code}: {message}")

        body = response.get("body")
        if body in (None, ""):
            return [], 0
        if not isinstance(body, Mapping):
            raise RuntimeError("TourAPI malformed response: body is not an object")

        items = body.get("items")
        if isinstance(items, Mapping):
            raw_items: object = items.get("item")
        elif isinstance(items, list):
            raw_items = items
        else:
            raw_items = None

        if isinstance(raw_items, Mapping):
            candidates = [raw_items]
        elif isinstance(raw_items, list):
            candidates = raw_items
        else:
            candidates = []
        rows = [dict(item) for item in candidates if isinstance(item, Mapping)]

        total_raw = body.get("totalCount")
        try:
            total = max(0, int(str(total_raw).strip()))
        except (TypeError, ValueError):
            total = len(rows)
        return rows, total

    @staticmethod
    def _service_error_message(service_error: Mapping[str, object]) -> str:
        header = service_error.get("cmmMsgHeader")
        if not isinstance(header, Mapping):
            return "unknown service error"
        return clean_text(
            header.get("errMsg")
            or header.get("returnAuthMsg")
            or header.get("returnReasonCode")
        ) or "unknown service error"

    def _map_row(self, row: dict[str, Any]) -> Event:
        title = clean_text(row.get("title")) or "제목 없음"
        content_id = clean_text(row.get("contentid")) or hashlib.sha256(
            "|".join(
                clean_text(row.get(key)) or ""
                for key in ("title", "eventstartdate", "eventenddate", "addr1")
            ).encode("utf-8")
        ).hexdigest()[:20]
        address = clean_text(row.get("addr1"))
        detail_url = f"{self.PORTAL_SEARCH_URL}?keyword={quote_plus(title)}"

        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=content_id,
            title=title,
            detail_url=detail_url,
            category="축제",
            event_start=parse_datetime(row.get("eventstartdate")),
            event_end=parse_datetime(row.get("eventenddate"), end_of_day=True),
            status="예정/진행",
            address=address,
            region=address.split(maxsplit=1)[0] if address else None,
            longitude=safe_float(row.get("mapx")),
            latitude=safe_float(row.get("mapy")),
            image_url=clean_text(row.get("firstimage")),
            phone=clean_text(row.get("tel")),
            child_relevance_score=child_relevance(title, None),
            license_code=self.info.license_code,
            fetched_at=datetime.now(KST),
            raw=row,
        )


TourFestivalSource = TourApiFestivalSource

__all__ = ["TourApiFestivalSource", "TourFestivalSource"]
