"""Find Claude Code config directories and edit the env block of settings.json."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Mapping

SETTINGS_NAME = "settings.json"


class ConfigError(Exception):
    """The settings file cannot be read or written."""


def default_config_dir(environ: Mapping[str, str] | None = None, home: Path | None = None) -> Path:
    """Return the config directory: $CLAUDE_CONFIG_DIR if set, else ~/.claude."""
    environ = os.environ if environ is None else environ
    if environ.get("CLAUDE_CONFIG_DIR"):
        return Path(environ["CLAUDE_CONFIG_DIR"]).expanduser()
    return (home or Path.home()) / ".claude"


def discover_config_dirs(home: Path | None = None) -> list[Path]:
    """List the ~/.claude* directories. Each one can hold one Claude Code login."""
    home = home or Path.home()
    return sorted(p for p in home.glob(".claude*") if p.is_dir())


def settings_path(config_dir: Path) -> Path:
    """Return the path of settings.json in a config directory."""
    return config_dir / SETTINGS_NAME


def load_settings(config_dir: Path) -> dict:
    """Read settings.json. Return {} when the file is missing."""
    path = settings_path(config_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path} is not valid JSON: {exc.msg} (line {exc.lineno}).") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must hold a JSON object.")
    return data


def load_env(config_dir: Path) -> dict[str, str]:
    """Return the env block of settings.json as {name: value}."""
    env = load_settings(config_dir).get("env", {})
    if not isinstance(env, dict):
        raise ConfigError(f"The env key in {settings_path(config_dir)} must be an object.")
    return {k: str(v) for k, v in env.items()}


def update_env(config_dir: Path, updates: Mapping[str, str | None]) -> Path:
    """Merge updates into the env block. A value of None removes the key.

    The write is atomic. The old file is kept as settings.json.bak. The mode is 0600.
    All other keys in the file stay as they were.
    """
    settings = load_settings(config_dir)
    env = settings.get("env", {})
    if not isinstance(env, dict):
        raise ConfigError(f"The env key in {settings_path(config_dir)} must be an object.")
    for key, value in updates.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    settings["env"] = env
    if not env:
        settings.pop("env")

    path = settings_path(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_name(path.name + ".bak")
        backup.write_bytes(path.read_bytes())
        os.chmod(backup, 0o600)
    fd, tmp = tempfile.mkstemp(dir=config_dir, prefix=".settings-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(settings, handle, indent=2)
            handle.write("\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path
