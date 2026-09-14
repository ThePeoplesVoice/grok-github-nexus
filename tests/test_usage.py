"""Tests for nexus.usage — counters must not lie about collaborative work."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.usage import (
    already_counted,
    increment_usage,
    load_usage_stats,
    record_counted_review,
    review_count_token,
    usage_push_refspec,
)


def test_collaborative_type_increments_from_zero(tmp_path: Path):
    p = tmp_path / "usage_stats.json"
    p.write_text(
        json.dumps(
            {
                "total_successful_analyses": 0,
                "by_type": {
                    "commit": 0,
                    "pr": 0,
                    "issue": 0,
                    "self_audit": 0,
                    "pulse": 0,
                    "complete": 0,
                    "other": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    stats = increment_usage("pr", path=p, persist=True)
    assert stats["by_type"]["pr"] == 1
    assert stats["total_successful_analyses"] == 1
    stats = increment_usage("issue", path=p, persist=True)
    assert stats["by_type"]["issue"] == 1
    assert stats["total_successful_analyses"] == 2


def test_internal_type_still_increments(tmp_path: Path):
    p = tmp_path / "usage_stats.json"
    p.write_text(
        json.dumps(
            {
                "total_successful_analyses": 5,
                "by_type": {
                    "commit": 5,
                    "pr": 0,
                    "issue": 0,
                    "self_audit": 0,
                    "pulse": 0,
                    "complete": 0,
                    "other": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    stats = increment_usage("pulse", path=p, persist=True)
    assert stats["by_type"]["pulse"] == 1
    assert stats["total_successful_analyses"] == 6


def test_backfill_shape_is_consistent():
    stats = load_usage_stats()
    assert stats["by_type"]["pr"] >= 3
    assert stats["total_successful_analyses"] >= stats["by_type"]["pr"]


def _blank_usage(tmp_path: Path) -> Path:
    p = tmp_path / "usage_stats.json"
    p.write_text(
        json.dumps(
            {
                "total_successful_analyses": 3,
                "by_type": {
                    "commit": 0,
                    "pr": 3,
                    "issue": 0,
                    "self_audit": 0,
                    "pulse": 0,
                    "complete": 0,
                    "other": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    return p


def test_record_counted_review_is_idempotent(tmp_path: Path):
    p = _blank_usage(tmp_path)
    first, applied = record_counted_review("pr", 179, path=p, persist=True)
    assert applied is True
    assert first["by_type"]["pr"] == 4
    assert first["total_successful_analyses"] == 4
    assert first["counted_reviews"] == ["pr:179"]
    assert already_counted(first, "pr", 179) is True

    second, applied_again = record_counted_review("pr", 179, path=p, persist=True)
    assert applied_again is False
    assert second["by_type"]["pr"] == 4
    assert second["total_successful_analyses"] == 4
    assert load_usage_stats(p)["by_type"]["pr"] == 4


def test_record_counted_review_rejects_junk():
    assert review_count_token("pr", 0) is None
    assert review_count_token("pr", "nope") is None
    assert review_count_token("pulse", 12) is None
    assert review_count_token("pr", -1) is None


def test_usage_push_refspec_is_the_detached_head_write_path():
    assert usage_push_refspec("cursor/analysis-sim") == (
        "HEAD:refs/heads/cursor/analysis-sim"
    )
    assert usage_push_refspec("") is None
    assert usage_push_refspec(None) is None
    assert usage_push_refspec("-evil") is None
    assert usage_push_refspec("foo:bar") is None
    assert usage_push_refspec("foo bar") is None
    assert usage_push_refspec("foo..bar") is None
