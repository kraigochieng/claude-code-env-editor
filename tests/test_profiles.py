import stat
from pathlib import Path

import pytest

from claude_code_env_editor.profiles import (
    Profile,
    ProfileError,
    delete_profile,
    get_profile,
    load_profiles,
    rename_profile,
    save_profile,
    snapshot,
    templates,
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


def test_templates_come_from_the_presets() -> None:
    available: dict[str, Profile] = templates()
    assert available["deepseek"].base_url.startswith("https://api.deepseek.com")
    assert not any(p.has_key for p in available.values())


# -- seeding -----------------------------------------------------------------


def test_first_use_copies_the_templates_into_the_file(tmp_path: Path) -> None:
    path: Path = store(tmp_path)
    loaded: dict[str, Profile] = load_profiles(path=path)
    assert list(loaded) == list(templates())
    assert path.exists() and "templates_seeded = true" in path.read_text()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_a_deleted_template_stays_deleted(tmp_path: Path) -> None:
    path: Path = store(tmp_path)
    load_profiles(path=path)
    delete_profile(name="zai", path=path)
    assert "zai" not in load_profiles(path=path)
    assert "zai" not in load_profiles(path=path)


def test_an_old_file_gets_only_the_missing_templates_once(tmp_path: Path) -> None:
    path: Path = store(tmp_path)
    path.parent.mkdir()
    path.write_text(
        '[profiles.mine.variables]\nANTHROPIC_MODEL = "m"\n'
        '[profiles.deepseek.variables]\nANTHROPIC_MODEL = "my-own-deepseek-model"\n'
    )
    loaded: dict[str, Profile] = load_profiles(path=path)
    assert loaded["mine"].variables == {"ANTHROPIC_MODEL": "m"}
    assert loaded["deepseek"].variables == {"ANTHROPIC_MODEL": "my-own-deepseek-model"}  # not replaced
    assert "openrouter" in loaded
    assert load_profiles(path=path).keys() == loaded.keys()


def test_reading_without_seeding_writes_nothing(tmp_path: Path) -> None:
    path: Path = store(tmp_path)
    assert load_profiles(path=path, seed=False) == {}
    assert not path.exists()


def test_a_broken_file_is_not_overwritten_by_seeding(tmp_path: Path) -> None:
    path: Path = store(tmp_path)
    path.parent.mkdir()
    path.write_text("profiles = [")
    with pytest.raises(ProfileError):
        load_profiles(path=path)
    with pytest.raises(ProfileError):
        save_profile(profile=Profile(name="a", variables={}), path=path)
    assert path.read_text() == "profiles = ["


def test_file_with_an_unknown_variable_is_refused(tmp_path: Path) -> None:
    path: Path = store(tmp_path)
    path.parent.mkdir()
    path.write_text('[profiles.evil.variables]\nLD_PRELOAD = "/tmp/x.so"\n')
    with pytest.raises(ProfileError, match="LD_PRELOAD"):
        load_profiles(path=path)


# -- save, edit, delete ------------------------------------------------------


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    path: Path = store(tmp_path)
    save_profile(profile=Profile(name="work", variables=DEEPSEEK, note="DeepSeek at work"), path=path)
    loaded: dict[str, Profile] = load_profiles(path=path)
    assert loaded["work"].variables == DEEPSEEK and loaded["work"].note == "DeepSeek at work"
    assert list(loaded)[-1] == "work"  # after the seeded templates


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
    assert load_profiles(path=path)["work"].variables == {"ANTHROPIC_MODEL": "m"}


def test_a_template_profile_can_be_changed_like_any_other(tmp_path: Path) -> None:
    path: Path = store(tmp_path)
    changed: Profile = Profile(name="deepseek", variables={"ANTHROPIC_MODEL": "deepseek-v4-pro"})
    save_profile(profile=changed, path=path, overwrite=True)
    assert load_profiles(path=path)["deepseek"].variables == {"ANTHROPIC_MODEL": "deepseek-v4-pro"}


def test_delete(tmp_path: Path) -> None:
    path: Path = store(tmp_path)
    save_profile(profile=Profile(name="a", variables={}), path=path)
    delete_profile(name="a", path=path)
    assert "a" not in load_profiles(path=path)
    with pytest.raises(ProfileError, match="Unknown"):
        delete_profile(name="a", path=path)


def test_get_profile_explains_and_can_fall_back_to_a_template(tmp_path: Path) -> None:
    path: Path = store(tmp_path)
    with pytest.raises(ProfileError, match="Choose one of"):
        get_profile(name="nope", path=path)
    delete_profile(name="deepseek", path=path)
    with pytest.raises(ProfileError):
        get_profile(name="deepseek", path=path)
    assert get_profile(name="deepseek", path=path, include_templates=True).base_url.startswith("https://api.deepseek")


# -- rename ------------------------------------------------------------------


def test_rename_keeps_position_variables_and_note(tmp_path: Path) -> None:
    path: Path = store(tmp_path)
    save_profile(profile=Profile(name="work", variables=DEEPSEEK, note="n"), path=path)
    before: list[str] = list(load_profiles(path=path))
    rename_profile(old="work", new="work-ds", path=path)
    after: dict[str, Profile] = load_profiles(path=path)
    assert list(after) == [("work-ds" if name == "work" else name) for name in before]
    assert after["work-ds"].variables == DEEPSEEK and after["work-ds"].note == "n"
    assert "work" not in after


def test_rename_a_template_profile(tmp_path: Path) -> None:
    path: Path = store(tmp_path)
    rename_profile(old="deepseek", new="my-deepseek", path=path)
    names: dict[str, Profile] = load_profiles(path=path)
    assert "my-deepseek" in names and "deepseek" not in names


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("nope", "x", "Unknown"),
        ("deepseek", "deepseek", "same"),
        ("deepseek", "openrouter", "exists"),
        ("deepseek", "has space", "valid profile name"),
    ],
)
def test_rename_refusals(tmp_path: Path, old: str, new: str, message: str) -> None:
    path: Path = store(tmp_path)
    with pytest.raises(ProfileError, match=message):
        rename_profile(old=old, new=new, path=path)
    assert "deepseek" in load_profiles(path=path)  # nothing changed


