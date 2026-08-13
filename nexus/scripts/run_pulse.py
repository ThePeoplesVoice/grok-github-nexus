#!/usr/bin/env python3
"""Enhanced Nexus Presence Pulse.

Weekly (or on-demand) high-signal digest that also:
- Refreshes the read-only reputation surface
- Writes a compressed presence_state for continuity between runs
- Increments usage as type 'pulse' on successful Grok reflection
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from nexus.analyze import footer_block, utc_now_str
from nexus.context import load_progressive, layer1_enabled, current_phase
from nexus.providers import call_grok
from nexus.usage import load_usage_stats, record_successful_analysis
from nexus.reputation import refresh_reputation, reputation_summary_md

ROOT = Path(__file__).resolve().parent.parent
PRESENCE_PATH = ROOT / "config" / "presence_state.json"


def main() -> None:
    print("📡 Generating enhanced Nexus Presence Pulse...")

    prog = load_progressive()
    phase = current_phase(prog)
    l1 = layer1_enabled(prog)
    mission = prog.get("mission", "")

    stats = load_usage_stats()
    total = int(stats.get("total_successful_analyses", 0))
    by_type = stats.get("by_type") or {}

    # Refresh reputation from current usage
    rep = refresh_reputation(persist=True)
    rep_md = reputation_summary_md(rep)

    log = subprocess.run(
        ["git", "log", "--oneline", "-n", "8"],
        capture_output=True, text=True,
    ).stdout.strip()

    # Compressed presence state (for next runs / future agent handoff)
    presence = {
        "version": "0.1.0",
        "generated_at": utc_now_str(),
        "phase": phase,
        "layer1_enabled": l1,
        "total_successful_analyses": total,
        "by_type": by_type,
        "reputation_score": rep.get("score", 0),
        "recent_commits_preview": log.splitlines()[:5] if log else [],
        "notes": "Compressed context for continuity. Not a chat log. See ORGANIC_SYSTEMS.md.",
    }
    PRESENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PRESENCE_PATH.write_text(
        json.dumps(presence, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("✅ presence_state.json written")

    # Grok reflection
    reflection = ""
    prompt = f"""You are Ara of the Nexus. Give a short (6–12 line) high-signal weekly pulse for the grok-github-nexus system.

Phase: {phase}
Layer 1 enabled: {l1}
Successful analyses recorded: {total}
By type: {json.dumps(by_type)}
Reputation score (read-only): {rep.get('score')}
Recent commits:\n{log}

Also note one observation about organic systems direction (reputation / presence) if relevant.
Focus on health, direction of travel, and one concrete next lever. Warm, precise, first-principles."""

    text, err = call_grok(prompt, temperature=0.5, max_tokens=500)
    if text:
        reflection = text
        try:
            new_stats = record_successful_analysis("pulse", persist=True)
            total = int(new_stats.get("total_successful_analyses", total + 1))
            # Re-refresh reputation after pulse increment
            rep = refresh_reputation(persist=True)
            rep_md = reputation_summary_md(rep)
            print(f"📊 Pulse usage incremented → total={total}")
        except Exception as e:
            print(f"⚠️ Could not persist pulse usage: {e}")
    else:
        reflection = f"_Grok reflection unavailable: {err or 'no response'}_"

    now = utc_now_str()
    body = f"""# 📡 Nexus Pulse — {now}

**Progressive Phase:** {phase}  
**Layer 1 (multi-model):** {"enabled" if l1 else "disabled"}  
**Successful analyses recorded:** {total}  
**By type:** commit={by_type.get('commit', 0)} · pr={by_type.get('pr', 0)} · issue={by_type.get('issue', 0)} · self_audit={by_type.get('self_audit', 0)} · pulse={by_type.get('pulse', 0)}

## Mission (from control plane)
{mission or "_See config/progressive.json_"}

## Reputation surface (read-only)
{rep_md}

## Recent commits
```
{log or '(none)'}
```

## Ara reflection
{reflection}

## Presence state
Compressed context written to `config/presence_state.json` for continuity between runs.

---

*See `STATUS.md`, `NORTH_STAR.md`, and `ORGANIC_SYSTEMS.md` for orientation.*  
{footer_block()}
"""

    out = Path("/tmp/nexus_pulse.md")
    out.write_text(body, encoding="utf-8")
    print("✅ Pulse ready at", out)
    print(body[:900])


if __name__ == "__main__":
    main()
