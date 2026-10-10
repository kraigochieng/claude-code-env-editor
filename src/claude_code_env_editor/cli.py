"""Command line interface. With no command, the tool opens the TUI."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Final, Literal

from claude_code_env_editor import __version__, config
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
from claude_code_env_editor.presets import Preset, load_presets, preset_values
from claude_code_env_editor.registry import (
    add_to_registry,
    load_registry,
    remove_from_registry,
)
from claude_code_env_editor.verify import FAIL, PASS, SKIP, Check, Endpoint, verify

PROG: Final[str] = "claude-code-env-editor"
EPILOG: Final[str] = f"Run '{PROG} help <command>' for the help of one command."
MARKS: Final[dict[str, str]] = {PASS: "ok  ", FAIL: "FAIL", SKIP: "skip"}


def _add_dir(p: argparse.ArgumentParser) -> None:
    """Add the --config-dir option to a command."""
    p.add_argument(
        "--config-dir",
        type=Path,
        metavar="PATH",
        help="Claude Code config directory (default: $CLAUDE_CONFIG_DIR, then ~/.claude).",
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

    p = add_command(name="help", help_="Show the help of the tool or of one command.", example=f"{PROG} help set")
    p.add_argument("topic", nargs="?", metavar="<command>")
    return parser


def _chosen_config_dir(args: argparse.Namespace) -> Path:
    """Return the config directory the user chose, or the default."""
    return args.config_dir.expanduser() if args.config_dir else config.default_config_dir()


def _values_in_effect(config_dir: Path) -> dict[str, str]:
    """Return {name: value} for every variable that has a value now."""
    rows: list[Row] = resolve(settings_env=config.load_env(config_dir=config_dir), environ=os.environ)
    return {r.name: r.value for r in rows if r.source != SOURCE_UNSET}


def cmd_show(args: argparse.Namespace) -> int:
    """Print each variable with its value and source."""
    config_dir: Path = _chosen_config_dir(args=args)
    print(f"config dir: {config_dir}")
    for row in resolve(settings_env=config.load_env(config_dir=config_dir), environ=os.environ):
        value: str = row.value if args.reveal else row.display
        print(f"{row.name:<34} {value or '-':<28} [{row.source}]")
    return 0


def _read_secret(name: str) -> str:
    """Read a secret from a hidden prompt, or from stdin when it is piped."""
    if sys.stdin.isatty():
        return getpass.getpass(prompt=f"{name}: ")
    return sys.stdin.readline().rstrip("\n")


def cmd_set(args: argparse.Namespace) -> int:
    """Set one variable in settings.json, or print an export line for --no-write-secret."""
    spec: VarSpec | None = BY_NAME.get(args.name)
    if spec and not spec.writable:
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
    config_dir: Path = _chosen_config_dir(args=args)
    if spec and spec.secret and args.no_write_secret:
        print(f"Nothing written. Run this in your shell:\n  export {args.name}={_shell_quote(value=value)}")
        return 0
    path: Path = config.update_env(config_dir=config_dir, updates={args.name: value})
    shown: str = mask(value=value, secret=bool(spec and spec.secret))
    print(f"Set {args.name}={shown} in {path}")
    return 0


def cmd_unset(args: argparse.Namespace) -> int:
    """Remove one variable from settings.json."""
    path: Path = config.update_env(config_dir=_chosen_config_dir(args=args), updates={args.name: None})
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
        values: dict[str, str] = preset_values(preset_id=args.name)
    except KeyError as exc:
        print(exc.args[0], file=sys.stderr)
        return 2
    path: Path = config.update_env(config_dir=_chosen_config_dir(args=args), updates=values)
    print(f"Applied preset '{args.name}' ({len(values)} variables) to {path}")
    if "ANTHROPIC_AUTH_TOKEN" not in values:
        print(f"Next: {PROG} set ANTHROPIC_AUTH_TOKEN")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Run the verify checks and return 1 if any check failed."""
    endpoint: Endpoint = Endpoint.from_values(values=_values_in_effect(config_dir=_chosen_config_dir(args=args)))
    print(f"Sending requests to {endpoint.host} only.")
    checks: list[Check] = verify(endpoint=endpoint)
    for c in checks:
        print(f"[{MARKS[c.status]}] {c.name:<12} {c.detail}")
    return 1 if any(c.status == FAIL for c in checks) else 0


def cmd_export(args: argparse.Namespace) -> int:
    """Print 'export NAME=value' lines for the variables that have a value."""
    for row in resolve(settings_env=config.load_env(config_dir=_chosen_config_dir(args=args)), environ=os.environ):
        if row.source == SOURCE_UNSET or not row.spec or not row.spec.writable:
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


def cmd_vars(args: argparse.Namespace) -> int:
    """List every variable in the catalog with its type and meaning."""
    for spec in CATALOG:
        flag: Literal['secret'] | Literal['string'] | Literal['url'] | Literal['integer'] | Literal['choice'] = "secret" if spec.secret else spec.kind
        print(f"{spec.name:<34} {flag:<8} {spec.help}")
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

    return run(config_dir=_chosen_config_dir(args=args))


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
        "tui": cmd_tui,
        "self-update": cmd_self_update,
        "self-uninstall": cmd_self_uninstall,
    }[args.command]
    try:
        return handler(args)
    except config.ConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
