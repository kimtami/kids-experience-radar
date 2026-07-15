import json

import pytest

from kids_experience_radar.policy import assert_html_source_allowed, blocked_reason
from kids_experience_radar.sources.configured_html import ConfiguredHtmlSource, HtmlSourceSpec
from kids_experience_radar.sources.hmoka import HmokaProgramSource
from kids_experience_radar.sources.hyundai_motorstudio import HyundaiMotorstudioKidsWorkshopSource
from kids_experience_radar.sources.kimchikan import KimchikanSource
from kids_experience_radar.sources.leeum_hoam import LeeumHoamProgramSource
from kids_experience_radar.sources.samsung_innovation import SamsungInnovationSource
from kids_experience_radar.tips import load_tip_events


def test_known_private_or_blocked_sources_are_rejected() -> None:
    assert blocked_reason("https://cafe.naver.com/example/1")
    assert blocked_reason("https://www.ggoomgil.go.kr/front/index.do")
    with pytest.raises(ValueError):
        assert_html_source_allowed("https://share.gg.go.kr/list", "approved")
    with pytest.raises(ValueError):
        assert_html_source_allowed("file:///tmp/programs.html", "approved")


def test_pending_html_source_cannot_be_constructed() -> None:
    spec = HtmlSourceSpec.from_dict(
        {
            "source_id": "x",
            "name": "x",
            "owner": "x",
            "list_url": "https://example.org/programs",
            "card_selector": ".card",
            "legal_review_status": "pending",
            "fields": {"title": ".title"},
        }
    )
    with pytest.raises(ValueError):
        ConfiguredHtmlSource(spec)


def test_approved_html_fixture_parses_fact_fields() -> None:
    spec = HtmlSourceSpec.from_dict(
        {
            "source_id": "approved",
            "name": "Approved",
            "owner": "Museum",
            "list_url": "https://example.org/programs",
            "card_selector": ".card",
            "legal_review_status": "approved",
            "fields": {
                "title": ".title",
                "detail_url": {"selector": "a", "attr": "href"},
                "event_start": {"selector": "time", "attr": "datetime"},
                "age_text": ".target",
                "price_text": ".fee",
            },
        }
    )
    source = ConfiguredHtmlSource(spec)
    rows = source.parse_html(
        '<div class="card"><a href="/p/1"><span class="title">초등 미술 체험</span></a>'
        '<time datetime="2026-08-01"></time><span class="target">초등 2학년</span>'
        '<span class="fee">무료</span></div>'
    )
    assert len(rows) == 1
    assert rows[0].detail_url == "https://example.org/p/1"
    assert rows[0].age_min == 8
    assert rows[0].price_min == 0


def test_tip_import_requires_official_not_cafe_url(tmp_path) -> None:
    path = tmp_path / "tips.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"title": "공식 행사", "official_url": "https://museum.example/event/1"}),
                json.dumps({"title": "카페 글", "official_url": "https://cafe.naver.com/x/1"}),
                json.dumps({"title": "잘못된 링크", "official_url": "javascript:alert(1)"}),
            ]
        ),
        encoding="utf-8",
    )
    events, errors = load_tip_events(path)
    assert len(events) == 1
    assert len(errors) == 2


def test_private_collectors_require_exact_runtime_approval(monkeypatch) -> None:
    sources = [
        HyundaiMotorstudioKidsWorkshopSource(),
        SamsungInnovationSource(),
        KimchikanSource(),
        HmokaProgramSource(),
        LeeumHoamProgramSource(),
    ]
    monkeypatch.delenv("KIDS_RADAR_APPROVED_SOURCES", raising=False)
    assert all(source.available()[0] is False for source in sources)

    approved_id = sources[3].info.source_id
    monkeypatch.setenv("KIDS_RADAR_APPROVED_SOURCES", approved_id)
    assert sources[3].available() == (True, None)
    assert all(source.available()[0] is False for source in sources if source is not sources[3])
