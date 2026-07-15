from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.goyang_children_museum import (
    GoyangChildrenMuseumCityNewsSource,
    GoyangNewsPost,
)


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def window() -> CrawlWindow:
    return CrawlWindow(
        start=datetime(2026, 7, 15, tzinfo=KST),
        end=datetime(2026, 11, 30, 23, 59, 59, tzinfo=KST),
        max_pages=1,
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
        if url == GoyangChildrenMuseumCityNewsSource.LIST_URL:
            return fixture("goyang_children_museum_list.html")
        assert url == GoyangChildrenMuseumCityNewsSource.DETAIL_URL
        assert params is not None
        return fixture(
            {
                "20260521170309845": "goyang_children_museum_detail_season.html",
                "20260515135041411": "goyang_children_museum_detail_mind.html",
            }[str(params["q_bbscttSn"])]
        )

    def post(self, *_: object, **__: object) -> None:
        raise AssertionError("this source must never POST")


def test_crawl_emits_future_child_facts_using_city_news_get_only() -> None:
    source = GoyangChildrenMuseumCityNewsSource()
    client = FakeClient()

    events = list(source.crawl(client, window()))  # type: ignore[arg-type]

    sessions = [event for event in events if "칠석달" in event.title]
    assert [event.event_start for event in sessions] == [
        datetime(2026, 8, 1, tzinfo=KST),
        datetime(2026, 8, 2, tzinfo=KST),
        datetime(2026, 8, 15, tzinfo=KST),
        datetime(2026, 8, 16, tzinfo=KST),
    ]
    assert all(event.event_end is not None and event.event_end.hour == 23 for event in sessions)
    assert all(event.age_text == "초등학생 2~4학년" for event in sessions)
    assert all((event.age_min, event.age_max) == (8, 10) for event in sessions)
    assert all(event.price_min is None and event.price_text is None for event in sessions)
    assert all(event.status == "모집예정" for event in sessions)
    assert all(event.address == "경기도 고양시 덕양구 화중로 26" for event in sessions)
    assert all(event.raw["application_timing"] == "7월 중" for event in sessions)

    ongoing = [event for event in events if "일상 속 뮤지엄" in event.title]
    assert len(ongoing) == 1
    assert ongoing[0].event_start == datetime(2026, 5, 27, tzinfo=KST)
    assert ongoing[0].event_end == datetime(2026, 11, 25, 23, 59, 59, tzinfo=KST)
    assert ongoing[0].status == "운영중"
    assert "초등학생" in (ongoing[0].age_text or "")
    assert ongoing[0].phone == "031-839-0329"

    assert all(
        event.event_end is not None and event.event_end >= window().start
        for event in events
    )
    assert all(event.detail_url.startswith(source.DETAIL_URL) for event in events)
    assert all(set(event.raw) <= source.PUBLIC_RAW_FIELDS for event in events)
    assert not any(
        token in str(event.raw).casefold()
        for event in events
        for token in ("<p", "<img", "webview", "filedownload", "goyangcm.or.kr")
    )

    serialized_calls = repr(client.calls).casefold()
    assert "goyangcm.or.kr" not in serialized_calls
    assert not any(
        token in serialized_calls
        for token in ("/login", "/apply", "filedownload", "/component/file", "/www/user/bbs")
    )
    assert {method for method, _, _ in client.calls} <= {"robots", "get"}
    list_policy_targets = [
        url
        for method, url, _ in client.calls
        if method == "robots" and url.startswith(source.LIST_URL)
    ]
    assert len(list_policy_targets) == 1
    assert "q_bbsCode=1090" in list_policy_targets[0]
    assert "q_searchKey=1000" in list_policy_targets[0]
    assert "q_searchVal=%EA%B3%A0%EC%96%91" in list_policy_targets[0]
    assert "q_currPage=1" in list_policy_targets[0]
    detail_gets = [call for call in client.calls if call[1] == source.DETAIL_URL]
    assert len(detail_gets) == 2
    assert all(call[2] and call[2]["q_bbsCode"] == "1090" for call in detail_gets)


def test_backfill_window_uses_observation_time_for_program_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = GoyangChildrenMuseumCityNewsSource()
    observed_at = datetime(2026, 8, 1, 12, tzinfo=KST)
    monkeypatch.setattr(source, "_now", lambda: observed_at)
    backfill = CrawlWindow(
        start=datetime(2026, 1, 1, tzinfo=KST),
        end=datetime(2026, 11, 30, 23, 59, 59, tzinfo=KST),
        max_pages=1,
    )

    events = list(source.crawl(FakeClient(), backfill))  # type: ignore[arg-type]

    ongoing = next(event for event in events if "일상 속 뮤지엄" in event.title)
    assert ongoing.status == "운영중"


def test_program_identity_prevents_same_article_same_date_collisions() -> None:
    source = GoyangChildrenMuseumCityNewsSource
    post = GoyangNewsPost(
        post_id="20260521170309845",
        title="고양어린이박물관, 세시풍속 교육 ‘단오·칠석’ 참가자 모집",
        detail_url=source._canonical_detail("20260521170309845", "") or "",
        department="문화예술과",
        published_date="2026-05-21",
        estn_column="",
    )
    facts = source.parse_detail(
        fixture("goyang_children_museum_detail_season.html"), post
    )
    danoh = next(fact for fact in facts if fact.label == "단오")
    chilseok = next(fact for fact in facts if fact.label == "칠석")
    same_session = datetime(2026, 8, 1, tzinfo=KST)

    events = [
        source._map(
            fact,
            reference=datetime(2026, 7, 15, tzinfo=KST),
            session_start=same_session,
        )
        for fact in (danoh, chilseok)
    ]

    assert events[0].external_id != events[1].external_id
    assert all(event.external_id.endswith(":20260801") for event in events)

    corrected = replace(
        chilseok,
        program_name="표시 제목 교정",
        schedule_text="8월 1일 운영 문구 교정",
        audience="초등학생 2~4학년 20명",
    )
    corrected_event = source._map(
        corrected,
        reference=datetime(2026, 7, 15, tzinfo=KST),
        session_start=same_session,
    )
    assert corrected_event.external_id == events[1].external_id


def test_public_contact_filter_drops_mobile_numbers() -> None:
    source = GoyangChildrenMuseumCityNewsSource

    assert source._phone("문의 031-839-0329") == "031-839-0329"
    assert source._phone("담당자 010-1234-5678") is None


@pytest.mark.parametrize(
    "audience",
    [
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
def test_adult_professional_audiences_are_not_child_participants(
    audience: str,
) -> None:
    assert not GoyangChildrenMuseumCityNewsSource._has_child_participant(audience)


@pytest.mark.parametrize(
    "audience",
    [
        "초등학생",
        "어린이와 보호자",
        "자녀와 함께",
        "가족",
        "만 6~8세",
        "학부모와 어린이",
    ],
)
def test_explicit_child_or_family_audiences_are_kept(audience: str) -> None:
    assert GoyangChildrenMuseumCityNewsSource._has_child_participant(audience)


def test_crawl_fails_before_details_when_max_pages_would_truncate_results() -> None:
    class TruncatedClient(FakeClient):
        def get_text(
            self, url: str, *, params: dict[str, object] | None = None
        ) -> str:
            self.calls.append(("get", url, params))
            assert url == GoyangChildrenMuseumCityNewsSource.LIST_URL
            return fixture("goyang_children_museum_list.html").replace(
                "총 <strong>2</strong>건 (1 / 1page)",
                "총 <strong>13</strong>건 (1 / 2page)",
            )

    source = GoyangChildrenMuseumCityNewsSource()
    client = TruncatedClient()

    with pytest.raises(RuntimeError, match="max_pages is smaller"):
        list(source.crawl(client, window()))  # type: ignore[arg-type]

    assert [call[1] for call in client.calls if call[0] == "get"] == [
        source.LIST_URL
    ]


def test_list_contract_rejects_unsafe_rows_and_fails_loud_on_drift() -> None:
    source = GoyangChildrenMuseumCityNewsSource

    posts = source.parse_list(fixture("goyang_children_museum_list.html"))
    assert [post.post_id for post in posts] == [
        "20260521170309845",
        "20260515135041411",
    ]
    assert all(post.detail_url.startswith(source.DETAIL_URL) for post in posts)
    assert all("login" not in post.detail_url for post in posts)

    with pytest.raises(RuntimeError, match="Goyang city news list"):
        source.parse_list("<html><body>changed</body></html>")
    with pytest.raises(RuntimeError, match="invalid row"):
        source.parse_list(
            "<p class='bbs-total'>총 <strong>1</strong>건 (1 / 1page)</p>"
            "<table class='table-list'><tbody><tr><td>broken</td></tr></tbody></table>"
        )

    unsafe_among_valid = fixture("goyang_children_museum_list.html").replace(
        "20260515135041411", "../../login"
    )
    with pytest.raises(RuntimeError, match="invalid row"):
        source.parse_list(unsafe_among_valid)


def test_detail_contract_ignores_mobile_assets_and_fails_loud_on_drift() -> None:
    source = GoyangChildrenMuseumCityNewsSource
    post = GoyangNewsPost(
        post_id="20260521170309845",
        title="고양어린이박물관, 세시풍속 교육 ‘단오·칠석’ 참가자 모집",
        detail_url=source._canonical_detail("20260521170309845", "") or "",
        department="문화예술과",
        published_date="2026-05-21",
        estn_column="",
    )

    facts = source.parse_detail(fixture("goyang_children_museum_detail_season.html"), post)

    assert [fact.program_name for fact in facts if fact.label == "칠석"] == [
        "한땀한땀~ 칠석달!"
    ]
    chisok = next(fact for fact in facts if fact.label == "칠석")
    assert [value.date().isoformat() for value in chisok.session_starts] == [
        "2026-08-01",
        "2026-08-02",
        "2026-08-15",
        "2026-08-16",
    ]
    assert chisok.price_min is None
    assert "12월 31일" not in repr(facts)
    assert "goyangcm.or.kr" not in repr(facts)

    with pytest.raises(RuntimeError, match="Goyang city news detail"):
        source.parse_detail("<html><h3 class='article-subject'>changed</h3></html>", post)


@pytest.mark.parametrize(
    ("post_id", "estn_column"),
    [
        ("../../login", ""),
        ("1234567890123", ""),
        ("123456789012345678901", ""),
        ("20260521170309845", "../../login"),
        ("20260521170309845 OR 1=1", "All"),
    ],
)
def test_canonical_detail_rejects_non_numeric_or_non_allowlisted_values(
    post_id: str, estn_column: str
) -> None:
    assert GoyangChildrenMuseumCityNewsSource._canonical_detail(
        post_id, estn_column
    ) is None


def test_canonical_detail_accepts_only_reviewed_public_variants() -> None:
    source = GoyangChildrenMuseumCityNewsSource

    for estn_column in ("", "All", "Y"):
        url = source._canonical_detail("20260521170309845", estn_column)
        assert url is not None
        assert url.startswith(source.DETAIL_URL)
        assert "q_bbsCode=1090" in url
        assert "q_bbscttSn=20260521170309845" in url


def test_source_is_opt_in_and_describes_non_actioning_boundary() -> None:
    source = GoyangChildrenMuseumCityNewsSource()

    assert source.info.source_id == "goyang_children_museum_city_news"
    assert source.info.enabled_by_default is False
    assert source.info.policy_status == "approved_html"
    notes = (source.info.notes or "").casefold()
    for token in ("goyang city news", "login", "application", "attachment", "image"):
        assert token in notes
