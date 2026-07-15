from __future__ import annotations

import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from .models import Event
from .normalizers import (
    KST,
    child_relevance,
    clean_text,
    parse_age_range,
    parse_datetime,
    parse_price,
    safe_float,
)
from .policy import blocked_reason


def _rows(path: Path) -> Iterable[dict]:
    if path.suffix.casefold() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            yield from csv.DictReader(handle)
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def load_tip_events(path: str | Path) -> tuple[list[Event], list[str]]:
    source_path = Path(path)
    events: list[Event] = []
    errors: list[str] = []
    for index, row in enumerate(_rows(source_path), start=1):
        title = clean_text(row.get("title") or row.get("행사명"))
        detail_url = clean_text(row.get("official_url") or row.get("detail_url") or row.get("공식URL"))
        if not title or not detail_url:
            errors.append(f"row {index}: title and official_url are required")
            continue
        parsed_url = urlparse(detail_url)
        if parsed_url.scheme.casefold() not in {"http", "https"} or not parsed_url.hostname:
            errors.append(f"row {index}: official_url must be an http(s) URL")
            continue
        if reason := blocked_reason(detail_url):
            errors.append(f"row {index}: community/chat URL rejected ({reason}); submit the organizer's official URL")
            continue
        age_min, age_max, age_text = parse_age_range(row.get("age_text") or row.get("대상"))
        price_min, price_text = parse_price(row.get("price_text") or row.get("가격"))
        description = clean_text(row.get("description") or row.get("설명"))
        external_id = hashlib.sha256(detail_url.encode("utf-8")).hexdigest()[:20]
        events.append(
            Event(
                source_id="community_official_links",
                source_name="사용자 제보 공식 원문",
                external_id=external_id,
                title=title,
                detail_url=detail_url,
                provider_name=clean_text(row.get("provider_name") or row.get("주최")),
                category=clean_text(row.get("category") or row.get("분류")) or "제보",
                description=description,
                event_start=parse_datetime(row.get("event_start") or row.get("행사시작")),
                event_end=parse_datetime(row.get("event_end") or row.get("행사종료"), end_of_day=True),
                apply_start=parse_datetime(row.get("apply_start") or row.get("신청시작")),
                apply_end=parse_datetime(row.get("apply_end") or row.get("신청마감"), end_of_day=True),
                status=clean_text(row.get("status") or row.get("상태")),
                age_text=age_text,
                age_min=age_min,
                age_max=age_max,
                price_text=price_text,
                price_min=price_min,
                venue_name=clean_text(row.get("venue_name") or row.get("장소")),
                address=clean_text(row.get("address") or row.get("주소")),
                region=clean_text(row.get("region") or row.get("지역")),
                latitude=safe_float(row.get("latitude") or row.get("위도")),
                longitude=safe_float(row.get("longitude") or row.get("경도")),
                child_relevance_score=child_relevance(title, age_text, description),
                fetched_at=datetime.now(KST),
                raw={"discovered_via": "user_submission", "input_file": source_path.name},
            )
        )
    return events, errors
