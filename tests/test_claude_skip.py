"""Claude unavailable -> quiet "skipped"; Grok alone decides the check (fail-closed, #239).

Also covers the shared Grok timeout / retry / backoff budget.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
import yaml

from nexus.analyze import fusion_note
from nexus.providers import (
    CLAUDE_URL,
    GROK_URL,
    call_claude,
    call_grok,
    claude_unavailable_reason,
    grok_worst_case_seconds,
    is_claude_skipped,
    resolve_grok_timeout,
)
from nexus.scripts import run_commit_analysis, run_issue_triage, run_pr_analysis, run_self_audit

from tests.test_analyzer_grok_failure import (  # noqa: F401
    GROK_WORKFLOWS, WORKFLOWS, _no_side_effects, _ok_response, ci_env,
)

CLAUDE_MODULES = [run_pr_analysis, run_commit_analysis, run_issue_triage, run_self_audit]
_ids = lambda m: m.__name__.rsplit(".", 1)[-1]  # noqa: E731


def _resp(status: int, message: str) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = {"error": {"type": "error", "message": message}}
    resp.text = message
    return resp


CREDITS_MSG = "Your credit balance is too low to access the Anthropic API."


def _claude_ok() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"content": [{"text": "Claude says fine."}]}
    return resp


# --- detection -------------------------------------------------------------

@pytest.mark.parametrize("status,message", [
    (400, "Your credit balance is too low to access the Anthropic API."),
    (400, "Billing issue: please update your payment method."),
    (401, "invalid x-api-key"),
    (402, "Payment required"),
    (403, "Your account does not have access."),
    (429, "You have exceeded your monthly usage quota."),
])
def test_claude_unavailable_is_skipped(status, message):
    with patch("nexus.providers.requests.post", return_value=_resp(status, message)):
        text, err = call_claude("hi", api_key="sk-ant-test-000000")
    assert text is None and is_claude_skipped(err)
    assert claude_unavailable_reason(status, message)


@pytest.mark.parametrize("status,message", [
    (400, "max_tokens: field required"),
    (429, "Number of request tokens has exceeded your per-minute rate limit"),
    (500, "Internal server error"),
    (529, "Overloaded"),
])
def test_other_claude_errors_are_not_skips(status, message):
    with patch("nexus.providers.requests.post", return_value=_resp(status, message)):
        text, err = call_claude("hi", api_key="sk-ant-test-000000")
    assert text is None and not is_claude_skipped(err) and str(status) in err


def test_claude_without_key_is_skipped(monkeypatch):
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    with patch("nexus.providers.requests.post", side_effect=AssertionError("must not call API")):
        text, err = call_claude("hi")
    assert text is None and is_claude_skipped(err) and "CLAUDE_API_KEY" in err


def test_fusion_note_says_claude_was_skipped():
    skipped = "Claude skipped (unavailable): CLAUDE_API_KEY not set"
    assert "Claude second reviewer skipped (unavailable)" in fusion_note(
        grok_ok=True, claude_ok=False, claude_error=skipped)
    assert "Grok failed" in fusion_note(
        grok_ok=False, claude_ok=False, grok_error="boom", claude_error=skipped)


# --- entrypoints: skipped is never a pass ---------------------------------

def _router(grok, claude):
    """requests.post stand-in that answers Grok and Claude separately."""
    grok_iter = iter(grok) if isinstance(grok, list) else None

    def post(url, **_kwargs):
        if url == CLAUDE_URL:
            if isinstance(claude, Exception):
                raise claude
            return claude
        assert url == GROK_URL
        item = next(grok_iter) if grok_iter is not None else grok
        if isinstance(item, Exception):
            raise item
        return item
    return post


def _run(module, post, monkeypatch):
    monkeypatch.setenv("CLAUDE_API_KEY", "sk-ant-test-key-000000")
    patches = [patch("nexus.providers.requests.post", side_effect=post)]
    if hasattr(module, "layer1_enabled"):
        patches.append(patch.object(module, "layer1_enabled", return_value=True))
    patches += _no_side_effects(module)
    for p in patches:
        p.start()
    try:
        return module.main()
    finally:
        for p in reversed(patches):
            p.stop()


@pytest.mark.parametrize("module", CLAUDE_MODULES, ids=_ids)
def test_claude_credits_skipped_and_grok_ok_passes(module, ci_env, monkeypatch, capsys):
    post = _router(_ok_response("Grok ok"), _resp(400, CREDITS_MSG))
    assert _run(module, post, monkeypatch) == 0
    out = capsys.readouterr().out
    summary = ci_env.read_text(encoding="utf-8")
    assert "Grok call succeeded" in summary
    assert "Claude second reviewer skipped (unavailable" in summary
    assert "::warning" not in out and "FAILED" not in summary


@pytest.mark.parametrize("module", CLAUDE_MODULES, ids=_ids)
def test_claude_skipped_and_grok_timeouts_fail_closed(module, ci_env, monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("nexus.providers._sleep", sleeps.append)
    timeout = requests.ReadTimeout("Read timed out. (read timeout=180)")
    post = _router([timeout, timeout, timeout], _resp(400, CREDITS_MSG))
    assert _run(module, post, monkeypatch) == 1
    summary = ci_env.read_text(encoding="utf-8")
    assert "Grok call failed (timeout)" in summary
    assert "Claude second reviewer skipped (unavailable" in summary
    assert sleeps == [5.0, 10.0]


@pytest.mark.parametrize("module", CLAUDE_MODULES, ids=_ids)
def test_claude_success_cannot_rescue_failed_grok(module, ci_env, monkeypatch):
    post = _router(_resp(401, "Incorrect API key provided"), _claude_ok())
    assert _run(module, post, monkeypatch) == 1
    assert "Grok call failed" in ci_env.read_text(encoding="utf-8")


def test_claude_malformed_output_keeps_failed_warning(ci_env, monkeypatch, capsys):
    bad = MagicMock(status_code=200)
    bad.json.side_effect = ValueError("Expecting value")
    post = _router(_ok_response("Grok ok"), bad)
    assert _run(run_pr_analysis, post, monkeypatch) == 0
    assert "::warning title=PR Analyzer::Claude second reviewer FAILED" in capsys.readouterr().out


def test_self_audit_report_says_claude_skipped(ci_env, monkeypatch):
    post = _router(_ok_response("Grok audit"), _resp(402, "Payment required"))
    assert _run(run_self_audit, post, monkeypatch) == 0
    body = Path("/tmp/nexus_self_audit.md").read_text(encoding="utf-8")
    assert "Claude second reviewer skipped (unavailable) — Grok-only self-audit." in body


def test_self_audit_fails_closed_when_grok_times_out_and_claude_skipped(ci_env, monkeypatch):
    timeout = requests.ReadTimeout("Read timed out.")
    post = _router([timeout] * 3, _resp(400, CREDITS_MSG))
    assert _run(run_self_audit, post, monkeypatch) == 1


def test_pr_report_says_claude_skipped(ci_env, monkeypatch):
    post = _router(_ok_response("Grok review"), _resp(400, CREDITS_MSG))
    assert _run(run_pr_analysis, post, monkeypatch) == 0
    body = Path("/tmp/pr_analysis.md").read_text(encoding="utf-8")
    assert "Claude second reviewer skipped (unavailable) — Grok-only review." in body


# --- Grok timeout / retry / backoff ----------------------------------------

def test_grok_retries_with_backoff_then_recovers(monkeypatch):
    for name in ("GROK_RETRIES", "GROK_TIMEOUT_SECONDS", "GROK_RETRY_BACKOFF_SECONDS"):
        monkeypatch.delenv(name, raising=False)
    sleeps: list[float] = []
    monkeypatch.setattr("nexus.providers._sleep", sleeps.append)
    t = requests.ReadTimeout("Read timed out.")
    with patch("nexus.providers.requests.post", side_effect=[t, t, _ok_response("third time")]) as post:
        text, err = call_grok("hi", api_key="k")
    assert text == "third time" and err is None
    assert post.call_count == 3 and sleeps == [5.0, 10.0]
    assert post.call_args.kwargs["timeout"] == (10, 180.0)


def test_grok_retry_settings_from_env(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("nexus.providers._sleep", sleeps.append)
    monkeypatch.setenv("GROK_RETRY_BACKOFF_SECONDS", "2")
    monkeypatch.setenv("GROK_TIMEOUT_SECONDS", "120")
    with patch("nexus.providers.requests.post", side_effect=requests.ReadTimeout("t/o")) as post:
        text, err = call_grok("hi", api_key="k")
    assert text is None and "t/o" in err
    assert post.call_count == 3 and sleeps == [2.0, 4.0]
    assert post.call_args.kwargs["timeout"] == (10, 120.0)

    sleeps.clear()
    monkeypatch.setenv("GROK_RETRIES", "0")
    with patch("nexus.providers.requests.post", side_effect=requests.ReadTimeout("t/o")) as post:
        call_grok("hi", api_key="k")
    assert post.call_count == 1 and sleeps == []


def test_grok_timeout_is_clamped(monkeypatch):
    monkeypatch.setenv("GROK_TIMEOUT_SECONDS", "9999")
    assert resolve_grok_timeout() == 300
    monkeypatch.setenv("GROK_TIMEOUT_SECONDS", "junk")
    assert resolve_grok_timeout() == 180
    assert resolve_grok_timeout(45) == 45


CLAUDE_CALL_SECONDS = 10 + 90  # call_claude: connect + read, no retry


@pytest.mark.parametrize("name", sorted(GROK_WORKFLOWS))
def test_grok_jobs_outlast_worst_case_retries(name, monkeypatch):
    """Even at the env caps, Grok's worst case plus Claude fits inside timeout-minutes."""
    wf = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    for job in wf["jobs"].values():
        limit = int(job["timeout-minutes"]) * 60
        for var in ("GROK_RETRIES", "GROK_TIMEOUT_SECONDS", "GROK_RETRY_BACKOFF_SECONDS"):
            monkeypatch.delenv(var, raising=False)
        assert grok_worst_case_seconds() == 3 * 190 + 15
        assert grok_worst_case_seconds() + CLAUDE_CALL_SECONDS + 300 <= limit
        monkeypatch.setenv("GROK_RETRIES", "99")
        monkeypatch.setenv("GROK_TIMEOUT_SECONDS", "9999")
        monkeypatch.setenv("GROK_RETRY_BACKOFF_SECONDS", "9999")
        assert grok_worst_case_seconds() + CLAUDE_CALL_SECONDS < limit


def test_complete_stays_at_one_grok_retry():
    """Complete runs on medium effort and commits to main: keep it at 1 retry."""
    wf = yaml.safe_load((WORKFLOWS / "nexus-complete.yml").read_text(encoding="utf-8"))
    envs = [st.get("env", {}) for job in wf["jobs"].values() for st in job["steps"]]
    assert any(str(e.get("GROK_RETRIES")) == "1" for e in envs if "GROK_API_KEY" in e)
    assert not any("GROK_TIMEOUT_SECONDS" in e for e in envs)  # default 180 s
