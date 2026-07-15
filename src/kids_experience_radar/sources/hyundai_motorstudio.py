from __future__ import annotations

from datetime import datetime
import hashlib
import re
from typing import Iterable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from ..http import PoliteHttpClient
from ..models import CrawlWindow, Event
from ..normalizers import (
    KST,
    child_relevance,
    clean_text,
    parse_age_range,
    parse_price,
)
from ..policy import explicit_source_approval
from .base import Source, SourceInfo


_PROGRAM_ID_RE = re.compile(r"goResrv\s*\(\s*(['\"])([A-Za-z0-9_-]{1,64})\1\s*\)")


def _node_text(node: Tag | None) -> str | None:
    if node is None:
        return None
    return clean_text(node.get_text(" ", strip=True))


def _normalize_label(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _detail_value(details: dict[str, str], *aliases: str) -> str | None:
    for alias in aliases:
        value = details.get(_normalize_label(alias))
        if value:
            return value
    return None


def _safe_url(value: object | None, *, base_url: str) -> str | None:
    raw = clean_text(value)
    if not raw:
        return None
    absolute = urljoin(base_url, raw)
    if urlparse(absolute).scheme.casefold() not in {"http", "https"}:
        return None
    return absolute


class HyundaiMotorstudioKidsWorkshopSource(Source):
    LIST_URL = (
        "https://motorstudio.hyundai.com/goyang/cotn/exp/kidsWorkShop.do?strgCd=01"
    )
    VENUE_NAME = "현대 모터스튜디오 고양"
    ADDRESS = "경기도 고양시 일산서구 킨텍스로 217-6"

    def __init__(self) -> None:
        self.info = SourceInfo(
            source_id="hyundai_motorstudio_goyang_kids",
            name="현대 모터스튜디오 고양 어린이 워크숍",
            owner="현대자동차",
            source_type="reviewed_public_html",
            official_url=self.LIST_URL,
            license_code=None,
            enabled_by_default=False,
            policy_status="reviewed_public_html",
            notes=(
                "Official public list only. Crawl at low frequency; never call the "
                "reservation submission endpoint."
            ),
        )

    def available(self) -> tuple[bool, str | None]:
        return explicit_source_approval(self.info.source_id)

    @staticmethod
    def _program_id(section: Tag) -> str | None:
        for node in section.select("[onclick]"):
            match = _PROGRAM_ID_RE.search(str(node.get("onclick") or ""))
            if match:
                return match.group(2)
        return None

    @staticmethod
    def _details(section: Tag) -> dict[str, str]:
        details: dict[str, str] = {}
        for block in section.select(".expln_cotn .dtl_info"):
            label = _node_text(block.select_one("h4.tit"))
            value = _node_text(block.select_one("p"))
            if label and value:
                details.setdefault(_normalize_label(label), value)
        return details

    def parse_html(self, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        sections = soup.select("section.list_set")
        if not sections:
            raise RuntimeError(
                "Hyundai Motorstudio page structure changed: section.list_set not found"
            )

        events: list[Event] = []
        cards_with_details = 0
        for section in sections:
            title = _node_text(section.select_one(".expln_text .cotn_title h3"))
            if not title:
                continue
            summary = _node_text(section.select_one(".expln_text .cotn_title > p"))
            details = self._details(section)
            if details:
                cards_with_details += 1

            target = _detail_value(
                details, "참여가능연령", "참여연령", "대상연령", "대상"
            )
            operating_hours = _detail_value(details, "운영시간")
            duration = _detail_value(details, "소요시간")
            price_raw = _detail_value(details, "참가비", "이용요금", "요금")
            venue = _detail_value(details, "장소", "운영장소") or self.VENUE_NAME
            age_min, age_max, age_text = parse_age_range(target)
            price_min, price_text = parse_price(price_raw)
            program_id = self._program_id(section)
            external_id = (
                program_id
                or hashlib.sha256(
                    f"{self.info.source_id}|{title}".encode("utf-8")
                ).hexdigest()[:20]
            )

            description_parts = [summary]
            if operating_hours:
                description_parts.append(f"운영시간: {operating_hours}")
            if duration:
                description_parts.append(f"소요시간: {duration}")
            description = clean_text(
                " ".join(part for part in description_parts if part)
            )
            image_node = section.select_one(".img_btn_wrap img[src]")
            image_url = _safe_url(
                image_node.get("src") if image_node else None,
                base_url=self.LIST_URL,
            )

            events.append(
                Event(
                    source_id=self.info.source_id,
                    source_name=self.info.name,
                    external_id=external_id,
                    title=title,
                    detail_url=self.LIST_URL,
                    provider_name=self.info.owner,
                    category="어린이 워크숍",
                    description=description,
                    age_text=age_text,
                    age_min=age_min,
                    age_max=age_max,
                    price_text=price_text,
                    price_min=price_min,
                    venue_name=venue,
                    address=self.ADDRESS,
                    region="경기도 고양시",
                    latitude=None,
                    longitude=None,
                    image_url=image_url,
                    child_relevance_score=child_relevance(title, age_text, description),
                    license_code=self.info.license_code,
                    fetched_at=datetime.now(KST),
                    raw={
                        "program_id": program_id,
                        "summary": summary,
                        "details": details,
                        "operating_hours": operating_hours,
                        "duration": duration,
                        "source_url": self.LIST_URL,
                    },
                )
            )

        if not events:
            raise RuntimeError(
                "Hyundai Motorstudio page structure changed: no workshop titles parsed"
            )
        if cards_with_details == 0:
            raise RuntimeError(
                "Hyundai Motorstudio page structure changed: no detail fields parsed"
            )
        return events

    def crawl(self, client: PoliteHttpClient, window: CrawlWindow) -> Iterable[Event]:
        del window  # Programs are recurring and the public list has no event dates.
        client.assert_html_allowed(self.LIST_URL)
        html = client.get_text(self.LIST_URL)
        yield from self.parse_html(html)
