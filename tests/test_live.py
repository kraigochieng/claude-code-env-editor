"""Live tests against real providers. They are skipped unless the key variables are set.

Run them with:
    CCEE_LIVE_DEEPSEEK_KEY=... CCEE_LIVE_OPENROUTER_KEY=... pytest -m live

Each test sends one or two requests with max_tokens=1. CI does not run them.
"""

from __future__ import annotations

import os
from typing import Final

import pytest

from claude_code_env_editor.verify import FAIL, PASS, Check, Endpoint, verify

DEEPSEEK_URL: Final[str] = "https://api.deepseek.com/anthropic"
OPENROUTER_URL: Final[str] = "https://openrouter.ai/api"
DEEPSEEK_KEY: Final[str] = os.environ.get("CCEE_LIVE_DEEPSEEK_KEY", "")
OPENROUTER_KEY: Final[str] = os.environ.get("CCEE_LIVE_OPENROUTER_KEY", "")
DEEPSEEK_MODEL: Final[str] = os.environ.get("CCEE_LIVE_DEEPSEEK_MODEL", "deepseek-flash")
OPENROUTER_MODEL: Final[str] = os.environ.get("CCEE_LIVE_OPENROUTER_MODEL", "deepseek/deepseek-chat")

needs_deepseek = pytest.mark.skipif(not DEEPSEEK_KEY, reason="CCEE_LIVE_DEEPSEEK_KEY is not set")
needs_openrouter = pytest.mark.skipif(not OPENROUTER_KEY, reason="CCEE_LIVE_OPENROUTER_KEY is not set")

pytestmark = pytest.mark.live

NETWORK_DOWN: Final[tuple[str, ...]] = ("Cannot connect to", "No answer from")


def run(base_url: str, key: str, model: str) -> list[Check]:
    """Verify one endpoint with the given key and model."""
    values: dict[str, str] = {
        "ANTHROPIC_BASE_URL": base_url,
        "ANTHROPIC_AUTH_TOKEN": key,
        "ANTHROPIC_MODEL": model,
    }
    checks: list[Check] = verify(endpoint=Endpoint.from_values(values=values))
    if "no-such-host" not in base_url and any(c.detail.startswith(NETWORK_DOWN) for c in checks):
        pytest.skip("The network is not available.")
    return checks


def statuses(checks: list[Check]) -> dict[str, str]:
    """Return {check name: status}."""
    return {c.name: c.status for c in checks}


@needs_deepseek
def test_deepseek_good_model_passes() -> None:
    checks: list[Check] = run(base_url=DEEPSEEK_URL, key=DEEPSEEK_KEY, model=DEEPSEEK_MODEL)
    assert statuses(checks)["model"] == PASS, checks


@needs_deepseek
def test_deepseek_mistyped_model_gives_a_readable_message() -> None:
    checks: list[Check] = run(base_url=DEEPSEEK_URL, key=DEEPSEEK_KEY, model=f"{DEEPSEEK_MODEL}x")
    last: Check = checks[-1]
    assert last.status == FAIL
    assert "does not accept the model" in last.detail
    assert "{" not in last.detail and "request_id" not in last.detail


@needs_deepseek
def test_deepseek_wrong_key_is_rejected() -> None:
    checks: list[Check] = run(base_url=DEEPSEEK_URL, key="sk-wrong-key-for-the-test", model=DEEPSEEK_MODEL)
    assert checks[-1].status == FAIL
    assert "rejects the key" in checks[-1].detail


@needs_openrouter
def test_openrouter_good_model_passes() -> None:
    checks: list[Check] = run(base_url=OPENROUTER_URL, key=OPENROUTER_KEY, model=OPENROUTER_MODEL)
    assert statuses(checks)["model"] == PASS, checks


@needs_openrouter
def test_openrouter_mistyped_model_gives_a_readable_message() -> None:
    checks: list[Check] = run(base_url=OPENROUTER_URL, key=OPENROUTER_KEY, model=f"{OPENROUTER_MODEL}x")
    last: Check = checks[-1]
    assert last.status == FAIL and "does not accept the model" in last.detail
    assert "{" not in last.detail


@needs_openrouter
def test_openrouter_wrong_key_is_caught_even_though_models_are_public() -> None:
    checks: list[Check] = run(base_url=OPENROUTER_URL, key="sk-or-v1-wrong-key-for-the-test", model=OPENROUTER_MODEL)
    assert checks[-1].status == FAIL
    assert "lists models without a key" in checks[-1].detail


def test_unreachable_host_gives_a_readable_message() -> None:
    checks: list[Check] = run(base_url="https://no-such-host.invalid", key="x", model="m")
    assert checks[-1].status == FAIL
    assert "Cannot connect to no-such-host.invalid" in checks[-1].detail
