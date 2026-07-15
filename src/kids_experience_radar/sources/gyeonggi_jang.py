from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
import re
from typing import Any
from urllib.parse import urlparse

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
    parse_price,
)
from .base import Source, SourceInfo


_DETAIL_PATH_RE = re.compile(r"^/(events|edus)/(\d{1,20})/?$")
_SPACE_MARKER = "컬처라운지경기장"


def _text(node: Tag | None) -> str | None:
    return clean_text(node.get_text(" ", strip=True)) if node else None


def _normalized_marker(value: object | None) -> str:
    text = (clean_text(value) or "").casefold()
    return re.sub(r"[^0-9a-z가-힣]+", "", text)


def _is_gyeonggi_jang_row(row: Mapping[str, Any]) -> bool:
    if clean_text(row.get("display")) == "none":
        return False
    haystack = " ".join(
        clean_text(row.get(field)) or ""
        for field in ("title", "summary", "place", "affiliationName")
    )
    return _SPACE_MARKER in _normalized_marker(haystack)


def _canonical_detail(raw_url: object | None) -> tuple[str, str, str] | None:
    url = clean_text(raw_url)
    if not url:
        return None
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or not (
        hostname == "ggcf.kr" or hostname.endswith(".ggcf.kr")
    ):
        return None
    match = _DETAIL_PATH_RE.fullmatch(parsed.path)
    if not match:
        return None
    content_type, content_id = match.groups()
    canonical_host = hostname
    canonical = f"https://{canonical_host}/{content_type}/{content_id}"
    external_id = (
        f"{content_type}:{content_id}"
        if canonical_host in {"ggcf.kr", "www.ggcf.kr"}
        else f"{canonical_host}:{content_type}:{content_id}"
    )
    return canonical, content_type, external_id


def _is_child_candidate(
    title: str, audience: str | None, description: str | None
) -> bool:
    text = " ".join(
        value for value in (title, audience or "", description or "") if value
    ).casefold()
    child_tokens = ("초등", "어린이", "아동", "가족", "키즈", "누구나", "보호자")
    if any(token in text for token in ("성인만", "성인 대상", "학부모만")) and not any(
        token in text for token in ("초등", "어린이", "아동", "가족", "자녀")
    ):
        return False
    if any(token in text for token in child_tokens):
        return True
    age_min, age_max, _ = parse_age_range(audience)
    return (age_min is not None and age_min <= 13) or (
        age_max is not None and age_max <= 13
    )


