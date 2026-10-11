"""Where a variables page reads and writes its values: the live settings file, or one profile."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from claude_code_env_editor import config
from claude_code_env_editor.envvars import BY_NAME
from claude_code_env_editor.profiles import Profile, save_profile

SourceKind = Literal["file", "profile"]


class VariableSource(ABC):
    """A set of variables that a page shows and edits."""

    kind: SourceKind
    name: str

    @property
    @abstractmethod
    def editable(self) -> bool:
        """Return True when the page may change the values."""

    @abstractmethod
    def load(self) -> dict[str, str]:
        """Return {name: value} of all variables."""

    @abstractmethod
    def save(self, updates: Mapping[str, str | None]) -> None:
        """Apply updates. A value of None removes the variable."""


class FileSource(VariableSource):
    """The env block of a settings file: what Claude Code reads now."""

    kind: SourceKind = "file"

    def __init__(self, settings_file: Path) -> None:
        """Keep the settings file."""
        self.settings_file: Path = settings_file
        self.name: str = "current file"

    @property
    def editable(self) -> bool:
        """The file can always be edited."""
        return True

    def load(self) -> dict[str, str]:
        """Return the env block of the file."""
        return config.load_env(settings_file=self.settings_file)

    def save(self, updates: Mapping[str, str | None]) -> None:
        """Write the updates to the env block atomically."""
        config.update_env(settings_file=self.settings_file, updates=updates)


class ProfileSource(VariableSource):
    """The variables of one profile. A built-in profile is read-only."""

    kind: SourceKind = "profile"

    def __init__(self, profile: Profile) -> None:
        """Keep the profile."""
        self.profile: Profile = profile
        self.name: str = profile.name

    @property
    def editable(self) -> bool:
        """Only a profile of the user can be edited."""
        return not self.profile.builtin

    def load(self) -> dict[str, str]:
        """Return the variables of the profile."""
        return dict(self.profile.variables)

    def save(self, updates: Mapping[str, str | None]) -> None:
        """Write the changed profile to profiles.toml. Invalid values raise ValueError."""
        variables: dict[str, str] = dict(self.profile.variables)
        for key, value in updates.items():
            if value is None:
                variables.pop(key, None)
            else:
                variables[key] = value
        changed: Profile = Profile(name=self.profile.name, variables=variables, note=self.profile.note)
        save_profile(profile=changed, overwrite=True)
        self.profile = changed


def matching_profile(env: Mapping[str, str], profiles: Mapping[str, Profile]) -> Profile | None:
    """Return the profile whose variables equal the known variables of env, or None.

    A profile of the user wins over a built-in one. An env block without known variables matches nothing.
    """
    known: dict[str, str] = {name: value for name, value in env.items() if name in BY_NAME}
    if not known:
        return None
    matches: list[Profile] = [profile for profile in profiles.values() if profile.variables == known]
    matches.sort(key=lambda profile: profile.builtin)
    return matches[0] if matches else None
