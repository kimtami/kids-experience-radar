from __future__ import annotations

from datetime import datetime
from typing import Iterable
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from ..http import PoliteHttpClient
from ..models import CrawlWindow, Event
from ..normalizers import KST, child_relevance, clean_text, parse_age_range, parse_date_range
from .base import Source, SourceInfo


KNPS_PARKS: dict[str, tuple[str, str, str]] = {
    "B01": ("jirisan", "지리산", "전북특별자치도·전라남도·경상남도"),
    "B02": ("hallyeohaesang", "한려해상", "경상남도·전라남도"),
    "B03": ("seoraksan", "설악산", "강원특별자치도"),
    "B04": ("naejangsan", "내장산", "전북특별자치도·전라남도"),
    "B05": ("deogyusan", "덕유산", "전북특별자치도·경상남도"),
    "B06": ("odaesan", "오대산", "강원특별자치도"),
    "B07": ("juwangsan", "주왕산", "경상북도"),
    "B08": ("taeanhaean", "태안해안", "충청남도"),
    "B09": ("dadohaehaesang", "다도해해상", "전라남도"),
    "B10": ("chiaksan", "치악산", "강원특별자치도"),
    "B11": ("woraksan", "월악산", "충청북도·경상북도"),
    "B12": ("sobaeksan", "소백산", "충청북도·경상북도"),
    "B13": ("gayasan", "가야산", "경상북도·경상남도"),
    "B14": ("bukhansan", "북한산", "서울특별시·경기도"),
    "B15": ("gyeongju", "경주", "경상북도 경주시"),
    "B16": ("gyeryongsan", "계룡산", "충청남도·대전광역시"),
    "B17": ("mudeungsan", "무등산", "광주광역시·전라남도"),
    "B18": ("byeonsanbando", "변산반도", "전북특별자치도"),
    "B19": ("songnisan", "속리산", "충청북도·경상북도"),
    "B20": ("wolchulsan", "월출산", "전라남도"),
    "B22": ("taebaeksan", "태백산", "강원특별자치도·경상북도"),
    "B25": ("palgongsan", "팔공산", "대구광역시·경상북도"),
}


_CHILD_TOKENS = (
    "초등",
    "어린이",
    "아동",
    "가족",
    "키즈",
    "청소년",
    "진로체험",
    "체험학습",
)
_ADULT_ONLY_TOKENS = ("성인", "전문 산악인", "전문가", "교원", "교사")


def _text(node: Tag | None) -> str | None:
    return clean_text(node.get_text(" ", strip=True)) if node else None


def _is_child_candidate(title: str) -> bool:
    lowered = title.casefold()
    if any(token in lowered for token in _ADULT_ONLY_TOKENS) and not any(
        token in lowered for token in ("초등", "어린이", "아동", "가족", "청소년", "자녀")
    ):
        return False
    return any(token in lowered for token in _CHILD_TOKENS)


def _audience_hint(title: str) -> str | None:
    lowered = title.casefold()
    if "초등" in lowered:
        return "초등학생"
    if "가족" in lowered:
        return "가족"
    if any(token in lowered for token in ("어린이", "아동", "키즈")):
        return "어린이"
    if "청소년" in lowered or "진로체험" in lowered:
        return "청소년"
    return None


def _canonical_detail(raw_url: str | None) -> tuple[str, str, str] | None:
    if not raw_url:
        return None
    absolute = urljoin("https://reservation.knps.or.kr/", raw_url)
    parsed = urlparse(absolute)
    if parsed.scheme != "https" or parsed.netloc != "reservation.knps.or.kr":
        return None
    if parsed.path != "/contents/G/serviceGuide.do":
        return None
    query = parse_qs(parsed.query)
    park_id = clean_text((query.get("parkId") or [None])[0])
    product_id = clean_text((query.get("prdId") or [None])[0])
    if not park_id or not product_id:
        return None
    return absolute, park_id, product_id


