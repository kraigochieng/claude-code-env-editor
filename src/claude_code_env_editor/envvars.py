"""Catalog of the variables the tool handles, with masking and source lookup."""

from __future__ import annotations

from typing import ClassVar, Final, Literal, Mapping, TypeAlias

from pydantic import BaseModel, ConfigDict

VarKind: TypeAlias = Literal["string", "url", "secret", "integer", "choice"]
Source: TypeAlias = Literal["env", "settings", "unset"]

STRING: Final = "string"
URL: Final = "url"
SECRET: Final = "secret"
INTEGER: Final = "integer"
CHOICE: Final = "choice"


class VarSpec(BaseModel):
    """The definition of one variable: name, type, help text, and an example value."""
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    name: str
    kind: VarKind
    help: str
    example: str = ""
    choices: tuple[str, ...] = ()
    minimum: int | None = None
    maximum: int | None = None
    writable: bool = True

    @property
    def secret(self) -> bool:
        """Return True when the value must be masked on screen."""
        return self.kind == SECRET


CATALOG: tuple[VarSpec, ...] = (
    VarSpec(name="ANTHROPIC_BASE_URL", kind=URL, help="Endpoint that Claude Code calls.", example="https://api.deepseek.com/anthropic"),
    VarSpec(name="ANTHROPIC_AUTH_TOKEN", kind=SECRET, help="Bearer token for the endpoint.", example="sk-..."),
    VarSpec(name="ANTHROPIC_API_KEY", kind=SECRET, help="API key sent in the x-api-key header.", example="sk-ant-..."),
    VarSpec(name="ANTHROPIC_MODEL", kind=STRING, help="Main model name.", example="deepseek-flash[1m]"),
    VarSpec(name="ANTHROPIC_DEFAULT_OPUS_MODEL", kind=STRING, help="Model that the opus alias uses.", example="deepseek-flash[1m]"),
    VarSpec(name="ANTHROPIC_DEFAULT_SONNET_MODEL", kind=STRING, help="Model that the sonnet alias uses.", example="deepseek-flash[1m]"),
    VarSpec(name="ANTHROPIC_DEFAULT_HAIKU_MODEL", kind=STRING, help="Model that the haiku alias uses.", example="deepseek-flash"),
    VarSpec(name="CLAUDE_CODE_SUBAGENT_MODEL", kind=STRING, help="Model that subagents use.", example="deepseek-flash"),
    VarSpec(
        name="CLAUDE_CODE_EFFORT_LEVEL",
        kind=CHOICE,
        help="Effort level for the model. Available levels depend on the model. auto uses the model default.",
        example="max",
        choices=("low", "medium", "high", "xhigh", "max", "auto"),
    ),
    VarSpec(
        name="CLAUDE_CODE_AUTO_COMPACT_WINDOW",
        kind=INTEGER,
        help="Context size in tokens at which Claude Code compacts. A plain integer, not 500k.",
        example="786432",
        minimum=100000,
        maximum=1000000,
    ),
    VarSpec(name="ANTHROPIC_SMALL_FAST_MODEL", kind=STRING, help="Older name for the fast model. Kept for compatibility.", example="deepseek-flash"),
    VarSpec(name="API_TIMEOUT_MS", kind=INTEGER, help="Request timeout in milliseconds.", example="600000"),
    VarSpec(name="CLAUDE_CONFIG_DIR", kind=STRING, help="Config directory of one Claude Code login. Not written to settings.json.", example="~/.claude-work",
        writable=False,
    ),
)

BY_NAME: dict[str, VarSpec] = {v.name: v for v in CATALOG}
CUSTOM_PREFIXES: Final[tuple[str, str]] = ("ANTHROPIC_", "CLAUDE_CODE_")

SOURCE_ENV: Final = "env"
SOURCE_SETTINGS: Final = "settings"
SOURCE_UNSET: Final = "unset"


def mask(value: str, secret: bool = True) -> str:
    """Hide a secret. Keep the first 4 and last 4 characters of a long value."""
    if not secret or not value:
        return value
    if len(value) <= 12:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def validate(spec: VarSpec, value: str) -> str | None:
    """Return an error text for a bad value, or None when the value is good."""
    if spec.kind == INTEGER:
        if not value.strip().isdigit():
            return f"{spec.name} must be a whole number. Write 500000, not 500k."
        number: int = int(value)
        if spec.minimum is not None and number < spec.minimum:
            return f"{spec.name} must be at least {spec.minimum}."
        if spec.maximum is not None and number > spec.maximum:
            return f"{spec.name} must be at most {spec.maximum}."
    if spec.kind == URL and not value.startswith(("http://", "https://")):
        return f"{spec.name} must start with http:// or https://."
    if spec.kind == CHOICE and spec.choices and value not in spec.choices:
        return f"{spec.name} must be one of: {', '.join(spec.choices)}."
    return None


class Row(BaseModel):
    """One line of the variable table: the name, the value, and where the value comes from."""
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    name: str
    value: str
    source: Source
    spec: VarSpec | None = None  # None for a custom variable
    shell_value: str = ""  # a different value in the shell. Claude Code ignores it

    @property
    def secret(self) -> bool:
        """Return True when this row holds a secret."""
        return bool(self.spec and self.spec.secret)

    @property
    def display(self) -> str:
        """Return the value as shown on screen, with secrets masked."""
        return mask(value=self.value, secret=self.secret) if self.value else ""


def resolve(settings_env: Mapping[str, str], environ: Mapping[str, str]) -> list[Row]:
    """List every known variable with its value and source.

    The settings.json env block wins over the shell environment. I tested this with Claude Code:
    a model in the env block overrides ANTHROPIC_MODEL exported in the shell. A different shell
    value is kept in shell_value so the screen can say that Claude Code ignores it.
    Unknown ANTHROPIC_* and CLAUDE_CODE_* keys in settings.json show as custom rows.
    """
    rows: list[Row] = []
    for spec in CATALOG:
        if spec.name in settings_env:
            value: str = str(settings_env[spec.name])
            shell: str = environ.get(spec.name, "")
            rows.append(
                Row(
                    name=spec.name,
                    value=value,
                    source=SOURCE_SETTINGS,
                    spec=spec,
                    shell_value=shell if shell != value else "",
                )
            )
        elif spec.name in environ:
            rows.append(Row(name=spec.name, value=environ[spec.name], source=SOURCE_ENV, spec=spec))
        else:
            rows.append(Row(name=spec.name, value="", source=SOURCE_UNSET, spec=spec))
    for name, value in settings_env.items():
        if name not in BY_NAME and name.startswith(CUSTOM_PREFIXES):
            rows.append(Row(name=name, value=str(value), source=SOURCE_SETTINGS, spec=None))
    return rows
