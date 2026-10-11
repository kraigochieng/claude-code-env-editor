import json
import time
from pathlib import Path
from typing import cast

import pytest
from rich.text import Text
from textual.pilot import Pilot
from textual.widgets import DataTable, Input, OptionList, Static

from claude_code_env_editor import cli
from claude_code_env_editor.profiles import Profile, load_profiles, save_profile, templates
from claude_code_env_editor.target import Target
from claude_code_env_editor.tui.app import EnvEditorApp, TextScreen
from claude_code_env_editor.tui.pages import ProfileListPage, VariablesPage
from claude_code_env_editor.verify import Check, Endpoint


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Give every test its own home directory, so the real logins and registry stay out of the tests."""
    home: Path = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    return home


@pytest.fixture
def profiles_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the tool at a profiles file in a temporary directory."""
    path: Path = tmp_path / "tool" / "profiles.toml"
    monkeypatch.setattr("claude_code_env_editor.profiles.default_profiles_path", lambda: path)
    return path


def write_settings(tmp_path: Path, env: dict[str, str]) -> None:
    (tmp_path / "settings.json").write_text(json.dumps({"env": env}))


def read_env(tmp_path: Path) -> dict[str, str]:
    return cast(dict[str, str], json.loads((tmp_path / "settings.json").read_text()).get("env", {}))


def screen_name(app: EnvEditorApp) -> str:
    return type(app.screen).__name__


def text_of(app: EnvEditorApp, selector: str) -> str:
    return str(app.screen.query_one(selector=selector, expect_type=Static).render())


async def move_to_profile(app: EnvEditorApp, pilot: Pilot[None], name: str) -> None:
    """Put the cursor of the profile list on a profile."""
    page: ProfileListPage = cast(ProfileListPage, app.screen)
    app.screen.query_one(selector=DataTable).move_cursor(row=page.names.index(name))
    await pilot.pause()


async def move_to_variable(app: EnvEditorApp, pilot: Pilot[None], name: str) -> None:
    """Put the cursor of a variables page on a variable."""
    page: VariablesPage = cast(VariablesPage, app.screen)
    app.screen.query_one(selector=DataTable).move_cursor(row=[r.name for r in page.rows].index(name))
    await pilot.pause()


async def open_current(app: EnvEditorApp, pilot: Pilot[None]) -> VariablesPage:
    """Press c on the profile list to open the values of the file."""
    await pilot.press("c")
    await pilot.pause()
    assert isinstance(app.screen, VariablesPage) and app.screen.source.kind == "file"
    return app.screen


async def open_profile(app: EnvEditorApp, pilot: Pilot[None], name: str) -> VariablesPage:
    """Open a profile from the list with Enter."""
    await move_to_profile(app, pilot, name)
    await pilot.press("enter")
    await pilot.pause()
    assert isinstance(app.screen, VariablesPage) and app.screen.source.kind == "profile"
    return app.screen


# -- the main page lists profiles -------------------------------------------


async def test_main_page_lists_the_profiles(tmp_path: Path, profiles_file: Path) -> None:
    save_profile(profile=Profile(name="mine", variables={"ANTHROPIC_MODEL": "m"}), path=profiles_file)
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ProfileListPage)
        assert "deepseek" in app.screen.names and "mine" in app.screen.names
        assert app.screen.names.index("mine") > app.screen.names.index("deepseek")


async def test_banner_names_the_profile_that_matches_the_file(tmp_path: Path, profiles_file: Path) -> None:
    write_settings(tmp_path, {"ANTHROPIC_BASE_URL": "https://openrouter.ai/api"})
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert "openrouter (the file matches this profile)" in text_of(app, "#banner")
        assert isinstance(app.screen, ProfileListPage) and app.screen.active is not None


async def test_banner_says_when_the_file_has_its_own_values(tmp_path: Path, profiles_file: Path) -> None:
    write_settings(tmp_path, {"ANTHROPIC_MODEL": "something-custom"})
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert "none (the file has its own values)" in text_of(app, "#banner")


