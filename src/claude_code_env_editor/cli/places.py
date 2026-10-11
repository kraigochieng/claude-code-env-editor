"""The dirs command: list, add, or remove the config directories that the tool knows."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from claude_code_env_editor import config
from claude_code_env_editor.cli.common import PROG
from claude_code_env_editor.registry import add_to_registry, load_registry, remove_from_registry


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
