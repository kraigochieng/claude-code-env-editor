"""Named sets of variables that the tool can apply to a settings file."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import ClassVar, Final, Iterable, Mapping
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
    """A name and a set of known variables."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    name: str
    variables: dict[str, str]
    note: str = ""

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
    """The content of profiles.toml. templates_seeded tells that the templates were copied in once."""

    templates_seeded: bool = False
    profiles: dict[str, _ProfileEntry] = {}


def default_profiles_path() -> Path:
    """Return profiles.toml in the user config dir of this OS, next to dirs.toml."""
    return Path(user_config_dir(appname=APP_NAME)) / PROFILES_NAME


def templates() -> dict[str, Profile]:
    """Return the templates that ship with the tool: the presets as profiles.

    A template is a starting point. The first use copies the templates into profiles.toml, and from then on
    they are normal profiles.
    """
    presets: dict[str, Preset] = load_presets()
    return {
        preset_id: Profile(name=preset_id, variables=dict(preset.variables), note=preset.label)
        for preset_id, preset in presets.items()
    }


def _read(path: Path) -> tuple[dict[str, Profile], bool]:
    """Return the profiles in the file and the seeded marker. A missing file gives ({}, False).

    A broken file raises ProfileError. The tool never replaces a file that it cannot read.
    """
    if not path.exists():
        return {}, False
    try:
        raw: dict[str, object] = tomllib.loads(path.read_text(encoding="utf-8"))
        parsed: _ProfilesFile = _ProfilesFile.model_validate(obj=raw)
        profiles: dict[str, Profile] = {
            name: Profile(name=name, variables=entry.variables, note=entry.note)
            for name, entry in parsed.profiles.items()
        }
        return profiles, parsed.templates_seeded
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ProfileError(f"{path} cannot be read: {exc}") from exc
    except ValidationError as exc:
        first: str = exc.errors()[0]["msg"]
        raise ProfileError(f"{path} has a wrong entry: {first}") from exc


def load_profiles(path: Path | None = None, seed: bool = True) -> dict[str, Profile]:
    """Return your profiles in file order.

    On first use, and once for a file from an older version, the templates are copied in under names that
    you do not have yet. A marker stops a second copy, so a profile that you delete stays deleted.
    With seed False, the file is only read.
    """
    file_path: Path = path or default_profiles_path()
    profiles, seeded = _read(path=file_path)
    if seed and not seeded:
        for name, template in templates().items():
            if name not in profiles:
                profiles[name] = template
        _write(profiles=profiles, path=file_path)
    return profiles


def get_profile(name: str, path: Path | None = None, include_templates: bool = False) -> Profile:
    """Return one profile by name. Raise ProfileError with the known names when it is missing.

    With include_templates, a template that you removed from your list is found too.
    """
    profiles: dict[str, Profile] = load_profiles(path=path)
    if name in profiles:
        return profiles[name]
    available: dict[str, Profile] = templates()
    if include_templates and name in available:
        return available[name]
    raise ProfileError(f"Unknown profile '{name}'. Choose one of: {', '.join(profiles) or 'none'}.")


def similar_name(name: str, names: Iterable[str]) -> str | None:
    """Return the name in names that differs from name only in case, or None.

    An identical name is not a similar name. The caller checks that case with its own rule.
    """
    wanted: str = name.casefold()
    for other in names:
        if other != name and other.casefold() == wanted:
            return other
    return None


def name_problem(name: str, taken: Iterable[str]) -> str | None:
    """Return a message when a profile name is not usable, or None when it is.

    A name is not usable when it breaks the name format, or when it equals a taken name or differs
    from one only in case.
    """
    if not NAME_PATTERN.match(name):
        return "Use letters, digits, '.', '-', and '_'. Start with a letter or a digit."
    taken_names: set[str] = set(taken)
    if name in taken_names or similar_name(name=name, names=taken_names) is not None:
        return f"A profile named '{name}' exists. Use another name."
    return None


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

    An existing name needs overwrite. A .gitignore is written next to the file, because it can hold keys.
    """
    file_path: Path = path or default_profiles_path()
    profiles: dict[str, Profile] = load_profiles(path=file_path)
    clash: str | None = similar_name(name=profile.name, names=profiles)
    if clash is not None:
        raise ProfileError(f"A profile named '{clash}' exists. Names are not case sensitive. Choose another name.")
    if profile.name in profiles and not overwrite:
        raise ProfileError(f"A profile named '{profile.name}' exists. Use --force to replace it.")
    profiles[profile.name] = Profile(name=profile.name, variables=profile.variables, note=profile.note)
    _write(profiles=profiles, path=file_path)
    return file_path


def delete_profile(name: str, path: Path | None = None) -> None:
    """Remove one of your profiles. A template that you remove stays removed."""
    file_path: Path = path or default_profiles_path()
    profiles: dict[str, Profile] = load_profiles(path=file_path)
    if name not in profiles:
        raise ProfileError(f"Unknown profile '{name}'. Yours: {', '.join(profiles) or 'none'}.")
    del profiles[name]
    _write(profiles=profiles, path=file_path)


def rename_profile(old: str, new: str, path: Path | None = None) -> None:
    """Give a profile a new name. It keeps its position, its variables, and its note.

    The new name follows the name rules. A name that exists is refused.
    """
    file_path: Path = path or default_profiles_path()
    profiles: dict[str, Profile] = load_profiles(path=file_path)
    if old not in profiles:
        raise ProfileError(f"Unknown profile '{old}'. Yours: {', '.join(profiles) or 'none'}.")
    if new == old:
        raise ProfileError("The new name is the same as the old name.")
    if new in profiles:
        raise ProfileError(f"A profile named '{new}' exists. Choose another name.")
    clash: str | None = similar_name(name=new, names=[name for name in profiles if name != old])
    if clash is not None:
        raise ProfileError(f"A profile named '{clash}' exists. Names are not case sensitive. Choose another name.")
    try:
        renamed: Profile = Profile(name=new, variables=profiles[old].variables, note=profiles[old].note)
    except ValidationError as exc:
        raise ProfileError(exc.errors()[0]["msg"].removeprefix("Value error, ")) from exc
    _write(profiles={(new if name == old else name): (renamed if name == old else p) for name, p in profiles.items()}, path=file_path)


def _write(profiles: Mapping[str, Profile], path: Path) -> None:
    """Write the profiles as TOML with the seeded marker, then make sure that a .gitignore lists the file."""
    data: dict[str, object] = {
        "templates_seeded": True,
        "profiles": {
            name: {"note": profile.note, "variables": dict(profile.variables)} for name, profile in profiles.items()
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    atomic_write_text(path=path, text=tomli_w.dumps(data), mode=0o600)
    ignore: Path = path.parent / GITIGNORE_NAME
    if not ignore.exists():
        atomic_write_text(path=ignore, text=f"{path.name}\n", mode=0o644)
