"""Commands that manage the tool itself, and the command that opens the full-screen interface."""

from __future__ import annotations

import argparse
import subprocess
import sys
from typing import Final

from claude_code_env_editor.cli import common

INSTALL_URL: Final[str] = "https://raw.githubusercontent.com/kraigochieng/claude-code-env-editor/main/install.sh"


def cmd_self_update(args: argparse.Namespace) -> int:
    """Download install.sh and run it to install the latest or a chosen version."""
    script: subprocess.CompletedProcess[str] = subprocess.run(
        args=["curl", "-LsSf", INSTALL_URL], capture_output=True, text=True
    )
    if script.returncode != 0:
        print("Error: cannot download install.sh.", file=sys.stderr)
        return 1
    cmd: list[str] = ["sh", "-s", "--"] + (["--version", args.target] if args.target else [])
    return subprocess.run(args=cmd, input=script.stdout, text=True).returncode


def cmd_self_uninstall(args: argparse.Namespace) -> int:
    """Remove this tool with uv."""
    return subprocess.run(args=["uv", "tool", "uninstall", "claude-code-env-editor"]).returncode


def cmd_tui(args: argparse.Namespace) -> int:
    """Open the full-screen interface."""
    from claude_code_env_editor.tui.app import run

    return run(target=common.chosen_target(args=args))
