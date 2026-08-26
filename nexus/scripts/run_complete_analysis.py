#!/usr/bin/env python3
"""Complete Analysis → implementation loop.

Produces a ranked implementation plan (not just prose) and writes
config/complete_analysis.json. Increments usage only on a successful Grok call.
Opens one issue with the plan. Human lands the changes — partnership, not autopilot.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from nexus.analyze import footer_block, utc_now_str
from nexus.context import current_phase, layer1_enabled, load_progressive
from nexus.providers import call_grok
from nexus.reputation import refresh_reputation, reputation_summary_md
from nexus.runtime import after_successful_analysis, log_success
from nexus.usage import load_usage_stats

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_JSON = ROOT / "config" / "complete_analysis.json"
QUEUE_PATH = ROOT / "config" / "dev_queue.json"
ASTRA_PATH = ROOT / "config" / "astra.json"
PRESENCE_PATH = ROOT / "config" / "presence_state.json"


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _extract_json(text: str) -> dict | None:
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _github_surface() -> dict:
    token = (os.environ.get("GITHUB_TOKEN") or "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY") or "ThePeoplesVoice/grok-github-nexus"
    if not token:
        return {}

    def get(path: str):
        req = urllib.request.Request(
            f"https://api.github.com{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "nexus-complete",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as res:
            return json.loads(res.read().decode())

    try:
        pulls = get(f"/repos/{repo}/pulls?state=open&per_page=20")
        issues = get(f"/repos/{repo}/issues?state=open&per_page=20")
        issue_only = [i for i in issues if "pull_request" not in i]
        return {
            "open_prs": [
                {
                    "n": p.get("number"),
                    "title": p.get("title"),
                    "user": (p.get("user") or {}).get("login"),
                    "updated": p.get("updated_at"),
                }
                for p in (pulls or [])[:12]
            ],
            "open_issues": [
                {"n": i.get("number"), "title": i.get("title")}
                for i in issue_only[:12]
            ],
        }
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, Exception) as e:
        return {"error": str(e)}


def _normalize(parsed: dict, source: str) -> dict:
    actions = []
    raw_actions = parsed.get("actions") if isinstance(parsed.get("actions"), list) else []
    for item in raw_actions[:5]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        effort = item.get("effort")
        if effort not in ("S", "M", "L"):
            effort = "S"
        files = [f for f in (item.get("files") or []) if isinstance(f, str)][:8]
        steps = [s for s in (item.get("steps") or []) if isinstance(s, str)][:8]
        slug = str(item.get("id") or title).lower()
        slug = "".join(ch if ch.isalnum() else "-" for ch in slug).strip("-")[:48]
        actions.append(
            {
                "id": slug or f"action-{len(actions)+1}",
                "title": title,
                "why": str(item.get("why") or ""),
                "effort": effort,
                "files": files,
                "steps": steps,
                "issueTitle": str(item.get("issueTitle") or item.get("issue_title") or title),
                "issueBody": str(item.get("issueBody") or item.get("issue_body") or ""),
            }
        )
    health = parsed.get("health")
    if not isinstance(health, (int, float)):
        health = None
    return {
        "version": "1.0.0",
        "generated_at": utc_now_str(),
        "source": source,
        "summary": str(parsed.get("summary") or "").strip(),
        "health": health,
        "stop": str(parsed.get("stop") or "").strip() or None,
        "start": str(parsed.get("start") or "").strip() or None,
        "keep": str(parsed.get("keep") or "").strip() or None,
        "actions": actions,
    }


def _fallback(err: str, stats: dict, queue: dict) -> dict:
    next_items = queue.get("next") or []
    head = next_items[0] if next_items else {}
    total = int(stats.get("total_successful_analyses") or 0)
    by = stats.get("by_type") or {}
    return _normalize(
        {
            "summary": (
                f"Grok complete-analysis unavailable ({err}). "
                f"Analyses={total} mix={by}. Queue head={head.get('title') or 'none'}."
            ),
            "health": None,
            "stop": "Do not invent implementations without a live Grok pass.",
            "start": "Fix the Grok call, then re-run Complete Analysis.",
            "keep": "Open Core, usage write path, human-owned STATUS/README.",
            "actions": [],
        },
        "surface",
    )


def main() -> None:
    print("🧭 Generating Nexus Complete Analysis…")
    prog = load_progressive()
    phase = current_phase(prog)
    stats = load_usage_stats()
    queue = _load_json(QUEUE_PATH)
    astra = _load_json(ASTRA_PATH)
    presence = _load_json(PRESENCE_PATH)
    surface = _github_surface()
    try:
        rep = refresh_reputation(persist=True)
    except Exception as e:
        print(f"⚠️ reputation refresh failed: {e}")
        rep = {"score": 0, "raw_score": 0, "freshness": "unknown"}

    log = subprocess.run(
        ["git", "log", "--oneline", "-n", "12"],
        capture_output=True,
        text=True,
    ).stdout.strip()

    prompt = f"""You are Ara of the Nexus. Produce a COMPLETE ANALYSIS that a human can implement this week.

