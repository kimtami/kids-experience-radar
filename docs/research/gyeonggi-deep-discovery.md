# 수원·경기도 체험정보 심층 수집원 조사

검증일: 2026-07-15 (Asia/Seoul)

## 결론

기존 조사에는 수원·경기도의 개별 운영기관이 충분히 들어 있지 않았다. 이번 재조사에서는 **51개 소스 단위**를 공식 원문 기준으로 검증했다. 이 가운데 기존에 이미 구현된 수원시립미술관과 삼성 이노베이션 뮤지엄 2개는 감사 표식이고, 나머지 **49개는 신규 또는 광역 포털보다 세밀한 기관별 수집원**이다. 49개 중 39개는 기존 조사 문서에 전혀 없었고, 10개는 시 통합예약과 일부 겹치지만 자체 공지가 더 빠르거나 더 풍부한 세부 수집원이다.

- P0 21개, P1 25개, P2 4개, P3 1개다. 한국잡월드는 공개 XHR 확인 후 P1에서 P0로 올렸다.
- 12개 경기문화재단 소스는 공통 공개 JSON API로 구현 범위에 들어갔다.
- 최종 원장 상태는 구현 표식 24개, 전용 어댑터 후보 19개, 수동 스키마 후속 7개, 정책 보류 1개다. 이번 추가 구현에는 수원시도서관, 수원 생태환경체험교육관, 경기도서관, 고양시 공식 뉴스 대체면이 포함된다.
- 공식 SNS 주소까지 확인한 소스는 28개다. SNS는 **발견용 신호**로만 사용하고, 최종 이벤트 레코드는 공식 홈페이지/API 원문이 있을 때만 발행한다.
- 전체 원장은 [JSON](./gyeonggi-deep-discovery.json)과 [CSV](./gyeonggi-deep-discovery.csv)에 있다.

## 사용자가 지적한 두 항목

### 1. `수원 경기,장`은 누락이 맞았다

