"""Collaborative-evidence helpers.

PR and issue analyses only count toward unlock when the target is a
living human review — not bot WIP, not automated pulse/audit residue.
"""

from __future__ import annotations

AUTOMATED_LABELS = {
    "automated",
    "nexus-complete",
    "nexus-pulse",
    "nexus-dev-cycle",
    "nexus-analysis",
    "self-audit",
    "nexus-optimisation",
}

BOT_LOGINS = {
    "github-actions[bot]",
    "copilot",
    "copilot-swe-agent[bot]",
    "dependabot[bot]",
    "nexus-bot",
}


def normalize_login(login: str | None) -> str:
    return (login or "").strip().lower()


def parse_label_list(raw: str | list[str] | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return [part.strip() for part in str(raw).split(",") if part.strip()]


def is_bot_actor(login: str | None, user_type: str | None = None) -> bool:
    name = normalize_login(login)
    if (user_type or "").strip().lower() == "bot":
        return True
    if name.endswith("[bot]"):
        return True
    return name in BOT_LOGINS


def labels_are_automated(labels: str | list[str] | None) -> bool:
    names = {item.lower() for item in parse_label_list(labels)}
    return bool(names & AUTOMATED_LABELS)


def is_collaborative_review_target(
    *,
    login: str | None,
    user_type: str | None = None,
    labels: str | list[str] | None = None,
) -> bool:
    """True when this PR/issue should increment collaborative usage."""
    if is_bot_actor(login, user_type):
        return False
    if labels_are_automated(labels):
        return False
    return True
