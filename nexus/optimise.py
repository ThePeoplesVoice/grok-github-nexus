"""Optimisation and integration on top of local simulation.

Consume observe → simulate → recommend, then:
- tell living partner reviews from grind bots
- flag stale queue items that already landed
- never persist Astra, usage, or reputation

This is the hourly integration surface. Simulate thinks.
Optimise decides what still belongs on the board.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .simulate import reassess

ROOT = Path(__file__).resolve().parent.parent
QUEUE_PATH = ROOT / "config" / "dev_queue.json"
STATUS_PATH = ROOT / "STATUS.md"

# Queue ids that local evidence can retire without inventing new work.
LANDED_EVIDENCE = {
    "land-status-sync-2026-09-13": {
        "file": "STATUS.md",
        "needle": "#171",
        "evidence": "STATUS.md pins Pulse #171; merged as #172",
    },
}


def utc_now_iso(now: datetime | None = None) -> str:
    stamp = now or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_queue(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else QUEUE_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {"version": "1.0.0", "done": [], "next": [], "backlog": []}


def detect_stale_next(
    queue: dict[str, Any] | None = None,
    *,
    root: Path | None = None,
) -> list[dict[str, Any]]:
    """Return next[] items whose landing evidence is already on disk."""
    data = queue if queue is not None else load_queue()
    base = root if root is not None else ROOT
    stale: list[dict[str, Any]] = []
    for item in data.get("next") or []:
        if not isinstance(item, dict):
            continue
        spec = LANDED_EVIDENCE.get(str(item.get("id") or ""))
        if not spec:
            continue
        target = base / spec["file"]
        try:
            text = target.read_text(encoding="utf-8")
        except Exception:
            continue
        if spec["needle"] in text:
            stale.append({
                "id": item.get("id"),
                "title": item.get("title"),
                "evidence": spec["evidence"],
                "stance": "retire",
            })
    return stale


def headline(report: dict[str, Any], stale: list[dict[str, Any]] | None = None) -> str:
    obs = report.get("observation") or {}
    card = obs.get("scorecard") or {}
    lag = obs.get("astra_lag") or {}
    gate = report.get("expansion_gate") or {}
    actions = report.get("recommendations") or []
    top_act = next((a for a in actions if a.get("stance") == "act"), actions[0] if actions else {})
    stale_ids = ",".join(str(item.get("id")) for item in (stale or []) if item.get("id")) or "none"
    return (
        f"gate={gate.get('recommendation')} "
        f"unlock={card.get('unlock_score')} "
        f"astra_lag={lag.get('lagging')} "
        f"top_act={top_act.get('id')} "
        f"stale_queue={stale_ids}"
    )


def optimise(
    report: dict[str, Any] | None = None,
    *,
    queue: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Rank simulation output and queue drift. Read-only on living meters."""
    assessed = report if report is not None else reassess(now=now)
    board = queue if queue is not None else load_queue()
    stale = detect_stale_next(board)
    actions = list(assessed.get("recommendations") or [])
    decisions = []
    for item in stale:
        decisions.append({
            "id": f"retire-{item.get('id')}",
            "title": f"Retire landed queue item `{item.get('id')}`",
            "stance": "retire",
            "leverage": "medium",
            "why": item.get("evidence"),
        })
    decisions.extend(actions)
    return {
        "observed_at": assessed.get("observed_at"),
        "headline": headline(assessed, stale),
        "expansion_gate": assessed.get("expansion_gate"),
        "stale_queue": stale,
        "decisions": decisions,
        "persisted": {
            "astra": False,
            "usage": False,
            "reputation": False,
            "issues": False,
            "queue": False,
        },
    }


def apply_queue_refresh(
    optimisation: dict[str, Any],
    *,
    queue: dict[str, Any] | None = None,
    path: str | Path | None = None,
    persist: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Move evidenced next[] items to done. Never writes Astra or usage."""
    data = copy_queue(queue if queue is not None else load_queue())
    stale_ids = {item.get("id") for item in optimisation.get("stale_queue") or []}
    kept: list[dict[str, Any]] = []
    done = list(data.get("done") or [])
    done_ids = {item.get("id") for item in done if isinstance(item, dict)}
    for item in data.get("next") or []:
        if not isinstance(item, dict):
            continue
        if item.get("id") in stale_ids and item.get("id") not in done_ids:
            done.insert(0, {
                "id": item.get("id"),
                "title": item.get("title"),
                "completed": utc_now_iso(now)[:10],
                "evidence": next(
                    (
                        row.get("evidence")
                        for row in (optimisation.get("stale_queue") or [])
                        if row.get("id") == item.get("id")
                    ),
                    "landed",
                ),
            })
            done_ids.add(item.get("id"))
        elif item.get("id") not in stale_ids:
            kept.append(item)
    data["done"] = done
    data["next"] = kept
    data["updated_at"] = utc_now_iso(now)
    if persist:
        target = Path(path) if path else QUEUE_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        persisted = dict(optimisation.get("persisted") or {})
        persisted["queue"] = True
        optimisation = {**optimisation, "persisted": persisted}
    return data


def copy_queue(queue: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(queue))


def format_optimisation_md(optimisation: dict[str, Any]) -> str:
    gate = optimisation.get("expansion_gate") or {}
    persisted = optimisation.get("persisted") or {}
    stale_lines = []
    for item in optimisation.get("stale_queue") or []:
        stale_lines.append(
            f"- `{item.get('id')}` — {item.get('evidence')}"
        )
    decision_lines = []
    for item in optimisation.get("decisions") or []:
        decision_lines.append(
            f"- **{item.get('stance')}** `{item.get('id')}` "
            f"(leverage {item.get('leverage')}): {item.get('title')} "
            f"— {item.get('why')}"
        )
    return f"""# 🔧 Nexus Optimisation / Integration

**Observed:** {optimisation.get('observed_at')}  
**Headline:** {optimisation.get('headline')}  
**Expansion gate:** {gate.get('recommendation')} — {gate.get('reason')}

## Stale queue items

{chr(10).join(stale_lines) or '- (none)'}

## Decisions

{chr(10).join(decision_lines) or '- (none)'}

## Persistence

Astra written: {persisted.get('astra')} · usage written: {persisted.get('usage')} · queue written: {persisted.get('queue')} · issues filed: {persisted.get('issues')}

See `AUTOMATED_DEVELOPMENT.md`. Optimise the board. Do not hand-edit Astra.
"""
