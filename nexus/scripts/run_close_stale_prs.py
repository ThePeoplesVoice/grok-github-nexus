#!/usr/bin/env python3
"""Close stale / superseded pull requests.

Default: dry-run report + auto-close only PRs with 0 commits ahead of main.
APPLY=true: also close noisy bot WIP idle ≥ 3 days.

Writes config/stale_prs.json. Does not touch STATUS.md / README.md.
Human PRs and keep-labeled PRs are never closed.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from nexus.analyze import utc_now_str
from nexus.stale import classify, should_close_on_run

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_JSON = ROOT / "config" / "stale_prs.json"
MAX_CLOSE = 40


def _env_flag(name: str, default: bool = False) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _gh(path: str, token: str, method: str = "GET", body: dict | None = None):
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "nexus-stale-prs",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        data=data,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(req, timeout=12) as res:
        raw = res.read().decode()
        return json.loads(raw) if raw else {}


def _list_open_pulls(repo: str, token: str) -> list[dict]:
    items: list[dict] = []
    page = 1
    while page <= 5:
        batch = _gh(f"/repos/{repo}/pulls?state=open&per_page=50&page={page}", token)
        if not isinstance(batch, list) or not batch:
            break
        items.extend(batch)
        if len(batch) < 50:
            break
        page += 1
    return items


def _compare(repo: str, token: str, base: str, head: str) -> dict:
    spec = urllib.parse.quote(f"{base}...{head}", safe="")
    try:
        return _gh(f"/repos/{repo}/compare/{spec}", token)
    except Exception as e:
        # Fail closed toward keep: pretend the PR is still uniquely ahead.
        return {"error": str(e), "ahead_by": 1, "behind_by": 0}


def main() -> None:
    token = (os.environ.get("GITHUB_TOKEN") or "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY") or "ThePeoplesVoice/grok-github-nexus"
    apply = _env_flag("APPLY", False)
    close_zero = _env_flag("CLOSE_ZERO_AHEAD", True)
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")

    print(f"🧹 Stale PR sweep — apply={apply} close_zero_ahead={close_zero}")
    pulls = _list_open_pulls(repo, token)
    now = datetime.now(timezone.utc)
    classified: list[dict] = []
    closed: list[dict] = []
    kept: list[dict] = []

    for pr in pulls:
        number = pr.get("number")
        head_ref = (pr.get("head") or {}).get("ref") or ""
        head_full = (pr.get("head") or {}).get("label") or head_ref
        base = (pr.get("base") or {}).get("ref") or "main"
        compare = _compare(repo, token, base, head_full or head_ref)
        verdict, reason = classify(pr, compare, now=now)
        row = {
            "number": number,
            "title": pr.get("title"),
            "html_url": pr.get("html_url"),
            "user": ((pr.get("user") or {}).get("login")),
            "head": head_ref,
            "ahead_by": compare.get("ahead_by"),
            "behind_by": compare.get("behind_by"),
            "verdict": verdict,
            "reason": reason,
        }
        classified.append(row)
        will_close = should_close_on_run(verdict, reason, apply, close_zero)
        if not will_close:
            kept.append(row)
            print(f"  keep  #{number} — {reason}")
            continue
        if len(closed) >= MAX_CLOSE:
            print(f"  skip  #{number} — max {MAX_CLOSE} closes this run")
            kept.append(row)
            continue
        comment = (
            f"Closing as {reason}. "
            "The Nexus stale sweeper does not merge. "
            "Reopen if this still has unique work, or add the `keep` label."
        )
        try:
            _gh(
                f"/repos/{repo}/issues/{number}/comments",
                token,
                method="POST",
                body={"body": comment},
            )
            _gh(
                f"/repos/{repo}/pulls/{number}",
                token,
                method="PATCH",
                body={"state": "closed"},
            )
            closed.append(row)
            print(f"  close #{number} — {reason}")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, Exception) as e:
            print(f"  fail  #{number} — {e}")
            kept.append({**row, "reason": f"close failed: {e}"})

    remaining = [
        c
        for c in classified
        if c["verdict"] == "close" and c not in closed
    ]
    payload = {
        "version": "1.0.0",
        "generated_at": utc_now_str(),
        "dry_run": not apply,
        "apply": apply,
        "open_scanned": len(pulls),
        "closed_count": len(closed),
        "kept_count": len(kept),
        "remaining_count": len(remaining),
        "candidates": remaining,
        "closed": closed,
        "kept": [
            {"number": k["number"], "title": k["title"], "reason": k["reason"]}
            for k in kept[:20]
        ],
        "notes": "Human PRs and keep-labeled PRs are never closed. STATUS.md / README.md untouched.",
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"✅ wrote {OUT_JSON} scanned={len(pulls)} closed={len(closed)} remaining={len(remaining)}")

    lines = [
        f"# 🧹 Nexus Stale PRs — {payload['generated_at']}",
        "",
        f"**Scanned:** {len(pulls)} open  ",
        f"**Closed:** {len(closed)}  ",
        f"**Kept:** {len(kept)}  ",
        f"**Remaining close-candidates:** {len(remaining)}  ",
        f"**Apply:** {apply}",
        "",
        "## Closed",
        "",
    ]
    if closed:
        for c in closed:
            lines.append(f"- #{c['number']} {c['title']} — {c['reason']}")
    else:
        lines.append("_None this run._")
    lines += ["", "## Remaining close-candidates", ""]
    if remaining:
        for c in remaining:
            lines.append(f"- #{c['number']} {c['title']} — {c['reason']}")
        lines.append("")
        lines.append("Dispatch with **apply** to close noisy bot WIP as well as fully superseded PRs.")
    else:
        lines.append("_None._")
    lines += [
        "",
        "Human PRs and anything labeled `keep` / `do-not-close` / `human` stay open.",
        "The sweeper never merges and never rewrites STATUS.md or README.md.",
    ]
    Path("/tmp/nexus_stale.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:40]))


if __name__ == "__main__":
    main()
