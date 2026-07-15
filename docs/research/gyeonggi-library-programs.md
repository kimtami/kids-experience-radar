# 경기도서관 어린이·가족 프로그램 공개 JSON 구현

- 구현일: 2026-07-15 (KST)
- source ID: `gyeonggi_library_programs`
- 구현 파일: `src/kids_experience_radar/sources/gyeonggi_library.py`
- 테스트: `tests/test_gyeonggi_library.py`
- 운영 기본값: 명시적 선택이 필요한 keyless opt-in

## 공식 공개 경로

- 프로그램 화면: <https://www.library.kr/ggl/community/events/program-list>
- 목록 메타데이터: `POST https://www.library.kr/api/homepageprogramlist`
- 상세 메타데이터: `POST https://www.library.kr/api/homepageprogramdetail?rec_key={REC_KEY}`
- 공식 상세 화면: `https://www.library.kr/ggl/community/events/program-detail/{REC_KEY}`
- robots.txt: <https://www.library.kr/robots.txt>

2026-07-15 재확인 시 robots.txt는 HTTP 200이었으며 `/api/homepageprogramlist`,
`/api/homepageprogramdetail`, 공개 프로그램 화면을 차단하지 않았다. 크롤러는 각 경로를
요청하기 전에 robots 규칙을 평가한다.

## 재검증으로 바로잡은 응답 스키마

사전 조사 메모에는 목록 배열이 `RESULT_DATA[]`로 기록돼 있었지만, 실제 공개 화면이
사용하는 응답은 다음과 같다.

- 목록 성공: `RESULT_CODE="200"`, `TOTAL_COUNT`, `RESULT_LIST[]`
- 상세 성공: `RESULT_CODE="100"`, `RESULT_DATA`

구현은 이 값을 엄격하게 검사한다. 키 누락, 배열 대신 다른 타입, 중첩 객체가 들어온 공개
필드, 상세 `REC_KEY` 불일치, 잘못된 날짜·시간·Y/N 플래그·재료비, 알 수 없는 상태 코드는
빈 결과로 처리하지 않고 `RuntimeError`로 실패한다. 페이지별 실제 행 수, 누적 고유
`REC_KEY`, 고정된 `TOTAL_COUNT`를 함께 검증하며, 중복·단축 페이지 또는 `max_pages`를
소진한 부분 수집도 오류로 처리한다.

## 수집 및 정규화 방식

목록 요청은 공개 화면과 같은 비인증 쿼리만 사용한다.

```text
manage_code=141674
search_type=all
search_text=
program_status=0
user_key=
display=100
page_no={N}
orderby_item=STATUS_PROGRAM_DATE
orderby=ASC
```

`search_text=어린이`의 실사 결과는 65건이었지만 검색 결과가 엄격한 대상 필터는 아니므로,
커넥터는 이 숫자에 의존하지 않는다. 전체 공개 목록을 페이지 단위로 읽고 운영일이 요청
기간과 겹치는 행의 공개 상세를 보완한 뒤, 병합된 제목·대상·설명에서 `초등`, `어린이`,
`아동`, `유아`, `가족`, `보호자`, `자녀`, `키즈`, `청소년` 등 명시적 근거가 있는 행만
남긴다. 이 순서라서 목록 문구는 일반적이지만 상세 대상이 초등인 프로그램도 놓치지 않는다.
반대로 대상이 성인·교사·교원·강사·전문가 전용이면 제목에 `어린이`가 있어도 제외한다.

목록에 이미 공개된 운영일로 요청 기간을 먼저 검사하므로 기간 밖 행은 상세를 호출하지
않는다. 기간 안 행의 상세에서 일정/시간, 접수기간, 상태, 대상, 장소, 무료·재료비, 공개
설명, 공개 문의번호, 썸네일을 정규화한다. 전용 필터로 확인된 아동·가족 프로그램은 공용
점수기가 `자녀` 같은 표현을 아직 모르는 경우에도 위치 조회 기본 임계값보다 높은 0.55
이상의 관련도 점수를 갖는다.

상태 코드는 공식 Nuxt 화면의 표시 로직과 맞췄다.

- `1`: 접수중
- `2`: 대기접수
- `3`: 접수마감
- `4`: 종료
- `5`: 접수예정
- `6`: 추첨대기 접수

위치 검색용 주소는 경기도서관 공식 서비스가 표기하는
`경기도 수원시 영통구 도청로 40`을 사용하고, 세부 장소는 각 프로그램의
`PROGRAM_FACILITY_NAME`으로 보존한다.

## 개인정보·신청 안전 경계

- `checkparticipants`, `program-apply`, 로그인, 예약, 신청자, 결제, 대기열 경로는 호출하지 않는다.
- `user_key`는 항상 빈 값이며 인증 쿠키나 사용자 세션을 만들지 않는다.
- 응답 전체를 저장하지 않는다. `PUBLIC_RAW_FIELDS`의 공개 프로그램 필드만 보존하며,
  이 필드가 객체·배열이거나 비정상적으로 큰 문자열이면 저장하지 않고 실패한다.
- 라이선스가 명시되지 않은 `PROGRAM_DESC`·`PROGRAM_DESC_TEXT` 본문은 아동 대상 판정과
  기관 공개 전화번호 추출에만 일시 사용하고 `description`이나 `raw`에 복제하지 않는다.
- `MANAGER_NAME`, `WORKER_KEY`, `FIRST_WORK` 같은 관리자·내부 작업 필드는 저장하지 않는다.
- 신청 인원 수는 공개 화면의 참고값일 뿐 좌석 보장으로 표현하지 않는다.
- 썸네일은 `https://hcms.kdot.cloud/upload/` 경로만 허용한다.

## 라이브 검증

2026-07-15 14:17 KST에 2026-07-15~12-31, 최대 4페이지로 직접 실행했다.

- 정규화 결과: 12건
- 공식 상세 경로 일치: 12/12
- 위치 주소 존재: 12/12
- 최소 아동 관련도 점수: 0.55
- 확인 예: 어린이 경제교실 2회, 어린이 다문화 2회, 초등 강연,
  어린이 AI 과정, 청소년 AI·독서토론 프로그램

건수와 상태는 기관 등록·수정에 따라 매일 달라질 수 있다. fixture 회귀 테스트는
목록/상세 스키마, 상세에서 확인되는 아동 대상, 성인 전용 제외, 일정·접수·가격·연령·위치
매핑, raw 필드 화이트리스트, 금지 경로 미호출, 페이지 누락·중복과 스키마 변경 시
fail-loud 동작을 검증한다.
