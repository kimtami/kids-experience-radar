from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
import sqlite3
from typing import Iterable

from .models import CrawlResult, Event
from .normalizers import KST, haversine_km, parse_datetime


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS events (
    uid TEXT PRIMARY KEY,
    canonical_key TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_name TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    detail_url TEXT NOT NULL,
    provider_name TEXT,
    category TEXT,
    description TEXT,
    event_start TEXT,
    event_end TEXT,
    apply_start TEXT,
    apply_end TEXT,
    status TEXT,
    age_text TEXT,
    age_min INTEGER,
    age_max INTEGER,
    price_text TEXT,
    price_min INTEGER,
    currency TEXT NOT NULL DEFAULT 'KRW',
    venue_name TEXT,
    address TEXT,
    region TEXT,
    latitude REAL,
    longitude REAL,
    image_url TEXT,
    phone TEXT,
    is_online INTEGER NOT NULL DEFAULT 0,
    child_relevance_score REAL NOT NULL DEFAULT 0,
    license_code TEXT,
    fetched_at TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    UNIQUE(source_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_events_window ON events(event_start, event_end);
CREATE INDEX IF NOT EXISTS idx_events_location ON events(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_events_canonical ON events(canonical_key);
CREATE INDEX IF NOT EXISTS idx_events_first_seen ON events(first_seen);

CREATE TABLE IF NOT EXISTS crawl_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    fetched INTEGER NOT NULL DEFAULT 0,
    stored INTEGER NOT NULL DEFAULT 0,
    changed INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    error TEXT
);

CREATE TABLE IF NOT EXISTS geocoding_cache (
    provider TEXT NOT NULL,
    query_address TEXT NOT NULL,
    matched_address TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    precision TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY(provider, query_address)
);
"""


EVENT_COLUMNS = (
    "source_id",
    "source_name",
    "external_id",
    "title",
    "detail_url",
    "provider_name",
    "category",
    "description",
    "event_start",
    "event_end",
    "apply_start",
    "apply_end",
    "status",
    "age_text",
    "age_min",
    "age_max",
    "price_text",
    "price_min",
    "currency",
    "venue_name",
    "address",
    "region",
    "latitude",
    "longitude",
    "image_url",
    "phone",
    "is_online",
    "child_relevance_score",
    "license_code",
    "fetched_at",
)


class EventStore:
    def __init__(self, path: str | Path, *, read_only: bool = False) -> None:
        self.path = Path(path)
        self.read_only = read_only
        if read_only:
            if not self.path.is_file():
                raise FileNotFoundError(f"event database does not exist: {self.path}")
            uri = f"{self.path.resolve().as_uri()}?mode=ro"
            self.connection = sqlite3.connect(uri, uri=True)
            self.connection.execute("PRAGMA query_only=ON")
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        if not read_only:
            self.connection.executescript(SCHEMA)

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "EventStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def upsert_events(self, events: Iterable[Event]) -> tuple[int, int]:
        stored = 0
        changed = 0
        now = datetime.now(KST).isoformat()
        sql = """
        INSERT INTO events (
            uid, canonical_key, source_id, source_name, external_id, title, detail_url,
            provider_name, category, description, event_start, event_end, apply_start,
            apply_end, status, age_text, age_min, age_max, price_text, price_min,
            currency, venue_name, address, region, latitude, longitude, image_url, phone,
            is_online, child_relevance_score, license_code, fetched_at, first_seen,
            last_seen, content_hash, raw_json
        ) VALUES (
            :uid, :canonical_key, :source_id, :source_name, :external_id, :title, :detail_url,
            :provider_name, :category, :description, :event_start, :event_end, :apply_start,
            :apply_end, :status, :age_text, :age_min, :age_max, :price_text, :price_min,
            :currency, :venue_name, :address, :region, :latitude, :longitude, :image_url, :phone,
            :is_online, :child_relevance_score, :license_code, :fetched_at, :first_seen,
            :last_seen, :content_hash, :raw_json
        )
        ON CONFLICT(uid) DO UPDATE SET
            canonical_key=excluded.canonical_key,
            source_name=excluded.source_name,
            title=excluded.title,
            detail_url=excluded.detail_url,
            provider_name=excluded.provider_name,
            category=excluded.category,
            description=excluded.description,
            event_start=excluded.event_start,
            event_end=excluded.event_end,
            apply_start=excluded.apply_start,
            apply_end=excluded.apply_end,
            status=excluded.status,
            age_text=excluded.age_text,
            age_min=excluded.age_min,
            age_max=excluded.age_max,
            price_text=excluded.price_text,
            price_min=excluded.price_min,
            currency=excluded.currency,
            venue_name=excluded.venue_name,
            address=excluded.address,
            region=excluded.region,
            latitude=COALESCE(excluded.latitude, events.latitude),
            longitude=COALESCE(excluded.longitude, events.longitude),
            image_url=excluded.image_url,
            phone=excluded.phone,
            is_online=excluded.is_online,
            child_relevance_score=excluded.child_relevance_score,
            license_code=excluded.license_code,
            fetched_at=excluded.fetched_at,
            last_seen=excluded.last_seen,
            content_hash=excluded.content_hash,
            raw_json=excluded.raw_json
        """
        with self.connection:
            for event in events:
                existing = self.connection.execute(
                    "SELECT content_hash FROM events WHERE uid = ?", (event.uid,)
                ).fetchone()
                content_hash = event.content_hash
                if existing is None or existing["content_hash"] != content_hash:
                    changed += 1
                data = event.to_dict(include_raw=False)
                data.update(
                    {
                        "uid": event.uid,
                        "canonical_key": event.canonical_key,
                        "is_online": int(event.is_online),
                        "first_seen": now,
                        "last_seen": now,
                        "content_hash": content_hash,
                        "raw_json": json.dumps(event.raw, ensure_ascii=False, default=str),
                    }
                )
                self.connection.execute(sql, data)
                stored += 1
        return stored, changed

    def record_run(self, result: CrawlResult) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO crawl_runs (
                    source_id, started_at, finished_at, fetched, stored, changed, skipped, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.source_id,
                    result.started_at.isoformat() if result.started_at else datetime.now(KST).isoformat(),
                    result.finished_at.isoformat() if result.finished_at else None,
                    result.fetched,
                    result.stored,
                    result.changed,
                    result.skipped,
                    result.error,
                ),
            )

    def missing_addresses(self, *, limit: int = 100) -> list[str]:
        rows = self.connection.execute(
            """
            SELECT address, COUNT(*) AS n
            FROM events
            WHERE latitude IS NULL AND longitude IS NULL
              AND address IS NOT NULL AND TRIM(address) <> ''
              AND is_online = 0
            GROUP BY address
            ORDER BY n DESC, address ASC
            LIMIT ?
            """,
            (max(1, limit),),
        ).fetchall()
        return [str(row["address"]) for row in rows]

    def cached_geocode(self, provider: str, query_address: str) -> dict[str, object] | None:
        row = self.connection.execute(
            """
            SELECT provider, query_address, matched_address, latitude, longitude,
                   precision, fetched_at
            FROM geocoding_cache
            WHERE provider = ? AND query_address = ?
            """,
            (provider, query_address),
        ).fetchone()
        return dict(row) if row else None

    def apply_geocode(
        self,
        *,
        provider: str,
        query_address: str,
        matched_address: str,
        latitude: float,
        longitude: float,
        precision: str,
    ) -> int:
        now = datetime.now(KST).isoformat()
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO geocoding_cache (
                    provider, query_address, matched_address, latitude, longitude,
                    precision, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider, query_address) DO UPDATE SET
                    matched_address=excluded.matched_address,
                    latitude=excluded.latitude,
                    longitude=excluded.longitude,
                    precision=excluded.precision,
                    fetched_at=excluded.fetched_at
                """,
                (
                    provider,
                    query_address,
                    matched_address,
                    latitude,
                    longitude,
                    precision,
                    now,
                ),
            )
            cursor = self.connection.execute(
                """
                UPDATE events
                SET latitude = ?, longitude = ?
                WHERE address = ? AND latitude IS NULL AND longitude IS NULL
                """,
                (latitude, longitude, query_address),
            )
        return cursor.rowcount

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> Event:
        values: dict[str, object] = {column: row[column] for column in EVENT_COLUMNS}
        for key in ("event_start", "event_end", "apply_start", "apply_end", "fetched_at"):
            values[key] = parse_datetime(values[key])
        values["is_online"] = bool(values["is_online"])
        values["raw"] = json.loads(row["raw_json"] or "{}")
        return Event(**values)  # type: ignore[arg-type]

    def query_nearby(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_km: float,
        child_score_min: float = 0.35,
        free_only: bool = False,
        include_unknown_location: bool = False,
        include_closed: bool = False,
        discovered_since: datetime | None = None,
        max_stale_hours: int | None = 48,
        limit: int = 100,
    ) -> list[Event]:
        now = datetime.now(KST)
        clauses = ["(event_end IS NULL OR event_end >= ?)", "child_relevance_score >= ?"]
        params: list[object] = [now.isoformat(), child_score_min]
        if max_stale_hours is not None:
            stale_cutoff = now - timedelta(hours=max(1, max_stale_hours))
            clauses.append("last_seen >= ?")
            params.append(stale_cutoff.isoformat())
        if free_only:
            clauses.append("price_min = 0")
        if discovered_since:
            clauses.append("first_seen >= ?")
            params.append(discovered_since.isoformat())
        rows = self.connection.execute(
            f"SELECT * FROM events WHERE {' AND '.join(clauses)} ORDER BY event_start ASC, first_seen DESC",
            params,
        ).fetchall()
        chosen: dict[str, Event] = {}
        closed_tokens = ("접수종료", "마감", "예약마감", "종료")
        for row in rows:
            event = self._event_from_row(row)
            if child_score_min > 0:
                target_text = f"{event.title} {event.age_text or ''}".casefold()
                elementary_tokens = ("초등", "어린이", "아동", "가족", "키즈")
                non_elementary_tokens = ("중학생", "고등학생", "대학생", "성인", "55세 이상")
                if any(token in target_text for token in non_elementary_tokens) and not any(
                    token in target_text for token in elementary_tokens
                ):
                    continue
                if event.age_min is not None and event.age_min >= 14:
                    continue
            if not include_closed:
                if event.apply_end and event.apply_end < now:
                    continue
                if event.status and any(token in event.status.replace(" ", "") for token in closed_tokens):
                    continue
            if event.latitude is None or event.longitude is None:
                if not include_unknown_location and not event.is_online:
                    continue
            else:
                event.distance_km = haversine_km(latitude, longitude, event.latitude, event.longitude)
                if event.distance_km > radius_km:
                    continue
            current = chosen.get(event.canonical_key)
            if current is None or event.child_relevance_score > current.child_relevance_score:
                chosen[event.canonical_key] = event
        result = list(chosen.values())
        result.sort(
            key=lambda event: (
                event.distance_km is None,
                event.distance_km if event.distance_km is not None else float("inf"),
                event.event_start or datetime.max.replace(tzinfo=KST),
            )
        )
        return result[:limit]

    def get_event(self, uid: str) -> Event | None:
        row = self.connection.execute(
            "SELECT * FROM events WHERE uid = ?",
            (uid,),
        ).fetchone()
        return self._event_from_row(row) if row is not None else None

    def stats(self) -> dict[str, object]:
        total = self.connection.execute("SELECT COUNT(*) AS n FROM events").fetchone()["n"]
        by_source = {
            row["source_id"]: row["n"]
            for row in self.connection.execute(
                "SELECT source_id, COUNT(*) AS n FROM events GROUP BY source_id ORDER BY source_id"
            )
        }
        last_runs = [
            dict(row)
            for row in self.connection.execute(
                """
                SELECT source_id, finished_at, fetched, stored, changed, error
                FROM crawl_runs
                WHERE id IN (SELECT MAX(id) FROM crawl_runs GROUP BY source_id)
                ORDER BY source_id
                """
            )
        ]
        return {"events": total, "by_source": by_source, "last_runs": last_runs}