def test_snapshot_keeps_only_known_variables_and_can_drop_keys() -> None:
    env: dict[str, str] = {**DEEPSEEK, "CLAUDE_CODE_CUSTOM_THING": "1", "PATH": "/x"}
    with_key: Profile = snapshot(name="s", env=env)
    assert with_key.variables == DEEPSEEK
    without_key: Profile = snapshot(name="s", env=env, include_keys=False)
    assert "ANTHROPIC_AUTH_TOKEN" not in without_key.variables and not without_key.has_key


# -- names are unique, also in case ------------------------------------------


def test_a_name_that_differs_only_in_case_is_refused_on_save(tmp_path: Path) -> None:
    path: Path = store(tmp_path)
    save_profile(profile=Profile(name="work", variables={}), path=path)
    with pytest.raises(ProfileError, match="not case sensitive"):
        save_profile(profile=Profile(name="Work", variables={}), path=path)
    with pytest.raises(ProfileError, match="not case sensitive"):
        save_profile(profile=Profile(name="WORK", variables={}), path=path, overwrite=True)
    assert [n for n in load_profiles(path=path) if n.casefold() == "work"] == ["work"]


def test_a_name_that_differs_only_in_case_is_refused_on_rename(tmp_path: Path) -> None:
    path: Path = store(tmp_path)
    with pytest.raises(ProfileError, match="not case sensitive"):
        rename_profile(old="zai", new="DeepSeek", path=path)


def test_a_profile_may_change_the_case_of_its_own_name(tmp_path: Path) -> None:
    path: Path = store(tmp_path)
    rename_profile(old="zai", new="Zai", path=path)
    assert "Zai" in load_profiles(path=path) and "zai" not in load_profiles(path=path)


def test_overwriting_the_same_name_keeps_one_profile(tmp_path: Path) -> None:
    path: Path = store(tmp_path)
    save_profile(profile=Profile(name="work", variables={"ANTHROPIC_MODEL": "a"}), path=path)
    save_profile(profile=Profile(name="work", variables={"ANTHROPIC_MODEL": "b"}), path=path, overwrite=True)
    names: list[str] = [n for n in load_profiles(path=path) if n == "work"]
    assert names == ["work"] and load_profiles(path=path)["work"].variables == {"ANTHROPIC_MODEL": "b"}
