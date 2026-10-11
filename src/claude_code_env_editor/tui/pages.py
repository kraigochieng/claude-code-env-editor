"""The two main pages: the profile list, and the variables of one profile."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final, cast

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static

from claude_code_env_editor import __version__, config
from claude_code_env_editor.apply import ApplyPlan, format_plan, plan_apply, secret_target_problem
from claude_code_env_editor.auth import visible_rows
from claude_code_env_editor.destinations import (
    Destination,
    DestinationKind,
    DestinationState,
    destination_state,
    login_destinations,
    project_destination,
    short_path,
)
from claude_code_env_editor.envvars import (
    CHOICE,
    SOURCE_ENV,
    SOURCE_UNSET,
    Row,
    resolve,
)
from claude_code_env_editor.profiles import (
    NAME_PATTERN,
    Profile,
    ProfileError,
    delete_profile,
    get_profile,
    load_profiles,
    rename_profile,
    save_profile,
    similar_name,
)
from claude_code_env_editor.sources import ProfileSource
from claude_code_env_editor.target import Target
from claude_code_env_editor.tui.dialogs import (
    REMOVE_CHOICE,
    ConfirmScreen,
    EditScreen,
    InputScreen,
    PickScreen,
    TextScreen,
    key_color,
)
from claude_code_env_editor.verify import FAIL, PASS, SKIP, Check, Endpoint, verify

if TYPE_CHECKING:
    from claude_code_env_editor.tui.app import EnvEditorApp

SECRET_NAMES: Final[tuple[str, ...]] = ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY")
PROJECT_FOLDER: Final[str] = "__project__"


class PageTable(DataTable[Text]):
    """A table whose right and left arrow keys move between pages: right goes forward, left goes back."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding(key="right", action="forward", show=False),
        Binding(key="left", action="back", show=False),
    ]

    class Forward(Message):
        """The user pressed the right arrow."""

    class Back(Message):
        """The user pressed the left arrow."""

    def action_forward(self) -> None:
        """Tell the page that the user wants to go forward."""
        self.post_message(self.Forward())

    def action_back(self) -> None:
        """Tell the page that the user wants to go back."""
        self.post_message(self.Back())


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

    # -- places ------------------------------------------------------------

    def known_destinations(self) -> list[Destination]:
        """Return the login folders. The place from --config-dir or --file comes first and is added if needed."""
        places: list[Destination] = login_destinations()
        files: list[Path] = [d.settings_file for d in places]
        if self.preferred.settings_file in files:
            places.insert(0, places.pop(files.index(self.preferred.settings_file)))
            return places
        kind: DestinationKind = "login" if self.preferred.user_level else "project"
        places.insert(
            0,
            Destination(
                label=short_path(path=self.preferred.settings_file),
                settings_file=self.preferred.settings_file,
                kind=kind,
                config_dir=self.preferred.config_dir,
            ),
        )
        return places

    def pick_destination(
        self, title: str, on_chosen: Callable[[Destination], None], profile: Profile | None = None
    ) -> None:
        """Let the user choose a login folder, or type a project folder, and pass the place to on_chosen.

        With a profile, each login folder shows the state of that profile in it.
        """
        places: list[Destination] = self.known_destinations()
        options: list[tuple[str, str]] = []
        for index, place in enumerate(places):
            state: str = ""
            if profile is not None:
                result: DestinationState = destination_state(profile=profile, destination=place)
                state = f"  {result.text}"
            options.append((str(index), f"{place.label}{state}"))
        options.append((PROJECT_FOLDER, "(a project folder: type its path)"))

        def chosen(choice: str | None) -> None:
            """Pass the chosen login folder on, or ask for the project folder."""
            if choice is None:
                return
            if choice != PROJECT_FOLDER:
                on_chosen(places[int(choice)])
                return

            def check_folder(text: str) -> str | None:
                """Return a message when the folder is not usable."""
                if not text:
                    return "Type the path of a project folder."
                if not Path(text).expanduser().is_dir():
                    return "That folder does not exist."
                return None

            def folder_typed(text: str | None) -> None:
                """Pass the project place on."""
                if text:
                    on_chosen(project_destination(folder=Path(text)))

            self.app.push_screen(
                screen=InputScreen(
                    title="Project folder",
                    prompt="Path of the project folder. The file is .claude/settings.local.json inside it.",
                    check=check_folder,
                ),
                callback=folder_typed,
            )

        self.app.push_screen(screen=PickScreen(title=title, options=options), callback=chosen)

    # -- apply -------------------------------------------------------------

    def begin_apply(self, name: str) -> None:
        """Ask where to apply the profile, then show the changes."""
        try:
            profile: Profile = get_profile(name=name)
        except ProfileError as exc:
            self.set_status(message=str(exc), error=True)
            return
        self.pick_destination(
            title=f"Apply '{name}' to which place?",
            profile=profile,
            on_chosen=lambda place: self.start_apply(profile=profile, destination=place),
        )

    def start_apply(self, profile: Profile, destination: Destination) -> None:
        """Show what the profile changes in the destination file and write it after a yes.

        The apply replaces the known variables, so nothing of the previous endpoint stays.
        """
        target: Target = destination.to_target()
        try:
            current: dict[str, str] = config.load_env(settings_file=target.settings_file)
        except config.ConfigError as exc:
            self.set_status(message=str(exc), error=True)
            return
        problem: str | None = secret_target_problem(profile=profile, target=target)
        if problem:
            self.set_status(message=f"Refused: {problem}", error=True)
            return
        plan: ApplyPlan = plan_apply(profile=profile, current_env=current, mode="replace")
        if not plan.writes:
            self.set_status(message=f"Nothing to change: {destination.label} already matches '{profile.name}'.")
            return
        lines: list[str] = format_plan(plan=plan, wrap=True)
        lines += [f"warning: {warning}" for warning in plan.warnings]
        if any(c.action == "remove" and c.name in SECRET_NAMES for c in plan.changes):
            lines.append("note: the key is removed because the endpoint changes. Set a new one in the profile.")

        def write_when_confirmed(confirmed: bool | None) -> None:
            """Write the plan only after a yes."""
            if not confirmed:
                self.set_status(message="Nothing written.")
                return
            try:
                config.update_env(settings_file=target.settings_file, updates=plan.updates())
            except config.ConfigError as exc:
                self.set_status(message=str(exc), error=True)
                return
            self.refresh_page()
            self.set_status(
                message=f"Applied '{profile.name}' to {destination.label}. The old file is kept as .bak."
            )

        self.app.push_screen(
            screen=ConfirmScreen(
                title=f"Apply '{profile.name}' to {destination.label}?",
                question="\n".join(lines),
                hint="The old file is kept as a .bak copy. Secrets are masked.",
            ),
            callback=write_when_confirmed,
        )

    # -- save, delete ------------------------------------------------------

    def start_delete(self, name: str) -> None:
        """Ask, then delete a profile."""

        def delete_when_confirmed(confirmed: bool | None) -> None:
            """Delete the profile only after a yes."""
            if not confirmed:
                self.set_status(message="Nothing deleted.")
                return
            try:
                delete_profile(name=name)
            except ProfileError as exc:
                self.set_status(message=str(exc), error=True)
                return
            self.refresh_page()
            self.set_status(message=f"Deleted profile '{name}'.")

        self.app.push_screen(
            screen=ConfirmScreen(
                title="Delete profile",
                question=f"Delete profile '{name}'? No settings file is changed.",
                hint="",
            ),
            callback=delete_when_confirmed,
        )

    # -- copy --------------------------------------------------------------

    def start_copy(self, original: Profile, on_done: Callable[[Profile], None]) -> None:
        """Ask for a name, save a copy of the profile under it, and pass the copy to on_done."""
        try:
            existing: set[str] = set(load_profiles())
        except ProfileError as exc:
            self.set_status(message=str(exc), error=True)
            return

        def check_name(text: str) -> str | None:
            """Return a message when the name is not usable."""
            if not NAME_PATTERN.match(text):
                return "Use letters, digits, '.', '-', and '_'. Start with a letter or a digit."
            if text in existing or similar_name(name=text, names=existing) is not None:
                return f"A profile named '{text}' exists. Use another name."
            return None

        def copy_to(name: str | None) -> None:
            """Save the copy."""
            if not name:
                return
            copy: Profile = Profile(name=name, variables=dict(original.variables), note=original.note)
            try:
                save_profile(profile=copy)
            except (ProfileError, ValueError) as exc:
                self.set_status(message=str(exc), error=True)
                return
            on_done(copy)

        self.app.push_screen(
            screen=InputScreen(
                title=f"Copy profile '{original.name}'",
                prompt="Name for the copy",
                check=check_name,
                placeholder=f"{original.name}-copy",
            ),
            callback=copy_to,
        )

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


class ProfileListPage(BasePage):
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
            self.app.call_from_thread(screen.update_body, self.render_checks(checks=checks, endpoint=endpoint))
        except RuntimeError:  # the app has closed while the checks ran
            return

    @staticmethod
    def render_checks(checks: list[Check], endpoint: Endpoint) -> Text:
        """Format the check results as text for the dialog."""
        body: Text = Text(text=f"Host: {endpoint.host}\n\n", style="dim")
        for c in checks:
            mark, style = {PASS: ("ok  ", "#7fb069"), FAIL: ("FAIL", "#e5534b")}.get(c.status, ("skip", "dim"))
            body.append(f"{mark}  ", style=style)
            body.append(f"{c.name:<12}")
            body.append(f"{c.detail}\n", style="dim")
        failed: bool = any(c.status == FAIL for c in checks)
        skipped: bool = any(c.status == SKIP for c in checks)
        verdict: str = "All checks passed."
        if failed:
            verdict = "Some checks failed."
        elif skipped:
            verdict = "No check failed. Some checks were skipped."
        body.append(f"\n{verdict}")
        return body


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
