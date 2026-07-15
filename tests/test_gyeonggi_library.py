from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.gyeonggi_library import GyeonggiLibraryProgramSource


FIXTURES = Path(__file__).parent / "fixtures"


def json_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parses_the_official_list_result_list_schema() -> None:
    rows, total_count = GyeonggiLibraryProgramSource.parse_list_page(
        json_fixture("gyeonggi_library_programs_page_1.json")
    )

    assert total_count == 3
    assert [row["REC_KEY"] for row in rows] == ["1381", "1349", "1386"]


def test_parses_the_official_detail_result_data_schema() -> None:
    detail = GyeonggiLibraryProgramSource.parse_detail(
        json_fixture("gyeonggi_library_program_detail.json"), expected_rec_key="1381"
    )

    assert detail["REC_KEY"] == 1381
    assert detail["PROGRAM_TARGET"] == "초등학생과 보호자(60가족)"
    assert "합성 어린이 경제 체험" in detail["PROGRAM_DESC"]


class FakeClient:
    def __init__(self) -> None:
        self.asserted: list[str] = []
        self.posts: list[tuple[str, dict[str, object] | None]] = []

    def assert_html_allowed(self, url: str) -> None:
        self.asserted.append(url)

    def post_json(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        data: dict[str, object] | None = None,
    ) -> Any:
        assert data is None
        self.posts.append((url, params))
        if url == GyeonggiLibraryProgramSource.LIST_ENDPOINT:
            return json_fixture("gyeonggi_library_programs_page_1.json")
        rec_key = str((params or {}).get("rec_key", ""))
        if rec_key == "1381":
            return json_fixture("gyeonggi_library_program_detail.json")
        if rec_key == "1349":
            adult = json_fixture("gyeonggi_library_programs_page_1.json")[
                "RESULT_LIST"
            ][1]
            return {
                "RESULT_CODE": "100",
                "RESULT_DATA": {
                    **adult,
                    "PROGRAM_DESC": (
                        "<p>합성 어린이 생태교육을 다루는 성인 직무 연수입니다.</p>"
                    ),
                },
            }
        if rec_key == "1386":
            return json_fixture("gyeonggi_library_program_detail_family.json")
        raise AssertionError(f"unexpected detail key: {rec_key}")


