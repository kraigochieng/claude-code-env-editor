"""Small dialogs of the interface: edit a value, ask yes or no, type a line, pick an item, show text.

Every dialog closes when the user clicks outside it, with the same result as Esc.
The keys in the hint lines use the colour of the keys in the footer.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, ClassVar, Final

from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from claude_code_env_editor.envvars import Row, VarSpec, validate

REMOVE_CHOICE: Final[str] = "__remove__"
FOOTER_KEY_FALLBACK: Final[str] = "#FFA62B"
DIALOG_CLASS: Final[str] = "dialog"


def key_color(app: App[Any]) -> str:
    """Return the colour that the footer uses for its keys, so that the dialogs match it."""
    return str(app.get_css_variables().get("footer-key-foreground", FOOTER_KEY_FALLBACK))


def hint_line(app: App[Any], items: Sequence[tuple[str, str]], tail: str = "") -> Text:
    """Build a hint line like the footer: each key in the footer colour, then what it does.

    Example: hint_line(app, [("enter", "save"), ("esc", "cancel")]).
    """
    color: str = key_color(app=app)
    line: Text = Text()
    for index, (key, meaning) in enumerate(items):
        if index:
            line.append("  ")
        line.append(key, style=f"bold {color}")
        line.append(f" {meaning}", style="dim")
    if tail:
        line.append(f"  {tail}", style="dim")
    return line


def key_sentence(app: App[Any], before: str, key: str, after: str) -> Text:
    """Build a sentence with one key in the footer colour, for example 'Paste with Ctrl+Shift+V (...)'."""
    line: Text = Text()
    if before:
        line.append(before, style="dim")
    line.append(key, style=f"bold {key_color(app=app)}")
    line.append(after, style="dim")
    return line


def paste_hint(app: App[Any]) -> Text:
    """Return the line that tells how to paste in a terminal."""
    return key_sentence(
        app=app,
        before="Paste with ",
        key="Ctrl+Shift+V",
        after=" (Ctrl+V does not work in a terminal).",
    )


def clicked_outside(screen: ModalScreen[Any], event: events.Click) -> bool:
    """Return True when the click landed outside the dialog box of a modal screen."""
    try:
        widget, _ = screen.get_widget_at(event.screen_x, event.screen_y)
    except Exception:  # no widget at that point: the click is outside
        return True
    dialogs: list[Any] = list(screen.query(f".{DIALOG_CLASS}"))
    if not dialogs:
        return False
    return dialogs[0] not in widget.ancestors_with_self


class EditScreen(ModalScreen[str | None]):
    """Dialog to type a new value for one variable."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding(key="escape", action="cancel", description="Cancel"),
        Binding(key="ctrl+r", action="reveal", description="Show or hide the key", show=False),
    ]

    def __init__(self, row: Row) -> None:
        """Keep the row to edit."""
        super().__init__()
        self.row = row

    def compose(self) -> ComposeResult:
        """Build the dialog: name, help text, input, error line, hints."""
        spec: VarSpec | None = self.row.spec
        with Vertical(classes=DIALOG_CLASS):
            yield Static(self.row.name, classes="heading")
            yield Static(spec.help if spec else "Custom variable.")
            yield Input(
                value=self.row.value,
                placeholder=spec.example if spec else "",
                password=self.row.secret,
                id="value",
            )
            yield Static("", id="error", classes="fail")
            yield Static(paste_hint(app=self.app), id="paste-hint", classes="hint")
            if self.row.secret:
                yield Static(
                    key_sentence(app=self.app, before="", key="Ctrl+R", after=" shows or hides the key."),
                    id="reveal-hint",
                    classes="hint",
                )
            yield Static(
                hint_line(
                    app=self.app, items=[("enter", "save"), ("esc", "cancel")], tail="An empty value removes it."
                ),
                classes="hint",
            )

    def on_click(self, event: events.Click) -> None:
        """Close the dialog without a change when the click is outside the box."""
        if clicked_outside(screen=self, event=event):
            self.action_cancel()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Check the typed value. Close the dialog when it is good, else show the error."""
        value: str = event.value.strip()
        if value and self.row.spec and (err := validate(spec=self.row.spec, value=value)):
            self.query_one(selector="#error", expect_type=Static).update(err)
            return
        self.dismiss(result=value)

    def action_reveal(self) -> None:
        """Show or hide the characters of a secret. A value that is not secret has nothing to hide."""
        if not self.row.secret:
            return
        box: Input = self.query_one(selector="#value", expect_type=Input)
        box.password = not box.password

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
        with Vertical(classes=DIALOG_CLASS):
            yield Static(self.title_text, classes="heading")
            with VerticalScroll(id="question-box"):
                yield Static(Text(self.question), id="question")
            yield Static(
                hint_line(app=self.app, items=[("y / enter", "yes"), ("n / esc", "no")]),
                classes="hint",
            )
            if self.hint_text:
                yield Static(Text(self.hint_text, style="dim"), classes="hint")

    def on_click(self, event: events.Click) -> None:
        """Answer no when the click is outside the box. Nothing is written."""
        if clicked_outside(screen=self, event=event):
            self.action_no()

    def action_yes(self) -> None:
        """Close the dialog with yes."""
        self.dismiss(result=True)

    def action_no(self) -> None:
        """Close the dialog with no."""
        self.dismiss(result=False)


class InputScreen(ModalScreen[str | None]):
    """Dialog to type one line of text. A check function can refuse the text with a message."""

    BINDINGS: ClassVar[list[BindingType]] = [Binding(key="escape", action="cancel", description="Cancel")]

    def __init__(self, title: str, prompt: str, check: Callable[[str], str | None], placeholder: str = "") -> None:
        """Keep the title, the prompt, the check function, and the placeholder."""
        super().__init__()
        self.title_text: str = title
        self.prompt: str = prompt
        self.check: Callable[[str], str | None] = check
        self.placeholder: str = placeholder

    def compose(self) -> ComposeResult:
        """Build the dialog: title, prompt, input, error line, hints."""
        with Vertical(classes=DIALOG_CLASS):
            yield Static(self.title_text, classes="heading")
            yield Static(Text(self.prompt))
            yield Input(placeholder=self.placeholder, id="line")
            yield Static("", id="error", classes="fail")
            yield Static(paste_hint(app=self.app), id="paste-hint", classes="hint")
            yield Static(hint_line(app=self.app, items=[("enter", "save"), ("esc", "cancel")]), classes="hint")

    def on_click(self, event: events.Click) -> None:
        """Close the dialog without text when the click is outside the box."""
        if clicked_outside(screen=self, event=event):
            self.action_cancel()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Run the check. Close the dialog with the text when it is good, else show the message."""
        text: str = event.value.strip()
        problem: str | None = self.check(text)
        if problem:
            self.query_one(selector="#error", expect_type=Static).update(Text(problem))
            return
        self.dismiss(result=text)

    def action_cancel(self) -> None:
        """Close the dialog without text."""
        self.dismiss(result=None)


