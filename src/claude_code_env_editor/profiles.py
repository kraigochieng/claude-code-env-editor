"""Named sets of variables that the tool can apply to a settings file."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import ClassVar, Final, Mapping
from urllib.parse import urlparse

import tomli_w
from platformdirs import user_config_dir
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from claude_code_env_editor.envvars import BY_NAME, validate
from claude_code_env_editor.files import atomic_write_text
from claude_code_env_editor.presets import Preset, load_presets
from claude_code_env_editor.registry import APP_NAME

if sys.version_info >= (3, 11):
    import tomllib
else:  # Python 3.10
    import tomli as tomllib

PROFILES_NAME: Final[str] = "profiles.toml"
GITIGNORE_NAME: Final[str] = ".gitignore"
NAME_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class ProfileError(Exception):
    """A profile is unknown, invalid, or cannot be saved."""


class Profile(BaseModel):
    """A name and a set of known variables. A built-in profile is read-only."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    name: str
    variables: dict[str, str]
    note: str = ""
    builtin: bool = False

    @field_validator("name")
    @classmethod
    def _name_is_simple(cls, value: str) -> str:
        """Allow letters, digits, dot, dash, and underscore. Start with a letter or a digit."""
        if not NAME_PATTERN.match(value):
            raise ValueError(
                f"'{value}' is not a valid profile name. Use letters, digits, '.', '-', and '_' (up to 64 characters)."
            )
        return value

    @field_validator("variables")
    @classmethod
    def _variables_are_known_and_valid(cls, value: dict[str, str]) -> dict[str, str]:
        """Allow only variables of the catalog, with valid values.

        This stops a shared profiles file from putting PATH or LD_PRELOAD into the settings of Claude Code.
        """
        for name, text in value.items():
            spec = BY_NAME.get(name)
            if spec is None:
                raise ValueError(f"{name} is not a variable that this tool handles.")
            error: str | None = validate(spec=spec, value=text)
            if error:
                raise ValueError(error)
        return value

    @property
    def base_url(self) -> str:
        """Return the endpoint URL of the profile, or an empty text."""
        return self.variables.get("ANTHROPIC_BASE_URL", "")

    @property
    def host(self) -> str:
        """Return the host of the endpoint. An empty URL means the Anthropic API."""
        return urlparse(url=self.base_url).netloc if self.base_url else "api.anthropic.com"

    @property
    def has_key(self) -> bool:
        """Return True when the profile holds a key."""
        return any(BY_NAME[name].secret for name in self.variables)


class _ProfileEntry(BaseModel):
    """One profile as it is written in profiles.toml."""

    note: str = ""
    variables: dict[str, str] = {}


class _ProfilesFile(BaseModel):
    """The content of profiles.toml."""

    profiles: dict[str, _ProfileEntry] = {}


def default_profiles_path() -> Path:
    """Return profiles.toml in the user config dir of this OS, next to dirs.toml."""
    return Path(user_config_dir(appname=APP_NAME)) / PROFILES_NAME


def builtin_profiles() -> dict[str, Profile]:
    """Return the presets as read-only profiles."""
    presets: dict[str, Preset] = load_presets()
    return {
        preset_id: Profile(name=preset_id, variables=dict(preset.variables), note=preset.label, builtin=True)
        for preset_id, preset in presets.items()
    }


def load_user_profiles(path: Path | None = None) -> dict[str, Profile]:
    """Return the profiles of the user. A missing file gives an empty dict.

    A broken file raises ProfileError. The tool never replaces a file that it cannot read.
    """
    file_path: Path = path or default_profiles_path()
    if not file_path.exists():
        return {}
    try:
        raw: dict[str, object] = tomllib.loads(file_path.read_text(encoding="utf-8"))
        parsed: _ProfilesFile = _ProfilesFile.model_validate(obj=raw)
        return {
            name: Profile(name=name, variables=entry.variables, note=entry.note)
            for name, entry in parsed.profiles.items()
        }
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ProfileError(f"{file_path} cannot be read: {exc}") from exc
    except ValidationError as exc:
        first: str = exc.errors()[0]["msg"]
        raise ProfileError(f"{file_path} has a wrong entry: {first}") from exc


def all_profiles(path: Path | None = None) -> dict[str, Profile]:
    """Return the built-in profiles first, then yours. A built-in name cannot be shadowed."""
    profiles: dict[str, Profile] = builtin_profiles()
    for name, profile in load_user_profiles(path=path).items():
        if name not in profiles:
            profiles[name] = profile
    return profiles


def get_profile(name: str, path: Path | None = None) -> Profile:
    """Return one profile by name. Raise ProfileError with the known names when it is missing."""
    profiles: dict[str, Profile] = all_profiles(path=path)
    if name not in profiles:
        raise ProfileError(f"Unknown profile '{name}'. Choose one of: {', '.join(profiles)}.")
    return profiles[name]


def snapshot(name: str, env: Mapping[str, str], include_keys: bool = True, note: str = "") -> Profile:
    """Make a profile from the known variables of an env block. Custom variables are left out."""
    variables: dict[str, str] = {
        key: value
        for key, value in env.items()
        if key in BY_NAME and (include_keys or not BY_NAME[key].secret)
    }
    return Profile(name=name, variables=variables, note=note)


def save_profile(profile: Profile, path: Path | None = None, overwrite: bool = False) -> Path:
    """Write a profile to profiles.toml (atomic, mode 0600) and return the path.

    A built-in name is refused. An existing name needs overwrite. A .gitignore is written next to the
    file, because the file can hold keys.
    """
    file_path: Path = path or default_profiles_path()
    if profile.name in builtin_profiles():
        raise ProfileError(f"'{profile.name}' is a built-in profile. Save it under another name.")
    user: dict[str, Profile] = load_user_profiles(path=file_path)
    if profile.name in user and not overwrite:
        raise ProfileError(f"A profile named '{profile.name}' exists. Use --force to replace it.")
    user[profile.name] = Profile(name=profile.name, variables=profile.variables, note=profile.note)
    _write(profiles=user, path=file_path)
    return file_path


def delete_profile(name: str, path: Path | None = None) -> None:
    """Remove one of your profiles. A built-in profile cannot be removed."""
    file_path: Path = path or default_profiles_path()
    if name in builtin_profiles():
        raise ProfileError(f"'{name}' is a built-in profile and cannot be deleted.")
    user: dict[str, Profile] = load_user_profiles(path=file_path)
    if name not in user:
        raise ProfileError(f"Unknown profile '{name}'. Yours: {', '.join(user) or 'none'}.")
    del user[name]
    _write(profiles=user, path=file_path)


def _write(profiles: Mapping[str, Profile], path: Path) -> None:
    """Write the profiles of the user as TOML, then make sure that a .gitignore lists the file."""
    data: dict[str, object] = {
        "profiles": {
            name: {"note": profile.note, "variables": dict(profile.variables)} for name, profile in profiles.items()
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    atomic_write_text(path=path, text=tomli_w.dumps(data), mode=0o600)
    ignore: Path = path.parent / GITIGNORE_NAME
    if not ignore.exists():
        atomic_write_text(path=ignore, text=f"{path.name}\n", mode=0o644)
