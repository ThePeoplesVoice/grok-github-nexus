"""Complete Analysis output budget — #136 / #141 truncated at 1200."""

from nexus.scripts.run_complete_analysis import COMPLETE_MAX_TOKENS


def test_complete_budget_above_known_clip():
    assert COMPLETE_MAX_TOKENS >= 2500
