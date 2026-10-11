"""Dev queue hygiene: next[] items that are finished or past their date drop out.

An item leaves next[] when it is already listed in done[], carries a terminal
``status`` (merged / done / closed / retired / expired), or its hold/expiry date
has passed. The date comes from an explicit ``expires`` / ``hold_until`` field,
or from an ``until-YYYY-MM-DD`` id / "until YYYY-MM-DD" title.

Retired items move to the top of done[] with the reason as evidence, so the
Dev Cycle issue never leads with a hold that ended weeks ago.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any

TERMINAL_STATUSES = frozenset({"merged", "done", "closed", "retired", "expired", "complete", "completed"})
DATE_KEYS = ("expires", "expires_at", "hold_until", "until")
_ID_UNTIL = re.compile(r"until-(\d{4}-\d{2}-\d{2})")
_TITLE_UNTIL = re.compile(r"\buntil\s+(?:[A-Za-z]+day\s+)?(\d{4}-\d{2}-\d{2})", re.IGNORECASE)


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def item_expiry(item: dict[str, Any]) -> date | None:
    for key in DATE_KEYS:
        found = _parse_date(item.get(key))
        if found:
            return found
    for pattern, text in ((_ID_UNTIL, item.get("id")), (_TITLE_UNTIL, item.get("title"))):
        match = pattern.search(text) if isinstance(text, str) else None
        if match:
            return _parse_date(match.group(1))
    return None


def retire_reason(item: dict[str, Any], *, today: date, done_ids: set[str]) -> str | None:
    """Why this next[] item should leave the queue, or None if it is still live."""
    if item.get("id") in done_ids:
        return "already in done"
    status = str(item.get("status") or "").strip().lower()
    if status in TERMINAL_STATUSES:
        return f"status {status}"
    expiry = item_expiry(item)
    if expiry and expiry < today:
        return f"hold/expiry {expiry.isoformat()} passed"
    return None


def retire_stale_items(queue: dict[str, Any], *, now: datetime | None = None) -> list[dict[str, Any]]:
    """Drop finished/expired items from queue['next'] in place; return what was retired."""
    today = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).date()
    done = [d for d in (queue.get("done") or []) if isinstance(d, dict)]
    done_ids = {d.get("id") for d in done}
    live: list[Any] = []
    retired: list[dict[str, Any]] = []
    for item in queue.get("next") or []:
        reason = retire_reason(item, today=today, done_ids=done_ids) if isinstance(item, dict) else None
        if reason is None:
            live.append(item)
            continue
        retired.append({**item, "retired_reason": reason})
        if item.get("id") not in done_ids:
            done.insert(0, {
                "id": item.get("id"),
                "title": item.get("title"),
                "completed": today.isoformat(),
                "evidence": f"auto-retired by dev cycle: {reason}",
            })
            done_ids.add(item.get("id"))
    queue["next"] = live
    queue["done"] = done
    return retired
