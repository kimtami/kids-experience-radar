from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
import re
from urllib.parse import parse_qs, urlencode, urlparse

from bs4 import BeautifulSoup, Tag

from ..http import HttpPolicyError, PoliteHttpClient
from ..models import CrawlWindow, Event
from ..normalizers import (
    KST,
    child_relevance,
    clean_text,
    parse_age_range,
    parse_date_range,
    parse_price,
)
from .base import Source, SourceInfo


_DATE_RE = r"20\d{2}[-./]\d{1,2}[-./]\d{1,2}"
_NUMERIC_ID_RE = re.compile(r"\d{1,20}")


def _node_text(node: Tag | None) -> str | None:
    return clean_text(node.get_text(" ", strip=True)) if node else None


def _safe_id(value: object | None) -> str | None:
    text = clean_text(value)
    return text if text and _NUMERIC_ID_RE.fullmatch(text) else None


def _period_text(value: str | None, *labels: str) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    label_pattern = "|".join(re.escape(label) for label in labels)
    if label_pattern:
        match = re.search(
            rf"(?:{label_pattern})\s*:?\s*({_DATE_RE})\s*[~～]\s*({_DATE_RE})",
            text,
        )
        if match:
            return f"{match.group(1)}~{match.group(2)}"
    dates = re.findall(_DATE_RE, text)
    if len(dates) >= 2:
        return f"{dates[0]}~{dates[1]}"
    if len(dates) == 1:
        return dates[0]
    return None


def _child_candidate(title: str, target: str | None, category: str | None = None) -> bool:
    text = clean_text(f"{title} {target or ''} {category or ''}") or ""
    text_without_childcare = text.replace("어린이집", "")
    child_tokens = ("초등", "어린이", "아동", "가족", "보호자")
    if any(token in text for token in ("유치원", "어린이집", "미취학")):
        if not any(token in text_without_childcare for token in ("초등", "가족", "보호자")):
            return False
    if any(token in text for token in ("성인", "어르신", "교사", "강사")):
        if not any(token in text_without_childcare for token in child_tokens):
            return False
    if any(token in text_without_childcare for token in child_tokens):
        return True
    age_min, age_max, _ = parse_age_range(target)
    return (age_min is not None and age_min <= 13) or (
        age_max is not None and age_max <= 13
    )


def _potential_child(title: str, target: str | None, category: str | None) -> bool:
    if _child_candidate(title, target, category):
        return True
    text = f"{title} {category or ''}"
    return any(
        token in text
        for token in ("교육", "체험", "방학", "박물관", "공원", "청소년")
    )


def _address(region: str, place: str | None) -> str | None:
    if not place:
        return None
    region_prefix = (
        r"(?:서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충청|"
        r"충북|충남|전라|전북|전남|경상|경북|경남|제주)"
        r"(?:특별자치)?(?:도|시)?\s"
    )
    if re.search(region_prefix, place):
        return place
    return f"{region} {place}"


@dataclass(slots=True)
class ReservationFacts:
    external_id: str
    title: str
    detail_url: str
    provider: str | None = None
    category: str | None = None
    status: str | None = None
    target: str | None = None
    application_period: str | None = None
    program_period: str | None = None
    place: str | None = None
    price: str | None = None


@dataclass(slots=True, frozen=True)
class RegionalReservationSpec:
    source_id: str
    name: str
    owner: str
    list_url: str
    detail_url: str
    base_params: Mapping[str, object]
    detail_base_params: Mapping[str, object]
    id_param: str
    page_param: str
    region: str
    category: str
    policy_status: str = "approved_html"
    blocked_reason: str | None = None


