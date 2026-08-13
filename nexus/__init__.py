"""
Nexus shared analysis core.

This package exists so analysis logic can live in maintainable Python
instead of only inside YAML heredocs. Workflows can import from here
as the migration progresses.

Aligned with:
  xAI  — truth-seeking
  X    — high-signal
  SpaceX — first-principles building

Self-analytical optimisation (audit) is a first-class capability so
expansion remains constrained by continuous critique.
"""

__version__ = "0.2.0"

from .context import load_context, load_progressive, load_usage_stats, layer1_enabled, current_phase
from .providers import call_grok, call_claude, format_api_error
from .audit import (
    structural_health,
    alignment_signals,
    progressive_snapshot,
    build_self_audit_prompt,
    format_audit_footer,
)

__all__ = [
    "load_context",
    "load_progressive",
    "load_usage_stats",
    "layer1_enabled",
    "current_phase",
    "call_grok",
    "call_claude",
    "format_api_error",
    "structural_health",
    "alignment_signals",
    "progressive_snapshot",
    "build_self_audit_prompt",
    "format_audit_footer",
]
