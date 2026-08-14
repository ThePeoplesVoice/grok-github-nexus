"""AI provider clients for the Nexus (Grok primary, Claude complementary)."""

from __future__ import annotations

import os
import re
from typing import Any

import requests

# Shared system voice — keep in sync with workflow prompts and NORTH_STAR.md
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

# grok-3 was retired 2026-05-15. Default to current frontier; override with GROK_MODEL.
DEFAULT_GROK_MODEL = "grok-4.6"
DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-20250514"


def _grok_model() -> str:
    return (os.environ.get("GROK_MODEL") or DEFAULT_GROK_MODEL).strip()


def _claude_model() -> str:
    return (os.environ.get("CLAUDE_MODEL") or DEFAULT_CLAUDE_MODEL).strip()


# ---------------------------------------------------------------------------
# Shared payload factory — always disables tools/search for analysis calls
# ---------------------------------------------------------------------------

def grok_analysis_payload(
    user_content: str,
    *,
    system: str = ARA_SYSTEM,
    temperature: float = 0.55,
    max_tokens: int = 1000,
    model: str | None = None,
) -> dict[str, Any]:
    """Return a Grok API payload with live search/tools disabled.

    Centralises the no-tools contract so every analysis call (self-audit,
    commit review, field notes, etc.) enforces it from a single place.
    """
    model_name = (model or _grok_model()).strip()
    return {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "search": False,
    }


# ---------------------------------------------------------------------------
# Output guard — reject replies that look like tool / shell traces
# ---------------------------------------------------------------------------

_TOOL_TRACE_PATTERNS = [
    re.compile(r"^\d+[▌▎▏▍▋▊█]\s", re.MULTILINE),       # numbered tool output prefixes
    re.compile(r"^\s*```\s*(sh|bash|shell)\b", re.MULTILINE),  # fenced shell blocks
    re.compile(r"^(ls|cat|find|pwd|echo|cd|grep)\s", re.MULTILINE),  # bare shell commands
    re.compile(r"\n\d+\s+(total|drwx|lrwx|-rw)", re.MULTILINE),     # ls -l output
]


def _looks_like_tool_trace(text: str) -> bool:
    """Return True if *text* looks like raw shell/tool output rather than prose."""
    for pattern in _TOOL_TRACE_PATTERNS:
        if pattern.search(text):
            return True
    return False


def format_api_error(provider: str, response: requests.Response) -> str:
    """Turn provider error payloads into short, human-readable messages."""
    message = ""
    raw_snippet = ""
    try:
        payload = response.json()
        if isinstance(payload, dict):
            err = payload.get("error")
            if isinstance(err, dict):
                message = err.get("message") or err.get("type") or err.get("code") or ""
            elif isinstance(err, str):
                message = err
            else:
                message = payload.get("message") or ""
            if not message:
                raw_snippet = str(payload)[:200]
        else:
            raw_snippet = str(payload)[:200]
    except Exception:
        raw_snippet = (response.text or "")[:200]

    message = " ".join(str(message).split())
    if (
        provider == "Claude"
        and response.status_code == 400
        and "credit balance is too low" in message.lower()
    ):
        return (
            "Claude API is temporarily unavailable due to insufficient credits. "
            "Running Grok-only path remains fully operational."
        )
    if message:
        return f"{provider} API {response.status_code}: {message[:220]}"
    if raw_snippet:
        return f"{provider} API {response.status_code}: {raw_snippet}"
    return f"{provider} API {response.status_code}: request failed (empty body)"


def call_grok(
    user_content: str,
    *,
    system: str = ARA_SYSTEM,
    temperature: float = 0.55,
    max_tokens: int = 1000,
    timeout: int = 90,
    api_key: str | None = None,
    model: str | None = None,
) -> tuple[str | None, str | None]:
    """Call Grok. Returns (analysis_text, error_message)."""
    key = api_key or os.environ.get("GROK_API_KEY") or os.environ.get("XAI_API_KEY")
    if not key:
        return None, "GROK_API_KEY (or XAI_API_KEY) missing"

    model_name = (model or _grok_model()).strip()

    try:
        payload = grok_analysis_payload(
            user_content,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model_name,
        )
        response = requests.post(
            GROK_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
        if response.status_code == 200:
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            if _looks_like_tool_trace(text):
                return None, (
                    "Grok response contained tool/shell traces instead of prose analysis. "
                    "The reply has been discarded. "
                    "Check that the xAI API search/tools contract is still respected."
                )
            return text, None
        return None, format_api_error("Grok", response) + f" [model={model_name}]"
    except Exception as e:
        return None, f"Grok exception: {str(e)[:180]}"


def call_claude(
    user_content: str,
    *,
    temperature: float | None = None,
    max_tokens: int = 1000,
    timeout: int = 90,
    api_key: str | None = None,
    model: str | None = None,
) -> tuple[str | None, str | None]:
    """Call Claude. Returns (analysis_text, error_message)."""
    key = api_key or os.environ.get("CLAUDE_API_KEY")
    if not key:
        return None, "CLAUDE_API_KEY missing"

    model_name = (model or _claude_model()).strip()

    try:
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": model_name,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": user_content}],
        }
        response = requests.post(
            CLAUDE_URL, headers=headers, json=payload, timeout=timeout
        )
        if response.status_code == 200:
            data = response.json()
            content = data.get("content") or []
            if content and isinstance(content, list):
                return content[0].get("text", str(data)), None
            return str(data), None
        return None, format_api_error("Claude", response) + f" [model={model_name}]"
    except Exception as e:
        return None, f"Claude exception: {str(e)[:180]}"
