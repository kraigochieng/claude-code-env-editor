"""Full-screen interface in the style of Claude Code."""

from __future__ import annotations

import os
from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Input, OptionList, Static
from textual.widgets.option_list import Option

from claude_code_env_editor import __version__, config
from claude_code_env_editor.envvars import SOURCE_UNSET, Row, mask, resolve, validate
from claude_code_env_editor.presets import load_presets, preset_values
from claude_code_env_editor.secrets import SecretStore
from claude_code_env_editor.verify import FAIL, PASS, Check, target_host, verify

HELP_KEYS = (
    ("e / enter", "Edit the selected variable"),
    ("v", "Verify the endpoint, the key, and the model"),
    ("r", "Reveal or hide secret values"),
    ("p", "Apply a preset endpoint"),
    ("d", "Switch the Claude Code config directory"),
    ("x", "Remove the selected variable from settings.json"),
    ("?", "Show this help"),
    ("q", "Quit"),
)


class EditScreen(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, row: Row) -> None:
        super().__init__()
        self.row = row

    def compose(self) -> ComposeResult:
        spec = self.row.spec
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
            yield Static("enter save  -  esc cancel  -  empty value removes the key", classes="hint")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if value and self.row.spec and (err := validate(self.row.spec, value)):
            self.query_one("#error", Static).update(err)
            return
        self.dismiss(value)

    def action_cancel(self) -> None:
        self.dismiss(None)


class PickScreen(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, title: str, options: list[tuple[str, str]]) -> None:
        super().__init__()
        self.title_text, self.options = title, options

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static(self.title_text, classes="heading")
            yield OptionList(*[Option(label, id=key) for key, label in self.options])
            yield Static("enter choose  -  esc cancel", classes="hint")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def action_cancel(self) -> None:
        self.dismiss(None)


class TextScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape", "close", "Close"), Binding("enter", "close", "Close")]

    def __init__(self, title: str, body: Text) -> None:
        super().__init__()
        self.title_text, self.body = title, body

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static(self.title_text, classes="heading")
            yield Static(self.body, id="body")
            yield Static("esc close", classes="hint")

    def action_close(self) -> None:
        self.dismiss(None)

    def update_body(self, body: Text) -> None:
        self.query_one("#body", Static).update(body)


