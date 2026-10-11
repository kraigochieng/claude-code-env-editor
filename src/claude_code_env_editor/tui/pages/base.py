"""What both main pages share: the banner, the table, the status line, and the help dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static

from claude_code_env_editor import __version__
from claude_code_env_editor.target import Target
from claude_code_env_editor.tui.dialogs import TextScreen, key_color
from claude_code_env_editor.tui.pages.table import PageTable

if TYPE_CHECKING:
    from claude_code_env_editor.tui.app import EnvEditorApp


class BasePage(Screen[None]):
    """What both main pages share: the banner, the table, the status line, and the flows for profiles."""

    # -- to be filled in by a page -----------------------------------------

    def columns(self) -> tuple[str, ...]:
        """Return the column titles of the table."""
        raise NotImplementedError

    def refresh_page(self) -> None:
        """Read the data again and redraw the table and the banner."""
        raise NotImplementedError

    def start_message(self) -> str:
        """Return the first text of the status line."""
        raise NotImplementedError

    def help_keys(self) -> list[tuple[str, str]]:
        """Return the (key, meaning) pairs for the help dialog."""
        raise NotImplementedError

    # -- shared structure --------------------------------------------------

    @property
    def editor(self) -> EnvEditorApp:
        """Return the application."""
        return cast("EnvEditorApp", self.app)

    @property
    def preferred(self) -> Target:
        """Return the place that --config-dir or --file chose, or the default login. It is listed first."""
        return self.editor.target

    def compose(self) -> ComposeResult:
        """Build the banner, the table, the status line, and the footer."""
        yield Static(id="banner")
        with Vertical(id="table-box"):
            yield PageTable(cursor_type="row", zebra_stripes=False)
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        """Create the table columns, fill the table, and show the first status text."""
        table: DataTable[Text] = self.query_one(selector=DataTable)
        table.add_columns(*self.columns())
        self.refresh_page()
        self.set_status(message=self.start_message())
        table.focus()

    def on_screen_resume(self) -> None:
        """Redraw when a page above this one closes, because its values may have changed."""
        table: DataTable[Text] = self.query_one(selector=DataTable)
        if table.columns:
            self.refresh_page()

    def set_status(self, message: str, error: bool = False) -> None:
        """Show a message on the status line. Use red for an error."""
        self.query_one(selector="#status", expect_type=Static).update(
            Text(text=message, style="#e5534b" if error else "dim")
        )

    def draw_banner(self, lines: list[tuple[str, str]]) -> None:
        """Draw the banner: the title with the version, then (label, text) lines."""
        t: Text = Text()
        t.append("* claude-code-env-editor", style="bold #d97757")
        t.append(f"  v{__version__}", style="dim")
        for label, text in lines:
            t.append(f"\n{label:<12}", style="dim")
            t.append(text)
        self.query_one(selector="#banner", expect_type=Static).update(t)

    # -- help ---------------------------------------------------------------

    def help_notes(self) -> list[str]:
        """Return the notes under the keys in the help dialog."""
        return []

    def action_help(self) -> None:
        """Open the help dialog with the keys of this page. The keys use the colour of the footer keys."""
        color: str = key_color(app=self.app)
        body: Text = Text()
        for key, text in self.help_keys():
            body.append(f"{key:<14}", style=f"bold {color}")
            body.append(f"{text}\n")
        for note in self.help_notes():
            body.append(f"\n{note}", style="dim")
        self.app.push_screen(screen=TextScreen(title="Help", body=body))
