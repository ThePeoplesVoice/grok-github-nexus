"""Tests for collaborative review gating."""

from __future__ import annotations

from nexus.collab import (
    is_bot_actor,
    is_collaborative_review_target,
    labels_are_automated,
)


def test_human_pr_counts():
    assert is_collaborative_review_target(login="ThePeoplesVoice", user_type="User") is True


def test_bot_pr_does_not_count():
    assert is_collaborative_review_target(login="Copilot", user_type="Bot") is False
    assert is_collaborative_review_target(login="dependabot[bot]") is False
    assert is_bot_actor("github-actions[bot]") is True


def test_automated_issue_labels_do_not_count():
    assert labels_are_automated("automated,nexus-pulse") is True
    assert is_collaborative_review_target(
        login="ThePeoplesVoice",
        user_type="User",
        labels="automated,nexus-complete",
    ) is False


def test_living_issue_counts():
    assert is_collaborative_review_target(
        login="ThePeoplesVoice",
        user_type="User",
        labels="enhancement",
    ) is True
