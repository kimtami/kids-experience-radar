#!/usr/bin/env python3
"""Build machine-readable source catalogs from the verified research tables."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESEARCH_DIR = ROOT / "docs" / "research"
OUTPUT_CSV = ROOT / "docs" / "SOURCE_CATALOG.csv"
OUTPUT_JSON = ROOT / "docs" / "SOURCE_CATALOG.json"

LINK_RE = re.compile(r"\[([^]]+)]\((https?://[^)]+)\)")
ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|")
PRIORITY_RE = re.compile(r"(?<![A-Z0-9])P([0-3])(?![A-Z0-9])")


@dataclass(frozen=True)
class CatalogRow:
    catalog_id: str
    group: str
    ordinal: int
    source_name: str
    official_url: str
    additional_official_urls: str
    access_structure: str
    audience_fields: str
    policy_notes: str
    recommendation: str
    priority: str
    implementation_status: str
    connector_id: str
    implementation_note: str
    verification_status: str
    verified_at: str
    source_document: str


DIRECT_CONNECTORS: dict[tuple[str, int], tuple[str, str, str]] = {
    ("regional_portals", 2): (
        "implemented_api",
        "seoul_reservation_education",
        "Exact official API product.",
    ),
    ("regional_portals", 3): (
        "implemented_api",
        "seoul_cultural_events",
        "Exact official API product.",
    ),
    ("regional_portals", 13): (
        "implemented_opt_in",
        "suwon_education_experience",
        "Public current/soon result table only; no detail, login, or reservation calls.",
    ),
    ("regional_portals", 51): (
        "implemented_opt_in",
        "gyeongbuk_education_experience",
        "Public list only; runtime robots fail-closed; no detail or reservation calls.",
    ),
    ("private_brands", 1): (
        "implemented_opt_in",
        "samsung_innovation_education",
        "Public facts-only JSON; disabled by default.",
    ),
    ("private_brands", 2): (
        "implemented_opt_in",
        "hyundai_motorstudio_goyang_kids",
        "Public program cards only; disabled by default.",
    ),
    ("private_brands", 8): (
        "implemented_opt_in",
        "museum_kimchikan_children",
        "Public program and calendar JSON only; disabled by default.",
    ),
    ("private_brands", 22): (
        "implemented_opt_in",
        "hmoka_programs",
        "Public list POST only; policy review required before operation.",
    ),
    ("private_brands", 23): (
        "implemented_opt_in",
        "leeum_hoam_programs",
        "Unified public-list parser; private source approval remains explicit.",
    ),
    ("private_brands", 24): (
        "implemented_opt_in",
        "leeum_hoam_programs",
        "Unified parser separates venues; private source approval remains explicit.",
    ),
    ("public_institutions", 64): (
        "implemented_official_dataset",
        "odcloud_nibr_education",
        "Uses the institution's official public-data dataset instead of HTML.",
    ),
    ("public_institutions", 65): (
        "implemented_official_dataset",
        "odcloud_nakdong_bioresource_education",
        "Uses the institution's official public-data dataset instead of HTML.",
    ),
    ("public_institutions", 78): (
        "implemented_official_dataset",
        "odcloud_mabik_education",
        "Uses the institution's official public-data dataset instead of HTML.",
    ),
}

for _ordinal, _connector_id in {
    11: "incheon_education_experience",
    22: "busan_education_experience",
    37: "chungbuk_education_experience",
    47: "jeonnam_education_experience",
}.items():
    DIRECT_CONNECTORS[("regional_portals", _ordinal)] = (
        "implemented_opt_in",
        _connector_id,
        "Shared education-office adapter; public list/detail GET only, no application.",
    )

for _ordinal, _connector_id in {
    7: "geumcheon_education_reservation",
    14: "goyang_experience_reservation",
    16: "anyang_education_reservation",
    18: "yongin_experience_reservation",
    19: "gimpo_experience_reservation",
    38: "cheongju_experience_reservation",
}.items():
    DIRECT_CONNECTORS[("regional_portals", _ordinal)] = (
        (
            "implemented_policy_guarded"
            if _connector_id
            in {"gimpo_experience_reservation", "anyang_education_reservation"}
            else "implemented_opt_in"
        ),
        _connector_id,
        (
            "Shared municipal adapter; public list/detail facts only. "
            "Gimpo remains robots-blocked; Anyang remains TLS-runtime-blocked."
        ),
    )

MODU_CONNECTORS = (
    "modu_museum_national_museum_korea",
    "modu_museum_gyeongju",
    "modu_museum_gwangju",
    "modu_museum_jeonju",
    "modu_museum_daegu",
    "modu_museum_buyeo",
    "modu_museum_gongju",
    "modu_museum_jinju",
    "modu_museum_cheongju",
    "modu_museum_gimhae",
    "modu_museum_jeju",
    "modu_museum_chuncheon",
    "modu_museum_naju",
    "modu_museum_iksan",
)
for _ordinal, _connector_id in enumerate(MODU_CONNECTORS, start=1):
    DIRECT_CONNECTORS[("public_institutions", _ordinal)] = (
        "implemented_opt_in",
        _connector_id,
        "Shared MODU adapter; facts-only public list and runtime robots check.",
    )

KNPS_CONNECTORS = (
    "knps_jirisan_trail_programs",
    "knps_hallyeohaesang_trail_programs",
    "knps_seoraksan_trail_programs",
    "knps_naejangsan_trail_programs",
    "knps_deogyusan_trail_programs",
    "knps_odaesan_trail_programs",
    "knps_juwangsan_trail_programs",
    "knps_taeanhaean_trail_programs",
    "knps_dadohaehaesang_trail_programs",
    "knps_chiaksan_trail_programs",
    "knps_woraksan_trail_programs",
    "knps_sobaeksan_trail_programs",
    "knps_gayasan_trail_programs",
    "knps_bukhansan_trail_programs",
    "knps_gyeongju_trail_programs",
    "knps_gyeryongsan_trail_programs",
    "knps_mudeungsan_trail_programs",
    "knps_byeonsanbando_trail_programs",
    "knps_songnisan_trail_programs",
    "knps_wolchulsan_trail_programs",
    "knps_taebaeksan_trail_programs",
    "knps_palgongsan_trail_programs",
)
for _ordinal, _connector_id in enumerate(KNPS_CONNECTORS, start=15):
    DIRECT_CONNECTORS[("public_institutions", _ordinal)] = (
        "implemented_opt_in",
        _connector_id,
        "Shared KNPS public-list adapter; no detail, login, queue, or reservation call.",
    )

KYWA_CAMP_CONNECTORS = (
    "kywa_central_camp_programs",
    "kywa_pyeongchang_camp_programs",
    "kywa_space_camp_programs",
    "kywa_bio_camp_programs",
    "kywa_ocean_camp_programs",
    "kywa_future_environment_camp_programs",
    "kywa_ecology_camp_programs",
)
for _ordinal, _connector_id in enumerate(KYWA_CAMP_CONNECTORS, start=37):
    DIRECT_CONNECTORS[("public_institutions", _ordinal)] = (
        "implemented_opt_in",
        _connector_id,
        "Whitelisted public camp-list facts; no application or payment endpoint.",
    )

for _ordinal, _connector_id in {
    44: "koagi_baekdudaegan_education",
    45: "koagi_sejong_education",
    46: "koagi_native_plants_education",
    47: "koagi_garden_culture_education",
}.items():
    DIRECT_CONNECTORS[("public_institutions", _ordinal)] = (
        "implemented_opt_in",
        _connector_id,
        "Public list only; semantic robots 404 follows RFC 9309 no-rules handling.",
    )


def implementation(
    group: str,
    ordinal: int,
    priority_value: str,
    recommendation: str,
) -> tuple[str, str, str]:
    direct = DIRECT_CONNECTORS.get((group, ordinal))
    if direct:
        return direct
    if priority_value == "P3" or recommendation.startswith(("deny", "partnership")):
        return (
            "policy_or_access_blocked",
            "",
            "No automated collector until an official API, permission, or partnership exists.",
        )
    return (
        "researched_not_implemented",
        "",
        "Verified candidate; requires a source-specific contract and policy approval.",
    )


def clean_markdown(value: str) -> str:
    value = LINK_RE.sub(lambda match: match.group(1), value)
    value = value.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", value).strip()


def split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def links(value: str) -> list[str]:
    return [match.group(2) for match in LINK_RE.finditer(value)]


def priority(value: str) -> str:
    matches = PRIORITY_RE.findall(value)
    return f"P{matches[-1]}" if matches else ""


def parse_document(group: str, filename: str) -> list[CatalogRow]:
    path = RESEARCH_DIR / filename
    rows: list[CatalogRow] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not ROW_RE.match(line):
            continue
        cells = split_row(line)
        ordinal = int(cells[0])

        if group == "regional_portals":
            name_cell, access, audience, recommendation = cells[1:5]
            policy = recommendation
            official_links = links(name_cell)
        elif group == "public_institutions":
            name_cell = cells[1]
            official_cell = cells[2]
            official_links = links(official_cell)
            if len(cells) == 5:
                audience = cells[3]
                access = cells[4]
                policy = cells[4]
                recommendation = cells[4]
            else:
                access = cells[3]
                audience = cells[4]
                policy = cells[5]
                recommendation = cells[5]
        elif group == "private_brands":
            name_cell, access, audience, policy, recommendation = cells[1:6]
            official_links = links(name_cell)
        else:  # pragma: no cover - script has a fixed input set
            raise ValueError(f"unknown group: {group}")

        if not official_links:
            raise ValueError(f"no official URL in {filename} row {ordinal}")

        all_text = " ".join(cells)
        cleaned_recommendation = clean_markdown(recommendation)
        priority_value = priority(all_text)
        implementation_status, connector_id, implementation_note = implementation(
            group,
            ordinal,
            priority_value,
            cleaned_recommendation,
        )
        rows.append(
            CatalogRow(
                catalog_id=f"{group}:{ordinal:03d}",
                group=group,
                ordinal=ordinal,
                source_name=clean_markdown(name_cell),
                official_url=official_links[0],
                additional_official_urls=";".join(official_links[1:]),
                access_structure=clean_markdown(access),
                audience_fields=clean_markdown(audience),
                policy_notes=clean_markdown(policy),
                recommendation=cleaned_recommendation,
                priority=priority_value,
                implementation_status=implementation_status,
                connector_id=connector_id,
                implementation_note=implementation_note,
                verification_status="official_page_verified",
                verified_at="2026-07-15",
                source_document=f"docs/research/{filename}",
            )
        )
    return rows


def main() -> None:
    rows: list[CatalogRow] = []
    rows.extend(parse_document("regional_portals", "regional-portals.md"))
    rows.extend(parse_document("public_institutions", "public-institutions.md"))
    rows.extend(parse_document("private_brands", "private-brands.md"))

    serialized = [asdict(row) for row in rows]
    OUTPUT_JSON.write_text(
        json.dumps(serialized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(serialized[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(serialized)

    counts: dict[str, int] = {}
    for row in rows:
        counts[row.group] = counts.get(row.group, 0) + 1
    unique_urls = len({row.official_url for row in rows})
    print(
        json.dumps(
            {"total": len(rows), "unique_primary_urls": unique_urls, "groups": counts},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
