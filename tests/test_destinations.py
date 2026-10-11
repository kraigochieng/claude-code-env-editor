import json
from pathlib import Path

from claude_code_env_editor.destinations import (
    Destination,
    DestinationState,
    destination_state,
    login_destinations,
    project_destination,
    short_path,
)
from claude_code_env_editor.profiles import Profile
from claude_code_env_editor.target import Target

DEEPSEEK: dict[str, str] = {
    "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
    "ANTHROPIC_MODEL": "deepseek-flash",
}


def make_login(home: Path, name: str, env: dict[str, str] | None) -> Destination:
    directory: Path = home / name
    directory.mkdir(parents=True)
    (directory / ".claude.json").write_text("{}")
    if env is not None:
        (directory / "settings.json").write_text(json.dumps({"env": env}))
    return Destination(label=f"~/{name}", settings_file=directory / "settings.json", kind="login", config_dir=directory)


def test_short_path_writes_the_home_directory_as_tilde(tmp_path: Path) -> None:
    assert short_path(path=tmp_path / ".claude-work", home=tmp_path) == "~/.claude-work"
    assert short_path(path=Path("/etc/x"), home=tmp_path) == "/etc/x"


def test_login_destinations_cover_default_registered_and_found_directories(tmp_path: Path) -> None:
    make_login(tmp_path, ".acme-login", None)
    found: list[Destination] = login_destinations(home=tmp_path, registry_path=tmp_path / "none.toml", environ={})
    labels: list[str] = [d.label for d in found]
    assert labels[0] == "~/.claude"  # the default directory comes first, even without files
    assert "~/.acme-login" in labels
    assert all(d.kind == "login" and d.settings_file.name == "settings.json" for d in found)


def test_project_destination_is_the_local_settings_file(tmp_path: Path) -> None:
    project: Destination = project_destination(folder=tmp_path / "app", home=tmp_path, environ={})
    assert project.kind == "project"
    assert project.settings_file == tmp_path / "app" / ".claude" / "settings.local.json"
    assert project.config_dir == tmp_path / ".claude"  # the default login applies
    assert project.label == "~/app"


def test_to_target_marks_a_login_as_user_level_and_a_project_as_not(tmp_path: Path) -> None:
    login: Destination = make_login(tmp_path, ".w", {})
    project: Destination = project_destination(folder=tmp_path / "app", home=tmp_path, environ={})
    login_target: Target = login.to_target()
    assert login_target.user_level and login_target.config_dir == login.config_dir
    assert not project.to_target().user_level


def test_state_matches_differs_empty_and_unreadable(tmp_path: Path) -> None:
    profile: Profile = Profile(name="ds", variables=DEEPSEEK)
    same: Destination = make_login(tmp_path, ".same", DEEPSEEK)
    other: Destination = make_login(tmp_path, ".other", {**DEEPSEEK, "ANTHROPIC_MODEL": "other", "API_TIMEOUT_MS": "5"})
    empty: Destination = make_login(tmp_path, ".empty", None)
    custom_only: Destination = make_login(tmp_path, ".custom", {"MY_OWN_VARIABLE": "1"})
    broken: Destination = make_login(tmp_path, ".broken", None)
    broken.settings_file.write_text("{bad")

    assert destination_state(profile=profile, destination=same).kind == "matches"
    differs: DestinationState = destination_state(profile=profile, destination=other)
    assert differs.kind == "differs" and differs.differing == ["ANTHROPIC_MODEL", "API_TIMEOUT_MS"]
    assert differs.text == "has other values (2 differ)"
    assert destination_state(profile=profile, destination=empty).kind == "empty"
    assert destination_state(profile=profile, destination=custom_only).kind == "empty"  # no known variables
    assert destination_state(profile=profile, destination=broken).text == "cannot be read"


def test_a_variable_that_the_profile_lacks_counts_as_a_difference(tmp_path: Path) -> None:
    profile: Profile = Profile(name="ds", variables={"ANTHROPIC_MODEL": "m"})
    place: Destination = make_login(tmp_path, ".x", {"ANTHROPIC_MODEL": "m", "API_TIMEOUT_MS": "5"})
    state: DestinationState = destination_state(profile=profile, destination=place)
    assert state.kind == "differs" and state.differing == ["API_TIMEOUT_MS"]
