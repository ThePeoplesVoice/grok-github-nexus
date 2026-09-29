#!/usr/bin/env python3
"""Fail a PR check while a required human-approval label is missing.

Inputs:
  --files PATH    newline-separated changed paths (default: $CHANGED_FILES_PATH)
  --gates PATH    gates config (default: $GATES_PATH, else config/gates.json)
  PR_LABELS_JSON  JSON list of label names on the PR (from the event payload)
  PR_LABELS       fallback: comma-separated label names

Exit codes: 0 = no gate triggered or all satisfied, 1 = a label is missing,
2 = inputs unreadable (fails closed).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from nexus.gates import evaluate_human_gates


def parse_labels(raw_json: str | None, raw_csv: str | None) -> list[str]:
    labels: list[str] = []
    if raw_json and raw_json.strip():
        try:
            data = json.loads(raw_json)
            if isinstance(data, list):
                labels.extend(str(x) for x in data if x is not None)
        except json.JSONDecodeError:
            pass
    if raw_csv:
        labels.extend(part for part in raw_csv.split(","))
    return [l.strip() for l in labels if l and l.strip()]


def read_paths(path: str) -> list[str]:
    text = Path(path).read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip()]


def render(results: list[dict], labels: list[str], n_files: int) -> str:
    lines = ["## 🚧 Human gate", ""]
    lines.append(f"Changed files checked: {n_files}. Labels on PR: "
                 + (", ".join(f"`{l}`" for l in labels) if labels else "none") + ".")
    lines.append("")
    if not results:
        lines.append("No human gate triggered.")
        return "\n".join(lines) + "\n"
    lines.append("| Gate | Required label | Status | Matching paths |")
    lines.append("| --- | --- | --- | --- |")
    for r in results:
        shown = ", ".join(f"`{p}`" for p in r["paths"][:5])
        if len(r["paths"]) > 5:
            shown += f" … (+{len(r['paths']) - 5})"
        status = "✅ approved" if r["satisfied"] else "❌ missing"
        lines.append(f"| {r['rule'].get('id')} | `{r['requires']}` | {status} | {shown} |")
    missing = [r for r in results if not r["satisfied"]]
    lines.append("")
    if missing:
        lines.append("Add the missing label(s). This check re-runs when labels change.")
    else:
        lines.append("All triggered gates carry their approval label.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--files", default=os.environ.get("CHANGED_FILES_PATH", ""))
    ap.add_argument("--gates", default=os.environ.get("GATES_PATH", ""))
    args = ap.parse_args(argv)

    if not args.files:
        print("::error title=Human gate::No changed-files list given; failing closed.")
        return 2
    try:
        paths = read_paths(args.files)
    except OSError as e:
        print(f"::error title=Human gate::Cannot read changed files ({e}); failing closed.")
        return 2

    gates_path = args.gates or None
    if gates_path and not Path(gates_path).is_file():
        print(f"::error title=Human gate::Gates config not found at {gates_path}; failing closed.")
        return 2

    labels = parse_labels(os.environ.get("PR_LABELS_JSON"), os.environ.get("PR_LABELS"))
    results = evaluate_human_gates(paths, labels, path=gates_path)
    report = render(results, labels, len(paths))
    print(report)

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        try:
            with open(summary, "a", encoding="utf-8") as fh:
                fh.write(report)
        except OSError:
            pass

    missing = [r for r in results if not r["satisfied"]]
    for r in missing:
        why = r["rule"].get("why") or "see config/gates.json"
        print(f"::error title=Human gate::Missing label `{r['requires']}` "
              f"(gate: {r['rule'].get('id')}). {why}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
