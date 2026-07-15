# 차단·점검 소스의 공식 대체 수집 경로 감사

- 감사일: 2026-07-15 (Asia/Seoul)
- 범위: `gyeonggi-deep-discovery.json`의 `hold_robots_deny`, `hold_policy_unknown`, `hold_until_maintenance_ends` 3건
- 원칙: 차단을 기술적으로 우회하지 않고, 같은 운영 주체·지자체가 공개한 별도 목록·RSS·보도자료·예약 포털만 찾는다.

## 결론

세 항목 모두 그대로 포기할 필요는 없었다. 다만 해결 방식은 차단된 URL을 뚫는 것이 아니라 **별도로 공개된 공식 배포면으로 수집원을 옮기는 것**이다.

| 기존 hold | 원래 URL의 상태 | 확인한 공식 대체면 | 판단 |
|---|---|---|---|
| 수원시도서관 통합 강좌·행사 | 구형 `/lecture/lectureList.do`가 점검 페이지만 반환 | 같은 수원시도서관의 `/reserve/lecture/lectureList.do`와 공개 상세 | `suwon_library_child_programs`로 구현 완료 |
| 고양어린이박물관 교육·행사 | 박물관 canonical 사이트가 `User-agent: * / Disallow: /` | 고양시 뉴스포털 검색 목록·상세와 공식 RSS | `goyang_children_museum_city_news`로 구현 완료, 박물관 사이트는 계속 미호출 |
| 삼성화재 모빌리티뮤지엄 | `stm.or.kr/robots.txt`가 유효한 정책 파일 대신 HTTP 412 HTML을 반환 | 삼성화재 본사 도메인의 박물관 소개·캠페인 페이지, 공식 SNS 수동 발견 | 부분 구현만 권고; 전체 일정 대체 피드는 아직 없음 |

핵심 차이는 수집 범위다. 수원시도서관과 고양어린이박물관은 반복 수집 가능한 목록/피드가 확인됐지만, 삼성화재 모빌리티뮤지엄은 삼성화재 본사에 게시되는 일부 캠페인만 구조화할 수 있다. 이를 전체 박물관 일정으로 과장하면 안 된다.

### 라이브 검증 요약

| 요청 | 2026-07-15 결과 |
|---|---|
| `www.suwonlib.go.kr/robots.txt` | HTTP 200 `text/plain`; `/reserve/lecture/` 허용 |
| 수원도서관 통합예약 목록·상세 | HTTP 200 HTML; S/R/W 합계 37건, 상세 필드 확인 |
| `www.goyang.go.kr/robots.txt` | HTTP 200 `text/plain`; `/news/user/bbs/` 허용 |
| 고양 뉴스 검색 목록·상세 | HTTP 200 HTML; 검색 99건/10페이지, 미래 프로그램 상세 확인 |
| 고양 공식 RSS 2개 | HTTP 200 `application/rss+xml`; 각 100 item |
| `www.samsungfire.com/robots.txt` | HTTP 200 `text/plain`; `Allow: /` |
| 삼성화재 소개·`/crmm` | HTTP 200 HTML; 소개는 정상, 캠페인은 2025 종료 콘텐츠 |
| `stm.or.kr/robots.txt` | HTTP 412 HTML; 유효한 robots 정책으로 해석 불가 |

## 1. 수원시도서관: 점검 중인 구형 경로 대신 공식 통합예약 경로 사용

### 확인 결과

