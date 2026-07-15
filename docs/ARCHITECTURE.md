# Architecture

```text
Official APIs / public-data files / policy-approved public lists / official-link tips
                                  │
                                  ▼
                    100 source adapter instances
                                  │
                       normalized Event facts
                                  │
                 ┌────────────────┴───────────────┐
                 ▼                                ▼
          SQLite provenance            optional venue geocoding
     events + crawl_runs + cache          Kakao Local + cache
                 │                                │
                 └────────────────┬───────────────┘
                                  ▼
                   status + age + price + radius
                                  │
                                  ▼
                    cross-source deduplication
                                  │
                  ┌───────────────┼──────────────┐
                  ▼               ▼              ▼
             FastAPI/CLI      stdio MCP    daily digest/webhook
```

수집·위치 보강·조회·발송을 분리한다. 한 크롤러가 실패해도 기존 데이터 조회는 가능하고, 알림 실패가 다음 수집을 막지 않는다.

MCP는 같은 `EventStore`, 레지스트리, 수집 엔진을 직접 재사용한다. 조회 도구는 SQLite
read-only 연결을 사용하고 원천 `raw`를 반환하지 않는다. 네트워크 갱신은 기본 비활성,
정확한 source ID allowlist가 있는 경우에만 기존 정책 게이트를 거쳐 실행한다. MCP는
스케줄러를 대체하지 않으므로 launchd/cron 일일 수집은 그대로 유지한다.

## Source registry

`registry.py`는 100개의 고유 `source_id`를 등록한다.

- 공식 API/공공데이터: 키 요구 여부를 `requires_key`로 표시
- 공공 HTML: 기본 비활성, 실행 직전 `robots.txt` 확인. 명확한 404/410만 RFC 9309에 따라 규칙 없음으로 보고, 5xx·WAF·모호한 HTML은 fail-closed
- 민간 공개 목록: 기본 비활성 + `KIDS_RADAR_APPROVED_SOURCES`의 정확한 ID 필요
- 모호한 비-robots HTML을 반환하는 소스: source 승인과 별도의 `KIDS_RADAR_ROBOTS_OVERRIDE_SOURCES` 확인이 모두 필요. 실제 `Disallow`는 override 불가
- 정책 검토 대기: `policy_status`로 표시하고 네트워크 요청 전 또는 robots 검사에서 중단
- 범용 HTML: 별도 설정에서 `legal_review_status=approved`일 때만 구성 가능

`kidradar sources`는 정적 정보와 현재 환경의 실행 가능 여부를, `kidradar doctor`는 기본 실행 소스가 준비됐는지를 보여준다. 100개 전체 메타데이터는 `docs/CONNECTOR_REGISTRY.csv`에 고정 스냅샷으로 내보낸다.

## 현재 테이블

### `events`

- `(source_id, external_id)`와 `uid`: 출처 내부 증분 갱신
- `canonical_key`: 제목 + 장소 + 회차 날짜 기반 교차 출처 중복 후보
- 행사/접수 시각, 대상 연령, 가격, 상태, 장소, 주소·좌표
- `first_seen`, `last_seen`, `content_hash`: 신규·변경 알림 판단
- `raw_json`: 허용된 원천 필드와 추적용 사실 데이터

### `crawl_runs`

소스별 시작/종료 시각, fetched/stored/changed/skipped, 오류를 기록한다. API 키가 포함된 전체 URL은 오류 문자열에 넣지 않는다.

### `geocoding_cache`

공개 행사장 주소, 공급자, 일치 주소, 좌표, 정밀도, 조회 시각을 저장한다. 같은 주소를 매일 다시 외부 API로 보내지 않는다. 부모의 검색 좌표는 이 테이블에 저장하지 않는다.

## 수집 계약

각 어댑터는 최소한 다음을 보장한다.

