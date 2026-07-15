from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
import re
from urllib.parse import parse_qs, urlencode, urlparse

from bs4 import BeautifulSoup

from ..http import PoliteHttpClient
from ..models import CrawlWindow, Event
from ..normalizers import KST, child_relevance, clean_text, parse_age_range, parse_datetime
from .base import Source, SourceInfo


_DATE_RE = r"20\d{2}[-./]\d{1,2}[-./]\d{1,2}"
_CHILD_TOKENS = (
    "초등",
    "어린이",
    "아동",
    "가족",
    "키즈",
    "자녀",
    "청소년",
    "유아",
    "꿈나무",
)
_POSSIBILITY_TOKENS = (
    "체험",
    "공방",
    "과학",
    "생태",
    "수목원",
    "박물관",
    "만들기",
    "탐방",
    "방학",
    "목공",
)
_ADULT_ONLY_TOKENS = ("성인", "지도사", "자격증", "교사", "강사", "시니어")


# The list publishes venue names rather than street addresses.  These stable,
# official municipal venue addresses make the records usable by the address
# geocoder while the original venue label remains in ``venue_name`` and raw.
_VENUE_ADDRESSES = {
    "서울대학교 수원수목원": "경기도 수원시 권선구 서둔동 92-6",
    "수원시 목공체험장": "경기도 수원시 장안구 정조로 1085",
    "열림공원유아숲체험원": "경기도 수원시 영통구 이의동 1180",
    "다람쥐유아숲체험원": "경기도 수원시 권선구 당수동 308-1",
    "반딧불이유아숲체험원": "경기도 수원시 장안구 조원동 산6",
    "수원시평생학습관": "경기도 수원시 팔달구 월드컵로381번길 2",
    "일월수목원": "경기도 수원시 장안구 일월로 61",
    "영흥수목원": "경기도 수원시 영통구 영통로 435",
    "숙지공원유아숲체험원": "경기도 수원시 팔달구 화서동 산42",
    "수원여성인력개발센터": "경기도 수원시 영통구 반달로7번길 40",
    "광교호수공원유아숲체험원": "경기도 수원시 영통구 하동 999",
    "광교중앙공원유아숲체험원": "경기도 수원시 영통구 이의동 1302",
}


@dataclass(slots=True)
class SuwonListFact:
    external_id: str
    title: str
    detail_url: str
    application_dates: tuple[str, str] | None
    event_dates: tuple[str, str] | None
    schedule: str | None
    target: str | None
    capacity: str | None
    venue: str | None
    status: str | None


