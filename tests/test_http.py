import httpx
import pytest

from kids_experience_radar.http import HttpPolicyError, HttpRequestError, PoliteHttpClient


def test_user_agent_has_public_project_fallback_and_accepts_operator_contact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KIDS_RADAR_CONTACT", raising=False)
    with PoliteHttpClient() as default_client:
        assert default_client.user_agent == (
            "KidsExperienceRadar/0.1.0 "
            "(+https://github.com/kimtami/kids-experience-radar)"
        )
    with PoliteHttpClient(contact="operator@example.org") as email_client:
        assert email_client.user_agent.endswith("(+mailto:operator@example.org)")
    with PoliteHttpClient(contact="https://example.org/contact") as url_client:
        assert url_client.user_agent.endswith("(+https://example.org/contact)")


@pytest.mark.parametrize(
    ("status", "error_type"),
    [(403, HttpPolicyError), (400, HttpRequestError)],
)
def test_http_errors_do_not_leak_keys_from_path_or_query(status, error_type) -> None:
    secret_path = "secret-path-api-key"
    secret_query = "secret-query-service-key"

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, request=request)

    with PoliteHttpClient(min_interval_seconds=0, max_retries=0) as client:
        client._client.close()
        client._client = httpx.Client(transport=httpx.MockTransport(respond))
        with pytest.raises(error_type) as captured:
            client.get(
                f"https://api.example.org/resources/{secret_path}",
                params={"serviceKey": secret_query},
            )

    message = str(captured.value)
    assert "api.example.org" in message
    assert secret_path not in message
    assert secret_query not in message


def test_post_json_sends_form_without_leaking_it_on_error() -> None:
    seen: dict[str, str] = {}

    def respond(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"ok": True}, request=request)

    with PoliteHttpClient(min_interval_seconds=0, max_retries=0) as client:
        client._client.close()
        client._client = httpx.Client(transport=httpx.MockTransport(respond))
        payload = client.post_json(
            "https://api.example.org/public-list",
            data={"page": 1, "category": "children"},
        )

    assert payload == {"ok": True}
    assert seen == {"method": "POST", "body": "page=1&category=children"}


@pytest.mark.parametrize("status", [404, 410])
def test_missing_robots_file_means_no_rules_under_rfc_9309(status: int) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/robots.txt"
        return httpx.Response(status, request=request)

    with PoliteHttpClient(min_interval_seconds=0, max_retries=0) as client:
        client._client.close()
        client._client = httpx.Client(transport=httpx.MockTransport(respond))
        decision = client.robots_decision("https://public.example.org/programs")

    assert decision.allowed is True
    assert f"robots unavailable ({status})" in decision.reason
    assert "RFC 9309" in decision.reason


def test_semantic_robots_404_html_means_no_rules() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<html><title>404 Not Found</title><body>Status:404</body></html>",
            request=request,
        )

    with PoliteHttpClient(min_interval_seconds=0, max_retries=0) as client:
        client._client.close()
        client._client = httpx.Client(transport=httpx.MockTransport(respond))
        decision = client.robots_decision("https://semantic-404.example.org/list")

    assert decision.allowed is True
    assert "semantic 404" in decision.reason


def test_robots_waf_page_and_server_error_still_fail_closed() -> None:
    responses = iter(
        [
            httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text="<html>Access denied by web application firewall</html>",
            ),
            httpx.Response(500),
        ]
    )

    def respond(request: httpx.Request) -> httpx.Response:
        response = next(responses)
        response.request = request
        return response

    with PoliteHttpClient(min_interval_seconds=0, max_retries=0) as client:
        client._client.close()
        client._client = httpx.Client(transport=httpx.MockTransport(respond))
        html_decision = client.robots_decision("https://waf.example.org/list")
        server_decision = client.robots_decision("https://server-error.example.org/list")

    assert html_decision.allowed is False
    assert "HTML/WAF" in html_decision.reason
    assert server_decision.allowed is False
    assert "fail closed" in server_decision.reason


def test_cached_robots_rules_are_evaluated_for_each_path() -> None:
    requested: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        assert request.url.path == "/robots.txt"
        return httpx.Response(
            200,
            text="User-agent: *\nAllow: /public\nDisallow: /private\n",
            request=request,
        )

    with PoliteHttpClient(min_interval_seconds=0, max_retries=0) as client:
        client._client.close()
        client._client = httpx.Client(transport=httpx.MockTransport(respond))
        public = client.robots_decision("https://paths.example.org/public/list")
        private = client.robots_decision("https://paths.example.org/private/data")

    assert public.allowed is True
    assert private.allowed is False
    assert private.reason == "disallowed by robots.txt"
    assert requested == ["/robots.txt"]


def test_cross_origin_redirect_is_blocked_before_target_request() -> None:
    requested: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.host == "source.example.org":
            return httpx.Response(
                302,
                headers={"location": "https://other.example.net/private"},
                request=request,
            )
        raise AssertionError("redirect target must not be requested")

    with PoliteHttpClient(min_interval_seconds=0, max_retries=0) as client:
        client._client.close()
        client._client = httpx.Client(transport=httpx.MockTransport(respond))
        with pytest.raises(HttpPolicyError, match="cross-origin redirect blocked"):
            client.get("https://source.example.org/list")

    assert requested == ["https://source.example.org/list"]


def test_same_origin_redirect_cannot_escape_cached_robots_rules() -> None:
    requested: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nAllow: /public\nDisallow: /private\n",
                request=request,
            )
        if request.url.path == "/public/list":
            return httpx.Response(
                302,
                headers={"location": "/private/data"},
                request=request,
            )
        raise AssertionError("robots-denied redirect target must not be requested")

    with PoliteHttpClient(min_interval_seconds=0, max_retries=0) as client:
        client._client.close()
        client._client = httpx.Client(transport=httpx.MockTransport(respond))
        client.assert_html_allowed("https://same.example.org/public/list")
        with pytest.raises(HttpPolicyError, match="disallowed by robots.txt"):
            client.get("https://same.example.org/public/list")

    assert requested == ["/robots.txt", "/public/list"]
