from pathlib import Path

from rich.text import Text
from textual.widgets import Input, Static

from claude_code_env_editor.profiles import Profile, load_profiles, save_profile
from claude_code_env_editor.tui.app import EnvEditorApp
from claude_code_env_editor.tui.pages import ProfileListPage, VariablesPage
from tests.tui.helpers import (
    choose,
    move_to_profile,
    move_to_variable,
    open_profile,
    read_env,
    screen_name,
    write_settings,
)

# -- key hints use the colour of the footer keys -------------------------------


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


# -- a click outside a dialog closes it ----------------------------------------


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
