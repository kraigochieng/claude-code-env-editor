"""The two main pages: the profile list, and the variables of one profile or of the live settings file."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final, cast

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static

from claude_code_env_editor import __version__, config
from claude_code_env_editor.apply import ApplyPlan, Mode, format_plan, plan_apply, secret_target_problem
from claude_code_env_editor.auth import describe, visible_rows
from claude_code_env_editor.destinations import (
    Destination,
    DestinationKind,
    applied_in,
    known_variables,
    login_destinations,
    project_destination,
    short_path,
)
from claude_code_env_editor.envvars import (
    BY_NAME,
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
    snapshot,
    templates,
)
from claude_code_env_editor.sources import FileSource, ProfileSource, VariableSource, matching_profile
from claude_code_env_editor.target import Target
from claude_code_env_editor.tui.dialogs import (
    OTHER_FILE,
    REMOVE_CHOICE,
    ConfirmScreen,
    EditScreen,
    InputScreen,
    PickScreen,
    TextScreen,
)
from claude_code_env_editor.verify import FAIL, PASS, SKIP, Check, Endpoint, verify

if TYPE_CHECKING:
    from claude_code_env_editor.tui.app import EnvEditorApp

SECRET_NAMES: Final[tuple[str, ...]] = ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY")
PROJECT_FOLDER: Final[str] = "__project__"


class BasePage(Screen[None]):
    """What both main pages share: the banner, the table, the status line, and the flows for the target file."""

    def __init__(self) -> None:
        """Secrets start hidden."""
        super().__init__()
        self.reveal: bool = False

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

    def current_values(self) -> dict[str, str]:
        """Return the values that Verify tests: the values of the page."""
        raise NotImplementedError

    # -- shared structure --------------------------------------------------

    @property
    def editor(self) -> EnvEditorApp:
        """Return the application, which holds the target."""
        return cast("EnvEditorApp", self.app)

    @property
    def target(self) -> Target:
        """Return the settings file that apply and save work on."""
        return self.editor.target

    def compose(self) -> ComposeResult:
        """Build the banner, the table, the status line, and the footer."""
        yield Static(id="banner")
        with Vertical(id="table-box"):
            yield DataTable(cursor_type="row", zebra_stripes=False)
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

    def draw_banner(self, profile_line: str, rows: list[Row]) -> None:
        """Draw the banner: version, file, profile, endpoint host, and expected auth."""
        values: dict[str, str] = {r.name: r.value for r in rows if r.value}
        t: Text = Text()
        t.append("* claude-code-env-editor", style="bold #d97757")
        t.append(f"  v{__version__}\n", style="dim")
        t.append("file        ", style="dim")
        t.append(f"{self.target.settings_file}\n")
        t.append("profile     ", style="dim")
        t.append(f"{profile_line}\n")
        t.append("endpoint    ", style="dim")
        t.append(f"{Endpoint.from_values(values=values).host}\n")
        t.append("auth        ", style="dim")
        t.append(describe(rows=rows))
        self.query_one(selector="#banner", expect_type=Static).update(t)

    def file_profile_line(self, env: Mapping[str, str]) -> str:
        """Return the banner text about which profile the target file matches."""
        try:
            match: Profile | None = matching_profile(env=env, profiles=load_profiles())
        except ProfileError:
            return "unknown (profiles.toml cannot be read)"
        if match is not None:
            return f"{match.name} (the file matches this profile)"
        if not any(name in BY_NAME for name in env):
            return "none (the file has no known variables)"
        return "none (the file has its own values)"

    def file_env(self) -> dict[str, str]:
        """Return the env block of the target file. Show an error and return {} when it cannot be read."""
        try:
            return config.load_env(settings_file=self.target.settings_file)
        except config.ConfigError as exc:
            self.set_status(message=str(exc), error=True)
            return {}

    # -- apply, save, delete (work on the target file and profiles.toml) ----

    def start_apply(self, name: str, mode: Mode) -> None:
        """Show what the profile changes in the target file and write it after a yes."""
        try:
            profile: Profile = get_profile(name=name)
            current: dict[str, str] = config.load_env(settings_file=self.target.settings_file)
        except (ProfileError, config.ConfigError) as exc:
            self.set_status(message=str(exc), error=True)
            return
        problem: str | None = secret_target_problem(profile=profile, target=self.target)
        if problem:
            self.set_status(message=f"Refused: {problem}", error=True)
            return
        plan: ApplyPlan = plan_apply(profile=profile, current_env=current, mode=mode)
        if not plan.writes:
            self.set_status(message=f"Nothing to change: the file already matches '{name}'.")
            return
        lines: list[str] = format_plan(plan=plan, reveal=self.reveal, wrap=True)
        lines += [f"warning: {warning}" for warning in plan.warnings]
        if any(c.action == "remove" and c.name in SECRET_NAMES for c in plan.changes):
            lines.append("note: the key is removed because the endpoint changes. Set a new one with e.")

        def write_when_confirmed(confirmed: bool | None) -> None:
            """Write the plan only after a yes."""
            if not confirmed:
                self.set_status(message="Nothing written.")
                return
            try:
                config.update_env(settings_file=self.target.settings_file, updates=plan.updates())
            except config.ConfigError as exc:
                self.set_status(message=str(exc), error=True)
                return
            self.refresh_page()
            self.set_status(message=f"Applied '{name}' ({mode}). The old file is kept as .bak.")

        self.app.push_screen(
            screen=ConfirmScreen(
                title=f"Apply profile '{name}' ({mode} mode) to {self.target.settings_file.name}?",
                question="\n".join(lines),
                hint="The old file is kept as a .bak copy. Secrets are masked.",
            ),
            callback=write_when_confirmed,
        )

    def start_save(self) -> None:
        """Save the values of the target file as a profile."""
        self.save_values_as_profile(env=self.file_env(), source_name=self.target.settings_file.name)

    def save_values_as_profile(self, env: Mapping[str, str], source_name: str, suggested: str = "") -> None:
        """Ask for a name, then for the key question, then save the known values of env as a profile."""
        try:
            existing: set[str] = set(load_profiles())
        except ProfileError as exc:
            self.set_status(message=str(exc), error=True)
            return
        known: dict[str, str] = {k: v for k, v in env.items() if k in BY_NAME}
        if not known:
            self.set_status(message="There are no known variables to save. Set some first.", error=True)
            return

        def check_name(text: str) -> str | None:
            """Return a message when the name is not usable."""
            if not NAME_PATTERN.match(text):
                return "Use letters, digits, '.', '-', and '_'. Start with a letter or a digit."
            if text in existing:
                return f"A profile named '{text}' exists. Use another name, or delete it first."
            return None

        def got_name(name: str | None) -> None:
            """Continue with the key question when the values hold a key."""
            if not name:
                return
            if not any(BY_NAME[k].secret for k in known):
                self.save_snapshot(name=name, env=env, include_keys=True)
                return

            def got_key_answer(include: bool | None) -> None:
                """Save the profile with or without the key."""
                self.save_snapshot(name=name, env=env, include_keys=bool(include))

            self.app.push_screen(
                screen=ConfirmScreen(
                    title=f"Include the key in profile '{name}'?",
                    question="yes: one command switches endpoint and key together.\n"
                    "no: the profile holds no key. You set the key after each apply.",
                    hint="profiles.toml is a second plaintext copy of the key (mode 0600). Do not share it.",
                ),
                callback=got_key_answer,
            )

        self.app.push_screen(
            screen=InputScreen(
                title="Save the current values as a profile",
                prompt=f"Name for the profile (from {source_name})",
                check=check_name,
                placeholder=suggested or "work-deepseek",
            ),
            callback=got_name,
        )

    def save_snapshot(self, name: str, env: Mapping[str, str], include_keys: bool) -> None:
        """Write the profile and say so."""
        try:
            path: Path = save_profile(profile=snapshot(name=name, env=env, include_keys=include_keys))
        except (ProfileError, ValueError) as exc:
            self.set_status(message=str(exc), error=True)
            return
        self.refresh_page()
        self.set_status(message=f"Saved profile '{name}' in {path}.")

    def start_delete(self, name: str) -> None:
        """Ask, then delete one of your profiles."""

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

    # -- places ------------------------------------------------------------

    def known_destinations(self) -> list[Destination]:
        """Return the login folders, and the target file when it is not one of them."""
        places: list[Destination] = login_destinations()
        if self.target.settings_file not in [d.settings_file for d in places]:
            kind: DestinationKind = "login" if self.target.user_level else "project"
            places.append(
                Destination(
                    label=short_path(path=self.target.settings_file),
                    settings_file=self.target.settings_file,
                    kind=kind,
                    config_dir=self.target.config_dir,
                )
            )
        return places

    def pick_destination(self, title: str, on_chosen: Callable[[Destination], None]) -> None:
        """Let the user choose a login folder, or type a project folder, and pass the place to on_chosen."""
        places: list[Destination] = self.known_destinations()
        options: list[tuple[str, str]] = [(str(index), place.label) for index, place in enumerate(places)]
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

    # -- target ------------------------------------------------------------

    def action_switch_dir(self) -> None:
        """Open the list of config directories, with an entry for any other settings file."""
        dirs: list[Path] = config.discover_config_dirs()
        if self.target.config_dir not in dirs:
            dirs.insert(0, self.target.config_dir)
        options: list[tuple[str, str]] = [(str(d), str(d)) for d in dirs]
        options.append((OTHER_FILE, "(another settings file: type a path)"))

        def use_chosen(choice: str | None) -> None:
            """Switch to the chosen directory, or ask for a file path."""
            if choice is None:
                return
            if choice == OTHER_FILE:
                self.ask_for_file()
                return
            self.editor.target = Target.from_config_dir(config_dir=Path(choice))
            self.refresh_page()
            self.set_status(message=f"Config dir: {choice}")

        self.app.push_screen(screen=PickScreen(title="Switch config directory", options=options), callback=use_chosen)

    def ask_for_file(self) -> None:
        """Ask for the path of a settings file and make it the target."""

        def check_path(text: str) -> str | None:
            """Return a message when the path is not usable."""
            if not text:
                return "Type a path."
            if Path(text).expanduser().is_dir():
                return "That is a directory. Type the path of a settings file."
            return None

        def use_file(text: str | None) -> None:
            """Make the typed file the target."""
            if not text:
                return
            self.editor.target = Target.from_file(settings_file=Path(text), known_dirs=config.discover_config_dirs())
            self.refresh_page()
            kind: str = "user level" if self.target.user_level else "project file"
            self.set_status(message=f"File: {self.target.settings_file} ({kind})")

        self.app.push_screen(
            screen=InputScreen(
                title="Open a settings file",
                prompt="Path of a settings file, for example .claude/settings.local.json",
                check=check_path,
            ),
            callback=use_file,
        )

    # -- help and verify ---------------------------------------------------

    def action_help(self) -> None:
        """Open the help dialog with the keys of this page."""
        body: Text = Text()
        for key, text in self.help_keys():
            body.append(f"{key:<14}", style="bold #d97757")
            body.append(f"{text}\n")
        body.append("\nProfiles are stored in profiles.toml. Apply writes the env block of the file.\n", style="dim")
        body.append("settings.json wins over the shell environment.", style="dim")
        self.app.push_screen(screen=TextScreen(title="Help", body=body))

    def action_verify(self) -> None:
        """Open the verify dialog and start the checks in a thread."""
        endpoint: Endpoint = Endpoint.from_values(values=self.current_values())
        screen: TextScreen = TextScreen(
            title="Verify", body=Text(text=f"Sending requests to {endpoint.host} only...", style="dim")
        )
        self.app.push_screen(screen=screen)
        login_found: bool = config.has_login(config_dir=self.target.config_dir)
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


class ProfileListPage(BasePage):
    """The main page: the profiles, with a mark on the one that matches the target file."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding(key="a", action="apply", description="apply"),
        Binding(key="m", action="merge", description="merge"),
        Binding(key="n", action="new", description="new"),
        Binding(key="c", action="current", description="current file"),
        Binding(key="s", action="save", description="save"),
        Binding(key="r", action="rename", description="rename"),
        Binding(key="x", action="delete", description="delete"),
        Binding(key="d", action="switch_dir", description="file"),
        Binding(key="v", action="verify", description="verify"),
        Binding(key="question_mark", action="help", description="help"),
        Binding(key="q", action="app.quit", description="quit"),
    ]

    def __init__(self) -> None:
        """Start with no profiles loaded."""
        super().__init__()
        self.profiles: dict[str, Profile] = {}
        self.names: list[str] = []
        self.active: Profile | None = None

    def columns(self) -> tuple[str, ...]:
        """Return the column titles."""
        return ("Profile", "Endpoint", "Key", "Applied in", "Note")

    def start_message(self) -> str:
        """Return the first status text."""
        return "Enter opens a profile. a applies it. c opens the current file. ? for help."

    def help_keys(self) -> list[tuple[str, str]]:
        """Return the keys of this page."""
        return [
            ("enter", "Open the profile and see its variables"),
            ("a", "Apply the profile to the file (replace mode)"),
            ("m", "Apply the profile in merge mode"),
            ("n", "New profile: from a template, from a folder, or a copy"),
            ("c", "Open the current values of the file"),
            ("s", "Save the current values of the file as a profile"),
            ("r", "Rename the profile"),
            ("x", "Delete the profile"),
            ("d", "Switch the config directory, or open another settings file"),
            ("v", "Verify the endpoint of the file"),
            ("?", "Show this help"),
            ("q", "Quit"),
        ]

    def current_values(self) -> dict[str, str]:
        """Return the values that Claude Code uses now, from the file."""
        rows: list[Row] = resolve(settings_env=self.file_env(), environ=os.environ)
        return {r.name: r.value for r in rows if r.value}

    def selected_name(self) -> str | None:
        """Return the name of the profile under the cursor, or None."""
        table: DataTable[Text] = self.query_one(selector=DataTable)
        if not self.names or table.cursor_row >= len(self.names):
            return None
        return self.names[table.cursor_row]

    def refresh_page(self) -> None:
        """Read the profiles and the file again, and redraw the list and the banner."""
        keep: str | None = self.selected_name()
        try:
            self.profiles = load_profiles()
        except ProfileError as exc:
            self.profiles = {}
            self.set_status(message=str(exc), error=True)
        env: dict[str, str] = self.file_env()
        self.active = matching_profile(env=env, profiles=self.profiles)
        self.names = list(self.profiles)
        where: dict[str, list[Destination]] = applied_in(
            profiles=self.profiles, destinations=self.known_destinations()
        )
        table: DataTable[Text] = self.query_one(selector=DataTable)
        table.clear()
        for profile in self.profiles.values():
            mark: str = " *" if self.active is not None and profile.name == self.active.name else ""
            table.add_row(
                Text(text=f"{profile.name}{mark}", style="bold"),
                Text(text=profile.host),
                Text(text="key" if profile.has_key else "no key", style="" if profile.has_key else "dim"),
                Text(text=", ".join(d.label for d in where.get(profile.name, [])) or "-", style="#7fb069"),
                Text(text=profile.note, style="dim"),
                key=profile.name,
            )
        if keep and keep in self.names:
            table.move_cursor(row=self.names.index(keep))
        rows: list[Row] = visible_rows(rows=resolve(settings_env=env, environ=os.environ))
        self.draw_banner(profile_line=self.file_profile_line(env=env), rows=rows)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open the profile when Enter is pressed on a row."""
        self.action_open()

    def action_open(self) -> None:
        """Open the variables of the profile under the cursor."""
        name: str | None = self.selected_name()
        if name is None:
            return
        self.app.push_screen(VariablesPage(source=ProfileSource(profile=self.profiles[name])))

    def action_current(self) -> None:
        """Open the variables of the live settings file."""
        self.app.push_screen(VariablesPage(source=FileSource(settings_file=self.target.settings_file)))

    def action_apply(self) -> None:
        """Apply the profile under the cursor in replace mode."""
        name: str | None = self.selected_name()
        if name is not None:
            self.start_apply(name=name, mode="replace")

    def action_merge(self) -> None:
        """Apply the profile under the cursor in merge mode."""
        name: str | None = self.selected_name()
        if name is not None:
            self.start_apply(name=name, mode="merge")

    def action_save(self) -> None:
        """Save the values of the file as a new profile."""
        self.start_save()

    def action_new(self) -> None:
        """Start a new profile from a template, from a folder, or as a copy of a profile."""
        options: list[tuple[str, str]] = [
            ("template", "From a template"),
            ("folder", "Import the values of a folder"),
            ("copy", "Copy a profile"),
        ]

        def chosen(choice: str | None) -> None:
            """Go on with the chosen source."""
            if choice == "template":
                self.new_from_template()
            elif choice == "folder":
                self.pick_destination(title="Import from which place?", on_chosen=self.new_from_destination)
            elif choice == "copy":
                self.new_from_copy()

        self.app.push_screen(screen=PickScreen(title="New profile", options=options), callback=chosen)

    def new_from_template(self) -> None:
        """Pick a template, then name the new profile."""
        available: dict[str, Profile] = templates()
        options: list[tuple[str, str]] = [(name, f"{name:<14} {p.note}") for name, p in available.items()]

        def chosen(name: str | None) -> None:
            """Ask for the name of the new profile."""
            if name is not None:
                self.save_values_as_profile(
                    env=available[name].variables, source_name=f"template {name}", suggested=name
                )

        self.app.push_screen(screen=PickScreen(title="Which template?", options=options), callback=chosen)

    def new_from_copy(self) -> None:
        """Pick one of your profiles, then name the copy."""
        options: list[tuple[str, str]] = [(name, f"{name:<20} {p.host}") for name, p in self.profiles.items()]

        def chosen(name: str | None) -> None:
            """Ask for the name of the copy."""
            if name is not None:
                self.save_values_as_profile(
                    env=self.profiles[name].variables, source_name=f"profile {name}", suggested=f"{name}-copy"
                )

        self.app.push_screen(screen=PickScreen(title="Copy which profile?", options=options), callback=chosen)

    def new_from_destination(self, place: Destination) -> None:
        """Import the known values of a place as a new profile."""
        values: dict[str, str] | None = known_variables(destination=place)
        if values is None:
            self.set_status(message=f"{place.label} cannot be read.", error=True)
            return
        if not values:
            self.set_status(message=f"{place.label} has no known variables to import.", error=True)
            return
        self.save_values_as_profile(env=values, source_name=place.label)

    def action_delete(self) -> None:
        """Delete the profile under the cursor."""
        name: str | None = self.selected_name()
        if name is not None:
            self.start_delete(name=name)

    def action_rename(self) -> None:
        """Ask for a new name for the profile under the cursor."""
        name: str | None = self.selected_name()
        if name is None:
            return
        existing: set[str] = set(self.profiles)

        def check_name(text: str) -> str | None:
            """Return a message when the new name is not usable."""
            if not NAME_PATTERN.match(text):
                return "Use letters, digits, '.', '-', and '_'. Start with a letter or a digit."
            if text != name and text in existing:
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
                title=f"Rename profile '{name}'",
                prompt="New name",
                check=check_name,
                placeholder=name,
            ),
            callback=rename_to,
        )


class VariablesPage(BasePage):
    """The variables of one profile, or of the live settings file."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding(key="e", action="edit", description="edit"),
        Binding(key="x", action="remove", description="remove"),
        Binding(key="r", action="reveal", description="reveal"),
        Binding(key="a", action="apply", description="apply"),
        Binding(key="m", action="merge", description="merge"),
        Binding(key="c", action="copy", description="copy"),
        Binding(key="s", action="save", description="save"),
        Binding(key="d", action="switch_dir", description="file"),
        Binding(key="v", action="verify", description="verify"),
        Binding(key="escape", action="back", description="back"),
        Binding(key="question_mark", action="help", description="help"),
        Binding(key="q", action="app.quit", description="quit"),
    ]

    def __init__(self, source: VariableSource) -> None:
        """Keep the source of the variables."""
        super().__init__()
        self.source: VariableSource = source
        self.rows: list[Row] = []

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Hide the keys that do not fit: profile actions on the file page, and save on a profile page."""
        if action in ("apply", "merge", "copy") and self.source.kind != "profile":
            return False
        if action == "save" and self.source.kind != "file":
            return False
        return True

    def columns(self) -> tuple[str, ...]:
        """Return the column titles."""
        return ("Variable", "Value", "Source")

    def start_message(self) -> str:
        """Return the first status text."""
        return "Press e to edit. Paste with Ctrl+Shift+V. Press ? for help."

    def help_keys(self) -> list[tuple[str, str]]:
        """Return the keys of this page."""
        keys: list[tuple[str, str]] = [
            ("e / enter", "Edit the selected variable"),
            ("ctrl+shift+v", "Paste in a value box. A terminal does not use Ctrl+V"),
            ("x", "Remove the selected variable (asks first)"),
            ("r", "Reveal or hide secret values"),
            ("v", "Verify the endpoint, the key, and the model"),
        ]
        if self.source.kind == "profile":
            keys += [
                ("a / m", "Apply this profile to the file (replace or merge)"),
                ("c", "Copy this profile under a new name"),
            ]
        else:
            keys.append(("s", "Save these values as a profile"))
        keys += [("d", "Switch the file"), ("esc", "Back to the profile list"), ("?", "Help"), ("q", "Quit")]
        return keys

    def current_values(self) -> dict[str, str]:
        """Return the values on the page."""
        return {r.name: r.value for r in self.rows if r.value}

    def selected(self) -> Row | None:
        """Return the row under the cursor, or None."""
        table: DataTable[Text] = self.query_one(selector=DataTable)
        if not self.rows or table.cursor_row >= len(self.rows):
            return None
        return self.rows[table.cursor_row]

    def refresh_page(self) -> None:
        """Read the values again and redraw the table and the banner."""
        keep: Row | None = self.selected()
        is_file: bool = self.source.kind == "file"
        try:
            values: dict[str, str] = self.source.load()
        except (config.ConfigError, ProfileError) as exc:
            values = {}
            self.set_status(message=str(exc), error=True)
        environ: Mapping[str, str] = os.environ if is_file else {}
        self.rows = visible_rows(rows=resolve(settings_env=values, environ=environ))
        table: DataTable[Text] = self.query_one(selector=DataTable)
        table.clear()
        for row in self.rows:
            value: str = row.value if self.reveal else row.display
            label: str = row.source
            if not is_file:
                label = "profile" if row.source == "settings" else "unset"
            elif row.shell_value:
                label = f"{row.source} (shell differs)"
            table.add_row(
                Text(text=row.name, style="bold" if row.source != SOURCE_UNSET else "dim"),
                Text(text=value or "-", style="dim" if row.source == SOURCE_UNSET else ""),
                Text(text=label, style="#d97757" if row.source != SOURCE_UNSET else "dim"),
                key=row.name,
            )
        if keep is not None and keep.name in [r.name for r in self.rows]:
            table.move_cursor(row=[r.name for r in self.rows].index(keep.name))
        if is_file:
            profile_line: str = self.file_profile_line(env=values)
        else:
            profile_line = self.source.name
        self.draw_banner(profile_line=profile_line, rows=self.rows)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Edit the variable when Enter is pressed on a row."""
        self.action_edit()

    def action_back(self) -> None:
        """Go back to the profile list."""
        self.app.pop_screen()

    def action_reveal(self) -> None:
        """Toggle between masked and full secret values."""
        self.reveal = not self.reveal
        self.refresh_page()
        self.set_status(message="Secrets are visible." if self.reveal else "Secrets are hidden.")

    def save_values(self, updates: Mapping[str, str | None], done_message: str, name: str) -> None:
        """Save updates to the source, show the result, and keep the cursor on the variable."""
        try:
            self.source.save(updates=updates)
        except (config.ConfigError, ProfileError, ValueError) as exc:
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
        if row is None or row.source == SOURCE_UNSET:
            return
        if row.source == SOURCE_ENV:
            self.set_status(
                message=f"{row.name} is in your shell, not in settings.json. The tool cannot remove it.", error=True
            )
            return
        shown: str = row.value if self.reveal else row.display
        where: str = "settings.json" if self.source.kind == "file" else f"profile '{self.source.name}'"
        question: str = f"Remove {row.name} (value: {shown or '-'}) from {where}?"

        def remove_when_confirmed(confirmed: bool | None) -> None:
            """Remove the variable only after a yes."""
            if not confirmed:
                self.set_status(message="Nothing removed.")
                return
            hint: str = " The old file is kept as settings.json.bak." if self.source.kind == "file" else ""
            self.save_values(updates={row.name: None}, done_message=f"Removed {row.name}.{hint}", name=row.name)

        self.app.push_screen(
            screen=ConfirmScreen(
                title="Remove variable",
                question=question,
                hint="The old file is kept as settings.json.bak." if self.source.kind == "file" else "",
            ),
            callback=remove_when_confirmed,
        )

    def action_apply(self) -> None:
        """Apply this profile to the target file in replace mode."""
        self.start_apply(name=self.source.name, mode="replace")

    def action_merge(self) -> None:
        """Apply this profile to the target file in merge mode."""
        self.start_apply(name=self.source.name, mode="merge")

    def action_save(self) -> None:
        """Save the values of the file as a new profile."""
        self.start_save()

    def action_copy(self) -> None:
        """Copy this profile under a new name and open the copy."""
        if not isinstance(self.source, ProfileSource):
            return
        original: Profile = self.source.profile
        try:
            existing: set[str] = set(load_profiles())
        except ProfileError as exc:
            self.set_status(message=str(exc), error=True)
            return

        def check_name(text: str) -> str | None:
            """Return a message when the name is not usable."""
            if not NAME_PATTERN.match(text):
                return "Use letters, digits, '.', '-', and '_'. Start with a letter or a digit."
            if text in existing:
                return f"A profile named '{text}' exists. Use another name."
            return None

        def copy_to(name: str | None) -> None:
            """Save the copy and open it."""
            if not name:
                return
            copy: Profile = Profile(name=name, variables=dict(original.variables), note=original.note)
            try:
                save_profile(profile=copy)
            except (ProfileError, ValueError) as exc:
                self.set_status(message=str(exc), error=True)
                return
            self.source = ProfileSource(profile=copy)
            self.refresh_page()
            self.set_status(message=f"Copied to '{name}'. You can edit it now.")

        self.app.push_screen(
            screen=InputScreen(
                title=f"Copy profile '{original.name}'",
                prompt="Name for the copy",
                check=check_name,
                placeholder=f"{original.name}-copy",
            ),
            callback=copy_to,
        )
