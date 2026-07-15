from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.suwon_culture_foundation import (
    SuwonCultureFoundationEducationSource,
)


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def window() -> CrawlWindow:
    return CrawlWindow(
        start=datetime(2026, 7, 15, tzinfo=KST),
        end=datetime(2026, 8, 31, 23, 59, 59, tzinfo=KST),
        max_pages=3,
    )


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def assert_html_allowed(self, url: str) -> None:
        self.calls.append(("robots", url, None))

    def get_text(
        self, url: str, *, params: dict[str, object] | None = None
    ) -> str:
        self.calls.append(("get", url, params))
        if params is not None:
            assert params["p"] == "30"
            return fixture("suwon_culture_foundation_list.html")
        idx = url.rsplit("=", 1)[-1]
        return fixture(
            {
                "3003": "suwon_culture_foundation_detail_child.html",
                "2999": "suwon_culture_foundation_detail_general.html",
                "2990": "suwon_culture_foundation_detail_family.html",
            }[idx]
        )


def test_crawl_collects_child_family_and_broad_experience_across_months() -> None:
    source = SuwonCultureFoundationEducationSource()
    client = FakeClient()

    events = list(source.crawl(client, window()))  # type: ignore[arg-type]

    assert [event.external_id for event in events] == ["3003", "2999", "2990"]
    list_calls = [call for call in client.calls if call[2] is not None]
    assert list_calls == [
        (
            "get",
            source.LIST_URL,
            {"p": "30", "curYear": 2026, "curMonth": 7},
        ),
        (
            "get",
            source.LIST_URL,
            {"p": "30", "curYear": 2026, "curMonth": 8},
        ),
    ]
    detail_calls = [call for call in client.calls if "30_view" in call[1]]
    assert len(detail_calls) == 3
    assert not any(
        token in url.casefold()
        for _, url, _ in client.calls
        for token in ("booking", "submit", "login", "payment", "membertoken")
    )

    child = events[0]
    assert child.title == "방학특강 홍재서당"
    assert child.detail_url == "https://www.swcf.or.kr/?p=30_view&idx=3003"
    assert child.apply_start == datetime(2026, 7, 2, tzinfo=KST)
    assert child.apply_end is not None and child.apply_end.hour == 23
    assert child.event_start == datetime(2026, 7, 28, tzinfo=KST)
    assert child.event_end is not None and child.event_end.month == 8
    assert child.age_text == "7세(2020년생) ~ 초등학교 4학년"
    assert child.age_min == 7 and child.age_max == 10
    assert child.price_min == 35_000
    assert child.venue_name == "수원전통문화관 예절교육관"
    assert child.address == "경기도 수원시 팔달구 정조로 887"
    assert child.region == "경기도 수원시"
    assert child.status == "접수중"
    assert child.child_relevance_score >= 0.55
    assert set(child.raw) <= source.PUBLIC_RAW_FIELDS
    assert "memberToken" not in str(child.raw)

    broad = events[1]
    assert broad.title == "퓨전 다식 체험 <한옥 다식방>"
    assert broad.age_text == "누구나"
    assert broad.age_min is None and broad.age_max is None
    assert broad.price_min == 20_000
    assert broad.child_relevance_score >= 0.2

    family = events[2]
    assert family.status == "마감"
    assert family.price_min == 0
    assert family.age_min == 7 and family.age_max == 13


def test_parsers_fail_closed_on_schema_drift_and_reject_external_detail() -> None:
    source = SuwonCultureFoundationEducationSource

    with pytest.raises(RuntimeError, match="SWCF education list"):
        source.parse_list("<html><body>changed</body></html>")
    with pytest.raises(RuntimeError, match="no valid rows"):
        source.parse_list(
            "<table id='ctable1'><caption>교육정보 리스트</caption>"
            "<tbody><tr><td>broken</td></tr></tbody></table>"
        )
    with pytest.raises(RuntimeError, match="SWCF education detail"):
        source.parse_detail("<html><body>changed</body></html>")
    assert source._canonical_detail("https://evil.example/?p=30_view&idx=12") is None
    assert source._canonical_detail("?p=30_view&idx=12&memberToken=secret") == (
        "12",
        "https://www.swcf.or.kr/?p=30_view&idx=12",
    )


def test_source_is_public_metadata_only_and_non_actioning() -> None:
    source = SuwonCultureFoundationEducationSource()

    assert source.info.enabled_by_default is False
    assert source.info.policy_status == "approved_html"
    assert source.info.license_code is None
    notes = (source.info.notes or "").casefold()
    for token in ("booking", "login", "identity", "payment", "submission"):
        assert token in notes
    assert source._age_range(
        "4세(2022년생) 이상 참여 가능, 초등학생 이하 보호자 동반"
    ) == (4, 13)


def test_month_enumeration_is_bounded() -> None:
    with pytest.raises(RuntimeError, match="24 calendar months"):
        SuwonCultureFoundationEducationSource._month_keys(
            datetime(2024, 1, 1, tzinfo=KST),
            datetime(2026, 2, 1, tzinfo=KST),
        )
