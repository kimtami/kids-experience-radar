from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
import re
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

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


_DATE_RE = r"20\d{2}[-./]\d{1,2}[-./]\d{1,2}"
_CHILD_CATEGORIES = ("어린이", "아동", "가족", "유아", "청소년")
_CHILD_TOKENS = (
    "초등",
    "어린이",
    "아동",
    "가족",
    "유아",
    "자녀",
    "키즈",
    "청소년",
)
_POSSIBILITY_TOKENS = (
    "체험",
    "방학",
    "만들기",
    "공예",
    "놀이",
    "요리",
    "전통",
    "생태",
    "과학",
    "미디어",
    "박물관",
    "주말",
)
_VENUE_ADDRESS_MARKERS = (
    ("수원전통문화관 예절교육관", "경기도 수원시 팔달구 정조로 887"),
    ("수원전통문화관 식생활체험관", "경기도 수원시 팔달구 정조로 893"),
    ("수원전통문화관 제공헌", "경기도 수원시 팔달구 정조로 893"),
    ("정조테마공연장", "경기도 수원시 팔달구 정조로 817"),
    ("망포글빛도서관", "경기도 수원시 영통구 망포로 100"),
    ("111CM", "경기도 수원시 장안구 수성로 195"),
)


@dataclass(slots=True)
class SwcfListFact:
    external_id: str
    title: str
    detail_url: str
    category: str | None
    event_dates: tuple[str, str] | None
    status: str | None
    venue: str | None


@dataclass(slots=True)
class SwcfDetailFact:
    category: str | None
    application_dates: tuple[str, str] | None
    application_method: str | None
    event_dates: tuple[str, str] | None
    schedule: str | None
    venue: str | None
    price: str | None
    provider: str | None
    phone: str | None
    target: str | None


