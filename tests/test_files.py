import stat
from pathlib import Path

import pytest

from claude_code_env_editor.files import atomic_write_text


def mode_of(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_writes_text_with_mode_0600_by_default(tmp_path: Path) -> None:
    target: Path = tmp_path / "a.txt"
    atomic_write_text(path=target, text="hello")
    assert target.read_text() == "hello"
    assert mode_of(target) == 0o600


def test_uses_the_given_mode(tmp_path: Path) -> None:
    target: Path = tmp_path / "a.txt"
    atomic_write_text(path=target, text="x", mode=0o644)
    assert mode_of(target) == 0o644


def test_creates_missing_parent_directories(tmp_path: Path) -> None:
    target: Path = tmp_path / "one" / "two" / "a.txt"
    atomic_write_text(path=target, text="x")
    assert target.read_text() == "x"


def test_keeps_a_private_backup_of_the_old_file(tmp_path: Path) -> None:
    target: Path = tmp_path / "a.txt"
    target.write_text("old")
    target.chmod(0o644)
    atomic_write_text(path=target, text="new", keep_backup=True)
    backup: Path = tmp_path / "a.txt.bak"
    assert target.read_text() == "new" and backup.read_text() == "old"
    assert mode_of(backup) == 0o600


def test_no_backup_without_the_flag(tmp_path: Path) -> None:
    target: Path = tmp_path / "a.txt"
    target.write_text("old")
    atomic_write_text(path=target, text="new")
    assert not (tmp_path / "a.txt.bak").exists()


def test_leaves_no_temporary_file_and_keeps_the_old_file_on_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target: Path = tmp_path / "a.txt"
    target.write_text("old")

    def fail(src: str, dst: Path) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("claude_code_env_editor.files.os.replace", fail)
    with pytest.raises(OSError):
        atomic_write_text(path=target, text="new")
    assert target.read_text() == "old"
    assert [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")] == []
