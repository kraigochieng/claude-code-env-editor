"""The argument parser: every command with its options, its help text, and one example."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Final, TypeAlias

from claude_code_env_editor import __version__
from claude_code_env_editor.cli.common import PROG

Subparsers: TypeAlias = "argparse._SubParsersAction[argparse.ArgumentParser]"

EPILOG: Final[str] = f"Run '{PROG} help <command>' for the help of one command."


def add_directory_options(p: argparse.ArgumentParser, allow_file: bool = True) -> None:
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


def add_command(sub: Subparsers, name: str, help_: str, example: str) -> argparse.ArgumentParser:
    """Register one command with its description and an example line."""
    return sub.add_parser(
        name=name,
        help=help_,
        description=help_,
        epilog=f"Example:\n  {example}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )


def add_tui(sub: Subparsers) -> None:
    """Register the tui command."""
    p: argparse.ArgumentParser = add_command(
        sub=sub,
        name="tui",
        help_="Open the full-screen interface (default).",
        example=f"{PROG} tui --config-dir ~/.claude-work",
    )
    add_directory_options(p=p)


def add_show(sub: Subparsers) -> None:
    """Register the show command."""
    p: argparse.ArgumentParser = add_command(
        sub=sub, name="show", help_="Show each variable, its value, and its source.", example=f"{PROG} show --reveal"
    )
    add_directory_options(p=p)
    p.add_argument("--reveal", action="store_true", help="Print secrets in full.")


def add_set(sub: Subparsers) -> None:
    """Register the set command."""
    p: argparse.ArgumentParser = add_command(
        sub=sub,
        name="set",
        help_="Set one variable in the env block of settings.json.",
        example=f"{PROG} set ANTHROPIC_MODEL deepseek-flash",
    )
    add_directory_options(p=p)
    p.add_argument("name", metavar="NAME")
    p.add_argument("value", nargs="?", help="New value. For a secret, omit it and the tool asks for it.")
    p.add_argument(
        "--no-write-secret",
        action="store_true",
        help="For a secret: do not write it to settings.json. Print an export line instead.",
    )


def add_unset(sub: Subparsers) -> None:
    """Register the unset command."""
    p: argparse.ArgumentParser = add_command(
        sub=sub,
        name="unset",
        help_="Remove one variable from the env block.",
        example=f"{PROG} unset ANTHROPIC_MODEL",
    )
    add_directory_options(p=p)
    p.add_argument("name", metavar="NAME")


def add_verify(sub: Subparsers) -> None:
    """Register the verify command."""
    p: argparse.ArgumentParser = add_command(
        sub=sub,
        name="verify",
        help_="Check the endpoint, the key, and the model.",
        example=f"{PROG} verify --config-dir ~/.claude-work",
    )
    add_directory_options(p=p)


def add_export(sub: Subparsers) -> None:
    """Register the export command."""
    p: argparse.ArgumentParser = add_command(
        sub=sub,
        name="export",
        help_="Print 'export NAME=value' lines for a shell.",
        example=f"eval \"$({PROG} export --reveal)\"",
    )
    add_directory_options(p=p)
    p.add_argument("--reveal", action="store_true", help="Print secrets in full. Without it they are masked.")


def add_vars(sub: Subparsers) -> None:
    """Register the vars command."""
    add_command(sub=sub, name="vars", help_="List all variables the tool handles.", example=f"{PROG} vars")


def add_self_update(sub: Subparsers) -> None:
    """Register the self-update command."""
    p: argparse.ArgumentParser = add_command(
        sub=sub,
        name="self-update",
        help_="Install the latest version, or the version you choose.",
        example=f"{PROG} self-update --version 0.2.0",
    )
    p.add_argument("--version", dest="target", metavar="X.Y.Z", help="Version to install (default: latest).")


def add_self_uninstall(sub: Subparsers) -> None:
    """Register the self-uninstall command."""
    add_command(sub=sub, name="self-uninstall", help_="Remove this tool.", example=f"{PROG} self-uninstall")


def add_dirs(sub: Subparsers) -> None:
    """Register the dirs command."""
    p: argparse.ArgumentParser = add_command(
        sub=sub,
        name="dirs",
        help_="List, add, or remove config directories.",
        example=f"{PROG} dirs add ~/work/claude-login",
    )
    p.add_argument("action", nargs="?", choices=["list", "add", "remove"], default="list")
    p.add_argument("path", nargs="?", type=Path, help="Directory for add or remove.")


def add_profile(sub: Subparsers) -> None:
    """Register the profile command."""
    p: argparse.ArgumentParser = add_command(
        sub=sub,
        name="profile",
        help_="List, show, save, apply, rename, or delete profiles (named sets of variables).",
        example=f"{PROG} profile rename deepseek work-deepseek",
    )
    add_directory_options(p=p)
    p.add_argument(
        "action",
        nargs="?",
        choices=["list", "show", "save", "apply", "rename", "delete", "templates"],
        default="list",
    )
    p.add_argument("name", nargs="?", help="Profile name for show, save, apply, rename, or delete.")
    p.add_argument("new_name", nargs="?", help="With rename: the new name.")
    p.add_argument(
        "--from",
        dest="source",
        metavar="PROFILE",
        help="With save: copy this profile, or a template (see 'profile templates').",
    )
    p.add_argument("--no-key", action="store_true", help="With save: leave the key out of the profile.")
    p.add_argument("--note", default="", help="With save: a note to store with the profile.")
    p.add_argument("--force", action="store_true", help="With save: replace a profile of the same name.")
    p.add_argument("--reveal", action="store_true", help="With show: print keys in full.")
    p.add_argument("--yes", action="store_true", help="With apply or delete: do not ask first.")
    p.add_argument("--dry-run", action="store_true", help="With apply: show the changes and write nothing.")
    p.add_argument(
        "--allow-secret-in-shared-file",
        action="store_true",
        help="With apply: allow a key in a file that may be committed.",
    )


def add_clear(sub: Subparsers) -> None:
    """Register the clear command."""
    p: argparse.ArgumentParser = add_command(
        sub=sub,
        name="clear",
        help_="Erase the known variables from the env block of a settings file.",
        example=f"{PROG} clear --config-dir ~/.claude-work --dry-run",
    )
    add_directory_options(p=p)
    p.add_argument("--yes", action="store_true", help="Do not ask first.")
    p.add_argument("--dry-run", action="store_true", help="Show what would be removed and write nothing.")


def add_help(sub: Subparsers) -> None:
    """Register the help command."""
    p: argparse.ArgumentParser = add_command(
        sub=sub, name="help", help_="Show the help of the tool or of one command.", example=f"{PROG} help set"
    )
    p.add_argument("topic", nargs="?", metavar="<command>")


COMMAND_REGISTRARS: Final[list[Callable[[Subparsers], None]]] = [
    add_tui,
    add_show,
    add_set,
    add_unset,
    add_verify,
    add_export,
    add_vars,
    add_self_update,
    add_self_uninstall,
    add_dirs,
    add_profile,
    add_clear,
    add_help,
]


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all commands and their help text."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog=PROG,
        description="View, edit, and verify the Anthropic variables for Claude Code.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    sub: Subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    for register in COMMAND_REGISTRARS:
        register(sub)
    return parser