def test_crawl_filters_adults_and_maps_public_child_program_metadata() -> None:
    source = GyeonggiLibraryProgramSource()
    client = FakeClient()
    window = CrawlWindow(
        start=datetime(2026, 7, 15, tzinfo=KST),
        end=datetime(2026, 8, 31, 23, 59, 59, tzinfo=KST),
        max_pages=2,
    )

    events = list(source.crawl(client, window))  # type: ignore[arg-type]

    assert [event.external_id for event in events] == ["1381", "1386"]
    child = events[0]
    assert child.title.startswith("[합성 초등경제]")
    assert child.detail_url == (
        "https://www.library.kr/ggl/community/events/program-detail/1381"
    )
    assert child.event_start == datetime(2026, 8, 3, 10, 0, tzinfo=KST)
    assert child.event_end == datetime(2026, 8, 3, 12, 0, tzinfo=KST)
    assert child.apply_start == datetime(2026, 7, 21, 10, 0, tzinfo=KST)
    assert child.apply_end == datetime(2026, 7, 31, 23, 55, tzinfo=KST)
    assert child.status == "접수예정"
    assert child.age_text == "초등학생과 보호자(60가족)"
    assert (child.age_min, child.age_max) == (7, 13)
    assert child.price_text == "무료"
    assert child.price_min == 0
    assert child.provider_name == "경기도서관"
    assert child.venue_name == "플래닛 경기홀"
    assert child.address == "경기도 수원시 영통구 도청로 40"
    assert child.region == "경기도 수원시"
    assert child.phone == "031-000-0000"
    assert child.image_url == (
        "https://hcms.kdot.cloud/upload/141674/P/synthetic-child.png"
    )
    assert child.child_relevance_score == 1.0
    assert child.description is None
    assert set(child.raw) <= source.PUBLIC_RAW_FIELDS
    assert "PROGRAM_DESC" not in child.raw
    assert "PROGRAM_DESC_TEXT" not in child.raw
    assert "합성 어린이 경제 체험 설명" not in repr(child.raw)
    assert "MANAGER_NAME" not in child.raw
    assert "WORKER_KEY" not in child.raw
    assert "FIRST_WORK" not in child.raw

    family = events[1]
    assert (family.age_min, family.age_max) == (8, 10)
    assert family.price_min == 5000
    assert family.price_text == "무료 (재료비 5,000원 별도)"

    assert client.posts == [
        (
            source.LIST_ENDPOINT,
            {
                "manage_code": source.MANAGE_CODE,
                "search_type": "all",
                "search_text": "",
                "program_status": "0",
                "user_key": "",
                "display": source.PAGE_SIZE,
                "page_no": 1,
                "orderby_item": "STATUS_PROGRAM_DATE",
                "orderby": "ASC",
            },
        ),
        (source.DETAIL_ENDPOINT, {"rec_key": "1381"}),
        (source.DETAIL_ENDPOINT, {"rec_key": "1349"}),
        (source.DETAIL_ENDPOINT, {"rec_key": "1386"}),
    ]
    assert len(client.asserted) == 4
    list_policy_target = urlsplit(client.asserted[0])
    assert f"{list_policy_target.scheme}://{list_policy_target.netloc}{list_policy_target.path}" == source.LIST_ENDPOINT
    assert parse_qs(list_policy_target.query, keep_blank_values=True) == {
        "manage_code": [source.MANAGE_CODE],
        "search_type": ["all"],
        "search_text": [""],
        "program_status": ["0"],
        "user_key": [""],
        "display": [str(source.PAGE_SIZE)],
        "page_no": ["1"],
        "orderby_item": ["STATUS_PROGRAM_DATE"],
        "orderby": ["ASC"],
    }
    assert client.asserted[1:] == [
        f"{source.DETAIL_ENDPOINT}?rec_key=1381",
        f"{source.DETAIL_ENDPOINT}?rec_key=1349",
        f"{source.DETAIL_ENDPOINT}?rec_key=1386",
    ]
    called_urls = [url for url, _ in client.posts]
    assert all(
        token not in url.casefold()
        for url in called_urls
        for token in ("checkparticipants", "program-apply", "login", "reserve")
    )


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"RESULT_CODE": "500", "TOTAL_COUNT": 0, "RESULT_LIST": []},
        {"RESULT_CODE": "200", "TOTAL_COUNT": "broken", "RESULT_LIST": []},
        {"RESULT_CODE": "200", "TOTAL_COUNT": 1, "RESULT_DATA": []},
        {"RESULT_CODE": "200", "TOTAL_COUNT": 1, "RESULT_LIST": ["broken"]},
        {
            "RESULT_CODE": "200",
            "TOTAL_COUNT": 1,
            "RESULT_LIST": [{"REC_KEY": "1381", "PROGRAM_TITLE": "필드 부족"}],
        },
        {
            "RESULT_CODE": "200",
            "TOTAL_COUNT": 1,
            "RESULT_LIST": [
                {
                    "REC_KEY": "1381",
                    "PROGRAM_TITLE": {"admin": "must not be stringified"},
                    "PROGRAM_START_DATE": "2026-08-03",
                    "PROGRAM_END_DATE": "2026-08-03",
                    "PROGRAM_STATUS": "5",
                }
            ],
        },
    ],
)
def test_list_schema_drift_fails_loudly(payload: object) -> None:
    with pytest.raises(RuntimeError, match="Gyeonggi Library list"):
        GyeonggiLibraryProgramSource.parse_list_page(payload)


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"RESULT_CODE": "200", "RESULT_DATA": {"REC_KEY": 1381}},
        {"RESULT_CODE": "100", "RESULT_DATA": []},
        {"RESULT_CODE": "100", "RESULT_DATA": {"REC_KEY": 9999}},
        {
            "RESULT_CODE": "100",
            "RESULT_DATA": {"REC_KEY": 1381, "PROGRAM_TITLE": "필드 부족"},
        },
        {
            "RESULT_CODE": "100",
            "RESULT_DATA": {
                "REC_KEY": 1381,
                "PROGRAM_TITLE": "중첩 필드",
                "PROGRAM_START_DATE": "2026-08-03",
                "PROGRAM_END_DATE": "2026-08-03",
                "PROGRAM_STATUS": "5",
                "PROGRAM_DESC_TEXT": {"internal": ["must not be retained"]},
            },
        },
    ],
)
def test_detail_schema_drift_fails_loudly(payload: object) -> None:
    with pytest.raises(RuntimeError, match="Gyeonggi Library detail"):
        GyeonggiLibraryProgramSource.parse_detail(
            payload, expected_rec_key="1381"
        )


