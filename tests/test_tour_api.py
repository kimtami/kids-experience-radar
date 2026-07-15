from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.tour_api import TourApiFestivalSource


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeClient:
    def __init__(self, pages: dict[int, dict[str, Any]]) -> None:
        self.pages = pages
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get_json(self, url: str, *, params: dict[str, object] | None = None) -> dict[str, Any]:
        assert params is not None
        self.calls.append((url, params))
        return self.pages[int(params["pageNo"])]


@pytest.fixture
def window() -> CrawlWindow:
    return CrawlWindow(
        start=datetime(2026, 7, 15, tzinfo=KST),
        end=datetime(2026, 8, 2, 23, 59, 59, tzinfo=KST),
        max_pages=3,
    )


def test_available_and_crawl_require_service_key(monkeypatch: pytest.MonkeyPatch, window: CrawlWindow) -> None:
    monkeypatch.delenv("DATA_GO_KR_SERVICE_KEY", raising=False)
    source = TourApiFestivalSource()

    assert source.available() == (False, "DATA_GO_KR_SERVICE_KEY is not set")
    with pytest.raises(RuntimeError, match="DATA_GO_KR_SERVICE_KEY is required"):
        list(source.crawl(FakeClient({}), window))  # type: ignore[arg-type]


def test_crawl_paginates_maps_fields_and_accepts_single_item(
    monkeypatch: pytest.MonkeyPatch, window: CrawlWindow
) -> None:
    monkeypatch.setenv("DATA_GO_KR_SERVICE_KEY", "encoded%2Bkey")
    monkeypatch.setattr(TourApiFestivalSource, "PAGE_SIZE", 2)
    client = FakeClient(
        {
            1: load_fixture("tour_api_festivals_page_1.json"),
            2: load_fixture("tour_api_festivals_page_2_single.json"),
        }
    )

    events = list(TourApiFestivalSource().crawl(client, window))  # type: ignore[arg-type]

    assert [event.external_id for event in events] == ["101", "102", "103"]
    assert len(client.calls) == 2
    first_url, first_params = client.calls[0]
    assert first_url == "https://apis.data.go.kr/B551011/KorService2/searchFestival2"
    assert first_params == {
        "serviceKey": "encoded+key",
        "MobileOS": "ETC",
        "MobileApp": "KidsExperienceRadar",
        "_type": "json",
        "eventStartDate": "20260715",
        "eventEndDate": "20260802",
        "numOfRows": 2,
        "pageNo": 1,
    }
    assert client.calls[1][1]["pageNo"] == 2

    child_event = events[0]
    assert child_event.title == "어린이 과학 체험 축제"
    assert child_event.event_start == datetime(2026, 7, 18, tzinfo=KST)
    assert child_event.event_end is not None
    assert child_event.event_end.date().isoformat() == "2026-07-19"
    assert child_event.event_end.hour == 23
    assert child_event.address == "서울특별시 종로구 세종대로 1"
    assert child_event.region == "서울특별시"
    assert child_event.longitude == pytest.approx(126.9784)
    assert child_event.latitude == pytest.approx(37.5666)
    assert child_event.image_url == "https://example.test/images/101.jpg"
    assert child_event.phone == "02-1234-5678"
    assert child_event.child_relevance_score == pytest.approx(0.65)
    assert "fes_detail.do" not in child_event.detail_url
    detail = urlparse(child_event.detail_url)
    assert detail.netloc == "korean.visitkorea.or.kr"
    assert parse_qs(detail.query)["keyword"] == ["어린이 과학 체험 축제"]

    assert events[1].longitude is None
    assert events[1].latitude is None


def test_parse_page_rejects_api_errors_and_defends_empty_shapes() -> None:
    with pytest.raises(RuntimeError, match="TourAPI error 30: SERVICE KEY IS NOT REGISTERED ERROR"):
        TourApiFestivalSource.parse_page(load_fixture("tour_api_error.json"))

    assert TourApiFestivalSource.parse_page({"response": {"header": {"resultCode": "0000"}}}) == ([], 0)
    assert TourApiFestivalSource.parse_page(
        {
            "response": {
                "header": {"resultCode": "0000", "resultMsg": "OK"},
                "body": {"items": {"item": [None, "bad-item"]}, "totalCount": "bad-total"},
            }
        }
    ) == ([], 0)


def test_parse_page_rejects_non_object_payload() -> None:
    with pytest.raises(RuntimeError, match="malformed response"):
        TourApiFestivalSource.parse_page([])  # type: ignore[arg-type]