class SuwonEducationSource(Source):
    """Read Suwon's public education/class/experience result table only."""

    LIST_URL = "https://www.suwon.go.kr/web/reserv/edu/list.do"
    PAGE_SIZE = 100
    PROGRESS_CODES = ("72", "73")  # 접수중, 접수준비
    PUBLIC_RAW_FIELDS = frozenset(
        {
            "external_id",
            "title",
            "application_period",
            "event_period",
            "schedule",
            "target",
            "capacity",
            "venue",
            "status",
        }
    )

    def __init__(self) -> None:
        self.info = SourceInfo(
            source_id="suwon_education_experience",
            name="수원시 교육·강좌·체험 어린이 가능 프로그램",
            owner="수원특례시",
            source_type="public_html",
            official_url=self.LIST_URL,
            license_code="KOGL-4",
            enabled_by_default=False,
            policy_status="approved_html",
            notes=(
                "Official public result-table GET with runtime robots check. Stores "
                "factual list metadata only. Never calls reservation, application, "
                "login, payment, queue, or personal-data paths. The page marks its "
                "work as KOGL type 4; review commercial reuse before production."
            ),
        )

    @staticmethod
    def _detail(value: object | None) -> tuple[str, str] | None:
        href = clean_text(value)
        if not href:
            return None
        parsed = urlparse(href)
        if parsed.path != "/web/reserv/edu/view.do":
            return None
        query = parse_qs(parsed.query)
        for key in ("eduMstSeq", "seqNo"):
            value = clean_text((query.get(key) or [None])[0])
            if value and re.fullmatch(r"\d{1,20}", value):
                detail_url = f"https://www.suwon.go.kr{parsed.path}?{urlencode({key: value})}"
                return f"{key}:{value}", detail_url
        return None

    @classmethod
    def parse_list(cls, html: str) -> list[SuwonListFact]:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.select_one("table.yeyak-t")
        if table is None or "교육" not in (
            clean_text(table.select_one("caption").get_text(" ", strip=True))
            if table.select_one("caption")
            else ""
        ):
            raise RuntimeError("Suwon education list structure changed: table not found")
        table_rows = table.select("tbody tr")
        facts: list[SuwonListFact] = []
        for row in table_rows:
            cells = row.find_all("td", recursive=False)
            link = row.select_one("td.p-subject a.title[href]")
            if len(cells) < 8 or link is None:
                continue
            detail = cls._detail(link.get("href"))
            title = clean_text(link.get_text(" ", strip=True))
            if detail is None or not title:
                continue
            external_id, detail_url = detail
            dates = re.findall(_DATE_RE, cells[2].get_text(" ", strip=True))
            application_dates = (dates[0], dates[1]) if len(dates) >= 2 else None
            event_dates = (dates[2], dates[3]) if len(dates) >= 4 else None
            facts.append(
                SuwonListFact(
                    external_id=external_id,
                    title=title,
                    detail_url=detail_url,
                    application_dates=application_dates,
                    event_dates=event_dates,
                    schedule=clean_text(cells[3].get_text(" ", strip=True)),
                    target=clean_text(cells[4].get_text(" ", strip=True)),
                    capacity=clean_text(cells[5].get_text(" ", strip=True)),
                    venue=clean_text(cells[6].get_text(" ", strip=True)),
                    status=clean_text(cells[7].get_text(" ", strip=True)),
                )
            )
        if table_rows and not facts:
            raise RuntimeError("Suwon education list structure changed: no valid rows")
        return facts

    @staticmethod
    def _candidate(fact: SuwonListFact) -> bool:
        haystack = f"{fact.title} {fact.target or ''}".casefold()
        has_child = any(token in haystack for token in _CHILD_TOKENS)
        if not has_child and any(token in haystack for token in _ADULT_ONLY_TOKENS):
            return False
        return has_child or any(token in haystack for token in _POSSIBILITY_TOKENS)

    @staticmethod
    def _audience(fact: SuwonListFact) -> tuple[int | None, int | None, str | None]:
        target = clean_text(fact.target)
        if target and target.casefold() not in {"전체", "누구나", "시민"}:
            age_min, age_max, age_text = parse_age_range(target)
            return age_min, age_max, age_text
        title = fact.title
        range_match = re.search(r"(\d{1,2})\s*[~–-]\s*(\d{1,2})\s*세", title)
        if range_match:
            first, last = (int(value) for value in range_match.groups())
            return min(first, last), max(first, last), range_match.group(0)
        for token, label in (
            ("초등", "초등학생"),
            ("어린이", "어린이"),
            ("아동", "아동"),
            ("가족", "가족"),
            ("청소년", "청소년"),
            ("유아", "유아"),
        ):
            if token in title:
                age_min, age_max, _ = parse_age_range(label)
                return age_min, age_max, label
        return None, None, None

    @staticmethod
    def _overlaps(event: Event, window: CrawlWindow) -> bool:
        if event.event_start is None and event.event_end is None:
            return True
        start = event.event_start or event.event_end
        end = event.event_end or event.event_start
        assert start is not None and end is not None
        return start <= window.end and end >= window.start

    def _map(self, fact: SuwonListFact) -> Event:
        age_min, age_max, age_text = self._audience(fact)
        apply_start = (
            parse_datetime(fact.application_dates[0]) if fact.application_dates else None
        )
        apply_end = (
            parse_datetime(fact.application_dates[1], end_of_day=True)
            if fact.application_dates
            else None
        )
        event_start = parse_datetime(fact.event_dates[0]) if fact.event_dates else None
        event_end = (
            parse_datetime(fact.event_dates[1], end_of_day=True)
            if fact.event_dates
            else None
        )
        application_period = (
            " ~ ".join(fact.application_dates) if fact.application_dates else None
        )
        event_period = " ~ ".join(fact.event_dates) if fact.event_dates else None
        normalized_venue = re.sub(r"^\s*\d+\s*[.)]\s*", "", fact.venue or "")
        address = _VENUE_ADDRESSES.get(normalized_venue)
        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=fact.external_id,
            title=fact.title,
            detail_url=fact.detail_url,
            provider_name="수원특례시",
            category="교육·강좌·체험",
            description=f"운영: {fact.schedule}" if fact.schedule else None,
            event_start=event_start,
            event_end=event_end,
            apply_start=apply_start,
            apply_end=apply_end,
            status=fact.status,
            age_text=age_text,
            age_min=age_min,
            age_max=age_max,
            price_text=None,
            price_min=None,
            venue_name=fact.venue,
            address=address,
            region="경기도 수원시",
            latitude=None,
            longitude=None,
            image_url=None,
            phone=None,
            is_online="온라인" in f"{fact.title} {fact.venue or ''}",
            child_relevance_score=child_relevance(
                fact.title, age_text, fact.schedule
            ),
            license_code=self.info.license_code,
            fetched_at=datetime.now(KST),
            raw={
                "external_id": fact.external_id,
                "title": fact.title,
                "application_period": application_period,
                "event_period": event_period,
                "schedule": fact.schedule,
                "target": fact.target,
                "capacity": fact.capacity,
                "venue": fact.venue,
                "status": fact.status,
            },
        )

    def crawl(
        self, client: PoliteHttpClient, window: CrawlWindow
    ) -> Iterable[Event]:
        client.assert_html_allowed(self.LIST_URL)
        seen: set[str] = set()
        for progress_code in self.PROGRESS_CODES:
            for page in range(1, window.max_pages + 1):
                html = client.get_text(
                    self.LIST_URL,
                    params={
                        "q_progressStatusCd": progress_code,
                        "q_rowPerPage": self.PAGE_SIZE,
                        "q_currPage": page,
                    },
                )
                facts = self.parse_list(html)
                for fact in facts:
                    if fact.external_id in seen or not self._candidate(fact):
                        continue
                    event = self._map(fact)
                    if self._overlaps(event, window):
                        seen.add(fact.external_id)
                        yield event
                if len(facts) < self.PAGE_SIZE:
                    break


__all__ = ["SuwonEducationSource"]
