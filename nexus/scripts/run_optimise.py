#!/usr/bin/env python3
"""Local optimisation / integration runner.

Simulate → decide stale queue / holds. No external AI. No GitHub issues.
Never persists Astra, usage, or reputation. Queue write is opt-in.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from nexus import __version__
from nexus.field_notes import append_field_note
from nexus.optimise import apply_queue_refresh, format_optimisation_md, optimise
from nexus.simulate import reassess

REPORT_PATH = Path("/tmp/nexus_optimisation.md")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Optimise Nexus board from a dry-run simulation.",
    )
    parser.add_argument(
        "--apply-queue",
        action="store_true",
        help="Retire evidenced next[] items. Still never writes Astra or usage.",
    )
    parser.add_argument(
        "--note",
        action="store_true",
        help="Append one field note. Still does not write Astra or usage.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print the optimisation dict as JSON.",
    )
    args = parser.parse_args(argv)

    print(f"🔧 Nexus optimisation / integration — package v{__version__}")
    print("=" * 60)

    report = reassess()
    result = optimise(report)
    if args.apply_queue:
        apply_queue_refresh(result, persist=True)
        persisted = dict(result.get("persisted") or {})
        persisted["queue"] = True
        result["persisted"] = persisted

    body = format_optimisation_md(result)
    REPORT_PATH.write_text(body, encoding="utf-8")

    if args.as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(body)

    print(f"✅ Report at {REPORT_PATH}")
    persisted = result.get("persisted") or {}
    print(
        "Persistence: "
        f"astra={persisted.get('astra')} "
        f"usage={persisted.get('usage')} "
        f"queue={persisted.get('queue')} "
        f"issues={persisted.get('issues')}"
    )

    if args.note:
        note = append_field_note(
            f"Optimisation reassessment. {result.get('headline')}",
            source="optimisation",
            tags=["automated", "optimisation", "reassess"],
            meta={"package": __version__, "persisted": persisted},
        )
        print(f"📝 Field note appended @ {note['ts']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
