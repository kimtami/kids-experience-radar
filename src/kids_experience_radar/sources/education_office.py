from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import re
from typing import Iterable
from urllib.parse import urlencode, urljoin, urlparse

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


@dataclass(slots=True, frozen=True)
class EducationOfficeConfig:
    source_id: str
    name: str
    owner: str
    list_url: str
    detail_url: str
    menu_id: str
    region: str
    extra_query: tuple[tuple[str, str], ...] = ()

    @property
    def official_url(self) -> str:
        query = {"mi": self.menu_id, **dict(self.extra_query)}
        return f"{self.list_url}?{urlencode(query)}"


EDUCATION_OFFICE_CONFIGS = (
    EducationOfficeConfig(
        source_id="incheon_education_experience",
        name="인천광역시교육청 견학·체험",
        owner="인천광역시교육청",
        list_url="https://www.ice.go.kr/ice/exprn/selectExprnList.do",
        detail_url="https://www.ice.go.kr/ice/exprn/selectExprnInfo.do",
        menu_id="11607",
        region="인천광역시",
    ),
    EducationOfficeConfig(
        source_id="busan_education_experience",
        name="부산광역시교육청 견학·체험",
        owner="부산광역시교육청",
        list_url="https://home.pen.go.kr/yeyak/exprn/selectExprnList.do",
        detail_url="https://home.pen.go.kr/yeyak/exprn/selectExprnInfo.do",
        menu_id="14438",
        region="부산광역시",
        extra_query=(("contestAt", "N"),),
    ),
    EducationOfficeConfig(
        source_id="chungbuk_education_experience",
        name="충청북도교육청 견학·체험",
        owner="충청북도교육청",
        list_url="https://www.cbe.go.kr/yeyak/exprn/selectExprnList.do",
        detail_url="https://www.cbe.go.kr/yeyak/exprn/selectExprnInfo.do",
        menu_id="11424",
        region="충청북도",
    ),
    EducationOfficeConfig(
        source_id="jeonnam_education_experience",
        name="전남광주통합특별시교육청 견학·체험",
        owner="전남광주통합특별시교육청",
        list_url="https://yeyak.jne.kr/yeyak/exprn/selectExprnList.do",
        detail_url="https://yeyak.jne.kr/yeyak/exprn/selectExprnInfo.do",
        menu_id="10205166",
        region="전남광주통합특별시",
    ),
)


