# 경기권 `manual_schema_review` 9개 소스 공개 수집 경로 실사

- 실사일: 2026-07-15 (KST)
- 대상: `gyeonggi-deep-discovery.json`에서 `implementation_status=manual_schema_review`인 9개 소스
- 판정 기준: 로그인 없이 첫 당사자 사이트가 브라우저에 공개한 목록·상세 HTML, JSON/XHR, RSS 또는 sitemap만 사용
- 금지 경계: 로그인, 회원 전용 화면, 신청·예약 제출, CAPTCHA, 대기열, WAF, 비공개 API, 세션 우회, 사용자 데이터, robots.txt의 명시적 차단 경로는 수집하지 않음
- 주의: 아래 건수와 프로그램 예시는 실사 시점 스냅샷이다. 구현 시 원문 URL과 `fetched_at`을 반드시 보존해야 한다.

후속 구현에서 `suwon_ecology_network`와 `gyeonggi_library_programs` 두 건을 각각 전용 HTML·첫 당사자 JSON 커넥터로 편입했다. 따라서 현재 심층 원장의 `manual_schema_review` 잔여 수는 7개이며, 이 문서는 최초 9개 전수 실사 기록을 그대로 보존한다.

## 결론

9개 중 **8개는 즉시 구현 가능한 첫 당사자 공개 메타데이터 경로**가 확인됐다. **시흥오이도박물관 1개는 사이트와 robots.txt가 모두 반복 시간 초과**여서 우회하지 않고 보류한다.

| source_id | 판정 | 권장 1차 경로 | 실사 결과 |
|---|---|---|---|
| `suwon_ecology_network` | `IMPLEMENT_PUBLIC_HTML` | 환경교육 프로그램 목록 + 상세 | 목록 3건, 상세 필드 확인 |
| `suwon_youth_programs` | `IMPLEMENT_PUBLIC_HTML` | 모집 게시판 + 활동 프로그램 카탈로그 | 모집 게시판 1,912건, 카탈로그 9건 |
| `gg_marine_safety` | `IMPLEMENT_PUBLIC_HTML_METADATA_ONLY` | 체험 코스 목록 + 상세 | 공개 코스 8건 |
| `gyeonggi_library_programs` | `IMPLEMENT_FIRST_PARTY_JSON` | `homepageprogramlist/detail` | 전체 321건, `어린이` 검색 65건 |
| `yongin_imagination_forest` | `IMPLEMENT_PUBLIC_HTML` | 상상의숲 프로그램 게시판 | 39건·4페이지 |
| `siheung_oido_museum` | `HOLD_RUNTIME_AND_ROBOTS_UNKNOWN` | 없음 | 사이트와 robots.txt 모두 시간 초과 |
| `gmocca_icheon` | `IMPLEMENT_PUBLIC_HTML` | 현재/예정 교육 목록 + 상세 | 현재 1건, 예정 0건 |
| `gyeonggi_ceramic_museum` | `IMPLEMENT_PUBLIC_HTML` | 기관 필터 교육 목록 + 상세 | 경기도자박물관 접수중 3건 |
| `goe_north_early_childhood` | `IMPLEMENT_PUBLIC_HTML_AND_XHR` | 가족체험 안내 + 공지 XHR/상세 | 공지 26건·3페이지, 2026 연간 일정 공개 |

`IMPLEMENT`은 **프로그램 안내 메타데이터 수집**을 뜻한다. 실제 신청 가능 좌석 조회, 로그인, 예약 버튼 호출 또는 신청 제출까지 허용한다는 뜻이 아니다.

## robots.txt 선확인 결과

