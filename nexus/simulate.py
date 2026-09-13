"""Local analysis, simulation, and optimisation without GitHub noise.

Observe living instruments → simulate deltas in memory → recommend.
Never persists Astra. Never increments usage. Never files issues.

This is the hourly reassessment surface: think here, act only when
the triad (true / high-signal / leaves the ground) still holds.
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from typing import Any

from .astra import compute_astra, load_astra
from .audit import alignment_signals, structural_health
from .context import current_phase, layer1_enabled, load_progressive
from .presence import load_presence
from .reputation import compute_reputation
from .usage import VALID_TYPES, load_usage_stats

COMPLETE_HOLD_UNTIL = datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc)

SCENARIO_IDS = (
    "baseline",
    "recompute_astra",
    "plus_one_pr",
    "plus_one_issue",
    "plus_one_pulse",
    "plus_one_complete",
    "idle_7",
    "idle_30",
)


def utc_now(now: datetime | None = None) -> datetime:
    stamp = now or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        return stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def apply_usage_delta(
    stats: dict[str, Any],
    analysis_type: str,
    amount: int = 1,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a copied usage snapshot with an in-memory increment."""
    out = copy.deepcopy(stats)
    kind = (analysis_type or "other").strip().lower()
    if kind not in VALID_TYPES:
        kind = "other"
    by_type = dict(out.get("by_type") or {})
    by_type[kind] = int(by_type.get(kind, 0)) + amount
    out["by_type"] = by_type
    out["total_successful_analyses"] = int(out.get("total_successful_analyses", 0)) + amount
    out["last_updated"] = utc_now(now).strftime("%Y-%m-%dT%H:%M:%SZ")
    out["last_type"] = kind
    return out


