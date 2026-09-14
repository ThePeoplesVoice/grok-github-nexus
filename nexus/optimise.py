"""Optimisation and integration on top of local simulation.

Consume observe → simulate → recommend, then:
- tell living partner reviews from grind bots
- flag stale queue items that already landed
- never persist Astra, usage, or reputation

This is the hourly integration surface. Simulate thinks.
Optimise decides what still belongs on the board.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .collab import classify_review_target, parse_label_list
from .simulate import reassess

ROOT = Path(__file__).resolve().parent.parent
QUEUE_PATH = ROOT / "config" / "dev_queue.json"
STATUS_PATH = ROOT / "STATUS.md"

# Queue ids that local evidence can retire without inventing new work.
LANDED_EVIDENCE = {
    "land-status-sync-2026-09-13": {
        "file": "STATUS.md",
        "needle": "#171",
        "evidence": "STATUS.md pins Pulse #171; merged as #172",
    },
}


def utc_now_iso(now: datetime | None = None) -> str:
    stamp = now or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_queue(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else QUEUE_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {"version": "1.0.0", "done": [], "next": [], "backlog": []}


def detect_stale_next(
    queue: dict[str, Any] | None = None,
    *,
    root: Path | None = None,
) -> list[dict[str, Any]]:
    """Return next[] items whose landing evidence is already on disk."""
    data = queue if queue is not None else load_queue()
    base = root if root is not None else ROOT
    stale: list[dict[str, Any]] = []
    for item in data.get("next") or []:
        if not isinstance(item, dict):
            continue
        spec = LANDED_EVIDENCE.get(str(item.get("id") or ""))
        if not spec:
            continue
        target = base / spec["file"]
        try:
            text = target.read_text(encoding="utf-8")
        except Exception:
            continue
        if spec["needle"] in text:
            stale.append({
                "id": item.get("id"),
                "title": item.get("title"),
                "evidence": spec["evidence"],
                "stance": "retire",
            })
    return stale


def headline(
    report: dict[str, Any],
    stale: list[dict[str, Any]] | None = None,
    *,
    next_move: dict[str, Any] | None = None,
    living_count: int | None = None,
) -> str:
    obs = report.get("observation") or {}
    card = obs.get("scorecard") or {}
    lag = obs.get("astra_lag") or {}
    gate = report.get("expansion_gate") or {}
    actions = report.get("recommendations") or []
    top_act = next((a for a in actions if a.get("stance") == "act"), actions[0] if actions else {})
    move_id = (next_move or {}).get("id") or top_act.get("id")
    stale_ids = ",".join(str(item.get("id")) for item in (stale or []) if item.get("id")) or "none"
    living = "" if living_count is None else f" living_open={living_count}"
    move_n = (next_move or {}).get("number")
    if move_n:
        living += f" land=#{move_n}"
    superseded = (next_move or {}).get("superseded") or []
    if superseded:
        living += " close=" + ",".join(f"#{item}" for item in superseded)
    return (
        f"gate={gate.get('recommendation')} "
        f"unlock={card.get('unlock_score')} "
        f"astra_lag={lag.get('lagging')} "
        f"top_act={move_id} "
        f"stale_queue={stale_ids}{living}"
    )


def _review_login(raw: dict[str, Any]) -> str | None:
    if raw.get("login"):
        return raw.get("login")
    author = raw.get("author")
    if isinstance(author, dict):
        return author.get("login")
    return None


def review_number(row: dict[str, Any] | None) -> int:
    """Best-effort PR number. Unknown or unparsable values sort last."""
    if not isinstance(row, dict):
        return 0
    raw = row.get("number")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def rank_living_reviews(
    living: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Newest PR number is current. Older living drafts are superseded."""
    rows = [item for item in (living or []) if isinstance(item, dict)]
    ordered = sorted(rows, key=review_number, reverse=True)
    current = ordered[0] if ordered else None
    superseded = ordered[1:] if len(ordered) > 1 else []
    return {
        "current": current,
        "superseded": superseded,
        "ordered": ordered,
        "current_number": review_number(current) or None,
        "superseded_numbers": [
            review_number(item) for item in superseded if review_number(item)
        ],
    }


