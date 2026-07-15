from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

import httpx

from .models import Event
from .normalizers import KST


def _date(value: datetime | None) -> str:
    return value.astimezone(KST).strftime("%m/%d %H:%M") if value else "일정 원문 확인"


def render_markdown(events: list[Event], *, heading: str = "오늘 새로 찾은 주변 체험") -> str:
    lines = [f"# {heading} ({len(events)}건)", ""]
    if not events:
        lines.append("새로 확인된 체험이 없습니다.")
        return "\n".join(lines) + "\n"
    for event in events:
        distance = f"{event.distance_km:.1f}km" if event.distance_km is not None else "거리 미확인"
        place = event.venue_name or event.address or event.region or "장소 원문 확인"
        fee = event.price_text or "가격 원문 확인"
        lines.extend(
            [
                f"## [{event.title}]({event.detail_url})",
                f"- {distance} · {place}",
                f"- 체험: {_date(event.event_start)} · {fee}",
                f"- 신청 마감: {_date(event.apply_end)} · 상태: {event.status or '원문 확인'}",
                f"- 출처: {event.source_name}",
                "",
            ]
        )
    lines.append("신청 가능 여부와 세부 조건은 반드시 주최기관 원문에서 다시 확인하세요.")
    return "\n".join(lines) + "\n"


def write_digest(path: str | Path, events: list[Event]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_markdown(events), encoding="utf-8")
    return output


def send_webhook(url: str, events: list[Event], *, timeout_seconds: float = 15.0) -> None:
    payload = {
        "text": render_markdown(events),
        "generated_at": datetime.now(KST).isoformat(),
        "count": len(events),
        "events": [event.to_dict(include_raw=False) for event in events],
    }
    response = httpx.post(url, json=payload, timeout=timeout_seconds)
    response.raise_for_status()


def render_json(events: list[Event]) -> str:
    return json.dumps(
        {"count": len(events), "events": [event.to_dict(include_raw=False) for event in events]},
        ensure_ascii=False,
        indent=2,
    )
