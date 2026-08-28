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


def _is_timeout_error(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    return "timeout" in name or "timed out" in message or "timeout" in message


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
    retries: int | None = None,
) -> tuple[str | None, str | None]:
    """Call Grok. Returns (analysis_text, error_message).

    Retries once on transport timeouts by default (override with GROK_RETRIES).
    """
    key = api_key or os.environ.get("GROK_API_KEY") or os.environ.get("XAI_API_KEY")
    if not key:
        return None, "GROK_API_KEY (or XAI_API_KEY) missing"

    model_name = (model or _grok_model()).strip()
    if retries is None:
        raw = (os.environ.get("GROK_RETRIES") or "1").strip()
        try:
            retries = max(0, int(raw))
        except ValueError:
            retries = 1

    attempts = 1 + max(0, retries)
    last_error = "Grok exception: request failed"

    for attempt in range(attempts):
        try:
            response = requests.post(
                GROK_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_content},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "search": False,
                },
                timeout=timeout,
            )
            if response.status_code == 200:
                data = response.json()
                text = data["choices"][0]["message"]["content"]
                return text, None
            return None, format_api_error("Grok", response) + f" [model={model_name}]"
        except Exception as e:
            last_error = f"Grok exception: {str(e)[:180]}"
            if attempt + 1 < attempts and _is_timeout_error(e):
                continue
            return None, last_error

    return None, last_error


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
