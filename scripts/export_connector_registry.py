#!/usr/bin/env python3
"""Export the executable connector registry without making network requests."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kids_experience_radar.registry import builtin_sources  # noqa: E402


def main() -> None:
    rows: list[dict[str, object]] = []
    for source in builtin_sources():
        row = source.info.to_dict()
        row["key_gated"] = bool(source.info.requires_key)
        row["operational_mode"] = (
            "default"
            if source.info.enabled_by_default
            else "explicit_opt_in"
            if not source.info.requires_key
            else "key_and_explicit_opt_in"
        )
        rows.append(row)

    json_path = ROOT / "docs" / "CONNECTOR_REGISTRY.json"
    csv_path = ROOT / "docs" / "CONNECTOR_REGISTRY.csv"
    json_path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"connectors": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
