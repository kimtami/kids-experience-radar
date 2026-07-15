from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import hashlib
import json
import re
from typing import Any


def _slug(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"\[[^]]+]", " ", value)
    value = re.sub(r"[^0-9a-z가-힣]+", "", value)
    return value[:160]


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


@dataclass(slots=True)
class Event:
    source_id: str
    source_name: str
    external_id: str
    title: str
    detail_url: str
    provider_name: str | None = None
    category: str | None = None
    description: str | None = None
    event_start: datetime | None = None
    event_end: datetime | None = None
    apply_start: datetime | None = None
    apply_end: datetime | None = None
    status: str | None = None
    age_text: str | None = None
    age_min: int | None = None
    age_max: int | None = None
    price_text: str | None = None
    price_min: int | None = None
    currency: str = "KRW"
    venue_name: str | None = None
    address: str | None = None
    region: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    image_url: str | None = None
    phone: str | None = None
    is_online: bool = False
    child_relevance_score: float = 0.0
    license_code: str | None = None
    fetched_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
    distance_km: float | None = field(default=None, compare=False)

    @property
    def uid(self) -> str:
        basis = f"{self.source_id}\x1f{self.external_id or self.detail_url}"
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]

    @property
    def canonical_key(self) -> str:
        # A session is defined at minute precision.  Date-only sources map to
        # 00:00, while real morning/afternoon sessions remain distinct instead
        # of being collapsed merely because their title and venue match.
        start_slot = (
            self.event_start.strftime("%Y-%m-%dT%H:%M")
            if self.event_start
            else ""
        )
        place = self.venue_name or self.address or self.region or ""
        basis = f"{_slug(self.title)}|{_slug(place)}|{start_slot}"
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]

    @property
    def content_hash(self) -> str:
        payload = self.to_dict(include_raw=False)
        payload.pop("uid", None)
        payload.pop("canonical_key", None)
        payload.pop("distance_km", None)
        payload.pop("fetched_at", None)
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

    def to_dict(self, *, include_raw: bool = True) -> dict[str, Any]:
        result = asdict(self)
        for key in ("event_start", "event_end", "apply_start", "apply_end", "fetched_at"):
            result[key] = _iso(getattr(self, key))
        result["uid"] = self.uid
        result["canonical_key"] = self.canonical_key
        if not include_raw:
            result.pop("raw", None)
        return result


@dataclass(slots=True, frozen=True)
class CrawlWindow:
    start: datetime
    end: datetime
    max_pages: int = 5


@dataclass(slots=True)
class CrawlResult:
    source_id: str
    fetched: int = 0
    stored: int = 0
    changed: int = 0
    skipped: int = 0
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["started_at"] = _iso(self.started_at)
        data["finished_at"] = _iso(self.finished_at)
        return data
