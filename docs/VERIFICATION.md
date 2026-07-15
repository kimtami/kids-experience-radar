# Verification record

검증일: **2026-07-15 (Asia/Seoul)**

## 최종 자동 검증

```text
pytest:       310 passed
ruff:         All checks passed
compileall:   success
package:      sdist + wheel build success
catalog:      234 rows = regional 60 + public 90 + private 84
primary URLs: 222 unique
mapped rows:  70 rows / 69 unique connector IDs
registry:     100 unique registered source IDs
defaults:     4 (3 Seoul sample sources + GGC official Open API)
key-gated:   25 (3 default + 22 explicit opt-in)
no-key opt-in:74
Gyeonggi deep discovery: 51 rows / 28 official SNS URLs
Gyeonggi status: implemented 24 / adapter 19 / manual 7 / policy hold 1
MCP:          6 tools / 2 resources / 1 prompt, stdio session success
```

FastAPI `TestClient`가 현재 설치된 Starlette에서 `httpx2` 전환 예정이라는
외부 라이브러리 deprecation warning 1개를 출력하지만 테스트 실패나 제품 코드
경고는 아니다.

310개 계약 테스트는 다음을 포함한다.

- 서울 API 필드·좌표·접수/행사 시각
- 문화포털 XML, TourAPI 페이지네이션·오류, 공유누리 JSON/XML
- KOPIS 31일 구간·아동공연, e청소년 초등 필터, 산림교육 XML
- 전국 평생학습강좌·문화축제 표준 API
- 전남도립미술관 목록/상세, ODCloud 11종과 날짜별 복합 ID
- MODU 14관·KOAGI 4기관·경북교육청 목록 DOM 및 구조 파손 fail-loud
- 교육청 4곳의 목록/정보 상세, 외부 링크 비호출, 순수 유아·교원 행 제외
- 국립공원 22곳의 공개 fragment 페이지네이션, 성인 제외, NetFunnel/예약 비호출
- KYWA 국립청소년시설 7곳의 공개 JSON 화이트리스트와 내부·개인 필드 폐기
- 지자체 6곳의 세 공통 DOM 계열, 날짜·대상·위치·가격, 금지 endpoint 계약
- 민간 공개 목록 5종의 승인 전 네트워크 차단과 사실 필드 화이트리스트
- GGC·경기문화재단·`경기,장`·수원시·수원문화재단·수원 3개 박물관·삼성 이노베이션 뮤지엄의 대상/가격/날짜/장소 계약
- 수원도서관·수원생태환경체험교육관·경기도서관의 전체 페이지 수·중복·날짜·아동 대상·공개 필드 계약
- 고양시 뉴스 대체면의 10페이지 완전성·안전한 기사 ID·고정 식별자·현재시각 상태 판정·박물관 원도메인 미호출 계약
- 삼성의 프로그램 운영 범위와 실제 회차 분리, 같은 날 시간별 회차 보존, 일정 DOM 변경 시 fail-loud, source 승인과 robots 모호성 확인의 이중 게이트
- Kakao 주소 응답 매핑·SQLite 지오코딩 캐시·다음 수집 시 좌표 보존
- 가격·학년·거리·중복·상태 필터, 48시간 freshness 상한, 다이제스트, FastAPI 조회
- 경로별 robots 캐시, RFC 9309의 robots 404/410 no-rules, 5xx/WAF fail-closed, same-origin 재검사와 cross-origin redirect 차단
- 234행 CSV/JSON, 수원·경기 51행 심층 원장, 민간 정책 9/56/14/5, 100개 registry ID
- README·아키텍처·카탈로그 요약의 레지스트리/매핑 수량 드리프트, 수원·경기 일일 plist의 공개 12개 소스와 삼성 승인 분리 계약
- MCP 인메모리·실제 stdio initialize/call, 도구 JSON Schema 상한, 위치 커서, `raw`·비밀키 비노출, 없는 DB 미생성, 수집 이중 승인 계약

## MCP 프로토콜 검증

공식 Python SDK `mcp==1.28.1`의 인메모리 연결과 별도 stdio subprocess 연결을 모두
실행했다. `uv run --directory <project> kidradar-mcp`로 시작한 서버에서 도구 6개,
리소스 2개, 프롬프트 1개를 발견하고 `get_radar_status`와
`search_nearby_experiences`의 structured output을 확인했다.

- 프로젝트 `.mcp.json`, Claude Desktop JSON, Codex TOML 예시 파싱 성공
- 조회 도구 `readOnlyHint=true`, 갱신 도구 `readOnlyHint=false/openWorldHint=true`
- 위도·경도·반경·limit·페이지·source 배열 상한이 MCP JSON Schema에 포함
- 검색·단건·다이제스트 응답에서 원천 `raw` 제거
- DB가 없을 때 조회 도구가 DB나 상위 디렉터리를 만들지 않음
- 갱신은 `KIDS_RADAR_MCP_ALLOW_CRAWL=1`과 정확한 source allowlist가 모두 없으면 차단
- 오류 문자열의 키·토큰 값은 `[REDACTED]`로 치환

