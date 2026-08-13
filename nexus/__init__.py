"""
Nexus shared analysis core.

This package exists so analysis logic can live in maintainable Python
instead of only inside YAML heredocs. Workflows can import from here
as the migration progresses.

Aligned with:
  xAI  — truth-seeking
  X    — high-signal
  SpaceX — first-principles building
"""

__version__ = "0.1.0"

from .context import load_context, load_progressive, load_usage_stats
from .providers import call_grok, call_claude, format_api_error

__all__ = [
    "load_context",
    "load_progressive",
    "load_usage_stats",
    "call_grok",
    "call_claude",
    "format_api_error",
]
