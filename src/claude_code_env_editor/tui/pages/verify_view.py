"""How the results of the verify checks look in the dialog."""

from __future__ import annotations

from rich.text import Text

from claude_code_env_editor.verify import FAIL, PASS, SKIP, Check, Endpoint


def render_checks(checks: list[Check], endpoint: Endpoint) -> Text:
    """Format the check results as text for the dialog."""
    body: Text = Text(text=f"Host: {endpoint.host}\n\n", style="dim")
    for c in checks:
        mark, style = {PASS: ("ok  ", "#7fb069"), FAIL: ("FAIL", "#e5534b")}.get(c.status, ("skip", "dim"))
        body.append(f"{mark}  ", style=style)
        body.append(f"{c.name:<12}")
        body.append(f"{c.detail}\n", style="dim")
    failed: bool = any(c.status == FAIL for c in checks)
    skipped: bool = any(c.status == SKIP for c in checks)
    verdict: str = "All checks passed."
    if failed:
        verdict = "Some checks failed."
    elif skipped:
        verdict = "No check failed. Some checks were skipped."
    body.append(f"\n{verdict}")
    return body
