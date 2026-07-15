from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

import pytest

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.ggc_events import GgcGyeonggiCultureSource


FIXTURE = Path(__file__).parent / "fixtures" / "ggc_playongoing_page_0.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def window() -> CrawlWindow:
    return CrawlWindow(
        start=datetime(2026, 7, 15, tzinfo=KST),
        end=datetime(2026, 12, 31, 23, 59, 59, tzinfo=KST),
        max_pages=3,
    )


class FakeClient:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = payloads
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def assert_html_allowed(self, url: str) -> None:
        self.calls.append(("robots", url, None))

    def get_json(
        self, url: str, *, params: dict[str, object] | None = None
    ) -> dict:
        self.calls.append(("get", url, params))
        return self.payloads.pop(0)


def test_maps_broad_child_possibilities_but_excludes_adult_past_and_unsafe() -> None:
    source = GgcGyeonggiCultureSource()
    client = FakeClient([load_fixture()])

    events = list(source.crawl(client, window()))  # type: ignore[arg-type]

    assert [event.external_id for event in events] == [
        "6a4f50a2954497b1205638a7",
        "69b24a66786a7564b5f2a0a6",
    ]
    assert client.calls == [
        ("robots", source.ENDPOINT, None),
        (
            "get",
            source.ENDPOINT,
            {"page": 0, "perpage": source.PAGE_SIZE},
        ),
    ]

    child = events[0]
    assert child.title == "우리들의 작은 우주 어린이 체험전"
    assert child.detail_url.endswith("/6a4f50a2954497b1205638a7")
    assert child.event_start == datetime(2026, 7, 20, tzinfo=KST)
    assert child.event_end is not None and child.event_end.hour == 23
    assert child.age_text == "어린이"
    assert child.age_min == 5 and child.age_max == 13
    assert child.price_min == 0 and child.price_text == "무료"
    assert child.venue_name == "경기상상캠퍼스"
    assert child.address == "경기도 수원시 권선구 서둔로 166"
    assert child.region == "경기도 수원시"
    assert child.child_relevance_score >= 0.6
    assert set(child.raw) <= source.PUBLIC_RAW_FIELDS
    assert "privateMemberId" not in child.raw

    broad = events[1]
    assert broad.age_text is None
    assert broad.price_min == 10_000
    assert broad.child_relevance_score >= 0.2


def test_pages_until_short_page_and_uses_zero_based_page_numbers() -> None:
    source = GgcGyeonggiCultureSource()
    first = load_fixture()
    first["DATA"] = first["DATA"][:2] * 50
    second = {"INFO": 0, "DATA": []}
    client = FakeClient([first, second])

    events = list(source.crawl(client, window()))  # type: ignore[arg-type]

    assert len(events) == 100
    assert [call[2] for call in client.calls if call[0] == "get"] == [
        {"page": 0, "perpage": 100},
        {"page": 1, "perpage": 100},
    ]


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"INFO": 7, "DATA": []},
        {"INFO": 0, "DATA": {}},
        {"INFO": 0, "DATA": ["broken"]},
    ],
)
def test_parse_page_fails_loudly_on_schema_drift(payload: object) -> None:
    with pytest.raises(RuntimeError, match="GGC Open API"):
        GgcGyeonggiCultureSource.parse_page(payload)


def test_source_is_official_keyless_default_and_never_uses_action_paths() -> None:
    source = GgcGyeonggiCultureSource()

    assert source.info.source_type == "open_api"
    assert source.info.requires_key is None
    assert source.info.enabled_by_default is True
    assert source.info.policy_status == "approved_api"
    notes = (source.info.notes or "").casefold()
    assert "reservation" in notes
    assert "login" in notes
    assert "application" in notes
