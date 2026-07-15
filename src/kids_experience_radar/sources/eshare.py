from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
import re
from typing import Iterable, Mapping
from urllib.parse import quote, urljoin, urlparse
import xml.etree.ElementTree as ET

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


_SUCCESS_CODES = {"0", "00", "0000", "200", "info-000", "ok", "success"}
_ROW_KEYS = {"rsrcno", "rsrcnm"}


def _tag_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _pick(row: dict[str, object], *aliases: str) -> object | None:
    folded = {str(key).casefold(): value for key, value in row.items()}
    for alias in aliases:
        value = folded.get(alias.casefold())
        if value not in (None, ""):
            return value
    return None


def _is_resource_row(value: Mapping[str, object]) -> bool:
    folded = {str(key).casefold(): item for key, item in value.items()}
    return any(folded.get(key) not in (None, "") for key in _ROW_KEYS)


def _json_rows(value: object) -> list[dict[str, object]]:
    if isinstance(value, dict):
        if _is_resource_row(value):
            return [value]
        rows: list[dict[str, object]] = []
        for child in value.values():
            rows.extend(_json_rows(child))
        return rows
    if isinstance(value, list):
        rows = []
        for child in value:
            rows.extend(_json_rows(child))
        return rows
    return []


def _find_json_value(value: object, aliases: set[str]) -> object | None:
    if isinstance(value, dict):
        if _is_resource_row(value):
            return None
        for key, child in value.items():
            if str(key).casefold() in aliases and child not in (None, ""):
                return child
        for child in value.values():
            found = _find_json_value(child, aliases)
            if found not in (None, ""):
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_json_value(child, aliases)
            if found not in (None, ""):
                return found
    return None


def _as_total(value: object | None) -> int | None:
    if value in (None, ""):
        return None
    try:
        total = int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return max(0, total)


def _check_result_code(code: object | None, message: object | None) -> None:
    if code in (None, ""):
        return
    normalized = str(code).strip().casefold()
    if normalized not in _SUCCESS_CODES:
        detail = clean_text(message) or "unknown error"
        raise RuntimeError(f"EShare API error {code}: {detail}")


def _parse_json(payload: object) -> tuple[list[dict[str, object]], int | None]:
    if not isinstance(payload, (dict, list)):
        raise RuntimeError("EShare API malformed JSON response")
    code = _find_json_value(
        payload, {"resultcode", "resultcd", "statuscode", "status", "code"}
    )
    message = _find_json_value(
        payload, {"resultmsg", "message", "msg", "errormessage", "error"}
    )
    _check_result_code(code, message)
    rows = _json_rows(payload)
    total = _as_total(
        _find_json_value(payload, {"totalcount", "totalcnt", "total_count"})
    )
    return rows, total


def _parse_xml(xml_text: str) -> tuple[list[dict[str, object]], int | None]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise RuntimeError("EShare API malformed XML response") from exc
    if _tag_name(root.tag).casefold() == "html":
        raise RuntimeError("EShare API returned HTML instead of API data")

    scalar_values: dict[str, str] = {}
    for element in root.iter():
        if len(list(element)) == 0 and element.text:
            scalar_values.setdefault(
                _tag_name(element.tag).casefold(), element.text.strip()
            )
    code = next(
        (
            scalar_values[key]
            for key in ("resultcode", "resultcd", "statuscode", "code")
            if key in scalar_values
        ),
        None,
    )
    if code is None and not any(
        _tag_name(element.tag).casefold() in _ROW_KEYS for element in root.iter()
    ):
        code = scalar_values.get("status")
    message = next(
        (
            scalar_values[key]
            for key in ("resultmsg", "message", "msg", "errormessage")
            if key in scalar_values
        ),
        None,
    )
    _check_result_code(code, message)

    rows: list[dict[str, object]] = []
    for element in root.iter():
        row: dict[str, object] = {
            _tag_name(child.tag): (child.text or "").strip()
            for child in list(element)
            if len(list(child)) == 0
        }
        if _is_resource_row(row):
            rows.append(row)
    total = next(
        (
            _as_total(scalar_values[key])
            for key in ("totalcount", "totalcnt", "total_count")
            if key in scalar_values
        ),
        None,
    )
    return rows, total


