"""Keep the list of Claude Code config directories that the user added."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Final

from platformdirs import user_config_dir
from pydantic import BaseModel, ValidationError

if sys.version_info >= (3, 11):
    import tomllib
else:  # Python 3.10
    import tomli as tomllib

APP_NAME: Final[str] = "claude-code-env-editor"
REGISTRY_NAME: Final[str] = "dirs.toml"


class RegistryFile(BaseModel):
    """The content of dirs.toml: the config directories that the user added."""

    dirs: list[Path] = []


def default_registry_path() -> Path:
    """Return the registry file in the user config dir of this OS.

    Linux uses $XDG_CONFIG_HOME (default ~/.config). macOS uses ~/Library/Application Support.
    Windows uses %APPDATA%.
    """
    return Path(user_config_dir(appname=APP_NAME)) / REGISTRY_NAME


def load_registry(registry_path: Path | None = None) -> list[Path]:
    """Return the registered directories. A missing or broken file gives an empty list."""
    path: Path = registry_path or default_registry_path()
    try:
        registry: RegistryFile = RegistryFile.model_validate(obj=tomllib.loads(path.read_text(encoding="utf-8")))
    except (OSError, tomllib.TOMLDecodeError, ValidationError):
        return []
    return [directory.expanduser() for directory in registry.dirs]


def _save_registry(dirs: list[Path], registry_path: Path) -> None:
    """Write the registry as a TOML list of strings."""
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    items: str = ",\n".join(f"  {json.dumps(obj=str(d))}" for d in dirs)
    registry_path.write_text(data=f"dirs = [\n{items}\n]\n" if dirs else "dirs = []\n", encoding="utf-8")


def add_to_registry(directory: Path, registry_path: Path | None = None) -> bool:
    """Register a directory. Return False when it is already there."""
    path: Path = registry_path or default_registry_path()
    resolved: Path = directory.expanduser().resolve()
    dirs: list[Path] = load_registry(registry_path=path)
    if resolved in dirs:
        return False
    _save_registry(dirs=[*dirs, resolved], registry_path=path)
    return True


def remove_from_registry(directory: Path, registry_path: Path | None = None) -> bool:
    """Remove a directory. Return False when it was not registered."""
    path: Path = registry_path or default_registry_path()
    resolved: Path = directory.expanduser().resolve()
    dirs: list[Path] = load_registry(registry_path=path)
    if resolved not in dirs:
        return False
    _save_registry(dirs=[d for d in dirs if d != resolved], registry_path=path)
    return True
