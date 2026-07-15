# Samsung Innovation Museum 공개 수집 감사

- 감사일: 2026-07-15 (Asia/Seoul)
- 대상 커넥터: `samsung_innovation_education`
- 공식 운영자: 삼성전자
- 위치: 경기도 수원시 영통구 삼성로 129

## 결론

기존 커넥터는 존재했고 공식 공개 JSON에도 정상 접근했지만, 부모 알림에 필요한 수준으로는 불완전했다.

1. 기존 구현은 교육 프로그램 목록의 `startDate`와 `endDate`를 실제 체험 회차로 저장했다. 라이브 응답에서 이 값은 여러 달에 걸친 **프로그램 운영 범위**이며, 실제 교육일은 공개 상세 페이지의 회차 표에 따로 있다.
2. 목록의 집계 `remainingNum`은 `-107/20`처럼 실제 회차 잔여석으로 사용할 수 없는 값도 있었다. 상세 회차 표에는 `20 / 20`, `2 / 20`, `0 / 20`처럼 회차별 값이 공개된다.
3. 공식 프로그램 메뉴에는 교육과 별도로 **이벤트 목록**이 있으며 기존 커넥터는 이 목록을 읽지 않았다.
4. 보완 구현은 어린이·초등·패밀리 프로그램만 골라 공개 상세 `GET`에서 회차별 날짜, 시간, 접수 기간, 잔여/정원, 상태를 저장하고, 공식 이벤트 JSON의 어린이 대상 항목도 함께 저장한다.

로그인, 회원가입, 예약 제출, 신청자 조회, 예약 확인·취소는 호출하지 않는다.

## 2026-07-15 라이브 실측

| 확인 항목 | 실측 결과 |
|---|---:|
| 교육 목록 `result.total` / 반환 행 | 17 / 17 |
| 현재 수집 창과 겹치는 어린이·초등·패밀리 프로그램 | 6 |
| 공개 상세에서 파싱한 실제 회차 | 15 |
| 공식 이벤트 목록 `result.total` | 3 |
| 초등 대상 이벤트 | 2 |
| 2026-07-15 이후 수집 창에 남은 이벤트 | 0 (두 건 모두 4월·6월 종료) |
| 첫 통합 실행 | fetched 15, stored 15, changed 15, error 0 |
| 같은 DB 두 번째 실행 | fetched 15, stored 15, changed 0, error 0 |
| 저장 JSON의 금지 내부 필드 표식 검사 | 0건 |

현재 회차 15건은 `어린이 연구소` 1~4주차, `[온라인] 어린이 연구소`, `패밀리 스마트 교실`의 실제 회차다. 라이브 저장 범위는 2026-07-18 11:30부터 2026-08-29 15:30까지였다.

## 공식 1차 출처와 공개 계약

### 1. 교육 프로그램 목록

