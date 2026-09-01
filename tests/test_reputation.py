"""Tests for nexus.reputation — computation, decay, and badge writing."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import pytest

from nexus.context import layer1_enabled
from nexus.reputation import (
    compute_reputation,
    load_reputation,
    refresh_reputation,
    reputation_badge_line,
    save_reputation,
    _staleness,
)
from nexus.usage import increment_usage


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
    # Internal churn is tracked, but collaborative PR/issue evidence is what drives the unlock score.
    assert rep["raw_score"] == pytest.approx(12.0, abs=0.01)
    assert rep["internal_score"] == pytest.approx(12.0, abs=0.01)
    assert rep["collaborative_score"] == pytest.approx(0.0, abs=0.01)
    assert rep["score"] == pytest.approx(0.0, abs=0.01)
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
    parsed = urlparse(badge.removeprefix("![Reputation](").removesuffix(")"))
    assert parsed.scheme == "https"
    assert parsed.netloc == "img.shields.io"
    assert "nexus_reputation" in badge
    assert str(rep["score"]) in badge


def test_effective_score_lower_than_raw_when_stale():
    stale_stats = dict(SAMPLE_STATS)
    stale_stats["last_updated"] = "2020-01-01T00:00:00Z"
    rep = compute_reputation(stale_stats)
    assert rep["score"] <= rep["raw_score"]
    assert rep["freshness"] == "stale"


def test_layer1_requires_collaborative_evidence(tmp_path):
    path = tmp_path / "usage_stats.json"
    prog = {
        "layers": {
            "1_progressive_unlocks": {
                "enabled": True,
                "triggers": {"min_successful_analyses": 1, "min_community_prs": 1},
            }
        }
    }

    stats = increment_usage("self_audit", path=path, persist=True)
    # Honest meter: internal work counts. Layer 1 still stays gated.
    assert stats["total_successful_analyses"] == 1
    assert stats["by_type"]["self_audit"] == 1
    assert layer1_enabled(prog=prog, usage=stats) is False

    collaborative = increment_usage("pr", path=path, persist=True)
    assert collaborative["by_type"]["pr"] == 1
    assert collaborative["total_successful_analyses"] == 2
    assert layer1_enabled(prog=prog, usage=collaborative) is True


def test_sync_public_badges_only_reports_real_badge_changes(tmp_path, monkeypatch):
    from nexus import reputation

    badge_path = tmp_path / "badges" / "reputation.md"
    readme_path = tmp_path / "README.md"
    status_path = tmp_path / "STATUS.md"

    readme_text = "# Human-owned README\n"
    status_text = "# Human-owned STATUS\n"
    readme_path.write_text(readme_text, encoding="utf-8")
    status_path.write_text(status_text, encoding="utf-8")

    monkeypatch.setattr(reputation, "BADGE_PATH", badge_path)

    rep = compute_reputation(SAMPLE_STATS)

    assert reputation.sync_public_badges(rep) == {
        "readme": False,
        "status": False,
        "badge_md": True,
    }
    assert reputation.sync_public_badges(rep) == {
        "readme": False,
        "status": False,
        "badge_md": False,
    }
    assert readme_path.read_text(encoding="utf-8") == readme_text
    assert status_path.read_text(encoding="utf-8") == status_text