class GyeonggiJangProgramSource(Source):
    """Collect public program facts for Suwon's Culture Lounge 경기,장.

    The official GGCF list JSON and public information-detail HTML are the only
    collection surfaces. The connector never follows or calls a booking link.
    """

    API_URLS = {
        "events": "https://www.ggcf.kr/api/events",
        "edus": "https://www.ggcf.kr/api/edus",
    }
    LIST_URLS = {
        "events": "https://www.ggcf.kr/events",
        "edus": "https://www.ggcf.kr/edus",
    }
    ADDRESS = "경기도 수원시 영통구 도청로 36 지하(경기융합타운)"
    REGION = "경기도 수원시"

    def __init__(self) -> None:
        self.info = SourceInfo(
            source_id="ggcf_gyeonggi_jang_programs",
            name="컬처라운지 경기,장 어린이·가족 프로그램",
            owner="경기문화재단",
            source_type="reviewed_public_json_html",
            official_url=self.LIST_URLS["events"],
            license_code=None,
            enabled_by_default=False,
            policy_status="reviewed_public_json_html",
            notes=(
                "Official GGCF events/education JSON list plus factual public detail "
                "HTML only. Exact-space filtering avoids ordinary stadium false "
                "positives. The official Instagram account is discovery-only; no "
                "Instagram, Naver booking, login, application, captcha, or reservation "
                "submission endpoint is called."
            ),
        )

    @classmethod
    def parse_api_page(cls, payload: object) -> tuple[list[dict[str, Any]], int]:
        if not isinstance(payload, Mapping):
            raise RuntimeError("GGCF API malformed response: expected an object")
        raw_rows = payload.get("list")
        if not isinstance(raw_rows, list):
            raise RuntimeError("GGCF API malformed response: list is not an array")
        try:
            last_page = int(payload.get("last_page"))
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "GGCF API malformed response: invalid last_page"
            ) from exc
        if last_page < 1:
            raise RuntimeError("GGCF API malformed response: invalid last_page")

        rows: list[dict[str, Any]] = []
        for value in raw_rows:
            if not isinstance(value, Mapping) or not _is_gyeonggi_jang_row(value):
                continue
            row = dict(value)
            if _canonical_detail(row.get("href")) is None:
                continue
            rows.append(row)
        return rows, last_page

    @staticmethod
    def parse_detail(html: str) -> dict[str, str | None]:
        soup = BeautifulSoup(html, "html.parser")
        schema = soup.select_one(".event-shcema, .event-schema")
        info_list = soup.select_one("ul.info-list")
        if schema is None or info_list is None:
            raise RuntimeError(
                "GGCF detail structure changed: schema or public fact list not found"
            )

        schema_facts: dict[str, str] = {}
        for meta in schema.select("meta[property]"):
            prop = clean_text(meta.get("property"))
            content = clean_text(meta.get("content"))
            if prop and content:
                schema_facts[prop] = content

        labelled: dict[str, str] = {}
        for item in info_list.select(":scope > li"):
            label = _text(item.select_one("dt"))
            value = _text(item.select_one("dd"))
            if label and value:
                labelled[re.sub(r"\s+", "", label)] = value

        audience = labelled.get("대상") or schema_facts.get("audience")
        place = labelled.get("장소") or schema_facts.get("location")
        if not audience or not place:
            raise RuntimeError(
                "GGCF detail structure changed: audience or place fact not found"
            )

        description_meta = soup.select_one('meta[property="og:description"]')
        description = (
            clean_text(description_meta.get("content"))
            if isinstance(description_meta, Tag)
            else None
        )
        published_schedule: str | None = None
        schedule_start: str | None = None
        schedule_end: str | None = None
        for node in soup.select(".program_show_tab p, .program_show_tab li"):
            candidate = _text(node)
            if not candidate or not re.search(
                r"(?:운영|행사|교육)\s*일정", candidate
            ):
                continue
            dates = re.findall(
                r"20\d{2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{1,2}",
                candidate,
            )
            if not dates:
                continue
            published_schedule = candidate
            normalized_dates = [
                re.sub(r"\s*([./-])\s*", r"\1", value) for value in dates
            ]
            schedule_start = normalized_dates[0]
            schedule_end = normalized_dates[-1]
            break
        return {
            "resource": schema_facts.get("resource"),
            "title": schema_facts.get("name"),
            "event_start": schema_facts.get("startDate"),
            "event_end": schema_facts.get("endDate"),
            "audience": audience,
            "place": place,
            "event_period": labelled.get("기간"),
            "application_period": labelled.get("접수"),
            "published_schedule": published_schedule,
            "schedule_start": schedule_start,
            "schedule_end": schedule_end,
            "price": labelled.get("참가비"),
            "description": description,
        }

    @staticmethod
    def _overlaps(event: Event, window: CrawlWindow) -> bool:
        if event.event_start is None and event.event_end is None:
            return True
        start = event.event_start or event.event_end
        end = event.event_end or event.event_start
        assert start is not None and end is not None
        return start <= window.end and end >= window.start

    def _map_row(
        self,
        row: Mapping[str, Any],
        detail: Mapping[str, str | None],
        *,
        content_type: str,
        external_id: str,
        detail_url: str,
    ) -> Event | None:
        title = clean_text(row.get("title")) or clean_text(detail.get("title"))
        if not title:
            return None
        description = clean_text(detail.get("description")) or clean_text(
            row.get("summary")
        )
        audience = clean_text(detail.get("audience"))
        if not _is_child_candidate(title, audience, description):
            return None

        age_min, age_max, age_text = parse_age_range(audience)
        price_min, price_text = parse_price(detail.get("price"))
        event_start = parse_datetime(detail.get("schedule_start")) or parse_datetime(
            row.get("progress_start")
        )
        event_end = parse_datetime(
            detail.get("schedule_end"), end_of_day=True
        ) or parse_datetime(row.get("progress_finish"), end_of_day=True)
        if event_start is None and event_end is None:
            event_start, event_end = parse_date_range(detail.get("event_period"))
        apply_start = parse_datetime(row.get("application_start"))
        apply_end = parse_datetime(row.get("application_finish"), end_of_day=True)
        if apply_start is None and apply_end is None:
            apply_start, apply_end = parse_date_range(
                detail.get("application_period")
            )
        place = clean_text(detail.get("place")) or clean_text(row.get("place"))
        api_id = clean_text(row.get("id"))
        affiliation_code = clean_text(row.get("affiliation_code"))
        affiliation_name = clean_text(row.get("affiliationName")) or "경기문화재단"
        status = clean_text(row.get("progress"))
        raw_event_period = " ~ ".join(
            value
            for value in (
                clean_text(row.get("progress_start")),
                clean_text(row.get("progress_finish")),
            )
            if value
        )
        raw_application_period = " ~ ".join(
            value
            for value in (
                clean_text(row.get("application_start")),
                clean_text(row.get("application_finish")),
            )
            if value
        )

        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=external_id,
            title=title,
            detail_url=detail_url,
            provider_name=affiliation_name,
            category="문화·교육·체험",
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
            venue_name=place,
            address=self.ADDRESS,
            region=self.REGION,
            image_url=None,
            is_online=False,
            child_relevance_score=child_relevance(title, age_text, description),
            license_code=self.info.license_code,
            fetched_at=datetime.now(KST),
            raw={
                "api_id": api_id,
                "content_type": content_type,
                "affiliation_code": affiliation_code,
                "affiliation_name": affiliation_name,
                "status": status,
                "event_period": raw_event_period or clean_text(
                    detail.get("event_period")
                ),
                "application_period": raw_application_period
                or clean_text(detail.get("application_period")),
                "published_schedule": clean_text(
                    detail.get("published_schedule")
                ),
                "audience": audience,
                "place": place,
                "price": clean_text(detail.get("price")),
            },
        )

    def crawl(
        self, client: PoliteHttpClient, window: CrawlWindow
    ) -> Iterable[Event]:
        seen_details: set[str] = set()
        for requested_type in ("events", "edus"):
            api_url = self.API_URLS[requested_type]
            client.assert_html_allowed(api_url)
            for page in range(1, window.max_pages + 1):
                payload = client.get_json(
                    api_url,
                    params={"progress": "soon", "limit": 100, "page": page},
                )
                rows, last_page = self.parse_api_page(payload)
                for row in rows:
                    canonical = _canonical_detail(row.get("href"))
                    if canonical is None:
                        continue
                    detail_url, content_type, external_id = canonical
                    if content_type != requested_type or detail_url in seen_details:
                        continue
                    seen_details.add(detail_url)
                    client.assert_html_allowed(detail_url)
                    detail = self.parse_detail(client.get_text(detail_url))
                    event = self._map_row(
                        row,
                        detail,
                        content_type=content_type,
                        external_id=external_id,
                        detail_url=detail_url,
                    )
                    if event is not None and self._overlaps(event, window):
                        yield event
                if page >= last_page:
                    break


__all__ = ["GyeonggiJangProgramSource"]