async def test_banner_for_an_empty_file(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert "no known variables" in text_of(app, "#banner")


async def test_help_opens_and_closes(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("question_mark")
        await pilot.pause()
        assert screen_name(app) == "TextScreen"
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ProfileListPage)


async def test_command_palette_and_theme_picker_are_disabled(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+p")
        await pilot.pause()
        assert isinstance(app.screen, ProfileListPage)
        assert "command_palette" not in {binding.action for _, binding in app._bindings}


# -- a profile page ----------------------------------------------------------


async def test_enter_opens_a_profile_and_shows_its_variables(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        page: VariablesPage = await open_profile(app, pilot, "deepseek")
        values: dict[str, str] = {r.name: r.value for r in page.rows}
        assert values["ANTHROPIC_BASE_URL"] == "https://api.deepseek.com/anthropic"
        assert "profile     deepseek\n" in text_of(app, "#banner")
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ProfileListPage)


async def test_a_template_profile_is_editable_and_copy_makes_another(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profile(app, pilot, "deepseek")
        await move_to_variable(app, pilot, "ANTHROPIC_MODEL")
        await pilot.press("e")
        await pilot.pause()
        assert screen_name(app) == "EditScreen"  # a template profile is a normal profile
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        assert screen_name(app) == "InputScreen"
        app.screen.query_one(selector=Input).value = "deepseek-copy"
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, VariablesPage) and app.screen.source.name == "deepseek-copy"
        assert app.screen.source.editable
    copied: Profile = load_profiles(path=profiles_file)["deepseek-copy"]
    assert copied.variables["ANTHROPIC_BASE_URL"] == "https://api.deepseek.com/anthropic"


async def test_editing_a_variable_of_your_profile_saves_it_in_profiles_toml(
    tmp_path: Path, profiles_file: Path
) -> None:
    save_profile(
        profile=Profile(name="mine", variables={"ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic"}),
        path=profiles_file,
    )
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profile(app, pilot, "mine")
        await move_to_variable(app, pilot, "ANTHROPIC_MODEL")
        await pilot.press("e")
        await pilot.pause()
        app.screen.query_one(selector=Input).value = "deepseek-flash"
        await pilot.press("enter")
        await pilot.pause()
    assert load_profiles(path=profiles_file)["mine"].variables["ANTHROPIC_MODEL"] == "deepseek-flash"
    assert not (tmp_path / "settings.json").exists()  # the file is not touched by a profile edit


async def test_removing_a_variable_of_your_profile_asks_first(tmp_path: Path, profiles_file: Path) -> None:
    save_profile(
        profile=Profile(name="mine", variables={"ANTHROPIC_MODEL": "m", "API_TIMEOUT_MS": "5000"}), path=profiles_file
    )
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profile(app, pilot, "mine")
        await move_to_variable(app, pilot, "API_TIMEOUT_MS")
        await pilot.press("x")
        await pilot.pause()
        assert screen_name(app) == "ConfirmScreen"
        await pilot.press("n")
        await pilot.pause()
        assert "API_TIMEOUT_MS" in load_profiles(path=profiles_file)["mine"].variables
        await pilot.press("x")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
    assert "API_TIMEOUT_MS" not in load_profiles(path=profiles_file)["mine"].variables


async def test_invalid_value_in_a_profile_is_rejected(tmp_path: Path, profiles_file: Path) -> None:
    save_profile(profile=Profile(name="mine", variables={"ANTHROPIC_MODEL": "m"}), path=profiles_file)
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profile(app, pilot, "mine")
        await move_to_variable(app, pilot, "ANTHROPIC_BASE_URL")
        await pilot.press("e")
        await pilot.pause()
        app.screen.query_one(selector=Input).value = "not-a-url"
        await pilot.press("enter")
        await pilot.pause()
        assert screen_name(app) == "EditScreen"  # still open, with an error
    assert "ANTHROPIC_BASE_URL" not in load_profiles(path=profiles_file)["mine"].variables


async def test_verify_on_a_profile_page_uses_the_profile_endpoint(
    tmp_path: Path, profiles_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []

    def fake_verify(endpoint: Endpoint, login_found: bool = False) -> list[Check]:
        seen.append(endpoint.host)
        return [Check(name="url", status="pass", detail="x")]

    monkeypatch.setattr("claude_code_env_editor.tui.pages.verify", fake_verify)
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profile(app, pilot, "deepseek")
        await pilot.press("v")
        await pilot.pause(0.5)
    assert seen == ["api.deepseek.com"]


# -- the live file page ------------------------------------------------------


async def test_current_file_page_lists_the_file_variables(tmp_path: Path, profiles_file: Path) -> None:
    write_settings(tmp_path, {"ANTHROPIC_MODEL": "m1"})
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        page: VariablesPage = await open_current(app, pilot)
        names: list[str] = [r.name for r in page.rows]
        assert "ANTHROPIC_BASE_URL" in names
        assert next(r for r in page.rows if r.name == "ANTHROPIC_MODEL").value == "m1"


async def test_edit_writes_settings(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_current(app, pilot)
        await pilot.press("e")
        await pilot.pause()
        await pilot.press(*"https://example.test")
        await pilot.press("enter")
        await pilot.pause()
    assert read_env(tmp_path)["ANTHROPIC_BASE_URL"] == "https://example.test"


async def test_invalid_value_is_rejected(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_current(app, pilot)
        await pilot.press("e")
        await pilot.pause()
        await pilot.press(*"nope")
        await pilot.press("enter")
        await pilot.pause()
    assert not (tmp_path / "settings.json").exists()


async def test_secret_is_masked_until_reveal(tmp_path: Path, profiles_file: Path) -> None:
    write_settings(tmp_path, {"ANTHROPIC_AUTH_TOKEN": "sk-0123456789abcdef"})
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_current(app, pilot)
        table: DataTable[Text] = app.screen.query_one(selector=DataTable)
        shown: list[str] = [str(c) for c in table.get_row(row_key="ANTHROPIC_AUTH_TOKEN")]
        assert not any("0123456789" in s for s in shown)
        await pilot.press("r")
        await pilot.pause()
        shown = [str(c) for c in table.get_row(row_key="ANTHROPIC_AUTH_TOKEN")]
        assert any("sk-0123456789abcdef" in s for s in shown)


async def test_choice_variable_opens_a_list_and_saves_the_choice(tmp_path: Path, profiles_file: Path) -> None:
    write_settings(tmp_path, {"CLAUDE_CODE_EFFORT_LEVEL": "low"})
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_current(app, pilot)
        await move_to_variable(app, pilot, "CLAUDE_CODE_EFFORT_LEVEL")
        await pilot.press("e")
        await pilot.pause()
        assert screen_name(app) == "PickScreen"
        await pilot.press("down", "enter")
        await pilot.pause()
    assert read_env(tmp_path)["CLAUDE_CODE_EFFORT_LEVEL"] == "medium"


async def test_x_asks_before_removing_and_no_keeps_the_value(tmp_path: Path, profiles_file: Path) -> None:
    write_settings(tmp_path, {"ANTHROPIC_MODEL": "m1"})
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_current(app, pilot)
        await move_to_variable(app, pilot, "ANTHROPIC_MODEL")
        await pilot.press("x")
        await pilot.pause()
        assert screen_name(app) == "ConfirmScreen"
        await pilot.press("n")
        await pilot.pause()
    assert read_env(tmp_path) == {"ANTHROPIC_MODEL": "m1"}


async def test_x_then_yes_removes_the_value(tmp_path: Path, profiles_file: Path) -> None:
    write_settings(tmp_path, {"ANTHROPIC_MODEL": "m1"})
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_current(app, pilot)
        await move_to_variable(app, pilot, "ANTHROPIC_MODEL")
        await pilot.press("x")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
    assert "env" not in json.loads((tmp_path / "settings.json").read_text())
    assert (tmp_path / "settings.json.bak").exists()


async def test_the_page_and_the_edit_dialog_tell_how_to_paste(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_current(app, pilot)
        assert "Ctrl+Shift+V" in text_of(app, "#status")
        await pilot.press("e")
        await pilot.pause()
        assert "Ctrl+Shift+V" in text_of(app, "#paste-hint")


async def test_closing_the_verify_dialog_before_the_answer_does_not_crash(
    tmp_path: Path, profiles_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def slow_verify(endpoint: Endpoint, login_found: bool = False) -> list[Check]:
        time.sleep(0.4)
        return [Check(name="url", status="pass", detail="x")]

    monkeypatch.setattr("claude_code_env_editor.tui.pages.verify", slow_verify)
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


# -- apply, save, delete -----------------------------------------------------


async def test_a_applies_replaces_stale_values_after_a_yes(tmp_path: Path, profiles_file: Path) -> None:
    write_settings(tmp_path, {"ANTHROPIC_BASE_URL": "https://openrouter.ai/api", "API_TIMEOUT_MS": "5000"})
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "deepseek")
        await pilot.press("a")
        await pilot.pause()
        assert screen_name(app) == "ConfirmScreen"
        question: str = text_of(app, "#question")
        assert "remove" in question and "API_TIMEOUT_MS" in question
        assert "deepseek-flash[1m]" in question  # a value with brackets shows as it is
        await pilot.press("y")
        await pilot.pause()
        assert "deepseek (the file matches this profile)" in text_of(app, "#banner")
    env: dict[str, str] = read_env(tmp_path)
    assert env["ANTHROPIC_BASE_URL"] == "https://api.deepseek.com/anthropic" and "API_TIMEOUT_MS" not in env


async def test_apply_with_no_answer_writes_nothing(tmp_path: Path, profiles_file: Path) -> None:
    write_settings(tmp_path, {"ANTHROPIC_MODEL": "keep-me"})
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "deepseek")
        await pilot.press("a")
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
    assert read_env(tmp_path) == {"ANTHROPIC_MODEL": "keep-me"}


async def test_m_applies_in_merge_mode(tmp_path: Path, profiles_file: Path) -> None:
    write_settings(tmp_path, {"API_TIMEOUT_MS": "5000"})
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "openrouter")
        await pilot.press("m")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
    env: dict[str, str] = read_env(tmp_path)
    assert env["API_TIMEOUT_MS"] == "5000" and env["ANTHROPIC_BASE_URL"] == "https://openrouter.ai/api"


async def test_a_on_a_profile_page_applies_that_profile(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profile(app, pilot, "openrouter")
        await pilot.press("a")
        await pilot.pause()
        assert screen_name(app) == "ConfirmScreen"
        await pilot.press("y")
        await pilot.pause()
    assert read_env(tmp_path)["ANTHROPIC_BASE_URL"] == "https://openrouter.ai/api"


async def test_s_saves_the_current_values_with_the_key(tmp_path: Path, profiles_file: Path) -> None:
    write_settings(
        tmp_path,
        {"ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic", "ANTHROPIC_AUTH_TOKEN": "sk-1234567890abcd"},
    )
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()
        assert screen_name(app) == "InputScreen"
        app.screen.query_one(selector=Input).value = "work-ds"
        await pilot.press("enter")
        await pilot.pause()
        assert screen_name(app) == "ConfirmScreen"  # the key question
        await pilot.press("y")
        await pilot.pause()
        assert isinstance(app.screen, ProfileListPage) and "work-ds" in app.screen.names
    assert load_profiles(path=profiles_file)["work-ds"].variables["ANTHROPIC_AUTH_TOKEN"] == "sk-1234567890abcd"


async def test_s_can_leave_the_key_out(tmp_path: Path, profiles_file: Path) -> None:
    write_settings(
        tmp_path,
        {"ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic", "ANTHROPIC_AUTH_TOKEN": "sk-1234567890abcd"},
    )
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()
        app.screen.query_one(selector=Input).value = "nokey"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
    assert not load_profiles(path=profiles_file)["nokey"].has_key


async def test_save_refuses_a_built_in_or_bad_name(tmp_path: Path, profiles_file: Path) -> None:
    write_settings(tmp_path, {"ANTHROPIC_MODEL": "m"})
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()
        for bad in ("deepseek", "has space"):
            app.screen.query_one(selector=Input).value = bad
            await pilot.press("enter")
            await pilot.pause()
            assert screen_name(app) == "InputScreen"
            assert text_of(app, "#error") != ""
    assert set(load_profiles(path=profiles_file)) == set(templates())  # nothing was added


async def test_x_deletes_any_profile_after_a_yes(tmp_path: Path, profiles_file: Path) -> None:
    save_profile(profile=Profile(name="mine", variables={"ANTHROPIC_MODEL": "m"}), path=profiles_file)
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        for name in ("mine", "deepseek"):
            await move_to_profile(app, pilot, name)
            await pilot.press("x")
            await pilot.pause()
            assert screen_name(app) == "ConfirmScreen"
            await pilot.press("n" if name == "deepseek" else "y")
            await pilot.pause()
        assert isinstance(app.screen, ProfileListPage)
        assert "mine" not in app.screen.names and "deepseek" in app.screen.names
    assert "mine" not in load_profiles(path=profiles_file)


async def test_r_renames_a_profile_and_keeps_the_cursor_on_it(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "deepseek")
        await pilot.press("r")
        await pilot.pause()
        assert screen_name(app) == "InputScreen"
        app.screen.query_one(selector=Input).value = "work-ds"
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ProfileListPage)
        assert "work-ds" in app.screen.names and "deepseek" not in app.screen.names
        assert app.screen.selected_name() == "work-ds"
    assert "work-ds" in load_profiles(path=profiles_file)


async def test_rename_refuses_an_existing_or_invalid_name(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "deepseek")
        await pilot.press("r")
        await pilot.pause()
        for bad in ("openrouter", "has space"):
            app.screen.query_one(selector=Input).value = bad
            await pilot.press("enter")
            await pilot.pause()
            assert screen_name(app) == "InputScreen"
            assert text_of(app, "#error") != ""
    assert "deepseek" in load_profiles(path=profiles_file)


# -- target ------------------------------------------------------------------


async def test_a_key_is_refused_for_a_shared_project_file(tmp_path: Path, profiles_file: Path) -> None:
    save_profile(
        profile=Profile(name="keyed", variables={"ANTHROPIC_AUTH_TOKEN": "sk-1234567890abcd"}), path=profiles_file
    )
    shared: Path = tmp_path / "proj" / ".claude" / "settings.json"
    target: Target = Target.from_file(settings_file=shared, known_dirs=[])
    app: EnvEditorApp = EnvEditorApp(target=target)
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "keyed")
        await pilot.press("a")
        await pilot.pause()
        assert isinstance(app.screen, ProfileListPage)  # no confirm dialog
        status: str = text_of(app, "#status")
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
        assert screen_name(app) == "InputScreen"
        app.screen.query_one(selector=Input).value = str(other)
        await pilot.press("enter")
        await pilot.pause()
        assert app.target.settings_file == other and not app.target.user_level
        page: VariablesPage = await open_current(app, pilot)
        assert next(r for r in page.rows if r.name == "ANTHROPIC_MODEL").value == "project-model"


def test_tui_command_accepts_a_file_option() -> None:
    args = cli.build_parser().parse_args(["tui", "--file", "x.json"])
    assert args.file == Path("x.json")


# -- applied in, and new profiles --------------------------------------------


def make_login(home: Path, name: str, env: dict[str, str]) -> Path:
    directory: Path = home / name
    directory.mkdir(parents=True)
    (directory / ".claude.json").write_text("{}")
    (directory / "settings.json").write_text(json.dumps({"env": env}))
    return directory


def cell(app: EnvEditorApp, row_key: str, column: int) -> str:
    table: DataTable[Text] = app.screen.query_one(selector=DataTable)
    return str(table.get_row(row_key=row_key)[column])


async def choose(app: EnvEditorApp, pilot: Pilot[None], option_id: str) -> None:
    """Highlight the option with this id in the open list and press Enter."""
    option_list: OptionList = app.screen.query_one(selector=OptionList)
    ids: list[str | None] = [option_list.get_option_at_index(index=i).id for i in range(option_list.option_count)]
    option_list.highlighted = ids.index(option_id)
    await pilot.pause()
    await pilot.press("enter")
    await pilot.pause()


async def test_applied_in_names_the_logins_whose_file_matches(
    tmp_path: Path, profiles_file: Path, isolated_home: Path
) -> None:
    deepseek: dict[str, str] = templates()["deepseek"].variables
    make_login(isolated_home, ".claude-work", deepseek)
    make_login(isolated_home, ".acme-login", {"ANTHROPIC_MODEL": "something-else"})
    app: EnvEditorApp = EnvEditorApp(config_dir=isolated_home / ".claude")
    async with app.run_test() as pilot:
        await pilot.pause()
        assert "~/.claude-work" in cell(app, "deepseek", 3)
        assert cell(app, "openrouter", 3) == "-"


async def test_n_creates_a_profile_from_a_template(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        await choose(app, pilot, "template")
        await choose(app, pilot, "ollama")
        assert screen_name(app) == "InputScreen"
        app.screen.query_one(selector=Input).value = "my-ollama"
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ProfileListPage) and "my-ollama" in app.screen.names
    saved: dict[str, Profile] = load_profiles(path=profiles_file)
    assert saved["my-ollama"].variables == templates()["ollama"].variables


async def test_n_imports_the_values_of_a_login_folder_with_its_key(
    tmp_path: Path, profiles_file: Path, isolated_home: Path
) -> None:
    values: dict[str, str] = {"ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic", "ANTHROPIC_AUTH_TOKEN": "sk-123456789012"}
    make_login(isolated_home, ".claude-work", values)
    app: EnvEditorApp = EnvEditorApp(config_dir=isolated_home / ".claude")
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        await choose(app, pilot, "folder")
        option_list: OptionList = app.screen.query_one(selector=OptionList)
        labels: list[str] = [str(option_list.get_option_at_index(index=i).prompt) for i in range(option_list.option_count)]
        await choose(app, pilot, str(labels.index("~/.claude-work")))
        assert screen_name(app) == "InputScreen"
        app.screen.query_one(selector=Input).value = "imported"
        await pilot.press("enter")
        await pilot.pause()
        assert screen_name(app) == "ConfirmScreen"  # the key question
        await pilot.press("y")
        await pilot.pause()
    assert load_profiles(path=profiles_file)["imported"].variables == values


async def test_n_imports_the_local_settings_of_a_project_folder(
    tmp_path: Path, profiles_file: Path, isolated_home: Path
) -> None:
    project: Path = tmp_path / "app"
    (project / ".claude").mkdir(parents=True)
    (project / ".claude" / "settings.local.json").write_text(json.dumps({"env": {"ANTHROPIC_MODEL": "project-model"}}))
    app: EnvEditorApp = EnvEditorApp(config_dir=isolated_home / ".claude")
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        await choose(app, pilot, "folder")
        await choose(app, pilot, "__project__")
        assert screen_name(app) == "InputScreen"
        app.screen.query_one(selector=Input).value = str(project)
        await pilot.press("enter")
        await pilot.pause()
        app.screen.query_one(selector=Input).value = "from-project"
        await pilot.press("enter")
        await pilot.pause()
    assert load_profiles(path=profiles_file)["from-project"].variables == {"ANTHROPIC_MODEL": "project-model"}


async def test_n_refuses_a_folder_without_known_variables(
    tmp_path: Path, profiles_file: Path, isolated_home: Path
) -> None:
    make_login(isolated_home, ".empty", {"MY_OWN": "1"})
    app: EnvEditorApp = EnvEditorApp(config_dir=isolated_home / ".claude")
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        await choose(app, pilot, "folder")
        option_list: OptionList = app.screen.query_one(selector=OptionList)
        labels: list[str] = [str(option_list.get_option_at_index(index=i).prompt) for i in range(option_list.option_count)]
        await choose(app, pilot, str(labels.index("~/.empty")))
        assert isinstance(app.screen, ProfileListPage)
        assert "no known variables" in text_of(app, "#status")


async def test_n_copies_a_profile(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        await choose(app, pilot, "copy")
        await choose(app, pilot, "deepseek")
        app.screen.query_one(selector=Input).value = "ds-two"
        await pilot.press("enter")
        await pilot.pause()
    saved: dict[str, Profile] = load_profiles(path=profiles_file)
    assert saved["ds-two"].variables == saved["deepseek"].variables
