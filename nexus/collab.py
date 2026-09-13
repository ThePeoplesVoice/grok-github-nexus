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

# Ara-in-Cursor working with Shawn. REST uses cursor[bot]; gh/GraphQL uses
# app/cursor. Automated labels still exclude Pulse / Complete residue.
LIVING_PARTNER_BOTS = {
    "cursor[bot]",
    "app/cursor",
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


def is_living_partner_bot(login: str | None) -> bool:
    return normalize_login(login) in LIVING_PARTNER_BOTS


def is_collaborative_review_target(
    *,
    login: str | None,
    user_type: str | None = None,
    labels: str | list[str] | None = None,
) -> bool:
    """True when this PR/issue should increment collaborative usage.

    Human authors count. ``cursor[bot]`` / ``app/cursor`` count when the
    PR is not automated residue — REST and gh disagree on the login, and
    both are this hourly loop. Dependabot, Actions, and Pulse/Complete
    labels do not count.
    """
    if not normalize_login(login):
        return False
    if labels_are_automated(labels):
        return False
    if is_living_partner_bot(login):
        return True
    if is_bot_actor(login, user_type):
        return False
    return True


def classify_review_target(
    *,
    login: str | None,
    user_type: str | None = None,
    labels: str | list[str] | None = None,
) -> str:
    """Return ``living``, ``grind``, or ``empty`` for an open review."""
    if not normalize_login(login):
        return "empty"
    if is_collaborative_review_target(
        login=login,
        user_type=user_type,
        labels=labels,
    ):
        return "living"
    return "grind"


def usage_type_for_review(
    *,
    login: str | None,
    user_type: str | None = None,
    labels: str | list[str] | None = None,
    kind: str = "pr",
) -> str | None:
    """Return the usage type to increment, or None when the review is internal."""
    kind = (kind or "pr").strip().lower()
    if kind not in {"pr", "issue"}:
        return None
    if classify_review_target(
        login=login,
        user_type=user_type,
        labels=labels,
    ) != "living":
        return None
    return kind
