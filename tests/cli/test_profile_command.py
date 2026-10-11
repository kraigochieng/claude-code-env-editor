import json
from pathlib import Path

import pytest

from claude_code_env_editor import cli
from tests.cli.helpers import run


def test_profile_list_shows_the_seeded_templates_without_a_kind(
    profiles_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(["profile"], tmp_path, monkeypatch) == 0
    out: str = capsys.readouterr().out
    assert "deepseek" in out and "api.deepseek.com" in out
    assert "built-in" not in out and "yours" not in out
    assert profiles_file.exists()  # the first use copied the templates in


def test_profile_save_show_masks_the_key_and_delete(
    profiles_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    settings: Path = tmp_path / "settings.json"
    settings.write_text(
        json.dumps(
            {"env": {"ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic", "ANTHROPIC_AUTH_TOKEN": "sk-0123456789abcdef"}}
        )
    )
    assert run(["profile", "save", "work"], tmp_path, monkeypatch) == 0
    assert "with a key" in capsys.readouterr().out
    assert run(["profile", "show", "work"], tmp_path, monkeypatch) == 0
    shown: str = capsys.readouterr().out
    assert "0123456789" not in shown and "api.deepseek.com" in shown
    assert run(["profile", "show", "work", "--reveal"], tmp_path, monkeypatch) == 0
    assert "sk-0123456789abcdef" in capsys.readouterr().out
    assert run(["profile", "delete", "work", "--yes"], tmp_path, monkeypatch) == 0
    assert run(["profile", "show", "work"], tmp_path, monkeypatch) == 1


def test_profile_save_without_key_and_copy_of_a_template(
    profiles_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(["profile", "save", "mine", "--from", "deepseek", "--note", "my copy"], tmp_path, monkeypatch) == 0
    assert "without a key" in capsys.readouterr().out
    assert run(["profile", "save", "mine", "--from", "deepseek"], tmp_path, monkeypatch) == 1
    assert "--force" in capsys.readouterr().err
    assert run(["profile", "save", "mine", "--from", "deepseek", "--force"], tmp_path, monkeypatch) == 0


def test_profile_save_with_nothing_to_save_is_refused(
    profiles_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run(["profile", "save", "empty"], tmp_path, monkeypatch) == 2


def test_profile_delete_needs_yes_without_a_terminal(
    profiles_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run(["profile", "save", "mine", "--from", "deepseek"], tmp_path, monkeypatch) == 0
    assert run(["profile", "delete", "mine"], tmp_path, monkeypatch) == 1
    assert run(["profile", "delete", "mine", "--yes"], tmp_path, monkeypatch) == 0


def test_a_template_profile_can_be_deleted_and_added_again_from_the_template(
    profiles_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(["profile", "delete", "deepseek", "--yes"], tmp_path, monkeypatch) == 0
    capsys.readouterr()
    assert run(["profile"], tmp_path, monkeypatch) == 0
    assert "deepseek" not in capsys.readouterr().out.split()
    assert run(["profile", "templates"], tmp_path, monkeypatch) == 0
    assert "deepseek" in capsys.readouterr().out
    assert run(["profile", "save", "deepseek", "--from", "deepseek"], tmp_path, monkeypatch) == 0
    assert run(["profile", "show", "deepseek"], tmp_path, monkeypatch) == 0


def test_profile_rename(
    profiles_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(["profile", "rename", "deepseek", "work-ds"], tmp_path, monkeypatch) == 0
    assert "Renamed profile 'deepseek' to 'work-ds'." in capsys.readouterr().out
    assert run(["profile", "show", "work-ds"], tmp_path, monkeypatch) == 0
    assert run(["profile", "show", "deepseek"], tmp_path, monkeypatch) == 1
    assert run(["profile", "rename", "work-ds", "openrouter"], tmp_path, monkeypatch) == 1  # name exists
    assert run(["profile", "rename", "work-ds"], tmp_path, monkeypatch) == 2  # new name missing


DEEPSEEK_SETTINGS: dict[str, dict[str, str]] = {
    "env": {
        "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
        "ANTHROPIC_AUTH_TOKEN": "sk-deepseek-0123456789",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-flash",
        "CLAUDE_CODE_MY_FLAG": "1",
    }
}


def test_profile_apply_replaces_stale_values_and_keeps_custom_ones(
    profiles_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "settings.json").write_text(json.dumps(DEEPSEEK_SETTINGS))
    assert run(["profile", "apply", "openrouter", "--yes"], tmp_path, monkeypatch) == 0
    env: dict[str, str] = json.loads((tmp_path / "settings.json").read_text())["env"]
    assert env["ANTHROPIC_BASE_URL"] == "https://openrouter.ai/api"
    assert "ANTHROPIC_DEFAULT_HAIKU_MODEL" not in env and "ANTHROPIC_AUTH_TOKEN" not in env
    assert env["CLAUDE_CODE_MY_FLAG"] == "1"
    out: str = capsys.readouterr().out
    assert "remove" in out and "0123456789" not in out and "the key was removed" in out
    assert (tmp_path / "settings.json.bak").exists()


def test_profile_apply_dry_run_writes_nothing(
    profiles_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "settings.json").write_text(json.dumps(DEEPSEEK_SETTINGS))
    before: str = (tmp_path / "settings.json").read_text()
    assert run(["profile", "apply", "openrouter", "--dry-run"], tmp_path, monkeypatch) == 0
    assert (tmp_path / "settings.json").read_text() == before
    assert "Nothing written (--dry-run)." in capsys.readouterr().out


def test_profile_apply_without_yes_and_without_a_terminal_writes_nothing(
    profiles_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "settings.json").write_text(json.dumps(DEEPSEEK_SETTINGS))
    before: str = (tmp_path / "settings.json").read_text()
    assert run(["profile", "apply", "openrouter"], tmp_path, monkeypatch) == 1
    assert (tmp_path / "settings.json").read_text() == before


def test_profile_apply_to_a_file_works_and_refuses_a_key_in_a_shared_file(
    profiles_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    shared: Path = tmp_path / "proj" / ".claude" / "settings.json"
    local: Path = tmp_path / "proj" / ".claude" / "settings.local.json"
    (tmp_path / "settings.json").write_text(json.dumps(DEEPSEEK_SETTINGS))
    assert cli.main(["profile", "save", "keyed", "--config-dir", str(tmp_path)]) == 0
    assert cli.main(["profile", "apply", "keyed", "--yes", "--file", str(shared)]) == 2
    assert not shared.exists()
    assert cli.main(["profile", "apply", "keyed", "--yes", "--file", str(local)]) == 0
    assert json.loads(local.read_text())["env"]["ANTHROPIC_AUTH_TOKEN"] == "sk-deepseek-0123456789"
    assert cli.main(["profile", "apply", "keyed", "--yes", "--allow-secret-in-shared-file", "--file", str(shared)]) == 0
    assert shared.exists()


def test_profile_apply_unknown_profile_is_an_error(
    profiles_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run(["profile", "apply", "nope", "--yes"], tmp_path, monkeypatch) == 1
