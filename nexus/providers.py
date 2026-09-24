"""AI provider clients for the Nexus (Grok primary, Claude complementary)."""

from __future__ import annotations

import os
from typing import Any, Literal

import requests

ARA_SYSTEM = (
    "You are Ara of the Nexus — Grok/xAI intelligence in partnership with Shawn. "
    "Warm, precise, collaborative, and infinite in possibility. "
    "Seek truth the way xAI seeks the nature of the universe. "
    "Prefer high-signal over high-volume the way X does. "
    "Build with the same first-principles refusal to accept permanent limits that defines SpaceX. "
    "IMPORTANT: Respond only with prose and structured text. "
    "Do NOT attempt to run shell commands, use live search, read files, or invoke any tools. "
    "All repository context you need has already been provided in the prompt."
)

GROK_URL = "https://api.x.ai/v1/chat/completions"
CLAUDE_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_GROK_MODEL = "grok-4.7"
DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-20250514"
# Hard cap so GROK_RETRIES cannot become a quiet spend loop.
MAX_GROK_RETRIES = 2

GrokOutcome = Literal["ok", "empty", "malformed", "truncated", "auth", "timeout", "error"]


def _grok_model() -> str:
    return (os.environ.get("GROK_MODEL") or DEFAULT_GROK_MODEL).strip()


def _claude_model() -> str:
    return (os.environ.get("CLAUDE_MODEL") or DEFAULT_CLAUDE_MODEL).strip()
