"""Shared runtime helpers for analysis runners.

Keeps the post-success path (usage + reputation + Astra + badge) consistent
across PR, issue, commit, self-audit, and pulse.
"""

from __future__ import annotations

from typing import Any

from .usage import record_counted_review, record_successful_analysis
from .reputation import refresh_reputation
from .astra import refresh_astra


def after_successful_analysis(
    analysis_type: str,
    *,
    review_number: int | str | None = None,
) -> dict[str, Any]:
    """Increment usage, refresh reputation + Astra (and badges), return all.

    When ``review_number`` is set, the increment is once-per-review so a
    usage-chore push cannot grind the collaborative meter.
    """
    applied = True
    already = False
    if review_number is not None:
        stats, applied = record_counted_review(
            analysis_type, review_number, persist=True
        )
        already = not applied
        if already:
            return {
                "stats": stats,
                "reputation": None,
                "astra": None,
                "total": int(stats.get("total_successful_analyses", 0)),
                "type_count": int((stats.get("by_type") or {}).get(analysis_type, 0)),
                "effective_score": None,
                "raw_score": None,
                "freshness": None,
                "astra_balance": None,
                "applied": False,
                "already_counted": True,
            }
    else:
        stats = record_successful_analysis(analysis_type, persist=True)
    rep = refresh_reputation(persist=True)
    astra = refresh_astra(persist=True, reputation=rep)
    return {
        "stats": stats,
        "reputation": rep,
        "astra": astra,
        "total": int(stats.get("total_successful_analyses", 0)),
        "type_count": int((stats.get("by_type") or {}).get(analysis_type, 0)),
        "effective_score": rep.get("score"),
        "raw_score": rep.get("raw_score"),
        "freshness": rep.get("freshness"),
        "astra_balance": astra.get("balance"),
        "applied": applied,
        "already_counted": already,
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
    print(
        f"🌟 Astra → balance={result.get('astra_balance')} "
        f"(land-backed, spendable=False)"
    )
