from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from kids_experience_radar.models import Event
from kids_experience_radar.normalizers import KST
from kids_experience_radar.server import create_app
from kids_experience_radar.store import EventStore


def test_read_api_health_sources_and_nearby_events(tmp_path) -> None:
    database = tmp_path / "api.sqlite3"
    now = datetime.now(KST)
    event = Event(
        source_id="official_fixture",
        source_name="공식 fixture",
        external_id="event-1",
        title="초등 가족 과학 체험",
        detail_url="https://example.org/official/event-1",
        event_start=now + timedelta(days=1),
        event_end=now + timedelta(days=1, hours=2),
        apply_end=now + timedelta(hours=12),
        status="접수중",
        age_text="초등학생",
        age_min=7,
        age_max=13,
        price_text="무료",
        price_min=0,
        venue_name="어린이과학관",
        latitude=37.5665,
        longitude=126.9780,
        child_relevance_score=1,
    )
    with EventStore(database) as store:
        store.upsert_events([event])

    client = TestClient(create_app(str(database)))
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["stats"]["events"] == 1

    sources = client.get("/sources")
    assert sources.status_code == 200
    source_ids = {row["source_id"] for row in sources.json()}
    assert len(source_ids) == 100
    assert "kopis_child_performances" in source_ids
    assert "kywa_elementary_activities" in source_ids
    assert "standard_lifelong_learning_children" in source_ids
    assert "standard_national_child_festivals" in source_ids
    assert "jeonnam_provincial_art_education" in source_ids

    response = client.get(
        "/events",
        params={
            "lat": 37.5665,
            "lon": 126.9780,
            "radius_km": 5,
            "free_only": "true",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["events"][0]["title"] == "초등 가족 과학 체험"
    assert "raw" not in payload["events"][0]
