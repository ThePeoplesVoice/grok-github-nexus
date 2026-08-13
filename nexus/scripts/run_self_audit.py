#!/usr/bin/env python3
"""Standalone entrypoint for the Nexus self-audit closed loop.

Designed to be called from GitHub Actions with a clean, minimal workflow YAML.
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
from nexus.context import layer1_enabled


def main() -> None:
    now = utc_now_str()
    snap = progressive_snapshot()
    health = structural_health()
    signals = alignment_signals()

    # Recent commits
    log = subprocess.run(
        ["git", "log", "--oneline", "-n", "12"],
        capture_output=True, text=True
    ).stdout.strip()

    # Lightweight tree summary
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
        extra_notes=(
            "Also consider long-horizon possibilities for native organic value systems "
            "(contribution reputation, sanctuary-tied credits, land-backed signal) "
            "and richer communication layers beyond the current x402 design."
        ),
    )

    # Grok primary
    grok_text, grok_err = call_grok(prompt, temperature=0.45, max_tokens=1400)

    # Claude complementary (Layer 1)
    claude_text = None
    claude_err = None
    if layer1_enabled() and os.environ.get("CLAUDE_API_KEY"):
        claude_text, claude_err = call_claude(
            prompt + (
                "\n\nRespond as a complementary high-rigor reviewer. Focus on maintenance debt, "
                "over-expansion risk, and whether the self-audit loop itself is healthy. "
                "Also note any openings for more organic currency or communication systems."
            ),
            max_tokens=1100,
        )

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

    # Precompute to avoid backslash inside f-string expression
    joined = "\n\n---\n\n".join(sections)
    footer = format_audit_footer()

    body = f"""# ⚖️ Nexus Self-Audit — {now}

**Progressive Phase:** {snap.get('phase')}  
**progressive.json version:** {snap.get('version')}  
**Layer 1:** {"enabled" if snap.get('layer1_enabled') else "disabled"}  
**Successful analyses recorded:** {snap.get('total_successful_analyses', 0)}  
**Structural health (heuristic):** {health['score']}/100  
**Triad keyword hits (heuristic):** {signals['total_triad_hits']}{fusion}

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
