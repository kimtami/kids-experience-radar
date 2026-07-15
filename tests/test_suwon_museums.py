from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pytest

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.suwon_museums import (
    SuwonMuseumProgramSource,
    builtin_suwon_museum_sources,
)


FIXTURES = Path(__file__).parent / "fixtures"


def json_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def text_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def sources_by_code() -> dict[str, SuwonMuseumProgramSource]:
    return {source.config.museum_code: source for source in builtin_suwon_museum_sources()}


def window() -> CrawlWindow:
    return CrawlWindow(
        start=datetime(2026, 7, 15, tzinfo=KST),
        end=datetime(2026, 8, 31, 23, 59, 59, tzinfo=KST),
        max_pages=3,
    )


def test_factory_builds_three_policy_scoped_museum_sources() -> None:
    sources = builtin_suwon_museum_sources()

    assert [source.info.source_id for source in sources] == [
        "suwon_museum_child_programs",
        "suwon_gwanggyo_museum_child_programs",
        "suwon_hwaseong_museum_child_programs",
    ]
    assert [source.config.museum_code for source in sources] == ["SW", "GG", "HS"]
    assert [source.config.address for source in sources] == [
        "경기도 수원시 영통구 창룡대로 265",
        "경기도 수원시 영통구 광교로 182",
        "경기도 수원시 팔달구 창룡대로 21",
    ]
    assert all(source.info.enabled_by_default is False for source in sources)
    assert all(source.info.requires_key is None for source in sources)
    assert all(
        source.info.policy_status == "reviewed_public_list_html" for source in sources
    )
    assert all("No login" in (source.info.notes or "") for source in sources)


def test_list_and_detail_parsers_are_defensive_and_whitelist_only() -> None:
    payload = json_fixture("suwon_museum_programs.json")
    rows, total_pages = SuwonMuseumProgramSource.parse_page(payload)

    assert len(rows) == 5
    assert total_pages == 1

    detail = SuwonMuseumProgramSource.parse_detail_html(
        text_fixture("suwon_museum_detail.html")
    )
    assert detail == {
        "program_name": "[주말교육] 자연 속 그림한자(8/1)",
        "program_period": "2026.8.1.(토)",
        "application_period": "2026.7.20.(월) 오전 10시부터 신청",
        "venue": "수원광교박물관 1층 다목적실",
        "audience": "어린이",
        "application_method": "온라인",
        "application_type": "선착순",
        "price": "(유료) 5000원",
        "contact": "031-5191-4224, 4228",
    }
    assert "SYNTHETIC-APPLICANT" not in repr(detail)
    assert "000-0000-0000" not in repr(detail)

    with pytest.raises(RuntimeError, match="Suwon museum list malformed"):
        SuwonMuseumProgramSource.parse_page({"items": []})
    with pytest.raises(RuntimeError, match="detail structure changed"):
        SuwonMuseumProgramSource.parse_detail_html("<html>changed</html>")


def test_period_parser_handles_korean_time_and_shorthand_ranges() -> None:
    start, end = SuwonMuseumProgramSource.parse_period(
        "2026.7.20.(월) 오전 10시부터 신청",
        open_ended_single=True,
    )
    assert start == datetime(2026, 7, 20, 10, 0, tzinfo=KST)
    assert end is None

    start, end = SuwonMuseumProgramSource.parse_period(
        "2026.4.22 ~ 5.20. 매주 (수) 10:00~12:00"
    )
    assert start == datetime(2026, 4, 22, 10, 0, tzinfo=KST)
    assert end == datetime(2026, 5, 20, 12, 0, tzinfo=KST)

    start, end = SuwonMuseumProgramSource.parse_period("2026년 7월 11, 25일")
    assert start == datetime(2026, 7, 11, tzinfo=KST)
    assert end is not None and end.date().isoformat() == "2026-07-25"


class FakeClient:
    def __init__(self) -> None:
        self.asserted: list[str] = []
        self.posts: list[tuple[str, dict[str, object] | None]] = []
        self.gets: list[str] = []

    def assert_html_allowed(self, url: str) -> None:
        self.asserted.append(url)

    def post_json(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        data: dict[str, object] | None = None,
    ) -> Any:
        assert params is None
        self.posts.append((url, data))
        return json_fixture("suwon_museum_programs.json")

    def get_text(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
    ) -> str:
        assert params is None
        self.gets.append(url)
        return text_fixture("suwon_museum_detail.html")


def test_crawl_filters_cross_museum_rows_and_never_calls_action_paths() -> None:
    source = sources_by_code()["GG"]
    client = FakeClient()

    events = list(source.crawl(client, window()))  # type: ignore[arg-type]

    assert len(events) == 1
    event = events[0]
    assert event.external_id == "258"
    assert event.title == "[주말교육] 자연 속 그림한자(8/1)"
    assert event.detail_url == (
        "https://rmuseum.suwon.go.kr/progrm/progrmDetail.do?"
        "museumCd=GG&progrmSeq=258&searchTabType=ING"
    )
    assert event.event_start == datetime(2026, 8, 1, tzinfo=KST)
    assert event.event_end is not None and event.event_end.hour == 23
    assert event.apply_start == datetime(2026, 7, 20, 10, 0, tzinfo=KST)
    assert event.apply_end == datetime(2026, 7, 30, 10, 0, tzinfo=KST)
    assert (event.age_min, event.age_max) == (5, 13)
    assert event.price_min == 5000
    assert event.status == "접수대기"
    assert event.provider_name == "수원광교박물관"
    assert event.address == "경기도 수원시 영통구 광교로 182"
    assert event.region == "경기도 수원시"
    assert event.phone == "031-5191-4224"
    assert event.is_online is False
    assert set(event.raw) == source.PUBLIC_RAW_FIELDS
    assert "memberId" not in event.raw
    assert "applicantPhone" not in event.raw
    assert "SYNTHETIC-APPLICANT" not in repr(event.raw)

    assert client.posts == [
        (
            source.LIST_ENDPOINT,
            {"pageIndex": 1, "museumCd": "GG", "searchTabType": "ING"},
        )
    ]
    assert client.gets == [event.detail_url]
    assert client.asserted == [source.LIST_ENDPOINT, event.detail_url]
    called_urls = [url for url, _ in client.posts] + client.gets
    assert all(
        token not in url.casefold()
        for url in called_urls
        for token in ("login", "apply", "payment", "reserve", "queue")
    )

    repeated = list(source.crawl(FakeClient(), window()))  # type: ignore[arg-type]
    assert [(item.uid, item.content_hash) for item in repeated] == [
        (item.uid, item.content_hash) for item in events
    ]
