"""Commands that work on the variables of one settings file: show, set, unset, verify, export, vars, clear."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Final

from claude_code_env_editor import config
from claude_code_env_editor.apply import ApplyPlan, format_plan, plan_clear
from claude_code_env_editor.auth import describe, visible_rows
from claude_code_env_editor.cli import common
from claude_code_env_editor.envvars import (
    BY_NAME,
    CATALOG,
    SOURCE_UNSET,
    Row,
    VarSpec,
    mask,
    resolve,
    validate,
)
from claude_code_env_editor.target import Target
from claude_code_env_editor.verify import FAIL, PASS, SKIP, Check, Endpoint, verify

MARKS: Final[dict[str, str]] = {PASS: "ok  ", FAIL: "FAIL", SKIP: "skip"}


def cmd_show(args: argparse.Namespace) -> int:
    """Print each variable with its value and source."""
    target: Target = common.chosen_target(args=args)
    print(f"settings file: {target.settings_file}")
    rows: list[Row] = visible_rows(
        rows=resolve(settings_env=config.load_env(settings_file=target.settings_file), environ=os.environ)
    )
    for row in rows:
        value: str = row.value if args.reveal else row.display
        note: str = "  (the shell has another value. Claude Code ignores it)" if row.shell_value else ""
        print(f"{row.name:<34} {value or '-':<28} [{row.source}]{note}")
    print(f"auth: {describe(rows=rows)}")
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    """Set one variable in settings.json, or print an export line for --no-write-secret."""
    spec: VarSpec | None = BY_NAME.get(args.name)
    if args.name == common.CONFIG_DIR_VARIABLE:
        print(f"{args.name} selects the config directory. Use --config-dir or set it in your shell.", file=sys.stderr)
        return 2
    value: str | None = args.value
    if value is None:
        if not (spec and spec.secret):
            print(f"Give a value: {common.PROG} set {args.name} VALUE", file=sys.stderr)
            return 2
        value = common.read_secret(name=args.name)
    if spec and (err := validate(spec=spec, value=value)):
        print(err, file=sys.stderr)
        return 2
    target: Target = common.chosen_target(args=args)
    if spec and spec.secret and args.no_write_secret:
        print(f"Nothing written. Run this in your shell:\n  export {args.name}={common.shell_quote(value=value)}")
        return 0
    path: Path = config.update_env(settings_file=target.settings_file, updates={args.name: value})
    shown: str = mask(value=value, secret=bool(spec and spec.secret))
    print(f"Set {args.name}={shown} in {path}")
    return 0


def cmd_unset(args: argparse.Namespace) -> int:
    """Remove one variable from settings.json."""
    settings_file: Path = common.chosen_target(args=args).settings_file
    path: Path = config.update_env(settings_file=settings_file, updates={args.name: None})
    print(f"Removed {args.name} from {path}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Run the verify checks and return 1 if any check failed."""
    target: Target = common.chosen_target(args=args)
    endpoint: Endpoint = Endpoint.from_values(values=common.values_in_effect(target=target))
    print(f"Sending requests to {endpoint.host} only.")
    checks: list[Check] = verify(endpoint=endpoint, login_found=config.has_login(config_dir=target.config_dir))
    for c in checks:
        print(f"[{MARKS[c.status]}] {c.name:<12} {c.detail}")
    return 1 if any(c.status == FAIL for c in checks) else 0


def cmd_export(args: argparse.Namespace) -> int:
    """Print 'export NAME=value' lines for the variables that have a value."""
    settings_file: Path = common.chosen_target(args=args).settings_file
    for row in resolve(settings_env=config.load_env(settings_file=settings_file), environ=os.environ):
        if row.source == SOURCE_UNSET or not row.spec:
            continue
        value: str = row.value if args.reveal else row.display
        print(f"export {row.name}={common.shell_quote(value=value)}")
    return 0


def cmd_vars(args: argparse.Namespace) -> int:
    """List every variable in the catalog with its type and meaning."""
    for spec in CATALOG:
        flag: str = "secret" if spec.secret else spec.kind
        print(f"{spec.name:<34} {flag:<8} {spec.help}")
        if spec.choices:
            print(f"{'':<43}Values: {', '.join(spec.choices)}")
        if spec.minimum is not None and spec.maximum is not None:
            print(f"{'':<43}Range: {spec.minimum} to {spec.maximum}")
    return 0


def cmd_clear(args: argparse.Namespace) -> int:
    """Remove every known variable from the env block of the chosen file. Custom variables stay."""
    target: Target = common.chosen_target(args=args)
    current: dict[str, str] = config.load_env(settings_file=target.settings_file)
    plan: ApplyPlan = plan_clear(current_env=current)
    print(f"Clear {target.settings_file}")
    if not plan.writes:
        print("Nothing to clear. The file has no known variables.")
        return 0
    for line in format_plan(plan=plan):
        print(line)
    if args.dry_run:
        print("Nothing written (--dry-run).")
        return 0
    if not args.yes and not common.ask_yes(question="Remove these variables?"):
        print("Nothing written. Use --yes to write without a question.", file=sys.stderr)
        return 1
    path: Path = config.update_env(settings_file=target.settings_file, updates=plan.updates())
    print(f"Cleared {len(plan.updates())} variables in {path}. The old file is kept as {path.name}.bak.")
    return 0
