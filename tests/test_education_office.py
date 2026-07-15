from __future__ import annotations

from datetime import datetime
from pathlib import Path
import pytest

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.education_office import (
    EducationOfficeExperienceSource,
    builtin_education_office_sources,
)


FIXTURES = Path(__file__).parent / "fixtures"
EMPTY_LIST = "<div class='bbs_ListA'><table><tbody></tbody></table></div>"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def sources_by_id() -> dict[str, EducationOfficeExperienceSource]:
    return {source.info.source_id: source for source in builtin_education_office_sources()}


def window() -> CrawlWindow:
    return CrawlWindow(
        start=datetime(2026, 7, 1, tzinfo=KST),
        end=datetime(2026, 12, 31, 23, 59, 59, tzinfo=KST),
        max_pages=3,
    )


def test_factory_builds_four_policy_scoped_sources() -> None:
    sources = builtin_education_office_sources()

    assert [source.info.source_id for source in sources] == [
        "incheon_education_experience",
        "busan_education_experience",
        "chungbuk_education_experience",
        "jeonnam_education_experience",
    ]
    assert all(source.info.enabled_by_default is False for source in sources)
    assert all(source.info.policy_status == "approved_html" for source in sources)
    assert all(source.info.requires_key is None for source in sources)
    assert all("selectExprnList.do" in source.config.list_url for source in sources)
    assert all("selectExprnInfo.do" in source.config.detail_url for source in sources)


@pytest.mark.parametrize(
    ("source_id", "fixture_name", "row_count", "child_count"),
    [
        ("incheon_education_experience", "education_office_ice_list.html", 2, 1),
        ("busan_education_experience", "education_office_pen_list.html", 2, 1),
        ("chungbuk_education_experience", "education_office_cbe_list.html", 1, 1),
        ("jeonnam_education_experience", "education_office_jne_list.html", 2, 1),
    ],
)
def test_common_list_parser_and_child_filter(
    source_id: str,
    fixture_name: str,
    row_count: int,
    child_count: int,
) -> None:
    source = sources_by_id()[source_id]
    events = source.parse_list_html(fixture(fixture_name))

    assert len(events) == row_count
    assert sum(source._is_child_candidate(event) for event in events) == child_count
    assert all(set(event.raw) == source.RAW_FACT_FIELDS for event in events)
    assert all(event.region == source.config.region for event in events)


def test_external_official_link_gets_stable_session_key_without_detail_ids() -> None:
    source = sources_by_id()["chungbuk_education_experience"]
    event = source.parse_list_html(fixture("education_office_cbe_list.html"))[0]

    assert event.external_id.startswith("external:")
    assert event.detail_url == "https://www.cbec.go.kr/reserve/sub.php?menukey=311"
    assert event.raw["provider_id"] is None
    assert event.raw["exprn_seq"] is None
    assert event.title == "스토리가 있는 문화예술 체험 — 하반기"
    assert event.status == "접수중"


@pytest.mark.parametrize(
    ("fixture_name", "expected_title", "expected_provider"),
    [
        (
            "education_office_ice_detail.html",
            "[실감체험] 2026학년도 여름방학 중 안전체험프로그램",
            "학생안전체험관",
        ),
        (
            "education_office_pen_detail.html",
            "토요가족체험 - 꿈누리 과학(7/18)",
            "유아교육진흥원",
        ),
        (
            "education_office_jne_detail.html",
            "2026. 가족사랑해양캠프",
            "전남광주통합특별시교육청송호학생수련장",
        ),
    ],
)
def test_public_information_detail_whitelist(
    fixture_name: str,
    expected_title: str,
    expected_provider: str,
) -> None:
    facts = EducationOfficeExperienceSource.parse_detail_html(fixture(fixture_name))

    assert facts["title"] == expected_title
    assert facts["provider_name"] == expected_provider
    assert set(facts) <= {
        "title",
        "provider_name",
        "event_period",
        "application_period",
        "age_text",
        "application_target",
        "reservation_region",
    }


