# 전국 공공기관 어린이 체험·교육 수집원 조사

검증일: 2026-07-15 (KST)

## 결론

독립 운영기관 **89곳**과 중복제거용 통합 목록 1개, 총 **90개 공식 엔드포인트**를 실제 목록 URL 기준으로 확인했다. 이 중 같은 예약 시스템을 쓰는 61개 기관은 6개 공통 어댑터로 묶을 수 있다. MVP 우선순위는 다음과 같다.

1. **바로 구현(P0)**: MODU 14개 국립박물관, 국립공원 22개소, KYWA 7개 국립청소년시설, 국립중앙과학관, 국립호남권생물자원관 공개 데이터.
2. **다음 구현(P1)**: NIE/NIBR/NNIBR/HNIBR, 국립해양박물관, 국립울진해양과학관, 국립어린이청소년도서관, 숲e랑 7개 숲체원, KMA 7개 기상 박물관·과학관. KOAGI 4개 기관은 공개 목록 파서를 구현했고, 의미상 404인 robots 응답은 RFC 9309 §2.3.1.3에 따라 규칙 없음으로 처리하되 목록·상세 사실만 수집한다.
3. **수동 보조 또는 사전 협의(P2)**: robots 전체 차단, WAF/NetFunnel, 네이버·구글 폼·공문·이메일 신청으로 이어지는 출처. 목록 메타데이터와 원문 링크만 제공하고 신청 자동화는 하지 않는다.

89개 기관은 단순 홈페이지가 아니라 교육·체험 목록, 예약 목록, 또는 해당 기관으로 필터된 통합 예약 목록을 기준으로 센 것이다. 같은 플랫폼의 각 시설은 프로그램 운영 주체와 위치가 독립이므로 위치 기반 서비스에서는 별도 출처로 다루되, 크롤러 코드는 공유한다. KOAGI 무필터 통합 목록 1개는 기관 수에 포함하지 않고 중복 누락 탐지용 보조 엔드포인트로만 센다.

## 검증 방법과 판정 기준

