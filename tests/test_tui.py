import json
import time
from pathlib import Path
from typing import cast

import pytest
from rich.text import Text
from textual.binding import Binding
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




# -- the main page: profiles -------------------------------------------------


async def test_main_page_lists_the_profiles(tmp_path: Path, profiles_file: Path) -> None:
    save_profile(profile=Profile(name="mine", variables={"ANTHROPIC_MODEL": "m"}), path=profiles_file)
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ProfileListPage)
        assert "deepseek" in app.screen.names and "mine" in app.screen.names
        assert app.screen.names.index("mine") > app.screen.names.index("deepseek")


async def test_main_page_shows_no_file_and_no_config_directory(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        banner: str = text_of(app, "#banner")
        assert "profiles" in banner and "settings.json" not in banner and str(tmp_path) not in banner


async def test_the_old_target_keys_are_gone(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        for key in ("d", "s", "r"):  # the old keys: switch place, save from file, rename
            await pilot.press(key)
            await pilot.pause()
            assert isinstance(app.screen, ProfileListPage)


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




async def test_main_page_has_only_name_endpoint_and_key_columns(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        table: DataTable[Text] = app.screen.query_one(selector=DataTable)
        titles: list[str] = [str(column.label) for column in table.columns.values()]
        assert titles == ["Profile", "Endpoint", "Key"]


async def test_right_arrow_opens_the_profile_and_left_arrow_goes_back(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "openrouter")
        await pilot.press("right")
        await pilot.pause()
        assert isinstance(app.screen, VariablesPage) and app.screen.source.name == "openrouter"
        await pilot.press("left")
        await pilot.pause()
        assert isinstance(app.screen, ProfileListPage)
        assert app.screen.selected_name() == "openrouter"  # the cursor stays on the profile


# -- one profile -------------------------------------------------------------


async def test_enter_opens_a_profile_and_esc_goes_back(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        page: VariablesPage = await open_profile(app, pilot, "deepseek")
        values: dict[str, str] = {r.name: r.value for r in page.rows}
        assert values["ANTHROPIC_BASE_URL"] == "https://api.deepseek.com/anthropic"
        banner: str = text_of(app, "#banner")
        assert "deepseek" in banner and "settings.json" not in banner
        assert "endpoint" not in banner and "auth" not in banner
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ProfileListPage)


async def test_editing_a_variable_saves_it_in_profiles_toml_and_not_in_a_file(
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
    assert not (tmp_path / "settings.json").exists()


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


async def test_removing_a_variable_asks_first(tmp_path: Path, profiles_file: Path) -> None:
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




async def test_choice_variable_opens_a_list_and_saves_the_choice(tmp_path: Path, profiles_file: Path) -> None:
    save_profile(profile=Profile(name="mine", variables={"CLAUDE_CODE_EFFORT_LEVEL": "low"}), path=profiles_file)
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profile(app, pilot, "mine")
        await move_to_variable(app, pilot, "CLAUDE_CODE_EFFORT_LEVEL")
        await pilot.press("e")
        await pilot.pause()
        assert screen_name(app) == "PickScreen"
        await pilot.press("down", "enter")
        await pilot.pause()
    assert load_profiles(path=profiles_file)["mine"].variables["CLAUDE_CODE_EFFORT_LEVEL"] == "medium"


async def test_the_page_and_the_edit_dialog_tell_how_to_paste(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profile(app, pilot, "deepseek")
        assert "Ctrl+Shift+V" in text_of(app, "#status")
        await pilot.press("e")
        await pilot.pause()
        assert "Ctrl+Shift+V" in text_of(app, "#paste-hint")


async def test_c_on_the_list_copies_a_profile_and_selects_the_copy(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "deepseek")
        await pilot.press("c")
        await pilot.pause()
        assert screen_name(app) == "InputScreen"
        app.screen.query_one(selector=Input).value = "deepseek-copy"
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ProfileListPage) and app.screen.selected_name() == "deepseek-copy"
    copied: Profile = load_profiles(path=profiles_file)["deepseek-copy"]
    assert copied.variables["ANTHROPIC_BASE_URL"] == "https://api.deepseek.com/anthropic"


# -- verify ------------------------------------------------------------------


async def test_verify_on_the_list_uses_the_endpoint_of_the_profile_under_the_cursor(
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


# -- apply: choose a place, see the changes ---------------------------------


async def test_a_lists_the_places_with_the_state_of_the_profile(
    tmp_path: Path, profiles_file: Path, isolated_home: Path
) -> None:
    make_login(isolated_home, ".same", templates()["deepseek"].variables)
    make_login(isolated_home, ".other", {"ANTHROPIC_MODEL": "x", "API_TIMEOUT_MS": "5"})
    (isolated_home / ".claude").mkdir()
    app: EnvEditorApp = EnvEditorApp(config_dir=isolated_home / ".claude")
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "deepseek")
        await pilot.press("a")
        await pilot.pause()
        assert screen_name(app) == "PickScreen"
        text: str = "\n".join(labels_of(app))
        assert "~/.same  matches this profile" in text
        assert "~/.other  has other values" in text
        assert "~/.claude  empty" in text
        assert "(a project folder: type its path)" in text


async def test_a_applies_to_the_chosen_place_after_a_yes(tmp_path: Path, profiles_file: Path) -> None:
    write_settings(tmp_path, {"ANTHROPIC_BASE_URL": "https://openrouter.ai/api", "API_TIMEOUT_MS": "5000"})
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "deepseek")
        await pilot.press("a")
        await pilot.pause()
        await choose(app, pilot, "0")  # the place from config_dir is first
        assert screen_name(app) == "ConfirmScreen"
        question: str = text_of(app, "#question")
        assert "remove" in question and "API_TIMEOUT_MS" in question
        assert "deepseek-flash[1m]" in question  # a value with brackets shows as it is
        await pilot.press("y")
        await pilot.pause()
        assert "deepseek" in cell(app, "deepseek", 0)
    env: dict[str, str] = read_env(tmp_path / "settings.json")
    assert env["ANTHROPIC_BASE_URL"] == "https://api.deepseek.com/anthropic" and "API_TIMEOUT_MS" not in env


async def test_apply_with_no_answer_writes_nothing(tmp_path: Path, profiles_file: Path) -> None:
    write_settings(tmp_path, {"ANTHROPIC_MODEL": "keep-me"})
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "deepseek")
        await pilot.press("a")
        await pilot.pause()
        await choose(app, pilot, "0")
        await pilot.press("n")
        await pilot.pause()
    assert read_env(tmp_path / "settings.json") == {"ANTHROPIC_MODEL": "keep-me"}


async def test_escape_in_the_place_list_writes_nothing(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "deepseek")
        await pilot.press("a")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ProfileListPage)
    assert not (tmp_path / "settings.json").exists()


async def test_m_applies_in_merge_mode(tmp_path: Path, profiles_file: Path) -> None:
    write_settings(tmp_path, {"API_TIMEOUT_MS": "5000"})
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "openrouter")
        await pilot.press("m")
        await pilot.pause()
        await choose(app, pilot, "0")
        await pilot.press("y")
        await pilot.pause()
    env: dict[str, str] = read_env(tmp_path / "settings.json")
    assert env["API_TIMEOUT_MS"] == "5000" and env["ANTHROPIC_BASE_URL"] == "https://openrouter.ai/api"


