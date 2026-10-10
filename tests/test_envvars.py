from claude_code_env_editor.envvars import (
    BY_NAME,
    SOURCE_ENV,
    SOURCE_SETTINGS,
    SOURCE_UNSET,
    Row,
    mask,
    resolve,
    validate,
)


def test_mask_hides_short_secret() -> None:
    assert mask(value="abcd1234") == "********"


def test_mask_keeps_edges_of_long_secret() -> None:
    assert mask(value="sk-ant-0123456789abcdef") == "sk-a...cdef"


def test_mask_leaves_plain_value() -> None:
    assert mask(value="https://x", secret=False) == "https://x"


def test_resolve_settings_win_over_the_shell() -> None:
    rows: dict[str, Row] = {
        r.name: r for r in resolve(settings_env={"ANTHROPIC_MODEL": "a"}, environ={"ANTHROPIC_MODEL": "b"})
    }
    row: Row = rows["ANTHROPIC_MODEL"]
    assert row.value == "a" and row.source == SOURCE_SETTINGS
    assert row.shell_value == "b"


def test_resolve_same_value_in_both_places_has_no_note() -> None:
    rows: dict[str, Row] = {
        r.name: r for r in resolve(settings_env={"ANTHROPIC_MODEL": "a"}, environ={"ANTHROPIC_MODEL": "a"})
    }
    assert rows["ANTHROPIC_MODEL"].shell_value == ""


def test_resolve_shell_only_value_has_the_env_source() -> None:
    rows: dict[str, Row] = {r.name: r for r in resolve(settings_env={}, environ={"ANTHROPIC_MODEL": "b"})}
    assert rows["ANTHROPIC_MODEL"].value == "b" and rows["ANTHROPIC_MODEL"].source == SOURCE_ENV


def test_resolve_sources() -> None:
    rows: dict[str, Row] = {r.name: r for r in resolve(settings_env={"ANTHROPIC_MODEL": "a"}, environ={})}
    assert rows["ANTHROPIC_MODEL"].source == SOURCE_SETTINGS
    assert rows["API_TIMEOUT_MS"].source == SOURCE_UNSET


def test_resolve_lists_custom_variable() -> None:
    rows: dict[str, Row] = {r.name: r for r in resolve(settings_env={"CLAUDE_CODE_NEW_THING": "1", "OTHER": "x"}, environ={})}
    assert rows["CLAUDE_CODE_NEW_THING"].spec is None
    assert "OTHER" not in rows


def test_secret_row_display_is_masked() -> None:
    row: Row = next(r for r in resolve(settings_env={"ANTHROPIC_AUTH_TOKEN": "sk-0123456789abcdef"}, environ={}) if r.secret)
    assert "0123456789" not in row.display


def test_validate() -> None:
    assert validate(spec=BY_NAME["API_TIMEOUT_MS"], value="abc")
    assert validate(spec=BY_NAME["API_TIMEOUT_MS"], value="5000") is None
    assert validate(spec=BY_NAME["ANTHROPIC_BASE_URL"], value="example.com")
    assert validate(spec=BY_NAME["ANTHROPIC_BASE_URL"], value="https://example.com") is None


def test_effort_level_is_a_choice_with_the_documented_values() -> None:
    spec = BY_NAME["CLAUDE_CODE_EFFORT_LEVEL"]
    assert spec.kind == "choice"
    assert spec.choices == ("low", "medium", "high", "xhigh", "max", "auto")
    assert validate(spec=spec, value="max") is None
    assert validate(spec=spec, value="extreme") is not None


def test_compact_window_range_and_plain_integer() -> None:
    spec = BY_NAME["CLAUDE_CODE_AUTO_COMPACT_WINDOW"]
    assert validate(spec=spec, value="500000") is None
    assert validate(spec=spec, value="99999") == "CLAUDE_CODE_AUTO_COMPACT_WINDOW must be at least 100000."
    assert validate(spec=spec, value="1000001") == "CLAUDE_CODE_AUTO_COMPACT_WINDOW must be at most 1000000."
    message = validate(spec=spec, value="500k")
    assert message is not None and "500000, not 500k" in message


def test_every_preset_value_passes_validation() -> None:
    from claude_code_env_editor.presets import load_presets

    for preset_id, preset in load_presets().items():
        for name, value in preset.variables.items():
            if name in BY_NAME:
                assert validate(spec=BY_NAME[name], value=value) is None, (preset_id, name)
