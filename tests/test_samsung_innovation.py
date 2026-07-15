from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pytest

from kids_experience_radar.http import HttpPolicyError
from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.samsung_innovation import SamsungInnovationSource


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture() -> dict[str, Any]:
    return json.loads(
        (FIXTURES / "samsung_innovation_education.json").read_text(encoding="utf-8")
    )


class FakeClient:
    def __init__(
        self,
        *,
        education_payload: object,
        event_payload: object,
        detail_html: str,
    ) -> None:
        self.education_payload = education_payload
        self.event_payload = event_payload
        self.detail_html = detail_html
        self.calls: list[tuple[str, str]] = []

    def assert_html_allowed(self, url: str) -> None:
        self.calls.append(("ROBOTS", url))

    def get_json(
        self, url: str, *, params: dict[str, object] | None = None
    ) -> object:
        assert params is None
        self.calls.append(("GET JSON", url))
        if url == SamsungInnovationSource.ENDPOINT:
            return self.education_payload
        if url == SamsungInnovationSource.EVENTS_ENDPOINT:
            return self.event_payload
        raise AssertionError(f"unexpected JSON URL: {url}")

    def get_text(
        self, url: str, *, params: dict[str, object] | None = None
    ) -> str:
        assert params is None
        self.calls.append(("GET HTML", url))
        if "getAcademyDetail.do" not in url:
            raise AssertionError(f"unexpected HTML URL: {url}")
        return self.detail_html


@pytest.fixture
def window() -> CrawlWindow:
    return CrawlWindow(
        start=datetime(2026, 7, 15, tzinfo=KST),
        end=datetime(2026, 8, 31, 23, 59, 59, tzinfo=KST),
    )


def test_crawl_maps_public_sessions_and_events_with_get_only(
    window: CrawlWindow,
) -> None:
    source = SamsungInnovationSource()
    education_row = load_fixture()["result"]["list"][0]
    education_payload = {
        "resultCode": "00",
        "result": {"list": [education_row]},
    }
    event_payload = json.loads(
        (FIXTURES / "samsung_innovation_events.json").read_text(
            encoding="utf-8"
        )
    )
    detail_html = (FIXTURES / "samsung_innovation_detail.html").read_text(
        encoding="utf-8"
    )
    client = FakeClient(
        education_payload=education_payload,
        event_payload=event_payload,
        detail_html=detail_html,
    )

    events = list(source.crawl(client, window))  # type: ignore[arg-type]

    assert client.calls == [
        ("ROBOTS", source.ENDPOINT),
        ("GET JSON", source.ENDPOINT),
        (
            "ROBOTS",
            "https://samsunginnovationmuseum.com/ko/reserve/edu/"
            "getAcademyDetail.do?showid=9001",
        ),
        (
            "GET HTML",
            "https://samsunginnovationmuseum.com/ko/reserve/edu/"
            "getAcademyDetail.do?showid=9001",
        ),
        ("ROBOTS", source.EVENTS_ENDPOINT),
        ("GET JSON", source.EVENTS_ENDPOINT),
    ]
    assert len(events) == 3
    assert all(
        method == "ROBOTS" or method.startswith("GET")
        for method, _ in client.calls
    )
    assert events[0].external_id.startswith("education:9001:")
    assert events[1].external_id.startswith("education:9001:")
    assert events[2].external_id == "event:7001"
    assert source.info.enabled_by_default is False
    assert source.info.policy_status == "reviewed_public_json"
    assert source.info.requires_key is None
    assert "low-frequency" in (source.info.notes or "")

    event = events[0]
    assert event.title == "합성 어린이 기술교실 A"
    assert event.detail_url == (
        "https://samsunginnovationmuseum.com/ko/reserve/edu/"
        "getAcademyDetail.do?showid=9001"
    )
    assert event.provider_name == "삼성 이노베이션 뮤지엄"
    assert event.category == "교육·체험"
    assert event.status == "접수예정"
    assert event.event_start == datetime(2026, 8, 22, 11, 30, tzinfo=KST)
    assert event.event_end == datetime(2026, 8, 22, 12, 30, tzinfo=KST)
    assert event.apply_start == datetime(2026, 8, 10, tzinfo=KST)
    assert event.apply_end is not None and event.apply_end.hour == 23
    assert event.age_text == "초등학생 (3학년 이상)"
    assert event.age_min == 9
    assert event.age_max == 13
    assert event.price_text == "무료"
    assert event.price_min == 0
    assert event.venue_name == "삼성 이노베이션 뮤지엄"
    assert event.address == "경기도 수원시 영통구 삼성로 129"
    assert event.region == "경기도 수원시"
    assert event.latitude is None
    assert event.longitude is None
    assert event.is_online is False
    assert "합성 AI 에너지 수업" in (event.description or "")
    assert "합성 에너지 교육" in (event.description or "")
    assert event.raw["program"]["pepleNumber"] == "20"
    assert event.raw["program"]["remainingNum"] == "4/20"
    assert event.raw["session"]["availability"] == "20 / 20"
    serialized_raw = json.dumps(event.raw, ensure_ascii=False)
    assert "chargerUserName" not in serialized_raw
    assert "synthetic-internal-plan" not in serialized_raw
    assert "synthetic-private-code" not in serialized_raw

    museum_event = events[2]
    assert museum_event.title == "합성 어린이 과학 아트 체험"
    assert museum_event.event_start == datetime(2026, 8, 15, 11, tzinfo=KST)
    assert museum_event.apply_start == datetime(2026, 8, 1, 10, tzinfo=KST)
    assert museum_event.status == "접수예정"
    assert museum_event.price_text == "무료"
    assert museum_event.price_min == 0
    assert museum_event.image_url == (
        "https://www.samsunginnovationmuseum.com/upload/images/test-event.png"
    )
    assert "accessUserIp" not in museum_event.raw
    assert "chargerUserName" not in museum_event.raw
    assert "loginSessionId" not in museum_event.raw


