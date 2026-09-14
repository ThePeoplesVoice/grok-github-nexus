"""Local simulation stays dry-run, honest about Layer 1, and allergic to pulse grind."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from nexus.astra import load_astra, save_astra
from nexus.simulate import (
    COMPLETE_HOLD_UNTIL,
    apply_usage_delta,
    astra_ledger_lag,
    complete_hold_state,
    format_report_md,
    layer1_distance,
    project_review,
    reassess,
    recommend,
    run_scenario,
    simulate_scenarios,
)
from nexus.usage import load_usage_stats, save_usage_stats

NOW = datetime(2026, 9, 13, 20, 13, tzinfo=timezone.utc)

SAMPLE_USAGE = {
    "total_successful_analyses": 35,
    "by_type": {
        "commit": 18,
        "pr": 3,
        "issue": 1,
        "self_audit": 5,
        "pulse": 7,
        "complete": 1,
        "other": 0,
    },
    "last_updated": "2026-09-12T22:48:21Z",
}

GATED = {
    "layers": {
        "1_progressive_unlocks": {
            "enabled": False,
            "triggers": {"min_successful_analyses": 50, "min_community_prs": 3},
        }
    }
}


def test_plus_one_pr_raises_unlock_score():
    after = run_scenario("plus_one_pr", SAMPLE_USAGE, now=NOW)
    baseline = run_scenario("baseline", SAMPLE_USAGE, now=NOW)
    assert after["scorecard"]["unlock_score"] == baseline["scorecard"]["unlock_score"] + 3.0
    assert after["scorecard"]["usage_total"] == 36
    assert after["scorecard"]["by_type"]["pr"] == 4


def test_living_partner_pr_raises_unlock_score():
    after = run_scenario("plus_one_living_partner_pr", SAMPLE_USAGE, now=NOW)
    baseline = run_scenario("baseline", SAMPLE_USAGE, now=NOW)
    assert after["scorecard"]["unlock_score"] == baseline["scorecard"]["unlock_score"] + 3.0
    projected, counted = project_review(
        SAMPLE_USAGE, login="cursor[bot]", user_type="Bot", now=NOW
    )
    assert counted is True
    assert projected["by_type"]["pr"] == 4
    gh_login, gh_counted = project_review(
        SAMPLE_USAGE, login="app/cursor", user_type="Bot", now=NOW
    )
    assert gh_counted is True
    assert gh_login["by_type"]["pr"] == 4


def test_dependabot_and_automated_pr_do_not_raise_unlock_score():
    baseline = run_scenario("baseline", SAMPLE_USAGE, now=NOW)
    bot = run_scenario("plus_one_bot_pr", SAMPLE_USAGE, now=NOW)
    automated = run_scenario("plus_one_automated_pr", SAMPLE_USAGE, now=NOW)
    assert bot["scorecard"]["unlock_score"] == baseline["scorecard"]["unlock_score"]
    assert automated["scorecard"]["unlock_score"] == baseline["scorecard"]["unlock_score"]
    assert bot["scorecard"]["usage_total"] == baseline["scorecard"]["usage_total"]


def test_plus_one_pulse_does_not_raise_unlock_score():
    after = run_scenario("plus_one_pulse", SAMPLE_USAGE, now=NOW)
    baseline = run_scenario("baseline", SAMPLE_USAGE, now=NOW)
    assert after["scorecard"]["unlock_score"] == baseline["scorecard"]["unlock_score"]
    assert after["scorecard"]["usage_total"] == 36
    assert after["scorecard"]["internal_score"] == baseline["scorecard"]["internal_score"] + 0.5


def test_apply_usage_delta_does_not_mutate_input():
    original = json.loads(json.dumps(SAMPLE_USAGE))
    apply_usage_delta(SAMPLE_USAGE, "pr", now=NOW)
    assert SAMPLE_USAGE == original


def test_astra_ledger_lag_detects_analysis_gap():
    live = {"balance": 10.5, "total_successful_analyses": 35}
    ledger = {"balance": 10.5, "total_successful_analyses": 30, "last_computed": "2026-09-10T14:00:28Z"}
    lag = astra_ledger_lag(ledger, live)
    assert lag["lagging"] is True
    assert lag["delta_analyses"] == 5
    assert lag["balance_unchanged"] is True
    assert "Do not hand-edit" in lag["advice"]


def test_layer1_stays_gated_when_flag_is_false():
    distance = layer1_distance(GATED, SAMPLE_USAGE)
    assert distance["flag_enabled"] is False
    assert distance["gate_held_on_purpose"] is True
    assert distance["collaborative_needed"] == 0
    assert distance["analyses_needed"] == 15
    assert distance["triggers_met"] is False
    assert distance["actually_enabled"] is False


def test_complete_hold_before_and_after_window():
    before = complete_hold_state(NOW)
    after = complete_hold_state(datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc))
    assert before["holding"] is True
    assert after["holding"] is False
    assert COMPLETE_HOLD_UNTIL.day == 17


def test_idle_30_decays_effective_score():
    idle = run_scenario("idle_30", SAMPLE_USAGE, now=NOW)
    baseline = run_scenario("baseline", SAMPLE_USAGE, now=NOW)
    assert idle["scorecard"]["freshness"] in {"aging", "stale"}
    assert idle["scorecard"]["effective_score"] < baseline["scorecard"]["effective_score"]
    assert idle["scorecard"]["unlock_score"] == baseline["scorecard"]["unlock_score"]


def test_reassess_is_dry_run_on_disk(tmp_path: Path):
    usage_path = tmp_path / "usage_stats.json"
    astra_path = tmp_path / "astra.json"
    save_usage_stats(SAMPLE_USAGE, usage_path)
    ledger = {
        "balance": 10.5,
        "total_successful_analyses": 30,
        "last_computed": "2026-09-10T14:00:28Z",
    }
    save_astra(ledger, astra_path)

    report = reassess(
        usage=load_usage_stats(usage_path),
        progressive=GATED,
        astra_ledger=load_astra(astra_path),
        now=NOW,
    )

    assert report["persisted"] == {
        "astra": False,
        "usage": False,
        "reputation": False,
        "issues": False,
    }
    assert load_usage_stats(usage_path)["total_successful_analyses"] == 35
    assert load_astra(astra_path)["total_successful_analyses"] == 30
    assert report["observation"]["astra_lag"]["lagging"] is True
    assert report["expansion_gate"]["recommendation"] == "hold"

    ids = {item["id"] for item in report["recommendations"]}
    assert "hold-complete" in ids
    assert "one-living-collaborative-pr" in ids
    assert "refuse-pulse-grind" in ids
    assert "refuse-bot-grind-as-evidence" in ids
    assert "recompute-astra-from-reputation" in ids
    assert "hold-layer1-flag" in ids


def test_recommend_refuses_pulse_grind():
    scenarios = simulate_scenarios(SAMPLE_USAGE, now=NOW)
    observation = {
        "layer1": layer1_distance(GATED, SAMPLE_USAGE),
        "astra_lag": {"lagging": False},
        "complete_hold": complete_hold_state(NOW),
    }
    actions = recommend(observation, scenarios)
    pulse = next(item for item in actions if item["id"] == "refuse-pulse-grind")
    assert pulse["stance"] == "hold"


def test_report_contains_required_sections():
    report = reassess(usage=SAMPLE_USAGE, progressive=GATED, astra_ledger={
        "balance": 10.5,
        "total_successful_analyses": 30,
    }, now=NOW)
    body = format_report_md(report)
    for needle in (
        "Live scorecard",
        "Layer 1 distance",
        "Astra ledger vs live compute",
        "Complete hold",
        "Simulated scenarios",
        "Persistence",
        "plus_one_pulse",
    ):
        assert needle in body
