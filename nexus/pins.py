"""One live pin per automated report family.

Pulse #155 stayed open after #171. Commit analysis #162 stayed open after
#170. The workflows meant to reuse a thread either created a second issue
or only closed same-day duplicates.

Policy a stranger can review:
- A family is identified by its required labels, which always include
  ``automated``.
- Among open issues that carry every required label, the newest
  ``created_at`` is the live pin.
- Older siblings close as completed, with a pointer at the live pin.
- Issues labelled keep / do-not-close / human are never closed here.
- Issues missing ``automated`` are never closed here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

KEEP_LABELS = frozenset({"keep", "do-not-close", "human"})

FAMILIES: dict[str, dict[str, Any]] = {
    "pulse": {
        "labels": ("nexus-pulse", "automated"),
        "title_prefix": "📡 Nexus Pulse",
    },
    "commit": {
        "labels": ("nexus-analysis", "automated"),
        "title_prefix": "🌌 Commit Analysis",
    },
    "self_audit": {
        "labels": ("self-audit", "nexus-optimisation", "automated"),
        "title_prefix": "Nexus Self-Audit",
    },
    "complete": {
        "labels": ("nexus-complete", "automated"),
        "title_prefix": "🧭 Nexus Complete Analysis",
    },
}


def family_spec(name: str) -> dict[str, Any]:
    key = (name or "").strip().lower()
    if key not in FAMILIES:
        known = ", ".join(sorted(FAMILIES))
        raise ValueError(f"unknown pin family {name!r} — expected one of: {known}")
    return FAMILIES[key]


def label_names(issue: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for item in issue.get("labels") or []:
        name = item.get("name") if isinstance(item, dict) else item
        if isinstance(name, str) and name.strip():
            out.add(name.strip().lower())
    return out


def has_labels(issue: dict[str, Any], required: tuple[str, ...] | list[str]) -> bool:
    names = label_names(issue)
    return all(label.lower() in names for label in required)


def is_protected(issue: dict[str, Any]) -> bool:
    names = label_names(issue)
    if "automated" not in names:
        return True
    return bool(names & KEEP_LABELS)


def _created_at(issue: dict[str, Any]) -> datetime:
    raw = issue.get("created_at") or ""
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _number(issue: dict[str, Any]) -> int:
    try:
        return int(issue.get("number") or 0)
    except (TypeError, ValueError):
        return 0


def partition_pins(
    issues: list[dict[str, Any]],
    required_labels: tuple[str, ...] | list[str],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Return (live_pin, superseded) for one family.

    Live pin is the newest matching unprotected issue. Protected issues
    stay out of both sides so a human keep-label is not auto-closed and
    does not steal the pin.
    """
    matching = [
        issue
        for issue in issues
        if has_labels(issue, required_labels) and not is_protected(issue)
    ]
    matching.sort(key=lambda issue: (_created_at(issue), _number(issue)), reverse=True)
    if not matching:
        return None, []
    return matching[0], matching[1:]


def pin_title(family: str, when: datetime | None = None) -> str:
    spec = family_spec(family)
    day = (when or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    return f"{spec['title_prefix']} — {day}"


def superseded_comment(live_number: int) -> str:
    return (
        f"Superseded by the live pin #{live_number}.\n\n"
        "Same automated family, newer report. Closed as consumed — not a failed run."
    )
