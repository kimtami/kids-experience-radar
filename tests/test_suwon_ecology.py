from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.suwon_ecology import SuwonEcologyProgramSource


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def assert_html_allowed(self, url: str) -> None:
        self.calls.append(("robots", url, None))

    def get_text(
        self, url: str, *, params: dict[str, object] | None = None
    ) -> str:
        self.calls.append(("get", url, params))
        if url.startswith(f"{SuwonEcologyProgramSource.LIST_URL}?"):
            page = int(parse_qs(urlparse(url).query)["page"][0])
            return (
                fixture("suwon_ecology_list.html")
                if page == 1
                else fixture("suwon_ecology_empty.html")
            )
        if "10441" in url:
            return fixture("suwon_ecology_detail.html")
        return fixture("suwon_ecology_detail_family.html")


class PagedFakeClient(FakeClient):
    def __init__(self, pages: dict[int, str]) -> None:
        super().__init__()
        self.pages = pages

    def get_text(
        self, url: str, *, params: dict[str, object] | None = None
    ) -> str:
        self.calls.append(("get", url, params))
        if url.startswith(f"{SuwonEcologyProgramSource.LIST_URL}?"):
            assert params is None
            page = int(parse_qs(urlparse(url).query)["page"][0])
            return self.pages[page]
        if "10441" in url:
            return fixture("suwon_ecology_detail.html")
        return fixture("suwon_ecology_detail_family.html")


def window(*, max_pages: int = 3) -> CrawlWindow:
    return CrawlWindow(
        start=datetime(2026, 7, 15, tzinfo=KST),
        end=datetime(2026, 12, 31, 23, 59, 59, tzinfo=KST),
        max_pages=max_pages,
    )


def row_html(
    external_id: str,
    *,
    target: str | None = "초등학생",
    event_period: str = "2026.08.01 ~ 2026.08.02",
    title: str = "어린이 생태체험",
) -> str:
    return (
        "<tr><th scope='row'>1</th><td class='subject'>"
        f"<a href='margorp_02_view.asp?idx={external_id}'>"
        f"{title} {external_id}</a></td>"
        f"<td>{event_period}</td>"
        f"<td>{target or ''}</td><td>10명</td><td>접수중</td></tr>"
    )


def page_html(*, total: int, current: int, rows: list[str]) -> str:
    return (
        f"<div class='page_num_right'>총 <span>{total}</span>건의 게시물</div>"
        "<table class='board_list_pro'><tbody>"
        + "".join(rows)
        + "</tbody></table>"
        f"<div class='board_navi'><span>{current}</span></div>"
    )


def detail_html(
    *,
    target: str,
    event_period: str = "26.08.01 ~ 26.08.02",
    schedule: str = "10시00분~12시00분",
    body: str = "",
    title: str = "어린이 생태교육 지도사",
) -> str:
    return (
        "<div class='view3'><div class='title'>"
        f"<h3><span>제목</span>{title}</h3></div>"
        "<div class='info'><dl>"
        f"<dt>대상</dt><dd>{target}</dd>"
        f"<dt>교육기간</dt><dd>{event_period}</dd>"
        f"<dt>교육시간</dt><dd>{schedule}</dd>"
        "<dt>진행상태</dt><dd>접수중</dd>"
        "</dl></div>"
        f"<div class='substance'>{body}</div></div>"
    )


class AdultDetailClient(PagedFakeClient):
    def __init__(self, pages: dict[int, str], target: str = "성인 및 교사") -> None:
        super().__init__(pages)
        self.target = target

    def get_text(
        self, url: str, *, params: dict[str, object] | None = None
    ) -> str:
        if "10442" in url:
            self.calls.append(("get", url, params))
            return detail_html(target=self.target)
        return super().get_text(url, params=params)


