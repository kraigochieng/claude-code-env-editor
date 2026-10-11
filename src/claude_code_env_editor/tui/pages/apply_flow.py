"""The flow that applies a profile to a place: choose the place, review the changes, write them."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Final

from rich.text import Text

from claude_code_env_editor import config
from claude_code_env_editor.apply import ApplyPlan, format_plan, plan_apply, secret_target_problem
from claude_code_env_editor.destinations import (
    Destination,
    DestinationKind,
    DestinationState,
    destination_state,
    login_destinations,
    project_destination,
    short_path,
)
from claude_code_env_editor.envvars import CATALOG, mask
from claude_code_env_editor.profiles import (
    Profile,
    ProfileError,
    get_profile,
)
from claude_code_env_editor.target import Target
from claude_code_env_editor.tui.dialogs import (
    ConfirmScreen,
    InputScreen,
    PickScreen,
)
from claude_code_env_editor.tui.pages.base import BasePage

SECRET_NAMES: Final[tuple[str, ...]] = ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY")
PROJECT_FOLDER: Final[str] = "__project__"


class ApplyFlowPage(BasePage):
    """A page that can apply a profile to a login folder or to a project folder."""

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
        self,
        title: str,
        on_chosen: Callable[[Destination], None],
        profile: Profile | None = None,
        intro: Text | None = None,
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

        self.app.push_screen(screen=PickScreen(title=title, options=options, intro=intro), callback=chosen)

    # -- apply -------------------------------------------------------------

    @staticmethod
    def variables_text(profile: Profile) -> Text:
        """Return the variables of a profile as lines of text. Secrets are masked."""
        text: Text = Text()
        if not profile.variables:
            text.append("This profile has no variables.\n", style="dim")
            text.append("Applying it removes the known variables of the place.", style="dim")
            return text
        text.append("This profile sets:", style="dim")
        for spec in CATALOG:
            if spec.name in profile.variables:
                value: str = mask(value=profile.variables[spec.name], secret=spec.secret)
                text.append(f"\n  {spec.name:<34} ")
                text.append(value, style="bold")
        return text

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
            intro=self.variables_text(profile=profile),
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
        plan: ApplyPlan = plan_apply(profile=profile, current_env=current)
        if not plan.writes:
            self.set_status(message=f"Nothing to change: {destination.label} already matches '{profile.name}'.")
            return
        lines: list[str] = format_plan(plan=plan, wrap=True)
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
