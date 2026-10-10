"""Full-screen interface in the style of Claude Code."""

from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar, Final

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Input, OptionList, Static
from textual.widgets.option_list import Option

from claude_code_env_editor import __version__, config
from claude_code_env_editor.auth import describe, visible_rows
from claude_code_env_editor.envvars import (
    CHOICE,
    SOURCE_ENV,
    SOURCE_UNSET,
    Row,
    VarSpec,
    resolve,
    validate,
)
from claude_code_env_editor.presets import Preset, load_presets, preset_values
from claude_code_env_editor.target import Target
from claude_code_env_editor.verify import FAIL, PASS, SKIP, Check, Endpoint, verify

REMOVE_CHOICE: Final[str] = "__remove__"
PASTE_HINT: Final[str] = "Paste with Ctrl+Shift+V (Ctrl+V does not work in a terminal)."

HELP_KEYS: Final[tuple[tuple[str, str], ...]] = (
    ("e / enter", "Edit the selected variable"),
    ("ctrl+shift+v", "Paste in a value box. A terminal does not use Ctrl+V"),
    ("v", "Verify the endpoint, the key, and the model"),
    ("r", "Reveal or hide secret values"),
    ("p", "Apply a preset endpoint"),
    ("d", "Switch the Claude Code config directory"),
    ("x", "Remove the selected variable from settings.json"),
    ("?", "Show this help"),
    ("q", "Quit"),
)


class EditScreen(ModalScreen[str | None]):
    """Dialog to type a new value for one variable."""
    BINDINGS: ClassVar[list[BindingType]] = [Binding(key="escape", action="cancel", description="Cancel")]

    def __init__(self, row: Row) -> None:
        """Keep the row to edit."""
        super().__init__()
        self.row = row

    def compose(self) -> ComposeResult:
        """Build the dialog: name, help text, input, error line, hint."""
        spec: VarSpec | None = self.row.spec
        with Vertical(classes="dialog"):
            yield Static(self.row.name, classes="heading")
            yield Static(spec.help if spec else "Custom variable.")
            yield Input(
                value=self.row.value,
                placeholder=spec.example if spec else "",
                password=self.row.secret,
                id="value",
            )
            yield Static("", id="error", classes="fail")
            yield Static(PASTE_HINT, id="paste-hint", classes="hint")
            yield Static("enter save  -  esc cancel  -  empty value removes the key", classes="hint")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Check the typed value. Close the dialog when it is good, else show the error."""
        value: str = event.value.strip()
        if value and self.row.spec and (err := validate(spec=self.row.spec, value=value)):
            self.query_one(selector="#error", expect_type=Static).update(err)
            return
        self.dismiss(result=value)

    def action_cancel(self) -> None:
        """Close the dialog without a change."""
        self.dismiss(result=None)


class ConfirmScreen(ModalScreen[bool]):
    """Dialog that asks a yes or no question. It returns True for yes."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding(key="y,enter", action="yes", description="Yes"),
        Binding(key="n,escape", action="no", description="No"),
    ]

    def __init__(self, title: str, question: str, hint: str) -> None:
        """Keep the title, the question, and the hint text."""
        super().__init__()
        self.title_text: str = title
        self.question: str = question
        self.hint_text: str = hint

    def compose(self) -> ComposeResult:
        """Build the dialog: title, question, key hints."""
        with Vertical(classes="dialog"):
            yield Static(self.title_text, classes="heading")
            yield Static(self.question, id="question")
            yield Static("y or enter: yes  -  n or esc: no", classes="hint")
            yield Static(self.hint_text, classes="hint")

    def action_yes(self) -> None:
        """Close the dialog with yes."""
        self.dismiss(result=True)

    def action_no(self) -> None:
        """Close the dialog with no."""
        self.dismiss(result=False)