def test_samsung_requires_separate_source_and_robots_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = SamsungInnovationSource()
    monkeypatch.setenv("KIDS_RADAR_APPROVED_SOURCES", source.info.source_id)
    monkeypatch.delenv("KIDS_RADAR_ROBOTS_OVERRIDE_SOURCES", raising=False)

    available, reason = source.available()

    assert available is False
    assert "KIDS_RADAR_ROBOTS_OVERRIDE_SOURCES" in (reason or "")


def test_ambiguous_robots_override_never_overrides_explicit_disallow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = SamsungInnovationSource()
    monkeypatch.setenv(
        "KIDS_RADAR_ROBOTS_OVERRIDE_SOURCES",
        source.info.source_id,
    )

    class AmbiguousClient:
        def assert_html_allowed(self, url: str) -> None:
            raise HttpPolicyError(
                "robots endpoint returned HTML/WAF; fail closed: robots.txt"
            )

    class ExplicitlyDeniedClient:
        def assert_html_allowed(self, url: str) -> None:
            raise HttpPolicyError("disallowed by robots.txt: robots.txt")

    source._assert_collection_allowed(AmbiguousClient(), source.ENDPOINT)  # type: ignore[arg-type]
    with pytest.raises(HttpPolicyError, match="disallowed by robots.txt"):
        source._assert_collection_allowed(  # type: ignore[arg-type]
            ExplicitlyDeniedClient(),
            source.ENDPOINT,
        )


def test_aggregate_mapper_still_normalizes_online_and_explicit_fee() -> None:
    source = SamsungInnovationSource()
    row = load_fixture()["result"]["list"][1]

    online = source._map_row(row)

    assert online.age_min == 7
    assert online.age_max == 8
    assert online.price_text == "12,000원"
    assert online.price_min == 12_000
    assert online.is_online is True
    assert online.raw["fee"] == "12,000원"


def test_parse_rows_accepts_envelope_bare_list_and_single_row() -> None:
    row = {
        "id": "1",
        "showName": "어린이 연구소",
        "showStatusNm": "접수중",
    }

    assert SamsungInnovationSource.parse_rows(
        {"resultCode": "00", "result": {"list": [row]}}
    ) == [row]
    assert SamsungInnovationSource.parse_rows([row, None, "bad"]) == [row]
    assert SamsungInnovationSource.parse_rows(row) == [row]
    assert SamsungInnovationSource.parse_rows(
        {"resultCode": "00", "result": {"list": row}}
    ) == [row]
    assert SamsungInnovationSource.parse_rows(
        {"resultCode": "00", "result": {"list": []}}
    ) == []


def test_parse_rows_rejects_error_and_malformed_shapes() -> None:
    with pytest.raises(
        RuntimeError, match="Samsung Innovation API error 99: 접근이 거부되었습니다"
    ):
        SamsungInnovationSource.parse_rows(
            {"resultCode": "99", "resultMessage": "접근이 거부되었습니다"}
        )

    with pytest.raises(RuntimeError, match="malformed response"):
        SamsungInnovationSource.parse_rows("not-an-object")
    with pytest.raises(RuntimeError, match="malformed response"):
        SamsungInnovationSource.parse_rows(
            {"resultCode": "00", "result": {"list": "not-a-list"}}
        )


def test_detail_parser_fails_loudly_when_schedule_structure_drifts() -> None:
    source = SamsungInnovationSource()
    html = (
        '<div class="reservationView__content">'
        '<div class="reservationView__head-category">어린이 연구소</div>'
        "</div>"
    )

    with pytest.raises(RuntimeError, match="schedule rows not found"):
        source.parse_detail_sessions(
            html,
            row={"id": "1", "showName": "어린이 연구소"},
            detail_url=source._education_detail_url("1"),
        )