| 호스트 | 실사 응답 | 수집 판단 |
|---|---|---|
| `www.suwoneco.com` | [robots.txt](https://www.suwoneco.com/robots.txt) 200. 세 개의 특정 게시판 경로만 차단 | `/lmth/02_margorp/` 허용 범위 |
| `www.syf.or.kr` | [robots.txt](https://www.syf.or.kr/robots.txt) 404 | 공개 페이지를 저빈도로만 조회. 404를 적극적 허가로 해석하지 않음 |
| `ggmsec.ggbada.co.kr` | [robots.txt](https://ggmsec.ggbada.co.kr/robots.txt) 200. `Googlebot` 그룹에 검색·게시판 차단 규칙 | 일반 UA를 사용하고 Googlebot을 사칭하지 않음. 공개 체험 코스 경로만 조회 |
| `www.library.kr` | [robots.txt](https://www.library.kr/robots.txt) 200. 일부 경로만 차단 | 프로그램 페이지/API는 차단 대상 아님 |
| `www.yicf.or.kr` | [robots.txt](https://www.yicf.or.kr/robots.txt) 200. `/sitesys`만 차단 | 공개 프로그램 게시판 허용 범위 |
| `oidomuseum.siheung.go.kr` | [robots.txt](https://oidomuseum.siheung.go.kr/robots.txt) HTTPS 2회 및 HTTP 1회 시간 초과 | 정책 확인 불가이므로 본문도 수집하지 않고 보류 |
| `www.gmocca.org` | [robots.txt](https://www.gmocca.org/robots.txt) 200. `/admin` 차단 | 공개 교육 경로 허용 범위 |
| `www.kocef.org` | [robots.txt](https://www.kocef.org/robots.txt) 200. 일부 관리·채용 경로 차단 | 공개 교육 신청 안내 목록/상세 허용 범위 |
| `www.goe-aha.kr` | [robots.txt](https://www.goe-aha.kr/robots.txt) 200. `/pCmsMngr/` 차단 | 공개 안내·공지 경로 허용 범위 |

보조 누락 탐지에 사용하는 `www.suwon.go.kr`의 [robots.txt](https://www.suwon.go.kr/robots.txt)도 200이며 `/culture/`는 명시적 차단 대상이 아니다.

## 공통 구현 원칙

1. 고정된 일반 UA와 연락 가능한 서비스 식별자를 사용하고 호스트별 동시성 1, 목록 1회/일을 기본값으로 둔다.
2. `ETag`와 `Last-Modified`가 있으면 조건부 요청을 사용하고, 오류 시 지수 백오프한다.
3. 목록에서 새 ID 또는 내용 해시가 바뀐 ID만 상세를 다시 읽는다.
4. 신청·예약 URL은 `application_url` 문자열로만 보존하고, 크롤러가 이동하거나 POST하지 않는다.
5. HTML 본문의 전화번호·주소는 프로그램 제공기관의 공개 연락처만 저장하며 첨부파일 다운로드는 별도 검토 전까지 하지 않는다.
6. SNS는 공식 사이트가 직접 링크한 계정의 **발견 신호**로만 사용한다. 로그인 벽, 비공개 게시물, 무한 스크롤 또는 플랫폼 우회 수집은 하지 않는다.
7. 기본 정규화 필드는 `source_id`, `source_item_id`, `title`, `summary`, `target_age_text`, `venue_text`, `program_start_at`, `program_end_at`, `apply_start_at`, `apply_end_at`, `fee_text`, `status_text`, `contact_text`, `source_url`, `application_url`, `fetched_at`, `content_hash`다.

---

## 1. `suwon_ecology_network` — 수원시 환경교육네트워크

### 판정

`IMPLEMENT_PUBLIC_HTML`. 기존 시설 홈페이지만 보는 방식 대신, 공식 사이트의 환경교육 프로그램 목록과 상세를 직접 수집할 수 있다.

### 목록

- 메서드/URL: `GET https://www.suwoneco.com/lmth/02_margorp/margorp_02.asp?page={N}`
- 공식 근거: [환경교육 프로그램 목록](https://www.suwoneco.com/lmth/02_margorp/margorp_02.asp?page=1)
- 검색 폼을 쓸 때의 공개 필드: `s_title=program_name|memo`, `s_text`, `page`
- 행: `table.board_list_pro tbody tr`
- 필드: 번호/`idx`, 제목, 교육기간, 대상, 인원, 진행상태
- 상세 링크: `margorp_02_view.asp?idx={idx}&page={N}`

실사 시 HTTP 200, 총 3건이었다. `으라차차생물탐험대`, 가족 대상 프로그램, `어린이농부학교`가 노출됐고 모두 2026년 일정과 `접수중` 상태를 공개했다.

### 상세

- 메서드/URL: `GET https://www.suwoneco.com/lmth/02_margorp/margorp_02_view.asp?idx={idx}&page={N}`
- 공식 예시: [idx 10441 상세](https://www.suwoneco.com/lmth/02_margorp/margorp_02_view.asp?idx=10441&page=1)
- 제목: `.view3 .title h3`
- 구조화 필드: `.view3 .info dl`의 `dt`/`dd`
- 확인된 라벨: `분야안내`, `교육장소`, `대상`, `교육기간`, `인원`, `교육시간`, `금액`, `진행상태`
- 본문: `.substance`

`idx=10441`은 실사 시 장소 `칠보산, 개구리논, 국립농업박물관`, 대상 `초등 1~4학년`, 기간 `2026-08-04~08-07`, 시간 `09:30~11:30`, 금액 `20,000원`, 상태 `접수중`을 반환했다. 위치 기반 분류는 목록 제목이 아니라 상세의 `교육장소`를 사용해야 한다.

### 안전 경계와 보조 발견

- 신청 폼 `margorp_02_write.asp`는 호출하지 않는다.
- 공식 홈페이지가 연결한 [Instagram](https://www.instagram.com/suwoneco_/)은 URL/계정 존재만 보조 신호로 보존한다.
- 수원시 통합 행사 JSON은 아래 “수원권 보조 누락 탐지” 절의 보조 소스로만 쓴다. 전용 상세가 더 정확한 원문이다.

---

## 2. `suwon_youth_programs` — 수원시청소년청년재단

### 판정

`IMPLEMENT_PUBLIC_HTML`. 정적 활동 카탈로그와 시시각각 바뀌는 모집 게시판을 함께 수집해야 누락이 줄어든다. 모집 게시판을 일일 1차, 프로그램 카탈로그를 주간 2차로 권장한다.

### A. 활동 프로그램 카탈로그

- 메서드/URL: `GET https://www.syf.or.kr/web/activitieWebList.do?menuIdx=486&menu_type=E`
- 공식 근거: [활동 프로그램 목록](https://www.syf.or.kr/web/activitieWebList.do?menuIdx=486&menu_type=E)
- 공개 파라미터: `pageindex`, `menu_type=E`, `fac_code`, `gethering_yn`, `st`, `sk`
- `gethering_yn`: `A` 예정, `S` 모집중, `E` 마감, `N` 해당없음
- `st`: `1` 프로그램명, `2` 대상, `3` 운영기간
- 행: `div.boardList ul.list li.item`
- 필드: 시설, 프로그램명, 대상, 운영기간, 주요내용, 모집상태
- 상세: `/web/activitieWebView.do?menuIdx=486&act_seq={act_seq}`

실사 시 HTTP 200, 9건이었다. 상세의 `.boardView`, `h4.tit`, 표 또는 `dt`/`dd`에서 대상, 기간, 내용, 모집 여부, 모집기간, 신청방법, 문의번호를 읽을 수 있다. [act_seq 3945 상세](https://www.syf.or.kr/web/activitieWebView.do?menuIdx=486&act_seq=3945)는 대상·기간·모집 여부·연락처를 공개했다.

### B. 현재 모집 게시판

- 메서드/URL: `GET https://www.syf.or.kr/web/board.do?menuIdx=322&pageindex={N}`
- 공식 근거: [모집 게시판](https://www.syf.or.kr/web/board.do?menuIdx=322)
- 공개 파라미터: `pageindex`, `mode`, `state`, `category_idx`, `st`, `sk`
- `st`: `1` 제목, `2` 내용, `3` 제목+내용, `4` 작성자
- 행: `table tbody tr`
- 필드: 번호, 기관, 제목, 작성자, 등록일, 첨부 여부
- 상세: `/web/board.do?menuIdx=322&bbsIdx={bbsIdx}`

실사 시 HTTP 200, 총 1,912건·192페이지였고 첫 페이지에 2026년 7월 모집 글이 다수 있었다. 매일 첫 2페이지를 읽고 새 `bbsIdx`만 상세화한 뒤 `초등`, `어린이`, `가족`, `청소년` 및 시설명을 기준으로 분류한다.

### 안전 경계

- 신청 링크는 문자열만 저장하고 외부 예약·접수 페이지로 이동하지 않는다.
- robots.txt가 404라는 사실은 수집 허가가 아니다. 동시성 1, 목록 1회/일, 변경 상세만 재조회한다.

---

## 3. `gg_marine_safety` — 경기해양안전체험관

### 판정

`IMPLEMENT_PUBLIC_HTML_METADATA_ONLY`. 체험 코스 설명·대상·요금·회차는 공개 수집할 수 있지만 예약 가능 좌석과 신청 흐름은 제외한다.

### 목록

- 메서드/URL: `GET https://ggmsec.ggbada.co.kr/ggmsec/kor/feel/course/index.do?menuPos=10`
- 공식 근거: [체험 코스 목록](https://ggmsec.ggbada.co.kr/ggmsec/kor/feel/course/index.do?menuPos=10)
- 행: `.gallery_type2_wrap > ul > li`
- 필드: `.gallery_info_area .title`, `.labels`, 요금 `.info_type1` 주변 `dd`, 회차 `.info_type2` 주변 `p .time`, `.memo`
- 상세 키: 카드의 `move_detail(paramKey1,paramKey2)` 인수

실사 시 HTTP 200, 수상 체험과 안전 체험을 합쳐 8개 코스가 공개됐다.

### 상세

- 메서드/URL: `GET https://ggmsec.ggbada.co.kr/ggmsec/kor/feel/course/detail.do?act=detail&idx={paramKey2}&menuPos=10&paramKey1={paramKey1}&paramKey2={paramKey2}`
- 공식 예시: [해양안전 만들기 체험 상세](https://ggmsec.ggbada.co.kr/ggmsec/kor/feel/course/detail.do?act=detail&idx=64&menuPos=10&paramKey1=56&paramKey2=64)
- 필드: 제목, 요금, 회차/시간, 이용대상, 설명, 주의사항

예시 상세는 실사 시 HTTP 200이었고 `해양안전 만들기 체험(~2026.07.25까지)`, `5,000원`, 5개 회차, 초등 1학년 이상은 보호자 없이 참여 가능하다는 공개 안내를 반환했다.

### 안전 경계

- `/apply_course.do`, 로그인 이동, 날짜별 좌석 조회, 예약 POST는 호출하지 않는다.
- Googlebot UA를 사칭하지 않는다.
- 기존 카탈로그의 `/home/kor/contents.do?menuPos=49`보다 현재 canonical `/ggmsec/kor/...` 경로를 사용한다.

---

## 4. `gyeonggi_library_programs` — 경기도서관

### 판정

`IMPLEMENT_FIRST_PARTY_JSON`. 공식 Nuxt 프로그램 화면이 직접 호출하는 동일 호스트 JSON API가 가장 안정적이다.

### 목록 API

- 메서드: `POST`
- URL: `https://www.library.kr/api/homepageprogramlist`
- 화면 근거: [도서관 프로그램](https://www.library.kr/ggl/community/events/program-list)
- 쿼리 파라미터:
  - `manage_code=141674`
  - `search_type=all`
  - `search_text={검색어}`
  - `program_status=0`
  - `user_key=` — 빈 값 유지, 인증을 시도하지 않음
  - `display=10`
  - `page_no={N}`
  - 선택: `program_major_category`, `program_medium_category`, `program_sub_category`
  - `orderby_item=STATUS_PROGRAM_DATE`
  - `orderby=ASC`

응답은 JSON이며 `RESULT_CODE`, `TOTAL_COUNT`, `RESULT_DATA[]`를 반환한다. 실사 시 HTTP 200, 전체 `TOTAL_COUNT=321`; `search_text=어린이`는 65건이었다. 공개된 어린이 경제교실·화폐전시관 견학, 어린이 다문화 프로그램 등은 대상, 운영일, 신청 시작일, 무료 여부를 포함했다.

확인된 주요 스키마:

```text
REC_KEY
PROGRAM_TITLE
PROGRAM_TARGET
PROGRAM_FACILITY_NAME
PROGRAM_START_DATE / PROGRAM_END_DATE
PROGRAM_START_TIME / PROGRAM_END_TIME
PROGRAM_APPLY_START_DATE / PROGRAM_APPLY_END_DATE
PROGRAM_STATUS
PROGRAM_DAYS
PROGRAM_FEE
RECRUITMENT_PERSONNEL_CNT
ONLINE_RECRUITMENT_CNT
NOW_ONLINE_APPLY_CNT
THUMBNAIL_PATH
```

### 상세 API

- 메서드: `POST`
- URL: `https://www.library.kr/api/homepageprogramdetail?rec_key={REC_KEY}`
- 공식 API 경로: [상세 API](https://www.library.kr/api/homepageprogramdetail?rec_key=1364)
- 응답: `RESULT_CODE`, `RESULT_DATA`
- 추가 필드: `PROGRAM_DESC` HTML, `PROGRAM_FEE`, `CONTACT_PHONE`, `ATTACH_FILE_LIST` 및 목록 필드

실사 시 `rec_key=1364`가 HTTP 200과 구조화 상세를 반환했다.

### 안전 경계

- `/checkparticipants`, 프로그램 신청, 로그인·예약 API는 호출하지 않는다.
- `NOW_ONLINE_APPLY_CNT`는 공개 목록 값이지만 좌석 보장으로 표현하지 않는다. `공개 화면 기준 접수 인원`으로만 표시한다.

---

## 5. `yongin_imagination_forest` — 용인어린이상상의숲

### 판정

`IMPLEMENT_PUBLIC_HTML`. 재단 통합 홈페이지의 상상의숲 전용 프로그램 게시판이 정확한 1차 소스다.

### 목록

- 메서드/URL: `GET https://www.yicf.or.kr/lib/cop/bbs/selectBoardList.do?bbsId=calendar2_lib&pageIndex={N}`
- 공식 근거: [상상의숲 프로그램 게시판](https://www.yicf.or.kr/lib/cop/bbs/selectBoardList.do?bbsId=calendar2_lib&pageIndex=1)
- 공개 필드: `bbsId=calendar2_lib`, `pageIndex`, `searchWrd`, `year`, `month`
- 행: `.involved-list__ul__li`
- ID: `fn_inqire_notice('{nttId}','calendar2_lib')`
- 필드: 제목, 운영기간, 운영장소, 모집상태, 포스터
- 상세: `/lib/cop/bbs/selectBoardArticle.do?bbsId=calendar2_lib&nttId={nttId}&pageIndex={N}`

실사 시 HTTP 200, 39건·4페이지였다. `색깔 없는 식물원은 심심해`, `매직컬 피노키오`, `감성체험 가루 나무 모래 흙`, `이야기파티시엘`, `싸운드써커스` 등의 2026 일정과 `모집중/예정/운영종료` 상태가 공개됐다.

### 상세

- 공식 예시: [이야기파티시엘 상세](https://www.yicf.or.kr/lib/cop/bbs/selectBoardArticle.do?bbsId=calendar2_lib&nttId=16624&pageIndex=1)
- 영역: `.involved-view`
- 필드: 제목, 모집기간, 신청방법, 문의, 운영기간, 운영시간, 운영장소, 본문

`nttId=16624`는 실사 시 모집기간, 2026-07-22~08-16 운영기간, 회차, 장소, 전화번호를 공개했다.

### 보조 목록과 안전 경계

- 더 넓은 공연 누락 점검에는 `GET /show/list.do?show_type=lib&viewType=img&page={N}`를 주간 보조 소스로 사용할 수 있다.
- 예약 링크는 저장만 하고 이동하지 않는다.
- 공식 footer의 [Instagram](https://www.instagram.com/yifc_forest/)은 발견 신호로만 사용한다.

---

## 6. `siheung_oido_museum` — 시흥오이도박물관

### 판정

`HOLD_RUNTIME_AND_ROBOTS_UNKNOWN`. **현재 크롤러를 작성하거나 가동하면 안 된다.**

### 실사 결과

- `https://oidomuseum.siheung.go.kr/robots.txt`: HTTPS 2회 시간 초과
- `http://oidomuseum.siheung.go.kr/robots.txt`: 1회 시간 초과
- 상위 시흥시 robots.txt도 시간 초과
- 따라서 본문을 추가로 가져오지 않았다. 프록시, 다른 UA, IP 변경, 검색 캐시로 우회하지 않았다.

공식 도메인의 과거 색인 URL에는 다음 형태가 남아 있지만, **현재 응답·robots 정책·목록 스키마를 확인하지 못했으므로 구현 근거가 아니다.**

- 후보 상세: [programDetail.hs 예시](https://oidomuseum.siheung.go.kr/program/programDetail.hs?programSeq=299&selectDate=2025-06-01)
- 후보 공지: [noticeDetail.hs 예시](https://oidomuseum.siheung.go.kr/service/notice/noticeDetail.hs?notiSeq=206)

과거 노출 형태는 프로그램명, 소개, 대상, 장소, 접수기간, 비용, 문의, 날짜·시간·정원·상태 표를 포함한 것으로 보인다. 그러나 이는 검색 인덱스에 남은 과거 스니펫에 불과하다.

### 재개 조건

다음 셋이 모두 충족된 날에만 다시 실사한다.

1. robots.txt가 정상 응답하고 프로그램 경로가 명시적으로 차단되지 않을 것
2. 공식 목록과 상세가 표준 브라우저 UA로 HTTP 200을 반환할 것
3. 목록의 현재 ID, 페이지네이션, 상세 필드가 라이브 응답에서 확인될 것

그전에는 시흥시의 다른 공개 행사 포털이 해당 박물관 행사를 재게시하는 경우에만 그 **별도 포털 원문**을 독립 소스로 수집한다.

---

## 7. `gmocca_icheon` — 경기도자미술관

### 판정

`IMPLEMENT_PUBLIC_HTML`. sitemap의 오래된 `/education/child`는 현재 404이므로 사용하지 말고, 홈페이지 내비게이션의 현재/예정 교육 경로를 사용한다.

### 목록

- 현재: `GET https://www.gmocca.org/education/current?currentPage={N}&rowCount=8&searchMuseum={filter}`
- 예정: `GET https://www.gmocca.org/education/intended?currentPage={N}&rowCount=8&searchMuseum={filter}`
- 공식 근거: [현재 교육](https://www.gmocca.org/education/current?currentPage=1&rowCount=8&searchMuseum=), [예정 교육](https://www.gmocca.org/education/intended?currentPage=1&rowCount=8&searchMuseum=)
- 공개 파라미터: `currentPage`, `rowCount`, `searchMuseum`
- `searchMuseum`: `torak`, `creation`, `gallary`, `package` 또는 빈 값
- 행: `article.type2.exhibition ul.list > li`
- 필드: `educationId`, 제목 `h4`, 장소 `.place`, 기간 `.date`
- 상세: `/education/view?educationId={educationId}&type=current|intended`

실사 시 현재 목록은 HTTP 200이며 1건(`educationId=126`, 2026 토락교실 상설, 2026-03-01~12-31), 예정 목록은 HTTP 200이며 0건이었다.

### 상세

- 공식 예시: [educationId 126 상세](https://www.gmocca.org/education/view?educationId=126&type=current)
- 필드: 제목, 교육기간, 교육시간, 모집기간, 장소, 대상, 참여방법, 본문, 문의
- 구조: 제목 `h2`, `ul.h-cont li`의 라벨/값, `.detail-cont .text`

### 안전 경계

- 네이버 지도·티켓 등 외부 신청 링크는 문자열로만 보존한다.
- 어린이 적합성은 제목만 보지 말고 대상과 본문에서 `어린이`, `초등`, `가족`, 연령을 추출한다.
- 공식 홈페이지가 직접 연결한 기관 계정은 [Instagram `g.mocca`](https://www.instagram.com/g.mocca/)이다. 기존 카탈로그의 `kocef` 계정과 기관 범위를 혼동하지 않는다.

---

## 8. `gyeonggi_ceramic_museum` — 경기도자박물관

### 판정

`IMPLEMENT_PUBLIC_HTML`. 한국도자재단의 공개 교육 목록을 `경기도자박물관` 기관 필터로 좁히면 바로 쓸 수 있다.

### 목록

- 메서드/URL: `GET https://www.kocef.org/html/apply_list.html?sb_div=1&gubun=2&kstatus=0&page={N}`
- 공식 근거: [경기도자박물관 교육 목록](https://www.kocef.org/html/apply_list.html?sb_div=1&gubun=2&kstatus=0&page=1)
- 파라미터:
  - `sb_div=1` 교육/체험 목록
  - `gubun=0` 전체, `1` 이천, `2` 경기도자박물관/광주, `3` 기타
  - `kstatus=0` 전체, `1` 접수중, `2` 상시, `3` 마감
  - `page`, `search=1|2|3`, `str`
- 행: `div.pic_board ul > li`
- ID: 상세 링크의 opaque `b_idx`
- 필드: 무료/유료, 상태, 제목, 접수기간, 교육기간, 장소
- 상세: `/html/apply_view.html?sb_div=1&b_idx={b_idx}`

실사 시 HTTP 200, `gubun=2`에 접수중 3건이 있었다. 가족 공동 프로그램, `달그락 꾸러미`, `수리수리 매직머그`가 각각 접수·교육기간과 장소를 공개했다.

### 상세

- 공식 예시: [b_idx=NzIg 상세](https://www.kocef.org/html/apply_view.html?sb_div=1&b_idx=NzIg)
- 필드: 제목, 유·무료, 상태, 교육기간, 접수기간, 장소, 대상, 비용, 문의, 본문, 신청 URL

예시 상세는 실사 시 HTTP 200이며 가족 단위 대상, 장소 `클레이플레이`, 문의 `031-799-1585`를 공개했다. `b_idx`는 디코딩하거나 추측하지 말고 원문 opaque ID로 저장한다.

### 안전 경계

- 외부 신청 링크로 이동하거나 제출하지 않는다.
- 공식 footer의 [블로그](https://blog.naver.com/kocef1), [Instagram](https://www.instagram.com/ceramic_kocef/)은 보조 발견 신호만 담당한다.

---

## 9. `goe_north_early_childhood` — 경기도교육청북부유아체험교육원

### 판정

`IMPLEMENT_PUBLIC_HTML_AND_XHR`. 회원가입이 필요한 예약 단계는 제외하고도, 공식 이용안내의 연간 운영표와 공지 목록/상세에서 일정·대상·모집 안내를 충분히 수집할 수 있다.

이 소스는 주 대상이 만 3~5세이므로 초등학생 전용 피드에서는 `preschool/family` 보조 카테고리로 분리한다. 다만 `유·초 이음 체험`처럼 초등 연계 프로그램이 공지에 올라오므로 완전히 제외하면 안 된다.

### A. 가족체험 연간 안내

- 메서드/URL: `GET https://www.goe-aha.kr/hmpg/prgm/prsn/info/contPageDetail.do?conts_no=0CE123C6B69811EFA22000224D6749B7`
- 공식 근거: [가족체험 이용안내](https://www.goe-aha.kr/hmpg/prgm/prsn/info/contPageDetail.do?conts_no=0CE123C6B69811EFA22000224D6749B7)
- 필드: 대상, 운영기간, 운영시간, 연간 날짜표, 예약 개시일, 회차/정원, 유의사항

실사 시 HTTP 200. 2026년 공개 안내에는 경기도 거주 만 3~5세 유아와 가족, 4~8월 및 9~12월 운영, 10:00~15:00, 총 36회, 회차별 가족 정원과 예약 개시일 표가 포함됐다.

### B. 공지 목록 공개 XHR

화면 shell은 [공지사항](https://www.goe-aha.kr/hmpg/noti/noti/bordContListPage.do?bbs_no=3)이고, 공식 브라우저 JavaScript가 다음 HTML fragment를 호출한다.

- 메서드: `POST`
- URL: `https://www.goe-aha.kr/hmpg/noti/noti/bordContListPgng.do`
- 폼 필드:
  - `miv_pageNo={N}`
  - `miv_pageSize=10`
  - `mode=W`
  - `sidx=NTC_DT_YN DESC, REF_NO DESC, REF_STEP_NO`
  - `sord=ASC`
  - `bbs_no=3`
  - `ctgry_no={선택값 또는 빈 값}`
  - `searchkey=all`
  - `searchtxt={검색어}`
- 응답: HTML fragment
- 총계: `#brdTotalCntTxt`에 삽입되는 값
- ID/제목: `javascript:contDetail('{pst_no}')` 링크 텍스트
- 필드: 중요 여부, 구분 배지, 제목, 작성일, 첨부 여부, 조회수, 페이지 링크

확장자 없는 `/bordContListPgng`는 실사 시 404였고, Java/Spring 매핑의 `.do`가 붙은 위 URL은 HTTP 200이었다. 응답은 실사 시 `검색결과 총 26건 (1/3)`을 반환했고 `2026 아하! 가족 놀이 체험 프로그램 안내`, `2026 아하 놀이체험(기관체험) 예약 안내`, `2026 아하! 유·초 이음 체험 운영 안내`, 생태탐험대 등 공개 체험 공지를 포함했다.

### C. 공지 상세

- 메서드/URL: `GET https://www.goe-aha.kr/hmpg/noti/noti/bordContDetail.do?bbs_no=3&mode=W&pst_no={pst_no}`
- 공식 예시: [2026 가족 놀이 체험 공지](https://www.goe-aha.kr/hmpg/noti/noti/bordContDetail.do?bbs_no=3&mode=W&pst_no=A73F1A9307BE11F19CA8005056895838)
- 필드: 제목, 구분, 작성일, 조회수, 첨부파일명/URL, 본문 HTML

예시 상세는 실사 시 HTTP 200이며 프로그램 안내와 공개 첨부파일 링크를 반환했다. 첨부는 URL과 파일명만 저장하고 자동 다운로드하지 않는다. 보도자료는 동일한 형태의 `/hmpg/noti/bodo/bordContDetail.do?bbs_no=4...`이지만 공지보다 낮은 우선순위의 보조 소스로 둔다.

### 안전 경계

- `/hmpg/prgm/prsn/aply/prsnAplyStep1Page.do`, 기관체험 신청, 마이페이지, 로그인은 호출하지 않는다.
- 공지 본문이 “회원가입 필요”라고 설명하더라도 공개 안내 메타데이터를 읽는 데 회원가입은 필요하지 않다. 실제 예약은 사용자에게 원문 링크만 제공한다.

---

## 수원권 보조 누락 탐지 — 수원시 통합 행사 JSON

수원시 환경교육네트워크와 청소년청년재단의 전용 소스를 대체하지 않지만, 기관이 수원시 통합 행사에도 올린 항목을 교차 검출할 수 있다.

- 메서드/URL: `GET https://www.suwon.go.kr/culture/smartSearchListJson.do`
- 공식 API: [수원시 통합 행사 JSON](https://www.suwon.go.kr/culture/smartSearchListJson.do?q_ingYn=0&q_currPage=1&q_rowPerPage=20&q_cultureNm=)
- 파라미터: `q_ingYn=0`, `q_currPage`, `q_rowPerPage`, `q_cultureNm`
- 응답: `currPage`, `totalNum`, `totalPage`, `dataList[]`
- 주요 필드: `ctrSeqNo`, `cultureNm`, `startDt`, `endDt`, `ctrTarget`, `ctrLocation`, `ticketPrice`, `reserveUrl`, `ctrSummary`, `ctrIntroduction`, `thumbImage`

2026-07-15 실사에서 HTTP 200, `totalNum=33`, 2페이지를 반환했다. 이 피드는 다음 용도로만 쓴다.

1. `초등`, `어린이`, `가족`, `체험`, `교육` 키워드와 수원 시설명으로 누락 후보 생성
2. 전용 원문과 `제목+기간+장소` 유사도로 중복 후보 연결
3. 전용 원문이 있으면 전용 원문을 canonical로 유지

`reserveUrl`은 저장만 하고 호출하지 않는다.

## 구현 우선순위와 권장 주기

| 우선순위 | 소스 | 목록 주기 | 상세 재조회 조건 |
|---|---|---:|---|
| P0 | 경기도서관 JSON, 수원청소년 모집 게시판, 수원환경교육, 용인상상의숲 | 매일 1회 | 새 ID 또는 목록 필드 해시 변경 |
| P1 | 경기해양안전체험관, 경기도자미술관, 경기도자박물관 | 매일 1회 | 새 ID·상태·기간 변경 |
| P1 | 북부유아체험교육원 공지 XHR | 매일 1회 | 새 `pst_no` 또는 제목/날짜 변경 |
| P2 | 북부유아체험교육원 연간 안내, SYF 정적 카탈로그 | 주 1회 | 본문 해시 변경 |
| 보조 | 수원시 통합 행사 JSON | 매일 1회 | 새 `ctrSeqNo` 또는 필드 변경 |
| HOLD | 시흥오이도박물관 | 주 1회 robots/호스트 상태 확인만 | robots와 공식 목록이 정상화된 뒤 수동 재실사 |

## 최종 권고

- 8개 소스는 별도의 우회 기술 없이도 공개된 첫 당사자 목록·상세·XHR만으로 구현 가능하다.
- “회원가입이 필요하다”는 문구는 대부분 **신청 단계**에 해당한다. 공개 안내 목록과 상세의 수집 가능 여부와 분리해야 한다.
- SNS만 바라보지 말고 공식 사이트 목록을 canonical로 삼되, 공식 사이트가 직접 연결한 SNS 계정은 새 프로그램 발견과 원문 역추적용으로만 둔다.
- 시흥오이도박물관은 접근 장애를 우회하지 않는다. 서비스가 정상화되고 robots 정책을 먼저 확인한 뒤 별도 실사해야 한다.