def superseded_close_actions(
    board: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Recommend closing older living drafts once a newer increment exists."""
    ranked = (board or {}).get("ranked") or rank_living_reviews(
        (board or {}).get("living")
    )
    current = ranked.get("current") or {}
    current_n = review_number(current) or ranked.get("current_number")
    actions: list[dict[str, Any]] = []
    for item in ranked.get("superseded") or []:
        number = review_number(item)
        if not number:
            continue
        actions.append({
            "id": f"close-superseded-living-pr-{number}",
            "title": f"Close superseded living draft #{number}",
            "stance": "retire",
            "leverage": "high",
            "why": (
                f"#{number} is an older living partner draft. "
                f"Land #{current_n}; close #{number}. Do not open another."
            ),
            "number": number,
            "superseded_by": current_n,
        })
    return actions


def observe_open_reviews(
    reviews: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Classify an injected snapshot of open PRs. No network."""
    living: list[dict[str, Any]] = []
    grind: list[dict[str, Any]] = []
    for raw in reviews or []:
        if not isinstance(raw, dict):
            continue
        login = _review_login(raw)
        user_type = raw.get("user_type") or raw.get("author_type")
        author = raw.get("author") if isinstance(raw.get("author"), dict) else {}
        if user_type is None and author.get("is_bot") is not None:
            user_type = "Bot" if author.get("is_bot") else "User"
        raw_labels = raw.get("labels")
        if isinstance(raw_labels, list):
            labels = [
                str((item or {}).get("name") if isinstance(item, dict) else item)
                for item in raw_labels
                if str((item or {}).get("name") if isinstance(item, dict) else item).strip()
            ]
        else:
            labels = parse_label_list(raw_labels)
        kind = classify_review_target(
            login=login,
            user_type=user_type,
            labels=labels,
        )
        row = {
            "number": raw.get("number"),
            "title": raw.get("title"),
            "login": login,
            "user_type": user_type,
            "labels": labels,
            "draft": bool(raw.get("draft") or raw.get("isDraft")),
            "class": kind,
        }
        if kind == "living":
            living.append(row)
        elif kind == "grind":
            grind.append(row)
    ranked = rank_living_reviews(living)
    current = ranked.get("current")
    superseded = ranked.get("superseded") or []
    if current:
        advice = (
            f"Land current living PR #{current.get('number')}. "
            "Do not open another."
        )
        if superseded:
            nums = ", ".join(
                f"#{item.get('number')}" for item in superseded if item.get("number")
            )
            advice += f" Close superseded {nums}."
    else:
        advice = "No living PR is open. One reviewable partner PR is the unlock path."
    return {
        "living_count": len(living),
        "grind_count": len(grind),
        "superseded_count": len(superseded),
        "living": living,
        "grind": grind,
        "ranked": ranked,
        "current": current,
        "superseded": superseded,
        "advice": advice,
    }


def choose_next_move(
    report: dict[str, Any],
    reviews: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pick the single board move. The newest living PR beats opening another."""
    board = reviews if reviews is not None else observe_open_reviews([])
    ranked = board.get("ranked") or rank_living_reviews(board.get("living") or [])
    current = board.get("current") or ranked.get("current")
    superseded = board.get("superseded") or ranked.get("superseded") or []
    if current:
        number = current.get("number")
        draft = bool(current.get("draft"))
        title = "Ready draft living PR" if draft else "Land open living PR"
        if number:
            title += f" #{number}"
        extra = ""
        if superseded:
            nums = ", ".join(
                f"#{item.get('number')}" for item in superseded if item.get("number")
            )
            extra = f" Close superseded {nums}."
        return {
            "id": "land-open-living-pr",
            "title": title,
            "stance": "act",
            "leverage": "high",
            "why": (
                f"Living partner PR #{number} is the current increment"
                f"{' (draft)' if draft else ''}. "
                "Opening another is grind. Review and land this one."
                f"{extra}"
            ),
            "number": number,
            "draft": draft,
            "superseded": [
                item.get("number") for item in superseded if item.get("number")
            ],
        }
    actions = report.get("recommendations") or []
    return next(
        (item for item in actions if item.get("stance") == "act"),
        actions[0] if actions else {
            "id": "hold",
            "title": "Hold",
            "stance": "hold",
            "leverage": "low",
            "why": "No ranked action.",
        },
    )


def discover_open_reviews() -> list[dict[str, Any]]:
    """Optional read-only `gh pr list`. Soft-fails to empty. Never files issues."""
    import subprocess

    try:
        proc = subprocess.run(
            [
                "gh",
                "pr",
                "list",
                "--state",
                "open",
                "--json",
                "number,title,author,labels,isDraft",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if proc.returncode != 0:
            return []
        rows = json.loads(proc.stdout or "[]")
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        author = row.get("author") or {}
        labels = row.get("labels") or []
        label_names = []
        for lab in labels:
            if isinstance(lab, dict):
                label_names.append(str(lab.get("name") or ""))
            else:
                label_names.append(str(lab))
        login = author.get("login") if isinstance(author, dict) else None
        is_bot = bool(author.get("is_bot")) if isinstance(author, dict) else False
        if str(login or "").endswith("[bot]"):
            is_bot = True
        out.append({
            "number": row.get("number"),
            "title": row.get("title"),
            "login": login,
            "user_type": "Bot" if is_bot else "User",
            "labels": label_names,
            "draft": bool(row.get("isDraft")),
        })
    return out


def optimise(
    report: dict[str, Any] | None = None,
    *,
    queue: dict[str, Any] | None = None,
    open_reviews: list[dict[str, Any]] | None = None,
    discover: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Rank simulation output and queue drift. Read-only on living meters.

    ``open_reviews=None`` plus ``discover=True`` calls read-only ``gh pr list``.
    Tests pass an explicit list (including ``[]``) so they stay offline.
    """
    assessed = report if report is not None else reassess(now=now)
    board = queue if queue is not None else load_queue()
    stale = detect_stale_next(board)
    snapshot = open_reviews
    if snapshot is None and discover:
        snapshot = discover_open_reviews()
    reviews = observe_open_reviews(snapshot or [])
    move = choose_next_move(assessed, reviews)
    actions = list(assessed.get("recommendations") or [])
    if reviews.get("living"):
        rewritten: list[dict[str, Any]] = []
        replaced = False
        for item in actions:
            if item.get("id") == "one-living-collaborative-pr":
                rewritten.append(move)
                replaced = True
            else:
                rewritten.append(item)
        if not replaced:
            rewritten.insert(0, move)
        actions = rewritten
    decisions = []
    for item in stale:
        decisions.append({
            "id": f"retire-{item.get('id')}",
            "title": f"Retire landed queue item `{item.get('id')}`",
            "stance": "retire",
            "leverage": "medium",
            "why": item.get("evidence"),
        })
    decisions.extend(superseded_close_actions(reviews))
    decisions.extend(actions)
    return {
        "observed_at": assessed.get("observed_at"),
        "headline": headline(
            assessed,
            stale,
            next_move=move,
            living_count=reviews.get("living_count"),
        ),
        "expansion_gate": assessed.get("expansion_gate"),
        "stale_queue": stale,
        "open_reviews": reviews,
        "next_move": move,
        "decisions": decisions,
        "persisted": {
            "astra": False,
            "usage": False,
            "reputation": False,
            "issues": False,
            "queue": False,
        },
    }


def apply_queue_refresh(
    optimisation: dict[str, Any],
    *,
    queue: dict[str, Any] | None = None,
    path: str | Path | None = None,
    persist: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Move evidenced next[] items to done. Never writes Astra or usage."""
    data = copy_queue(queue if queue is not None else load_queue())
    stale_ids = {item.get("id") for item in optimisation.get("stale_queue") or []}
    kept: list[dict[str, Any]] = []
    done = list(data.get("done") or [])
    done_ids = {item.get("id") for item in done if isinstance(item, dict)}
    for item in data.get("next") or []:
        if not isinstance(item, dict):
            continue
        if item.get("id") in stale_ids and item.get("id") not in done_ids:
            done.insert(0, {
                "id": item.get("id"),
                "title": item.get("title"),
                "completed": utc_now_iso(now)[:10],
                "evidence": next(
                    (
                        row.get("evidence")
                        for row in (optimisation.get("stale_queue") or [])
                        if row.get("id") == item.get("id")
                    ),
                    "landed",
                ),
            })
            done_ids.add(item.get("id"))
        elif item.get("id") not in stale_ids:
            kept.append(item)
    data["done"] = done
    data["next"] = kept
    data["updated_at"] = utc_now_iso(now)
    if persist:
        target = Path(path) if path else QUEUE_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        persisted = dict(optimisation.get("persisted") or {})
        persisted["queue"] = True
        optimisation = {**optimisation, "persisted": persisted}
    return data


def copy_queue(queue: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(queue))


def format_optimisation_md(optimisation: dict[str, Any]) -> str:
    gate = optimisation.get("expansion_gate") or {}
    persisted = optimisation.get("persisted") or {}
    move = optimisation.get("next_move") or {}
    reviews = optimisation.get("open_reviews") or {}
    stale_lines = []
    for item in optimisation.get("stale_queue") or []:
        stale_lines.append(
            f"- `{item.get('id')}` — {item.get('evidence')}"
        )
    decision_lines = []
    for item in optimisation.get("decisions") or []:
        decision_lines.append(
            f"- **{item.get('stance')}** `{item.get('id')}` "
            f"(leverage {item.get('leverage')}): {item.get('title')} "
            f"— {item.get('why')}"
        )
    living_lines = []
    current_n = ((reviews.get("current") or {}).get("number"))
    superseded_nums = {
        item.get("number") for item in (reviews.get("superseded") or [])
    }
    for item in reviews.get("living") or []:
        marker = "current" if item.get("number") == current_n else (
            "superseded" if item.get("number") in superseded_nums else "living"
        )
        living_lines.append(
            f"- {marker} #{item.get('number')} `{item.get('login')}` "
            f"{'(draft) ' if item.get('draft') else ''}— {item.get('title')}"
        )
    for item in reviews.get("grind") or []:
        living_lines.append(
            f"- grind #{item.get('number')} `{item.get('login')}` — {item.get('title')}"
        )
    return f"""# 🔧 Nexus Optimisation / Integration

**Observed:** {optimisation.get('observed_at')}  
**Headline:** {optimisation.get('headline')}  
**Expansion gate:** {gate.get('recommendation')} — {gate.get('reason')}

## Next move

- **{move.get('stance')}** `{move.get('id')}` — {move.get('title')} — {move.get('why')}

## Open reviews

{chr(10).join(living_lines) or '- (none injected)'}
- {reviews.get('advice') or 'No open-review snapshot.'}

## Stale queue items

{chr(10).join(stale_lines) or '- (none)'}

## Decisions

{chr(10).join(decision_lines) or '- (none)'}

## Persistence

Astra written: {persisted.get('astra')} · usage written: {persisted.get('usage')} · queue written: {persisted.get('queue')} · issues filed: {persisted.get('issues')}

See `AUTOMATED_DEVELOPMENT.md`. Optimise the board. Do not hand-edit Astra.
"""
