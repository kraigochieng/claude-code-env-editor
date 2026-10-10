"""The settings file that the tool reads and writes."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from claude_code_env_editor.config import SETTINGS_NAME


class Target(BaseModel):
    """One settings.json to edit, and the config directory whose login applies to it."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    settings_file: Path
    config_dir: Path

    @classmethod
    def from_config_dir(cls, config_dir: Path) -> Target:
        """Return the target for the settings.json of a config directory."""
        return cls(settings_file=config_dir / SETTINGS_NAME, config_dir=config_dir)
