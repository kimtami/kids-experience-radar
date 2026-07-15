from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

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
from ..policy import assert_html_source_allowed
from .base import Source, SourceInfo


@dataclass(slots=True, frozen=True)
class FieldSelector:
    selector: str | None = None
    attr: str = "text"
    default: str | None = None

    @classmethod
    def from_value(cls, value: str | dict | None) -> "FieldSelector":
        if value is None:
            return cls()
        if isinstance(value, str):
            return cls(selector=value)
        return cls(selector=value.get("selector"), attr=value.get("attr", "text"), default=value.get("default"))


@dataclass(slots=True, frozen=True)
class HtmlSourceSpec:
    source_id: str
    name: str
    owner: str
    list_url: str
    official_url: str
    card_selector: str
    fields: dict[str, FieldSelector]
    legal_review_status: str
    license_code: str | None = None
    page_param: str | None = None
    page_start: int = 1
    enabled: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "HtmlSourceSpec":
        return cls(
            source_id=data["source_id"],
            name=data["name"],
            owner=data["owner"],
            list_url=data["list_url"],
            official_url=data.get("official_url", data["list_url"]),
            card_selector=data["card_selector"],
            fields={key: FieldSelector.from_value(value) for key, value in data.get("fields", {}).items()},
            legal_review_status=data.get("legal_review_status", "pending"),
            license_code=data.get("license_code"),
            page_param=data.get("page_param"),
            page_start=int(data.get("page_start", 1)),
            enabled=bool(data.get("enabled", False)),
        )


class ConfiguredHtmlSource(Source):
    def __init__(self, spec: HtmlSourceSpec) -> None:
        assert_html_source_allowed(spec.list_url, spec.legal_review_status)
        self.spec = spec
        self.info = SourceInfo(
            source_id=spec.source_id,
            name=spec.name,
            owner=spec.owner,
            source_type="approved_html",
            official_url=spec.official_url,
            license_code=spec.license_code,
            enabled_by_default=spec.enabled,
            policy_status="approved_html",
            notes="Fail-closed robots check; facts and canonical links only.",
        )

    @staticmethod
    def _extract(card: Tag, selector: FieldSelector) -> str | None:
        if not selector.selector:
            return selector.default
        node = card.select_one(selector.selector)
        if node is None:
            return selector.default
        if selector.attr == "text":
            return clean_text(node.get_text(" ", strip=True))
        return clean_text(node.get(selector.attr)) or selector.default

    def parse_html(self, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        for card in soup.select(self.spec.card_selector):
            values = {name: self._extract(card, selector) for name, selector in self.spec.fields.items()}
            title = values.get("title") or "제목 없음"
            relative_url = values.get("detail_url") or self.spec.official_url
            detail_url = urljoin(self.spec.list_url, relative_url)
            external_id = values.get("external_id") or hashlib.sha256(detail_url.encode("utf-8")).hexdigest()[:20]
            age_min, age_max, age_text = parse_age_range(values.get("age_text"))
            price_min, price_text = parse_price(values.get("price_text"))
            description = clean_text(values.get("description"))
            events.append(
                Event(
                    source_id=self.info.source_id,
                    source_name=self.info.name,
                    external_id=external_id,
                    title=title,
                    detail_url=detail_url,
                    provider_name=values.get("provider_name") or self.spec.owner,
                    category=values.get("category"),
                    description=description,
                    event_start=parse_datetime(values.get("event_start")),
                    event_end=parse_datetime(values.get("event_end"), end_of_day=True),
                    apply_start=parse_datetime(values.get("apply_start")),
                    apply_end=parse_datetime(values.get("apply_end"), end_of_day=True),
                    status=values.get("status"),
                    age_text=age_text,
                    age_min=age_min,
                    age_max=age_max,
                    price_text=price_text,
                    price_min=price_min,
                    venue_name=values.get("venue_name"),
                    address=values.get("address"),
                    region=values.get("region"),
                    latitude=safe_float(values.get("latitude")),
                    longitude=safe_float(values.get("longitude")),
                    image_url=urljoin(self.spec.list_url, values["image_url"]) if values.get("image_url") else None,
                    child_relevance_score=child_relevance(title, age_text, description),
                    license_code=self.info.license_code,
                    fetched_at=datetime.now(KST),
                    raw={"parsed_fields": values},
                )
            )
        return events

    def crawl(self, client: PoliteHttpClient, window: CrawlWindow) -> Iterable[Event]:
        client.assert_html_allowed(self.spec.list_url)
        pages = window.max_pages if self.spec.page_param else 1
        for offset in range(pages):
            page = self.spec.page_start + offset
            params = {self.spec.page_param: page} if self.spec.page_param else None
            html = client.get_text(self.spec.list_url, params=params)
            events = self.parse_html(html)
            if not events:
                break
            for event in events:
                if event.event_end and event.event_end < window.start:
                    continue
                if event.event_start and event.event_start > window.end:
                    continue
                yield event


def load_html_sources(path: str | Path) -> list[ConfiguredHtmlSource]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else payload.get("sources", [])
    return [ConfiguredHtmlSource(HtmlSourceSpec.from_dict(row)) for row in rows if row.get("enabled", False)]
