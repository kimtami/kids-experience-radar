from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

import pytest

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.modu_museum import ModuMuseumSource


FIXTURES = Path(__file__).parent / "fixtures"


def fixture() -> str:
    return (FIXTURES / "modu_museum_programs.html").read_text(encoding="utf-8")


class FakeClient:
    def __init__(self, html: str) -> None:
        self.html = html
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def assert_html_allowed(self, url: str) -> None:
        self.calls.append(("robots", url, None))

    def get_text(self, url: str, *, params: dict[str, object] | None = None) -> str:
        self.calls.append(("get", url, params))
        return self.html


def test_all_sources_exposes_14_disabled_museums() -> None:
    sources = ModuMuseumSource.all_sources()

    assert len(sources) == 14
    assert len({source.info.source_id for source in sources}) == 14
    assert all(source.info.enabled_by_default is False for source in sources)
    assert all(source.info.policy_status == "reviewed_public_html" for source in sources)


def test_parse_html_maps_only_explicit_child_program_facts() -> None:
    source = ModuMuseumSource(1)

    events = source.parse_html(fixture())

    assert len(events) == 2
    family, explorer = events
    assert family.external_id == "10589"
    assert family.title == "특별전 연계 가족 강연"
    assert family.detail_url == "https://modu.museum.go.kr/learn/detail/10589"
    assert family.event_start == datetime(2026, 7, 25, tzinfo=KST)
    assert family.event_end is not None and family.event_end.date().isoformat() == "2026-07-25"
    assert family.status == "접수중 · 대면"
    assert family.age_text == "초등학생 포함 가족 누구나"
    assert family.age_min == 7 and family.age_max == 13
    assert family.provider_name == "국립중앙박물관"
    assert family.venue_name == "국립중앙박물관"
    assert family.region == "서울특별시"
    assert family.description is None
    assert family.image_url is None
    assert family.raw == {
        "program_id": "10589",
        "education_period": "2026.07.25 ~ 2026.07.25",
        "audience": "초등학생 포함 가족 누구나",
        "status": "접수중 · 대면",
        "institution": "국립중앙박물관",
    }
    assert explorer.age_min == 9 and explorer.age_max == 12
    assert all("교원 대상" not in event.title for event in events)


def test_crawl_checks_robots_and_uses_only_public_list() -> None:
    source = ModuMuseumSource(1)
    client = FakeClient(fixture())
    window = CrawlWindow(
        start=datetime(2026, 7, 15, tzinfo=KST),
        end=datetime(2026, 8, 31, 23, 59, tzinfo=KST),
    )

    events = list(source.crawl(client, window))  # type: ignore[arg-type]

    assert len(events) == 2
    assert client.calls == [
        ("robots", source.list_url, None),
        ("get", source.LIST_URL, {"museum": 1, "searchApplyStatus": "ONGOING"}),
    ]


@pytest.mark.parametrize(
    ("html", "message"),
    [
        ("<html></html>", "#listUl not found"),
        (
            '<ul id="listUl"><li><div class="card type02"><span class="title">어린이 교육</span></div></li></ul>',
            "no valid program ids parsed",
        ),
    ],
)
def test_parse_html_fails_loudly_on_structure_change(html: str, message: str) -> None:
    with pytest.raises(RuntimeError, match=re.escape(message)):
        ModuMuseumSource(1).parse_html(html)


def test_rejects_unknown_museum_id() -> None:
    with pytest.raises(ValueError, match="unknown MODU museum id"):
        ModuMuseumSource(99)
