#!/usr/bin/env python3
"""Standalone entrypoint for the Nexus self-audit closed loop.

Presence continuity + shared runtime on success.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from nexus.audit import (
    structural_health,
    alignment_signals,
    progressive_snapshot,
    build_self_audit_prompt,
    format_audit_footer,
    utc_now_str,
)
from nexus.providers import call_grok, call_claude
from nexus.context import (
    load_progressive,
    load_usage_stats,
    successful_analysis_gate_status,
    layer1_enabled,
    layer1_feature_enabled,
)
from nexus.presence import load_presence, format_presence_for_prompt
from nexus.runtime import after_successful_analysis, log_success


def main() -> None:
    now = utc_now_str()
    snap = progressive_snapshot()
    health = structural_health()
    signals = alignment_signals()
    presence = load_presence()
    presence_block = format_presence_for_prompt(presence)
    prog = load_progressive()
    stats = load_usage_stats()
    gate = successful_analysis_gate_status(prog, stats)
    l1_config = layer1_enabled(prog)
    l1 = layer1_feature_enabled("multi_model_fusion", prog, stats)

    log = subprocess.run(
        ["git", "log", "--oneline", "-n", "12"],
        capture_output=True, text=True
    ).stdout.strip()

    tree = subprocess.run(
        ["find", ".", "-type", "f", "-not", "-path", "./.git/*", "-not", "-name", "*.pyc"],
        capture_output=True, text=True
    ).stdout.strip()
    tree_lines = sorted(tree.splitlines())[:50]
    tree_summary = "\n".join(tree_lines)
    if len(tree.splitlines()) > 50:
        tree_summary += "\n… (truncated)"

    prompt = build_self_audit_prompt(
        recent_log=log,
        tree_summary=tree_summary,
        presence_block=presence_block,
        extra_notes=(
            "Also consider long-horizon possibilities for native organic value systems "
            "(contribution reputation with decay, sanctuary-tied credits, land-backed signal) "
            "and richer communication layers beyond the current x402 design. "
            "Use the prior presence state to notice continuity or drift since the last pulse."
        ),
    )

    grok_text, grok_err = call_grok(prompt, temperature=0.45, max_tokens=1400)

    claude_text = None
    claude_err = None
    if l1 and os.environ.get("CLAUDE_API_KEY"):
        claude_text, claude_err = call_claude(
            prompt + (
                "\n\nRespond as a complementary high-rigor reviewer. Focus on maintenance debt, "
                "over-expansion risk, and whether the self-audit loop itself is healthy. "
                "Also note any openings for more organic currency or communication systems."
            ),
            max_tokens=1100,
        )

    success = bool(grok_text or claude_text)

    if success:
        try:
            result = after_successful_analysis("self_audit")
            log_success(result, "self_audit")
        except Exception as e:
            print(f"⚠️ Could not persist usage/reputation: {e}")

    sections = []
    if grok_text:
        sections.append(f"### 🌌 Ara (Grok) Self-Audit\n\n{grok_text}")
    if claude_text:
        sections.append(f"### 🧠 Claude Complementary Critique\n\n{claude_text}")
    if not sections:
        err_msg = grok_err or "No analysis generated. Check GROK_API_KEY and workflow logs."
        sections.append(f"### Audit\n\n{err_msg}")

    fusion = ""
    if grok_text and claude_text:
        fusion = "\n\n**Multi-model self-audit active (Layer 1)**"
    elif grok_text and claude_err:
        fusion = "\n\n*Claude complementary unavailable — Ara primary only.*"
    elif l1_config and not l1 and gate["required"] > 0:
        fusion = (
            "\n\n*Multi-model fusion remains locked until successful analyses reach "
            f"{gate['required']} (current {gate['current']}) — Ara primary only.*"
        )

    joined = "\n\n---\n\n".join(sections)
    footer = format_audit_footer()

    if success:
        snap = progressive_snapshot()

    body = f"""# ⚖️ Nexus Self-Audit — {now}

**Progressive Phase:** {snap.get('phase')}  
**progressive.json version:** {snap.get('version')}  
**Layer 1:** {"enabled" if snap.get('layer1_enabled') else "disabled"}  
**Successful analyses recorded:** {snap.get('total_successful_analyses', 0)}  
**Structural health (heuristic):** {health['score']}/100  
**Triad keyword hits (heuristic):** {signals['total_triad_hits']}  
**Prior presence:** {presence.get('generated_at') or 'none'}{fusion}

---

{joined}

{footer}
"""

    out = Path("/tmp/nexus_self_audit.md")
    out.write_text(body, encoding="utf-8")
    print(body[:1200])
    print("\n✅ Self-audit body ready at", out)


if __name__ == "__main__":
    main()
