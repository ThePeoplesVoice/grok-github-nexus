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

# grok-3 was retired 2026-05-15. Default to current frontier; override with GROK_MODEL.
DEFAULT_GROK_MODEL = "grok-4.6"
DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-20250514"
RETIRED_GROK_MODELS = {"grok-3"}


def _grok_model(model: str | None = None) -> str:
    candidate = (model or os.environ.get("GROK_MODEL") or DEFAULT_GROK_MODEL).strip()
    if candidate.lower() in RETIRED_GROK_MODELS:
        return DEFAULT_GROK_MODEL
    return candidate


def _call_grok_api(
    *,
    key: str,
    model_name: str,
    system: str,
    user_content: str,
    temperature: float,
    max_tokens: int,
    timeout: int,
) -> requests.Response:
    return requests.post(
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
        },
        timeout=timeout,
    )


def _claude_model() -> str:
    return (os.environ.get("CLAUDE_MODEL") or DEFAULT_CLAUDE_MODEL).strip()


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

    model_name = _grok_model(model)

    try:
        response = _call_grok_api(
            key=key,
            model_name=model_name,
            system=system,
            user_content=user_content,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        if response.status_code == 400 and model_name != DEFAULT_GROK_MODEL:
            fallback_model = _grok_model(DEFAULT_GROK_MODEL)
            response = _call_grok_api(
                key=key,
                model_name=fallback_model,
                system=system,
                user_content=user_content,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            model_name = fallback_model
        if response.status_code == 200:
            data = response.json()
            text = data["choices"][0]["message"]["content"]
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
