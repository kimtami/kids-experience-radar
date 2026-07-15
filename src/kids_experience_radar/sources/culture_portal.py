from __future__ import annotations

from datetime import datetime
import hashlib
import os
from typing import Iterable
from urllib.parse import unquote
import xml.etree.ElementTree as ET

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


def _tag_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _first(row: dict[str, str], *aliases: str) -> str | None:
    lowered = {key.casefold(): value for key, value in row.items()}
    for alias in aliases:
        value = lowered.get(alias.casefold())
        if value not in (None, ""):
            return value
    return None


class CulturePortalSource(Source):
    ENDPOINT = "https://apis.data.go.kr/B553457/cultureinfo/period2"

    def __init__(self, *, service_type: str = "C") -> None:
        if service_type not in {"A", "B", "C"}:
            raise ValueError("service_type must be A, B, or C")
        self.service_type = service_type
        labels = {"A": "공연·전시", "B": "행사·축제", "C": "교육·체험"}
        self.info = SourceInfo(
            source_id=f"culture_portal_{service_type.casefold()}",
            name=f"문화포털 {labels[service_type]}",
            owner="한국문화정보원",
            source_type="open_api",
            official_url="https://www.data.go.kr/data/15138937/openapi.do",
            license_code="OPEN-DATA-NO-RESTRICTION",
            requires_key="DATA_GO_KR_SERVICE_KEY",
            enabled_by_default=False,
            notes="Official XML API; type C is education/experience.",
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
        page_size = 100
        for page in range(1, window.max_pages + 1):
            params = {
                "serviceKey": self.service_key,
                "PageNo": page,
                "numOfrows": page_size,
                "serviceTp": self.service_type,
                "from": window.start.strftime("%Y%m%d"),
                "to": window.end.strftime("%Y%m%d"),
            }
            xml_text = client.get_text(self.ENDPOINT, params=params)
            rows, total = self.parse_rows(xml_text)
            if not rows:
                break
            for row in rows:
                yield self._map_row(row)
            if page * page_size >= total:
                break

    @staticmethod
    def parse_rows(xml_text: str) -> tuple[list[dict[str, str]], int]:
        root = ET.fromstring(xml_text)
        result_code = next((el.text for el in root.iter() if _tag_name(el.tag).casefold() in {"resultcode", "code"}), None)
        if result_code and result_code not in {"00", "0", "INFO-000"}:
            message = next((el.text for el in root.iter() if _tag_name(el.tag).casefold() in {"resultmsg", "message"}), "unknown")
            raise RuntimeError(f"Culture Portal API error {result_code}: {message}")
        candidate_names = {"perforlist", "item"}
        rows: list[dict[str, str]] = []
        for element in root.iter():
            if _tag_name(element.tag).casefold() not in candidate_names:
                continue
            row = {
                _tag_name(child.tag): (child.text or "").strip()
                for child in list(element)
                if len(list(child)) == 0
            }
            if row:
                rows.append(row)
        total_raw = next(
            (el.text for el in root.iter() if _tag_name(el.tag).casefold() in {"totalcount", "totalcnt"}),
            None,
        )
        try:
            total = int(total_raw or len(rows))
        except ValueError:
            total = len(rows)
        return rows, total

    def _map_row(self, row: dict[str, str]) -> Event:
        title = clean_text(_first(row, "title", "subject", "eventNm", "name")) or "제목 없음"
        period = _first(row, "period", "date", "eventPeriod")
        event_start = parse_datetime(_first(row, "startDate", "startDt", "startdate"))
        event_end = parse_datetime(_first(row, "endDate", "endDt", "enddate"), end_of_day=True)
        if period and not event_start:
            event_start, fallback_end = parse_date_range(period)
            event_end = event_end or fallback_end
        age_min, age_max, age_text = parse_age_range(_first(row, "target", "useTrgt", "audience"))
        price_min, price_text = parse_price(_first(row, "price", "useFee", "fee"))
        detail_url = _first(row, "url", "placeUrl", "homepage", "link") or "https://www.culture.go.kr"
        external_id = _first(row, "seq", "id", "eventId") or hashlib.sha256(
            f"{title}|{period}|{detail_url}".encode("utf-8")
        ).hexdigest()[:20]
        description = clean_text(_first(row, "contents1", "contents", "description", "summary"))
        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=external_id,
            title=title,
            detail_url=detail_url,
            provider_name=clean_text(_first(row, "place", "organizer", "institution")),
            category=clean_text(_first(row, "realmName", "category", "serviceTp")),
            description=description,
            event_start=event_start,
            event_end=event_end,
            age_text=age_text,
            age_min=age_min,
            age_max=age_max,
            price_text=price_text,
            price_min=price_min,
            venue_name=clean_text(_first(row, "place", "venue")),
            address=clean_text(_first(row, "placeAddr", "address", "addr")),
            region=clean_text(_first(row, "area", "sigungu", "region")),
            longitude=safe_float(_first(row, "gpsX", "longitude", "x")),
            latitude=safe_float(_first(row, "gpsY", "latitude", "y")),
            image_url=_first(row, "thumbnail", "image", "imageUrl"),
            child_relevance_score=child_relevance(title, age_text, description),
            license_code=self.info.license_code,
            fetched_at=datetime.now(KST),
            raw=row,
        )