class _RegionalReservationSource(Source):
    def __init__(self, spec: RegionalReservationSpec) -> None:
        self.spec = spec
        self.list_url = spec.list_url
        self.info = SourceInfo(
            source_id=spec.source_id,
            name=spec.name,
            owner=spec.owner,
            source_type="public_html",
            official_url=f"{spec.list_url}?{urlencode(spec.base_params)}",
            license_code=None,
            enabled_by_default=False,
            policy_status=spec.policy_status,
            notes=(
                "Official public list and factual information detail GET only. "
                "No login, application, reservation submission, images, or full "
                "description collection. Runtime robots check is mandatory."
            ),
        )

    def available(self) -> tuple[bool, str | None]:
        if self.spec.blocked_reason:
            return False, self.spec.blocked_reason
        return True, None

    def _detail_url(self, external_id: str) -> str:
        params = dict(self.spec.detail_base_params)
        params[self.spec.id_param] = external_id
        return f"{self.spec.detail_url}?{urlencode(params)}"

    def _event(self, facts: ReservationFacts) -> Event:
        event_start, event_end = parse_date_range(facts.program_period)
        apply_start, apply_end = parse_date_range(facts.application_period)
        age_min, age_max, age_text = parse_age_range(facts.target)
        price_min, price_text = parse_price(facts.price)
        provider = facts.provider or self.spec.owner
        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=facts.external_id,
            title=facts.title,
            detail_url=facts.detail_url,
            provider_name=provider,
            category=facts.category or self.spec.category,
            description=None,
            event_start=event_start,
            event_end=event_end,
            apply_start=apply_start,
            apply_end=apply_end,
            status=facts.status,
            age_text=age_text,
            age_min=age_min,
            age_max=age_max,
            price_text=price_text,
            price_min=price_min,
            venue_name=facts.place,
            address=_address(self.spec.region, facts.place),
            region=self.spec.region,
            latitude=None,
            longitude=None,
            image_url=None,
            phone=None,
            is_online=False,
            child_relevance_score=child_relevance(
                facts.title,
                facts.target,
            ),
            license_code=self.info.license_code,
            fetched_at=datetime.now(KST),
            raw={
                "external_id": facts.external_id,
                "title": facts.title,
                "status": facts.status,
                "target": facts.target,
                "application_period": facts.application_period,
                "program_period": facts.program_period,
                "place": facts.place,
                "price": price_text,
                "provider": provider,
            },
        )

    @staticmethod
    def _overlaps(event: Event, window: CrawlWindow) -> bool:
        if event.event_start is None and event.event_end is None:
            return True
        start = event.event_start or event.event_end
        end = event.event_end or event.event_start
        assert start is not None and end is not None
        return start <= window.end and end >= window.start


class MunicipalWebReserveAdapter(_RegionalReservationSource):
    """Label-driven adapter for municipal `web*List/View.do` reservation pages."""

    def parse_list_html(self, html: str) -> list[ReservationFacts]:
        soup = BeautifulSoup(html, "html.parser")
        table = next(
            (
                candidate
                for candidate in soup.select("table")
                if candidate.select_one("caption")
                and "목록" in (_node_text(candidate.select_one("caption")) or "")
            ),
            None,
        )
        if table is None:
            raise RuntimeError(
                "MunicipalWebReserve structure changed: reservation list table not found"
            )

        facts: list[ReservationFacts] = []
        links_seen = 0
        for row in table.select("tbody tr"):
            link = next(
                (
                    node
                    for node in row.select("a[href]")
                    if self.spec.id_param in str(node.get("href") or "")
                ),
                None,
            )
            if link is None:
                continue
            links_seen += 1
            query = parse_qs(urlparse(str(link.get("href") or "")).query)
            external_id = _safe_id((query.get(self.spec.id_param) or [None])[0])
            cells = row.find_all("td", recursive=False)
            title = _node_text(link)
            if external_id is None or title is None or len(cells) < 6:
                continue

            status_values = [
                value
                for node in cells[0].select(".status")
                if (value := _node_text(node))
            ]
            place = _node_text(cells[1].select_one("p"))
            target = _node_text(cells[2])
            periods = _node_text(cells[3])
            price_candidates = [
                value
                for node in cells[5].select("p")
                if (value := _node_text(node))
                and ("원" in value or "무료" in value)
            ]
            facts.append(
                ReservationFacts(
                    external_id=external_id,
                    title=title,
                    detail_url=self._detail_url(external_id),
                    provider=self.spec.owner,
                    category=self.spec.category,
                    status=" · ".join(dict.fromkeys(status_values)) or None,
                    target=target,
                    application_period=_period_text(periods, "신청", "접수"),
                    program_period=_period_text(periods, "교육", "행사", "운영"),
                    place=place,
                    price=price_candidates[-1] if price_candidates else None,
                )
            )

        if links_seen and not facts:
            raise RuntimeError(
                "MunicipalWebReserve structure changed: no valid reservation rows parsed"
            )
        return facts

    def crawl(
        self,
        client: PoliteHttpClient,
        window: CrawlWindow,
    ) -> Iterable[Event]:
        available, reason = self.available()
        if not available:
            raise HttpPolicyError(reason or "source is unavailable")
        client.assert_html_allowed(self.list_url)
        seen: set[str] = set()
        for page in range(1, max(1, window.max_pages) + 1):
            params = dict(self.spec.base_params)
            params[self.spec.page_param] = page
            page_facts = self.parse_list_html(
                client.get_text(self.list_url, params=params)
            )
            if not page_facts:
                break
            for facts in page_facts:
                if facts.external_id in seen:
                    continue
                seen.add(facts.external_id)
                if not _child_candidate(facts.title, facts.target, facts.category):
                    continue
                event = self._event(facts)
                if self._overlaps(event, window):
                    yield event


