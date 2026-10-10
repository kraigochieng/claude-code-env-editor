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
