from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import re
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from ..http import PoliteHttpClient
from ..models import CrawlWindow, Event
from ..normalizers import KST, child_relevance, clean_text, parse_age_range
from .base import Source, SourceInfo


_VIEW_RE = re.compile(
    r"^\s*fnView\(\s*['\"]1090['\"]\s*,\s*"
    r"['\"](?P<post_id>\d{14,20})['\"]\s*,\s*"
    r"['\"]/news['\"]\s*,\s*['\"](?P<estn>All|Y|)['\"]\s*\)\s*;?\s*$"
)
_POST_ID_RE = re.compile(r"\d{14,20}")
_PUBLISHED_RE = re.compile(r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})")
_PAGE_RE = re.compile(r"\(\s*(\d+)\s*/\s*(\d+)\s*page\s*\)", re.I)
_PROGRAM_NAME_RE = re.compile(
    r"(?P<label>[가-힣A-Za-z0-9·]{1,20})\s*프로그램\s*[‘'\"]"
    r"(?P<name>[^’'\"]{1,100})[’'\"]"
)
_PROGRAM_CLAUSE_SPLIT_RE = re.compile(
    r",\s*(?=[가-힣A-Za-z0-9·]{1,20}\s*프로그램은)"
)
_PROGRAM_SCHEDULE_RE = re.compile(
    r"(?P<label>[가-힣A-Za-z0-9·]{1,20})\s*프로그램은"
    r"[^.]{0,180}?(?P<month>\d{1,2})월\s*"
    r"(?P<days>\d{1,2}일[^.]{0,120}?)"
    r"(?=(?:총\s*\d+\s*일간|운영|진행|개최|$))"
)
_MONTH_RANGE_RE = re.compile(
    r"(?:(?P<start_year>20\d{2})년\s*)?"
    r"(?P<start_month>\d{1,2})월\s*(?P<start_day>\d{1,2})일부터\s*"
    r"(?:(?P<end_year>20\d{2})년\s*)?"
    r"(?P<end_month>\d{1,2})월\s*(?P<end_day>\d{1,2})일까지"
)
_SINGLE_DATE_RE = re.compile(
    r"(?:(?P<year>20\d{2})년\s*)?(?P<month>\d{1,2})월\s*(?P<day>\d{1,2})일"
)
_PHONE_RE = re.compile(r"(?<!\d)(0\d{1,2})[- ](\d{3,4})[- ](\d{4})(?!\d)")
_CHILD_TOKENS = ("초등", "어린이", "아동", "유아", "가족", "보호자")
_EVENT_VERBS = ("운영", "진행", "개최")
_APPLICATION_TOKENS = ("신청", "접수", "모집")


@dataclass(slots=True, frozen=True)
class GoyangNewsPost:
    post_id: str
    title: str
    detail_url: str
    department: str | None
    published_date: str
    estn_column: str


@dataclass(slots=True, frozen=True)
class GoyangNewsPage:
    total: int
    current_page: int
    total_pages: int
    posts: tuple[GoyangNewsPost, ...]


@dataclass(slots=True, frozen=True)
class GoyangProgramFact:
    post_id: str
    article_title: str
    detail_url: str
    department: str | None
    published_date: str
    label: str | None
    program_name: str
    schedule_text: str
    audience: str
    event_start: datetime | None
    event_end: datetime | None
    session_starts: tuple[datetime, ...]
    price_text: str | None
    price_min: int | None
    status: str
    application_timing: str | None
    phone: str | None


