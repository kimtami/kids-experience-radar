from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pytest

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.hmoka import HmokaProgramSource


FIXTURE = Path(__file__).parent / "fixtures" / "hmoka_programs.json"


class FakeClient:
    def __init__(self, payloads: dict[str, Any]) -> None:
        self.payloads = payloads
        self.calls: list[tuple[str, dict[str, object] | None]] = []
        self.robots_urls: list[str] = []

    def assert_html_allowed(self, url: str) -> None:
        self.robots_urls.append(url)

    def post_json(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        data: dict[str, object] | None = None,
    ) -> Any:
        assert params is None
        self.calls.append((url, data))
        program_type = url.rstrip("/").split("/")[-2]
        return self.payloads[program_type]


@pytest.fixture
def window() -> CrawlWindow:
    return CrawlWindow(
        start=datetime(2026, 7, 15, tzinfo=KST),
        end=datetime(2026, 8, 31, 23, 59, 59, tzinfo=KST),
    )


def load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_crawl_posts_only_public_list_forms_and_maps_whitelisted_facts(
    window: CrawlWindow,
) -> None:
    source = HmokaProgramSource()
    client = FakeClient(load_fixture())

    events = list(source.crawl(client, window))  # type: ignore[arg-type]

    assert source.info.enabled_by_default is False
    assert source.info.policy_status == "review_required_public_json"
    assert source.info.requires_key is None
    assert client.robots_urls == [source.DATA_URL.format(program_type="exhibition")]
    assert [call[0] for call in client.calls] == [
        source.DATA_URL.format(program_type=program_type)
        for program_type in source.PROGRAM_TYPES
    ]
    assert all(
        data == {
            "st_cd": "480",
            "page": 1,
            "rows": 100,
            "searchEduName": "",
            "searchOnlineCode": "",
        }
        for _, data in client.calls
    )
    assert [event.external_id for event in events] == [
        "1435",
        "1410",
        "1442",
        "1438",
        "1439",
    ]

    first = events[0]
    assert first.title == "시가 된 사진"
    assert first.event_start == datetime(2026, 7, 26, tzinfo=KST)
    assert first.event_end is not None and first.event_end.hour == 23
    assert (first.age_min, first.age_max, first.age_text) == (6, 7, "6-7세")
    assert (first.price_min, first.price_text) == (20_000, "20,000원")
    assert first.status == "신청 가능"
    assert first.venue_name == "현대어린이책미술관 · 교육실 1"
    assert first.address == "경기도 성남시 분당구 판교역로146번길 20 현대백화점 판교점 5층"
    assert first.region == "경기도 성남시 분당구"
    assert first.description is None
    assert first.image_url is None
    assert first.detail_url == (
        "https://www.hmoka.org/programs/exhibition/view.do?st_cd=480&edu_seq=1435"
    )
    assert first.raw == {
        "title": "시가 된 사진",
        "period": "2026-07-26~2026-11-01",
        "target": "6-7세",
        "place": "교육실 1",
        "price": "20,000원",
        "status": "신청 가능",
        "official_url": first.detail_url,
    }

    always_on, mixed_age, closed, family = events[1:]
    assert (always_on.price_min, always_on.price_text, always_on.status) == (
        0,
        "무료",
        "상설운영",
    )
    assert (mixed_age.age_min, mixed_age.age_max, mixed_age.status) == (6, 8, "신청 예정")
    assert (closed.age_min, closed.age_max, closed.status) == (10, 12, "신청마감")
    assert (family.age_min, family.age_max) == (4, 10)


def test_parse_page_rejects_malformed_envelopes() -> None:
    assert HmokaProgramSource.parse_page({"contentList": [], "page": 1, "total": 0}) == (
        [],
        1,
        0,
    )

    with pytest.raises(RuntimeError, match="malformed response"):
        HmokaProgramSource.parse_page("not-an-object")
    with pytest.raises(RuntimeError, match="contentList"):
        HmokaProgramSource.parse_page({"page": 1, "total": 0})
    with pytest.raises(RuntimeError, match="contentList"):
        HmokaProgramSource.parse_page({"contentList": "not-a-list"})


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("초1-초4", (7, 10, "초1-초4")),
        ("초3-초6", (9, 12, "초3-초6")),
        ("6세-초2", (6, 8, "6세-초2")),
    ],
)
def test_age_parser_does_not_treat_grade_as_literal_age(
    target: str,
    expected: tuple[int, int, str],
) -> None:
    assert HmokaProgramSource._age(target) == expected


def test_crawl_paginates_a_public_list_larger_than_one_hundred(window: CrawlWindow) -> None:
    class PagedClient:
        def assert_html_allowed(self, url: str) -> None:
            return None

        def post_json(
            self,
            url: str,
            *,
            params: dict[str, object] | None = None,
            data: dict[str, object] | None = None,
        ) -> dict[str, object]:
            assert data is not None
            program_type = url.rstrip("/").split("/")[-2]
            page = int(data["page"])
            if program_type != "exhibition":
                return {"contentList": [], "page": page, "total": 0}
            start = (page - 1) * 100 + 1
            end = min(page * 100, 101)
            return {
                "contentList": [
                    {
                        "edu_seq": str(index),
                        "edu_name": f"어린이 교육 {index}",
                        "edu_target_name": "초1",
                    }
                    for index in range(start, end + 1)
                ],
                "page": page,
                "total": 101,
            }

    events = list(HmokaProgramSource().crawl(PagedClient(), window))  # type: ignore[arg-type]

    assert len(events) == 101
    assert events[-1].external_id == "101"
