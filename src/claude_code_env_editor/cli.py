"""Command line interface. With no command, the tool opens the TUI."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

from claude_code_env_editor import __version__, config
from claude_code_env_editor.envvars import BY_NAME, CATALOG, SOURCE_UNSET, mask, resolve, validate
from claude_code_env_editor.presets import load_presets, preset_values
from claude_code_env_editor.verify import FAIL, PASS, SKIP, target_host, verify

PROG = "claude-code-env-editor"
EPILOG = f"Run '{PROG} help <command>' for the help of one command."
MARKS = {PASS: "ok  ", FAIL: "FAIL", SKIP: "skip"}


def _add_dir(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--config-dir",
        type=Path,
        metavar="PATH",
        help="Claude Code config directory (default: $CLAUDE_CONFIG_DIR, then ~/.claude).",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="View, edit, and verify the Anthropic variables for Claude Code.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    def add(name, help_, example):
        p = sub.add_parser(
            name,
            help=help_,
            description=help_,
            epilog=f"Example:\n  {example}",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        return p

    p = add("tui", "Open the full-screen interface (default).", f"{PROG} tui --config-dir ~/.claude-work")
    _add_dir(p)

    p = add("show", "Show each variable, its value, and its source.", f"{PROG} show --reveal")
    _add_dir(p)
    p.add_argument("--reveal", action="store_true", help="Print secrets in full.")

    p = add("set", "Set one variable in the env block of settings.json.", f"{PROG} set ANTHROPIC_MODEL deepseek-flash")
    _add_dir(p)
    p.add_argument("name", metavar="NAME")
    p.add_argument("value", nargs="?", help="New value. For a secret, omit it and the tool asks for it.")
    p.add_argument(
        "--no-write-secret",
        action="store_true",
        help="For a secret: do not write it to settings.json. Print an export line instead.",
    )

    p = add("unset", "Remove one variable from the env block.", f"{PROG} unset ANTHROPIC_MODEL")
    _add_dir(p)
    p.add_argument("name", metavar="NAME")

    p = add("preset", "Apply a sample endpoint, or list them.", f"{PROG} preset deepseek")
    _add_dir(p)
    p.add_argument("name", nargs="?", metavar="PRESET", help="Preset id. Omit it to list the presets.")

    p = add("verify", "Check the endpoint, the key, and the model.", f"{PROG} verify --config-dir ~/.claude-work")
    _add_dir(p)

    p = add("export", "Print 'export NAME=value' lines for a shell.", f"eval \"$({PROG} export --reveal)\"")
    _add_dir(p)
    p.add_argument("--reveal", action="store_true", help="Print secrets in full. Without it they are masked.")

    p = add("vars", "List all variables the tool handles.", f"{PROG} vars")

    p = add("self-update", "Install the latest version, or the version you choose.", f"{PROG} self-update --version 0.2.0")
    p.add_argument("--version", dest="target", metavar="X.Y.Z", help="Version to install (default: latest).")

    p = add("self-uninstall", "Remove this tool.", f"{PROG} self-uninstall")

    p = add("help", "Show the help of the tool or of one command.", f"{PROG} help set")
    p.add_argument("topic", nargs="?", metavar="<command>")
    return parser


def _dir(args) -> Path:
    return args.config_dir.expanduser() if args.config_dir else config.default_config_dir()


def _values(config_dir: Path) -> dict[str, str]:
    rows = resolve(config.load_env(config_dir), os.environ)
    return {r.name: r.value for r in rows if r.source != SOURCE_UNSET}


def cmd_show(args) -> int:
    config_dir = _dir(args)
    print(f"config dir: {config_dir}")
    for row in resolve(config.load_env(config_dir), os.environ):
        value = row.value if args.reveal else row.display
        print(f"{row.name:<34} {value or '-':<28} [{row.source}]")
    return 0


def _read_secret(name: str) -> str:
    if sys.stdin.isatty():
        return getpass.getpass(f"{name}: ")
    return sys.stdin.readline().rstrip("\n")


def cmd_set(args) -> int:
    spec = BY_NAME.get(args.name)
    if spec and not spec.writable:
        print(f"{args.name} selects the config directory. Use --config-dir or set it in your shell.", file=sys.stderr)
        return 2
    value = args.value
    if value is None:
        if not (spec and spec.secret):
            print(f"Give a value: {PROG} set {args.name} VALUE", file=sys.stderr)
            return 2
        value = _read_secret(args.name)
    if spec and (err := validate(spec, value)):
        print(err, file=sys.stderr)
        return 2
    config_dir = _dir(args)
    if spec and spec.secret and args.no_write_secret:
        print(f"Nothing written. Run this in your shell:\n  export {args.name}={_quote(value)}")
        return 0
    path = config.update_env(config_dir, {args.name: value})
    shown = mask(value, bool(spec and spec.secret))
    print(f"Set {args.name}={shown} in {path}")
    return 0


def cmd_unset(args) -> int:
    path = config.update_env(_dir(args), {args.name: None})
    print(f"Removed {args.name} from {path}")
    return 0


def cmd_preset(args) -> int:
    presets = load_presets()
    if not args.name:
        for pid, body in presets.items():
            print(f"{pid:<12} {body['label']:<24} {body['ANTHROPIC_BASE_URL']}")
        return 0
    try:
        values = preset_values(args.name)
    except KeyError as exc:
        print(exc.args[0], file=sys.stderr)
        return 2
    path = config.update_env(_dir(args), values)
    print(f"Applied preset '{args.name}' ({len(values)} variables) to {path}")
    if "ANTHROPIC_AUTH_TOKEN" not in values:
        print(f"Next: {PROG} set ANTHROPIC_AUTH_TOKEN")
    return 0


def cmd_verify(args) -> int:
    values = _values(_dir(args))
    print(f"Sending requests to {target_host(values)} only.")
    checks = verify(values)
    for c in checks:
        print(f"[{MARKS[c.status]}] {c.name:<12} {c.detail}")
    return 1 if any(c.status == FAIL for c in checks) else 0


def cmd_export(args) -> int:
    for row in resolve(config.load_env(_dir(args)), os.environ):
        if row.source == SOURCE_UNSET or not row.spec or not row.spec.writable:
            continue
        value = row.value if args.reveal else row.display
        print(f"export {row.name}={_quote(value)}")
    return 0


def _quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def cmd_vars(args) -> int:
    for spec in CATALOG:
        flag = "secret" if spec.secret else spec.kind
        print(f"{spec.name:<34} {flag:<8} {spec.help}")
    return 0


INSTALL_URL = "https://raw.githubusercontent.com/kraigochieng/claude-code-env-editor/main/install.sh"


def cmd_self_update(args) -> int:
    import subprocess

    script = subprocess.run(["curl", "-LsSf", INSTALL_URL], capture_output=True, text=True)
    if script.returncode != 0:
        print("Error: cannot download install.sh.", file=sys.stderr)
        return 1
    cmd = ["sh", "-s", "--"] + (["--version", args.target] if args.target else [])
    return subprocess.run(cmd, input=script.stdout, text=True).returncode


def cmd_self_uninstall(args) -> int:
    import subprocess

    return subprocess.run(["uv", "tool", "uninstall", "claude-code-env-editor"]).returncode


def cmd_tui(args) -> int:
    from claude_code_env_editor.tui.app import run

    return run(_dir(args))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        args.command, args.config_dir = "tui", None
    if args.command == "help":
        parser.parse_args([args.topic, "--help"] if args.topic else ["--help"])
        return 0
    handler = {
        "show": cmd_show,
        "set": cmd_set,
        "unset": cmd_unset,
        "preset": cmd_preset,
        "verify": cmd_verify,
        "export": cmd_export,
        "vars": cmd_vars,
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
