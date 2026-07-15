from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from kids_experience_radar.http import HttpPolicyError
from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.regional_reservations import (
    GeumcheonEducationReservationSource,
    GimpoExperienceReservationSource,
)


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def assert_html_allowed(self, url: str) -> None:
        self.calls.append(("robots", url, None))

    def get_text(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
    ) -> str:
        self.calls.append(("get", url, params))
        assert params is not None
        return fixture(f"municipal_web_reserve_page_{params['pageIndex']}.html")


def test_geumcheon_crawl_pages_public_list_and_filters_adult_rows() -> None:
    source = GeumcheonEducationReservationSource()
    client = FakeClient()
    window = CrawlWindow(
        start=datetime(2026, 7, 15, tzinfo=KST),
        end=datetime(2026, 8, 31, 23, 59, 59, tzinfo=KST),
        max_pages=2,
    )

    events = list(source.crawl(client, window))  # type: ignore[arg-type]

    assert source.info.enabled_by_default is False
    assert [event.external_id for event in events] == ["156784", "156783"]
    assert client.calls == [
        ("robots", source.list_url, None),
        (
            "get",
            source.list_url,
            {"key": "112", "rep": "1", "pageIndex": 1},
        ),
        (
            "get",
            source.list_url,
            {"key": "112", "rep": "1", "pageIndex": 2},
        ),
    ]

    first = events[0]
    assert first.title == "내가 장원급제할 상인가"
    assert first.detail_url.endswith("edcLctreView.do?key=112&searchLctreKey=156784")
    assert first.event_start == datetime(2026, 8, 1, tzinfo=KST)
    assert first.apply_start == datetime(2026, 7, 15, tzinfo=KST)
    assert first.status == "모집 중 · 교육대기"
    assert (first.age_min, first.age_max) == (7, 13)
    assert (first.price_min, first.price_text) == (0, "무료")
    assert first.venue_name == "시흥행궁전시관"
    assert first.address == "서울특별시 금천구 시흥행궁전시관"
    assert set(first.raw) == {
        "external_id",
        "title",
        "status",
        "target",
        "application_period",
        "program_period",
        "place",
        "price",
        "provider",
    }


def test_municipal_parser_fails_loudly_when_list_structure_changes() -> None:
    with pytest.raises(RuntimeError, match="MunicipalWebReserve structure changed"):
        GeumcheonEducationReservationSource().parse_list_html("<html></html>")


def test_gimpo_source_is_exposed_but_blocks_before_any_network_call() -> None:
    source = GimpoExperienceReservationSource()
    client = FakeClient()
    available, reason = source.available()

    assert available is False
    assert reason is not None and "robots.txt disallows" in reason
    with pytest.raises(HttpPolicyError, match="robots.txt disallows"):
        list(
            source.crawl(
                client,  # type: ignore[arg-type]
                CrawlWindow(
                    start=datetime(2026, 7, 15, tzinfo=KST),
                    end=datetime(2026, 8, 15, tzinfo=KST),
                ),
            )
        )
    assert client.calls == []
