"""Find Claude Code config directories and edit the env block of settings.json."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import ClassVar, Final, Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from claude_code_env_editor.files import atomic_write_text
from claude_code_env_editor.registry import load_registry

SETTINGS_NAME: Final[str] = "settings.json"


class ConfigError(Exception):
    """The settings file cannot be read or written."""


class Settings(BaseModel):
    """The content of settings.json. Only the env block is known. All other keys are kept as they are."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    env: dict[str, str] = Field(default_factory=dict)

    @field_validator("env", mode="before")
    @classmethod
    def _env_values_to_text(cls, value: object) -> object:
        """Accept numbers and booleans in the env block and read them as text."""
        if isinstance(value, dict):
            return {str(k): str(v) for k, v in value.items()}
        return value

    def to_json_dict(self) -> dict[str, object]:
        """Return the JSON content: the unknown keys first, then env. An empty env is left out."""
        content: dict[str, object] = dict(self.model_extra or {})
        if self.env:
            content["env"] = self.env
        return content


def default_config_dir(environ: Mapping[str, str] | None = None, home: Path | None = None) -> Path:
    """Return the config directory: $CLAUDE_CONFIG_DIR if set, else ~/.claude."""
    env: Mapping[str, str] = os.environ if environ is None else environ
    if env.get("CLAUDE_CONFIG_DIR"):
        return Path(env["CLAUDE_CONFIG_DIR"]).expanduser()
    return (home or Path.home()) / ".claude"


def looks_like_config_dir(directory: Path) -> bool:
    """Return True when a directory holds the files of a Claude Code login."""
    if (directory / ".claude.json").is_file():
        return True
    return (directory / SETTINGS_NAME).is_file() and (directory / "projects").is_dir()


def scan_home_for_config_dirs(home: Path) -> list[Path]:
    """Find hidden directories in the home directory that look like a Claude Code login.

    The name does not matter. Only the files inside decide.
    """
    try:
        children: list[Path] = sorted(home.iterdir())
    except OSError:
        return []
    return [p for p in children if p.name.startswith(".") and p.is_dir() and looks_like_config_dir(directory=p)]


def discover_config_dirs(
    home: Path | None = None,
    registry_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> list[Path]:
    """List the config directories: the default one, registered ones, then scanned ones.

    A directory shows once. The order is the order of the sources.
    """
    home_dir: Path = home or Path.home()
    found: list[Path] = [default_config_dir(environ=environ, home=home_dir)]
    found += load_registry(registry_path=registry_path)
    found += scan_home_for_config_dirs(home=home_dir)
    unique: list[Path] = []
    for directory in found:
        if directory not in unique:
            unique.append(directory)
    return unique


def has_login(config_dir: Path, home: Path | None = None) -> bool:
    """Return True when Claude Code stored a login for this config directory.

    Only the presence of the oauthAccount key is checked. The account data and the token are never read out.
    The default directory keeps its file in the home directory (~/.claude.json). Others keep it inside.
    """
    home_dir: Path = home or Path.home()
    candidates: list[Path] = [config_dir / ".claude.json"]
    if config_dir == home_dir / ".claude":
        candidates.append(home_dir / ".claude.json")
    for candidate in candidates:
        try:
            content: object = json.loads(s=candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(content, dict) and "oauthAccount" in content:
            return True
    return False


def settings_path(config_dir: Path) -> Path:
    """Return the path of settings.json in a config directory."""
    return config_dir / SETTINGS_NAME


def load_settings(settings_file: Path) -> Settings:
    """Read a settings file. Return empty settings when the file is missing."""
    path: Path = settings_file
    if not path.exists():
        return Settings()
    try:
        data: object = json.loads(s=path.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path} is not valid JSON: {exc.msg} (line {exc.lineno}).") from exc
    try:
        return Settings.model_validate(obj=data)
    except ValidationError as exc:
        raise ConfigError(f"{path} has a wrong shape: {exc.errors()[0]['msg']} at {exc.errors()[0]['loc']}.") from exc


def load_env(settings_file: Path) -> dict[str, str]:
    """Return the env block of a settings file as {name: value}."""
    return load_settings(settings_file=settings_file).env


def update_env(settings_file: Path, updates: Mapping[str, str | None]) -> Path:
    """Merge updates into the env block of a settings file. A value of None removes the key.

    The write is atomic. The old file is kept as <name>.bak. The mode is 0600.
    All other keys in the file stay as they were.
    """
    settings: Settings = load_settings(settings_file=settings_file)
    for key, value in updates.items():
        if value is None:
            settings.env.pop(key, None)
        else:
            settings.env[key] = value

    text: str = json.dumps(obj=settings.to_json_dict(), indent=2) + "\n"
    atomic_write_text(path=settings_file, text=text, keep_backup=True)
    return settings_file
