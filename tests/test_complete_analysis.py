"""Tests for Complete Analysis response validation."""

from unittest.mock import patch

from nexus.scripts.run_complete_analysis import (
    _call_complete_grok,
    _extract_json,
    _validate_complete,
)


def test_extract_json_accepts_json_fence():
    assert _extract_json('```json\n{"summary": "ok", "actions": []}\n```') == {
        "summary": "ok",
        "actions": [],
    }


def test_validate_complete_reports_malformed_json():
    assert _validate_complete(None) == "response was not parseable JSON"


def test_validate_complete_reports_schema_mismatch():
    assert _validate_complete({"summary": "ok"}) == (
        "response JSON did not match the required schema (missing actions)"
    )


def test_validate_complete_accepts_required_schema():
    assert _validate_complete({"summary": "ok", "actions": []}) is None


def test_complete_retries_malformed_json_once():
    with patch(
        "nexus.scripts.run_complete_analysis.call_grok",
        side_effect=[("not JSON", None), ('{"summary": "ok", "actions": []}', None)],
    ) as call:
        parsed, err = _call_complete_grok("prompt")
    assert parsed == {"summary": "ok", "actions": []}
    assert err is None
    assert call.call_count == 2
