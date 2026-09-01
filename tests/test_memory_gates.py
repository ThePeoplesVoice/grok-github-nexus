"""Tests for nexus.memory and nexus.gates."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.gates import gate_summary, requires_human_gate
from nexus.memory import load_memory, memory_block_for_prompt, recent_memory, record_memory


def test_record_and_read_memory(tmp_path: Path):
    p = tmp_path / "memory.json"
    p.write_text(json.dumps({"version": "1.0.0", "entries": []}), encoding="utf-8")
    record_memory("tried X, failed", kind="failure", source="test", path=p)
    record_memory("corrected Y", kind="correction", source="test", path=p)
    notes = recent_memory(10, path=p)
    assert len(notes) == 2
    assert notes[-1]["kind"] == "correction"
    block = memory_block_for_prompt(10, path=p)
    assert "correction" in block
    assert "failed" in block


def test_memory_caps_at_200(tmp_path: Path):
    p = tmp_path / "memory.json"
    p.write_text(json.dumps({"version": "1.0.0", "entries": []}), encoding="utf-8")
    for i in range(250):
        record_memory(f"entry {i}", kind="note", source="test", path=p)
    assert len(load_memory(p)["entries"]) == 200


def test_gate_triggers_on_money_path(tmp_path: Path):
    gates = tmp_path / "gates.json"
    gates.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "id": "money",
                        "match": ["payment", "stripe"],
                        "requires": "human-approval:money",
                        "why": "thumb on payments",
                    }
                ],
                "approval_labels": ["human-approval:money"],
            }
        ),
        encoding="utf-8",
    )
    hit = requires_human_gate(["nexus/payments.py"], [], path=gates)
    assert hit is not None
    assert hit["requires"] == "human-approval:money"
    assert "human-approval:money" in gate_summary(hit)


def test_gate_clear_when_label_present(tmp_path: Path):
    gates = tmp_path / "gates.json"
    gates.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "id": "money",
                        "match": ["payment"],
                        "requires": "human-approval:money",
                        "why": "thumb",
                    }
                ],
                "approval_labels": ["human-approval:money"],
            }
        ),
        encoding="utf-8",
    )
    assert requires_human_gate(["nexus/payments.py"], ["human-approval:money"], path=gates) is None


def test_gate_ignores_unrelated_paths(tmp_path: Path):
    gates = tmp_path / "gates.json"
    gates.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "id": "money",
                        "match": ["payment"],
                        "requires": "human-approval:money",
                        "why": "thumb",
                    }
                ],
                "approval_labels": ["human-approval:money"],
            }
        ),
        encoding="utf-8",
    )
    assert requires_human_gate(["nexus/providers.py"], [], path=gates) is None
