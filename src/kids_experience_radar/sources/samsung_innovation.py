from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
import hashlib
import re
from typing import Any
from urllib.parse import quote, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from ..http import HttpPolicyError, PoliteHttpClient
from ..models import CrawlWindow, Event
from ..normalizers import (
    KST,
    child_relevance,
    clean_text,
    parse_age_range,
    parse_datetime,
    parse_price,
)
from ..policy import explicit_robots_override, explicit_source_approval
from .base import Source, SourceInfo


@dataclass(slots=True, frozen=True)
class SamsungSessionFacts:
    event_date: str
    start_time: str | None
    end_time: str | None
    apply_start_date: str | None
    apply_end_date: str | None
    availability: str | None
    status: str | None


def _node_text(node: Tag | None) -> str | None:
    if node is None:
        return None
    return clean_text(node.get_text(" ", strip=True))


def _join_distinct(*values: object | None) -> str | None:
    parts: list[str] = []
    for value in values:
        text = clean_text(value)
        if text and all(text.casefold() not in part.casefold() for part in parts):
            parts.append(text)
    return clean_text(" ".join(parts))


class SamsungInnovationSource(Source):
    """Collect public S/I/M education sessions and one-off event metadata."""

    ENDPOINT = (
        "https://samsunginnovationmuseum.com/ko/show/selectShowList.json"
        "?pageSize=50&showStatus=&fitPerson=&roomNo=&smallPicTitle1="
    )
    LIST_URL = (
        "https://samsunginnovationmuseum.com/ko/reserve/edu/academyList.do"
    )
    DETAIL_URL = (
        "https://samsunginnovationmuseum.com/ko/reserve/edu/"
        "getAcademyDetail.do?showid={show_id}"
    )
    EVENTS_ENDPOINT = (
        "https://samsunginnovationmuseum.com/ko/event/"
        "selectEventList.json?pageSize=100&languageCd=ko"
    )
    EVENTS_LIST_URL = (
        "https://samsunginnovationmuseum.com/ko/event/eventList.do"
    )
    EVENT_DETAIL_URL = (
        "https://samsunginnovationmuseum.com/ko/event/"
        "eventDetail.do?eventid={event_id}"
    )
    NOTICE_ENDPOINT = (
        "https://samsunginnovationmuseum.com/ko/news/notice_list.json?pageIndex=1"
    )
    NOTICE_LIST_URL = (
        "https://samsunginnovationmuseum.com/ko/news/notice_list.do"
    )
    ONLINE_ENDPOINT = (
        "https://samsunginnovationmuseum.com/ko/onlineEdu/"
        "onlineEduList.json?limitEnd=100"
    )
    ONLINE_LIST_URL = (
        "https://samsunginnovationmuseum.com/ko/onlineEdu/onlineEdu.do"
    )
    UPLOAD_BASE_URL = "https://www.samsunginnovationmuseum.com/upload/"
    ADDRESS = "경기도 수원시 영통구 삼성로 129"
    REGION = "경기도 수원시"
    VENUE = "삼성 이노베이션 뮤지엄"
    SUCCESS_CODES = {"0", "00", "ok", "success"}
    PUBLIC_FIELDS = (
        "id",
        "showName",
        "showStatusNm",
        "fitPersonNm",
        "fitPersonDetail",
        "pepleNumber",
        "applyTime1",
        "applyTime2",
        "startDate",
        "endDate",
        "remainingNum",
        "academyStatus",
        "detailInfo",
        "showTopic",
        "roomNm",
        "smallPicPath",
        "smallPicTitle1",
    )
    EVENT_PUBLIC_FIELDS = (
        "id",
        "eventName",
        "eventTypeNm",
        "fitPersonNm",
        "applyTime1",
        "applyTime2",
        "startDate",
        "endDate",
        "pepleNumber",
        "remainingNum",
        "eventTopic",
        "detailInfo",
        "smallPicPath",
        "smallPicTitle1",
        "smallPicTitle2",
    )
    PRICE_FIELDS = (
        "priceText",
        "showPrice",
        "educationFee",
        "useFee",
        "admissionFee",
        "price",
        "fee",
        "charge",
        "cost",
    )

    def __init__(self) -> None:
        self.info = SourceInfo(
            source_id="samsung_innovation_education",
            name="삼성 이노베이션 뮤지엄 어린이 교육",
            owner="삼성전자",
            source_type="public_json",
            official_url=self.LIST_URL,
            license_code=None,
            enabled_by_default=False,
            policy_status="reviewed_public_json",
            notes=(
                "Reviewed public JSON plus public detail HTML; low-frequency GET "
                "only. Emits individual education sessions and one-off museum "
                "events. Do not call reservation or login endpoints. "
                "Programs are free by the museum's official guidance unless a row "
                "publishes an explicit price. Requires separate source approval and "
                "a documented override for the site's ambiguous HTML robots response."
            ),
        )

    def available(self) -> tuple[bool, str | None]:
        approved, reason = explicit_source_approval(self.info.source_id)
        if not approved:
            return approved, reason
        return explicit_robots_override(self.info.source_id)

    def _assert_collection_allowed(
        self, client: PoliteHttpClient, url: str
    ) -> None:
        """Check robots on every collection path, then apply a reviewed override.

        The Samsung origin currently returns homepage HTML from ``/robots.txt``.
        ``PoliteHttpClient`` therefore fails closed.  A collector can proceed only
        when the operator has independently approved both the source and this
        ambiguous robots response.  An explicit robots ``Disallow`` must never be
        overridden; the override is limited to the client's HTML/WAF ambiguity.
        """

        try:
            client.assert_html_allowed(url)
            return
        except HttpPolicyError as exc:
            message = str(exc).casefold()
            if "returned html/waf" not in message:
                raise
            overridden, reason = explicit_robots_override(self.info.source_id)
            if not overridden:
                raise HttpPolicyError(reason or str(exc)) from exc

    def crawl(
        self, client: PoliteHttpClient, window: CrawlWindow
    ) -> Iterable[Event]:
        self._assert_collection_allowed(client, self.ENDPOINT)
        payload = client.get_json(self.ENDPOINT)
        for row in self.parse_rows(payload):
            if not self._is_child_program(row):
                continue
            if not self._program_may_overlap(row, window):
                continue
            show_id = clean_text(row.get("id"))
            if not show_id:
                continue
            detail_url = self._education_detail_url(show_id)
            self._assert_collection_allowed(client, detail_url)
            detail_html = client.get_text(detail_url)
            for event in self.parse_detail_sessions(
                detail_html,
                row=row,
                detail_url=detail_url,
            ):
                if self._overlaps_window(event, window):
                    yield event
        self._assert_collection_allowed(client, self.EVENTS_ENDPOINT)
        event_payload = client.get_json(self.EVENTS_ENDPOINT)
        for row in self.parse_rows(event_payload):
            if not self._is_child_event(row):
                continue
            event = self._map_event_row(row, reference=window.start)
            if self._overlaps_window(event, window):
                yield event

    @classmethod
    def parse_rows(cls, payload: object) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [dict(row) for row in payload if isinstance(row, Mapping)]
        if not isinstance(payload, Mapping):
            raise RuntimeError(
                "Samsung Innovation API malformed response: expected an object or list"
            )

        code = clean_text(payload.get("resultCode") or payload.get("resultCd"))
        if code is not None and code.casefold() not in cls.SUCCESS_CODES:
            message = clean_text(
                payload.get("resultMessage")
                or payload.get("resultMsg")
                or payload.get("message")
            ) or "unknown error"
            raise RuntimeError(f"Samsung Innovation API error {code}: {message}")

        if "result" in payload:
            result = payload.get("result")
            if result in (None, ""):
                return []
            if isinstance(result, Mapping):
                if "list" in result:
                    return cls._coerce_rows(result.get("list"))
                if "data" in result:
                    return cls._coerce_rows(result.get("data"))
                if cls._looks_like_row(result):
                    return [dict(result)]
                if not result:
                    return []
                raise RuntimeError(
                    "Samsung Innovation API malformed response: result has no list"
                )
            return cls._coerce_rows(result)

        if "list" in payload:
            return cls._coerce_rows(payload.get("list"))
        if cls._looks_like_row(payload):
            return [dict(payload)]
        raise RuntimeError(
            "Samsung Innovation API malformed response: missing result list"
        )

    @staticmethod
    def _looks_like_row(value: Mapping[object, object]) -> bool:
        return "id" in value or "showName" in value

    @classmethod
    def _coerce_rows(cls, value: object) -> list[dict[str, Any]]:
        if value in (None, ""):
            return []
        if isinstance(value, Mapping):
            if not cls._looks_like_row(value):
                raise RuntimeError(
                    "Samsung Innovation API malformed response: invalid single row"
                )
            return [dict(value)]
        if isinstance(value, list):
            return [dict(row) for row in value if isinstance(row, Mapping)]
        raise RuntimeError(
            "Samsung Innovation API malformed response: list is not an array or object"
        )

    @staticmethod
    def _overlaps_window(event: Event, window: CrawlWindow) -> bool:
        if event.event_start is None and event.event_end is None:
            return True
        start = event.event_start or event.event_end
        end = event.event_end or event.event_start
        assert start is not None and end is not None
        return start <= window.end and end >= window.start

    @staticmethod
    def _education_detail_url(show_id: str) -> str:
        return SamsungInnovationSource.DETAIL_URL.format(
            show_id=quote(show_id, safe="")
        )

    @staticmethod
    def _is_child_program(row: Mapping[str, Any]) -> bool:
        haystack = " ".join(
            clean_text(row.get(field)) or ""
            for field in (
                "showName",
                "fitPersonNm",
                "fitPersonDetail",
                "showTopic",
                "detailInfo",
            )
        ).casefold()
        child_tokens = ("초등", "어린이", "아동", "가족", "패밀리", "키즈")
        return any(token in haystack for token in child_tokens)

    @staticmethod
    def _is_child_event(row: Mapping[str, Any]) -> bool:
        haystack = " ".join(
            clean_text(row.get(field)) or ""
            for field in (
                "eventName",
                "fitPersonNm",
                "eventTopic",
                "detailInfo",
                "smallPicTitle1",
                "smallPicTitle2",
            )
        ).casefold()
        child_tokens = ("초등", "어린이", "아동", "가족", "패밀리", "키즈")
        return any(token in haystack for token in child_tokens)

    @staticmethod
    def _program_may_overlap(
        row: Mapping[str, Any], window: CrawlWindow
    ) -> bool:
        start = parse_datetime(row.get("startDate"))
        end = parse_datetime(row.get("endDate"), end_of_day=True)
        if start is not None and start > window.end:
            return False
        if end is not None and end < window.start:
            return False
        return True

    @staticmethod
    def _safe_image_url(value: object | None, *, base_url: str) -> str | None:
        raw = clean_text(value)
        if not raw:
            return None
        absolute = urljoin(base_url, raw)
        parsed = urlparse(absolute)
        host = (parsed.hostname or "").casefold()
        if parsed.scheme.casefold() not in {"http", "https"}:
            return None
        if host not in {
            "samsunginnovationmuseum.com",
            "www.samsunginnovationmuseum.com",
        }:
            return None
        return absolute

    @staticmethod
    def _detail_summary(soup: BeautifulSoup) -> dict[str, str]:
        summary: dict[str, str] = {}
        for item in soup.select(".reservationView__grayBox-item"):
            label = _node_text(item.select_one(".reservationView__grayBox-tit"))
            value = _node_text(item.select_one(".reservationView__grayBox-text"))
            if label and value:
                summary[re.sub(r"\s+", "", label)] = value
        return summary

    @staticmethod
    def _session_facts(row: Tag) -> SamsungSessionFacts | None:
        cells = row.select("td")
        if len(cells) < 4:
            return None
        event_text = _node_text(cells[0]) or ""
        date_match = re.search(r"20\d{2}-\d{2}-\d{2}", event_text)
        if not date_match:
            return None
        time_match = re.search(
            r"(\d{1,2}:\d{2})\s*(?:~|[-–])\s*(\d{1,2}:\d{2})",
            event_text,
        )
        apply_dates = re.findall(
            r"20\d{2}-\d{2}-\d{2}", _node_text(cells[1]) or ""
        )
        return SamsungSessionFacts(
            event_date=date_match.group(0),
            start_time=time_match.group(1) if time_match else None,
            end_time=time_match.group(2) if time_match else None,
            apply_start_date=apply_dates[0] if apply_dates else None,
            apply_end_date=apply_dates[1] if len(apply_dates) > 1 else None,
            availability=_node_text(cells[2]),
            status=_node_text(cells[3]),
        )

    @staticmethod
    def _normalize_session_status(value: str | None) -> str | None:
        compact = re.sub(r"\s+", "", value or "")
        if compact in {"예약하기", "신청하기", "접수하기"}:
            return "접수중"
        return clean_text(value)

    def parse_detail_sessions(
        self,
        html: str,
        *,
        row: Mapping[str, Any],
        detail_url: str,
    ) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        detail_root = soup.select_one(".reservationView__content")
        if detail_root is None:
            raise RuntimeError(
                "Samsung Innovation detail structure changed: content not found"
            )
        title = _node_text(
            detail_root.select_one(".reservationView__head-category")
        ) or clean_text(row.get("showName"))
        if not title:
            raise RuntimeError(
                "Samsung Innovation detail structure changed: title not found"
            )

        summary = self._detail_summary(soup)
        target = summary.get("교육대상") or clean_text(row.get("fitPersonNm"))
        venue = summary.get("교육장소") or clean_text(row.get("roomNm")) or self.VENUE
        if re.sub(r"\s+", "", venue).casefold() == re.sub(
            r"\s+", "", self.VENUE
        ).casefold():
            venue = self.VENUE
        topic = summary.get("주제/내용")
        description = _join_distinct(
            topic,
            self._description(row),
        )
        image_node = detail_root.select_one(".reservationView__slider img[src]")
        image_url = self._safe_image_url(
            image_node.get("src") if isinstance(image_node, Tag) else None,
            base_url=detail_url,
        )
        age_min, age_max, age_text = self._target_age(
            target,
            row.get("fitPersonDetail"),
        )
        price_min, price_text, price_field = self._price(row)
        raw_id = clean_text(row.get("id")) or hashlib.sha256(
            title.encode("utf-8")
        ).hexdigest()[:20]
        public_program = {
            field: row[field] for field in self.PUBLIC_FIELDS if field in row
        }
        if price_field is not None:
            public_program[price_field] = row[price_field]

        schedule_rows = detail_root.select(".tableHori__tbody-tr")
        if not schedule_rows:
            raise RuntimeError(
                "Samsung Innovation detail structure changed: schedule rows not found"
            )

        events: list[Event] = []
        for schedule_row in schedule_rows:
            facts = self._session_facts(schedule_row)
            if facts is None:
                continue
            start_value = " ".join(
                value for value in (facts.event_date, facts.start_time) if value
            )
            end_value = " ".join(
                value for value in (facts.event_date, facts.end_time) if value
            )
            event_start = parse_datetime(start_value)
            event_end = parse_datetime(
                end_value,
                end_of_day=facts.end_time is None,
            )
            identity = "|".join(
                (
                    raw_id,
                    facts.event_date,
                    facts.start_time or "",
                    facts.end_time or "",
                )
            )
            external_id = (
                f"education:{raw_id}:"
                f"{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:16]}"
            )
            is_online = "온라인" in f"{title} {venue} {description or ''}".casefold()
            session_raw: dict[str, Any] = {
                "event_date": facts.event_date,
                "start_time": facts.start_time,
                "end_time": facts.end_time,
                "apply_start_date": facts.apply_start_date,
                "apply_end_date": facts.apply_end_date,
                "availability": facts.availability,
                "status": facts.status,
                "target": target,
                "venue": venue,
            }
            events.append(
                Event(
                    source_id=self.info.source_id,
                    source_name=self.info.name,
                    external_id=external_id,
                    title=title,
                    detail_url=detail_url,
                    provider_name=self.VENUE,
                    category="교육·체험",
                    description=description,
                    event_start=event_start,
                    event_end=event_end,
                    apply_start=parse_datetime(facts.apply_start_date),
                    apply_end=parse_datetime(
                        facts.apply_end_date,
                        end_of_day=True,
                    ),
                    status=self._normalize_session_status(facts.status),
                    age_text=age_text,
                    age_min=age_min,
                    age_max=age_max,
                    price_text=price_text,
                    price_min=price_min,
                    venue_name=venue,
                    address=None if is_online else self.ADDRESS,
                    region="온라인" if is_online else self.REGION,
                    image_url=image_url,
                    is_online=is_online,
                    child_relevance_score=child_relevance(
                        title, age_text, description
                    ),
                    license_code=self.info.license_code,
                    fetched_at=datetime.now(KST),
                    raw={
                        "program": public_program,
                        "session": session_raw,
                    },
                )
            )
        if not events:
            raise RuntimeError(
                "Samsung Innovation detail structure changed: no valid schedule rows"
            )
        return events

    @staticmethod
    def _status_from_apply_window(
        apply_start: datetime | None,
        apply_end: datetime | None,
        *,
        reference: datetime,
    ) -> str | None:
        if apply_start is not None and reference < apply_start:
            return "접수예정"
        if apply_end is not None and reference > apply_end:
            return "접수마감"
        if apply_start is not None or apply_end is not None:
            return "접수중"
        return None

    def _map_event_row(
        self,
        row: Mapping[str, Any],
        *,
        reference: datetime,
    ) -> Event:
        title = clean_text(row.get("eventName")) or clean_text(
            row.get("smallPicTitle1")
        ) or "제목 없음"
        raw_id = clean_text(row.get("id")) or hashlib.sha256(
            "|".join(
                clean_text(row.get(field)) or ""
                for field in ("eventName", "startDate", "endDate")
            ).encode("utf-8")
        ).hexdigest()[:20]
        detail_url = self.EVENT_DETAIL_URL.format(
            event_id=quote(raw_id, safe="")
        )
        target = clean_text(row.get("fitPersonNm"))
        age_min, age_max, age_text = parse_age_range(target)
        description = _join_distinct(
            row.get("eventTopic"),
            row.get("detailInfo"),
            row.get("smallPicTitle2"),
        )
        apply_start = parse_datetime(row.get("applyTime1"))
        apply_end = parse_datetime(row.get("applyTime2"), end_of_day=True)
        image_url = self._safe_image_url(
            (
                f"{self.UPLOAD_BASE_URL.rstrip('/')}/"
                f"{(clean_text(row.get('smallPicPath')) or '').lstrip('/')}"
                if clean_text(row.get("smallPicPath"))
                else None
            ),
            base_url=self.UPLOAD_BASE_URL,
        )
        public_raw = {
            field: row[field]
            for field in self.EVENT_PUBLIC_FIELDS
            if field in row
        }
        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=f"event:{raw_id}",
            title=title,
            detail_url=detail_url,
            provider_name=self.VENUE,
            category=clean_text(row.get("eventTypeNm")) or "이벤트·체험",
            description=description,
            event_start=parse_datetime(row.get("startDate")),
            event_end=parse_datetime(row.get("endDate"), end_of_day=True),
            apply_start=apply_start,
            apply_end=apply_end,
            status=self._status_from_apply_window(
                apply_start,
                apply_end,
                reference=reference,
            ),
            age_text=age_text,
            age_min=age_min,
            age_max=age_max,
            price_text="무료",
            price_min=0,
            venue_name=self.VENUE,
            address=self.ADDRESS,
            region=self.REGION,
            image_url=image_url,
            child_relevance_score=child_relevance(
                title, age_text, description
            ),
            license_code=self.info.license_code,
            fetched_at=datetime.now(KST),
            raw=public_raw,
        )

    @staticmethod
    def _target_age(
        fit_person: object | None, fit_detail: object | None
    ) -> tuple[int | None, int | None, str | None]:
        target = " ".join(
            value
            for value in (clean_text(fit_person), clean_text(fit_detail))
            if value
        )
        age_min, age_max, age_text = parse_age_range(target)
        if not age_text or "초등" not in age_text:
            return age_min, age_max, age_text

        detail = clean_text(fit_detail) or ""
        grade_range = re.search(
            r"([1-6])\s*학년?\s*(?:~|[-–]|부터)\s*([1-6])\s*학년?", detail
        ) or re.search(r"([1-6])\s*(?:~|[-–])\s*([1-6])\s*학년", detail)
        if grade_range:
            first, last = (int(value) for value in grade_range.groups())
            return min(first, last) + 6, max(first, last) + 6, age_text

        minimum = re.search(r"([1-6])\s*학년\s*(?:이상|부터)", detail)
        maximum = re.search(r"([1-6])\s*학년\s*(?:이하|까지)", detail)
        single = re.fullmatch(r"\(?\s*([1-6])\s*학년\s*\)?", detail)
        if minimum:
            age_min = int(minimum.group(1)) + 6
        if maximum:
            age_max = int(maximum.group(1)) + 6
        if single:
            age_min = age_max = int(single.group(1)) + 6
        return age_min, age_max, age_text

    @classmethod
    def _price(
        cls, row: Mapping[str, Any]
    ) -> tuple[int | None, str, str | None]:
        for field in cls.PRICE_FIELDS:
            raw_value = row.get(field)
            price_text = clean_text(raw_value)
            if not price_text:
                continue
            compact = re.sub(r"\s+", "", price_text)
            normalized = (
                f"{price_text}원"
                if re.fullmatch(r"[0-9][0-9,]*", compact)
                else price_text
            )
            price_min, parsed_text = parse_price(normalized)
            return price_min, parsed_text or price_text, field
        return 0, "무료", None

    @staticmethod
    def _description(row: Mapping[str, Any]) -> str | None:
        topic = clean_text(row.get("showTopic"))
        detail = clean_text(row.get("detailInfo"))
        if topic and detail and topic.casefold() not in detail.casefold():
            return f"{topic} {detail}"
        return detail or topic

    def _map_row(self, row: dict[str, Any]) -> Event:
        title = clean_text(row.get("showName")) or "제목 없음"
        raw_id = clean_text(row.get("id"))
        external_id = raw_id or hashlib.sha256(
            "|".join(
                clean_text(row.get(field)) or ""
                for field in ("showName", "startDate", "endDate")
            ).encode("utf-8")
        ).hexdigest()[:20]
        detail_url = (
            self.DETAIL_URL.format(show_id=quote(raw_id, safe=""))
            if raw_id
            else self.LIST_URL
        )
        description = self._description(row)
        age_min, age_max, age_text = self._target_age(
            row.get("fitPersonNm"), row.get("fitPersonDetail")
        )
        price_min, price_text, price_field = self._price(row)
        public_raw = {
            field: row[field] for field in self.PUBLIC_FIELDS if field in row
        }
        if price_field is not None:
            public_raw[price_field] = row[price_field]
        online_haystack = " ".join(
            value for value in (title, description or "") if value
        ).casefold()

        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=external_id,
            title=title,
            detail_url=detail_url,
            provider_name=self.VENUE,
            category="교육·체험",
            description=description,
            event_start=parse_datetime(row.get("startDate")),
            event_end=parse_datetime(row.get("endDate"), end_of_day=True),
            apply_start=parse_datetime(row.get("applyTime1")),
            apply_end=parse_datetime(row.get("applyTime2"), end_of_day=True),
            status=clean_text(row.get("showStatusNm"))
            or clean_text(row.get("academyStatus")),
            age_text=age_text,
            age_min=age_min,
            age_max=age_max,
            price_text=price_text,
            price_min=price_min,
            venue_name=self.VENUE,
            address=self.ADDRESS,
            region=self.REGION,
            is_online="온라인" in online_haystack or "zoom" in online_haystack,
            child_relevance_score=child_relevance(title, age_text, description),
            license_code=self.info.license_code,
            fetched_at=datetime.now(KST),
            raw=public_raw,
        )


SamsungInnovationMuseumSource = SamsungInnovationSource
SamsungInnovationEducationSource = SamsungInnovationSource

__all__ = [
    "SamsungInnovationEducationSource",
    "SamsungInnovationMuseumSource",
    "SamsungInnovationSource",
]
