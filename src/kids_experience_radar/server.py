from __future__ import annotations

from datetime import datetime, timedelta
import os

from fastapi import FastAPI, Query

from .normalizers import KST
from .registry import builtin_sources
from .store import EventStore


def create_app(database: str | None = None) -> FastAPI:
    database = database or os.getenv("KIDS_RADAR_DB", "data/radar.sqlite3")
    app = FastAPI(title="Kids Experience Radar", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, object]:
        with EventStore(database) as store:
            return {"ok": True, "stats": store.stats()}

    @app.get("/sources")
    def sources() -> list[dict[str, object]]:
        result = []
        for source in builtin_sources():
            available, reason = source.available()
            row = source.info.to_dict()
            row.update({"available": available, "unavailable_reason": reason})
            result.append(row)
        return result

    @app.get("/events")
    def events(
        lat: float = Query(ge=-90, le=90),
        lon: float = Query(ge=-180, le=180),
        radius_km: float = Query(20, gt=0, le=300),
        child_score_min: float = Query(0.35, ge=0, le=1),
        free_only: bool = False,
        include_unknown_location: bool = False,
        include_closed: bool = False,
        new_within_hours: int | None = Query(None, ge=1, le=720),
        max_stale_hours: int = Query(48, ge=1, le=720),
        limit: int = Query(100, ge=1, le=500),
    ) -> dict[str, object]:
        discovered_since = (
            datetime.now(KST) - timedelta(hours=new_within_hours) if new_within_hours is not None else None
        )
        with EventStore(database) as store:
            rows = store.query_nearby(
                latitude=lat,
                longitude=lon,
                radius_km=radius_km,
                child_score_min=child_score_min,
                free_only=free_only,
                include_unknown_location=include_unknown_location,
                include_closed=include_closed,
                discovered_since=discovered_since,
                max_stale_hours=max_stale_hours,
                limit=limit,
            )
        return {"count": len(rows), "events": [event.to_dict(include_raw=False) for event in rows]}

    return app


app = create_app()
