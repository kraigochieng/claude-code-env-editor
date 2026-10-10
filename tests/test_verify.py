from collections.abc import Callable
from typing import Final

import httpx

from claude_code_env_editor.verify import (
    FAIL,
    PASS,
    SKIP,
    Check,
    Endpoint,
    strip_model_suffix,
    verify,
)

VALUES: Final[dict[str, str]] = {
    "ANTHROPIC_BASE_URL": "https://example.test/anthropic",
    "ANTHROPIC_AUTH_TOKEN": "sk-secret-token",
    "ANTHROPIC_MODEL": "deepseek-flash[1m]",
}


def client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


def ok_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/v1/models"):
        return httpx.Response(200, json={"data": []})
    return httpx.Response(200, json={"model": "deepseek-flash"})


def test_strip_model_suffix() -> None:
    assert strip_model_suffix(model="deepseek-flash[1m]") == "deepseek-flash"
    assert strip_model_suffix(model="plain") == "plain"


def test_auth_headers_prefer_bearer() -> None:
    h: dict[str, str] = Endpoint.from_values(values={"ANTHROPIC_AUTH_TOKEN": "t", "ANTHROPIC_API_KEY": "k"}).headers
    assert h["authorization"] == "Bearer t" and "x-api-key" not in h


def test_auth_headers_api_key() -> None:
    assert Endpoint.from_values(values={"ANTHROPIC_API_KEY": "k"}).headers["x-api-key"] == "k"


def test_all_pass() -> None:
    checks: list[Check] = verify(endpoint=Endpoint.from_values(values=VALUES), client=client(ok_handler))
    assert [c.status for c in checks] == [PASS, PASS, PASS]


def test_model_request_drops_suffix() -> None:
    seen: dict[str, bytes] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            seen["body"] = request.read()
        return ok_handler(request)

    verify(endpoint=Endpoint.from_values(values=VALUES), client=client(handler))
    assert b'"model":"deepseek-flash"' in seen["body"].replace(b" ", b"")


def test_wrong_key_stops_early() -> None:
    checks: list[Check] = verify(endpoint=Endpoint.from_values(values=VALUES), client=client(lambda r: httpx.Response(401)))
    assert checks[-1].name == "key" and checks[-1].status == FAIL
    assert len(checks) == 2


def test_missing_models_route_is_skipped_then_model_checked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/v1/models"):
            return httpx.Response(404)
        return httpx.Response(200, json={"model": "m"})

    checks: list[Check] = verify(endpoint=Endpoint.from_values(values=VALUES), client=client(handler))
    assert [c.status for c in checks] == [PASS, SKIP, PASS]


def test_bad_model_fails() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(400, text="unknown model")
        return httpx.Response(200)

    assert verify(endpoint=Endpoint.from_values(values=VALUES), client=client(handler))[-1].status == FAIL


def test_redirect_fails_and_is_not_followed() -> None:
    checks: list[Check] = verify(endpoint=Endpoint.from_values(values=VALUES), client=client(lambda r: httpx.Response(302, headers={"location": "https://evil.test"})))
    assert checks[-1].status == FAIL


def test_no_credentials() -> None:
    checks: list[Check] = verify(endpoint=Endpoint.from_values(values={"ANTHROPIC_BASE_URL": "https://example.test"}), client=client(ok_handler))
    assert checks[-1].name == "credentials" and checks[-1].status == FAIL


def test_invalid_url() -> None:
    assert verify(endpoint=Endpoint.from_values(values={"ANTHROPIC_BASE_URL": "nope"}))[0].status == FAIL


def test_error_text_hides_secret() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("failed for sk-secret-token")

    checks: list[Check] = verify(endpoint=Endpoint.from_values(values=VALUES), client=client(handler))
    assert "sk-secret-token" not in checks[-1].detail


def test_endpoint_defaults_and_host() -> None:
    endpoint: Endpoint = Endpoint.from_values(values={})
    assert endpoint.host == "api.anthropic.com" and not endpoint.has_credentials


def test_endpoint_model_falls_back_to_sonnet_alias() -> None:
    assert Endpoint.from_values(values={"ANTHROPIC_DEFAULT_SONNET_MODEL": "s"}).model == "s"
