# Kids Experience Radar

초등학생 부모가 동네 중심점 주변의 무료·저가 체험, 교육, 공원·박물관 프로그램을 매일 모아 보는 정책 준수형 Python MVP입니다. 단순 링크 모음이 아니라 공식 소스 조사, 실행 커넥터, 증분 저장, 위치 필터, 일일 알림 출력까지 포함합니다.

## 이번 조사·구현 결과

검증 기준일은 **2026-07-15 (Asia/Seoul)**입니다.

| 구분 | 수량 | 의미 |
|---|---:|---|
| 지역 포털 | 60 | 17개 시·도의 지자체·교육청 공식 포털/데이터 상품 |
| 국립·공공기관 | 90 | 독립 기관 89곳 + 중복 탐지용 통합 목록 1개 |
| 대기업·민간 | 84 | 기업 체험관, 미술관, 문화공간, 키즈 시설의 공식 후보 |
| **검증된 source unit** | **234** | 서로 다른 스키마·갱신주기 또는 독립 운영 단위 |
| 고유 대표 URL | 222 | 공통 플랫폼 URL을 여러 기관이 공유하는 경우를 합친 값 |
| **등록 커넥터** | **100** | `kidradar sources`에 등록된 독립 실행 단위 |
| 카탈로그와 직접 연결된 행 | 70 | 69개 고유 connector ID가 공식 목록 또는 공식 데이터 대체 경로에 연결 |
| **수원·경기 심층 원장** | **51** | 기존 전국 원장을 보완한 기관별 소스 49개 + 기존 구현 감사 표식 2개 |

234개를 “234개 조직”이나 “모두 지금 크롤링 가능”이라고 부풀리지 않습니다. 같은 공통 플랫폼을 쓰는 기관은 source unit으로 각각 검증하되 공통 어댑터로 구현했고, robots 전면 차단·로그인·WAF·NetFunnel·제휴 전용 소스는 코드가 있어도 실행을 막거나 조사 목록으로만 남겼습니다. 수원·경기 51개 심층 원장은 전국 원장과 억지로 합산하지 않고 별도로 제공하며, 공식 URL 51개·공식 SNS 28개·구현/보류 사유를 행 단위로 남겼습니다.