def apply_idle(
    stats: dict[str, Any],
    days: float,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a copied usage snapshot aged by ``days`` of inactivity."""
    out = copy.deepcopy(stats)
    past = utc_now(now) - timedelta(days=days)
    out["last_updated"] = past.strftime("%Y-%m-%dT%H:%M:%SZ")
    return out


def astra_ledger_lag(
    ledger: dict[str, Any],
    live: dict[str, Any],
) -> dict[str, Any]:
    ledger_n = int(ledger.get("total_successful_analyses", 0) or 0)
    live_n = int(live.get("total_successful_analyses", 0) or 0)
    ledger_balance = float(ledger.get("balance", 0) or 0)
    live_balance = float(live.get("balance", 0) or 0)
    return {
        "lagging": ledger_n != live_n,
        "ledger_analyses": ledger_n,
        "live_analyses": live_n,
        "delta_analyses": live_n - ledger_n,
        "ledger_balance": ledger_balance,
        "live_balance": live_balance,
        "balance_unchanged": ledger_balance == live_balance,
        "ledger_last_computed": ledger.get("last_computed"),
        "advice": (
            "Let the organic script recompute Astra. Do not hand-edit config/astra.json."
            if ledger_n != live_n
            else "Astra ledger matches live compute."
        ),
    }


def layer1_distance(
    prog: dict[str, Any],
    usage: dict[str, Any],
) -> dict[str, Any]:
    layer = (prog.get("layers") or {}).get("1_progressive_unlocks") or {}
    triggers = layer.get("triggers") or {}
    by_type = usage.get("by_type") or {}
    prs = int(by_type.get("pr", 0) or 0)
    issues = int(by_type.get("issue", 0) or 0)
    collaborative = prs + issues
    total = int(usage.get("total_successful_analyses", 0) or 0)
    need_prs = int(triggers.get("min_community_prs", 0) or 0)
    need_total = int(triggers.get("min_successful_analyses", 0) or 0)
    flag = bool(layer.get("enabled", False))
    triggers_met = collaborative >= need_prs and total >= need_total
    return {
        "flag_enabled": flag,
        "gate_held_on_purpose": not flag,
        "pr": prs,
        "issue": issues,
        "collaborative_count": collaborative,
        "collaborative_needed": max(0, need_prs - collaborative),
        "analyses": total,
        "analyses_needed": max(0, need_total - total),
        "triggers_met": triggers_met,
        "would_unlock_if_flag_flipped": triggers_met,
        "actually_enabled": layer1_enabled(prog, usage),
    }


def complete_hold_state(now: datetime | None = None) -> dict[str, Any]:
    stamp = utc_now(now)
    remaining = COMPLETE_HOLD_UNTIL - stamp
    holding = stamp < COMPLETE_HOLD_UNTIL
    return {
        "holding": holding,
        "until": COMPLETE_HOLD_UNTIL.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seconds_remaining": max(0, int(remaining.total_seconds())),
        "advice": (
            "Do not dispatch Complete again until Thursday 2026-09-17 10:00 UTC."
            if holding
            else "Complete hold window has passed — dispatch only if a genuine Grok ok is the goal."
        ),
    }


def _scorecard(usage: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    reputation = compute_reputation(usage, now=now)
    astra = compute_astra(reputation)
    return {
        "usage_total": int(usage.get("total_successful_analyses", 0) or 0),
        "by_type": dict(usage.get("by_type") or {}),
        "collaborative_score": reputation.get("collaborative_score"),
        "unlock_score": reputation.get("unlock_score"),
        "internal_score": reputation.get("internal_score"),
        "effective_score": reputation.get("score"),
        "raw_score": reputation.get("raw_score"),
        "freshness": reputation.get("freshness"),
        "days_idle": reputation.get("days_idle"),
        "decay_factor": reputation.get("decay_factor"),
        "astra_balance": astra.get("balance"),
        "astra_analyses": astra.get("total_successful_analyses"),
    }


def observe(
    *,
    usage: dict[str, Any] | None = None,
    progressive: dict[str, Any] | None = None,
    astra_ledger: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Read-only snapshot. Computes live Astra without writing the ledger."""
    stats = usage if usage is not None else load_usage_stats()
    prog = progressive if progressive is not None else load_progressive()
    ledger = astra_ledger if astra_ledger is not None else load_astra()
    live = _scorecard(stats, now=now)
    live_astra = {
        "balance": live["astra_balance"],
        "total_successful_analyses": live["astra_analyses"],
    }
    return {
        "observed_at": utc_now(now).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "phase": current_phase(prog),
        "layer1": layer1_distance(prog, stats),
        "health": structural_health(),
        "triad_hits": alignment_signals().get("total_triad_hits"),
        "scorecard": live,
        "astra_lag": astra_ledger_lag(ledger, live_astra),
        "complete_hold": complete_hold_state(now),
        "presence_at": (load_presence() or {}).get("generated_at") if usage is None else None,
    }


def run_scenario(
    scenario_id: str,
    usage: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    if scenario_id == "baseline" or scenario_id == "recompute_astra":
        projected = copy.deepcopy(usage)
        note = (
            "Live compute of Astra from current usage. Ledger is not written."
            if scenario_id == "recompute_astra"
            else "Current instruments, no delta."
        )
    elif scenario_id == "plus_one_pr":
        projected = apply_usage_delta(usage, "pr", now=now)
        note = "One collaborative PR review. This is the unlock-score path."
    elif scenario_id == "plus_one_issue":
        projected = apply_usage_delta(usage, "issue", now=now)
        note = "One collaborative issue triage. Counts toward unlock score."
    elif scenario_id == "plus_one_pulse":
        projected = apply_usage_delta(usage, "pulse", now=now)
        note = "Internal pulse churn. Usage rises; collaborative unlock score does not."
    elif scenario_id == "plus_one_complete":
        projected = apply_usage_delta(usage, "complete", now=now)
        note = "Complete increment only after a genuine Grok ok — currently held."
    elif scenario_id == "idle_7":
        projected = apply_idle(usage, 7, now=now)
        note = "Seven idle days. Freshness leaves the fresh band."
    elif scenario_id == "idle_30":
        projected = apply_idle(usage, 30, now=now)
        note = "Thirty idle days. Half-life decay applies to the collaborative score."
    else:
        raise ValueError(f"unknown scenario: {scenario_id}")

    return {
        "id": scenario_id,
        "note": note,
        "scorecard": _scorecard(projected, now=now),
    }


def simulate_scenarios(
    usage: dict[str, Any] | None = None,
    *,
    now: datetime | None = None,
    scenario_ids: tuple[str, ...] | list[str] = SCENARIO_IDS,
) -> list[dict[str, Any]]:
    stats = usage if usage is not None else load_usage_stats()
    return [run_scenario(sid, stats, now=now) for sid in scenario_ids]


def recommend(
    observation: dict[str, Any],
    scenarios: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Ranked next actions. Prefer hold/maintenance over new surfaces."""
    layer1 = observation.get("layer1") or {}
    lag = observation.get("astra_lag") or {}
    hold = observation.get("complete_hold") or {}
    by_id = {item.get("id"): item for item in scenarios}

    pulse = by_id.get("plus_one_pulse") or {}
    pr = by_id.get("plus_one_pr") or {}
    baseline = by_id.get("baseline") or {}
    pulse_unlock = (pulse.get("scorecard") or {}).get("unlock_score")
    baseline_unlock = (baseline.get("scorecard") or {}).get("unlock_score")
    pr_unlock = (pr.get("scorecard") or {}).get("unlock_score")

    actions: list[dict[str, Any]] = []

    if hold.get("holding"):
        actions.append({
            "id": "hold-complete",
            "title": "Hold Complete until 2026-09-17 10:00 UTC",
            "stance": "hold",
            "leverage": "high",
            "why": hold.get("advice"),
        })

    actions.append({
        "id": "one-living-collaborative-pr",
        "title": "Open one non-chore PR a collaborator can actually review",
        "stance": "act",
        "leverage": "high",
        "why": (
            f"Unlock score {baseline_unlock} → {pr_unlock} on +1 PR. "
            f"Layer 1 still gated on purpose (flag={layer1.get('flag_enabled')}, "
            f"analyses short {layer1.get('analyses_needed')}). "
            "Internal pulse/self-audit churn is not the evidence."
        ),
    })

    if lag.get("lagging"):
        actions.append({
            "id": "recompute-astra-from-reputation",
            "title": "Let the organic script recompute Astra",
            "stance": "act",
            "leverage": "medium",
            "why": lag.get("advice") + (
                f" Ledger analyses={lag.get('ledger_analyses')} "
                f"vs live={lag.get('live_analyses')}."
            ),
        })

    if pulse_unlock == baseline_unlock:
        actions.append({
            "id": "refuse-pulse-grind",
            "title": "Do not grind Pulse or self-audit to chase Layer 1",
            "stance": "hold",
            "leverage": "high",
            "why": (
                f"Simulated +1 pulse leaves unlock score at {pulse_unlock}. "
                "That path is noise."
            ),
        })

    if layer1.get("gate_held_on_purpose"):
        actions.append({
            "id": "hold-layer1-flag",
            "title": "Keep Layer 1 gated until collaborative evidence is enough",
            "stance": "hold",
            "leverage": "medium",
            "why": (
                "enabled=false is the actual gate. Do not flip it from "
                "usage totals or simulation output."
            ),
        })

    return actions


def expansion_gate(observation: dict[str, Any]) -> dict[str, Any]:
    hold = observation.get("complete_hold") or {}
    layer1 = observation.get("layer1") or {}
    if hold.get("holding") or layer1.get("gate_held_on_purpose"):
        return {
            "recommendation": "hold",
            "reason": (
                "Complete is held, Layer 1 is gated on purpose, and extra "
                "analysis issues are grinding. Simulate here; ship one living PR."
            ),
        }
    return {
        "recommendation": "simplify",
        "reason": "Prefer signal density over a new surface.",
    }


def reassess(
    *,
    usage: dict[str, Any] | None = None,
    progressive: dict[str, Any] | None = None,
    astra_ledger: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Full observe → simulate → recommend cycle. Read-only on living files."""
    stats = usage if usage is not None else load_usage_stats()
    observation = observe(
        usage=stats,
        progressive=progressive,
        astra_ledger=astra_ledger,
        now=now,
    )
    scenarios = simulate_scenarios(stats, now=now)
    actions = recommend(observation, scenarios)
    return {
        "observed_at": observation["observed_at"],
        "observation": observation,
        "scenarios": scenarios,
        "recommendations": actions,
        "expansion_gate": expansion_gate(observation),
        "persisted": {
            "astra": False,
            "usage": False,
            "reputation": False,
            "issues": False,
        },
    }


def format_report_md(report: dict[str, Any]) -> str:
    obs = report.get("observation") or {}
    card = obs.get("scorecard") or {}
    layer1 = obs.get("layer1") or {}
    lag = obs.get("astra_lag") or {}
    hold = obs.get("complete_hold") or {}
    health = obs.get("health") or {}
    gate = report.get("expansion_gate") or {}
    by_type = card.get("by_type") or {}

    scenario_lines = []
    for item in report.get("scenarios") or []:
        sc = item.get("scorecard") or {}
        scenario_lines.append(
            f"- `{item.get('id')}` — unlock {sc.get('unlock_score')} · "
            f"effective {sc.get('effective_score')} · "
            f"freshness {sc.get('freshness')} · "
            f"Astra {sc.get('astra_balance')} — {item.get('note')}"
        )

    action_lines = []
    for item in report.get("recommendations") or []:
        action_lines.append(
            f"- **{item.get('stance')}** `{item.get('id')}` "
            f"(leverage {item.get('leverage')}): {item.get('title')} "
            f"— {item.get('why')}"
        )

    persisted = report.get("persisted") or {}
    return f"""# 🧪 Nexus Simulation / Reassessment

**Observed:** {report.get('observed_at')}  
**Phase:** {obs.get('phase')}  
**Structural health:** {health.get('score')}/100  
**Expansion gate:** {gate.get('recommendation')} — {gate.get('reason')}

## Live scorecard (not written)

- Usage total **{card.get('usage_total')}** — pr {by_type.get('pr', 0)} · issue {by_type.get('issue', 0)} · commit {by_type.get('commit', 0)} · pulse {by_type.get('pulse', 0)} · complete {by_type.get('complete', 0)}
- Unlock / collaborative **{card.get('unlock_score')}** · internal {card.get('internal_score')} · raw {card.get('raw_score')}
- Effective **{card.get('effective_score')}** ({card.get('freshness')}, idle {card.get('days_idle')}d)
- Live Astra **{card.get('astra_balance')}** from {card.get('astra_analyses')} analyses

## Layer 1 distance

- Flag enabled: **{layer1.get('flag_enabled')}** (gate held on purpose: {layer1.get('gate_held_on_purpose')})
- Collaborative count: {layer1.get('collaborative_count')} (still need {layer1.get('collaborative_needed')})
- Analyses: {layer1.get('analyses')} (still need {layer1.get('analyses_needed')})
- Triggers met: {layer1.get('triggers_met')} · actually enabled: {layer1.get('actually_enabled')}

## Astra ledger vs live compute

- Lagging: **{lag.get('lagging')}** ({lag.get('ledger_analyses')} → {lag.get('live_analyses')})
- Balance ledger {lag.get('ledger_balance')} vs live {lag.get('live_balance')}
- {lag.get('advice')}

## Complete hold

- Holding: **{hold.get('holding')}** until {hold.get('until')}
- {hold.get('advice')}

## Simulated scenarios (memory only)

{chr(10).join(scenario_lines) or '- (none)'}

## Recommendations

{chr(10).join(action_lines) or '- (none)'}

## Persistence

Astra written: {persisted.get('astra')} · usage written: {persisted.get('usage')} · issues filed: {persisted.get('issues')}

See `AUTOMATED_DEVELOPMENT.md`. Think here. Do not grind Pulse to feel busy.
"""
