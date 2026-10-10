import json
import stat

import pytest

from claude_code_env_editor import config


def test_default_config_dir_uses_env(tmp_path):
    assert config.default_config_dir({"CLAUDE_CONFIG_DIR": str(tmp_path)}) == tmp_path


def test_default_config_dir_falls_back_to_home(tmp_path):
    assert config.default_config_dir({}, home=tmp_path) == tmp_path / ".claude"


def test_discover_always_lists_the_default_directory(tmp_path):
    found = config.discover_config_dirs(tmp_path, tmp_path / "none.toml", environ={})
    assert found == [tmp_path / ".claude"]


def test_discover_uses_claude_config_dir_as_default(tmp_path):
    env = {"CLAUDE_CONFIG_DIR": str(tmp_path / "custom")}
    found = config.discover_config_dirs(tmp_path, tmp_path / "none.toml", environ=env)
    assert found[0] == tmp_path / "custom"


def test_update_env_keeps_other_keys(tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps({"theme": "dark", "env": {"A": "1"}}))
    config.update_env(tmp_path, {"B": "2"})
    data = json.loads((tmp_path / "settings.json").read_text())
    assert data == {"theme": "dark", "env": {"A": "1", "B": "2"}}


def test_update_env_removes_key_and_empty_block(tmp_path):
    config.update_env(tmp_path, {"A": "1"})
    config.update_env(tmp_path, {"A": None})
    assert json.loads((tmp_path / "settings.json").read_text()) == {}


def test_update_env_sets_mode_and_backup(tmp_path):
    config.update_env(tmp_path, {"A": "1"})
    config.update_env(tmp_path, {"A": "2"})
    mode = stat.S_IMODE((tmp_path / "settings.json").stat().st_mode)
    assert mode == 0o600
    assert json.loads((tmp_path / "settings.json.bak").read_text())["env"] == {"A": "1"}


def test_update_env_leaves_no_temp_file(tmp_path):
    config.update_env(tmp_path, {"A": "1"})
    assert [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")] == []


def test_invalid_json_raises(tmp_path):
    (tmp_path / "settings.json").write_text("{bad")
    with pytest.raises(config.ConfigError):
        config.load_settings(tmp_path)


def make_login(path):
    path.mkdir()
    (path / ".claude.json").write_text("{}")
    return path


def test_scan_finds_directory_without_claude_name(tmp_path):
    login = make_login(tmp_path / ".work-login")
    assert login in config.scan_home_for_config_dirs(tmp_path)


def test_scan_ignores_unrelated_directories(tmp_path):
    (tmp_path / ".ssh").mkdir()
    (tmp_path / ".other").mkdir()
    (tmp_path / ".other" / "settings.json").write_text("{}")
    assert config.scan_home_for_config_dirs(tmp_path) == []


def test_scan_accepts_settings_with_projects(tmp_path):
    login = tmp_path / ".acct"
    (login / "projects").mkdir(parents=True)
    (login / "settings.json").write_text("{}")
    assert login in config.scan_home_for_config_dirs(tmp_path)


def test_discover_merges_sources_without_duplicates(tmp_path):
    from claude_code_env_editor.registry import add_to_registry

    registry = tmp_path / "reg" / "dirs.toml"
    scanned = make_login(tmp_path / ".scanned")
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    add_to_registry(outside, registry)
    add_to_registry(scanned, registry)
    found = config.discover_config_dirs(tmp_path, registry, environ={})
    assert found[0] == tmp_path / ".claude"
    assert outside.resolve() in found
    assert found.count(scanned.resolve()) == 1 or found.count(scanned) == 1
