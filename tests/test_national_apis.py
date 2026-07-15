from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.forest import ForestEducationSource
from kids_experience_radar.sources.kywa import KywaYouthActivitySource
from kids_experience_radar.sources.odcloud import builtin_odcloud_sources


FIXTURES = Path(__file__).parent / "fixtures"


class JsonClient:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.calls = 0

    def get_json(self, url: str, *, params: dict[str, object] | None = None) -> object:
        self.calls += 1
        return self.payload


def test_kywa_keeps_only_elementary_programs_and_redacts_business_id(monkeypatch) -> None:
    monkeypatch.setenv("DATA_GO_KR_SERVICE_KEY", "test-key")
    payload = json.loads((FIXTURES / "kywa_activities.json").read_text())
    source = KywaYouthActivitySource()
    client = JsonClient(payload)
    window = CrawlWindow(
        start=datetime(2026, 7, 15, tzinfo=KST),
        end=datetime(2026, 8, 15, tzinfo=KST),
        max_pages=1,
    )

    events = list(source.crawl(client, window))  # type: ignore[arg-type]

    assert len(events) == 1
    event = events[0]
    assert event.title == "숲속 초등 생태 탐험"
    assert event.price_min == 0
    assert event.age_min == 7 and event.age_max == 13
    assert event.latitude == 37.5665 and event.longitude == 126.978
    assert event.region == "서울특별시 종로구"
    assert "brno" not in event.raw


def test_forest_xml_maps_seasonal_program_catalogue() -> None:
    source = ForestEducationSource()
    rows, total = source.parse_page(
        (FIXTURES / "forest_education.xml").read_text(encoding="utf-8")
    )
    assert total == 1
    event = source._map_row(rows[0])
    assert event.title == "가족 숲 생태 체험"
    assert event.status == "4~10월"
    assert event.region == "강원특별자치도 평창군"
    assert event.child_relevance_score >= 0.8


def test_odcloud_catalog_includes_new_museum_and_themepark_sources() -> None:
    sources = {source.info.source_id: source for source in builtin_odcloud_sources()}
    assert "odcloud_mmca_education" in sources
    assert "odcloud_suwon_art_education" in sources
    assert "odcloud_ulsan_children_themepark" in sources
    assert "odcloud_nakdong_bioresource_education" in sources
    assert "odcloud_korean_film_museum_education" in sources
    assert "odcloud_yangcheon_community_courses" in sources
    assert "odcloud_gangjin_celadon_experiences" in sources
    themepark = sources["odcloud_ulsan_children_themepark"]
    event = themepark._map_row(
        {
            "프로그램명": "어린이 창의 놀이",
            "대상": "초등 1~3학년",
            "장소": "대왕별아이누리",
            "1인 참가비(원)": 5000,
        }
    )
    assert event.price_min == 5000
    assert event.age_min == 7 and event.age_max == 9


def test_odcloud_source_level_child_filter(monkeypatch) -> None:
    monkeypatch.setenv("DATA_GO_KR_SERVICE_KEY", "test-key")
    source = {
        item.info.source_id: item for item in builtin_odcloud_sources()
    }["odcloud_yangcheon_community_courses"]
    client = JsonClient(
        {
            "data": [
                {
                    "번호": 1,
                    "강좌명": "성인 영어",
                    "수강대상": "성인",
                    "교육시작일": "2026-01-01",
                    "교육종료일": "2026-12-31",
                },
                {
                    "번호": 2,
                    "강좌명": "어린이 미술",
                    "수강대상": "초등학생",
                    "교육시작일": "2026-01-01",
                    "교육종료일": "2026-12-31",
                },
            ],
            "totalCount": 2,
        }
    )
    window = CrawlWindow(
        start=datetime(2026, 7, 15, tzinfo=KST),
        end=datetime(2026, 8, 15, tzinfo=KST),
        max_pages=1,
    )

    events = list(source.crawl(client, window))  # type: ignore[arg-type]
    assert [event.title for event in events] == ["어린이 미술"]


def test_odcloud_composite_external_id_keeps_separate_sessions() -> None:
    source = {
        item.info.source_id: item for item in builtin_odcloud_sources()
    }["odcloud_nakdong_bioresource_education"]

    first = source._map_row(
        {
            "프로그램명": "가족 생물 탐험",
            "교육시작일자": "2026-07-20",
            "이용대상": "초등학생 가족",
        }
    )
    second = source._map_row(
        {
            "프로그램명": "가족 생물 탐험",
            "교육시작일자": "2026-07-27",
            "이용대상": "초등학생 가족",
        }
    )

    assert first.external_id == "가족 생물 탐험|2026-07-20"
    assert second.external_id == "가족 생물 탐험|2026-07-27"
    assert first.uid != second.uid
