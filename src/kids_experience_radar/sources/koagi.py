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
    parse_datetime,
    parse_price,
)
from .base import Source, SourceInfo


_PROGRAM_ID_RE = re.compile(r"opGoPrgrmDtl\s*\(\s*['\"](\d+)['\"]\s*\)")
_DATE_TIME_RE = re.compile(
    r"(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})(?:\s*\((\d{1,2}:\d{2})\))?"
)
_CHILD_TOKENS = (
    "초등",
    "어린이",
    "아동",
    "가족",
    "유아",
    "청소년",
    "전연령",
    "누구나",
    "보호자",
)


SITES: dict[int, tuple[str, str, str]] = {
    2: ("baekdudaegan", "국립백두대간수목원", "경상북도 봉화군"),
    3: ("sejong", "국립세종수목원", "세종특별자치시"),
    4: ("native_plants", "국립한국자생식물원", "강원특별자치도 평창군"),
    5: ("garden_culture", "국립정원문화원", "전라남도 담양군"),
}


def _text(node: Tag | None) -> str | None:
    return clean_text(node.get_text(" ", strip=True)) if node else None


def _details(card: Tag) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in card.select("ul.dot-info > li"):
        label = _text(row.select_one(":scope > strong"))
        value = _text(row.select_one(":scope > p"))
        if label and value:
            result[label.replace(" ", "")] = value
    return result


def _parse_datetime_range(value: str | None) -> tuple[datetime | None, datetime | None]:
    text = clean_text(value)
    if not text:
        return None, None
    matches = _DATE_TIME_RE.findall(text)
    parsed: list[datetime | None] = []
    for date_value, time_value in matches[:2]:
        rendered = f"{date_value} {time_value}" if time_value else date_value
        parsed.append(parse_datetime(rendered, end_of_day=False))
    if not parsed:
        return None, None
    start = parsed[0]
    if len(parsed) == 1:
        end = parse_datetime(matches[0][0], end_of_day=True)
    elif matches[1][1]:
        end = parsed[1]
    else:
        end = parse_datetime(matches[1][0], end_of_day=True)
    return start, end


def _is_child_program(title: str, audience: str | None) -> bool:
    text = f"{title} {audience or ''}".casefold()
    if "성인" in text and not any(
        token in text for token in ("가족", "어린이", "아동", "유아", "청소년", "초등")
    ):
        return False
    if any(token in text for token in _CHILD_TOKENS):
        return True
    age_min, age_max, _ = parse_age_range(audience)
    return (age_min is not None and age_min <= 13) or (
        age_max is not None and age_max <= 18
    )


