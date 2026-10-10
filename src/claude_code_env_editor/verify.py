"""Check an endpoint, a key, and a model with real requests."""

from __future__ import annotations

import re
import time
from typing import Literal, Mapping
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict

ANTHROPIC_VERSION = "2023-06-01"
PASS, FAIL, SKIP = "pass", "fail", "skip"
_SUFFIX = re.compile(r"\[[^\]]*\]$")


class Check(BaseModel):
    """The result of one check: its name, pass/fail/skip, and a detail text."""
    model_config = ConfigDict(frozen=True)

    name: str
    status: Literal["pass", "fail", "skip"]
    detail: str = ""


DEFAULT_BASE_URL = "https://api.anthropic.com"
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")


class Endpoint(BaseModel):
    """The endpoint to test: URL, credentials, and the model name."""

    model_config = ConfigDict(frozen=True)

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
    def has_credentials(self) -> bool:
        """Return True when a token or a key is set."""
        return bool(self.auth_token or self.api_key)

    @property
    def headers(self) -> dict[str, str]:
        """Build the request headers. A bearer token wins over an API key."""
        headers = {"anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json"}
        if self.auth_token:
            headers["authorization"] = f"Bearer {self.auth_token}"
        elif self.api_key:
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


def verify(
    endpoint: Endpoint,
    client: httpx.Client | None = None,
    timeout: float = 20.0,
) -> list[Check]:
    """Run the checks in order. Stop after a failure that makes later checks useless.

    The request goes only to the endpoint URL. The client never follows a redirect.
    """
    parsed = urlparse(url=endpoint.base_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return [Check(name="url", status=FAIL, detail=f"'{endpoint.base_url}' is not a valid http or https URL.")]
    detail = parsed.netloc
    if parsed.scheme == "http" and parsed.hostname not in LOCAL_HOSTS:
        detail += " (warning: http sends the key without encryption)"
    checks = [Check(name="url", status=PASS, detail=detail)]

    if not endpoint.has_credentials:
        checks.append(Check(name="credentials", status=FAIL, detail="Set ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY."))
        return checks

    own_client = client is None
    client = client or httpx.Client(timeout=timeout, follow_redirects=False)
    try:
        checks.append(_check_models(client=client, endpoint=endpoint))
        if checks[-1].status == FAIL:
            return checks
        if not endpoint.model:
            checks.append(Check(name="model", status=SKIP, detail="Set ANTHROPIC_MODEL to test the model name."))
        else:
            checks.append(_check_message(client=client, endpoint=endpoint))
    finally:
        if own_client:
            client.close()
    return checks


def _check_models(client: httpx.Client, endpoint: Endpoint) -> Check:
    """Check the key with GET /v1/models."""
    start = time.perf_counter()
    try:
        resp = client.get(url=f"{endpoint.base_url}/v1/models", headers=endpoint.headers)
    except httpx.HTTPError as exc:
        return Check(name="key", status=FAIL, detail=endpoint.redact(text=f"{type(exc).__name__}: {exc}"))
    ms = int((time.perf_counter() - start) * 1000)
    if resp.status_code in (401, 403):
        return Check(name="key", status=FAIL, detail=f"HTTP {resp.status_code}: the endpoint rejects the key.")
    if resp.status_code in (404, 405):
        return Check(name="key", status=SKIP, detail=f"HTTP {resp.status_code}: the endpoint has no /v1/models route.")
    if 300 <= resp.status_code < 400:
        return Check(
            name="key",
            status=FAIL,
            detail=f"HTTP {resp.status_code}: the endpoint redirects. The tool does not follow redirects.",
        )
    if resp.status_code >= 400:
        return Check(name="key", status=FAIL, detail=f"HTTP {resp.status_code}")
    return Check(name="key", status=PASS, detail=f"HTTP {resp.status_code} in {ms} ms")


def _check_message(client: httpx.Client, endpoint: Endpoint) -> Check:
    """Check the model name with a one-token POST /v1/messages."""
    body = {
        "model": strip_model_suffix(model=endpoint.model),
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "hi"}],
    }
    start = time.perf_counter()
    try:
        resp = client.post(url=f"{endpoint.base_url}/v1/messages", headers=endpoint.headers, json=body)
    except httpx.HTTPError as exc:
        return Check(name="model", status=FAIL, detail=endpoint.redact(text=f"{type(exc).__name__}: {exc}"))
    ms = int((time.perf_counter() - start) * 1000)
    if resp.status_code in (401, 403):
        return Check(name="model", status=FAIL, detail=f"HTTP {resp.status_code}: the endpoint rejects the key.")
    if resp.status_code >= 400:
        return Check(name="model", status=FAIL, detail=endpoint.redact(text=f"HTTP {resp.status_code}: {resp.text[:200]}"))
    try:
        name = resp.json().get("model", body["model"])
    except ValueError:
        name = body["model"]
    return Check(name="model", status=PASS, detail=f"{name} answered in {ms} ms")
