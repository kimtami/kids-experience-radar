from __future__ import annotations

from datetime import datetime
import re
from typing import Iterable
from urllib.parse import urlencode

from bs4 import BeautifulSoup, Tag

from ..http import PoliteHttpClient
from ..models import CrawlWindow, Event
from ..normalizers import (
    KST,
    child_relevance,
    clean_text,
    parse_age_range,
    parse_date_range,
    parse_datetime,
)
from .base import Source, SourceInfo


class GyeongbukEducationExperienceSource(Source):
    """Public-list collector for the Gyeongbuk education experience portal."""

    SOURCE_ID = "gyeongbuk_education_experience"
    SOURCE_NAME = "경상북도교육청 온체험 견학·체험"
    LIST_URL = "https://www.gbe.kr/edushare/exprn/selectExprnList.do"
    DETAIL_URL = "https://www.gbe.kr/edushare/exprn/selectExprnInfo.do"
    INSTITUTIONS_URL = (
        "https://www.gbe.kr/edushare/rs/search/selectRsTypeDetailList.do"
    )
    MENU_ID = "17609"
    RAW_FACT_FIELDS = frozenset(
        {"provider_id", "exprn_seq", "exprn_period_seq", "application_target"}
    )

    def __init__(self) -> None:
        self.info = SourceInfo(
            source_id=self.SOURCE_ID,
            name=self.SOURCE_NAME,
            owner="경상북도교육청",
            source_type="approved_html",
            official_url=f"{self.LIST_URL}?mi={self.MENU_ID}",
            license_code=None,
            enabled_by_default=False,
            policy_status="approved_html",
            notes=(
                "Public institution discovery and list pages only. Runtime robots check; "
                "no login, detail-page fetch, or reservation submission."
            ),
        )

    @staticmethod
    def _safe_id(value: object | None) -> str | None:
        text = clean_text(value)
        if not text or not re.fullmatch(r"[0-9A-Za-z_-]{1,80}", text):
            return None
        return text

    @classmethod
    def parse_institutions(cls, payload: object) -> dict[str, str]:
        if not isinstance(payload, list):
            raise ValueError("institution response must be a JSON list")
        institutions: dict[str, str] = {}
        for row in payload:
            if not isinstance(row, dict):
                continue
            provider_id = cls._safe_id(row.get("rsSysId"))
            provider_name = clean_text(row.get("rsSysNm"))
            if provider_id and provider_name:
                institutions[provider_id] = provider_name[:160]
        return institutions

    @staticmethod
    def _cell_fact(cell: Tag, label: str) -> str | None:
        fragment = BeautifulSoup(str(cell), "html.parser")
        for title in fragment.select(".tit"):
            title.decompose()
        text = clean_text(fragment.get_text(" ", strip=True))
        if text and text.startswith(label):
            text = clean_text(text[len(label) :])
        return text

    @staticmethod
    def _parse_period(value: str | None) -> tuple[datetime | None, datetime | None]:
        text = clean_text(value)
        if not text:
            return None, None
        parts = re.split(r"\s*[~～]\s*", text, maxsplit=1)
        if len(parts) != 2:
            return parse_date_range(text)
        start = parse_datetime(parts[0])
        end_has_time = bool(re.search(r"\d{1,2}:\d{2}", parts[1]))
        end = parse_datetime(parts[1], end_of_day=not end_has_time)
        return start, end

    @classmethod
    def parse_list_html(
        cls,
        html: str,
        *,
        institutions: dict[str, str] | None = None,
    ) -> list[Event]:
        providers = institutions or {}
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        for row in soup.select(".rvelst table tbody tr"):
            link = row.select_one("a.viewExprnInfo[data-id][data-period-id]")
            cells = row.find_all("td", recursive=False)
            if link is None or len(cells) < 8:
                continue

            exprn_seq = cls._safe_id(link.get("data-id"))
            period_seq = cls._safe_id(link.get("data-period-id"))
            provider_id = cls._safe_id(
                link.get("data-rssysid") or link.get("data-rsSysId")
            )
            if not exprn_seq or not period_seq or not provider_id:
                continue

            title_node = link.select_one(".pc_mint") or link.select_one("li")
            title = clean_text(
                title_node.get_text(" ", strip=True)
                if title_node
                else link.get_text(" ", strip=True)
            )
            if not title:
                continue

            provider_name = cls._cell_fact(cells[1], "기관명") or providers.get(
                provider_id
            )
            if provider_name:
                provider_name = provider_name[:160]
            event_start, event_end = cls._parse_period(
                cls._cell_fact(cells[3], "운영기간")
            )
            apply_start, apply_end = cls._parse_period(
                cls._cell_fact(cells[4], "접수기간")
            )
            age_source = cls._cell_fact(cells[5], "체험대상")
            age_min, age_max, age_text = parse_age_range(age_source)
            application_target = cls._cell_fact(cells[6], "신청대상")
            status = cls._cell_fact(cells[7], "예약상태")
            detail_query = urlencode(
                {
                    "srchRsSysId": provider_id,
                    "exprnSeq": exprn_seq,
                    "exprnPeriodSeq": period_seq,
                }
            )
            detail_url = f"{cls.DETAIL_URL}?{detail_query}"
            raw = {
                "provider_id": provider_id,
                "exprn_seq": exprn_seq,
                "exprn_period_seq": period_seq,
                "application_target": application_target,
            }
            raw = {key: value for key, value in raw.items() if key in cls.RAW_FACT_FIELDS}

            events.append(
                Event(
                    source_id=cls.SOURCE_ID,
                    source_name=cls.SOURCE_NAME,
                    external_id=f"{provider_id}:{exprn_seq}:{period_seq}",
                    title=title,
                    detail_url=detail_url,
                    provider_name=provider_name or providers.get(provider_id),
                    category="견학·체험",
                    event_start=event_start,
                    event_end=event_end,
                    apply_start=apply_start,
                    apply_end=apply_end,
                    status=status,
                    age_text=age_text,
                    age_min=age_min,
                    age_max=age_max,
                    region="경상북도",
                    child_relevance_score=child_relevance(title, age_text),
                    fetched_at=datetime.now(KST),
                    raw=raw,
                )
            )
        return events

    @staticmethod
    def _child_candidate(event: Event) -> bool:
        text = f"{event.title} {event.age_text or ''}".casefold()
        school_tokens = ("초등", "어린이", "아동", "학생", "가족")
        if "유아" in text and not any(token in text for token in school_tokens):
            return False
        return any(token in text for token in (*school_tokens, "보호자"))

    @staticmethod
    def _overlaps(event: Event, window: CrawlWindow) -> bool:
        if event.event_start is None and event.event_end is None:
            return True
        start = event.event_start or event.event_end
        end = event.event_end or event.event_start
        assert start is not None and end is not None
        return start <= window.end and end >= window.start

    def crawl(self, client: PoliteHttpClient, window: CrawlWindow) -> Iterable[Event]:
        client.assert_html_allowed(self.LIST_URL)
        payload = client.post(
            self.INSTITUTIONS_URL,
            data={"rsType": "exprn"},
        ).json()
        institutions = self.parse_institutions(payload)

        for page in range(1, window.max_pages + 1):
            html = client.get_text(
                self.LIST_URL,
                params={
                    "mi": self.MENU_ID,
                    "srchRsvSttus": "REQST",
                    "currPage": page,
                },
            )
            page_events = self.parse_list_html(html, institutions=institutions)
            if not page_events:
                break
            for event in page_events:
                if self._child_candidate(event) and self._overlaps(event, window):
                    yield event
