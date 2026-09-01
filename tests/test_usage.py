"""Tests for nexus.usage — counters must not lie about collaborative work."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.usage import increment_usage, load_usage_stats


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