class KoagiEducationSource(Source):
    """Public education cards from the KOAGI integrated reservation site."""

    LIST_URL = (
        "https://reserve.koagi.or.kr/reserve/edc/prgrm/aply/"
        "BD_selectReserveEdcPrgrmList.do"
    )
    DETAIL_URL = (
        "https://reserve.koagi.or.kr/reserve/edc/prgrm/aply/"
        "BD_selectReserveEdcPrgrmFrom.do"
    )

    def __init__(self, site_seq: int) -> None:
        if site_seq not in SITES:
            raise ValueError(f"unknown KOAGI site sequence: {site_seq}")
        self.site_seq = site_seq
        slug, institution, region = SITES[site_seq]
        self.institution = institution
        self.region = region
        self.list_url = f"{self.LIST_URL}?q_siteSeq={site_seq}"
        self.info = SourceInfo(
            source_id=f"koagi_{slug}_education",
            name=f"{institution} 어린이·가족 교육",
            owner=institution,
            source_type="reviewed_public_html",
            official_url=self.list_url,
            license_code=None,
            enabled_by_default=False,
            policy_status="reviewed_public_html",
            notes=(
                "Official KOAGI public education list only; factual labels and canonical "
                "detail links only. Its semantic robots 404 is handled as no rules under "
                "RFC 9309 section 2.3.1.3; ambiguous HTML/WAF and 5xx still fail closed. "
                "No images, full descriptions, login, or application calls."
            ),
        )

    @classmethod
    def all_sources(cls) -> list["KoagiEducationSource"]:
        return [cls(site_seq) for site_seq in sorted(SITES)]

    def parse_html(self, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        container = soup.select_one("ul.gallery-items.gallery-poster-edu")
        if container is None:
            raise RuntimeError("KOAGI page structure changed: gallery-poster-edu not found")

        events: list[Event] = []
        valid_ids = 0
        for card in container.select(":scope > li"):
            match = _PROGRAM_ID_RE.search(str(card.get("onclick") or ""))
            if not match:
                continue
            valid_ids += 1
            program_id = match.group(1)
            title = _text(card.select_one(".info-wrap .title > strong"))
            if not title:
                continue
            facts = _details(card)
            audience = facts.get("이용대상")
            if not _is_child_program(title, audience):
                continue

            status = next(
                (
                    value
                    for node in card.select(".badges .badge")
                    if "outline" not in (node.get("class") or [])
                    and (value := _text(node))
                ),
                None,
            )
            categories = [
                value
                for node in card.select(".badges .badge.outline")
                if (value := _text(node))
            ]
            application_period = facts.get("접수일시")
            use_period = facts.get("이용일시")
            apply_start, apply_end = _parse_datetime_range(application_period)
            event_start, event_end = _parse_datetime_range(use_period)
            age_min, age_max, age_text = parse_age_range(audience)
            price_min, price_text = parse_price(facts.get("참가비"))

            participant = facts.get("참여자")
            application_method = facts.get("신청방법")
            capacity = facts.get("모집정원")
            recruitment_type = facts.get("모집유형")
            description_parts = [
                f"참여자: {participant}" if participant else None,
                f"신청방법: {application_method}" if application_method else None,
                f"모집정원: {capacity}" if capacity else None,
                f"모집유형: {recruitment_type}" if recruitment_type else None,
            ]
            description = " · ".join(part for part in description_parts if part) or None
            detail_url = (
                f"{self.DETAIL_URL}?q_siteSeq={self.site_seq}&q_prgrmNo={program_id}"
            )

            events.append(
                Event(
                    source_id=self.info.source_id,
                    source_name=self.info.name,
                    external_id=f"{self.site_seq}:{program_id}",
                    title=title,
                    detail_url=detail_url,
                    provider_name=self.institution,
                    category=" · ".join(categories) or "수목원 교육·체험",
                    description=description,
                    event_start=event_start,
                    event_end=event_end,
                    apply_start=apply_start,
                    apply_end=apply_end,
                    status=status,
                    age_text=age_text,
                    age_min=age_min,
                    age_max=age_max,
                    price_text=price_text,
                    price_min=price_min,
                    venue_name=self.institution,
                    address=None,
                    region=self.region,
                    latitude=None,
                    longitude=None,
                    image_url=None,
                    child_relevance_score=child_relevance(title, age_text, description),
                    license_code=self.info.license_code,
                    fetched_at=datetime.now(KST),
                    raw={
                        "program_id": program_id,
                        "site_seq": self.site_seq,
                        "status": status,
                        "application_period": application_period,
                        "use_period": use_period,
                        "participant": participant,
                        "price": facts.get("참가비"),
                        "audience": audience,
                        "application_method": application_method,
                        "capacity": capacity,
                        "recruitment_type": recruitment_type,
                        "categories": categories,
                    },
                )
            )

        if valid_ids == 0 and container.select("li"):
            raise RuntimeError("KOAGI page structure changed: no valid program ids parsed")
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
        html = client.get_text(self.LIST_URL, params={"q_siteSeq": self.site_seq})
        for event in self.parse_html(html):
            if self._overlaps(event, window):
                yield event
