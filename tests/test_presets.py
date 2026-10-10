import pytest

from claude_code_env_editor.envvars import BY_NAME
from claude_code_env_editor.presets import load_presets, preset_values


def test_every_preset_has_label_and_url() -> None:
    for pid, preset in load_presets().items():
        assert preset.label, pid
        assert preset.base_url.startswith("http"), pid


def test_preset_keys_are_in_catalog() -> None:
    for pid in load_presets():
        for key in preset_values(preset_id=pid):
            assert key in BY_NAME, (pid, key)


def test_deepseek_preset_matches_documented_values() -> None:
    v = preset_values(preset_id="deepseek")
    assert v["ANTHROPIC_MODEL"] == "deepseek-flash[1m]"
    assert v["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] == "786432"
    assert "ANTHROPIC_AUTH_TOKEN" not in v


def test_unknown_preset() -> None:
    with pytest.raises(KeyError):
        preset_values(preset_id="nope")
