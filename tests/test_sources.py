from pathlib import Path

import pytest

from claude_code_env_editor.profiles import Profile, load_profiles, save_profile
from claude_code_env_editor.sources import ProfileSource

VARS: dict[str, str] = {
    "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
    "ANTHROPIC_MODEL": "deepseek-flash",
}


def test_profile_source_loads_the_variables() -> None:
    source: ProfileSource = ProfileSource(profile=Profile(name="b", variables=VARS))
    assert source.name == "b"
    assert source.load() == VARS


def test_profile_source_saves_changes_to_profiles_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path: Path = tmp_path / "profiles.toml"
    monkeypatch.setattr("claude_code_env_editor.profiles.default_profiles_path", lambda: path)
    profile: Profile = Profile(name="mine", variables=VARS, note="n")
    save_profile(profile=profile, path=path)
    source: ProfileSource = ProfileSource(profile=profile)
    source.save(updates={"ANTHROPIC_MODEL": "deepseek-v4-pro", "ANTHROPIC_BASE_URL": None})
    saved: Profile = load_profiles(path=path)["mine"]
    assert saved.variables == {"ANTHROPIC_MODEL": "deepseek-v4-pro"} and saved.note == "n"
    assert source.load() == {"ANTHROPIC_MODEL": "deepseek-v4-pro"}


def test_profile_source_refuses_an_invalid_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path: Path = tmp_path / "profiles.toml"
    monkeypatch.setattr("claude_code_env_editor.profiles.default_profiles_path", lambda: path)
    source: ProfileSource = ProfileSource(profile=Profile(name="mine", variables=VARS))
    with pytest.raises(ValueError):
        source.save(updates={"ANTHROPIC_BASE_URL": "not-a-url"})
    assert source.load() == VARS and not path.exists()