async def test_the_profile_page_has_no_apply_merge_copy_or_verify_keys(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profile(app, pilot, "openrouter")
        keys: set[str] = {b.key for b in app.screen.BINDINGS if isinstance(b, Binding)}
        assert keys == {"e", "x", "escape", "question_mark", "q"}
        for key in ("a", "m", "c", "v"):
            await pilot.press(key)
            await pilot.pause()
            assert isinstance(app.screen, VariablesPage)  # no dialog opened
        await pilot.press("question_mark")
        await pilot.pause()
        help_text: str = text_of(app, "#body")
        assert "Apply" not in help_text and "apply" not in help_text and "Verify" not in help_text
    assert not (tmp_path / "settings.json").exists()


async def test_apply_to_a_project_folder_writes_the_local_settings_file_with_the_key(
    tmp_path: Path, profiles_file: Path
) -> None:
    save_profile(
        profile=Profile(
            name="keyed",
            variables={"ANTHROPIC_BASE_URL": "https://openrouter.ai/api", "ANTHROPIC_AUTH_TOKEN": "sk-or-v1-0123456789"},
        ),
        path=profiles_file,
    )
    project: Path = tmp_path / "app"
    project.mkdir()
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "keyed")
        await pilot.press("a")
        await pilot.pause()
        await choose(app, pilot, "__project__")
        app.screen.query_one(selector=Input).value = str(project)
        await pilot.press("enter")
        await pilot.pause()
        assert screen_name(app) == "ConfirmScreen"
        await pilot.press("y")
        await pilot.pause()
    local: Path = project / ".claude" / "settings.local.json"
    assert read_env(local)["ANTHROPIC_AUTH_TOKEN"] == "sk-or-v1-0123456789"


