import json
import stat
from pathlib import Path

import pytest

from claude_code_env_editor import config


def test_default_config_dir_uses_env(tmp_path: Path) -> None:
    assert config.default_config_dir(environ={"CLAUDE_CONFIG_DIR": str(tmp_path)}) == tmp_path


def test_default_config_dir_falls_back_to_home(tmp_path: Path) -> None:
    assert config.default_config_dir(environ={}, home=tmp_path) == tmp_path / ".claude"


def test_discover_always_lists_the_default_directory(tmp_path: Path) -> None:
    found: list[Path] = config.discover_config_dirs(home=tmp_path, registry_path=tmp_path / "none.toml", environ={})
    assert found == [tmp_path / ".claude"]


def test_discover_uses_claude_config_dir_as_default(tmp_path: Path) -> None:
    env: dict[str, str] = {"CLAUDE_CONFIG_DIR": str(tmp_path / "custom")}
    found: list[Path] = config.discover_config_dirs(home=tmp_path, registry_path=tmp_path / "none.toml", environ=env)
    assert found[0] == tmp_path / "custom"


def test_update_env_keeps_other_keys(tmp_path: Path) -> None:
    (tmp_path / "settings.json").write_text(data=json.dumps(obj={"theme": "dark", "env": {"A": "1"}}))
    config.update_env(config_dir=tmp_path, updates={"B": "2"})
    data: dict[str, object] = json.loads(s=(tmp_path / "settings.json").read_text())
    assert data == {"theme": "dark", "env": {"A": "1", "B": "2"}}


def test_update_env_removes_key_and_empty_block(tmp_path: Path) -> None:
    config.update_env(config_dir=tmp_path, updates={"A": "1"})
    config.update_env(config_dir=tmp_path, updates={"A": None})
    assert json.loads(s=(tmp_path / "settings.json").read_text()) == {}


def test_update_env_sets_mode_and_backup(tmp_path: Path) -> None:
    config.update_env(config_dir=tmp_path, updates={"A": "1"})
    config.update_env(config_dir=tmp_path, updates={"A": "2"})
    mode: int = stat.S_IMODE((tmp_path / "settings.json").stat().st_mode)
    assert mode == 0o600
    assert json.loads(s=(tmp_path / "settings.json.bak").read_text())["env"] == {"A": "1"}


def test_update_env_leaves_no_temp_file(tmp_path: Path) -> None:
    config.update_env(config_dir=tmp_path, updates={"A": "1"})
    assert [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")] == []


def test_invalid_json_raises(tmp_path: Path) -> None:
    (tmp_path / "settings.json").write_text(data="{bad")
    with pytest.raises(config.ConfigError):
        config.load_settings(config_dir=tmp_path)


def make_login(path: Path) -> Path:
    path.mkdir()
    (path / ".claude.json").write_text(data="{}")
    return path


def test_scan_finds_directory_without_claude_name(tmp_path: Path) -> None:
    login: Path = make_login(tmp_path / ".work-login")
    assert login in config.scan_home_for_config_dirs(home=tmp_path)


def test_scan_ignores_unrelated_directories(tmp_path: Path) -> None:
    (tmp_path / ".ssh").mkdir()
    (tmp_path / ".other").mkdir()
    (tmp_path / ".other" / "settings.json").write_text(data="{}")
    assert config.scan_home_for_config_dirs(home=tmp_path) == []


def test_scan_accepts_settings_with_projects(tmp_path: Path) -> None:
    login: Path = tmp_path / ".acct"
    (login / "projects").mkdir(parents=True)
    (login / "settings.json").write_text(data="{}")
    assert login in config.scan_home_for_config_dirs(home=tmp_path)


def test_discover_merges_sources_without_duplicates(tmp_path: Path) -> None:
    from claude_code_env_editor.registry import add_to_registry

    registry: Path = tmp_path / "reg" / "dirs.toml"
    scanned: Path = make_login(tmp_path / ".scanned")
    outside: Path = tmp_path / "elsewhere"
    outside.mkdir()
    add_to_registry(directory=outside, registry_path=registry)
    add_to_registry(directory=scanned, registry_path=registry)
    found: list[Path] = config.discover_config_dirs(home=tmp_path, registry_path=registry, environ={})
    assert found[0] == tmp_path / ".claude"
    assert outside.resolve() in found
    assert found.count(scanned.resolve()) == 1 or found.count(scanned) == 1


def test_env_numbers_are_read_as_text(tmp_path: Path) -> None:
    (tmp_path / "settings.json").write_text(data=json.dumps(obj={"env": {"API_TIMEOUT_MS": 5000}}))
    assert config.load_env(config_dir=tmp_path) == {"API_TIMEOUT_MS": "5000"}


def test_env_that_is_not_an_object_raises(tmp_path: Path) -> None:
    (tmp_path / "settings.json").write_text(data=json.dumps(obj={"env": ["a"]}))
    with pytest.raises(config.ConfigError):
        config.load_env(config_dir=tmp_path)


def test_top_level_list_raises(tmp_path: Path) -> None:
    (tmp_path / "settings.json").write_text(data="[]")
    with pytest.raises(config.ConfigError):
        config.load_settings(config_dir=tmp_path)


def test_unknown_keys_survive_a_write(tmp_path: Path) -> None:
    (tmp_path / "settings.json").write_text(data=json.dumps(obj={"hooks": {"a": [1, 2]}, "n": 3}))
    config.update_env(config_dir=tmp_path, updates={"A": "1"})
    data: dict[str, object] = json.loads(s=(tmp_path / "settings.json").read_text())
    assert data["hooks"] == {"a": [1, 2]} and data["n"] == 3 and data["env"] == {"A": "1"}


def test_has_login_in_config_dir(tmp_path: Path) -> None:
    (tmp_path / ".claude.json").write_text(data=json.dumps(obj={"oauthAccount": {"emailAddress": "x"}}))
    assert config.has_login(config_dir=tmp_path, home=tmp_path / "home") is True


def test_has_login_false_without_file_or_key(tmp_path: Path) -> None:
    assert config.has_login(config_dir=tmp_path, home=tmp_path / "home") is False
    (tmp_path / ".claude.json").write_text(data=json.dumps(obj={"theme": "dark"}))
    assert config.has_login(config_dir=tmp_path, home=tmp_path / "home") is False


def test_default_directory_reads_login_from_home_file(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude.json").write_text(data=json.dumps(obj={"oauthAccount": {}}))
    assert config.has_login(config_dir=tmp_path / ".claude", home=tmp_path) is True


def test_has_login_ignores_broken_json(tmp_path: Path) -> None:
    (tmp_path / ".claude.json").write_text(data="{bad")
    assert config.has_login(config_dir=tmp_path, home=tmp_path / "home") is False
