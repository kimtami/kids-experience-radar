from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.regional_reservations import (
    GoyangExperienceReservationSource,
    YonginExperienceReservationSource,
)


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class GoyangClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def assert_html_allowed(self, url: str) -> None:
        self.calls.append(("robots", url, None))

    def get_text(self, url: str, *, params: dict[str, object] | None = None) -> str:
        self.calls.append(("get", url, params))
        assert params is not None
        return fixture(f"bd_select_goyang_page_{params['q_currPage']}.html")


class YonginClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def assert_html_allowed(self, url: str) -> None:
        self.calls.append(("robots", url, None))

    def get_text(self, url: str, *, params: dict[str, object] | None = None) -> str:
        self.calls.append(("get", url, params))
        if url == YonginExperienceReservationSource().list_url:
            return fixture("bd_select_yongin_page_1.html")
        assert params is None
        return fixture("bd_select_yongin_detail.html")


def window(*, pages: int = 2) -> CrawlWindow:
    return CrawlWindow(
        start=datetime(2026, 7, 1, tzinfo=KST),
        end=datetime(2026, 8, 31, 23, 59, 59, tzinfo=KST),
        max_pages=pages,
    )


def test_goyang_common_adapter_paginates_and_filters_preschool_and_adult() -> None:
    source = GoyangExperienceReservationSource()
    client = GoyangClient()

    events = list(source.crawl(client, window()))  # type: ignore[arg-type]

    assert [event.external_id for event in events] == ["7093", "6985"]
    assert client.calls == [
        ("robots", source.list_url, None),
        ("get", source.list_url, {"q_resveTopClCode": "CL_02", "q_currPage": 1}),
        ("get", source.list_url, {"q_resveTopClCode": "CL_02", "q_currPage": 2}),
    ]
    family = events[0]
    assert family.detail_url.endswith(
        "BD_selectResveManage.do?q_resveTopClCode=CL_02&resveSn=7093"
    )
    assert family.status == "접수중"
    assert family.price_text == "무료"
    assert family.event_start == datetime(2026, 8, 1, tzinfo=KST)
    assert family.apply_start == datetime(2026, 7, 1, tzinfo=KST)
    assert family.address == "경기도 고양시 정발산유아숲체험원"


def test_yongin_fetches_only_public_information_detail_for_child_candidate() -> None:
    source = YonginExperienceReservationSource()
    client = YonginClient()

    events = list(source.crawl(client, window(pages=1)))  # type: ignore[arg-type]

    assert len(events) == 1
    event = events[0]
    assert event.external_id == "2535"
    assert event.detail_url.endswith(
        "BD_selectResveManage.do?q_lclas=CL_01&q_rsn=2535"
    )
    assert event.age_text == "어린이(만 13세 이하)"
    assert event.event_start == datetime(2026, 7, 3, tzinfo=KST)
    assert event.apply_start == datetime(2026, 6, 24, tzinfo=KST)
    assert event.price_text == "무료"
    assert event.address == "경기도 용인시 수지구 수지로 253 수지생태공원"
    assert event.phone is None
    assert "전화번호" not in event.raw
    assert client.calls == [
        ("robots", source.list_url, None),
        ("get", source.list_url, {"q_lclas": "CL_01", "q_currPage": 1}),
        ("robots", event.detail_url, None),
        ("get", event.detail_url, None),
    ]
    assert all("apply" not in url.casefold() for _, url, _ in client.calls)


def test_bd_select_parser_fails_loudly_on_structure_change() -> None:
    with pytest.raises(RuntimeError, match="BDSelectReservation structure changed"):
        GoyangExperienceReservationSource().parse_list_html("<html></html>")
