"""Load Nexus shared context, progressive control plane, and usage stats."""

from __future__ import annotations

import json
import os
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


def successful_analysis_gate_status(
    prog: dict[str, Any] | None = None,
    stats: dict[str, Any] | None = None,
) -> dict[str, int | bool]:
    """Return the measured Layer 1 analysis gate state.

    Only uses repository-local counters that are already persisted in config/usage_stats.json.
    This makes the progressive gate real for multi-model fusion without depending on
    unavailable external metrics at runtime.
    """
    state = prog if prog is not None else load_progressive()
    counters = stats if stats is not None else load_usage_stats()
    triggers = (
        state.get("layers", {})
        .get("1_progressive_unlocks", {})
        .get("triggers", {})
    )
    required = int(triggers.get("min_successful_analyses", 0) or 0)
    current = int(counters.get("total_successful_analyses", 0) or 0)
    return {
        "current": current,
        "required": required,
        "remaining": max(required - current, 0),
        "met": current >= required,
    }


def layer1_enabled(prog: dict[str, Any] | None = None) -> bool:
    """Convenience: is Layer 1 progressive unlocks enabled?"""
    state = prog if prog is not None else load_progressive()
    return bool(
        state.get("layers", {})
        .get("1_progressive_unlocks", {})
        .get("enabled", True)
    )


def layer1_feature_enabled(
    feature: str,
    prog: dict[str, Any] | None = None,
    stats: dict[str, Any] | None = None,
) -> bool:
    """Return whether a Layer 1 feature is active at runtime.

    Today the only feature with a measured runtime gate is multi-model fusion.
    Other Layer 1 features continue to follow the control-plane enabled flag.
    """
    state = prog if prog is not None else load_progressive()
    if not layer1_enabled(state):
        return False
    feature_name = (feature or "").strip().lower()
    if feature_name == "multi_model_fusion":
        if str(os.environ.get("NEXUS_FORCE_MULTI_MODEL_FUSION", "")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            return True
        return bool(successful_analysis_gate_status(state, stats).get("met"))
    return True


def current_phase(prog: dict[str, Any] | None = None) -> str:
    state = prog if prog is not None else load_progressive()
    return str(state.get("current_phase", "Layer 0 — Open Core"))
