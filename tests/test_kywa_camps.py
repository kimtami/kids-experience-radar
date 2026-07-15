from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

import pytest

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.kywa_camps import KYWA_CENTERS, KywaCampSource


FIXTURE = Path(__file__).parent / "fixtures" / "kywa_camp_programs.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def window() -> CrawlWindow:
    return CrawlWindow(
        start=datetime(2026, 7, 15, tzinfo=KST),
        end=datetime(2026, 8, 31, 23, 59, 59, tzinfo=KST),
        max_pages=3,
    )


class FakeClient:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = payloads
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def assert_html_allowed(self, url: str) -> None:
        self.calls.append(("robots", url, None))

    def post_json(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        data: dict[str, object] | None = None,
    ) -> dict:
        assert params is None
        self.calls.append(("post", url, data))
        return self.payloads.pop(0)


def test_all_seven_centers_have_unique_disabled_sources() -> None:
    sources = KywaCampSource.all_sources()

    assert len(KYWA_CENTERS) == 7
    assert len(sources) == 7
    assert len({source.info.source_id for source in sources}) == 7
    assert len({source.center.code for source in sources}) == 7
    assert all(source.info.enabled_by_default is False for source in sources)
    assert all(source.info.policy_status == "reviewed_public_json" for source in sources)


def test_maps_only_whitelisted_public_list_facts() -> None:
    source = KywaCampSource("2")
    rows, total_pages = source.parse_page(load_fixture())
    event = source._map_row(rows[0])

    assert total_pages == 2
    assert event is not None
    assert event.external_id == "2:GS2026071501:3131"
    assert event.title == "초등 가족 우주과학 캠프"
    assert event.detail_url == (
        "https://booking.kywa.or.kr/reservation/campReservationView.do?"
        "pgm_no=GS2026071501&center_cd=2&pgm_gb=3131"
    )
    assert event.category == "가족캠프"
    assert event.status == "접수중"
    assert event.event_start == datetime(2026, 8, 14, tzinfo=KST)
    assert event.apply_end is not None and event.apply_end.date().isoformat() == "2026-08-10"
    assert event.age_min == 9 and event.age_max == 12
    assert event.price_min == 120000
    assert event.price_text == "120,000원"
    assert set(event.raw) <= source.PUBLIC_RAW_FIELDS
    assert not {
        "member_id",
        "member_pwd",
        "member_name",
        "mng_hp",
        "cre_ip",
    } & set(event.raw)
    assert "fixture-private" not in json.dumps(event.to_dict(), ensure_ascii=False)


def test_crawl_pages_and_never_calls_application_or_payment_paths() -> None:
    source = KywaCampSource("2")
    second_page = {
        "cnt": 3,
        "paginationInfo": {"totalPageCount": 2},
        "resultList": [],
    }
    client = FakeClient([load_fixture(), second_page])

    events = list(source.crawl(client, window()))  # type: ignore[arg-type]

    assert [event.external_id for event in events] == ["2:GS2026071501:3131"]
    assert client.calls == [
        ("robots", source.info.official_url, None),
        (
            "post",
            source.LIST_ENDPOINT,
            {
                "multi_center_cd": "2",
                "multi_pgm_gb": "3101,3131,3151",
                "pageIndex": 1,
            },
        ),
        (
            "post",
            source.LIST_ENDPOINT,
            {
                "multi_center_cd": "2",
                "multi_pgm_gb": "3101,3131,3151",
                "pageIndex": 2,
            },
        ),
    ]
    called_urls = " ".join(url for _, url, _ in client.calls).casefold()
    assert "campreservationreg" not in called_urls
    assert "payment" not in called_urls
    assert "login" not in called_urls


def test_window_filter_and_family_lodging_filter() -> None:
    source = KywaCampSource("2")
    rows, _ = source.parse_page(load_fixture())
    events = [source._map_row(row) for row in rows]

    assert events[0] is not None and source._child_candidate(events[0])
    assert events[1] is not None and not source._child_candidate(events[1])
    assert events[2] is not None and not source._child_candidate(events[2])
    assert events[0] is not None
    old_window = CrawlWindow(
        start=datetime(2027, 1, 1, tzinfo=KST),
        end=datetime(2027, 1, 31, tzinfo=KST),
        max_pages=1,
    )
    assert not source._overlaps(events[0], old_window)


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"resultList": [], "paginationInfo": []},
        {"resultList": [], "paginationInfo": {"totalPageCount": "broken"}},
    ],
)
def test_parse_page_fails_loudly_on_malformed_payload(payload: object) -> None:
    with pytest.raises(RuntimeError):
        KywaCampSource.parse_page(payload)


def test_rejects_unknown_center() -> None:
    with pytest.raises(ValueError, match="unknown KYWA center"):
        KywaCampSource("999")
