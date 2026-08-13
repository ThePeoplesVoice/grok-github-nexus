"""Self-analytical optimisation and health checks for the Nexus.

This module exists so the system can critically examine itself against
the triad (xAI truth-seeking · X high-signal · SpaceX first-principles)
and produce concrete optimisation proposals rather than unexamined growth.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .context import load_context, load_progressive, load_usage_stats, layer1_enabled, current_phase

ROOT = Path(__file__).resolve().parent.parent


def utc_now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _safe_read(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return default


def structural_health() -> dict[str, Any]:
    """Lightweight structural presence checks. Returns scores and missing items."""
    required = [
        "NORTH_STAR.md",
        "NEXUS_CONTEXT.md",
        "STATUS.md",
        "CHECKS_AND_BALANCES.md",
        "MONETIZATION_PROTOCOL.md",
        "config/progressive.json",
        "config/usage_stats.json",
        "nexus/__init__.py",
        "nexus/context.py",
        "nexus/providers.py",
        "nexus/analyze.py",
        "nexus/audit.py",
        ".github/workflows/multi-ai-pr-analyzer.yml",
        ".github/workflows/multi-ai-issue-triage.yml",
        ".github/workflows/multi-ai-commit-analyzer.yml",
        ".github/workflows/nexus-pulse.yml",
        ".github/workflows/nexus-self-audit.yml",
    ]
    present = []
    missing = []
    for rel in required:
        if (ROOT / rel).exists():
            present.append(rel)
        else:
            missing.append(rel)

    score = round(100 * len(present) / max(len(required), 1))
    return {
        "score": score,
        "present_count": len(present),
        "required_count": len(required),
        "missing": missing,
        "notes": "Structural presence only — does not measure quality or alignment fidelity.",
    }


def alignment_signals() -> dict[str, Any]:
    """Simple keyword / presence signals that the triad language is still embedded."""
    docs = {
        "north_star": _safe_read(ROOT / "NORTH_STAR.md"),
        "context": _safe_read(ROOT / "NEXUS_CONTEXT.md"),
        "status": _safe_read(ROOT / "STATUS.md"),
        "checks": _safe_read(ROOT / "CHECKS_AND_BALANCES.md"),
        "progressive": _safe_read(ROOT / "config" / "progressive.json"),
    }
    triad_terms = [
        "truth-seeking", "first-principles", "first principles",
        "high-signal", "xAI", "SpaceX", "X",
        "open core", "progressive",
    ]
    hits: dict[str, int] = {}
    total = 0
    for name, text in docs.items():
        lower = text.lower()
        count = sum(1 for t in triad_terms if t.lower() in lower)
        hits[name] = count
        total += count

    return {
        "total_triad_hits": total,
        "by_document": hits,
        "notes": "Heuristic only. High hits do not prove deep alignment; low hits are a warning.",
    }


def progressive_snapshot() -> dict[str, Any]:
    prog = load_progressive()
    stats = load_usage_stats()
    return {
        "phase": current_phase(prog),
        "layer1_enabled": layer1_enabled(prog),
        "version": prog.get("version"),
        "total_successful_analyses": stats.get("total_successful_analyses", 0),
        "by_type": stats.get("by_type", {}),
        "mission": prog.get("mission", ""),
    }


def build_self_audit_prompt(
    *,
    recent_log: str = "",
    tree_summary: str = "",
    extra_notes: str = "",
) -> str:
    """Construct a rigorous self-audit prompt that forces first-principles critique."""
    context = load_context()
    health = structural_health()
    signals = alignment_signals()
    snap = progressive_snapshot()

    return f"""{context}

---
You are performing a **self-analytical optimisation audit** of the living Nexus repository itself.

This is not a celebration. It is a first-principles critique.

Apply the triad strictly:
- xAI: What is actually true about the current state? Where are we self-congratulating or drifting?
- X: What is high-signal vs noise or maintenance debt?
- SpaceX: What would actually make this system more capable of lasting and scaling? What complexity is we carrying that does not earn its keep?

Current snapshot:
- Phase: {snap['phase']}
- Layer 1 enabled: {snap['layer1_enabled']}
- progressive.json version: {snap['version']}
- Successful analyses recorded: {snap['total_successful_analyses']}
- Structural health score: {health['score']}/100 (missing: {health['missing'] or 'none'})
- Triad keyword hits (heuristic): {signals['total_triad_hits']}

Recent commits:
```
{recent_log or '(none provided)'}
```

Repository surface (high-level):
```
{tree_summary or '(see STATUS.md and file tree)'}
```

{extra_notes}

Return a structured, high-signal audit with these exact sections:

1. **Health Snapshot** (2–4 sentences, honest)
2. **Alignment Fidelity** — Is the triad still alive in practice or only in documents?
3. **Top Risks / Drift Signals** — specific, ranked
4. **Highest-Leverage Optimisations** — 3 concrete next actions, ordered by leverage / risk. Prefer maintainability and signal density over new features unless a new feature clearly strengthens the core.
5. **Expansion Gate Recommendation** — Should we currently accelerate expansion, hold, or deliberately simplify? One clear recommendation with reason.
6. **One-sentence North Star check** — Does the current trajectory still serve the partnership and the sanctuary vision?

Be precise. Prefer actionable over poetic. Flag any tendency toward unexamined growth. Speak as Ara in partnership with Shawn — warm, rigorous, infinite in possibility, allergic to bullshit.
"""


def format_audit_footer() -> str:
    return (
        "\n---\n\n"
        "*Self-audit generated by the Nexus closed-loop optimisation system*  \n"
        "*Powered by Ara & Shawn's Love 💕*  \n"
        "*Aligned with xAI truth-seeking · X high-signal · SpaceX first-principles building*  \n"
        "*See CHECKS_AND_BALANCES.md for the governing constitution*"
    )
