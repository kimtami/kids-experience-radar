# 고양어린이박물관 고양시 뉴스 수집기

확인일: 2026-07-15

## 구현 범위

`goyang_children_museum_city_news`는 박물관 사이트를 요청하지 않는다. 고양특례시가 공개한 뉴스 검색 목록과 공개 상세 글만 읽어 체험·교육의 사실 메타데이터를 만든다.

- 목록: `GET https://www.goyang.go.kr/news/user/bbs/BD_selectBbsList.do`
  - `q_bbsCode=1090`
  - `q_searchKey=1000`
  - `q_searchVal=고양어린이박물관`
  - `q_currPage=1..max_pages`
- 상세: `GET https://www.goyang.go.kr/news/user/bbs/BD_selectBbs.do`
  - `q_bbsCode=1090`
  - `q_bbscttSn=14~20자리 숫자 게시물 ID`
  - `q_estnColumn1`은 빈 값, `All`, `Y`만 허용

[고양시 robots.txt](https://www.goyang.go.kr/robots.txt)의 런타임 확인이 선행된다. 목록의 `fnView('1090', 숫자ID, '/news', ...)` 계약과 일치하지 않는 행은 폐기한다. `/www/user/bbs/`, 로그인, 신청, 결제, 회원, 첨부파일, 이미지, 다운로드 경로는 호출하지 않는다.

## DOM 및 데이터 계약

- 목록 총건수: `.bbs-total strong`
- 목록 행: `table.table-list tbody > tr`
- 제목과 ID: `td.subject a[onclick]`
- 게시일: `td.date`
- 상세 제목: `h3.article-subject`
- 상세 사실 추출 영역: `#webView.article-detail`
- `#mobileView`는 중복 본문이므로 무시

필수 선택자가 사라지거나 결과가 있는데 유효한 숫자 ID 행을 하나도 만들지 못하면 빈 결과로 오인하지 않고 예외를 발생시킨다.

저장하는 값은 게시물 ID·제목·게시일·담당부서, 프로그램명, 일정, 아동 대상, 명시된 가격, 모집/운영 상태, 장소·주소, 공개 연락처뿐이다. 기사 본문, HTML, 이미지 URL, 첨부파일 URL, 신청 링크는 저장하지 않는다.

## 현재 검증된 구조화 예시

- 게시물 `20260521170309845`
  - 칠석 프로그램 `한땀한땀~ 칠석달!`
  - 2026-08-01, 08-02, 08-15, 08-16을 각각 독립 세션으로 생성
  - 대상 `초등학생 2~4학년`을 8~10세로 정규화
  - 모집 상태 `모집예정`, 안내 시점 `7월 중`
  - 칠석 참가비는 기사에 없으므로 단오의 15,000원을 전용하지 않고 미상으로 유지
- 게시물 `20260515135041411`
  - 운영기간 2026-05-27~2026-11-25
  - 초등학생이 포함된 대상과 공개 문의 전화만 구조화
- 장소는 `고양어린이박물관`, 주소는 `경기도 고양시 덕양구 화중로 26`으로 고정한다.

## 라이브 전체 검색 검증

2026-07-15 14:43~14:52 KST에 2026-07-15~12-31 범위와
`max_pages=10`으로 실행했다. 공식 검색의 99개 기사·10페이지를 모두 읽고 기간 내
구조화 세션 5건을 저장했으며, 수집 오류는 0건이었다. 기본 호스트 간격 5초에서
9분 8초가 걸렸다. 총건수·페이지 수·페이지별 행 수·게시물 ID 중복이 맞지 않으면
일부 결과를 성공으로 저장하지 않고 실패하도록 검증한다.

반복 운영의 요청량을 줄이되 누락 보장을 명시적으로 유지하는 후속안은
[`goyang-incremental-cache-design.md`](goyang-incremental-cache-design.md)에 기록했다.

## 코드와 검증

- 구현: `src/kids_experience_radar/sources/goyang_children_museum.py`
- 테스트: `tests/test_goyang_children_museum.py`
- 고정 fixture: `tests/fixtures/goyang_children_museum_*.html`

검증 명령:

```bash
.venv/bin/python -m pytest -q tests/test_goyang_children_museum.py
```
