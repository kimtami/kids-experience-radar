from __future__ import annotations

from datetime import datetime
from html import unescape
import hashlib
import os
from typing import Iterable
from urllib.parse import parse_qs, urlparse

from ..http import PoliteHttpClient
from ..models import CrawlWindow, Event
from ..normalizers import (
    KST,
    child_relevance,
    clean_text,
    parse_age_range,
    parse_date_range,
    parse_datetime,
    parse_price,
    safe_float,
)
from .base import Source, SourceInfo


class SeoulOpenDataSource(Source):
    BASE_URL = "http://openapi.seoul.go.kr:8088"

    def __init__(self, *, service: str, source_id: str, name: str, mode: str) -> None:
        self.service = service
        self.mode = mode
        self.info = SourceInfo(
            source_id=source_id,
            name=name,
            owner="서울특별시",
            source_type="open_api",
            official_url=(
                "https://data.seoul.go.kr/dataList/OA-15486/A/1/datasetView.do"
                if mode == "event"
                else "https://www.data.go.kr/data/15134352/openapi.do"
            ),
            license_code="KOGL-1",
            requires_key="SEOUL_OPEN_DATA_KEY (sample key works with 5 rows)",
            enabled_by_default=True,
            notes="Official API. The sample key is intentionally limited to five rows.",
        )

    @property
    def api_key(self) -> str:
        return os.getenv("SEOUL_OPEN_DATA_KEY", "").strip() or "sample"

    def crawl(self, client: PoliteHttpClient, window: CrawlWindow) -> Iterable[Event]:
        key = self.api_key
        page_size = 5 if key == "sample" else 200
        max_pages = 1 if key == "sample" else window.max_pages
        for page in range(max_pages):
            start = page * page_size + 1
            end = start + page_size - 1
            url = f"{self.BASE_URL}/{key}/json/{self.service}/{start}/{end}/"
            payload = client.get_json(url)
            envelope = payload.get(self.service) or {}
            result = envelope.get("RESULT") or {}
            if result.get("CODE") not in (None, "INFO-000"):
                raise RuntimeError(f"Seoul API error {result.get('CODE')}: {result.get('MESSAGE')}")
            rows = envelope.get("row") or []
            if not rows:
                break
            for row in rows:
                event = self._map_event(row) if self.mode == "event" else self._map_reservation(row)
                if self._overlaps_window(event, window):
                    yield event
            total = int(envelope.get("list_total_count") or len(rows))
            if end >= total:
                break

    @staticmethod
    def _overlaps_window(event: Event, window: CrawlWindow) -> bool:
        if event.event_start is None and event.event_end is None:
            return True
        start = event.event_start or event.event_end
        end = event.event_end or event.event_start
        assert start is not None and end is not None
        return start <= window.end and end >= window.start

    def _map_reservation(self, row: dict) -> Event:
        title = clean_text(unescape(str(row.get("SVCNM") or ""))) or "제목 없음"
        description = clean_text(row.get("DTLCONT"))
        age_min, age_max, age_text = parse_age_range(row.get("USETGTINFO"))
        price_min, price_text = parse_price(row.get("PAYATNM"))
        event_start = parse_datetime(row.get("SVCOPNBGNDT"))
        event_end = parse_datetime(row.get("SVCOPNENDDT"), end_of_day=True)
        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=str(row.get("SVCID") or row.get("SVCURL") or title),
            title=title,
            detail_url=str(row.get("SVCURL") or "https://yeyak.seoul.go.kr"),
            provider_name=clean_text(row.get("PLACENM")),
            category=" / ".join(
                value for value in (clean_text(row.get("MAXCLASSNM")), clean_text(row.get("MINCLASSNM"))) if value
            ) or None,
            description=description,
            event_start=event_start,
            event_end=event_end,
            apply_start=parse_datetime(row.get("RCPTBGNDT")),
            apply_end=parse_datetime(row.get("RCPTENDDT"), end_of_day=True),
            status=clean_text(row.get("SVCSTATNM")),
            age_text=age_text,
            age_min=age_min,
            age_max=age_max,
            price_text=price_text,
            price_min=price_min,
            venue_name=clean_text(row.get("PLACENM")),
            region=clean_text(row.get("AREANM")),
            latitude=safe_float(row.get("Y")),
            longitude=safe_float(row.get("X")),
            image_url=str(row.get("IMGURL")) if row.get("IMGURL") else None,
            phone=clean_text(row.get("TELNO")),
            is_online=any(
                token in (title + " " + (description or "")).casefold()
                for token in ("온라인", "비대면", "zoom", "줌")
            ),
            child_relevance_score=child_relevance(title, age_text, description),
            license_code=self.info.license_code,
            fetched_at=datetime.now(KST),
            raw=row,
        )

    def _map_event(self, row: dict) -> Event:
        title = clean_text(row.get("TITLE")) or "제목 없음"
        description = clean_text(" ".join(str(row.get(key) or "") for key in ("PROGRAM", "ETC_DESC")))
        age_min, age_max, age_text = parse_age_range(row.get("USE_TRGT"))
        price_min, price_text = parse_price(row.get("USE_FEE") or row.get("IS_FREE"))
        event_start = parse_datetime(row.get("STRTDATE"))
        event_end = parse_datetime(row.get("END_DATE"), end_of_day=True)
        if not event_start:
            event_start, fallback_end = parse_date_range(row.get("DATE"))
            event_end = event_end or fallback_end
        detail_url = str(row.get("HMPG_ADDR") or row.get("ORG_LINK") or "https://culture.seoul.go.kr")
        query = parse_qs(urlparse(detail_url).query)
        external_id = (query.get("cultcode") or query.get("seq") or [None])[0]
        if not external_id:
            external_id = hashlib.sha256(detail_url.encode("utf-8")).hexdigest()[:20]
        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=external_id,
            title=title,
            detail_url=detail_url,
            provider_name=clean_text(row.get("ORG_NAME")),
            category=clean_text(row.get("CODENAME")),
            description=description,
            event_start=event_start,
            event_end=event_end,
            status="예정/진행",
            age_text=age_text,
            age_min=age_min,
            age_max=age_max,
            price_text=price_text,
            price_min=price_min,
            venue_name=clean_text(row.get("PLACE")),
            region=clean_text(row.get("GUNAME")),
            latitude=safe_float(row.get("LAT")),
            longitude=safe_float(row.get("LOT")),
            image_url=str(row.get("MAIN_IMG")) if row.get("MAIN_IMG") else None,
            phone=clean_text(row.get("INQUIRY")),
            child_relevance_score=child_relevance(title, age_text, description),
            license_code=self.info.license_code,
            fetched_at=datetime.now(KST),
            raw=row,
        )


def builtin_seoul_sources() -> list[SeoulOpenDataSource]:
    return [
        SeoulOpenDataSource(
            service="ListPublicReservationCulture",
            source_id="seoul_reservation_culture",
            name="서울시 문화체험 공공서비스예약",
            mode="reservation",
        ),
        SeoulOpenDataSource(
            service="ListPublicReservationEducation",
            source_id="seoul_reservation_education",
            name="서울시 교육 공공서비스예약",
            mode="reservation",
        ),
        SeoulOpenDataSource(
            service="culturalEventInfo",
            source_id="seoul_cultural_events",
            name="서울문화포털 문화행사",
            mode="event",
        ),
    ]
