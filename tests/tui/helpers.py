"""Helpers that the tests of the full-screen interface share."""

import json
from pathlib import Path
from typing import cast

from rich.text import Text
from textual.pilot import Pilot
from textual.widgets import DataTable, OptionList, Static

from claude_code_env_editor.tui.app import EnvEditorApp
from claude_code_env_editor.tui.pages import ProfileListPage, VariablesPage


def write_settings(tmp_path: Path, env: dict[str, str]) -> None:
    (tmp_path / "settings.json").write_text(json.dumps({"env": env}))


def read_env(path: Path) -> dict[str, str]:
    return cast(dict[str, str], json.loads(path.read_text()).get("env", {}))


def make_login(home: Path, name: str, env: dict[str, str]) -> Path:
    directory: Path = home / name
    directory.mkdir(parents=True)
    (directory / ".claude.json").write_text("{}")
    (directory / "settings.json").write_text(json.dumps({"env": env}))
    return directory


def screen_name(app: EnvEditorApp) -> str:
    return type(app.screen).__name__


def text_of(app: EnvEditorApp, selector: str) -> str:
    return str(app.screen.query_one(selector=selector, expect_type=Static).render())


def cell(app: EnvEditorApp, row_key: str, column: int) -> str:
    table: DataTable[Text] = app.screen.query_one(selector=DataTable)
    return str(table.get_row(row_key=row_key)[column])


def labels_of(app: EnvEditorApp) -> list[str]:
    option_list: OptionList = app.screen.query_one(selector=OptionList)
    return [str(option_list.get_option_at_index(index=i).prompt) for i in range(option_list.option_count)]


async def move_to_profile(app: EnvEditorApp, pilot: Pilot[None], name: str) -> None:
    """Put the cursor of the profile list on a profile."""
    page: ProfileListPage = cast(ProfileListPage, app.screen)
    app.screen.query_one(selector=DataTable).move_cursor(row=page.names.index(name))
    await pilot.pause()


async def move_to_variable(app: EnvEditorApp, pilot: Pilot[None], name: str) -> None:
    """Put the cursor of a profile page on a variable."""
    page: VariablesPage = cast(VariablesPage, app.screen)
    app.screen.query_one(selector=DataTable).move_cursor(row=[r.name for r in page.rows].index(name))
    await pilot.pause()


async def open_profile(app: EnvEditorApp, pilot: Pilot[None], name: str) -> VariablesPage:
    """Open a profile from the list with Enter."""
    await move_to_profile(app, pilot, name)
    await pilot.press("enter")
    await pilot.pause()
    assert isinstance(app.screen, VariablesPage)
    return app.screen


async def choose(app: EnvEditorApp, pilot: Pilot[None], option_id: str) -> None:
    """Highlight the option with this id in the open list and press Enter."""
    option_list: OptionList = app.screen.query_one(selector=OptionList)
    ids: list[str | None] = [option_list.get_option_at_index(index=i).id for i in range(option_list.option_count)]
    option_list.highlighted = ids.index(option_id)
    await pilot.pause()
    await pilot.press("enter")
    await pilot.pause()
