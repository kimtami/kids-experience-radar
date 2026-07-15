from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
import os
from typing import Any
import xml.etree.ElementTree as ET

from ..http import PoliteHttpClient
from ..models import CrawlWindow, Event
from ..normalizers import KST, clean_text, parse_datetime
from .base import Source, SourceInfo


class KopisChildPerformanceSource(Source):
    """KOPIS performances explicitly classified as children's performances."""

    ENDPOINT = "https://www.kopis.or.kr/openApi/restful/pblprfr"
    DETAIL_PAGE = "https://www.kopis.or.kr/por/db/pblprfr/pblprfrView.do"
    PAGE_SIZE = 100

    def __init__(self) -> None:
        self.info = SourceInfo(
            source_id="kopis_child_performances",
            name="KOPIS 아동 공연",
            owner="예술경영지원센터",
            source_type="open_api",
            official_url="https://kopis.or.kr/por/cs/openapi/openApiInfo.do",
            license_code="KOPIS-ATTRIBUTION",
            requires_key="KOPIS_API_KEY",
            enabled_by_default=False,
            notes=(
                "Official XML API with kidstate=Y. KOPIS attribution is required; "
                "the API permits date windows of at most 31 days."
            ),
        )

    @property
    def api_key(self) -> str:
        return os.getenv("KOPIS_API_KEY", "").strip()

    def available(self) -> tuple[bool, str | None]:
        if not self.api_key:
            return False, "KOPIS_API_KEY is not set"
        return True, None

    def crawl(self, client: PoliteHttpClient, window: CrawlWindow) -> Iterable[Event]:
        if not self.api_key:
            raise RuntimeError("KOPIS_API_KEY is required")

        seen: set[str] = set()
        chunk_start = window.start
        while chunk_start <= window.end:
            chunk_end = min(window.end, chunk_start + timedelta(days=30))
            for page in range(1, window.max_pages + 1):
                xml_text = client.get_text(
                    self.ENDPOINT,
                    params={
                        "service": self.api_key,
                        "stdate": chunk_start.strftime("%Y%m%d"),
                        "eddate": chunk_end.strftime("%Y%m%d"),
                        "cpage": page,
                        "rows": self.PAGE_SIZE,
                        "kidstate": "Y",
                    },
                )
                rows = self.parse_rows(xml_text)
                for row in rows:
                    event = self._map_row(row)
                    if event.external_id not in seen:
                        seen.add(event.external_id)
                        yield event
                if len(rows) < self.PAGE_SIZE:
                    break
            chunk_start = chunk_end + timedelta(days=1)

    @staticmethod
    def parse_rows(xml_text: str) -> list[dict[str, str]]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise RuntimeError("KOPIS returned malformed XML") from exc

        error_code = clean_text(
            root.findtext(".//resultcode")
            or root.findtext(".//resultCode")
            or root.findtext(".//returnReasonCode")
        )
        if error_code and error_code not in {"00", "0", "INFO-000"}:
            message = clean_text(
                root.findtext(".//resultmsg")
                or root.findtext(".//resultMsg")
                or root.findtext(".//errMsg")
            ) or "unknown error"
            raise RuntimeError(f"KOPIS API error {error_code}: {message}")

        rows: list[dict[str, str]] = []
        for element in root.findall(".//db"):
            row = {
                child.tag.rsplit("}", 1)[-1]: (child.text or "").strip()
                for child in list(element)
            }
            if row:
                rows.append(row)
        return rows

    def _map_row(self, row: dict[str, Any]) -> Event:
        performance_id = clean_text(row.get("mt20id")) or "unknown"
        title = clean_text(row.get("prfnm")) or "제목 없음"
        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=performance_id,
            title=title,
            detail_url=(
                f"{self.DETAIL_PAGE}?menuId=MNU_00020&mt20Id={performance_id}"
            ),
            provider_name=clean_text(row.get("fcltynm")),
            category=clean_text(row.get("genrenm")) or "아동공연",
            event_start=parse_datetime(row.get("prfpdfrom")),
            event_end=parse_datetime(row.get("prfpdto"), end_of_day=True),
            status=clean_text(row.get("prfstate")),
            age_text="아동공연(KOPIS kidstate=Y)",
            venue_name=clean_text(row.get("fcltynm")),
            region=clean_text(row.get("area")),
            image_url=clean_text(row.get("poster")),
            child_relevance_score=1.0,
            license_code=self.info.license_code,
            fetched_at=datetime.now(KST),
            raw=dict(row),
        )


__all__ = ["KopisChildPerformanceSource"]
