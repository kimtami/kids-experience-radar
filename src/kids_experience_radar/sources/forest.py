from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
import hashlib
import os
from urllib.parse import unquote
import xml.etree.ElementTree as ET

from ..http import PoliteHttpClient
from ..models import CrawlWindow, Event
from ..normalizers import KST, child_relevance, clean_text
from .base import Source, SourceInfo


class ForestEducationSource(Source):
    ENDPOINT = (
        "https://api.forest.go.kr/openapi/service/"
        "cultureInfoService/frstEduInfoOpenAPI"
    )

    def __init__(self) -> None:
        self.info = SourceInfo(
            source_id="forest_education_programs",
            name="산림청 산림교육 운영 프로그램",
            owner="산림청",
            source_type="open_api",
            official_url="https://www.data.go.kr/data/3057832/openapi.do",
            license_code="OPEN-DATA",
            requires_key="DATA_GO_KR_SERVICE_KEY",
            enabled_by_default=False,
            notes=(
                "Official XML API with eduType=4. The operating-period field is often "
                "seasonal text rather than bookable session dates."
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
            xml_text = client.get_text(
                self.ENDPOINT,
                params={
                    "ServiceKey": self.service_key,
                    "eduType": 4,
                    "pageNo": page,
                    "numOfRows": 100,
                },
            )
            rows, total = self.parse_page(xml_text)
            yield from (self._map_row(row) for row in rows)
            if not rows or page * 100 >= total:
                break

    @staticmethod
    def parse_page(xml_text: str) -> tuple[list[dict[str, str]], int]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise RuntimeError("Forest API returned malformed XML") from exc
        code = clean_text(
            root.findtext(".//resultCode") or root.findtext(".//resultcode")
        )
        if code and code not in {"00", "0", "0000", "INFO-000"}:
            message = clean_text(
                root.findtext(".//resultMsg") or root.findtext(".//resultmsg")
            ) or "unknown error"
            raise RuntimeError(f"Forest API error {code}: {message}")
        rows: list[dict[str, str]] = []
        for item in root.findall(".//item"):
            row = {
                child.tag.rsplit("}", 1)[-1]: (child.text or "").strip()
                for child in list(item)
            }
            if row:
                rows.append(row)
        try:
            total = int(root.findtext(".//totalCount") or len(rows))
        except ValueError:
            total = len(rows)
        return rows, total

    def _map_row(self, row: dict[str, str]) -> Event:
        title = clean_text(row.get("title") or row.get("facnm")) or "제목 없음"
        facility = clean_text(row.get("facnm"))
        address = clean_text(row.get("addr"))
        period = clean_text(row.get("period"))
        description = clean_text(row.get("cont"))
        external_id = hashlib.sha256(
            f"{title}|{facility}|{address}".encode()
        ).hexdigest()[:20]
        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=external_id,
            title=title,
            detail_url=self.info.official_url,
            provider_name=clean_text(row.get("mnagnnm")) or self.info.owner,
            category=clean_text(row.get("category")) or "산림교육",
            description=description,
            status=period,
            venue_name=facility,
            address=address,
            region=" ".join(address.split()[:2]) if address else None,
            phone=clean_text(row.get("tel")),
            child_relevance_score=child_relevance(title, None, description),
            license_code=self.info.license_code,
            fetched_at=datetime.now(KST),
            raw=dict(row),
        )


__all__ = ["ForestEducationSource"]
