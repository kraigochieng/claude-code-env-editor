"""Built-in sample endpoints."""

from __future__ import annotations

from importlib import resources

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


def load_presets() -> dict[str, dict[str, str]]:
    """Return {preset id: {variable: value}}. The label is under the key 'label'."""
    text = resources.files("claude_code_env_editor").joinpath("presets.toml").read_text(encoding="utf-8")
    return tomllib.loads(text)


def preset_values(preset_id: str) -> dict[str, str]:
    presets = load_presets()
    if preset_id not in presets:
        raise KeyError(f"Unknown preset '{preset_id}'. Choose one of: {', '.join(presets)}.")
    return {k: v for k, v in presets[preset_id].items() if k != "label"}
