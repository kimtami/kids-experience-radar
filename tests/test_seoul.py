from kids_experience_radar.sources.seoul import builtin_seoul_sources


def test_maps_seoul_reservation_fields() -> None:
    source = builtin_seoul_sources()[0]
    event = source._map_reservation(
        {
            "SVCID": "S1",
            "SVCNM": "초등 가족 역사 체험",
            "SVCURL": "https://yeyak.seoul.go.kr/item/S1",
            "PLACENM": "서울역사박물관",
            "MAXCLASSNM": "문화체험",
            "MINCLASSNM": "교육체험",
            "SVCSTATNM": "접수중",
            "PAYATNM": "무료",
            "USETGTINFO": "초등 1~3학년 및 보호자",
            "SVCOPNBGNDT": "2026-08-01 00:00:00.0",
            "SVCOPNENDDT": "2026-08-02 00:00:00.0",
            "RCPTBGNDT": "2026-07-15 10:00:00.0",
            "RCPTENDDT": "2026-07-25 18:00:00.0",
            "AREANM": "종로구",
            "X": "126.9703",
            "Y": "37.5705",
            "DTLCONT": "<p>박물관 체험</p>",
        }
    )
    assert event.external_id == "S1"
    assert event.price_min == 0
    assert event.age_min == 7
    assert event.age_max == 9
    assert event.latitude == 37.5705
    assert event.longitude == 126.9703
    assert event.event_end is not None and event.event_end.hour == 23
    assert event.child_relevance_score >= 0.9


def test_maps_seoul_cultural_event_coordinates() -> None:
    source = builtin_seoul_sources()[2]
    event = source._map_event(
        {
            "TITLE": "어린이 미술 전시",
            "HMPG_ADDR": "https://culture.seoul.go.kr/view?cultcode=10",
            "STRTDATE": "2026-09-01",
            "END_DATE": "2026-09-30",
            "USE_TRGT": "어린이 및 가족",
            "USE_FEE": "무료",
            "PLACE": "꿈의숲",
            "GUNAME": "강북구",
            "LAT": "37.62",
            "LOT": "127.04",
        }
    )
    assert event.latitude == 37.62
    assert event.longitude == 127.04
    assert event.price_min == 0
    assert event.external_id == "10"