def _join_address(address: object | None, detail: object | None) -> str | None:
    address_text = clean_text(address)
    detail_text = clean_text(detail)
    if not address_text:
        return detail_text
    if not detail_text or detail_text in address_text:
        return address_text
    return f"{address_text} {detail_text}"


def _parse_target_age(
    value: object | None,
) -> tuple[int | None, int | None, str | None]:
    age_min, age_max, age_text = parse_age_range(value)
    if not age_text:
        return age_min, age_max, age_text
    grade_range = re.search(
        r"(?:초등학교|초등|초)\s*([1-6])\s*(?:학년)?\s*(?:~|[-–]|부터)\s*"
        r"(?:초등학교|초등|초)?\s*([1-6])\s*학년?",
        age_text,
    )
    if grade_range:
        first, last = (int(value) for value in grade_range.groups())
        age_min, age_max = min(first, last) + 6, max(first, last) + 6
    return age_min, age_max, age_text


def _region_from_address(address: str | None) -> str | None:
    if not address:
        return None
    parts = address.split()
    if not parts:
        return None
    if parts[0] == "세종특별자치시" or len(parts) == 1:
        return parts[0]
    if len(parts) >= 2 and parts[1].endswith(("시", "군", "구")):
        return " ".join(parts[:2])
    return parts[0]


def _absolute_url(value: object | None) -> str | None:
    url = clean_text(value)
    if not url or url.casefold() in {"null", "none", "-"}:
        return None
    absolute = urljoin("https://www.eshare.go.kr", url)
    if urlparse(absolute).scheme.casefold() not in {"http", "https"}:
        return None
    return absolute


