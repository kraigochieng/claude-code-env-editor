from claude_code_env_editor.envvars import (
    BY_NAME,
    SOURCE_ENV,
    SOURCE_SETTINGS,
    SOURCE_UNSET,
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


def test_resolve_env_wins_over_settings() -> None:
    rows = {r.name: r for r in resolve(settings_env={"ANTHROPIC_MODEL": "a"}, environ={"ANTHROPIC_MODEL": "b"})}
    assert rows["ANTHROPIC_MODEL"].value == "b"
    assert rows["ANTHROPIC_MODEL"].source == SOURCE_ENV


def test_resolve_sources() -> None:
    rows = {r.name: r for r in resolve(settings_env={"ANTHROPIC_MODEL": "a"}, environ={})}
    assert rows["ANTHROPIC_MODEL"].source == SOURCE_SETTINGS
    assert rows["API_TIMEOUT_MS"].source == SOURCE_UNSET


def test_resolve_lists_custom_variable() -> None:
    rows = {r.name: r for r in resolve(settings_env={"CLAUDE_CODE_NEW_THING": "1", "OTHER": "x"}, environ={})}
    assert rows["CLAUDE_CODE_NEW_THING"].spec is None
    assert "OTHER" not in rows


def test_secret_row_display_is_masked() -> None:
    row = next(r for r in resolve(settings_env={"ANTHROPIC_AUTH_TOKEN": "sk-0123456789abcdef"}, environ={}) if r.secret)
    assert "0123456789" not in row.display


def test_validate() -> None:
    assert validate(spec=BY_NAME["API_TIMEOUT_MS"], value="abc")
    assert validate(spec=BY_NAME["API_TIMEOUT_MS"], value="5000") is None
    assert validate(spec=BY_NAME["ANTHROPIC_BASE_URL"], value="example.com")
    assert validate(spec=BY_NAME["ANTHROPIC_BASE_URL"], value="https://example.com") is None
