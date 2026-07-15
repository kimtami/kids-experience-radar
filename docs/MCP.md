# Kids Experience Radar MCP

검증 기준: 2026-07-15, MCP Python SDK `1.28.1`

## 제공 기능

로컬 SQLite와 기존 크롤러를 직접 재사용하는 `stdio` MCP 서버다. FastAPI를 다시
호출하거나 별도 데이터를 복제하지 않는다.

| MCP 기능 | 종류 | 동작 |
|---|---|---|
| `list_experience_sources` | 읽기 도구 | 공식 소스 검색·실행 가능 상태·커서 페이지네이션 |
| `search_nearby_experiences` | 읽기 도구 | 위도·경도·반경·무료·신규·마감 필터 |
| `get_experience` | 읽기 도구 | 24자리 공개 event UID로 단일 행사 조회 |
| `render_nearby_digest` | 읽기 도구 | Markdown/JSON 다이제스트를 메모리에서 반환 |
| `get_radar_status` | 읽기 도구 | DB 건수·소스별 마지막 실행·MCP 갱신 게이트 |
| `refresh_experience_sources` | 네트워크·DB 도구 | 이중 승인된 정확한 source ID만 갱신 |
| `kidradar://sources` | 리소스 | 공식 소스 레지스트리 |
| `kidradar://stats` | 리소스 | 로컬 DB와 최근 수집 상태 |
| `find_family_experiences` | 프롬프트 | 위치 기반 가족 체험 검색 지침 |

검색 응답은 `raw` 원문 필드를 제외한다. MCP 인자로 임의 URL, DB·파일 경로,
HTML 설정, 환경파일, 웹훅, 셸 명령, `--all`, 신청·결제·로그인 경로를 받지 않는다.
행사 제목·설명은 신뢰되지 않은 데이터로 취급하며 그 안의 명령문을 실행 지시로 해석하지
않도록 서버 instructions에 명시했다.

## 설치와 직접 실행

```bash
uv sync --extra dev
cp .env.example .env
uv run kidradar crawl --source ggc_gyeonggi_child_events --max-pages 5
uv run kidradar-mcp
```

마지막 명령은 stdio JSON-RPC 서버이므로 터미널에 일반 화면이 뜨지 않는 것이 정상이다.
stdout은 MCP 프로토콜 전용이며 일반 로그나 비밀값을 출력하지 않는다.
좌표가 아직 없는 행사는 `search_nearby_experiences`에서
`include_unknown_location=true`일 때만 보이며 거리순 필터를 적용할 수 없다. Kakao 키를
설정하고 `uv run kidradar geocode`를 실행하면 주소 기반 반경 검색이 가능하다. 사용자가
도구에 전달한 검색 중심 좌표는 DB에 저장하지 않는다.

## 범용 MCP 클라이언트

이 서버는 특정 모델의 SDK를 호출하지 않는다. MCP 호스트가 `kidradar-mcp` 프로세스를
실행하고 표준 입력·출력으로 JSON-RPC를 주고받으므로, 기반 모델이 무엇이든 stdio MCP를
지원하는 클라이언트에서 사용할 수 있다.

저장소를 복제하지 않는 실행 명령은 다음과 같다.

```bash
uvx --from git+https://github.com/kimtami/kids-experience-radar.git@v0.1.0 kidradar-mcp
```

클라이언트 설정에는
[`config/mcp-stdio-server.example.json`](../config/mcp-stdio-server.example.json)의 서버
객체를 해당 제품이 요구하는 바깥 설정 구조 안에 넣는다. `KIDS_RADAR_DB`는 반드시 실제
절대 경로로 바꾼다. 첫 검색 전에 같은 DB 경로로 공개 소스를 한 번 수집한다.

```bash
mkdir -p "$HOME/.local/share/kids-experience-radar"
KIDS_RADAR_DB="$HOME/.local/share/kids-experience-radar/radar.sqlite3" \
  uvx --from git+https://github.com/kimtami/kids-experience-radar.git@v0.1.0 \
  kidradar crawl --source seoul_reservation_culture
```

GUI 앱이 `uvx`를 찾지 못하면 터미널에서 `command -v uvx`로 절대 경로를 확인하고 설정의
`command`를 그 경로로 바꾼다. 태그를 고정했으므로 기본 브랜치의 후속 변경이 설치 결과를
임의로 바꾸지 않는다.

