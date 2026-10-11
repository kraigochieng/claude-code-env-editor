import json
from pathlib import Path

import pytest

from claude_code_env_editor import cli


def run(args: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    return cli.main([*args, "--config-dir", str(tmp_path)] if args[0] not in ("vars", "help") else args)


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    assert "usage" in capsys.readouterr().out.lower()


@pytest.mark.parametrize("command", ["tui", "show", "set", "unset", "preset", "verify", "export", "vars", "help", "self-update", "self-uninstall", "dirs", "profile"])
def test_every_command_has_help(command: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main([command, "--help"])
    assert exc.value.code == 0
    assert "Example:" in capsys.readouterr().out


def test_help_command_for_topic(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["help", "set"])
    assert exc.value.code == 0
    assert "NAME" in capsys.readouterr().out


def test_wrong_command_exits_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["nope"])
    assert exc.value.code != 0


def test_set_and_show_masks_nothing_for_plain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(["set", "ANTHROPIC_MODEL", "m1"], tmp_path, monkeypatch) == 0
    assert json.loads(s=(tmp_path / "settings.json").read_text())["env"] == {"ANTHROPIC_MODEL": "m1"}
    run(["show"], tmp_path, monkeypatch)
    assert "m1" in capsys.readouterr().out


def test_set_rejects_bad_integer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert run(["set", "API_TIMEOUT_MS", "abc"], tmp_path, monkeypatch) == 2


def test_set_secret_does_not_print_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    run(["set", "ANTHROPIC_AUTH_TOKEN", "sk-0123456789abcdef"], tmp_path, monkeypatch)
    assert "0123456789" not in capsys.readouterr().out


def test_show_masks_secret_unless_reveal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "settings.json").write_text(data=json.dumps(obj={"env": {"ANTHROPIC_AUTH_TOKEN": "sk-0123456789abcdef"}}))
    run(["show"], tmp_path, monkeypatch)
    assert "0123456789" not in capsys.readouterr().out
    run(["show", "--reveal"], tmp_path, monkeypatch)
    assert "sk-0123456789abcdef" in capsys.readouterr().out


def test_preset_applies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert run(["preset", "deepseek"], tmp_path, monkeypatch) == 0
    env: dict[str, str] = json.loads(s=(tmp_path / "settings.json").read_text())["env"]
    assert env["ANTHROPIC_BASE_URL"] == "https://api.deepseek.com/anthropic"


def test_export_format(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    run(["set", "ANTHROPIC_MODEL", "m1"], tmp_path, monkeypatch)
    capsys.readouterr()
    run(["export"], tmp_path, monkeypatch)
    assert "export ANTHROPIC_MODEL='m1'" in capsys.readouterr().out


def test_unset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run(["set", "ANTHROPIC_MODEL", "m1"], tmp_path, monkeypatch)
    run(["unset", "ANTHROPIC_MODEL"], tmp_path, monkeypatch)
    assert json.loads(s=(tmp_path / "settings.json").read_text()) == {}


def test_no_write_secret_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    run(["set", "ANTHROPIC_AUTH_TOKEN", "sk-0123456789abcdef", "--no-write-secret"], tmp_path, monkeypatch)
    assert not (tmp_path / "settings.json").exists()
    assert "export ANTHROPIC_AUTH_TOKEN=" in capsys.readouterr().out


def test_set_secret_writes_settings_with_mode_0600(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run(["set", "ANTHROPIC_AUTH_TOKEN", "sk-0123456789abcdef"], tmp_path, monkeypatch)
    assert (tmp_path / "settings.json").stat().st_mode & 0o777 == 0o600


def test_set_refuses_the_config_dir_variable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert run(["set", "CLAUDE_CONFIG_DIR", "/x"], tmp_path, monkeypatch) == 2
    assert not (tmp_path / "settings.json").exists()


def test_config_dir_variable_is_not_in_the_catalog() -> None:
    from claude_code_env_editor.envvars import BY_NAME

    assert "CLAUDE_CONFIG_DIR" not in BY_NAME


@pytest.fixture
def profiles_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the tool at a profiles file in a temporary directory."""
    path: Path = tmp_path / "tool" / "profiles.toml"
    monkeypatch.setattr("claude_code_env_editor.profiles.default_profiles_path", lambda: path)
    return path


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


def test_profile_apply_merge_keeps_unlisted_variables(
    profiles_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "settings.json").write_text(json.dumps(DEEPSEEK_SETTINGS))
    assert run(["profile", "apply", "openrouter", "--merge", "--yes"], tmp_path, monkeypatch) == 0
    env: dict[str, str] = json.loads((tmp_path / "settings.json").read_text())["env"]
    assert env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "deepseek-flash" and "ANTHROPIC_AUTH_TOKEN" in env


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


def test_config_dir_and_file_exclude_each_other(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["show", "--config-dir", str(tmp_path), "--file", str(tmp_path / "s.json")])
    assert exc.value.code == 2
    assert "not allowed with" in capsys.readouterr().err


def test_preset_alias_keeps_merging_and_prints_a_tip(
    profiles_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "settings.json").write_text(json.dumps(DEEPSEEK_SETTINGS))
    assert run(["preset", "openrouter"], tmp_path, monkeypatch) == 0
    env: dict[str, str] = json.loads((tmp_path / "settings.json").read_text())["env"]
    assert env["ANTHROPIC_BASE_URL"] == "https://openrouter.ai/api"
    assert "ANTHROPIC_DEFAULT_HAIKU_MODEL" in env  # merge keeps old values, as before
    assert "profile apply" in capsys.readouterr().out
    assert run(["preset", "nope"], tmp_path, monkeypatch) == 2