def test_weekday_times_grade_ranges_and_pagination_contract() -> None:
    start, end = EducationOfficeExperienceSource._parse_period(
        "2026/07/14(화) 10:00 ~ 2026/07/16(목) 15:00"
    )
    assert start == datetime(2026, 7, 14, 10, 0, tzinfo=KST)
    assert end == datetime(2026, 7, 16, 15, 0, tzinfo=KST)
    assert EducationOfficeExperienceSource._age("초(4학년) 이상 학생")[:2] == (
        10,
        12,
    )
    assert EducationOfficeExperienceSource._age("초등학교 1~3학년 가족")[:2] == (
        7,
        9,
    )
    assert (
        EducationOfficeExperienceSource.max_page_from_html(
            fixture("education_office_ice_list.html")
        )
        == 2
    )
    assert (
        EducationOfficeExperienceSource.max_page_from_html(
            fixture("education_office_cbe_list.html")
        )
        == 1
    )


class FakeClient:
    def __init__(self, source: EducationOfficeExperienceSource) -> None:
        self.source = source
        self.asserted: list[str] = []
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def assert_html_allowed(self, url: str) -> None:
        self.asserted.append(url)

    def get_text(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
    ) -> str:
        self.calls.append((url, params))
        if url == self.source.config.detail_url or url.startswith(
            f"{self.source.config.detail_url}?"
        ):
            assert params is None
            return fixture("education_office_ice_detail.html")
        assert url == self.source.config.list_url
        assert params is not None
        if params["srchRsvSttus"] == "REQST" and params["currPage"] == 1:
            return fixture("education_office_ice_list.html")
        return EMPTY_LIST


def test_crawl_gets_only_public_lists_and_information_detail() -> None:
    source = sources_by_id()["incheon_education_experience"]
    client = FakeClient(source)

    events = list(source.crawl(client, window()))  # type: ignore[arg-type]

    assert len(events) == 1
    event = events[0]
    assert event.external_id == "1000028:320:440"
    assert event.title == "[실감체험] 2026학년도 여름방학 중 안전체험프로그램"
    assert event.event_start == datetime(2026, 8, 5, tzinfo=KST)
    assert event.apply_start == datetime(2026, 7, 13, 13, 0, tzinfo=KST)
    assert (event.age_min, event.age_max) == (10, 12)
    assert event.child_relevance_score >= 0.45
    assert set(event.raw) == source.RAW_FACT_FIELDS
    assert client.asserted == [source.config.list_url, event.detail_url]

    assert client.calls[0] == (
        source.config.list_url,
        {
            "mi": "11607",
            "srchRsvSttus": "REQST",
            "currPage": 1,
            "pageIndex": 10,
        },
    )
    assert client.calls[1] == (event.detail_url, None)
    assert client.calls[2][1] == {
        "mi": "11607",
        "srchRsvSttus": "REQST",
        "currPage": 2,
        "pageIndex": 10,
    }
    assert client.calls[3][1] == {
        "mi": "11607",
        "srchRsvSttus": "PREV",
        "currPage": 1,
        "pageIndex": 10,
    }
    assert all(
        forbidden not in url.casefold()
        for url, _ in client.calls
        for forbidden in ("/ad/rs/", "login", "rsvctm", "apply")
    )


class ExternalListClient:
    def __init__(self, source: EducationOfficeExperienceSource) -> None:
        self.source = source
        self.asserted: list[str] = []
        self.calls: list[str] = []

    def assert_html_allowed(self, url: str) -> None:
        self.asserted.append(url)

    def get_text(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
    ) -> str:
        assert url == self.source.config.list_url
        assert params is not None
        self.calls.append(url)
        if params["srchRsvSttus"] == "REQST":
            return fixture("education_office_cbe_list.html")
        return EMPTY_LIST


def test_external_link_is_never_fetched_as_common_information_detail() -> None:
    source = sources_by_id()["chungbuk_education_experience"]
    client = ExternalListClient(source)

    events = list(source.crawl(client, window()))  # type: ignore[arg-type]

    assert len(events) == 1
    assert events[0].detail_url.startswith("https://www.cbec.go.kr/")
    assert client.asserted == [source.config.list_url]
    assert client.calls == [source.config.list_url, source.config.list_url]
