"""Local Sense Lab tool stubs. Wired end-to-end; no remote side effects."""

from __future__ import annotations

from typing import Any

SHAPES = frozenset({"sphere", "box", "cylinder", "tower"})
PHYSICS = {
    "gravity": (0.0, 40.0, 9.8),
    "bounciness": (0.0, 1.0, 0.34),
    "friction": (0.0, 1.0, 0.62),
}
SOURCES = frozenset({"self", "world", "unknown"})


def spawn_shape(shape: str, count: int = 1) -> dict[str, Any]:
    kind = str(shape or "").strip().lower()
    if kind not in SHAPES:
        return {"ok": False, "error": f"unknown shape: {shape}"}
    n = 1
    try:
        n = int(count)
    except (TypeError, ValueError):
        n = 1
    n = max(1, min(n, 8))
    if kind == "tower":
        n = 1
    return {"ok": True, "tool": "spawn_shape", "shape": kind, "count": n}


def set_physics_param(name: str, value: float) -> dict[str, Any]:
    key = str(name or "").strip().lower()
    if key not in PHYSICS:
        return {"ok": False, "error": f"unknown param: {name}"}
    lo, hi, _default = PHYSICS[key]
    try:
        raw = float(value)
    except (TypeError, ValueError):
        return {"ok": False, "error": "value must be a number"}
    clamped = max(lo, min(hi, raw))
    return {
        "ok": True,
        "tool": "set_physics_param",
        "name": key,
        "value": clamped,
        "clamped": clamped != raw,
    }


def note_sensation_map(
    sensation: str,
    maps_to: str,
    source: str = "unknown",
    note: str = "",
) -> dict[str, Any]:
    sensation_s = str(sensation or "").strip()
    maps_to_s = str(maps_to or "").strip()
    if not sensation_s or not maps_to_s:
        return {"ok": False, "error": "sensation and maps_to are required"}
    src = str(source or "unknown").strip().lower()
    if src not in SOURCES:
        src = "unknown"
    line = str(note or "").strip()
    if len(line) > 240:
        line = line[:240]
    return {
        "ok": True,
        "tool": "note_sensation_map",
        "sensation": sensation_s,
        "maps_to": maps_to_s,
        "source": src,
        "note": line,
        "dictionary": "chat-only",
    }


HANDLERS = {
    "spawn_shape": spawn_shape,
    "set_physics_param": set_physics_param,
    "note_sensation_map": note_sensation_map,
}


def run_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    handler = HANDLERS.get(name)
    if handler is None:
        return {"ok": False, "error": f"unknown tool: {name}"}
    args = arguments or {}
    if not isinstance(args, dict):
        return {"ok": False, "error": "arguments must be an object"}
    try:
        return handler(**args)
    except TypeError as exc:
        return {"ok": False, "error": str(exc)}
