from __future__ import annotations

from datetime import datetime
import re
from typing import Iterable

from bs4 import BeautifulSoup, Tag

from ..http import PoliteHttpClient
from ..models import CrawlWindow, Event
from ..normalizers import (
    KST,
    child_relevance,
    clean_text,
    parse_age_range,
    parse_date_range,
)
from .base import Source, SourceInfo


_PROGRAM_ID_RE = re.compile(r"goDetail\s*\(\s*['\"]?(\d+)['\"]?\s*\)")
_CHILD_TOKENS = ("초등", "어린이", "아동", "가족", "유아", "청소년", "보호자")
_ADULT_ONLY_TOKENS = ("성인", "일반인", "교원", "교사", "전문가", "개발자")


MUSEUMS: dict[int, tuple[str, str, str]] = {
    1: ("national_museum_korea", "국립중앙박물관", "서울특별시"),
    2: ("gyeongju", "국립경주박물관", "경상북도 경주시"),
    3: ("gwangju", "국립광주박물관", "광주광역시"),
    4: ("jeonju", "국립전주박물관", "전북특별자치도 전주시"),
    5: ("daegu", "국립대구박물관", "대구광역시"),
    6: ("buyeo", "국립부여박물관", "충청남도 부여군"),
    7: ("gongju", "국립공주박물관", "충청남도 공주시"),
    8: ("jinju", "국립진주박물관", "경상남도 진주시"),
    9: ("cheongju", "국립청주박물관", "충청북도 청주시"),
    10: ("gimhae", "국립김해박물관", "경상남도 김해시"),
    11: ("jeju", "국립제주박물관", "제주특별자치도 제주시"),
    12: ("chuncheon", "국립춘천박물관", "강원특별자치도 춘천시"),
    13: ("naju", "국립나주박물관", "전라남도 나주시"),
    14: ("iksan", "국립익산박물관", "전북특별자치도 익산시"),
}


def _text(node: Tag | None) -> str | None:
    return clean_text(node.get_text(" ", strip=True)) if node else None


def _details(card: Tag) -> dict[str, str]:
    result: dict[str, str] = {}
    for block in card.select("dl.info_text"):
        label = _text(block.select_one("dt"))
        value = _text(block.select_one("dd"))
        if label and value:
            result[label.replace(" ", "")] = value
    return result


def _is_child_program(title: str, audience: str | None) -> bool:
    text = f"{title} {audience or ''}".casefold()
    explicit_child = any(token in text for token in _CHILD_TOKENS)
    if not explicit_child:
        return False
    if any(token in text for token in _ADULT_ONLY_TOKENS) and not any(
        token in text for token in ("가족", "학생", "아동", "보호자 동반", "자녀")
    ):
        return False
    return True


class ModuMuseumSource(Source):
    """Public education listings for the 14 museums on MODU."""

    LIST_URL = "https://modu.museum.go.kr/learn"
    DETAIL_ROOT = "https://modu.museum.go.kr/learn/detail/"

    def __init__(self, museum_id: int) -> None:
        if museum_id not in MUSEUMS:
            raise ValueError(f"unknown MODU museum id: {museum_id}")
        self.museum_id = museum_id
        slug, institution, region = MUSEUMS[museum_id]
        self.institution = institution
        self.region = region
        self.list_url = (
            f"{self.LIST_URL}?museum={museum_id}&searchApplyStatus=ONGOING"
        )
        self.info = SourceInfo(
            source_id=f"modu_museum_{slug}",
            name=f"{institution} 어린이·가족 교육",
            owner=institution,
            source_type="reviewed_public_html",
            official_url=self.list_url,
            license_code=None,
            enabled_by_default=False,
            policy_status="reviewed_public_html",
            notes=(
                "Official MODU public list only; facts and canonical detail links only. "
                "No images, full descriptions, login, likes, or application calls."
            ),
        )

    @classmethod
    def all_sources(cls) -> list["ModuMuseumSource"]:
        return [cls(museum_id) for museum_id in sorted(MUSEUMS)]

    def parse_html(self, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        container = soup.select_one("#listUl")
        if container is None:
            raise RuntimeError("MODU page structure changed: #listUl not found")

        events: list[Event] = []
        valid_ids = 0
        for card in container.select("li .card.type02"):
            trigger = card.select_one("[onclick*='goDetail']")
            match = _PROGRAM_ID_RE.search(str(trigger.get("onclick") or "")) if trigger else None
            if not match:
                continue
            valid_ids += 1
            program_id = match.group(1)
            title = _text(card.select_one(".cont .title"))
            if not title:
                continue
            facts = _details(card)
            audience = facts.get("교육대상")
            if not _is_child_program(title, audience):
                continue

            institution = _text(card.select_one(".writer")) or self.institution
            status_parts = [
                value
                for node in card.select(".cont .badge > span")
                if (value := _text(node))
            ]
            status = " · ".join(dict.fromkeys(status_parts)) or None
            period = facts.get("교육기간")
            event_start, event_end = parse_date_range(period)
            age_min, age_max, age_text = parse_age_range(audience)

            events.append(
                Event(
                    source_id=self.info.source_id,
                    source_name=self.info.name,
                    external_id=program_id,
                    title=title,
                    detail_url=f"{self.DETAIL_ROOT}{program_id}",
                    provider_name=institution,
                    category="박물관 교육·체험",
                    description=None,
                    event_start=event_start,
                    event_end=event_end,
                    status=status,
                    age_text=age_text,
                    age_min=age_min,
                    age_max=age_max,
                    venue_name=institution,
                    address=None,
                    region=self.region,
                    latitude=None,
                    longitude=None,
                    image_url=None,
                    child_relevance_score=child_relevance(title, age_text),
                    license_code=self.info.license_code,
                    fetched_at=datetime.now(KST),
                    raw={
                        "program_id": program_id,
                        "education_period": period,
                        "audience": audience,
                        "status": status,
                        "institution": institution,
                    },
                )
            )

        if valid_ids == 0 and container.select("li"):
            raise RuntimeError("MODU page structure changed: no valid program ids parsed")
        return events

    @staticmethod
    def _overlaps(event: Event, window: CrawlWindow) -> bool:
        if event.event_start is None and event.event_end is None:
            return True
        start = event.event_start or event.event_end
        end = event.event_end or event.event_start
        assert start is not None and end is not None
        return start <= window.end and end >= window.start

    def crawl(self, client: PoliteHttpClient, window: CrawlWindow) -> Iterable[Event]:
        client.assert_html_allowed(self.list_url)
        html = client.get_text(
            self.LIST_URL,
            params={"museum": self.museum_id, "searchApplyStatus": "ONGOING"},
        )
        for event in self.parse_html(html):
            if self._overlaps(event, window):
                yield event