async def test_a_project_folder_that_does_not_exist_is_refused(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "deepseek")
        await pilot.press("a")
        await pilot.pause()
        await choose(app, pilot, "__project__")
        app.screen.query_one(selector=Input).value = str(tmp_path / "missing")
        await pilot.press("enter")
        await pilot.pause()
        assert screen_name(app) == "InputScreen" and text_of(app, "#error") != ""


async def test_a_key_is_refused_for_a_shared_project_file(tmp_path: Path, profiles_file: Path) -> None:
    save_profile(
        profile=Profile(name="keyed", variables={"ANTHROPIC_AUTH_TOKEN": "sk-1234567890abcd"}), path=profiles_file
    )
    shared: Path = tmp_path / "proj" / ".claude" / "settings.json"
    app: EnvEditorApp = EnvEditorApp(target=Target.from_file(settings_file=shared, known_dirs=[]))
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "keyed")
        await pilot.press("a")
        await pilot.pause()
        await choose(app, pilot, "0")  # the place from --file is first
        assert isinstance(app.screen, ProfileListPage)  # no confirm dialog
        status: str = text_of(app, "#status")
        assert "Refused" in status and "committed" in status
    assert not shared.exists()


async def test_the_place_from_file_or_config_dir_is_listed_first(tmp_path: Path, profiles_file: Path) -> None:
    other: Path = tmp_path / "proj" / ".claude" / "settings.local.json"
    app: EnvEditorApp = EnvEditorApp(target=Target.from_file(settings_file=other, known_dirs=[]))
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "deepseek")
        await pilot.press("a")
        await pilot.pause()
        assert labels_of(app)[0].startswith(str(other))


async def test_nothing_to_change_when_the_place_already_matches(tmp_path: Path, profiles_file: Path) -> None:
    write_settings(tmp_path, templates()["openrouter"].variables)
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "openrouter")
        await pilot.press("a")
        await pilot.pause()
        await choose(app, pilot, "0")
        assert isinstance(app.screen, ProfileListPage)
        assert "Nothing to change" in text_of(app, "#status")


# -- delete and rename -------------------------------------------------------


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


async def test_e_edits_the_name_of_a_profile_and_keeps_the_cursor_on_it(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "deepseek")
        await pilot.press("e")
        await pilot.pause()
        assert screen_name(app) == "InputScreen"
        assert "Edit profile" in text_of(app, ".heading")
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
        await pilot.press("e")
        await pilot.pause()
        for bad in ("openrouter", "has space"):
            app.screen.query_one(selector=Input).value = bad
            await pilot.press("enter")
            await pilot.pause()
            assert screen_name(app) == "InputScreen"
            assert text_of(app, "#error") != ""
    assert "deepseek" in load_profiles(path=profiles_file)


# -- new profiles ------------------------------------------------------------
















def test_tui_command_accepts_a_file_option() -> None:
    args = cli.build_parser().parse_args(["tui", "--file", "x.json"])
    assert args.file == Path("x.json")