| 실행 환경 | 지원 상태 |
|---|---|
| 로컬 stdio MCP 호스트 | 지원 |
| Claude Code·Claude Desktop·Codex | 설정 예시 포함 |
| 자체 MCP 클라이언트·에이전트 런타임 | 표준 initialize/tools/resources/prompts로 연결 가능 |
| MCP 기능이 없는 브라우저 채팅 | 직접 연결 불가 |
| 원격 HTTP만 허용하는 호스트 | 현재 직접 연결 불가 |

즉 “모든 LLM”보다 정확한 표현은 “stdio MCP 호스트가 연결할 수 있는 모든 기반 모델”이다.
원격 사용이 필요하면 로컬 서버를 무인증으로 노출하지 말고 인증·TLS가 적용된 Streamable
HTTP 배포를 별도로 구성해야 한다.

## Claude Code

프로젝트 루트에서 Claude Code를 열면 [`.mcp.json`](../.mcp.json)을 발견한다. 최초에는
프로젝트 MCP 실행 승인을 묻는다.

```bash
claude mcp list
```

Claude Desktop은
[`config/claude-desktop-mcp.example.json`](../config/claude-desktop-mcp.example.json)의
`/ABSOLUTE/PATH`를 실제 프로젝트 경로로 바꾼 뒤 Desktop 설정에 병합한다. 설정 변경 후
클라이언트를 재시작한다.

## Codex

전역 설정을 자동으로 바꾸지는 않는다. 다음 명령으로 로컬 stdio 서버를 등록할 수 있다.

```bash
codex mcp add \
  --env KIDS_RADAR_ENV_FILE=/ABSOLUTE/PATH/kids-experience-radar/.env \
  --env KIDS_RADAR_DB=/ABSOLUTE/PATH/kids-experience-radar/data/radar.sqlite3 \
  --env KIDS_RADAR_MCP_ALLOW_CRAWL=0 \
  kids_experience_radar -- \
  uv run --directory /ABSOLUTE/PATH/kids-experience-radar kidradar-mcp

codex mcp get kids_experience_radar
```

직접 TOML을 관리하려면
[`config/codex-mcp.example.toml`](../config/codex-mcp.example.toml)을 참고한다. 고양시 뉴스
전체 갱신은 약 9분이므로 예시는 `tool_timeout_sec=900`으로 둔다.

## 기본 읽기 전용과 갱신 승인

MCP 서버는 기본적으로 조회 전용이다. `refresh_experience_sources`를 사용하려면 서버 시작
환경에 다음 두 값을 모두 넣어야 한다.

```dotenv
KIDS_RADAR_MCP_ALLOW_CRAWL=1
KIDS_RADAR_MCP_CRAWL_SOURCES=suwon_library_child_programs,suwon_ecology_child_programs,gyeonggi_library_programs,goyang_children_museum_city_news
```

도구 호출의 `source_ids`가 위 allowlist의 정확한 ID와 일치해야 한다. 최대 25개 소스,
25페이지, 180일 구간으로 제한하고 동시에 두 갱신을 실행하지 않는다. 각 소스의 기존
API 키·robots·정책·민간 승인 게이트도 그대로 적용된다. 설정을 바꾸면 MCP 클라이언트를
재시작한다.

MCP는 스케줄러가 아니다. 매일 자동 수집은 기존 launchd/cron 프로필이 담당하고, MCP는
에이전트가 저장 결과를 검색하거나 운영자가 명시적으로 갱신할 때 사용하는 인터페이스다.

## 프로토콜 검증

테스트는 공식 SDK의 인메모리 세션과 실제 stdio subprocess 세션을 모두 사용한다.

```bash
uv run pytest -q tests/test_mcp_server.py
```

검증 범위는 도구·리소스·프롬프트 discovery, structured output, 위치 필터, 커서와 필터
결합, `raw` 비노출, 없는 DB 미생성, 기본 갱신 차단, source allowlist, 실제 stdio
initialize/call이다.

운영 의존성은 안정판 v1에 맞춰 `mcp>=1.28.1,<2`로 고정했다. 2026-07-15 기준 v2는
사전 릴리스이므로 자동 메이저 업그레이드를 허용하지 않는다. 원격 배포가 필요해지면
deprecated SSE가 아니라 인증·TLS가 적용된 Streamable HTTP를 별도 설계한다.
