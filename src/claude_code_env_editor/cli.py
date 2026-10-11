"""Command line interface. With no command, the tool opens the TUI."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Final

from claude_code_env_editor import __version__, config
from claude_code_env_editor.apply import (
    ApplyPlan,
    Mode,
    format_plan,
    plan_apply,
    secret_target_problem,
)
from claude_code_env_editor.auth import describe, visible_rows
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
from claude_code_env_editor.presets import Preset, load_presets
from claude_code_env_editor.profiles import (
    Profile,
    ProfileError,
    all_profiles,
    delete_profile,
    get_profile,
    save_profile,
    snapshot,
)
from claude_code_env_editor.registry import (
    add_to_registry,
    load_registry,
    remove_from_registry,
)
from claude_code_env_editor.target import Target
from claude_code_env_editor.verify import FAIL, PASS, SKIP, Check, Endpoint, verify

CONFIG_DIR_VARIABLE: Final[str] = "CLAUDE_CONFIG_DIR"
PROG: Final[str] = "claude-code-env-editor"
EPILOG: Final[str] = f"Run '{PROG} help <command>' for the help of one command."
MARKS: Final[dict[str, str]] = {PASS: "ok  ", FAIL: "FAIL", SKIP: "skip"}


def _add_dir(p: argparse.ArgumentParser, allow_file: bool = True) -> None:
    """Add --config-dir, and --file when allow_file is True, to a command. The two exclude each other."""
    group: argparse._MutuallyExclusiveGroup = p.add_mutually_exclusive_group()
    group.add_argument(
        "--config-dir",
        type=Path,
        metavar="PATH",
        help="Claude Code config directory (default: $CLAUDE_CONFIG_DIR, then ~/.claude).",
    )
    if allow_file:
        group.add_argument(
            "--file",
            type=Path,
            metavar="PATH",
            help="Any settings file to edit, for example .claude/settings.local.json of a project.",
        )


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all commands and their help text."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog=PROG,
        description="View, edit, and verify the Anthropic variables for Claude Code.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    sub: argparse._SubParsersAction[argparse.ArgumentParser] = parser.add_subparsers(dest="command", metavar="<command>")

    def add_command(name: str, help_: str, example: str) -> argparse.ArgumentParser:
        """Register one command with its description and an example line."""
        p: argparse.ArgumentParser = sub.add_parser(
            name=name,
            help=help_,
            description=help_,
            epilog=f"Example:\n  {example}",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        return p

    p: argparse.ArgumentParser = add_command(name="tui", help_="Open the full-screen interface (default).", example=f"{PROG} tui --config-dir ~/.claude-work")
    _add_dir(p=p)

    p = add_command(name="show", help_="Show each variable, its value, and its source.", example=f"{PROG} show --reveal")
    _add_dir(p=p)
    p.add_argument("--reveal", action="store_true", help="Print secrets in full.")

    p = add_command(name="set", help_="Set one variable in the env block of settings.json.", example=f"{PROG} set ANTHROPIC_MODEL deepseek-flash")
    _add_dir(p=p)
    p.add_argument("name", metavar="NAME")
    p.add_argument("value", nargs="?", help="New value. For a secret, omit it and the tool asks for it.")
    p.add_argument(
        "--no-write-secret",
        action="store_true",
        help="For a secret: do not write it to settings.json. Print an export line instead.",
    )

    p = add_command(name="unset", help_="Remove one variable from the env block.", example=f"{PROG} unset ANTHROPIC_MODEL")
    _add_dir(p=p)
    p.add_argument("name", metavar="NAME")

    p = add_command(name="preset", help_="Apply a sample endpoint, or list them.", example=f"{PROG} preset deepseek")
    _add_dir(p=p)
    p.add_argument("name", nargs="?", metavar="PRESET", help="Preset id. Omit it to list the presets.")

    p = add_command(name="verify", help_="Check the endpoint, the key, and the model.", example=f"{PROG} verify --config-dir ~/.claude-work")
    _add_dir(p=p)

    p = add_command(name="export", help_="Print 'export NAME=value' lines for a shell.", example=f"eval \"$({PROG} export --reveal)\"")
    _add_dir(p=p)
    p.add_argument("--reveal", action="store_true", help="Print secrets in full. Without it they are masked.")

    p = add_command(name="vars", help_="List all variables the tool handles.", example=f"{PROG} vars")

    p = add_command(name="self-update", help_="Install the latest version, or the version you choose.", example=f"{PROG} self-update --version 0.2.0")
    p.add_argument("--version", dest="target", metavar="X.Y.Z", help="Version to install (default: latest).")

    p = add_command(name="self-uninstall", help_="Remove this tool.", example=f"{PROG} self-uninstall")

    p = add_command(name="dirs", help_="List, add, or remove config directories.", example=f"{PROG} dirs add ~/work/claude-login")
    p.add_argument("action", nargs="?", choices=["list", "add", "remove"], default="list")
    p.add_argument("path", nargs="?", type=Path, help="Directory for add or remove.")

    p = add_command(
        name="profile",
        help_="List, show, save, apply, or delete profiles (named sets of variables).",
        example=f"{PROG} profile apply deepseek --file .claude/settings.local.json",
    )
    _add_dir(p=p)
    p.add_argument("action", nargs="?", choices=["list", "show", "save", "apply", "delete"], default="list")
    p.add_argument("name", nargs="?", help="Profile name for show, save, apply, or delete.")
    p.add_argument("--from", dest="source", metavar="PROFILE", help="With save: copy this profile (built-in or yours).")
    p.add_argument("--no-key", action="store_true", help="With save: leave the key out of the profile.")
    p.add_argument("--note", default="", help="With save: a note to store with the profile.")
    p.add_argument("--force", action="store_true", help="With save: replace a profile of the same name.")
    p.add_argument("--reveal", action="store_true", help="With show: print keys in full.")
    p.add_argument("--yes", action="store_true", help="With apply or delete: do not ask first.")
    p.add_argument("--merge", action="store_true", help="With apply: change only the listed variables.")
    p.add_argument("--dry-run", action="store_true", help="With apply: show the changes and write nothing.")
    p.add_argument(
        "--allow-secret-in-shared-file",
        action="store_true",
        help="With apply: allow a key in a file that may be committed.",
    )

    p = add_command(name="help", help_="Show the help of the tool or of one command.", example=f"{PROG} help set")
    p.add_argument("topic", nargs="?", metavar="<command>")
    return parser


def _chosen_target(args: argparse.Namespace) -> Target:
    """Return the target for the file or the config directory the user chose, or for the default one."""
    chosen_file: Path | None = getattr(args, "file", None)
    if chosen_file is not None:
        return Target.from_file(settings_file=chosen_file, known_dirs=config.discover_config_dirs())
    config_dir: Path = args.config_dir.expanduser() if args.config_dir else config.default_config_dir()
    return Target.from_config_dir(config_dir=config_dir)


def _values_in_effect(target: Target) -> dict[str, str]:
    """Return {name: value} for every variable that has a value now."""
    rows: list[Row] = resolve(settings_env=config.load_env(settings_file=target.settings_file), environ=os.environ)
    return {r.name: r.value for r in rows if r.source != SOURCE_UNSET}


def cmd_show(args: argparse.Namespace) -> int:
    """Print each variable with its value and source."""
    target: Target = _chosen_target(args=args)
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


def _read_secret(name: str) -> str:
    """Read a secret from a hidden prompt, or from stdin when it is piped."""
    if sys.stdin.isatty():
        return getpass.getpass(prompt=f"{name}: ")
    return sys.stdin.readline().rstrip("\n")


def cmd_set(args: argparse.Namespace) -> int:
    """Set one variable in settings.json, or print an export line for --no-write-secret."""
    spec: VarSpec | None = BY_NAME.get(args.name)
    if args.name == CONFIG_DIR_VARIABLE:
        print(f"{args.name} selects the config directory. Use --config-dir or set it in your shell.", file=sys.stderr)
        return 2
    value: str | None = args.value
    if value is None:
        if not (spec and spec.secret):
            print(f"Give a value: {PROG} set {args.name} VALUE", file=sys.stderr)
            return 2
        value = _read_secret(name=args.name)
    if spec and (err := validate(spec=spec, value=value)):
        print(err, file=sys.stderr)
        return 2
    target: Target = _chosen_target(args=args)
    if spec and spec.secret and args.no_write_secret:
        print(f"Nothing written. Run this in your shell:\n  export {args.name}={_shell_quote(value=value)}")
        return 0
    path: Path = config.update_env(settings_file=target.settings_file, updates={args.name: value})
    shown: str = mask(value=value, secret=bool(spec and spec.secret))
    print(f"Set {args.name}={shown} in {path}")
    return 0


def cmd_unset(args: argparse.Namespace) -> int:
    """Remove one variable from settings.json."""
    path: Path = config.update_env(settings_file=_chosen_target(args=args).settings_file, updates={args.name: None})
    print(f"Removed {args.name} from {path}")
    return 0


def cmd_preset(args: argparse.Namespace) -> int:
    """List the presets, or apply one to settings.json."""
    presets: dict[str, Preset] = load_presets()
    if not args.name:
        for pid, preset in presets.items():
            print(f"{pid:<12} {preset.label:<24} {preset.base_url}")
        return 0
    try:
        preset_profile: Profile = get_profile(name=args.name)
    except ProfileError as exc:
        print(exc, file=sys.stderr)
        return 2
    code: int = _apply(
        args=args, profile=preset_profile, mode="merge", assume_yes=True, dry_run=False, allow_shared_secret=False
    )
    print(f"Tip: '{PROG} profile apply {args.name}' also removes values of the previous endpoint.")
    return code


def cmd_verify(args: argparse.Namespace) -> int:
    """Run the verify checks and return 1 if any check failed."""
    target: Target = _chosen_target(args=args)
    endpoint: Endpoint = Endpoint.from_values(values=_values_in_effect(target=target))
    print(f"Sending requests to {endpoint.host} only.")
    checks: list[Check] = verify(endpoint=endpoint, login_found=config.has_login(config_dir=target.config_dir))
    for c in checks:
        print(f"[{MARKS[c.status]}] {c.name:<12} {c.detail}")
    return 1 if any(c.status == FAIL for c in checks) else 0


def cmd_export(args: argparse.Namespace) -> int:
    """Print 'export NAME=value' lines for the variables that have a value."""
    for row in resolve(settings_env=config.load_env(settings_file=_chosen_target(args=args).settings_file), environ=os.environ):
        if row.source == SOURCE_UNSET or not row.spec:
            continue
        value: str = row.value if args.reveal else row.display
        print(f"export {row.name}={_shell_quote(value=value)}")
    return 0


def _shell_quote(value: str) -> str:
    """Quote a value for a POSIX shell."""
    return "'" + value.replace("'", "'\"'\"'") + "'"


def cmd_dirs(args: argparse.Namespace) -> int:
    """List the known config directories, or change the registry."""
    if args.action == "list":
        registered: set[Path] = set(load_registry())
        for directory in config.discover_config_dirs():
            origin: str = "registered" if directory in registered else "found"
            print(f"{directory}  [{origin}]")
        return 0
    if args.path is None:
        print(f"Give a directory: {PROG} dirs {args.action} PATH", file=sys.stderr)
        return 2
    if args.action == "add":
        if not args.path.expanduser().is_dir():
            print(f"{args.path} is not a directory.", file=sys.stderr)
            return 2
        changed: bool = add_to_registry(directory=args.path)
    else:
        changed = remove_from_registry(directory=args.path)
    print(("Done: " if changed else "No change: ") + f"{args.action} {args.path}")
    return 0


def _ask_yes(question: str) -> bool:
    """Ask a yes or no question on the terminal. Return False when no terminal is attached."""
    if not sys.stdin.isatty():
        return False
    return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")


def _apply(
    args: argparse.Namespace,
    profile: Profile,
    mode: Mode,
    assume_yes: bool,
    dry_run: bool,
    allow_shared_secret: bool,
) -> int:
    """Show what a profile changes in the target file, ask, and write it. Return the exit code."""
    target: Target = _chosen_target(args=args)
    problem: str | None = secret_target_problem(profile=profile, target=target)
    if problem and not allow_shared_secret:
        print(f"Refused: {problem}", file=sys.stderr)
        return 2
    current: dict[str, str] = config.load_env(settings_file=target.settings_file)
    plan: ApplyPlan = plan_apply(profile=profile, current_env=current, mode=mode)
    print(f"Profile '{profile.name}' -> {target.settings_file} ({mode} mode)")
    for line in format_plan(plan=plan):
        print(line)
    for warning in plan.warnings:
        print(f"  warning: {warning}")
    removed_key: bool = any(c.action == "remove" and BY_NAME[c.name].secret for c in plan.changes)
    if removed_key:
        print(f"  note: the key was removed because the endpoint changed. Next: {PROG} set ANTHROPIC_AUTH_TOKEN")
    if not plan.writes:
        print("Nothing to change.")
        return 0
    if dry_run:
        print("Nothing written (--dry-run).")
        return 0
    if not assume_yes and not _ask_yes(question="Write these changes?"):
        print("Nothing written. Use --yes to write without a question.", file=sys.stderr)
        return 1
    path: Path = config.update_env(settings_file=target.settings_file, updates=plan.updates())
    print(f"Applied profile '{profile.name}' to {path}. The old file is kept as {path.name}.bak.")
    return 0


def cmd_profile(args: argparse.Namespace) -> int:
    """List, show, save, or delete profiles."""
    if args.action == "list":
        for entry in all_profiles().values():
            kind: str = "built-in" if entry.builtin else "yours"
            key: str = "key" if entry.has_key else "no key"
            print(f"{entry.name:<20} {kind:<9} {entry.host:<28} {key:<7} {entry.note}")
        return 0
    if args.name is None:
        print(f"Give a profile name: {PROG} profile {args.action} NAME", file=sys.stderr)
        return 2
    if args.action == "show":
        profile: Profile = get_profile(name=args.name)
        print(f"{profile.name}  ({'built-in' if profile.builtin else 'yours'})  {profile.note}".rstrip())
        for name, value in profile.variables.items():
            secret: bool = BY_NAME[name].secret
            print(f"  {name:<34} {value if args.reveal else mask(value=value, secret=secret)}")
        return 0
    if args.action == "save":
        if args.source:
            base: Profile = get_profile(name=args.source)
            variables: dict[str, str] = dict(base.variables)
            note: str = args.note or base.note
            result: Profile = Profile(name=args.name, variables=variables, note=note)
            if args.no_key:
                result = snapshot(name=args.name, env=variables, include_keys=False, note=note)
        else:
            env: dict[str, str] = config.load_env(settings_file=_chosen_target(args=args).settings_file)
            result = snapshot(name=args.name, env=env, include_keys=not args.no_key, note=args.note)
        if not result.variables:
            print("There are no known variables to save. Set some first.", file=sys.stderr)
            return 2
        path: Path = save_profile(profile=result, overwrite=args.force)
        key_text: str = "with a key" if result.has_key else "without a key"
        print(f"Saved profile '{args.name}' ({len(result.variables)} variables, {key_text}) in {path}")
        return 0
    if args.action == "apply":
        return _apply(
            args=args,
            profile=get_profile(name=args.name),
            mode="merge" if args.merge else "replace",
            assume_yes=args.yes,
            dry_run=args.dry_run,
            allow_shared_secret=args.allow_secret_in_shared_file,
        )
    target_profile: Profile = get_profile(name=args.name)
    if target_profile.builtin:
        print(f"'{args.name}' is a built-in profile and cannot be deleted.", file=sys.stderr)
        return 2
    if not args.yes and not _ask_yes(question=f"Delete profile '{args.name}'?"):
        print("Nothing deleted. Use --yes to delete without a question.", file=sys.stderr)
        return 1
    delete_profile(name=args.name)
    print(f"Deleted profile '{args.name}'.")
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


INSTALL_URL: Final[str] = "https://raw.githubusercontent.com/kraigochieng/claude-code-env-editor/main/install.sh"


def cmd_self_update(args: argparse.Namespace) -> int:
    """Download install.sh and run it to install the latest or a chosen version."""
    import subprocess

    script: subprocess.CompletedProcess[str] = subprocess.run(args=["curl", "-LsSf", INSTALL_URL], capture_output=True, text=True)
    if script.returncode != 0:
        print("Error: cannot download install.sh.", file=sys.stderr)
        return 1
    cmd: list[str] = ["sh", "-s", "--"] + (["--version", args.target] if args.target else [])
    return subprocess.run(args=cmd, input=script.stdout, text=True).returncode


def cmd_self_uninstall(args: argparse.Namespace) -> int:
    """Remove this tool with uv."""
    import subprocess

    return subprocess.run(args=["uv", "tool", "uninstall", "claude-code-env-editor"]).returncode


def cmd_tui(args: argparse.Namespace) -> int:
    """Open the full-screen interface."""
    from claude_code_env_editor.tui.app import run

    return run(target=_chosen_target(args=args))


def main(argv: list[str] | None = None) -> int:
    """Parse the arguments, run the command, and return the exit code."""
    parser: argparse.ArgumentParser = build_parser()
    args: argparse.Namespace = parser.parse_args(args=argv)
    if args.command is None:
        args.command, args.config_dir = "tui", None
    if args.command == "help":
        parser.parse_args(args=[args.topic, "--help"] if args.topic else ["--help"])
        return 0
    handler: Callable[[argparse.Namespace], int] = {
        "show": cmd_show,
        "set": cmd_set,
        "unset": cmd_unset,
        "preset": cmd_preset,
        "verify": cmd_verify,
        "export": cmd_export,
        "vars": cmd_vars,
        "dirs": cmd_dirs,
        "profile": cmd_profile,
        "tui": cmd_tui,
        "self-update": cmd_self_update,
        "self-uninstall": cmd_self_uninstall,
    }[args.command]
    try:
        return handler(args)
    except (config.ConfigError, ProfileError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
