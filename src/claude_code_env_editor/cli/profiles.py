"""The profile command: list, show, save, apply, rename, and delete profiles."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from claude_code_env_editor import config
from claude_code_env_editor.apply import ApplyPlan, format_plan, plan_apply, secret_target_problem
from claude_code_env_editor.cli import common
from claude_code_env_editor.envvars import BY_NAME, mask
from claude_code_env_editor.profiles import (
    Profile,
    delete_profile,
    get_profile,
    load_profiles,
    rename_profile,
    save_profile,
    snapshot,
    templates,
)
from claude_code_env_editor.target import Target


def apply_profile(
    args: argparse.Namespace,
    profile: Profile,
    assume_yes: bool,
    dry_run: bool,
    allow_shared_secret: bool,
) -> int:
    """Show what a profile changes in the target file, ask, and write it. Return the exit code."""
    target: Target = common.chosen_target(args=args)
    problem: str | None = secret_target_problem(profile=profile, target=target)
    if problem and not allow_shared_secret:
        print(f"Refused: {problem}", file=sys.stderr)
        return 2
    current: dict[str, str] = config.load_env(settings_file=target.settings_file)
    plan: ApplyPlan = plan_apply(profile=profile, current_env=current)
    print(f"Profile '{profile.name}' -> {target.settings_file}")
    for line in format_plan(plan=plan):
        print(line)
    removed_key: bool = any(c.action == "remove" and BY_NAME[c.name].secret for c in plan.changes)
    if removed_key:
        print(
            "  note: the key was removed because the endpoint changed. "
            f"Next: {common.PROG} set ANTHROPIC_AUTH_TOKEN"
        )
    if not plan.writes:
        print("Nothing to change.")
        return 0
    if dry_run:
        print("Nothing written (--dry-run).")
        return 0
    if not assume_yes and not common.ask_yes(question="Write these changes?"):
        print("Nothing written. Use --yes to write without a question.", file=sys.stderr)
        return 1
    path: Path = config.update_env(settings_file=target.settings_file, updates=plan.updates())
    print(f"Applied profile '{profile.name}' to {path}. The old file is kept as {path.name}.bak.")
    return 0


def list_profiles(action: str) -> int:
    """Print the profiles of the user (action list) or the templates (action templates)."""
    shown: dict[str, Profile] = load_profiles() if action == "list" else templates()
    for entry in shown.values():
        key: str = "key" if entry.has_key else "no key"
        print(f"{entry.name:<20} {entry.host:<28} {key:<7} {entry.note}")
    return 0


def show_profile(name: str, reveal: bool) -> int:
    """Print the variables of one profile. Keys are masked unless reveal is True."""
    profile: Profile = get_profile(name=name)
    print(f"{profile.name}  {profile.note}".rstrip())
    for variable, value in profile.variables.items():
        secret: bool = BY_NAME[variable].secret
        print(f"  {variable:<34} {value if reveal else mask(value=value, secret=secret)}")
    return 0


def save_new_profile(args: argparse.Namespace) -> int:
    """Save a profile from another profile or template (--from), or from the variables of the chosen file."""
    if args.source:
        base: Profile = get_profile(name=args.source, include_templates=True)
        variables: dict[str, str] = dict(base.variables)
        note: str = args.note or base.note
        result: Profile = Profile(name=args.name, variables=variables, note=note)
        if args.no_key:
            result = snapshot(name=args.name, env=variables, include_keys=False, note=note)
    else:
        env: dict[str, str] = config.load_env(settings_file=common.chosen_target(args=args).settings_file)
        result = snapshot(name=args.name, env=env, include_keys=not args.no_key, note=args.note)
    if not result.variables:
        print("There are no known variables to save. Set some first.", file=sys.stderr)
        return 2
    path: Path = save_profile(profile=result, overwrite=args.force)
    key_text: str = "with a key" if result.has_key else "without a key"
    print(f"Saved profile '{args.name}' ({len(result.variables)} variables, {key_text}) in {path}")
    return 0


def rename_existing_profile(name: str, new_name: str | None) -> int:
    """Rename a profile. Return 2 when the new name is missing."""
    if new_name is None:
        print(f"Give the new name: {common.PROG} profile rename {name} NEW", file=sys.stderr)
        return 2
    rename_profile(old=name, new=new_name)
    print(f"Renamed profile '{name}' to '{new_name}'.")
    return 0


def delete_existing_profile(name: str, assume_yes: bool) -> int:
    """Delete a profile after a yes. An unknown name stops with the list of names."""
    get_profile(name=name)
    if not assume_yes and not common.ask_yes(question=f"Delete profile '{name}'?"):
        print("Nothing deleted. Use --yes to delete without a question.", file=sys.stderr)
        return 1
    delete_profile(name=name)
    print(f"Deleted profile '{name}'.")
    return 0


def cmd_profile(args: argparse.Namespace) -> int:
    """List, show, save, apply, rename, or delete profiles."""
    if args.action in ("list", "templates"):
        return list_profiles(action=args.action)
    if args.name is None:
        print(f"Give a profile name: {common.PROG} profile {args.action} NAME", file=sys.stderr)
        return 2
    if args.action == "show":
        return show_profile(name=args.name, reveal=args.reveal)
    if args.action == "save":
        return save_new_profile(args=args)
    if args.action == "apply":
        return apply_profile(
            args=args,
            profile=get_profile(name=args.name),
            assume_yes=args.yes,
            dry_run=args.dry_run,
            allow_shared_secret=args.allow_secret_in_shared_file,
        )
    if args.action == "rename":
        return rename_existing_profile(name=args.name, new_name=args.new_name)
    return delete_existing_profile(name=args.name, assume_yes=args.yes)
