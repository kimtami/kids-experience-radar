from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pytest

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.kimchikan import KimchikanSource


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeClient:
    def __init__(self, programs: Any, calendars: dict[str, Any]) -> None:
        self.programs = programs
        self.calendars = calendars
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get_json(self, url: str, *, params: dict[str, object] | None = None) -> Any:
        assert params is not None
        self.calls.append((url, params))
        if url == KimchikanSource.PROGRAMS_ENDPOINT:
            return self.programs
        assert url == KimchikanSource.CALENDAR_ENDPOINT
        return self.calendars[str(params["programCode"])]


@pytest.fixture
def window() -> CrawlWindow:
    return CrawlWindow(
        start=datetime(2026, 7, 15, tzinfo=KST),
        end=datetime(2026, 8, 2, 23, 59, 59, tzinfo=KST),
    )


def test_source_policy_is_public_json_opt_in() -> None:
    info = KimchikanSource().info

    assert info.enabled_by_default is False
    assert info.requires_key is None
    assert info.source_type == "public_json_api"
    assert "robots.txt Allow" in (info.notes or "")
    assert "booking" in (info.notes or "")


def test_crawl_uses_only_program_and_calendar_gets_and_maps_each_schedule(
    window: CrawlWindow,
) -> None:
    client = FakeClient(
        load_fixture("kimchikan_programs.json"),
        {
            "PR0001": load_fixture("kimchikan_calendar_list.json"),
            "PR0002": load_fixture("kimchikan_calendar_single.json"),
        },
    )

    events = list(KimchikanSource().crawl(client, window))  # type: ignore[arg-type]

    assert [event.external_id for event in events] == [
        "PR00014101",
        "PR00014102",
        "PR00025201",
    ]
    assert client.calls == [
        (
            "https://kimchikan.com/rsv/programs",
            {"page": 1, "size": 50, "keyword": "어린이", "language": "ko"},
        ),
        (
            "https://kimchikan.com/rsv/schedules/calendar",
            {"programCode": "PR0001", "start": "2026-07-15", "end": "2026-08-02"},
        ),
        (
            "https://kimchikan.com/rsv/schedules/calendar",
            {"programCode": "PR0002", "start": "2026-07-15", "end": "2026-08-02"},
        ),
    ]

    first = events[0]
    assert first.title == "2026 어린이김치학교 [6-9] [개인]"
    assert first.event_start == datetime(2026, 7, 18, 10, 30, tzinfo=KST)
    assert first.event_end == datetime(2026, 7, 18, 11, 50, tzinfo=KST)
    assert first.apply_start == datetime(2026, 6, 17, 10, 0, tzinfo=KST)
    assert first.apply_end is None
    assert first.status == "예약 가능 · 잔여 6명"
    assert first.age_text == "6~9세 (출생년도: 2018~2021년)"
    assert (first.age_min, first.age_max) == (6, 9)
    assert first.price_min == 0
    assert first.price_text == "어린이 무료 · 보호자 입장료 1인 5,000원"
    assert first.address == "서울특별시 종로구 인사동길 35-4"
    assert first.latitude is None
    assert first.longitude is None
    assert first.image_url == "https://kimchikan.com/upload/images/children-6-9.jpg"
    assert first.raw["program"]["programStatus"] == "001"
    assert first.raw["schedule"]["reservedCnt"] == 18
    assert events[1].status == "마감"
    assert (events[2].age_min, events[2].age_max) == (10, 13)


def test_calendar_summary_empty_and_single_shapes_are_defensive(window: CrawlWindow) -> None:
    programs = {"content": load_fixture("kimchikan_programs.json")["content"][:1]}

    summary = FakeClient(
        programs,
        {"PR0001": load_fixture("kimchikan_calendar_summary.json")},
    )
    assert list(KimchikanSource().crawl(summary, window)) == []  # type: ignore[arg-type]

    empty = FakeClient(programs, {"PR0001": {"content": []}})
    assert list(KimchikanSource().crawl(empty, window)) == []  # type: ignore[arg-type]

    single = KimchikanSource.parse_schedules(
        {"schSeq": 1, "schDate": "2026-07-18", "isClosed": False}
    )
    assert single == [{"schSeq": 1, "schDate": "2026-07-18", "isClosed": False}]


def test_response_errors_and_malformed_shapes_are_rejected() -> None:
    with pytest.raises(RuntimeError, match="Kimchikan API error 400: Bad Request"):
        KimchikanSource.parse_programs(
            {"status": 400, "error": "Bad Request", "message": "invalid keyword"}
        )

    with pytest.raises(RuntimeError, match="Kimchikan API error: unavailable"):
        KimchikanSource.parse_schedules({"success": False, "message": "unavailable"})

    with pytest.raises(RuntimeError, match="malformed response"):
        KimchikanSource.parse_programs("not-json-object")

    assert KimchikanSource.parse_programs({}) == []
    assert KimchikanSource.parse_schedules([]) == []
