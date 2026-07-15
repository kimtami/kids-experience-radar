from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

import pytest

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.koagi import KoagiEducationSource


FIXTURES = Path(__file__).parent / "fixtures"


def fixture() -> str:
    return (FIXTURES / "koagi_education_programs.html").read_text(encoding="utf-8")


class FakeClient:
    def __init__(self, html: str) -> None:
        self.html = html
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def assert_html_allowed(self, url: str) -> None:
        self.calls.append(("robots", url, None))

    def get_text(self, url: str, *, params: dict[str, object] | None = None) -> str:
        self.calls.append(("get", url, params))
        return self.html


def test_all_sources_exposes_four_disabled_institutions(monkeypatch) -> None:
    monkeypatch.delenv("KIDS_RADAR_APPROVED_SOURCES", raising=False)
    sources = KoagiEducationSource.all_sources()

    assert len(sources) == 4
    assert len({source.info.source_id for source in sources}) == 4
    assert all(source.info.enabled_by_default is False for source in sources)
    assert all(source.info.policy_status == "reviewed_public_html" for source in sources)
    assert all(source.available() == (True, None) for source in sources)
    assert all("RFC 9309" in (source.info.notes or "") for source in sources)
    assert all("5xx still fail closed" in (source.info.notes or "") for source in sources)


def test_parse_html_maps_only_child_program_and_fact_fields() -> None:
    source = KoagiEducationSource(2)

    events = source.parse_html(fixture())

    assert len(events) == 1
    event = events[0]
    assert event.external_id == "2:28932"
    assert event.title == "숲에서 만나는 여름 곤충"
    assert event.detail_url.endswith(
        "BD_selectReserveEdcPrgrmFrom.do?q_siteSeq=2&q_prgrmNo=28932"
    )
    assert event.apply_start == datetime(2026, 7, 15, 9, 30, tzinfo=KST)
    assert event.apply_end == datetime(2026, 7, 31, 18, 0, tzinfo=KST)
    assert event.event_start == datetime(2026, 8, 2, 10, 0, tzinfo=KST)
    assert event.event_end == datetime(2026, 8, 2, 11, 30, tzinfo=KST)
    assert event.status == "접수중"
    assert event.age_text == "초등학생 동반 가족"
    assert event.age_min == 7 and event.age_max == 13
    assert event.price_text == "5,000원" and event.price_min == 5000
    assert event.provider_name == "국립백두대간수목원"
    assert event.region == "경상북도 봉화군"
    assert event.image_url is None
    assert event.description == "참여자: 개인 · 신청방법: 온라인 · 모집정원: 10 명 · 모집유형: 선착순"
    assert event.raw == {
        "program_id": "28932",
        "site_seq": 2,
        "status": "접수중",
        "application_period": "2026-07-15 (09:30) ~ 2026-07-31 (18:00)",
        "use_period": "2026-08-02 (10:00) ~ 2026-08-02 (11:30)",
        "participant": "개인",
        "price": "5,000원",
        "audience": "초등학생 동반 가족",
        "application_method": "온라인",
        "capacity": "10 명",
        "recruitment_type": "선착순",
        "categories": ["체험", "유료"],
    }


def test_crawl_checks_robots_and_filters_to_window() -> None:
    source = KoagiEducationSource(2)
    client = FakeClient(fixture())
    window = CrawlWindow(
        start=datetime(2026, 8, 1, tzinfo=KST),
        end=datetime(2026, 8, 31, 23, 59, tzinfo=KST),
    )

    events = list(source.crawl(client, window))  # type: ignore[arg-type]

    assert len(events) == 1
    assert client.calls == [
        ("robots", source.list_url, None),
        ("get", source.LIST_URL, {"q_siteSeq": 2}),
    ]


@pytest.mark.parametrize(
    ("html", "message"),
    [
        ("<html></html>", "gallery-poster-edu not found"),
        (
            '<ul class="gallery-items gallery-poster-edu"><li><strong>어린이 체험</strong></li></ul>',
            "no valid program ids parsed",
        ),
    ],
)
def test_parse_html_fails_loudly_on_structure_change(html: str, message: str) -> None:
    with pytest.raises(RuntimeError, match=re.escape(message)):
        KoagiEducationSource(2).parse_html(html)


def test_rejects_unknown_site_sequence() -> None:
    with pytest.raises(ValueError, match="unknown KOAGI site sequence"):
        KoagiEducationSource(99)
