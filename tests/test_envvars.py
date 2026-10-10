from claude_code_env_editor.envvars import (
    BY_NAME,
    SOURCE_ENV,
    SOURCE_SETTINGS,
    SOURCE_UNSET,
    mask,
    resolve,
    validate,
)


def test_mask_hides_short_secret():
    assert mask("abcd1234") == "********"


def test_mask_keeps_edges_of_long_secret():
    assert mask("sk-ant-0123456789abcdef") == "sk-a...cdef"


def test_mask_leaves_plain_value():
    assert mask("https://x", secret=False) == "https://x"


def test_resolve_env_wins_over_settings():
    rows = {r.name: r for r in resolve({"ANTHROPIC_MODEL": "a"}, {"ANTHROPIC_MODEL": "b"})}
    assert rows["ANTHROPIC_MODEL"].value == "b"
    assert rows["ANTHROPIC_MODEL"].source == SOURCE_ENV


def test_resolve_sources():
    rows = {r.name: r for r in resolve({"ANTHROPIC_MODEL": "a"}, {})}
    assert rows["ANTHROPIC_MODEL"].source == SOURCE_SETTINGS
    assert rows["API_TIMEOUT_MS"].source == SOURCE_UNSET


def test_resolve_lists_custom_variable():
    rows = {r.name: r for r in resolve({"CLAUDE_CODE_NEW_THING": "1", "OTHER": "x"}, {})}
    assert rows["CLAUDE_CODE_NEW_THING"].spec is None
    assert "OTHER" not in rows


def test_secret_row_display_is_masked():
    row = next(r for r in resolve({"ANTHROPIC_AUTH_TOKEN": "sk-0123456789abcdef"}, {}) if r.secret)
    assert "0123456789" not in row.display


def test_validate():
    assert validate(BY_NAME["API_TIMEOUT_MS"], "abc")
    assert validate(BY_NAME["API_TIMEOUT_MS"], "5000") is None
    assert validate(BY_NAME["ANTHROPIC_BASE_URL"], "example.com")
    assert validate(BY_NAME["ANTHROPIC_BASE_URL"], "https://example.com") is None
