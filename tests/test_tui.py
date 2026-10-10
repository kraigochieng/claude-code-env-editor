import json

from claude_code_env_editor.tui.app import EnvEditorApp


async def test_home_lists_variables(tmp_path):
    (tmp_path / "settings.json").write_text(data=json.dumps(obj={"env": {"ANTHROPIC_MODEL": "m1"}}))
    app = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        names = [r.name for r in app.rows]
        assert "ANTHROPIC_BASE_URL" in names
        assert next(r for r in app.rows if r.name == "ANTHROPIC_MODEL").value == "m1"


async def test_edit_writes_settings(tmp_path):
    app = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        # row 0 is ANTHROPIC_BASE_URL
        await pilot.press("e")
        await pilot.pause()
        await pilot.press(*"https://example.test")
        await pilot.press("enter")
        await pilot.pause()
    env = json.loads(s=(tmp_path / "settings.json").read_text())["env"]
    assert env["ANTHROPIC_BASE_URL"] == "https://example.test"


async def test_invalid_value_is_rejected(tmp_path):
    app = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        await pilot.press(*"nope")
        await pilot.press("enter")
        await pilot.pause()
    assert not (tmp_path / "settings.json").exists()


async def test_secret_is_masked_until_reveal(tmp_path):
    (tmp_path / "settings.json").write_text(data=json.dumps(obj={"env": {"ANTHROPIC_AUTH_TOKEN": "sk-0123456789abcdef"}}))
    app = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one(selector="DataTable")
        shown = [str(c) for c in table.get_row("ANTHROPIC_AUTH_TOKEN")]
        assert not any("0123456789" in s for s in shown)
        await pilot.press("r")
        await pilot.pause()
        shown = [str(c) for c in table.get_row("ANTHROPIC_AUTH_TOKEN")]
        assert any("sk-0123456789abcdef" in s for s in shown)


async def test_help_screen_opens_and_closes(tmp_path):
    app = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.press("question_mark")
        await pilot.pause()
        assert len(app.screen_stack) == 2
        await pilot.press("escape")
        await pilot.pause()
        assert len(app.screen_stack) == 1
