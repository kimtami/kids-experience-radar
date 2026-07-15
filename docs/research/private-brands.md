# 기업·브랜드·민간 체험 소스 조사

검증 기준일: **2026-07-15 (Asia/Seoul)**
범위: 전국 기업 체험관·공장 견학·어린이 직업/과학/문화 체험·민간 미술관/박물관·쇼핑몰/문화센터·대기업 사회공헌 교육. 아래에는 이 날짜에 **공식 1차 웹페이지가 실제로 확인된 후보만** 넣었다.

## 먼저 읽을 결론

- 총 **84개 독립 후보**를 확인했다. 같은 기업이라도 지역·신청 단위가 독립된 실제 방문처는 별도 후보로 세었고, 공통 어댑터로 묶을 수 있는 경우는 뒤에서 다시 합쳤다.
- 그중 공식 페이지가 초등/어린이·가족 대상 프로그램, 체험권 또는 공개 강좌 신청을 명시하는 후보가 **30개 이상**이다. 반대로 검증일 현재 마감·목록 없음·성인 중심·중학생 이상·기관 전용인 후보는 표에서 별도로 낮췄다.
- 곧바로 기술 검토할 가치가 큰 소스는 삼성 이노베이션 뮤지엄, 뮤지엄김치간, 현대어린이책미술관, 리움/호암 프로그램, 현대 모터스튜디오 고양, D MUSEUM/대림미술관이다. 이 중 앞의 다섯 구조는 실제 응답/HTML을 다시 파싱해 아래에 샘플을 남겼다.
- `robots.txt` 허용 또는 부재는 이용 허락이 아니다. 민간 페이지는 원칙적으로 제목·기간·장소·대상·가격·상태·공식 URL 같은 **사실 메타데이터만** 저빈도로 읽고, 이미지·설명문·예약자 정보·회원/결제 API는 저장하지 않는다.
- 로그인, 실명 인증, 추첨 지원, 단체 협약, WAF/대기열이 있는 곳은 크롤러가 아니라 `partnership` 대상으로 분류했다. 예약·결제·캡차·회원 API를 자동 호출하는 후보는 없다.
- 단순 상설시설과 현재 모집 가능한 회차를 구분해야 한다. `facility` 후보를 “오늘 신청 가능” 알림으로 승격시키지 않는다.

## 판정 기준

### 목록/구조

- `JSON`: 비로그인 공개 목록 응답이 확인됨
- `HTML`: 서버 HTML의 카드/표/공지 목록을 읽을 수 있음
- `SPA`: 브라우저 렌더링이 필요하거나 내부 구조가 자주 바뀔 가능성이 큼
- `static`: 시설/요금/소개만 있고 반복 모집 목록은 없음
- `PDF`: 공식 PDF/보도자료가 모집 정보의 주 소스
- `empty`: 목록 자체는 공개지만 검증일 현재 대상 결과가 없음

### 수집 권고

- `allowlist`: 법무/운영 승인 후 공개 목록의 화이트리스트 필드만 저빈도 수집
- `metadata-only`: 제목·기간·지역·대상·요금·상태·canonical URL만 수집; 본문/이미지/잔여석/예약 API 제외
- `partnership`: 공식 피드·서면 허가·운영기관 제휴 전 자동수집 금지
- `deny`: robots 전면 차단, 대상 불일치, 폐쇄형 신청, 또는 반복 목록 부재로 자동수집하지 않음

### 정책 표기