class EShareEducationSource(Source):
    ENDPOINT = "https://www.eshare.go.kr/eshare-openapi/rsrc/list/040000"

    def __init__(self) -> None:
        self.info = SourceInfo(
            source_id="eshare_education",
            name="공유누리 교육·강좌",
            owner="행정안전부",
            source_type="open_api",
            official_url="https://www.eshare.go.kr/OpenApi/Info/detail.do?svcNo=18",
            license_code="OPEN-DATA-NO-RESTRICTION",
            requires_key="ESHARE_API_KEY",
            enabled_by_default=False,
            notes="Official API only; the shared website disallows HTML crawling.",
        )

    @property
    def api_key(self) -> str:
        return os.getenv("ESHARE_API_KEY", "").strip()

    def available(self) -> tuple[bool, str | None]:
        if not self.api_key:
            return False, "ESHARE_API_KEY is not set"
        return True, None

    def crawl(self, client: PoliteHttpClient, window: CrawlWindow) -> Iterable[Event]:
        if not self.api_key:
            raise RuntimeError("ESHARE_API_KEY is required")
        page_size = 100
        endpoint = f"{self.ENDPOINT}/{quote(self.api_key, safe='')}"
        for page in range(1, window.max_pages + 1):
            params: dict[str, object] = {
                "pageNo": page,
                "numOfRows": page_size,
            }
            text = client.get_text(endpoint, params=params)
            rows, total = self.parse_rows(text)
            if not rows:
                break
            for row in rows:
                yield self._map_row(row)
            if total is not None and page * page_size >= total:
                break
            if total is None and len(rows) < page_size:
                break

    @staticmethod
    def parse_rows(response_text: str) -> tuple[list[dict[str, object]], int | None]:
        text = response_text.lstrip("\ufeff\r\n\t ")
        if not text:
            raise RuntimeError("EShare API returned an empty response")
        if text.startswith(("{", "[")):
            try:
                return _parse_json(json.loads(text))
            except json.JSONDecodeError as exc:
                raise RuntimeError("EShare API malformed JSON response") from exc
        if text.startswith("<"):
            return _parse_xml(text)
        raise RuntimeError("EShare API returned an unsupported response format")

    def _map_row(self, row: dict[str, object]) -> Event:
        title = clean_text(_pick(row, "rsrcNm", "resourceName", "name")) or "제목 없음"
        resource_no = clean_text(_pick(row, "rsrcNo", "resourceNo", "id"))
        address = _join_address(
            _pick(row, "addr", "address"), _pick(row, "daddr", "detailAddress")
        )
        detail_url = _absolute_url(_pick(row, "instUrlAddr", "dtlUrlAddr", "url"))
        if not detail_url and resource_no:
            detail_url = (
                "https://www.eshare.go.kr/UserPortal/Upv/UprResrcFacl/index.do"
                f"?rsrc_no={quote(resource_no, safe='')}"
            )
        detail_url = detail_url or self.info.official_url
        external_id = (
            resource_no
            or hashlib.sha256(
                f"{title}|{address}|{detail_url}".encode("utf-8")
            ).hexdigest()[:20]
        )

        description = clean_text(
            _pick(row, "rsrcIntr", "description", "dtlCn", "usePrpse")
        )
        age_min, age_max, age_text = _parse_target_age(
            _pick(row, "useTrgtInfo", "useTrgt", "useTgt", "target")
        )
        price_raw = _pick(row, "amt1", "useFee", "fee", "price")
        free_raw = clean_text(_pick(row, "freeYn", "isFree"))
        if (
            price_raw not in (None, "")
            and str(price_raw).strip().replace(",", "").isdigit()
        ):
            price_raw = f"{price_raw}원"
        if price_raw in (None, "") and free_raw:
            if free_raw.casefold() in {"y", "yes", "true", "1", "무료"}:
                price_raw = "무료"
            elif free_raw.casefold() in {"n", "no", "false", "0", "유료"}:
                price_raw = "유료"
        price_min, price_text = parse_price(price_raw)

        availability = clean_text(_pick(row, "usePsblYn", "availableYn"))
        status = None
        if availability:
            status = (
                "이용가능"
                if availability.casefold() in {"y", "yes", "true", "1"}
                else "이용불가"
            )

        provider = (
            clean_text(_pick(row, "rsrcInstNm", "instNm", "mngInstNm", "orgNm"))
            or self.info.owner
        )
        category = clean_text(_pick(row, "rsrcClsNm", "category")) or "교육·강좌"
        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=external_id,
            title=title,
            detail_url=detail_url,
            provider_name=provider,
            category=category,
            description=description,
            event_start=parse_datetime(
                _pick(row, "useBgngYmd", "startDate", "bgngYmd")
            ),
            event_end=parse_datetime(
                _pick(row, "useEndYmd", "endDate", "endYmd"), end_of_day=True
            ),
            apply_start=parse_datetime(_pick(row, "rcptBgngYmd", "applyStartDate")),
            apply_end=parse_datetime(
                _pick(row, "rcptEndYmd", "applyEndDate"), end_of_day=True
            ),
            status=status,
            age_text=age_text,
            age_min=age_min,
            age_max=age_max,
            price_text=price_text,
            price_min=price_min,
            venue_name=clean_text(_pick(row, "placeNm", "venueName")) or title,
            address=address,
            region=clean_text(_pick(row, "ctpvNm", "region"))
            or _region_from_address(address),
            latitude=safe_float(_pick(row, "lat", "latitude")),
            longitude=safe_float(_pick(row, "lot", "longitude", "lon")),
            image_url=_absolute_url(_pick(row, "imgFileUrlAddr", "imageUrl")),
            phone=clean_text(_pick(row, "telNo", "phone", "inqTelNo")),
            child_relevance_score=child_relevance(title, age_text, description),
            license_code=self.info.license_code,
            fetched_at=datetime.now(KST),
            raw=row,
        )


# Keep the conventional mixed-case spelling used by the source registry.
EshareEducationSource = EShareEducationSource
