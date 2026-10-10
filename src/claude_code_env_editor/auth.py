"""Decide which secret variable fits a base URL, and which rows to show."""

from __future__ import annotations

from urllib.parse import urlparse

from claude_code_env_editor.authkind import HEADER_OF, VARIABLE_OF, AuthKind
from claude_code_env_editor.envvars import SOURCE_UNSET, Row
from claude_code_env_editor.presets import Preset, load_presets

DEFAULT_PRESET: str = "anthropic"


def _netloc(url: str) -> str:
    """Return host and port of a URL, in lower case."""
    return urlparse(url=url).netloc.lower()


def expected_auth(base_url: str) -> AuthKind | None:
    """Return the secret variable kind that the endpoint of base_url expects.

    An empty URL means the Anthropic API. An endpoint that no preset names gives None.
    """
    presets: dict[str, Preset] = load_presets()
    target: str = _netloc(url=base_url) if base_url else _netloc(url=presets[DEFAULT_PRESET].base_url)
    for preset in presets.values():
        if _netloc(url=preset.base_url) == target:
            return preset.auth
    return None


def visible_rows(rows: list[Row]) -> list[Row]:
    """Hide the secret variable that the endpoint does not use, when it has no value.

    A variable that is set stays visible, so the user can see it. With an unknown endpoint, all rows stay.
    """
    base_url: str = next((r.value for r in rows if r.name == "ANTHROPIC_BASE_URL"), "")
    kind: AuthKind | None = expected_auth(base_url=base_url)
    if kind is None:
        return rows
    unused: set[str] = {name for other, name in VARIABLE_OF.items() if other != kind}
    return [r for r in rows if not (r.name in unused and r.source == SOURCE_UNSET)]


def describe(rows: list[Row]) -> str:
    """Return one line for the banner: the expected variable and header, or a warning."""
    base_url: str = next((r.value for r in rows if r.name == "ANTHROPIC_BASE_URL"), "")
    kind: AuthKind | None = expected_auth(base_url=base_url)
    if kind is None:
        return "unknown endpoint: set the variable your provider documents"
    text: str = f"{VARIABLE_OF[kind]} ({HEADER_OF[kind]})"
    if kind == "api_key" and not base_url:
        text += ", or your Claude login"
    unused: list[str] = [
        r.name for r in rows if r.name in VARIABLE_OF.values() and r.name != VARIABLE_OF[kind] and r.value
    ]
    if unused:
        text += f"  [warning: {', '.join(unused)} is set but not expected here]"
    return text
