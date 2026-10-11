"""Full-screen interface in the style of Claude Code. The main page lists the profiles."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from textual.app import App

from claude_code_env_editor.target import Target
from claude_code_env_editor.tui.dialogs import TextScreen
from claude_code_env_editor.tui.pages import ProfileListPage

__all__ = ["EnvEditorApp", "TextScreen", "run"]


class EnvEditorApp(App[None]):
    """The application. It holds the target file and opens the profile list."""

    CSS_PATH: ClassVar[str] = "styles.tcss"
    ENABLE_COMMAND_PALETTE: ClassVar[bool] = False
    TITLE: str = "claude-code-env-editor"

    def __init__(self, config_dir: Path | None = None, target: Target | None = None) -> None:
        """Keep the target (a settings file), or build it from a config directory."""
        super().__init__()
        if target is None:
            if config_dir is None:
                raise ValueError("Give a config directory or a target.")
            target = Target.from_config_dir(config_dir=config_dir)
        self.target: Target = target

    def on_mount(self) -> None:
        """Open the profile list."""
        self.push_screen(ProfileListPage())


def run(target: Target) -> int:
    """Open the interface for one target (a settings file)."""
    EnvEditorApp(target=target).run()
    return 0
