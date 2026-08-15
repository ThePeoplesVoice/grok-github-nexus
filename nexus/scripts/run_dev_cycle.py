#!/usr/bin/env python3
"""Automated development cycle runner.

Observe → score → refresh queue metadata → append field note.
Does not call external AI providers. Safe for frequent schedule.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nexus import __version__
from nexus.audit import structural_health, alignment_signals, progressive_snapshot
from nexus.usage import load_usage_stats
from nexus.reputation import compute_reputation, reputation_summary_md
from nexus.presence import load_presence
from nexus.field_notes import append_field_note, notes_summary_md

# scripts/ -> nexus/ -> repo root
ROOT = Path(__file__).resolve().parent.parent.parent
QUEUE_PATH = ROOT / "config" / "dev_queue.json"


def _load_queue() -> dict[str, Any]:
    try:
        data = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {"version": "1.0.0", "done": [], "next": [], "backlog": []}


def _save_queue(data: dict[str, Any]) -> None:
    data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _recent_commits(n: int = 8) -> str:
    r = subprocess.run(
        ["git", "log", "--oneline", "-n", str(n)],
        capture_output=True, text=True,
    )
    return r.stdout.strip()


def _propose_from_observation(
    *,
    health: dict[str, Any],
    stats: dict[str, Any],
    rep: dict[str, Any],
    presence: dict[str, Any],
    queue: dict[str, Any],
) -> list[dict[str, Any]]:
    """Lightweight heuristic proposals — not AI. Merge with existing next[] by id."""
    existing_ids = {item.get("id") for item in (queue.get("next") or []) if isinstance(item, dict)}
    existing_ids |= {item.get("id") for item in (queue.get("done") or []) if isinstance(item, dict)}
    proposals: list[dict[str, Any]] = []

    total = int(stats.get("total_successful_analyses", 0))
    if total < 5 and "accumulate-real-usage" not in existing_ids:
        proposals.append({
            "id": "accumulate-real-usage",
            "title": "Run live provider analyses so usage/reputation leave zero",
            "priority": 1,
            "leverage": "high",
            "risk": "low",
            "why": f"Only {total} successful analyses recorded — organic stack is still cold.",
        })

    if health.get("score", 100) < 90 and "restore-structural-health" not in existing_ids:
        proposals.append({
            "id": "restore-structural-health",
            "title": f"Restore structural health (now {health.get('score')}/100)",
            "priority": 1,
            "leverage": "high",
            "risk": "low",
            "why": f"Missing: {health.get('missing')}",
        })

    if not presence.get("generated_at") and "first-real-pulse" not in existing_ids:
        proposals.append({
            "id": "first-real-pulse",
            "title": "Dispatch Nexus Pulse once secrets are present to seed presence_state",
            "priority": 2,
            "leverage": "high",
            "risk": "low",
            "why": "Presence continuity is scaffolded but not yet populated by a live pulse.",
        })

    if rep.get("freshness") == "stale" and "refresh-activity" not in existing_ids:
        proposals.append({
            "id": "refresh-activity",
            "title": "Generate fresh analyses — reputation is stale under half-life decay",
            "priority": 2,
            "leverage": "medium",
            "risk": "low",
            "why": f"days_idle={rep.get('days_idle')} decay={rep.get('decay_factor')}",
        })

    return proposals


def main() -> None:
    print(f"🔄 Nexus automated development cycle — package v{__version__}")
    print("=" * 60)

    health = structural_health()
    signals = alignment_signals()
    snap = progressive_snapshot()
    stats = load_usage_stats()
    rep = compute_reputation()
    presence = load_presence()
    queue = _load_queue()
    log = _recent_commits()

    print(f"Structural health: {health['score']}/100")
    print(f"Triad hits: {signals['total_triad_hits']}")
    print(f"Phase: {snap.get('phase')}")
    print(f"Analyses: {stats.get('total_successful_analyses')}")
    print(reputation_summary_md(rep))
    print(f"Presence: {presence.get('generated_at') or 'none'}")
    print("Recent commits:")
    print(log or "(none)")

    # Merge heuristic proposals into next[]
    proposals = _propose_from_observation(
        health=health, stats=stats, rep=rep, presence=presence, queue=queue
    )
    next_items = list(queue.get("next") or [])
    existing = {i.get("id") for i in next_items if isinstance(i, dict)}
    for p in proposals:
        if p["id"] not in existing:
            next_items.append(p)
            print(f"➕ Queued: {p['id']} — {p['title']}")

    # Stable sort by priority
    next_items.sort(key=lambda x: int(x.get("priority", 99)) if isinstance(x, dict) else 99)
    queue["next"] = next_items
    queue["last_cycle"] = {
        "structural_health": health["score"],
        "triad_hits": signals["total_triad_hits"],
        "total_analyses": stats.get("total_successful_analyses", 0),
        "reputation_effective": rep.get("score"),
        "reputation_freshness": rep.get("freshness"),
        "presence_at": presence.get("generated_at"),
        "package_version": __version__,
    }
    _save_queue(queue)
    print(f"✅ dev_queue.json updated ({len(next_items)} next items)")

    # Field note
    note_text = (
        f"Dev cycle complete. health={health['score']} "
        f"analyses={stats.get('total_successful_analyses')} "
        f"rep_effective={rep.get('score')} freshness={rep.get('freshness')} "
        f"next_top={(next_items[0].get('id') if next_items else None)}"
    )
    note = append_field_note(
        note_text,
        source="dev_cycle",
        tags=["automated", "cycle"],
        meta={"health": health["score"], "package": __version__},
    )
    print(f"📝 Field note appended @ {note['ts']}")

    body = f"""# 🔄 Nexus Dev Cycle Report

**Package:** v{__version__}  
**Structural health:** {health['score']}/100  
**Triad hits:** {signals['total_triad_hits']}  
**Analyses:** {stats.get('total_successful_analyses')}  
**Reputation:** effective {rep.get('score')} ({rep.get('freshness')})  
**Presence:** {presence.get('generated_at') or 'none'}

## Top next items
{chr(10).join(f"- `{i.get('id')}` (p{i.get('priority')}): {i.get('title')}" for i in next_items[:5]) or '- (empty)'}

## Recent field notes
{notes_summary_md(5)}

## Recent commits
```
{log or '(none)'}
```

See `AUTOMATED_DEVELOPMENT.md` and `config/dev_queue.json`.
"""
    out = Path("/tmp/nexus_dev_cycle.md")
    out.write_text(body, encoding="utf-8")
    print(f"✅ Report at {out}")
    print(body[:900])


if __name__ == "__main__":
    main()
