"""Check an endpoint, a key, and a model with real requests."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse

import httpx

ANTHROPIC_VERSION = "2023-06-01"
PASS, FAIL, SKIP = "pass", "fail", "skip"
_SUFFIX = re.compile(r"\[[^\]]*\]$")


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str = ""


def strip_model_suffix(model: str) -> str:
    """Remove a Claude Code suffix such as [1m] before the model goes to the endpoint."""
    return _SUFFIX.sub("", model)


def auth_headers(values: Mapping[str, str]) -> dict[str, str]:
    headers = {"anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json"}
    if values.get("ANTHROPIC_AUTH_TOKEN"):
        headers["authorization"] = f"Bearer {values['ANTHROPIC_AUTH_TOKEN']}"
    elif values.get("ANTHROPIC_API_KEY"):
        headers["x-api-key"] = values["ANTHROPIC_API_KEY"]
    return headers


def target_host(values: Mapping[str, str]) -> str:
    return urlparse(values.get("ANTHROPIC_BASE_URL") or "https://api.anthropic.com").netloc


def _redact(text: str, values: Mapping[str, str]) -> str:
    for key in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY"):
        if values.get(key):
            text = text.replace(values[key], "***")
    return text


def verify(
    values: Mapping[str, str],
    client: httpx.Client | None = None,
    timeout: float = 20.0,
) -> list[Check]:
    """Run the checks in order. Stop after a failure that makes later checks useless.

    The request goes only to ANTHROPIC_BASE_URL. The client never follows a redirect.
    """
    base = (values.get("ANTHROPIC_BASE_URL") or "https://api.anthropic.com").rstrip("/")
    checks: list[Check] = []
    parsed = urlparse(base)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return [Check("url", FAIL, f"'{base}' is not a valid http or https URL.")]
    detail = parsed.netloc
    if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
        detail += " (warning: http sends the key without encryption)"
    checks.append(Check("url", PASS, detail))

    headers = auth_headers(values)
    if len(headers) == 2:
        checks.append(Check("credentials", FAIL, "Set ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY."))
        return checks

    own = client is None
    client = client or httpx.Client(timeout=timeout, follow_redirects=False)
    try:
        checks.append(_check_models(client, base, headers, values))
        if checks[-1].status == FAIL:
            return checks
        model = values.get("ANTHROPIC_MODEL") or values.get("ANTHROPIC_DEFAULT_SONNET_MODEL")
        if not model:
            checks.append(Check("model", SKIP, "Set ANTHROPIC_MODEL to test the model name."))
        else:
            checks.append(_check_message(client, base, headers, model, values))
    finally:
        if own:
            client.close()
    return checks


def _check_models(client, base, headers, values) -> Check:
    start = time.perf_counter()
    try:
        resp = client.get(f"{base}/v1/models", headers=headers)
    except httpx.HTTPError as exc:
        return Check("key", FAIL, _redact(f"{type(exc).__name__}: {exc}", values))
    ms = int((time.perf_counter() - start) * 1000)
    if resp.status_code in (401, 403):
        return Check("key", FAIL, f"HTTP {resp.status_code}: the endpoint rejects the key.")
    if resp.status_code in (404, 405):
        return Check("key", SKIP, f"HTTP {resp.status_code}: the endpoint has no /v1/models route.")
    if 300 <= resp.status_code < 400:
        return Check("key", FAIL, f"HTTP {resp.status_code}: the endpoint redirects. The tool does not follow redirects.")
    if resp.status_code >= 400:
        return Check("key", FAIL, f"HTTP {resp.status_code}")
    return Check("key", PASS, f"HTTP {resp.status_code} in {ms} ms")


def _check_message(client, base, headers, model, values) -> Check:
    body = {
        "model": strip_model_suffix(model),
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "hi"}],
    }
    start = time.perf_counter()
    try:
        resp = client.post(f"{base}/v1/messages", headers=headers, json=body)
    except httpx.HTTPError as exc:
        return Check("model", FAIL, _redact(f"{type(exc).__name__}: {exc}", values))
    ms = int((time.perf_counter() - start) * 1000)
    if resp.status_code in (401, 403):
        return Check("model", FAIL, f"HTTP {resp.status_code}: the endpoint rejects the key.")
    if resp.status_code >= 400:
        return Check("model", FAIL, _redact(f"HTTP {resp.status_code}: {resp.text[:200]}", values))
    try:
        name = resp.json().get("model", body["model"])
    except ValueError:
        name = body["model"]
    return Check("model", PASS, f"{name} answered in {ms} ms")