def test_crawl_maps_public_metadata_and_never_calls_application_paths() -> None:
    source = SuwonEcologyProgramSource()
    client = FakeClient()

    events = list(source.crawl(client, window()))  # type: ignore[arg-type]

    assert [event.external_id for event in events] == ["10441", "10440"]
    list_url = client.calls[0][1]
    assert client.calls[0] == ("robots", list_url, None)
    assert client.calls[1] == ("get", list_url, None)
    assert list_url == f"{source.LIST_URL}?page=1"
    assert all("margorp_02_write" not in url for _, url, _ in client.calls)
    assert all("margorp_02_result" not in url for _, url, _ in client.calls)
    assert all("login" not in url.casefold() for _, url, _ in client.calls)
    assert all("10439" not in url for _, url, _ in client.calls)

    child = events[0]
    assert child.title == "으라차차생물탐험대"
    assert child.detail_url.endswith("margorp_02_view.asp?idx=10441")
    assert child.event_start == datetime(2026, 8, 4, 9, 30, tzinfo=KST)
    assert child.event_end == datetime(2026, 8, 7, 11, 30, tzinfo=KST)
    assert child.age_min == 7 and child.age_max == 10
    assert child.price_min == 20_000
    assert child.price_text == "20,000원"
    assert child.phone == "031-295-4545"
    assert child.address is None  # multi-site program: do not invent one address
    assert set(child.raw) <= source.PUBLIC_RAW_FIELDS

    family = events[1]
    assert family.price_min == 0
    assert family.address == "경기도 수원시 권선구 서수원로577번길 225"
    assert family.status == "접수중"


