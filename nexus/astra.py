"""Astra — organic land-backed currency of the Nexus.

Named unit of contribution signal, symbolically tied to the Keysbrook
sanctuary vision. Currently a transparent, decaying balance derived
from reputation. Never gates Open Core. Spendability deferred.

See ASTRA.md for the full protocol.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .reputation import load_reputation, compute_reputation

ROOT = Path(__file__).resolve().parent.parent
ASTRA_PATH = ROOT / "config" / "astra.json"
BADGE_PATH = ROOT / "badges" / "astra.md"


def _defaults() -> dict[str, Any]:
    return {
        "version": "1.0.0",
        "name": "Astra",
        "description": "Organic land-backed contribution currency. Derived from reputation. Never gates Open Core.",
        "balance": 0.0,
        "raw_balance": 0.0,
        "decay_factor": 1.0,
        "days_idle": 0.0,
        "freshness": "unknown",
        "unit": "Astra",
        "land_backed": True,
        "spendable": False,
        "sanctuary_tie": "Keysbrook jarrah / black cockatoo sanctuary vision",
        "source_reputation_score": 0.0,
        "total_successful_analyses": 0,
        "last_activity": None,
        "last_computed": None,
        "notes": "balance = effective reputation at launch. Formula and spend rules live in ASTRA.md and this module.",
    }


def compute_astra(reputation: dict[str, Any] | None = None) -> dict[str, Any]:
    """Derive current Astra state from reputation (or recompute reputation)."""
    rep = reputation if reputation is not None else compute_reputation()

    balance = float(rep.get("score", 0.0))
    raw = float(rep.get("raw_score", balance))
    decay = float(rep.get("decay_factor", 1.0))
    days = float(rep.get("days_idle", 0.0))
    freshness = rep.get("freshness", "unknown")

    return {
        "version": "1.0.0",
        "name": "Astra",
        "description": "Organic land-backed contribution currency. Derived from reputation. Never gates Open Core.",
        "balance": round(balance, 2),
        "raw_balance": round(raw, 2),
        "decay_factor": decay,
        "days_idle": days,
        "freshness": freshness,
        "unit": "Astra",
        "land_backed": True,
        "spendable": False,
        "sanctuary_tie": "Keysbrook jarrah / black cockatoo sanctuary vision",
        "source_reputation_score": balance,
        "total_successful_analyses": int(rep.get("total_successful_analyses", 0)),
        "last_activity": rep.get("last_activity"),
        "last_computed": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": (
            "balance = effective reputation (includes 30-day half-life decay). "
            "Land-backed in spirit. Spendability off by design at launch. "
            "See ASTRA.md."
        ),
    }


def save_astra(data: dict[str, Any], path: str | Path | None = None) -> Path:
    target = Path(path) if path else ASTRA_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def load_astra(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else ASTRA_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else _defaults()
    except Exception:
        return _defaults()


def write_astra_badge(data: dict[str, Any] | None = None) -> Path:
    d = data if data is not None else load_astra()
    bal = d.get("balance", 0)
    freshness = d.get("freshness", "unknown")
    spendable = "yes" if d.get("spendable") else "no"

    body = f"""# Astra Badge

![Astra](https://img.shields.io/badge/astra-{bal}-gold)

**Balance:** {bal} Astra  
**Freshness:** {freshness}  
**Spendable:** {spendable}  
**Land-backed:** yes (Keysbrook sanctuary vision)

Organic contribution currency. Does not gate Open Core.  
See `ASTRA.md` and `nexus/astra.py`.
"""
    BADGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BADGE_PATH.write_text(body, encoding="utf-8")
    return BADGE_PATH


def refresh_astra(persist: bool = True, reputation: dict[str, Any] | None = None) -> dict[str, Any]:
    """Recompute and optionally persist Astra state + badge."""
    data = compute_astra(reputation)
    if persist:
        save_astra(data)
        write_astra_badge(data)
    return data


def astra_summary_md(data: dict[str, Any] | None = None) -> str:
    d = data if data is not None else load_astra()
    return (
        f"**Astra (organic currency):** **{d.get('balance', 0)}** Astra "
        f"(raw {d.get('raw_balance', 0)}, freshness={d.get('freshness', 'unknown')}, "
        f"spendable={d.get('spendable', False)})\n"
        f"- Land-backed by Keysbrook sanctuary vision\n"
        f"- Derived from reputation with identical decay\n"
        f"- Never gates Open Core. See ASTRA.md."
    )
