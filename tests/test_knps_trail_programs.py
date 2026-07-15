from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

import pytest

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.knps_trail_programs import (
    KNPS_PARKS,
    KnpsTrailProgramSource,
)


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


EXPECTED_SOURCE_IDS = {
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
}


class FakeClient:
    def __init__(self, pages: list[str]) -> None:
        self.pages = pages
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def assert_html_allowed(self, url: str) -> None:
        self.calls.append(("robots", url, None))

    def post_text(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        data: dict[str, object] | None = None,
    ) -> str:
        assert params is None
        self.calls.append(("post", url, data))
        return self.pages.pop(0)


def window() -> CrawlWindow:
    return CrawlWindow(
        start=datetime(2026, 7, 15, tzinfo=KST),
        end=datetime(2026, 8, 31, 23, 59, 59, tzinfo=KST),
        max_pages=5,
    )


def test_all_sources_have_22_unique_stable_ids_and_are_disabled() -> None:
    sources = KnpsTrailProgramSource.all_sources()

    assert len(KNPS_PARKS) == 22
    assert len(sources) == 22
    assert {source.info.source_id for source in sources} == EXPECTED_SOURCE_IDS
    assert len({source.dept_id for source in sources}) == 22
    assert all(source.info.enabled_by_default is False for source in sources)
    assert all(source.info.policy_status == "reviewed_public_list" for source in sources)


def test_parse_page_maps_only_list_facts_and_safe_canonical_link() -> None:
    source = KnpsTrailProgramSource("B01")

    rows, total = source.parse_page(load_fixture("knps_trail_programs_page_1.html"))

    assert total == 3
    assert len(rows) == 2
    child = source._map_row(rows[0])
    assert child.external_id == "GB011XXX07001"
    assert child.title == "[2026년] 가족과 함께하는 국립공원 생태체험"
    assert child.detail_url == (
        "https://reservation.knps.or.kr/contents/G/serviceGuide.do?"
        "parkId=B011&prdId=GB011XXX07001&orgnztGbn=G"
    )
    assert child.provider_name == "국립공원공단"
    assert child.event_start == datetime(2026, 7, 20, tzinfo=KST)
    assert child.event_end is not None and child.event_end.date().isoformat() == "2026-08-31"
    assert child.age_text == "가족"
    assert child.age_min == 5 and child.age_max == 13
    assert child.venue_name == "중산리탐방안내소"
    assert child.region == "전북특별자치도·전라남도·경상남도"
    assert child.price_text is None and child.price_min is None
    assert child.status is None
    assert child.description is None
    assert child.image_url is None
    assert child.raw == {
        "product_id": "GB011XXX07001",
        "park_id": "B011",
        "park_name": "지리산",
        "meeting_place": "중산리탐방안내소",
        "operating_period": "2026-07-20 ~ 2026-08-31",
    }


def test_crawl_pages_filters_adult_rows_and_never_calls_booking_or_netfunnel() -> None:
    source = KnpsTrailProgramSource("B01")
    source.PAGE_SIZE = 2
    client = FakeClient(
        [
            load_fixture("knps_trail_programs_page_1.html"),
            load_fixture("knps_trail_programs_page_2.html"),
        ]
    )

    events = list(source.crawl(client, window()))  # type: ignore[arg-type]

    assert [event.external_id for event in events] == [
        "GB011XXX07001",
        "GB012XXX07003",
    ]
    assert events[1].age_text == "초등학생"
    assert events[1].age_min == 7 and events[1].age_max == 13
    assert client.calls == [
        ("robots", source.LIST_ENDPOINT, None),
        (
            "post",
            source.LIST_ENDPOINT,
            {
                "dept_id": "B01",
                "dept_name": "지리산",
                "orgnzt_gbn": "G",
                "pageNo": 1,
                "listScale": 2,
            },
        ),
        (
            "post",
            source.LIST_ENDPOINT,
            {
                "dept_id": "B01",
                "dept_name": "지리산",
                "orgnzt_gbn": "G",
                "pageNo": 2,
                "listScale": 2,
            },
        ),
    ]
    called_urls = " ".join(url for _, url, _ in client.calls).casefold()
    assert "serviceguide" not in called_urls
    assert "netfunnel" not in called_urls


def test_crawl_filters_program_outside_window() -> None:
    source = KnpsTrailProgramSource("B01")
    source.PAGE_SIZE = 2
    client = FakeClient([load_fixture("knps_trail_programs_page_1.html")])
    past_window = CrawlWindow(
        start=datetime(2027, 1, 1, tzinfo=KST),
        end=datetime(2027, 1, 31, 23, 59, tzinfo=KST),
        max_pages=1,
    )

    assert list(source.crawl(client, past_window)) == []  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("html", "message"),
    [
        ("<html></html>", "trail program table not found"),
        (
            '<div class="article-info"><span class="total"><span>1</span></span></div>'
            '<table class="table trail-prod-list"><tbody><tr><td>broken</td></tr></tbody></table>',
            "no valid program rows parsed",
        ),
    ],
)
def test_parse_page_fails_loudly_on_structure_change(html: str, message: str) -> None:
    with pytest.raises(RuntimeError, match=re.escape(message)):
        KnpsTrailProgramSource("B01").parse_page(html)


def test_rejects_unknown_department() -> None:
    with pytest.raises(ValueError, match="unknown KNPS department"):
        KnpsTrailProgramSource("B99")
