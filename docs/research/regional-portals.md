# 전국 지자체·교육청 체험·교육 예약 포털 조사

- 확인 기준일: 2026-07-15 (KST)
- 범위: 전국 17개 시·도와 주요 기초지자체의 **공식** 통합예약, 체험, 교육, 견학, 문화행사 목록
- 결과: 공식 source unit 60개. 이 중 일일 자동 수집 후보 P1/P2 44개, 자동화 보류 P3 16개
- source unit은 독립 포털 또는 별도 스키마·갱신주기를 가진 공식 공개 데이터 상품이다. 같은 서울 열린데이터광장이라도 예약·교육·문화행사는 서로 다른 데이터 상품으로 구분했다.
- 확인 방법: 공식 목록/문서 직접 GET, 공개 폼·스크립트·응답 구조 확인, `robots.txt`와 로그인·SSO·NetFunnel·WAF 상태 확인. HTTP 상태는 기준일의 관측값이며 영구 보장을 뜻하지 않는다.

## 판정 기준

| 등급 | 뜻 | 운영 원칙 |
|---|---|---|
| P1 | 공식 API 또는 안정적인 공개 목록이며 초등 가족 체험 적합도가 높음 | 먼저 구현. API 키·이용약관·출처표시 준수 |
| P2 | 공개 SSR/HTML 목록. 사이트별 파서와 보수적 요청 정책 필요 | 하루 1회, 변경된 항목만 상세 조회 |
| P3 | `Disallow: /`, NetFunnel, SSO, WAF, 불안정 접속 또는 낮은 체험 적합도 | 자동화하지 않음. 공개 API 협의·수동 링크·대체 데이터 사용 |

명확한 `robots.txt` 404/410은 RFC 9309 §2.3.1.3에 따라 규칙 없음으로 처리하지만, 콘텐츠 복제나 신청 자동화 허가를 뜻하지 않는다. 약관과 기관 정책을 별도로 확인하며 로그인, 예약 제출, 캡차, 대기열 우회는 전부 범위 밖이다. 5xx·WAF·모호한 HTML robots 응답은 fail-closed한다.

## 지역별 공식 소스 인벤토리

### 서울특별시 — 9

