"""Read-only contribution reputation surface.

Derived from usage_stats and simple, auditable heuristics.
No tokens. No spend. No gating of Open Core.
See ORGANIC_SYSTEMS.md for design intent and constraints.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .usage import load_usage_stats, DEFAULT_PATH as USAGE_PATH

ROOT = Path(__file__).resolve().parent.parent
REPUTATION_PATH = ROOT / "config" / "reputation.json"

# Simple, transparent weights — easy to critique and change
WEIGHTS = {
    "pr": 3.0,          # merged-path analyses carry more signal
    "issue": 1.5,
    "commit": 1.0,
    "self_audit": 2.0,  # governance work is high-value
    "pulse": 0.5,
    "other": 0.5,
}


def _defaults() -> dict[str, Any]:
    return {
        "version": "0.1.0",
        "description": "Read-only contribution reputation derived from usage_stats. Not a currency.",
        "score": 0.0,
        "components": {},
        "total_successful_analyses": 0,
        "last_computed": None,
        "notes": "Weights are documented in nexus/reputation.py. Open Core remains ungated.",
    }


def compute_reputation(usage: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compute a simple reputation snapshot from usage counters."""
    stats = usage if usage is not None else load_usage_stats()
    by_type = stats.get("by_type") or {}

    components: dict[str, float] = {}
    score = 0.0
    for key, weight in WEIGHTS.items():
        count = int(by_type.get(key, 0))
        part = round(count * weight, 2)
        components[key] = part
        score += part

    result = {
        "version": "0.1.0",
        "description": "Read-only contribution reputation derived from usage_stats. Not a currency.",
        "score": round(score, 2),
        "components": components,
        "weights": WEIGHTS,
        "total_successful_analyses": int(stats.get("total_successful_analyses", 0)),
        "last_computed": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": "Weights live in nexus/reputation.py. Subject to continuous critique. Open Core forever free.",
    }
    return result


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


def refresh_reputation(persist: bool = True) -> dict[str, Any]:
    """Recompute from current usage and optionally write config/reputation.json."""
    data = compute_reputation()
    if persist:
        save_reputation(data)
    return data


def reputation_summary_md(data: dict[str, Any] | None = None) -> str:
    """Short markdown block for pulse / status surfaces."""
    d = data if data is not None else load_reputation()
    comps = d.get("components") or {}
    lines = [
        f"**Reputation score (read-only):** {d.get('score', 0)}",
        f"- From {d.get('total_successful_analyses', 0)} successful analyses",
        f"- Components: pr={comps.get('pr', 0)} · issue={comps.get('issue', 0)} · "
        f"commit={comps.get('commit', 0)} · self_audit={comps.get('self_audit', 0)} · "
        f"pulse={comps.get('pulse', 0)}",
        "- Not a token. Does not gate Open Core. See ORGANIC_SYSTEMS.md.",
    ]
    return "\n".join(lines)
