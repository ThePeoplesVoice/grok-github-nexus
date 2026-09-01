"""Persistent memory for the Nexus.

Survives runs. Records attempts, failures, corrections, and what worked.
The difference between an apprentice and a colleague: the colleague remembers.

See config/memory.json.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MEMORY_PATH = ROOT / "config" / "memory.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _defaults() -> dict[str, Any]:
    return {
        "version": "1.0.0",
        "description": "Persistent memory for the Nexus.",
        "updated_at": None,
        "entries": [],
        "notes": "Append via record_memory. Read via recent_memory.",
    }


def load_memory(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else MEMORY_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _defaults()
        base = _defaults()
        base.update(data)
        if not isinstance(base.get("entries"), list):
            base["entries"] = []
        return base
    except Exception:
        return _defaults()


def save_memory(data: dict[str, Any], path: str | Path | None = None) -> Path:
    target = Path(path) if path else MEMORY_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def record_memory(
    text: str,
    *,
    kind: str = "note",
    source: str = "system",
    tags: list[str] | None = None,
    meta: dict[str, Any] | None = None,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Append one memory entry. kind: attempt | failure | correction | success | note."""
    mem = load_memory(path)
    entry = {
        "ts": _utc_now(),
        "kind": (kind or "note").strip().lower(),
        "source": source,
        "text": text.strip(),
        "tags": tags or [],
        "meta": meta or {},
    }
    entries = mem.get("entries") or []
    entries.append(entry)
    # Keep the last 200 entries — enough to learn, small enough to stay cheap.
    mem["entries"] = entries[-200:]
    mem["updated_at"] = _utc_now()
    save_memory(mem, path)
    return entry


def recent_memory(n: int = 8, path: str | Path | None = None) -> list[dict[str, Any]]:
    mem = load_memory(path)
    entries = mem.get("entries") or []
    return entries[-n:]


def memory_block_for_prompt(n: int = 6, path: str | Path | None = None) -> str:
    """Compressed memory for inclusion in Complete/Pulse prompts."""
    notes = recent_memory(n, path)
    if not notes:
        return "_No memory yet — first run._"
    lines = []
    for e in notes:
        kind = e.get("kind") or "note"
        lines.append(f"- [{kind}] {e.get('text')}")
    return "\n".join(lines)