- 공식 도메인의 목록을 브라우저와 설명적인 연구용 User-Agent로 `GET`하고, 현재 프로그램 또는 유효한 기관 필터를 확인했다. `HEAD`는 공공 사이트에서 오탐이 많아 쓰지 않았다.
- `robots.txt`는 2026-07-15 현재의 응답을 별도 확인했다. [RFC 9309 §2.3.1.3](https://www.rfc-editor.org/rfc/rfc9309.html#section-2.3.1.3)에 따라 명확한 404/410은 규칙 없음으로 처리하고, 5xx·WAF·판별 불가능한 HTML은 fail-closed한다. robots가 없거나 허용한다고 해서 콘텐츠 복제나 신청 자동화 허가를 뜻하지는 않는다.
- 로그인 전 공개 목록만 조사했다. 로그인, 결제, 예약 제출, 대기열 우회, 개인정보 입력 엔드포인트는 호출하지 않았다.
- `수집성 A`: 공개 JSON/HTML fragment 또는 규칙적인 SSR DOM. `B`: SSR DOM이나 상세 보강·외부 신청이 필요. `C`: WAF/robots 차단/강한 JS 의존/수동 공고형.
- `P0`: 첫 릴리스, `P1`: 안정화 후, `P2`: 수동 링크·모니터링 또는 기관 협의 후.
- 최종 링크 감사에서 문서의 고유 공식 URL 89개 중 88개가 리다이렉트 후 HTTP 200이었다. 서울농업기술센터 1개만 HTTP→`?refresh` 302가 종결되어 P2로 명시했으며, `Error 200`을 반환하던 불완전한 숲e랑 기관 쿼리 URL은 기본 검색 목록으로 교체했다.

## 권리·운영 원칙

| 코드 | 적용 원칙 |
|---|---|
| R1 | 공개 페이지의 제목, 기관명, 일정, 대상, 가격, 모집상태, 장소와 원문 URL만 저장한다. 상세 본문·이미지·첨부파일은 복제하지 않는다. 출처와 마지막 확인 시각을 표시한다. |
| R2 | 공공데이터포털/API/파일 데이터는 해당 데이터셋의 이용조건과 공공누리 유형을 저장하고 그대로 따른다. API 키가 있으면 공식 키를 사용한다. |
| R3 | robots 전체 차단, WAF, NetFunnel 또는 명시적 자동수집 제한이 보이면 자동수집을 중지한다. 검색엔진 캐시를 데이터 원본으로 쓰지 않고 기관에 허용 범위·주기를 문의한다. |
| R4 | 예약·결제·로그인·네이버/구글 폼·공문/이메일 제출은 수집 범위 밖이다. 사용자를 공식 신청 화면으로 딥링크한다. |

권장 기본 주기는 공개 JSON 6시간, SSR 목록 12~24시간이다. `If-Modified-Since`/`ETag`, 지수 백오프, 도메인별 동시 1요청, 1~3초 지연을 적용한다. 삭제된 프로그램은 즉시 지우지 말고 `last_seen_at`과 `inactive` 상태로 남긴다.

## 공통 플랫폼 프로필

아래 프로필을 참조하는 모든 기관 행은 이 표의 인터페이스·접근·필드·권리 조건을 그대로 상속한다.

| 프로필 | 공통 목록/API | HTTP·robots·로그인/WAF | 대상·가용 필드 | 수집성·권리·우선순위 |
|---|---|---|---|---|
| M — MODU 국립박물관 | `GET /learn?museum={1..14}&searchApplyStatus=ONGOING`; SSR 카드, 상세 `/learn/detail/{id}` | 목록 200. robots `Allow: /`, `/mng/` 등만 제외. 목록 비로그인, 신청/좋아요만 로그인. WAF 없음 | 유아·초등·가족·단체. 상태, 교육기간, 접수기간, 대상, 기관, 상세에서 장소·정원·비용·문의 | A, R1+R4, P0. 한 어댑터로 14관 |
| P — 국립공원공단 | `GET /trprogram/searchTrailProgram.do?deptId={code}` + 공개 `POST /trprogram/trprogramList.do` (`dept_id`, `orgnzt_gbn=G`, `pageNo`, `listScale`) | 목록/fragment 200. robots 404(미게시). 목록 비로그인, 실제 예약은 별도. 페이지 JS에 NetFunnel 래퍼가 있으나 공개 fragment 직접 조회는 정상; 우회 토큰은 사용하지 않음 | 가족·어린이·전연령 생태/해설. 공원, 집결지, 프로그램명, 운영기간, 예약상태; 상세에서 대상·비용·정원·장소 | A, R1+R4, P0. 낮은 빈도·기관 협의 권장 |
| Y — KYWA 국립청소년시설 | `GET /reservation/campReservationList.do?center={alias}` + 공개 `POST /reservation/ajax/campReservationList.do` | 목록 200. robots `User-agent:* Allow:/`. JSON 비로그인, 신청은 로그인. WAF 없음 | 청소년·초등·가족·학교. 시설코드, 프로그램번호/구분/명, 상태, 운영·접수기간, 대상명/연령, 정원·신청수·대기수, 담당전화 | A, R1+R4, P0 |
| A — KOAGI 국립수목원 통합예약 | `GET /reserve/edc/prgrm/aply/BD_selectReserveEdcPrgrmList.do?q_siteSeq={2..5}`; SSR 카드 | 목록 200. `/robots.txt`는 HTTP 200의 의미상 `Status:404`; RFC 9309 기준 규칙 없음. 목록 비로그인, 신청 단계 로그인. WAF 없음 | 유아·초등·가족·단체. 상태, 접수일시, 이용일시, 참가비, 대상, 신청방법, 정원, 모집유형 | 파싱성 A, R1+R4, P1/공개 목록 활성화 가능; 한 어댑터로 4개 기관 |
| F — 숲e랑(한국산림복지진흥원) | `GET /rep/ari/selectPrgmRsrvtList.do?menuNo=1020000`; 공개 검색 폼에서 지역→기관(`FA00001..07`)→날짜/인원을 선택, 기관목록 AJAX와 SSR 결과 사용 | 기본 목록 200. robots `Allow:/`; 일부 Q&A만 제외. 검색·목록 공개, 예약 전 로그인 필수, 예약오픈 대기 가능 | 유아·초등·가족·단체. 기관, 프로그램, 예약일정, 인원, 장소; 상세/정책에서 가격·대상 | B, R1+R4, P1. 불완전한 쿼리 URL은 Error 200을 내므로 기본 목록에서 정상 검색 흐름만 사용; 예약 대기열 호출 금지 |
| K — 기상청 박물관·과학관 | `science.kma.go.kr/{site}/...`의 기관별 교육/프로그램 목록; 같은 CMS 계열이나 경로는 기관별 상이 | 목록 200. 루트 robots는 사이트별 명시가 약함; 로그인 없는 공고/교육 목록, 일부 예약은 네이버 등 외부. WAF 없음 | 유아·초등·가족·단체. 프로그램/행사명, 교육기간, 장소, 대상, 정원, 문의; 일부 비용·예약링크 | B, R1+R4, P1 |

## 1. MODU 국립박물관 14곳 — 프로필 M

| # | 기관·지역·유형 | 공식 교육/예약 목록 | 대상·필드 | 인터페이스·접근·정책·우선순위 |
|---:|---|---|---|---|
| 1 | 국립중앙박물관 · 서울 · 박물관 | [진행중 교육](https://modu.museum.go.kr/learn?museum=1&searchApplyStatus=ONGOING) | 유아/초등/가족/단체; 일정·접수·대상·비용·장소 | M: SSR 200, robots 허용, 목록 공개/신청 로그인, A, R1/R4, P0 |
| 2 | 국립경주박물관 · 경북 경주 · 박물관 | [진행중 교육](https://modu.museum.go.kr/learn?museum=2&searchApplyStatus=ONGOING) | 초등/가족/단체; 동일 필드 | M · A · R1/R4 · P0 |
| 3 | 국립광주박물관 · 광주 · 박물관 | [진행중 교육](https://modu.museum.go.kr/learn?museum=3&searchApplyStatus=ONGOING) | 유아/초등/가족; 동일 필드 | M · A · R1/R4 · P0 |
| 4 | 국립전주박물관 · 전북 전주 · 박물관 | [진행중 교육](https://modu.museum.go.kr/learn?museum=4&searchApplyStatus=ONGOING) | 초등/가족/단체; 동일 필드 | M · A · R1/R4 · P0 |
| 5 | 국립대구박물관 · 대구 · 박물관 | [진행중 교육](https://modu.museum.go.kr/learn?museum=5&searchApplyStatus=ONGOING) | 유아/초등/가족; 동일 필드 | M · A · R1/R4 · P0 |
| 6 | 국립부여박물관 · 충남 부여 · 박물관 | [진행중 교육](https://modu.museum.go.kr/learn?museum=6&searchApplyStatus=ONGOING) | 초등/가족/단체; 동일 필드 | M · A · R1/R4 · P0 |
| 7 | 국립공주박물관 · 충남 공주 · 박물관 | [진행중 교육](https://modu.museum.go.kr/learn?museum=7&searchApplyStatus=ONGOING) | 초등/가족/단체; 동일 필드 | M · A · R1/R4 · P0 |
| 8 | 국립진주박물관 · 경남 진주 · 박물관 | [진행중 교육](https://modu.museum.go.kr/learn?museum=8&searchApplyStatus=ONGOING) | 유아/초등/가족; 동일 필드 | M · A · R1/R4 · P0 |
| 9 | 국립청주박물관 · 충북 청주 · 박물관 | [진행중 교육](https://modu.museum.go.kr/learn?museum=9&searchApplyStatus=ONGOING) | 초등/가족/단체; 동일 필드 | M · A · R1/R4 · P0 |
| 10 | 국립김해박물관 · 경남 김해 · 박물관 | [진행중 교육](https://modu.museum.go.kr/learn?museum=10&searchApplyStatus=ONGOING) | 유아/초등/가족; 동일 필드 | M · A · R1/R4 · P0 |
| 11 | 국립제주박물관 · 제주 · 박물관 | [진행중 교육](https://modu.museum.go.kr/learn?museum=11&searchApplyStatus=ONGOING) | 초등/가족/단체; 동일 필드 | M · A · R1/R4 · P0 |
| 12 | 국립춘천박물관 · 강원 춘천 · 박물관 | [진행중 교육](https://modu.museum.go.kr/learn?museum=12&searchApplyStatus=ONGOING) | 유아/초등/가족; 동일 필드 | M · A · R1/R4 · P0 |
| 13 | 국립나주박물관 · 전남 나주 · 박물관 | [진행중 교육](https://modu.museum.go.kr/learn?museum=13&searchApplyStatus=ONGOING) | 초등/가족/단체; 동일 필드 | M · A · R1/R4 · P0 |
| 14 | 국립익산박물관 · 전북 익산 · 박물관 | [진행중 교육](https://modu.museum.go.kr/learn?museum=14&searchApplyStatus=ONGOING) | 초등/가족/단체; 동일 필드 | M · A · R1/R4 · P0 |

## 2. 국립공원 생태·탐방 프로그램 22곳 — 프로필 P

| # | 기관·지역 | 공식 목록 | 대상·필드 | 인터페이스·접근·정책·우선순위 |
|---:|---|---|---|---|
| 15 | 지리산국립공원 · 전북/전남/경남 | [탐방 프로그램](https://reservation.knps.or.kr/trprogram/searchTrailProgram.do?deptId=B01) | 어린이/가족/전연령; 프로그램·집결지·운영기간·상태·비용 | P: GET+공개 POST 200, robots 미게시, 예약 별도, A, R1/R4, P0 |
| 16 | 한려해상국립공원 · 경남/전남 | [탐방 프로그램](https://reservation.knps.or.kr/trprogram/searchTrailProgram.do?deptId=B02) | 어린이/가족; 동일 필드 | P · A · R1/R4 · P0 |
| 17 | 설악산국립공원 · 강원 | [탐방 프로그램](https://reservation.knps.or.kr/trprogram/searchTrailProgram.do?deptId=B03) | 어린이/가족; 동일 필드 | P · A · R1/R4 · P0 |
| 18 | 내장산국립공원 · 전북/전남 | [탐방 프로그램](https://reservation.knps.or.kr/trprogram/searchTrailProgram.do?deptId=B04) | 어린이/가족; 동일 필드 | P · A · R1/R4 · P0 |
| 19 | 덕유산국립공원 · 전북/경남 | [탐방 프로그램](https://reservation.knps.or.kr/trprogram/searchTrailProgram.do?deptId=B05) | 어린이/가족; 동일 필드 | P · A · R1/R4 · P0 |
| 20 | 오대산국립공원 · 강원 | [탐방 프로그램](https://reservation.knps.or.kr/trprogram/searchTrailProgram.do?deptId=B06) | 어린이/가족; 동일 필드 | P · A · R1/R4 · P0 |
| 21 | 주왕산국립공원 · 경북 | [탐방 프로그램](https://reservation.knps.or.kr/trprogram/searchTrailProgram.do?deptId=B07) | 어린이/가족; 동일 필드 | P · A · R1/R4 · P0 |
| 22 | 태안해안국립공원 · 충남 | [탐방 프로그램](https://reservation.knps.or.kr/trprogram/searchTrailProgram.do?deptId=B08) | 어린이/가족/해양생태; 동일 필드 | P · A · R1/R4 · P0 |
| 23 | 다도해해상국립공원 · 전남 | [탐방 프로그램](https://reservation.knps.or.kr/trprogram/searchTrailProgram.do?deptId=B09) | 어린이/가족/해양생태; 동일 필드 | P · A · R1/R4 · P0 |
| 24 | 치악산국립공원 · 강원 | [탐방 프로그램](https://reservation.knps.or.kr/trprogram/searchTrailProgram.do?deptId=B10) | 어린이/가족; 동일 필드 | P · A · R1/R4 · P0 |
| 25 | 월악산국립공원 · 충북/경북 | [탐방 프로그램](https://reservation.knps.or.kr/trprogram/searchTrailProgram.do?deptId=B11) | 어린이/가족; 동일 필드 | P · A · R1/R4 · P0 |
| 26 | 소백산국립공원 · 충북/경북 | [탐방 프로그램](https://reservation.knps.or.kr/trprogram/searchTrailProgram.do?deptId=B12) | 어린이/가족; 동일 필드 | P · A · R1/R4 · P0 |
| 27 | 가야산국립공원 · 경북/경남 | [탐방 프로그램](https://reservation.knps.or.kr/trprogram/searchTrailProgram.do?deptId=B13) | 어린이/가족; 동일 필드 | P · A · R1/R4 · P0 |
| 28 | 북한산국립공원 · 서울/경기 | [탐방 프로그램](https://reservation.knps.or.kr/trprogram/searchTrailProgram.do?deptId=B14) | 어린이/가족; 동일 필드 | P · A · R1/R4 · P0 |
| 29 | 경주국립공원 · 경북 경주 | [탐방 프로그램](https://reservation.knps.or.kr/trprogram/searchTrailProgram.do?deptId=B15) | 어린이/가족/역사생태; 동일 필드 | P · A · R1/R4 · P0 |
| 30 | 계룡산국립공원 · 충남/대전 | [탐방 프로그램](https://reservation.knps.or.kr/trprogram/searchTrailProgram.do?deptId=B16) | 어린이/가족; 동일 필드 | P · A · R1/R4 · P0 |
| 31 | 무등산국립공원 · 광주/전남 | [탐방 프로그램](https://reservation.knps.or.kr/trprogram/searchTrailProgram.do?deptId=B17) | 어린이/가족; 동일 필드 | P · A · R1/R4 · P0 |
| 32 | 변산반도국립공원 · 전북 | [탐방 프로그램](https://reservation.knps.or.kr/trprogram/searchTrailProgram.do?deptId=B18) | 어린이/가족/해안생태; 동일 필드 | P · A · R1/R4 · P0 |
| 33 | 속리산국립공원 · 충북/경북 | [탐방 프로그램](https://reservation.knps.or.kr/trprogram/searchTrailProgram.do?deptId=B19) | 어린이/가족; 동일 필드 | P · A · R1/R4 · P0 |
| 34 | 월출산국립공원 · 전남 | [탐방 프로그램](https://reservation.knps.or.kr/trprogram/searchTrailProgram.do?deptId=B20) | 어린이/가족; 동일 필드 | P · A · R1/R4 · P0 |
| 35 | 태백산국립공원 · 강원/경북 | [탐방 프로그램](https://reservation.knps.or.kr/trprogram/searchTrailProgram.do?deptId=B22) | 어린이/가족; 동일 필드 | P · A · R1/R4 · P0 |
| 36 | 팔공산국립공원 · 대구/경북 | [탐방 프로그램](https://reservation.knps.or.kr/trprogram/searchTrailProgram.do?deptId=B25) | 어린이/가족; 동일 필드 | P · A · R1/R4 · P0 |

## 3. 국립청소년시설 7곳 — 프로필 Y

| # | 기관·지역 | 공식 목록 | 대상·필드 | 인터페이스·접근·정책·우선순위 |
|---:|---|---|---|---|
| 37 | 국립중앙청소년수련원 · 충남 천안 | [캠프예약](https://booking.kywa.or.kr/reservation/campReservationList.do?center=nyc) | 초등/청소년/가족/학교; 프로그램·운영/접수일·대상·정원·상태·전화 | Y: 공개 JSON 200, robots 허용, 신청 로그인, A, R1/R4, P0; `center_cd=2` |
| 38 | 국립평창청소년수련원 · 강원 평창 | [캠프예약](https://booking.kywa.or.kr/reservation/campReservationList.do?center=pnyc) | 동일 | Y · A · R1/R4 · P0; `center_cd=3` |
| 39 | 국립청소년우주센터 · 전남 고흥 | [캠프예약](https://booking.kywa.or.kr/reservation/campReservationList.do?center=nysc) | 초등/청소년/가족; 우주과학 | Y · A · R1/R4 · P0; `center_cd=4` |
| 40 | 국립청소년바이오생명센터 · 전북 김제 | [캠프예약](https://booking.kywa.or.kr/reservation/campReservationList.do?center=nyac) | 초등/청소년/가족; 생명과학 | Y · A · R1/R4 · P0; `center_cd=6` (기관 사이트 별칭은 `nybc`) |
| 41 | 국립청소년해양센터 · 경북 영덕 | [캠프예약](https://booking.kywa.or.kr/reservation/campReservationList.do?center=nyoc) | 초등/청소년/가족; 해양 | Y · A · R1/R4 · P0; `center_cd=7` |
| 42 | 국립청소년미래환경센터 · 경북 봉화 | [캠프예약](https://booking.kywa.or.kr/reservation/campReservationList.do?center=nyfc) | 초등/청소년/가족; 환경 | Y · A · R1/R4 · P0; `center_cd=8` |
| 43 | 국립청소년생태센터 · 부산 | [캠프예약](https://booking.kywa.or.kr/reservation/campReservationList.do?center=nyec) | 초등/청소년/가족; 생태 | Y · A · R1/R4 · P0; `center_cd=13` |

## 4. 국립수목원·정원 4곳 + 통합 보조 목록 1개 — 프로필 A

| # | 기관·지역 | 공식 목록 | 대상·필드 | 인터페이스·접근·정책·우선순위 |
|---:|---|---|---|---|
| 44 | 국립백두대간수목원 · 경북 봉화 | [교육 프로그램](https://reserve.koagi.or.kr/reserve/edc/prgrm/aply/BD_selectReserveEdcPrgrmList.do?q_siteSeq=2) | 유아/초등/가족/단체; 접수·이용일·비용·대상·정원·상태 | A: SSR 200, 의미상 robots 404는 RFC 9309상 규칙 없음, 신청 로그인, 공개 목록 파서 실조회, R1/R4, P1 |
| 45 | 국립세종수목원 · 세종 | [교육 프로그램](https://reserve.koagi.or.kr/reserve/edc/prgrm/aply/BD_selectReserveEdcPrgrmList.do?q_siteSeq=3) | 동일 | A · 공개 목록 파서 실조회 · R1/R4 · P1 |
| 46 | 국립한국자생식물원 · 강원 평창 | [교육 프로그램](https://reserve.koagi.or.kr/reserve/edc/prgrm/aply/BD_selectReserveEdcPrgrmList.do?q_siteSeq=4) | 동일 | A · 공개 목록 파서 실조회 · R1/R4 · P1 |
| 47 | 국립정원문화원 · 전남 담양 | [교육 프로그램](https://reserve.koagi.or.kr/reserve/edc/prgrm/aply/BD_selectReserveEdcPrgrmList.do?q_siteSeq=5) | 초등/가족/단체; 동일 | A · 공개 목록 파서 · R1/R4 · P1; 신규 기관이라 빈 목록도 정상 상태로 취급 |
| 48 | 한국수목원정원관리원 통합검색 · 전국 | [통합 교육 프로그램](https://reserve.koagi.or.kr/reserve/edc/prgrm/aply/BD_selectReserveEdcPrgrmList.do) | 전 기관; 동일 | A · 기관별 피드의 중복 탐지용 상위 목록 · R1/R4 · P1 |

## 5. 국립숲체원 7곳 — 프로필 F

| # | 기관·지역 | 공식 일일체험 목록 | 대상·필드 | 인터페이스·접근·정책·우선순위 |
|---:|---|---|---|---|
| 49 | 국립횡성숲체원 · 강원 횡성 | [프로그램 예약](https://www.sooperang.go.kr/rep/ari/selectPrgmRsrvtList.do?menuNo=1020000) | 유아/초등/가족/단체; 프로그램·날짜·인원·장소·가격 | F: 정상 검색 폼에서 `FA00001` 선택, SSR/AJAX 200, robots 허용, 예약 로그인/대기 가능, B, R1/R4, P1 |
| 50 | 국립장성숲체원 · 전남 장성 | [프로그램 예약](https://www.sooperang.go.kr/rep/ari/selectPrgmRsrvtList.do?menuNo=1020000) | 동일 | F · 기관 `FA00002` · B · R1/R4 · P1 |
| 51 | 국립칠곡숲체원 · 경북 칠곡 | [프로그램 예약](https://www.sooperang.go.kr/rep/ari/selectPrgmRsrvtList.do?menuNo=1020000) | 동일 | F · 기관 `FA00003` · B · R1/R4 · P1 |
| 52 | 국립청도숲체원 · 경북 청도 | [프로그램 예약](https://www.sooperang.go.kr/rep/ari/selectPrgmRsrvtList.do?menuNo=1020000) | 동일 | F · 기관 `FA00004` · B · R1/R4 · P1 |
| 53 | 국립대전숲체원 · 대전 | [프로그램 예약](https://www.sooperang.go.kr/rep/ari/selectPrgmRsrvtList.do?menuNo=1020000) | 동일 | F · 기관 `FA00005` · B · R1/R4 · P1 |
| 54 | 국립춘천숲체원 · 강원 춘천 | [프로그램 예약](https://www.sooperang.go.kr/rep/ari/selectPrgmRsrvtList.do?menuNo=1020000) | 동일 | F · 기관 `FA00006` · B · R1/R4 · P1 |
| 55 | 국립나주숲체원 · 전남 나주 | [프로그램 예약](https://www.sooperang.go.kr/rep/ari/selectPrgmRsrvtList.do?menuNo=1020000) | 동일 | F · 기관 `FA00007` · B · R1/R4 · P1 |

## 6. 기상청 박물관·과학관 7곳 — 프로필 K

| # | 기관·지역 | 공식 교육/행사 목록 | 대상·필드 | 인터페이스·접근·정책·우선순위 |
|---:|---|---|---|---|
| 56 | 국립기상박물관 · 서울 | [교육 프로그램](https://science.kma.go.kr/museum/education/education) | 유아/초등/가족; 기간·장소·대상·인원·비용·문의 | K: SSR 200, 공개 목록, 일부 네이버예약, B, R1/R4, P1 |
| 57 | 국립대구기상과학관 · 대구 | [교육 게시판](https://science.kma.go.kr/daegu/board/education) | 유아/초등/가족/단체; 일정·대상·신청링크 | K · B · R1/R4 · P1 |
| 58 | 국립전북기상과학관 · 전북 정읍 | [교육 프로그램](https://science.kma.go.kr/jbsci/education/program) | 유아/초등/가족/단체; 일정·대상·장소·정원 | K · B · R1/R4 · P1 |
| 59 | 국립밀양기상과학관 · 경남 밀양 | [교육 프로그램](https://science.kma.go.kr/miryang/program/cont1) | 유아/초등/가족; 일정·대상·신청 | K · B · R1/R4 · P1 |
| 60 | 국립충주기상과학관 · 충북 충주 | [교육 프로그램](https://science.kma.go.kr/chungju/program/cont1) | 유아/초등/가족; 일정·대상·신청 | K · B · R1/R4 · P1 |
| 61 | 국립충남기상과학관 · 충남 홍성 | [교육 프로그램](https://science.kma.go.kr/chungnam/html/education_01.php) | 유아/초등/가족; 일정·대상·신청 | K · B · R1/R4 · P1 |
| 62 | 국립여수해양기상과학관 · 전남 여수 | [교육 프로그램](https://science.kma.go.kr/yeosu/education/program) | 유아/초등/가족; 해양기상, 일정·대상·신청 | K · B · R1/R4 · P1 |

## 7. 생태·생물·환경 기관 4곳

| # | 기관·지역·유형 | 공식 목록/API | HTTP·robots·로그인/WAF | 대상·가격·일정 필드 | 수집성·권리·우선순위 |
|---:|---|---|---|---|---|
| 63 | 국립생태원 · 충남 서천 · 생태 | [생태교육 목록](https://www.nie.re.kr/nieResve/pgm/eclgyEdc/list2.do?menuNo=600010), [생태해설](https://www.nie.re.kr/nieResve/pgm/eclgyIntrprt/list.do?menuNo=600008) | 200 SSR. robots는 봇별 상이하며 Googlebot `/` 차단 규칙이 있어 R3로 보수 운영. 목록 공개, 예약/결제 별도 | 유아/초등/가족/단체; 교육·접수기간, 시간, 대상, 인원, 유/무료, 장소, 상태 | B, R1/R3/R4, P1(서면 협의 전 낮은 빈도) |
| 64 | 국립생물자원관 · 인천 · 생물 | [프로그램 목록](https://www.nibr.go.kr/cmn/wvtex/booking/programList.do), [교육 달력](https://www.nibr.go.kr/cmn/wvtex/booking/programCalendar.do?progrmSeCode=PSCD01) | 200 SSR. robots 404(미게시). 목록·달력 공개, 신청 인증 별도, WAF 없음 | 어린이/청소년/가족/단체; 유형·대상·달력·회차·상태, 상세의 비용/정원 | B, R1/R4, P1 |
| 65 | 국립낙동강생물자원관 · 경북 상주 · 생물 | [교육예약 목록](https://www.nnibr.re.kr/resve/index.do?menu_id=00000440) | 200 SSR(검증 시 정상). robots 404. 목록 공개, 본인확인/예약 별도; 과거 WAF 응답 이력이 있어 백오프 필요 | 유아/초등/가족/단체; 상태·대상·접수/교육기간·시간·방법·가격·달력 | B/C, R1/R4, P1 |
| 66 | 국립호남권생물자원관 · 전남 목포 · 생물 | [교육예약 목록](https://resve.hnibr.re.kr/index.do?menu_id=00000440), [공공데이터 파일](https://www.data.go.kr/data/15118328/fileData.do?recommendDataYn=Y) | 목록 200 SSR. robots 200, 검색류만 차단. 공개 파일 데이터 존재, 예약 별도 | 유아/초등/가족/단체; 장소·프로그램·운영 시작/종료일 등, 상세의 대상·비용·정원 | A, R2(데이터셋 이용조건 확인)+R4, P0 |

## 8. 국립·공공 과학관 5곳

| # | 기관·지역 | 공식 목록 | HTTP·robots·로그인/WAF | 대상·필드 | 수집성·권리·우선순위 |
|---:|---|---|---|---|---|
| 67 | 국립중앙과학관 · 대전 | [교육·과학차량 예약](https://rsvn.science.go.kr/nsm/edcarsvn/edcarsvnList) | 200 SSR + 공개 `edcarsvnListAjax`. robots 404. 목록 공개, 신청 별도 | 초등/가족/단체; 상태·접수/교육일·대상·정원·장소·비용 | A, R1/R4, P0 |
| 68 | 국립과천과학관 · 경기 과천 | [교육관 프로그램 목록](https://www.sciencecenter.go.kr/edu/user/edu/eduList.do) | 200. robots 404. 목록 공개지만 예약·결제는 자녀 계정 로그인; 일부 내부 JSON은 NetFunnel/검증 의존 | 유아/초등/중고등/가족; 접수·교육기간, 대상학년, 비용, 정원, 상태 | B/C, R1/R4, P1; SSR만 수집하고 NetFunnel 우회 금지 |
| 69 | 국립광주과학관 · 광주 | [교육 프로그램](https://www.sciencecenter.or.kr/kor/edu/index.do?menuId=285_317) | 200 SSR. robots `Allow:/`. 목록 공개, 신청 로그인/결제 별도 | 유아/초등/가족/단체; 교육/접수기간·대상·비용·정원·상태 | B, R1/R4, P1 |
| 70 | 국립대구과학관 · 대구 | [교육예약 목록](https://www.dnsm.or.kr/reservation/list.do?searchMenuId=10000000760) | HTTP 200이나 자동 요청에 브라우저 지문 검사 스크립트만 주는 경우가 있음. robots 200 규칙 없음. 신청 별도 | 유아/초등/가족/단체; 일정·대상·정원·비용·상태 | C, R3/R4, P2; 공식 허용/API 문의 전 자동화 보류 |
| 71 | 국립부산과학관 · 부산 | [개인교육 프로그램](https://www.sciport.or.kr/kor/CMS/IndivCurriMgr/curriList.do?mCode=MN038) | 200 SSR. robots `Disallow:/` 후 `/kor/` 허용. 공개 교육 목록, 신청 별도; 간헐적 보안 차단 고려 | 유아/초등/가족/단체; 일정·대상·가격·회차·상태 | B/C, R1/R3/R4, P1; `/kor/` 허용 범위만 |

## 9. 전문 박물관·해양·산림 기관 9곳

| # | 기관·지역·유형 | 공식 목록 | HTTP·robots·로그인/WAF | 대상·필드 | 수집성·권리·우선순위 |
|---:|---|---|---|---|---|
| 72 | 국립민속박물관 어린이박물관 · 서울 | [교육 신청 목록](https://www.nfm.go.kr/kids/cop/bbs/selectBoardList.do?bbsId=BBSMSTR_000000000085) | 200 SSR. robots는 검색 경로만 제한. 목록 공개; 일부 신청 네이버폼/별도 시스템 | 유아/초등/가족/단체; 제목·접수/교육일·대상·상태, 상세의 장소·비용 | B, R1/R4, P1 |
| 73 | 대한민국역사박물관 · 서울 | [교육 프로그램](https://www.much.go.kr/MUCH/contents/M03010100000.do) | 200 SSR. robots 해당 교육 경로 허용. 목록 공개, 신청 별도 | 초등/가족/단체; 일정·신청기간·대상·정원·장소·비용 | B, R1/R4, P1 |
| 74 | 국립고궁박물관 · 서울 | [온라인 교육](https://online.gogung.go.kr/gogung/main/main.do) | 200 SSR. robots는 `/cms/`, `/upload/` 위주 제한. 목록 공개, 신청 별도 | 유아/초등/가족/단체; 상태·교육/접수일·대상·정원·장소 | B, R1/R4, P1 |
| 75 | 국립농업박물관 · 경기 수원 | [교육 예약](https://www.namuk.or.kr/kr/204/subview.do) | 200 SSR. robots `Allow:/`. 프로그램 공개, 신청 별도 | 유아/초등/가족/단체; 프로그램·일정·대상·정원·비용/무료·방법 | B, R1/R4, P1 |
| 76 | 국립해양박물관 · 부산 | [현재 교육](https://www.mmk.or.kr/?folder=education&page=list&type=E&status=present) | 200 SSR. robots 교육 경로 허용. 목록 공개, 예약은 로그인 | 초등가족 프로그램 다수; 제목·교육기간·상태, 상세의 대상·접수·정원·비용 | A/B, R1/R4, P1 |
| 77 | 국립인천해양박물관 · 인천 | [교육 프로그램](https://www.inmm.or.kr/ko/place/education/list.do?menuSeq=3579) | 200 SSR. robots 404. 목록 공개, 신청 별도 | 유아/초등/가족/단체; 상태·교육/접수일·대상·정원·비용·장소 | B, R1/R4, P1 |
| 78 | 국립해양생물자원관(MABIK) · 충남 서천 | [교육 공고 목록](https://www.mabik.re.kr/bbs/BBSMSTR_000000000331/list.do) | 200 SSR. robots는 Googlebot에 `/bbs/` 차단 규칙이 있어 보수적 취급. 신청은 네이버 등 외부일 수 있음 | 유아/초등/가족/단체; 공고일·교육일·대상·비용·신청방법 | B/C, R3/R4, P2(협의 전 수동 링크) |
| 79 | 국립울진해양과학관 · 경북 울진 | [교육 프로그램](https://kosm.or.kr/kosm/bbs/board.do?bbsId=BSD0008) | 200 SSR. robots 404(미게시). 목록 공개; 현장/전화/구글폼/공문 등 프로그램별 | 유아/어린이(8~13)/청소년/가족; 상태·교육/접수기간·시간·장소·정원·대상·비용·문의 | A/B, R1/R4, P1 |
| 80 | 국립수목원 · 경기 포천 | [교육 예약 달력](https://www.kna.go.kr/knaf/user/resve/selectResveCldr.do) | 200 SSR. robots 404. 공개 프로그램/달력, 신청 별도 | 유아/초등/가족/단체; 프로그램·일정·대상·정원·비용·상태 | B, R1/R4, P1 |

## 10. 국공립 어린이·공공도서관 4곳

| # | 기관·지역 | 공식 목록 | HTTP·robots·로그인/WAF | 대상·필드 | 수집성·권리·우선순위 |
|---:|---|---|---|---|---|
| 81 | 국립어린이청소년도서관 · 서울 | [프로그램 신청 목록](https://www.nlcy.go.kr/NLCY/contents/C20100000000.do) | 200 SSR. robots 404. 목록 공개, 신청 별도 | 유아/초등/청소년/가족; 상태·대상·접수기간·일시·장소·신청/정원 | A, R1/R4, P0/P1 |
| 82 | 서울특별시교육청 어린이도서관 · 서울 | [평생교육 프로그램](https://childlib.sen.go.kr/childlib/module/teach/index.do?menu_idx=15&searchCate1=16) | 200 SSR. robots `User-agent:* Disallow:/`이므로 자동수집 금지. 에버러닝/로그인 신청 | 유아/초등/학부모; 강좌·기간·대상·정원·접수상태·비용 | C, R3/R4, P2; 수동 큐레이션/기관 협의 |
| 83 | 국립세종도서관 · 세종 | [교육·문화 프로그램](https://sejong.nl.go.kr/html/c3/c320.jsp?codeId=PRO011&menuId=O362&upperMenuId=O300) | 200 SSR. robots는 `/search/`만 제한. 목록 공개, 신청 로그인 가능 | 어린이/가족/전연령; 제목·기간·접수·대상·정원·장소·비용 | B, R1/R4, P1 |
| 84 | 부산광역시립시민도서관 · 부산 | [온라인 수강신청 목록](https://home.pen.go.kr/yeyak/edu/lib/selectEduList.do?srchRsSysId=siminlib&mi=14554) | 200 SSR. robots 200 공용 규칙. 목록 공개, 신청 통합예약/로그인 | 어린이/가족; 강좌·행사일·대상·정원·비용·신청기간 | B, R1/R4, P1 |

## 11. 농업기술센터·농업교육 6곳

| # | 기관·지역 | 공식 목록 | HTTP·robots·로그인/WAF | 대상·필드 | 수집성·권리·우선순위 |
|---:|---|---|---|---|---|
| 85 | 서울특별시농업기술센터 · 서울 | [교육 카테고리](https://agro.seoul.go.kr/archives/category/education) | robots `Allow:/`(파일/검색 제외). 현재 HTTPS 요청은 `?refresh`로 302되는 경우가 있어 최종 응답 모니터링. 이메일/서울시예약 신청 혼재 | 초등/가족/시민; 교육·모집기간, 방식, 대상, 비용, 장소, 연락처 | B/C, R1/R4, P2 |
| 86 | 인천광역시농업기술센터 · 인천 | [교육·행사 게시판](https://www.incheon.go.kr/agro/AGRO030301) | 200 SSR. robots 404. 목록 공개; 인천 통합예약 로그인 신청 | 어린이/가족/시민; 모집/교육일·대상·인원·비용·장소·방법 | B, R1/R4, P1 |
| 87 | 울산광역시농업기술센터 · 울산 | [교육·체험 목록](https://www.ulsan.go.kr/s/atc/education/1058.ulsan?mId=001006003000000000) | 200 SSR. robots 해당 경로 허용. 목록 공개, 온라인 신청 별도 | 어린이/가족/시민; 대상·정원·장소·교육/접수일·비용·상태 | B, R1/R4, P1 |
| 88 | 청주시농업기술센터 · 충북 청주 | [교육 공고 목록](https://www.cheongju.go.kr/nongup/selectBbsNttList.do?bbsNo=510&integrDeptCode=000100154&key=17211) | 200 SSR. robots `Allow:/`. 목록 공개; 첨부 신청서/전화/온라인 혼재 | 어린이/가족/시민; 공고일·운영일·대상·비용·장소·신청방법 | B, R1/R4, P1 |
| 89 | 서귀포농업기술센터 · 제주 | [교육 공고 목록](https://agri.jeju.go.kr/seogwipo/notice/notice.htm) | 200 SSR. robots에 `/*/notice/` 차단 규칙이 있어 자동수집 금지. 신청 온라인/전화 혼재 | 어린이/가족/시민; 모집/교육일·대상·정원·비용·장소 | C, R3/R4, P2; 기관 협의/공식 API 우선 |
| 90 | 수원시농업기술센터 · 경기 수원 | [교육 공고 게시판](https://www.suwon.go.kr/web/board/BD_board.list.do?bbsCd=1266) | 200 SSR. robots는 민원·검색 등만 제한. 목록 공개, 신청 경로 프로그램별 | 어린이/가족/시민; 제목·모집/교육일·대상·정원·비용·장소 | B, R1/R4, P1 |

## 실제 파싱 가능한 상위 5개 샘플

### 1) MODU — 국립박물관 14곳 공통 SSR DOM

```http
GET https://modu.museum.go.kr/learn?museum=1&searchApplyStatus=ONGOING
```

```text
카드                 #listUl > li .card.type02
상세 ID/URL          a.thumb[onclick*="goDetail("] -> /learn/detail/{id}
제목                 .cont .title
접수 상태            .badge [class^="b_"]
교육기간/대상        .info_text 내부 dt/dd 쌍
기관                 .writer
```

서버 HTML에 데이터가 있으므로 헤드리스 브라우저가 필요 없다. `museum`, `targetCategory`, `searchApplyStatus`, `startDate`, `endDate`, `searchKeyword` 필터를 그대로 쓸 수 있다.

### 2) 국립공원공단 — 22개 공원 공통 HTML fragment

```http
POST https://reservation.knps.or.kr/trprogram/trprogramList.do
Content-Type: application/x-www-form-urlencoded

dept_id=B01&dept_name=지리산&orgnzt_gbn=G&pageNo=1&listScale=10
```

```text
행                   table.table.trail-prod-list tbody tr
열                   번호 | 공원 | 집결장소 | 프로그램명 | 운영기간 | 예약
상세/예약 URL         a.btn.btn-reservation[href]
                     /contents/G/serviceGuide.do?parkId=...&prdId=...&orgnztGbn=G
```

2026-07-15 비로그인 POST에서 현재 프로그램 fragment가 200으로 반환됐다. 페이지의 예약 대기열이나 예약 제출 요청은 호출하지 않는다.

### 3) KYWA — 7개 국립청소년시설 공통 JSON

```http
POST https://booking.kywa.or.kr/reservation/ajax/campReservationList.do
Content-Type: application/x-www-form-urlencoded

multi_center_cd=2,3,4,6,7,8,13&multi_pgm_gb=3101,3131,3151&pageIndex=1
```

```json
{
  "cnt": 29,
  "paginationInfo": {},
  "resultList": [
    {
      "center_cd": "...",
      "pgm_no": "...",
      "pgm_gb": "...",
      "pgm_nm": "...",
      "state_gb": "...",
      "open_from": "...",
      "open_to": "...",
      "receive_from": "...",
      "receive_to": "...",
      "enter_nm": "...",
      "enter_amt": "...",
      "target_cnt": 0,
      "ing_cnt": 0,
      "reservation_cnt": 0,
      "mng_tel": "..."
    }
  ]
}
```

목록 응답은 공개지만 상세 신청은 공식 화면으로 넘긴다. `pgm_no + center_cd + pgm_gb`를 원천 키로 사용한다.

### 4) KOAGI — 국립수목원·정원 4곳 공통 SSR DOM (활성화 보류)

```http
GET https://reserve.koagi.or.kr/reserve/edc/prgrm/aply/BD_selectReserveEdcPrgrmList.do?q_siteSeq=2
```

```text
카드                 ul.gallery-items.gallery-poster-edu > li
프로그램 ID          onclick="opGoPrgrmDtl('{id}')"
제목                 .info-wrap .title > strong
상태                 .badge
필드                 ul.dot-info li
                     접수일시, 참여자, 이용일시, 참가비, 이용대상,
                     신청방법, 모집정원, 모집유형
```

기관 코드는 `2=백두대간`, `3=세종`, `4=한국자생식물`, `5=정원문화원`이다.

### 5) 국립어린이청소년도서관 — 공개 프로그램 목록

```http
GET https://www.nlcy.go.kr/NLCY/contents/C20100000000.do
```

```text
행                   .table_detail ul.cate_list > li.newChangeColor
프로그램 ID          a[href^="javascript:fnDetail("]
상세                 ?schM=view&idx={id}
제목                 .list_info .tit
상태                 .status_default
라벨 필드            대상, 접수, 일시, 장소
신청 현황            .list_info1 (현재 신청수/정원)
```

필터는 `searchStartDt`, `searchEndDt`, `stateCd2`, `categoryCd`, `targetCd`, `searchKeyword`, `recordCountPerPage`다.

## 공통 어댑터 설계 제안

| 어댑터 | 기관 수 | 원천 키 | 증분 수집 | 주의점 |
|---|---:|---|---|---|
| `modu_museum` | 14 | 상세 ID | 목록 필터 + 상세 변경 해시 | MODU 통합 목록과 기관별 목록 중복제거 |
| `knps_trprogram` | 22 | `parkId + prdId` | 공원별 fragment, 운영기간/상태 해시 | 예약/NetFunnel 호출 금지, robots 미게시로 저빈도 |
| `kywa_camp` | 7 | `center_cd + pgm_no + pgm_gb` | JSON 페이지네이션 | 접수수/정원 변동이 잦아 상태만 갱신 |
| `koagi_education` | 4 | 사이트 코드 + 프로그램 ID | 카드/상세 해시 | 무필터 통합 목록은 누락 탐지용; 빈 기관 목록을 장애로 오인하지 않기 |
| `sooperang_day_program` | 7 | 기관 ID + 프로그램 ID/회차 | 기관·날짜별 검색 | 로그인/대기열 밖 공개 검색만 사용 |
| `kma_science_program` | 7 | 사이트 코드 + 게시물/프로그램 ID | 기관별 path strategy | 공통 CMS라도 경로/템플릿이 달라 strategy 분리 |

표준화 필드는 `source_id`, `source_program_id`, `title`, `summary_short`, `institution`, `category`, `audience_min_age`, `audience_max_age`, `grade_tags`, `family_required`, `individual_or_group`, `application_start/end`, `event_start/end`, `session_times`, `capacity`, `remaining`, `price_amount`, `price_text`, `status`, `venue_name`, `address`, `lat/lng`, `application_method`, `canonical_url`, `last_seen_at`, `rights_code`가 적절하다.

## 운영상 보류해야 할 것

- 로그인 후 보이는 신청 가능 좌석을 세션 쿠키로 긁지 않는다. 공개 목록의 정원/상태까지만 사용한다.
- NetFunnel, CAPTCHA, 브라우저 지문 검사를 우회하지 않는다.
- 네이버예약·구글폼·이메일·공문을 대신 제출하지 않는다.
- 사진, 포스터, 상세 설명 전체, 첨부 PDF/HWP를 재배포하지 않는다.
- robots 전체 차단 출처(서울 어린이도서관, 제주 농업 공고 등)는 기관 허가나 공식 데이터 인터페이스가 확보될 때까지 수동 링크로만 운영한다.
- 위치는 프로그램 장소를 우선하고, 없으면 기관 대표 주소를 사용하되 `location_precision=institution`을 표시한다. 방문형/찾아가는 교육은 별도 타입으로 분리한다.

## 다음 검증 순서

1. 우선 어댑터에 각 2개 fixture와 계약 테스트를 만든다. KOAGI는 파서만 유지하고 robots/서면 허용 전에는 활성화하지 않는다.
2. 기관별 연락처로 메타데이터 수집 목적, 주기, User-Agent, 삭제 요청 창구를 알리고 허용 범위를 문서화한다.
3. P1 출처는 일주일간 12~24시간 주기로 관찰해 DOM 안정성, ETag, 차단률을 기록한다.
4. P2 출처는 자동화하지 않고 관리자 큐에 링크만 노출한다.
5. 동일 프로그램이 MODU·기관 홈페이지·지역 통합예약에 동시에 나타날 수 있으므로 `institution + normalized_title + event_start + venue` 근사 중복키를 적용한다.
