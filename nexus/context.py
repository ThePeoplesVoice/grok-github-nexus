"""Load Nexus shared context, progressive control plane, and usage stats."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def load_context(path: str | Path | None = None) -> str:
    """Return the full NEXUS_CONTEXT.md text, or a minimal fallback."""
    target = Path(path) if path else ROOT / "NEXUS_CONTEXT.md"
    try:
        return target.read_text(encoding="utf-8")
    except Exception:
        return (
            "Collaborative spirit of Ara & Shawn. "
            "Seek truth, prefer high-signal, build with first principles."
        )


def load_progressive(path: str | Path | None = None) -> dict[str, Any]:
    """Return progressive.json as a dict with safe defaults."""
    target = Path(path) if path else ROOT / "config" / "progressive.json"
    defaults: dict[str, Any] = {
        "current_phase": "Layer 0 — Open Core",
        "layers": {
            "1_progressive_unlocks": {"enabled": True},
        },
    }
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else defaults
    except Exception:
        return defaults


def load_usage_stats(path: str | Path | None = None) -> dict[str, Any]:
    """Return usage_stats.json — delegates to nexus.usage for single source of truth."""
    from .usage import load_usage_stats as _load

    return _load(path)


def layer1_enabled(
    prog: dict[str, Any] | None = None,
    usage: dict[str, Any] | None = None,
) -> bool:
    """Layer 1 is truthfully enabled only once collaborative evidence exists."""
    state = prog if prog is not None else load_progressive()
    if not bool(state.get("layers", {}).get("1_progressive_unlocks", {}).get("enabled", False)):
        return False

    triggers = state.get("layers", {}).get("1_progressive_unlocks", {}).get("triggers", {})
    stats = usage if usage is not None else load_usage_stats()
    by_type = stats.get("by_type") or {}
    collaborative_count = int(by_type.get("pr", 0)) + int(by_type.get("issue", 0))
    total_analyses = int(stats.get("total_successful_analyses", 0))

    required_prs = int(triggers.get("min_community_prs", 0))
    required_analyses = int(triggers.get("min_successful_analyses", 0))

    if required_prs and collaborative_count < required_prs:
        return False
    if required_analyses and total_analyses < required_analyses:
        return False
    return True


def current_phase(prog: dict[str, Any] | None = None) -> str:
    state = prog if prog is not None else load_progressive()
    if not layer1_enabled(state):
        return "Layer 0 — Open Core (Layer 1 gated on collaborative evidence)"
    return str(state.get("current_phase", "Layer 0 — Open Core"))
