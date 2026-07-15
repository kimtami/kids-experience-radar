# 수원·경기 상시 수집 구현 감사

조사·라이브 검증일: 2026-07-15 (KST)

## 결론

이전 버전은 전국 후보 수는 많았지만 수원·경기의 실제 일일 수집 밀도가 부족했다. 이번 보완에서는 시설 소개를 저장하는 방식이 아니라, 다음 **13개 source ID**의 반복 갱신 목록을 독립 계약으로 구현했다. 고양시 공식 보도자료처럼 프로그램 날짜를 구조화할 수 있는 공식 대체면만 예외적으로 사용한다.

| source ID | 공식 수집면 | 2026-07-15 라이브 결과 | 동작 |
|---|---|---:|---|
| `ggc_gyeonggi_child_events` | [GGC 공개 Open API](https://ggc.ggcf.kr/openAPI) | 현재 창 3건 | 경기도 전역 문화행사 API를 0-based 페이지네이션 |
| `ggcf_affiliate_child_programs` | [경기문화재단 행사](https://www.ggcf.kr/events)·[교육](https://www.ggcf.kr/edus)·[전시](https://www.ggcf.kr/exhibitions) | 77건 | 산하기관 통합 공개 JSON 세 종류 수집 |
| `ggcf_gyeonggi_jang_programs` | [컬처라운지 경기,장 공식 목록](https://www.ggcf.kr/events) | 1건 | 행사·교육에서 정확한 공간 표지만 상세 확인 |
| `suwon_education_experience` | [수원시 통합예약 교육·강좌·체험](https://www.suwon.go.kr/web/reserv/edu/list.do) | 88~92건 | 접수중·접수준비 공개 표의 회차 사실 수집; 페이지 상한·관측 시점에 따라 변동 |
| `suwon_culture_foundation_education` | [수원문화재단 교육정보](https://www.swcf.or.kr/?p=30) | 12~13건 | 월별 공개 목록과 공식 정보 상세, `idx` 중복 제거 |
| `suwon_museum_child_programs` | [수원시박물관사업소 프로그램](https://rmuseum.suwon.go.kr/progrm/progrmList.do) | 1건 | 공개 검색 POST + 정보 상세 GET; `museumCd=SW` 재검증 |
| `suwon_gwanggyo_museum_child_programs` | 같은 공식 시스템 | 2건 | 응답의 `museumCd=GG`를 다시 검증 |
| `suwon_hwaseong_museum_child_programs` | 같은 공식 시스템 | 2건 | 응답의 `museumCd=HS`를 다시 검증 |
| `suwon_library_child_programs` | [수원시도서관 통합예약](https://www.suwonlib.go.kr/reserve/lecture/lectureList.do) | 67건 | 점검 중인 구형 경로 대신 같은 기관의 정상 공개 목록·상세 사용 |
| `suwon_ecology_child_programs` | [수원 생태환경체험교육관](https://www.suwoneco.com/lmth/02_margorp/margorp_02.asp) | 3건 | 공개 목록·정보 상세만 읽고 신청·결과 경로 제외 |
| `goyang_children_museum_city_news` | [고양시 뉴스](https://www.goyang.go.kr/news/user/bbs/BD_selectBbsList.do) | 99개 기사·10페이지 전체 확인, 기간 내 세션 5건 | 박물관 차단 도메인은 미호출, 시 공식 기사 일정만 구조화 |
| `gyeonggi_library_programs` | [경기도서관 프로그램](https://www.library.kr/ggl/community/events/program-list) | 12건 | 공식 화면이 사용하는 공개 JSON 목록·상세, 신청·참가자 경로 제외 |
| `samsung_innovation_education` | [삼성 이노베이션 뮤지엄 교육](https://samsunginnovationmuseum.com/ko/reserve/edu/academyList.do) | 15회차 | 어린이 교육 상세 회차와 공식 이벤트 JSON 수집 |

라이브 결과 수는 조사일의 2026-07-15~2026-12-31 창 기준이며 모집 변경에 따라 달라진다. 광역 발견용 행은 초등·어린이 근거가 약하면 낮은 관련도 점수로 저장되어 기본 알림에서 빠지고, 명시적인 어린이·가족·학년 정보가 있는 행이 우선 노출된다.

## 1. 경기문화재단 산하기관 통합 JSON

경기문화재단의 공식 행사·교육·전시 페이지가 직접 사용하는 공개 목록은 다음과 같다.

```text
GET https://www.ggcf.kr/api/events?progress=soon&limit=100&page=1
GET https://www.ggcf.kr/api/edus?progress=soon&limit=100&page=1
GET https://www.ggcf.kr/api/exhibitions?progress=soon&limit=100&page=1
```

응답은 `list`, `last_page`, `title`, `summary`, `href`, `place`, `progress`, 운영·접수 기간, `affiliationName`, `affiliation_code`를 제공한다. 수집기는 다음 산하기관을 한 계약으로 분리한다.

- 경기문화재단
- 경기역사문화유산원·남한산성역사문화관
- 경기도박물관
- 경기도미술관
- 백남준아트센터
- 실학박물관
- 전곡선사박물관
- 경기도어린이박물관
- 경기북부어린이박물관
- 경기창작캠퍼스
- 경기상상캠퍼스
- 경기문화예술교육지원센터

라이브 77건의 기관별 분포는 경기상상캠퍼스 24, 경기도어린이박물관 14, 실학박물관 12, 백남준아트센터 8, 경기창작캠퍼스 8, 경기북부어린이박물관 3, 경기도박물관 3, 경기역사문화유산원 2, 경기문화재단 2, 경기도미술관 1이었다. 이 중 63건은 교육·체험, 10건은 행사·체험, 4건은 전시·체험이다.

공식 목록에서 실제 확인된 예시는 다음과 같다.

- 경기도어린이박물관 여름방학 프로그램 6종과 어린이 전파교실
- 경기상상캠퍼스 여름상상캠프, 상상실험실, 생활창작공방
- 실학박물관과 천안홍대용과학관의 별자리 무드등 체험
- 남한산성역사문화관 여름방학 교육과 전통 공예 체험
- 경기상상캠퍼스 어린이 체험 전시 `<우리들의 작은 우주>`
- 경기북부어린이박물관 어린이 전시

`컬처라운지 경기,장`은 전용 상세 커넥터가 더 정확하므로 통합 커넥터에서 제외해 중복을 막는다. 통합 커넥터는 상세·신청 링크를 호출하지 않고 목록에 공개된 사실만 저장한다.

## 2. GGC 경기도 전역 공개 Open API

[공식 Open API 가이드](https://ggc.ggcf.kr/openAPI)는 `GET https://ggc.ggcf.kr/open/json/playongoing`과 `page`, `perpage` 계약을 공개하고, 기관명·제목·분류·상세 URL·주소·시간·비용·문의·주최·시작/종료일 필드를 설명한다. 사이트는 이 정보가 대국민 서비스에 Open API로 제공된다고 명시한다.

구현은 한 페이지 100건으로 0번부터 `CrawlWindow.max_pages`까지 읽는다. 라이브 응답의 종료일 키가 문서와 달리 `enddate:`로 게시되는 사례가 있어 정상 `enddate`와 함께 처리한다. 공식 `https://ggc.ggcf.kr/cultureEvents/view/<24 hex>` 상세만 canonical URL로 인정하며 외부 홈페이지·예약 URL은 호출하지 않는다.

교육 분류는 넓은 발견 후보로 저장하되, 초등·어린이·가족·아동 근거가 없으면 관련도 점수가 낮다. 성인 전용 과정은 제외한다.

## 3. 수원시 통합예약

[수원시 교육·강좌·체험 목록](https://www.suwon.go.kr/web/reserv/edu/list.do)은 공개 표에 다음 필드를 함께 제공한다.

- 강좌명과 숫자형 공식 상세 ID
- 접수 시작·종료일
- 교육 시작·종료일과 요일·시간
- 대상
- 모집·대기 인원
- 교육장소
- 접수중·접수준비·대기접수·마감 상태

공식 `robots.txt`는 민원·검색 등 다른 경로를 제한하지만 `/web/reserv/edu/list.do`는 차단하지 않는다. 수집기는 서버 필터 `q_progressStatusCd=72/73`, `q_rowPerPage=100`, `q_currPage=N`만 사용한다. 상세 ID는 `eduMstSeq` 또는 `seqNo` 숫자만 허용하고 추적·세션성 쿼리는 버린다.

라이브에서는 접수중·접수준비 목록을 확인했고, 성인 전용을 제외한 뒤 수집 창과 겹치는 어린이·가족 또는 체험 가능 프로그램 88~92개를 만들었다. 가족 수목원, 유아숲 가족 탐사, 목공체험, 일월·영흥수목원, 방학 특강이 포함됐다. 페이지가 표시한 공공누리 제4유형을 `KOGL-4`로 기록하며 상용 재사용 전 범위를 검토해야 한다.

## 4. 수원문화재단과 수원 3개 박물관

[수원문화재단 교육정보](https://www.swcf.or.kr/?p=30)는 월별 목록과 숫자형 `idx` 공식 상세를 공개한다. 어린이·가족·전체 체험 후보만 남기고 성인 전용을 제외하며, 같은 프로그램이 여러 달에 반복돼도 `idx`로 한 번만 저장한다. 2026-07-15 라이브 창에서는 방학특강 홍재서당, 어린이 소리꾼, 국악 놀이터, 전통 다식 체험 등을 포함해 12~13건이 관측됐다. 외부 예약·로그인·결제 링크는 호출하지 않는다.

[수원시박물관사업소 프로그램 목록](https://rmuseum.suwon.go.kr/progrm/progrmList.do)은 상태를 바꾸지 않는 공개 검색 POST JSON과 공식 정보 상세 GET을 사용한다. 응답이 요청한 박물관 외 행도 섞어 돌려주는 현행 동작 때문에 각 행의 `museumCd`를 재검증한다. 수원박물관 1건, 수원광교박물관 2건, 수원화성박물관 2건의 공개 사실을 파싱했으며, 신청자 현황·마스킹된 ID·전화번호 영역은 읽거나 저장하지 않는다. 호스트 또는 robots 확인이 간헐적으로 실패하면 기존 결과를 성공으로 가장하지 않고 해당 실행을 fail-closed한다.

수원시·수원문화재단·3개 박물관의 반복 장소는 기관 공식 도로명 주소로 정규화했다. 주소가 확정되지 않은 복수 장소나 온라인·학교 순회 항목은 가짜 주소를 만들지 않고 `None`으로 남겨 `--include-unknown-location` 검토 대상으로 보낸다.

## 5. 공식 대체면과 신규 공개 JSON

수원시도서관 구형 `/lecture/` 주소의 점검 화면은 같은 공식 호스트의 정상 운영 중인 `/reserve/lecture/` 공개 목록으로 교체했다. 수원 생태환경체험교육관은 공개 프로그램 목록과 숫자형 상세만, 경기도서관은 공식 Nuxt 화면이 사용하는 공개 목록·상세 JSON만 읽는다.

고양어린이박물관의 원래 호스트는 `Disallow: /`이므로 요청하지 않는다. 대신 고양특례시 뉴스 검색 목록에서 박물관 기사 ID를 찾고, 같은 고양시 호스트의 공개 상세에 명시된 프로그램 일정·대상·비용·장소만 구조화한다. 기사 본문·이미지·첨부를 복제하지 않는다. 각 계약과 라이브 필드는 `blocked-source-alternatives.md`, `goyang-children-museum-city-news.md`, `gyeonggi-library-programs.md`에 기록했다.

## 6. 삼성 이노베이션 뮤지엄 운영 게이트

공개 목록의 연간 운영기간과 실제 수업일을 혼동하지 않도록 상세 회차 표의 날짜·시간·접수기간·잔여/정원을 기준으로 15회차를 만들었다. 같은 날 11:30과 14:00은 별도 회차이며, 상세 일정 DOM이 사라지면 0건 정상으로 처리하지 않고 오류를 낸다. 같은 DB 두 번째 실행은 15건 모두 `changed=0`이었다.

다만 공식 이용조건에는 사전승낙 조항이 있고 `robots.txt`가 유효한 규칙 대신 홈페이지 HTML을 반환했다. 그래서 정확한 source ID가 `KIDS_RADAR_APPROVED_SOURCES`와 `KIDS_RADAR_ROBOTS_OVERRIDE_SOURCES` 양쪽에 있어야만 네트워크를 허용한다. 이 확인은 서면 허가를 대신하지 않으며, 실제 robots `Disallow`가 관측되면 override하지 않는다. 공개 소스용 일일 plist에서는 제외하고 승인 후 `--source samsung_innovation_education`을 추가한다.

## 7. SNS와 커뮤니티의 역할

공식 SNS는 웹 목록보다 먼저 월별 캘린더를 올리는 경우가 있어 발견면으로 유지한다. 현재 확인된 대표 계정은 [`@gyeonggi_jang`](https://www.instagram.com/gyeonggi_jang/)이다.

운영 원칙은 다음과 같다.

1. 공식 SNS URL과 발견 키워드는 후보 카탈로그에 저장한다.
2. 알림 이벤트는 가능하면 같은 운영기관의 공개 JSON·HTML·보도자료·공식 상세로 재확인한다.
3. Instagram·Naver·Kakao의 로그인, 비공개 글, 회원글, 댓글, 단톡 대화, CAPTCHA, 세션 쿠키를 우회하지 않는다.
4. 카페·단톡 제보는 작성자나 본문을 수집하지 않고 주최기관 공식 URL만 `import-tips`로 받는다.

이 경계는 정보 발견을 포기하는 것이 아니라, 소셜 링크를 레이더로 쓰고 최종 데이터의 출처와 지속성을 공식 원문으로 고정하는 방식이다.

## 구현 파일

- `src/kids_experience_radar/sources/ggc_events.py`
- `src/kids_experience_radar/sources/ggcf_affiliates.py`
- `src/kids_experience_radar/sources/gyeonggi_jang.py`
- `src/kids_experience_radar/sources/suwon_education.py`
- `src/kids_experience_radar/sources/suwon_culture_foundation.py`
- `src/kids_experience_radar/sources/suwon_museums.py`
- `src/kids_experience_radar/sources/suwon_library.py`
- `src/kids_experience_radar/sources/suwon_ecology.py`
- `src/kids_experience_radar/sources/goyang_children_museum.py`
- `src/kids_experience_radar/sources/gyeonggi_library.py`
- `src/kids_experience_radar/sources/samsung_innovation.py`
- 대응 테스트·고정 픽스처: `tests/test_ggc_events.py`, `test_ggcf_affiliates.py`, `test_gyeonggi_jang.py`, `test_suwon_education.py`, `test_suwon_culture_foundation.py`, `test_suwon_museums.py`, `test_suwon_library.py`, `test_suwon_ecology.py`, `test_goyang_children_museum.py`, `test_gyeonggi_library.py`, `test_samsung_innovation.py`

모든 구현은 공개 목록·정보 상세만 사용한다. 수원박물관의 상태를 바꾸지 않는 공개 목록 검색 POST와 경기도서관 공개 JSON 조회 POST 외에는 GET이며, 예약, 신청, 로그인, 결제, 본인확인, 좌석 선점, NetFunnel, 외부 예약 제출은 호출하지 않는다. 공개 12개 source ID의 매일 실행 예시는 `config/com.kidsradar.suwon-gyeonggi.daily.plist.example`에 고정했다.
