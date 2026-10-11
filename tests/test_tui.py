import json
import time
from pathlib import Path

import pytest
from rich.text import Text
from textual.pilot import Pilot
from textual.widgets import DataTable, Input, OptionList, Static

from claude_code_env_editor import cli
from claude_code_env_editor.profiles import Profile, load_user_profiles, save_profile
from claude_code_env_editor.target import Target
from claude_code_env_editor.tui.app import EnvEditorApp, TextScreen
from claude_code_env_editor.verify import Check, Endpoint


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


async def test_command_palette_and_theme_picker_are_disabled(tmp_path: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+p")
        await pilot.pause()
        assert len(app.screen_stack) == 1
        assert "command_palette" not in {binding.action for _, binding in app._bindings}


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


async def test_closing_the_verify_dialog_before_the_answer_does_not_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def slow_verify(endpoint: Endpoint, login_found: bool = False) -> list[Check]:
        time.sleep(0.4)
        return [Check(name="url", status="pass", detail="x")]

    monkeypatch.setattr("claude_code_env_editor.tui.app.verify", slow_verify)
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("v")
        await pilot.pause(0.05)
        await pilot.press("escape")
        await pilot.pause(0.8)
        assert len(app.screen_stack) == 1


async def test_update_body_on_a_closed_dialog_does_nothing(tmp_path: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        screen: TextScreen = TextScreen(title="t", body=Text("x"))
        app.push_screen(screen=screen)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        screen.update_body(body=Text("y"))


async def test_x_asks_before_removing_and_no_keeps_the_value(tmp_path: Path) -> None:
    (tmp_path / "settings.json").write_text(json.dumps({"env": {"ANTHROPIC_MODEL": "m1"}}))
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        names: list[str] = [r.name for r in app.rows]
        app.query_one(selector=DataTable).move_cursor(row=names.index("ANTHROPIC_MODEL"))
        await pilot.press("x")
        await pilot.pause()
        assert type(app.screen).__name__ == "ConfirmScreen"
        await pilot.press("n")
        await pilot.pause()
    assert json.loads((tmp_path / "settings.json").read_text())["env"] == {"ANTHROPIC_MODEL": "m1"}


async def test_x_then_yes_removes_the_value(tmp_path: Path) -> None:
    (tmp_path / "settings.json").write_text(json.dumps({"env": {"ANTHROPIC_MODEL": "m1"}}))
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        names: list[str] = [r.name for r in app.rows]
        app.query_one(selector=DataTable).move_cursor(row=names.index("ANTHROPIC_MODEL"))
        await pilot.press("x")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
    assert "env" not in json.loads((tmp_path / "settings.json").read_text())
    assert (tmp_path / "settings.json.bak").exists()


@pytest.fixture
def profiles_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the tool at a profiles file in a temporary directory."""
    path: Path = tmp_path / "tool" / "profiles.toml"
    monkeypatch.setattr("claude_code_env_editor.profiles.default_profiles_path", lambda: path)
    return path


def option_ids(option_list: OptionList) -> list[str | None]:
    return [option_list.get_option_at_index(index=i).id for i in range(option_list.option_count)]


async def open_profiles(app: EnvEditorApp, pilot: Pilot[None], highlight: str | None = None) -> OptionList:
    """Press p and optionally move the highlight to a profile."""
    await pilot.press("p")
    await pilot.pause()
    assert type(app.screen).__name__ == "ProfileScreen"
    option_list: OptionList = app.screen.query_one(selector="#profiles", expect_type=OptionList)
    if highlight is not None:
        option_list.highlighted = option_ids(option_list).index(highlight)
        await pilot.pause()
    return option_list


async def test_p_lists_built_in_profiles(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        option_list: OptionList = await open_profiles(app, pilot)
        assert "deepseek" in option_ids(option_list) and "openrouter" in option_ids(option_list)


async def test_apply_replaces_stale_values_after_a_yes(tmp_path: Path, profiles_file: Path) -> None:
    (tmp_path / "settings.json").write_text(
        json.dumps({"env": {"ANTHROPIC_BASE_URL": "https://openrouter.ai/api", "API_TIMEOUT_MS": "5000"}})
    )
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profiles(app, pilot, highlight="deepseek")
        await pilot.press("enter")
        await pilot.pause()
        assert type(app.screen).__name__ == "ConfirmScreen"
        question: str = str(app.screen.query_one(selector="#question", expect_type=Static).render())
        assert "remove" in question and "API_TIMEOUT_MS" in question
        assert "deepseek-flash[1m]" in question  # a value with brackets shows as it is
        await pilot.press("y")
        await pilot.pause()
    env: dict[str, str] = json.loads((tmp_path / "settings.json").read_text())["env"]
    assert env["ANTHROPIC_BASE_URL"] == "https://api.deepseek.com/anthropic"
    assert "API_TIMEOUT_MS" not in env


async def test_apply_with_no_answers_writes_nothing(tmp_path: Path, profiles_file: Path) -> None:
    (tmp_path / "settings.json").write_text(json.dumps({"env": {"ANTHROPIC_MODEL": "keep-me"}}))
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profiles(app, pilot, highlight="deepseek")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
    assert json.loads((tmp_path / "settings.json").read_text())["env"] == {"ANTHROPIC_MODEL": "keep-me"}


async def test_m_applies_in_merge_mode(tmp_path: Path, profiles_file: Path) -> None:
    (tmp_path / "settings.json").write_text(json.dumps({"env": {"API_TIMEOUT_MS": "5000"}}))
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profiles(app, pilot, highlight="openrouter")
        await pilot.press("m")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
    env: dict[str, str] = json.loads((tmp_path / "settings.json").read_text())["env"]
    assert env["API_TIMEOUT_MS"] == "5000" and env["ANTHROPIC_BASE_URL"] == "https://openrouter.ai/api"


async def test_s_saves_the_current_values_with_the_key(tmp_path: Path, profiles_file: Path) -> None:
    (tmp_path / "settings.json").write_text(
        json.dumps({"env": {"ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic", "ANTHROPIC_AUTH_TOKEN": "sk-1234567890abcd"}})
    )
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profiles(app, pilot)
        await pilot.press("s")
        await pilot.pause()
        assert type(app.screen).__name__ == "InputScreen"
        app.screen.query_one(selector=Input).value = "work-ds"
        await pilot.press("enter")
        await pilot.pause()
        assert type(app.screen).__name__ == "ConfirmScreen"  # the key question
        await pilot.press("y")
        await pilot.pause()
        assert type(app.screen).__name__ == "ProfileScreen"  # the list opens again
    saved: dict[str, Profile] = load_user_profiles(path=profiles_file)
    assert saved["work-ds"].variables["ANTHROPIC_AUTH_TOKEN"] == "sk-1234567890abcd"


async def test_s_can_leave_the_key_out(tmp_path: Path, profiles_file: Path) -> None:
    (tmp_path / "settings.json").write_text(
        json.dumps({"env": {"ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic", "ANTHROPIC_AUTH_TOKEN": "sk-1234567890abcd"}})
    )
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profiles(app, pilot)
        await pilot.press("s")
        await pilot.pause()
        app.screen.query_one(selector=Input).value = "nokey"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
    assert not load_user_profiles(path=profiles_file)["nokey"].has_key


async def test_save_refuses_a_built_in_or_bad_name(tmp_path: Path, profiles_file: Path) -> None:
    (tmp_path / "settings.json").write_text(json.dumps({"env": {"ANTHROPIC_MODEL": "m"}}))
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profiles(app, pilot)
        await pilot.press("s")
        await pilot.pause()
        for bad in ("deepseek", "has space"):
            app.screen.query_one(selector=Input).value = bad
            await pilot.press("enter")
            await pilot.pause()
            assert type(app.screen).__name__ == "InputScreen"
            assert str(app.screen.query_one(selector="#error", expect_type=Static).render()) != ""
    assert not profiles_file.exists()


async def test_x_deletes_your_profile_after_a_yes_and_not_a_built_in(tmp_path: Path, profiles_file: Path) -> None:
    save_profile(profile=Profile(name="mine", variables={"ANTHROPIC_MODEL": "m"}), path=profiles_file)
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profiles(app, pilot, highlight="deepseek")
        await pilot.press("x")
        await pilot.pause()
        assert len(app.screen_stack) == 1  # a built-in cannot be deleted: no dialog
        status: str = str(app.query_one(selector="#status", expect_type=Static).render())
        assert "built-in" in status
        await open_profiles(app, pilot, highlight="mine")
        await pilot.press("x")
        await pilot.pause()
        assert type(app.screen).__name__ == "ConfirmScreen"
        await pilot.press("y")
        await pilot.pause()
    assert "mine" not in load_user_profiles(path=profiles_file)


async def test_a_key_is_refused_for_a_shared_project_file(tmp_path: Path, profiles_file: Path) -> None:
    save_profile(
        profile=Profile(name="keyed", variables={"ANTHROPIC_AUTH_TOKEN": "sk-1234567890abcd"}), path=profiles_file
    )
    shared: Path = tmp_path / "proj" / ".claude" / "settings.json"
    target: Target = Target.from_file(settings_file=shared, known_dirs=[])
    app: EnvEditorApp = EnvEditorApp(target=target)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profiles(app, pilot, highlight="keyed")
        await pilot.press("enter")
        await pilot.pause()
        assert len(app.screen_stack) == 1  # no confirm dialog
        status: str = str(app.query_one(selector="#status", expect_type=Static).render())
        assert "Refused" in status and "committed" in status
    assert not shared.exists()


async def test_d_can_open_another_settings_file(tmp_path: Path, profiles_file: Path) -> None:
    other: Path = tmp_path / "proj" / ".claude" / "settings.local.json"
    other.parent.mkdir(parents=True)
    other.write_text(json.dumps({"env": {"ANTHROPIC_MODEL": "project-model"}}))
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        option_list: OptionList = app.screen.query_one(selector=OptionList)
        option_list.highlighted = option_list.option_count - 1
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert type(app.screen).__name__ == "InputScreen"
        app.screen.query_one(selector=Input).value = str(other)
        await pilot.press("enter")
        await pilot.pause()
        assert app.target.settings_file == other and not app.target.user_level
        assert next(r for r in app.rows if r.name == "ANTHROPIC_MODEL").value == "project-model"


def test_tui_command_accepts_a_file_option() -> None:
    args = cli.build_parser().parse_args(["tui", "--file", "x.json"])
    assert args.file == Path("x.json")
