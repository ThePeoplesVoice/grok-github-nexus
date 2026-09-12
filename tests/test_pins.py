"""Tests for one-live-pin automated report policy."""

from __future__ import annotations

import pytest

from nexus.pins import (
    family_spec,
    has_labels,
    is_protected,
    partition_pins,
    pin_title,
    superseded_comment,
)


def _issue(number: int, created: str, labels: list[str]) -> dict:
    return {
        "number": number,
        "created_at": created,
        "labels": [{"name": name} for name in labels],
        "title": f"issue {number}",
    }


PULSE = ("nexus-pulse", "automated")


def test_unknown_family_is_rejected():
    with pytest.raises(ValueError, match="unknown pin family"):
        family_spec("newsletter")


def test_newest_pulse_wins_and_older_are_superseded():
    live, superseded = partition_pins(
        [
            _issue(155, "2026-09-07T14:08:22Z", ["automated", "nexus-pulse"]),
            _issue(171, "2026-09-12T21:43:09Z", ["automated", "nexus-pulse"]),
        ],
        PULSE,
    )
    assert live is not None
    assert live["number"] == 171
    assert [item["number"] for item in superseded] == [155]


def test_commit_family_does_not_eat_pulses():
    live, superseded = partition_pins(
        [
            _issue(170, "2026-09-12T19:03:14Z", ["nexus-analysis", "automated"]),
            _issue(162, "2026-09-08T22:52:56Z", ["nexus-analysis", "automated"]),
            _issue(171, "2026-09-12T21:43:09Z", ["nexus-pulse", "automated"]),
        ],
        ("nexus-analysis", "automated"),
    )
    assert live is not None
    assert live["number"] == 170
    assert [item["number"] for item in superseded] == [162]


def test_keep_label_is_not_closed_and_does_not_steal_the_pin():
    live, superseded = partition_pins(
        [
            _issue(200, "2026-09-13T00:00:00Z", ["automated", "nexus-pulse", "keep"]),
            _issue(171, "2026-09-12T21:43:09Z", ["automated", "nexus-pulse"]),
            _issue(155, "2026-09-07T14:08:22Z", ["automated", "nexus-pulse"]),
        ],
        PULSE,
    )
    assert live is not None
    assert live["number"] == 171
    assert [item["number"] for item in superseded] == [155]


def test_human_issue_without_automated_is_ignored():
    assert is_protected(_issue(42, "2026-09-13T00:00:00Z", ["enhancement"])) is True
    live, superseded = partition_pins(
        [_issue(42, "2026-09-13T00:00:00Z", ["enhancement"])],
        PULSE,
    )
    assert live is None
    assert superseded == []


def test_partial_label_match_is_not_a_pin():
    issue = _issue(9, "2026-09-13T00:00:00Z", ["automated"])
    assert has_labels(issue, PULSE) is False


def test_pin_title_and_close_comment_are_stable():
    from datetime import datetime, timezone

    title = pin_title("pulse", datetime(2026, 9, 12, tzinfo=timezone.utc))
    assert title == "📡 Nexus Pulse — 2026-09-12"
    assert "#171" in superseded_comment(171)
