# 경기 `adapter_candidate` 19개 반복 수집 경로 감사

- 조사일: 2026-07-15 (Asia/Seoul)
- 대상: `gyeonggi-deep-discovery.json`에서 `implementation_status == "adapter_candidate"`인 19개 전부
- 원칙: 공식 공개 목록·상세 HTML, 공식 공개 JSON/XHR, 공식 RSS·사이트맵, 공공데이터만 조사했다. 로그인, 본인인증, CAPTCHA, WAF 우회, 예약 제출, 결제, 신청자 조회·취소 API는 수집 경로에서 제외한다.
- 주의: 아래 평가는 **공개 메타데이터를 낮은 빈도로 반복 조회할 수 있는 기술 경로**에 관한 것이다. `robots.txt`는 라이선스가 아니므로 운영 전 각 기관 이용약관·저작권 고지와 재배포 범위를 별도로 검토해야 한다.

## 결론

19개 모두에서 공식 공개 정보 경로를 확인했다. 다만 경로의 정보 밀도는 다르다.

- 즉시 구현 가능한 공식 JSON/XHR: 2개 (`korea_jobworld_children`, `hwaseong_children_culture`)
- 공식 HTML 목록/상세로 즉시 구현 가능: 16개. `goe_future_science`는 공식 공공데이터 CSV를 보조 소스로 함께 쓸 수 있다.
- 제한형 공지/정적 프로그램 수집: 1개 (`gg_safety_experience`). 공개 공지로 새 프로그램과 예약 개시일은 알 수 있지만, 예약 잔여석을 얻기 위해 신청 흐름에 들어가면 안 된다.

따라서 기존 19개를 단순히 “후보”로 남길 이유는 없다. 18개는 공개 메타데이터 어댑터로 구현하고, 경기국민안전체험관 1개는 `notice_only` 기능으로 명시해 구현하는 것이 맞다.

## 19개 공식 피드 표