def test_source_is_keyless_opt_in_and_metadata_only() -> None:
    source = GyeonggiLibraryProgramSource()

    assert source.info.source_id == "gyeonggi_library_programs"
    assert source.info.source_type == "public_json"
    assert source.info.requires_key is None
    assert source.info.enabled_by_default is False
    assert source.info.policy_status == "reviewed_first_party_public_json"
    notes = (source.info.notes or "").casefold()
    assert "checkparticipants" in notes
    assert "login" in notes
    assert "program-apply" in notes


def test_public_contact_filter_keeps_official_landline_and_drops_mobile() -> None:
    source = GyeonggiLibraryProgramSource

    assert source._phone("문의 031-8008-4650") == "031-8008-4650"
    assert source._phone("담당자 010-1234-5678") is None


class UnknownStatusClient(FakeClient):
    def post_json(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        data: dict[str, object] | None = None,
    ) -> Any:
        payload = super().post_json(url, params=params, data=data)
        if url == GyeonggiLibraryProgramSource.DETAIL_ENDPOINT:
            payload["RESULT_DATA"]["PROGRAM_STATUS"] = "99"
        return payload


def test_unknown_program_status_fails_instead_of_mislabeling() -> None:
    source = GyeonggiLibraryProgramSource()
    window = CrawlWindow(
        start=datetime(2026, 8, 1, tzinfo=KST),
        end=datetime(2026, 8, 31, 23, 59, 59, tzinfo=KST),
        max_pages=1,
    )

    with pytest.raises(RuntimeError, match="unknown PROGRAM_STATUS"):
        list(source.crawl(UnknownStatusClient(), window))  # type: ignore[arg-type]


def test_out_of_window_list_rows_do_not_trigger_detail_requests() -> None:
    source = GyeonggiLibraryProgramSource()
    client = FakeClient()
    window = CrawlWindow(
        start=datetime(2026, 9, 1, tzinfo=KST),
        end=datetime(2026, 9, 30, 23, 59, 59, tzinfo=KST),
        max_pages=1,
    )

    assert list(source.crawl(client, window)) == []  # type: ignore[arg-type]
    assert client.posts == [
        (
            source.LIST_ENDPOINT,
            {
                "manage_code": source.MANAGE_CODE,
                "search_type": "all",
                "search_text": "",
                "program_status": "0",
                "user_key": "",
                "display": source.PAGE_SIZE,
                "page_no": 1,
                "orderby_item": "STATUS_PROGRAM_DATE",
                "orderby": "ASC",
            },
        )
    ]


