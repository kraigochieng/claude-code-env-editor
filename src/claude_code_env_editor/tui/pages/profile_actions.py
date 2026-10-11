"""The flows that delete a profile and copy a profile."""

from __future__ import annotations

from collections.abc import Callable

from claude_code_env_editor.profiles import (
    NAME_PATTERN,
    Profile,
    ProfileError,
    delete_profile,
    load_profiles,
    save_profile,
    similar_name,
)
from claude_code_env_editor.tui.dialogs import ConfirmScreen, InputScreen
from claude_code_env_editor.tui.pages.apply_flow import ApplyFlowPage


class ProfileActionsPage(ApplyFlowPage):
    """A page that can apply, delete, and copy a profile."""

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