class KnpsTrailProgramSource(Source):
    """Read public national-park trail program list fragments only."""

    SEARCH_URL = "https://reservation.knps.or.kr/trprogram/searchTrailProgram.do"
    LIST_ENDPOINT = "https://reservation.knps.or.kr/trprogram/trprogramList.do"
    PAGE_SIZE = 30

    def __init__(self, dept_id: str) -> None:
        if dept_id not in KNPS_PARKS:
            raise ValueError(f"unknown KNPS department: {dept_id}")
        self.dept_id = dept_id
        slug, park_name, region = KNPS_PARKS[dept_id]
        self.park_name = park_name
        self.region = region
        self.search_url = f"{self.SEARCH_URL}?deptId={dept_id}"
        self.info = SourceInfo(
            source_id=f"knps_{slug}_trail_programs",
            name=f"{park_name}국립공원 어린이·가족 탐방프로그램",
            owner="국립공원공단",
            source_type="reviewed_public_html_fragment",
            official_url=self.search_url,
            license_code=None,
            enabled_by_default=False,
            policy_status="reviewed_public_list",
            notes=(
                "Official read-only trail-program list fragment. Runtime robots policy is "
                "always checked. Only list facts and the canonical information link are "
                "stored; no serviceGuide fetch, reservation submission, login, or NetFunnel "
                "endpoint is called. Child filtering is conservative and title-based."
            ),
        )

    @classmethod
    def all_sources(cls) -> list["KnpsTrailProgramSource"]:
        return [cls(dept_id) for dept_id in KNPS_PARKS]

    @staticmethod
    def parse_page(html: str) -> tuple[list[dict[str, str]], int]:
        soup = BeautifulSoup(html, "html.parser")
        total_text = _text(soup.select_one(".article-info.trail-prod-list .total > span"))
        try:
            total = int(total_text or "0")
        except ValueError:
            total = 0

        table = soup.select_one("table.table.trail-prod-list")
        if table is None:
            if total == 0 and soup.select_one(".article-info.trail-prod-list") is not None:
                return [], 0
            raise RuntimeError("KNPS page structure changed: trail program table not found")

        rows: list[dict[str, str]] = []
        table_rows = table.select("tbody tr")
        for row in table_rows:
            cells = row.select(":scope > td")
            if len(cells) < 6:
                continue
            detail_node = cells[5].select_one("a[href]")
            detail = _canonical_detail(
                clean_text(detail_node.get("href")) if detail_node else None
            )
            if detail is None:
                continue
            detail_url, park_id, product_id = detail
            park_name = _text(cells[1])
            meeting_place = _text(cells[2])
            title = _text(cells[3])
            operating_period = _text(cells[4])
            if not park_name or not title or not operating_period:
                continue
            rows.append(
                {
                    "product_id": product_id,
                    "park_id": park_id,
                    "park_name": park_name,
                    "meeting_place": meeting_place or "",
                    "title": title,
                    "operating_period": operating_period,
                    "detail_url": detail_url,
                }
            )

        if table_rows and not rows:
            raise RuntimeError("KNPS page structure changed: no valid program rows parsed")
        return rows, total

    def _map_row(self, row: dict[str, str]) -> Event:
        title = row["title"]
        event_start, event_end = parse_date_range(row.get("operating_period"))
        age_text = _audience_hint(title)
        if age_text == "청소년":
            age_min, age_max = 13, 18
        else:
            age_min, age_max, _ = parse_age_range(age_text)
        meeting_place = clean_text(row.get("meeting_place"))
        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=row["product_id"],
            title=title,
            detail_url=row["detail_url"],
            provider_name="국립공원공단",
            category="국립공원 생태·탐방",
            description=None,
            event_start=event_start,
            event_end=event_end,
            apply_start=None,
            apply_end=None,
            status=None,
            age_text=age_text,
            age_min=age_min,
            age_max=age_max,
            price_text=None,
            price_min=None,
            venue_name=meeting_place,
            address=None,
            region=self.region,
            latitude=None,
            longitude=None,
            image_url=None,
            child_relevance_score=child_relevance(title, age_text),
            license_code=self.info.license_code,
            fetched_at=datetime.now(KST),
            raw={
                "product_id": row["product_id"],
                "park_id": row["park_id"],
                "park_name": row["park_name"],
                "meeting_place": meeting_place,
                "operating_period": row["operating_period"],
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

    def crawl(self, client: PoliteHttpClient, window: CrawlWindow) -> Iterable[Event]:
        client.assert_html_allowed(self.LIST_ENDPOINT)
        for page in range(1, window.max_pages + 1):
            html = client.post_text(
                self.LIST_ENDPOINT,
                data={
                    "dept_id": self.dept_id,
                    "dept_name": self.park_name,
                    "orgnzt_gbn": "G",
                    "pageNo": page,
                    "listScale": self.PAGE_SIZE,
                },
            )
            rows, total = self.parse_page(html)
            for row in rows:
                if not _is_child_candidate(row["title"]):
                    continue
                event = self._map_row(row)
                if self._overlaps(event, window):
                    yield event
            if not rows or page * self.PAGE_SIZE >= total:
                break
