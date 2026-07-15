from datetime import datetime, timedelta

from kids_experience_radar.digest import render_markdown
from kids_experience_radar.models import Event
from kids_experience_radar.normalizers import KST


def test_digest_contains_official_link_and_source() -> None:
    now = datetime.now(KST)
    event = Event(
        source_id="official",
        source_name="공식 API",
        external_id="1",
        title="초등 과학 체험",
        detail_url="https://example.org/official/1",
        event_start=now + timedelta(days=1),
        apply_end=now + timedelta(hours=12),
        price_text="무료",
        venue_name="어린이과학관",
        status="접수중",
        child_relevance_score=1,
        distance_km=2.4,
    )
    body = render_markdown([event])
    assert "[초등 과학 체험](https://example.org/official/1)" in body
    assert "2.4km" in body
    assert "출처: 공식 API" in body
    assert "원문" in body
