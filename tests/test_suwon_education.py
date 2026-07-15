from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.suwon_education import SuwonEducationSource


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
        assert params is not None
        return (
            fixture("suwon_education_list.html")
            if params["q_progressStatusCd"] == "72"
            else fixture("suwon_education_empty.html")
        )


def test_crawl_collects_family_and_broad_experience_not_adult_or_past() -> None:
    source = SuwonEducationSource()
    client = FakeClient()

    events = list(source.crawl(client, window()))  # type: ignore[arg-type]

    assert [event.external_id for event in events] == [
        "seqNo:11992",
        "eduMstSeq:20260708123456",
    ]
    assert client.calls == [
        ("robots", source.LIST_URL, None),
        (
            "get",
            source.LIST_URL,
            {
                "q_progressStatusCd": "72",
                "q_rowPerPage": 100,
                "q_currPage": 1,
            },
        ),
        (
            "get",
            source.LIST_URL,
            {
                "q_progressStatusCd": "73",
                "q_rowPerPage": 100,
                "q_currPage": 1,
            },
        ),
    ]

    family = events[0]
    assert family.detail_url == (
        "https://www.suwon.go.kr/web/reserv/edu/view.do?seqNo=11992"
    )
    assert family.apply_start == datetime(2026, 7, 8, tzinfo=KST)
    assert family.apply_end is not None and family.apply_end.hour == 23
    assert family.event_start == datetime(2026, 7, 18, tzinfo=KST)
    assert family.age_text == "가족"
    assert family.age_min == 5 and family.age_max == 13
    assert family.status == "접수중"
    assert family.venue_name == "서울대학교 수원수목원"
    assert family.address == "경기도 수원시 권선구 서둔동 92-6"
    assert family.region == "경기도 수원시"
    assert family.child_relevance_score >= 0.25
    assert "memberToken" not in family.detail_url

    woodworking = events[1]
    assert woodworking.age_text == "초등 3~6학년"
    assert woodworking.address == "경기도 수원시 장안구 정조로 1085"
    assert woodworking.age_min == 9 and woodworking.age_max == 12
    assert woodworking.raw["capacity"] == "0 / 15 (0 / 0)"
    assert set(woodworking.raw) <= source.PUBLIC_RAW_FIELDS


def test_parse_list_fails_closed_on_missing_or_drifted_table() -> None:
    with pytest.raises(RuntimeError, match="Suwon education list"):
        SuwonEducationSource.parse_list("<html><body>changed</body></html>")
    with pytest.raises(RuntimeError, match="no valid rows"):
        SuwonEducationSource.parse_list(
            "<table class='yeyak-t'><caption>교육 목록</caption><tbody>"
            "<tr><td>broken</td></tr></tbody></table>"
        )


def test_source_is_public_list_only_and_non_actioning() -> None:
    source = SuwonEducationSource()

    assert source.info.enabled_by_default is False
    assert source.info.policy_status == "approved_html"
    assert source.info.license_code == "KOGL-4"
    notes = (source.info.notes or "").casefold()
    assert "reservation" in notes
    assert "login" in notes
    assert "payment" in notes
