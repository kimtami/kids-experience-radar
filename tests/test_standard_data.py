from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.standard_data import (
    LifelongLearningCourseSource,
    NationalCultureFestivalSource,
)


FIXTURES = Path(__file__).parent / "fixtures"


class JsonClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.params: dict[str, object] | None = None

    def get_json(self, url: str, *, params: dict[str, object] | None = None) -> dict:
        self.params = params
        return self.payload


def window() -> CrawlWindow:
    return CrawlWindow(
        start=datetime(2026, 7, 1, tzinfo=KST),
        end=datetime(2026, 8, 31, 23, 59, tzinfo=KST),
        max_pages=1,
    )


def test_lifelong_learning_keeps_only_explicit_child_courses(monkeypatch) -> None:
    monkeypatch.setenv("DATA_GO_KR_SERVICE_KEY", "test-key")
    payload = json.loads((FIXTURES / "standard_lifelong_learning.json").read_text())
    client = JsonClient(payload)

    events = list(LifelongLearningCourseSource().crawl(client, window()))  # type: ignore[arg-type]

    assert len(events) == 1
    event = events[0]
    assert event.title == "시간여행 한국사 교실"
    assert event.age_min == 9 and event.age_max == 12
    assert event.price_min == 0
    assert event.region == "경상남도 창원시"
    assert event.detail_url == "https://jhlib.gne.go.kr"
    assert client.params is not None and client.params["numOfRows"] == 1000


def test_national_festivals_keep_experience_rows_and_coordinates(monkeypatch) -> None:
    monkeypatch.setenv("DATA_GO_KR_SERVICE_KEY", "test-key")
    payload = json.loads((FIXTURES / "standard_culture_festivals.json").read_text())
    client = JsonClient(payload)

    events = list(NationalCultureFestivalSource().crawl(client, window()))  # type: ignore[arg-type]

    assert len(events) == 1
    event = events[0]
    assert event.title == "어린이 과학축제"
    assert event.latitude == 37.57 and event.longitude == 126.9769
    assert event.region == "서울특별시 종로구"
    assert event.child_relevance_score >= 0.8