class GeumcheonEducationReservationSource(MunicipalWebReserveAdapter):
    def __init__(self) -> None:
        super().__init__(
            RegionalReservationSpec(
                source_id="geumcheon_education_reservation",
                name="금천구 통합예약 어린이 교육",
                owner="서울특별시 금천구",
                list_url="https://www.geumcheon.go.kr/reserve/webEdcLctreList.do",
                detail_url="https://www.geumcheon.go.kr/reserve/edcLctreView.do",
                base_params={"key": "112", "rep": "1"},
                detail_base_params={"key": "112"},
                id_param="searchLctreKey",
                page_param="pageIndex",
                region="서울특별시 금천구",
                category="교육·강좌",
            )
        )


class GimpoExperienceReservationSource(MunicipalWebReserveAdapter):
    def __init__(self) -> None:
        super().__init__(
            RegionalReservationSpec(
                source_id="gimpo_experience_reservation",
                name="김포시 통합예약 어린이 견학·체험",
                owner="경기도 김포시",
                list_url="https://www.gimpo.go.kr/reserve/webEtcResveList.do",
                detail_url="https://www.gimpo.go.kr/reserve/webEtcResveView.do",
                base_params={
                    "key": "113",
                    "rep": "1",
                    "etcProgramSection": "EXPERIENCE",
                },
                detail_base_params={"key": "113"},
                id_param="searchEtcResveNo",
                page_param="pageIndex",
                region="경기도 김포시",
                category="견학·체험",
                policy_status="robots_disallow",
                blocked_reason=(
                    "www.gimpo.go.kr robots.txt disallows all paths for the crawler "
                    "user-agent; automated collection is disabled"
                ),
            )
        )


