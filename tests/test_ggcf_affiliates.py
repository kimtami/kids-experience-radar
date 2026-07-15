from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

import pytest

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.ggcf_affiliates import GgcfAffiliateProgramSource


FIXTURE = Path(__file__).parent / "fixtures" / "ggcf_affiliate_programs.json"


def payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def window() -> CrawlWindow:
    return CrawlWindow(
        start=datetime(2026, 7, 15, tzinfo=KST),
        end=datetime(2026, 10, 31, 23, 59, 59, tzinfo=KST),
        max_pages=3,
    )


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def assert_html_allowed(self, url: str) -> None:
        self.calls.append(("robots", url, None))

    def get_json(
        self, url: str, *, params: dict[str, object] | None = None
    ) -> dict:
        self.calls.append(("get", url, params))
        value = payload()
        content_type = url.rsplit("/", 1)[-1]
        if content_type != "edus":
            for row in value["list"]:
                row["href"] = row["href"].replace(
                    "/edus/", f"/{content_type}/"
                )
        return value


def test_crawl_uses_two_aggregate_lists_and_excludes_exact_venue_adult_and_unsafe() -> None:
    source = GgcfAffiliateProgramSource()
    client = FakeClient()

    events = list(source.crawl(client, window()))  # type: ignore[arg-type]

    assert [event.external_id for event in events] == [
        "events:3287",
        "events:3241",
        "edus:3287",
        "edus:3241",
        "exhibitions:3287",
        "exhibitions:3241",
    ]
    assert client.calls == [
        ("robots", source.API_URLS["events"], None),
        (
            "get",
            source.API_URLS["events"],
            {"progress": "soon", "limit": 100, "page": 1},
        ),
        ("robots", source.API_URLS["edus"], None),
        (
            "get",
            source.API_URLS["edus"],
            {"progress": "soon", "limit": 100, "page": 1},
        ),
        ("robots", source.API_URLS["exhibitions"], None),
        (
            "get",
            source.API_URLS["exhibitions"],
            {"progress": "soon", "limit": 100, "page": 1},
        ),
    ]

    child = events[0]
    assert child.title == "2026년 어린이 전파교실"
    assert child.detail_url == "https://gcm.ggcf.kr/events/796"
    assert child.event_start == datetime(2026, 7, 30, tzinfo=KST)
    assert child.apply_end is not None and child.apply_end.hour == 23
    assert child.age_text == "어린이"
    assert child.age_min == 5 and child.age_max == 13
    assert child.provider_name == "경기도어린이박물관"
    assert child.region == "경기도 용인시"
    assert child.address == "경기도 용인시 기흥구 상갈로 6"
    assert child.child_relevance_score >= 0.6
    assert set(child.raw) <= source.PUBLIC_RAW_FIELDS
    assert "internal_editor_id" not in child.raw

    maker = events[1]
    assert maker.detail_url == "https://sscampus.ggcf.kr/events/1709"
    assert maker.address == "경기도 수원시 권선구 서둔로 166"
    assert maker.age_text is None
    assert maker.region == "경기도 수원시"
    assert maker.child_relevance_score >= 0.15


def test_parse_page_fails_loudly_on_schema_drift() -> None:
    for malformed in (
        [],
        {},
        {"last_page": 1, "list": {}},
        {"last_page": 0, "list": []},
        {"last_page": "bad", "list": []},
        {"last_page": 1, "list": ["bad"]},
    ):
        with pytest.raises(RuntimeError, match="GGCF affiliate API"):
            GgcfAffiliateProgramSource.parse_page(malformed)


def test_source_is_reviewed_list_only_and_never_calls_details_or_actions() -> None:
    source = GgcfAffiliateProgramSource()

    assert source.info.enabled_by_default is False
    assert source.info.policy_status == "reviewed_public_json"
    notes = (source.info.notes or "").casefold()
    for token in ("detail", "reservation", "application", "login", "payment"):
        assert token in notes
