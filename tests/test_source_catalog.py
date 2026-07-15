from __future__ import annotations

import csv
import json
import plistlib
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]


def test_generated_source_catalog_matches_verified_research_inventory() -> None:
    with (ROOT / "docs" / "SOURCE_CATALOG.csv").open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 234
    assert Counter(row["group"] for row in rows) == {
        "regional_portals": 60,
        "public_institutions": 90,
        "private_brands": 84,
    }
    assert all(row["priority"] in {"P0", "P1", "P2", "P3"} for row in rows)
    assert all(row["verified_at"] == "2026-07-15" for row in rows)
    assert all(urlparse(row["official_url"]).scheme == "https" for row in rows)
    implemented = [row for row in rows if row["connector_id"]]
    assert len(implemented) == 70
    assert len({row["connector_id"] for row in implemented}) == 69

    json_rows = json.loads((ROOT / "docs" / "SOURCE_CATALOG.json").read_text())
    assert [row["catalog_id"] for row in json_rows] == [
        row["catalog_id"] for row in rows
    ]


def test_private_source_policy_counts_are_explicit() -> None:
    with (ROOT / "docs" / "SOURCE_CATALOG.csv").open(encoding="utf-8-sig") as handle:
        private_rows = [
            row for row in csv.DictReader(handle) if row["group"] == "private_brands"
        ]

    decisions = Counter(row["recommendation"].split(" · ", 1)[0] for row in private_rows)
    assert decisions == {
        "allowlist": 9,
        "metadata-only": 56,
        "partnership": 14,
        "deny": 5,
    }


def test_exported_connector_registry_has_100_unique_registered_sources() -> None:
    rows = json.loads((ROOT / "docs" / "CONNECTOR_REGISTRY.json").read_text())

    assert len(rows) == 100
    assert len({row["source_id"] for row in rows}) == 100
    assert sum(row["enabled_by_default"] for row in rows) == 4
    assert sum(row["policy_status"] == "pending_robots_review" for row in rows) == 0
    assert sum(row["policy_status"] == "robots_disallow" for row in rows) == 1
    assert sum(row["policy_status"] == "runtime_tls_blocked" for row in rows) == 1


def test_summary_docs_match_generated_registry_and_catalog_counts() -> None:
    registry = json.loads((ROOT / "docs" / "CONNECTOR_REGISTRY.json").read_text())
    catalog = json.loads((ROOT / "docs" / "SOURCE_CATALOG.json").read_text())
    mapped = [row for row in catalog if row.get("connector_id")]

    expected = {
        ROOT / "README.md": [
            f"| **등록 커넥터** | **{len(registry)}** |",
            f"| 카탈로그와 직접 연결된 행 | {len(mapped)} |",
        ],
        ROOT / "docs" / "ARCHITECTURE.md": [
            f"{len(registry)} source adapter instances",
        ],
        ROOT / "docs" / "SOURCE_CATALOG.md": [
            f"실제 코드에 등록된 {len(registry)}개 커넥터",
            f"{len(mapped)}개 조사 행이 "
            f"{len({row['connector_id'] for row in mapped})}개 고유 connector ID",
        ],
    }
    for path, snippets in expected.items():
        content = path.read_text(encoding="utf-8")
        assert all(snippet in content for snippet in snippets), path


def test_suwon_gyeonggi_daily_profile_has_public_sources_and_guarded_samsung_docs(
) -> None:
    path = ROOT / "config" / "com.kidsradar.suwon-gyeonggi.daily.plist.example"
    profile = plistlib.loads(path.read_bytes())
    command = profile["ProgramArguments"][2]
    public_sources = {
        "ggc_gyeonggi_child_events",
        "ggcf_affiliate_child_programs",
        "ggcf_gyeonggi_jang_programs",
        "suwon_education_experience",
        "suwon_culture_foundation_education",
        "suwon_ecology_child_programs",
        "suwon_library_child_programs",
        "suwon_museum_child_programs",
        "suwon_gwanggyo_museum_child_programs",
        "suwon_hwaseong_museum_child_programs",
        "goyang_children_museum_city_news",
        "gyeonggi_library_programs",
    }

    assert all(f"--source {source_id}" in command for source_id in public_sources)
    assert "--source samsung_innovation_education" not in command
    assert "--include-unknown-location" in command
    assert "--max-stale-hours 48" in command
    assert "--max-pages 25" in command
    assert "digest_status=$?" in command
    assert "if [ $crawl_status -ne 0 ]" in command
    assert "exit $digest_status" in command

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "KIDS_RADAR_APPROVED_SOURCES=samsung_innovation_education" in readme
    assert "KIDS_RADAR_ROBOTS_OVERRIDE_SOURCES=samsung_innovation_education" in readme
    assert "--source samsung_innovation_education" in readme
