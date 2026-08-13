#!/usr/bin/env python3
"""Standalone entrypoint for Multi-AI Commit Analysis.

Preserves local git fallback when providers are unavailable.
Increments usage only on successful AI analysis (not pure local fallback).
Inherits compressed presence_state for continuity.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from nexus.analyze import build_commit_prompt, fusion_note, footer_block, utc_now_str
from nexus.context import load_context, load_progressive, layer1_enabled, current_phase
from nexus.providers import call_grok, call_claude
from nexus.usage import record_successful_analysis, load_usage_stats
from nexus.reputation import refresh_reputation
from nexus.presence import load_presence, format_presence_for_prompt


def gather_commits(n: int = 5) -> list[dict[str, Any]]:
    result = subprocess.run(
        ["git", "log", "--oneline", "-n", str(n)],
        capture_output=True, text=True,
    )
    lines = [l for l in result.stdout.strip().splitlines() if l.strip()]
    details: list[dict[str, Any]] = []
    for line in lines:
        sha = line.split()[0]
        show = subprocess.run(
            ["git", "show", "--stat", "--pretty=fuller", sha],
            capture_output=True, text=True,
        )
        details.append({
            "sha": sha,
            "oneline": line,
            "details": show.stdout[:1800],
        })
    return details


def local_analysis(commits: list[dict[str, Any]]) -> str:
    lines = [
        "*AI providers were unavailable — local git analysis generated automatically.*",
        "",
        f"**{len(commits)} commit(s) examined.**",
        "",
    ]
    for c in commits:
        sha = c["sha"]
        oneline = c["oneline"]
        detail = c["details"]
        stat_lines = [l for l in detail.splitlines() if "|" in l or "changed" in l]
        summary_line = next((l for l in stat_lines if "changed" in l), "")
        files_touched = [l.split("|")[0].strip() for l in stat_lines if "|" in l]
        lines.append(f"#### `{sha[:7]}` — {' '.join(oneline.split()[1:])}")
        if summary_line:
            lines.append(f"- **Stats:** {summary_line.strip()}")
        if files_touched:
            shown = ", ".join(files_touched[:6])
            if len(files_touched) > 6:
                shown += " …"
            lines.append(f"- **Files:** {shown}")
        lines.append("")
    lines.append("---")
    lines.append("*Tip: Add `GROK_API_KEY` (and optionally `CLAUDE_API_KEY`) to enable AI-powered analysis.*")
    return "\n".join(lines)


def main() -> None:
    print("🌌 Starting Ara & Shawn multi-model Commit Analysis (package path)...")

    context = load_context()
    prog = load_progressive()
    phase = current_phase(prog)
    l1 = layer1_enabled(prog)
    stats = load_usage_stats()
    total_analyses = int(stats.get("total_successful_analyses", 0))
    presence_block = format_presence_for_prompt(load_presence())

    print(f"✅ Progressive phase: {phase} | Layer 1 enabled: {l1}")
    print(f"📊 Current successful analyses: {total_analyses}")

    commit_details = gather_commits(5)
    print(f"📊 {len(commit_details)} commits prepared")

    grok_text, grok_err = None, None
    claude_text, claude_err = None, None

    if commit_details:
        base = build_commit_prompt(context, commit_details)
        prompt = (
            base
            + "\n\nPrior presence state (compressed continuity from last pulse):\n```\n"
            + presence_block
            + "\n```\nUse this only as continuity context — judge the new commits on their own merits."
        )

        grok_text, grok_err = call_grok(prompt, temperature=0.55, max_tokens=1000)
        if grok_text:
            print("✅ Ara (Grok) commit analysis complete")
        elif grok_err:
            print(f"⚠️ {grok_err}")

        if l1:
            claude_text, claude_err = call_claude(
                prompt + (
                    "\n\nRespond as a complementary reviewer focused on systems thinking, "
                    "maintainability, and long-horizon impact. Apply first-principles rigor."
                ),
                max_tokens=1000,
            )
            if claude_text:
                print("✅ Claude complementary analysis complete")
            elif claude_err:
                print(f"⚠️ {claude_err}")
        else:
            print("ℹ️ Layer 1 disabled — skipping Claude")

    success = bool(grok_text or claude_text)

    if success:
        try:
            new_stats = record_successful_analysis("commit", persist=True)
            total_analyses = int(new_stats.get("total_successful_analyses", total_analyses + 1))
            print(
                f"📊 Usage incremented → total={total_analyses} "
                f"commit={new_stats.get('by_type', {}).get('commit')}"
            )
            rep = refresh_reputation(persist=True)
            print(f"🌱 Reputation refreshed → effective={rep.get('score')} "
                  f"raw={rep.get('raw_score')} freshness={rep.get('freshness')}")
        except Exception as e:
            print(f"⚠️ Could not persist usage/reputation: {e}")

    sections: list[str] = []
    if grok_text:
        sections.append(f"### 🌌 Ara (Grok) Primary\n\n{grok_text}")
    if claude_text:
        sections.append(f"### 🧠 Claude Complementary\n\n{claude_text}")
    if not sections:
        sections.append(f"### 🔍 Local Git Analysis (Fallback)\n\n{local_analysis(commit_details)}")

    note = fusion_note(
        grok_ok=bool(grok_text),
        claude_ok=bool(claude_text),
        grok_error=grok_err,
        claude_error=claude_err,
        layer1=l1,
    )

    commit_list = "\n".join(
        f"- `{c['sha'][:7]}` {c['oneline']}" for c in commit_details
    ) or "- (none)"

    joined = "\n\n---\n\n".join(sections)

    body = f"""# 🌌 Ara & Shawn Commit Analysis

**Generated:** {utc_now_str()}{note}
**Progressive Phase:** {phase}
**Successful analyses to date:** {total_analyses}

## Recent commits examined
{commit_list}

---

{joined}

---

{footer_block()}
"""

    out = Path("/tmp/commit_analysis.md")
    out.write_text(body, encoding="utf-8")
    print("✅ Report ready at", out)
    print(body[:600])


if __name__ == "__main__":
    main()
