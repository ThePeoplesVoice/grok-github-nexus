"""Append-only field notes for Nexus continuity.

Lightweight durable memory. Not a chat log. Not a scoreboard.
See ORGANIC_SYSTEMS.md and AUTOMATED_DEVELOPMENT.md.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
NOTES_PATH = ROOT / "config" / "field_notes.jsonl"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_field_note(
    text: str,
    *,
    source: str = "dev_cycle",
    tags: list[str] | None = None,
    meta: dict[str, Any] | None = None,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Append one JSONL note. Returns the note dict."""
    target = Path(path) if path else NOTES_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    note = {
        "ts": utc_now_iso(),
        "source": source,
        "text": text.strip(),
        "tags": tags or [],
        "meta": meta or {},
    }
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(note, ensure_ascii=False) + "\n")
    return note


def read_recent_notes(n: int = 10, path: str | Path | None = None) -> list[dict[str, Any]]:
    target = Path(path) if path else NOTES_PATH
    if not target.exists():
        return []
    lines = target.read_text(encoding="utf-8").splitlines()
    notes: list[dict[str, Any]] = []
    for line in lines[-n:]:
        line = line.strip()
        if not line:
            continue
        try:
            notes.append(json.loads(line))
        except Exception:
            continue
    return notes


def notes_summary_md(n: int = 5) -> str:
    notes = read_recent_notes(n)
    if not notes:
        return "_No field notes yet._"
    parts = []
    for note in notes:
        tags = ", ".join(note.get("tags") or []) or "—"
        parts.append(
            f"- **{note.get('ts')}** ({note.get('source')}) [{tags}]: {note.get('text')}"
        )
    return "\n".join(parts)
