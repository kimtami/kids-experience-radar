from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import os
from typing import Iterable
from urllib.parse import unquote

from ..http import PoliteHttpClient
from ..models import CrawlWindow, Event
from ..normalizers import (
    KST,
    child_relevance,
    clean_text,
    parse_age_range,
    parse_datetime,
    parse_price,
    safe_float,
)
from .base import Source, SourceInfo


def _pick(row: dict, aliases: tuple[str, ...]) -> object | None:
    folded = {str(key).replace(" ", "").casefold(): value for key, value in row.items()}
    for alias in aliases:
        value = folded.get(alias.replace(" ", "").casefold())
        if value not in (None, ""):
            return value
    return None


@dataclass(slots=True, frozen=True)
class ODCloudSpec:
    source_id: str
    name: str
    owner: str
    dataset_id: str
    resource_id: str
    official_url: str
    title_fields: tuple[str, ...]
    external_id_fields: tuple[str, ...] = ("순번", "번호", "id")
    external_id_composite_fields: tuple[str, ...] = ()
    provider_fields: tuple[str, ...] = ("기관명", "마을명", "박물관명")
    description_fields: tuple[str, ...] = ("상세정보", "체험상세정보", "내용", "교육내용")
    start_fields: tuple[str, ...] = ("시작일", "교육시작일", "교육시작일자")
    end_fields: tuple[str, ...] = ("종료일", "교육종료일", "교육종료일자")
    apply_start_fields: tuple[str, ...] = ("접수시작일", "신청시작일")
    apply_end_fields: tuple[str, ...] = ("접수종료일", "신청종료일")
    age_fields: tuple[str, ...] = ("교육대상", "대상", "참여대상")
    price_fields: tuple[str, ...] = ("교육비", "수강금액", "참가비", "유무료여부")
    venue_fields: tuple[str, ...] = ("교육장소", "장소", "마을명")
    address_fields: tuple[str, ...] = ("주소", "소재지", "도로명주소")
    region_fields: tuple[str, ...] = ("시도명", "시군구명", "지역")
    lat_fields: tuple[str, ...] = ("위도", "lat", "latitude")
    lon_fields: tuple[str, ...] = ("경도", "lon", "longitude")
    url_fields: tuple[str, ...] = ("신청URL", "예약URL", "홈페이지", "관련사이트")
    default_url: str = "https://www.data.go.kr"
    default_address: str | None = None
    default_region: str | None = None
    enabled_by_default: bool = False
    license_code: str = "OPEN-DATA"
    min_child_score: float | None = None
    extra_defaults: dict[str, str] = field(default_factory=dict)