class EnvEditorApp(App):
    CSS_PATH = "theme.tcss"
    TITLE = "claude-code-env-editor"
    BINDINGS = [
        Binding("e,enter", "edit", "edit"),
        Binding("v", "verify", "verify"),
        Binding("r", "reveal", "reveal"),
        Binding("p", "preset", "preset"),
        Binding("d", "switch_dir", "dir"),
        Binding("x", "remove", "remove"),
        Binding("question_mark", "help", "? help"),
        Binding("q", "quit", "quit"),
    ]

    def __init__(self, config_dir: Path) -> None:
        super().__init__()
        self.config_dir = config_dir
        self.reveal = False
        self.rows: list[Row] = []
        self._store: SecretStore | None = None

    def compose(self) -> ComposeResult:
        yield Static(id="banner")
        with Vertical(id="table-box"):
            yield DataTable(cursor_type="row", zebra_stripes=False)
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Variable", "Value", "Source")
        self.refresh_rows()
        table.focus()

    # -- data ---------------------------------------------------------------

    def refresh_rows(self, keep: str | None = None) -> None:
        try:
            self.rows = resolve(config.load_env(self.config_dir), os.environ)
        except config.ConfigError as exc:
            self.rows = []
            self.set_status(str(exc), error=True)
        table = self.query_one(DataTable)
        table.clear()
        for row in self.rows:
            value = row.value if self.reveal else row.display
            style = "dim" if row.source == SOURCE_UNSET else ""
            table.add_row(
                Text(row.name, style="bold" if row.source != SOURCE_UNSET else "dim"),
                Text(value or "-", style=style),
                Text(row.source, style="#d97757" if row.source != SOURCE_UNSET else "dim"),
                key=row.name,
            )
        if keep:
            names = [r.name for r in self.rows]
            if keep in names:
                table.move_cursor(row=names.index(keep))
        self.query_one("#banner", Static).update(self._banner())

    def _banner(self) -> Text:
        t = Text()
        t.append("* claude-code-env-editor", style="bold #d97757")
        t.append(f"  v{__version__}\n", style="dim")
        t.append("config dir  ", style="dim")
        t.append(f"{self.config_dir}\n")
        t.append("endpoint    ", style="dim")
        values = {r.name: r.value for r in self.rows if r.value}
        t.append(target_host(values))
        return t

    def set_status(self, message: str, error: bool = False) -> None:
        self.query_one("#status", Static).update(Text(message, style="#e5534b" if error else "dim"))

    def selected(self) -> Row | None:
        table = self.query_one(DataTable)
        if not self.rows or table.cursor_row >= len(self.rows):
            return None
        return self.rows[table.cursor_row]

    def secret_store(self) -> SecretStore:
        if self._store is None:
            self._store = SecretStore(passphrase=lambda: "")
        return self._store

    # -- actions ------------------------------------------------------------

    def action_edit(self) -> None:
        row = self.selected()
        if row is None:
            return
        if row.spec and not row.spec.writable:
            self.set_status(f"{row.name} selects the config directory. Use the d key.", error=True)
            return

        def done(value: str | None) -> None:
            if value is None:
                return
            try:
                config.update_env(self.config_dir, {row.name: value or None})
            except config.ConfigError as exc:
                self.set_status(str(exc), error=True)
                return
            if row.secret and value:
                self._remember_secret(row.name, value)
            self.refresh_rows(keep=row.name)
            self.set_status(f"Saved {row.name}." if value else f"Removed {row.name}.")

        self.push_screen(EditScreen(row), done)

    def _remember_secret(self, name: str, value: str) -> None:
        store = self.secret_store()
        if store.backend != "keyring":
            return  # the file vault needs a passphrase prompt. Use the CLI for that.
        try:
            store.set(f"{self.config_dir}:{name}", value)
        except Exception:  # keyring errors must not block the edit
            pass

    def action_remove(self) -> None:
        row = self.selected()
        if row is None or row.source == SOURCE_UNSET:
            return
        config.update_env(self.config_dir, {row.name: None})
        self.refresh_rows(keep=row.name)
        self.set_status(f"Removed {row.name} from settings.json.")

    def action_reveal(self) -> None:
        self.reveal = not self.reveal
        row = self.selected()
        self.refresh_rows(keep=row.name if row else None)
        self.set_status("Secrets are visible." if self.reveal else "Secrets are hidden.")

    def action_preset(self) -> None:
        presets = load_presets()
        options = [(pid, f"{body['label']:<24} {body['ANTHROPIC_BASE_URL']}") for pid, body in presets.items()]

        def done(pid: str | None) -> None:
            if not pid:
                return
            values = preset_values(pid)
            config.update_env(self.config_dir, values)
            self.refresh_rows()
            self.set_status(f"Applied preset '{pid}'. Set ANTHROPIC_AUTH_TOKEN next if it is empty.")

        self.push_screen(PickScreen("Apply a preset", options), done)

    def action_switch_dir(self) -> None:
        dirs = config.discover_config_dirs()
        if self.config_dir not in dirs:
            dirs.insert(0, self.config_dir)
        options = [(str(d), str(d)) for d in dirs]

        def done(choice: str | None) -> None:
            if choice:
                self.config_dir = Path(choice)
                self.refresh_rows()
                self.set_status(f"Config dir: {choice}")

        self.push_screen(PickScreen("Switch config directory", options), done)

    def action_help(self) -> None:
        body = Text()
        for key, text in HELP_KEYS:
            body.append(f"{key:<12}", style="bold #d97757")
            body.append(f"{text}\n")
        body.append("\nThe tool writes to the env block of settings.json in the config dir.\n", style="dim")
        body.append("The process environment wins over settings.json.", style="dim")
        self.push_screen(TextScreen("Help", body))

    def action_verify(self) -> None:
        values = {r.name: r.value for r in self.rows if r.value}
        screen = TextScreen("Verify", Text(f"Sending requests to {target_host(values)} only...", style="dim"))
        self.push_screen(screen)
        self._run_verify(screen, values)

    @work(thread=True)
    def _run_verify(self, screen: TextScreen, values: dict[str, str]) -> None:
        checks = verify(values)
        self.call_from_thread(screen.update_body, self._render_checks(checks, values))

    @staticmethod
    def _render_checks(checks: list[Check], values: dict[str, str]) -> Text:
        body = Text(f"Host: {target_host(values)}\n\n", style="dim")
        for c in checks:
            mark, style = {PASS: ("ok  ", "#7fb069"), FAIL: ("FAIL", "#e5534b")}.get(c.status, ("skip", "dim"))
            body.append(f"{mark}  ", style=style)
            body.append(f"{c.name:<12}")
            body.append(f"{c.detail}\n", style="dim")
        verdict = "Some checks failed." if any(c.status == FAIL for c in checks) else "All checks passed."
        body.append(f"\n{verdict}")
        return body


def run(config_dir: Path) -> int:
    EnvEditorApp(config_dir).run()
    return 0
