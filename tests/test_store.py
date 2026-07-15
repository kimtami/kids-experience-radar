from datetime import datetime, timedelta

from kids_experience_radar.models import Event
from kids_experience_radar.normalizers import KST
from kids_experience_radar.store import EventStore


def make_event(source: str, external: str, title: str, lat: float, lon: float) -> Event:
    now = datetime.now(KST)
    return Event(
        source_id=source,
        source_name=source,
        external_id=external,
        title=title,
        detail_url=f"https://example.org/{external}",
        event_start=now + timedelta(days=10),
        event_end=now + timedelta(days=11),
        apply_end=now + timedelta(days=5),
        status="접수중",
        age_text="초등학생",
        age_min=7,
        age_max=13,
        price_text="무료",
        price_min=0,
        venue_name="같은 과학관",
        latitude=lat,
        longitude=lon,
        child_relevance_score=0.9,
        fetched_at=now,
    )


def test_upsert_is_stable_and_query_deduplicates(tmp_path) -> None:
    db = tmp_path / "events.sqlite3"
    first = make_event("source-a", "1", "어린이 과학 체험", 37.5665, 126.9780)
    duplicate = make_event("source-b", "2", "어린이 과학 체험", 37.5665, 126.9780)
    with EventStore(db) as store:
        assert store.upsert_events([first]) == (1, 1)
        first.fetched_at = datetime.now(KST) + timedelta(minutes=5)
        assert store.upsert_events([first]) == (1, 0)
        assert store.upsert_events([duplicate]) == (1, 1)
        rows = store.query_nearby(
            latitude=37.5665,
            longitude=126.9780,
            radius_km=5,
            free_only=True,
        )
    assert len(rows) == 1
    assert rows[0].distance_km == 0


def test_closed_event_is_excluded(tmp_path) -> None:
    event = make_event("source-a", "1", "어린이 체험", 37.5665, 126.9780)
    event.status = "접수종료"
    with EventStore(tmp_path / "events.sqlite3") as store:
        store.upsert_events([event])
        assert store.query_nearby(latitude=37.5665, longitude=126.9780, radius_km=5) == []


def test_same_day_sessions_at_different_times_are_not_deduplicated(tmp_path) -> None:
    morning = make_event("source-a", "morning", "어린이 AI 체험", 37.5665, 126.9780)
    afternoon = make_event("source-a", "afternoon", "어린이 AI 체험", 37.5665, 126.9780)
    session_day = (datetime.now(KST) + timedelta(days=10)).date()
    morning.event_start = datetime.combine(
        session_day,
        datetime.min.time(),
        tzinfo=KST,
    ).replace(hour=10)
    afternoon.event_start = morning.event_start.replace(hour=14)

    with EventStore(tmp_path / "sessions.sqlite3") as store:
        store.upsert_events([morning, afternoon])
        rows = store.query_nearby(
            latitude=37.5665,
            longitude=126.9780,
            radius_km=5,
        )

    assert {row.external_id for row in rows} == {"morning", "afternoon"}


def test_rows_missing_from_daily_snapshots_age_out_of_results(tmp_path) -> None:
    database = tmp_path / "stale.sqlite3"
    event = make_event("source-a", "stale", "어린이 생태 체험", 37.5665, 126.9780)
    with EventStore(database) as store:
        store.upsert_events([event])
        stale_at = (datetime.now(KST) - timedelta(hours=49)).isoformat()
        with store.connection:
            store.connection.execute(
                "UPDATE events SET last_seen = ? WHERE uid = ?",
                (stale_at, event.uid),
            )
        assert store.query_nearby(
            latitude=37.5665,
            longitude=126.9780,
            radius_km=5,
        ) == []
        assert len(
            store.query_nearby(
                latitude=37.5665,
                longitude=126.9780,
                radius_km=5,
                max_stale_hours=None,
            )
        ) == 1