class ODCloudDatasetSource(Source):
    BASE_URL = "https://api.odcloud.kr/api"

    def __init__(self, spec: ODCloudSpec) -> None:
        self.spec = spec
        self.info = SourceInfo(
            source_id=spec.source_id,
            name=spec.name,
            owner=spec.owner,
            source_type="odcloud_api",
            official_url=spec.official_url,
            license_code=spec.license_code,
            requires_key="DATA_GO_KR_SERVICE_KEY",
            enabled_by_default=spec.enabled_by_default,
            notes="ODCloud auto-converted public dataset; freshness follows the dataset update cycle.",
        )

    @property
    def service_key(self) -> str:
        return unquote(os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip())

    def available(self) -> tuple[bool, str | None]:
        if not self.service_key:
            return False, "DATA_GO_KR_SERVICE_KEY is not set"
        return True, None

    def crawl(self, client: PoliteHttpClient, window: CrawlWindow) -> Iterable[Event]:
        if not self.service_key:
            raise RuntimeError("DATA_GO_KR_SERVICE_KEY is required")
        endpoint = f"{self.BASE_URL}/{self.spec.dataset_id}/v1/uddi:{self.spec.resource_id}"
        page_size = 100
        for page in range(1, window.max_pages + 1):
            payload = client.get_json(
                endpoint,
                params={"page": page, "perPage": page_size, "serviceKey": self.service_key},
            )
            rows = payload.get("data") or []
            for row in rows:
                event = self._map_row(row)
                if (
                    self.spec.min_child_score is not None
                    and event.child_relevance_score < self.spec.min_child_score
                ):
                    continue
                if self._overlaps_window(event, window):
                    yield event
            total = int(payload.get("totalCount") or len(rows))
            if not rows or page * page_size >= total:
                break

    @staticmethod
    def _overlaps_window(event: Event, window: CrawlWindow) -> bool:
        if event.event_start is None and event.event_end is None:
            return True
        start = event.event_start or event.event_end
        end = event.event_end or event.event_start
        assert start is not None and end is not None
        return start <= window.end and end >= window.start

    def _map_row(self, row: dict) -> Event:
        spec = self.spec
        title = clean_text(_pick(row, spec.title_fields)) or "제목 없음"
        description = clean_text(_pick(row, spec.description_fields))
        age_min, age_max, age_text = parse_age_range(_pick(row, spec.age_fields))
        price_raw = _pick(row, spec.price_fields)
        if price_raw not in (None, "") and str(price_raw).replace(",", "").strip().isdigit():
            price_raw = f"{price_raw}원"
        price_min, price_text = parse_price(price_raw)
        start = parse_datetime(_pick(row, spec.start_fields))
        end = parse_datetime(_pick(row, spec.end_fields), end_of_day=True)
        detail_url = clean_text(_pick(row, spec.url_fields)) or spec.default_url
        composite_parts = [
            clean_text(_pick(row, (field_name,)))
            for field_name in spec.external_id_composite_fields
        ]
        composite_parts = [part for part in composite_parts if part]
        raw_external = (
            "|".join(composite_parts)
            if composite_parts
            else clean_text(_pick(row, spec.external_id_fields))
        )
        external_id = raw_external or hashlib.sha256(
            f"{title}|{start}|{detail_url}".encode("utf-8")
        ).hexdigest()[:20]
        return Event(
            source_id=self.info.source_id,
            source_name=self.info.name,
            external_id=external_id,
            title=title,
            detail_url=detail_url,
            provider_name=clean_text(_pick(row, spec.provider_fields)) or spec.owner,
            category="교육·체험",
            description=description,
            event_start=start,
            event_end=end,
            apply_start=parse_datetime(_pick(row, spec.apply_start_fields)),
            apply_end=parse_datetime(_pick(row, spec.apply_end_fields), end_of_day=True),
            age_text=age_text,
            age_min=age_min,
            age_max=age_max,
            price_text=price_text,
            price_min=price_min,
            venue_name=clean_text(_pick(row, spec.venue_fields)),
            address=clean_text(_pick(row, spec.address_fields)) or spec.default_address,
            region=clean_text(_pick(row, spec.region_fields)) or spec.default_region,
            latitude=safe_float(_pick(row, spec.lat_fields)),
            longitude=safe_float(_pick(row, spec.lon_fields)),
            child_relevance_score=child_relevance(title, age_text, description),
            license_code=spec.license_code,
            fetched_at=datetime.now(KST),
            raw=row,
        )


