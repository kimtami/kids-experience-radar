from __future__ import annotations

from collections import Counter
import csv
import json
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "docs" / "research" / "gyeonggi-deep-discovery.json"
CSV_PATH = ROOT / "docs" / "research" / "gyeonggi-deep-discovery.csv"


def test_gyeonggi_deep_catalog_is_machine_readable_complete_and_stable() -> None:
    rows = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    with CSV_PATH.open(encoding="utf-8-sig") as handle:
        csv_rows = list(csv.DictReader(handle))

    assert len(rows) == 51
    assert len(csv_rows) == 51
    assert [row["id"] for row in rows] == [row["id"] for row in csv_rows]
    assert rows == csv_rows
    assert len({row["id"] for row in rows}) == 51
    assert all(urlparse(row["official_url"]).scheme == "https" for row in rows)
    assert all(row["priority"] in {"P0", "P1", "P2", "P3"} for row in rows)
    assert Counter(row["priority"] for row in rows) == {
        "P0": 21,
        "P1": 25,
        "P2": 4,
        "P3": 1,
    }

    required = {
        "id",
        "organization",
        "source_name",
        "location",
        "official_url",
        "official_social_url",
        "audience",
        "collection_method",
        "cadence",
        "robots_api_status",
        "priority",
        "policy",
        "implementation_status",
        "existing_catalog_overlap",
        "notes",
    }
    assert all(set(row) == required for row in rows)


def test_official_alternatives_are_recorded_without_erasing_original_blocks() -> None:
    rows = {
        row["id"]: row
        for row in json.loads(JSON_PATH.read_text(encoding="utf-8"))
    }

    assert rows["suwon_library_programs"]["implementation_status"] == (
        "implemented_official_alternative"
    )
    assert rows["suwon_ecology_network"]["implementation_status"] == (
        "implemented_dedicated_html"
    )
    assert rows["gyeonggi_library_programs"]["implementation_status"] == (
        "implemented_first_party_json"
    )
    goyang = rows["goyang_children_museum"]
    assert goyang["implementation_status"] == (
        "implemented_via_official_city_publication"
    )
    assert "museum origin remains" in goyang["robots_api_status"]
    assert "deny all automated requests to museum origin" in goyang["policy"]


def test_social_discovery_is_official_link_inventory_not_private_content() -> None:
    rows = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    social = [row["official_social_url"] for row in rows if row["official_social_url"]]

    assert len(social) == 28
    assert all(urlparse(url).scheme == "https" for url in social)
    assert {
        urlparse(url).netloc.removeprefix("www.") for url in social
    } <= {"instagram.com", "facebook.com", "pf.kakao.com"}
    assert sum(
        row["existing_catalog_overlap"] == "missing_before_this_audit"
        for row in rows
    ) == 32
    assert all("login" not in row["collection_method"].casefold() for row in rows)


def test_corrected_adapter_candidate_semantics_do_not_regress() -> None:
    rows = {
        row["id"]: row
        for row in json.loads(JSON_PATH.read_text(encoding="utf-8"))
    }

    haewoojae = rows["haewoojae_programs"]
    assert haewoojae["official_url"] == (
        "https://haewoojae.com/m/load.asp?subPage=220"
    )
    assert "subPage=220/230" in haewoojae["collection_method"]
    assert "subPage=221/231" in haewoojae["collection_method"]
    assert "subPage=411" in haewoojae["notes"]

    namyangju = rows["namyangju_children_vision"]
    assert namyangju["official_url"] == "https://www.ncuc.or.kr/children/715"
    assert "32-character action-value" in namyangju["collection_method"]
    assert "/children/674" in namyangju["notes"]
    assert "/children/2356" in namyangju["notes"]

    nfm_paju = rows["nfm_paju_family"]
    assert nfm_paju["official_url"] == (
        "https://www.nfm.go.kr/user/eduPlan/home/85/dataList.do"
        "?searchEduPlanCate=&searchStatus="
    )
    assert "home/87" in nfm_paju["notes"]
    assert "eduPlanIdx" in nfm_paju["notes"]

    astronomy = rows["bucheon_astronomy"]
    assert "Crawl-delay: 600" in astronomy["robots_api_status"]
    assert "at least 600 seconds" in astronomy["policy"]
    assert "dedicated host queue and cache" in astronomy["notes"]

    safety = rows["gg_safety_experience"]
    assert safety["priority"] == "P0"
    assert safety["collection_method"].startswith("notice-only public board")
    assert "Notice-only connector scope" in safety["notes"]
    assert "remaining-seat availability is intentionally unavailable" in safety["notes"]

    jobworld = rows["korea_jobworld_children"]
    assert jobworld["priority"] == "P0"
    assert "selectExrPreviewImg JSON" in jobworld["collection_method"]
    assert "reservation ZIP" in jobworld["notes"]
    assert "member/name/school identifiers" in jobworld["notes"]

    south_early_childhood = rows["goe_south_early_childhood"]
    assert south_early_childhood["official_url"] == (
        "https://www.kench.kr/kench/na/ntt/selectNttList.do"
        "?mi=10730&bbsId=6141"
    )
    assert "notice list/detail" in south_early_childhood["collection_method"]
    assert "rsvtInfo description" in south_early_childhood["collection_method"]
    assert "selectAplyList" in south_early_childhood["notes"]
    assert "must never be used as a feed" in south_early_childhood["notes"]