전국 표준데이터는 위 234개와 별도의 집계 레이어입니다. [전국 평생학습강좌 표준데이터](https://www.data.go.kr/data/15013110/standard.do)는 348개 제공기관 데이터셋, [전국 문화축제 표준데이터](https://www.data.go.kr/data/15013104/standard.do)는 229개 제공기관 데이터셋을 한 API로 조회합니다. 지자체 포털과 중복될 수 있으므로 234에 더하지 않습니다.

## 구현된 커넥터 묶음

- 서울 공공서비스예약 2종과 서울 문화행사
- 문화포털 교육·체험/행사·축제/공연·전시 3종
- KOPIS 아동공연, e청소년 초등 활동, 산림교육
- 전국 평생학습강좌·문화축제 표준 API
- TourAPI 축제, 공유누리 교육·강좌, 전남도립미술관 API
- ODCloud 공식 데이터 11종: 농촌체험, 국립생물·해양생물·낙동강생물자원관, 독립기념관, 국립현대미술관, 수원시립미술관, 울산어린이테마파크, 한국영화박물관, 양천구 어린이 강좌, 고려청자박물관
- MODU 국립박물관 14관 공통 어댑터
- 한국수목원정원관리원 4기관 공통 어댑터
- 국립공원공단 탐방프로그램 22개 국립공원 공통 어댑터
- 한국청소년활동진흥원 국립청소년시설 7곳 공개 캠프 목록
- 인천·부산·충북·전남 계열 교육청 체험예약 4곳과 경상북도교육청 온체험
- 금천·김포·고양·용인·안양·청주 지자체 예약 포털 6곳(김포는 현재 robots 전면 차단으로 실행 중지)
- 현대 모터스튜디오 고양, 삼성 이노베이션 뮤지엄, 뮤지엄김치간, 현대어린이책미술관, 리움·호암 공개 목록
- GGC 경기도 문화행사 Open API, 경기문화재단 산하기관 통합 행사·교육·전시, 컬처라운지 `경기,장`
- 수원시 교육·강좌·체험, 수원문화재단 교육정보, 수원박물관·수원광교박물관·수원화성박물관
- 수원시도서관 통합예약, 수원 생태환경체험교육관, 경기도서관 공개 JSON
- 고양어린이박물관은 차단된 박물관 사이트 대신 고양시 공식 뉴스 공개 목록·상세만 수집

전체 100개의 ID·키·기본 활성 여부·정책 상태는 [`docs/CONNECTOR_REGISTRY.csv`](docs/CONNECTOR_REGISTRY.csv)와 [`docs/CONNECTOR_REGISTRY.json`](docs/CONNECTOR_REGISTRY.json)에 있습니다.

## 안전 상태를 숫자와 분리한 이유

- 기본 실행: 서울 공식 sample API 3개 + GGC 공식 Open API 1개
- 키와 명시 선택 필요: 공식 API·공공데이터 22개(기본 실행 3개까지 합치면 key-gated 25개)
- 명시 선택 필요: 키 없는 공공 HTML/JSON·민간 공개 목록 74개
- KOAGI 4기관: 의미상 robots 404를 RFC 9309 규칙 없음으로 처리하며 공개 목록 실조회 가능
- 김포시 1곳: 현재 `robots.txt`가 일반 User-Agent 전체를 차단해 코드가 있어도 `available=False`
- 안양시 1곳: fixture와 브라우저용 응답 파서는 구현했지만 현재 표준 TLS 런타임에서 안전한 연결을 맺지 못해 `available=False`
- 리움·호암: 의미상 robots 404 처리는 가능하지만 민간 source 승인 없이는 실행 차단
- 민간 5종: 정확한 source ID를 `KIDS_RADAR_APPROVED_SOURCES`에 넣기 전에는 `--all`에서도 네트워크 요청 없음
- 삼성 이노베이션 뮤지엄: source 승인과 모호한 robots 응답에 대한 별도 운영자 확인을 모두 통과해야 하며, 명시적 `Disallow`는 override할 수 없음

예약 버튼 클릭, 로그인, 결제, 캡차, 대기열, 세션 쿠키, 개인 신청 정보는 다루지 않습니다. 네이버 카페·카카오 단톡·밴드에서는 대화나 작성자를 긁지 않고 주최기관의 공식 URL만 제보받습니다.

## 5분 실행

Python 3.11 이상과 [uv](https://docs.astral.sh/uv/)가 필요합니다.

```bash
uv sync --extra dev
cp .env.example .env
uv run kidradar sources
uv run kidradar doctor
```

서울 공식 sample API로 수집과 반경 검색을 바로 확인할 수 있습니다.

```bash
uv run kidradar crawl \
  --source seoul_reservation_culture \
  --source seoul_reservation_education \
  --source seoul_cultural_events \
  --from 2026-07-15 --to 2026-12-31

uv run kidradar nearby \
  --lat 37.5665 --lon 126.9780 \
  --radius-km 20 --child-score-min 0.35
```

전체 공공 API를 쓰려면 `.env`에 발급 키를 넣습니다.

```dotenv
SEOUL_OPEN_DATA_KEY=...
DATA_GO_KR_SERVICE_KEY=...
ESHARE_API_KEY=...
KOPIS_API_KEY=...
KAKAO_REST_API_KEY=...
KIDS_RADAR_CONTACT=ops@your-domain.example
```

민간 소스는 정책·약관 또는 서면 허용 검토 후 정확한 ID만 승인합니다. 공공 목록은 별도 승인 환경변수 없이 source ID를 선택할 수 있지만 실행 때마다 robots를 확인합니다.

```dotenv
KIDS_RADAR_APPROVED_SOURCES=hmoka_programs,museum_kimchikan_children
```

```bash
uv run kidradar crawl --source hmoka_programs --from 2026-07-15 --to 2026-12-31
```

삼성 이노베이션 뮤지엄은 공식 이용조건의 사전승낙 조항과 `robots.txt`가 규칙 대신 HTML을 반환하는 현 상태 때문에 두 개의 독립 확인이 필요합니다. 다음 값은 허가를 대신하지 않으며, 운영자가 메타데이터·링크 이용 범위를 확인한 뒤에만 설정합니다.

```dotenv
KIDS_RADAR_APPROVED_SOURCES=samsung_innovation_education
KIDS_RADAR_ROBOTS_OVERRIDE_SOURCES=samsung_innovation_education
```

```bash
uv run kidradar crawl \
  --source samsung_innovation_education \
  --from 2026-07-15 --to 2026-12-31
```

키 없이 공개 공공 목록을 선택 실행하는 예시입니다. 신청·로그인·결제 엔드포인트는 호출하지 않습니다.

```bash
uv run kidradar crawl \
  --source knps_jirisan_trail_programs \
  --source kywa_space_camp_programs \
  --source incheon_education_experience \
  --source geumcheon_education_reservation \
  --from 2026-07-15 --to 2026-12-31
```

## 위치 기반 처리

공식 좌표가 있는 행사는 곧바로 거리순으로 검색합니다. 주소만 있는 공개 장소는 [카카오 로컬 주소 검색 API](https://developers.kakao.com/docs/latest/ko/local/dev-guide#address-coord)를 선택적으로 사용해 한 번 지오코딩하고 SQLite에 캐시합니다. 사용자의 실시간 위치는 지오코더로 보내지 않습니다.

```bash
uv run kidradar geocode --limit 100
uv run kidradar nearby --lat 37.5665 --lon 126.9780 --radius-km 20
```

## 매일 수집·알림

```bash
uv run kidradar crawl --source seoul_reservation_culture --source seoul_cultural_events
uv run kidradar geocode --limit 100
uv run kidradar digest \
  --lat 37.5665 --lon 126.9780 --radius-km 20 \
  --new-within-hours 26 --format markdown --output data/daily.md
```

`config/com.kidsradar.daily.plist.example`을 macOS launchd에 맞춰 수정하거나 같은 명령을 cron에서 하루 한 번 실행할 수 있습니다. 수원·경기는 `config/com.kidsradar.suwon-gyeonggi.daily.plist.example`에 GGC·경기문화재단·경기,장·수원시·수원문화재단·수원 3개 박물관·수원도서관·수원생태·경기도서관·고양시 뉴스 등 12개 공개 소스를 명시했습니다. 한 소스가 실패해도 지오코딩과 다이제스트를 만들고 원래 수집 오류를 종료 코드로 보존합니다. 좌표가 아직 없는 공식 장소도 누락되지 않게 표시하되, 48시간 넘게 갱신되지 않은 행은 기본 제외합니다.

승인 완료된 삼성 소스를 같은 일일 실행에 넣으려면 위 두 환경변수를 launchd 환경에 넣고 plist의 `kidradar crawl` 명령에 `--source samsung_innovation_education`을 추가합니다. 승인 전 공개 소스 프로필에는 의도적으로 포함하지 않았습니다. 첫 수집은 모두 신규이므로 실제 발송은 두 번째 정상 수집부터 시작하는 편이 안전합니다.

## 읽기 API

```bash
uv run kidradar serve --host 127.0.0.1 --port 8080
```

```text
GET /health
GET /sources
GET /events?lat=37.5665&lon=126.9780&radius_km=20&free_only=true
GET /events?lat=37.5665&lon=126.9780&radius_km=20&new_within_hours=26
```

외부 공개 시 인증·속도 제한·TLS를 앞단에 추가해야 합니다.

## MCP 서버

Codex·Claude Code·Claude Desktop을 포함해 표준 MCP stdio를 지원하는 호스트에서 로컬
위치 검색과 일일 수집 결과를 직접 사용할 수 있습니다. 특정 LLM API에 종속되지 않으며,
호스트가 MCP 도구를 모델에 연결하는 구조입니다.

```bash
uv sync --extra dev
uv run kidradar-mcp
```

저장소를 복제하지 않고 GitHub 버전을 직접 실행할 수도 있습니다.

```bash
uvx --from git+https://github.com/kimtami/kids-experience-radar.git@v0.1.0 kidradar-mcp
```

프로젝트 루트의 [`.mcp.json`](.mcp.json)은 Claude Code용 읽기 전용 기본 설정입니다.
Codex 등록 명령, Claude Desktop 설정, 범용 stdio 서버 설정, 6개 도구·2개 리소스·1개
프롬프트, 선택적 수집 allowlist 사용법은 [`docs/MCP.md`](docs/MCP.md)에 정리했습니다.
MCP 갱신은 기본 차단되며
`KIDS_RADAR_MCP_ALLOW_CRAWL=1`과 정확한
`KIDS_RADAR_MCP_CRAWL_SOURCES`를 함께 지정해야 작동합니다. 임의 URL·파일·DB 경로,
신청·로그인·결제, 웹훅은 MCP 입력으로 노출하지 않습니다.

LLM 자체가 MCP 서버에 직접 붙는 것은 아닙니다. 사용하는 앱이나 에이전트 런타임이
stdio MCP 클라이언트 기능을 제공해야 합니다. 브라우저 채팅처럼 로컬 MCP 프로세스를
실행할 수 없는 제품과 원격 HTTP 전용 클라이언트에는 이 버전을 직접 연결할 수 없습니다.

## 카탈로그와 연구 원문

- [`docs/SOURCE_CATALOG.csv`](docs/SOURCE_CATALOG.csv): 234개 전체, 우선순위·정책·구현 상태·connector ID
- [`docs/SOURCE_CATALOG.json`](docs/SOURCE_CATALOG.json): 같은 내용의 JSON
- [`docs/research/regional-portals.md`](docs/research/regional-portals.md): 전국 17개 시·도 60개 상세 조사
- [`docs/research/public-institutions.md`](docs/research/public-institutions.md): 공공기관 90개와 공통 어댑터 설계
- [`docs/research/private-brands.md`](docs/research/private-brands.md): 민간 84개와 allowlist/metadata/partnership/deny 판정
- [`docs/research/gyeonggi-deep-discovery.csv`](docs/research/gyeonggi-deep-discovery.csv): 수원·경기 51개 심층 원장과 구현/보류 상태
- [`docs/research/gyeonggi-deep-discovery.md`](docs/research/gyeonggi-deep-discovery.md): `경기,장`, 공식 SNS, 기관별 수집면 검증 기록
- [`docs/research/gyeonggi-implementation-audit.md`](docs/research/gyeonggi-implementation-audit.md): 수원·경기 13개 실행 커넥터와 라이브 증분 감사
- [`docs/research/blocked-source-alternatives.md`](docs/research/blocked-source-alternatives.md): 차단·점검 소스의 공식 대체 공개면 감사
- [`docs/research/gyeonggi-manual-schema-alternatives.md`](docs/research/gyeonggi-manual-schema-alternatives.md): 수동 스키마 9개 공개 경로 실사
- [`docs/research/gyeonggi-adapter-candidate-feeds.md`](docs/research/gyeonggi-adapter-candidate-feeds.md): 나머지 후보 19개 공식 반복 수집 경로 전수 감사
- [`docs/LEGAL_AND_OPERATIONS.md`](docs/LEGAL_AND_OPERATIONS.md): 법적·운영 안전선
- [`docs/MCP.md`](docs/MCP.md): 범용 stdio·Codex·Claude MCP 설치, 도구, 권한 경계
- [`docs/VERIFICATION.md`](docs/VERIFICATION.md): 테스트와 라이브 스모크 기록

카탈로그 재생성:

```bash
python3 scripts/build_source_catalog.py
uv run python scripts/export_connector_registry.py
```

## 테스트

```bash
uv run pytest
uv run ruff check src tests scripts
uv run python -m compileall -q src tests scripts
uv build
```

## 라이선스와 외부 데이터

프로그램 코드는 [MIT License](LICENSE)로 공개합니다. 기관명·상표·수집 대상 사이트의
콘텐츠와 데이터는 MIT 라이선스에 포함되지 않으며 각 제공기관의 이용조건을 따릅니다.
자세한 경계는 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)에 기록했습니다.
