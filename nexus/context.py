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


def load_domain_packs(
    pack_ids: list[str] | None = None,
    domain_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Load one or more domain pack JSON files from config/domain_packs/.

    Args:
        pack_ids: List of pack IDs to load (e.g. ``["wa_construction"]``).
                  If None, all ``*.json`` files in the directory are loaded.
        domain_dir: Override the default ``config/domain_packs/`` directory.

    Returns:
        Dict keyed by pack ID. Missing or malformed packs are silently skipped.
    """
    base = Path(domain_dir) if domain_dir else ROOT / "config" / "domain_packs"
    result: dict[str, Any] = {}
    if not base.is_dir():
        return result
    if pack_ids is not None:
        paths = [base / f"{pid}.json" for pid in pack_ids]
    else:
        paths = sorted(base.glob("*.json"))
    for p in paths:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                pid = str(data.get("id") or p.stem)
                result[pid] = data
        except Exception:
            pass
    return result


def domain_pack_summary(packs: dict[str, Any]) -> str:
    """Return a compact, prompt-ready text summary of loaded domain packs."""
    if not packs:
        return ""
    lines = ["## Domain Context"]
    for pid, pack in packs.items():
        name = pack.get("name", pid)
        desc = pack.get("description", "")
        voice = pack.get("voice", "")
        hints = pack.get("analysis_hints", [])
        lines.append(f"\n### {name}")
        if desc:
            lines.append(desc)
        if voice:
            lines.append(f"_Voice: {voice}_")
        if hints:
            lines.append("**Analysis hints:**")
            lines.extend(f"- {h}" for h in hints[:5])
    return "\n".join(lines)
