from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pytest

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.leeum_hoam import LeeumHoamProgramSource


FIXTURE = Path(__file__).parent / "fixtures" / "leeum_hoam_programs.json"


class FakeClient:
    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict[str, object] | None]] = []
        self.robots_urls: list[str] = []

    def assert_html_allowed(self, url: str) -> None:
        self.robots_urls.append(url)

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
    ) -> Any:
        self.calls.append((url, params))
        return self.payload


@pytest.fixture
def window() -> CrawlWindow:
    return CrawlWindow(
        start=datetime(2026, 7, 15, tzinfo=KST),
        end=datetime(2026, 8, 31, 23, 59, 59, tzinfo=KST),
    )


def load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_crawl_reads_unified_public_list_and_retains_only_whitelisted_facts(
    window: CrawlWindow,
) -> None:
    source = LeeumHoamProgramSource()
    client = FakeClient(load_fixture())

    events = list(source.crawl(client, window))  # type: ignore[arg-type]

    assert source.info.enabled_by_default is False
    assert source.info.policy_status == "review_required_public_json"
    assert source.info.requires_key is None
    assert client.robots_urls == [source.ENDPOINT]
    assert client.calls == [
        (
            source.ENDPOINT,
            {
                "view": "list",
                "status[]": [1, 2],
                "type1": 102,
                "keyword": "",
                "startDate": "",
                "endDate": "",
                "limit": 100,
                "found": "LM",
                "page": 1,
            },
        )
    ]
    assert [event.external_id for event in events] == ["1677", "1700"]

    leeum = events[0]
    assert leeum.title == "키즈랩 7월 프로그램 - 초등학교 3-4학년"
    assert leeum.detail_url == "https://www.leeumhoam.org/leeum/edu/program/1677"
    assert leeum.event_start == datetime(2026, 7, 5, tzinfo=KST)
    assert leeum.event_end is not None and leeum.event_end.hour == 23
    assert (leeum.age_min, leeum.age_max, leeum.age_text) == (
        9,
        10,
        "초등학교 3-4학년",
    )
    assert (leeum.price_min, leeum.price_text) == (0, "무료")
    assert leeum.status == "신청중"
    assert leeum.venue_name == "삼성아동교육문화센터 1층 키즈랩"
    assert leeum.address == "서울특별시 용산구 이태원로55길 60-16"
    assert leeum.region == "서울특별시 용산구"
    assert leeum.description is None
    assert leeum.image_url is None
    assert leeum.phone is None
    assert leeum.raw == {
        "title": leeum.title,
        "period": "2026.07.05~2026.07.18",
        "target": "초등학교 3-4학년",
        "place": "삼성아동교육문화센터 1층 키즈랩",
        "price": "무료",
        "status": "신청중",
        "official_url": leeum.detail_url,
    }

    hoam = events[1]
    assert hoam.detail_url == "https://www.leeumhoam.org/leeum/edu/program/1700"
    assert (hoam.age_min, hoam.age_max, hoam.age_text) == (
        7,
        9,
        "초등학교 1-3학년",
    )
    assert (hoam.price_min, hoam.price_text) == (15_000, "15,000원")
    assert hoam.status == "신청예정"
    assert hoam.venue_name == "호암미술관"
    assert hoam.address == "경기도 용인시 처인구 포곡읍 에버랜드로562번길 38"
    assert hoam.region == "경기도 용인시 처인구"


def test_parse_page_rejects_malformed_envelopes() -> None:
    assert LeeumHoamProgramSource.parse_page(
        {"list": [], "paging": {"page": 1, "maxPage": 1}, "total": 0}
    ) == ([], 1, 1, 0)

    with pytest.raises(RuntimeError, match="malformed response"):
        LeeumHoamProgramSource.parse_page(["not-an-object"])
    with pytest.raises(RuntimeError, match="missing list"):
        LeeumHoamProgramSource.parse_page({"paging": {}})
    with pytest.raises(RuntimeError, match="list is not an array"):
        LeeumHoamProgramSource.parse_page({"list": {"proId": 1}})
    with pytest.raises(RuntimeError, match="paging is not an object"):
        LeeumHoamProgramSource.parse_page({"list": [], "paging": []})


def test_crawl_paginates_unified_public_list(window: CrawlWindow) -> None:
    class PagedClient:
        def assert_html_allowed(self, url: str) -> None:
            return None

        def get_json(
            self,
            url: str,
            *,
            params: dict[str, object] | None = None,
        ) -> dict[str, object]:
            assert params is not None
            page = int(params["page"])
            start = (page - 1) * 100 + 1
            end = min(page * 100, 101)
            return {
                "list": [
                    {
                        "proId": str(index),
                        "title": f"어린이 프로그램 {index}",
                        "homeTarget": "초등 1학년",
                    }
                    for index in range(start, end + 1)
                ],
                "paging": {"page": page, "maxPage": 2, "totalCount": 101},
                "total": 101,
            }

    events = list(LeeumHoamProgramSource().crawl(PagedClient(), window))  # type: ignore[arg-type]

    assert len(events) == 101
    assert events[-1].external_id == "101"
