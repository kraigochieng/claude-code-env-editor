"""A table whose arrow keys move between pages."""

from __future__ import annotations

from typing import ClassVar

from rich.text import Text
from textual.binding import Binding, BindingType
from textual.message import Message
from textual.widgets import DataTable


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
