from pathlib import Path

import pytest

from claude_code_env_editor import cli


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    assert "usage" in capsys.readouterr().out.lower()


@pytest.mark.parametrize("command", ["tui", "show", "set", "unset", "clear", "verify", "export", "vars", "help", "self-update", "self-uninstall", "dirs", "profile"])
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


def test_config_dir_and_file_exclude_each_other(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["show", "--config-dir", str(tmp_path), "--file", str(tmp_path / "s.json")])
    assert exc.value.code == 2
    assert "not allowed with" in capsys.readouterr().err


def test_the_preset_command_and_the_merge_option_are_gone(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["preset", "deepseek"])
    assert exc.value.code == 2
    with pytest.raises(SystemExit) as merge_exc:
        cli.main(["profile", "apply", "deepseek", "--merge"])
    assert merge_exc.value.code == 2
    assert "unrecognized arguments: --merge" in capsys.readouterr().err
    assert "merge" not in cli.build_parser().format_help().lower()
    assert "preset" not in cli.build_parser().format_help().lower()


def test_tui_command_accepts_a_file_option() -> None:
    args = cli.build_parser().parse_args(["tui", "--file", "x.json"])
    assert args.file == Path("x.json")