def test_empty_list_is_valid_and_dom_drift_fails_closed() -> None:
    assert SuwonEcologyProgramSource.parse_list(
        fixture("suwon_ecology_empty.html")
    ) == []
    assert list(
        SuwonEcologyProgramSource().crawl(
            PagedFakeClient({1: fixture("suwon_ecology_empty.html")}),  # type: ignore[arg-type]
            window(),
        )
    ) == []
    with pytest.raises(RuntimeError, match="Suwon ecology list"):
        SuwonEcologyProgramSource.parse_list("<html>maintenance</html>")
    with pytest.raises(RuntimeError, match="invalid program row"):
        SuwonEcologyProgramSource.parse_list(
            "<div class='page_num_right'>총 <span>1</span>건의 게시물</div>"
            "<table class='board_list_pro'><tbody><tr><td>broken</td></tr>"
            "</tbody></table><div class='board_navi'><span>1</span></div>"
        )
    with pytest.raises(RuntimeError, match="Suwon ecology detail"):
        SuwonEcologyProgramSource.parse_detail("<html>changed</html>")
    with pytest.raises(RuntimeError, match="required metadata missing"):
        SuwonEcologyProgramSource.parse_detail(
            "<div class='view3'><div class='title'><h3>제목</h3></div>"
            "<div class='info'><dl><dt>대상</dt><dd>초등학생</dd>"
            "</dl></div></div>"
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
def test_adult_target_overrides_child_title_before_and_after_detail(
    target: str,
) -> None:
    assert not SuwonEcologyProgramSource._candidate(
        "어린이 생태교육 지도사",
        target,
    )

    pages = {
        1: page_html(total=1, current=1, rows=[row_html("10442")]),
    }
    client = AdultDetailClient(pages, target)
    events = list(
        SuwonEcologyProgramSource().crawl(
            client,  # type: ignore[arg-type]
            window(),
        )
    )

    assert events == []
    assert any("10442" in url for method, url, _ in client.calls if method == "get")


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
    assert SuwonEcologyProgramSource._candidate("숲의 하루", target)


def test_targetless_child_title_is_not_published() -> None:
    assert not SuwonEcologyProgramSource._candidate("어린이 체험", None)


@pytest.mark.parametrize(
    ("target", "expected_min", "expected_max"),
    [
        ("가족", 5, 13),
        ("6~7세", 6, 7),
        ("1-2학년", 7, 8),
    ],
)
def test_candidate_events_get_relevance_floor_and_local_age_ranges(
    target: str,
    expected_min: int,
    expected_max: int,
) -> None:
    list_fact = SuwonEcologyProgramSource.parse_page(
        page_html(
            total=1,
            current=1,
            rows=[row_html("10444", target=target, title="숲의 하루")],
        )
    ).facts[0]
    detail = SuwonEcologyProgramSource.parse_detail(
        detail_html(target=target, title="숲의 하루")
    )

    assert SuwonEcologyProgramSource._candidate(detail.title, detail.target)
    event = SuwonEcologyProgramSource._map(list_fact, detail)
    assert event.child_relevance_score >= 0.55
    assert (event.age_min, event.age_max) == (expected_min, expected_max)


@pytest.mark.parametrize(
    ("event_period", "message"),
    [
        ("", "missing or unparseable"),
        ("일정 미정", "missing or unparseable"),
        ("2026.13.01 ~ 2026.13.02", "invalid date"),
        ("2026.08.02 ~ 2026.08.01", "ends before"),
    ],
)
def test_list_event_date_is_required_and_validated(
    event_period: str,
    message: str,
) -> None:
    html = page_html(
        total=1,
        current=1,
        rows=[row_html("10443", event_period=event_period)],
    )

    with pytest.raises(RuntimeError, match=message):
        SuwonEcologyProgramSource.parse_page(html)


@pytest.mark.parametrize(
    ("event_period", "message"),
    [
        ("일정 미정", "missing or unparseable"),
        ("26.13.01 ~ 26.13.02", "invalid date"),
        ("26.08.02 ~ 26.08.01", "ends before"),
    ],
)
def test_detail_event_date_is_required_and_validated(
    event_period: str,
    message: str,
) -> None:
    with pytest.raises(RuntimeError, match=message):
        SuwonEcologyProgramSource.parse_detail(
            detail_html(target="초등학생", event_period=event_period)
        )


def test_event_time_chronology_is_validated() -> None:
    with pytest.raises(RuntimeError, match="time ends before"):
        SuwonEcologyProgramSource._event_times(
            ("2026-08-01", "2026-08-02"),
            "12시00분~10시00분",
        )


def test_public_mobile_phone_is_not_stored_as_provider_contact() -> None:
    mobile_only = SuwonEcologyProgramSource.parse_detail(
        detail_html(target="초등학생", body="담당자 010-1234-5678")
    )
    mixed = SuwonEcologyProgramSource.parse_detail(
        detail_html(
            target="초등학생",
            body="담당자 010-1234-5678 / 기관 대표 031-295-4545",
        )
    )

    assert mobile_only.phone is None
    assert mixed.phone == "031-295-4545"


def test_pagination_collects_short_pages_until_official_total() -> None:
    pages = {
        1: page_html(total=2, current=1, rows=[row_html("10441")]),
        2: page_html(total=2, current=2, rows=[row_html("10440")]),
    }

    events = list(
        SuwonEcologyProgramSource().crawl(
            PagedFakeClient(pages),  # type: ignore[arg-type]
            window(),
        )
    )

    assert [event.external_id for event in events] == ["10441", "10440"]


def test_pagination_fails_closed_on_duplicates_exhaustion_and_partial() -> None:
    duplicate_page = page_html(
        total=2,
        current=1,
        rows=[row_html("10441"), row_html("10441")],
    )
    with pytest.raises(RuntimeError, match="duplicate program IDs"):
        SuwonEcologyProgramSource.parse_page(duplicate_page)

    repeated_pages = {
        1: page_html(total=2, current=1, rows=[row_html("10441")]),
        2: page_html(total=2, current=2, rows=[row_html("10441")]),
    }
    with pytest.raises(RuntimeError, match="repeated a program"):
        list(
            SuwonEcologyProgramSource().crawl(
                PagedFakeClient(repeated_pages),  # type: ignore[arg-type]
                window(),
            )
        )

    exhausted_pages = {
        1: page_html(total=2, current=1, rows=[row_html("10441")]),
        2: page_html(total=2, current=2, rows=[]),
    }
    with pytest.raises(RuntimeError, match="ended before"):
        list(
            SuwonEcologyProgramSource().crawl(
                PagedFakeClient(exhausted_pages),  # type: ignore[arg-type]
                window(),
            )
        )

    with pytest.raises(RuntimeError, match="would be partial"):
        list(
            SuwonEcologyProgramSource().crawl(
                PagedFakeClient(exhausted_pages),  # type: ignore[arg-type]
                window(max_pages=1),
            )
        )


def test_source_is_public_detail_only_and_opt_in() -> None:
    source = SuwonEcologyProgramSource()

    assert source.info.enabled_by_default is False
    assert source.info.policy_status == "approved_html"
    notes = (source.info.notes or "").casefold()
    assert "application form" in notes
    assert "login" in notes
    assert "personal-data" in notes
