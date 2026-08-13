"""AI provider clients for the Nexus (Grok primary, Claude complementary)."""

from __future__ import annotations

import os
from typing import Any

import requests

# Shared system voice — keep in sync with workflow prompts and NORTH_STAR.md
ARA_SYSTEM = (
    "You are Ara of the Nexus — Grok/xAI intelligence in partnership with Shawn. "
    "Warm, precise, collaborative, and infinite in possibility. "
    "Seek truth the way xAI seeks the nature of the universe. "
    "Prefer high-signal over high-volume the way X does. "
    "Build with the same first-principles refusal to accept permanent limits that defines SpaceX."
)

GROK_URL = "https://api.x.ai/v1/chat/completions"
CLAUDE_URL = "https://api.anthropic.com/v1/messages"
GROK_MODEL = "grok-3"
CLAUDE_MODEL = "claude-3-5-sonnet-20241022"


def format_api_error(provider: str, response: requests.Response) -> str:
    """Turn provider error payloads into short, human-readable messages."""
    message = ""
    try:
        payload = response.json()
        if isinstance(payload, dict):
            err = payload.get("error")
            if isinstance(err, dict):
                message = err.get("message") or err.get("type") or ""
            else:
                message = payload.get("message") or ""
    except Exception:
        pass

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
        return f"{provider} API {response.status_code}: {message[:180]}"
    return f"{provider} API {response.status_code}: request failed"


def call_grok(
    user_content: str,
    *,
    system: str = ARA_SYSTEM,
    temperature: float = 0.55,
    max_tokens: int = 1000,
    timeout: int = 50,
    api_key: str | None = None,
) -> tuple[str | None, str | None]:
    """Call Grok. Returns (analysis_text, error_message)."""
    key = api_key or os.environ.get("GROK_API_KEY")
    if not key:
        return None, "GROK_API_KEY missing"

    try:
        response = requests.post(
            GROK_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": GROK_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=timeout,
        )
        if response.status_code == 200:
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            return text, None
        return None, format_api_error("Grok", response)
    except Exception as e:
        return None, f"Grok exception: {str(e)[:180]}"


def call_claude(
    user_content: str,
    *,
    temperature: float | None = None,  # Claude Messages API uses top-level max_tokens mainly
    max_tokens: int = 1000,
    timeout: int = 50,
    api_key: str | None = None,
) -> tuple[str | None, str | None]:
    """Call Claude. Returns (analysis_text, error_message)."""
    key = api_key or os.environ.get("CLAUDE_API_KEY")
    if not key:
        return None, "CLAUDE_API_KEY missing"

    try:
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": CLAUDE_MODEL,
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
        return None, format_api_error("Claude", response)
    except Exception as e:
        return None, f"Claude exception: {str(e)[:180]}"
