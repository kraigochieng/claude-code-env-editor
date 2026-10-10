"""Check an endpoint, a key, and a model with real requests."""

from __future__ import annotations

import difflib
import re
import time
from typing import ClassVar, Final, Literal, Mapping
from urllib.parse import ParseResult, urlparse

import httpx
from pydantic import BaseModel, ConfigDict

ANTHROPIC_VERSION: Final[str] = "2023-06-01"
PASS: Final = "pass"
FAIL: Final = "fail"
SKIP: Final = "skip"
_SUFFIX: Final[re.Pattern[str]] = re.compile(r"\[[^\]]*\]$")


class Check(BaseModel):
    """The result of one check: its name, pass/fail/skip, and a detail text."""
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    name: str
    status: Literal["pass", "fail", "skip"]
    detail: str = ""


DEFAULT_BASE_URL: Final[str] = "https://api.anthropic.com"
LOCAL_HOSTS: Final[tuple[str, str, str]] = ("localhost", "127.0.0.1", "::1")


class Endpoint(BaseModel):
    """The endpoint to test: URL, credentials, and the model name."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    base_url: str = DEFAULT_BASE_URL
    auth_token: str = ""
    api_key: str = ""
    model: str = ""

    @classmethod
    def from_values(cls, values: Mapping[str, str]) -> "Endpoint":
        """Build an endpoint from the variable values {name: value}."""
        return cls(
            base_url=(values.get("ANTHROPIC_BASE_URL") or DEFAULT_BASE_URL).rstrip("/"),
            auth_token=values.get("ANTHROPIC_AUTH_TOKEN", ""),
            api_key=values.get("ANTHROPIC_API_KEY", ""),
            model=values.get("ANTHROPIC_MODEL") or values.get("ANTHROPIC_DEFAULT_SONNET_MODEL") or "",
        )

    @property
    def host(self) -> str:
        """Return the host that the requests go to."""
        return urlparse(url=self.base_url).netloc

    @property
    def is_anthropic(self) -> bool:
        """Return True when the endpoint is the Anthropic API, where a Claude login works."""
        return self.host == urlparse(url=DEFAULT_BASE_URL).netloc

    @property
    def is_local(self) -> bool:
        """Return True when the endpoint runs on this machine."""
        return urlparse(url=self.base_url).hostname in LOCAL_HOSTS

    @property
    def has_credentials(self) -> bool:
        """Return True when a token or a key is set."""
        return bool(self.auth_token or self.api_key)

    @property
    def headers(self) -> dict[str, str]:
        """Build the request headers. Claude Code sends both headers when both variables are set."""
        headers: dict[str, str] = {"anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json"}
        if self.auth_token:
            headers["authorization"] = f"Bearer {self.auth_token}"
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def redact(self, text: str) -> str:
        """Replace any secret of this endpoint in a text with ***."""
        for secret in (self.auth_token, self.api_key):
            if secret:
                text = text.replace(secret, "***")
        return text


def strip_model_suffix(model: str) -> str:
    """Remove a Claude Code suffix such as [1m] before the model goes to the endpoint."""
    return _SUFFIX.sub(repl="", string=model)


_REQUEST_ID: re.Pattern[str] = re.compile(r"\s*\(request_id: [^)]*\)")
_MAX_MESSAGE: Final[int] = 300


class ModelList(BaseModel):
    """The result of the models check and the model ids the endpoint listed, if any."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    check: Check
    ids: list[str] = []
    listed_without_key: bool = False


