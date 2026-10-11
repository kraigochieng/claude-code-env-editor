"""The page that shows the variables of one profile."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from rich.text import Text
from textual.binding import Binding, BindingType
from textual.widgets import DataTable

from claude_code_env_editor.auth import visible_rows
from claude_code_env_editor.envvars import (
    CHOICE,
    SOURCE_ENV,
    SOURCE_UNSET,
    Row,
    resolve,
)
from claude_code_env_editor.profiles import Profile, ProfileError
from claude_code_env_editor.sources import ProfileSource
from claude_code_env_editor.tui.dialogs import (
    REMOVE_CHOICE,
    ConfirmScreen,
    EditScreen,
    PickScreen,
)
from claude_code_env_editor.tui.pages.base import BasePage
from claude_code_env_editor.tui.pages.table import PageTable


class VariablesPage(BasePage):
    """The variables of one profile."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding(key="e", action="edit", description="edit"),
        Binding(key="x", action="remove", description="remove"),
        Binding(key="escape", action="back", description="back"),
        Binding(key="question_mark", action="help", description="help"),
        Binding(key="q", action="app.quit", description="quit"),
    ]

    def __init__(self, profile: Profile, fresh: bool = False) -> None:
        """Keep the profile that the page shows. fresh is True for a profile that was just created."""
        super().__init__()
        self.fresh: bool = fresh
        self.source: ProfileSource = ProfileSource(profile=profile)
        self.rows: list[Row] = []

    def columns(self) -> tuple[str, ...]:
        """Return the column titles."""
        return ("Variable", "Value")

    def start_message(self) -> str:
        """Return the first status text."""
        if self.fresh:
            return "New profile. Press e to set a value. Left arrow goes back. ? for help."
        return "Press e to edit. Paste with Ctrl+Shift+V. Left arrow goes back. ? for help."

    def help_notes(self) -> list[str]:
        """Return the notes under the keys."""
        return ["Changes are saved in profiles.toml."]

    def help_keys(self) -> list[tuple[str, str]]:
        """Return the keys of this page."""
        return [
            ("e / enter", "Edit the selected variable"),
            ("ctrl+shift+v", "Paste in a value box. A terminal does not use Ctrl+V"),
            ("ctrl+r", "In the edit box of a key: show or hide the key"),
            ("left / esc", "Back to the profile list"),
            ("x", "Remove the selected variable (asks first)"),
            ("?", "Help"),
            ("q", "Quit"),
        ]

    def selected(self) -> Row | None:
        """Return the row under the cursor, or None."""
        table: DataTable[Text] = self.query_one(selector=DataTable)
        if not self.rows or table.cursor_row >= len(self.rows):
            return None
        return self.rows[table.cursor_row]

    def refresh_page(self) -> None:
        """Read the values again and redraw the table and the banner."""
        keep: Row | None = self.selected()
        self.rows = visible_rows(rows=resolve(settings_env=self.source.load(), environ={}))
        table: DataTable[Text] = self.query_one(selector=DataTable)
        table.clear()
        for row in self.rows:
            value: str = row.display
            table.add_row(
                Text(text=row.name, style="bold" if row.source != SOURCE_UNSET else "dim"),
                Text(text=value or "-", style="dim" if row.source == SOURCE_UNSET else ""),
                key=row.name,
            )
        names: list[str] = [r.name for r in self.rows]
        if keep is not None and keep.name in names:
            table.move_cursor(row=names.index(keep.name))
        self.draw_banner(lines=[("profile", self.source.name)])

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Edit the variable when Enter is pressed on a row."""
        self.action_edit()

    def on_page_table_back(self, event: PageTable.Back) -> None:
        """Go back to the profile list when the left arrow is pressed."""
        self.action_back()

    def action_back(self) -> None:
        """Go back to the profile list."""
        self.app.pop_screen()

    def save_values(self, updates: Mapping[str, str | None], done_message: str, name: str) -> None:
        """Save updates to the profile, show the result, and keep the cursor on the variable."""
        try:
            self.source.save(updates=updates)
        except (ProfileError, ValueError) as exc:
            self.set_status(message=str(exc), error=True)
            return
        self.refresh_page()
        table: DataTable[Text] = self.query_one(selector=DataTable)
        names: list[str] = [r.name for r in self.rows]
        if name in names:
            table.move_cursor(row=names.index(name))
        self.set_status(message=done_message)

    def action_edit(self) -> None:
        """Open the edit dialog for the selected variable and save the result."""
        row: Row | None = self.selected()
        if row is None:
            return

        def save_edited_value(value: str | None) -> None:
            """Save the new value. An empty value removes the variable."""
            if value is None:
                return
            self.save_values(
                updates={row.name: value or None},
                done_message=f"Saved {row.name}." if value else f"Removed {row.name}.",
                name=row.name,
            )

        if row.spec and row.spec.kind == CHOICE:
            options: list[tuple[str, str]] = [(choice, choice) for choice in row.spec.choices]
            options.append((REMOVE_CHOICE, "(remove)"))

            def save_chosen_value(choice: str | None) -> None:
                """Save the chosen value. The remove entry removes the variable."""
                if choice is not None:
                    save_edited_value(value="" if choice == REMOVE_CHOICE else choice)

            self.app.push_screen(
                screen=PickScreen(title=f"{row.name} (now: {row.value or 'unset'})", options=options),
                callback=save_chosen_value,
            )
            return
        self.app.push_screen(screen=EditScreen(row=row), callback=save_edited_value)

    def action_remove(self) -> None:
        """Remove the selected variable after a yes."""
        row: Row | None = self.selected()
        if row is None or row.source in (SOURCE_UNSET, SOURCE_ENV):
            return
        shown: str = row.display
        question: str = f"Remove {row.name} (value: {shown or '-'}) from profile '{self.source.name}'?"

        def remove_when_confirmed(confirmed: bool | None) -> None:
            """Remove the variable only after a yes."""
            if not confirmed:
                self.set_status(message="Nothing removed.")
                return
            self.save_values(updates={row.name: None}, done_message=f"Removed {row.name}.", name=row.name)

        self.app.push_screen(
            screen=ConfirmScreen(title="Remove variable", question=question, hint=""),
            callback=remove_when_confirmed,
        )
