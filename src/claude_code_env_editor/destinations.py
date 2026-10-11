"""Places where a profile can be applied, and the state of a profile in each place."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import ClassVar, Final, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict

from claude_code_env_editor import config
from claude_code_env_editor.envvars import BY_NAME
from claude_code_env_editor.profiles import Profile
from claude_code_env_editor.target import Target

DestinationKind: TypeAlias = Literal["login", "project"]
StateKind: TypeAlias = Literal["matches", "differs", "empty", "unreadable"]

PROJECT_SETTINGS: Final[str] = ".claude/settings.local.json"


class Destination(BaseModel):
    """A place where a profile can be applied: one settings file."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    label: str
    settings_file: Path
    kind: DestinationKind
    config_dir: Path  # the config directory whose login applies to this file

    def to_target(self) -> Target:
        """Return the Target that apply and the config functions use."""
        return Target(settings_file=self.settings_file, config_dir=self.config_dir, user_level=self.kind == "login")


class DestinationState(BaseModel):
    """What a destination holds, compared with one profile."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    kind: StateKind
    differing: list[str] = []

    @property
    def text(self) -> str:
        """Return a short text for a list."""
        if self.kind == "matches":
            return "matches this profile"
        if self.kind == "differs":
            return f"has other values ({len(self.differing)} differ)"
        if self.kind == "empty":
            return "empty"
        return "cannot be read"


def short_path(path: Path, home: Path | None = None) -> str:
    """Return a path with the home directory written as ~."""
    home_dir: Path = home or Path.home()
    try:
        return "~/" + path.relative_to(home_dir).as_posix()
    except ValueError:
        return str(path)


def login_destinations(
    home: Path | None = None,
    registry_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> list[Destination]:
    """Return one destination for each known config directory: the default one, registered ones, found ones."""
    home_dir: Path = home or Path.home()
    return [
        Destination(
            label=short_path(path=directory, home=home_dir),
            settings_file=config.settings_path(config_dir=directory),
            kind="login",
            config_dir=directory,
        )
        for directory in config.discover_config_dirs(home=home_dir, registry_path=registry_path, environ=environ)
    ]


def project_destination(folder: Path, home: Path | None = None, environ: Mapping[str, str] | None = None) -> Destination:
    """Return the destination for a project folder: its .claude/settings.local.json.

    Claude Code keeps that file out of git, so a key cannot reach the repository by accident.
    """
    resolved: Path = folder.expanduser()
    return Destination(
        label=short_path(path=resolved, home=home),
        settings_file=resolved / PROJECT_SETTINGS,
        kind="project",
        config_dir=config.default_config_dir(environ=environ, home=home),
    )


def known_variables(destination: Destination) -> dict[str, str] | None:
    """Return the known variables in the env block of a destination, or None when the file cannot be read."""
    try:
        env: dict[str, str] = config.load_env(settings_file=destination.settings_file)
    except config.ConfigError:
        return None
    return {name: value for name, value in env.items() if name in BY_NAME}


def destination_state(profile: Profile, destination: Destination) -> DestinationState:
    """Compare the known variables of a destination with a profile."""
    known: dict[str, str] | None = known_variables(destination=destination)
    if known is None:
        return DestinationState(kind="unreadable")
    if not known:
        return DestinationState(kind="empty")
    if known == profile.variables:
        return DestinationState(kind="matches")
    names: list[str] = sorted(
        name for name in set(known) | set(profile.variables) if known.get(name) != profile.variables.get(name)
    )
    return DestinationState(kind="differs", differing=names)
