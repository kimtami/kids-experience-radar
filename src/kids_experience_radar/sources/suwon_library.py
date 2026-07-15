from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
import re
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from ..http import PoliteHttpClient
from ..models import CrawlWindow, Event
from ..normalizers import KST, child_relevance, clean_text, parse_age_range
from .base import Source, SourceInfo


_FULL_DATE_RE = re.compile(r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})")
_PARTIAL_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})[./-](\d{1,2})(?!\d)")
_TIME_RE = re.compile(r"([01]?\d|2[0-3]):([0-5]\d)")
_DETAIL_ID_RE = re.compile(r"fnDetail\(['\"](\d{1,20})['\"]\)")
_PAGE_META_RE = re.compile(
    r"총\s*([\d,]+)\s*건\s*\(\s*(\d+)\s*/\s*(\d+)\s*페이지\s*\)"
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
    "취업",
    "자격증",
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
_STATUS_BY_CLASS = {
    "ready": "접수예정",
    "apply": "접수중",
    "wait": "대기자접수중",
    "finish": "접수마감",
}
_VENUE_ADDRESSES = {
    # Verified on the official Suwon library site and shared with the SWCF map.
    "망포글빛": "경기도 수원시 영통구 망포로 100",
}


@dataclass(slots=True)
class SuwonLibraryFact:
    external_id: str
    title: str
    detail_url: str
    library: str | None
    target: str | None
    event_period: str | None
    event_time: str | None
    application_period: str | None
    application_time: str | None
    venue: str | None
    capacity: str | None
    waiting: str | None
    status: str | None


@dataclass(slots=True)
class SuwonLibraryPage:
    facts: list[SuwonLibraryFact]
    total: int
    current_page: int
    total_pages: int


class SuwonLibraryProgramSource(Source):
    """Read Suwon Library's working public integrated-reservation list.

    The legacy ``/lecture/lectureList.do`` page currently serves a maintenance
    placeholder.  The same city library service publishes the recurring facts
    at ``/reserve/lecture/lectureList.do``.  This adapter uses that official
    replacement and never calls application, login, or personal-reservation
    paths.
    """

    LIST_URL = "https://www.suwonlib.go.kr/reserve/lecture/lectureList.do"
    DETAIL_URL = "https://www.suwonlib.go.kr/reserve/lecture/lectureDetail.do"
    PAGE_SIZE = 100
    TARGET_CODES = ("AL", "IN", "EL", "FA")  # anyone, preschool, primary, family
    PUBLIC_RAW_FIELDS = frozenset(
        {
            "external_id",
            "title",
            "library",
            "target",
            "event_period",
            "event_time",
            "application_period",
            "application_time",
            "venue",
            "capacity",
            "waiting",
            "status",
        }
    )

    def __init__(self) -> None:
        self.info = SourceInfo(
            source_id="suwon_library_child_programs",
            name="수원시도서관 어린이·가족 독서문화프로그램",
            owner="수원특례시 도서관사업소",
            source_type="public_html",
            official_url=self.LIST_URL,
            license_code=None,
            enabled_by_default=False,
            policy_status="approved_html",
            notes=(
                "Official replacement for the maintenance-only legacy lecture URL. "
                "Uses the public integrated-reservation list GET and numeric detail "
                "links only. Never calls apply, login, member, payment, queue, or "
                "personal reservation endpoints. Runtime robots check is mandatory."
            ),
        )

    @staticmethod
    def _field(container: object, prefix: str) -> str | None:
        if not hasattr(container, "select"):
            return None
        for node in container.select("span"):  # type: ignore[union-attr]
            value = clean_text(node.get_text(" ", strip=True))
            if value and value.startswith(prefix):
                return clean_text(value.split(":", 1)[1])
        return None

    @classmethod
    def parse_page(cls, html: str) -> SuwonLibraryPage:
        soup = BeautifulSoup(html, "html.parser")
        wrap = soup.select_one("div.lectureWrap")
        listing = wrap.select_one("ul.lecture-list") if wrap else None
        if wrap is None or listing is None:
            raise RuntimeError("Suwon library list structure changed: list not found")

        rows = listing.find_all("li", recursive=False)
        facts: list[SuwonLibraryFact] = []
        for row in rows:
            link = row.select_one("div.title a[onclick]")
            match = _DETAIL_ID_RE.search(str(link.get("onclick") or "")) if link else None
            title = clean_text(link.get_text(" ", strip=True)) if link else None
            if match is None or not title:
                raise RuntimeError(
                    "Suwon library list structure changed: invalid program row"
                )
            external_id = match.group(1)
            icons = [
                value
                for node in row.select("div.title i.icon:not(.target) span")
                if (value := clean_text(node.get_text(" ", strip=True)))
            ]
            info = row.select("div.info")
            event_info = info[0] if info else None
            apply_info = info[1] if len(info) > 1 else None
            status_node = row.select_one("div.info_r p")
            status_class = next(
                (
                    name
                    for name in (status_node.get("class") or [])
                    if name in _STATUS_BY_CLASS
                ),
                None,
            ) if status_node else None
            status = _STATUS_BY_CLASS.get(status_class or "")
            if status is None and status_node is not None:
                status = clean_text(status_node.get_text(" ", strip=True))

            fact = SuwonLibraryFact(
                external_id=external_id,
                title=title,
                detail_url=f"{cls.DETAIL_URL}?lectureIdx={external_id}",
                library=icons[0] if icons else None,
                target=cls._field(event_info, "대상"),
                event_period=cls._field(event_info, "교육기간"),
                event_time=cls._field(event_info, "시간"),
                application_period=cls._field(apply_info, "접수기간"),
                application_time=cls._field(apply_info, "시간"),
                venue=cls._field(event_info, "장소"),
                capacity=cls._field(apply_info, "신청자수"),
                waiting=cls._field(apply_info, "대기자수"),
                status=status,
            )
            cls._dates(
                fact.event_period,
                required=True,
                field_name=f"event date for program {external_id}",
            )
            cls._times(
                fact.event_time,
                field_name=f"event time for program {external_id}",
            )
            facts.append(fact)
        if rows and not facts:
            raise RuntimeError("Suwon library list structure changed: no valid rows")

        meta_node = wrap.select_one("div.lecture-top > span")
        meta_text = clean_text(meta_node.get_text(" ", strip=True)) if meta_node else None
        meta = _PAGE_META_RE.search(meta_text or "")
        if meta is None:
            raise RuntimeError(
                "Suwon library list structure changed: pagination metadata not found"
            )
        total = int(meta.group(1).replace(",", ""))
        current_page = int(meta.group(2))
        total_pages = int(meta.group(3))
        expected_pages = max(1, (total + cls.PAGE_SIZE - 1) // cls.PAGE_SIZE)
        if current_page < 1 or total_pages != expected_pages or current_page > total_pages:
            raise RuntimeError(
                "Suwon library pagination metadata is inconsistent: "
                f"total={total}, current={current_page}, pages={total_pages}"
            )
        expected_rows = (
            0
            if total == 0
            else (
                cls.PAGE_SIZE
                if current_page < total_pages
                else total - (current_page - 1) * cls.PAGE_SIZE
            )
        )
        if len(facts) != expected_rows:
            raise RuntimeError(
                "Suwon library page is incomplete: "
                f"page={current_page}, expected={expected_rows}, actual={len(facts)}"
            )
        external_ids = [fact.external_id for fact in facts]
        if len(external_ids) != len(set(external_ids)):
            raise RuntimeError(
                f"Suwon library page {current_page} contains duplicate program IDs"
            )
        return SuwonLibraryPage(
            facts=facts,
            total=total,
            current_page=current_page,
            total_pages=total_pages,
        )

    @classmethod
    def parse_list(cls, html: str) -> list[SuwonLibraryFact]:
        return cls.parse_page(html).facts

    @staticmethod
    def _dates(
        value: str | None,
        *,
        required: bool = False,
        field_name: str = "date",
    ) -> tuple[str, str] | None:
        text = value or ""
        full = list(_FULL_DATE_RE.finditer(text))
        if not full:
            if required:
                raise RuntimeError(
                    f"Suwon library {field_name} is missing or unparseable"
                )
            return None
        year, month, day = (int(part) for part in full[0].groups())
        tail = text[full[0].end():]
        second_full = _FULL_DATE_RE.search(tail)
        if second_full:
            end_parts = tuple(int(part) for part in second_full.groups())
        else:
            partial = _PARTIAL_DATE_RE.search(tail)
            end_parts = (
                (year, int(partial.group(1)), int(partial.group(2)))
                if partial
                else (year, month, day)
            )
        try:
            start_date = datetime(year, month, day).date()
            end_date = datetime(*end_parts).date()
        except ValueError as exc:
            raise RuntimeError(
                f"Suwon library {field_name} contains an invalid date"
            ) from exc
        if end_date < start_date:
            raise RuntimeError(
                f"Suwon library {field_name} ends before it starts"
            )
        return start_date.isoformat(), end_date.isoformat()

    @staticmethod
    def _times(
        value: str | None,
        *,
        field_name: str = "time",
        reject_reversed: bool = True,
    ) -> tuple[str, str] | None:
        matches = _TIME_RE.findall(value or "")
        if not matches:
            return None
        normalized = [f"{int(hour):02d}:{minute}" for hour, minute in matches]
        start = normalized[0]
        end = normalized[1] if len(normalized) > 1 else start
        if reject_reversed and end < start:
            raise RuntimeError(
                f"Suwon library {field_name} ends before it starts"
            )
        return start, end

    @classmethod
    def _period(
        cls,
        dates_text: str | None,
        times_text: str | None,
        *,
        end_of_day: bool,
        required_dates: bool,
        field_name: str,
        reject_reversed_times: bool,
    ) -> tuple[datetime | None, datetime | None]:
        dates = cls._dates(
            dates_text,
            required=required_dates,
            field_name=field_name,
        )
        if dates is None:
            return None, None
        times = cls._times(
            times_text,
            field_name=field_name.replace("date", "time"),
            reject_reversed=reject_reversed_times,
        )
        start_time = times[0] if times else "00:00"
        end_time = times[1] if times else ("23:59" if end_of_day else "00:00")
        start = datetime.fromisoformat(f"{dates[0]}T{start_time}:00").replace(
            tzinfo=KST
        )
        end = datetime.fromisoformat(f"{dates[1]}T{end_time}:00").replace(tzinfo=KST)
        if end < start:
            raise RuntimeError(f"Suwon library {field_name} ends before it starts")
        return start, end

    @staticmethod
    def _candidate(fact: SuwonLibraryFact) -> bool:
        target = (fact.target or "").casefold()
        if not target:
            return False
        return SuwonLibraryProgramSource._target_has_child(target)

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
                raise RuntimeError("Suwon library target age ends before it starts")
            return low, high, text
        bare_grade = _BARE_GRADE_RANGE_RE.search(text)
        if bare_grade:
            low, high = (int(part) for part in bare_grade.groups())
            if high < low:
                raise RuntimeError("Suwon library target grade ends before it starts")
            return low + 6, high + 6, text
        return age_min, age_max, age_text

    @classmethod
    def _map(cls, fact: SuwonLibraryFact) -> Event:
        age_min, age_max, age_text = cls._source_age_range(
            fact.target or fact.title
        )
        event_start, event_end = cls._period(
            fact.event_period,
            fact.event_time,
            end_of_day=True,
            required_dates=True,
            field_name=f"event date for program {fact.external_id}",
            reject_reversed_times=True,
        )
        apply_start, apply_end = cls._period(
            fact.application_period,
            fact.application_time,
            end_of_day=True,
            required_dates=False,
            field_name=f"application date for program {fact.external_id}",
            reject_reversed_times=False,
        )
        if event_start is None or event_end is None:
            raise RuntimeError(
                f"Suwon library program {fact.external_id} has no event date"
            )
        library = clean_text(fact.library)
        address = next(
            (
                value
                for marker, value in _VENUE_ADDRESSES.items()
                if marker in f"{library or ''} {fact.venue or ''}"
            ),
            None,
        )
        raw = {
            "external_id": fact.external_id,
            "title": fact.title,
            "library": library,
            "target": fact.target,
            "event_period": fact.event_period,
            "event_time": fact.event_time,
            "application_period": fact.application_period,
            "application_time": fact.application_time,
            "venue": fact.venue,
            "capacity": fact.capacity,
            "waiting": fact.waiting,
            "status": fact.status,
        }
        return Event(
            source_id="suwon_library_child_programs",
            source_name="수원시도서관 어린이·가족 독서문화프로그램",
            external_id=fact.external_id,
            title=fact.title,
            detail_url=fact.detail_url,
            provider_name=(f"{library}도서관" if library else "수원시 도서관사업소"),
            category="도서관·독서문화",
            description=(f"교육시간: {fact.event_time}" if fact.event_time else None),
            event_start=event_start,
            event_end=event_end,
            apply_start=apply_start,
            apply_end=apply_end,
            status=fact.status,
            age_text=age_text or fact.target,
            age_min=age_min,
            age_max=age_max,
            price_text=None,
            price_min=None,
            venue_name=fact.venue or (f"{library}도서관" if library else None),
            address=address,
            region="경기도 수원시",
            latitude=None,
            longitude=None,
            image_url=None,
            phone=None,
            is_online="온라인" in f"{fact.title} {fact.venue or ''}",
            child_relevance_score=max(
                0.55,
                child_relevance(fact.title, fact.target, fact.event_time),
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
            raise RuntimeError("Suwon library event has no event date")
        if end < start:
            raise RuntimeError("Suwon library event ends before it starts")
        return start <= window.end and end >= window.start

    def crawl(
        self, client: PoliteHttpClient, window: CrawlWindow
    ) -> Iterable[Event]:
        seen: set[str] = set()
        all_facts: list[SuwonLibraryFact] = []
        expected_total: int | None = None
        expected_pages: int | None = None
        for page in range(1, window.max_pages + 1):
            query = urlencode(
                {
                    "mode": "search",
                    "searchTargetCdArray": self.TARGET_CODES,
                    "searchYmdCondition": "lecturePeriod",
                    "searchStartYmd": window.start.date().isoformat(),
                    "searchEndYmd": window.end.date().isoformat(),
                    "currentPageNo": page,
                    "recordCountPerPage": self.PAGE_SIZE,
                },
                doseq=True,
            )
            request_url = f"{self.LIST_URL}?{query}"
            client.assert_html_allowed(request_url)
            html = client.get_text(request_url)
            parsed = self.parse_page(html)
            if parsed.current_page != page:
                raise RuntimeError(
                    "Suwon library returned the wrong page: "
                    f"requested={page}, returned={parsed.current_page}"
                )
            if expected_total is None:
                expected_total = parsed.total
                expected_pages = parsed.total_pages
                if parsed.total_pages > window.max_pages:
                    raise RuntimeError(
                        "Suwon library collection would be partial: "
                        f"requires {parsed.total_pages} pages, max_pages={window.max_pages}"
                    )
            elif (
                parsed.total != expected_total
                or parsed.total_pages != expected_pages
            ):
                raise RuntimeError(
                    "Suwon library pagination changed while collecting the list"
                )

            page_ids = {fact.external_id for fact in parsed.facts}
            duplicates = seen.intersection(page_ids)
            if duplicates:
                duplicate = sorted(duplicates)[0]
                raise RuntimeError(
                    "Suwon library repeated a program across pages: "
                    f"external_id={duplicate}"
                )
            seen.update(page_ids)
            all_facts.extend(parsed.facts)
            if page == parsed.total_pages:
                break

        if expected_total is None or expected_pages is None:
            raise RuntimeError("Suwon library collection did not fetch a list page")
        if len(all_facts) != expected_total:
            raise RuntimeError(
                "Suwon library collection is incomplete: "
                f"expected={expected_total}, collected={len(all_facts)}"
            )

        for fact in all_facts:
            if not self._candidate(fact):
                continue
            event = self._map(fact)
            if self._overlaps(event, window):
                yield event


__all__ = ["SuwonLibraryProgramSource"]
