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
    """Return usage_stats.json as a dict with safe defaults."""
    target = Path(path) if path else ROOT / "config" / "usage_stats.json"
    defaults: dict[str, Any] = {
        "total_successful_analyses": 0,
        "by_type": {"commit": 0, "pr": 0, "issue": 0},
        "last_updated": None,
    }
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else defaults
    except Exception:
        return defaults


def layer1_enabled(prog: dict[str, Any] | None = None) -> bool:
    """Convenience: is Layer 1 progressive unlocks enabled?"""
    state = prog if prog is not None else load_progressive()
    return bool(
        state.get("layers", {})
        .get("1_progressive_unlocks", {})
        .get("enabled", True)
    )


def current_phase(prog: dict[str, Any] | None = None) -> str:
    state = prog if prog is not None else load_progressive()
    return str(state.get("current_phase", "Layer 0 — Open Core"))
