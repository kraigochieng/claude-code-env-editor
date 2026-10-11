"""Built-in sample endpoints."""

from __future__ import annotations

import sys
from importlib import resources
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from claude_code_env_editor.authkind import AuthKind

if sys.version_info >= (3, 11):
    import tomllib
else:  # Python 3.10
    import tomli as tomllib


class Preset(BaseModel):
    """A sample endpoint: a label and the variables it sets."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    label: str
    variables: dict[str, str]
    auth: AuthKind | None = None

    @property
    def base_url(self) -> str:
        """Return the endpoint URL of this preset."""
        return self.variables["ANTHROPIC_BASE_URL"]


def load_presets() -> dict[str, Preset]:
    """Return {preset id: Preset} from presets.toml."""
    text: str = resources.files("claude_code_env_editor").joinpath("presets.toml").read_text(encoding="utf-8")
    raw: dict[str, dict[str, str]] = tomllib.loads(text)
    return {
        preset_id: Preset(
            label=body["label"],
            variables={k: v for k, v in body.items() if k not in ("label", "auth")},
            auth=body.get("auth"),
        )
        for preset_id, body in raw.items()
    }
