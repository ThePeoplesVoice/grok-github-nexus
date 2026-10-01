"""A failed Grok call must fail the analyzer step; a good call must pass."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from nexus.grok_status import grok_exit_code, redact
from nexus.scripts import run_commit_analysis, run_pr_analysis

ROOT = Path(__file__).resolve().parent.parent
FAKE_KEY = "xai-test-secret-value-123456"


def _ok_response(text: str = "Looks good.") -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"choices": [{"message": {"content": text}}]}
    return resp


def _error_response(status: int = 500) -> MagicMock:
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
    monkeypatch.setenv("GROK_RETRIES", "0")
    for name in ("XAI_API_KEY", "CLAUDE_API_KEY", "PR_NUMBER"):
        monkeypatch.delenv(name, raising=False)
    return summary


def _no_side_effects(module):
    """Keep tests from writing usage/memory files in the repo."""
    patches = [patch.object(module, "after_successful_analysis", return_value={"total": 1}),
               patch.object(module, "log_success")]
    if hasattr(module, "record_memory"):
        patches.append(patch.object(module, "record_memory"))
    if hasattr(module, "gather_commits"):
        patches.append(patch.object(module, "gather_commits", return_value=[
            {"sha": "abc1234", "oneline": "abc1234 test commit", "details": "1 file changed"}
        ]))
    return patches


def _run_main(module, post):
    patches = _no_side_effects(module) + [patch("nexus.providers.requests.post", **post)]
    for p in patches:
        p.start()
    try:
        return module.main()
    finally:
        for p in reversed(patches):
            p.stop()


FAILURES = {
    "network": {"side_effect": requests.ConnectionError("connection refused")},
    "http_500": {"return_value": _error_response(500)},
    "http_401": {"return_value": _error_response(401)},
    "malformed": {"return_value": _malformed_response()},
    "empty": {"return_value": _ok_response("   ")},
}


@pytest.mark.parametrize("module", [run_pr_analysis, run_commit_analysis])
@pytest.mark.parametrize("kind", sorted(FAILURES))
def test_failed_grok_call_fails_the_analyzer(module, kind, ci_env, capsys):
    assert _run_main(module, FAILURES[kind]) == 1
    out = capsys.readouterr().out
    assert "::error title=" in out and "Grok call failed" in out
    summary = ci_env.read_text(encoding="utf-8")
    assert "Grok call failed" in summary
    assert FAKE_KEY not in out and FAKE_KEY not in summary


@pytest.mark.parametrize("module", [run_pr_analysis, run_commit_analysis])
def test_missing_key_fails_the_analyzer(module, ci_env, monkeypatch, capsys):
    monkeypatch.delenv("GROK_API_KEY")
    assert _run_main(module, {"side_effect": AssertionError("must not call API")}) == 1
    assert "missing" in ci_env.read_text(encoding="utf-8")


@pytest.mark.parametrize("module", [run_pr_analysis, run_commit_analysis])
def test_successful_grok_call_passes(module, ci_env, capsys):
    assert _run_main(module, {"return_value": _ok_response()}) == 0
    assert "Grok call succeeded" in ci_env.read_text(encoding="utf-8")
    assert "::error" not in capsys.readouterr().out


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


def test_grok_exit_code_without_summary_file(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert grok_exit_code("X", None, "Grok exception: boom") == 1
    assert grok_exit_code("X", "fine", None) == 0


def test_pr_analyzer_workflow_has_no_swallowing():
    body = (ROOT / ".github/workflows/multi-ai-pr-analyzer.yml").read_text(encoding="utf-8")
    step = body.split("Run Ara + Claude PR Analysis", 1)[1].split("- name:", 1)[0]
    assert "continue-on-error" not in step and "|| true" not in step
    assert "head.repo.full_name == github.repository" in body
    assert "github.event.pull_request.user.login != 'dependabot[bot]'" in body