## 수원·경기 실행 커넥터 라이브 감사

2026-07-15 KST에 공개 목록·공개 정보 상세만 실조회했다. 건수는 접수 변화와 조회 창·페이지 상한에 따라 달라지므로 합계를 서비스 재고처럼 해석하지 않으며, 경기문화재단 통합 목록과 `경기,장`처럼 겹칠 수 있는 행도 단순 합산하지 않는다.

| source ID | 당일 관측 | 비고 |
|---|---:|---|
| `ggc_gyeonggi_child_events` | 3 | GGC 공식 Open API |
| `ggcf_affiliate_child_programs` | 77 | 행사·교육·전시 통합; `경기,장` 전용 행 제외 |
| `ggcf_gyeonggi_jang_programs` | 1 | 만 5세 이상·무료 프로그램 공식 상세 확인 |
| `suwon_education_experience` | 88~92 | 페이지 상한과 재검증 시점에 따라 변동 |
| `suwon_culture_foundation_education` | 12~13 | 월간 중복 제거 후 공식 상세 확인 |
| 수원박물관 3개 source ID | 5 | SW 1·GG 2·HS 2; 간헐적 robots/호스트 timeout이면 fail-closed |
| `suwon_library_child_programs` | 67~71 | 공식 통합예약 전 페이지; 재검증 시 모집 변화 반영 |
| `suwon_ecology_child_programs` | 3 | 공식 공개 목록·상세 |
| `goyang_children_museum_city_news` | 5 | 99개 기사/10페이지 전체 검색 후 기간 내 구조화 세션; 9분 8초, 오류 0 |
| `gyeonggi_library_programs` | 12 | 공식 프로그램 JSON 목록·상세 |
| `samsung_innovation_education` | 15회차 | 같은 DB 두 번째 실행 `changed=0`; 운영 범위가 아닌 상세 회차 기준 |

삼성은 공개 GET 파서가 동작해도 기본·공공 일일 프로필에서 제외한다. `KIDS_RADAR_APPROVED_SOURCES`와 `KIDS_RADAR_ROBOTS_OVERRIDE_SOURCES`에 모두 정확한 source ID가 있을 때만 네트워크를 허용하며, 실제 `Disallow`는 override하지 않는다. 수원·경기 공개 소스 12개는 `config/com.kidsradar.suwon-gyeonggi.daily.plist.example`에 명시했다. 승인된 삼성까지 일일 실행하려면 같은 plist의 crawl 명령에 `--source samsung_innovation_education`을 추가한다.

고양시 뉴스 검색은 감사 시 99개 기사/10페이지였고, 목록 10회와 상세 99회를 동일 호스트에 요청하므로 기본 5초 간격에서 약 9분이 걸린다. 일일 프로필은 증가 여유를 위해 `--max-pages 25`를 사용하며, 페이지 상한·총건수·행 수가 맞지 않으면 일부 결과를 조용히 저장하지 않고 실패한다. 운영 최적화는 전체 목록 완전성을 보존하는 체크포인트·본문 해시 캐시 방식으로 별도 적용한다.

## 신규 공공 커넥터 라이브 증분 스모크

서로 다른 여섯 공식 플랫폼을 같은 SQLite에 두 번 수집했다. 기간은
2026-07-15~2026-12-31, 소스별 최대 1페이지다.

| source ID | 첫 실행 `fetched / changed` | 두 번째 `fetched / changed` |
|---|---:|---:|
| `koagi_baekdudaegan_education` | 3 / 3 | 3 / 0 |
| `knps_jirisan_trail_programs` | 2 / 2 | 2 / 0 |
| `kywa_space_camp_programs` | 3 / 3 | 3 / 0 |
| `incheon_education_experience` | 2 / 2 | 2 / 0 |
| `geumcheon_education_reservation` | 2 / 2 | 2 / 0 |
| `cheongju_experience_reservation` | 8 / 8 | 8 / 0 |
| **합계** | **20 / 20** | **20 / 0** |

두 실행 모두 오류 0건이다. 같은 원문을 다시 읽을 때 `fetched_at` 변화만으로
신규 알림이 생기지 않는다.

교육청 공통 어댑터의 별도 1페이지 실조회에서는 인천 2건, 부산 15건,
충북 0건(현재 공개 모집 결과 없음), 전남 계열 4건을 파싱했다. 네 곳 모두
robots 허용이며 목록 GET과 내부 정보 상세 GET만 호출했다.