- `R-A`: 해당 공개 경로가 [robots 표준](https://www.rfc-editor.org/rfc/rfc9309)에 의해 전면 차단되지는 않음
- `R-N`: robots가 404이거나 의미 있는 규칙이 없음. **허용으로 해석하지 않음**
- `R-X`: 관련 도메인/경로가 전면 차단됨
- `R-W`: 검증 환경에서 WAF/연결 차단/오류가 발생함
- `T-0`: 공식 약관/저작권 표시에서 메타데이터 재사용 허락을 찾지 못함; 출시 전 서면 검토 필요
- `T-1`: 회원·예약·상업 카탈로그 약관이 결합된 서비스; 공개 사실만 읽거나 제휴 필요
- `T-P`: 신청자 선발·기관 협약·개인정보 입력이 본질인 서비스; 파트너십 전용

정책 표시는 2026-07-15 스냅샷이다. 배포 전과 이후 정기적으로 robots·약관·응답 구조를 재확인해야 한다.

## 1. 기업 체험관·공장 견학·브랜드 박물관

| # | 브랜드·지역·프로그램 / 공식 목록 | 공개 여부·구조 | 무료/저가·대상 | robots·약관·예약 장벽 | 권고 |
|---:|---|---|---|---|---|
| 1 | 삼성전자 · 수원 · [Samsung Innovation Museum 어린이 교육](https://samsunginnovationmuseum.com/ko/reserve/edu/academyList.do) | **JSON 공개**: `selectShowList.json`; 교육/신청 기간·대상·상태·잔여 | 공식 관람/교육 안내상 무료, 어린이·가족 | [robots](https://samsunginnovationmuseum.com/robots.txt) `R-N/T-0`; 예약만 로그인. 응답의 IP·세션·사용자 필드는 반드시 폐기 | `allowlist` · **P0** |
| 2 | 현대자동차 · 고양 · [키즈 워크숍](https://motorstudio.hyundai.com/goyang/cotn/exp/kidsWorkShop.do?strgCd=01) | **HTML 공개**: 반복 프로그램 카드와 예약 코드 | 공식 카드 기준 6~13세, 8천~3.3만원 | [robots](https://motorstudio.hyundai.com/robots.txt) `R-A/T-0`; 공개 GET만, 예약 함수 미호출 | `allowlist` · **P0** |
| 3 | 현대자동차 · 서울 · [Motorstudio Seoul](https://motorstudio.hyundai.com/seoul/ln/main.do?strgCd=02) | `static HTML`; 현재 어린이 반복 모집 목록은 별도 확인 필요 | 전시/브랜드 체험, 회차별 대상·비용 확인 | [robots](https://motorstudio.hyundai.com/robots.txt) `R-X/T-0`; `/ln/` 차단이므로 자동수집 금지 | `deny` · P3 |
| 4 | 현대자동차 · 부산 · [Motorstudio Busan](https://motorstudio.hyundai.com/busan/ln/main.do?strgCd=05) | `static HTML`; 전시/행사 소개 중심 | 가족 관람 가능 여부·비용은 행사별 확인 | [robots](https://motorstudio.hyundai.com/robots.txt) `R-X/T-0`; `/ln/` 차단 | `deny` · P3 |
| 5 | 기아 · 서울 · [Kia360 체험](https://www.kia.com/kr/experience/flagship/kia360/experience) | `static/HTML`; 상설 전시와 예약 안내, 반복 어린이 목록 없음 | 전 연령 브랜드 체험; 비용은 개별 페이지 확인 | [robots](https://www.kia.com/robots.txt) `R-A/T-0`; 마이페이지 차단, 예약 흐름 제외 | `metadata-only` · P2 |
| 6 | BMW · 인천 영종 · [Junior Campus](https://driving-center.bmw.co.kr/useAmount/view) | `HTML` 요금/프로그램 표; 일정은 예약 시스템 | 초등 대상, 공식 요금표 1만·1.2만·1.6만원 | [robots](https://driving-center.bmw.co.kr/robots.txt) `R-N/T-1`; BMW OneID 로그인 이후는 수집 금지 | `metadata-only` · P1 |
| 7 | 롯데웰푸드 · 서울 마곡 · [SweetPark 개인 예약 달력](https://sweetpark.lotternd.com/kor/schedule/sweet__schedule.html) | **HTML 공개** 월간 캘린더·회차·잔여/마감 | 공식 안내상 무료; 2026년 기준 출생연도 2017~2021 | [robots](https://sweetpark.lotternd.com/robots.txt) `R-N/T-0`; 달력 GET까지만 | `allowlist` · P1 |
| 8 | 풀무원 · 서울 인사동 · [뮤지엄김치간 어린이김치학교](https://kimchikan.com/rsv/info) | **JSON 공개** 프로그램·달력·회차·잔여 | 6~13세 프로그램, 어린이 무료·보호자 5천원 | [robots](https://kimchikan.com/robots.txt) `R-A/T-0`; `/admin/` 차단, 예약 개인정보 입력 제외 | `allowlist` · **P0** |
| 9 | 하림산업 · 전북 익산 · [First Kitchen Tour](https://www.harim-foods.com/theme/s007/index/tour.php) | 공식 투어 소개/신청 페이지는 존재하나 검증 환경에서 403 | 인원·대상·비용은 공식 신청 화면에서 확인 | [robots](https://www.harim-foods.com/robots.txt) `R-W/T-1`; WAF 우회 금지 | `partnership` · P2 |
| 10 | 서울우유 · 경기 양주 · [공장견학](https://tour.seoulmilk.co.kr/tour/visit_01.php?int_place=1) | `HTML` 견학안내·신청, 장소 파라미터 `int_place=1` | 단체 중심; 공식 페이지에서 정원/운영일 확인 | [robots](https://tour.seoulmilk.co.kr/robots.txt) `R-N/T-1`; 신청/개인정보 제외 | `metadata-only` · P2 |
| 11 | 서울우유 · 경남 거창 · [공장견학](https://tour.seoulmilk.co.kr/tour/visit_01.php?int_place=2) | `HTML`; 거창군 산업관광 연계 안내 | 단체 중심; 비용·대상은 공식 연계 페이지 확인 | [robots](https://tour.seoulmilk.co.kr/robots.txt) `R-N/T-1`; 신청 흐름 제외 | `metadata-only` · P2 |
| 12 | 오뚜기 · 충북 음성 · [대풍공장 견학](https://www.otoki.com/brand/factory-tour) | `HTML` 공개; 검증일 현재 “마감” 표시 | 모집 때 대상/비용 재확인 | [robots](https://www.otoki.com/robots.txt) `R-N/T-0`; 마감 상태 감시만 | `metadata-only` · P2 |
| 13 | POSCO · 경북 포항 · [Park1538 공식 안내](https://www.posco.com/homepage/docs/kor7/jsp/common/posco/s91a1000011c.jsp) | POSCO 공식 안내는 공개; 전용 예약 도메인은 검증 환경 연결 실패 | 전 연령 문화·철 체험; 예약 조건 확인 | [robots](https://park1538.posco.com/robots.txt) `R-W/T-1`; 전용 사이트 우회 금지 | `partnership` · P2 |
| 14 | POSCO · 전남 광양 · [Park1538 Gwangyang 공식 소개](https://newsroom.posco.com/en/gwangyang-once-the-city-of-steel-reborn-as-a-premium-cultural-city-with-the-opening-of-park1538-gwangyang/) | 공식 기업 뉴스/시설 소개; 반복 모집 피드는 미확인 | 가족/일반 관람, 세부 예약 조건 확인 | 전용 [robots](https://park1538.posco.com/robots.txt) `R-W/T-1` | `partnership` · P2 |
| 15 | LG · 서울 마곡 · [LG Discovery Lab 프로그램](https://www.lgdlab.or.kr/program-all) | `SPA/HTML` 공개 목록, 장소·학년 필터 | 공식 안내상 무료; 다수 과정은 중학생 이상, 초6 과정만 선별 | [robots](https://www.lgdlab.or.kr/robots.txt) `R-A/T-0`; 지원/예약 계정 제외 | `metadata-only` · P2 |
| 16 | LG · 부산 · [LG Discovery Lab 프로그램](https://www.lgdlab.or.kr/program-all) | 같은 목록에서 부산 장소 필터 | 공식 안내상 무료; 학년 조건 엄격 | [robots](https://www.lgdlab.or.kr/robots.txt) `R-A/T-0`; 서울과 공통 어댑터 | `metadata-only` · P2 |
| 17 | 넥슨 · 제주 · [Nexon Computer Museum 프로그램](https://www.nexonmuseum.org/ko/program) | React/SPA 공개 목록; 공식 프로그램/공지 | 현재 공개 프로그램은 단체 도슨트 비중이 큼; 비용은 상세 확인 | [robots](https://www.nexonmuseum.org/robots.txt) `R-A/T-0`; 번들 내 헤더/키 노출 금지, 브라우저 렌더링 우선 | `metadata-only` · P2 |
| 18 | 넷마블 · 서울 구로 · [Netmarble Game Museum 공식 소식](https://ch.netmarble.com/ESG/Detail?bbs_code=1010&post_seq=6687) | 공식 뉴스 HTML; 독립 반복 모집 목록은 미확인 | 가족 관람/기획전, 비용·예약은 박물관 공식 안내 확인 | [robots](https://ch.netmarble.com/robots.txt) `R-A/T-0`; 기사 감시만, 전시 DB 복제 금지 | `metadata-only` · P2 |
| 19 | 우리금융 · 서울 · [우리은행 은행사박물관](https://www.woorimuseum.com/wbm/main.do) | 레거시 `.do` HTML; 어린이 금융교육/공지 여부 감시 | 공식 사회공헌 안내의 무료 금융교육 후보; 부모 직접 신청 여부 재확인 | [robots](https://www.woorimuseum.com/robots.txt) `R-N/T-0` | `metadata-only` · P2 |
| 20 | 신한금융 · 서울 · [한국금융사박물관/교육 공식 소개](https://www.shinhangroup.com/kr/archive/business/detail/352) | 기업 아카이브 HTML; 별도 회차 목록 미확인 | 공식 소개상 무료·전 연령, 어린이 프로그램 포함 | [robots](https://www.shinhangroup.com/robots.txt) `R-A/T-P`; 자동수집보다 공식 교육 일정 피드 문의 우선 | `partnership` · P2 |
| 21 | 오설록 · 제주 · [Tea Museum·체험 프로그램](https://www.osulloc.com/kr/ko/store-introduction/jeju-map) | 상설시설 HTML과 외부 예약 링크; 반복 공개 목록은 미확인 | 가족/일반, 체험별 유료 | [robots](https://www.osulloc.com/robots.txt) `R-A/T-1`; 마이페이지·쇼핑·예약 데이터 제외 | `metadata-only` · P3 |

## 2. 민간 미술관·박물관·문화재단

| # | 브랜드·지역·프로그램 / 공식 목록 | 공개 여부·구조 | 무료/저가·대상 | robots·약관·예약 장벽 | 권고 |
|---:|---|---|---|---|---|
| 22 | 현대백화점그룹 · 경기 판교 · [현대어린이책미술관 교육](https://www.hmoka.org/programs/exhibition/list.do?st_cd=480) | **JSON 공개** POST `data.do`; 교육명·기간·대상·장소·요금·상태 | 6세~초6, 공식 목록에 2만원대 프로그램 다수 | [robots](https://www.hmoka.org/robots.txt) `R-A/T-0`; 공개 검색 POST만, 신청 제외 | `allowlist` · **P1** |
| 23 | 삼성문화재단 · 서울 · [리움 프로그램](https://www.leeumhoam.org/leeum/edu/program) | **JSON 공개** 목록 + 상세 EditorJS; 키즈 필터 | 공식 키즈랩 무료 사례, 초3~4 등 회차별 | [robots](https://www.leeumhoam.org/robots.txt) `R-N/T-0`; 예약 로그인 제외, 상태와 종료일 교차검증 | `allowlist` · **P1** |
| 24 | 삼성문화재단 · 경기 용인 · [호암 어린이 프로그램](https://www.leeumhoam.org/leeum/edu/program) | 리움 통합 목록에 호암 장소 프로그램 포함; 상세 URL은 `/hoam/program/{id}` | 공식 상세의 무료 어린이+보호자 사례 | [robots](https://www.leeumhoam.org/robots.txt) `R-N/T-0`; 장소 필드로 분리 | `allowlist` · **P1** |
| 25 | 대림문화재단 · 서울 성동 · [D MUSEUM 교육](https://www.daelimmuseum.org/learn/education/home) | 공개 `api.daelimmuseum.org/v1/program/learn/*` JSON | 공식 목록 사례: 4~10세 3만원, 단체 4~13세 2만원 | [robots](https://www.daelimmuseum.org/robots.txt) `R-N/T-0`; 결제/예약 제외 | `allowlist` · P1 |
| 26 | 대림문화재단 · 서울 종로 · [대림미술관 교육](https://www.daelimmuseum.org/learn/education/home) | D MUSEUM과 같은 공개 API, `eduPlace`로 장소 분리 | 어린이/가족 여부·요금은 회차별 | [robots](https://www.daelimmuseum.org/robots.txt) `R-N/T-0` | `allowlist` · P1 |
| 27 | 아모레퍼시픽 · 서울 용산 · [APMA PROGRAM](https://apma.amorepacific.com/contents/program/index.do) | `HTML` 공개 프로그램 목록/상세 | 검증일 목록은 일반/전문가 프로그램 중심; 어린이 키워드만 감시 | [robots](https://apma.amorepacific.com/robots.txt) `R-A/T-0`; `/api/`, `/ajax/`, 마이페이지 차단 | `metadata-only` · P2 |
| 28 | 롯데문화재단 · 서울 송파 · [Lotte Museum 프로그램](https://www.lottemuseum.com/ko/programs/?cate=event) | `HTML/SPA` 공개 목록/상세 | 어린이·교육 프로그램과 유료 전시, 가격은 상세별 | [robots](https://www.lottemuseum.com/robots.txt) `R-N/T-1`; L.POINT/티켓 흐름 제외 | `metadata-only` · P2 |
| 29 | 한솔문화재단 · 강원 원주 · [Museum SAN 관람 안내](https://www.museumsan.org/guide/visitor) | `static HTML`; 교육은 공지/PDF 분산 | 공식 아동 관람료와 가족 프로그램은 페이지별 확인 | [robots](https://www.museumsan.org/robots.txt) `R-A/T-0`; 반복 모집 목록 미확인 | `metadata-only` · P3 |
| 30 | 헬로우뮤지움 · 서울 성동 · [공식 홈페이지](https://hellomuseum.com/) | 아임웹 HTML/공지/PDF; 어린이 전문 미술관 | 어린이·가족, 비용은 프로그램별 | [robots](https://hellomuseum.com/robots.txt) `R-A/T-0`; 로그인/장바구니 차단 | `metadata-only` · P2 |
| 31 | 사비나미술관 · 서울 은평 · [어린이 교육](https://www.savinamuseum.com/kor/education/education01_childinfo.jsp) | 레거시 JSP HTML; 교육 소개와 뉴스 상세 | 어린이 융복합 미술교육, 비용/일정은 상세별 | [robots](https://www.savinamuseum.com/robots.txt) `R-N/T-0` | `metadata-only` · P2 |
| 32 | 가현문화재단 · 서울 삼청 · [Museum Hanmi](https://museumhanmi.or.kr/) | WordPress HTML·공식 PDF; 시즌 어린이 프로그램 | 어린이/가족, 가격은 공고별 | [robots](https://museumhanmi.or.kr/robots.txt) `R-A/T-0`; RSS는 사이트 공지용으로만 평가 | `metadata-only` · P2 |
| 33 | 모란미술관 · 경기 남양주 · [공식 홈페이지](https://www.moranmuseum.org/) | 아임웹 HTML; 교육/어린이 공모 공지 | 어린이 미술대회·교육, 비용은 공고별 | [robots](https://www.moranmuseum.org/robots.txt) `R-A/T-0`; 로그인 제외 | `metadata-only` · P2 |
| 34 | 포도뮤지엄 · 제주 · [교육·문화 프로그램](https://www.podomuseum.com/program2) | 아임웹 HTML 카드/상세; 2026 프로그램 게시 | 어린이·청소년 관람료 6천원, 일부 공식 프로그램 무료/1만원 | [robots](https://www.podomuseum.com/robots.txt) `R-A/T-0`; 네이버 예약 잔여석은 제외 | `metadata-only` · P2 |
| 35 | 본태박물관 · 제주 · [교육 프로그램](https://bontemuseum.com/academy-jeju) | 아임웹 HTML; 현재 공개 아카데미는 성인 중심 | 검증일 프로그램은 초등 직접 신청과 맞지 않고 고가 멤버십 중심 | [robots](https://bontemuseum.com/robots.txt) `R-A/T-1` | `deny` · P3 |
| 36 | 송은문화재단 · 서울 강남 · [SONGEUN](https://www.songeun.or.kr/) | 공식 전시/프로그램 페이지 존재 | 일반 관람; 어린이 반복 목록 미확인 | [robots](https://www.songeun.or.kr/robots.txt) **`R-X`(Disallow `/`)** | `deny` · P3 |
| 37 | 태진문화재단 · 서울 강남 · [Platform-L](https://platform-l.org/) | HTML/SPA 프로그램; 어린이 키워드 감시 | 프로그램별 대상·가격 | [robots](https://platform-l.org/robots.txt) `R-N/T-0`; Yeti만 명시되어 타 UA 허용으로 단정 금지 | `metadata-only` · P3 |
| 38 | Kunst1 · 부산 · [Museum 1](https://museum1.co.kr/) | 아임웹 HTML; 현재 전시와 티켓 중심 | 가족 관람 가능, 유료; 어린이 교육 목록 미확인 | [robots](https://museum1.co.kr/robots.txt) `R-A/T-1` | `metadata-only` · P3 |
| 39 | 브릭캠퍼스 · 제주 · [전시/체험](https://www.brickcampus.com/page/exhibition?gbn=1) | `HTML`, 지점 파라미터 `gbn=1` | 공식 페이지 1.6만원, 36개월 미만 무료; 체험존 상설 | [robots](https://www.brickcampus.com/robots.txt) `R-A/T-1`; 티켓 제외 | `metadata-only` · P3 |
| 40 | 브릭캠퍼스 · 부산 기장 · [전시/체험](https://www.brickcampus.com/page/exhibition?gbn=2) | `HTML`, `gbn=2`; 운영시간/요금 | 공식 페이지 1.5만원, 36개월 미만 무료 | [robots](https://www.brickcampus.com/robots.txt) `R-A/T-1` | `metadata-only` · P3 |
| 41 | 석파문화원 · 서울 종로 · [석파정 서울미술관 어린이 교육](https://seoulmuseum.org/%EC%96%B4%EB%A6%B0%EC%9D%B4-%EA%B5%90%EC%9C%A1) | 아임웹 HTML 카드; 현재/종료 프로그램 혼재 | 어린이·가족, 가격은 상세별 | [robots](https://seoulmuseum.org/robots.txt) `R-A/T-0`; 종료 여부 필수 | `metadata-only` · P2 |
| 42 | KT&G · 서울 홍대 · [상상마당 아카데미](https://www.sangsangmadang.com/lec/list) | `HTML/JSON성 목록`; 지점·분야 필터 | 대부분 성인/청년 유료, 어린이 키워드만 선별 | [robots](https://www.sangsangmadang.com/robots.txt) `R-N/T-1`; 결제 제외 | `metadata-only` · P3 |
| 43 | KT&G · 강원 춘천 · [상상마당 아카데미](https://www.sangsangmadang.com/lec/list) | 42와 공통 목록, 춘천 장소 필터 | 가족/어린이 결과가 있을 때만 | [robots](https://www.sangsangmadang.com/robots.txt) `R-N/T-1` | `metadata-only` · P3 |
| 44 | KT&G · 부산 · [상상마당 아카데미](https://www.sangsangmadang.com/lec/list) | 42와 공통 목록, 부산 장소 필터 | 가족/어린이 결과가 있을 때만 | [robots](https://www.sangsangmadang.com/robots.txt) `R-N/T-1` | `metadata-only` · P3 |
| 45 | 아라리오 · 제주 · [ARARIO Museum 공식 소개](https://www.arario.com/bbs/content.php?co_id=business02) | `static HTML`; 전시시설 소개, 반복 어린이 목록 없음 | 일반/가족 유료 관람 | [robots](https://www.arario.com/robots.txt) `R-A/T-0`; 관리자 경로 제외 | `metadata-only` · P3 |
| 46 | 파라다이스시티 · 인천 · [Artis Adventure 키즈 패키지](https://www.p-city.com/front/reservation/reservationStep1To2?RP_SEQ=12445) | 공식 예약 상품 HTML; 상시 목록보다는 상품 단위 | 어린이 동반 예술 체험, 숙박/시설 결합 고가 상품 | [robots](https://www.p-city.com/robots.txt) `R-A/T-1`; 관리자·가격·결제·객실 API 제외 | `metadata-only` · P3 |

## 3. 백화점·쇼핑몰·문화센터

| # | 브랜드·지역·프로그램 / 공식 목록 | 공개 여부·구조 | 무료/저가·대상 | robots·약관·예약 장벽 | 권고 |
|---:|---|---|---|---|---|
| 47 | 롯데백화점 · 전국 · [문화센터 강좌](https://culture.lotteshopping.com/index.do) | 레거시 `.do` HTML, 지점/학기/강좌 상세 | 유아·초등 원데이/요리/과학, 유료 다양 | [robots](https://culture.lotteshopping.com/robots.txt) `R-A/T-1`; 회원/결제 제외 | `metadata-only` · P1 |
| 48 | 현대백화점 · 전국 · [문화센터](https://www.ehyundai.com/newCulture/CT/CT000000_M.do) | `.do` HTML/검색; 지점·학기별 | 유아·초등 강좌, 유료 다양 | [robots](https://www.ehyundai.com/robots.txt) `R-N/T-1`; 검색 경로 robots 해석이 불명확해 제휴 우선 | `partnership` · P2 |
| 49 | 현대백화점 · 서울/판교 · [CH 1985](https://www.ehyundai.com/newCulture/CT/CT000000_M.do) | 48과 같은 플랫폼, 브랜드/지점 필터 | 현재 성인 강좌 비중이 높아 어린이 결과만 | [robots](https://www.ehyundai.com/robots.txt) `R-N/T-1` | `partnership` · P3 |
| 50 | 신세계 · 전국 · [신세계 아카데미](https://sacademy.shinsegae.com/sdotcom/MW0010P0/MW0010P0.do) | `.do` HTML/JS, 12개 지점 목록 | 유아·초등 강좌, 유료 다양 | [robots](https://sacademy.shinsegae.com/robots.txt) `R-N/T-1`; 로그인/결제 제외 | `metadata-only` · P2 |
| 51 | AK플라자 · 경기/강원 · [문화아카데미](https://culture.akplaza.com/academy/store01) | SPA/HTML, 분당·수원·평택·원주 | 유아·초등 강좌, 유료 다양 | [robots](https://culture.akplaza.com/robots.txt) `R-N/T-1`; 회원 예약 제외 | `metadata-only` · P2 |
| 52 | 홈플러스 · 전국 · [문화센터](https://mschool.homeplus.co.kr/) | 공식 목록은 있으나 검증 환경 400; 지점·강좌 검색 | 유아·초등 저가 강좌 다수 | [robots](https://mschool.homeplus.co.kr/robots.txt) `R-W/T-1`; 저작권/상업 카탈로그 검토 전 자동수집 금지 | `partnership` · P2 |
| 53 | 갤러리아 · 전국 · [문화센터 공개 강좌](https://dept.galleria.co.kr/g-culture/culture-center/branch/centercity/open-lecture) | HTML/SPA, 지점·강좌 카드 | 유아·초등 강좌, 유료 다양 | [robots](https://dept.galleria.co.kr/robots.txt) `R-N/T-1`; 로그인/결제 제외 | `metadata-only` · P2 |
| 54 | IKEA · 경기 고양 · [매장 이벤트/프로모션](https://www.ikea.com/kr/ko/stores/goyang/) | 공개 CMS HTML; 어린이 생일파티·워크숍 링크 | 무료/회원/유료가 이벤트별 상이, 어린이·가족 | [robots](https://www.ikea.com/robots.txt) `R-A/T-1`; IKEA Family 신청 제외 | `metadata-only` · P1 |
| 55 | IKEA · 경기 광명 · [매장 이벤트](https://www.ikea.com/kr/ko/stores/gwangmyeong/) | 54와 같은 CMS, 지점 slug | 이벤트별 대상·가격 | [robots](https://www.ikea.com/robots.txt) `R-A/T-1` | `metadata-only` · P2 |
| 56 | IKEA · 경기 기흥 · [매장 이벤트](https://www.ikea.com/kr/ko/stores/giheung/) | 54와 같은 CMS, 지점 slug | 어린이/가족 이벤트, 조건별 | [robots](https://www.ikea.com/robots.txt) `R-A/T-1` | `metadata-only` · P2 |
| 57 | IKEA · 부산 동부산 · [매장 이벤트](https://www.ikea.com/kr/ko/stores/dong-busan/) | 54와 같은 CMS, 지점 slug | 어린이/가족 이벤트, 조건별 | [robots](https://www.ikea.com/robots.txt) `R-A/T-1` | `metadata-only` · P2 |
| 58 | IKEA · 서울 강동 · [매장 이벤트](https://www.ikea.com/kr/ko/stores/gangdong/) | 54와 같은 CMS, 지점 slug | 어린이날 등 가족 행사; 일부 IKEA Family 조건 | [robots](https://www.ikea.com/robots.txt) `R-A/T-1` | `metadata-only` · P2 |
| 59 | 스타필드 · 경기 안성 · [별마당 키즈](https://www.starfield.co.kr/anseong/entertainment/libraryKids.do) | `static HTML`; “이달의 프로그램” 영역 있으나 상시 비어 있을 수 있음 | 어린이·가족, 행사별 무료/유료 | [robots](https://www.starfield.co.kr/robots.txt) `R-A/T-1`; 시설과 회차 분리 | `metadata-only` · P2 |
| 60 | 스타필드시티 · 경기 부천 · [별마당 키즈](https://www.starfield.co.kr/bucheon/entertainment/libraryKids.do) | `HTML`; 월간 프로그램 영역 | 어린이·가족, 행사별 | [robots](https://www.starfield.co.kr/robots.txt) `R-A/T-1` | `metadata-only` · P2 |
| 61 | 스타필드 · 경기 고양 · [이벤트 목록](https://www.starfield.co.kr/goyang/eventBenefit/events) | 공개 SSR/SPA 목록, 상세 ID `EV...` | 어린이·가족 키워드 결과만; 가격은 상세별 | [robots](https://www.starfield.co.kr/robots.txt) `R-A/T-1`; 브랜드 할인 이벤트와 교육행사 구분 | `metadata-only` · P2 |
| 62 | 스타필드 · 경기 하남 · [이벤트 목록](https://www.starfield.co.kr/hanam/eventBenefit/events) | 61과 공통 라우트 | 어린이·가족 결과만 | [robots](https://www.starfield.co.kr/robots.txt) `R-A/T-1` | `metadata-only` · P2 |
| 63 | 스타필드 · 경기 수원 · [이벤트 목록](https://www.starfield.co.kr/suwon/eventBenefit/events) | 61과 공통 라우트 | 어린이·가족 결과만 | [robots](https://www.starfield.co.kr/robots.txt) `R-A/T-1` | `metadata-only` · P2 |

## 4. 직업체험·아쿠아리움·테마파크

| # | 브랜드·지역·프로그램 / 공식 목록 | 공개 여부·구조 | 무료/저가·대상 | robots·약관·예약 장벽 | 권고 |
|---:|---|---|---|---|---|
| 64 | MBC Playbe · 서울 잠실 · [KidZania 서울](https://www.kidzania.co.kr/home.do?srcLocalDiv=001) | 공식 HTML 시설/이벤트, 지역 코드 `001`; 티켓 별도 | 어린이 직업체험, 유료 | [robots](https://www.kidzania.co.kr/robots.txt) `R-N/T-1`; 회원/티켓/키조 계정 제외 | `metadata-only` · P2 |
| 65 | MBC Playbe · 부산 센텀 · [KidZania 부산](https://www.kidzania.co.kr/home.do?srcLocalDiv=002) | 서울과 공통 레거시 HTML, 지역 코드 `002` | 어린이 직업체험, 유료 | [robots](https://www.kidzania.co.kr/robots.txt) `R-N/T-1` | `metadata-only` · P2 |
| 66 | Merlin · 부산 해운대 · [SEA LIFE 체험](https://www.visitsealife.com/busan/whats-inside/) | 공개 CMS HTML, 체험/이벤트/학교 페이지 | 어린이·가족, 유료; 학교 프로그램 별도 | [robots](https://www.visitsealife.com/robots.txt) `R-A/T-1`; 티켓 제외 | `metadata-only` · P2 |
| 67 | Merlin · 서울 코엑스 · [SEA LIFE COEX](https://www.visitsealife.com/coex-seoul/) | 66과 같은 CMS | 어린이·가족, 유료 | [robots](https://www.visitsealife.com/robots.txt) `R-A/T-1` | `metadata-only` · P2 |
| 68 | 한화 · 제주 · [Aqua Planet Jeju](https://www.aquaplanet.co.kr/jeju/index.do) | 레거시 `.do` HTML, 공연/생태설명/요금 | 어린이·가족, 고가 유료 | [robots](https://www.aquaplanet.co.kr/robots.txt) `R-N/T-1`; 티켓 제외 | `metadata-only` · P3 |
| 69 | 한화 · 전남 여수 · [Aqua Planet Yeosu](https://www.aquaplanet.co.kr/yeosu/index.do) | 68과 공통 `.do` CMS | 어린이·가족, 유료 | [robots](https://www.aquaplanet.co.kr/robots.txt) `R-N/T-1` | `metadata-only` · P3 |
| 70 | 한화 · 경기 일산 · [Aqua Planet Ilsan](https://m.aquaplanet.co.kr/ilsan/index.do) | 모바일 `.do` CMS, 지점별 일정 | 어린이·가족, 유료 | [robots](https://m.aquaplanet.co.kr/robots.txt) `R-N/T-1` | `metadata-only` · P3 |
| 71 | 한화 · 경기 광교 · [Aqua Planet Gwanggyo](https://m.aquaplanet.co.kr/gwanggyo/guide/schedule/operating-time.do) | 68과 공통 모바일 `.do` CMS | 어린이·가족, 유료 | [robots](https://m.aquaplanet.co.kr/robots.txt) `R-N/T-1` | `metadata-only` · P3 |
| 72 | 롯데월드 · 서울 잠실 · [Aquarium](https://aquarium.lotteworld.com/) | 공개 HTML/SPA, 생태설명·체험/이벤트 | 어린이·가족, 유료 | [robots](https://aquarium.lotteworld.com/robots.txt) `R-A/T-1`; 로그인·티켓·커뮤니케이션 경로 제외 | `metadata-only` · P2 |
| 73 | 삼성물산 · 경기 용인 · [Everland E3 어린이 생태교육](https://www.witheverland.com/427599) | 공식 블로그 HTML; 시즌 모집 공지형 | 동물·식물·과학·사육사/수의사 과정, 어린이 | [robots](https://www.witheverland.com/robots.txt) `R-A/T-1`; 검색·관리·예약/멤버십 제외 | `metadata-only` · P2 |
| 74 | Merlin · 강원 춘천 · [LEGOLAND Korea 시즌 이벤트](https://legoland.kr/%ED%8C%8C%ED%81%AC%EC%9D%B4%EB%B2%A4%ED%8A%B8/) | 공개 CMS HTML; 2026 시즌 날짜·상세 | 어린이·가족, 파크 입장/추가 체험 유료 | [robots](https://legoland.kr/robots.txt) `R-A/T-1`; 티켓/호텔 제외 | `metadata-only` · P2 |

## 5. 대기업 사회공헌·선발형 교육

| # | 브랜드·지역·프로그램 / 공식 목록 | 공개 여부·구조 | 무료/저가·대상 | robots·약관·예약 장벽 | 권고 |
|---:|---|---|---|---|---|
| 75 | 스마일게이트 · 경기 판교/서울 · [Future Lab 프로그램 신청](https://www.futurelab.center/front/program/program) | 공개 JSON/HTML 목록; 검증일 어린이 `ing/plan` 결과는 비어 있음 | 어린이·청소년·가족 워크숍, 무료 또는 기부형 | [robots](https://www.futurelab.center/robots.txt) `R-N/T-P`; 신청은 회원·개인정보 | `metadata-only` · P2 |
| 76 | NC문화재단 · 서울 · [Projectory](https://www.projectory.or.kr/main) | 공식 소개/멤버십 신청, 반복 공개 프로그램 피드 미확인 | 어린이 프로젝트 공간; 멤버십·상담 선발 | [robots](https://www.projectory.or.kr/robots.txt) `R-A/T-P`; 상담/회원 데이터 수집 금지 | `partnership` · P2 |
| 77 | 네이버 커넥트재단 · 전국/온라인 · [서비스 목록](https://connect.or.kr/services) | 공식 HTML; Entry·SEF 등 교육서비스 소개 | 초등 SW·AI 콘텐츠가 있으나 위치 기반 부모 직접 모집 피드는 아님 | [robots](https://connect.or.kr/robots.txt) `R-N/T-P`; 개별 서비스와 제휴 필요 | `partnership` · P3 |
| 78 | LG · 서울대/온라인/미국 · [LG AI 청소년 캠프](https://lgaiyouthcamp.or.kr/introduction/aicamp) | 공식 HTML 모집요강·FAQ·히스토리 | 초6~중2, 공식 안내 전액 무료, 100명 선발 | [robots](https://lgaiyouthcamp.or.kr/robots.txt) `R-N/T-P`; 실명·영상·지원서, 연 1회 | `metadata-only` · P2 |
| 79 | 삼성 · 전국 · [Samsung Dream Class](https://www.dreamclass.org/) | 공식 공지/뉴스 HTML, 학교·멘토 중심 | 주 대상 중학생; 초등 부모 서비스 범위 밖 | [robots](https://www.dreamclass.org/robots.txt) `R-N/T-P` | `deny` · P3 |
| 80 | POSCO 1% 나눔재단 · 포항/광양 등 · [미래세대 사업](https://poscofoundation.org/front/nanum/001/view.do) | 공식 사업소개/공고 HTML·PDF | 지역아동센터·기관 대상 예술/환경/진로 사업 중심 | [robots](https://poscofoundation.org/robots.txt) `R-A/T-P`; 부모 직접 신청 아님 | `partnership` · P2 |
| 81 | CJ나눔재단 · 전국 · [DonorsCamp 꿈키움](https://www.donorscamp.org/DreamSupport.do) | 공식 HTML/공고, 기관·동아리 신청 | 아동·청소년, 지원형/무료 | [robots](https://www.donorscamp.org/robots.txt) `R-X/T-P`; 허용된 공고 경로 외 크롤링 금지 | `partnership` · P2 |
| 82 | SK · 전국 · [사회적 가치 프로그램](https://sk.co.kr/ko/together/programs.jsp) | 공식 그룹 사업소개 HTML, 개별 사업 링크 | SUNNY 등 청년/기관 사업 비중; 초등 부모 직접 목록 아님 | [robots](https://sk.co.kr/robots.txt) `R-A/T-P`; 라이브러리/관리 경로 제외 | `partnership` · P3 |
| 83 | 카카오 · 전국/선발형 · [AI Rookie Camp 지원](https://www.kakaoairookiecamp.com/apply) | 공식 신청 페이지, 계정/폼 중심 | 모집 차수별 연령·비용 확인; 선발형 | [robots](https://www.kakaoairookiecamp.com/robots.txt) `R-A/T-P`; 로그인·폼 자동화 금지 | `partnership` · P2 |
| 84 | 파라다이스문화재단 · 서울/인천 · [공지 목록](https://pcf.or.kr/board/notice) | 공식 HTML 공지/PDF; 문화예술 지원·시즌 행사 | 가족/어린이 여부는 공고별, 대개 프로젝트/기관 단위 | [robots](https://pcf.or.kr/robots.txt) `R-A/T-P` | `partnership` · P3 |

## 6. 실제 파싱 가능한 상위 5 구조 샘플

아래 요청은 모두 비로그인 공개 목록만 사용한다. 운영 코드는 도메인별 최소 6~24시간 간격, 조건부 GET, 지수 백오프, `429/403` 즉시 중지, 응답 필드 화이트리스트를 기본값으로 해야 한다.

### 6.1 Samsung Innovation Museum — 공개 JSON

공식 UI: [어린이 교육 목록](https://samsunginnovationmuseum.com/ko/reserve/edu/academyList.do)

```bash
curl -sS 'https://samsunginnovationmuseum.com/ko/show/selectShowList.json?pageSize=50&showStatus=&fitPerson=&roomNo=&smallPicTitle1=' \
  | jq '.result.list[] | {
      id, showName, showStatusNm, fitPersonNm, fitPersonDetail,
      pepleNumber, applyTime1, applyTime2, startDate, endDate,
      remainingNum, academyStatus, detailInfo, showTopic
    }'
```

응답 봉투는 `resultCode`, `resultMessage`, `result.list`다. 실제 행에는 `accessUserIp`, `loginSessionId`, 사용자/관리자 식별자 같은 공개 알림에 불필요한 필드도 섞여 있으므로 **원본 행 저장을 금지**하고 위 필드만 복사한다. 상세/예약 POST, 로그인, 신청자 조회는 호출하지 않는다.

### 6.2 Museum Kimchikan — 프로그램 + 달력 JSON

공식 UI: [교육·체험 예약 안내](https://kimchikan.com/rsv/info)

```bash
curl -sS 'https://kimchikan.com/rsv/programs?page=1&size=50&keyword=%EC%96%B4%EB%A6%B0%EC%9D%B4&language=ko' \
  | jq '.content[] | {
      programCode, programName, programStatus, minCnt, maxCnt,
      guardianFee, homepageTag, infoList, targetDetailsList
    }'

curl -sS 'https://kimchikan.com/rsv/schedules/calendar?programCode=PR0001&start=2026-07-01&end=2026-09-01' \
  | jq '.[] | {schSeq, schDate, startTime, endTime, openDatetime, reservedCnt, remainCnt, isClosed}'
```

프로그램 응답 봉투는 `content`, `page`, `size`, `totalCount`, `totalPages`다. 달력에서 `remainCnt`와 `isClosed`를 읽되 예약번호·참가자·연락처를 요구하는 이후 단계는 호출하지 않는다. HTML이 든 `programContent`는 저장하지 않고 `infoList`의 정규화된 사실 필드만 사용한다.

### 6.3 현대어린이책미술관 — 공개 검색 POST JSON

공식 UI: [교육 프로그램](https://www.hmoka.org/programs/exhibition/list.do?st_cd=480)

```bash
curl -sS -X POST 'https://www.hmoka.org/programs/exhibition/data.do' \
  --data 'st_cd=480&page=1&rows=100&searchEduName=&searchOnlineCode=' \
  | jq '.contentList[] | {
      edu_seq, edu_name, edu_start_date, edu_end_date, time,
      place_name, edu_time, edu_target_name, personnel, edu_charge,
      status, online_yn, online_code_name, reservation_date,
      summary, list_image_url
    }'
```

응답은 `contentList`, `page`, `total`이다. 실제 행 스키마에는 `child_name`, `parent_hp`, 관리자 ID처럼 목록 알림과 무관한 필드가 함께 정의되어 있으므로 역시 화이트리스트만 저장한다. 상세 canonical은 `https://www.hmoka.org/programs/{code}/view.do?st_cd=480&edu_seq={edu_seq}` 형태로 만들고 신청 POST는 호출하지 않는다.

### 6.4 리움/호암 — 통합 목록 JSON + 상세 EditorJS

공식 UI: [배움·연구 프로그램](https://www.leeumhoam.org/leeum/edu/program)

```bash
curl -sS 'https://www.leeumhoam.org/leeum/edu/program/list?view=list&status%5B%5D=1&status%5B%5D=2&type1=102&keyword=&startDate=&endDate=&limit=20&found=LM&page=1' \
  | jq '.list[] | {
      proId, title, type1, type1Name, programStartDate,
      programEndDate, status, statusName, proImg
    }'
```

응답은 `list`, `paging`, `total`이다. 상세 `https://www.leeumhoam.org/leeum/edu/program/{proId}`에는 `let content = {blocks:[...]}` 형태의 EditorJS 데이터가 있어 대상·장소·참가비를 보강할 수 있다. 목록의 `statusName`이 종료일과 어긋난 사례가 있으므로 `programEndDate < today`이면 상태와 무관하게 종료 처리한다. 호암 프로그램도 통합 목록에 섞이므로 상세 장소/URL로 venue를 확정한다.

### 6.5 Hyundai Motorstudio Goyang — 서버 HTML

공식 UI: [키즈 워크숍](https://motorstudio.hyundai.com/goyang/cotn/exp/kidsWorkShop.do?strgCd=01)

```python
from bs4 import BeautifulSoup
import re

soup = BeautifulSoup(html, "html.parser")
for card in soup.select("section.list_set"):
    title = card.select_one(".expln_text .cotn_title h3")
    fields = {
        h.get_text(" ", strip=True): h.find_next_sibling("p").get_text(" ", strip=True)
        for h in card.select(".expln_cotn .dtl_info h4.tit")
        if h.find_next_sibling("p")
    }
    reserve = card.select_one("[onclick*='goResrv']")
    program_id = re.search(r"goResrv\('([^']+)'\)", reserve.get("onclick", "")).group(1) if reserve else None
```

안정적인 단위는 `section.list_set` 카드이고 제목은 `.expln_text .cotn_title h3`, 키/값은 `.expln_cotn .dtl_info h4.tit + p`, 프로그램 ID는 `goResrv('KIDCM13')` 같은 공개 onclick 값이다. `goResrv`를 실행하거나 예약 URL을 따라가지 않는다.

## 7. 공통 어댑터로 묶을 수 있는 계열/플랫폼

| 어댑터 | 적용 후보 | 공통 키 | 반드시 분리할 것 |
|---|---|---|---|
| `hyundai_motorstudio_html` | 2~4 | `strgCd`, `.do` HTML | 고양 키즈 목록과 서울/부산 정적 페이지의 robots 경로 차이 |
| `seoulmilk_factory_html` | 10~11 | `int_place` | 양주/거창 주소·정원·연계 신청처 |
| `leeum_hoam_program_json` | 23~24 | `proId`, `type1`, 통합 `/list` | 상세의 실제 venue, canonical prefix, 종료일 |
| `daelim_foundation_learn_api` | 25~26 | `prgIdx`, `eduTgtCd`, `eduPlace` | D MUSEUM/대림미술관 장소와 가격 |
| `brickcampus_html` | 39~40 | `gbn` | 지점별 운영기간·요금 |
| `sangsangmadang_lecture` | 42~44 | 강좌 ID·장소 | 성인 강좌 제외 규칙, 지점 좌표 |
| `department_culture_center` | 47~53 | 지점·학기·강좌 ID | 회사별 약관/로그인/HTML이 달라 **공통 도메인 코드가 아니라 공통 정규화 계층만** 공유 |
| `ikea_store_cms` | 54~58 | store slug, CMS detail slug | Family 전용/구매 프로모션과 실제 어린이 체험 분류 |
| `starfield_events` | 59~63 | branch slug, `EV...` 상세 ID | 별마당 키즈 시설과 일반 할인 이벤트/교육 행사 구분 |
| `kidzania_legacy` | 64~65 | `srcLocalDiv` (`001` 서울, `002` 부산) | 가격·운영시간·시설 파트너 변화 |
| `sealife_cms` | 66~67 | venue path | 부산/코엑스 티켓·학교 프로그램 분리 |
| `aquaplanet_do` | 68~71 | branch path + `.do` | 데스크톱/모바일 도메인, 지점별 공연명/시간 |
| `lg_discovery_programs` | 15~16 | 장소·학년 | 초등 6학년만 통과하도록 대상 필터 엄격 적용 |

## 8. 출시 순서

1. **P0**: 이미 구조가 안정적으로 검증된 1, 2, 8만 기본 비활성 opt-in 소스로 운영하고, 저장 필드·호출 빈도·삭제 정책을 고정한다.
2. **P1**: 22~26, 7, 47, 54를 대상으로 법무/운영 승인과 fixture를 먼저 만든다. 목록 결과가 비어 있어도 정상 성공으로 처리한다.
3. **P2**: 공식 URL을 부모에게 연결하는 `metadata-only` 감시로 시작한다. 예약 가능·잔여석은 원문을 다시 확인한 시점에만 표시한다.
4. **P3**: 상설 고가시설, 성인 중심 강좌, 반복 목록 부재, robots 차단 소스는 주변 시설 카탈로그 또는 수동 제보 대상으로만 유지한다.
5. `partnership` 소스에는 제휴 문의용 최소 스키마를 제안한다: `source_event_id`, `title`, `venue`, `address`, `lat/lon`, `target_age/grade`, `fee`, `registration_open/close`, `event_start/end`, `status`, `canonical_url`, `updated_at`.

## 9. 운영 안전선

- 원문 설명, 이미지, PDF 본문, 강의안은 복제하지 않는다. 검색/알림에는 사실 필드와 공식 링크만 쓴다.
- `robots.txt`의 404, 빈 파일, 특정 검색봇만 허용된 규칙은 자동 허용으로 취급하지 않는다.
- 공개 JSON에 내부 필드가 섞여 있어도 “공개됐으니 저장 가능”으로 보지 않는다. SIM·MOKA처럼 알려진 민감/내부 필드를 명시적으로 버리고 알 수 없는 새 필드는 기본 폐기한다.
- 회원, 결제, 실명, 보호자 동의, 예약 변경/취소, 신청자 조회, 대기열, 캡차, 모바일 내부 API는 호출하지 않는다.
- 하루 알림을 만들기 전 공식 상세를 재확인하고, 종료일·접수마감·품절/마감·대상 학년을 다시 검증한다.
- 소스별 `legal_review_status`, `robots_checked_at`, `terms_checked_at`, `last_success_at`, `content_hash`, `backoff_until`을 운영 메타데이터로 보관한다.
