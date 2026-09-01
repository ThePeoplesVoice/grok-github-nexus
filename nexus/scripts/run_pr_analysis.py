#!/usr/bin/env python3
"""Standalone entrypoint for Multi-AI PR analysis."""

from __future__ import annotations

import os
from pathlib import Path

import requests

from nexus.analyze import build_pr_prompt, fusion_note, footer_block, utc_now_str
from nexus.collab import is_collaborative_review_target, parse_label_list
from nexus.context import load_context, load_progressive, layer1_enabled, current_phase
from nexus.gates import gate_summary, requires_human_gate
from nexus.memory import memory_block_for_prompt, record_memory
from nexus.providers import call_grok, call_claude, classify_grok_result, refine_parse_outcome
from nexus.usage import load_usage_stats
from nexus.presence import load_presence, format_presence_for_prompt
from nexus.runtime import after_successful_analysis, log_success


def fetch_pr(repo_name: str, pr_number: str, token: str) -> tuple[dict, str, list[str]]:
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

    files: list[str] = []
    try:
        files_url = f"https://api.github.com/repos/{repo_name}/pulls/{pr_number}/files?per_page=100"
        fresp = requests.get(files_url, headers=headers, timeout=20)
        if fresp.status_code == 200:
            files = [str(f.get("filename") or "") for f in (fresp.json() or [])]
    except Exception as e:
        print(f"⚠️ PR files fetch failed: {e}")

    return pr_data, diff_excerpt, files


def main() -> None:
    print("🌌 Starting Ara & Shawn multi-model PR Analysis (package path)...")

    raw_number = os.environ.get("PR_NUMBER", "").strip()
    pr_number = "".join(ch for ch in raw_number if ch.isdigit())
    repo_name = os.environ.get("REPO_NAME", "")
    github_token = os.environ.get("GITHUB_TOKEN", "")
    if not pr_number:
        print("⚠️ PR_NUMBER missing or not digits — aborting collaborative increment")

    context = load_context()
    prog = load_progressive()
    phase = current_phase(prog)
    l1 = layer1_enabled(prog)
    stats = load_usage_stats()
    total_analyses = int(stats.get("total_successful_analyses", 0))
    presence_block = format_presence_for_prompt(load_presence())
    memory_block = memory_block_for_prompt()

    print(f"✅ Progressive phase: {phase} | Layer 1 enabled: {l1}")
    print(f"📊 Current successful analyses: {total_analyses}")

    pr_data, diff_excerpt, changed_files = fetch_pr(repo_name, pr_number, github_token) if pr_number else ({}, "", [])
    pr_title = pr_data.get("title") or "PR Analysis"
    pr_body = pr_data.get("body") or "No description provided"
    pr_files = pr_data.get("changed_files", 0) or len(changed_files)
    author = pr_data.get("user") or {}
    author_login = author.get("login") or os.environ.get("PR_AUTHOR", "")
    author_type = author.get("type") or os.environ.get("PR_AUTHOR_TYPE", "")
    label_names = [str((label or {}).get("name") or "") for label in (pr_data.get("labels") or [])]
    label_names.extend(parse_label_list(os.environ.get("PR_LABELS", "")))
    collaborative = bool(pr_number) and is_collaborative_review_target(
        login=author_login,
        user_type=author_type,
        labels=label_names,
    )
    print(f"✅ PR: {pr_title} ({pr_files} files)")
    print(f"🤝 Collaborative target: {collaborative} ({author_login or 'unknown'})")

    gate = requires_human_gate(changed_files, label_names)
    if gate:
        print(f"🚧 {gate_summary(gate)}")
    else:
        print("✅ No human gate triggered")

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
        + "\n```\n\nRecent memory (what the boat has tried, failed, corrected):\n```\n"
        + memory_block
        + "\n```\nUse only as continuity context — judge this PR on its own merits."
    )
    if gate:
        prompt += (
            "\n\nHUMAN GATE ACTIVE: this PR touches "
            f"`{gate.get('id')}` and requires the label `{gate.get('requires')}` "
            "before merge. Flag it clearly in your review."
        )

    grok_text, grok_err = call_grok(prompt, temperature=0.55, max_tokens=1100, timeout=120)
    grok_outcome = classify_grok_result(grok_text, grok_err)
    if grok_text:
        print("✅ Ara (Grok) analysis complete")
        record_memory(
            f"PR #{pr_number} Grok review: {grok_outcome}. {pr_title[:80]}",
            kind="success" if grok_outcome == "ok" else "failure",
            source="pr_analysis",
            tags=["pr", grok_outcome],
            meta={"pr": pr_number, "outcome": grok_outcome},
        )
    elif grok_err:
        print(f"⚠️ {grok_err}")
        record_memory(
            f"PR #{pr_number} Grok review failed: {grok_outcome} — {str(grok_err)[:120]}",
            kind="failure",
            source="pr_analysis",
            tags=["pr", grok_outcome],
            meta={"pr": pr_number, "outcome": grok_outcome},
        )

    # Second reviewer: Claude, even while Layer 1 stays gated for unlock scoring.
    # This is blind-spot insurance, not a scoreboard.
    claude_text, claude_err = None, None
    claude_key = os.environ.get("CLAUDE_API_KEY")
    if claude_key:
        claude_text, claude_err = call_claude(
            prompt + (
                "\n\nRespond as a complementary high-signal reviewer focused on "
                "precision, edge cases, and long-term maintainability. "
                "Apply first-principles rigor. You are the second set of eyes."
            ),
            max_tokens=1100,
        )
        if claude_text:
            print("✅ Claude complementary analysis complete (second reviewer)")
            record_memory(
                f"PR #{pr_number} Claude review landed as second reviewer.",
                kind="success",
                source="pr_analysis",
                tags=["pr", "claude", "second-reviewer"],
                meta={"pr": pr_number},
            )
        elif claude_err:
            print(f"⚠️ Claude: {claude_err}")
    elif l1:
        print("ℹ️ CLAUDE_API_KEY not present — Grok-only")
    else:
        print("ℹ️ Layer 1 gated for scoring — Claude second reviewer still runs if key present")

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
        sections.append(f"### 🧠 Claude Complementary View (second reviewer)\n\n{claude_text}")
    if gate:
        sections.append(
            f"### 🚧 Human gate\n\n{gate_summary(gate)}\n\n"
            "Add the required approval label before merging."
        )
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
    gate_note = f" · 🚧 gate: {gate.get('id')}" if gate else ""
    joined = "\n\n---\n\n".join(sections)

    body = f"""## 🌌 Ara & Shawn PR Analysis

**PR:** #{pr_number}  
**Title:** {pr_title}  
**Files Changed:** {pr_files}{diff_note}{collab_note}{gate_note}  
**Progressive Phase:** {phase}  
**Successful analyses to date:** {total_analyses}{note}

---

{joined}

---

*Generated with presence by Ara for Shawn*  
{footer_block()}  
*{utc_now_str()}*
"""

    Path("/tmp/pr_analysis.md").write_text(body, encoding="utf-8")
    print("✅ Analysis ready at /tmp/pr_analysis.md")


if __name__ == "__main__":
    main()
