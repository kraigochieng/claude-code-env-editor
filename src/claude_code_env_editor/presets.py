"""Built-in sample endpoints."""

from __future__ import annotations

import sys
from importlib import resources

from pydantic import BaseModel, ConfigDict

if sys.version_info >= (3, 11):
    import tomllib
else:  # Python 3.10
    import tomli as tomllib


class Preset(BaseModel):
    """A sample endpoint: a label and the variables it sets."""

    model_config = ConfigDict(frozen=True)

    label: str
    variables: dict[str, str]

    @property
    def base_url(self) -> str:
        """Return the endpoint URL of this preset."""
        return self.variables["ANTHROPIC_BASE_URL"]


def load_presets() -> dict[str, Preset]:
    """Return {preset id: Preset} from presets.toml."""
    text = resources.files("claude_code_env_editor").joinpath("presets.toml").read_text(encoding="utf-8")
    raw = tomllib.loads(text)
    return {
        preset_id: Preset(label=body["label"], variables={k: v for k, v in body.items() if k != "label"})
        for preset_id, body in raw.items()
    }


def preset_values(preset_id: str) -> dict[str, str]:
    """Return the variables of one preset, without its label."""
    presets = load_presets()
    if preset_id not in presets:
        raise KeyError(f"Unknown preset '{preset_id}'. Choose one of: {', '.join(presets)}.")
    return dict(presets[preset_id].variables)
