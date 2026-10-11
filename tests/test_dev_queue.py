"""Finished or expired dev-queue items must not lead the Dev Cycle issue (#245)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from nexus.dev_queue import item_expiry, retire_stale_items

NOW = datetime(2026, 10, 6, 0, 30, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parent.parent


def _queue() -> dict:
    return {
        "done": [{"id": "land-status-sync-2026-09-13", "title": "merged", "completed": "2026-09-12"}],
        "next": [
            {"id": "land-status-sync-2026-09-13", "title": "Merge status sync", "priority": 1},
            {"id": "hold-complete-until-2026-09-17",
             "title": "Do not dispatch Complete again until Thursday 2026-09-17 10:00 UTC", "priority": 2},
            {"id": "one-living-collaborative-pr", "title": "Open one non-chore PR", "priority": 3},
            {"id": "pr-landed", "title": "Land a PR", "status": "Merged", "priority": 4},
            {"id": "closed-thing", "title": "Close it", "status": "closed", "priority": 5},
            {"id": "future-hold", "title": "Hold", "hold_until": "2026-10-09", "priority": 6},
            {"id": "expires-today", "title": "Today", "expires": "2026-10-06", "priority": 7},
        ],
    }


def test_expired_hold_and_terminal_status_drop_out_of_next():
    queue = _queue()
    retired = retire_stale_items(queue, now=NOW)

    assert [i["id"] for i in queue["next"]] == [
        "one-living-collaborative-pr", "future-hold", "expires-today",
    ]
    reasons = {r["id"]: r["retired_reason"] for r in retired}
    assert reasons == {
        "land-status-sync-2026-09-13": "already in done",
        "hold-complete-until-2026-09-17": "hold/expiry 2026-09-17 passed",
        "pr-landed": "status merged",
        "closed-thing": "status closed",
    }


def test_retired_items_move_to_done_once_newest_first():
    queue = _queue()
    retire_stale_items(queue, now=NOW)
    ids = [d["id"] for d in queue["done"]]

    assert ids.count("land-status-sync-2026-09-13") == 1
    assert ids[0] == "closed-thing"
    assert {"hold-complete-until-2026-09-17", "pr-landed"} <= set(ids)
    hold = next(d for d in queue["done"] if d["id"] == "hold-complete-until-2026-09-17")
    assert hold["completed"] == "2026-10-06"
    assert hold["evidence"].startswith("auto-retired by dev cycle")
    # second read is a no-op
    assert retire_stale_items(queue, now=NOW) == []


def test_branch_dates_in_ids_are_not_treated_as_expiry():
    assert item_expiry({"id": "land-status-sync-2026-09-13", "title": "Merge ara/status-sync-2026-09-13"}) is None
    assert item_expiry({"id": "sweep-automated-issues-2026-09-13"}) is None


def test_committed_queue_has_no_stale_next_items():
    queue = json.loads((ROOT / "config" / "dev_queue.json").read_text(encoding="utf-8"))
    assert retire_stale_items(queue, now=NOW) == []
