#!/usr/bin/env python3
"""Standalone entrypoint for Multi-AI Commit Analysis.

Local fallback preserved. Presence continuity + shared runtime on success.
"""

from __future__ import annotations

import subprocess
import re
from pathlib import Path
from typing import Any

from nexus.analyze import build_commit_prompt, fusion_note, footer_block, utc_now_str
from nexus.context import load_context, load_progressive, layer1_enabled, current_phase
from nexus.providers import call_grok, call_claude
from nexus.usage import load_usage_stats
from nexus.presence import load_presence, format_presence_for_prompt
from nexus.runtime import after_successful_analysis, log_success


def commit_subject(oneline: str) -> str:
    parts = oneline.split(maxsplit=1)
    if len(parts) == 2 and re.fullmatch(r"[0-9a-f]{7,40}", parts[0]):
        return parts[1]
    return oneline.strip()


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
        subject = commit_subject(c["oneline"])
        detail = c["details"]
        stat_lines = [l for l in detail.splitlines() if "|" in l or "changed" in l]
        summary_line = next((l for l in stat_lines if "changed" in l), "")
        files_touched = [l.split("|")[0].strip() for l in stat_lines if "|" in l]
        lines.append(f"#### `{sha[:7]}` — {subject}")
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
            result = after_successful_analysis("commit")
            total_analyses = int(result.get("total", total_analyses + 1))
            log_success(result, "commit")
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
        f"- `{c['sha'][:7]}` {commit_subject(c['oneline'])}" for c in commit_details
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
