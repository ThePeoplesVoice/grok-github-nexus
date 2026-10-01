"""Turn a Grok call result into a CI exit code with a readable report.

A failed Grok call (missing key, network error, non-2xx, empty or malformed
reply) must make the analyzer step fail. This module prints a GitHub
``::error::`` annotation, appends one line to ``$GITHUB_STEP_SUMMARY`` when it
is set, and returns the exit code. Error text is redacted before it is shown.
"""

from __future__ import annotations

import os
import re

from nexus.providers import classify_grok_result

_KEY_ENV_VARS = ("GROK_API_KEY", "XAI_API_KEY", "CLAUDE_API_KEY", "GITHUB_TOKEN")
# Provider error bodies can echo a (partially masked) key back.
_KEY_PATTERN = re.compile(r"\b(?:xai|sk|sk-ant|ghp|ghs|gho)[-_][A-Za-z0-9_*.\-]{6,}")


def redact(text: str | None) -> str:
    """Remove secret values and key-shaped tokens from an error message."""
    out = str(text or "")
    for name in _KEY_ENV_VARS:
        value = (os.environ.get(name) or "").strip()
        if len(value) >= 4:
            out = out.replace(value, "[redacted]")
    out = _KEY_PATTERN.sub("[redacted]", out)
    return " ".join(out.split())[:300]


def _write_summary(line: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line.rstrip() + "\n")
    except OSError:
        pass


def grok_exit_code(analyzer: str, grok_text: str | None, grok_err: str | None) -> int:
    """Return 0 when Grok produced text, 1 otherwise, and report the result."""
    if isinstance(grok_text, str) and grok_text.strip():
        print(f"✅ {analyzer}: Grok call succeeded")
        _write_summary(f"✅ **{analyzer}:** Grok call succeeded.")
        return 0

    outcome = classify_grok_result(grok_text, grok_err)
    reason = redact(grok_err) or "no text returned"
    print(f"::error title={analyzer}::Grok call failed ({outcome}): {reason}")
    _write_summary(f"❌ **{analyzer}:** Grok call failed ({outcome}): {reason}")
    return 1


def report_skip(analyzer: str, reason: str) -> int:
    """An intended skip: say so in the log and summary, then exit 0."""
    print(f"⏭️ {analyzer}: skipped: {reason}")
    _write_summary(f"⏭️ **{analyzer}:** skipped: {reason}")
    return 0


def report_claude(
    analyzer: str,
    claude_text: str | None,
    claude_err: str | None,
    *,
    attempted: bool,
) -> None:
    """Report the Claude second reviewer outcome. Never changes the exit code.

    Claude is a complementary reviewer, so its state is labelled (succeeded,
    failed, skipped) as a warning but does not decide the check. Grok does.
    """
    if not attempted:
        _write_summary(f"⏭️ **{analyzer}:** Claude second reviewer skipped (not configured for this run).")
        return
    if isinstance(claude_text, str) and claude_text.strip():
        _write_summary(f"✅ **{analyzer}:** Claude second reviewer succeeded.")
        return
    reason = redact(claude_err) or "no text returned"
    if "insufficient credits" in reason.lower() or "credit balance" in reason.lower():
        reason = "insufficient credits on the Claude account"
    print(f"::warning title={analyzer}::Claude second reviewer FAILED: {reason}")
    _write_summary(f"⚠️ **{analyzer}:** Claude second reviewer FAILED: {reason}")
