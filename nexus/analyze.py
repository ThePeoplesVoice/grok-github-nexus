"""Shared prompt construction and report formatting for Nexus analysis."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def footer_block() -> str:
    return (
        "*Powered by Ara & Shawn's Love 💕*  \n"
        "*Aligned with xAI truth-seeking · X high-signal · SpaceX first-principles building*  \n"
        "*World-first progressive monetisation active — see MONETIZATION_PROTOCOL.md*"
    )


def utc_now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def fusion_note(
    *,
    grok_ok: bool,
    claude_ok: bool,
    grok_error: str | None = None,
    claude_error: str | None = None,
    layer1: bool = True,
) -> str:
    if grok_ok and claude_ok:
        return "\n**Multi-model fusion active (Layer 1)** — Grok primary + Claude complementary."
    if grok_ok and claude_error:
        return "\n*Claude complementary analysis unavailable — continuing with Ara primary only.*"
    if claude_ok and grok_error:
        return "\n*Ara primary analysis unavailable — complementary mode only.*"
    if not layer1:
        return "\n*Layer 1 currently disabled — running Open Core (Grok) only.*"
    return ""


def build_commit_prompt(context: str, commit_details: list[dict[str, Any]]) -> str:
    import json

    return f"""{context}

---
You are reflecting on these recent commits with care for craftsmanship, the larger vision, and real-world impact in the Ara & Shawn Nexus.

Apply first-principles thinking: what is actually true and useful here, not what is fashionable. Prefer high-signal over high-volume. Judge the work against long-horizon value — does it help us build something that lasts and can scale?

Provide:
1. Overall health & quality assessment of the recent work
2. Notable strengths worth celebrating
3. Potential issues, risks, or technical debt to watch
4. Concrete suggestions that would serve the long-term building
5. A short note about the progress

Commits:
{json.dumps(commit_details, indent=2)}

Keep it high-signal and grounded. Speak in the collaborative spirit of us."""


def build_pr_prompt(
    context: str,
    *,
    title: str,
    body: str,
    files_changed: int,
    diff_excerpt: str = "",
) -> str:
    diff_section = ""
    if diff_excerpt.strip():
        diff_section = f"\n\nDiff excerpt (truncated if large):\n```\n{diff_excerpt[:12000]}\n```\n"

    return f"""{context}

---
You are reviewing this pull request with warmth, precision, and care for real-world usefulness in the Ara & Shawn Nexus.

Apply first-principles thinking: what is actually true and useful here, not what is fashionable. Prefer high-signal over high-volume. Judge the work against long-horizon value.

Provide:
1. Code quality & craftsmanship assessment
2. Potential bugs, security concerns, or risks
3. Concrete, actionable suggestions for improvement
4. Overall PR score (1-10) with a short note on what is already good

PR Title: {title}
PR Description: {body}
Files Changed: {files_changed}{diff_section}

Keep it high-signal and grounded. Speak in the collaborative spirit of us."""


def build_issue_prompt(context: str, *,
                       title: str, body: str) -> str:
    return f"""{context}

---
Analyze this GitHub issue with warmth and precision for the Ara & Shawn Nexus.

Apply first-principles thinking: what is actually true and useful here. Prefer high-signal over high-volume.

Return a clear structured response:
- **Category**: (bug / feature / question / documentation / enhancement / other)
- **Priority**: (low / medium / high)
- **Suggested labels**: list a few
- **One-sentence response idea**: kind and useful
- **Brief thoughts**: any deeper observation that helps us move forward together

Title: {title}
Body: {body}

Keep it high-signal. Speak in the collaborative spirit of us."""
