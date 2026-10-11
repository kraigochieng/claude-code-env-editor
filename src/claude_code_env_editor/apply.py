"""Plan and apply a profile to a settings file."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar, Final, Literal, TypeAlias
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict

from claude_code_env_editor.envvars import BY_NAME, CATALOG, mask
from claude_code_env_editor.profiles import Profile
from claude_code_env_editor.target import Target

Action: TypeAlias = Literal["set", "remove", "same", "keep"]

DEFAULT_HOST: Final[str] = "api.anthropic.com"
LOCAL_SETTINGS_NAME: Final[str] = "settings.local.json"


class Change(BaseModel):
    """What apply does to one variable."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    name: str
    action: Action
    old: str = ""
    new: str = ""
    reason: str = ""


class ApplyPlan(BaseModel):
    """The changes that apply would make, with the notes that the user should read first."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    profile_name: str
    changes: list[Change]
    custom_kept: list[str]

    @property
    def writes(self) -> bool:
        """Return True when the plan changes at least one value."""
        return any(change.action in ("set", "remove") for change in self.changes)

    def updates(self) -> dict[str, str | None]:
        """Return {name: new value, or None to remove} for update_env."""
        result: dict[str, str | None] = {}
        for change in self.changes:
            if change.action == "set":
                result[change.name] = change.new
            elif change.action == "remove":
                result[change.name] = None
        return result


def host_of(url: str | None) -> str:
    """Return the host and port of a URL in lower case. An empty URL means the Anthropic API."""
    return urlparse(url=url).netloc.lower() if url else DEFAULT_HOST


def plan_apply(profile: Profile, current_env: Mapping[str, str]) -> ApplyPlan:
    """Work out what applying a profile does to an env block.

    It sets every variable of the profile and removes every known variable that the profile does not list,
    so nothing of the previous endpoint stays. A key stays when the endpoint host does not change, because
    it goes to the same place. Custom variables are never touched.
    """
    known_current: dict[str, str] = {name: value for name, value in current_env.items() if name in BY_NAME}
    custom: list[str] = [name for name in current_env if name not in BY_NAME]
    old_host: str = host_of(url=current_env.get("ANTHROPIC_BASE_URL"))
    new_host: str = host_of(url=profile.variables.get("ANTHROPIC_BASE_URL"))

    changes: list[Change] = []
    for spec in CATALOG:
        name: str = spec.name
        old: str = known_current.get(name, "")
        if name in profile.variables:
            new: str = profile.variables[name]
            if name in known_current and old == new:
                changes.append(Change(name=name, action="same", old=old, new=new))
            else:
                changes.append(Change(name=name, action="set", old=old, new=new))
        elif name in known_current:
            if spec.secret and old_host == new_host:
                changes.append(Change(name=name, action="keep", old=old, reason="same endpoint host as before"))
            else:
                changes.append(Change(name=name, action="remove", old=old))
    return ApplyPlan(profile_name=profile.name, changes=changes, custom_kept=custom)


def format_plan(plan: ApplyPlan, reveal: bool = False, wrap: bool = False) -> list[str]:
    """Return the lines of a summary. Secrets are masked unless reveal is True.

    With wrap, every change takes up to three short lines (name, value, previous value), so that a long
    URL fits in a narrow dialog.
    """

    def show(name: str, value: str) -> str:
        return value if reveal else mask(value=value, secret=BY_NAME[name].secret)

    lines: list[str] = []
    if wrap:
        for change in plan.changes:
            lines.append(f"  {change.action:<7} {change.name}")
            if change.action in ("set", "same"):
                lines.append(f"            {show(change.name, change.new)}")
            if change.action in ("set", "remove") and change.old:
                lines.append(f"            was: {show(change.name, change.old)}")
            if change.action == "keep":
                lines.append(f"            {change.reason}")
        for name in plan.custom_kept:
            lines.append(f"  keep    {name}")
            lines.append("            custom variable, not touched")
        return lines
    for change in plan.changes:
        if change.action == "set":
            was: str = f"  (was: {show(change.name, change.old)})" if change.old else ""
            lines.append(f"  set     {change.name:<34} {show(change.name, change.new)}{was}")
        elif change.action == "remove":
            lines.append(f"  remove  {change.name:<34} (was: {show(change.name, change.old)})")
        elif change.action == "keep":
            lines.append(f"  keep    {change.name:<34} ({change.reason})")
        else:
            lines.append(f"  same    {change.name:<34} {show(change.name, change.new)}")
    for name in plan.custom_kept:
        lines.append(f"  keep    {name:<34} (custom variable, not touched)")
    return lines


def secret_target_problem(profile: Profile, target: Target) -> str | None:
    """Return a reason to refuse a profile with a key, or None when the target is fine.

    A file inside a config directory is private to a login. settings.local.json stays out of git.
    Any other file, such as .claude/settings.json of a project, is usually committed.
    """
    if not profile.has_key or target.user_level or target.settings_file.name == LOCAL_SETTINGS_NAME:
        return None
    return (
        f"{target.settings_file} may be committed to a repository, and this profile holds a key. "
        f"Apply it to {LOCAL_SETTINGS_NAME} or to a config directory instead, "
        "or pass --allow-secret-in-shared-file."
    )
