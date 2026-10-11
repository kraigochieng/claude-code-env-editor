from pathlib import Path

from textual.binding import Binding
from textual.widgets import Input

from claude_code_env_editor.profiles import Profile, save_profile, templates
from claude_code_env_editor.target import Target
from claude_code_env_editor.tui.app import EnvEditorApp
from claude_code_env_editor.tui.pages import ProfileListPage, VariablesPage
from tests.tui.helpers import (
    cell,
    choose,
    labels_of,
    make_login,
    move_to_profile,
    open_profile,
    read_env,
    screen_name,
    text_of,
    write_settings,
)

# -- apply: choose a place, see the changes ------------------------------------


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


async def test_there_is_no_merge_key_and_the_titles_name_no_mode(tmp_path: Path, profiles_file: Path) -> None:
    write_settings(tmp_path, {"API_TIMEOUT_MS": "5000"})
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "openrouter")
        await pilot.press("m")  # m is not a key of the list any more
        await pilot.pause()
        assert isinstance(app.screen, ProfileListPage)
        keys: set[str] = {b.key for b in app.screen.BINDINGS if isinstance(b, Binding)}
        assert "m" not in keys
        await pilot.press("question_mark")
        await pilot.pause()
        assert "merge" not in text_of(app, "#body").lower()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        assert "(replace mode)" not in text_of(app, ".heading") and "merge" not in text_of(app, ".heading").lower()
        await choose(app, pilot, "0")
        assert screen_name(app) == "ConfirmScreen"
        assert "mode" not in text_of(app, ".heading")
        await pilot.press("y")
        await pilot.pause()
    env: dict[str, str] = read_env(tmp_path / "settings.json")
    assert "API_TIMEOUT_MS" not in env and env["ANTHROPIC_BASE_URL"] == "https://openrouter.ai/api"


async def test_the_profile_page_has_no_apply_copy_or_verify_keys(tmp_path: Path, profiles_file: Path) -> None:
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_profile(app, pilot, "openrouter")
        keys: set[str] = {b.key for b in app.screen.BINDINGS if isinstance(b, Binding)}
        assert keys == {"e", "x", "escape", "question_mark", "q"}
        for key in ("a", "c", "v"):
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


# -- the apply dialog shows the variables of the profile -----------------------


async def test_the_place_list_shows_the_variables_of_the_profile_with_the_key_masked(
    tmp_path: Path, profiles_file: Path
) -> None:
    save_profile(
        profile=Profile(
            name="keyed",
            variables={
                "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
                "ANTHROPIC_AUTH_TOKEN": "sk-0123456789abcdef",
                "ANTHROPIC_MODEL": "deepseek-flash[1m]",
            },
        ),
        path=profiles_file,
    )
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "keyed")
        await pilot.press("a")
        await pilot.pause()
        assert screen_name(app) == "PickScreen"
        intro: str = text_of(app, "#intro")
        assert "This profile sets:" in intro
        assert "ANTHROPIC_BASE_URL" in intro and "https://api.deepseek.com/anthropic" in intro
        assert "deepseek-flash[1m]" in intro
        assert "ANTHROPIC_AUTH_TOKEN" in intro and "0123456789" not in intro  # the key is masked
        assert [name for name in ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_MODEL")
                if intro.index(name) >= 0] == ["ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_MODEL"]


async def test_the_place_list_of_an_empty_profile_says_what_applying_does(tmp_path: Path, profiles_file: Path) -> None:
    save_profile(profile=Profile(name="empty", variables={}), path=profiles_file)
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "empty")
        await pilot.press("a")
        await pilot.pause()
        assert "no variables" in text_of(app, "#intro")
        assert "removes the known variables" in text_of(app, "#intro")


async def test_enter_in_the_place_list_works_at_once_without_a_tab(tmp_path: Path, profiles_file: Path) -> None:
    write_settings(tmp_path, {"API_TIMEOUT_MS": "5000"})
    app: EnvEditorApp = EnvEditorApp(config_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await move_to_profile(app, pilot, "deepseek")
        await pilot.press("a")
        await pilot.pause()
        await pilot.press("enter")  # the list has the focus, although the dialog has a variables box above it
        await pilot.pause()
        assert screen_name(app) == "ConfirmScreen"