```text
source_id, external_id, title, detail_url, provider_name
event_start/end, apply_start/end, status
age_text/min/max, price_text/min
venue_name, address/region, latitude/longitude
child_relevance_score, fetched_at, raw
```

API 응답 구조가 바뀌면 빈 정상 결과와 구조 파손을 구분한다. MODU·KOAGI·교육청·지자체·국립공원·KYWA·민간 공개 JSON/HTML 테스트는 필수 컨테이너나 키가 사라질 때 조용히 0건을 저장하지 않고 실패한다. 페이지가 100건을 넘는 HMOKA·리움 통합 목록도 2페이지 계약 테스트가 있다.

## 위치 처리

1. 공식 응답 좌표를 최우선으로 사용한다.
2. 주소만 있으면 `kidradar geocode`가 행사장 주소만 Kakao Local에 보낸다.
3. 캐시된 좌표는 다음 원천 갱신에서 좌표가 비어 있어도 보존한다.
4. 좌표 없는 오프라인 행사는 기본 반경 결과에서 제외하고 `--include-unknown-location`일 때만 표시한다.
5. 온라인 행사는 좌표 없이도 별도 플래그로 표시할 수 있다.

사용자의 기기 위치·이동경로·아이 학교는 수집 모델에 없다. 검색 중심점을 서버에 장기 저장하는 기능도 포함하지 않는다.

## 중복 판정

현재 단계:

1. 같은 `source_id + external_id`는 갱신
2. 제목 정규화 + 장소/주소/지역 + 행사 시작 시각(분 단위)으로 `canonical_key` 생성
3. 조회 시 같은 canonical key 중 관련도가 높은 행 하나를 선택

오전/오후, 날짜가 다른 회차는 별도 이벤트다. 같은 날짜의 11:30·14:00도 합치지 않는다. 날짜만 있는 원천과 시각까지 있는 원천의 교차 중복은 현재 자동 병합하지 않고 출처별 사실을 보존한다. ODCloud에서 프로그램명이 같고 날짜가 다른 행은 복합 external ID로 보존한다.

운영 확장 시에는 다음 세 모델로 분리한다.

- `experience_series`: 프로그램 정체성, 주최, 대상
- `sessions`: 회차별 행사·접수 시각, 정원, 상태, 가격
- `venues`: 정규화 주소, 좌표, 지오코딩 공급자·정밀도

## 일일 파이프라인

```text
01:00 approved sources crawl
01:20 missing venue addresses geocode from cache/API
01:30 source count/null/date anomaly checks
07:00 user radius/age/price/day filters
07:01 official status freshness check where permitted
07:05 digest generation and business-message/email/push handoff
```

첫 수집은 모든 행이 신규이므로 발송은 두 번째 정상 수집부터 시작한다. `changed`가 0인지 확인해 `fetched_at`만 달라져 재알림되는 문제를 방지한다.

조회·다이제스트는 기본적으로 `last_seen`이 48시간 이내인 행만 사용한다. 한 소스가 장기간 실패했을 때 과거의 `접수중` 상태가 계속 노출되는 것을 막기 위한 상한이며, 운영자가 원인 조사 목적으로만 명시적으로 해제할 수 있다. HTTP 리디렉션은 자동 추적하지 않고 한 단계씩 검사하며, 다른 origin으로 이동하면 중단하고 같은 origin의 새 경로도 robots 규칙을 다시 평가한다.

## 다음 운영 단계

- API 키 발급 후 22개 key-gated 소스의 라이브 계약 테스트
- 남은 P0/P1 후보는 숲체원·과학관·공통 CMS 계열부터 어댑터 추가
- 기관별 서면 수집 범위·요청 주기·삭제 창구 기록
- 발송 직전 모집 상태 재검증과 이미 발송한 회차 기록
- 수집량 급변, null 비율, 미래/과거 비율, 마지막 성공 시각 대시보드
- 사용자 계정이 필요해질 때 위치·아동정보 최소화와 보유기간 별도 설계