class BDSelectReservationAdapter(_RegionalReservationSource):
    """Adapter for the Goyang/Yongin `BD_selectResveManage*` family."""

    def __init__(
        self,
        spec: RegionalReservationSpec,
        *,
        container_selector: str,
        view_function: str,
        layout: str,
        fetch_details: bool,
    ) -> None:
        super().__init__(spec)
        self.container_selector = container_selector
        self.view_function = view_function
        self.layout = layout
        self.fetch_details = fetch_details
        self._view_re = re.compile(
            rf"\b{re.escape(view_function)}\s*\(\s*['\"]?(\d{{1,20}})"
        )

    def parse_list_html(self, html: str) -> list[ReservationFacts]:
        soup = BeautifulSoup(html, "html.parser")
        container = soup.select_one(self.container_selector)
        if container is None:
            raise RuntimeError(
                "BDSelectReservation structure changed: reservation list not found"
            )

        facts: list[ReservationFacts] = []
        valid_links = 0
        for item in container.find_all("li", recursive=False):
            link = next(
                (
                    node
                    for node in item.select("a[onclick]")
                    if self._view_re.search(str(node.get("onclick") or ""))
                ),
                None,
            )
            if link is None:
                continue
            match = self._view_re.search(str(link.get("onclick") or ""))
            if match is None:
                continue
            external_id = _safe_id(match.group(1))
            if external_id is None:
                continue
            valid_links += 1

            if self.layout == "goyang":
                subject = item.select_one(".list_type02")
                title = _node_text(item.select_one(".list_type02 .subject_tit"))
                direct_spans = subject.find_all("span", recursive=False) if subject else []
                place = _node_text(direct_spans[-1]) if direct_spans else None
                status = _node_text(item.select_one(".list_type01"))
                target = _node_text(item.select_one(".list_type03"))
                periods = _node_text(item.select_one(".list_type04"))
                price_block = _node_text(item.select_one(".list_type06"))
                price_match = re.search(
                    r"무료|[0-9][0-9,]*\s*원",
                    price_block or "",
                )
                provider = self.spec.owner
            else:
                title = _node_text(item.select_one(".service-title"))
                provider = _node_text(item.select_one(".service-center"))
                place = None
                target = None
                periods = " ".join(
                    value
                    for node in item.select("ul")
                    if (value := _node_text(node))
                )
                price_match = None
                status = next(
                    (
                        value
                        for node in item.find_all("div", recursive=False)
                        if any(
                            str(class_name).startswith("service-")
                            and class_name not in {"service-center", "service-title"}
                            for class_name in (node.get("class") or [])
                        )
                        and (value := _node_text(node))
                    ),
                    None,
                )

            if title is None:
                continue
            facts.append(
                ReservationFacts(
                    external_id=external_id,
                    title=title,
                    detail_url=self._detail_url(external_id),
                    provider=provider,
                    category=self.spec.category,
                    status=status,
                    target=target,
                    application_period=_period_text(periods, "신청", "접수"),
                    program_period=_period_text(
                        periods,
                        "체험",
                        "예약",
                        "교육",
                        "프로그램",
                    ),
                    place=place,
                    price=price_match.group(0) if price_match else None,
                )
            )

        if valid_links and not facts:
            raise RuntimeError(
                "BDSelectReservation structure changed: no valid reservation rows parsed"
            )
        return facts

    def parse_detail_html(
        self,
        facts: ReservationFacts,
        html: str,
    ) -> ReservationFacts:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.select_one(".experience-detail table")
        title = _node_text(soup.select_one(".detail-title"))
        if table is None or title is None:
            raise RuntimeError(
                "BDSelectReservation detail structure changed: factual table not found"
            )

        labels: dict[str, str] = {}
        for row in table.select("tr"):
            label = _node_text(row.select_one("th"))
            value = _node_text(row.select_one("td"))
            if label and value:
                labels[re.sub(r"\s+", "", label)] = value

        facts.title = title
        facts.status = _node_text(soup.select_one(".experience-title-area .state")) or facts.status
        facts.provider = _node_text(soup.select_one(".article-header .sub-title")) or facts.provider
        facts.target = labels.get("이용대상") or facts.target
        facts.price = labels.get("이용료") or facts.price
        facts.application_period = (
            _period_text(labels.get("접수기간")) or facts.application_period
        )
        facts.program_period = (
            _period_text(labels.get("프로그램기간")) or facts.program_period
        )
        facts.place = labels.get("장소정보") or facts.place
        return facts

    def crawl(
        self,
        client: PoliteHttpClient,
        window: CrawlWindow,
    ) -> Iterable[Event]:
        client.assert_html_allowed(self.list_url)
        seen: set[str] = set()
        for page in range(1, max(1, window.max_pages) + 1):
            params = dict(self.spec.base_params)
            params[self.spec.page_param] = page
            page_facts = self.parse_list_html(
                client.get_text(self.list_url, params=params)
            )
            if not page_facts:
                break
            for facts in page_facts:
                if facts.external_id in seen:
                    continue
                seen.add(facts.external_id)
                if self.fetch_details:
                    if not _potential_child(facts.title, facts.target, facts.provider):
                        continue
                    client.assert_html_allowed(facts.detail_url)
                    facts = self.parse_detail_html(
                        facts,
                        client.get_text(facts.detail_url),
                    )
                if not _child_candidate(facts.title, facts.target, facts.category):
                    continue
                event = self._event(facts)
                if self._overlaps(event, window):
                    yield event


