import json
from pathlib import Path

import pytest

from claude_code_env_editor import cli
from claude_code_env_editor.cli import common
from tests.cli.helpers import run


def write_env(tmp_path: Path, env: dict[str, str], extra: dict[str, object] | None = None) -> Path:
    settings: Path = tmp_path / "settings.json"
    settings.write_text(data=json.dumps(obj={**(extra or {}), "env": env}))
    return settings


def test_clear_removes_known_variables_and_keeps_custom_variables_and_other_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    settings: Path = write_env(
        tmp_path,
        {
            "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
            "ANTHROPIC_AUTH_TOKEN": "sk-0123456789abcdef",
            "ANTHROPIC_MODEL": "deepseek-flash",
            "HTTP_PROXY": "http://proxy:3128",
        },
        extra={"theme": "dark"},
    )
    assert run(["clear", "--yes"], tmp_path, monkeypatch) == 0
    saved: dict[str, object] = json.loads(s=settings.read_text())
    assert saved["env"] == {"HTTP_PROXY": "http://proxy:3128"}
    assert saved["theme"] == "dark"
    assert (tmp_path / "settings.json.bak").exists()
    assert "0123456789" not in capsys.readouterr().out  # the key is masked


def test_clear_dry_run_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    settings: Path = write_env(tmp_path, {"ANTHROPIC_MODEL": "m1"})
    before: str = settings.read_text()
    assert run(["clear", "--dry-run"], tmp_path, monkeypatch) == 0
    assert settings.read_text() == before
    assert "ANTHROPIC_MODEL" in capsys.readouterr().out
    assert not (tmp_path / "settings.json.bak").exists()


def test_clear_answer_no_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings: Path = write_env(tmp_path, {"ANTHROPIC_MODEL": "m1"})
    before: str = settings.read_text()
    monkeypatch.setattr(common, "ask_yes", lambda question: False)
    assert run(["clear"], tmp_path, monkeypatch) == 1
    assert settings.read_text() == before


def test_clear_with_nothing_to_clear_creates_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(["clear", "--yes"], tmp_path, monkeypatch) == 0
    assert "Nothing to clear" in capsys.readouterr().out
    assert not (tmp_path / "settings.json").exists()
    write_env(tmp_path, {"HTTP_PROXY": "http://proxy:3128"})
    assert run(["clear", "--yes"], tmp_path, monkeypatch) == 0
    assert not (tmp_path / "settings.json.bak").exists()


def test_clear_works_on_any_settings_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project: Path = tmp_path / "project" / ".claude"
    project.mkdir(parents=True)
    local: Path = project / "settings.local.json"
    local.write_text(data=json.dumps(obj={"env": {"ANTHROPIC_MODEL": "m1", "API_TIMEOUT_MS": "5000"}}))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    assert cli.main(["clear", "--file", str(local), "--yes"]) == 0
    assert json.loads(s=local.read_text()).get("env", {}) == {}  # an empty env block may be dropped
