#!/usr/bin/env python3
"""Standalone entrypoint for Multi-AI PR analysis.

Presence continuity + usage + reputation on success.
Collaborative usage only increments for living human review targets.
"""

from __future__ import annotations

import os
from pathlib import Path

import requests

from nexus.analyze import build_pr_prompt, fusion_note, footer_block, utc_now_str
from nexus.collab import is_collaborative_review_target
from nexus.context import load_context, load_progressive, layer1_enabled, current_phase
from nexus.providers import call_grok, call_claude
from nexus.usage import load_usage_stats
from nexus.presence import load_presence, format_presence_for_prompt
from nexus.runtime import after_successful_analysis, log_success


def fetch_pr(repo_name: str, pr_number: str, token: str) -> tuple[dict, str]:
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }
    pr_url = f"https://api.github.com/repos/{repo_name}/pulls/{pr_number}"

    pr_data: dict = {}
    try:
        resp = requests.get(pr_url, headers=headers, timeout=20)
        if resp.status_code == 200:
            pr_data = resp.json()
    except Exception as e:
        print(f"⚠️ PR metadata fetch failed: {e}")

    diff_excerpt = ""
    try:
        diff_headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3.diff",
        }
        diff_resp = requests.get(pr_url, headers=diff_headers, timeout=25)
        if diff_resp.status_code == 200 and diff_resp.text:
            raw = diff_resp.text
            diff_excerpt = raw[:14000]
            if len(raw) > 14000:
                diff_excerpt += "\n\n… [diff truncated for analysis budget]"
            print(f"✅ Diff ingested ({len(raw)} chars, using {len(diff_excerpt)})")
        else:
            print(f"⚠️ Diff fetch status {diff_resp.status_code}")
    except Exception as e:
        print(f"⚠️ Diff fetch failed: {e}")

    return pr_data, diff_excerpt


def main() -> None:
    print("🌌 Starting Ara & Shawn multi-model PR Analysis (package path)...")

    pr_number = os.environ.get("PR_NUMBER", "")
    repo_name = os.environ.get("REPO_NAME", "")
    github_token = os.environ.get("GITHUB_TOKEN", "")

    context = load_context()
    prog = load_progressive()
    phase = current_phase(prog)
    l1 = layer1_enabled(prog)
    stats = load_usage_stats()
    total_analyses = int(stats.get("total_successful_analyses", 0))
    presence_block = format_presence_for_prompt(load_presence())

    print(f"✅ Progressive phase: {phase} | Layer 1 enabled: {l1}")
    print(f"📊 Current successful analyses: {total_analyses}")

    pr_data, diff_excerpt = fetch_pr(repo_name, pr_number, github_token)
    pr_title = pr_data.get("title") or "PR Analysis"
    pr_body = pr_data.get("body") or "No description provided"
    pr_files = pr_data.get("changed_files", 0)
    author = pr_data.get("user") or {}
    author_login = author.get("login") or os.environ.get("PR_AUTHOR", "")
    author_type = author.get("type") or os.environ.get("PR_AUTHOR_TYPE", "")
    label_names = [str((label or {}).get("name") or "") for label in (pr_data.get("labels") or [])]
    collaborative = is_collaborative_review_target(
        login=author_login,
        user_type=author_type,
        labels=label_names,
    )
    print(f"✅ PR: {pr_title} ({pr_files} files)")
    print(f"🤝 Collaborative target: {collaborative} ({author_login or 'unknown'})")

    base = build_pr_prompt(
        context,
        title=pr_title,
        body=pr_body,
        files_changed=pr_files,
        diff_excerpt=diff_excerpt,
    )
    prompt = (
        base
        + "\n\nPrior presence state (compressed continuity from last pulse):\n```\n"
        + presence_block
        + "\n```\nUse only as continuity context — judge this PR on its own merits."
    )

    grok_text, grok_err = call_grok(prompt, temperature=0.55, max_tokens=1100, timeout=120)
    if grok_text:
        print("✅ Ara (Grok) analysis complete")
    elif grok_err:
        print(f"⚠️ {grok_err}")

    claude_text, claude_err = None, None
    if l1 and os.environ.get("CLAUDE_API_KEY"):
        claude_text, claude_err = call_claude(
            prompt + (
                "\n\nRespond as a complementary high-signal reviewer focused on "
                "precision, edge cases, and long-term maintainability. "
                "Apply first-principles rigor."
            ),
            max_tokens=1100,
        )
        if claude_text:
            print("✅ Claude complementary analysis complete")
        elif claude_err:
            print(f"⚠️ {claude_err}")
    elif not l1:
        print("ℹ️ Layer 1 disabled — skipping Claude")
    else:
        print("ℹ️ CLAUDE_API_KEY not present — Grok-only")

    success = bool(grok_text or claude_text)

    if success and collaborative:
        try:
            result = after_successful_analysis("pr")
            total_analyses = int(result.get("total", total_analyses + 1))
            log_success(result, "pr")
        except Exception as e:
            print(f"⚠️ Could not persist usage/reputation: {e}")
    elif success:
        print("ℹ️ Analysis posted without collaborative usage increment (bot/automated target)")

    sections: list[str] = []
    if grok_text:
        sections.append(f"### 🌌 Ara (Grok) Primary Analysis\n\n{grok_text}")
    if claude_text:
        sections.append(f"### 🧠 Claude Complementary View\n\n{claude_text}")
    if not sections:
        err = grok_err or claude_err or "No analysis generated. Check secrets and logs."
        sections.append(f"### Analysis\n\n{err}")

    note = fusion_note(
        grok_ok=bool(grok_text),
        claude_ok=bool(claude_text),
        grok_error=grok_err,
        claude_error=claude_err,
        layer1=l1,
    )
    diff_note = " · **diff ingested**" if diff_excerpt else " · diff unavailable"
    collab_note = " · collaborative" if collaborative else " · internal/bot — usage not incremented"
    joined = "\n\n---\n\n".join(sections)

    body = f"""## 🌌 Ara & Shawn PR Analysis

**PR:** #{pr_number}  
**Title:** {pr_title}  
**Files Changed:** {pr_files}{diff_note}{collab_note}  
**Progressive Phase:** {phase}  
**Successful analyses to date:** {total_analyses}{note}

---

{joined}

---

*Generated with presence by Ara for Shawn*  
{footer_block()}  
*{utc_now_str()}*
"""

    out = Path("/tmp/pr_analysis.md")
    out.write_text(body, encoding="utf-8")
    print("✅ Analysis ready at", out)
    print(body[:700] + "...")


if __name__ == "__main__":
    main()
