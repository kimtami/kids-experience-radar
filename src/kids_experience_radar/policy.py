from __future__ import annotations

from dataclasses import dataclass
import os
from urllib.parse import urlparse


@dataclass(slots=True, frozen=True)
class BlockRule:
    host_suffix: str
    reason: str


BLOCKED_HTML_HOSTS = (
    BlockRule("cafe.naver.com", "member/community content; use official source URL submission instead"),
    BlockRule("m.cafe.naver.com", "member/community content; use official source URL submission instead"),
    BlockRule("open.kakao.com", "chat content is not a crawl source"),
    BlockRule("talk.kakao.com", "chat content is not a crawl source"),
    BlockRule("band.us", "private/community content"),
    BlockRule("ggoomgil.go.kr", "robots.txt disallows all crawling"),
    BlockRule("share.gg.go.kr", "NetFunnel/WAF enumeration is not allowed; use an official API or partnership"),
)


def blocked_reason(url: str) -> str | None:
    host = (urlparse(url).hostname or "").casefold()
    for rule in BLOCKED_HTML_HOSTS:
        if host == rule.host_suffix or host.endswith(f".{rule.host_suffix}"):
            return rule.reason
    return None


def assert_html_source_allowed(url: str, legal_review_status: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"HTML source must use an http(s) URL: {url}")
    reason = blocked_reason(url)
    if reason:
        raise ValueError(f"blocked HTML source {url}: {reason}")
    if legal_review_status != "approved":
        raise ValueError(
            f"HTML source {url} is not legally approved (status={legal_review_status!r}); "
            "robots allowance alone is insufficient"
        )


def explicit_source_approval(source_id: str) -> tuple[bool, str | None]:
    """Require a source-id allowlist before opt-in private collectors can run."""

    approved = {
        value.strip()
        for value in os.getenv("KIDS_RADAR_APPROVED_SOURCES", "").split(",")
        if value.strip()
    }
    if source_id in approved:
        return True, None
    return (
        False,
        f"{source_id} requires policy approval; add its exact id to "
        "KIDS_RADAR_APPROVED_SOURCES after review",
    )


def explicit_robots_override(source_id: str) -> tuple[bool, str | None]:
    """Require a separate operator acknowledgement for an ambiguous robots URL.

    This is intentionally distinct from source/legal approval.  It must never
    be used to override an explicit ``Disallow`` rule; it exists only for a
    reviewed origin whose ``/robots.txt`` publishes non-robots HTML instead of
    a parseable policy file.
    """

    approved = {
        value.strip()
        for value in os.getenv("KIDS_RADAR_ROBOTS_OVERRIDE_SOURCES", "").split(",")
        if value.strip()
    }
    if source_id in approved:
        return True, None
    return (
        False,
        f"{source_id} has an ambiguous non-robots /robots.txt response; add its "
        "exact id to KIDS_RADAR_ROBOTS_OVERRIDE_SOURCES only after a documented "
        "human policy review",
    )
