from pathlib import Path

from rich.text import Text
from textual.widgets import DataTable, Input

from claude_code_env_editor.profiles import Profile, load_profiles, save_profile
from claude_code_env_editor.tui.app import EnvEditorApp
from claude_code_env_editor.tui.pages import ProfileListPage, VariablesPage
from tests.tui.helpers import move_to_profile, screen_name, text_of

# -- the main page: profiles ---------------------------------------------------


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


# -- delete and rename ---------------------------------------------------------


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


# -- new profile from scratch --------------------------------------------------


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