class GoyangExperienceReservationSource(BDSelectReservationAdapter):
    def __init__(self) -> None:
        super().__init__(
            RegionalReservationSpec(
                source_id="goyang_experience_reservation",
                name="고양시 통합예약 어린이 체험·견학",
                owner="경기도 고양시",
                list_url=(
                    "https://www.goyang.go.kr/resve/manage/"
                    "BD_selectResveManageList.do"
                ),
                detail_url=(
                    "https://www.goyang.go.kr/resve/manage/"
                    "BD_selectResveManage.do"
                ),
                base_params={"q_resveTopClCode": "CL_02"},
                detail_base_params={"q_resveTopClCode": "CL_02"},
                id_param="resveSn",
                page_param="q_currPage",
                region="경기도 고양시",
                category="체험·견학",
            ),
            container_selector="ul.list_style",
            view_function="opResveView",
            layout="goyang",
            fetch_details=False,
        )


class YonginExperienceReservationSource(BDSelectReservationAdapter):
    def __init__(self) -> None:
        super().__init__(
            RegionalReservationSpec(
                source_id="yongin_experience_reservation",
                name="용인시 통합예약 어린이 체험·참여",
                owner="경기도 용인시",
                list_url=(
                    "https://resve.yongin.go.kr/resve/manage/"
                    "BD_selectResveManageList.do"
                ),
                detail_url=(
                    "https://resve.yongin.go.kr/resve/manage/"
                    "BD_selectResveManage.do"
                ),
                base_params={"q_lclas": "CL_01"},
                detail_base_params={"q_lclas": "CL_01"},
                id_param="q_rsn",
                page_param="q_currPage",
                region="경기도 용인시",
                category="체험·참여",
            ),
            container_selector="ul.reservation-list",
            view_function="fnView",
            layout="yongin",
            fetch_details=True,
        )


def _infer_target(text: str | None) -> str | None:
    value = clean_text(text)
    if not value:
        return None
    grade = re.search(
        r"초(?:등(?:학교)?)?\s*[1-6](?:\s*(?:~|[-–])\s*[1-6])?\s*학년?",
        value,
    )
    if grade:
        return clean_text(grade.group(0))
    for marker in ("초등학생", "어린이", "아동", "가족", "청소년"):
        if marker in value:
            return marker
    return None