| # | 소스 ID | 반복 수집할 공식 경로 | 안정 키·페이지/스키마 | 정책·중복 처리 | 판정 |
|---:|---|---|---|---|---|
| 1 | `suwon_dodream` | [프로그램 목록 `?p=40`](https://www.swdodream.or.kr/?p=40), 상세 `?p=40_view&idx={idx}&page={page}` | `idx`; 제목, 장소, 대상, 행사일, 접수/상태. 목록의 새 `idx`만 상세 조회 | `robots.txt`가 `p=27*` 공지를 막으므로 절대 조회하지 않고 허용된 `p=40`만 사용. 수원 통합 포털과 제목+행사일+장소 중복 제거 | 구현 가능 |
| 2 | `national_map_museum` | [교육 목록](https://www.ngii.go.kr/map/board/list.do?board_code=edudetail_map), 상세 `view.do?sq={sq}&board_code=edudetail_map&currentPage=1` | `sq`, `currentPage`; 교육기간·시간·대상·장소·정원·신청 안내 | 공개 게시판만. 신청·개인정보 입력 경로 제외 | 구현 가능 |
| 3 | `haewoojae_programs` | [교육 목록 `subPage=220`](https://haewoojae.com/m/load.asp?subPage=220), [행사 목록 `subPage=230`](https://haewoojae.com/m/load.asp?subPage=230); 상세는 각각 `221`/`231` + `idx` | `idx`, `page`, `type=B1`; 제목, 기간, 정원/상태. 레거시 CP949/EUC-KR 디코딩 대비 | 기존 등록 URL `subPage=411`은 공지 상세 템플릿이므로 주 피드로 쓰지 않음. `/sub_page/`, 다운로드·관리 경로 금지 | 구현 가능 |
| 4 | `gg_safety_experience` | [프로그램 소개](https://ggsec.gg.go.kr/sub02_01_01), [체험 공지 목록 `type=04`](https://ggsec.gg.go.kr/boardList?type=04), 상세 `boardView?board_id={id}` | `board_id`; 제목, 게시일, 행사/접수 개시일, 대상. 정적 프로그램 유형은 별도 스냅샷 | `reservChoice`, `reservAgree` 등 예약 단계는 조회하지 않음. 잔여석 수집 불가를 정상 상태로 처리 | **공지 제한형** |
| 5 | `goe_future_science` | [학생 강좌 목록](https://www.gise.kr/gise/aply/lctr/selectLctrList.do?lctrLrnClsfCd=STUDY&mi=10718), 상세 `insertLctrRcptInfoView.do?...&lctrSn={lctrSn}`; [공식 공공데이터](https://www.data.go.kr/data/15154190/fileData.do) | `lctrSn`, `pageIndex`; 접수상태·지역·강좌명·그룹·장소·내용. CSV는 강좌/접수/수강 기간·정원·대상·문의처 | 공개 설명만 읽고 로그인·접수 제출 제외. CSV는 연간/후행 자료이므로 웹 목록이 최신성 원본 | 구현 가능 + CSV 보강 |
| 6 | `goe_safety_education` | [공식 공지 목록](https://www.goese.kr/ko/board/notice_ko/list.do), 상세 `view.do?docSeq={docSeq}` | `docSeq`, `pageIndex`; 제목, 게시일, 프로그램 기간·대상·장소·방법 | URL의 `;jsessionid=` 제거해 canonicalize. `expConfirmList.do`, `reserved.do` 등 예약 흐름 제외 | 구현 가능 |
| 7 | `kcmf_gyeonggi` | [경기센터 공지 목록](https://kcmf.or.kr/KCMF/contents/KCMF050907.do), 같은 경로의 `?schM=view&id={id}` 상세 | 20자리 `id`, `page`, `viewCount`; 제목, 게시일, 교육/접수기간, 대상, 방식, 문의 | 검색 내부 API·로그인·강좌 신청 제외. 공개 SSR 게시판만 | 구현 가능 |
| 8 | `gill_paju_campus` | [파주 모집·행사 목록](https://www.gill.or.kr/gill/pgm/i-81/evnt/front/list.do), 상세 `i-81/evnt/front/detail.do?evnt_sn={id}` | `evnt_sn`, `pageIndex`, `searchCl`; 캠퍼스, 분류, 상태, 제목, 모집인원·기간 | 본인인증·신청 POST 제외. 8·9번은 한 어댑터에 고정 캠퍼스 ID로 분리 가능 | 구현 가능 |
| 9 | `gill_yangpyeong_campus` | [양평 모집·행사 목록](https://www.gill.or.kr/gill/pgm/i-290/evnt/front/list.do), 상세 `i-290/evnt/front/detail.do?evnt_sn={id}` | `evnt_sn`, `pageIndex`, `searchCl`; 8번과 동일 스키마 | 같은 `evnt_sn` 체계라도 캠퍼스 코드와 함께 복합 키 사용 | 구현 가능 |
| 10 | `ggac_arts_education` | [수원 교육](https://www.ggac.or.kr/ggac/M0000294/edu/program/list.do?gubun=CD001605), [용인 교육](https://www.ggac.or.kr/ggac/M0000117/edu/program/list.do?gubun=CD001606), 상세 `view.do?gubun={code}&idx={idx}` | `gubun + idx` (`EP...`), `searchYear`, `searchStatus`; 상태·기간·대상·장소·가격 | `robots.txt`의 Googlebot 전용 board 규칙과 무관한 `/edu/program/` 공개 경로만. 티켓팅 제외 | 구현 가능 |
| 11 | `korea_jobworld_children` | [어린이체험관 층별 목록](https://www.koreajobworld.or.kr/exrPreview/exrPreViewList.do?site=1&floor=1&exhpCd=33), 공식 XHR `selectExrPreviewImg.do?exhpHzCd={id}` | `exhpHzCd`; 체험실명·직업·권장연령/기간·정원·설명·운영상태. 응답은 허용 필드만 화이트리스트 | 예약·결제 제외. 공공데이터의 과거 예약 ZIP은 회원/성명/학교 등 개인·기관 식별 필드가 있어 **절대 수집하지 않음** | **JSON 즉시 구현** |
| 12 | `hwaseong_children_culture` | [공식 예약 화면](https://childrenjob.hscity.go.kr/booking/fmcs/1)에서 사용하는 읽기 전용 `/booking/rest/daily/*` JSON | `company → part → course → DailyMonthList`; 날짜별 `status_code/name`, 온라인 정원·신청수. 필요 시 공개 `DailyTimeList`로 회차 구분 | `DailyReserve`, 신청 품목·회원·신청/취소 경로 금지. `robots.txt`의 `/*search*`를 피함 | **JSON 즉시 구현** |
| 13 | `namyangju_children_vision` | [어린이비전센터 공지 목록 `/children/715`](https://www.ncuc.or.kr/children/715), 상세 `?action=read&action-value={hash}` | 32자 `action-value`, `page_size`; 제목·분류·등록일·본문/첨부 | 등록 URL `/children/674`는 홈. `robots.txt`가 막는 `/children/2356`과 예약·결제는 조회하지 않음 | 구현 가능 |
| 14 | `bucheon_robopark` | [교육 목록](https://robopark.org/ko/contents/RP0403000000.do), 상세 `?mode=view&eduSn={eduSn}` | `eduSn`; 상태·유/무료·대상·신청/교육기간·정원/신청/대기 수 | [부천 통합 예약](https://reserv.bucheon.go.kr/site/main/see/list)에 같은 항목이 있을 때 `제공기관+제목+기간`으로 병합; 기관 상세를 설명 원본으로 유지 | 구현 가능 |
| 15 | `korea_manhwa_museum` | [한국만화박물관 교육 목록](https://www.komacon.kr/comicsmuseum/edu/ssad.asp), 상세 `ssad_view.asp?sq={sq}&mode=&nowPage={page}` | `sq`, `nowPage`, `mode`; 제목·분류·기간·대상·가격·장소 | 부천시 강좌/예약 포털과 정규화 제목+기간+기관으로 중복 제거. 신청 폼 제외 | 구현 가능 |
| 16 | `bucheon_astronomy` | [공지/프로그램 목록](https://www.astrobucheon.or.kr/sub/sub0301.php), 상세 `sub0301.php?id={id}&page={page}&mode=read`; [정적 프로그램 안내](https://www.astrobucheon.or.kr/sub/program1_1.php?ca_id=1060) | `id`; 제목, 게시일, 본문 일정·대상·비용. 목록 쿼리 `mode=list&page=` | `robots.txt`에 `Crawl-delay: 600`, 이미지/PDF/XML 등 금지. **하루 1회 목록**, 새 ID 상세는 10분 이상 간격으로 큐잉·캐시; 외부 네이버 예약 미접속 | **속도 제한 조건부 구현** |
| 17 | `pocheon_hantangang_geopark` | [체험 프로그램 목록](https://www.hantangeopark.kr/bbs/board.php?bo_table=program_01), 상세 `?bo_table=program_01&wr_id={wr_id}` | `wr_id`, `page`, `sca=진행중/종료`; 상태·기간·대상·비용·장소·문의 | 신청 게시판 `program_01_request`와 `write.php` 제외 | 구현 가능 |
| 18 | `nfm_paju_family` | 기존 `home/87` 대신 [전체교육 `home/85`](https://www.nfm.go.kr/user/eduPlan/home/85/dataList.do?searchEduPlanCate=&searchStatus=)을 수집, 상세 `home/85/dataView.do?eduPlanIdx={id}` | `eduPlanIdx`, `page`; 접수상태·대상·접수/교육기간·장소·유/무료·접수방식 | 상세의 장소가 파주 주소이거나 제목에 `파주`가 있는 것 중 유아·어린이·청소년·가족만 유지. 서울 소스와 `eduPlanIdx`로 중복 제거. 신청 버튼/외부 폼 제외 | 구현 가능, 등록 URL 교정 필요 |
| 19 | `goe_south_early_childhood` | [공지 목록](https://www.kench.kr/kench/na/ntt/selectNttList.do?mi=10730&bbsId=6141), 상세 `selectNttInfo.do?...&nttSn={id}`; [가족체험 운영 개요](https://www.kench.kr/kench/cm/cntnts/cntntsView.do?mi=10764&cntntsId=1572), 공개 `rsvtInfo.do?mi=...&sn=...` 설명 페이지 | `nttSn`; 제목·등록일·본문 일정/대상. 정적 프로그램은 `mi+sn` | `aply/rm/rsvt/selectAplyList.do`는 **예약 조회/취소 화면**이므로 피드가 아님. 읽기 전용 설명·공지까지만, 로그인/신청/취소 POST 제외 | 구현 가능, 경로 교정 필요 |

### 2026-07-15 실물 레코드로 확인한 안정 키

단순히 URL 모양만 추정하지 않고, 공개 목록과 상세이 실제로 연결되는지 다음 ID들로 확인했다. fixture에는 개인정보가 없는 최소 HTML/JSON만 보관한다.

- 수원 두드림 `idx=769, 770, 771, 772`
- 국립지도박물관 [`sq=105777`](https://www.ngii.go.kr/map/board/view.do?sq=105777&board_code=edudetail_map&currentPage=1)
- 해우재 [`idx=4762`](https://haewoojae.com/m/load.asp?subPage=221&page=1&idx=4762&type=B1); 같은 교육 목록에 `4760`, `4759`, `4758`도 노출
- 경기국민안전체험관 `board_id=2383`(2026년 8월 예약 안내), `board_id=3054`(어린이날 프로그램)
- 미래과학교육원 [`lctrSn=SY00001399`](https://www.gise.kr/gise/aply/lctr/insertLctrRcptInfoView.do?lctrLrnClsfCd=STUDY&lctrSn=SY00001399&mi=10718); `lctrSn`은 숫자 전용이 아닌 `SY...` 문자열
- 경기도교육청안전교육관 [`docSeq=2910`](https://www.goese.kr/ko/board/notice_ko/view.do?docSeq=2910)
- KCMF 경기 `id=20260109135042664857`
- GILL 파주 `evnt_sn=513, 879`, 양평 `evnt_sn=985`
- 경기아트센터 `idx=EP000056`
- 한국잡월드 `exhpHzCd=3300028`(로봇연구소 공개 체험 설명 JSON)
- 화성시어린이문화센터 `company=HSKIDS01`, `part=01/06`, `course=01/61`; 월별 키는 `date_yyyymm`
- 남양주 어린이비전센터 [`action-value=bae113c87134a0dce1ee00c83db52e5c`](https://www.ncuc.or.kr/children/715?action=read&action-value=bae113c87134a0dce1ee00c83db52e5c)
- 부천로보파크 `eduSn=2304`
- 한국만화박물관 `sq=409, 410, 411, 412, 413`
- 부천천문과학관 `id=802`를 포함한 `mode=read` 링크
- 한탄강세계지질공원 `wr_id=21`
- 국립민속박물관 파주 [`eduPlanIdx=3006`](https://www.nfm.go.kr/user/eduPlan/home/85/dataView.do?eduPlanIdx=3006), [`eduPlanIdx=2996`](https://www.nfm.go.kr/user/eduPlan/home/85/dataView.do?eduPlanIdx=2996)
- 남부유아체험교육원 [`nttSn=1200432`](https://www.kench.kr/kench/na/ntt/selectNttInfo.do?mi=10730&bbsId=6141&nttSn=1200432)

이로써 표의 19개 후보 모두 실제 공개 목록·상세 또는 읽기 전용 공식 JSON에서 안정 키를 확인했다. GISE 상세와 화성 JSON은 공개 프로그램 메타데이터 필드만 fixture에 남기며, 동의·신청 폼과 개인식별 필드는 저장하지 않는다.

## 구조화 피드 세부 명세

### 화성시어린이문화센터

공식 화면의 자바스크립트가 호출하는 공개 읽기 전용 엔드포인트다. `application/x-www-form-urlencoded` POST를 사용하되 아래 조회 메서드만 허용한다.

1. `POST /booking/rest/daily/company`
2. `POST /booking/rest/daily/part` — `company_code=HSKIDS01`
3. `POST /booking/rest/daily/course` — `company_code`, `part_code`
4. `POST /booking/rest/daily/DailyMonthList` — `company_code`, `part_code`, `course_code`, `date_yyyymm`
5. 날짜별 회차가 필요할 때만 `POST /booking/rest/daily/DailyTimeList`

현재 공개 응답에서 확인한 값은 `HSKIDS01`, `01 키즈체험관`, `06 교육프로그램`, 개인/단체 과정과 날짜별 `status_name`(예약가능·마감·휴관일·예약불가), `online_capa`, `online_regcnt`다. 원시 응답을 그대로 저장하지 말고 이 공개 시설·회차 필드만 화이트리스트한다. `DailyReserve`, `DailyItemList`, 신청자 조회/등록/취소 이름을 가진 엔드포인트는 차단 목록에 둔다.

### 한국잡월드 어린이체험관

층별 공개 목록의 `getImgList(previewOd, exhpHzCd)`에서 `exhpHzCd`를 얻은 뒤 다음 공식 GET JSON을 호출한다.

```text
GET https://www.koreajobworld.or.kr/exrPreview/selectExrPreviewImg.do?exhpHzCd={id}
```

허용 필드는 `exhpHzCd`, `exhpHallDiv`, `usepossStartDt`, `usepossEndDt`, `exhpHallNm`, `exhpHallExpl`, `expPoint`, `exhCapaPcnt`, `expCapaPcnt`, `adminSitu`, `opSitu`, `expTerm`, `floor`, `exhpOccu`, `exhpDtlCn`, `interestTypeCn`, `recomYn`, `hitYn`이다. `sysModId` 같은 내부 운영자 식별 필드는 버리고, 이미지 전체 미러링도 하지 않는다.

### 경기도교육청미래과학교육원 공공데이터 보강

[데이터셋 15154190](https://www.data.go.kr/data/15154190/fileData.do)의 [공식 카탈로그 JSON](https://www.data.go.kr/catalog/15154190/fileData.json)은 공개 CSV 파일 포인터와 갱신일을 제공한다. 확인된 열은 강좌구분, 강좌그룹, 연수과정명, 접수시작일/마감일, 수강시작일/종료일, 선정방식, 정원, 대상자, 연수장소, 연수내용, 문의처다.

이 CSV는 실시간 접수상태가 없고 연간 파일이므로 다음처럼 사용한다.

- 웹 목록의 `lctrSn`과 제목·기간을 기준으로 최신 상태를 결정한다.
- CSV는 누락된 대상·정원·장소·문의처 보강과 과거 추세 분석에만 쓴다.
- 파일 포인터는 바뀔 수 있으므로 하드코딩한 `atchFileId` 대신 카탈로그 JSON에서 매번 확인한다.

## 공개 경로별 구현 주의점

### HTML 목록/상세 공통

- 목록은 하루 1회, 새 안정 키가 나타나거나 목록의 수정일/상태가 바뀐 항목만 상세 조회한다.
- `ETag`/`Last-Modified`가 있으면 조건부 GET을 사용하고, 없으면 본문 해시로 변경 여부를 판단한다.
- 상세 파싱이 실패했을 때 빈 성공으로 삼지 말고, 목록 건수·필수 필드·상태 어휘가 바뀌면 `schema_changed`로 실패를 드러낸다.
- 원문 HTML 전체를 장기 재배포하지 않고, 제목·기간·대상·가격·장소·상태·공식 링크 같은 사실 메타데이터만 저장한다.
- 이메일·전화는 공개 문의처라도 서비스 노출에 꼭 필요할 때만 저장한다. 신청자 이름, 회원 ID, 학교/기관명, 휴대전화, 생년월일은 저장하지 않는다.

### 인코딩·세션 URL

- 해우재 같은 레거시 페이지는 헤더가 부정확할 수 있어 UTF-8 파싱 실패 시 CP949/EUC-KR을 검증한다.
- `;jsessionid=...`, CSRF 토큰, 뷰 상태, 쿠키는 canonical URL과 저장 데이터에서 제거한다.
- 상세 키만 URL에 남기고 추적 매개변수와 페이지 번호는 중복 키에서 제외한다.

### 어린이·가족 필터

기관 이름만으로 모두 어린이 프로그램으로 간주하지 않는다. 제목·대상·본문에 아래 긍정 신호가 하나 이상 있어야 한다.

- `어린이`, `초등`, `유아`, `청소년`, `가족`, `보호자 동반`, 구체적인 학년/연령

그리고 `성인만`, `교원만`, `전문가만`, `기관 담당자만`은 제외한다. 국립민속박물관은 반드시 이 필터와 파주 장소 필터를 함께 적용한다.

## 공공데이터포털 조사 결과

| 기관 | 공식 데이터 | 사용 판정 |
|---|---|---|
| 미래과학교육원 | [경기도교육청미래과학교육원 강좌 정보](https://www.data.go.kr/data/15154190/fileData.do) | 실시간 웹 목록 보강용으로 사용 |
| 경기국민안전체험관 | [경기도 국민안전체험관 예약](https://www.data.go.kr/data/15149341/fileData.do) | 일회성/시점성 예약 자료라 일일 신규 프로그램 피드로 부적합. 신청자 수준 필드가 섞일 가능성이 있어 원시 수집 금지 |
| 한국잡월드 | [체험관 예약 관련 파일데이터](https://www.data.go.kr/data/15124197/fileData.do) | 과거 압축파일에 회원/성명/학교 등 개인·기관 식별 가능 필드가 확인되어 **수집 금지** |
| 한국잡월드 | [휴관일 정보](https://www.data.go.kr/data/15069028/fileData.do) | 영업일 보강에는 사용 가능하나 프로그램 모집 정보는 아님 |

나머지 16개 기관은 2026-07-15 공식 공공데이터포털 검색에서 이 서비스에 직접 쓸 수 있는 반복형 프로그램 API/파일을 확인하지 못했다. 따라서 해당 기관의 공식 공개 목록·상세가 1차 소스다.

## `robots.txt`, RSS, 사이트맵 감사

- 수원 두드림은 [사이트맵](https://www.swdodream.or.kr/sitemap.xml)이 정상 XML이지만 개별 프로그램이 아니라 `p=38`, `p=40` 인덱스만 담는다. 발견 보조용이지 이벤트 피드 대체재가 아니다.
- 19개 후보에서 현재 운영 가능한 행사 RSS/Atom 피드는 확인하지 못했다. 화면에 RSS 문구만 있고 안정 URL/행사 스키마를 확인할 수 없는 경우는 피드로 승격하지 않는다.
- `robots.txt` 404/빈 응답: 국토지리정보원, 미래과학교육원, 안전교육관, GILL, 한국잡월드, 한국만화박물관, 한탄강지질공원, 남부유아체험교육원. 이를 무조건 허용 신호로 해석하지 않고 실행 직전 재확인하며 보수적 속도를 적용한다.
- 명시 허용 또는 대상 경로에 금지 규칙 없음: 경기국민안전체험관, KCMF, 부천로보파크, 경기아트센터의 `/edu/program/`, 국립민속박물관의 `/user/eduPlan/`.
- 부분 금지: 해우재는 `/sub_page/`, 다운로드/관리 자원 금지; 화성은 `/*search*` 금지; 남양주도시공사는 `/children/2356` 금지; 수원 두드림은 `p=27*` 등 일부 게시판 금지.
- 부천천문과학관은 가장 엄격하다. 일반 봇에 이미지/PDF/XML·관리·자산 경로 금지와 `Crawl-delay: 600`이 있어 위 표의 저빈도 큐를 강제해야 한다.

모든 호스트는 고정된 설명형 User-Agent와 연락 가능한 운영자 URL/이메일을 사용하고, 실행 시점의 robots 정책이 바뀌면 해당 호스트를 즉시 중단한다.

## 중복 제거 규칙

1. **동일 기관 안정 키 우선**: `source_id + stable_id`를 1차 키로 쓴다.
2. **부천 교차 게시**: 로보파크·만화박물관·천문과학관과 부천 통합 예약이 겹치면 `provider + normalized_title + start_date + venue`로 병합한다. 기관 원문은 설명의 원본, 통합 예약은 공개 상태가 있을 때 상태 보조로만 쓴다.
3. **국립민속박물관 서울/파주**: 같은 `eduPlanIdx`는 한 건이다. `파주`, `탄현면 헤이리로 30`, `파주관` 장소 신호로 경기 레코드에 귀속한다.
4. **GILL 두 캠퍼스**: `campus_menu_id + evnt_sn`을 키로 하여 파주/양평을 섞지 않는다.
5. **수원 포털 중복**: 두드림·해우재가 수원 통합 소스에 재게시되면 기관명, 제목, 행사 시작일, 장소를 비교하고 공식 시설 페이지 URL을 canonical source로 유지한다.
6. 안정 키가 없는 교차 게시의 fuzzy 병합은 날짜가 겹치고 장소가 동일할 때만 수행하며, 자동 확신도가 낮으면 둘 다 남겨 사람이 확인한다.

## 구현 우선순위

1. **P0**: 화성 JSON, 한국잡월드 JSON, 미래과학교육원 HTML+CSV, 경기국민안전체험관 공지형
2. **P1**: 수원 두드림, 국립지도박물관, 안전교육관, KCMF 경기, GILL 2개 캠퍼스, 경기아트센터, 남양주비전센터, 부천 3개 시설, 한탄강지질공원, 국립민속박물관 파주
3. **P2**: 해우재, 남부유아체험교육원

부천천문과학관은 사업 우선순위는 P1이지만, 크롤러 스케줄에서는 별도의 600초 host throttle을 가진다.

## 완료 기준

- 19개 ID 각각에 대해 최소 1개의 공개 목록/구조화 피드와 안정 키를 fixture로 고정한다.
- 목록 0건, 마감만 존재, 인코딩 오류, 상태 어휘 추가, 404/500, robots 변경을 테스트한다.
- 신청/예약/결제/회원/취소 URL denylist 테스트와 개인식별 필드 미저장 테스트를 둔다.
- 공개 목록 건수와 파싱 건수가 갑자기 0 또는 급감하면 성공으로 처리하지 않고 알림을 발생시킨다.
- 공식 링크는 상세 페이지까지만 제공하고, 사용자가 직접 신청 사이트로 이동하도록 한다. 수집기가 신청을 대신 수행하지 않는다.
