# 수집원 카탈로그 개요

검증 기준일: **2026-07-15 (Asia/Seoul)**

## 집계

| 조사군 | source unit | 우선순위 | 구현 연결 행 |
|---|---:|---|---:|
| 전국 지자체·교육청 | 60 | P1 15 · P2 29 · P3 16 | 14 |
| 국립·공공기관 | 90 | P0 45 · P1 40 · P2 5 | 50 |
| 대기업·민간 | 84 | P0 3 · P1 9 · P2 48 · P3 24 | 6 |
| **합계** | **234** | P0 48 · P1 64 · P2 82 · P3 40 | **70** |

`source unit`은 조직 수가 아니라 독립 포털 또는 별도 스키마·갱신주기를 가진 공식 데이터 상품 단위다. 대표 URL은 222개이며, MODU·KOAGI·리움/호암처럼 한 플랫폼 URL을 여러 기관이 공유해 234보다 작다.

전체 행은 다음 파일에서 필터·정렬할 수 있다.

- [`SOURCE_CATALOG.csv`](SOURCE_CATALOG.csv)
- [`SOURCE_CATALOG.json`](SOURCE_CATALOG.json)

실제 코드에 등록된 100개 커넥터는 별도 레지스트리다.

- [`CONNECTOR_REGISTRY.csv`](CONNECTOR_REGISTRY.csv)
- [`CONNECTOR_REGISTRY.json`](CONNECTOR_REGISTRY.json)

## 구현 상태 값

| 값 | 의미 |
|---|---|
| `implemented_api` | 조사 행과 동일한 공식 API 커넥터 |
| `implemented_official_dataset` | HTML 대신 해당 기관의 공식 공공데이터를 사용 |
| `implemented_opt_in` | 파서·테스트는 있으나 기본 비활성; 정책·운영 승인 후 선택 실행 |
| `implemented_policy_guarded` | 파서는 있지만 현재 robots/접근 상태가 fail-closed라 실행 금지 |
| `researched_not_implemented` | 공식 페이지와 구조는 검증했지만 전용 계약·파서는 아직 없음 |
| `policy_or_access_blocked` | robots 전면 차단, WAF, SSO, NetFunnel, 제휴 전용 또는 낮은 적합도로 자동화 금지 |

70개 조사 행이 69개 고유 connector ID에 직접 연결된다. 리움과 호암은 통합 목록 한 커넥터가 두 행을 처리한다. 전국 기본 원장과 별개로 수원·경기 기관별 심층 원장 51개도 유지하며, 그중 실행 가능한 공통 API·공통 HTML·전용 어댑터를 레지스트리에 연결했다. 전체 레지스트리가 100개인 이유는 문화포털·KOPIS·TourAPI·전국 표준 API·ODCloud 같은 전국 집계와 수원·경기 심층 어댑터 등 기본 원장의 69개 고유 연결 외 31개 실행 단위도 포함하기 때문이다.

## 수원·경기 심층 보완 원장

기본 234행은 전국 세 조사군의 비교 가능한 기준선으로 고정하고, 사용자가 지적한 지역 밀도 문제는 별도 51행 원장으로 더 세밀하게 보완했다. 51행은 기관별 공식 목록 49개와 기존 구현 감사 표식 2개이며, P0 21/P1 25/P2 4/P3 1, 공식 SNS 28개를 보존한다. 2026-07-15 최종 상태는 구현 표식 24개, 전용 어댑터 후보 19개, 수동 스키마 후속 7개, 정책 보류 1개다.

- [`research/gyeonggi-deep-discovery.csv`](research/gyeonggi-deep-discovery.csv)
- [`research/gyeonggi-deep-discovery.json`](research/gyeonggi-deep-discovery.json)
- [`research/gyeonggi-deep-discovery.md`](research/gyeonggi-deep-discovery.md)

## 민간 판정

민간 84개는 기술적으로 열리는지만 보지 않고 재사용 범위와 신청 장벽을 분리했다.

| 판정 | 수량 | 운영 원칙 |
|---|---:|---|
| `allowlist` | 9 | 승인 후 제목·기간·장소·대상·가격·상태·공식 URL만 저빈도 수집 |
| `metadata-only` | 56 | 본문·이미지·잔여석·예약 API 없이 사실 메타데이터만 검토 |
| `partnership` | 14 | 공식 피드·서면 허가·운영기관 제휴 전 자동수집 금지 |
| `deny` | 5 | robots 차단, 대상 불일치 또는 폐쇄형 신청으로 자동수집하지 않음 |

현재 민간 5개 커넥터는 `KIDS_RADAR_APPROVED_SOURCES`에 정확한 ID를 넣기 전에는 `--all`에서도 네트워크를 호출하지 않는다. 리움·호암의 의미상 robots 404는 RFC 9309의 unavailable 규칙에 따라 처리되지만, 민간 source 승인 절차는 그대로 유지한다.

## 전국 집계 레이어

- [전국 평생학습강좌 표준데이터](https://www.data.go.kr/data/15013110/standard.do): 제공기관 데이터셋 348개를 한 API로 조회
- [전국 문화축제 표준데이터](https://www.data.go.kr/data/15013104/standard.do): 제공기관 데이터셋 229개를 한 API로 조회
- [문화포털 한눈에 보는 문화정보](https://www.data.go.kr/data/15138937/openapi.do): 교육·체험, 행사·축제, 공연·전시
- [KOPIS OpenAPI](https://kopis.or.kr/por/cs/openapi/openApiInfo.do): `kidstate=Y` 아동공연
- [e청소년 활동 API](https://www.data.go.kr/data/15156313/openapi.do): 초등 대상 신고 활동
- [산림교육 API](https://www.data.go.kr/data/3057832/openapi.do): 산림교육 프로그램

표준데이터의 제공기관 수는 개별 포털과 겹치므로 234에 합산하지 않는다. 날짜·좌표·접수상태가 약한 데이터는 발견용으로 사용하고 발송 전 원문에서 모집 상태를 확인한다.

## 자동 수집 금지선

- 네이버 카페 회원글·댓글, 카카오 단톡/오픈채팅, 밴드 대화 원문
- 로그인 후 좌석·회원·신청자 정보
- 예약·결제·본인인증·지원서 제출
- CAPTCHA, WAF, SSO, NetFunnel, 브라우저 지문 검사 우회
- robots 전면 차단 경로
- 이미지·상세 본문·PDF/HWP 전체 재배포

커뮤니티에서 발견한 내용은 주최기관 공식 URL만 구조화해 `import-tips`로 가져온다.

## 상세 조사 문서

- [`research/regional-portals.md`](research/regional-portals.md)
- [`research/public-institutions.md`](research/public-institutions.md)
- [`research/private-brands.md`](research/private-brands.md)

## 재생성 및 검증

```bash
python3 scripts/build_source_catalog.py
uv run python scripts/export_connector_registry.py
uv run pytest tests/test_source_catalog.py
```

생성 결과의 계약 테스트는 234행, 조사군별 60/90/84, 구현 연결 70행/69개 고유 ID, 모든 행의 P0~P3, 2026-07-15 검증일, HTTPS 공식 URL, 민간 정책 9/56/14/5, 레지스트리 100개 고유 ID를 확인한다. 별도 수원·경기 계약 테스트는 심층 원장 51행, P0/P1/P2/P3 분포, 공식 URL·SNS·상태 필드를 확인한다.
