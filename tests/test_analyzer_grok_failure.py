"""Every Grok-calling entrypoint must fail on a failed Grok call and pass on a good one."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
import yaml

from nexus.grok_status import grok_exit_code, redact, report_claude, report_skip
from nexus.scripts import (
    run_commit_analysis,
    run_complete_analysis,
    run_issue_triage,
    run_pr_analysis,
    run_pulse,
    run_self_audit,
)

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
FAKE_KEY = "xai-test-secret-value-123456"
COMPLETE_JSON = '{"summary": "fine", "health": 80, "actions": []}'
ALL_MODULES = [
    run_pr_analysis,
    run_commit_analysis,
    run_issue_triage,
    run_pulse,
    run_self_audit,
    run_complete_analysis,
]


def _ok_response(text: str = "Looks good.") -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"choices": [{"message": {"content": text}}]}
    return resp


def _error_response(status: int) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = {"error": {"message": "upstream exploded"}}
    resp.text = "upstream exploded"
    return resp


def _malformed_response() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.side_effect = ValueError("Expecting value: line 1 column 1")
    return resp


@pytest.fixture
def ci_env(tmp_path, monkeypatch):
    summary = tmp_path / "summary.md"
    summary.write_text("", encoding="utf-8")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("GROK_API_KEY", FAKE_KEY)
    monkeypatch.setenv("ISSUE_USER", "octo-human")
    monkeypatch.setenv("ISSUE_USER_TYPE", "User")
    for name in ("XAI_API_KEY", "CLAUDE_API_KEY", "PR_NUMBER", "GITHUB_TOKEN", "GITHUB_OUTPUT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("nexus.scripts.run_pulse.PRESENCE_PATH", tmp_path / "presence.json")
    monkeypatch.setattr("nexus.scripts.run_complete_analysis.OUT_JSON", tmp_path / "complete.json")
    return summary


def _no_side_effects(module):
    """Keep tests from writing usage, memory or reputation files in the repo."""
    rep = {"score": 1, "raw_score": 1, "freshness": "fresh"}
    result = {"total": 1, "reputation": rep, "stats": {}}
    names = {
        "after_successful_analysis": {"return_value": result},
        "log_success": {},
        "record_memory": {},
        "refresh_reputation": {"return_value": rep},
        "gather_commits": {"return_value": [
            {"sha": "abc1234", "oneline": "abc1234 test commit", "details": "1 file changed"}
        ]},
    }
    return [patch.object(module, n, **kw) for n, kw in names.items() if hasattr(module, n)]


def _run_main(module, post):
    patches = _no_side_effects(module) + [patch("nexus.providers.requests.post", **post)]
    for p in patches:
        p.start()
    try:
        return module.main()
    finally:
        for p in reversed(patches):
            p.stop()


def _success_text(module) -> str:
    return COMPLETE_JSON if module is run_complete_analysis else "Looks good."


FAILURES = {
    "network": {"side_effect": requests.ConnectionError("connection refused")},
    "timeout": {"side_effect": requests.ReadTimeout("Read timed out. (read timeout=90)")},
    "http_500": {"return_value": _error_response(500)},
    "http_401": {"return_value": _error_response(401)},
    "malformed": {"return_value": _malformed_response()},
    "empty": {"return_value": _ok_response("   ")},
}


@pytest.mark.parametrize("module", ALL_MODULES, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
@pytest.mark.parametrize("kind", sorted(FAILURES))
def test_failed_grok_call_fails_the_entrypoint(module, kind, ci_env, capsys):
    assert _run_main(module, FAILURES[kind]) == 1
    out = capsys.readouterr().out
    assert "::error title=" in out and "Grok call failed" in out
    summary = ci_env.read_text(encoding="utf-8")
    assert "Grok call failed" in summary
    assert FAKE_KEY not in out and FAKE_KEY not in summary


@pytest.mark.parametrize("module", ALL_MODULES, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_missing_key_fails_the_entrypoint(module, ci_env, monkeypatch):
    monkeypatch.delenv("GROK_API_KEY")
    assert _run_main(module, {"side_effect": AssertionError("must not call API")}) == 1
    assert "missing" in ci_env.read_text(encoding="utf-8")


@pytest.mark.parametrize("module", ALL_MODULES, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_successful_grok_call_passes(module, ci_env, capsys):
    assert _run_main(module, {"return_value": _ok_response(_success_text(module))}) == 0
    assert "Grok call succeeded" in ci_env.read_text(encoding="utf-8")
    assert "::error" not in capsys.readouterr().out


def test_complete_unparseable_json_fails(ci_env):
    assert _run_main(run_complete_analysis, {"return_value": _ok_response("not json")}) == 1
    assert "Grok call failed" in ci_env.read_text(encoding="utf-8")


def test_issue_triage_bot_issue_is_labelled_skip(ci_env, monkeypatch):
    monkeypatch.setenv("ISSUE_USER", "dependabot[bot]")
    monkeypatch.setenv("ISSUE_USER_TYPE", "Bot")
    assert _run_main(run_issue_triage, {"side_effect": AssertionError("must not call API")}) == 0
    assert "skipped" in ci_env.read_text(encoding="utf-8")


def test_transient_failure_retries_once_then_fails():
    from nexus.providers import call_grok
    with patch("nexus.providers.requests.post", return_value=_error_response(503)) as post:
        text, err = call_grok("hi", api_key="k")
    assert text is None and "503" in err
    assert post.call_count == 2  # one retry, then give up


def test_timeout_retry_recovers():
    from nexus.providers import call_grok
    side = [requests.ReadTimeout("Read timed out."), _ok_response("recovered")]
    with patch("nexus.providers.requests.post", side_effect=side) as post:
        text, err = call_grok("hi", api_key="k")
    assert text == "recovered" and err is None and post.call_count == 2


def test_auth_error_is_not_retried():
    from nexus.providers import call_grok
    with patch("nexus.providers.requests.post", return_value=_error_response(401)) as post:
        text, err = call_grok("hi", api_key="k", retries=1)
    assert text is None and "401" in err
    assert post.call_count == 1


def test_grok_request_uses_connect_timeout_low_effort_and_trims_prompt(monkeypatch):
    from nexus.providers import call_grok
    monkeypatch.delenv("GROK_REASONING_EFFORT", raising=False)
    monkeypatch.setenv("GROK_MAX_PROMPT_CHARS", "1000")
    with patch("nexus.providers.requests.post", return_value=_ok_response()) as post:
        call_grok("x" * 5000, api_key="k", model="grok-4.7")
    kwargs = post.call_args.kwargs
    assert kwargs["timeout"] == (10, 90)
    assert kwargs["json"]["reasoning_effort"] == "low"
    user = kwargs["json"]["messages"][1]["content"]
    assert len(user) <= 1000 and "prompt trimmed" in user


def test_reasoning_effort_only_for_models_that_take_it():
    from nexus.providers import _grok_reasoning_effort
    assert _grok_reasoning_effort("grok-4.7", None) == "low"
    assert _grok_reasoning_effort("grok-4.7", "medium") == "medium"
    assert _grok_reasoning_effort("grok-4.7", "bogus") == "low"
    assert _grok_reasoning_effort("grok-4.20-0309-non-reasoning", None) is None
    assert _grok_reasoning_effort("grok-4.3", None) is None
    assert _grok_reasoning_effort("grok-3", None) is None


def test_entrypoint_exits_nonzero_without_key(tmp_path):
    """End to end: the real module entrypoint returns a non-zero exit code."""
    env = {k: v for k, v in os.environ.items()
           if k not in ("GROK_API_KEY", "XAI_API_KEY", "CLAUDE_API_KEY")}
    env["GITHUB_STEP_SUMMARY"] = str(tmp_path / "summary.md")
    proc = subprocess.run(
        [sys.executable, "-m", "nexus.scripts.run_commit_analysis"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "Grok call failed" in (tmp_path / "summary.md").read_text(encoding="utf-8")


def test_redact_strips_key_values_and_key_shapes(monkeypatch):
    monkeypatch.setenv("GROK_API_KEY", FAKE_KEY)
    msg = f"Grok API 401: Incorrect API key provided: {FAKE_KEY} / xai-abc****wxyz"
    cleaned = redact(msg)
    assert FAKE_KEY not in cleaned and "xai-abc" not in cleaned
    assert "Incorrect API key" in cleaned


def test_grok_exit_code_without_summary_file(monkeypatch):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert grok_exit_code("X", None, "Grok exception: boom") == 1
    assert grok_exit_code("X", "fine", None) == 0
    assert report_skip("X", "why") == 0


def test_claude_out_of_credits_is_a_labelled_failure(ci_env, capsys):
    err = ("Claude API is temporarily unavailable due to insufficient credits. "
           "Running Grok-only path remains fully operational.")
    report_claude("X", None, err, attempted=True)
    out = capsys.readouterr().out
    summary = ci_env.read_text(encoding="utf-8")
    assert "::warning title=X::Claude second reviewer FAILED: insufficient credits" in out
    assert "Claude second reviewer FAILED" in summary
    report_claude("X", None, None, attempted=False)
    assert "Claude second reviewer skipped" in ci_env.read_text(encoding="utf-8")


def test_claude_failure_does_not_change_grok_exit(ci_env, monkeypatch):
    monkeypatch.setenv("CLAUDE_API_KEY", "sk-ant-test-key-000000")
    responses = [_ok_response("Grok ok"), _error_response(400)]
    assert _run_main(run_pr_analysis, {"side_effect": responses}) == 0
    assert "Claude second reviewer FAILED" in ci_env.read_text(encoding="utf-8")


# --- workflow shape -------------------------------------------------------

def _wf(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


GROK_WORKFLOWS = {
    "multi-ai-pr-analyzer.yml": "Run Ara + Claude PR Analysis",
    "multi-ai-commit-analyzer.yml": "🌌 Ara + Claude Commit Analysis",
    "multi-ai-issue-triage.yml": "Ara + Claude Issue Analysis",
    "nexus-pulse.yml": "Generate Pulse",
    "nexus-self-audit.yml": "Run Self-Audit",
    "nexus-complete.yml": "Run Complete Analysis",
}


@pytest.mark.parametrize("name,step_name", sorted(GROK_WORKFLOWS.items()))
def test_grok_step_is_not_swallowed_and_pip_is_cached(name, step_name):
    wf = _wf(name)
    steps = [s for job in wf["jobs"].values() for s in job["steps"]]
    step = next(s for s in steps if s.get("name") == step_name)
    assert "continue-on-error" not in step
    assert "|| true" not in step["run"] and "||true" not in step["run"]
    setup = next(s for s in steps if str(s.get("uses", "")).startswith("actions/setup-python"))
    assert setup["with"].get("cache") == "pip"


def test_pr_analyzer_skips_forks_and_dependabot_and_cancels_superseded_runs():
    wf = _wf("multi-ai-pr-analyzer.yml")
    cond = wf["jobs"]["analyze-with-ara"]["if"]
    assert "head.repo.full_name == github.repository" in cond
    assert "dependabot[bot]" in cond
    assert wf["concurrency"]["cancel-in-progress"] is True


def test_reports_still_publish_when_grok_fails():
    triage = _wf("multi-ai-issue-triage.yml")
    post = next(s for s in triage["jobs"]["triage"]["steps"] if s.get("name") == "Post Full Analysis Comment")
    assert post["if"].startswith("always()")
    pr = _wf("multi-ai-pr-analyzer.yml")
    post = next(s for s in pr["jobs"]["analyze-with-ara"]["steps"] if s.get("name") == "Post Analysis to PR")
    assert post["if"] == "always()"


def test_tests_workflow_only_cancels_pr_runs():
    wf = _wf("nexus-tests.yml")
    assert "pull_request" in wf["concurrency"]["cancel-in-progress"]
