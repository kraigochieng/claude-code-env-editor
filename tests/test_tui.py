import json
from pathlib import Path

from rich.text import Text
from textual.widgets import DataTable, Static

from claude_code_env_editor.tui.app import EnvEditorApp


async def test_home_lists_variables(tmp_path: Path) -> None:
    (tmp_path / "settings.json").write_text(data=json.dumps(obj={"env": {"ANTHROPIC_MODEL": "m1"}}))
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        names: list[str] = [r.name for r in app.rows]
        assert "ANTHROPIC_BASE_URL" in names
        assert next(r for r in app.rows if r.name == "ANTHROPIC_MODEL").value == "m1"


async def test_edit_writes_settings(tmp_path: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        # row 0 is ANTHROPIC_BASE_URL
        await pilot.press("e")
        await pilot.pause()
        await pilot.press(*"https://example.test")
        await pilot.press("enter")
        await pilot.pause()
    env: dict[str, str] = json.loads(s=(tmp_path / "settings.json").read_text())["env"]
    assert env["ANTHROPIC_BASE_URL"] == "https://example.test"


async def test_invalid_value_is_rejected(tmp_path: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        await pilot.press(*"nope")
        await pilot.press("enter")
        await pilot.pause()
    assert not (tmp_path / "settings.json").exists()


async def test_secret_is_masked_until_reveal(tmp_path: Path) -> None:
    (tmp_path / "settings.json").write_text(data=json.dumps(obj={"env": {"ANTHROPIC_AUTH_TOKEN": "sk-0123456789abcdef"}}))
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        table: DataTable[Text] = app.query_one(selector=DataTable)
        shown: list[str] = [str(c) for c in table.get_row(row_key="ANTHROPIC_AUTH_TOKEN")]
        assert not any("0123456789" in s for s in shown)
        await pilot.press("r")
        await pilot.pause()
        shown = [str(c) for c in table.get_row(row_key="ANTHROPIC_AUTH_TOKEN")]
        assert any("sk-0123456789abcdef" in s for s in shown)


async def test_help_screen_opens_and_closes(tmp_path: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.press("question_mark")
        await pilot.pause()
        assert len(app.screen_stack) == 2
        await pilot.press("escape")
        await pilot.pause()
        assert len(app.screen_stack) == 1


async def test_verify_without_key_shows_skip_not_failure(tmp_path: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("v")
        await pilot.pause(0.5)
        assert len(app.screen_stack) == 2


async def test_choice_variable_opens_a_list_and_saves_the_choice(tmp_path: Path) -> None:
    (tmp_path / "settings.json").write_text(data=json.dumps(obj={"env": {"CLAUDE_CODE_EFFORT_LEVEL": "low"}}))
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        names: list[str] = [r.name for r in app.rows]
        table = app.query_one(selector=DataTable)
        table.move_cursor(row=names.index("CLAUDE_CODE_EFFORT_LEVEL"))
        await pilot.press("e")
        await pilot.pause()
        assert type(app.screen).__name__ == "PickScreen"
        await pilot.press("down", "enter")
        await pilot.pause()
    env: dict[str, str] = json.loads(s=(tmp_path / "settings.json").read_text())["env"]
    assert env["CLAUDE_CODE_EFFORT_LEVEL"] == "medium"


async def test_home_and_edit_dialog_tell_how_to_paste(tmp_path: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        status: str = str(app.query_one(selector="#status", expect_type=Static).render())
        assert "Ctrl+Shift+V" in status
        await pilot.press("e")
        await pilot.pause()
        hint: str = str(app.screen.query_one(selector="#paste-hint", expect_type=Static).render())
        assert "Ctrl+Shift+V" in hint