기존 원장의 `https://www.suwonlib.go.kr/lecture/lectureList.do`는 감사 시 HTTP 200이지만 648바이트의 `수원시도서관사업소 홈페이지 점검중입니다!` 페이지만 반환했다. 반면 같은 공식 호스트의 [수원시도서관 통합예약시스템](https://www.suwonlib.go.kr/reserve/index.do)은 정상 운영 중이며, 독서문화프로그램 목록과 공개 상세를 로그인 없이 제공한다.

[공식 robots.txt](https://www.suwonlib.go.kr/robots.txt)는 `User-agent: *`에 대해 `/down.asp`, `/member/`만 금지한다. 아래 `/reserve/lecture/` 정보 경로는 금지하지 않는다.

### 반복 수집 계약

목록은 공개 `GET`이다.

[초등 대상 공식 목록 예시](https://www.suwonlib.go.kr/reserve/lecture/lectureList.do?mode=search&searchTargetCdArray=EL&status2Cd=R)

```text
https://www.suwonlib.go.kr/reserve/lecture/lectureList.do
  ?mode=search
  &searchTargetCdArray=IN
  &searchTargetCdArray=EL
  &searchTargetCdArray=FA
  &status2Cd={S|R|W}
  &currentPageNo={N}
  &recordCountPerPage=10
```

- 대상 코드: `IN=유아`, `EL=초등`, `FA=가족`
- 상태 코드: `S=접수예정`, `R=접수중`, `W=대기자접수중`
- 페이지: `currentPageNo`
- 목록 키: `onclick="fnDetail('{lectureIdx}')"`
- 공개 상세: `GET https://www.suwonlib.go.kr/reserve/lecture/lectureDetail.do?lectureIdx={lectureIdx}`

2026-07-15 라이브 실측에서 세 대상 코드의 합집합은 `S 27건`, `R 6건`, `W 4건`이었다. 첫 공개 상세 `lectureIdx=1447654`는 프로그램명, 도서관명, 대상, 교육일시, 장소, 접수기간, 신청방법, 상태, 신청/대기 인원, 재료비, 안내전화를 모두 반환했다. [공개 상세 예시](https://www.suwonlib.go.kr/reserve/lecture/lectureDetail.do?lectureIdx=1447654)

목록은 현재 프로그램뿐 아니라 과거 프로그램도 함께 제공하므로 상태 코드 세 개를 각각 요청하고, 일정·접수 종료가 지난 행은 저장 전에 제외해야 한다. 여러 대상 코드가 붙은 같은 프로그램은 `lectureIdx`로 중복 제거한다.

### 추가 공식 발견면

[도서관 체험교실 안내](https://www.suwonlib.go.kr/reserve/experience/experienceGuide.do)도 같은 통합예약 도메인에서 2026년 운영기간, 대상, 요일·시간, 체험 내용과 신청 방법을 공개한다. 다만 어린이집·유치원 단체 프로그램 비중이 높으므로 개인 초등 가족 알림과는 별도 유형으로 분류해야 한다.

### 구현 경계

- 호출: 목록 `GET`, 공개 상세 `GET`
- 미호출: `lectureApply.do`, 로그인, 나의 예약현황, 신청·취소·결제
- 저장: 공개 일정·대상·장소·비용·정원·상태·원문 링크
- 비저장: 신청자 개인정보, 세션, 쿠키, 신청 화면

구현 source ID: `suwon_library_child_programs`. 심층 원장 상태는 `implemented_official_alternative`로 변경했다.

## 2. 고양어린이박물관: 박물관 사이트는 건드리지 않고 고양시 공식 배포면 사용

### 원래 사이트의 차단은 그대로 존중

`https://www.goyangcm.or.kr/robots.txt`의 `User-agent: * / Disallow: /`는 명시적 전체 차단이다. 해당 도메인의 프로그램·공지·이미지·예약 경로를 크롤링해서는 안 된다.

대신 고양특례시는 산하 고양어린이박물관의 모집·교육·축제 보도자료를 [고양특례시 뉴스포털](https://www.goyang.go.kr/news/)에도 반복 게시한다. 고양시 [robots.txt](https://www.goyang.go.kr/robots.txt)는 기본 `Allow: /`이고 `/www/user/bbs/`, `/edu/intra/`, `/intra/`, `/login/`만 금지한다. 아래 대체 경로는 `/news/user/bbs/`이므로 금지 경로와 다르다.

### 검색 목록·상세 계약

```text
GET https://www.goyang.go.kr/news/user/bbs/BD_selectBbsList.do
  ?q_bbsCode=1090
  &q_searchKey=1000
  &q_searchVal=고양어린이박물관
  &q_currPage={N}
```

[고양어린이박물관 공식 검색 결과 예시](https://www.goyang.go.kr/news/user/bbs/BD_selectBbsList.do?q_bbsCode=1090&q_searchKey=1000&q_searchVal=%EA%B3%A0%EC%96%91%EC%96%B4%EB%A6%B0%EC%9D%B4%EB%B0%95%EB%AC%BC%EA%B4%80&q_currPage=1)

감사 시 전체 검색 `q_searchKey=1000`은 99건, 10페이지를 반환했다. 제목 전용 `q_searchKey=1001`은 77건이어서 종합 기사 본문 속 프로그램을 놓친다. 따라서 `1000`이 맞다. 목록 DOM 계약은 다음과 같다.

- 전체 건수: `.bbs-total strong`
- 행: `tbody tr`
- 제목: `.subject a`
- 식별자: `onclick="fnView('1090','{q_bbscttSn}','/news','{q_estnColumn1}')"`
- 담당 부서: 행의 세 번째 `td`
- 게시일: `td.date`
- 페이지: `q_currPage`

상세 canonical은 다음과 같다.

```text
GET https://www.goyang.go.kr/news/user/bbs/BD_selectBbs.do
  ?q_bbsCode=1090
  &q_bbscttSn={q_bbscttSn}
  &q_estnColumn1={All|Y}
```

상세 제목은 `h3.article-subject`, 담당부서·전화·첨부는 `ul.article-info`, 본문은 `#webView.article-detail`에서 읽는다. `#mobileView`는 같은 내용의 모바일 중복이므로 다시 저장하지 않는다.

2026년 첫 페이지에는 다음처럼 프로그램성이 명백한 공식 게시물이 포함됐다.

- `2026-05-21` 세시풍속 교육 `단오·칠석` 참가자 모집
- `2026-05-15` 문화가 있는 날 연계 교육 `일상 속 뮤지엄: 잠시, 마음`
- `2026-04-29` 어린이날 축제와 하반기 프로그램 예고
- `2025-09-30` 어린이 가족 공공디자인 워크숍 참가자 모집

특히 [세시풍속 `단오·칠석` 공식 상세](https://www.goyang.go.kr/news/user/bbs/BD_selectBbs.do?q_bbsCode=1090&q_bbscttSn=20260521170309845)는 2026-07-15 기준 아직 미래인 칠석 프로그램을 `초등 2~4학년`, `8월 1·2·15·16일`, `7월 중 모집`으로 명시한다. 단오 프로그램에 대해서도 모집 시작 시각, 운영 기간, 대상과 1인당 15,000원 참가비를 공개한다. 즉 이 대체면은 단순 기관 소개가 아니라 실제 부모 알림 필드를 제공한다.

[문화가 있는 날 연계 교육 `일상 속 뮤지엄: 잠시, 마음`](https://www.goyang.go.kr/news/user/bbs/BD_selectBbs.do?q_bbsCode=1090&q_bbscttSn=20260515135041411&q_estnColumn1=All)은 2026년 5월 27일부터 11월 25일까지의 운영기간과 초등 과정·유아 가족 과정을 함께 공개한다. 5월 모집 글이라도 11월 프로그램까지 포함되므로 게시일만으로 만료시키지 말고 본문 운영일을 기준으로 판단해야 한다.

[2026 어린이날 축제 공식 보도자료](https://www.goyang.go.kr/news/user/bbs/BD_selectBbs.do?q_bbsCode=1090&q_bbscttSn=20260429114807441&q_estnColumn1=Y)는 일정·장소와 체험 프로그램 구성을 본문에 공개한다. [고양시 공식 보도자료](https://www.goyang.go.kr/news/user/bbs/BD_selectBbs.do?q_bbsCode=1090&q_bbscttSn=20220603113632610&q_estnColumn1=All)는 박물관 공식 소식 채널로 `@goyangcm`도 직접 확인해 준다.

### 공식 RSS 계약

고양시는 [RSS 서비스 안내](https://www.goyang.go.kr/www/www06/www06_6.jsp)에서 보도자료 RSS 주소를 직접 제공한다. 박물관 명칭을 item 제목·본문에서 필터링하면 HTML 목록보다 적은 요청으로 같은 보도자료를 발견할 수 있다.

```text
GET https://www.goyang.go.kr/news/user/bbs/ND_selectRssList.do
  ?q_bbsCode=1090
  &q_estnColumn1=All
```

보조 고양포커스 피드:

```text
GET https://www.goyang.go.kr/news/user/bbs/ND_selectRssList.do
  ?q_bbsCode=1090
  &q_estnColumn1=Y
```

감사 시 두 피드 모두 최신 100개 item을 반환했다. RSS 2.0 item에서 `title`, `link`, `content:encoded`, `pubDate`, `author`를 사용할 수 있다. 다만 `All` 최신 100개에서는 박물관 일치 항목이 0건, `Y`에서는 제목·본문 기준 2건뿐이었다. RSS는 전체 99건을 검색하는 전용 목록의 대체물이 아니라 새 글을 빠르게 감지하는 보조면이다. `title + content:encoded`에 `고양어린이박물관`이 있는 항목만 통과시키고, 본문에 명시된 모집일·운영일·대상·장소·비용만 저장한다. 날짜가 없거나 행사 종료를 알리는 회고성 기사라면 알림 이벤트로 만들지 않는다.

권장 운영은 RSS 두 개를 매일 읽고, 검색 목록 첫 1~2페이지를 주 1회 확인하며, 최초 도입 때만 10페이지 전체를 백필하는 방식이다. 두 RSS 사이의 중복은 링크의 `q_bbscttSn`으로 제거한다.

### 통합검색 보조면

고양시 전체 콘텐츠에서 새 별칭을 찾을 때는 공식 통합검색의 공개 폼도 사용할 수 있다.

```text
POST https://www.goyang.go.kr/www/search.do

query=고양어린이박물관
collection=ALL
searchField=ALL
sort=DATE/DESC
days=MONTH
viewCount=100
q_currPartPage=1
```

감사 시 321개 결과를 반환했지만, 전용 검색 목록보다 잡음이 많다. 주 1회 보조 발견에만 쓰고 결과 URL이 robots에서 허용된 `/news/user/bbs/`일 때만 후속 조회한다. `/www/user/bbs/` 결과는 후속 요청하지 않는다.

### 구현 경계

- 1순위: `q_searchVal=고양어린이박물관` 검색 목록의 첫 페이지와 통과 행의 공개 상세
- 2순위: 고양시 RSS 2개를 새 글 change detector로 사용
- 3순위: 고양시 통합검색으로 명칭 변형·종합 기사 발견
- 미호출: `goyangcm.or.kr` 전체, 박물관 예약·로그인·결제, 첨부 원본 대량 다운로드
- SNS: [공식 Instagram `@goyangcm`](https://www.instagram.com/goyangcm/)은 수동 발견 및 링크 제공만 하고 자동 로그인·스크롤 수집은 하지 않는다.

구현 source ID: `goyang_children_museum_city_news`. 심층 원장 상태는 `implemented_via_official_city_publication`으로 변경했다. 이 경로는 박물관의 모든 상시 프로그램을 보장하지 않지만, 신청·축제·워크숍 공지를 반복적으로 포착하는 정책 준수 공식 대체 피드다. 기사에는 공공누리 제4유형이 표시되므로 본문·이미지·첨부를 복제하지 않고 제목·일정·대상·비용·장소·연락처 같은 사실 메타데이터와 고양시 원문 링크만 저장한다.

## 3. 삼성화재 모빌리티뮤지엄: 삼성화재 본사 공개면을 부분 수집

### 확인된 정책 경계

박물관 도메인 `https://www.stm.or.kr/robots.txt`는 감사 시 유효한 `text/plain` 정책 대신 HTTP 412 HTML 오류를 반환했다. 이를 허용으로 간주하지 않는다. 또한 Naver Blog RSS 후보 `https://rss.blog.naver.com/stm_blog.xml`은 별도 호스트의 robots가 `User-agent: * / Disallow: /`이므로 자동 수집 대안에서 제외한다.

반면 박물관 운영사인 삼성화재의 [공식 robots.txt](https://www.samsungfire.com/robots.txt)는 `User-agent: * / Allow: /`이다. 삼성화재 본사 도메인에는 다음 두 공개 정보면이 있다.

1. [삼성화재 공식 모빌리티뮤지엄 소개](https://www.samsungfire.com/m/company/M_U04_09_02_001.html): 박물관이 복합문화공간이고 어린이 교통안전교육을 운영한다는 사실과 공식 박물관 링크를 제공한다.
2. [삼성화재 카르르 세이프티 빌리지](https://www.samsungfire.com/crmm): 모빌리티뮤지엄에서 열린 어린이 킥보드 안전교실·스탬프 미션의 공개 일정, 장소, 대상 연령, 비용 조건과 예약 방식을 정적 HTML로 제공한다.

두 번째 페이지는 로그인 없이 공개 `GET`으로 읽을 수 있고, 본문에 다음 구조가 있다.

- 행사명: 제목과 `<h3>/<h4>`
- 일정: `Day`, `Time`
- 장소: 목록 항목
- 대상: `참여 가능 연령`
- 비용·입장 조건: 공통 유의사항
- 신청 URL: 링크로만 존재하며 수집기는 호출하지 않음

다만 2026-07-15 현재 `/crmm` 본문은 2025년 10~11월 행사와 `2025년 12월 14일까지`라는 유지 조건을 담은 종료 콘텐츠였다. 현재 행사로 알리면 안 된다. 이 URL은 삼성화재가 새 캠페인으로 갱신할 가능성을 감시하는 **보조 발견면**일 뿐, 박물관 전체 교육 일정의 대체 목록이 아니다.

### SNS·보도 보조면

- [박물관 공식 Instagram `@samsungtransportationmuseum`](https://www.instagram.com/samsungtransportationmuseum/): 프로그램 선행 발견 후보. 플랫폼 자동 수집 대신 수동 확인·공식 링크 보관만 권고한다.
- [삼성화재 공식 Instagram](https://www.instagram.com/samsungfiretalk/): 삼성화재 공동 캠페인 발견 보조 채널.
- [용인시 공식 관광 게시물](https://www.yongin.go.kr/user/bbs/BD_selectBbs.do?q_bbsCode=1076&q_bbscttSn=20260114103347120&q_clCode=1): 운영시간·요금·주소를 검증하는 지자체 보조 출처다. 프로그램 모집의 주 피드로는 쓰지 않는다.

### 구현 권고

`samsung_mobility_museum_parent_campaigns`라는 별도 보조 커넥터로 삼성화재 본사 도메인만 수집할 수 있다.

- 허용 경로 화이트리스트: 위 공식 소개 페이지와 `/crmm`
- 행사 본문에 명시적 연도·일정·대상·장소가 모두 있을 때만 이벤트 생성
- 종료일이 현재보다 과거면 저장하지 않음
- 일정에 연도가 없으면 같은 본문의 명시적 연도 단서가 없을 때 이벤트 생성 금지
- 신청·Naver 예약·`/crnv`·로그인·결제 링크는 호출 금지

기존 `samsung_mobility_museum` hold는 그대로 유지하되 `partial_official_parent_feed` 보조 상태를 추가하는 것이 정확하다. 전체 프로그램 수집을 원한다면 박물관에 공식 피드 또는 메타데이터 제휴를 요청해야 한다.

## 운영 우선순위

1. `suwon_library_child_programs`: 구현 완료. 매일 1회, 공개 대상·상태 필터와 필요한 페이지를 순회한다.
2. `goyang_children_museum_city_news`: 구현 완료. 공식 검색 목록·상세만 사용하며 박물관 원래 도메인은 요청하지 않는다.
3. `samsung_mobility_museum_parent_campaigns`: 부분 구현. 삼성화재 본사 캠페인만 수집하고 전체 커버리지로 표시하지 않음.
4. 세 source 모두 원문 링크 중심의 사실 메타데이터만 저장하고 이미지·첨부·본문 전체를 재배포하지 않는다.

## 차단 우회로 채택하지 않은 후보

| 후보 | 제외 이유 |
|---|---|
| `goyangcm.or.kr`의 다른 경로·서브페이지 | canonical 도메인의 명시적 `Disallow: /` 적용 |
| `stm.or.kr`의 숨은 XHR·검색 서브도메인 추측 | 정책 미확인 상태에서 엔드포인트 탐색을 접근 허용으로 해석할 수 없음 |
| `rss.blog.naver.com/stm_blog.xml` | RSS 호스트 robots가 명시적으로 전체 차단 |
| Instagram 비공식 API·로그인 쿠키·스크롤 자동화 | 플랫폼 접근 제약 및 로그인 우회가 필요할 수 있음 |
| Naver 예약의 잔여석·신청 API | 예약 정보면이 아니라 거래·계정 경로이며 현재 요청 범위를 벗어남 |

이 감사에서 말하는 대체 경로는 접근제어 우회가 아니다. 운영 주체가 다른 공식 도메인이나 RSS로 다시 공개한 동일 사실을 그 공개 조건 안에서 읽는 방식이다.