class PickScreen(ModalScreen[str | None]):
    """Dialog to choose one item from a list."""
    BINDINGS: ClassVar[list[BindingType]] = [Binding(key="escape", action="cancel", description="Cancel")]

    def __init__(self, title: str, options: list[tuple[str, str]]) -> None:
        """Keep the title and the (id, label) options."""
        super().__init__()
        self.title_text, self.options = title, options

    def compose(self) -> ComposeResult:
        """Build the dialog: title, option list, hint."""
        with Vertical(classes="dialog"):
            yield Static(self.title_text, classes="heading")
            yield OptionList(*[Option(label, id=key) for key, label in self.options])
            yield Static("enter choose  -  esc cancel", classes="hint")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Close the dialog and return the id of the chosen option."""
        self.dismiss(result=event.option.id)

    def action_cancel(self) -> None:
        """Close the dialog without a choice."""
        self.dismiss(result=None)


class TextScreen(ModalScreen[None]):
    """Dialog that shows read-only text."""
    BINDINGS: ClassVar[list[BindingType]] = [Binding(key="escape", action="close", description="Close"), Binding(key="enter", action="close", description="Close")]

    def __init__(self, title: str, body: Text) -> None:
        """Keep the title and the text to show."""
        super().__init__()
        self.title_text, self.body = title, body

    def compose(self) -> ComposeResult:
        """Build the dialog: title, text, hint."""
        with Vertical(classes="dialog"):
            yield Static(self.title_text, classes="heading")
            yield Static(self.body, id="body")
            yield Static("esc close", classes="hint")

    def action_close(self) -> None:
        """Close the dialog."""
        self.dismiss(result=None)

    def update_body(self, body: Text) -> None:
        """Replace the text in the open dialog. Do nothing when the dialog is already closed."""
        try:
            self.query_one(selector="#body", expect_type=Static).update(body)
        except NoMatches:
            return


class EnvEditorApp(App[None]):
    """The main screen: a table of variables and the actions on them."""
    CSS_PATH: ClassVar[str] = "styles.tcss"
    ENABLE_COMMAND_PALETTE: ClassVar[bool] = False
    TITLE: str = "claude-code-env-editor"
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding(key="e,enter", action="edit", description="edit"),
        Binding(key="v", action="verify", description="verify"),
        Binding(key="r", action="reveal", description="reveal"),
        Binding(key="p", action="preset", description="preset"),
        Binding(key="d", action="switch_dir", description="dir"),
        Binding(key="x", action="remove", description="remove"),
        Binding(key="question_mark", action="help", description="help"),
        Binding(key="q", action="quit", description="quit"),
    ]

    def __init__(self, config_dir: Path) -> None:
        """Keep the config directory. Secrets start hidden."""
        super().__init__()
        self.target: Target = Target.from_config_dir(config_dir=config_dir)
        self.reveal = False
        self.rows: list[Row] = []

    def compose(self) -> ComposeResult:
        """Build the banner, the table, the status line, and the footer."""
        yield Static(id="banner")
        with Vertical(id="table-box"):
            yield DataTable(cursor_type="row", zebra_stripes=False)
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        """Create the table columns and fill the rows."""
        table: DataTable[Text] = self.query_one(selector=DataTable)
        table.add_columns("Variable", "Value", "Source")
        self.refresh_rows()
        self.set_status(message="Press e to edit. Paste with Ctrl+Shift+V. Press ? for help.")
        table.focus()

    # -- data ---------------------------------------------------------------

    def refresh_rows(self, keep: str | None = None) -> None:
        """Read the variables again and redraw the table. Keep the cursor on the row named keep."""
        try:
            self.rows = visible_rows(
                rows=resolve(settings_env=config.load_env(settings_file=self.target.settings_file), environ=os.environ)
            )
        except config.ConfigError as exc:
            self.rows = []
            self.set_status(message=str(exc), error=True)
        table: DataTable[Text] = self.query_one(selector=DataTable)
        table.clear()
        for row in self.rows:
            value: str = row.value if self.reveal else row.display
            style: str = "dim" if row.source == SOURCE_UNSET else ""
            table.add_row(
                Text(text=row.name, style="bold" if row.source != SOURCE_UNSET else "dim"),
                Text(text=value or "-", style=style),
                Text(
                    text=f"{row.source} (shell differs)" if row.shell_value else row.source,
                    style="#d97757" if row.source != SOURCE_UNSET else "dim",
                ),
                key=row.name,
            )
        if keep:
            names: list[str] = [r.name for r in self.rows]
            if keep in names:
                table.move_cursor(row=names.index(keep))
        self.query_one(selector="#banner", expect_type=Static).update(self._banner())

    def _endpoint(self) -> Endpoint:
        """Build the endpoint from the values now in the table."""
        return Endpoint.from_values(values={r.name: r.value for r in self.rows if r.value})

    def _banner(self) -> Text:
        """Build the banner text: version, config directory, and endpoint host."""
        t: Text = Text()
        t.append("* claude-code-env-editor", style="bold #d97757")
        t.append(f"  v{__version__}\n", style="dim")
        t.append("config dir  ", style="dim")
        t.append(f"{self.target.config_dir}\n")
        t.append("endpoint    ", style="dim")
        t.append(f"{self._endpoint().host}\n")
        t.append("auth        ", style="dim")
        t.append(describe(rows=self.rows))
        return t

    def set_status(self, message: str, error: bool = False) -> None:
        """Show a message on the status line. Use red for an error."""
        self.query_one(selector="#status", expect_type=Static).update(Text(text=message, style="#e5534b" if error else "dim"))

    def selected(self) -> Row | None:
        """Return the row under the cursor, or None."""
        table: DataTable[Text] = self.query_one(selector=DataTable)
        if not self.rows or table.cursor_row >= len(self.rows):
            return None
        return self.rows[table.cursor_row]

    # -- actions ------------------------------------------------------------

    def action_edit(self) -> None:
        """Open the edit dialog for the selected variable and save the result."""
        row: Row | None = self.selected()
        if row is None:
            return

        def save_edited_value(value: str | None) -> None:
            """Save the new value. An empty value removes the key."""
            if value is None:
                return
            try:
                config.update_env(settings_file=self.target.settings_file, updates={row.name: value or None})
            except config.ConfigError as exc:
                self.set_status(message=str(exc), error=True)
                return
            self.refresh_rows(keep=row.name)
            self.set_status(message=f"Saved {row.name}." if value else f"Removed {row.name}.")

        if row.spec and row.spec.kind == CHOICE:
            options: list[tuple[str, str]] = [(choice, choice) for choice in row.spec.choices]
            options.append((REMOVE_CHOICE, "(remove from settings.json)"))

            def save_chosen_value(choice: str | None) -> None:
                """Save the chosen value. The remove entry removes the key."""
                if choice is not None:
                    save_edited_value(value="" if choice == REMOVE_CHOICE else choice)

            self.push_screen(
                screen=PickScreen(title=f"{row.name} (now: {row.value or 'unset'})", options=options),
                callback=save_chosen_value,
            )
            return
        self.push_screen(screen=EditScreen(row=row), callback=save_edited_value)

    def action_remove(self) -> None:
        """Remove the selected variable from settings.json."""
        row: Row | None = self.selected()
        if row is None or row.source == SOURCE_UNSET:
            return
        if row.source == SOURCE_ENV:
            self.set_status(message=f"{row.name} is in your shell, not in settings.json. The tool cannot remove it.", error=True)
            return
        shown: str = row.value if self.reveal else row.display
        question: str = f"Remove {row.name} (value: {shown or '-'}) from settings.json?"

        def remove_when_confirmed(confirmed: bool | None) -> None:
            """Remove the variable only after a yes."""
            if not confirmed:
                self.set_status(message="Nothing removed.")
                return
            config.update_env(settings_file=self.target.settings_file, updates={row.name: None})
            self.refresh_rows(keep=row.name)
            self.set_status(message=f"Removed {row.name}. The old file is kept as settings.json.bak.")

        self.push_screen(
            screen=ConfirmScreen(
                title="Remove variable",
                question=question,
                hint="The old file is kept as settings.json.bak.",
            ),
            callback=remove_when_confirmed,
        )

    def action_reveal(self) -> None:
        """Toggle between masked and full secret values."""
        self.reveal = not self.reveal
        row: Row | None = self.selected()
        self.refresh_rows(keep=row.name if row else None)
        self.set_status(message="Secrets are visible." if self.reveal else "Secrets are hidden.")

    def action_preset(self) -> None:
        """Open the preset list and apply the chosen preset."""
        presets: dict[str, Preset] = load_presets()
        options: list[tuple[str, str]] = [(pid, f"{preset.label:<24} {preset.base_url}") for pid, preset in presets.items()]

        def apply_chosen_preset(pid: str | None) -> None:
            """Write the preset values to settings.json."""
            if not pid:
                return
            values: dict[str, str] = preset_values(preset_id=pid)
            config.update_env(settings_file=self.target.settings_file, updates=values)
            self.refresh_rows()
            self.set_status(message=f"Applied preset '{pid}'. Set ANTHROPIC_AUTH_TOKEN next if it is empty.")

        self.push_screen(screen=PickScreen(title="Apply a preset", options=options), callback=apply_chosen_preset)

    def action_switch_dir(self) -> None:
        """Open the config directory list and switch to the chosen one."""
        dirs: list[Path] = config.discover_config_dirs()
        if self.target.config_dir not in dirs:
            dirs.insert(0, self.target.config_dir)
        options: list[tuple[str, str]] = [(str(d), str(d)) for d in dirs]

        def use_chosen_dir(choice: str | None) -> None:
            """Switch to the chosen config directory."""
            if choice:
                self.target = Target.from_config_dir(config_dir=Path(choice))
                self.refresh_rows()
                self.set_status(message=f"Config dir: {choice}")

        self.push_screen(screen=PickScreen(title="Switch config directory", options=options), callback=use_chosen_dir)

    def action_help(self) -> None:
        """Open the help screen with the keys."""
        body: Text = Text()
        for key, text in HELP_KEYS:
            body.append(f"{key:<12}", style="bold #d97757")
            body.append(f"{text}\n")
        body.append("\nThe tool writes to the env block of settings.json in the config dir.\n", style="dim")
        body.append("settings.json wins over the shell environment.", style="dim")
        self.push_screen(screen=TextScreen(title="Help", body=body))

    def action_verify(self) -> None:
        """Open the verify dialog and start the checks in a thread."""
        endpoint: Endpoint = self._endpoint()
        screen: TextScreen = TextScreen(title="Verify", body=Text(text=f"Sending requests to {endpoint.host} only...", style="dim"))
        self.push_screen(screen=screen)
        login_found: bool = config.has_login(config_dir=self.target.config_dir)
        self._run_verify(screen=screen, endpoint=endpoint, login_found=login_found)

    @work(thread=True)
    def _run_verify(self, screen: TextScreen, endpoint: Endpoint, login_found: bool) -> None:
        """Run the checks in a worker thread. Show the result in the dialog."""
        checks: list[Check] = verify(endpoint=endpoint, login_found=login_found)
        try:
            self.call_from_thread(screen.update_body, self._render_checks(checks=checks, endpoint=endpoint))
        except RuntimeError:  # the app has closed while the checks ran
            return

    @staticmethod
    def _render_checks(checks: list[Check], endpoint: Endpoint) -> Text:
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


def run(config_dir: Path) -> int:
    """Open the interface for one config directory."""
    EnvEditorApp(config_dir=config_dir).run()
    return 0
