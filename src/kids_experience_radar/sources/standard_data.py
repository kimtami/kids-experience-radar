from __future__ import annotations

from datetime import datetime
import hashlib
import os
from typing import Iterable
from urllib.parse import unquote, urlparse

from ..http import PoliteHttpClient
from ..models import CrawlWindow, Event
from ..normalizers import (
    KST,
    child_relevance,
    clean_text,
    parse_age_range,
    parse_datetime,
    parse_price,
    safe_float,
)
from .base import Source, SourceInfo


def _items_and_total(payload: dict) -> tuple[list[dict], int]:
    response = payload.get("response") or payload
    header = response.get("header") or {}
    result_code = str(header.get("resultCode") or "00")
    if result_code not in {"0", "00", "0000"}:
        message = clean_text(header.get("resultMsg")) or "unknown API error"
        raise RuntimeError(f"public standard data API error {result_code}: {message}")

    body = response.get("body") or {}
    raw_items = body.get("items") or []
    if isinstance(raw_items, dict):
        raw_items = raw_items.get("item") or []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]
    items = [item for item in raw_items if isinstance(item, dict)]
    total = int(body.get("totalCount") or len(items))
    return items, total


def _overlaps(event: Event, window: CrawlWindow) -> bool:
    if event.event_start is None and event.event_end is None:
        return True
    start = event.event_start or event.event_end
    end = event.event_end or event.event_start
    assert start is not None and end is not None
    return start <= window.end and end >= window.start


def _region_from_address(address: str | None) -> str | None:
    if not address:
        return None
    parts = address.split()
    return " ".join(parts[:2]) if len(parts) >= 2 else address


def _official_url(value: object | None, fallback: str) -> str:
    url = clean_text(value)
    if not url:
        return fallback
    if not urlparse(url).scheme:
        return f"https://{url.lstrip('/')}"
    return url


def _external_id(*parts: object | None) -> str:
    basis = "|".join(clean_text(part) or "" for part in parts)
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]


def _is_child_focused(*parts: object | None) -> bool:
    text = " ".join(clean_text(part) or "" for part in parts).casefold()
    return any(token in text for token in ("초등", "어린이", "아동", "가족", "키즈"))


class _StandardDataSource(Source):
    endpoint: str

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
        page_size = 1000
        for page in range(1, window.max_pages + 1):
            payload = client.get_json(
                self.endpoint,
                params={
                    "serviceKey": self.service_key,
                    "pageNo": page,
                    "numOfRows": page_size,
                    "type": "json",
                },
            )
            rows, total = _items_and_total(payload)
            for row in rows:
                event = self._map_row(row)
                if event is not None and _overlaps(event, window):
                    yield event
            if not rows or page * page_size >= total:
                break

    def _map_row(self, row: dict) -> Event | None:
        raise NotImplementedError


class LifelongLearningCourseSource(_StandardDataSource):
    endpoint = "https://api.data.go.kr/openapi/tn_pubr_public_lftm_lrn_lctre_api"

    def __init__(self) -> None:
        self.info = SourceInfo(
            source_id="standard_lifelong_learning_children",
            name="전국 평생학습강좌 어린이·가족 프로그램",
            owner="행정안전부·지방자치단체",
            source_type="public_standard_api",
            official_url="https://www.data.go.kr/data/15013110/standard.do",
            license_code="PUBLIC-DATA-STANDARD",
            requires_key="DATA_GO_KR_SERVICE_KEY",
            enabled_by_default=False,
            notes=(
                "Nationwide merged standard data. Only rows explicitly mentioning "
                "elementary children, children, families, or kids are emitted."
            ),
        )

    def _map_row(self, row: dict) -> Event | None:
        title = clean_text(row.get("lctreNm")) or "제목 없음"
        age_text = clean_text(row.get("edcTrgetType"))
        description = clean_text(row.get("lctreCo"))
        if not _is_child_focused(title, age_text, description):
            return None

        age_min, age_max, age_text = parse_age_range(age_text)
        raw_price = row.get("lctreCost")
        if raw_price not in (None, "") and str(raw_price).replace(",", "").isdigit():
            raw_price = f"{raw_price}원"
        price_min, price_text = parse_price(raw_price)
        address = clean_text(row.get("edcRdnmadr"))
        provider = clean_text(row.get("operInstitutionNm"))
        start = parse_datetime(row.get("edcStartDay"))
        end = parse_datetime(row.get("edcEndDay"), end_of_day=True)
        detail_url = _official_url(
            row.get("homepageUrl"), self.info.official_url
        )
        score = child_relevance(title, age_text, description)
        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=_external_id(title, provider, start, address),
            title=title,
            detail_url=detail_url,
            provider_name=provider,
            category="교육·체험",
            description=description,
            event_start=start,
            event_end=end,
            apply_start=parse_datetime(row.get("rceptStartDate")),
            apply_end=parse_datetime(row.get("rceptEndDate"), end_of_day=True),
            age_text=age_text,
            age_min=age_min,
            age_max=age_max,
            price_text=price_text,
            price_min=price_min,
            venue_name=clean_text(row.get("edcPlace")),
            address=address,
            region=_region_from_address(address),
            phone=clean_text(row.get("operPhoneNumber")),
            is_online="온라인" in (clean_text(row.get("edcMthType")) or ""),
            child_relevance_score=score,
            license_code=self.info.license_code,
            fetched_at=datetime.now(KST),
            raw=row,
        )


class NationalCultureFestivalSource(_StandardDataSource):
    endpoint = "https://api.data.go.kr/openapi/tn_pubr_public_cltur_fstvl_api"

    def __init__(self) -> None:
        self.info = SourceInfo(
            source_id="standard_national_child_festivals",
            name="전국 문화축제 어린이 체험",
            owner="문화체육관광부·한국관광공사·지방자치단체",
            source_type="public_standard_api",
            official_url="https://www.data.go.kr/data/15013104/standard.do",
            license_code="PUBLIC-DATA-STANDARD",
            requires_key="DATA_GO_KR_SERVICE_KEY",
            enabled_by_default=False,
            notes=(
                "Quarterly nationwide aggregate. Only festivals whose official name or "
                "description explicitly mentions experiences, children, families, or kids are emitted."
            ),
        )

    def _map_row(self, row: dict) -> Event | None:
        title = clean_text(row.get("fstvlNm")) or "제목 없음"
        description = clean_text(row.get("fstvlCo"))
        if not any(
            token in f"{title} {description or ''}".casefold()
            for token in ("체험", "어린이", "아동", "가족", "키즈")
        ):
            return None

        provider = clean_text(row.get("mnnstNm")) or clean_text(row.get("auspcInsttNm"))
        address = clean_text(row.get("rdnmadr")) or clean_text(row.get("lnmadr"))
        start = parse_datetime(row.get("fstvlStartDate"))
        end = parse_datetime(row.get("fstvlEndDate"), end_of_day=True)
        child_text = "가족·어린이 체험 포함" if _is_child_focused(title, description) else None
        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=_external_id(title, start, address),
            title=title,
            detail_url=_official_url(row.get("homepageUrl"), self.info.official_url),
            provider_name=provider,
            category="축제·체험",
            description=description,
            event_start=start,
            event_end=end,
            age_text=child_text,
            venue_name=clean_text(row.get("opar")),
            address=address,
            region=_region_from_address(address),
            latitude=safe_float(row.get("latitude")),
            longitude=safe_float(row.get("longitude")),
            phone=clean_text(row.get("phoneNumber")),
            child_relevance_score=child_relevance(title, child_text, description),
            license_code=self.info.license_code,
            fetched_at=datetime.now(KST),
            raw=row,
        )