class PickScreen(ModalScreen[str | None]):
    """Dialog to choose one item from a list."""

    BINDINGS: ClassVar[list[BindingType]] = [Binding(key="escape", action="cancel", description="Cancel")]

    def __init__(self, title: str, options: list[tuple[str, str]], intro: Text | None = None) -> None:
        """Keep the title and the (id, label) options. intro is a text shown above the list, for example values."""
        super().__init__()
        self.title_text, self.options = title, options
        self.intro: Text | None = intro

    def compose(self) -> ComposeResult:
        """Build the dialog: title, optional intro, option list, hint."""
        with Vertical(classes=DIALOG_CLASS):
            yield Static(self.title_text, classes="heading")
            if self.intro is not None:
                with VerticalScroll(id="intro-box"):
                    yield Static(self.intro, id="intro")
            yield OptionList(*[Option(Text(label), id=key) for key, label in self.options])
            yield Static(hint_line(app=self.app, items=[("enter", "choose"), ("esc", "cancel")]), classes="hint")

    def on_mount(self) -> None:
        """Put the keyboard focus on the list, so that Enter chooses the highlighted place."""
        self.query_one(selector=OptionList).focus()

    def on_click(self, event: events.Click) -> None:
        """Close the dialog without a choice when the click is outside the box."""
        if clicked_outside(screen=self, event=event):
            self.action_cancel()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Close the dialog and return the id of the chosen option."""
        self.dismiss(result=event.option.id)

    def action_cancel(self) -> None:
        """Close the dialog without a choice."""
        self.dismiss(result=None)


class TextScreen(ModalScreen[None]):
    """Dialog that shows read-only text."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding(key="escape", action="close", description="Close"),
        Binding(key="enter", action="close", description="Close"),
    ]

    def __init__(self, title: str, body: Text) -> None:
        """Keep the title and the text to show."""
        super().__init__()
        self.title_text, self.body = title, body

    def compose(self) -> ComposeResult:
        """Build the dialog: title, text, hint."""
        with Vertical(classes=DIALOG_CLASS):
            yield Static(self.title_text, classes="heading")
            yield Static(self.body, id="body")
            yield Static(hint_line(app=self.app, items=[("esc / enter", "close")]), classes="hint")

    def on_click(self, event: events.Click) -> None:
        """Close the dialog when the click is outside the box."""
        if clicked_outside(screen=self, event=event):
            self.action_close()

    def action_close(self) -> None:
        """Close the dialog."""
        self.dismiss(result=None)

    def update_body(self, body: Text) -> None:
        """Replace the text in the open dialog. Do nothing when the dialog is already closed."""
        try:
            self.query_one(selector="#body", expect_type=Static).update(body)
        except NoMatches:
            return