class SelectWebListAdapter(_RegionalReservationSource):
    """Adapter for municipal `select*WebList/View.do` table/card pages."""

    def __init__(
        self,
        spec: RegionalReservationSpec,
        *,
        layout: str,
        fetch_details: bool,
    ) -> None:
        super().__init__(spec)
        self.layout = layout
        self.fetch_details = fetch_details

    def _id_from_link(self, link: Tag) -> str | None:
        query = parse_qs(urlparse(str(link.get("href") or "")).query)
        return _safe_id((query.get(self.spec.id_param) or [None])[0])

    def _parse_table(self, soup: BeautifulSoup) -> list[ReservationFacts]:
        table = next(
            (
                candidate
                for candidate in soup.select("table")
                if candidate.select_one(f'a[href*="{self.spec.id_param}="]')
                or "목록" in (_node_text(candidate.select_one("caption")) or "")
            ),
            None,
        )
        if table is None:
            raise RuntimeError(
                "SelectWebList structure changed: reservation table not found"
            )

        facts: list[ReservationFacts] = []
        valid_links = 0
        for row in table.select("tbody tr"):
            link = row.select_one(f'a[href*="{self.spec.id_param}="]')
            if link is None:
                continue
            external_id = self._id_from_link(link)
            if external_id is None:
                continue
            valid_links += 1
            cells = row.find_all("td", recursive=False)
            title = _node_text(link.select_one("b") or link)
            if title is None or len(cells) < 7:
                continue
            category = _node_text(cells[1])
            subject_strings = [clean_text(value) for value in cells[2].stripped_strings]
            subject_strings = [value for value in subject_strings if value]
            provider = subject_strings[1] if len(subject_strings) > 1 else self.spec.owner
            place_parts = subject_strings[1:] if len(subject_strings) > 1 else []
            place = " ".join(place_parts) or provider
            period_block = _node_text(cells[3])
            application_block = _node_text(cells[4])
            statuses = [
                value
                for node in cells[6].select(".state")
                if (value := _node_text(node))
            ]
            facts.append(
                ReservationFacts(
                    external_id=external_id,
                    title=title,
                    detail_url=self._detail_url(external_id),
                    provider=provider,
                    category=category or self.spec.category,
                    status=statuses[-1] if statuses else _node_text(cells[6]),
                    target=_infer_target(f"{title} {category or ''}"),
                    application_period=_period_text(
                        application_block,
                        "접수기간",
                        "모집기간",
                    ),
                    program_period=_period_text(period_block),
                    place=place,
                    price=None,
                )
            )

        if valid_links and not facts:
            raise RuntimeError(
                "SelectWebList structure changed: no valid table rows parsed"
            )
        return facts

    def _parse_cards(self, soup: BeautifulSoup) -> list[ReservationFacts]:
        container = soup.select_one(".listWrap.thumbnail")
        if container is None:
            raise RuntimeError(
                "SelectWebList structure changed: reservation cards not found"
            )

        facts: list[ReservationFacts] = []
        valid_links = 0
        for item in container.select(":scope > ul > li"):
            link = item.select_one(f'a[href*="{self.spec.id_param}="]')
            if link is None:
                continue
            external_id = self._id_from_link(link)
            if external_id is None:
                continue
            valid_links += 1
            title = _node_text(item.select_one(".title"))
            if title is None:
                continue
            labels: dict[str, str] = {}
            for field in item.select(".prgInformation > li"):
                label = _node_text(field.select_one("span"))
                value = _node_text(field)
                if label and value:
                    labels[label.replace(" ", "")] = clean_text(value[len(label) :]) or ""
            facts.append(
                ReservationFacts(
                    external_id=external_id,
                    title=title,
                    detail_url=self._detail_url(external_id),
                    provider=_node_text(item.select_one(".organ")) or self.spec.owner,
                    category=self.spec.category,
                    status=_node_text(item.select_one(".stateType")),
                    target=labels.get("대상") or _infer_target(title),
                    application_period=_period_text(labels.get("접수")),
                    program_period=_period_text(labels.get("운영")),
                    place=labels.get("장소"),
                    price=_node_text(item.select_one(".pay")),
                )
            )

        if valid_links and not facts:
            raise RuntimeError(
                "SelectWebList structure changed: no valid cards parsed"
            )
        return facts

    def parse_list_html(self, html: str) -> list[ReservationFacts]:
        soup = BeautifulSoup(html, "html.parser")
        return self._parse_table(soup) if self.layout == "table" else self._parse_cards(soup)

    def parse_detail_html(
        self,
        facts: ReservationFacts,
        html: str,
    ) -> ReservationFacts:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.select_one("table.p-table.block")
        if table is None:
            raise RuntimeError(
                "SelectWebList detail structure changed: factual table not found"
            )

        labels: dict[str, str] = {}
        for row in table.select("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            for index, cell in enumerate(cells):
                if cell.name != "th" or index + 1 >= len(cells):
                    continue
                value_cell = cells[index + 1]
                if value_cell.name != "td":
                    continue
                label = _node_text(cell)
                value = _node_text(value_cell)
                if label and value:
                    labels[re.sub(r"\s+", "", label)] = value

        content = labels.get("교육내용") or ""
        target = (
            labels.get("교육대상")
            or labels.get("수강대상")
            or labels.get("대상")
        )
        if target is None:
            target_match = re.search(r"대상\s*[:：]\s*(.+)", content)
            if target_match:
                target = clean_text(target_match.group(1))

        facts.status = _node_text(table.select_one(".flag")) or facts.status
        facts.target = target or facts.target
        facts.price = labels.get("수강료") or labels.get("이용료") or facts.price
        facts.application_period = (
            _period_text(labels.get("모집기간") or labels.get("접수기간"))
            or facts.application_period
        )
        facts.program_period = (
            _period_text(labels.get("운영기간") or labels.get("교육기간"))
            or facts.program_period
        )
        facts.place = labels.get("교육기관/장소") or labels.get("장소") or facts.place
        return facts

    def crawl(
        self,
        client: PoliteHttpClient,
        window: CrawlWindow,
    ) -> Iterable[Event]:
        client.assert_html_allowed(self.list_url)
        seen: set[str] = set()
        for page in range(1, max(1, window.max_pages) + 1):
            params = dict(self.spec.base_params)
            params[self.spec.page_param] = page
            page_facts = self.parse_list_html(
                client.get_text(self.list_url, params=params)
            )
            if not page_facts:
                break
            for facts in page_facts:
                if facts.external_id in seen:
                    continue
                seen.add(facts.external_id)
                if self.fetch_details:
                    if not _potential_child(facts.title, facts.target, facts.category):
                        continue
                    client.assert_html_allowed(facts.detail_url)
                    facts = self.parse_detail_html(
                        facts,
                        client.get_text(facts.detail_url),
                    )
                if not _child_candidate(facts.title, facts.target, facts.category):
                    continue
                event = self._event(facts)
                if self._overlaps(event, window):
                    yield event


class AnyangEducationReservationSource(SelectWebListAdapter):
    def __init__(self) -> None:
        super().__init__(
            RegionalReservationSpec(
                source_id="anyang_education_reservation",
                name="안양시 통합예약 어린이 교육강좌",
                owner="경기도 안양시",
                list_url="https://www.anyang.go.kr/reserve/selectEduLctreWebList.do",
                detail_url="https://www.anyang.go.kr/reserve/eduLctreWebView.do",
                base_params={"key": "1376", "searchDiv": "1"},
                detail_base_params={"key": "1376"},
                id_param="eduLctreNo",
                page_param="pageIndex",
                region="경기도 안양시",
                category="교육·강좌",
                policy_status="runtime_tls_blocked",
                blocked_reason=(
                    "www.anyang.go.kr TLS handshake fails in PoliteHttpClient; "
                    "automated collection remains disabled until the official server "
                    "and runtime negotiate a supported secure connection"
                ),
            ),
            layout="table",
            fetch_details=True,
        )


class CheongjuExperienceReservationSource(SelectWebListAdapter):
    def __init__(self) -> None:
        super().__init__(
            RegionalReservationSpec(
                source_id="cheongju_experience_reservation",
                name="청주시 통합예약 어린이 체험",
                owner="충청북도 청주시",
                list_url="https://ticket.cheongju.go.kr/www/selectExprnWebList.do",
                detail_url="https://ticket.cheongju.go.kr/www/selectExprnWebView.do",
                base_params={"key": "8", "viewMode": "card", "pageUnit": 8},
                detail_base_params={"key": "8"},
                id_param="exprnNo",
                page_param="pageIndex",
                region="충청북도 청주시",
                category="견학·체험",
            ),
            layout="cards",
            fetch_details=False,
        )


def builtin_regional_reservation_sources() -> list[Source]:
    return [
        GeumcheonEducationReservationSource(),
        GimpoExperienceReservationSource(),
        GoyangExperienceReservationSource(),
        YonginExperienceReservationSource(),
        AnyangEducationReservationSource(),
        CheongjuExperienceReservationSource(),
    ]


__all__ = [
    "AnyangEducationReservationSource",
    "BDSelectReservationAdapter",
    "CheongjuExperienceReservationSource",
    "GeumcheonEducationReservationSource",
    "GimpoExperienceReservationSource",
    "GoyangExperienceReservationSource",
    "MunicipalWebReserveAdapter",
    "SelectWebListAdapter",
    "YonginExperienceReservationSource",
    "builtin_regional_reservation_sources",
]
