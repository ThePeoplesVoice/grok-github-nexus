"""Tests for nexus.context domain pack loading helpers."""

import json
from pathlib import Path

import pytest

from nexus.context import domain_pack_summary, load_domain_packs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_pack(dir_: Path, pid: str, data: dict) -> Path:
    p = dir_ / f"{pid}.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


SAMPLE_CONSTRUCTION = {
    "id": "wa_construction",
    "name": "WA Construction",
    "description": "Perth Hills quoting context.",
    "voice": "Grounded and practical.",
    "analysis_hints": ["Flag missing GST.", "Challenge rural site prep costs."],
}

SAMPLE_SANCTUARY = {
    "id": "keysbrook_sanctuary",
    "name": "Keysbrook Sanctuary",
    "description": "Jarrah forest restoration vision.",
    "voice": "Reverent and practical.",
    "analysis_hints": ["Preserve hollow-bearing marri.", "Long horizon thinking."],
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_load_all_packs_from_directory(tmp_path):
    _write_pack(tmp_path, "wa_construction", SAMPLE_CONSTRUCTION)
    _write_pack(tmp_path, "keysbrook_sanctuary", SAMPLE_SANCTUARY)

    packs = load_domain_packs(domain_dir=tmp_path)

    assert set(packs.keys()) == {"wa_construction", "keysbrook_sanctuary"}
    assert packs["wa_construction"]["name"] == "WA Construction"
    assert packs["keysbrook_sanctuary"]["name"] == "Keysbrook Sanctuary"


def test_load_specific_pack_ids(tmp_path):
    _write_pack(tmp_path, "wa_construction", SAMPLE_CONSTRUCTION)
    _write_pack(tmp_path, "keysbrook_sanctuary", SAMPLE_SANCTUARY)

    packs = load_domain_packs(pack_ids=["wa_construction"], domain_dir=tmp_path)

    assert "wa_construction" in packs
    assert "keysbrook_sanctuary" not in packs


def test_missing_directory_returns_empty():
    packs = load_domain_packs(domain_dir="/nonexistent/path/abc")
    assert packs == {}


def test_malformed_json_skipped(tmp_path):
    (tmp_path / "bad.json").write_text("{broken json", encoding="utf-8")
    _write_pack(tmp_path, "wa_construction", SAMPLE_CONSTRUCTION)

    packs = load_domain_packs(domain_dir=tmp_path)

    assert "wa_construction" in packs
    assert "bad" not in packs


def test_pack_id_falls_back_to_filename(tmp_path):
    data = dict(SAMPLE_CONSTRUCTION)
    del data["id"]
    _write_pack(tmp_path, "fallback_pack", data)

    packs = load_domain_packs(domain_dir=tmp_path)

    assert "fallback_pack" in packs


def test_domain_pack_summary_contains_key_sections(tmp_path):
    _write_pack(tmp_path, "wa_construction", SAMPLE_CONSTRUCTION)
    _write_pack(tmp_path, "keysbrook_sanctuary", SAMPLE_SANCTUARY)

    packs = load_domain_packs(domain_dir=tmp_path)
    summary = domain_pack_summary(packs)

    assert "## Domain Context" in summary
    assert "WA Construction" in summary
    assert "Keysbrook Sanctuary" in summary
    assert "Flag missing GST." in summary
    assert "Preserve hollow-bearing marri." in summary


def test_domain_pack_summary_empty_packs():
    assert domain_pack_summary({}) == ""


def test_real_packs_load_and_parse():
    """Smoke-test against the actual pack files in the repository."""
    packs = load_domain_packs()
    assert "wa_construction" in packs
    assert "keysbrook_sanctuary" in packs
    assert packs["wa_construction"]["version"] == "1.0.0"
    assert packs["keysbrook_sanctuary"]["version"] == "1.0.0"