class PagingClient(FakeClient):
    def post_json(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        data: dict[str, object] | None = None,
    ) -> Any:
        if url != GyeonggiLibraryProgramSource.LIST_ENDPOINT:
            return super().post_json(url, params=params, data=data)
        assert data is None
        self.posts.append((url, params))
        fixture = json_fixture("gyeonggi_library_programs_page_1.json")
        page_number = (params or {}).get("page_no")
        if page_number == 1:
            adult = fixture["RESULT_LIST"][1]
            fixture["TOTAL_COUNT"] = 101
            fixture["RESULT_LIST"] = [
                {**adult, "REC_KEY": str(2000 + index)} for index in range(100)
            ]
            return fixture
        if page_number == 2:
            fixture["TOTAL_COUNT"] = 101
            fixture["RESULT_LIST"] = [fixture["RESULT_LIST"][0]]
            return fixture
        raise AssertionError(f"unexpected page: {page_number}")


def test_pages_until_total_count_is_covered() -> None:
    source = GyeonggiLibraryProgramSource()
    client = PagingClient()
    window = CrawlWindow(
        start=datetime(2026, 8, 1, tzinfo=KST),
        end=datetime(2026, 8, 31, 23, 59, 59, tzinfo=KST),
        max_pages=3,
    )

    events = list(source.crawl(client, window))  # type: ignore[arg-type]

    assert [event.external_id for event in events] == ["1381"]
    assert [
        params["page_no"]
        for url, params in client.posts
        if url == source.LIST_ENDPOINT and params is not None
    ] == [1, 2]


class DetailRevealsChildClient(FakeClient):
    ROW = {
        "REC_KEY": "1500",
        "PROGRAM_TITLE": "함께 읽는 그림책",
        "PROGRAM_TARGET": "",
        "PROGRAM_FACILITY_NAME": "이야기방",
        "PROGRAM_START_DATE": "2026-08-20 00:00:00",
        "PROGRAM_END_DATE": "2026-08-20 00:00:00",
        "PROGRAM_START_TIME": "10:00",
        "PROGRAM_END_TIME": "11:00",
        "PROGRAM_APPLY_START_DATE": "2026-08-01 10:00:00",
        "PROGRAM_APPLY_END_DATE": "2026-08-18 18:00:00",
        "PROGRAM_STATUS": "1",
        "PROGRAM_FEE": "0",
        "MATERIAL_COST_YN": "N",
        "MATERIAL_COST": "0",
        "ONLY_OFFLINE_YN": "N",
        "ONLINE_CLOSED": "N",
        "PROGRAM_DESC_TEXT": "그림책을 함께 읽습니다.",
    }

    def post_json(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        data: dict[str, object] | None = None,
    ) -> Any:
        assert data is None
        self.posts.append((url, params))
        if url == GyeonggiLibraryProgramSource.LIST_ENDPOINT:
            return {
                "RESULT_CODE": "200",
                "TOTAL_COUNT": 1,
                "RESULT_LIST": [dict(self.ROW)],
            }
        if url == GyeonggiLibraryProgramSource.DETAIL_ENDPOINT:
            return {
                "RESULT_CODE": "100",
                "RESULT_DATA": {
                    **self.ROW,
                    "PROGRAM_TARGET": "부모와 자녀",
                    "PROGRAM_DESC": "<p>그림책을 함께 읽습니다.</p>",
                },
            }
        raise AssertionError(f"unexpected URL: {url}")


def test_detail_can_reveal_child_target_and_keeps_relevance_above_query_floor() -> None:
    source = GyeonggiLibraryProgramSource()
    window = CrawlWindow(
        start=datetime(2026, 8, 1, tzinfo=KST),
        end=datetime(2026, 8, 31, 23, 59, 59, tzinfo=KST),
        max_pages=1,
    )

    events = list(source.crawl(DetailRevealsChildClient(), window))  # type: ignore[arg-type]

    assert len(events) == 1
    assert events[0].age_text == "부모와 자녀"
    assert events[0].child_relevance_score >= 0.55


