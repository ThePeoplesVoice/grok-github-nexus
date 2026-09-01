"""Usage tracking for progressive unlock triggers.

Lightweight, file-based counters that analysis workflows can increment
after a successful Grok / Claude call. The write path is intentionally
simple so it can be called from any runner; GitHub Actions then commits
the updated config/usage_stats.json when permissions allow.

Aligned with the progressive control plane in config/progressive.json.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / "config" / "usage_stats.json"

VALID_TYPES = ("commit", "pr", "issue", "self_audit", "pulse", "complete", "other")
COLLABORATIVE_TYPES = ("pr", "issue")
INTERNAL_TYPES = tuple(t for t in VALID_TYPES if t not in COLLABORATIVE_TYPES)


def _defaults() -> dict[str, Any]:
    return {
        "version": "1.1.1",
        "description": "Lightweight counters for progressive unlock triggers. Incremented after successful analysis.",
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
        "last_updated": None,
        "last_type": None,
        "notes": "Counters feed min_successful_analyses in progressive.json Layer 1. Written by nexus.usage after successful provider calls.",
    }


def load_usage_stats(path: str | Path | None = None) -> dict[str, Any]:
    """Return usage_stats.json as a dict. Safe defaults on any error."""
    target = Path(path) if path else DEFAULT_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _defaults()
        # Ensure required keys exist even if file is older
        base = _defaults()
        base.update(data)
        by_type = base.get("by_type") or {}
        for k in VALID_TYPES:
            by_type.setdefault(k, 0)
        base["by_type"] = by_type
        return base
    except Exception:
        return _defaults()


def save_usage_stats(stats: dict[str, Any], path: str | Path | None = None) -> Path:
    """Write stats dict to disk (pretty JSON). Returns the path written."""
    target = Path(path) if path else DEFAULT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(stats, indent=2, ensure_ascii=False) + "\n"
    target.write_text(text, encoding="utf-8")
    return target


def increment_usage(
    analysis_type: str = "other",
    *,
    path: str | Path | None = None,
    persist: bool = True,
    amount: int = 1,
) -> dict[str, Any]:
    """Increment total + by_type counters and optionally persist.

    Returns the updated stats dict.
    analysis_type is normalised to one of VALID_TYPES.
    """
    t = (analysis_type or "other").strip().lower()
    if t not in VALID_TYPES:
        t = "other"

    stats = load_usage_stats(path)
    by_type = stats.get("by_type") or {}

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stats["total_successful_analyses"] = int(stats.get("total_successful_analyses", 0)) + amount
    by_type[t] = int(by_type.get(t, 0)) + amount
    stats["by_type"] = by_type
    stats["last_updated"] = now
    stats["last_type"] = t
    stats["version"] = stats.get("version") or "1.1.1"

    if persist:
        save_usage_stats(stats, path)

    return stats


def record_successful_analysis(
    analysis_type: str,
    *,
    path: str | Path | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Convenience alias used by runners after a successful Grok/Claude call."""
    return increment_usage(analysis_type, path=path, persist=persist)
