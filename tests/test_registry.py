from pathlib import Path
import pytest
from claude_code_env_editor import registry


def test_missing_file_gives_empty_list(tmp_path: Path) -> None:
    assert registry.load_registry(registry_path=tmp_path / "none.toml") == []


def test_broken_file_gives_empty_list(tmp_path: Path) -> None:
    path = tmp_path / "dirs.toml"
    path.write_text(data="dirs = [")
    assert registry.load_registry(registry_path=path) == []


def test_add_and_remove(tmp_path: Path) -> None:
    path = tmp_path / "cfg" / "dirs.toml"
    target = tmp_path / "login"
    target.mkdir()
    assert registry.add_to_registry(directory=target, registry_path=path) is True
    assert registry.add_to_registry(directory=target, registry_path=path) is False
    assert registry.load_registry(registry_path=path) == [target.resolve()]
    assert registry.remove_from_registry(directory=target, registry_path=path) is True
    assert registry.remove_from_registry(directory=target, registry_path=path) is False
    assert registry.load_registry(registry_path=path) == []


def test_path_with_quotes_and_backslashes_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "dirs.toml"
    odd = tmp_path / 'a "b" \\c'
    odd.mkdir()
    registry.add_to_registry(directory=odd, registry_path=path)
    assert registry.load_registry(registry_path=path) == [odd.resolve()]


def test_default_path_is_in_user_config_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr("sys.platform", "linux")
    assert registry.default_registry_path().name == "dirs.toml"


def test_wrong_type_gives_empty_list(tmp_path: Path) -> None:
    path = tmp_path / "dirs.toml"
    path.write_text(data="dirs = 5")
    assert registry.load_registry(registry_path=path) == []
