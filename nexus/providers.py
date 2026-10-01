"""AI provider clients for the Nexus (Grok primary, Claude complementary)."""

from __future__ import annotations

import os
import re
import time
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
# Hard cap so GROK_RETRIES cannot become a quiet spend loop: at most one retry,
# and only for transient failures (timeout, connection error, 5xx).
MAX_GROK_RETRIES = 1
GROK_CONNECT_TIMEOUT = 10
DEFAULT_GROK_READ_TIMEOUT = 90
GROK_RETRY_BACKOFF_SECONDS = 3.0
# grok-4.5+ are reasoning models that default to "high" effort (docs.x.ai,
# Reasoning). High effort on a large diff ran past the 120 s read timeout.
DEFAULT_GROK_REASONING_EFFORT = "low"
GROK_REASONING_EFFORTS = ("low", "medium", "high", "xhigh")
# Upper bound on the user prompt sent to Grok; longer prompts are trimmed.
DEFAULT_GROK_MAX_PROMPT_CHARS = 24000
_sleep = time.sleep

GrokOutcome = Literal["ok", "empty", "malformed", "truncated", "auth", "timeout", "error"]


def _grok_model() -> str:
    return (os.environ.get("GROK_MODEL") or DEFAULT_GROK_MODEL).strip()


def _claude_model() -> str:
    return (os.environ.get("CLAUDE_MODEL") or DEFAULT_CLAUDE_MODEL).strip()


def _grok_reasoning_effort(model: str, effort: str | None) -> str | None:
    """Effort to send, or None when the model does not take reasoning_effort."""
    value = (effort or os.environ.get("GROK_REASONING_EFFORT") or DEFAULT_GROK_REASONING_EFFORT)
    value = value.strip().lower()
    if value not in GROK_REASONING_EFFORTS:
        value = DEFAULT_GROK_REASONING_EFFORT
    name = model.lower()
    if "non-reasoning" in name or "multi-agent" in name:
        return None
    match = re.match(r"grok-(\d+)\.(\d+)", name)
    if not match or (int(match.group(1)), int(match.group(2))) < (4, 5):
        return None
    return value


def trim_prompt(text: str, limit: int | None = None) -> str:
    """Cap prompt length so one oversized diff cannot stall the call."""
    if limit is None:
        try:
            limit = int(os.environ.get("GROK_MAX_PROMPT_CHARS") or DEFAULT_GROK_MAX_PROMPT_CHARS)
        except ValueError:
            limit = DEFAULT_GROK_MAX_PROMPT_CHARS
    if limit <= 0 or len(text) <= limit:
        return text
    marker = f"\n\n… [prompt trimmed from {len(text)} to {limit} chars]"
    return text[: max(0, limit - len(marker))] + marker


def _is_transient_status(status: int) -> bool:
    return 500 <= status <= 599