async def test_variables_page_has_only_variable_and_value_columns(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profile(app, pilot, "deepseek")
        table: DataTable[Text] = app.screen.query_one(selector=DataTable)
        assert [str(column.label) for column in table.columns.values()] == ["Variable", "Value"]


# -- reveal lives in the edit box of a key ------------------------------------


async def test_a_secret_is_always_masked_in_the_table_and_has_no_reveal_key(tmp_path: Path, profiles_file: Path) -> None:
    save_profile(
        profile=Profile(name="keyed", variables={"ANTHROPIC_AUTH_TOKEN": "sk-0123456789abcdef"}), path=profiles_file
    )
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profile(app, pilot, "keyed")
        row: list[str] = [str(c) for c in app.screen.query_one(selector=DataTable).get_row(row_key="ANTHROPIC_AUTH_TOKEN")]
        assert not any("0123456789" in cell_text for cell_text in row)
        await pilot.press("r")  # r is not a key of this page any more
        await pilot.pause()
        row = [str(c) for c in app.screen.query_one(selector=DataTable).get_row(row_key="ANTHROPIC_AUTH_TOKEN")]
        assert not any("0123456789" in cell_text for cell_text in row)
        keys: set[str] = {binding.key for binding in app.screen.BINDINGS if isinstance(binding, Binding)}
        assert "r" not in keys


async def test_the_edit_box_of_a_key_shows_and_hides_the_key_with_ctrl_r(tmp_path: Path, profiles_file: Path) -> None:
    save_profile(
        profile=Profile(name="keyed", variables={"ANTHROPIC_AUTH_TOKEN": "sk-0123456789abcdef"}), path=profiles_file
    )
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profile(app, pilot, "keyed")
        await move_to_variable(app, pilot, "ANTHROPIC_AUTH_TOKEN")
        await pilot.press("e")
        await pilot.pause()
        box: Input = app.screen.query_one(selector=Input)
        assert box.password is True
        assert "Ctrl+R" in text_of(app, "#reveal-hint")
        await pilot.press("ctrl+r")
        await pilot.pause()
        assert box.password is False and box.value == "sk-0123456789abcdef"
        await pilot.press("ctrl+r")
        await pilot.pause()
        assert box.password is True


async def test_the_edit_box_of_a_plain_variable_has_no_reveal_hint(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profile(app, pilot, "deepseek")
        await move_to_variable(app, pilot, "ANTHROPIC_MODEL")
        await pilot.press("e")
        await pilot.pause()
        assert not app.screen.query("#reveal-hint")
        box: Input = app.screen.query_one(selector=Input)
        await pilot.press("ctrl+r")
        await pilot.pause()
        assert box.password is False  # nothing changed


async def test_the_api_key_variable_has_the_reveal_control_too(tmp_path: Path, profiles_file: Path) -> None:
    save_profile(
        profile=Profile(
            name="keyed",
            variables={"ANTHROPIC_BASE_URL": "https://api.anthropic.com", "ANTHROPIC_API_KEY": "sk-ant-0123456789"},
        ),
        path=profiles_file,
    )
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profile(app, pilot, "keyed")
        await move_to_variable(app, pilot, "ANTHROPIC_API_KEY")
        await pilot.press("e")
        await pilot.pause()
        assert "Ctrl+R" in text_of(app, "#reveal-hint")


# -- new profile from scratch -------------------------------------------------


async def test_n_creates_an_empty_profile_and_opens_it(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        assert screen_name(app) == "InputScreen"  # one question: the name
        app.screen.query_one(selector=Input).value = "scratch"
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, VariablesPage) and app.screen.source.name == "scratch"
        assert all(row.value == "" for row in app.screen.rows)
        assert "New profile" in text_of(app, "#status")
        await pilot.press("e")  # the cursor is on the first variable, so e edits it at once
        await pilot.pause()
        app.screen.query_one(selector=Input).value = "https://api.deepseek.com/anthropic"
        await pilot.press("enter")
        await pilot.pause()
    assert load_profiles(path=profiles_file)["scratch"].variables == {
        "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic"
    }


async def test_n_refuses_a_name_that_exists_also_in_another_case(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        for bad in ("deepseek", "DeepSeek", "has space", ""):
            app.screen.query_one(selector=Input).value = bad
            await pilot.press("enter")
            await pilot.pause()
            assert screen_name(app) == "InputScreen" and text_of(app, "#error") != ""
    assert [n for n in load_profiles(path=profiles_file) if n.casefold() == "deepseek"] == ["deepseek"]


async def test_escape_in_the_new_profile_box_creates_nothing(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        before: list[str] = list(load_profiles(path=profiles_file))
        await pilot.press("n")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ProfileListPage)
    assert list(load_profiles(path=profiles_file)) == before


async def test_edit_and_copy_refuse_a_name_in_another_case(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "zai")
        await pilot.press("e")
        await pilot.pause()
        app.screen.query_one(selector=Input).value = "OpenRouter"
        await pilot.press("enter")
        await pilot.pause()
        assert screen_name(app) == "InputScreen" and text_of(app, "#error") != ""
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        app.screen.query_one(selector=Input).value = "MOONSHOT"
        await pilot.press("enter")
        await pilot.pause()
        assert screen_name(app) == "InputScreen" and text_of(app, "#error") != ""

# -- key hints use the colour of the footer keys ------------------------------


def test_hint_line_uses_the_footer_key_colour() -> None:
    from claude_code_env_editor.tui.dialogs import hint_line, key_color, key_sentence

    app: EnvEditorApp = EnvEditorApp(config_dir=Path("."))
    color: str = key_color(app=app)
    assert color.lower() == "#ffa62b"
    line: Text = hint_line(app=app, items=[("enter", "save"), ("esc", "cancel")])
    styled: dict[str, str] = {line.plain[s.start : s.end]: str(s.style) for s in line.spans}
    assert styled["enter"] == f"bold {color}" and styled["esc"] == f"bold {color}"
    sentence: Text = key_sentence(app=app, before="Paste with ", key="Ctrl+Shift+V", after=" now.")
    assert [sentence.plain[s.start : s.end] for s in sentence.spans if str(s.style) == f"bold {color}"] == [
        "Ctrl+Shift+V"
    ]


async def test_the_dialogs_show_their_keys_in_the_footer_colour(tmp_path: Path, profiles_file: Path) -> None:
    from claude_code_env_editor.tui.dialogs import key_color

    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        footer_color: str = str(app.get_css_variables()["footer-key-foreground"])
        assert key_color(app=app) == footer_color
        await pilot.press("n")
        await pilot.pause()
        hints: list[Static] = list(app.screen.query(".hint").results(Static))
        assert hints, "the dialog has hint lines"
        spans: list[str] = []
        for hint in hints:
            content: object = hint.content  # the Text that the dialog built
            if isinstance(content, Text):
                spans += [str(span.style) for span in content.spans]
        assert f"bold {footer_color}" in spans


# -- a click outside a dialog closes it ---------------------------------------


async def test_a_click_outside_the_edit_box_closes_it_without_a_change(tmp_path: Path, profiles_file: Path) -> None:
    save_profile(profile=Profile(name="mine", variables={"ANTHROPIC_MODEL": "m"}), path=profiles_file)
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profile(app, pilot, "mine")
        await move_to_variable(app, pilot, "ANTHROPIC_MODEL")
        await pilot.press("e")
        await pilot.pause()
        app.screen.query_one(selector=Input).value = "changed"
        await pilot.click(offset=(0, 0))
        await pilot.pause()
        assert isinstance(app.screen, VariablesPage)
    assert load_profiles(path=profiles_file)["mine"].variables == {"ANTHROPIC_MODEL": "m"}


async def test_a_click_inside_the_dialog_keeps_it_open(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        await pilot.click(".heading")
        await pilot.pause()
        assert screen_name(app) == "InputScreen"


async def test_a_click_outside_the_confirm_dialog_answers_no(tmp_path: Path, profiles_file: Path) -> None:
    write_settings(tmp_path, {"API_TIMEOUT_MS": "5000"})
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "deepseek")
        await pilot.press("a")
        await pilot.pause()
        await choose(app, pilot, "0")
        assert screen_name(app) == "ConfirmScreen"
        await pilot.click(offset=(0, 0))
        await pilot.pause()
        assert isinstance(app.screen, ProfileListPage)
    assert read_env(tmp_path / "settings.json") == {"API_TIMEOUT_MS": "5000"}


async def test_a_click_outside_closes_the_pick_list_the_help_and_the_name_box(
    tmp_path: Path, profiles_file: Path
) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        for key, name in (("a", "PickScreen"), ("question_mark", "TextScreen"), ("e", "InputScreen")):
            await move_to_profile(app, pilot, "deepseek")
            await pilot.press(key)
            await pilot.pause()
            assert screen_name(app) == name
            await pilot.click(offset=(0, 0))
            await pilot.pause()
            assert isinstance(app.screen, ProfileListPage)
