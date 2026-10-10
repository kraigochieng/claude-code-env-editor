import httpx

from claude_code_env_editor.verify import FAIL, PASS, SKIP, auth_headers, strip_model_suffix, verify

VALUES = {
    "ANTHROPIC_BASE_URL": "https://example.test/anthropic",
    "ANTHROPIC_AUTH_TOKEN": "sk-secret-token",
    "ANTHROPIC_MODEL": "deepseek-flash[1m]",
}


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


def ok_handler(request):
    if request.url.path.endswith("/v1/models"):
        return httpx.Response(200, json={"data": []})
    return httpx.Response(200, json={"model": "deepseek-flash"})


def test_strip_model_suffix():
    assert strip_model_suffix("deepseek-flash[1m]") == "deepseek-flash"
    assert strip_model_suffix("plain") == "plain"


def test_auth_headers_prefer_bearer():
    h = auth_headers({"ANTHROPIC_AUTH_TOKEN": "t", "ANTHROPIC_API_KEY": "k"})
    assert h["authorization"] == "Bearer t" and "x-api-key" not in h


def test_auth_headers_api_key():
    assert auth_headers({"ANTHROPIC_API_KEY": "k"})["x-api-key"] == "k"


def test_all_pass():
    checks = verify(VALUES, client=client(ok_handler))
    assert [c.status for c in checks] == [PASS, PASS, PASS]


def test_model_request_drops_suffix():
    seen = {}

    def handler(request):
        if request.method == "POST":
            seen["body"] = request.read()
        return ok_handler(request)

    verify(VALUES, client=client(handler))
    assert b'"model":"deepseek-flash"' in seen["body"].replace(b" ", b"")


def test_wrong_key_stops_early():
    checks = verify(VALUES, client=client(lambda r: httpx.Response(401)))
    assert checks[-1].name == "key" and checks[-1].status == FAIL
    assert len(checks) == 2


def test_missing_models_route_is_skipped_then_model_checked():
    def handler(request):
        if request.url.path.endswith("/v1/models"):
            return httpx.Response(404)
        return httpx.Response(200, json={"model": "m"})

    checks = verify(VALUES, client=client(handler))
    assert [c.status for c in checks] == [PASS, SKIP, PASS]


def test_bad_model_fails():
    def handler(request):
        if request.method == "POST":
            return httpx.Response(400, text="unknown model")
        return httpx.Response(200)

    assert verify(VALUES, client=client(handler))[-1].status == FAIL


def test_redirect_fails_and_is_not_followed():
    checks = verify(VALUES, client=client(lambda r: httpx.Response(302, headers={"location": "https://evil.test"})))
    assert checks[-1].status == FAIL


def test_no_credentials():
    checks = verify({"ANTHROPIC_BASE_URL": "https://example.test"}, client=client(ok_handler))
    assert checks[-1].name == "credentials" and checks[-1].status == FAIL


def test_invalid_url():
    assert verify({"ANTHROPIC_BASE_URL": "nope"})[0].status == FAIL


def test_error_text_hides_secret():
    def handler(request):
        raise httpx.ConnectError("failed for sk-secret-token")

    checks = verify(VALUES, client=client(handler))
    assert "sk-secret-token" not in checks[-1].detail