def _is_timeout_error(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    return "timeout" in name or "timed out" in message or "timeout" in message


def _is_auth_error(blob: str) -> bool:
    if "incorrect api key" in blob or "unauthorized" in blob:
        return True
    if "api_key" in blob or "api key" in blob:
        return True
    if "grok_api_key" in blob and "missing" in blob:
        return True
    if "xai_api_key" in blob and "missing" in blob:
        return True
    if " api 401:" in blob or "api 401:" in blob or "status 401" in blob:
        return True
    return False


def resolve_grok_retries(retries: int | None = None) -> int:
    """Clamp extra attempts to [0, MAX_GROK_RETRIES]."""
    if retries is None:
        raw = (os.environ.get("GROK_RETRIES") or "1").strip()
        try:
            retries = int(raw)
        except ValueError:
            retries = 1
    return max(0, min(MAX_GROK_RETRIES, retries))


def classify_grok_result(text: str | None, error: str | None) -> GrokOutcome:
    """Typed pipe outcome for Complete/Pulse diagnostics.

    empty | malformed | truncated | ok | auth | timeout | error
    """
    if isinstance(text, str) and text.strip():
        stripped = text.strip()
        if stripped.startswith("{") and not stripped.endswith("}"):
            return "truncated"
        if stripped.startswith("[") and not stripped.endswith("]"):
            return "truncated"
        return "ok"
    blob = (error or "").lower()
    if _is_auth_error(blob):
        return "auth"
    if "timeout" in blob or "timed out" in blob:
        return "timeout"
    if "empty content" in blob or blob.endswith("empty") or "empty body" in blob:
        return "empty"
    if "malformed" in blob or "unparseable" in blob or "parse" in blob:
        return "malformed"
    if "truncat" in blob:
        return "truncated"
    if error:
        return "error"
    return "empty"


def refine_parse_outcome(
    text: str | None,
    error: str | None,
    parsed_ok: bool,
) -> GrokOutcome:
    """If JSON parse failed after a live reply, prefer truncated/malformed over ok."""
    if parsed_ok:
        return "ok"
    base = classify_grok_result(text, error)
    if base != "ok":
        return base
    stripped = (text or "").strip()
    if stripped.startswith("{") and not stripped.endswith("}"):
        return "truncated"
    if stripped.startswith("[") and not stripped.endswith("]"):
        return "truncated"
    return "malformed"


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
    timeout: int | None = None,
    api_key: str | None = None,
    model: str | None = None,
    retries: int | None = None,
    response_format: dict[str, Any] | None = None,
    reasoning_effort: str | None = None,
) -> tuple[str | None, str | None]:
    """Call Grok. Returns (analysis_text, error_message).

    ``timeout`` is the read timeout in seconds; the connect timeout is fixed at
    GROK_CONNECT_TIMEOUT. One retry with backoff happens only on a timeout,
    connection error or 5xx. Auth errors, other 4xx and empty or malformed
    replies fail at once, since retrying them only adds cost and latency.
    """
    key = api_key or os.environ.get("GROK_API_KEY") or os.environ.get("XAI_API_KEY")
    if not key:
        return None, "GROK_API_KEY (or XAI_API_KEY) missing"

    model_name = (model or _grok_model()).strip()
    retries = resolve_grok_retries(retries)
    read_timeout = timeout or DEFAULT_GROK_READ_TIMEOUT
    effort = _grok_reasoning_effort(model_name, reasoning_effort)

    payload: dict[str, Any] = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": trim_prompt(user_content)},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "search": False,
    }
    if effort:
        payload["reasoning_effort"] = effort
    if response_format:
        payload["response_format"] = response_format

    attempts = 1 + retries
    last_error = "Grok exception: request failed"

    for attempt in range(attempts):
        transient = False
        try:
            response = requests.post(
                GROK_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=(GROK_CONNECT_TIMEOUT, read_timeout),
            )
            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError as e:
                    return None, f"Grok response malformed JSON: {str(e)[:120]}"
                choices = data.get("choices") if isinstance(data, dict) else None
                message = (
                    choices[0].get("message")
                    if isinstance(choices, list) and choices and isinstance(choices[0], dict)
                    else None
                )
                text = message.get("content") if isinstance(message, dict) else None
                if isinstance(text, str) and text.strip():
                    return text, None
                return None, "Grok response empty content"
            last_error = format_api_error("Grok", response) + f" [model={model_name}]"
            transient = _is_transient_status(response.status_code)
            if not transient:
                return None, last_error
        except Exception as e:
            last_error = f"Grok exception: {str(e)[:180]}"
            transient = _is_timeout_error(e) or isinstance(
                e, (requests.ConnectionError, ConnectionError)
            )
            if not transient:
                return None, last_error

        if attempt + 1 < attempts:
            delay = GROK_RETRY_BACKOFF_SECONDS * (2 ** attempt)
            print(f"⏳ Grok transient failure, retry {attempt + 2}/{attempts} in {delay:.0f}s: {last_error[:120]}")
            _sleep(delay)

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
            CLAUDE_URL, headers=headers, json=payload, timeout=(GROK_CONNECT_TIMEOUT, timeout)
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
