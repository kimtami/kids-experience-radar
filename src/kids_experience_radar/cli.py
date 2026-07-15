from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sys

from .engine import crawl_sources
from .digest import render_json, render_markdown, send_webhook
from .geocoding import KakaoAddressGeocoder
from .http import PoliteHttpClient
from .models import CrawlWindow
from .normalizers import KST, parse_datetime
from .registry import builtin_sources, source_map
from .store import EventStore
from .tips import load_tip_events


def load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _datetime_arg(value: str, *, end: bool = False) -> datetime:
    parsed = parse_datetime(value, end_of_day=end)
    if parsed is None:
        raise argparse.ArgumentTypeError(f"invalid date/datetime: {value}")
    return parsed


def _json_dump(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kidradar", description="Daily nearby children's experience crawler")
    parser.add_argument("--env-file", default=".env")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sources", help="List source policy and key requirements")
    sub.add_parser("doctor", help="Check which connectors are currently runnable")

    crawl = sub.add_parser("crawl", help="Fetch and upsert source events")
    crawl.add_argument("--source", action="append", dest="source_ids")
    crawl.add_argument("--all", action="store_true", help="Include non-default/static connectors")
    crawl.add_argument("--db", default=os.getenv("KIDS_RADAR_DB", "data/radar.sqlite3"))
    crawl.add_argument("--from", dest="start", default=datetime.now(KST).date().isoformat())
    crawl.add_argument("--to", dest="end", default=(datetime.now(KST) + timedelta(days=120)).date().isoformat())
    crawl.add_argument("--max-pages", type=int, default=5)
    crawl.add_argument("--html-config")

    nearby = sub.add_parser("nearby", help="Return deduplicated upcoming events around a point")
    nearby.add_argument("--db", default=os.getenv("KIDS_RADAR_DB", "data/radar.sqlite3"))
    nearby.add_argument("--lat", type=float, required=True)
    nearby.add_argument("--lon", type=float, required=True)
    nearby.add_argument("--radius-km", type=float, default=20)
    nearby.add_argument("--child-score-min", type=float, default=0.35)
    nearby.add_argument("--free-only", action="store_true")
    nearby.add_argument("--include-unknown-location", action="store_true")
    nearby.add_argument("--include-closed", action="store_true")
    nearby.add_argument(
        "--max-stale-hours",
        type=int,
        default=48,
        help="Hide rows not seen in a successful source result within this many hours",
    )
    nearby.add_argument("--new-within-hours", type=int)
    nearby.add_argument("--limit", type=int, default=100)

    tips = sub.add_parser("import-tips", help="Import official organizer URLs shared by users")
    tips.add_argument("path")
    tips.add_argument("--db", default=os.getenv("KIDS_RADAR_DB", "data/radar.sqlite3"))

    stats = sub.add_parser("stats", help="Show database counts and last runs")
    stats.add_argument("--db", default=os.getenv("KIDS_RADAR_DB", "data/radar.sqlite3"))

    geocode = sub.add_parser("geocode", help="Geocode missing public venue addresses")
    geocode.add_argument("--db", default=os.getenv("KIDS_RADAR_DB", "data/radar.sqlite3"))
    geocode.add_argument("--limit", type=int, default=100)

    digest = sub.add_parser("digest", help="Create a daily nearby digest and optionally POST a webhook")
    digest.add_argument("--db", default=os.getenv("KIDS_RADAR_DB", "data/radar.sqlite3"))
    digest.add_argument("--lat", type=float, required=True)
    digest.add_argument("--lon", type=float, required=True)
    digest.add_argument("--radius-km", type=float, default=20)
    digest.add_argument("--child-score-min", type=float, default=0.35)
    digest.add_argument("--free-only", action="store_true")
    digest.add_argument("--include-unknown-location", action="store_true")
    digest.add_argument("--max-stale-hours", type=int, default=48)
    digest.add_argument("--new-within-hours", type=int, default=26)
    digest.add_argument("--limit", type=int, default=50)
    digest.add_argument("--format", choices=("markdown", "json"), default="markdown")
    digest.add_argument("--output")
    digest.add_argument("--webhook-url", default=os.getenv("KIDS_RADAR_WEBHOOK_URL"))

    serve = sub.add_parser("serve", help="Start the nearby read API")
    serve.add_argument("--db", default=os.getenv("KIDS_RADAR_DB", "data/radar.sqlite3"))
    serve.add_argument("--host", default=os.getenv("KIDS_RADAR_HOST", "127.0.0.1"))
    serve.add_argument("--port", type=int, default=int(os.getenv("KIDS_RADAR_PORT", "8080")))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    load_dotenv(args.env_file)

    if args.command in {"sources", "doctor"}:
        rows = []
        for source in builtin_sources():
            available, reason = source.available()
            row = source.info.to_dict()
            row.update({"available": available, "unavailable_reason": reason})
            rows.append(row)
        _json_dump(rows)
        return 0 if args.command == "sources" or all(row["available"] for row in rows if row["enabled_by_default"]) else 2

    if args.command == "crawl":
        sources_by_id = source_map(html_config=args.html_config)
        if args.source_ids:
            unknown = sorted(set(args.source_ids) - set(sources_by_id))
            if unknown:
                parser.error(f"unknown source(s): {', '.join(unknown)}")
            selected = [sources_by_id[source_id] for source_id in args.source_ids]
        elif args.all:
            selected = list(sources_by_id.values())
        else:
            selected = [source for source in sources_by_id.values() if source.info.enabled_by_default]
        start = _datetime_arg(args.start)
        end = _datetime_arg(args.end, end=True)
        if end < start:
            parser.error("--to must be on or after --from")
        results = crawl_sources(
            selected,
            database=args.db,
            window=CrawlWindow(start=start, end=end, max_pages=max(1, args.max_pages)),
        )
        _json_dump([result.to_dict() for result in results])
        return 1 if any(result.error for result in results) else 0

    if args.command == "nearby":
        discovered_since = (
            datetime.now(KST) - timedelta(hours=args.new_within_hours) if args.new_within_hours else None
        )
        with EventStore(args.db) as store:
            events = store.query_nearby(
                latitude=args.lat,
                longitude=args.lon,
                radius_km=args.radius_km,
                child_score_min=args.child_score_min,
                free_only=args.free_only,
                include_unknown_location=args.include_unknown_location,
                include_closed=args.include_closed,
                discovered_since=discovered_since,
                max_stale_hours=max(1, args.max_stale_hours),
                limit=args.limit,
            )
        _json_dump({"count": len(events), "events": [event.to_dict(include_raw=False) for event in events]})
        return 0

    if args.command == "import-tips":
        events, errors = load_tip_events(args.path)
        with EventStore(args.db) as store:
            stored, changed = store.upsert_events(events)
        _json_dump({"read": len(events) + len(errors), "stored": stored, "changed": changed, "errors": errors})
        return 1 if errors else 0

    if args.command == "stats":
        with EventStore(args.db) as store:
            _json_dump(store.stats())
        return 0

    if args.command == "geocode":
        geocoder = KakaoAddressGeocoder()
        available, reason = geocoder.available()
        if not available:
            _json_dump({"error": reason})
            return 2
        requested = matched = updated = 0
        with PoliteHttpClient() as client, EventStore(args.db) as store:
            addresses = store.missing_addresses(limit=args.limit)
            for address in addresses:
                requested += 1
                cached = store.cached_geocode(geocoder.provider, address)
                if cached:
                    result = cached
                else:
                    fresh = geocoder.geocode(client, address)
                    if fresh is None:
                        continue
                    result = {
                        "provider": fresh.provider,
                        "query_address": fresh.query_address,
                        "matched_address": fresh.matched_address,
                        "latitude": fresh.latitude,
                        "longitude": fresh.longitude,
                        "precision": fresh.precision,
                    }
                matched += 1
                updated += store.apply_geocode(
                    provider=str(result["provider"]),
                    query_address=str(result["query_address"]),
                    matched_address=str(result["matched_address"]),
                    latitude=float(result["latitude"]),
                    longitude=float(result["longitude"]),
                    precision=str(result["precision"]),
                )
        _json_dump({"requested": requested, "matched": matched, "events_updated": updated})
        return 0

    if args.command == "digest":
        discovered_since = datetime.now(KST) - timedelta(hours=args.new_within_hours)
        with EventStore(args.db) as store:
            events = store.query_nearby(
                latitude=args.lat,
                longitude=args.lon,
                radius_km=args.radius_km,
                child_score_min=args.child_score_min,
                free_only=args.free_only,
                include_unknown_location=args.include_unknown_location,
                discovered_since=discovered_since,
                max_stale_hours=max(1, args.max_stale_hours),
                limit=args.limit,
            )
        body = render_markdown(events) if args.format == "markdown" else render_json(events)
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(body, encoding="utf-8")
        else:
            print(body, end="" if body.endswith("\n") else "\n")
        if args.webhook_url and events:
            send_webhook(args.webhook_url, events)
        return 0

    if args.command == "serve":
        os.environ["KIDS_RADAR_DB"] = args.db
        import uvicorn

        uvicorn.run("kids_experience_radar.server:app", host=args.host, port=args.port, reload=False)
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
