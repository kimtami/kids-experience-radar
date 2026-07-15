from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
import re
from urllib.parse import parse_qs, urlencode, urlparse

from bs4 import BeautifulSoup

from ..http import PoliteHttpClient
from ..models import CrawlWindow, Event
from ..normalizers import (
    KST,
    child_relevance,
    clean_text,
    parse_age_range,
    parse_price,
)
from .base import Source, SourceInfo


_DATE_RANGE_RE = re.compile(
    r"(?P<sy>(?:20)?\d{2})[./-](?P<sm>\d{1,2})[./-](?P<sd>\d{1,2})"
    r"\s*~\s*(?P<ey>(?:20)?\d{2})[./-](?P<em>\d{1,2})[./-](?P<ed>\d{1,2})"
)
_TIME_RE = re.compile(
    r"(?P<sh>[01]?\d|2[0-3])\s*(?:시|:)\s*(?P<sm>[0-5]?\d)?\s*분?"
    r"\s*~\s*(?P<eh>[01]?\d|2[0-3])\s*(?:시|:)\s*(?P<em>[0-5]?\d)?\s*분?"
)
_LANDLINE_PHONE_RE = re.compile(
    r"(?<!\d)(?:02-\d{3,4}-\d{4}|0(?:3[1-3]|4[1-4]|5[1-5]|6[1-4])-\d{3,4}-\d{4})(?!\d)"
)
_ADULT_ONLY_TOKENS = (
    "성인",
    "어르신",
    "시니어",
    "대학생",
    "교사",
    "강사",
    "직장인",
    "교원",
    "학부모",
    "지도사",
    "상담사",
    "활동가",
    "어린이집",
)
_TARGET_CHILD_TOKENS = ("초등", "아동", "유아", "청소년", "가족")
_TARGET_CHILD_PHRASES = (
    "어린이 대상",
)
_TARGET_COMPANION_PHRASES = (
    "어린이와",
    "어린이 동반",
    "자녀와",
    "자녀 동반",
    "보호자 동반",
)
_TARGET_COMPANION_RE = re.compile(
    r"(?:학부모|부모|보호자|성인|교사|강사|교원)\s*(?:와|과|및|,|·|/)\s*"
    r"(?:초등학생?|어린이|아동|유아|자녀)"
    r"|(?:초등학생?|어린이|아동|유아|자녀)\s*(?:와|과|및|,|·|/)\s*"
    r"(?:학부모|부모|보호자|성인|교사|강사|교원)"
)
_BARE_AGE_RANGE_RE = re.compile(r"(?<!\d)(\d{1,2})\s*(?:~|[-–])\s*(\d{1,2})\s*세")
_BARE_GRADE_RANGE_RE = re.compile(r"(?<!\d)([1-6])\s*(?:~|[-–])\s*([1-6])\s*학년")


@dataclass(slots=True)
class SuwonEcologyListFact:
    external_id: str
    title: str
    detail_url: str
    event_dates: tuple[str, str] | None
    target: str | None
    capacity: str | None
    status: str | None


@dataclass(slots=True)
class SuwonEcologyDetailFact:
    title: str
    category: str | None
    venue: str | None
    target: str | None
    event_dates: tuple[str, str] | None
    capacity: str | None
    schedule: str | None
    price: str | None
    status: str | None
    phone: str | None


@dataclass(slots=True)
class SuwonEcologyPage:
    facts: list[SuwonEcologyListFact]
    total: int
    current_page: int