| # | 기관·공식 목록 | HTTP·접근 상태 | 구조·주요 필드/키 | 수집 방식·우선순위 |
|---:|---|---|---|---|
| 1 | [서울 공공서비스예약 통합정보](https://data.seoul.go.kr/dataList/OA-20497/S/1/datasetView.do) | 문서 200, API 공개키 필요, robots 허용 | `tvYeyakCOllect`; `SVCID`, `SVCNM`, `SVCSTATNM`, `PAYATNM`, `PLACENM`, `USETGTINFO`, `SVCURL`, `X/Y`, 운영·접수 시작/종료 | 공식 JSON API, 1–1000 구간 페이지네이션. **P1** |
| 2 | [서울 공공서비스예약 교육강좌 정보](https://data.seoul.go.kr/dataList/OA-2268/A/1/datasetView.do) | 문서 200, API 공개키 필요 | `ListPublicReservationEducation`; 소분류·서비스명·대상·지역 선택 필터 | 공식 JSON API. #1 중복은 `SVCID`로 제거하고 교육 세부 분류 보강. **P1** |
| 3 | [서울 문화행사 정보](https://data.seoul.go.kr/dataList/OA-15486/S/1/datasetView.do?tab=A) | 문서 200, API 공개키 필요 | `culturalEventInfo`; `CODENAME`, `TITLE`, 날짜, 장소, 대상, 요금, 좌표, 원문 URL | 공식 JSON API, 어린이·가족·교육 분류 필터. **P1** |
| 4 | [서울의 공원 프로그램](https://parks.seoul.go.kr/friend/gathering/list.do) | 200; robots에서 목록 경로 비차단 | SSR 목록·상세; 프로그램명, 공원, 모집/운영기간, 대상, 상태 | 목록 1회/일, 변경 상세만. **P1** |
| 5 | [서울시교육청과학전시관 가족천문교실](https://ssei.sen.go.kr/fus/MI000000000000000084/program/CD00000218/list0010v.do) | 200; robots의 일부 구 게시판 차단과 무관한 공개 목록 | SSR; 회차, 신청기간, 대상, 정원, 상태, 상세키 | 가족·초등 대상만 수집. **P2** |
| 6 | [강남구 통합예약 교육·체험](https://life.gangnam.go.kr/fmcs/52?action=read&classcd=00009&comcd=GNCC28&type=R) | 200; robots 허용 | FMCS SSR; `classcd`, `comcd`, 프로그램·운영시간·요일·대상·정원 | FMCS 전용 파서, 상세키 조합. **P2** |
| 7 | [금천구 통합예약 교육강좌](https://www.geumcheon.go.kr/reserve/webEdcLctreList.do?key=112) | 200; robots는 검색 경로만 차단 | `webEdcLctreList/View`; `searchLctreKey`, 접수/교육기간, 대상, 장소, 상태 | `MunicipalWebReserveAdapter`. **P2** |
| 8 | [종로구 통합예약](https://www.jongno.go.kr/reserv/main.do) | 200; robots `User-agent: * / Disallow: /` | 교육·체험·시설 통합 UI | 자동 수집 금지, 링크 디렉터리나 기관 협의만. **P3** |
| 9 | [동작구 통합예약 이용 안내](https://www.dongjak.go.kr/yeyak/main/contents.do?menuNo=1600023) | 200; robots 선택 규칙, 전체 정책 재검토 필요 | 교육·체험·시설·행사 카테고리, 공개 SSR | 정책 확인 후 하루 1회. **P2** |

### 인천광역시 — 2

| # | 기관·공식 목록 | HTTP·접근 상태 | 구조·주요 필드/키 | 수집 방식·우선순위 |
|---:|---|---|---|---|
| 10 | [인천광역시 온라인통합예약 교육강좌](https://www.incheon.go.kr/res/RE010101/lctreEdcList?sortType=CHILD&stateType=ING&appTp=LCTRE&curPage=1) | 200; robots 404, 목록 공개·예약은 로그인 가능 | `resveInsttCode`, `setleChrgeSeCode=FREE/CHARGE`, `stateType=ING/WAITING`, `appTp`, `sortType=CHILD/WEEKEND`, 날짜·검색어·`curPage`; 상세 `progrmSn` | 어린이/주말·접수중 서버 필터 활용. **P1** |
| 11 | [인천광역시교육청 체험예약](https://www.ice.go.kr/ice/exprn/selectExprnList.do?mi=11607) | 200; robots는 `/common`, `/comm`만 차단 | `srchRsSysId`, `exprnSeq`, `exprnPeriodSeq`, `srchRsvSttus`, 접수/운영일, `srchRceptTrget`(유아·학생·학부모·가족 등), `currPage` | 교육청 공통 어댑터. 목록·상세 공개, 신청만 로그인. **P1** |

### 경기도 — 9

| # | 기관·공식 목록 | HTTP·접근 상태 | 구조·주요 필드/키 | 수집 방식·우선순위 |
|---:|---|---|---|---|
| 12 | [경기공유서비스](https://share.gg.go.kr/) | 루트 200·robots 허용/사이트맵; 일부 목록에서 NetFunnel 관측 | `facilityId`, `instiCode`, 지역·시설·프로그램·예약 링크 | 대기열 우회 금지. 공유누리 공식 API나 기관 협의 전까지 자동화 보류. **P3** |
| 13 | [수원시 교육강좌 예약](https://www.suwon.go.kr/web/reserv/edu/list.do) | 200; robots의 비관련 경로만 차단 | `eduMstSeq`; 강좌명, 접수/교육기간, 요일·시간, 대상, 모집/대기, 장소, 상태 | 공개 SSR 표/카드. **P1** |
| 14 | [고양시 통합예약](https://www.goyang.go.kr/resve/manage/BD_selectResveManageList.do?q_resveTopClCode=CL_02) | 200; robots 허용 | `q_resveTopClCode=CL_01..05`, `q_resveSttusCode`, `resveSn`; 상세 JS 링크 | `BDSelectReservationAdapter`. **P2** |
| 15 | [부천시 공공서비스예약 견학·체험](https://reserv.bucheon.go.kr/site/main/see/list) | 200; robots 404 | `program_seq`; 무료/유료, 온라인, 상태, 신청·운영일, 장소. 자연생태공원·건강체험관·천문과학관·재난체험 등 기관 필터 | 적합도가 높고 상세키 안정적. **P1** |
| 16 | [안양시 교육강좌 예약](https://www.anyang.go.kr/reserve/selectEduLctreWebList.do?key=1376&searchDiv=1) | 브라우저용 공개 HTML 구조 확인; 현재 표준 Python TLS 런타임은 안전한 연결 협상 실패 | `selectEduLctreWebList`, `eduLctreWebView`, `eduLctreNo`, `key`, `searchDiv`; 별도 [온라인예약 목록](https://www.anyang.go.kr/reserve/selectResveWebList.do?key=3483) | `SelectWebListAdapter` fixture 구현, `available=False`로 네트워크 차단. 서버 TLS 정상화 후 재검증. **P2** |
| 17 | [화성시 통합예약](https://yeyak.hscity.go.kr/indexIntro.do) | 200; robots 허용이나 `netfunnel.js`와 `NetFunnel_Action` 확인 | 대기열 후 목록·로그인 진입 | 대기열 우회 금지. 공개 피드 요청 전까지 **P3** |
| 18 | [용인시 통합예약 체험·참여](https://resve.yongin.go.kr/resve/manage/BD_selectResveManageList.do?q_lclas=CL_01&q_resveCl=CL_01_3) | 200; robots 404 | `q_lclas=CL_01` 체험/참여, `CL_02` 교육, `q_resveCl`, `resveSn`; 안전·견학·숲·농촌·기후 체험 | 고양과 같은 `BDSelectReservationAdapter`. **P2** |
| 19 | [김포시 통합예약 체험](https://www.gimpo.go.kr/reserve/webEtcResveList.do?key=113&rep=1&etcProgramSection=EXPERIENCE) | 공개 목록 구조 확인; 현재 일반 User-Agent robots `Disallow: /` | `webEtcResveList/View`, `etcProgramSection`, `searchEtcGroup`, `searchEtcResveNo`; 제목·접수/운영일·대상·장소·가격·상태 | 금천과 같은 파서는 구현하되 `available=False`; robots 정책 변경/서면 허용 전 자동 요청 금지. **P3** |
| 20 | [경기데이터드림 문화·관광 데이터](https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=Y3WQP2JI34FGGG9LO9ID30977197&infSeq=1) | 공식 문서 공개, 키 필요; 현 데이터의 갱신/분할 규칙이 모호 | `https://openapi.gg.go.kr/{service}`; `KEY`, `Type`, `pIndex`, `pSize` | 실제 최신 행·라이선스 검증 후 승격. **P3** |

### 부산광역시 — 3

| # | 기관·공식 목록 | HTTP·접근 상태 | 구조·주요 필드/키 | 수집 방식·우선순위 |
|---:|---|---|---|---|
| 21 | [부산광역시 통합예약 교육강좌](https://reserve.busan.go.kr/lctre/list?curPage=1) / [견학·체험](https://reserve.busan.go.kr/exprn) | 목록 200; robots 요청은 401로 정책 확인 불가 | `progrmSn`, `resveGroupSn`, `curPage`, 기간·분류·구군·상태·기관·예약방법·검색어; `/lctre/view`, `/exprn/view` | 운영자 문의와 낮은 빈도 전제. **P2** |
| 22 | [부산광역시교육청 통합예약 체험](https://home.pen.go.kr/yeyak/exprn/selectExprnList.do?contestAt=N&mi=14438) | 200; robots의 선택 제한에 목록 미포함 | 교육청 공통 `srchRsSysId`, `exprnSeq`, `exprnPeriodSeq`, 상태·기간·대상 | 교육청 공통 어댑터. **P1** |
| 23 | [부산소방재난본부 안전교육](https://119edu.busan.go.kr/main/4?action=list) | 200; robots 응답이 정상 정책 텍스트가 아니어서 재확인 필요 | `action=list/read`; 교육명, 대상, 기간, 정원, 상태 | 아동 안전 체험만 필터. **P2** |

### 대구광역시 — 3

| # | 기관·공식 목록 | HTTP·접근 상태 | 구조·주요 필드/키 | 수집 방식·우선순위 |
|---:|---|---|---|---|
| 24 | [대구광역시 통합예약](https://yeyak.daegu.go.kr/) | 200; robots 허용이나 SPA에 NetFunnel 스크립트·대기 호스트 확인 | SPA 라우트 `/expr`, `/lect`; 내부 `/api/v1/res/cmmn/` 흔적 | 비공개 API 역공학·대기열 우회 금지. 공식 API 협의 전 **P3** |
| 25 | [대구 북구 통합예약](https://www.buk.daegu.kr/reserve/index.do?menu_id=00002964) | 200; robots는 파일·게시판 일부 제한 | 공개 SSR; 프로그램, 기관, 신청/운영일, 대상, 상태 | 하루 1회 HTML. **P2** |
| 26 | [대구 서구 통합예약](https://dgs.go.kr/reserve/main.do) | 200; robots는 검색만 차단 | 공개 SSR, 체험·교육 카테고리와 어린이 건강 프로그램 | 목록 중심 수집. **P2** |

### 광주광역시 — 2

| # | 기관·공식 목록 | HTTP·접근 상태 | 구조·주요 필드/키 | 수집 방식·우선순위 |
|---:|---|---|---|---|
| 27 | [광주광역시 바로예약 교육](https://www.gwangju.go.kr/reserve/bookingList.do?pageId=reserve1&searchCate1=A) / [체험](https://www.gwangju.go.kr/reserve/bookingList.do?pageId=reserve44&searchCate1=B) | 200; robots에 Googlebot 전체 차단 규칙이 있어 일반 UA 정책도 전문 검토 필요 | `bookingCode`, `pageId`, `searchCate1=A/B`; 제목, 상태, 기간, 기관, 대상, 요금 | Googlebot 가장 금지. 보수적 UA·정책 확인 후 **P2** |
| 28 | [광주광역시유아교육진흥원](https://iedu.gen.go.kr/) | 200; robots 404 | 가족·유아 체험 프로그램 공개 SSR, 신청 공지/회차/대상 | 초등 연계·가족 허용 프로그램만. **P2** |

### 대전광역시 — 2

| # | 기관·공식 목록 | HTTP·접근 상태 | 구조·주요 필드/키 | 수집 방식·우선순위 |
|---:|---|---|---|---|
| 29 | [대전 OK예약 견학·체험](https://www.daejeon.go.kr/okr2019/expRsvtList.do) | 200; robots `Disallow: /` | 공개 화면은 있으나 전체 자동 접근 금지 | 링크만 제공, 자동 수집 금지. **P3** |
| 30 | [대전유아교육진흥원](https://www.dje-i.go.kr/djei/main.do) | 200; robots `Disallow: /` | 가족 주말체험 등 공개 메뉴 | 자동 수집 금지. **P3** |

### 울산광역시 — 2

| # | 기관·공식 목록 | HTTP·접근 상태 | 구조·주요 필드/키 | 수집 방식·우선순위 |
|---:|---|---|---|---|
| 31 | [울산광역시 공공시설예약서비스](https://www.ulsan.go.kr/y/yes) | 공식 진입 URL이나 기준일 HEAD 405·GET 리다이렉트/타임아웃 혼재; 시 루트 robots는 일부 관리 경로 외 허용 | 통합 교육·체험·시설 UI | 안정된 canonical/공식 피드 확인 전 **P3** |
| 32 | [울산유아교육진흥원](https://use.go.kr/uskids/index.do) | 200; robots 404 | 체험교육·가족체험 안내, 교육청 통합예약 연결 | 가족/초등 허용 공지만 하루 1회. **P2** |

### 세종특별자치시 — 2

| # | 기관·공식 목록 | HTTP·접근 상태 | 구조·주요 필드/키 | 수집 방식·우선순위 |
|---:|---|---|---|---|
| 33 | [세종시 통합예약시스템](https://onestop.sejong.go.kr/) | 200 후 `/Usr/main/main.do`; robots `Disallow: /` | 시설·실내놀이터·교육 예약 | 자동 수집 금지. **P3** |
| 34 | [세종SW교육체험센터 개인체험](https://edu.sje.go.kr/sw/sub.do?menukey=4203) | 200; robots에서 일반 UA 허용, Googlebot 별도 차단 | Switch ON 등 회차형 SW체험; 제목, 일시, 학년/대상, 신청기간, 정원 | 일반 식별 UA, 하루 1회. **P2** |

### 강원특별자치도 — 2

| # | 기관·공식 목록 | HTTP·접근 상태 | 구조·주요 필드/키 | 수집 방식·우선순위 |
|---:|---|---|---|---|
| 35 | [원주시 통합예약](https://yeyak.wonju.go.kr/) | 200; robots 404. [원주시 공식 안내](https://www.wonju.go.kr/www/contents.do?key=6188)가 교육강좌·통합예약 경로 확인 | 공개 SSR; 강좌/체험명, 기관, 대상, 접수/운영일, 상태 | 하루 1회. **P2** |
| 36 | [춘천도시공사 통합예약](https://rev.cuc.or.kr/www/1) | 200; robots 허용 | 주로 체육시설·강좌, 일부 가족 프로그램 | 현재 체험 적합도가 낮아 감시 목록만. **P3** |

### 충청북도 — 4

| # | 기관·공식 목록 | HTTP·접근 상태 | 구조·주요 필드/키 | 수집 방식·우선순위 |
|---:|---|---|---|---|
| 37 | [충청북도교육청 통합예약 체험](https://www.cbe.go.kr/yeyak/exprn/selectExprnList.do?mi=11424) | 200; robots의 `/common`, `/comm` 외 허용 | 교육청 공통 키; 기관, 체험명, 운영/신청기간, 대상, 신청구분, 상태 | 교육청 공통 어댑터. **P1** |
| 38 | [청주시 통합예약 체험](https://ticket.cheongju.go.kr/www/selectExprnWebList.do?key=8) | 200; robots 404 | `selectExprnWebList/View`; 교육은 `selectEduLctreWebList`, `lctreNo`, `key`, 페이지 | `SelectWebListAdapter`. **P1** |
| 39 | [충주시 통합예약](https://www.chungju.go.kr/rev/reserve/1) | 200; robots 문법이 불명확해 정책 재확인 필요 | 문화체험·교육 공개 SSR, 목록·상세 ID | 하루 1회, 문의 권장. **P2** |
| 40 | [충청북도교육문화원 통합예약](https://www.cbec.go.kr/reserve/main.php) | 200; robots `Disallow: /` | 공연·체험·강좌 예약 | 자동 수집 금지. **P3** |

### 충청남도 — 2

| # | 기관·공식 목록 | HTTP·접근 상태 | 구조·주요 필드/키 | 수집 방식·우선순위 |
|---:|---|---|---|---|
| 41 | [아산시 통합예약](https://www.asan.go.kr/yeyak/) | 200; robots 404 | 평생학습/교육·체험 SSR, 제목·기관·신청/운영일·대상·상태 | 하루 1회. **P2** |
| 42 | [천안시 통합예약](https://gongyoo.cheonan.go.kr/) | 공식 시 사이트 연결 확인; 기준일 환경에서 403/WAF | 공유·교육·체험 통합 UI | WAF 우회 금지, 기관 API 협의만. **P3** |

### 전북특별자치도 — 4

| # | 기관·공식 목록 | HTTP·접근 상태 | 구조·주요 필드/키 | 수집 방식·우선순위 |
|---:|---|---|---|---|
| 43 | [장수군 통합예약](https://www.jangsu.go.kr/reserve/index.jangsu?menuCd=DOM_000000503002000000) | 200; robots는 이미지·업로드·게시판 일부만 제한 | `.jangsu` DOM CMS; `menuCd`, 공연/문화행사·체험·교육, 세부 ID | `RegionalDOMCmsAdapter`. **P2** |
| 44 | [전주관광 프로그램 예약](https://tour.jeonju.go.kr/index.jeonju?menuCd=DOM_000000102002001000) | 200; robots 허용 | `.jeonju` DOM CMS; `facSid`, 프로그램, 일정, 대상, 요금, 장소 | 관광 체험 적합도 높음. **P2** |
| 45 | [익산글로벌문화관 교육·체험 예약](https://www.iksan.go.kr/global/) | 200; robots 주요 UA 허용 | `.iksan` CMS; 다문화 교육·체험, 일정, 대상, 모집상태 | 초등·가족 대상 필터. **P2** |
| 46 | [김제시 통합예약](https://www.gimje.go.kr/reserve/index.gimje) | 200; robots는 검색·게시판 일부 제한 | `.gimje` CMS; 교육·체험, 신청/운영일, 대상, 상태 | 지역 DOM CMS 변형. **P2** |

### 전라남도 — 4

| # | 기관·공식 목록 | HTTP·접근 상태 | 구조·주요 필드/키 | 수집 방식·우선순위 |
|---:|---|---|---|---|
| 47 | [전라남도교육청 통합예약 체험](https://yeyak.jne.kr/yeyak/exprn/selectExprnList.do?mi=10205166) | 200; robots는 검색·일부 게시판만 차단 | 교육청 공통 키; 기관, 체험명, 운영/신청기간, 대상, 상태 | 교육청 공통 어댑터. **P1** |
| 48 | [여수시 OK통합예약](https://www.yeosu.go.kr/newok/) | 200; robots 허용 | VR체험, 이순신 스토리워크, 환경 견학 등; 프로그램·회차·대상·상태 | 체험 카테고리 우선. **P1** |
| 49 | [순천시 바로예약](https://www.suncheon.go.kr/yeyak/) | 200; robots는 CMS·투표 일부 제한 | 교육강좌·체험 SSR, 제목·기관·기간·대상·상태 | 하루 1회. **P2** |
| 50 | [곡성교육포털](https://www.gokmg.or.kr/edu/) | 구 군청 URL이 현 포털로 연결; 200, robots 404 | 통합 프로그램 예약·온라인 결제, 제목·기관·일정·대상·정원 | 결제/신청은 제외하고 공개 목록만. **P2** |

### 경상북도 — 3

| # | 기관·공식 목록 | HTTP·접근 상태 | 구조·주요 필드/키 | 수집 방식·우선순위 |
|---:|---|---|---|---|
| 51 | [경상북도교육청 온체험 통합예약](https://www.gbe.kr/edushare/exprn/selectExprnList.do?mi=17609) | 200; robots는 편집기 경로만 차단 | 교육청 공통 키. 기관 AJAX `POST /edushare/rs/search/selectRsTypeDetailList.do` + `rsType=exprn`이 `rsSysId`, `rsSysNm` JSON 반환; 프로그램 옵션 AJAX와 공개 상세 | 실응답 fixture 보유. **P1** |
| 52 | [상주시 통합예약](https://www.sangju.go.kr/reserve/reservation/list.tc?mn=15375&searchTrgtClsfCd=RMS004001) | 200; robots는 내부 경로 일부 외 허용 | `.tc`; `cyclNo`, `searchTrgtClsfCd`, 제목, 접수/운영일, 대상, 정원, 상태 | 하루 1회. **P2** |
| 53 | [봉화군 통합예약](https://www.bonghwa.go.kr/reservation/main.do) | 200; robots `Disallow: /` | 교육·체험·시설 통합 UI | 자동 수집 금지. **P3** |

### 경상남도 — 4

| # | 기관·공식 목록 | HTTP·접근 상태 | 구조·주요 필드/키 | 수집 방식·우선순위 |
|---:|---|---|---|---|
| 54 | [경상남도교육청 통합예약](https://service.gne.go.kr/yeyak/trn/trnList.do?insttId=myhappy&mi=7124) | 현재 302로 `/sso/agentInitProc.jsp` 진입 후 루트 이동, 세션 필요 | 검색엔진에는 일부 체험 목록이 노출되지만 직접 목록은 SSO 의존 | 세션 자동화 금지, 공개 피드 협의. **P3** |
| 55 | [창원시 일상플러스](https://www.changwon.go.kr/booking/) | 200 후 `/booking/main.web`; robots `Crawl-delay: 10` | 교육강좌·견학체험·대관; `.web`, `fcd`, `lectureId`, 신청/운영일·대상·상태 | 10초 이상 간격, 하루 1회. **P1** |
| 56 | [김해시 공공예약포털](https://www.gimhae.go.kr/yes/) | 200 후 `/yes/main.web`; robots는 검색 등 일부만 제한 | 공공시설·교육·체험; `.web` 목록/상세 ID | 하루 1회. **P2** |
| 57 | [양산시 통합예약](https://www.yangsan.go.kr/booking/main.do) | 200; robots는 시스템·검색·게시판 일부 제한 | 공개 SSR; 체험·교육, 기간, 대상, 가격, 상태 | 하루 1회. **P2** |

### 제주특별자치도 — 2

| # | 기관·공식 목록 | HTTP·접근 상태 | 구조·주요 필드/키 | 수집 방식·우선순위 |
|---:|---|---|---|---|
| 58 | [제주특별자치도교육청 기관 체험예약](https://org.jje.go.kr/jjeExperience/list.jje?menuCd=DOM_000000501001000000) | 200; 일반 UA robots `Disallow: /` | `.jje` DOM CMS; `experienceSid`, 유형, 제목, 날짜, 장소, 상태 | 화면 자동 수집 금지. 아래 공개 파일 사용. **P3** |
| 59 | [제주교육청 체험프로그램 공개데이터](https://www.data.go.kr/data/15146035/fileData.do) | 공공데이터포털 공식 파일 데이터 | 관리기관, 체험유형, 제목, 시작/종료, 기타일정, 신청 시작/종료, 정원/대기, 장소 | 갱신주기를 확인해 화면 대신 사용. 위치 기반 후보의 seed로 유용. **P2** |

### 전국 보완 소스 — 1

| # | 기관·공식 목록 | HTTP·접근 상태 | 구조·주요 필드/키 | 수집 방식·우선순위 |
|---:|---|---|---|---|
| 60 | [한국문화관광해설사중앙협의회 지역별 예약](https://www.kctg.or.kr/reservation/apply01.do) | 200; robots는 공통·검색 일부 외 허용 | 시도·관광지 선택, 프로그램/일정/신청 링크 | 지자체 누락 지역의 보완용. **P2** |

## 공통 어댑터 설계

### 1. `SeoulOpenApiAdapter`

대상은 #1–#3이다. URL의 키·포맷·시작·종료 인덱스를 조립하고 `list_total_count`, `row`, `RESULT`를 공통 처리한다. `SVCID` 또는 데이터 상품의 고유키를 `external_id`로 저장한다. 상세 설명의 HTML은 정화하고, 이미지·긴 설명 재배포는 데이터 상품별 공공누리 조건을 확인한다.

### 2. `EducationOfficeReservationAdapter`

대상은 ICE #11, PEN #22, CBE #37, JNE #47, GBE #51이다. 공통 패턴은 다음과 같다.

- 목록: `/{site}/exprn/selectExprnList.do`
- 상세: `/{site}/exprn/selectExprnInfo.do`
- 키: `srchRsSysId`, `exprnSeq`, `exprnPeriodSeq`, `mi`, `currPage`
- 필터: `srchRsvSttus=REQST|END|PREV`, `srchPeriodDiv=rcept|oper`, 시작/종료일, `srchRceptTrget`
- 필드: 운영기관, 체험명, 운영기간, 신청기간, 대상, 신청유형, 예약상태, 장소

`mi`와 context path만 사이트 설정으로 둔다. GBE는 기관 JSON AJAX를 선택적으로 사용한다. GNE #54는 비슷해 보여도 SSO 경계가 있으므로 이 어댑터에 넣지 않는다.

### 3. `MunicipalWebReserveAdapter`

대상은 금천 #7과 김포 #19다. `webEdcLctreList/View`, `webEtcResveList/View` 패턴과 `key`, `rep`, `searchLctreKey`, `etcProgramSection`, `searchEtcGroup`, `searchEtcResveNo`를 설정으로 받는다. DOM 클래스보다 한글 라벨과 상세 링크의 안정 키를 우선한다.

### 4. `BDSelectReservationAdapter`

대상은 고양 #14와 용인 #18이다. `BD_selectResveManageList.do`와 `q_lclas`, `q_resveTopClCode`/`q_resveCl`, 상태 필터, `resveSn`을 공통 처리한다. 자바스크립트 `opResveView(resveSn)`에서 상세키를 안전하게 추출한다.

### 5. `SelectWebListAdapter`

대상은 안양 #16과 청주 #38이다. `select{Kind}WebList.do` / `{kind}WebView.do`, `key`, `pageIndex`, `eduLctreNo`/`lctreNo`/`exprnNo` 변형을 사이트 설정으로 둔다.

### 6. `RegionalDOMCmsAdapter`

대상은 장수 #43, 전주 #44, 익산 #45, 김제 #46이며, 제주 #58은 정책상 파싱하지 않는다. `.jangsu`, `.jeonju`, `.iksan`, `.gimje`, `.jje` 확장과 `menuCd=DOM_...`, `facSid`, `experienceSid`를 처리한다. 동일 CMS여도 robots 정책은 사이트별로 독립 판정한다.

### 7. `LabelDrivenSsrAdapter`

수원, 부천, 부산, 대구 구청, 광주, 원주, 여수, 순천, 창원, 김해, 양산처럼 마크업이 제각각인 사이트용 얇은 기반 클래스다. 소스별 설정에는 목록 링크 선택자, 상세 ID 정규식, 다음 페이지 방식, 라벨 사전만 둔다. 내용 추출은 `접수기간`, `운영기간`, `대상`, `장소`, `이용료`, `정원`, `상태` 같은 라벨 기반으로 하고, DOM 구조 변경 시 조용히 오염시키지 말고 해당 소스를 실패 상태로 전환한다.

### 8. `ManualOnlySource`

P3 소스는 “파서 미구현”이 아니라 명시적인 정책 상태다. `reason=robots_disallow|netfunnel|sso|waf|unstable|low_relevance`를 저장하고 사용자에게 공식 링크만 노출한다. 캡차·NetFunnel·로그인 쿠키·SSO를 자동화하는 코드는 만들지 않는다.

## 정규화 및 위치 기반 필드

모든 어댑터가 최소한 아래 구조를 반환하게 한다.

```text
source_id, external_id, canonical_url, title, provider_name
region_sido, region_sigungu, venue_name, address, latitude, longitude
application_starts_at, application_ends_at
program_starts_at, program_ends_at, schedule_text
audience_text, min_grade, max_grade, family_allowed
price_text, price_min, price_max, currency, status
capacity, wait_capacity, image_url, summary, fetched_at, content_fingerprint
```

- 공개 좌표가 있으면 그대로 사용한다. 서울은 `X=경도`, `Y=위도` 매핑을 fixture에 명시했다.
- 주소만 있으면 정규화된 장소 주소를 한 번 지오코딩하고 캐시한다. 매일 같은 주소를 재지오코딩하지 않는다.
- 1차 중복키는 `(source_id, external_id)`다. 교차 포털 중복은 정규화 제목·기관·장소 geohash·운영일로 후보 군집만 만들고, 날짜가 다른 회차를 합치지 않는다.
- `content_fingerprint`가 바뀐 항목만 상세를 다시 읽는다. 마감·취소·추가모집 변화를 별도 이벤트로 기록한다.

## 구현 순서

1. 서울 공식 API 3개를 먼저 연결한다. 좌표와 접수 상태가 있어 위치 기반 알림의 기준 데이터가 된다.
2. 교육청 공통 어댑터 하나로 인천·부산·충북·전남·경북 5개 포털을 연결한다. GBE 기관 AJAX로 기관 목록 자동발견을 검증한다.
3. 금천 `MunicipalWebReserveAdapter`, 고양·용인 `BDSelectReservationAdapter`, 청주 `SelectWebListAdapter`를 공개 목록·사실 상세 범위로 연결한다.
4. 김포는 robots 전면 차단, 안양은 현재 TLS 런타임 차단 상태로 파서만 유지하고 네트워크 실행을 중지한다.
5. 나머지 P2는 하루 1회 저속 수집으로 확장하고, P3는 공식 API 요청 또는 수동 링크 상태로 유지한다.

## 운영 안전선

- API는 문서상의 키, 호출량, 출처표시, 라이선스를 따른다. 키는 저장소에 넣지 않는다.
- HTML은 소스별 1일 1회에 임의 지연을 두고, `ETag`/`Last-Modified`를 지원하면 조건부 요청한다. 창원은 최소 10초 간격을 지킨다.
- 목록을 먼저 읽고 신규·변경 ID만 상세 조회한다. 예약 버튼 클릭, 좌석 선점, 자동 신청은 하지 않는다.
- robots 전체 차단, SSO, WAF, NetFunnel을 만나면 즉시 중단한다. 브라우저 위장, 쿠키 재사용, 대기열·캡차 우회는 금지한다.
- 긴 본문과 이미지는 원문 링크 중심으로 제공한다. 알림에는 제목·기관·일시·대상·가격·상태와 짧은 사실 요약만 싣는다.
- 모든 레코드에 `fetched_at`, 원문 URL, 원문 해시를 보존해 삭제·정정 요청과 출처 검증에 대응한다.

## 구현용 요청 fixture

- [`seoul-public-reservation-request.json`](./fixtures/seoul-public-reservation-request.json): 서울 API URL, 페이지네이션, 전체 필드 매핑
- [`gyeongbuk-education-request.json`](./fixtures/gyeongbuk-education-request.json): 2026-07-15 실응답을 포함한 교육청 기관/프로그램 AJAX와 목록·상세 요청
- [`gimpo-experience-request.json`](./fixtures/gimpo-experience-request.json): 지자체 `webEtcResveList/View` 요청·안정 키·정규화 필드
