#!/usr/bin/env python3
"""Post an automated report onto one live pin and close older siblings.

Used by Pulse, Commit Analysis, Self-Audit, and Complete workflows.
Does not increment usage. Does not touch human issues.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests

from nexus.pins import (
    FAMILIES,
    family_spec,
    partition_pins,
    pin_title,
    superseded_comment,
)

API = "https://api.github.com"


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _list_open(owner: str, repo: str, labels: tuple[str, ...], token: str) -> list[dict]:
    params = {
        "state": "open",
        "labels": ",".join(labels),
        "per_page": 100,
        "sort": "created",
        "direction": "desc",
    }
    url = f"{API}/repos/{owner}/{repo}/issues"
    resp = requests.get(url, headers=_headers(token), params=params, timeout=30)
    resp.raise_for_status()
    return [item for item in resp.json() if "pull_request" not in item]


def _comment(owner: str, repo: str, number: int, body: str, token: str) -> None:
    url = f"{API}/repos/{owner}/{repo}/issues/{number}/comments"
    resp = requests.post(url, headers=_headers(token), json={"body": body}, timeout=30)
    resp.raise_for_status()


def _close(owner: str, repo: str, number: int, token: str) -> None:
    url = f"{API}/repos/{owner}/{repo}/issues/{number}"
    resp = requests.patch(
        url,
        headers=_headers(token),
        json={"state": "closed", "state_reason": "completed"},
        timeout=30,
    )
    resp.raise_for_status()


def _create(
    owner: str,
    repo: str,
    title: str,
    body: str,
    labels: tuple[str, ...],
    token: str,
) -> dict:
    url = f"{API}/repos/{owner}/{repo}/issues"
    resp = requests.post(
        url,
        headers=_headers(token),
        json={"title": title, "body": body, "labels": list(labels)},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pin an automated Nexus report to one issue.")
    parser.add_argument("--family", required=True, choices=sorted(FAMILIES))
    parser.add_argument("--body", required=True, help="Path to the markdown report")
    args = parser.parse_args(argv)

    spec = family_spec(args.family)
    labels = tuple(spec["labels"])

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    repo_full = os.environ.get("GITHUB_REPOSITORY") or ""
    if not token or "/" not in repo_full:
        print("⚠️ GITHUB_TOKEN or GITHUB_REPOSITORY missing — pin skipped")
        return 0

    owner, repo = repo_full.split("/", 1)
    body_path = Path(args.body)
    if body_path.is_file():
        body = body_path.read_text(encoding="utf-8")
    else:
        body = (
            f"Report file missing at `{args.body}`.\n\n"
            "Workflow still pinned so the family does not fork a new thread. See Actions logs."
        )
        print(f"⚠️ body file missing: {body_path}")

    issues = _list_open(owner, repo, labels, token)
    live, superseded = partition_pins(issues, labels)

    if live is None:
        created = _create(owner, repo, pin_title(args.family), body, labels, token)
        print(f"✅ created live {args.family} pin #{created.get('number')}")
        return 0

    live_number = int(live["number"])
    _comment(owner, repo, live_number, body, token)
    print(f"✅ posted {args.family} report onto #{live_number}")

    for issue in superseded:
        number = int(issue["number"])
        try:
            _comment(owner, repo, number, superseded_comment(live_number), token)
            _close(owner, repo, number, token)
            print(f"✅ closed superseded #{number} → #{live_number}")
        except Exception as exc:
            print(f"⚠️ could not close #{number}: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
