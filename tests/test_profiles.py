import stat
from pathlib import Path

import pytest

from claude_code_env_editor.profiles import (
    Profile,
    ProfileError,
    all_profiles,
    builtin_profiles,
    delete_profile,
    get_profile,
    load_user_profiles,
    save_profile,
    snapshot,
)

KEY: str = "sk-demo-0123456789abcdef"
DEEPSEEK: dict[str, str] = {
    "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
    "ANTHROPIC_AUTH_TOKEN": KEY,
    "ANTHROPIC_MODEL": "deepseek-flash",
}


def store(tmp_path: Path) -> Path:
    return tmp_path / "cfg" / "profiles.toml"


def test_name_rules() -> None:
    assert Profile(name="work.ds-1_a", variables={}).name == "work.ds-1_a"
    for bad in ("", "-start", "has space", "a/b", "x" * 65):
        with pytest.raises(ValueError):
            Profile(name=bad, variables={})


def test_only_known_variables_with_valid_values_are_allowed() -> None:
    with pytest.raises(ValueError, match="PATH"):
        Profile(name="p", variables={"PATH": "/tmp"})
    with pytest.raises(ValueError, match="at most"):
        Profile(name="p", variables={"CLAUDE_CODE_AUTO_COMPACT_WINDOW": "5000000"})
    with pytest.raises(ValueError, match="one of"):
        Profile(name="p", variables={"CLAUDE_CODE_EFFORT_LEVEL": "extreme"})


def test_properties() -> None:
    profile: Profile = Profile(name="p", variables=DEEPSEEK)
    assert profile.host == "api.deepseek.com" and profile.has_key
    assert Profile(name="q", variables={"ANTHROPIC_MODEL": "m"}).host == "api.anthropic.com"
    assert not Profile(name="q", variables={"ANTHROPIC_MODEL": "m"}).has_key


def test_builtins_come_from_the_presets() -> None:
    builtins: dict[str, Profile] = builtin_profiles()
    assert builtins["deepseek"].builtin and builtins["deepseek"].base_url.startswith("https://api.deepseek.com")
    assert not any(p.has_key for p in builtins.values())


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    path: Path = store(tmp_path)
    save_profile(profile=Profile(name="work", variables=DEEPSEEK, note="DeepSeek at work"), path=path)
    loaded: dict[str, Profile] = load_user_profiles(path=path)
    assert loaded["work"].variables == DEEPSEEK and loaded["work"].note == "DeepSeek at work"
    assert not loaded["work"].builtin


def test_file_mode_directory_mode_and_gitignore(tmp_path: Path) -> None:
    path: Path = store(tmp_path)
    save_profile(profile=Profile(name="work", variables=DEEPSEEK), path=path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert (path.parent / ".gitignore").read_text() == "profiles.toml\n"


def test_existing_name_needs_overwrite(tmp_path: Path) -> None:
    path: Path = store(tmp_path)
    save_profile(profile=Profile(name="work", variables=DEEPSEEK), path=path)
    with pytest.raises(ProfileError, match="--force"):
        save_profile(profile=Profile(name="work", variables={}), path=path)
    save_profile(profile=Profile(name="work", variables={"ANTHROPIC_MODEL": "m"}), path=path, overwrite=True)
    assert load_user_profiles(path=path)["work"].variables == {"ANTHROPIC_MODEL": "m"}


def test_builtin_name_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ProfileError, match="built-in"):
        save_profile(profile=Profile(name="deepseek", variables={}), path=store(tmp_path))


def test_delete(tmp_path: Path) -> None:
    path: Path = store(tmp_path)
    save_profile(profile=Profile(name="a", variables={}), path=path)
    save_profile(profile=Profile(name="b", variables={}), path=path)
    delete_profile(name="a", path=path)
    assert list(load_user_profiles(path=path)) == ["b"]
    with pytest.raises(ProfileError, match="Unknown"):
        delete_profile(name="a", path=path)
    with pytest.raises(ProfileError, match="built-in"):
        delete_profile(name="deepseek", path=path)


def test_broken_file_raises_and_is_not_overwritten(tmp_path: Path) -> None:
    path: Path = store(tmp_path)
    path.parent.mkdir()
    path.write_text("profiles = [")
    with pytest.raises(ProfileError):
        load_user_profiles(path=path)
    with pytest.raises(ProfileError):
        save_profile(profile=Profile(name="a", variables={}), path=path)
    assert path.read_text() == "profiles = ["


def test_file_with_an_unknown_variable_is_refused(tmp_path: Path) -> None:
    path: Path = store(tmp_path)
    path.parent.mkdir()
    path.write_text('[profiles.evil.variables]\nLD_PRELOAD = "/tmp/x.so"\n')
    with pytest.raises(ProfileError, match="LD_PRELOAD"):
        load_user_profiles(path=path)


def test_all_profiles_lists_builtins_first_and_get_profile_explains(tmp_path: Path) -> None:
    path: Path = store(tmp_path)
    save_profile(profile=Profile(name="mine", variables=DEEPSEEK), path=path)
    names: list[str] = list(all_profiles(path=path))
    assert names[: len(builtin_profiles())] == list(builtin_profiles())
    assert names[-1] == "mine"
    with pytest.raises(ProfileError, match="Choose one of"):
        get_profile(name="nope", path=path)


def test_snapshot_keeps_only_known_variables_and_can_drop_keys() -> None:
    env: dict[str, str] = {**DEEPSEEK, "CLAUDE_CODE_CUSTOM_THING": "1", "PATH": "/x"}
    with_key: Profile = snapshot(name="s", env=env)
    assert with_key.variables == DEEPSEEK
    without_key: Profile = snapshot(name="s", env=env, include_keys=False)
    assert "ANTHROPIC_AUTH_TOKEN" not in without_key.variables and not without_key.has_key
