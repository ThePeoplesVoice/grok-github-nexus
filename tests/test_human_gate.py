"""Tests for the enforcing human-gate check."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nexus.gates import evaluate_human_gates, requires_human_gate, unmet_human_gates
from nexus.scripts import check_human_gate

ROOT = Path(__file__).resolve().parent.parent

RULES = {
    "rules": [
        {"id": "money", "match": ["payment", "stripe"], "requires": "human-approval:money", "why": "thumb"},
        {"id": "deploy", "match": ["deploy", "vercel"], "requires": "human-approval:deploy", "why": "users"},
        {"id": "public", "match": ["readme", "docs/"], "requires": "human-approval:public", "why": "voice"},
    ]
}


@pytest.fixture()
def gates(tmp_path: Path) -> Path:
    p = tmp_path / "gates.json"
    p.write_text(json.dumps(RULES), encoding="utf-8")
    return p


def _files(tmp_path: Path, *paths: str) -> Path:
    f = tmp_path / "changed.txt"
    f.write_text("\n".join(paths) + "\n", encoding="utf-8")
    return f


def test_reports_every_unmet_gate(gates: Path):
    paths = ["nexus/payments.py", "README.md", "nexus/providers.py"]
    unmet = unmet_human_gates(paths, [], path=gates)
    assert [r["requires"] for r in unmet] == ["human-approval:money", "human-approval:public"]
    assert unmet[0]["paths"] == ["nexus/payments.py"]


def test_partial_labels_leave_remaining_gate(gates: Path):
    paths = ["nexus/payments.py", "docs/KEY_SETUP.md"]
    unmet = unmet_human_gates(paths, ["Human-Approval:Money"], path=gates)
    assert [r["requires"] for r in unmet] == ["human-approval:public"]
    all_hits = evaluate_human_gates(paths, ["human-approval:money"], path=gates)
    assert [r["satisfied"] for r in all_hits] == [True, False]


def test_agrees_with_first_hit_helper(gates: Path):
    paths = ["vercel.json"]
    first = requires_human_gate(paths, [], path=gates)
    unmet = unmet_human_gates(paths, [], path=gates)
    assert first is not None and unmet[0]["rule"] == first


def test_check_fails_when_label_missing(tmp_path: Path, gates: Path, monkeypatch, capsys):
    monkeypatch.setenv("PR_LABELS_JSON", json.dumps(["automated"]))
    monkeypatch.delenv("PR_LABELS", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    rc = check_human_gate.main(["--files", str(_files(tmp_path, "README.md")), "--gates", str(gates)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "::error title=Human gate::Missing label `human-approval:public`" in out


def test_check_passes_when_label_present(tmp_path: Path, gates: Path, monkeypatch):
    monkeypatch.setenv("PR_LABELS_JSON", json.dumps(["human-approval:public"]))
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    rc = check_human_gate.main(["--files", str(_files(tmp_path, "README.md")), "--gates", str(gates)])
    assert rc == 0
    assert "✅ approved" in summary.read_text(encoding="utf-8")


def test_check_passes_when_no_gate_triggered(tmp_path: Path, gates: Path, monkeypatch):
    monkeypatch.setenv("PR_LABELS_JSON", "[]")
    rc = check_human_gate.main(["--files", str(_files(tmp_path, "nexus/providers.py")), "--gates", str(gates)])
    assert rc == 0


def test_check_fails_closed_on_missing_inputs(tmp_path: Path, gates: Path, monkeypatch):
    monkeypatch.delenv("CHANGED_FILES_PATH", raising=False)
    assert check_human_gate.main(["--gates", str(gates)]) == 2
    assert check_human_gate.main(["--files", str(tmp_path / "nope.txt"), "--gates", str(gates)]) == 2
    f = _files(tmp_path, "README.md")
    assert check_human_gate.main(["--files", str(f), "--gates", str(tmp_path / "missing.json")]) == 2


def test_label_parsing_accepts_json_and_csv():
    assert check_human_gate.parse_labels('["a", "b"]', None) == ["a", "b"]
    assert check_human_gate.parse_labels("not json", " c , ,d") == ["c", "d"]
    assert check_human_gate.parse_labels(None, None) == []


def test_repo_gates_config_covers_all_approval_labels():
    cfg = json.loads((ROOT / "config" / "gates.json").read_text(encoding="utf-8"))
    required = {r["requires"] for r in cfg["rules"]}
    assert required == set(cfg["approval_labels"])


def test_gate_workflow_reruns_on_label_changes_and_names_check():
    body = (ROOT / ".github" / "workflows" / "nexus-human-gate.yml").read_text(encoding="utf-8")
    for event in ("opened", "synchronize", "reopened", "labeled", "unlabeled"):
        assert event in body
    assert "name: human-gate" in body
    assert "python -m nexus.scripts.check_human_gate" in body
    assert "secrets." not in body


def test_required_test_check_runs_on_every_pr():
    body = (ROOT / ".github" / "workflows" / "nexus-tests.yml").read_text(encoding="utf-8")
    pr_block = body.split("pull_request:", 1)[1].split("workflow_dispatch:", 1)[0]
    assert "paths:" not in pr_block
