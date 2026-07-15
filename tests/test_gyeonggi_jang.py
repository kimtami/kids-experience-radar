from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pytest

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.gyeonggi_jang import GyeonggiJangProgramSource


FIXTURES = Path(__file__).parent / "fixtures"


def api_fixture() -> dict[str, dict[str, Any]]:
    return json.loads(
        (FIXTURES / "gyeonggi_jang_api.json").read_text(encoding="utf-8")
    )


def detail_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeClient:
    def __init__(self) -> None:
        self.payloads = api_fixture()
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def assert_html_allowed(self, url: str) -> None:
        self.calls.append(("robots", url, None))

    def get_json(
        self, url: str, *, params: dict[str, object] | None = None
    ) -> dict[str, Any]:
        self.calls.append(("json", url, params))
        kind = "events" if url.endswith("/events") else "edus"
        return self.payloads[kind]

    def get_text(self, url: str, *, params: dict[str, object] | None = None) -> str:
        self.calls.append(("html", url, params))
        if url.endswith("/events/321"):
            return detail_fixture("gyeonggi_jang_event_detail.html")
        if url.endswith("/edus/600"):
            return detail_fixture("gyeonggi_jang_edu_detail.html")
        raise AssertionError(f"unexpected detail URL: {url}")


@pytest.fixture
def window() -> CrawlWindow:
    return CrawlWindow(
        start=datetime(2026, 7, 15, tzinfo=KST),
        end=datetime(2026, 8, 31, 23, 59, 59, tzinfo=KST),
    )


def test_crawl_collects_public_event_and_education_details_without_reservation_calls(
    window: CrawlWindow,
) -> None:
    source = GyeonggiJangProgramSource()
    client = FakeClient()

    events = list(source.crawl(client, window))  # type: ignore[arg-type]

    assert source.info.source_id == "ggcf_gyeonggi_jang_programs"
    assert source.info.owner == "경기문화재단"
    assert source.info.policy_status == "reviewed_public_json_html"
    assert source.info.enabled_by_default is False
    assert source.available() == (True, None)
    assert [event.external_id for event in events] == ["events:321", "edus:600"]

    first = events[0]
    assert first.title == "매머드 발자국을 찾아라! 비누 속 고대동물 탐험"
    assert first.detail_url == "https://ggcf.kr/events/321"
    assert first.provider_name == "경기문화재단"
    assert first.category == "문화·교육·체험"
    # The public body publishes 7/12 while the structured list says 7/14.
    # Preserve the structured period in raw and use the explicit session line.
    assert first.event_start == datetime(2026, 7, 12, tzinfo=KST)
    assert first.event_end is not None and first.event_end.hour == 23
    assert first.apply_start == datetime(2026, 6, 28, tzinfo=KST)
    assert first.apply_end is not None and first.apply_end.hour == 23
    assert first.status == "진행중"
    assert first.age_text == "만 5세 이상 누구나"
    assert first.age_min == 5
    assert first.price_text == "무료" and first.price_min == 0
    assert first.venue_name == "경기도 컬처라운지 경기, 장"
    assert first.address == "경기도 수원시 영통구 도청로 36 지하(경기융합타운)"
    assert first.region == "경기도 수원시"
    assert first.image_url is None
    assert "석고 화석볼" in (first.description or "")
    assert first.raw == {
        "api_id": "1377",
        "content_type": "events",
        "affiliation_code": "01",
        "affiliation_name": "경기문화재단",
        "status": "진행중",
        "event_period": "2026-07-14(화) ~ 2026-07-26(일)",
        "application_period": "2026-06-28(일) ~ 2026-07-25(토)",
        "published_schedule": (
            "- 운영일정 : 2026. 7. 12.(일) 14:00, 15:30 / "
            "2026. 7. 26.(일) 14:00, 15:30"
        ),
        "audience": "만 5세 이상 누구나",
        "place": "경기도 컬처라운지 경기, 장",
        "price": "무료",
    }
    assert "fileUrl" not in first.raw
    assert "internal_editor_id" not in first.raw

    second = events[1]
    assert second.age_min == 9 and second.age_max == 12
    assert second.price_text == "재료비 5,000원"
    assert second.price_min == 5_000

    called_urls = [url for _, url, _ in client.calls]
    assert not any("booking.naver.com" in url for url in called_urls)
    assert not any("reserve" in url.casefold() for url in called_urls)
    assert client.calls == [
        ("robots", source.API_URLS["events"], None),
        (
            "json",
            source.API_URLS["events"],
            {"progress": "soon", "limit": 100, "page": 1},
        ),
        ("robots", "https://ggcf.kr/events/321", None),
        ("html", "https://ggcf.kr/events/321", None),
        ("robots", source.API_URLS["edus"], None),
        (
            "json",
            source.API_URLS["edus"],
            {"progress": "soon", "limit": 100, "page": 1},
        ),
        ("robots", "https://ggcf.kr/edus/600", None),
        ("html", "https://ggcf.kr/edus/600", None),
    ]


def test_parse_api_page_filters_exact_space_and_rejects_stadium_false_positive() -> None:
    rows, last_page = GyeonggiJangProgramSource.parse_api_page(
        api_fixture()["events"]
    )

    assert last_page == 1
    assert [row["href"] for row in rows] == ["https://ggcf.kr/events/321"]


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"current_page": 1, "last_page": 1},
        {"current_page": 1, "last_page": 1, "list": "bad"},
        {"current_page": 1, "last_page": 0, "list": []},
    ],
)
def test_parse_api_page_fails_loudly_on_malformed_payload(payload: object) -> None:
    with pytest.raises(RuntimeError, match="GGCF API malformed response"):
        GyeonggiJangProgramSource.parse_api_page(payload)


def test_parse_detail_fails_loudly_when_public_fact_structure_changes() -> None:
    with pytest.raises(RuntimeError, match="GGCF detail structure changed"):
        GyeonggiJangProgramSource.parse_detail("<html><body>empty</body></html>")
