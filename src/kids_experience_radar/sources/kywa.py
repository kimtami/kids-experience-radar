from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
import hashlib
import os
from typing import Any
from urllib.parse import unquote

from ..http import PoliteHttpClient
from ..models import CrawlWindow, Event
from ..normalizers import KST, child_relevance, clean_text, parse_price, safe_float
from .base import Source, SourceInfo


def _mapping_rows(value: object) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


class KywaYouthActivitySource(Source):
    ENDPOINT = (
        "https://apis.data.go.kr/B552713/svc002/"
        "getYthActvtyRprtPrgmTrFcltyInfo"
    )

    def __init__(self) -> None:
        self.info = SourceInfo(
            source_id="kywa_elementary_activities",
            name="한국청소년활동진흥원 초등 대상 활동",
            owner="한국청소년활동진흥원",
            source_type="open_api",
            official_url="https://www.data.go.kr/data/15156313/openapi.do",
            license_code="OPEN-DATA-NO-RESTRICTION",
            requires_key="DATA_GO_KR_SERVICE_KEY",
            enabled_by_default=False,
            notes=(
                "Official JSON/XML API. Only rows marked schboyYn are retained. "
                "This is a program/facility catalogue and may not contain session dates."
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
            payload = client.get_json(
                self.ENDPOINT,
                params={
                    "serviceKey": self.service_key,
                    "pageNo": page,
                    "numOfRows": 100,
                    "returnType": "JSON",
                },
            )
            rows, total = self.parse_page(payload)
            elementary = [row for row in rows if self._truthy(row.get("schboyYn"))]
            yield from (self._map_row(row) for row in elementary)
            if not rows or page * 100 >= total:
                break

    @staticmethod
    def parse_page(payload: object) -> tuple[list[dict[str, Any]], int]:
        if not isinstance(payload, Mapping):
            raise RuntimeError("KYWA API malformed response")
        response: object = payload.get("response", payload)
        if not isinstance(response, Mapping):
            raise RuntimeError("KYWA API malformed response")
        header = response.get("header")
        if not isinstance(header, Mapping):
            header = {}
        code = clean_text(header.get("resultCode"))
        if code and code not in {"00", "0", "INFO-000"}:
            message = clean_text(header.get("resultMsg")) or "unknown error"
            raise RuntimeError(f"KYWA API error {code}: {message}")
        body = response.get("body")
        if not isinstance(body, Mapping):
            return [], 0
        items = body.get("items")
        raw_rows = items.get("item") if isinstance(items, Mapping) else items
        rows = _mapping_rows(raw_rows)
        try:
            total = int(str(body.get("totalCount") or len(rows)))
        except ValueError:
            total = len(rows)
        return rows, total

    @staticmethod
    def _truthy(value: object) -> bool:
        return (clean_text(value) or "").casefold() in {"y", "yes", "true", "1"}

    def _map_row(self, row: dict[str, Any]) -> Event:
        title = clean_text(row.get("trnActvNm")) or clean_text(row.get("fcltNm")) or "제목 없음"
        facility = clean_text(row.get("fcltNm"))
        operator = clean_text(row.get("operInstNm") or row.get("prgrmDvlpOperMnbdNm"))
        address = clean_text(
            " ".join(
                part
                for part in (
                    clean_text(row.get("addr1") or row.get("lctnAddr1")),
                    clean_text(row.get("addr2") or row.get("lctnAddr2")),
                )
                if part
            )
        )
        price_value = row.get("ppPrtcpCst")
        if price_value in (None, ""):
            price_value = row.get("prtcpCst")
        price_min, price_text = parse_price(price_value)
        if price_text and price_text.replace(",", "").isdigit():
            price_min, price_text = parse_price(f"{price_text}원")
        detail_url = clean_text(row.get("hmpgAddr")) or self.info.official_url
        external_id = hashlib.sha256(
            f"{title}|{facility}|{operator}|{address}".encode()
        ).hexdigest()[:20]
        description = clean_text(row.get("prgrmCn") or row.get("intrcnCn"))
        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=external_id,
            title=title,
            detail_url=detail_url,
            provider_name=operator,
            category=clean_text(row.get("prgrmRelmNm")) or "청소년활동",
            description=description,
            status=clean_text(row.get("prgrsSttsNm")),
            age_text="초등학생",
            age_min=7,
            age_max=13,
            price_text=price_text,
            price_min=price_min,
            venue_name=facility,
            address=address,
            region=clean_text(
                " ".join(
                    part
                    for part in (
                        clean_text(row.get("ctpvNm")),
                        clean_text(row.get("sggNm")),
                    )
                    if part
                )
            ),
            latitude=safe_float(row.get("lat")),
            longitude=safe_float(row.get("lot")),
            phone=clean_text(row.get("telno")),
            child_relevance_score=child_relevance(title, "초등학생", description),
            license_code=self.info.license_code,
            fetched_at=datetime.now(KST),
            raw={
                key: row.get(key)
                for key in (
                    "trnActvNm",
                    "prgrmCn",
                    "ppPrtcpCst",
                    "certYn",
                    "highRiskActvYn",
                    "ctpvNm",
                    "sggNm",
                    "prgrsSttsNm",
                    "fcltNm",
                    "telno",
                    "hmpgAddr",
                    "addr1",
                    "addr2",
                    "lot",
                    "lat",
                    "operInstNm",
                    "prgrmRelmNm",
                    "schboyYn",
                    "prtcpCst",
                )
                if key in row
            },
        )


__all__ = ["KywaYouthActivitySource"]
