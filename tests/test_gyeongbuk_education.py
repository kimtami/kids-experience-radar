from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from kids_experience_radar.models import CrawlWindow
from kids_experience_radar.normalizers import KST
from kids_experience_radar.sources.gyeongbuk_education import (
    GyeongbukEducationExperienceSource,
)


CONTRACT_PATH = (
    Path(__file__).parents[1]
    / "docs"
    / "research"
    / "fixtures"
    / "gyeongbuk-education-request.json"
)

LIST_HTML = """
<div class="rvelst tbl_st"><table><tbody>
  <tr>
    <td>1</td>
    <td><p class="tit">기관명</p>경상북도교육청 수학문화관</td>
    <td><p class="tit">체험명</p>
      <a class="viewExprnInfo" data-id="401" data-period-id="1002" data-rsSysId="gbemc">
        <span class="pc_mint">초등 3~6학년 가족 수학 체험</span>
      </a>
    </td>
    <td><p class="tit">운영기간</p><p>2026/08/01 ~</p><p>2026/08/31</p></td>
    <td><p class="tit">접수기간</p><p>2026/07/15 09:00:00 ~</p><p>2026/07/31 18:00:00</p></td>
    <td><p class="tit">체험대상</p>초등 3~6학년 가족</td>
    <td><p class="tit">신청대상</p>본인인증</td>
    <td><p class="tit">예약상태</p><a>접수중</a></td>
  </tr>
</tbody></table></div>
"""


def _contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_request_contract_matches_connector_and_is_disabled_by_default() -> None:
    contract = _contract()
    source = GyeongbukEducationExperienceSource()

    assert source.INSTITUTIONS_URL == contract["institution_discovery_request"]["url"]
    assert source.LIST_URL == contract["list_request"]["url"]
    assert source.info.official_url == contract["official_list"]
    assert source.info.enabled_by_default is False

    institutions = source.parse_institutions(contract["live_response_sample_truncated"])
    assert institutions["gbemc"] == "경상북도교육청 수학문화관"
    assert institutions["gbai"] == "경상북도교육청 인공지능교육관"


def test_parses_only_whitelisted_public_list_facts() -> None:
    source = GyeongbukEducationExperienceSource()
    events = source.parse_list_html(
        LIST_HTML,
        institutions={"gbemc": "경상북도교육청 수학문화관"},
    )

    assert len(events) == 1
    event = events[0]
    assert event.external_id == "gbemc:401:1002"
    assert event.title == "초등 3~6학년 가족 수학 체험"
    assert event.provider_name == "경상북도교육청 수학문화관"
    assert event.event_start == datetime(2026, 8, 1, tzinfo=KST)
    assert event.apply_start == datetime(2026, 7, 15, 9, 0, tzinfo=KST)
    assert event.status == "접수중"
    assert event.age_min == 9
    assert event.age_max == 12
    assert set(event.raw) == source.RAW_FACT_FIELDS
    assert "exprnSeq=401" in event.detail_url
    assert "exprnPeriodSeq=1002" in event.detail_url


class _Response:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def json(self) -> object:
        return self._payload


class _FakeClient:
    def __init__(self, contract: dict) -> None:
        self.contract = contract
        self.allowed_urls: list[str] = []
        self.posts: list[tuple[str, dict[str, object] | None]] = []
        self.gets: list[tuple[str, dict[str, object] | None]] = []

    def assert_html_allowed(self, url: str) -> None:
        self.allowed_urls.append(url)

    def post(self, url: str, *, data: dict[str, object] | None = None) -> _Response:
        self.posts.append((url, data))
        return _Response(self.contract["live_response_sample_truncated"])

    def get_text(self, url: str, *, params: dict[str, object] | None = None) -> str:
        self.gets.append((url, params))
        return LIST_HTML


def test_crawl_uses_public_ajax_and_list_only() -> None:
    source = GyeongbukEducationExperienceSource()
    client = _FakeClient(_contract())
    window = CrawlWindow(
        start=datetime(2026, 7, 15, tzinfo=KST),
        end=datetime(2026, 9, 1, tzinfo=KST),
        max_pages=1,
    )

    events = list(source.crawl(client, window))  # type: ignore[arg-type]

    assert len(events) == 1
    assert client.allowed_urls == [source.LIST_URL]
    assert client.posts == [(source.INSTITUTIONS_URL, {"rsType": "exprn"})]
    assert client.gets == [
        (
            source.LIST_URL,
            {"mi": "17609", "srchRsvSttus": "REQST", "currPage": 1},
        )
    ]
