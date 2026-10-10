"""Catalog of the variables the tool handles, with masking and source lookup."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

STRING, URL, SECRET, INTEGER, CHOICE = "string", "url", "secret", "integer", "choice"


@dataclass(frozen=True)
class VarSpec:
    name: str
    kind: str
    help: str
    example: str = ""
    choices: tuple[str, ...] = ()
    writable: bool = True

    @property
    def secret(self) -> bool:
        return self.kind == SECRET


CATALOG: tuple[VarSpec, ...] = (
    VarSpec("ANTHROPIC_BASE_URL", URL, "Endpoint that Claude Code calls.", "https://api.deepseek.com/anthropic"),
    VarSpec("ANTHROPIC_AUTH_TOKEN", SECRET, "Bearer token for the endpoint.", "sk-..."),
    VarSpec("ANTHROPIC_API_KEY", SECRET, "API key sent in the x-api-key header.", "sk-ant-..."),
    VarSpec("ANTHROPIC_MODEL", STRING, "Main model name.", "deepseek-flash[1m]"),
    VarSpec("ANTHROPIC_DEFAULT_OPUS_MODEL", STRING, "Model that the opus alias uses.", "deepseek-flash[1m]"),
    VarSpec("ANTHROPIC_DEFAULT_SONNET_MODEL", STRING, "Model that the sonnet alias uses.", "deepseek-flash[1m]"),
    VarSpec("ANTHROPIC_DEFAULT_HAIKU_MODEL", STRING, "Model that the haiku alias uses.", "deepseek-flash"),
    VarSpec("CLAUDE_CODE_SUBAGENT_MODEL", STRING, "Model that subagents use.", "deepseek-flash"),
    VarSpec("CLAUDE_CODE_EFFORT_LEVEL", STRING, "Effort level for the model.", "max"),
    VarSpec("CLAUDE_CODE_AUTO_COMPACT_WINDOW", INTEGER, "Context size at which Claude Code compacts.", "786432"),
    VarSpec("ANTHROPIC_SMALL_FAST_MODEL", STRING, "Older name for the fast model. Kept for compatibility.", "deepseek-flash"),
    VarSpec("API_TIMEOUT_MS", INTEGER, "Request timeout in milliseconds.", "600000"),
    VarSpec(
        "CLAUDE_CONFIG_DIR",
        STRING,
        "Config directory of one Claude Code login. Not written to settings.json.",
        "~/.claude-work",
        writable=False,
    ),
)

BY_NAME: dict[str, VarSpec] = {v.name: v for v in CATALOG}
CUSTOM_PREFIXES = ("ANTHROPIC_", "CLAUDE_CODE_")

SOURCE_ENV, SOURCE_SETTINGS, SOURCE_UNSET = "env", "settings", "unset"


def mask(value: str, secret: bool = True) -> str:
    """Hide a secret. Keep the first 4 and last 4 characters of a long value."""
    if not secret or not value:
        return value
    if len(value) <= 12:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def validate(spec: VarSpec, value: str) -> str | None:
    """Return an error text for a bad value, or None when the value is good."""
    if spec.kind == INTEGER and not value.strip().isdigit():
        return f"{spec.name} must be a whole number."
    if spec.kind == URL and not value.startswith(("http://", "https://")):
        return f"{spec.name} must start with http:// or https://."
    if spec.kind == CHOICE and spec.choices and value not in spec.choices:
        return f"{spec.name} must be one of: {', '.join(spec.choices)}."
    return None


@dataclass(frozen=True)
class Row:
    name: str
    value: str
    source: str
    spec: VarSpec | None  # None for a custom variable

    @property
    def secret(self) -> bool:
        return bool(self.spec and self.spec.secret)

    @property
    def display(self) -> str:
        return mask(self.value, self.secret) if self.value else ""


def resolve(settings_env: Mapping[str, str], environ: Mapping[str, str]) -> list[Row]:
    """List every known variable with its value and source.

    The process environment wins over the settings.json env block.
    Unknown ANTHROPIC_* and CLAUDE_CODE_* keys in settings.json show as custom rows.
    """
    rows: list[Row] = []
    for spec in CATALOG:
        if spec.name in environ:
            rows.append(Row(spec.name, environ[spec.name], SOURCE_ENV, spec))
        elif spec.name in settings_env:
            rows.append(Row(spec.name, str(settings_env[spec.name]), SOURCE_SETTINGS, spec))
        else:
            rows.append(Row(spec.name, "", SOURCE_UNSET, spec))
    for name, value in settings_env.items():
        if name not in BY_NAME and name.startswith(CUSTOM_PREFIXES):
            rows.append(Row(name, str(value), SOURCE_SETTINGS, None))
    return rows
