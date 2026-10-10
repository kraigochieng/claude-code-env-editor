import json

import pytest

from claude_code_env_editor import cli


def run(args, tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    return cli.main([*args, "--config-dir", str(tmp_path)] if args[0] not in ("vars", "help") else args)


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    assert "usage" in capsys.readouterr().out.lower()


@pytest.mark.parametrize("command", ["tui", "show", "set", "unset", "preset", "verify", "export", "vars", "help"])
def test_every_command_has_help(command, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main([command, "--help"])
    assert exc.value.code == 0
    assert "Example:" in capsys.readouterr().out


def test_help_command_for_topic(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["help", "set"])
    assert exc.value.code == 0
    assert "NAME" in capsys.readouterr().out


def test_wrong_command_exits_nonzero(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["nope"])
    assert exc.value.code != 0


def test_set_and_show_masks_nothing_for_plain(tmp_path, monkeypatch, capsys):
    assert run(["set", "ANTHROPIC_MODEL", "m1"], tmp_path, monkeypatch) == 0
    assert json.loads((tmp_path / "settings.json").read_text())["env"] == {"ANTHROPIC_MODEL": "m1"}
    run(["show"], tmp_path, monkeypatch)
    assert "m1" in capsys.readouterr().out


def test_set_rejects_bad_integer(tmp_path, monkeypatch):
    assert run(["set", "API_TIMEOUT_MS", "abc"], tmp_path, monkeypatch) == 2


def test_set_secret_does_not_print_it(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "_store", lambda: type("S", (), {"set": lambda *a: None})())
    run(["set", "ANTHROPIC_AUTH_TOKEN", "sk-0123456789abcdef"], tmp_path, monkeypatch)
    assert "0123456789" not in capsys.readouterr().out


def test_show_masks_secret_unless_reveal(tmp_path, monkeypatch, capsys):
    (tmp_path / "settings.json").write_text(json.dumps({"env": {"ANTHROPIC_AUTH_TOKEN": "sk-0123456789abcdef"}}))
    run(["show"], tmp_path, monkeypatch)
    assert "0123456789" not in capsys.readouterr().out
    run(["show", "--reveal"], tmp_path, monkeypatch)
    assert "sk-0123456789abcdef" in capsys.readouterr().out


def test_preset_applies(tmp_path, monkeypatch):
    assert run(["preset", "deepseek"], tmp_path, monkeypatch) == 0
    env = json.loads((tmp_path / "settings.json").read_text())["env"]
    assert env["ANTHROPIC_BASE_URL"] == "https://api.deepseek.com/anthropic"


def test_export_format(tmp_path, monkeypatch, capsys):
    run(["set", "ANTHROPIC_MODEL", "m1"], tmp_path, monkeypatch)
    capsys.readouterr()
    run(["export"], tmp_path, monkeypatch)
    assert "export ANTHROPIC_MODEL='m1'" in capsys.readouterr().out


def test_unset(tmp_path, monkeypatch):
    run(["set", "ANTHROPIC_MODEL", "m1"], tmp_path, monkeypatch)
    run(["unset", "ANTHROPIC_MODEL"], tmp_path, monkeypatch)
    assert json.loads((tmp_path / "settings.json").read_text()) == {}
