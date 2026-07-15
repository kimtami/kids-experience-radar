from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.regional_reservations import (
    AnyangEducationReservationSource,
    CheongjuExperienceReservationSource,
    SelectWebListAdapter,
    builtin_regional_reservation_sources,
)


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class AnyangClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def assert_html_allowed(self, url: str) -> None:
        self.calls.append(("robots", url, None))

    def get_text(self, url: str, *, params: dict[str, object] | None = None) -> str:
        self.calls.append(("get", url, params))
        if url == AnyangEducationReservationSource().list_url:
            return fixture("select_web_anyang_page_1.html")
        assert params is None
        return fixture("select_web_anyang_detail.html")


class CheongjuClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def assert_html_allowed(self, url: str) -> None:
        self.calls.append(("robots", url, None))

    def get_text(self, url: str, *, params: dict[str, object] | None = None) -> str:
        self.calls.append(("get", url, params))
        assert params is not None
        return fixture(f"select_web_cheongju_page_{params['pageIndex']}.html")


def window(*, pages: int) -> CrawlWindow:
    return CrawlWindow(
        start=datetime(2026, 7, 1, tzinfo=KST),
        end=datetime(2026, 8, 31, 23, 59, 59, tzinfo=KST),
        max_pages=pages,
    )


def test_anyang_fetches_detail_facts_only_for_child_candidate() -> None:
    source = AnyangEducationReservationSource()
    client = AnyangClient()

    events = list(source.crawl(client, window(pages=1)))  # type: ignore[arg-type]

    assert len(events) == 1
    event = events[0]
    assert event.external_id == "7702"
    assert event.title == "어린이 경제 교육"
    assert event.detail_url.endswith("eduLctreWebView.do?key=1376&eduLctreNo=7702")
    assert event.status == "모집중"
    assert event.age_text == "초등학생(보호자 및 일반인 수업 참석 가능)"
    assert (event.age_min, event.age_max) == (7, 13)
    assert event.price_text == "무료"
    assert event.event_start == datetime(2026, 8, 3, tzinfo=KST)
    assert event.venue_name == "안양7동행정복지센터 4층 다목적 강당"
    assert event.address == "경기도 안양시 안양7동행정복지센터 4층 다목적 강당"
    assert event.phone is None and "연락처" not in event.raw
    assert client.calls == [
        ("robots", source.list_url, None),
        (
            "get",
            source.list_url,
            {"key": "1376", "searchDiv": "1", "pageIndex": 1},
        ),
        ("robots", event.detail_url, None),
        ("get", event.detail_url, None),
    ]


def test_cheongju_card_layout_paginates_and_filters_adult() -> None:
    source = CheongjuExperienceReservationSource()
    client = CheongjuClient()

    events = list(source.crawl(client, window(pages=2)))  # type: ignore[arg-type]

    assert [event.external_id for event in events] == ["478", "457"]
    assert client.calls == [
        ("robots", source.list_url, None),
        (
            "get",
            source.list_url,
            {"key": "8", "viewMode": "card", "pageUnit": 8, "pageIndex": 1},
        ),
        (
            "get",
            source.list_url,
            {"key": "8", "viewMode": "card", "pageUnit": 8, "pageIndex": 2},
        ),
    ]
    first = events[0]
    assert first.provider_name == "농업기술센터 연구개발과"
    assert first.status == "접수중"
    assert first.price_text == "무료"
    assert first.event_start == datetime(2026, 7, 27, tzinfo=KST)
    assert first.address == "충청북도 청주시 유기농마케팅센터"


def test_select_web_structure_break_and_six_source_factory() -> None:
    with pytest.raises(RuntimeError, match="SelectWebList structure changed"):
        AnyangEducationReservationSource().parse_list_html("<html></html>")

    sources = builtin_regional_reservation_sources()
    assert len(sources) == 6
    assert len({source.info.source_id for source in sources}) == 6
    assert all(source.info.enabled_by_default is False for source in sources)
    assert sum(isinstance(source, SelectWebListAdapter) for source in sources) == 2
    unavailable = {
        source.info.source_id: source.available()[1]
        for source in sources
        if not source.available()[0]
    }
    assert set(unavailable) == {
        "gimpo_experience_reservation",
        "anyang_education_reservation",
    }
    assert "TLS handshake" in (unavailable["anyang_education_reservation"] or "")
