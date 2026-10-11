from pathlib import Path

from claude_code_env_editor.apply import (
    ApplyPlan,
    Change,
    format_plan,
    host_of,
    plan_apply,
    secret_target_problem,
)
from claude_code_env_editor.profiles import Profile
from claude_code_env_editor.target import Target

DEEPSEEK_ENV: dict[str, str] = {
    "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
    "ANTHROPIC_AUTH_TOKEN": "sk-deepseek-0123456789",
    "ANTHROPIC_MODEL": "deepseek-flash",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-flash",
    "CLAUDE_CODE_MY_FLAG": "1",
}
OPENROUTER: Profile = Profile(
    name="or",
    variables={"ANTHROPIC_BASE_URL": "https://openrouter.ai/api", "ANTHROPIC_MODEL": "deepseek/deepseek-chat"},
)


def by_name(plan: ApplyPlan) -> dict[str, Change]:
    return {change.name: change for change in plan.changes}


def test_host_of() -> None:
    assert host_of("https://API.DeepSeek.com/anthropic") == "api.deepseek.com"
    assert host_of("") == "api.anthropic.com" and host_of(None) == "api.anthropic.com"
    assert host_of("http://localhost:4000") == "localhost:4000"


def test_replace_removes_stale_variables_and_the_key_of_another_host() -> None:
    plan: ApplyPlan = plan_apply(profile=OPENROUTER, current_env=DEEPSEEK_ENV, mode="replace")
    changes: dict[str, Change] = by_name(plan)
    assert changes["ANTHROPIC_BASE_URL"].action == "set"
    assert changes["ANTHROPIC_MODEL"].action == "set"
    assert changes["ANTHROPIC_DEFAULT_HAIKU_MODEL"].action == "remove"
    assert changes["ANTHROPIC_AUTH_TOKEN"].action == "remove"
    assert plan.custom_kept == ["CLAUDE_CODE_MY_FLAG"]
    assert plan.updates()["ANTHROPIC_DEFAULT_HAIKU_MODEL"] is None
    assert plan.writes


def test_replace_keeps_the_key_when_the_host_does_not_change() -> None:
    same_host: Profile = Profile(
        name="ds2",
        variables={"ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic", "ANTHROPIC_MODEL": "deepseek-v4-pro"},
    )
    changes: dict[str, Change] = by_name(plan_apply(profile=same_host, current_env=DEEPSEEK_ENV, mode="replace"))
    assert changes["ANTHROPIC_AUTH_TOKEN"].action == "keep"
    assert changes["ANTHROPIC_BASE_URL"].action == "same"
    assert changes["ANTHROPIC_MODEL"].action == "set"


def test_replace_sets_the_key_of_the_profile() -> None:
    with_key: Profile = Profile(
        name="k", variables={**OPENROUTER.variables, "ANTHROPIC_AUTH_TOKEN": "sk-or-v1-new0000000000"}
    )
    changes: dict[str, Change] = by_name(plan_apply(profile=with_key, current_env=DEEPSEEK_ENV))
    assert changes["ANTHROPIC_AUTH_TOKEN"].action == "set"
    assert changes["ANTHROPIC_AUTH_TOKEN"].old == "sk-deepseek-0123456789"


def test_merge_changes_only_the_listed_variables_and_warns_about_a_key_for_another_host() -> None:
    plan: ApplyPlan = plan_apply(profile=OPENROUTER, current_env=DEEPSEEK_ENV, mode="merge")
    changes: dict[str, Change] = by_name(plan)
    assert "ANTHROPIC_DEFAULT_HAIKU_MODEL" not in changes and "ANTHROPIC_AUTH_TOKEN" not in changes
    assert set(plan.updates()) == {"ANTHROPIC_BASE_URL", "ANTHROPIC_MODEL"}
    assert len(plan.warnings) == 1 and "openrouter.ai" in plan.warnings[0]


def test_nothing_to_write_when_the_target_already_matches() -> None:
    plan: ApplyPlan = plan_apply(profile=OPENROUTER, current_env=dict(OPENROUTER.variables))
    assert not plan.writes and plan.updates() == {}


def test_summary_masks_secrets_unless_asked() -> None:
    with_key: Profile = Profile(name="k", variables={"ANTHROPIC_AUTH_TOKEN": "sk-or-v1-new0000000000"})
    plan: ApplyPlan = plan_apply(profile=with_key, current_env=DEEPSEEK_ENV)
    text: str = "\n".join(format_plan(plan=plan))
    assert "0123456789" not in text and "new0000000000" not in text
    revealed: str = "\n".join(format_plan(plan=plan, reveal=True))
    assert "sk-or-v1-new0000000000" in revealed


def test_key_in_a_shared_project_file_is_a_problem(tmp_path: Path) -> None:
    with_key: Profile = Profile(name="k", variables={"ANTHROPIC_AUTH_TOKEN": "sk-x-0000000000"})
    without_key: Profile = Profile(name="n", variables={"ANTHROPIC_MODEL": "m"})
    shared: Target = Target.from_file(settings_file=tmp_path / "proj" / ".claude" / "settings.json", known_dirs=[])
    local: Target = Target.from_file(settings_file=tmp_path / "proj" / ".claude" / "settings.local.json", known_dirs=[])
    user: Target = Target.from_config_dir(config_dir=tmp_path / ".claude-work")
    assert secret_target_problem(profile=with_key, target=shared) is not None
    assert secret_target_problem(profile=with_key, target=local) is None
    assert secret_target_problem(profile=with_key, target=user) is None
    assert secret_target_problem(profile=without_key, target=shared) is None


def test_wrapped_summary_has_short_lines_and_masks_secrets() -> None:
    with_key: Profile = Profile(
        name="k",
        variables={
            "ANTHROPIC_BASE_URL": "https://openrouter.ai/api/with/a/very/long/path/that/would/not/fit/in/a/dialog",
            "ANTHROPIC_AUTH_TOKEN": "sk-or-v1-new0000000000",
        },
    )
    plan: ApplyPlan = plan_apply(profile=with_key, current_env=DEEPSEEK_ENV)
    lines: list[str] = format_plan(plan=plan, wrap=True)
    assert any(line.strip() == "set     ANTHROPIC_BASE_URL" for line in lines)
    assert any(line.strip().startswith("was: https://api.deepseek.com") for line in lines)
    assert not any("0123456789" in line or "new0000000000" in line for line in lines)
    assert any(line.strip() == "keep    CLAUDE_CODE_MY_FLAG" for line in lines)