class PaginationDriftClient(FakeClient):
    def __init__(self, pages: list[list[dict[str, Any]]], total: int) -> None:
        super().__init__()
        self.pages = pages
        self.total = total

    def post_json(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        data: dict[str, object] | None = None,
    ) -> Any:
        assert url == GyeonggiLibraryProgramSource.LIST_ENDPOINT
        assert data is None
        self.posts.append((url, params))
        page_number = int(str((params or {}).get("page_no")))
        return {
            "RESULT_CODE": "200",
            "TOTAL_COUNT": self.total,
            "RESULT_LIST": self.pages[page_number - 1],
        }


def adult_rows(count: int, *, start_id: int = 2000) -> list[dict[str, Any]]:
    adult = json_fixture("gyeonggi_library_programs_page_1.json")["RESULT_LIST"][1]
    return [{**adult, "REC_KEY": str(start_id + index)} for index in range(count)]


def august_window(*, max_pages: int) -> CrawlWindow:
    return CrawlWindow(
        start=datetime(2026, 8, 1, tzinfo=KST),
        end=datetime(2026, 8, 31, 23, 59, 59, tzinfo=KST),
        max_pages=max_pages,
    )


def test_nonterminal_short_page_fails_loudly() -> None:
    client = PaginationDriftClient(
        [adult_rows(99), adult_rows(2, start_id=3000)], total=101
    )

    with pytest.raises(RuntimeError, match="short page"):
        list(
            GyeonggiLibraryProgramSource().crawl(
                client, august_window(max_pages=2)  # type: ignore[arg-type]
            )
        )


def test_duplicate_rec_key_across_pages_fails_loudly() -> None:
    first_page = adult_rows(100)
    client = PaginationDriftClient(
        [first_page, [{**first_page[0]}]], total=101
    )

    with pytest.raises(RuntimeError, match="duplicate REC_KEY"):
        list(
            GyeonggiLibraryProgramSource().crawl(
                client, august_window(max_pages=2)  # type: ignore[arg-type]
            )
        )


def test_max_pages_cannot_silently_return_a_partial_catalog() -> None:
    client = PaginationDriftClient([adult_rows(100)], total=201)

    with pytest.raises(RuntimeError, match="max_pages"):
        list(
            GyeonggiLibraryProgramSource().crawl(
                client, august_window(max_pages=1)  # type: ignore[arg-type]
            )
        )


class MutatedDetailClient(FakeClient):
    def __init__(self, field: str, value: object) -> None:
        super().__init__()
        self.field = field
        self.value = value

    def post_json(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        data: dict[str, object] | None = None,
    ) -> Any:
        payload = super().post_json(url, params=params, data=data)
        if (
            url == GyeonggiLibraryProgramSource.DETAIL_ENDPOINT
            and str((params or {}).get("rec_key")) == "1381"
        ):
            payload["RESULT_DATA"][self.field] = self.value
        return payload


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("MATERIAL_COST_YN", "UNKNOWN", "MATERIAL_COST_YN"),
        ("ONLY_OFFLINE_YN", "UNKNOWN", "ONLY_OFFLINE_YN"),
        ("ONLINE_CLOSED", "UNKNOWN", "ONLINE_CLOSED"),
        ("MATERIAL_COST", "not-a-price", "MATERIAL_COST"),
        ("PROGRAM_START_DATE", "not-a-date", "invalid PROGRAM_START_DATE"),
        ("PROGRAM_END_TIME", "25:99", "invalid PROGRAM_END_DATE time"),
        (
            "PROGRAM_APPLY_START_DATE",
            "not-a-date",
            "invalid application start",
        ),
    ],
)
def test_detail_flags_prices_and_dates_are_fail_loud(
    field: str, value: object, message: str
) -> None:
    client = MutatedDetailClient(field, value)

    with pytest.raises(RuntimeError, match=message):
        list(
            GyeonggiLibraryProgramSource().crawl(
                client, august_window(max_pages=1)  # type: ignore[arg-type]
            )
        )
