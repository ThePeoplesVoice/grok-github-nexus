"""Read-only contribution reputation surface.

Derived from usage_stats and simple, auditable heuristics.
No tokens. No spend. No gating of Open Core.

Includes a transparent staleness decay (30-day half-life) so scores
do not grow forever without continued activity.

On refresh, rewrites badges/reputation.md so the public signal stays current.

See ORGANIC_SYSTEMS.md for design intent and constraints.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .usage import load_usage_stats

ROOT = Path(__file__).resolve().parent.parent
REPUTATION_PATH = ROOT / "config" / "reputation.json"
BADGE_PATH = ROOT / "badges" / "reputation.md"

WEIGHTS = {
    "pr": 3.0,
    "issue": 1.5,
    "commit": 1.0,
    "self_audit": 2.0,
    "pulse": 0.5,
    "complete": 1.0,
    "other": 0.5,
}

HALF_LIFE_DAYS = 30.0


def _defaults() -> dict[str, Any]:
    return {
        "version": "0.2.0",
        "description": "Read-only contribution reputation derived from usage_stats. Not a currency.",
        "raw_score": 0.0,
        "score": 0.0,
        "decay_factor": 1.0,
        "days_idle": 0.0,
        "freshness": "unknown",
        "components": {},
        "weights": WEIGHTS,
        "half_life_days": HALF_LIFE_DAYS,
        "total_successful_analyses": 0,
        "last_activity": None,
        "last_computed": None,
        "notes": "Weights + decay live in nexus/reputation.py. Open Core remains ungated.",
    }


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        cleaned = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except Exception:
        return None


def _staleness(last_activity: str | None, now: datetime | None = None) -> tuple[float, float, str]:
    now = now or datetime.now(timezone.utc)
    dt = _parse_iso(last_activity)
    if dt is None:
        return 0.0, 1.0, "unknown"

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    days = max(0.0, (now - dt).total_seconds() / 86400.0)
    factor = 0.5 ** (days / HALF_LIFE_DAYS)
    factor = max(0.01, min(1.0, factor))

    if days < 7:
        label = "fresh"
    elif days < HALF_LIFE_DAYS:
        label = "aging"
    else:
        label = "stale"

    return round(days, 2), round(factor, 4), label


def compute_reputation(usage: dict[str, Any] | None = None) -> dict[str, Any]:
    stats = usage if usage is not None else load_usage_stats()
    by_type = stats.get("by_type") or {}
    last_activity = stats.get("last_updated")

    components: dict[str, float] = {}
    raw = 0.0
    for key, weight in WEIGHTS.items():
        count = int(by_type.get(key, 0))
        part = round(count * weight, 2)
        components[key] = part
        raw += part

    days_idle, decay_factor, freshness = _staleness(last_activity)
    effective = round(raw * decay_factor, 2)

    return {
        "version": "0.2.0",
        "description": "Read-only contribution reputation derived from usage_stats. Not a currency.",
        "raw_score": round(raw, 2),
        "score": effective,
        "decay_factor": decay_factor,
        "days_idle": days_idle,
        "freshness": freshness,
        "components": components,
        "weights": WEIGHTS,
        "half_life_days": HALF_LIFE_DAYS,
        "total_successful_analyses": int(stats.get("total_successful_analyses", 0)),
        "last_activity": last_activity,
        "last_computed": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": (
            "effective score = raw_score × 0.5^(days_idle / 30). "
            "Subject to continuous critique. Open Core forever free."
        ),
    }


def save_reputation(data: dict[str, Any], path: str | Path | None = None) -> Path:
    target = Path(path) if path else REPUTATION_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def load_reputation(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else REPUTATION_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else _defaults()
    except Exception:
        return _defaults()


def reputation_badge_line(data: dict[str, Any] | None = None) -> str:
    d = data if data is not None else load_reputation()
    score = d.get("score", 0)
    return f"![Reputation](https://img.shields.io/badge/nexus_reputation-{score}-blue)"


def write_badge(data: dict[str, Any] | None = None) -> bool:
    d = data if data is not None else load_reputation()
    score = d.get("score", 0)
    raw = d.get("raw_score", score)
    freshness = d.get("freshness", "unknown")
    total = d.get("total_successful_analyses", 0)
    decay = d.get("decay_factor", 1.0)

    badge = reputation_badge_line(d)
    body = f"""# Nexus Reputation Badge

{badge}
**Effective score:** {score}  
**Raw (lifetime) score:** {raw}  
**Freshness:** {freshness} (decay factor {decay})  
**From analyses:** {total}

Read-only. Not a token. Does not gate Open Core.  
Formula: `effective = raw × 0.5^(days_idle / 30)`  
See `ORGANIC_SYSTEMS.md` and `nexus/reputation.py`.
"""
    BADGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if BADGE_PATH.exists() and BADGE_PATH.read_text(encoding="utf-8") == body:
        return False
    BADGE_PATH.write_text(body, encoding="utf-8")
    return True


def sync_public_badges(data: dict[str, Any] | None = None) -> dict[str, bool]:
    """Rewrite generated reputation badge artifacts."""
    d = data if data is not None else load_reputation()
    badge_changed = write_badge(d)
    return {
        "readme": False,
        "status": False,
        "badge_md": badge_changed,
    }


def refresh_reputation(persist: bool = True) -> dict[str, Any]:
    data = compute_reputation()
    if persist:
        save_reputation(data)
        sync_public_badges(data)
    return data


def reputation_summary_md(data: dict[str, Any] | None = None) -> str:
    d = data if data is not None else load_reputation()
    comps = d.get("components") or {}
    lines = [
        f"**Reputation (read-only):** effective **{d.get('score', 0)}** "
        f"(raw {d.get('raw_score', d.get('score', 0))}, "
        f"freshness={d.get('freshness', 'unknown')}, "
        f"decay={d.get('decay_factor', 1.0)})",
        f"- From {d.get('total_successful_analyses', 0)} successful analyses",
        f"- Components: pr={comps.get('pr', 0)} · issue={comps.get('issue', 0)} · "
        f"commit={comps.get('commit', 0)} · self_audit={comps.get('self_audit', 0)} · "
        f"pulse={comps.get('pulse', 0)} · complete={comps.get('complete', 0)}",
        "- Half-life 30 days on idle. Not a token. Does not gate Open Core.",
    ]
    return "\n".join(lines)