KYWA 7개 시설의 공개 캠프 JSON 실조회에서는 초등·가족 필터로 평창 1건,
우주센터 3건, 해양센터 2건, 미래환경센터 2건, 생태센터 1건을 확인했다.
단순 숙소 이용 상품과 성인 전용 행은 제외했다.

## 기존 파이프라인 증분 스모크

공식 서울 sample API 3종, MODU 국립중앙박물관, 경상북도교육청 온체험도
같은 방식으로 두 번 수집해 첫 실행 27건 변경, 두 번째 실행 27건 중 변경 0건을
확인했다. 서울시청 중심 반경 25km 조회에서도 좌표가 있는 결과가 거리와 함께
반환됐다.

ODCloud의 고려청자박물관 공식 데이터는 공공데이터포털 문서의 테스트 키로
1페이지 3건을 가져와 저장했다. 실제 서비스에서는 본인에게 발급된 디코딩 키를
사용해야 한다.

## robots·접근 경계 스모크

| source | 결과 |
|---|---|
| KOAGI 백두대간수목원 | 의미상 robots 404를 RFC 9309 규칙 없음으로 판정, 공개 목록 3건 정상 수집 |
| 리움·호암 | 정확한 민간 승인 ID를 넣었을 때 공개 목록 4건 확인; 승인 없이는 네트워크 전 차단 |
| 김포 통합예약 | 일반 User-Agent `Disallow: /`; `available=False`, 목록 요청 전 중단 |
| 안양 통합예약 | 파서/fixture는 있으나 현재 표준 TLS 런타임 연결 실패; `available=False` |
| HMOKA 등 민간 5종 | 정확한 승인 ID가 없으면 `available()`에서 즉시 중단 |
| 삼성 이노베이션 뮤지엄 | source 승인 + robots 모호성 확인 둘 중 하나라도 없으면 네트워크 전에 중단; 명시적 차단은 우회 불가 |

robots의 명확한 HTTP 404/410만 RFC 9309 §2.3.1.3에 따라 규칙 없음으로
처리한다. 5xx, 네트워크 오류, WAF 또는 의미를 확정할 수 없는 HTML은 계속
fail-closed한다. 로그인, 본인인증, 예약·신청 제출, 결제, CAPTCHA, NetFunnel
토큰은 어떤 커넥터도 호출하지 않는다.

## 조사 검증

- 지역 포털: 17개 시·도, source unit 60개, P1 15/P2 29/P3 16
- 공공기관: 독립 기관 89곳 + 통합 보조 목록 1개
- 민간: 공식 후보 84개, allowlist 9, metadata-only 56, partnership 14, deny 5
- 카탈로그: 234행 모두 공식 HTTPS URL, P0~P3, 정책·구현 상태, 검증일 보유
- 직접 구현 연결: 70행, 69개 고유 connector ID
- 수원·경기 심층 원장: 51행(P0 21/P1 25/P2 4/P3 1), 공식 SNS 28개

HTTP 상태와 모집 건수는 당일 관측값이며 영구 보장을 뜻하지 않는다. 배포 후에도
robots·약관·필드 구조·건수 급변을 주기적으로 다시 확인해야 한다.

## 재현 명령

```bash
uv sync --extra dev
python3 scripts/build_source_catalog.py
uv run python scripts/export_connector_registry.py
uv run pytest
uv run pytest -q tests/test_mcp_server.py
uvx ruff check src tests scripts
uv run python -m compileall -q src tests scripts
uv build

uv run kidradar crawl \
  --source koagi_baekdudaegan_education \
  --source knps_jirisan_trail_programs \
  --source kywa_space_camp_programs \
  --source incheon_education_experience \
  --source geumcheon_education_reservation \
  --source cheongju_experience_reservation \
  --from 2026-07-15 --to 2026-12-31 --max-pages 1

uv run kidradar crawl \
  --source ggc_gyeonggi_child_events \
  --source ggcf_affiliate_child_programs \
  --source ggcf_gyeonggi_jang_programs \
  --source suwon_education_experience \
  --source suwon_culture_foundation_education \
  --source suwon_museum_child_programs \
  --source suwon_gwanggyo_museum_child_programs \
  --source suwon_hwaseong_museum_child_programs \
  --from 2026-07-15 --to 2026-12-31 --max-pages 10

# 운영 범위를 확인한 삼성만 별도 이중 승인 후 추가
KIDS_RADAR_APPROVED_SOURCES=samsung_innovation_education \
KIDS_RADAR_ROBOTS_OVERRIDE_SOURCES=samsung_innovation_education \
uv run kidradar crawl --source samsung_innovation_education \
  --from 2026-07-15 --to 2026-12-31
```