class SuwonEcologyProgramSource(Source):
    """Collect public program facts from Suwon's ecology education center."""

    ORIGIN = "https://www.suwoneco.com"
    LIST_URL = f"{ORIGIN}/lmth/02_margorp/margorp_02.asp"
    PUBLIC_RAW_FIELDS = frozenset(
        {
            "external_id",
            "title",
            "category",
            "venue",
            "target",
            "event_period",
            "capacity",
            "schedule",
            "price",
            "status",
            "phone",
        }
    )

    def __init__(self) -> None:
        self.info = SourceInfo(
            source_id="suwon_ecology_child_programs",
            name="수원시 생태환경체험교육관 어린이·가족 프로그램",
            owner="수원시 생태환경체험교육관",
            source_type="public_html",
            official_url=self.LIST_URL,
            license_code=None,
            enabled_by_default=False,
            policy_status="approved_html",
            notes=(
                "Official public program list and information detail GET only. "
                "Runtime robots check required. Never calls the application form, "
                "application result, login, member, payment, or personal-data paths."
            ),
        )

    @staticmethod
    def _dates(
        value: str | None,
        *,
        required: bool = False,
        field_name: str = "event date",
    ) -> tuple[str, str] | None:
        match = _DATE_RANGE_RE.search(value or "")
        if match is None:
            if required:
                raise RuntimeError(
                    f"Suwon ecology {field_name} is missing or unparseable"
                )
            return None
        values = {key: int(raw) for key, raw in match.groupdict().items()}
        start_year = values["sy"] + 2000 if values["sy"] < 100 else values["sy"]
        end_year = values["ey"] + 2000 if values["ey"] < 100 else values["ey"]
        try:
            start = datetime(
                start_year,
                values["sm"],
                values["sd"],
            ).date()
            end = datetime(
                end_year,
                values["em"],
                values["ed"],
            ).date()
        except ValueError as exc:
            raise RuntimeError(
                f"Suwon ecology {field_name} contains an invalid date"
            ) from exc
        if end < start:
            raise RuntimeError(
                f"Suwon ecology {field_name} ends before it starts"
            )
        return start.isoformat(), end.isoformat()

    @classmethod
    def _canonical_detail(cls, href: object | None) -> tuple[str, str] | None:
        value = clean_text(href)
        if not value:
            return None
        parsed = urlparse(value)
        if parsed.scheme or parsed.netloc:
            return None
        if not parsed.path.endswith("margorp_02_view.asp"):
            return None
        idx = clean_text((parse_qs(parsed.query).get("idx") or [None])[0])
        if not idx or not re.fullmatch(r"\d{1,12}", idx):
            return None
        return idx, f"{cls.ORIGIN}/lmth/02_margorp/margorp_02_view.asp?idx={idx}"

    @classmethod
    def parse_page(cls, html: str) -> SuwonEcologyPage:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.select_one("table.board_list_pro")
        if table is None:
            raise RuntimeError("Suwon ecology list structure changed: table not found")

        total_node = soup.select_one("div.page_num_right span")
        total_text = clean_text(total_node.get_text(" ", strip=True)) if total_node else None
        if not total_text or not re.fullmatch(r"[\d,]+", total_text):
            raise RuntimeError(
                "Suwon ecology list structure changed: total count not found"
            )
        total = int(total_text.replace(",", ""))
        navigation = soup.select_one("div.board_navi")
        current_nodes = navigation.find_all("span", recursive=False) if navigation else []
        current_values = [
            value
            for node in current_nodes
            if (value := clean_text(node.get_text(" ", strip=True)))
            and value.isdigit()
        ]
        if len(current_values) != 1:
            raise RuntimeError(
                "Suwon ecology list structure changed: current page not found"
            )
        current_page = int(current_values[0])
        if current_page < 1:
            raise RuntimeError("Suwon ecology pagination metadata is inconsistent")

        rows = table.select("tbody tr")
        facts: list[SuwonEcologyListFact] = []
        for row in rows:
            cells = row.find_all("td", recursive=False)
            link = row.select_one("td.subject a[href]")
            detail = cls._canonical_detail(link.get("href")) if link else None
            if len(cells) < 5 or link is None or detail is None:
                raise RuntimeError(
                    "Suwon ecology list structure changed: invalid program row"
                )
            external_id, detail_url = detail
            title = clean_text(link.get_text(" ", strip=True))
            if not title:
                raise RuntimeError(
                    "Suwon ecology list structure changed: program title missing"
                )
            status_image = cells[4].select_one("img[alt]")
            status = clean_text(status_image.get("alt")) if status_image else clean_text(
                cells[4].get_text(" ", strip=True)
            )
            event_dates = cls._dates(
                cells[1].get_text(" ", strip=True),
                required=True,
                field_name=f"event date for program {external_id}",
            )
            facts.append(
                SuwonEcologyListFact(
                    external_id=external_id,
                    title=title,
                    detail_url=detail_url,
                    event_dates=event_dates,
                    target=clean_text(cells[2].get_text(" ", strip=True)),
                    capacity=clean_text(cells[3].get_text(" ", strip=True)),
                    status=status,
                )
            )
        if rows and not facts:
            raise RuntimeError("Suwon ecology list structure changed: no valid rows")
        external_ids = [fact.external_id for fact in facts]
        if len(external_ids) != len(set(external_ids)):
            raise RuntimeError(
                f"Suwon ecology page {current_page} contains duplicate program IDs"
            )
        if len(facts) > total or (total == 0 and facts):
            raise RuntimeError(
                "Suwon ecology pagination metadata is inconsistent: "
                f"total={total}, page_rows={len(facts)}"
            )
        return SuwonEcologyPage(
            facts=facts,
            total=total,
            current_page=current_page,
        )

    @classmethod
    def parse_list(cls, html: str) -> list[SuwonEcologyListFact]:
        return cls.parse_page(html).facts

    @classmethod
    def parse_detail(cls, html: str) -> SuwonEcologyDetailFact:
        soup = BeautifulSoup(html, "html.parser")
        view = soup.select_one("div.view3")
        title_node = view.select_one("div.title h3") if view else None
        if view is None or title_node is None:
            raise RuntimeError("Suwon ecology detail structure changed: view not found")
        label = title_node.select_one("span")
        if label:
            label.decompose()
        title = clean_text(title_node.get_text(" ", strip=True))
        fields: dict[str, str] = {}
        for term in view.select("div.info dl dt"):
            value_node = term.find_next_sibling("dd")
            key = clean_text(term.get_text(" ", strip=True))
            if not key or value_node is None:
                continue
            image = value_node.select_one("img[alt]")
            value = clean_text(image.get("alt")) if image else clean_text(
                value_node.get_text(" ", strip=True)
            )
            if value:
                fields[key] = value
        if not title or not fields:
            raise RuntimeError("Suwon ecology detail structure changed: no metadata")
        required_fields = {"대상", "교육기간", "진행상태"}
        missing_fields = required_fields.difference(fields)
        if missing_fields:
            raise RuntimeError(
                "Suwon ecology detail structure changed: required metadata missing "
                + ", ".join(sorted(missing_fields))
            )
        body_node = view.select_one("div.substance")
        body = clean_text(body_node.get_text(" ", strip=True)) if body_node else None
        phone_match = _LANDLINE_PHONE_RE.search(body or "")
        phone = phone_match.group(0) if phone_match else None
        event_dates = cls._dates(
            fields.get("교육기간"),
            required=True,
            field_name="detail event date",
        )
        return SuwonEcologyDetailFact(
            title=title,
            category=fields.get("분야안내"),
            venue=fields.get("교육장소"),
            target=fields.get("대상"),
            event_dates=event_dates,
            capacity=fields.get("인원"),
            schedule=fields.get("교육시간"),
            price=fields.get("금액"),
            status=fields.get("진행상태"),
            phone=phone,
        )

    @staticmethod
    def _event_times(
        dates: tuple[str, str] | None, schedule: str | None
    ) -> tuple[datetime | None, datetime | None]:
        if dates is None:
            raise RuntimeError("Suwon ecology program has no event date")
        match = _TIME_RE.search(schedule or "")
        if match:
            values = match.groupdict(default="0")
            start_time = f"{int(values['sh']):02d}:{int(values['sm']):02d}:00"
            end_time = f"{int(values['eh']):02d}:{int(values['em']):02d}:00"
            if end_time < start_time:
                raise RuntimeError(
                    "Suwon ecology event time ends before it starts"
                )
        else:
            start_time, end_time = "00:00:00", "23:59:59"
        start = datetime.fromisoformat(f"{dates[0]}T{start_time}").replace(
            tzinfo=KST
        )
        end = datetime.fromisoformat(f"{dates[1]}T{end_time}").replace(tzinfo=KST)
        if end < start:
            raise RuntimeError("Suwon ecology event ends before it starts")
        return start, end

    @classmethod
    def _map(
        cls,
        list_fact: SuwonEcologyListFact,
        detail: SuwonEcologyDetailFact,
    ) -> Event:
        dates = detail.event_dates or list_fact.event_dates
        if dates is None:
            raise RuntimeError(
                f"Suwon ecology program {list_fact.external_id} has no event date"
            )
        event_start, event_end = cls._event_times(dates, detail.schedule)
        age_min, age_max, age_text = cls._source_age_range(
            detail.target or list_fact.target or detail.title
        )
        price_min, price_text = parse_price(detail.price)
        venue = detail.venue
        address = (
            "경기도 수원시 권선구 서수원로577번길 225"
            if venue and any(token in venue for token in ("생태환경체험교육관", "청개구리집"))
            else None
        )
        period = " ~ ".join(dates) if dates else None
        raw = {
            "external_id": list_fact.external_id,
            "title": detail.title,
            "category": detail.category,
            "venue": venue,
            "target": detail.target or list_fact.target,
            "event_period": period,
            "capacity": detail.capacity or list_fact.capacity,
            "schedule": detail.schedule,
            "price": price_text,
            "status": detail.status or list_fact.status,
            "phone": detail.phone,
        }
        return Event(
            source_id="suwon_ecology_child_programs",
            source_name="수원시 생태환경체험교육관 어린이·가족 프로그램",
            external_id=list_fact.external_id,
            title=detail.title,
            detail_url=list_fact.detail_url,
            provider_name="수원시 생태환경체험교육관",
            category="생태·환경 체험",
            description=(f"교육시간: {detail.schedule}" if detail.schedule else None),
            event_start=event_start,
            event_end=event_end,
            apply_start=None,
            apply_end=None,
            status=detail.status or list_fact.status,
            age_text=age_text or detail.target or list_fact.target,
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
            is_online=False,
            child_relevance_score=max(
                0.55,
                child_relevance(
                    detail.title,
                    detail.target or list_fact.target,
                    detail.category,
                ),
            ),
            license_code=None,
            fetched_at=datetime.now(KST),
            raw=raw,
        )

    @staticmethod
    def _overlaps(event: Event, window: CrawlWindow) -> bool:
        start = event.event_start or event.event_end
        end = event.event_end or event.event_start
        if start is None or end is None:
            raise RuntimeError("Suwon ecology event has no event date")
        if end < start:
            raise RuntimeError("Suwon ecology event ends before it starts")
        return start <= window.end and end >= window.start

    @staticmethod
    def _candidate(title: str, target: str | None) -> bool:
        _ = title
        target_text = (target or "").casefold()
        if not target_text:
            return False
        return SuwonEcologyProgramSource._target_has_child(target_text)

    @staticmethod
    def _target_has_child(target: str) -> bool:
        normalized = clean_text(target) or ""
        if _TARGET_COMPANION_RE.search(normalized) or any(
            phrase in normalized for phrase in _TARGET_COMPANION_PHRASES
        ):
            return True
        if any(token in normalized for token in _ADULT_ONLY_TOKENS):
            return False
        if any(token in normalized for token in _TARGET_CHILD_TOKENS):
            return True
        if any(phrase in normalized for phrase in _TARGET_CHILD_PHRASES):
            return True
        if normalized == "어린이":
            return True
        if re.search(r"(?:어린이|자녀).*(?:동반|함께)", normalized):
            return True
        if re.search(r"(?:동반|함께).*(?:어린이|자녀)", normalized):
            return True
        return bool(
            _BARE_AGE_RANGE_RE.search(normalized)
            or _BARE_GRADE_RANGE_RE.search(normalized)
        )

    @staticmethod
    def _source_age_range(value: str | None) -> tuple[int | None, int | None, str | None]:
        age_min, age_max, age_text = parse_age_range(value)
        text = clean_text(value)
        if not text:
            return age_min, age_max, age_text
        bare_age = _BARE_AGE_RANGE_RE.search(text)
        if bare_age:
            low, high = (int(part) for part in bare_age.groups())
            if high < low:
                raise RuntimeError("Suwon ecology target age ends before it starts")
            return low, high, text
        bare_grade = _BARE_GRADE_RANGE_RE.search(text)
        if bare_grade:
            low, high = (int(part) for part in bare_grade.groups())
            if high < low:
                raise RuntimeError("Suwon ecology target grade ends before it starts")
            return low + 6, high + 6, text
        return age_min, age_max, age_text

    def crawl(
        self, client: PoliteHttpClient, window: CrawlWindow
    ) -> Iterable[Event]:
        seen: set[str] = set()
        all_facts: list[SuwonEcologyListFact] = []
        expected_total: int | None = None
        for page in range(1, window.max_pages + 1):
            request_url = f"{self.LIST_URL}?{urlencode({'page': page})}"
            client.assert_html_allowed(request_url)
            html = client.get_text(request_url)
            parsed = self.parse_page(html)
            if parsed.current_page != page:
                raise RuntimeError(
                    "Suwon ecology returned the wrong page: "
                    f"requested={page}, returned={parsed.current_page}"
                )
            if expected_total is None:
                expected_total = parsed.total
            elif parsed.total != expected_total:
                raise RuntimeError(
                    "Suwon ecology total changed while collecting the list"
                )

            page_ids = {fact.external_id for fact in parsed.facts}
            duplicates = seen.intersection(page_ids)
            if duplicates:
                duplicate = sorted(duplicates)[0]
                raise RuntimeError(
                    "Suwon ecology repeated a program across pages: "
                    f"external_id={duplicate}"
                )
            seen.update(page_ids)
            all_facts.extend(parsed.facts)
            if len(all_facts) > expected_total:
                raise RuntimeError(
                    "Suwon ecology collection exceeded the official total count"
                )
            if len(all_facts) == expected_total:
                break
            if not parsed.facts:
                raise RuntimeError(
                    "Suwon ecology pagination ended before the official total count"
                )

        if expected_total is None:
            raise RuntimeError("Suwon ecology collection did not fetch a list page")
        if len(all_facts) != expected_total:
            raise RuntimeError(
                "Suwon ecology collection would be partial: "
                f"expected={expected_total}, collected={len(all_facts)}, "
                f"max_pages={window.max_pages}"
            )

        for fact in all_facts:
            if not self._candidate(fact.title, fact.target):
                continue
            client.assert_html_allowed(fact.detail_url)
            detail = self.parse_detail(client.get_text(fact.detail_url))
            if not self._candidate(
                detail.title,
                detail.target or fact.target,
            ):
                continue
            event = self._map(fact, detail)
            if self._overlaps(event, window):
                yield event


__all__ = ["SuwonEcologyProgramSource"]
