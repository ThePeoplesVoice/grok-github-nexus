"""Human-in-the-loop gates for the Nexus.

The boat runs free on chores. Money, deploy, payments, and public posts
require an explicit human approval label before merge. That one rule keeps
the power from becoming a liability.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
GATES_PATH = ROOT / "config" / "gates.json"


def _defaults() -> dict[str, Any]:
    return {
        "version": "1.0.0",
        "rules": [],
        "approval_labels": [],
    }


def load_gates(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else GATES_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else _defaults()
    except Exception:
        return _defaults()


def requires_human_gate(
    paths: list[str],
    labels: list[str],
    *,
    path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Return the first matching gate rule that lacks its approval label, or None.

    paths: changed file paths in the PR.
    labels: labels currently on the PR.
    """
    gates = load_gates(path)
    rules = gates.get("rules") or []
    label_set = {str(l).strip().lower() for l in (labels or [])}
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        match = rule.get("match") or []
        requires = str(rule.get("requires") or "").strip().lower()
        if not match or not requires:
            continue
        hit = False
        for p in paths or []:
            pl = str(p).lower()
            for m in match:
                if str(m).lower() in pl:
                    hit = True
                    break
            if hit:
                break
        if hit and requires not in label_set:
            return rule
    return None


def gate_summary(rule: dict[str, Any] | None) -> str:
    if not rule:
        return "No human gate triggered."
    return (
        f"Human gate required: `{rule.get('requires')}` "
        f"({rule.get('why') or 'see config/gates.json'})"
    )