def verify(
    endpoint: Endpoint,
    client: httpx.Client | None = None,
    timeout: float = 20.0,
    login_found: bool = False,
) -> list[Check]:
    """Run the checks in order. Stop after a failure that makes later checks useless.

    The request goes only to the endpoint URL. The client never follows a redirect.
    Without a key, the result depends on the endpoint: the Anthropic API uses the Claude login
    (skip), a local endpoint gets an unauthenticated request, and any other endpoint fails.
    """
    parsed: ParseResult = urlparse(url=endpoint.base_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return [Check(name="url", status=FAIL, detail=f"'{endpoint.base_url}' is not a valid http or https URL.")]
    detail: str = parsed.netloc
    if parsed.scheme == "http" and parsed.hostname not in LOCAL_HOSTS:
        detail += " (warning: http sends the key without encryption)"
    checks: list[Check] = [Check(name="url", status=PASS, detail=detail)]

    if not endpoint.has_credentials and not endpoint.is_local:
        if endpoint.is_anthropic:
            login: str = "A login was found." if login_found else "No login was found in this config directory."
            detail_text: str = f"No key set. Claude Code uses your Claude login. {login} This tool cannot test the login."
            checks.append(Check(name="credentials", status=SKIP, detail=detail_text))
            return checks
        checks.append(
            Check(
                name="credentials",
                status=FAIL,
                detail="This endpoint needs a key. A Claude login works only with the Anthropic API. "
                "Set ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY.",
            )
        )
        return checks

    own_client: bool = client is None
    http_client: httpx.Client = client or httpx.Client(timeout=timeout, follow_redirects=False)
    try:
        models: ModelList = _check_models(client=http_client, endpoint=endpoint, timeout=timeout)
        checks.append(models.check)
        if models.check.status == FAIL:
            return checks
        if not endpoint.model:
            checks.append(
                Check(
                    name="model",
                    status=SKIP,
                    detail="Set ANTHROPIC_MODEL to test the model name. "
                    "The key is not proven until a model request succeeds.",
                )
            )
        else:
            checks.append(_check_message(client=http_client, endpoint=endpoint, models=models, timeout=timeout))
    finally:
        if own_client:
            http_client.close()
    return checks


def provider_message(resp: httpx.Response, endpoint: Endpoint) -> str:
    """Return the error message from a JSON error body, or the start of the text. Secrets are removed."""
    message: str = ""
    try:
        data: object = resp.json()
    except ValueError:
        data = None
    if isinstance(data, dict):
        error: object = data.get("error")
        if isinstance(error, dict):
            message = str(error.get("message", ""))
        elif isinstance(error, str):
            message = error
        else:
            message = str(data.get("message") or data.get("detail") or "")
    if not message:
        message = resp.text
    message = _REQUEST_ID.sub(repl="", string=" ".join(message.split()))
    return endpoint.redact(text=message[:_MAX_MESSAGE])


def describe_exception(exc: httpx.HTTPError, endpoint: Endpoint, timeout: float) -> str:
    """Return a plain explanation of a network error."""
    if isinstance(exc, httpx.TimeoutException):
        return f"No answer from {endpoint.host} within {timeout:.0f} seconds. The endpoint may be slow or down."
    if isinstance(exc, httpx.ConnectError):
        return f"Cannot connect to {endpoint.host}. Check the base URL and your network."
    return endpoint.redact(text=f"{type(exc).__name__}: {exc}")


def suggest_models(model: str, ids: list[str]) -> str:
    """Return ' Did you mean: a, b?' for the listed ids closest to model, or an empty text."""
    close: list[str] = difflib.get_close_matches(word=model, possibilities=ids, n=3, cutoff=0.6)
    return f" Did you mean: {', '.join(close)}?" if close else ""


def _model_ids(resp: httpx.Response) -> list[str]:
    """Read the model ids from a /v1/models answer. Return an empty list when the shape is unknown."""
    try:
        data: object = resp.json()
    except ValueError:
        return []
    items: object = data.get("data") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    return [str(item["id"]) for item in items if isinstance(item, dict) and "id" in item]


def _check_models(client: httpx.Client, endpoint: Endpoint, timeout: float) -> ModelList:
    """Reach GET /v1/models. This proves the key only on endpoints that protect the list."""
    start: float = time.perf_counter()
    try:
        resp: httpx.Response = client.get(url=f"{endpoint.base_url}/v1/models", headers=endpoint.headers)
    except httpx.HTTPError as exc:
        return ModelList(check=Check(name="key", status=FAIL, detail=describe_exception(exc=exc, endpoint=endpoint, timeout=timeout)))
    ms: int = int((time.perf_counter() - start) * 1000)
    code: int = resp.status_code
    if code in (401, 403):
        return ModelList(
            check=Check(
                name="key",
                status=FAIL,
                detail=f"HTTP {code}: the endpoint rejects the key. {provider_message(resp=resp, endpoint=endpoint)}".strip(),
            )
        )
    if code in (404, 405):
        return ModelList(
            check=Check(name="key", status=SKIP, detail=f"HTTP {code}: the endpoint has no /v1/models route.")
        )
    if 300 <= code < 400:
        return ModelList(
            check=Check(
                name="key",
                status=FAIL,
                detail=f"HTTP {code}: the endpoint redirects. The tool does not follow redirects.",
            )
        )
    if code >= 400:
        return ModelList(check=Check(name="key", status=FAIL, detail=_explain_status(code=code, resp=resp, endpoint=endpoint)))
    ids: list[str] = _model_ids(resp=resp)
    count: str = f", {len(ids)} models listed" if ids else ""
    return ModelList(
        check=Check(name="key", status=PASS, detail=f"HTTP {code} in {ms} ms{count}"),
        ids=ids,
        listed_without_key=True,
    )


def _explain_status(code: int, resp: httpx.Response, endpoint: Endpoint) -> str:
    """Explain an HTTP error status in plain words and add the provider message."""
    reason: str
    if code in (401, 403):
        reason = "the endpoint rejects the key"
    elif code == 402:
        reason = "the account has no credit or needs a payment"
    elif code == 429:
        reason = "the rate limit or the quota is reached. Wait and try again, or check your plan"
    elif code >= 500:
        reason = "the endpoint has a problem. Try again later"
    else:
        reason = "the endpoint refuses the request"
    return f"HTTP {code}: {reason}. {provider_message(resp=resp, endpoint=endpoint)}".strip()


def _check_message(client: httpx.Client, endpoint: Endpoint, models: ModelList, timeout: float) -> Check:
    """Check the key and the model name with a one-token POST /v1/messages."""
    requested_model: str = strip_model_suffix(model=endpoint.model)
    body: dict[str, object] = {
        "model": requested_model,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "hi"}],
    }
    start: float = time.perf_counter()
    try:
        resp: httpx.Response = client.post(url=f"{endpoint.base_url}/v1/messages", headers=endpoint.headers, json=body)
    except httpx.HTTPError as exc:
        return Check(name="model", status=FAIL, detail=describe_exception(exc=exc, endpoint=endpoint, timeout=timeout))
    ms: int = int((time.perf_counter() - start) * 1000)
    code: int = resp.status_code
    if code in (401, 403):
        note: str = " This endpoint lists models without a key, so only this request proves the key." if models.listed_without_key else ""
        return Check(name="model", status=FAIL, detail=f"{_explain_status(code=code, resp=resp, endpoint=endpoint)}{note}")
    if code in (400, 404, 422):
        hint: str = suggest_models(model=requested_model, ids=models.ids)
        sent: str = f" (sent as '{requested_model}')" if requested_model != endpoint.model else ""
        return Check(
            name="model",
            status=FAIL,
            detail=f"HTTP {code}: the endpoint does not accept the model '{endpoint.model}'{sent}. "
            f"{provider_message(resp=resp, endpoint=endpoint)}{hint}".strip(),
        )
    if code >= 400:
        return Check(name="model", status=FAIL, detail=_explain_status(code=code, resp=resp, endpoint=endpoint))
    try:
        name: str = str(resp.json().get("model", requested_model))
    except ValueError:
        name = requested_model
    sent_note: str = f" (sent as '{requested_model}')" if requested_model != endpoint.model else ""
    return Check(name="model", status=PASS, detail=f"{name} answered in {ms} ms{sent_note}")
