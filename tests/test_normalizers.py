from datetime import time

from kids_experience_radar.normalizers import (
    child_relevance,
    clean_text,
    haversine_km,
    parse_age_range,
    parse_datetime,
    parse_price,
)


def test_clean_text_preserves_korean_program_brackets_but_removes_html() -> None:
    assert clean_text("<b>경기상상캠퍼스</b> <여름상상캠프>") == (
        "경기상상캠퍼스 <여름상상캠프>"
    )
    assert clean_text("<AI 체험> <K-POP 교실>") == "<AI 체험> <K-POP 교실>"
    assert clean_text('<div class="title">어린이 <strong>과학</strong></div>') == (
        "어린이 과학"
    )
    assert clean_text("<script>steal()</script>어린이 체험") == "어린이 체험"


def test_korean_age_and_price_parsing() -> None:
    assert parse_age_range("초등 1~3학년")[:2] == (7, 9)
    assert parse_age_range("8세 이상")[:2] == (8, None)
    assert parse_price("무료(재료비 5,000원 별도)")[0] == 5000
    assert parse_price("참가비 10,000원")[0] == 10000


def test_end_date_is_inclusive() -> None:
    parsed = parse_datetime("2026-08-01", end_of_day=True)
    assert parsed is not None
    assert parsed.time() == time.max


def test_child_relevance_and_distance() -> None:
    assert child_relevance("초등 어린이 과학 체험", None) >= 0.9
    assert child_relevance("성인 대상 와인 강좌", None) == 0
    assert 0.9 < haversine_km(37.5665, 126.9780, 37.5755, 126.9780) < 1.1
