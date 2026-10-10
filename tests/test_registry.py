from claude_code_env_editor import registry


def test_missing_file_gives_empty_list(tmp_path):
    assert registry.load_registry(tmp_path / "none.toml") == []


def test_broken_file_gives_empty_list(tmp_path):
    path = tmp_path / "dirs.toml"
    path.write_text("dirs = [")
    assert registry.load_registry(path) == []


def test_add_and_remove(tmp_path):
    path = tmp_path / "cfg" / "dirs.toml"
    target = tmp_path / "login"
    target.mkdir()
    assert registry.add_to_registry(target, path) is True
    assert registry.add_to_registry(target, path) is False
    assert registry.load_registry(path) == [target.resolve()]
    assert registry.remove_from_registry(target, path) is True
    assert registry.remove_from_registry(target, path) is False
    assert registry.load_registry(path) == []


def test_path_with_quotes_and_backslashes_round_trips(tmp_path):
    path = tmp_path / "dirs.toml"
    odd = tmp_path / 'a "b" \\c'
    odd.mkdir()
    registry.add_to_registry(odd, path)
    assert registry.load_registry(path) == [odd.resolve()]


def test_default_path_is_in_user_config_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr("sys.platform", "linux")
    assert registry.default_registry_path().name == "dirs.toml"
