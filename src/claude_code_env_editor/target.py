"""The settings file that the tool reads and writes."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from claude_code_env_editor.config import SETTINGS_NAME, default_config_dir


class Target(BaseModel):
    """One settings file to edit, and the config directory whose login applies to it."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    settings_file: Path
    config_dir: Path
    user_level: bool = True  # True: the file is the settings.json of a config directory (one login)

    @classmethod
    def from_config_dir(cls, config_dir: Path) -> Target:
        """Return the target for the settings.json of a config directory."""
        return cls(settings_file=config_dir / SETTINGS_NAME, config_dir=config_dir)

    @classmethod
    def from_file(cls, settings_file: Path, known_dirs: Sequence[Path]) -> Target:
        """Return the target for any settings file.

        A settings.json in a known config directory, or in a directory that holds .claude.json, is a user
        level file of that login. Any other file, such as a project file, uses the default login for checks.
        """
        file: Path = settings_file.expanduser()
        parent: Path = file.parent
        known: set[Path] = {directory.resolve() for directory in known_dirs}
        if file.name == SETTINGS_NAME and (parent.resolve() in known or (parent / ".claude.json").is_file()):
            return cls(settings_file=file, config_dir=parent, user_level=True)
        return cls(settings_file=file, config_dir=default_config_dir(), user_level=False)
