from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.suwon_library import SuwonLibraryProgramSource


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def window(*, max_pages: int = 3) -> CrawlWindow:
    return CrawlWindow(
        start=datetime(2026, 7, 15, tzinfo=KST),
        end=datetime(2026, 12, 31, 23, 59, 59, tzinfo=KST),
        max_pages=max_pages,
    )


def page_html(
    *,
    total: int,
    current: int,
    total_pages: int,
    external_ids: list[str],
    title: str = "어린이 체험",
    target: str | None = "초등학생",
    event_period: str | None = "2026.08.01 ~ 2026.08.02",
    event_time: str | None = "10:00 ~ 12:00",
) -> str:
    date_field = (
        f"<span>교육기간 : {event_period}</span>" if event_period is not None else ""
    )
    time_field = f"<span>시간 : {event_time}</span>" if event_time is not None else ""
    target_field = f"<span>대상 : {target}</span>" if target is not None else ""
    rows = "".join(
        "<li><div class='title'>"
        f"<a onclick=\"fnDetail('{external_id}')\">{title} {external_id}</a>"
        "<i class='icon'><span>선경</span></i>"
        f"</div><div class='info'>{target_field}{date_field}{time_field}</div>"
        "<div class='info'></div></li>"
        for external_id in external_ids
    )
    return (
        "<div class='lectureWrap'>"
        "<div class='lecture-top'><span>"
        f"총 <strong>{total}</strong>건 "
        f"(<strong>{current}</strong>/{total_pages}페이지)"
        "</span></div>"
        f"<ul class='lecture-list'>{rows}</ul></div>"
    )


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def assert_html_allowed(self, url: str) -> None:
        self.calls.append(("robots", url, None))

    def get_text(
        self, url: str, *, params: dict[str, object] | None = None
    ) -> str:
        self.calls.append(("get", url, params))
        return fixture("suwon_library_programs.html")


class PagedFakeClient(FakeClient):
    def __init__(self, pages: dict[int, str]) -> None:
        super().__init__()
        self.pages = pages

    def get_text(
        self, url: str, *, params: dict[str, object] | None = None
    ) -> str:
        self.calls.append(("get", url, params))
        assert params is None
        query = parse_qs(urlparse(url).query)
        return self.pages[int(query["currentPageNo"][0])]


def test_crawl_uses_working_official_replacement_and_never_calls_apply() -> None:
    source = SuwonLibraryProgramSource()
    client = FakeClient()

    events = list(source.crawl(client, window()))  # type: ignore[arg-type]

    assert [event.external_id for event in events] == ["1447654", "1443716"]
    robots_url = client.calls[0][1]
    assert client.calls[0] == ("robots", robots_url, None)
    assert client.calls[1] == ("get", robots_url, None)
    assert robots_url.startswith(f"{source.LIST_URL}?")
    query = parse_qs(urlparse(robots_url).query)
    assert query == {
        "mode": ["search"],
        "searchTargetCdArray": ["AL", "IN", "EL", "FA"],
        "searchYmdCondition": ["lecturePeriod"],
        "searchStartYmd": ["2026-07-15"],
        "searchEndYmd": ["2026-12-31"],
        "currentPageNo": ["1"],
        "recordCountPerPage": ["100"],
    }
    assert all("lectureApply" not in call[1] for call in client.calls)
    assert all("login" not in call[1].casefold() for call in client.calls)

    primary = events[0]
    assert primary.title == "<식물 세밀화 그리기 [접시꽃]>"
    assert primary.detail_url.endswith("lectureDetail.do?lectureIdx=1447654")
    assert primary.event_start == datetime(2026, 8, 11, 10, 30, tzinfo=KST)
    assert primary.event_end == datetime(2026, 8, 12, 12, 0, tzinfo=KST)
    assert primary.apply_start == datetime(2026, 7, 21, 9, 0, tzinfo=KST)
    assert primary.apply_end == datetime(2026, 8, 10, 18, 0, tzinfo=KST)
    assert primary.age_min == 9 and primary.age_max == 12
    assert primary.status == "접수중"
    assert primary.raw["capacity"] == "0/10"
    assert set(primary.raw) <= source.PUBLIC_RAW_FIELDS

    family = events[1]
    assert family.status == "접수예정"
    assert family.address == "경기도 수원시 영통구 망포로 100"
    assert family.provider_name == "망포글빛도서관"


def test_empty_result_is_valid_but_structure_drift_fails_closed() -> None:
    assert SuwonLibraryProgramSource.parse_list(
        fixture("suwon_library_empty.html")
    ) == []
    assert list(
        SuwonLibraryProgramSource().crawl(
            PagedFakeClient({1: fixture("suwon_library_empty.html")}),  # type: ignore[arg-type]
            window(),
        )
    ) == []
    with pytest.raises(RuntimeError, match="Suwon library list"):
        SuwonLibraryProgramSource.parse_list("<html><body>maintenance</body></html>")
    with pytest.raises(RuntimeError, match="invalid program row"):
        SuwonLibraryProgramSource.parse_list(
            "<div class='lectureWrap'>"
            "<div class='lecture-top'><span>총 <strong>1</strong>건 "
            "(<strong>1</strong>/1페이지)</span></div>"
            "<ul class='lecture-list'><li>broken</li></ul></div>"
        )
    with pytest.raises(RuntimeError, match="pagination metadata"):
        SuwonLibraryProgramSource.parse_list(
            "<div class='lectureWrap'><ul class='lecture-list'></ul></div>"
        )


