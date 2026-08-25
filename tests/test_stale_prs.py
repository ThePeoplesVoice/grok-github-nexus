"""Tests for nexus.stale classification."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

from nexus.stale import classify, is_bot_pr, should_close_on_run

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


def _pr(**kwargs):
    base = {
        "number": 1,
        "title": "feat: real work",
        "user": {"login": "ThePeoplesVoice", "type": "User"},
        "head": {"ref": "feat/real"},
        "labels": [],
        "draft": False,
        "updated_at": "2026-08-20T00:00:00Z",
    }
    base.update(kwargs)
    return base


def test_keep_human_with_unique_commits():
    v, reason = classify(_pr(), {"ahead_by": 4, "behind_by": 0}, now=NOW)
    assert v == "keep"
    assert "human" in reason


def test_close_zero_ahead():
    v, reason = classify(_pr(), {"ahead_by": 0, "behind_by": 12}, now=NOW)
    assert v == "close"
    assert reason.startswith("superseded")


def test_keep_label_wins():
    pr = _pr(labels=[{"name": "keep"}], user={"login": "Copilot", "type": "Bot"})
    v, _ = classify(pr, {"ahead_by": 0, "behind_by": 9}, now=NOW)
    assert v == "keep"


def test_close_noisy_bot_wip():
    pr = _pr(
        title="[WIP] Analyze commits for 2026-08-13",
        user={"login": "Copilot", "type": "Bot"},
        head={"ref": "copilot/commit-analysis-2026-08-13"},
        updated_at="2026-08-13T00:00:00Z",
    )
    v, reason = classify(pr, {"ahead_by": 2, "behind_by": 5}, now=NOW)
    assert v == "close"
    assert "bot WIP" in reason


def test_keep_fresh_bot():
    pr = _pr(
        title="[WIP] live",
        user={"login": "Copilot", "type": "Bot"},
        head={"ref": "copilot/commit-analysis-now"},
        updated_at=(NOW - timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    v, _ = classify(pr, {"ahead_by": 2, "behind_by": 1}, now=NOW)
    assert v == "keep"


def test_is_bot_from_branch():
    assert is_bot_pr(_pr(user={"login": "someone", "type": "User"}, head={"ref": "copilot/x"}))


def test_dry_run_only_closes_superseded():
    assert should_close_on_run("close", "superseded — 0 commits ahead of main", apply=False, close_zero_ahead=True)
    assert not should_close_on_run("close", "bot WIP, 5 behind main, idle 10d", apply=False, close_zero_ahead=True)
    assert should_close_on_run("close", "bot WIP, 5 behind main, idle 10d", apply=True, close_zero_ahead=True)
    assert not should_close_on_run("keep", "human author with unique commits", apply=True, close_zero_ahead=True)
