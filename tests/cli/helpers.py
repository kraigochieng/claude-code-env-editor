"""Helpers that the tests of the command line interface share."""

from pathlib import Path

import pytest

from claude_code_env_editor import cli


def run(args: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    return cli.main([*args, "--config-dir", str(tmp_path)] if args[0] not in ("vars", "help") else args)
