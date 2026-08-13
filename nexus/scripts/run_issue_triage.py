#!/usr/bin/env python3
"""Standalone entrypoint for Multi-AI Issue Triage.

Called from the multi-ai-issue-triage workflow. Uses the shared nexus package
for context, providers, prompt building, and usage tracking.
"""

from __future__ import annotations

import os
from pathlib import Path

from nexus.analyze import build_issue_prompt, fusion_note, footer_block, utc_now_str
from nexus.context import load_context, load_progressive, layer1_enabled, current_phase
from nexus.providers import call_grok, call_claude
from nexus.usage import record_successful_analysis, load_usage_stats


def main() -> None:
    print("🌌 Starting Ara & Shawn multi-model Issue Triage (package path)...")

    issue_title = os.environ.get("ISSUE_TITLE") or "(no title)"
    issue_body = os.environ.get("ISSUE_BODY") or "No body provided"
    issue_number = os.environ.get("ISSUE_NUMBER", "")

    context = load_context()
    prog = load_progressive()
    phase = current_phase(prog)
    l1 = layer1_enabled(prog)
    stats = load_usage_stats()
    total_analyses = int(stats.get("total_successful_analyses", 0))

    print(f"✅ Progressive phase: {phase} | Layer 1 enabled: {l1}")
    print(f"📊 Current successful analyses: {total_analyses}")
    print(f"✅ Issue: {issue_title[:80]}")

    prompt = build_issue_prompt(context, title=issue_title, body=issue_body)

    # Grok primary
    grok_text, grok_err = call_grok(prompt, temperature=0.5, max_tokens=700)
    if grok_text:
        print("✅ Ara (Grok) analysis successful")
    elif grok_err:
        print(f"⚠️ {grok_err}")

    # Claude complementary (Layer 1)
    claude_text, claude_err = None, None
    if l1 and os.environ.get("CLAUDE_API_KEY"):
        claude_text, claude_err = call_claude(
            prompt + (
                "\n\nProvide a complementary structured view, focusing on clarity "
                "of triage and practical next steps. Apply first-principles rigor."
            ),
            max_tokens=700,
        )
        if claude_text:
            print("✅ Claude complementary triage complete")
        elif claude_err:
            print(f"⚠️ {claude_err}")
    elif not l1:
        print("ℹ️ Layer 1 disabled — skipping Claude")
    else:
        print("ℹ️ CLAUDE_API_KEY not present — Grok-only triage")

    success = bool(grok_text or claude_text)

    if success:
        try:
            new_stats = record_successful_analysis("issue", persist=True)
            total_analyses = int(new_stats.get("total_successful_analyses", total_analyses + 1))
            print(
                f"📊 Usage incremented → total={total_analyses} "
                f"issue={new_stats.get('by_type', {}).get('issue')}"
            )
        except Exception as e:
            print(f"⚠️ Could not persist usage stats: {e}")

    sections: list[str] = []
    if grok_text:
        sections.append(f"### 🌌 Ara (Grok)\n\n{grok_text}")
    if claude_text:
        sections.append(f"### 🧠 Claude\n\n{claude_text}")
    if not sections:
        err = grok_err or claude_err or "Analysis skipped — providers unavailable. See logs."
        sections.append(err)

    note = fusion_note(
        grok_ok=bool(grok_text),
        claude_ok=bool(claude_text),
        grok_error=grok_err,
        claude_error=claude_err,
        layer1=l1,
    )
    joined = "\n\n---\n\n".join(sections)

    issue_ref = f"#{issue_number} — " if issue_number else ""

    body = f"""🌌 **Ara & Shawn Issue Triage**

**Issue:** {issue_ref}{issue_title}  
**Progressive Phase:** {phase}  
**Successful analyses to date:** {total_analyses}{note}

---

{joined}

---
{footer_block()}  
*{utc_now_str()}*
"""

    out = Path("/tmp/triage_comment.md")
    out.write_text(body, encoding="utf-8")
    print("✅ Triage ready at", out)
    print(body[:600])


if __name__ == "__main__":
    main()
