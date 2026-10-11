import json
from pathlib import Path

import pytest

from claude_code_env_editor.profiles import Profile, load_user_profiles, save_profile
from claude_code_env_editor.sources import FileSource, ProfileSource, matching_profile

VARS: dict[str, str] = {
    "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
    "ANTHROPIC_MODEL": "deepseek-flash",
}


def test_file_source_loads_and_saves_the_env_block(tmp_path: Path) -> None:
    settings: Path = tmp_path / "settings.json"
    settings.write_text(json.dumps({"theme": "dark", "env": {"A": "1"}}))
    source: FileSource = FileSource(settings_file=settings)
    assert source.kind == "file" and source.editable
    assert source.load() == {"A": "1"}
    source.save(updates={"B": "2", "A": None})
    data: dict[str, object] = json.loads(settings.read_text())
    assert data == {"theme": "dark", "env": {"B": "2"}}


def test_profile_source_of_a_builtin_is_read_only() -> None:
    source: ProfileSource = ProfileSource(profile=Profile(name="b", variables=VARS, builtin=True))
    assert source.kind == "profile" and not source.editable
    assert source.load() == VARS


def test_profile_source_saves_changes_to_profiles_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path: Path = tmp_path / "profiles.toml"
    monkeypatch.setattr("claude_code_env_editor.profiles.default_profiles_path", lambda: path)
    profile: Profile = Profile(name="mine", variables=VARS, note="n")
    save_profile(profile=profile, path=path)
    source: ProfileSource = ProfileSource(profile=profile)
    source.save(updates={"ANTHROPIC_MODEL": "deepseek-v4-pro", "ANTHROPIC_BASE_URL": None})
    saved: Profile = load_user_profiles(path=path)["mine"]
    assert saved.variables == {"ANTHROPIC_MODEL": "deepseek-v4-pro"} and saved.note == "n"
    assert source.load() == {"ANTHROPIC_MODEL": "deepseek-v4-pro"}


def test_profile_source_refuses_an_invalid_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path: Path = tmp_path / "profiles.toml"
    monkeypatch.setattr("claude_code_env_editor.profiles.default_profiles_path", lambda: path)
    source: ProfileSource = ProfileSource(profile=Profile(name="mine", variables=VARS))
    with pytest.raises(ValueError):
        source.save(updates={"ANTHROPIC_BASE_URL": "not-a-url"})
    assert source.load() == VARS and not path.exists()


def test_matching_profile_compares_known_variables_only() -> None:
    profiles: dict[str, Profile] = {"ds": Profile(name="ds", variables=VARS)}
    env: dict[str, str] = {**VARS, "PATH": "/x", "SOME_CUSTOM": "1"}
    found: Profile | None = matching_profile(env=env, profiles=profiles)
    assert found is not None and found.name == "ds"
    assert matching_profile(env={**VARS, "ANTHROPIC_MODEL": "other"}, profiles=profiles) is None


def test_matching_profile_prefers_yours_over_a_builtin() -> None:
    profiles: dict[str, Profile] = {
        "builtin": Profile(name="builtin", variables=VARS, builtin=True),
        "mine": Profile(name="mine", variables=VARS),
    }
    found: Profile | None = matching_profile(env=VARS, profiles=profiles)
    assert found is not None and found.name == "mine"


def test_empty_env_matches_nothing() -> None:
    assert matching_profile(env={}, profiles={"p": Profile(name="p", variables={})}) is None
