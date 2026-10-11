"""Small dialogs of the interface: edit a value, ask yes or no, type a line, pick an item, show text."""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar, Final

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from claude_code_env_editor.envvars import Row, VarSpec, validate

REMOVE_CHOICE: Final[str] = "__remove__"
OTHER_FILE: Final[str] = "__file__"
PASTE_HINT: Final[str] = "Paste with Ctrl+Shift+V (Ctrl+V does not work in a terminal)."


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
            with VerticalScroll(id="question-box"):
                yield Static(Text(self.question), id="question")
            yield Static("y or enter: yes  -  n or esc: no", classes="hint")
            yield Static(self.hint_text, classes="hint")

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
        with Vertical(classes="dialog"):
            yield Static(self.title_text, classes="heading")
            yield Static(Text(self.prompt))
            yield Input(placeholder=self.placeholder, id="line")
            yield Static("", id="error", classes="fail")
            yield Static(PASTE_HINT, id="paste-hint", classes="hint")
            yield Static("enter save  -  esc cancel", classes="hint")

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
