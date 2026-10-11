"""Command line interface. With no command, the tool opens the TUI."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from typing import Final

from claude_code_env_editor import config
from claude_code_env_editor.cli.maintenance import cmd_self_uninstall, cmd_self_update, cmd_tui
from claude_code_env_editor.cli.parser import build_parser
from claude_code_env_editor.cli.places import cmd_dirs
from claude_code_env_editor.cli.profiles import cmd_profile
from claude_code_env_editor.cli.variables import (
    cmd_clear,
    cmd_export,
    cmd_set,
    cmd_show,
    cmd_unset,
    cmd_vars,
    cmd_verify,
)
from claude_code_env_editor.profiles import ProfileError

__all__ = ["build_parser", "main"]

HANDLERS: Final[dict[str, Callable[[argparse.Namespace], int]]] = {
    "show": cmd_show,
    "set": cmd_set,
    "unset": cmd_unset,
    "verify": cmd_verify,
    "export": cmd_export,
    "vars": cmd_vars,
    "dirs": cmd_dirs,
    "profile": cmd_profile,
    "clear": cmd_clear,
    "tui": cmd_tui,
    "self-update": cmd_self_update,
    "self-uninstall": cmd_self_uninstall,
}


def main(argv: list[str] | None = None) -> int:
    """Parse the arguments, run the command, and return the exit code."""
    parser: argparse.ArgumentParser = build_parser()
    args: argparse.Namespace = parser.parse_args(args=argv)
    if args.command is None:
        args.command, args.config_dir = "tui", None
    if args.command == "help":
        parser.parse_args(args=[args.topic, "--help"] if args.topic else ["--help"])
        return 0
    handler: Callable[[argparse.Namespace], int] = HANDLERS[args.command]
    try:
        return handler(args)
    except (config.ConfigError, ProfileError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