def test_pagination_validates_counts_duplicates_and_max_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(SuwonLibraryProgramSource, "PAGE_SIZE", 2)

    with pytest.raises(RuntimeError, match="page is incomplete"):
        SuwonLibraryProgramSource.parse_page(
            page_html(total=3, current=1, total_pages=2, external_ids=["1"])
        )
    with pytest.raises(RuntimeError, match="duplicate program IDs"):
        SuwonLibraryProgramSource.parse_page(
            page_html(
                total=2,
                current=1,
                total_pages=1,
                external_ids=["1", "1"],
            )
        )
    with pytest.raises(RuntimeError, match="pagination metadata is inconsistent"):
        SuwonLibraryProgramSource.parse_page(
            page_html(total=3, current=1, total_pages=3, external_ids=["1", "2"])
        )

    pages = {
        1: page_html(
            total=3,
            current=1,
            total_pages=2,
            external_ids=["1", "2"],
        ),
        2: page_html(
            total=3,
            current=2,
            total_pages=2,
            external_ids=["2"],
        ),
    }
    with pytest.raises(RuntimeError, match="repeated a program"):
        list(
            SuwonLibraryProgramSource().crawl(
                PagedFakeClient(pages),  # type: ignore[arg-type]
                window(),
            )
        )

    with pytest.raises(RuntimeError, match="would be partial"):
        list(
            SuwonLibraryProgramSource().crawl(
                PagedFakeClient(pages),  # type: ignore[arg-type]
                window(max_pages=1),
            )
        )


@pytest.mark.parametrize(
    "target",
    [
        "성인 및 교사",
        "어린이집 교사",
        "어린이 교육 지도사",
        "직장인",
        "교원",
        "학부모만",
        "유아교육 지도사",
        "유아 교사",
        "아동 지도사",
        "아동 상담사",
        "성인 가족",
    ],
)
def test_adult_target_overrides_child_word_in_title(target: str) -> None:
    adult_only = page_html(
        total=1,
        current=1,
        total_pages=1,
        external_ids=["9001"],
        title="어린이 독서교육 지도사",
        target=target,
    )

    events = list(
        SuwonLibraryProgramSource().crawl(
            PagedFakeClient({1: adult_only}),  # type: ignore[arg-type]
            window(),
        )
    )

    assert events == []


@pytest.mark.parametrize(
    "target",
    [
        "초등학생",
        "어린이와 보호자",
        "자녀와 함께",
        "가족",
        "보호자 동반",
        "학부모와 어린이",
    ],
)
def test_explicit_child_or_family_target_is_included(target: str) -> None:
    page = SuwonLibraryProgramSource.parse_page(
        page_html(
            total=1,
            current=1,
            total_pages=1,
            external_ids=["9003"],
            title="그림책 교실",
            target=target,
        )
    )

    assert SuwonLibraryProgramSource._candidate(page.facts[0])


def test_targetless_possibility_title_is_not_published() -> None:
    fact = SuwonLibraryProgramSource.parse_page(
        page_html(
            total=1,
            current=1,
            total_pages=1,
            external_ids=["9005"],
            title="그림책 활동가 양성과정",
            target=None,
        )
    ).facts[0]

    assert not SuwonLibraryProgramSource._candidate(fact)


@pytest.mark.parametrize(
    ("title", "target", "expected_min", "expected_max"),
    [
        ("그림책 교실", "6~7세", 6, 7),
        ("책 놀이", "유아", None, None),
        ("책 놀이", "1-2학년", 7, 8),
    ],
)
def test_candidate_events_get_relevance_floor_and_local_age_ranges(
    title: str,
    target: str,
    expected_min: int | None,
    expected_max: int | None,
) -> None:
    fact = SuwonLibraryProgramSource.parse_page(
        page_html(
            total=1,
            current=1,
            total_pages=1,
            external_ids=["9004"],
            title=title,
            target=target,
        )
    ).facts[0]

    assert SuwonLibraryProgramSource._candidate(fact)
    event = SuwonLibraryProgramSource._map(fact)
    assert event.child_relevance_score >= 0.55
    assert (event.age_min, event.age_max) == (expected_min, expected_max)


@pytest.mark.parametrize(
    ("event_period", "event_time", "message"),
    [
        (None, "10:00 ~ 12:00", "missing or unparseable"),
        ("일정 미정", "10:00 ~ 12:00", "missing or unparseable"),
        ("2026.13.01 ~ 2026.13.02", "10:00 ~ 12:00", "invalid date"),
        ("2026.08.02 ~ 2026.08.01", "10:00 ~ 12:00", "ends before"),
        ("2026.08.01 ~ 2026.08.02", "12:00 ~ 10:00", "ends before"),
    ],
)
def test_event_date_is_required_and_chronology_is_validated(
    event_period: str | None,
    event_time: str | None,
    message: str,
) -> None:
    html = page_html(
        total=1,
        current=1,
        total_pages=1,
        external_ids=["9002"],
        event_period=event_period,
        event_time=event_time,
    )

    with pytest.raises(RuntimeError, match=message):
        SuwonLibraryProgramSource.parse_page(html)


def test_source_is_public_metadata_only_and_opt_in() -> None:
    source = SuwonLibraryProgramSource()

    assert source.info.enabled_by_default is False
    assert source.info.policy_status == "approved_html"
    assert source.info.official_url.startswith("https://www.suwonlib.go.kr/reserve/")
    notes = (source.info.notes or "").casefold()
    assert "apply" in notes
    assert "login" in notes
    assert "personal" in notes