class SuwonCultureFoundationEducationSource(Source):
    """Collect public education metadata from Suwon Cultural Foundation."""

    ORIGIN = "https://www.swcf.or.kr"
    LIST_URL = f"{ORIGIN}/?p=30"
    PUBLIC_RAW_FIELDS = frozenset(
        {
            "external_id",
            "title",
            "category",
            "application_period",
            "application_method",
            "event_period",
            "schedule",
            "target",
            "venue",
            "status",
            "price",
            "provider",
            "phone",
        }
    )

    def __init__(self) -> None:
        self.info = SourceInfo(
            source_id="suwon_culture_foundation_education",
            name="수원문화재단 어린이·가족 교육·체험",
            owner="수원문화재단",
            source_type="public_html",
            official_url=self.LIST_URL,
            license_code=None,
            enabled_by_default=False,
            policy_status="approved_html",
            notes=(
                "Official public education list/detail GET with runtime robots check. "
                "Stores factual metadata only. Never follows or calls the external "
                "booking, reception, login, identity, payment, or submission links."
            ),
        )

    @classmethod
    def _canonical_detail(cls, value: object | None) -> tuple[str, str] | None:
        href = clean_text(value)
        if not href:
            return None
        parsed = urlparse(href)
        if parsed.scheme and parsed.scheme != "https":
            return None
        if parsed.netloc and parsed.netloc != "www.swcf.or.kr":
            return None
        if parsed.path not in {"", "/"} or parsed.fragment:
            return None
        query = parse_qs(parsed.query)
        if (query.get("p") or [None])[0] != "30_view":
            return None
        idx = clean_text((query.get("idx") or [None])[0])
        if not idx or not re.fullmatch(r"\d{1,12}", idx):
            return None
        return idx, f"{cls.ORIGIN}/?p=30_view&idx={idx}"

    @classmethod
    def parse_list(cls, html: str) -> list[SwcfListFact]:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.select_one("table#ctable1")
        caption = clean_text(table.select_one("caption").get_text(" ", strip=True)) if table else None
        if table is None or "교육정보" not in (caption or ""):
            raise RuntimeError("SWCF education list structure changed: table not found")

        rows = table.select("tbody tr")
        facts: list[SwcfListFact] = []
        for row in rows:
            cells = row.find_all("td", recursive=False)
            link = row.select_one("td.txt_left a[href]")
            if len(cells) < 5 or link is None:
                continue
            detail = cls._canonical_detail(link.get("href"))
            if detail is None:
                continue
            external_id, detail_url = detail
            for badge in link.select("span"):
                badge.decompose()
            title = clean_text(link.get_text(" ", strip=True))
            if not title:
                continue
            dates = re.findall(_DATE_RE, cells[1].get_text(" ", strip=True))
            facts.append(
                SwcfListFact(
                    external_id=external_id,
                    title=title,
                    detail_url=detail_url,
                    category=clean_text(cells[0].get_text(" ", strip=True)),
                    event_dates=(dates[0], dates[1]) if len(dates) >= 2 else None,
                    status=clean_text(cells[2].get_text(" ", strip=True)),
                    venue=clean_text(cells[4].get_text(" ", strip=True)),
                )
            )
        if rows and not facts:
            raise RuntimeError("SWCF education list structure changed: no valid rows")
        return facts

    @staticmethod
    def _dates(value: str | None) -> tuple[str, str] | None:
        matches = re.findall(_DATE_RE, value or "")
        return (matches[0], matches[1]) if len(matches) >= 2 else None

    @staticmethod
    def _target_text(soup: BeautifulSoup) -> str | None:
        article = soup.select_one(".schedule_box .narticle")
        if article is None:
            return None
        lines = [
            text
            for raw in article.get_text("\n", strip=True).splitlines()
            if (text := clean_text(raw))
        ]
        for index, line in enumerate(lines):
            match = re.search(
                r"(?:^|[·•○*-])\s*(?:참여|교육|모집|수강|운영)?\s*대상"
                r"\s*[:：]\s*(.*)",
                line,
            )
            if match:
                target = clean_text(match.group(1))
                if not target and index + 1 < len(lines):
                    target = lines[index + 1]
                if target:
                    return target[:180]
        return None

    @classmethod
    def parse_detail(cls, html: str) -> SwcfDetailFact:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.select_one("table.list2")
        caption = clean_text(table.select_one("caption").get_text(" ", strip=True)) if table else None
        if table is None or "교육정보 상세" not in (caption or ""):
            raise RuntimeError("SWCF education detail structure changed: table not found")
        fields: dict[str, str] = {}
        for row in table.select("tbody tr"):
            label_node = row.find("th", recursive=False)
            value_node = row.find("td", recursive=False)
            label = clean_text(label_node.get_text(" ", strip=True)) if label_node else None
            value = clean_text(value_node.get_text(" ", strip=True)) if value_node else None
            if label and value:
                fields[label.replace(" ", "")] = value
        if not fields:
            raise RuntimeError("SWCF education detail structure changed: no metadata")
        return SwcfDetailFact(
            category=fields.get("교육분류"),
            application_dates=cls._dates(fields.get("접수기간")),
            application_method=fields.get("접수방법"),
            event_dates=cls._dates(fields.get("교육기간")),
            schedule=fields.get("교육시간"),
            venue=fields.get("교육장소"),
            price=fields.get("이용료"),
            provider=fields.get("주최/주관"),
            phone=fields.get("문의처"),
            target=cls._target_text(soup),
        )

    @staticmethod
    def _candidate(fact: SwcfListFact) -> bool:
        category = (fact.category or "").casefold()
        if "성인" in category and not any(token in category for token in _CHILD_CATEGORIES):
            return False
        haystack = f"{fact.title} {fact.category or ''} {fact.venue or ''}".casefold()
        return any(token in haystack for token in _CHILD_TOKENS) or any(
            token in haystack for token in _POSSIBILITY_TOKENS
        )

    @staticmethod
    def _detail_candidate(detail: SwcfDetailFact) -> bool:
        target = (detail.target or "").casefold()
        if not target or "성인" not in target:
            return True
        has_child = any(token in target for token in _CHILD_TOKENS) or bool(
            re.search(r"(?:[4-9]|1[0-3])\s*세", target)
        )
        return has_child

    @staticmethod
    def _age_range(value: str | None) -> tuple[int | None, int | None]:
        text = clean_text(value) or ""
        normalized = text.replace("초등학교", "초등")
        age_min, age_max, _ = parse_age_range(normalized)
        stated_ages = [int(raw) for raw in re.findall(r"(\d{1,2})\s*세", text)]
        stated_grades = [
            int(raw) + 6
            for raw in re.findall(r"초등(?:학교)?\s*([1-6])\s*학년", text)
        ]
        if stated_ages and stated_grades:
            return min(stated_ages), max(stated_grades)
        if stated_ages and "이상" in text:
            return min(stated_ages), 13 if "초등" in text else age_max
        if stated_grades and "이상" in text:
            return min(stated_grades), 13
        if stated_grades and "성인" in text:
            return min(stated_grades), 13
        if stated_grades and "이하" in text:
            return 7, max(stated_grades)
        return age_min, age_max

    @staticmethod
    def _month_keys(start: datetime, end: datetime) -> list[tuple[int, int]]:
        cursor = date(start.year, start.month, 1)
        last = date(end.year, end.month, 1)
        result: list[tuple[int, int]] = []
        while cursor <= last:
            result.append((cursor.year, cursor.month))
            if len(result) > 24:
                raise RuntimeError("SWCF crawl window exceeds 24 calendar months")
            cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
        return result

    @staticmethod
    def _overlaps(event: Event, window: CrawlWindow) -> bool:
        if event.event_start is None and event.event_end is None:
            return True
        start = event.event_start or event.event_end
        end = event.event_end or event.event_start
        assert start is not None and end is not None
        return start <= window.end and end >= window.start

    def _map(self, fact: SwcfListFact, detail: SwcfDetailFact) -> Event:
        category = detail.category or fact.category
        event_dates = detail.event_dates or fact.event_dates
        age_text = detail.target
        if not age_text and any(token in (category or "") for token in _CHILD_CATEGORIES):
            age_text = category
        age_min, age_max = self._age_range(age_text)
        price_min, price_text = parse_price(detail.price)
        event_start = parse_datetime(event_dates[0]) if event_dates else None
        event_end = parse_datetime(event_dates[1], end_of_day=True) if event_dates else None
        apply_start = (
            parse_datetime(detail.application_dates[0])
            if detail.application_dates
            else None
        )
        apply_end = (
            parse_datetime(detail.application_dates[1], end_of_day=True)
            if detail.application_dates
            else None
        )
        venue = detail.venue or fact.venue
        address = None
        # Multi-venue series cannot safely be represented by a single point.
        if venue and "," not in venue:
            for marker, candidate in _VENUE_ADDRESS_MARKERS:
                if marker in venue:
                    address = candidate
                    break
        description = f"교육시간: {detail.schedule}" if detail.schedule else None
        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=fact.external_id,
            title=fact.title,
            detail_url=fact.detail_url,
            provider_name=detail.provider or "수원문화재단",
            category=f"교육/{category}" if category else "교육·체험",
            description=description,
            event_start=event_start,
            event_end=event_end,
            apply_start=apply_start,
            apply_end=apply_end,
            status=fact.status,
            age_text=age_text,
            age_min=age_min,
            age_max=age_max,
            price_text=price_text,
            price_min=price_min,
            venue_name=venue,
            address=address,
            region="경기도 수원시",
            latitude=None,
            longitude=None,
            image_url=None,
            phone=detail.phone,
            is_online="온라인 교육" in f"{fact.title} {venue or ''}",
            child_relevance_score=child_relevance(
                fact.title, age_text, description
            ),
            license_code=self.info.license_code,
            fetched_at=datetime.now(KST),
            raw={
                "external_id": fact.external_id,
                "title": fact.title,
                "category": category,
                "application_period": (
                    " ~ ".join(detail.application_dates)
                    if detail.application_dates
                    else None
                ),
                "application_method": detail.application_method,
                "event_period": " ~ ".join(event_dates) if event_dates else None,
                "schedule": detail.schedule,
                "target": detail.target,
                "venue": venue,
                "status": fact.status,
                "price": detail.price,
                "provider": detail.provider,
                "phone": detail.phone,
            },
        )

    def crawl(
        self, client: PoliteHttpClient, window: CrawlWindow
    ) -> Iterable[Event]:
        client.assert_html_allowed(self.LIST_URL)
        seen: set[str] = set()
        for year, month in self._month_keys(window.start, window.end):
            html = client.get_text(
                self.LIST_URL,
                params={"p": "30", "curYear": year, "curMonth": month},
            )
            for fact in self.parse_list(html):
                if fact.external_id in seen or not self._candidate(fact):
                    continue
                detail = self.parse_detail(client.get_text(fact.detail_url))
                if not self._detail_candidate(detail):
                    continue
                event = self._map(fact, detail)
                if self._overlaps(event, window):
                    seen.add(fact.external_id)
                    yield event


__all__ = ["SuwonCultureFoundationEducationSource"]
