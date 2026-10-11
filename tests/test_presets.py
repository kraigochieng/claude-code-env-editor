
from claude_code_env_editor.envvars import BY_NAME
from claude_code_env_editor.presets import load_presets


def test_every_preset_has_label_and_url() -> None:
    for pid, preset in load_presets().items():
        assert preset.label, pid
        assert preset.base_url.startswith("http"), pid


def test_preset_keys_are_in_catalog() -> None:
    for pid in load_presets():
        for key in load_presets()[pid].variables:
            assert key in BY_NAME, (pid, key)


def test_deepseek_preset_matches_documented_values() -> None:
    v: dict[str, str] = load_presets()["deepseek"].variables
    assert v["ANTHROPIC_MODEL"] == "deepseek-flash[1m]"
    assert v["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] == "786432"
    assert "ANTHROPIC_AUTH_TOKEN" not in v
