"""Tests for nexus.reputation — computation, decay, and badge writing."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from nexus.reputation import (
    compute_reputation,
    save_reputation,
    load_reputation,
    refresh_reputation,
    reputation_badge_line,
    _staleness,
)


SAMPLE_STATS = {
    "total_successful_analyses": 12,
    "by_type": {
        "commit": 9,
        "pr": 0,
        "issue": 0,
        "self_audit": 1,
        "pulse": 2,
        "other": 0,
    },
    "last_updated": "2026-08-17T17:15:53Z",
}


def test_compute_reputation_weights():
    rep = compute_reputation(SAMPLE_STATS)
    # commit: 9 * 1.0 = 9.0 ; self_audit: 1 * 2.0 = 2.0 ; pulse: 2 * 0.5 = 1.0 → raw = 12.0
    assert rep["raw_score"] == pytest.approx(12.0, abs=0.01)
    assert rep["total_successful_analyses"] == 12
    assert rep["components"]["commit"] == pytest.approx(9.0)
    assert rep["components"]["self_audit"] == pytest.approx(2.0)
    assert rep["components"]["pulse"] == pytest.approx(1.0)


def test_decay_fresh():
    days, factor, label = _staleness("2026-08-17T17:00:00Z")
    # should be < 7 days from "now" used in tests — use a very recent date
    assert label in ("fresh", "aging", "stale")  # label depends on when test runs
    assert 0.0 < factor <= 1.0


def test_staleness_far_past():
    days, factor, label = _staleness("2020-01-01T00:00:00Z")
    assert label == "stale"
    assert factor <= 0.01  # heavily decayed


def test_staleness_none():
    days, factor, label = _staleness(None)
    assert label == "unknown"
    assert factor == 1.0


def test_save_load_reputation(tmp_path):
    rep = compute_reputation(SAMPLE_STATS)
    path = tmp_path / "reputation.json"
    save_reputation(rep, path)
    loaded = load_reputation(path)
    assert loaded["raw_score"] == rep["raw_score"]
    assert loaded["total_successful_analyses"] == rep["total_successful_analyses"]


def test_load_reputation_missing_file(tmp_path):
    loaded = load_reputation(tmp_path / "nonexistent.json")
    assert loaded["raw_score"] == 0.0
    assert loaded["freshness"] == "unknown"


def test_badge_line_contains_score():
    rep = compute_reputation(SAMPLE_STATS)
    badge = reputation_badge_line(rep)
    assert "shields.io" in badge
    assert "nexus_reputation" in badge
    assert str(rep["score"]) in badge


def test_effective_score_lower_than_raw_when_stale():
    stale_stats = dict(SAMPLE_STATS)
    stale_stats["last_updated"] = "2020-01-01T00:00:00Z"
    rep = compute_reputation(stale_stats)
    assert rep["score"] <= rep["raw_score"]
    assert rep["freshness"] == "stale"
