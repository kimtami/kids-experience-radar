from __future__ import annotations

from datetime import date, datetime, time, timezone, timedelta
from html import unescape
import math
import re
from typing import Iterable


KST = timezone(timedelta(hours=9))


# Restrict tag removal to real, known HTML element names.  Program titles in
# Korean public feeds commonly use angle brackets for emphasis and may start
# with ASCII text (for example ``<AI 체험>`` or ``<K-POP 교실>``); a generic
# ``<[A-Za-z]...>`` expression incorrectly erased those titles.
_HTML_TAG_NAMES = (
    "a|abbr|address|article|aside|audio|b|bdi|bdo|blockquote|body|br|button|"
    "canvas|caption|cite|code|col|colgroup|data|datalist|dd|del|details|dfn|"
    "dialog|div|dl|dt|em|fieldset|figcaption|figure|footer|form|h[1-6]|head|"
    "header|hgroup|hr|html|i|iframe|img|input|ins|kbd|label|legend|li|link|"
    "main|map|mark|menu|meta|meter|nav|noscript|object|ol|optgroup|option|"
    "output|p|picture|pre|progress|q|rp|rt|ruby|s|samp|section|select|slot|"
    "small|source|span|strong|sub|summary|sup|table|tbody|td|template|"
    "textarea|tfoot|th|thead|time|title|tr|track|u|ul|var|video|wbr"
)
_HTML_TAG_RE = re.compile(
    rf"</?(?:{_HTML_TAG_NAMES})(?:\s[^<>]*?)?\s*/?>",
    flags=re.I,
)


def clean_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = unescape(str(value))
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    # Strip actual HTML tags while preserving angle-bracket program titles.
    text = _HTML_TAG_RE.sub(" ", text)
    text = re.sub(r"[\u00a0\s]+", " ", text).strip()
    return text or None


def safe_float(value: object | None) -> float | None:
    if value in (None, "", "null", "None"):
        return None
    try:
        parsed = float(str(value).strip())
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def parse_datetime(value: object | None, *, end_of_day: bool = False) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None
    text = text.strip().replace("년", "-").replace("월", "-").replace("일", "")
    text = re.sub(r"\([^)]*\)", "", text).strip()
    candidates = [text, text.replace(".", "-").rstrip("- ")]
    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=KST)
            if end_of_day and parsed.timetz().replace(tzinfo=None) == time.min:
                parsed = datetime.combine(parsed.date(), time.max, tzinfo=parsed.tzinfo)
            return parsed
        except ValueError:
            pass
    digits = re.sub(r"\D", "", text)
    formats: Iterable[tuple[str, str]] = (
        ("%Y%m%d%H%M%S", digits[:14]),
        ("%Y%m%d%H%M", digits[:12]),
        ("%Y%m%d", digits[:8]),
    )
    for fmt, candidate in formats:
        if len(candidate) != len(datetime.now().strftime(fmt)):
            continue
        try:
            parsed = datetime.strptime(candidate, fmt).replace(tzinfo=KST)
            if fmt == "%Y%m%d" and end_of_day:
                parsed = datetime.combine(parsed.date(), time.max, tzinfo=KST)
            return parsed
        except ValueError:
            continue
    match = re.search(r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if match:
        parsed_date = date(*(int(part) for part in match.groups()))
        return datetime.combine(parsed_date, time.max if end_of_day else time.min, tzinfo=KST)
    return None


def parse_date_range(value: object | None) -> tuple[datetime | None, datetime | None]:
    text = clean_text(value)
    if not text:
        return None, None
    matches = re.findall(r"20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}", text)
    if len(matches) >= 2:
        return parse_datetime(matches[0]), parse_datetime(matches[1], end_of_day=True)
    if len(matches) == 1:
        start = parse_datetime(matches[0])
        end = parse_datetime(matches[0], end_of_day=True)
        return start, end
    return parse_datetime(text), None


def parse_price(value: object | None) -> tuple[int | None, str | None]:
    text = clean_text(value)
    if not text:
        return None, None
    lowered = text.casefold()
    if any(token in lowered for token in ("무료", "free", "무 료")) or re.search(
        r"(?<![\d,])0\s*원", lowered
    ):
        extra = re.search(r"(?:재료비|교재비|별도)\D{0,8}([0-9][0-9,]*)", text)
        return (int(extra.group(1).replace(",", "")) if extra else 0), text
    numbers = [int(raw.replace(",", "")) for raw in re.findall(r"(?<!\d)([0-9][0-9,]{0,10})(?=\s*원)", text)]
    return (min(numbers) if numbers else None), text


def parse_age_range(value: object | None) -> tuple[int | None, int | None, str | None]:
    text = clean_text(value)
    if not text:
        return None, None, None
    low = text.casefold()
    age_min: int | None = None
    age_max: int | None = None
    if "초등" in low or re.search(r"\b초\s*\d", low):
        age_min, age_max = 7, 13
        grade_range = re.search(
            r"(?:초등?|초)\s*([1-6])\s*(?:~|[-–]|부터)\s*([1-6])\s*학년?", low
        )
        if grade_range:
            age_min = int(grade_range.group(1)) + 6
            age_max = int(grade_range.group(2)) + 6
        else:
            grades = [int(v) for v in re.findall(r"(?:초등?|초)\s*([1-6])", low)]
            if grades:
                age_min, age_max = min(grades) + 6, max(grades) + 6
    if any(token in low for token in ("어린이", "아동", "가족", "보호자 동반")):
        age_min = 5 if age_min is None else age_min
        age_max = 13 if age_max is None else age_max
    range_match = re.search(r"(\d{1,2})\s*세\s*(?:~|[-–]|부터)\s*(\d{1,2})\s*세?", low)
    if range_match:
        age_min, age_max = int(range_match.group(1)), int(range_match.group(2))
    else:
        min_match = re.search(r"(\d{1,2})\s*세\s*(?:이상|부터)", low)
        max_match = re.search(r"(\d{1,2})\s*세\s*(?:이하|까지)", low)
        if min_match:
            age_min = int(min_match.group(1))
        if max_match:
            age_max = int(max_match.group(1))
    return age_min, age_max, text


def child_relevance(title: str, age_text: str | None, description: str | None = None) -> float:
    haystack = " ".join(part for part in (title, age_text or "", description or "") if part).casefold()
    score = 0.0
    weights = {
        "초등": 0.55,
        "어린이": 0.45,
        "아동": 0.45,
        "가족": 0.25,
        "키즈": 0.4,
        "체험": 0.2,
        "교육": 0.15,
        "보호자": 0.1,
    }
    for token, weight in weights.items():
        if token in haystack:
            score += weight
    if re.search(r"(?:초|초등)\s*[1-6]", haystack):
        score += 0.25
    if "성인만" in haystack or "성인 대상" in haystack:
        score -= 0.8
    if "유아만" in haystack:
        score -= 0.35
    return max(0.0, min(1.0, score))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
