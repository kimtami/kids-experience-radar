from __future__ import annotations

from datetime import datetime
import os
from typing import Iterable
from urllib.parse import unquote

from ..http import PoliteHttpClient
from ..models import CrawlWindow, Event
from ..normalizers import KST, child_relevance, clean_text, parse_age_range, parse_date_range
from .base import Source, SourceInfo


def _items(payload: dict) -> tuple[list[dict], int]:
    response = payload.get("response") or payload
    header = response.get("header") or {}
    code = str(header.get("resultCode") or "00")
    if code not in {"0", "00", "0000"}:
        message = clean_text(header.get("resultMsg")) or "unknown API error"
        raise RuntimeError(f"Jeonnam art API error {code}: {message}")
    body = response.get("body") or {}
    raw_items = body.get("items") or []
    if isinstance(raw_items, dict):
        raw_items = raw_items.get("item") or []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]
    items = [row for row in raw_items if isinstance(row, dict)]
    return items, int(body.get("totalCount") or len(items))


def _child_candidate(row: dict) -> bool:
    text = " ".join(
        clean_text(row.get(key)) or ""
        for key in ("artEduTitle", "artEduTarget", "artEduSubTitle")
    ).casefold()
    return any(token in text for token in ("초등", "어린이", "아동", "가족", "키즈"))


class JeonnamProvincialArtEducationSource(Source):
    BASE_URL = "https://apis.data.go.kr/6460000/jnArtEdu"

    def __init__(self) -> None:
        self.info = SourceInfo(
            source_id="jeonnam_provincial_art_education",
            name="전남도립미술관 어린이·가족 교육",
            owner="전남도립미술관",
            source_type="open_api",
            official_url="https://www.data.go.kr/data/15159552/openapi.do",
            license_code="OPEN-DATA",
            requires_key="DATA_GO_KR_SERVICE_KEY",
            enabled_by_default=False,
            notes=(
                "Official list/detail API. List rows are filtered for explicit child or family "
                "targets before detail calls."
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
        page_size = 100
        for page in range(1, window.max_pages + 1):
            list_payload = client.get_json(
                f"{self.BASE_URL}/getEduList",
                params={
                    "serviceKey": self.service_key,
                    "startPage": page,
                    "pageSize": page_size,
                    "type": "json",
                },
            )
            rows, total = _items(list_payload)
            for row in rows:
                if not _child_candidate(row):
                    continue
                education_id = clean_text(row.get("artEduId"))
                detail = row
                if education_id:
                    detail_payload = client.get_json(
                        f"{self.BASE_URL}/getEduDetail",
                        params={
                            "serviceKey": self.service_key,
                            "artEduId": education_id,
                            "type": "json",
                        },
                    )
                    details, _ = _items(detail_payload)
                    if details:
                        detail = {**row, **details[0]}
                event = self._map_row(detail)
                if self._overlaps(event, window):
                    yield event
            if not rows or page * page_size >= total:
                break

    @staticmethod
    def _overlaps(event: Event, window: CrawlWindow) -> bool:
        if event.event_start is None and event.event_end is None:
            return True
        start = event.event_start or event.event_end
        end = event.event_end or event.event_start
        assert start is not None and end is not None
        return start <= window.end and end >= window.start

    def _map_row(self, row: dict) -> Event:
        title = clean_text(row.get("artEduTitle")) or "제목 없음"
        target = clean_text(row.get("artEduTarget"))
        age_min, age_max, age_text = parse_age_range(target)
        start, end = parse_date_range(row.get("artEduPeriod"))
        apply_start, apply_end = parse_date_range(row.get("artEduApplyDt"))
        description = clean_text(row.get("artEduContent")) or clean_text(
            row.get("artEduSubTitle")
        )
        detail_url = next(
            (
                value
                for key in ("artEduReqstUrl1", "artEduReqstUrl2", "artEduReqstUrl3")
                if (value := clean_text(row.get(key)))
            ),
            "https://artmuseum.jeonnam.go.kr/www/edu/view/list",
        )
        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=clean_text(row.get("artEduId")) or f"{title}|{start}",
            title=title,
            detail_url=detail_url,
            provider_name="전남도립미술관",
            category="미술·교육·체험",
            description=description,
            event_start=start,
            event_end=end,
            apply_start=apply_start,
            apply_end=apply_end,
            status=clean_text(row.get("artEduStatus")),
            age_text=age_text,
            age_min=age_min,
            age_max=age_max,
            venue_name=clean_text(row.get("artEduPlace")) or "전남도립미술관",
            address="전남광주통합특별시 광양시 광양읍 순광로 660",
            region="전남광주통합특별시 광양시",
            image_url=clean_text(row.get("artEduThumb")),
            child_relevance_score=child_relevance(title, age_text, description),
            license_code=self.info.license_code,
            fetched_at=datetime.now(KST),
            raw=row,
        )
