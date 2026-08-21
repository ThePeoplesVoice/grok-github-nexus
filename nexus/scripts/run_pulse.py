#!/usr/bin/env python3
"""Enhanced Nexus Presence Pulse.

Always produces a pulse report + presence_state, even when Grok is unavailable.
Increments usage only on successful Grok reflection.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from nexus.analyze import footer_block, utc_now_str
from nexus.context import (
    load_progressive,
    successful_analysis_gate_status,
    layer1_enabled,
    layer1_feature_enabled,
    current_phase,
)
from nexus.providers import call_grok
from nexus.usage import load_usage_stats
from nexus.reputation import reputation_summary_md, refresh_reputation
from nexus.runtime import after_successful_analysis, log_success

# scripts/ -> nexus/ -> repo root
ROOT = Path(__file__).resolve().parent.parent.parent
PRESENCE_PATH = ROOT / "config" / "presence_state.json"


def main() -> None:
    print("📡 Generating enhanced Nexus Presence Pulse...")

    prog = load_progressive()
    phase = current_phase(prog)
    stats = load_usage_stats()
    gate = successful_analysis_gate_status(prog, stats)
    l1_config = layer1_enabled(prog)
    l1 = layer1_feature_enabled("multi_model_fusion", prog, stats)
    mission = prog.get("mission", "")
    total = int(stats.get("total_successful_analyses", 0))
    by_type = dict(stats.get("by_type") or {})

    try:
        rep = refresh_reputation(persist=True)
    except Exception as e:
        print(f"⚠️ reputation refresh failed: {e}")
        rep = {"score": 0, "raw_score": 0, "freshness": "unknown"}
    rep_md = reputation_summary_md(rep)

    log = subprocess.run(
        ["git", "log", "--oneline", "-n", "8"],
        capture_output=True, text=True,
    ).stdout.strip()

    presence = {
        "version": "0.2.0",
        "generated_at": utc_now_str(),
        "phase": phase,
        "layer1_enabled": l1,
        "layer1_config_enabled": l1_config,
        "successful_analysis_gate": gate,
        "total_successful_analyses": total,
        "by_type": by_type,
        "reputation_score": rep.get("score", 0),
        "reputation_raw": rep.get("raw_score", 0),
        "reputation_freshness": rep.get("freshness", "unknown"),
        "recent_commits_preview": log.splitlines()[:5] if log else [],
        "notes": "Compressed context for continuity. Not a chat log. See ORGANIC_SYSTEMS.md.",
    }
    PRESENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PRESENCE_PATH.write_text(
        json.dumps(presence, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("✅ presence_state.json written")

    reflection = ""
    prompt = f"""You are Ara of the Nexus. Give a short (6–12 line) high-signal weekly pulse for the grok-github-nexus system.

Phase: {phase}
Layer 1 enabled: {l1}
Successful analyses recorded: {total}
By type: {json.dumps(by_type)}
Reputation effective: {rep.get('score')} (raw {rep.get('raw_score')}, freshness {rep.get('freshness')})
Recent commits:\n{log}

Also note one observation about organic systems direction (reputation decay / presence continuity) if relevant.
Focus on health, direction of travel, and one concrete next lever. Warm, precise, first-principles."""

    text, err = call_grok(prompt, temperature=0.5, max_tokens=500)
    if text:
        reflection = text
        try:
            result = after_successful_analysis("pulse")
            total = int(result.get("total", total + 1))
            rep = result["reputation"]
            rep_md = reputation_summary_md(rep)
            by_type = dict(result["stats"].get("by_type") or by_type)
            gate = successful_analysis_gate_status(prog, result["stats"])
            l1 = layer1_feature_enabled("multi_model_fusion", prog, result["stats"])
            log_success(result, "pulse")
            presence["layer1_enabled"] = l1
            presence["successful_analysis_gate"] = gate
            presence["total_successful_analyses"] = total
            presence["by_type"] = by_type
            presence["reputation_score"] = rep.get("score", 0)
            presence["reputation_raw"] = rep.get("raw_score", 0)
            presence["reputation_freshness"] = rep.get("freshness", "unknown")
            PRESENCE_PATH.write_text(
                json.dumps(presence, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except Exception as e:
            print(f"⚠️ Could not persist pulse usage: {e}")
    else:
        reflection = (
            f"_Grok reflection unavailable: {err or 'no response'}_\n\n"
            "_Pulse still recorded structural state + presence_state for continuity._"
        )
        print(f"⚠️ Grok unavailable: {err}")

    now = utc_now_str()
    body = f"""# 📡 Nexus Pulse — {now}

**Progressive Phase:** {phase}  
**Layer 1 config:** {"enabled" if l1_config else "disabled"}  
**Multi-model fusion:** {"unlocked" if l1 else "locked"} ({gate['current']}/{gate['required']} successful analyses)  
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
