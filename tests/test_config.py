import json
import stat

import pytest

from claude_code_env_editor import config


def test_default_config_dir_uses_env(tmp_path):
    assert config.default_config_dir({"CLAUDE_CONFIG_DIR": str(tmp_path)}) == tmp_path


def test_default_config_dir_falls_back_to_home(tmp_path):
    assert config.default_config_dir({}, home=tmp_path) == tmp_path / ".claude"


def test_discover_config_dirs(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude-work").mkdir()
    (tmp_path / ".claude.json").write_text("{}")
    assert [p.name for p in config.discover_config_dirs(tmp_path)] == [".claude", ".claude-work"]


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
