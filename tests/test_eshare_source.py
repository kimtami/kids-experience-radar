from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.eshare import (
    EShareEducationSource,
    EshareEducationSource,
)


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeClient:
    def __init__(self, pages: dict[int, str]) -> None:
        self.pages = pages
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get_text(self, url: str, *, params: dict[str, object] | None = None) -> str:
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


def test_available_and_crawl_require_api_key(
    monkeypatch: pytest.MonkeyPatch, window: CrawlWindow
) -> None:
    monkeypatch.delenv("ESHARE_API_KEY", raising=False)
    source = EShareEducationSource()

    assert EshareEducationSource is EShareEducationSource
    assert source.info.enabled_by_default is False
    assert source.available() == (False, "ESHARE_API_KEY is not set")
    with pytest.raises(RuntimeError, match="ESHARE_API_KEY is required"):
        list(source.crawl(FakeClient({}), window))  # type: ignore[arg-type]


def test_crawl_parses_json_and_xml_paginates_and_maps_resource_fields(
    monkeypatch: pytest.MonkeyPatch, window: CrawlWindow
) -> None:
    monkeypatch.setenv("ESHARE_API_KEY", "key/with+symbols")
    client = FakeClient(
        {
            1: load_fixture("eshare_education_page_1.json"),
            2: load_fixture("eshare_education_page_2.xml"),
        }
    )

    events = list(EShareEducationSource().crawl(client, window))  # type: ignore[arg-type]

    assert [event.external_id for event in events] == ["EDU001", "EDU002", "EDU003"]
    assert len(client.calls) == 2
    first_url, first_params = client.calls[0]
    assert first_url == (
        "https://www.eshare.go.kr/eshare-openapi/rsrc/list/040000/key%2Fwith%2Bsymbols"
    )
    assert first_params == {
        "pageNo": 1,
        "numOfRows": 100,
    }
    assert client.calls[1][1]["pageNo"] == 2

    child_event = events[0]
    assert child_event.title == "초등 가족 생태 체험 교육"
    assert child_event.detail_url == "https://booking.example.test/program/EDU001"
    assert child_event.provider_name == "서울생태교육관"
    assert child_event.category == "교육·강좌"
    assert child_event.event_start is None
    assert child_event.event_end is None
    assert child_event.age_min == 7
    assert child_event.age_max == 12
    assert child_event.price_min == 0
    assert child_event.price_text == "무료"
    assert child_event.status == "이용가능"
    assert child_event.address == "서울특별시 종로구 세종대로 1 어린이교육실"
    assert child_event.region == "서울특별시 종로구"
    assert child_event.longitude == pytest.approx(126.9784)
    assert child_event.latitude == pytest.approx(37.5666)
    assert (
        child_event.image_url == "https://www.eshare.go.kr/images/education/EDU001.jpg"
    )
    assert child_event.phone == "02-1234-5678"
    assert child_event.child_relevance_score == pytest.approx(1.0)

    assert events[1].longitude is None
    assert events[1].latitude is None
    assert events[1].price_text == "유료"
    assert "rsrc_no=EDU002" in events[1].detail_url

    assert events[2].address == "세종특별자치시 도움6로 42 문화교실 2층"
    assert events[2].region == "세종특별자치시"
    assert "rsrc_no=EDU003" in events[2].detail_url


def test_parse_rows_accepts_bare_single_resource_and_rejects_api_errors() -> None:
    rows, total = EShareEducationSource.parse_rows(
        '{"rsrcNo":"ONE","rsrcNm":"어린이 강좌","addr":"서울특별시 중구"}'
    )
    assert [row["rsrcNo"] for row in rows] == ["ONE"]
    assert total is None

    with pytest.raises(RuntimeError, match="EShare API error 401: invalid key"):
        EShareEducationSource.parse_rows(
            '{"response":{"header":{"resultCode":"401","resultMsg":"invalid key"}}}'
        )


@pytest.mark.parametrize(
    "payload",
    ["", "not-json-or-xml", "<response>", "<html><body>denied</body></html>"],
)
def test_parse_rows_rejects_empty_unknown_and_malformed_payloads(payload: str) -> None:
    with pytest.raises(RuntimeError, match="EShare API"):
        EShareEducationSource.parse_rows(payload)
