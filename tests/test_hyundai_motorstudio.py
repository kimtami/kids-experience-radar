from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from urllib.robotparser import RobotFileParser

import pytest

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.hyundai_motorstudio import (
    HyundaiMotorstudioKidsWorkshopSource,
)


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeClient:
    def __init__(self, html: str, robots: str) -> None:
        self.html = html
        self.robots = robots
        self.calls: list[tuple[str, str]] = []

    def assert_html_allowed(self, url: str) -> None:
        parser = RobotFileParser()
        parser.parse(self.robots.splitlines())
        assert parser.can_fetch("KidsExperienceRadar/0.1", url)
        self.calls.append(("robots", url))

    def get_text(self, url: str, *, params: dict[str, object] | None = None) -> str:
        assert params is None
        self.calls.append(("get", url))
        return self.html


@pytest.fixture
def window() -> CrawlWindow:
    return CrawlWindow(
        start=datetime(2026, 7, 15, tzinfo=KST),
        end=datetime(2026, 8, 15, 23, 59, 59, tzinfo=KST),
    )


def test_source_metadata_is_reviewed_and_disabled_by_default() -> None:
    source = HyundaiMotorstudioKidsWorkshopSource()

    assert source.info.enabled_by_default is False
    assert source.info.policy_status == "reviewed_public_html"
    assert source.info.requires_key is None
    assert source.info.official_url == source.LIST_URL
    assert "low frequency" in (source.info.notes or "")


def test_parse_html_maps_workshop_fields_and_uses_safe_list_links() -> None:
    source = HyundaiMotorstudioKidsWorkshopSource()

    events = source.parse_html(load_fixture("hyundai_motorstudio_kids.html"))

    assert len(events) == 2
    workshop = events[0]
    assert workshop.external_id == "KIDCM13"
    assert workshop.title == "리틀 연구원의 수소에너지 탐험"
    assert workshop.detail_url == source.LIST_URL
    assert workshop.age_text == "10세~13세"
    assert workshop.age_min == 10
    assert workshop.age_max == 13
    assert workshop.price_text == "33,000원"
    assert workshop.price_min == 33000
    assert workshop.venue_name == "현대 모터스튜디오 고양"
    assert workshop.address == "경기도 고양시 일산서구 킨텍스로 217-6"
    assert workshop.region == "경기도 고양시"
    assert workshop.latitude is None
    assert workshop.longitude is None
    assert workshop.image_url == (
        "https://motorstudio.hyundai.com/home/programs/hydrogen.png"
    )
    assert workshop.raw["operating_hours"] == "토 11:00"
    assert "운영시간: 토 11:00" in (workshop.description or "")
    assert workshop.child_relevance_score == pytest.approx(0.45)

    group = events[1]
    assert len(group.external_id) == 20
    assert group.price_min == 0
    assert group.venue_name == "키즈 워크숍 존"
    assert group.raw["program_id"] is None


def test_crawl_checks_robots_then_fetches_only_the_public_list(
    window: CrawlWindow,
) -> None:
    source = HyundaiMotorstudioKidsWorkshopSource()
    client = FakeClient(
        load_fixture("hyundai_motorstudio_kids.html"),
        load_fixture("hyundai_motorstudio_robots.txt"),
    )

    events = list(source.crawl(client, window))  # type: ignore[arg-type]

    assert len(events) == 2
    assert client.calls == [
        ("robots", source.LIST_URL),
        ("get", source.LIST_URL),
    ]
    assert all("goResrv" not in url for _, url in client.calls)


@pytest.mark.parametrize(
    ("html", "message"),
    [
        ("<html><body></body></html>", "section.list_set not found"),
        (
            '<section class="list_set"><div class="expln_text"></div></section>',
            "no workshop titles parsed",
        ),
        (
            '<section class="list_set"><div class="expln_text">'
            '<div class="cotn_title"><h3>어린이 체험</h3></div></div></section>',
            "no detail fields parsed",
        ),
    ],
)
def test_parse_html_fails_loudly_when_required_structure_changes(
    html: str, message: str
) -> None:
    with pytest.raises(RuntimeError, match=re.escape(message)):
        HyundaiMotorstudioKidsWorkshopSource().parse_html(html)
