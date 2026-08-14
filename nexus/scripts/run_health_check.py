#!/usr/bin/env python3
"""Package + system health check for the Nexus.

No external AI. Exit 1 if structural score < 80 or loader errors.
"""

from __future__ import annotations

import sys
from pathlib import Path

from nexus import __version__
from nexus.audit import structural_health, alignment_signals, progressive_snapshot
from nexus.usage import load_usage_stats
from nexus.reputation import compute_reputation, reputation_summary_md
from nexus.presence import load_presence, format_presence_for_prompt
from nexus.context import load_context, load_progressive
from nexus.field_notes import notes_summary_md


def main() -> int:
    print(f"🩺 Nexus health check — package v{__version__}")
    print("=" * 60)

    errors: list[str] = []
    rep: dict = {}

    try:
        ctx = load_context()
        print(f"✅ context loaded ({len(ctx)} chars)")
    except Exception as e:
        errors.append(f"context: {e}")
        print(f"❌ context: {e}")

    try:
        prog = load_progressive()
        print(f"✅ progressive v{prog.get('version')} phase={str(prog.get('current_phase', ''))[:60]}")
    except Exception as e:
        errors.append(f"progressive: {e}")
        print(f"❌ progressive: {e}")

    try:
        stats = load_usage_stats()
        print(f"✅ usage total={stats.get('total_successful_analyses')} by_type={stats.get('by_type')}")
    except Exception as e:
        errors.append(f"usage: {e}")
        print(f"❌ usage: {e}")

    try:
        rep = compute_reputation()
        print(f"✅ reputation effective={rep.get('score')} raw={rep.get('raw_score')} "
              f"freshness={rep.get('freshness')} days_idle={rep.get('days_idle')}")
        print(reputation_summary_md(rep))
    except Exception as e:
        errors.append(f"reputation: {e}")
        print(f"❌ reputation: {e}")

    try:
        presence = load_presence()
        print(f"✅ presence generated_at={presence.get('generated_at')}")
        print("--- presence block ---")
        print(format_presence_for_prompt(presence)[:500])
        print("----------------------")
    except Exception as e:
        errors.append(f"presence: {e}")
        print(f"❌ presence: {e}")

    try:
        print("Recent field notes:")
        print(notes_summary_md(3))
    except Exception as e:
        print(f"⚠️ field notes: {e}")

    health = structural_health()
    signals = alignment_signals()
    snap = progressive_snapshot()

    print("=" * 60)
    print(f"Structural health: {health['score']}/100 "
          f"({health['present_count']}/{health['required_count']})")
    if health["missing"]:
        print(f"Missing: {health['missing']}")
    print(f"Triad heuristic hits: {signals['total_triad_hits']}")
    print(f"Phase: {snap.get('phase')}")
    print(f"Layer 1: {snap.get('layer1_enabled')}")

    out = Path("/tmp/nexus_health.md")
    body = f"""# 🩺 Nexus Health Check

**Package:** v{__version__}  
**Structural health:** {health['score']}/100  
**Triad hits:** {signals['total_triad_hits']}  
**Phase:** {snap.get('phase')}  
**Analyses:** {snap.get('total_successful_analyses')}  
**Reputation effective:** {rep.get('score', 'n/a')} ({rep.get('freshness', 'n/a')})  
**Presence:** {presence.get('generated_at') if 'presence' in dir() else 'n/a'}  
**Errors:** {errors or 'none'}

Missing structural items: {health['missing'] or 'none'}
"""
    out.write_text(body, encoding="utf-8")
    print(f"\n✅ Report written to {out}")

    if errors:
        print(f"❌ {len(errors)} error(s)")
        return 1
    if health["score"] < 80:
        print("❌ Structural health below 80")
        return 1
    print("✅ Health check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