def builtin_odcloud_sources() -> list[ODCloudDatasetSource]:
    specs = [
        ODCloudSpec(
            source_id="odcloud_rural_experiences",
            name="전국 농촌체험휴양마을 체험프로그램",
            owner="한국농어촌공사",
            dataset_id="15148474",
            resource_id="98da324b-82c9-4752-b2c5-a7ed451f2bf6",
            official_url="https://www.data.go.kr/data/15148474/fileData.do",
            title_fields=("체험명",),
            external_id_fields=("순번",),
            provider_fields=("마을명",),
            description_fields=("체험 상세 정보",),
            venue_fields=("마을명",),
            default_url="https://www.welchon.com",
            enabled_by_default=False,
            license_code="OPEN-DATA-NO-RESTRICTION",
        ),
        ODCloudSpec(
            source_id="odcloud_nibr_education",
            name="국립생물자원관 교육프로그램",
            owner="국립생물자원관",
            dataset_id="15149734",
            resource_id="95eb9f7b-6579-4a07-b296-96a98915da59",
            official_url="https://www.data.go.kr/data/15149734/fileData.do",
            title_fields=("프로그램제목", "프로그램명", "교육명"),
            default_url="https://www.nibr.go.kr",
            default_address="인천광역시 서구 환경로 42",
            default_region="인천광역시 서구",
            enabled_by_default=False,
            license_code="KOGL-1",
        ),
        ODCloudSpec(
            source_id="odcloud_mabik_education",
            name="국립해양생물자원관 교육프로그램",
            owner="국립해양생물자원관",
            dataset_id="15154211",
            resource_id="4db63ad6-8c8d-41ba-9e34-9a665a5c4175",
            official_url="https://www.data.go.kr/data/15154211/fileData.do",
            title_fields=("교육과정명", "교육명", "프로그램명"),
            external_id_fields=("교육번호", "순번"),
            default_url="https://www.mabik.re.kr",
            default_address="충청남도 서천군 장항읍 장산로101번길 75",
            default_region="충청남도 서천군",
            enabled_by_default=False,
            license_code="OPEN-DATA-NO-RESTRICTION",
        ),
        ODCloudSpec(
            source_id="odcloud_independence_education",
            name="독립기념관 교육프로그램",
            owner="독립기념관",
            dataset_id="15072463",
            resource_id="32803e7f-994e-4186-8bc7-dc98b16ec0ac",
            official_url="https://www.data.go.kr/data/15072463/fileData.do",
            title_fields=("2026년 교육프로그램", "교육프로그램", "프로그램명"),
            external_id_fields=("구분", "순번"),
            default_url="https://i815.or.kr",
            default_address="충청남도 천안시 동남구 목천읍 독립기념관로 1",
            default_region="충청남도 천안시",
            enabled_by_default=False,
            license_code="OPEN-DATA-NO-RESTRICTION",
        ),
        ODCloudSpec(
            source_id="odcloud_mmca_education",
            name="국립현대미술관 교육프로그램",
            owner="국립현대미술관",
            dataset_id="15156786",
            resource_id="403cab90-843f-4f0a-8db6-aba36edba543",
            official_url="https://www.data.go.kr/data/15156786/fileData.do",
            title_fields=("교육명",),
            provider_fields=("장소",),
            start_fields=("교육시작일",),
            end_fields=("교육종료일",),
            age_fields=("교육대상",),
            venue_fields=("장소상세", "장소"),
            default_url="https://www.mmca.go.kr/educations/educationsList.do",
            enabled_by_default=False,
            license_code="OPEN-DATA",
        ),
        ODCloudSpec(
            source_id="odcloud_suwon_art_education",
            name="수원시립미술관 교육정보",
            owner="경기도 수원시",
            dataset_id="15146620",
            resource_id="008e3876-1816-408f-925b-8873a93873aa",
            official_url="https://www.data.go.kr/data/15146620/fileData.do",
            title_fields=("교육명",),
            external_id_fields=("연번",),
            description_fields=("교육내용",),
            start_fields=("교육시작일",),
            end_fields=("교육종료일",),
            age_fields=("교육대상",),
            venue_fields=("교육장소",),
            url_fields=("바로가기링크",),
            default_url="https://suma.suwon.go.kr/edu/",
            default_region="경기도 수원시",
            enabled_by_default=False,
            license_code="OPEN-DATA-NO-RESTRICTION",
        ),
        ODCloudSpec(
            source_id="odcloud_ulsan_children_themepark",
            name="울산시립어린이테마파크 놀이체험프로그램",
            owner="울산시설공단",
            dataset_id="15087229",
            resource_id="1ec1d801-e1d6-41ed-808c-e92ba7e3e83d",
            official_url="https://www.data.go.kr/data/15087229/fileData.do",
            title_fields=("프로그램명",),
            external_id_fields=("프로그램명",),
            description_fields=("단체 이용 방법", "비고"),
            age_fields=("대상",),
            price_fields=("1인 참가비(원)",),
            venue_fields=("장소",),
            default_url="https://www.kidspark.or.kr/",
            default_region="울산광역시",
            enabled_by_default=False,
            license_code="OPEN-DATA-NO-RESTRICTION",
        ),
        ODCloudSpec(
            source_id="odcloud_nakdong_bioresource_education",
            name="국립낙동강생물자원관 교육정보",
            owner="국립낙동강생물자원관",
            dataset_id="15039055",
            resource_id="cabfba7f-affb-4f21-abdb-b37083067235",
            official_url="https://www.data.go.kr/data/15039055/fileData.do",
            title_fields=("프로그램명",),
            external_id_fields=("프로그램명",),
            external_id_composite_fields=("프로그램명", "교육시작일자"),
            start_fields=("교육시작일자",),
            end_fields=("교육종료일자",),
            apply_start_fields=("교육예약 시작일시",),
            apply_end_fields=("교육예약 종료일시",),
            age_fields=("이용대상",),
            default_url="https://www.nnibr.re.kr/",
            default_address="경상북도 상주시 도남2길 137",
            default_region="경상북도 상주시",
            enabled_by_default=False,
            license_code="OPEN-DATA-NO-RESTRICTION",
            min_child_score=0.2,
        ),
        ODCloudSpec(
            source_id="odcloud_korean_film_museum_education",
            name="한국영화박물관 교육프로그램",
            owner="한국영상자료원",
            dataset_id="15116766",
            resource_id="e2f56c10-6df8-4f20-b85f-dfc5f6295803",
            official_url="https://www.data.go.kr/data/15116766/fileData.do",
            title_fields=("교육명",),
            external_id_fields=("교육명",),
            external_id_composite_fields=("교육명", "교육시작일"),
            description_fields=("교육내용",),
            start_fields=("교육시작일",),
            end_fields=("교육종료일",),
            apply_start_fields=("신청시작일",),
            apply_end_fields=("신청종료일",),
            age_fields=("교육대상",),
            price_fields=("교육비",),
            venue_fields=("교육장소",),
            default_url="https://www.koreafilm.or.kr/museum/education/current",
            default_address="서울특별시 마포구 월드컵북로 400",
            default_region="서울특별시 마포구",
            enabled_by_default=False,
            license_code="OPEN-DATA-NO-RESTRICTION",
            min_child_score=0.2,
        ),
        ODCloudSpec(
            source_id="odcloud_yangcheon_community_courses",
            name="양천구 자치회관 어린이 프로그램",
            owner="서울특별시 양천구",
            dataset_id="15037743",
            resource_id="ee655a86-1c86-4859-896a-8c6675df1f18",
            official_url="https://www.data.go.kr/data/15037743/fileData.do",
            title_fields=("강좌명",),
            external_id_fields=("번호",),
            provider_fields=("교육기관",),
            description_fields=("교육요일",),
            start_fields=("교육시작일",),
            end_fields=("교육종료일",),
            age_fields=("수강대상",),
            price_fields=("수강료",),
            venue_fields=("교육장소", "교육기관"),
            address_fields=("주소",),
            lat_fields=("위도",),
            lon_fields=("경도",),
            default_url="https://www.yangcheon.go.kr/",
            default_region="서울특별시 양천구",
            enabled_by_default=False,
            license_code="OPEN-DATA-NO-RESTRICTION",
            min_child_score=0.2,
        ),
        ODCloudSpec(
            source_id="odcloud_gangjin_celadon_experiences",
            name="고려청자박물관 체험프로그램",
            owner="전라남도 강진군",
            dataset_id="15041050",
            resource_id="087c7782-1799-46b2-972a-8b69387c7c95",
            official_url="https://www.data.go.kr/data/15041050/fileData.do",
            title_fields=("체험프로그램명",),
            external_id_fields=("체험프로그램명",),
            description_fields=("체험소요시간", "안내및문의"),
            price_fields=("체험비용",),
            venue_fields=("고려청자박물관",),
            default_url="https://www.celadon.go.kr/",
            default_address="전라남도 강진군 대구면 청자촌길 33",
            default_region="전라남도 강진군",
            enabled_by_default=False,
            license_code="OPEN-DATA-NO-RESTRICTION",
        ),
    ]
    return [ODCloudDatasetSource(spec) for spec in specs]
