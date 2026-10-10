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


def test_auth_headers_send_both_when_both_are_set() -> None:
    h: dict[str, str] = Endpoint.from_values(values={"ANTHROPIC_AUTH_TOKEN": "t", "ANTHROPIC_API_KEY": "k"}).headers
    assert h["authorization"] == "Bearer t" and h["x-api-key"] == "k"


def test_auth_headers_bearer_only() -> None:
    h: dict[str, str] = Endpoint.from_values(values={"ANTHROPIC_AUTH_TOKEN": "t"}).headers
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


def no_key_handler(request: httpx.Request) -> httpx.Response:
    """Answer 200 only when the request carries no key."""
    if "authorization" in request.headers or "x-api-key" in request.headers:
        return httpx.Response(400)
    return httpx.Response(200, json={"model": "m", "data": []})


def test_no_key_on_anthropic_api_is_skipped_not_failed() -> None:
    checks: list[Check] = verify(Endpoint.from_values({}), client=client(ok_handler), login_found=True)
    assert [c.status for c in checks] == [PASS, SKIP]
    assert "A login was found." in checks[-1].detail


def test_no_key_and_no_login_on_anthropic_api_is_skipped_with_note() -> None:
    checks: list[Check] = verify(Endpoint.from_values({}), client=client(ok_handler), login_found=False)
    assert checks[-1].status == SKIP and "No login was found" in checks[-1].detail


def test_no_key_on_remote_custom_endpoint_fails() -> None:
    values: dict[str, str] = {"ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic"}
    checks: list[Check] = verify(Endpoint.from_values(values), client=client(ok_handler), login_found=True)
    assert checks[-1].name == "credentials" and checks[-1].status == FAIL


def test_no_key_on_local_endpoint_sends_request_without_key() -> None:
    values: dict[str, str] = {"ANTHROPIC_BASE_URL": "http://localhost:11434", "ANTHROPIC_MODEL": "llama"}
    checks: list[Check] = verify(Endpoint.from_values(values), client=client(no_key_handler))
    assert [c.status for c in checks] == [PASS, PASS, PASS]


def test_endpoint_kind_properties() -> None:
    assert Endpoint.from_values({}).is_anthropic
    assert Endpoint.from_values({"ANTHROPIC_BASE_URL": "http://127.0.0.1:4000"}).is_local
    assert not Endpoint.from_values({"ANTHROPIC_BASE_URL": "https://openrouter.ai/api"}).is_local
