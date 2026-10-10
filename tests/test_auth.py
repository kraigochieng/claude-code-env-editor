from claude_code_env_editor.auth import describe, expected_auth, visible_rows
from claude_code_env_editor.envvars import Row, resolve


def names(rows: list[Row]) -> list[str]:
    return [r.name for r in rows]


def test_empty_url_means_the_anthropic_api() -> None:
    assert expected_auth(base_url="") == "api_key"
    assert expected_auth(base_url="https://api.anthropic.com") == "api_key"


def test_known_third_party_endpoint_expects_a_token() -> None:
    assert expected_auth(base_url="https://api.deepseek.com/anthropic") == "auth_token"
    assert expected_auth(base_url="https://openrouter.ai/api") == "auth_token"


def test_unknown_endpoint_has_no_expected_auth() -> None:
    assert expected_auth(base_url="https://gateway.example.test") is None


def test_unused_secret_is_hidden_for_a_known_endpoint() -> None:
    rows: list[Row] = resolve(settings_env={"ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic"}, environ={})
    shown: list[str] = names(visible_rows(rows=rows))
    assert "ANTHROPIC_AUTH_TOKEN" in shown and "ANTHROPIC_API_KEY" not in shown


def test_unused_secret_that_is_set_stays_visible_with_a_warning() -> None:
    env: dict[str, str] = {"ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic", "ANTHROPIC_API_KEY": "k"}
    rows: list[Row] = resolve(settings_env=env, environ={})
    assert "ANTHROPIC_API_KEY" in names(visible_rows(rows=rows))
    assert "warning" in describe(rows=rows)


def test_unknown_endpoint_shows_both_secrets() -> None:
    rows: list[Row] = resolve(settings_env={"ANTHROPIC_BASE_URL": "https://gateway.example.test"}, environ={})
    shown: list[str] = names(visible_rows(rows=rows))
    assert "ANTHROPIC_AUTH_TOKEN" in shown and "ANTHROPIC_API_KEY" in shown


def test_default_endpoint_hides_the_token_and_mentions_the_login() -> None:
    rows: list[Row] = resolve(settings_env={}, environ={})
    assert "ANTHROPIC_AUTH_TOKEN" not in names(visible_rows(rows=rows))
    assert "login" in describe(rows=rows)
