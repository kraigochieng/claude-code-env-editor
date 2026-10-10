"""Keep the list of Claude Code config directories that the user added."""

from __future__ import annotations

import json
from pathlib import Path

from platformdirs import user_config_dir

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

APP_NAME = "claude-code-env-editor"
REGISTRY_NAME = "dirs.toml"


def default_registry_path() -> Path:
    """Return the registry file in the user config dir of this OS.

    Linux uses $XDG_CONFIG_HOME (default ~/.config). macOS uses ~/Library/Application Support.
    Windows uses %APPDATA%.
    """
    return Path(user_config_dir(APP_NAME)) / REGISTRY_NAME


def load_registry(registry_path: Path | None = None) -> list[Path]:
    """Return the registered directories. A missing or broken file gives an empty list."""
    path = registry_path or default_registry_path()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return []
    return [Path(p).expanduser() for p in data.get("dirs", []) if isinstance(p, str)]


def _save_registry(dirs: list[Path], registry_path: Path) -> None:
    """Write the registry as a TOML list of strings."""
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    items = ",\n".join(f"  {json.dumps(str(d))}" for d in dirs)
    registry_path.write_text(f"dirs = [\n{items}\n]\n" if dirs else "dirs = []\n", encoding="utf-8")


def add_to_registry(directory: Path, registry_path: Path | None = None) -> bool:
    """Register a directory. Return False when it is already there."""
    path = registry_path or default_registry_path()
    directory = directory.expanduser().resolve()
    dirs = load_registry(path)
    if directory in dirs:
        return False
    _save_registry([*dirs, directory], path)
    return True


def remove_from_registry(directory: Path, registry_path: Path | None = None) -> bool:
    """Remove a directory. Return False when it was not registered."""
    path = registry_path or default_registry_path()
    directory = directory.expanduser().resolve()
    dirs = load_registry(path)
    if directory not in dirs:
        return False
    _save_registry([d for d in dirs if d != directory], path)
    return True
