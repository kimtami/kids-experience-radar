from __future__ import annotations

from datetime import datetime
from pathlib import Path

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.kopis import KopisChildPerformanceSource


FIXTURE = Path(__file__).parent / "fixtures" / "kopis_child_performances.xml"


class FakeClient:
    def __init__(self, xml_text: str) -> None:
        self.xml_text = xml_text
        self.calls: list[dict[str, object]] = []

    def get_text(self, url: str, *, params: dict[str, object] | None = None) -> str:
        assert url == KopisChildPerformanceSource.ENDPOINT
        assert params is not None
        self.calls.append(params)
        return self.xml_text


def test_kopis_chunks_31_day_windows_and_deduplicates(monkeypatch) -> None:
    monkeypatch.setenv("KOPIS_API_KEY", "test-key")
    source = KopisChildPerformanceSource()
    client = FakeClient(FIXTURE.read_text(encoding="utf-8"))
    window = CrawlWindow(
        start=datetime(2026, 7, 15, tzinfo=KST),
        end=datetime(2026, 8, 20, 23, 59, 59, tzinfo=KST),
        max_pages=1,
    )

    events = list(source.crawl(client, window))  # type: ignore[arg-type]

    assert len(events) == 1
    assert len(client.calls) == 2
    assert client.calls[0]["kidstate"] == "Y"
    assert client.calls[0]["stdate"] == "20260715"
    assert client.calls[0]["eddate"] == "20260814"
    event = events[0]
    assert event.external_id == "PF999001"
    assert event.title == "어린이 과학 뮤지컬"
    assert event.event_start == datetime(2026, 7, 20, tzinfo=KST)
    assert event.event_end is not None and event.event_end.hour == 23
    assert event.venue_name == "꿈빛극장"
    assert event.region == "서울특별시"
    assert event.child_relevance_score == 1
    assert "mt20Id=PF999001" in event.detail_url
