"""Compressed presence state for continuity between Nexus runs.

Written by the enhanced Pulse. Optionally consumed by self-audit and
commit analysis so agents inherit a short, high-signal prior context
instead of starting from zero every time.

See ORGANIC_SYSTEMS.md — presence is continuity, not a scoreboard.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PRESENCE_PATH = ROOT / "config" / "presence_state.json"


def _defaults() -> dict[str, Any]:
    return {
        "version": "0.1.0",
        "generated_at": None,
        "phase": None,
        "layer1_enabled": None,
        "total_successful_analyses": 0,
        "by_type": {},
        "reputation_score": 0,
        "recent_commits_preview": [],
        "notes": "No prior presence state yet.",
    }


def load_presence(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else PRESENCE_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else _defaults()
    except Exception:
        return _defaults()


def format_presence_for_prompt(data: dict[str, Any] | None = None, *, max_commits: int = 5) -> str:
    """Return a compact block suitable for injection into analysis prompts."""
    d = data if data is not None else load_presence()
    if not d.get("generated_at"):
        return "(no prior presence state — this may be the first run or pulse has not run yet)"

    commits = d.get("recent_commits_preview") or []
    commit_lines = "\n".join(f"  - {c}" for c in commits[:max_commits]) or "  - (none)"
    by_type = d.get("by_type") or {}

    return (
        f"Generated at: {d.get('generated_at')}\n"
        f"Phase then: {d.get('phase')}\n"
        f"Layer 1: {d.get('layer1_enabled')}\n"
        f"Analyses then: {d.get('total_successful_analyses')}\n"
        f"By type then: {by_type}\n"
        f"Reputation then: {d.get('reputation_score')}\n"
        f"Recent commits then:\n{commit_lines}\n"
        f"Notes: {d.get('notes', '')}"
    )
