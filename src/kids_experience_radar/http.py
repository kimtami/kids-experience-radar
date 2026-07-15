from __future__ import annotations

from dataclasses import dataclass
from email.utils import parsedate_to_datetime
import os
import random
import re
import ssl
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
import truststore

from . import __version__


PROJECT_URL = "https://github.com/kimtami/kids-experience-radar"


class HttpPolicyError(RuntimeError):
    """Raised when a page is blocked by policy before collection."""


class RetryableHttpError(RuntimeError):
    pass


class HttpRequestError(RuntimeError):
    pass


@dataclass(slots=True)
class RobotsDecision:
    allowed: bool
    robots_url: str
    reason: str


@dataclass(slots=True)
class _RobotsState:
    robots_url: str
    parser: RobotFileParser | None = None
    terminal_allowed: bool | None = None
    reason: str | None = None


class PoliteHttpClient:
    def __init__(
        self,
        *,
        min_interval_seconds: float = 5.0,
        timeout_seconds: float = 25.0,
        max_retries: int = 3,
        contact: str | None = None,
    ) -> None:
        contact = (contact or os.getenv("KIDS_RADAR_CONTACT", "")).strip()
        if contact.startswith(("https://", "http://")):
            contact_uri = contact
        elif contact:
            contact_uri = f"mailto:{contact}"
        else:
            contact_uri = PROJECT_URL
        self.user_agent = f"KidsExperienceRadar/{__version__} (+{contact_uri})"
        self.min_interval_seconds = min_interval_seconds
        self.max_retries = max_retries
        self._last_request_by_host: dict[str, float] = {}
        self._robots: dict[str, _RobotsState] = {}
        native_tls = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self._client = httpx.Client(
            timeout=timeout_seconds,
            # Redirects are followed manually so a collection request cannot
            # escape its reviewed origin or land on a robots-denied path.
            follow_redirects=False,
            verify=native_tls,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json, application/xml, text/xml, text/html;q=0.9, */*;q=0.5",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "PoliteHttpClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _wait_for_host(self, url: str) -> None:
        host = urlparse(url).netloc
        now = time.monotonic()
        wait = self.min_interval_seconds - (now - self._last_request_by_host.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        self._last_request_by_host[host] = time.monotonic()

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float | None:
        raw = response.headers.get("Retry-After")
        if not raw:
            return None
        try:
            return max(0.0, float(raw))
        except ValueError:
            try:
                return max(0.0, (parsedate_to_datetime(raw) - parsedate_to_datetime(response.headers["Date"])).total_seconds())
            except (KeyError, TypeError, ValueError):
                return None

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, object] | None = None,
        data: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
        allowed_status_codes: frozenset[int] = frozenset(),
    ) -> httpx.Response:
        last_error: Exception | None = None
        host = urlparse(url).hostname or "remote host"
        for attempt in range(self.max_retries + 1):
            try:
                response = self._request_with_safe_redirects(
                    method,
                    url,
                    params=params,
                    data=data,
                    headers=headers,
                )
                if response.status_code in (401, 403):
                    raise HttpPolicyError(f"access denied ({response.status_code}) for {host}")
                if response.status_code in allowed_status_codes:
                    return response
                if response.status_code == 429 or response.status_code >= 500:
                    retry_after = self._retry_after_seconds(response)
                    if attempt < self.max_retries:
                        time.sleep(retry_after if retry_after is not None else (2**attempt + random.random()))
                        continue
                    raise RetryableHttpError(
                        f"HTTP {response.status_code} after retries for {host}"
                    )
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise HttpRequestError(
                        f"HTTP {response.status_code} for {host}"
                    ) from exc
                return response
            except HttpPolicyError:
                raise
            except HttpRequestError:
                raise
            except (httpx.TimeoutException, httpx.TransportError, RetryableHttpError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(2**attempt + random.random())
                    continue
                break
        error_name = type(last_error).__name__ if last_error else "unknown error"
        raise RetryableHttpError(f"request failed for {host}: {error_name}")

    @staticmethod
    def _origin(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme.casefold()}://{parsed.netloc.casefold()}"

    def _decision_from_state(
        self, state: _RobotsState, target_url: str
    ) -> RobotsDecision:
        if state.parser is not None:
            allowed = state.parser.can_fetch(self.user_agent, target_url)
            return RobotsDecision(
                allowed,
                state.robots_url,
                "allowed" if allowed else "disallowed by robots.txt",
            )
        return RobotsDecision(
            bool(state.terminal_allowed),
            state.robots_url,
            state.reason or "robots policy unavailable; fail closed",
        )

    def _request_with_safe_redirects(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, object] | None,
        data: dict[str, object] | None,
        headers: dict[str, str] | None,
    ) -> httpx.Response:
        request = self._client.build_request(
            method,
            url,
            params=params,
            data=data,
            headers=headers,
        )
        for _ in range(10):
            request_url = str(request.url)
            self._wait_for_host(request_url)
            response = self._client.send(request)
            next_request = response.next_request
            if next_request is None:
                return response

            target_url = str(next_request.url)
            source_origin = self._origin(request_url)
            target_origin = self._origin(target_url)
            if source_origin != target_origin:
                source_host = urlparse(request_url).hostname or "remote host"
                raise HttpPolicyError(
                    f"cross-origin redirect blocked for {source_host}"
                )

            # If the source loaded robots rules before collection, evaluate the
            # redirected path against those same cached rules.  This avoids the
            # classic allow-/list then redirect-to-/private bypass.
            state = self._robots.get(target_origin)
            if state is not None:
                decision = self._decision_from_state(state, target_url)
                if not decision.allowed:
                    raise HttpPolicyError(
                        f"redirect target {decision.reason}: {decision.robots_url}"
                    )
            request = next_request
        host = urlparse(url).hostname or "remote host"
        raise HttpRequestError(f"too many redirects for {host}")

    def get(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        return self._request("GET", url, params=params, headers=headers)

    def post(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        data: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        return self._request("POST", url, params=params, data=data, headers=headers)

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict:
        response = self.get(url, params=params, headers=headers)
        return response.json()

    def get_text(self, url: str, *, params: dict[str, object] | None = None) -> str:
        response = self.get(url, params=params)
        if not response.encoding:
            response.encoding = response.charset_encoding or "utf-8"
        return response.text

    def post_json(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        data: dict[str, object] | None = None,
    ) -> dict:
        return self.post(url, params=params, data=data).json()

    def post_text(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        data: dict[str, object] | None = None,
    ) -> str:
        response = self.post(url, params=params, data=data)
        if not response.encoding:
            response.encoding = response.charset_encoding or "utf-8"
        return response.text

    @staticmethod
    def _is_semantic_robots_404(body: str) -> bool:
        sample = re.sub(r"\s+", " ", body[:20_000]).casefold()
        missing_markers = (
            "404 not found",
            "status:404",
            "status: 404",
            "페이지를 찾을 수 없",
            "요청하신 페이지를 찾을 수 없",
        )
        block_markers = (
            "captcha",
            "access denied",
            "web application firewall",
            "cloudflare ray id",
            "로그인",
        )
        return any(marker in sample for marker in missing_markers) and not any(
            marker in sample for marker in block_markers
        )

    def robots_decision(self, url: str) -> RobotsDecision:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin in self._robots:
            return self._decision_from_state(self._robots[origin], url)
        robots_url = f"{origin}/robots.txt"
        try:
            response = self._request(
                "GET",
                robots_url,
                allowed_status_codes=frozenset({404, 410}),
            )
            if response.status_code in {404, 410}:
                state = _RobotsState(
                    robots_url=robots_url,
                    terminal_allowed=True,
                    reason=(
                        f"robots unavailable ({response.status_code}); no rules apply "
                        "under RFC 9309 section 2.3.1.3"
                    ),
                )
                self._robots[origin] = state
                return self._decision_from_state(state, url)
            content_type = response.headers.get("content-type", "").casefold()
            body = response.text
            if "html" in content_type or "<html" in body[:300].casefold():
                if self._is_semantic_robots_404(body):
                    state = _RobotsState(
                        robots_url=robots_url,
                        terminal_allowed=True,
                        reason=(
                            "robots endpoint published a semantic 404 page; "
                            "no rules apply"
                        ),
                    )
                else:
                    state = _RobotsState(
                        robots_url=robots_url,
                        terminal_allowed=False,
                        reason="robots endpoint returned HTML/WAF; fail closed",
                    )
            else:
                parser = RobotFileParser()
                parser.set_url(robots_url)
                parser.parse(body.splitlines())
                state = _RobotsState(robots_url=robots_url, parser=parser)
        except Exception as exc:
            state = _RobotsState(
                robots_url=robots_url,
                terminal_allowed=False,
                reason=(
                    "robots unavailable; fail closed: "
                    f"{type(exc).__name__}"
                ),
            )
        self._robots[origin] = state
        return self._decision_from_state(state, url)

    def assert_html_allowed(self, url: str) -> None:
        decision = self.robots_decision(url)
        if not decision.allowed:
            raise HttpPolicyError(f"{decision.reason}: {decision.robots_url}")
