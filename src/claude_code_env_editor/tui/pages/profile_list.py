"""The main page: your profiles."""

from __future__ import annotations

from typing import ClassVar

from rich.text import Text
from textual import work
from textual.binding import Binding, BindingType
from textual.widgets import DataTable

from claude_code_env_editor import config
from claude_code_env_editor.profiles import (
    NAME_PATTERN,
    Profile,
    ProfileError,
    load_profiles,
    rename_profile,
    save_profile,
    similar_name,
)
from claude_code_env_editor.tui.dialogs import InputScreen, TextScreen
from claude_code_env_editor.tui.pages.profile_actions import ProfileActionsPage
from claude_code_env_editor.tui.pages.table import PageTable
from claude_code_env_editor.tui.pages.variables import VariablesPage
from claude_code_env_editor.tui.pages.verify_view import render_checks
from claude_code_env_editor.verify import Check, Endpoint, verify


class ProfileListPage(ProfileActionsPage):
    """The main page: your profiles, and where each one is applied."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding(key="a", action="apply", description="apply"),
        Binding(key="c", action="copy", description="copy"),
        Binding(key="v", action="verify", description="verify"),
        Binding(key="n", action="new", description="new"),
        Binding(key="e", action="edit", description="edit"),
        Binding(key="x", action="delete", description="delete"),
        Binding(key="question_mark", action="help", description="help"),
        Binding(key="q", action="app.quit", description="quit"),
    ]

    def __init__(self) -> None:
        """Start with no profiles loaded."""
        super().__init__()
        self.profiles: dict[str, Profile] = {}
        self.names: list[str] = []

    def columns(self) -> tuple[str, ...]:
        """Return the column titles."""
        return ("Profile", "Endpoint", "Key")

    def start_message(self) -> str:
        """Return the first status text."""
        return "Right arrow opens a profile. a applies it. n makes a new one. ? for help."

    def help_keys(self) -> list[tuple[str, str]]:
        """Return the keys of this page."""
        return [
            ("right / enter", "Open the profile and see its variables"),
            ("a", "Apply the profile to a place you choose"),
            ("c", "Copy the profile under a new name"),
            ("v", "Verify the endpoint, the key, and the model of the profile"),
            ("n", "New profile from scratch"),
            ("e", "Edit the name of the profile"),
            ("x", "Delete the profile"),
            ("?", "Show this help"),
            ("q", "Quit"),
        ]

    def help_notes(self) -> list[str]:
        """Return the notes under the keys."""
        return ["Profiles are stored in profiles.toml.", "Apply writes the env block of the place that you choose."]

    def current_values(self) -> dict[str, str]:
        """Return the variables of the profile under the cursor."""
        name: str | None = self.selected_name()
        return dict(self.profiles[name].variables) if name is not None else {}

    def selected_name(self) -> str | None:
        """Return the name of the profile under the cursor, or None."""
        table: DataTable[Text] = self.query_one(selector=DataTable)
        if not self.names or table.cursor_row >= len(self.names):
            return None
        return self.names[table.cursor_row]

    def refresh_page(self) -> None:
        """Read the profiles and the places again, and redraw the list and the banner."""
        keep: str | None = self.selected_name()
        try:
            self.profiles = load_profiles()
        except ProfileError as exc:
            self.profiles = {}
            self.set_status(message=str(exc), error=True)
        self.names = list(self.profiles)
        table: DataTable[Text] = self.query_one(selector=DataTable)
        table.clear()
        for profile in self.profiles.values():
            table.add_row(
                Text(text=profile.name, style="bold"),
                Text(text=profile.host),
                Text(text="key" if profile.has_key else "no key", style="" if profile.has_key else "dim"),
                key=profile.name,
            )
        if keep and keep in self.names:
            table.move_cursor(row=self.names.index(keep))
        self.draw_banner(lines=[("profiles", str(len(self.profiles)))])

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open the profile when Enter is pressed on a row."""
        self.action_open()

    def on_page_table_forward(self, event: PageTable.Forward) -> None:
        """Open the profile when the right arrow is pressed."""
        self.action_open()

    def action_open(self) -> None:
        """Open the variables of the profile under the cursor."""
        name: str | None = self.selected_name()
        if name is None:
            return
        self.app.push_screen(VariablesPage(profile=self.profiles[name]))

    def action_apply(self) -> None:
        """Apply the profile under the cursor."""
        name: str | None = self.selected_name()
        if name is not None:
            self.begin_apply(name=name)

    def action_new(self) -> None:
        """Ask for a name, create an empty profile, and open it so that its variables can be set."""
        existing: set[str] = set(self.profiles)

        def check_name(text: str) -> str | None:
            """Return a message when the name is not usable."""
            if not NAME_PATTERN.match(text):
                return "Use letters, digits, '.', '-', and '_'. Start with a letter or a digit."
            if text in existing or similar_name(name=text, names=existing) is not None:
                return f"A profile named '{text}' exists. Use another name."
            return None

        def create(name: str | None) -> None:
            """Save the empty profile and open its variables."""
            if not name:
                return
            profile: Profile = Profile(name=name, variables={})
            try:
                save_profile(profile=profile)
            except (ProfileError, ValueError) as exc:
                self.set_status(message=str(exc), error=True)
                return
            self.refresh_page()
            table: PageTable = self.query_one(selector=PageTable)
            if name in self.names:
                table.move_cursor(row=self.names.index(name))
            self.app.push_screen(VariablesPage(profile=profile, fresh=True))

        self.app.push_screen(
            screen=InputScreen(
                title="New profile",
                prompt="Name for the new profile",
                check=check_name,
                placeholder="work-deepseek",
            ),
            callback=create,
        )

    def action_delete(self) -> None:
        """Delete the profile under the cursor."""
        name: str | None = self.selected_name()
        if name is not None:
            self.start_delete(name=name)

    def action_copy(self) -> None:
        """Copy the profile under the cursor and keep the cursor on the copy."""
        name: str | None = self.selected_name()
        if name is None:
            return

        def done(copy: Profile) -> None:
            """Show the copy in the list."""
            self.refresh_page()
            table: DataTable[Text] = self.query_one(selector=DataTable)
            if copy.name in self.names:
                table.move_cursor(row=self.names.index(copy.name))
            self.set_status(message=f"Copied '{name}' to '{copy.name}'.")

        self.start_copy(original=self.profiles[name], on_done=done)

    def action_edit(self) -> None:
        """Edit the name of the profile under the cursor."""
        name: str | None = self.selected_name()
        if name is None:
            return
        existing: set[str] = set(self.profiles)

        def check_name(text: str) -> str | None:
            """Return a message when the new name is not usable."""
            if not NAME_PATTERN.match(text):
                return "Use letters, digits, '.', '-', and '_'. Start with a letter or a digit."
            others: set[str] = existing - {name}
            if text in others or similar_name(name=text, names=others) is not None:
                return f"A profile named '{text}' exists. Use another name."
            return None

        def rename_to(new_name: str | None) -> None:
            """Rename the profile and keep the cursor on it."""
            if not new_name or new_name == name:
                return
            try:
                rename_profile(old=name, new=new_name)
            except ProfileError as exc:
                self.set_status(message=str(exc), error=True)
                return
            self.refresh_page()
            table: DataTable[Text] = self.query_one(selector=DataTable)
            if new_name in self.names:
                table.move_cursor(row=self.names.index(new_name))
            self.set_status(message=f"Renamed '{name}' to '{new_name}'.")

        self.app.push_screen(
            screen=InputScreen(
                title=f"Edit profile '{name}'",
                prompt="Profile name",
                check=check_name,
                placeholder=name,
            ),
            callback=rename_to,
        )

    # -- verify ------------------------------------------------------------

    def action_verify(self) -> None:
        """Open the verify dialog and start the checks in a thread."""
        endpoint: Endpoint = Endpoint.from_values(values=self.current_values())
        screen: TextScreen = TextScreen(
            title="Verify", body=Text(text=f"Sending requests to {endpoint.host} only...", style="dim")
        )
        self.app.push_screen(screen=screen)
        login_found: bool = config.has_login(config_dir=self.preferred.config_dir)
        self.run_verify(screen=screen, endpoint=endpoint, login_found=login_found)

    @work(thread=True)
    def run_verify(self, screen: TextScreen, endpoint: Endpoint, login_found: bool) -> None:
        """Run the checks in a worker thread. Show the result in the dialog."""
        checks: list[Check] = verify(endpoint=endpoint, login_found=login_found)
        try:
            self.app.call_from_thread(screen.update_body, render_checks(checks=checks, endpoint=endpoint))
        except RuntimeError:  # the app has closed while the checks ran
            return
