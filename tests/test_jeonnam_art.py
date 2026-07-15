from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.jeonnam_art import JeonnamProvincialArtEducationSource


FIXTURES = Path(__file__).parent / "fixtures"


class ArtClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_json(self, url: str, *, params: dict[str, object] | None = None) -> dict:
        self.calls.append(url)
        fixture = "jeonnam_art_detail.json" if url.endswith("getEduDetail") else "jeonnam_art_list.json"
        return json.loads((FIXTURES / fixture).read_text())


def test_jeonnam_art_filters_before_detail_and_maps_ranges(monkeypatch) -> None:
    monkeypatch.setenv("DATA_GO_KR_SERVICE_KEY", "test-key")
    source = JeonnamProvincialArtEducationSource()
    client = ArtClient()
    window = CrawlWindow(
        start=datetime(2026, 7, 15, tzinfo=KST),
        end=datetime(2026, 8, 31, tzinfo=KST),
        max_pages=1,
    )

    events = list(source.crawl(client, window))  # type: ignore[arg-type]

    assert len(events) == 1
    assert len(client.calls) == 2
    event = events[0]
    assert event.external_id == "EDU-2026-10"
    assert event.event_start == datetime(2026, 7, 20, tzinfo=KST)
    assert event.event_end is not None and event.event_end.date().isoformat() == "2026-08-10"
    assert event.apply_end is not None and event.apply_end.date().isoformat() == "2026-07-18"
    assert event.age_min == 9 and event.age_max == 12
    assert event.detail_url.endswith("EDU-2026-10")