class EducationOfficeExperienceSource(Source):
    """Collect public education-office experience list and information pages.

    The connector never calls authentication, identity-verification, availability,
    application, or reservation-submission endpoints.
    """

    PAGE_SIZE = 10
    OPEN_STATUSES = ("REQST", "PREV")
    RAW_FACT_FIELDS = frozenset(
        {
            "provider_id",
            "exprn_seq",
            "exprn_period_seq",
            "application_target",
            "reservation_region",
        }
    )

    def __init__(self, config: EducationOfficeConfig) -> None:
        self.config = config
        self.info = SourceInfo(
            source_id=config.source_id,
            name=config.name,
            owner=config.owner,
            source_type="approved_html",
            official_url=config.official_url,
            license_code=None,
            enabled_by_default=False,
            policy_status="approved_html",
            notes=(
                "Official public list and information-detail GET only. Runtime robots "
                "check; no login, identity verification, availability, or application "
                "endpoint."
            ),
        )

    @staticmethod
    def _safe_id(value: object | None) -> str | None:
        text = clean_text(value)
        if not text or not re.fullmatch(r"[0-9A-Za-z_-]{1,100}", text):
            return None
        return text

    @staticmethod
    def _cell_fact(cell: Tag, label: str | None = None) -> str | None:
        fragment = BeautifulSoup(str(cell), "html.parser")
        for title in fragment.select(".tit"):
            title.decompose()
        text = clean_text(fragment.get_text(" ", strip=True))
        if label and text and text.startswith(label):
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

    @staticmethod
    def _age(value: str | None) -> tuple[int | None, int | None, str | None]:
        text = clean_text(value)
        if not text:
            return None, None, None
        normalized = text.replace("–", "-").replace("~", "-")
        grade_range = re.search(
            r"초(?:등(?:학교)?)?\s*\(?\s*([1-6])\s*(?:학년)?\s*\)?\s*-\s*"
            r"(?:초(?:등(?:학교)?)?\s*)?\(?\s*([1-6])\s*(?:학년)?\s*\)?",
            normalized,
        )
        if grade_range:
            first, last = (int(value) + 6 for value in grade_range.groups())
            return min(first, last), max(first, last), text
        minimum_grade = re.search(
            r"초(?:등(?:학교)?)?\s*\(?\s*([1-6])\s*(?:학년)?\s*\)?\s*이상",
            normalized,
        )
        if minimum_grade:
            return int(minimum_grade.group(1)) + 6, 12, text
        single_grade = re.search(
            r"초(?:등(?:학교)?)?\s*\(?\s*([1-6])\s*학년\s*\)?",
            normalized,
        )
        if single_grade:
            age = int(single_grade.group(1)) + 6
            return age, age, text
        return parse_age_range(text)

    @staticmethod
    def _normalize_status(value: str | None) -> str | None:
        text = clean_text(value)
        if not text:
            return None
        compact = re.sub(r"\s+", "", text)
        for status in (
            "접수중",
            "신청중",
            "접수예정",
            "신청예정",
            "예정",
            "예약가능",
            "마감",
            "종료",
            "예약불가",
        ):
            if status in compact:
                return status
        return text[:80]

    @staticmethod
    def _is_child_candidate(event: Event) -> bool:
        text = " ".join(
            part
            for part in (
                event.title,
                event.age_text or "",
                clean_text(event.raw.get("application_target")) or "",
            )
            if part
        ).casefold()
        scrubbed = re.sub(r"(?:대학생|중학생|고등학생)", "", text)
        scrubbed = scrubbed.replace("어린이집", "")
        explicit_child = any(
            marker in scrubbed for marker in ("어린이", "아동", "가족", "학생")
        ) or bool(re.search(r"초(?:등학생|\s*\(?\s*[1-6])", scrubbed))
        return explicit_child

    @staticmethod
    def _overlaps_window(event: Event, window: CrawlWindow) -> bool:
        start = event.event_start or event.event_end
        end = event.event_end or event.event_start
        if start is None and end is None:
            start = event.apply_start or event.apply_end
            end = event.apply_end or event.apply_start
        if start is None or end is None:
            return True
        return start <= window.end and end >= window.start

    def _detail_url(
        self,
        *,
        provider_id: str,
        exprn_seq: str,
        period_seq: str,
    ) -> str:
        query = {
            "mi": self.config.menu_id,
            **dict(self.config.extra_query),
            "srchRsSysId": provider_id,
            "exprnSeq": exprn_seq,
            "exprnPeriodSeq": period_seq,
        }
        return f"{self.config.detail_url}?{urlencode(query)}"

    def _list_params(self, *, status: str, page: int) -> dict[str, object]:
        return {
            "mi": self.config.menu_id,
            **dict(self.config.extra_query),
            "srchRsvSttus": status,
            "currPage": page,
            "pageIndex": self.PAGE_SIZE,
        }

    @staticmethod
    def max_page_from_html(html: str) -> int:
        soup = BeautifulSoup(html, "html.parser")
        pages = [1]
        text = clean_text(soup.get_text(" ", strip=True)) or ""
        for match in re.finditer(r"\b\d+\s*/\s*(\d+)\s*페이지", text):
            pages.append(int(match.group(1)))
        for node in soup.select("[onclick*='goPaging'], a[href*='goPaging']"):
            script = f"{node.get('onclick') or ''} {node.get('href') or ''}"
            pages.extend(int(value) for value in re.findall(r"goPaging\((\d+)\)", script))
        return max(pages)

    def parse_list_html(self, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        for row in soup.select("table tbody tr"):
            cells = row.find_all("td", recursive=False)
            if len(cells) < 8:
                continue

            title_cell = cells[2]
            internal = title_cell.select_one(
                "a.viewExprnInfo[data-id][data-period-id]"
            )
            provider_id: str | None = None
            exprn_seq: str | None = None
            period_seq: str | None = None
            if internal is not None:
                provider_id = self._safe_id(
                    internal.get("data-rssysid") or internal.get("data-rsSysId")
                )
                exprn_seq = self._safe_id(internal.get("data-id"))
                period_seq = self._safe_id(internal.get("data-period-id"))
                if not provider_id or not exprn_seq or not period_seq:
                    continue
                title_link = internal
                detail_url = self._detail_url(
                    provider_id=provider_id,
                    exprn_seq=exprn_seq,
                    period_seq=period_seq,
                )
                external_id = f"{provider_id}:{exprn_seq}:{period_seq}"
            else:
                title_link = next(
                    (
                        anchor
                        for anchor in title_cell.select("a[href]")
                        if urlparse(urljoin(self.config.list_url, anchor.get("href", ""))).scheme
                        in {"http", "https"}
                    ),
                    None,
                )
                if title_link is None:
                    continue
                detail_url = urljoin(self.config.list_url, title_link.get("href", ""))
                if urlparse(detail_url).scheme not in {"http", "https"}:
                    continue
                external_id = "external:" + hashlib.sha256(
                    "|".join(
                        (
                            detail_url,
                            self._cell_fact(cells[1]) or "",
                            self._cell_fact(cells[3]) or "",
                            self._cell_fact(cells[4]) or "",
                        )
                    ).encode("utf-8")
                ).hexdigest()[:20]

            title = clean_text(title_link.get_text(" ", strip=True))
            if not title:
                continue
            subtitles = [
                clean_text(node.get_text(" ", strip=True))
                for node in title_cell.find_all("p", recursive=False)
            ]
            subtitle = next(
                (value for value in subtitles if value and value not in title),
                None,
            )
            if subtitle:
                title = f"{title} — {subtitle}"

            provider_name = self._cell_fact(cells[1])
            event_start, event_end = self._parse_period(self._cell_fact(cells[3]))
            apply_start, apply_end = self._parse_period(self._cell_fact(cells[4]))
            age_min, age_max, age_text = self._age(self._cell_fact(cells[5]))
            application_target = self._cell_fact(cells[6])
            status = self._normalize_status(self._cell_fact(cells[7]))
            raw = {
                "provider_id": provider_id,
                "exprn_seq": exprn_seq,
                "exprn_period_seq": period_seq,
                "application_target": application_target,
                "reservation_region": None,
            }
            raw = {
                key: value
                for key, value in raw.items()
                if key in self.RAW_FACT_FIELDS
            }

            events.append(
                Event(
                    source_id=self.info.source_id,
                    source_name=self.info.name,
                    external_id=external_id,
                    title=title,
                    detail_url=detail_url,
                    provider_name=provider_name,
                    category="견학·체험",
                    event_start=event_start,
                    event_end=event_end,
                    apply_start=apply_start,
                    apply_end=apply_end,
                    status=status,
                    age_text=age_text,
                    age_min=age_min,
                    age_max=age_max,
                    venue_name=provider_name,
                    region=self.config.region,
                    child_relevance_score=child_relevance(title, age_text),
                    fetched_at=datetime.now(KST),
                    raw=raw,
                )
            )
        return events

    @staticmethod
    def parse_detail_html(html: str) -> dict[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one(".rsvInfoWrap .txt, .rveInfo .infoBox")
        if root is None:
            return {}
        facts: dict[str, str] = {}
        title = root.select_one("h3")
        title_text = clean_text(title.get_text(" ", strip=True) if title else None)
        if title_text:
            facts["title"] = title_text

        labels = {
            "운영기관": "provider_name",
            "체험기간": "event_period",
            "운영기간": "event_period",
            "신청기간": "application_period",
            "접수기간": "application_period",
            "체험대상": "age_text",
            "신청대상": "application_target",
            "예약지역": "reservation_region",
        }
        for item in root.select("ul > li"):
            label_node = item.find("p", recursive=False)
            if label_node is None:
                continue
            label = clean_text(label_node.get_text(" ", strip=True))
            fact_key = labels.get(label or "")
            if fact_key is None:
                continue
            value_node = item.find("div", class_="dsc", recursive=False)
            if value_node is not None:
                value = clean_text(value_node.get_text(" ", strip=True))
            else:
                fragment = BeautifulSoup(str(item), "html.parser")
                copied_label = fragment.find("p", recursive=False)
                if copied_label is None:
                    copied_label = fragment.find("p")
                if copied_label is not None:
                    copied_label.decompose()
                value = clean_text(fragment.get_text(" ", strip=True))
            if value:
                facts[fact_key] = value
        return facts

    def _apply_detail(self, event: Event, facts: dict[str, str]) -> Event:
        event.title = facts.get("title", event.title)
        event.provider_name = facts.get("provider_name", event.provider_name)
        event.venue_name = event.provider_name
        if period := facts.get("event_period"):
            event.event_start, event.event_end = self._parse_period(period)
        if period := facts.get("application_period"):
            event.apply_start, event.apply_end = self._parse_period(period)
        if target := facts.get("age_text"):
            event.age_min, event.age_max, event.age_text = self._age(target)
        event.raw["application_target"] = facts.get(
            "application_target", event.raw.get("application_target")
        )
        event.raw["reservation_region"] = facts.get("reservation_region")
        event.raw = {
            key: value
            for key, value in event.raw.items()
            if key in self.RAW_FACT_FIELDS
        }
        event.child_relevance_score = child_relevance(event.title, event.age_text)
        return event

    def crawl(
        self,
        client: PoliteHttpClient,
        window: CrawlWindow,
    ) -> Iterable[Event]:
        client.assert_html_allowed(self.config.list_url)
        seen: set[str] = set()
        for status in self.OPEN_STATUSES:
            for page in range(1, max(1, window.max_pages) + 1):
                html = client.get_text(
                    self.config.list_url,
                    params=self._list_params(status=status, page=page),
                )
                page_events = self.parse_list_html(html)
                if not page_events:
                    break
                for event in page_events:
                    if event.external_id in seen:
                        continue
                    seen.add(event.external_id)
                    if not self._is_child_candidate(event):
                        continue
                    if not self._overlaps_window(event, window):
                        continue

                    if event.raw.get("exprn_seq"):
                        client.assert_html_allowed(event.detail_url)
                        detail_html = client.get_text(event.detail_url)
                        self._apply_detail(event, self.parse_detail_html(detail_html))
                        if not self._is_child_candidate(event):
                            continue
                        if not self._overlaps_window(event, window):
                            continue
                    event.child_relevance_score = max(
                        event.child_relevance_score,
                        0.45,
                    )
                    yield event
                if page >= self.max_page_from_html(html):
                    break


def builtin_education_office_sources() -> list[EducationOfficeExperienceSource]:
    return [EducationOfficeExperienceSource(config) for config in EDUCATION_OFFICE_CONFIGS]


__all__ = [
    "EDUCATION_OFFICE_CONFIGS",
    "EducationOfficeConfig",
    "EducationOfficeExperienceSource",
    "builtin_education_office_sources",
]