- 공식 UI: [교육 프로그램 예약 목록](https://samsunginnovationmuseum.com/ko/reserve/edu/academyList.do)
- 공개 목록 GET: `https://samsunginnovationmuseum.com/ko/show/selectShowList.json?pageSize=50&showStatus=&fitPerson=&roomNo=&smallPicTitle1=`
- 응답 봉투: `resultCode`, `resultMessage`, `result.total`, `result.list`
- 사용하는 목록 필드: `id`, `showName`, `showStatusNm`, `fitPersonNm`, `fitPersonDetail`, `pepleNumber`, `applyTime1`, `applyTime2`, `startDate`, `endDate`, `remainingNum`, `academyStatus`, `detailInfo`, `showTopic`, `roomNm`, `smallPicPath`, `smallPicTitle1`

목록은 프로그램 발견과 상세 URL 생성에만 쓴다. 실제 체험 회차와 잔여석의 기준은 아래 상세 표다.

### 2. 교육 회차 상세

- 공개 상세 GET: `https://samsunginnovationmuseum.com/ko/reserve/edu/getAcademyDetail.do?showid={id}`
- 공식 상세 예시: [2026 어린이연구소 4주차](https://samsunginnovationmuseum.com/ko/reserve/edu/getAcademyDetail.do?showid=2357)
- 공개 DOM 계약:
  - 제목: `.reservationView__head-category`
  - 대상·장소·주제: `.reservationView__grayBox-item`
  - 회차: `.tableHori__tbody-tr`
  - 회차 열: 교육일정, 접수 기간, 잔여/정원, 신청현황

상세 페이지에는 `reserveAcademy(...)` 버튼과 예약 URL이 함께 들어 있지만 파서는 버튼의 텍스트 상태만 읽는다. `showPlanId`, 예약 코드, `reserveAcademy.do` URL은 읽거나 저장하거나 호출하지 않는다. 회차 식별자는 프로그램 ID와 공개 날짜·시간을 해시해 만들므로 내부 plan ID도 필요 없다.

### 3. 단발성 공식 이벤트

- 공식 UI: [이벤트 목록](https://samsunginnovationmuseum.com/ko/event/eventList.do)
- 공개 목록 GET: `https://samsunginnovationmuseum.com/ko/event/selectEventList.json?pageSize=100&languageCd=ko`
- 상세 canonical: `https://samsunginnovationmuseum.com/ko/event/eventDetail.do?eventid={id}`
- 사용하는 필드: `id`, `eventName`, `eventTypeNm`, `fitPersonNm`, `applyTime1`, `applyTime2`, `startDate`, `endDate`, `pepleNumber`, `remainingNum`, `eventTopic`, `detailInfo`, `smallPicPath`, `smallPicTitle1`, `smallPicTitle2`

라이브 목록에는 초등학생 대상 `S/I/M 아트클래스 ‘Sand of Innovation’`, `[과학 매직쇼] AI와 떠나는 우주 탐험`이 확인됐다. 감사일 기준 종료된 항목이라 현재 이벤트로 저장하지 않았지만, 같은 API에 새 항목이 올라오면 날짜 창과 대상 필터를 통과해 자동 저장된다.

### 4. 공지·뉴스·온라인 학습관 발견 경로

| 경로 | 공식 URL / 공개 GET | 라이브 상태 | 수집 판단 |
|---|---|---|---|
| 공지사항 | [UI](https://samsunginnovationmuseum.com/ko/news/notice_list.do) · `.../ko/news/notice_list.json?pageIndex=1` | 첫 페이지 10건, 총 10페이지. 이벤트 2건과 전시투어 운영 공지가 포함됨 | 이벤트 API와 중복되는 모집 공지는 구조화 이벤트를 우선한다. 운영 변경 감시용 후보 경로로 유지 |
| 푸터 공지 | `https://samsunginnovationmuseum.com/ko/getNoticeList.json` | 공지 일부를 반복 | 공지 목록과 중복이므로 별도 이벤트 생성 안 함 |
| 함께 가요 S/I/M으로 | [UI](https://samsunginnovationmuseum.com/ko/news/news_list.do) · `.../ko/news/news_list.json?pageIndex=1` | 행사 종료 후 보도·후기 중심 | 신청 발견보다 늦으므로 검증·회고용. 모집 소스로 사용하지 않음 |
| 온라인 학습관 | [UI](https://samsunginnovationmuseum.com/ko/onlineEdu/onlineEdu.do) · `.../ko/onlineEdu/onlineEduList.json?limitEnd=100` | 28개 공개 학습 콘텐츠 | 유효하지만 위치 기반 신청형 체험과 다른 evergreen 콘텐츠이므로 별도 카테고리 후보 |
| FAQ | [공식 FAQ](https://samsunginnovationmuseum.com/ko/intro/selectFaqList.do) | 모든 프로그램·교육이 무료라고 명시 | 가격이 따로 게시되지 않으면 `무료` 근거로 사용 |

공지나 뉴스에만 있는 일정을 본문에서 억지로 추정해 이벤트 날짜로 만들지 않는다. 모집 가능한 항목은 구조화된 교육 회차 또는 이벤트 API를 우선하고, 공지는 새 공식 소스 후보를 발견하는 감시 경로로 둔다.

## 공식 SNS 조사

[공식 사이트맵](https://samsunginnovationmuseum.com/ko/statics/operation/siteMap.do), 헤더, 푸터에는 Instagram, Facebook, YouTube, Naver Blog 등 뮤지엄 소유 SNS 링크가 게시되어 있지 않았다. 공식 명칭으로 웹 검색도 교차 확인했지만 뮤지엄이 소유한다고 1차 출처로 검증할 수 있는 별도 SNS 계정은 찾지 못했다. 따라서 이름이 비슷한 비공식 계정을 수집 대상으로 추정하지 않는다.

[Samsung Newsroom Korea](https://news.samsung.com/kr/)에는 뮤지엄 프로그램 기사들이 있으나 대부분 행사 후 보도다. 예를 들어 공식 뉴스룸은 어린이 연구소와 퀴즈 골든벨 운영 사실을 확인하는 보조 1차 출처이지만, 현재 신청 가능 여부는 뮤지엄의 회차 상세가 더 빠르고 정확하다.

## robots와 이용조건

- `https://samsunginnovationmuseum.com/robots.txt`는 감사 시 HTTP 200 `text/html`로 76,296바이트 홈페이지 HTML을 반환했다. 유효한 robots 규칙 파일로 간주할 수 없고, 허용 선언으로 해석하지도 않았다.
- 커넥터는 기본 비활성이다. 정확한 source ID를 `KIDS_RADAR_APPROVED_SOURCES`에 넣는 정책 승인과, `KIDS_RADAR_ROBOTS_OVERRIDE_SOURCES`에 넣는 모호한 robots 응답 확인을 **둘 다** 요구한다. 어느 하나라도 없으면 목록 요청 전에 중단하며, 실제 `Disallow`는 override하지 않는다.
- [공식 이용약관](https://samsunginnovationmuseum.com/ko/statics/operation/conditions.do) 제12조는 사이트 정보·콘텐츠의 복제·송신·출판·배포 등에 사전 승낙을 요구한다. 상용 서비스에서 재배포하려면 삼성전자에 메타데이터 이용·링크 제공 범위를 확인하거나 제휴 승인을 받아야 한다.

현재 구현은 위험을 줄이기 위해 전체 응답이나 상세 본문·이미지를 복제하지 않는다. 공개 사실 필드와 원문 링크 중심으로 저장한다. 두 환경변수는 기술적 운영 확인일 뿐 사전승낙이나 재배포 허가를 대신하지 않는다.

## 개인정보·내부 필드 폐기 확인

라이브 JSON에는 알림 서비스에 불필요한 다음 필드들이 섞여 있었다.

- `accessUserIp`, `loginSessionId`
- `createUserid`, `updateUserid`, `chargerUserid`, `receiverUserid`
- `chargerUserName`
- `email`, `tel`
- 그 밖의 상태·관리용 필드

파서는 사전에 선언한 `PUBLIC_FIELDS`와 `EVENT_PUBLIC_FIELDS`만 새 딕셔너리로 복사한다. 전체 원본 행을 저장하지 않는다. 상세 HTML도 제목·대상·장소·주제와 회차 표의 공개 사실만 저장하며 `onclick` 인수는 폐기한다. 라이브 SQLite의 `raw_json`에서 위 금지 표식을 검색한 결과는 0건이었다.

## 구현·검증 파일

- `src/kids_experience_radar/sources/samsung_innovation.py`
- `tests/test_samsung_innovation.py`
- `tests/fixtures/samsung_innovation_detail.html`
- `tests/fixtures/samsung_innovation_events.json`

테스트는 모든 네트워크 호출이 GET인지, 실제 회차 매핑, 같은 날짜의 시간별 회차 분리, 일정 DOM이 사라졌을 때 fail-loud, 이벤트 날짜 창 필터, 가격·대상 정규화, 내부 식별자·IP·세션·담당자 필드 미저장, 두 승인값 중 하나라도 없을 때 네트워크 전 중단, 명시적 robots 차단 우회 금지를 검증한다.
