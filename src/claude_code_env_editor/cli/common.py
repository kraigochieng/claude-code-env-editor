"""Names and helpers that more than one command of the command line interface uses."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path
from typing import Final

from claude_code_env_editor import config
from claude_code_env_editor.envvars import SOURCE_UNSET, Row, resolve
from claude_code_env_editor.target import Target

CONFIG_DIR_VARIABLE: Final[str] = "CLAUDE_CONFIG_DIR"
PROG: Final[str] = "claude-code-env-editor"


def chosen_target(args: argparse.Namespace) -> Target:
    """Return the target for the file or the config directory the user chose, or for the default one."""
    chosen_file: Path | None = getattr(args, "file", None)
    if chosen_file is not None:
        return Target.from_file(settings_file=chosen_file, known_dirs=config.discover_config_dirs())
    config_dir: Path = args.config_dir.expanduser() if args.config_dir else config.default_config_dir()
    return Target.from_config_dir(config_dir=config_dir)


def values_in_effect(target: Target) -> dict[str, str]:
    """Return {name: value} for every variable that has a value now."""
    rows: list[Row] = resolve(settings_env=config.load_env(settings_file=target.settings_file), environ=os.environ)
    return {r.name: r.value for r in rows if r.source != SOURCE_UNSET}


def ask_yes(question: str) -> bool:
    """Ask a yes or no question on the terminal. Return False when no terminal is attached."""
    if not sys.stdin.isatty():
        return False
    return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")


def read_secret(name: str) -> str:
    """Read a secret from a hidden prompt, or from stdin when it is piped."""
    if sys.stdin.isatty():
        return getpass.getpass(prompt=f"{name}: ")
    return sys.stdin.readline().rstrip("\n")


def shell_quote(value: str) -> str:
    """Quote a value for a POSIX shell."""
    return "'" + value.replace("'", "'\"'\"'") + "'"
