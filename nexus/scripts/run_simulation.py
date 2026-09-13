#!/usr/bin/env python3
"""Local analysis / simulation / optimisation runner.

Observe → simulate → recommend. No external AI. No GitHub issues.
Never persists Astra, usage, or reputation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from nexus import __version__
from nexus.field_notes import append_field_note
from nexus.simulate import format_report_md, reassess

REPORT_PATH = Path("/tmp/nexus_simulation.md")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reassess Nexus instruments without writing living files.",
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
        help="Print the reassessment dict as JSON.",
    )
    args = parser.parse_args(argv)

    print(f"🧪 Nexus simulation / reassessment — package v{__version__}")
    print("=" * 60)

    report = reassess()
    body = format_report_md(report)
    REPORT_PATH.write_text(body, encoding="utf-8")

    if args.as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(body)

    print(f"✅ Report at {REPORT_PATH}")
    persisted = report.get("persisted") or {}
    print(
        "Persistence: "
        f"astra={persisted.get('astra')} "
        f"usage={persisted.get('usage')} "
        f"issues={persisted.get('issues')}"
    )

    if args.note:
        obs = report.get("observation") or {}
        card = obs.get("scorecard") or {}
        gate = report.get("expansion_gate") or {}
        top = (report.get("recommendations") or [{}])[0]
        note = append_field_note(
            (
                f"Simulation reassessment. health={obs.get('health', {}).get('score')} "
                f"analyses={card.get('usage_total')} unlock={card.get('unlock_score')} "
                f"astra_lag={obs.get('astra_lag', {}).get('lagging')} "
                f"gate={gate.get('recommendation')} top={top.get('id')}"
            ),
            source="simulation",
            tags=["automated", "simulation", "reassess"],
            meta={"package": __version__, "persisted": persisted},
        )
        print(f"📝 Field note appended @ {note['ts']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
