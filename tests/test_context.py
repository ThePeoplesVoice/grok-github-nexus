"""Tests for nexus.context progressive gating helpers."""

from __future__ import annotations

from nexus.context import (
    successful_analysis_gate_status,
    layer1_enabled,
    layer1_feature_enabled,
)


def _prog(*, enabled: bool = True, min_successful_analyses: int = 50) -> dict:
    return {
        "layers": {
            "1_progressive_unlocks": {
                "enabled": enabled,
                "triggers": {
                    "min_successful_analyses": min_successful_analyses,
                    "min_stars": 10,
                    "min_community_prs": 3,
                },
            }
        }
    }


def _stats(total: int) -> dict:
    return {"total_successful_analyses": total}


def test_successful_analysis_gate_status_reports_remaining():
    gate = successful_analysis_gate_status(_prog(min_successful_analyses=50), _stats(12))
    assert gate == {
        "current": 12,
        "required": 50,
        "remaining": 38,
        "met": False,
    }


def test_layer1_feature_enabled_requires_config_flag():
    prog = _prog(enabled=False, min_successful_analyses=1)
    assert layer1_enabled(prog) is False
    assert layer1_feature_enabled("multi_model_fusion", prog, _stats(99)) is False


def test_layer1_feature_enabled_unlocks_at_analysis_threshold():
    prog = _prog(enabled=True, min_successful_analyses=12)
    assert layer1_enabled(prog) is True
    assert layer1_feature_enabled("multi_model_fusion", prog, _stats(12)) is True
    assert layer1_feature_enabled("multi_model_fusion", prog, _stats(11)) is False


def test_non_gated_layer1_features_follow_control_plane_flag():
    prog = _prog(enabled=True, min_successful_analyses=999)
    assert layer1_feature_enabled("presence_continuity", prog, _stats(0)) is True
