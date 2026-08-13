"""Shared runtime helpers for analysis runners.

Keeps the post-success path (usage + reputation + badge) consistent
across PR, issue, commit, self-audit, and pulse.
"""

from __future__ import annotations

from typing import Any

from .usage import record_successful_analysis
from .reputation import refresh_reputation


def after_successful_analysis(analysis_type: str) -> dict[str, Any]:
    """Increment usage, refresh reputation (and badge/README), return both."""
    stats = record_successful_analysis(analysis_type, persist=True)
    rep = refresh_reputation(persist=True)
    return {
        "stats": stats,
        "reputation": rep,
        "total": int(stats.get("total_successful_analyses", 0)),
        "type_count": int((stats.get("by_type") or {}).get(analysis_type, 0)),
        "effective_score": rep.get("score"),
        "raw_score": rep.get("raw_score"),
        "freshness": rep.get("freshness"),
    }


def log_success(result: dict[str, Any], analysis_type: str) -> None:
    print(
        f"📊 Usage incremented → total={result.get('total')} "
        f"{analysis_type}={result.get('type_count')}"
    )
    print(
        f"🌱 Reputation → effective={result.get('effective_score')} "
        f"raw={result.get('raw_score')} freshness={result.get('freshness')}"
    )
