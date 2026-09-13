"""Optimisation stays dry-run on meters and retires only evidenced queue items."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from nexus.astra import load_astra, save_astra
from nexus.optimise import (
    apply_queue_refresh,
    detect_stale_next,
    format_optimisation_md,
    headline,
    optimise,
)
from nexus.simulate import reassess
from nexus.usage import load_usage_stats, save_usage_stats

NOW = datetime(2026, 9, 13, 21, 6, tzinfo=timezone.utc)

SAMPLE_USAGE = {
    "total_successful_analyses": 35,
    "by_type": {
        "commit": 18,
        "pr": 3,
        "issue": 1,
        "self_audit": 5,
        "pulse": 7,
        "complete": 1,
        "other": 0,
    },
    "last_updated": "2026-09-12T22:48:21Z",
}

GATED = {
    "layers": {
        "1_progressive_unlocks": {
            "enabled": False,
            "triggers": {"min_successful_analyses": 50, "min_community_prs": 3},
        }
    }
}

QUEUE = {
    "done": [],
    "next": [
        {
            "id": "land-status-sync-2026-09-13",
            "title": "Merge ara/status-sync-2026-09-13 after human-approval:public",
        },
        {
            "id": "hold-complete-until-2026-09-17",
            "title": "Do not dispatch Complete again until Thursday",
        },
    ],
    "backlog": [],
}


def test_detects_landed_status_sync(tmp_path: Path):
    (tmp_path / "STATUS.md").write_text("Pulse [#171](https://example) pin.\n", encoding="utf-8")
    stale = detect_stale_next(QUEUE, root=tmp_path)
    assert [item["id"] for item in stale] == ["land-status-sync-2026-09-13"]


def test_does_not_retire_when_pin_missing(tmp_path: Path):
    (tmp_path / "STATUS.md").write_text("No pulse pin yet.\n", encoding="utf-8")
    stale = detect_stale_next(QUEUE, root=tmp_path)
    assert stale == []


def test_optimise_is_dry_run_on_meters(tmp_path: Path):
    usage_path = tmp_path / "usage_stats.json"
    astra_path = tmp_path / "astra.json"
    save_usage_stats(SAMPLE_USAGE, usage_path)
    save_astra({"balance": 10.5, "total_successful_analyses": 30}, astra_path)

    report = reassess(
        usage=load_usage_stats(usage_path),
        progressive=GATED,
        astra_ledger=load_astra(astra_path),
        now=NOW,
    )
    result = optimise(report, queue=QUEUE, now=NOW)

    assert result["persisted"]["astra"] is False
    assert result["persisted"]["usage"] is False
    assert result["persisted"]["queue"] is False
    assert load_usage_stats(usage_path)["total_successful_analyses"] == 35
    assert load_astra(astra_path)["total_successful_analyses"] == 30
    assert "gate=hold" in result["headline"]
    assert "unlock=10.5" in result["headline"]
    ids = {item["id"] for item in result["decisions"]}
    assert "one-living-collaborative-pr" in ids
    assert "hold-complete" in ids


def test_apply_queue_refresh_retires_only_stale_and_optional_persist(tmp_path: Path):
    queue_path = tmp_path / "dev_queue.json"
    (tmp_path / "STATUS.md").write_text("Pulse #171\n", encoding="utf-8")
    report = reassess(usage=SAMPLE_USAGE, progressive=GATED, astra_ledger={
        "balance": 10.5,
        "total_successful_analyses": 30,
    }, now=NOW)
    result = optimise(report, queue=QUEUE, now=NOW)
    result["stale_queue"] = detect_stale_next(QUEUE, root=tmp_path)

    updated = apply_queue_refresh(result, queue=QUEUE, path=queue_path, persist=True, now=NOW)
    assert [item["id"] for item in updated["next"]] == ["hold-complete-until-2026-09-17"]
    assert updated["done"][0]["id"] == "land-status-sync-2026-09-13"
    written = json.loads(queue_path.read_text(encoding="utf-8"))
    assert written["done"][0]["id"] == "land-status-sync-2026-09-13"

    dry = apply_queue_refresh(result, queue=QUEUE, persist=False, now=NOW)
    assert dry["done"][0]["id"] == "land-status-sync-2026-09-13"


def test_headline_and_report_sections():
    report = reassess(usage=SAMPLE_USAGE, progressive=GATED, astra_ledger={
        "balance": 10.5,
        "total_successful_analyses": 30,
    }, now=NOW)
    result = optimise(report, queue=QUEUE, now=NOW)
    text = format_optimisation_md(result)
    assert "Optimisation / Integration" in text
    assert "Persistence" in text
    assert headline(report).startswith("gate=")