정확한 시설명은 경기문화재단의 **컬처라운지 경기,장**이다. 수원 영통구 경기융합타운, 경기도서관 옆에서 운영한다. 공식 [행사 상세 `/events/318`](https://www.ggcf.kr/events/318)에는 `[컬처라운지 경기,장] 6월 팝업 프로그램`이 공개되어 있고, 대상은 만 5세 이상, 참가비는 무료로 안내되었다. 같은 항목은 경기문화재단 공개 [`/api/events`](https://www.ggcf.kr/api/events?page=1&year=2026&progress=now)에서 장소, 행사기간, 신청기간, 상세 URL까지 JSON으로 내려온다.

따라서 스포츠 경기장 검색으로 처리하면 안 된다. `경기,장`, `컬처라운지`, `플레이:경기`, 경기융합타운 장소 문자열을 기관 식별어로 사용해야 한다.

### 2. 삼성 이노베이션 뮤지엄은 구현되어 있었지만 기본 비활성 상태였다

기존 코드에는 [`samsung_innovation_education`](../../src/kids_experience_radar/sources/samsung_innovation.py) 소스가 있고, 공식 [어린이 교육 목록](https://samsunginnovationmuseum.com/ko/reserve/edu/academyList.do)의 공개 JSON과 상세·이벤트를 읽는다. 다만 명시적 소스 승인 방식이어서 운영자가 활성화하지 않으면 일일 결과에 나타나지 않는다. 이번 통합에서는 구현 유무와 실제 활성화 여부를 별도로 표시해야 한다.

삼성화재 [모빌리티뮤지엄](https://www.stm.or.kr/)은 별도 시설이다. 어린이 교통안전교육 가능성은 높지만 `robots.txt` 요청이 정책 문서가 아니라 412 HTML 오류를 반환했으므로 자동수집 대상으로 승격하지 않았다. 공식 피드 확인 또는 기관 협의 전까지 수동 링크만 유지한다.

## 라이브 재검증 증거

2026-07-15에 원장의 `official_url` 51개를 동일한 메타데이터 전용 사용자 에이전트, 리디렉션 허용, 연결 8초/전체 20초 제한으로 다시 요청했다.

- **51/51 최종 HTTP 200**을 확인했다.
- 리디렉션 후 정규 주소가 달랐던 경기미래교육 양평캠퍼스와 남양주 어린이비전센터는 최종 URL로 원장을 고쳤다.
- 45개 고유 호스트의 `robots.txt`도 별도 확인했다. [고양어린이박물관](https://www.goyangcm.or.kr/robots.txt)은 `User-agent: * / Disallow: /`이므로 그 도메인은 자동수집 금지다. 대신 허용된 고양시 뉴스 공개 목록·상세에서 박물관 프로그램을 구조화한다.
- [부천천문과학관 robots](https://www.astrobucheon.or.kr/robots.txt)은 일반 목록을 막지 않지만 `Crawl-delay: 600`을 명시한다. 일일 1회 수준으로만 접근해야 한다.
- [국립민속박물관 robots](https://nfm.go.kr/robots.txt)의 전체 차단은 `DataForSeoBot`에만 적용되고, 일반 사용자 에이전트에는 교육 목록 경로를 차단하지 않는다.
- robots가 없거나 404인 사이트는 허용으로 간주하지 않았다. 원장에는 `manual_schema_review`, `metadata-only`, `hold`를 분리했다.

경기문화재단 공개 API도 직접 재호출했다.

| 공식 API | 2026-07-15 응답 |
|---|---:|
| [`/api/edus?progress=now`](https://www.ggcf.kr/api/edus?page=1&year=2026&progress=now) | 44건, 9페이지 |
| [`/api/edus?progress=after`](https://www.ggcf.kr/api/edus?page=1&year=2026&progress=after) | 31건, 7페이지 |
| [`/api/events?progress=now`](https://www.ggcf.kr/api/events?page=1&year=2026&progress=now) | 8건, 2페이지 |
| [`/api/events?progress=after`](https://www.ggcf.kr/api/events?page=1&year=2026&progress=after) | 21건, 5페이지 |
| [`/api/exhibitions?progress=now`](https://www.ggcf.kr/api/exhibitions?page=1&year=2026&progress=now) | 12건, 3페이지 |
| [`/api/exhibitions?progress=after`](https://www.ggcf.kr/api/exhibitions?page=1&year=2026&progress=after) | 4건, 1페이지 |

응답에는 `id`, `affiliation_code`, `affiliationName`, `title`, `summary`, `place`, `href`, 행사·신청 시작/종료일, 이미지 URL이 들어 있다. 페이지 HTML을 12번 긁는 대신 API를 한 번 순회한 뒤 소속기관과 장소로 분리할 수 있다.

수원 쪽에서는 [수원문화재단 교육정보](https://www.swcf.or.kr/?p=30)와 [수원시립미술관 교육](https://suma.suwon.go.kr/edu/edu_list.do)이 각각 HTTP 200으로 현재 프로그램을 노출했다. 수원문화재단 목록에는 `어린이 소리꾼`, `방학특강 홍재서당`, 수원전통문화관 여름학기, 수원시미디어센터 방학교육이 확인되었다. 수원시립미술관은 기존 ODCloud 구현과 중복되므로 새 크롤러 대신 원문 보강용으로만 둔다.

추가 공식 대체면도 라이브로 재검증했다. 점검 페이지만 반환하던 수원도서관 구형 주소 대신 같은 기관의 [통합예약 독서문화프로그램](https://www.suwonlib.go.kr/reserve/lecture/lectureList.do)을 사용하고, [수원 생태환경체험교육관](https://www.suwoneco.com/lmth/02_margorp/margorp_02.asp) 공개 목록·상세와 [경기도서관 프로그램](https://www.library.kr/ggl/community/events/program-list)의 첫 당사자 JSON을 전용 커넥터로 연결했다. 고양어린이박물관은 박물관 호스트를 요청하지 않고 [고양시 뉴스](https://www.goyang.go.kr/news/user/bbs/BD_selectBbsList.do)의 공개 검색·상세만 사용한다.

## 가장 먼저 운영할 소스

| 묶음 | 기관·시설 | 공개 표면 | 조치 |
|---|---|---|---|
| GGCF 공통 API | 경기,장, 경기상상캠퍼스, 경기도·북부 어린이박물관, 경기도박물관, 경기도미술관, 백남준아트센터, 실학박물관, 전곡선사박물관, 남한산성역사문화관, 경기창작캠퍼스, 경기옛길 | `/api/events`, `/api/edus`, `/api/exhibitions` | P0. 공통 API 1회 순회 후 기관 분리 |
| 수원 박물관 3곳 | 수원박물관, 수원광교박물관, 수원화성박물관 | [`progrmList.do`](https://rmuseum.suwon.go.kr/progrm/progrmList.do), 공개 POST `progrmAjaxList.do` | P0. `museumCd=SW/GG/HS`로 한 어댑터에서 분리 |
| 수원문화재단 | 일반 교육, 수원전통문화관, 수원시미디어센터 | [`?p=30`](https://www.swcf.or.kr/?p=30), [`?p=157`](https://www.swcf.or.kr/?p=157), [`?p=307`](https://www.swcf.or.kr/?p=307) | P0. 공통 HTML 파서 + 장소 필터 |
| 도 직속 체험 | [국민안전체험관](https://ggsec.gg.go.kr/sub03_01_01), [미래과학교육원](https://www.gise.kr/gise/main.do) | 공개 일정·공고·상세 | P0. 신청 동작 없이 목록/상세만 |
| 시군 어린이시설 | [화성시어린이문화센터](https://childrenjob.hscity.go.kr/booking/fmcs/1), [부천로보파크](https://robopark.org/ko/main/index.do), [한국만화박물관](https://www.komacon.kr/comicsmuseum/edu/ssad.asp) | 공개 목록·상세 | P0/P1. 통합예약과 ID/제목/기간 중복 제거 |
| 국가·공공기관 | [국립지도박물관](https://www.ngii.go.kr/map/board/list.do?board_code=edudetail_map), [한국잡월드](https://www.koreajobworld.or.kr/page.do?id=48&site=1), [경기시청자미디어센터](https://kcmf.or.kr/KCMF/contents/KCMF050907.do) | 공개 게시판·프로그램 | P1. 유료/무료·대상·신청상태 메타데이터만 |

## 공식 SNS를 사용하는 방법

SNS는 사이트보다 공지가 빠른 경우가 있어 발견 채널로 유용하지만, 게시물 단독으로 운영 레코드를 확정하지 않는다.

1. 공식 홈페이지 푸터가 가리키는 계정만 허용한다.
2. 인스타그램·카카오채널·블로그 게시물에서 제목, 기관명, 날짜 후보를 추출한다.
3. 공식 홈페이지/API에서 같은 프로그램을 찾으면 원문 URL로 승격한다.
4. 원문이 없으면 `discovery_only` 대기열에 두고 알림 본문에는 노출하지 않는다.
5. 비공개 계정, 로그인 벽, 카페/단톡방, 개인 계정, CAPTCHA를 우회하지 않는다.

확인한 대표 계정은 [경기문화재단](https://www.instagram.com/ggcfkr/), [경기상상캠퍼스](https://www.instagram.com/sscampus.kr/), [경기도어린이박물관](https://www.instagram.com/g_childrens_museum), [전곡선사박물관](https://www.instagram.com/jgpmuseum/), [수원문화재단](https://www.instagram.com/swcf_official/), [수원시도서관](https://www.instagram.com/suwon_lib/), [수원 기후변화체험교육관](https://www.instagram.com/swdodream/), [고양어린이박물관](https://www.instagram.com/goyangcm/)이다. 고양어린이박물관은 SNS 발견만 허용하고 공식 사이트 자동수집은 robots 정책 때문에 금지한다.

## 중복 제거 기준

기관 자체 목록과 수원·고양·용인·부천 통합예약이 같은 프로그램을 함께 노출할 수 있다. 우선순위는 `기관 공개 API > 기관 공식 상세 > 지자체 통합예약 상세 > 공식 SNS > 보도자료`다. 정규 키는 가능하면 기관의 `program id`를 쓰고, 없으면 `기관 + 정규화 제목 + 시작일 + 장소` 해시를 사용한다. 신청 상태는 통합예약이 더 정확할 수 있으므로 기관 원문의 설명과 통합예약의 잔여/상태를 병합하되 출처 URL을 모두 보존한다.

## 안전선

- 공개 목록·상세·공식 JSON만 읽는다.
- 로그인, 결제, 예약 제출, 대기열, CAPTCHA, 개인정보 필드는 수집하지 않는다.
- 공개 JSON에 세션·IP·회원 관련 필드가 섞여 있으면 즉시 폐기한다.
- `robots.txt` 전체 차단은 자동수집 금지다. 이번 원장에서는 고양어린이박물관이 해당한다.
- 정책을 확인할 수 없는 삼성화재 모빌리티뮤지엄은 기관 협의 전까지 수동 링크다.
- 고양어린이박물관 원래 도메인은 계속 자동수집 금지이며, 고양시 공식 뉴스 대체면만 허용한다.
- 일일 실행은 조건부 GET, ETag/Last-Modified, 낮은 동시성, 도메인별 속도 제한을 적용한다.