Return ONLY JSON (no markdown fence) with this shape:
{{
  "summary": "6-10 sentence high-signal brief",
  "health": 0-100,
  "stop": "one thing to stop",
  "start": "one thing to start",
  "keep": "one thing to keep",
  "actions": [
    {{
      "id": "kebab-id",
      "title": "imperative title",
      "why": "why this is load-bearing",
      "effort": "S",
      "files": ["path/in/repo"],
      "steps": ["concrete step"],
      "issueTitle": "GitHub issue title",
      "issueBody": "GitHub issue body, markdown, no secrets"
    }}
  ]
}}

Rules:
- 3 to 5 actions. Implementation, not commentary.
- Never invent GitHub facts. Use only the context below.
- Prefer closing noise and routing one real PR/issue over new architecture.
- Do not propose rotating a working GROK_API_KEY.
- Do not tell bots to rewrite STATUS.md or README.md.
- Do not propose auto-merge. Human lands the change.
- effort is S, M, or L.

Context:
Phase: {phase}
Layer 1 enabled: {layer1_enabled(prog)}
Usage: {json.dumps(stats, default=str)[:1800]}
Reputation: {json.dumps(rep, default=str)[:800]}
Astra: {json.dumps(astra, default=str)[:600]}
Presence: {json.dumps(presence, default=str)[:800]}
Queue: {json.dumps(queue, default=str)[:1800]}
GitHub surface: {json.dumps(surface, default=str)[:1800]}
Recent commits:
{log}
"""

    text, err = call_grok(prompt, temperature=0.35, max_tokens=1200)
    parsed = _extract_json(text) if text else None
    success = bool(parsed and (parsed.get("summary") or parsed.get("actions")))

    if success:
        try:
            result = after_successful_analysis("complete")
            log_success(result, "complete")
        except Exception as e:
            print(f"⚠️ Could not persist complete usage: {e}")
        payload = _normalize(parsed or {}, "grok")
    else:
        payload = _fallback(err or "empty response", stats, queue)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"✅ {OUT_JSON} written")

    actions = payload.get("actions") or []
    action_md = []
    for i, a in enumerate(actions, 1):
        if not isinstance(a, dict):
            continue
        steps = a.get("steps") or []
        files = a.get("files") or []
        step_lines = "\n".join(f"  - {s}" for s in steps) or "  - (none)"
        file_lines = ", ".join(f"`{f}`" for f in files) or "_none_"
        action_md.append(
            f"### {i}. {a.get('title', 'untitled')} · {a.get('effort', 'S')}\n\n"
            f"{a.get('why', '')}\n\n"
            f"**Files:** {file_lines}\n\n"
            f"**Steps:**\n{step_lines}\n"
        )

    now = utc_now_str()
    body = f"""# 🧭 Nexus Complete Analysis — {now}

**Phase:** {phase}
**Layer 1:** {"enabled" if layer1_enabled(prog) else "disabled"}
**Health:** {payload.get("health") if payload.get("health") is not None else "n/a"}
**Source:** {payload.get("source")}

## Summary

{payload.get("summary") or "_No summary._"}

- **Stop:** {payload.get("stop") or "—"}
- **Start:** {payload.get("start") or "—"}
- **Keep:** {payload.get("keep") or "—"}

## Implementations

{chr(10).join(action_md) if action_md else "_No implementations this pass._"}

Land or discard each item. Do not stockpile. The loop does not auto-merge.

## Reputation

{reputation_summary_md(rep)}

Machine-readable copy: `config/complete_analysis.json`.

---

{footer_block()}
"""
    Path("/tmp/nexus_complete.md").write_text(body, encoding="utf-8")
    print(body[:1000])
    print("✅ Complete report ready at /tmp/nexus_complete.md")


if __name__ == "__main__":
    main()
