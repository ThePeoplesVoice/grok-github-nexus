"""Classify and (optionally) close stale / superseded pull requests.

Partnership, not autopilot:
- Human PRs with unique commits are never closed.
- Labels keep / do-not-close / human are sacred.
- Fully superseded (0 commits ahead of main) may close on the weekly dry-run.
- Noisy bot WIP needs an explicit apply=true dispatch.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

KEEP_LABELS = frozenset({"keep", "do-not-close", "human"})
NOISY_PREFIXES = (
    "copilot/commit-analysis",
    "copilot/fix-nexus-self-audit",
    "copilot/nexus-self-audit",
    "copilot/fix-grok-api",
    "copilot/resolve-grok-api",
    "dependabot/",
)
BOT_LOGINS = frozenset(
    {
        "copilot",
        "github-actions[bot]",
        "dependabot[bot]",
        "nexus-bot",
    }
)


def _login(pr: dict[str, Any]) -> str:
    return str(((pr.get("user") or {}).get("login") or "")).lower()


def _head(pr: dict[str, Any]) -> str:
    return str(((pr.get("head") or {}).get("ref") or ""))


def is_bot_pr(pr: dict[str, Any]) -> bool:
    login = _login(pr)
    typ = str((pr.get("user") or {}).get("type") or "")
    head = _head(pr)
    if typ == "Bot" or login.endswith("[bot]") or login in BOT_LOGINS:
        return True
    if head.startswith("copilot/") or head.startswith("dependabot/"):
        return True
    return False


def _labels(pr: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for item in pr.get("labels") or []:
        name = item.get("name") if isinstance(item, dict) else item
        if isinstance(name, str):
            out.add(name.lower())
    return out


def _age_days(pr: dict[str, Any], now: datetime) -> float:
    raw = pr.get("updated_at") or pr.get("created_at")
    if not raw:
        return 999.0
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (now - dt).total_seconds() / 86400.0)
    except Exception:
        return 999.0


def classify(
    pr: dict[str, Any],
    compare: dict[str, Any],
    now: datetime | None = None,
) -> tuple[str, str]:
    """Return (verdict, reason) where verdict is 'close' or 'keep'."""
    now = now or datetime.now(timezone.utc)
    if _labels(pr) & KEEP_LABELS:
        return "keep", "keep / do-not-close / human label"
    ahead = int(compare.get("ahead_by") or 0)
    behind = int(compare.get("behind_by") or 0)
    if ahead <= 0:
        return "close", "superseded — 0 commits ahead of main"
    if not is_bot_pr(pr):
        return "keep", "human author with unique commits"
    age = _age_days(pr, now)
    title = str(pr.get("title") or "")
    head = _head(pr)
    noisy = "[wip]" in title.lower() or any(head.startswith(p) for p in NOISY_PREFIXES)
    draft = bool(pr.get("draft"))
    if age < 2:
        return "keep", "updated in the last 48h — may still be live"
    if (noisy or draft) and behind >= 1 and age >= 3:
        return "close", f"bot WIP, {behind} behind main, idle {age:.0f}d"
    if behind >= 10 and age >= 7:
        return "close", f"bot PR {behind} behind, idle {age:.0f}d"
    return "keep", "unique work still ahead of main"


def should_close_on_run(verdict: str, reason: str, apply: bool, close_zero_ahead: bool) -> bool:
    if verdict != "close":
        return False
    if apply:
        return True
    return close_zero_ahead and reason.startswith("superseded")
