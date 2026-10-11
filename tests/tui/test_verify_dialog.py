import time
from pathlib import Path

import pytest
from rich.text import Text

from claude_code_env_editor.tui.app import EnvEditorApp, TextScreen
from claude_code_env_editor.tui.pages import ProfileListPage
from claude_code_env_editor.verify import Check, Endpoint
from tests.tui.helpers import move_to_profile

# -- verify --------------------------------------------------------------------


async def test_verify_on_the_list_uses_the_endpoint_of_the_profile_under_the_cursor(
    tmp_path: Path, profiles_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []

    def fake_verify(endpoint: Endpoint, login_found: bool = False) -> list[Check]:
        seen.append(endpoint.host)
        return [Check(name="url", status="pass", detail="x")]

    monkeypatch.setattr("claude_code_env_editor.tui.pages.profile_list.verify", fake_verify)
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        for name in ("openrouter", "deepseek"):
            await move_to_profile(app, pilot, name)
            await pilot.press("v")
            await pilot.pause(0.5)
            await pilot.press("escape")
            await pilot.pause()
    assert seen == ["openrouter.ai", "api.deepseek.com"]


async def test_closing_the_verify_dialog_before_the_answer_does_not_crash(
    tmp_path: Path, profiles_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def slow_verify(endpoint: Endpoint, login_found: bool = False) -> list[Check]:
        time.sleep(0.4)
        return [Check(name="url", status="pass", detail="x")]

    monkeypatch.setattr("claude_code_env_editor.tui.pages.profile_list.verify", slow_verify)
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("v")
        await pilot.pause(0.05)
        await pilot.press("escape")
        await pilot.pause(0.8)
        assert isinstance(app.screen, ProfileListPage)


async def test_update_body_on_a_closed_dialog_does_nothing(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        screen: TextScreen = TextScreen(title="t", body=Text("x"))
        app.push_screen(screen=screen)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        screen.update_body(body=Text("y"))
