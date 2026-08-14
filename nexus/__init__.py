"""Nexus shared analysis core."""

__version__ = "0.7.0"

from .context import load_context, load_progressive, load_usage_stats, layer1_enabled, current_phase
from .providers import call_grok, call_claude, format_api_error
from .audit import (
    structural_health,
    alignment_signals,
    progressive_snapshot,
    build_self_audit_prompt,
    format_audit_footer,
)
from .usage import (
    increment_usage,
    record_successful_analysis,
    save_usage_stats,
)
from .reputation import (
    compute_reputation,
    refresh_reputation,
    load_reputation,
    reputation_summary_md,
    reputation_badge_line,
    sync_public_badges,
)
from .presence import load_presence, format_presence_for_prompt
from .runtime import after_successful_analysis, log_success
from .field_notes import append_field_note, read_recent_notes, notes_summary_md

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
    "increment_usage",
    "record_successful_analysis",
    "save_usage_stats",
    "compute_reputation",
    "refresh_reputation",
    "load_reputation",
    "reputation_summary_md",
    "reputation_badge_line",
    "sync_public_badges",
    "load_presence",
    "format_presence_for_prompt",
    "after_successful_analysis",
    "log_success",
    "append_field_note",
    "read_recent_notes",
    "notes_summary_md",
]