class GoyangChildrenMuseumCityNewsSource(Source):
    """Collect factual child-program metadata from Goyang City News only.

    The museum origin is deliberately outside this adapter's network boundary.
    The only collection requests are GETs to the public Goyang City News list
    and its numeric public-detail endpoint.
    """

    LIST_URL = "https://www.goyang.go.kr/news/user/bbs/BD_selectBbsList.do"
    DETAIL_URL = "https://www.goyang.go.kr/news/user/bbs/BD_selectBbs.do"
    ADDRESS = "경기도 고양시 덕양구 화중로 26"
    VENUE = "고양어린이박물관"
    PAGE_SIZE = 10
    PUBLIC_RAW_FIELDS = frozenset(
        {
            "post_id",
            "article_title",
            "published_date",
            "department",
            "label",
            "program_name",
            "schedule_text",
            "event_date",
            "audience",
            "price_text",
            "status",
            "application_timing",
            "venue",
            "address",
            "phone",
        }
    )

    def __init__(self) -> None:
        self.info = SourceInfo(
            source_id="goyang_children_museum_city_news",
            name="고양어린이박물관 고양시 뉴스 체험·교육 일정",
            owner="고양특례시",
            source_type="public_html",
            official_url=self.LIST_URL,
            license_code=None,
            enabled_by_default=False,
            policy_status="approved_html",
            notes=(
                "Goyang City News public list/detail GET metadata only. The "
                "museum origin is never requested. Never calls login, application, "
                "submission, attachment, image, download, payment, or member paths; "
                "stores only factual schedule/audience/price/location/status fields."
            ),
        )

    @classmethod
    def _canonical_detail(cls, post_id: str, estn_column: str) -> str | None:
        if _POST_ID_RE.fullmatch(post_id) is None or estn_column not in {"", "All", "Y"}:
            return None
        query = urlencode(
            (
                ("q_bbsCode", "1090"),
                ("q_bbscttSn", post_id),
                ("q_estnColumn1", estn_column),
            )
        )
        return f"{cls.DETAIL_URL}?{query}"

    @staticmethod
    def _published(value: str | None) -> str | None:
        match = _PUBLISHED_RE.search(value or "")
        if match is None:
            return None
        try:
            parsed = date(*(int(part) for part in match.groups()))
        except ValueError:
            return None
        return parsed.isoformat()

    @classmethod
    def _page_metadata(cls, html: str) -> tuple[int, int, int]:
        soup = BeautifulSoup(html, "html.parser")
        total_node = soup.select_one(".bbs-total strong")
        total_container = soup.select_one(".bbs-total")
        total_text = (
            clean_text(total_container.get_text(" ", strip=True))
            if total_container
            else None
        )
        if total_node is None or total_text is None:
            raise RuntimeError("Goyang city news list structure changed: total not found")
        try:
            total = int(clean_text(total_node.get_text(" ", strip=True)) or "")
        except ValueError as exc:
            raise RuntimeError(
                "Goyang city news list structure changed: invalid total"
            ) from exc
        page_match = _PAGE_RE.search(total_text)
        if page_match is None:
            raise RuntimeError("Goyang city news list structure changed: page count not found")
        current_page, total_pages = (int(value) for value in page_match.groups())
        expected_pages = max(1, (total + cls.PAGE_SIZE - 1) // cls.PAGE_SIZE)
        if (
            total < 0
            or current_page < 1
            or total_pages != expected_pages
            or current_page > total_pages
        ):
            raise RuntimeError(
                "Goyang city news list structure changed: invalid pagination metadata"
            )
        return total, current_page, total_pages

    @classmethod
    def _page_count(cls, html: str) -> int:
        return cls._page_metadata(html)[2]

    @classmethod
    def parse_page(cls, html: str) -> GoyangNewsPage:
        soup = BeautifulSoup(html, "html.parser")
        tbody = soup.select_one("table.table-list tbody")
        if tbody is None:
            raise RuntimeError("Goyang city news list structure changed: list not found")
        total, current_page, total_pages = cls._page_metadata(html)

        rows = tbody.find_all("tr", recursive=False)
        if total == 0:
            if rows and not all(
                any(
                    marker in (clean_text(row.get_text(" ", strip=True)) or "")
                    for marker in ("검색 결과가 없습니다", "등록된 게시물이 없습니다")
                )
                for row in rows
            ):
                raise RuntimeError(
                    "Goyang city news list structure changed: rows exist for zero total"
                )
            return GoyangNewsPage(total, current_page, total_pages, ())

        expected_rows = (
            cls.PAGE_SIZE
            if current_page < total_pages
            else total - (current_page - 1) * cls.PAGE_SIZE
        )
        if len(rows) != expected_rows:
            raise RuntimeError(
                "Goyang city news page is incomplete: "
                f"page={current_page}, expected={expected_rows}, rows={len(rows)}"
            )

        posts: list[GoyangNewsPost] = []
        for row_number, row in enumerate(rows, start=1):
            link = row.select_one("td.subject a[onclick]")
            onclick = str(link.get("onclick") or "") if link else ""
            match = _VIEW_RE.fullmatch(onclick)
            title = clean_text(link.get_text(" ", strip=True)) if link else None
            if match is None or not title:
                raise RuntimeError(
                    "Goyang city news list structure changed: invalid row "
                    f"{row_number} on page {current_page}"
                )
            post_id = match.group("post_id")
            estn_column = match.group("estn")
            detail_url = cls._canonical_detail(post_id, estn_column)
            cells = row.find_all("td", recursive=False)
            department = clean_text(cells[2].get_text(" ", strip=True)) if len(cells) >= 3 else None
            published_node = row.select_one("td.date")
            published_date = cls._published(
                clean_text(published_node.get_text(" ", strip=True)) if published_node else None
            )
            if detail_url is None or published_date is None or len(cells) < 4:
                raise RuntimeError(
                    "Goyang city news list structure changed: unsafe row "
                    f"{row_number} on page {current_page}"
                )
            posts.append(
                GoyangNewsPost(
                    post_id=post_id,
                    title=title,
                    detail_url=detail_url,
                    department=department,
                    published_date=published_date,
                    estn_column=estn_column,
                )
            )
        if len(posts) != expected_rows:
            raise RuntimeError("Goyang city news list structure changed: no valid rows")
        return GoyangNewsPage(
            total, current_page, total_pages, tuple(posts)
        )

    @classmethod
    def parse_list(cls, html: str) -> list[GoyangNewsPost]:
        return list(cls.parse_page(html).posts)

    @staticmethod
    def _sentences(text: str) -> list[str]:
        return [
            sentence
            for part in re.split(r"(?<=[.!?])\s+", text)
            if (sentence := clean_text(part))
        ]

    @staticmethod
    def _make_datetime(year: int, month: int, day: int, *, end: bool = False) -> datetime | None:
        try:
            return datetime(
                year,
                month,
                day,
                23 if end else 0,
                59 if end else 0,
                59 if end else 0,
                tzinfo=KST,
            )
        except ValueError:
            return None

    @classmethod
    def _program_dates(
        cls, year: int, month: int, days_text: str
    ) -> tuple[datetime | None, datetime | None, tuple[datetime, ...]]:
        range_match = re.search(
            r"(?<!\d)(\d{1,2})일부터\s*(\d{1,2})일까지", days_text
        )
        if range_match:
            start = cls._make_datetime(year, month, int(range_match.group(1)))
            end = cls._make_datetime(year, month, int(range_match.group(2)), end=True)
            if start is not None and end is not None and start <= end:
                return start, end, ()
            return None, None, ()

        sessions: list[datetime] = []
        seen_days: set[int] = set()
        for raw_day in re.findall(r"(?<!\d)(\d{1,2})일", days_text):
            day = int(raw_day)
            if day in seen_days:
                continue
            parsed = cls._make_datetime(year, month, day)
            if parsed is not None:
                seen_days.add(day)
                sessions.append(parsed)
        return None, None, tuple(sessions)

    @staticmethod
    def _program_audience(label: str, sentences: list[str]) -> str | None:
        escaped = re.escape(label)
        for sentence in sentences:
            if f"{label} 프로그램" not in sentence:
                continue
            targeted = re.search(
                rf"{escaped}\s*프로그램은\s*(?P<value>[^.]+?)(?:을|를)\s*대상",
                sentence,
            )
            if targeted:
                value = clean_text(targeted.group("value"))
                if value and GoyangChildrenMuseumCityNewsSource._has_child_participant(
                    value
                ):
                    return value
            family = re.search(
                rf"{escaped}\s*프로그램은\s*"
                r"(?P<value>만\s*\d{1,2}\s*[~～\-]\s*\d{1,2}\s*세\s*"
                r"어린이와\s*보호자)",
                sentence,
            )
            if family:
                return clean_text(family.group("value"))
        return None

    @classmethod
    def _has_child_participant(cls, value: str) -> bool:
        text = clean_text(value) or ""
        text = text.replace(cls.VENUE, "")
        for professional_phrase in (
            "어린이집",
            "어린이 교육 지도사",
            "어린이교육 지도사",
            "어린이교육지도사",
            "유아 교육 지도사",
            "유아교육 지도사",
            "유아교육지도사",
            "유아 교사",
            "유아교사",
            "아동 지도사",
            "아동지도사",
            "아동 상담사",
            "아동상담사",
            "보육교사",
        ):
            text = text.replace(professional_phrase, "")
        explicit_child = bool(
            re.search(r"초등(?:학생)?|\d\s*[~～\-]\s*\d\s*학년", text)
            or re.search(r"만\s*\d{1,2}(?:\s*[~～\-]\s*\d{1,2})?\s*세", text)
            or any(token in text for token in ("어린이", "아동", "유아", "자녀"))
            or "보호자 동반" in text
        )
        if explicit_child:
            return True
        if any(token in text for token in ("성인", "학부모만")):
            return False
        return "가족" in text

    @staticmethod
    def _general_audience(sentences: list[str]) -> str | None:
        for sentence in sentences:
            if (
                "대상" not in sentence
                or not GoyangChildrenMuseumCityNewsSource._has_child_participant(
                    sentence
                )
            ):
                continue
            list_match = re.search(
                r"((?:성인\s*,\s*)?(?:초등학생|어린이|아동|유아\s*가족)"
                r"(?:\s*,\s*(?:초등학생|어린이|아동|유아\s*가족|가족))*)"
                r"\s*(?:을|를)\s*대상",
                sentence,
            )
            if list_match:
                return clean_text(list_match.group(1))
            grade = re.search(
                r"초등(?:학생)?\s*[1-6](?:\s*[~～\-]\s*[1-6])?\s*학년",
                sentence,
            )
            if grade:
                return clean_text(grade.group(0))
            for token in ("초등학생", "어린이", "아동", "유아 가족", "가족"):
                if token in sentence and GoyangChildrenMuseumCityNewsSource._has_child_participant(token):
                    return token
        return None

    @staticmethod
    def _program_price(label: str, sentences: list[str]) -> tuple[str | None, int | None]:
        for sentence in sentences:
            if f"{label} 프로그램" not in sentence or "참가비" not in sentence:
                continue
            match = re.search(
                r"참가비(?:는|가|:)?\s*(?P<unit>1인당\s*)?"
                r"(?P<amount>무료|[0-9][0-9,]*\s*원)",
                sentence,
            )
            if match is None:
                continue
            amount = clean_text(match.group("amount"))
            price_text = clean_text(f"{match.group('unit') or ''}{amount or ''}")
            if amount == "무료":
                return price_text, 0
            if amount:
                return price_text, int(re.sub(r"\D", "", amount))
        return None, None

    @staticmethod
    def _application_fact(label: str, sentences: list[str]) -> tuple[str, str | None]:
        for sentence in sentences:
            if f"{label} 프로그램" not in sentence or not any(
                token in sentence for token in _APPLICATION_TOKENS
            ):
                continue
            month_only = re.search(r"(?:오는\s*)?(\d{1,2})월\s*중", sentence)
            timing = f"{int(month_only.group(1))}월 중" if month_only else None
            if "예정" in sentence and ("모집" in sentence or "접수" in sentence):
                return "모집예정", timing
            exact = re.search(
                r"(?:오는\s*)?(\d{1,2})월\s*(\d{1,2})일"
                r"(?:\s*(오전|오후)\s*(\d{1,2})시)?부터",
                sentence,
            )
            if exact:
                timing = clean_text(exact.group(0))
            if "선착순" in sentence:
                return "선착순 신청", timing
            return "모집안내", timing
        return "운영", None

    @staticmethod
    def _phone(text: str) -> str | None:
        match = _PHONE_RE.search(text)
        if match is None or match.group(1).startswith("01"):
            return None
        return "-".join(match.groups())

    @classmethod
    def _specific_program_facts(
        cls,
        *,
        post: GoyangNewsPost,
        article_title: str,
        sentences: list[str],
        body_text: str,
        year: int,
    ) -> list[GoyangProgramFact]:
        names = {
            match.group("label"): clean_text(match.group("name")) or match.group("label")
            for match in _PROGRAM_NAME_RE.finditer(body_text)
        }
        facts: list[GoyangProgramFact] = []
        seen: set[tuple[str, int, str]] = set()
        for sentence in sentences:
            if not any(verb in sentence for verb in _EVENT_VERBS):
                continue
            for clause in _PROGRAM_CLAUSE_SPLIT_RE.split(sentence):
                schedule = _PROGRAM_SCHEDULE_RE.search(clause)
                if schedule is None:
                    continue
                label = schedule.group("label")
                audience = cls._program_audience(label, sentences)
                if audience is None:
                    continue
                month = int(schedule.group("month"))
                days_text = clean_text(schedule.group("days")) or ""
                event_start, event_end, session_starts = cls._program_dates(
                    year, month, days_text
                )
                if event_start is None and not session_starts:
                    continue
                key = (label, month, days_text)
                if key in seen:
                    continue
                seen.add(key)
                price_text, price_min = cls._program_price(label, sentences)
                status, application_timing = cls._application_fact(label, sentences)
                facts.append(
                    GoyangProgramFact(
                        post_id=post.post_id,
                        article_title=article_title,
                        detail_url=post.detail_url,
                        department=post.department,
                        published_date=post.published_date,
                        label=label,
                        program_name=names.get(label, f"{label} 프로그램"),
                        schedule_text=f"{month}월 {days_text}",
                        audience=audience,
                        event_start=event_start,
                        event_end=event_end,
                        session_starts=session_starts,
                        price_text=price_text,
                        price_min=price_min,
                        status=status,
                        application_timing=application_timing,
                        phone=cls._phone(body_text),
                    )
                )
        return facts

    @classmethod
    def _general_fact(
        cls,
        *,
        post: GoyangNewsPost,
        article_title: str,
        sentences: list[str],
        body_text: str,
        year: int,
    ) -> GoyangProgramFact | None:
        audience = cls._general_audience(sentences)
        if audience is None:
            return None
        for sentence in sentences:
            if not any(verb in sentence for verb in _EVENT_VERBS):
                continue
            match = _MONTH_RANGE_RE.search(sentence)
            if match is None:
                continue
            start_year = int(match.group("start_year") or year)
            end_year = int(match.group("end_year") or start_year)
            start = cls._make_datetime(
                start_year,
                int(match.group("start_month")),
                int(match.group("start_day")),
            )
            end = cls._make_datetime(
                end_year,
                int(match.group("end_month")),
                int(match.group("end_day")),
                end=True,
            )
            if start is None or end is None or start > end:
                continue
            return GoyangProgramFact(
                post_id=post.post_id,
                article_title=article_title,
                detail_url=post.detail_url,
                department=post.department,
                published_date=post.published_date,
                label=None,
                program_name=article_title,
                schedule_text=(
                    f"{start.date().isoformat()}~{end.date().isoformat()}"
                ),
                audience=audience,
                event_start=start,
                event_end=end,
                session_starts=(),
                price_text=None,
                price_min=None,
                status="운영",
                application_timing=None,
                phone=cls._phone(body_text),
            )

        for sentence in sentences:
            if not any(verb in sentence for verb in _EVENT_VERBS):
                continue
            if any(token in sentence for token in _APPLICATION_TOKENS):
                continue
            matches = list(_SINGLE_DATE_RE.finditer(sentence))
            sessions = tuple(
                parsed
                for match in matches
                if (
                    parsed := cls._make_datetime(
                        int(match.group("year") or year),
                        int(match.group("month")),
                        int(match.group("day")),
                    )
                )
                is not None
            )
            if not sessions:
                continue
            return GoyangProgramFact(
                post_id=post.post_id,
                article_title=article_title,
                detail_url=post.detail_url,
                department=post.department,
                published_date=post.published_date,
                label=None,
                program_name=article_title,
                schedule_text=clean_text(sentence) or "",
                audience=audience,
                event_start=None,
                event_end=None,
                session_starts=sessions,
                price_text=None,
                price_min=None,
                status="운영예정" if "예정" in sentence else "운영",
                application_timing=None,
                phone=cls._phone(body_text),
            )
        return None

    @classmethod
    def parse_detail(
        cls, html: str, post: GoyangNewsPost
    ) -> list[GoyangProgramFact]:
        soup = BeautifulSoup(html, "html.parser")
        title_node = soup.select_one("h3.article-subject")
        body_node = soup.select_one("#webView.article-detail")
        if title_node is None or body_node is None:
            raise RuntimeError("Goyang city news detail structure changed: article not found")
        article_title = clean_text(title_node.get_text(" ", strip=True))
        body_text = clean_text(body_node.get_text(" ", strip=True))
        if not article_title or not body_text:
            raise RuntimeError("Goyang city news detail structure changed: empty article")
        if cls.VENUE not in f"{article_title} {body_text}":
            return []
        year = date.fromisoformat(post.published_date).year
        sentences = cls._sentences(body_text)
        specific = cls._specific_program_facts(
            post=post,
            article_title=article_title,
            sentences=sentences,
            body_text=body_text,
            year=year,
        )
        if specific:
            return specific
        general = cls._general_fact(
            post=post,
            article_title=article_title,
            sentences=sentences,
            body_text=body_text,
            year=year,
        )
        return [general] if general is not None else []

    @staticmethod
    def _age(audience: str) -> tuple[int | None, int | None, str]:
        grade = re.search(
            r"초등(?:학생)?\s*([1-6])\s*[~～\-]\s*([1-6])\s*학년",
            audience,
        )
        if grade:
            return int(grade.group(1)) + 6, int(grade.group(2)) + 6, audience
        exact_age = re.search(
            r"만\s*(\d{1,2})\s*[~～\-]\s*(\d{1,2})\s*세", audience
        )
        if exact_age:
            return int(exact_age.group(1)), int(exact_age.group(2)), audience
        if "성인" in audience and any(token in audience for token in _CHILD_TOKENS):
            return None, None, audience
        age_min, age_max, age_text = parse_age_range(audience)
        return age_min, age_max, age_text or audience

    @staticmethod
    def _status(fact: GoyangProgramFact, reference: datetime) -> str:
        if fact.status != "운영" or fact.event_start is None or fact.event_end is None:
            return fact.status
        if fact.event_start <= reference <= fact.event_end:
            return "운영중"
        if reference < fact.event_start:
            return "운영예정"
        return "운영종료"

    @staticmethod
    def _program_key(fact: GoyangProgramFact) -> str:
        """Distinguish programs without tying identity to editable facts."""

        # A post yields at most one unlabeled general fact. Specific facts have
        # an official article label such as "단오" or "칠석". Dates, audience,
        # status and display names are deliberately excluded so an editorial
        # correction updates the same record instead of creating a new ID.
        identity = fact.label or "general"
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]

    @classmethod
    def _map(
        cls,
        fact: GoyangProgramFact,
        *,
        reference: datetime,
        session_start: datetime | None = None,
    ) -> Event:
        event_start = session_start or fact.event_start
        event_end = (
            cls._make_datetime(
                session_start.year,
                session_start.month,
                session_start.day,
                end=True,
            )
            if session_start is not None
            else fact.event_end
        )
        status = cls._status(fact, reference)
        age_min, age_max, age_text = cls._age(fact.audience)
        event_date = event_start.date().isoformat() if event_start else None
        program_key = cls._program_key(fact)
        external_id = f"{fact.post_id}:{program_key}"
        if session_start is not None and event_start is not None:
            external_id = f"{external_id}:{event_start:%Y%m%d}"
        raw = {
            "post_id": fact.post_id,
            "article_title": fact.article_title,
            "published_date": fact.published_date,
            "department": fact.department,
            "label": fact.label,
            "program_name": fact.program_name,
            "schedule_text": fact.schedule_text,
            "event_date": event_date,
            "audience": fact.audience,
            "price_text": fact.price_text,
            "status": status,
            "application_timing": fact.application_timing,
            "venue": cls.VENUE,
            "address": cls.ADDRESS,
            "phone": fact.phone,
        }
        return Event(
            source_id="goyang_children_museum_city_news",
            source_name="고양어린이박물관 고양시 뉴스 체험·교육 일정",
            external_id=external_id,
            title=fact.program_name,
            detail_url=fact.detail_url,
            provider_name=cls.VENUE,
            category="박물관·체험교육",
            description=None,
            event_start=event_start,
            event_end=event_end,
            apply_start=None,
            apply_end=None,
            status=status,
            age_text=age_text,
            age_min=age_min,
            age_max=age_max,
            price_text=fact.price_text,
            price_min=fact.price_min,
            venue_name=cls.VENUE,
            address=cls.ADDRESS,
            region="경기도 고양시",
            latitude=None,
            longitude=None,
            image_url=None,
            phone=fact.phone,
            is_online=False,
            child_relevance_score=child_relevance(
                fact.program_name, fact.audience, fact.article_title
            ),
            license_code=None,
            fetched_at=datetime.now(KST),
            raw=raw,
        )

    @staticmethod
    def _overlaps(event: Event, window: CrawlWindow) -> bool:
        if event.event_start is None or event.event_end is None:
            return False
        return event.event_start <= window.end and event.event_end >= window.start

    @staticmethod
    def _now() -> datetime:
        """Return one KST observation time for status calculations."""

        return datetime.now(KST)

    def crawl(
        self, client: PoliteHttpClient, window: CrawlWindow
    ) -> Iterable[Event]:
        status_reference = self._now()
        seen_posts: set[str] = set()
        seen_events: set[str] = set()
        expected_page_count: int | None = None
        expected_total: int | None = None
        for page in range(1, window.max_pages + 1):
            list_params = {
                "q_bbsCode": "1090",
                "q_searchKey": "1000",
                "q_searchVal": self.VENUE,
                "q_currPage": page,
            }
            client.assert_html_allowed(
                f"{self.LIST_URL}?{urlencode(list_params)}"
            )
            html = client.get_text(
                self.LIST_URL,
                params=list_params,
            )
            total, current_page, page_count = self._page_metadata(html)
            if expected_page_count is None:
                expected_page_count = page_count
                expected_total = total
                if page_count > window.max_pages:
                    raise RuntimeError(
                        "Goyang city news crawl incomplete: max_pages is smaller "
                        f"than the official page count ({window.max_pages} < {page_count})"
                    )
            elif page_count != expected_page_count or total != expected_total:
                raise RuntimeError(
                    "Goyang city news crawl incomplete: totals changed during crawl"
                )
            parsed_page = self.parse_page(html)
            if parsed_page.current_page != page:
                raise RuntimeError(
                    "Goyang city news crawl incomplete: unexpected current page"
                )
            posts = parsed_page.posts
            for post in posts:
                if post.post_id in seen_posts:
                    raise RuntimeError(
                        "Goyang city news crawl incomplete: duplicate post across pages"
                    )
                seen_posts.add(post.post_id)
                client.assert_html_allowed(post.detail_url)
                detail_html = client.get_text(
                    self.DETAIL_URL,
                    params={
                        "q_bbsCode": "1090",
                        "q_bbscttSn": post.post_id,
                        "q_estnColumn1": post.estn_column,
                    },
                )
                for fact in self.parse_detail(detail_html, post):
                    session_values: tuple[datetime | None, ...] = (
                        tuple(fact.session_starts) if fact.session_starts else (None,)
                    )
                    for session_start in session_values:
                        event = self._map(
                            fact,
                            reference=status_reference,
                            session_start=session_start,
                        )
                        if event.external_id in seen_events or not self._overlaps(event, window):
                            continue
                        seen_events.add(event.external_id)
                        yield event
            if page >= page_count:
                break
        if expected_total is None or len(seen_posts) != expected_total:
            raise RuntimeError(
                "Goyang city news crawl incomplete: "
                f"expected={expected_total}, collected={len(seen_posts)}"
            )


__all__ = [
    "GoyangChildrenMuseumCityNewsSource",
    "GoyangNewsPost",
    "GoyangProgramFact",
]
