from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

from .http import PoliteHttpClient
from .models import CrawlResult, CrawlWindow
from .normalizers import KST
from .sources.base import Source
from .store import EventStore


def crawl_sources(
    sources: Iterable[Source],
    *,
    database: str | Path,
    window: CrawlWindow,
) -> list[CrawlResult]:
    results: list[CrawlResult] = []
    with PoliteHttpClient() as client, EventStore(database) as store:
        for source in sources:
            result = CrawlResult(source_id=source.info.source_id, started_at=datetime.now(KST))
            available, reason = source.available()
            if not available:
                result.error = reason
                result.finished_at = datetime.now(KST)
                store.record_run(result)
                results.append(result)
                continue
            try:
                events = list(source.crawl(client, window))
                result.fetched = len(events)
                result.stored, result.changed = store.upsert_events(events)
            except Exception as exc:
                result.error = f"{type(exc).__name__}: {exc}"
            result.finished_at = datetime.now(KST)
            store.record_run(result)
            results.append(result)
    return results
