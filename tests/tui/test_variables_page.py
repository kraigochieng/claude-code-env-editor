from pathlib import Path

from rich.text import Text
from textual.binding import Binding
from textual.widgets import DataTable, Input

from claude_code_env_editor.profiles import Profile, load_profiles, save_profile
from claude_code_env_editor.tui.app import EnvEditorApp
from claude_code_env_editor.tui.pages import ProfileListPage, VariablesPage
from tests.tui.helpers import move_to_variable, open_profile, screen_name, text_of

# -- one profile ---------------------------------------------------------------


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


# -- new profiles --------------------------------------------------------------


async def test_variables_page_has_only_variable_and_value_columns(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profile(app, pilot, "deepseek")
        table: DataTable[Text] = app.screen.query_one(selector=DataTable)
        assert [str(column.label) for column in table.columns.values()] == ["Variable", "Value"]


# -- reveal lives in the edit box of a key -------------------------------------


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
