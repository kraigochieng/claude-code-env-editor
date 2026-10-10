from pathlib import Path

import pytest
from pydantic import ValidationError

from claude_code_env_editor.target import Target


def test_from_config_dir_points_at_settings_json(tmp_path: Path) -> None:
    target: Target = Target.from_config_dir(config_dir=tmp_path)
    assert target.settings_file == tmp_path / "settings.json"
    assert target.config_dir == tmp_path


def test_target_is_frozen(tmp_path: Path) -> None:
    target: Target = Target.from_config_dir(config_dir=tmp_path)
    with pytest.raises(ValidationError):
        target.config_dir = tmp_path / "other"  # type: ignore[misc]


def test_from_file_in_a_known_config_dir_is_user_level(tmp_path: Path) -> None:
    login: Path = tmp_path / ".acme"
    login.mkdir()
    target: Target = Target.from_file(settings_file=login / "settings.json", known_dirs=[login])
    assert target.user_level and target.config_dir == login


def test_from_file_next_to_claude_json_is_user_level(tmp_path: Path) -> None:
    login: Path = tmp_path / ".other"
    login.mkdir()
    (login / ".claude.json").write_text("{}")
    target: Target = Target.from_file(settings_file=login / "settings.json", known_dirs=[])
    assert target.user_level and target.config_dir == login


def test_from_file_of_a_project_file_uses_the_default_login(tmp_path: Path) -> None:
    project_file: Path = tmp_path / "proj" / ".claude" / "settings.local.json"
    target: Target = Target.from_file(settings_file=project_file, known_dirs=[])
    assert not target.user_level
    assert target.settings_file == project_file
