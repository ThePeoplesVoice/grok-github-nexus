"""Tests for nexus.providers — error formatting and API call guards."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from nexus.providers import format_api_error, call_grok, call_claude


def _mock_response(status: int, body: dict | str) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    if isinstance(body, dict):
        resp.json.return_value = body
        resp.text = str(body)
    else:
        resp.json.side_effect = ValueError("not json")
        resp.text = body
    return resp


# ── format_api_error ──────────────────────────────────────────────────────────

def test_format_api_error_dict_message():
    resp = _mock_response(400, {"error": {"message": "Incorrect API key provided."}})
    msg = format_api_error("Grok", resp)
    assert "400" in msg
    assert "Incorrect API key" in msg


def test_format_api_error_string_error():
    resp = _mock_response(403, {"error": "Forbidden"})
    msg = format_api_error("Grok", resp)
    assert "403" in msg
    assert "Forbidden" in msg


def test_format_api_error_plain_message_key():
    resp = _mock_response(402, {"message": "Insufficient credits"})
    msg = format_api_error("Grok", resp)
    assert "402" in msg
    assert "Insufficient credits" in msg


def test_format_api_error_non_json():
    resp = _mock_response(500, "Internal Server Error")
    msg = format_api_error("Grok", resp)
    assert "500" in msg


def test_format_api_error_claude_low_credits():
    resp = _mock_response(
        400,
        {"error": {"message": "Your credit balance is too low to process this request."}},
    )
    msg = format_api_error("Claude", resp)
    assert "insufficient credits" in msg.lower()
    assert "Grok-only" in msg


# ── call_grok ─────────────────────────────────────────────────────────────────

def test_call_grok_no_key():
    with patch.dict(os.environ, {}, clear=False):
        env_backup = {}
        for k in ("GROK_API_KEY", "XAI_API_KEY"):
            env_backup[k] = os.environ.pop(k, None)
        try:
            text, err = call_grok("hello")
            assert text is None
            assert err is not None
            assert "GROK_API_KEY" in err
        finally:
            for k, v in env_backup.items():
                if v is not None:
                    os.environ[k] = v


def test_call_grok_success():
    ok_resp = _mock_response(200, {
        "choices": [{"message": {"content": "Hi from Grok"}}]
    })
    with patch("nexus.providers.requests.post", return_value=ok_resp):
        with patch.dict(os.environ, {"GROK_API_KEY": "xai-test-key"}):
            text, err = call_grok("hello")
    assert text == "Hi from Grok"
    assert err is None


def test_call_grok_400_error():
    err_resp = _mock_response(400, {"error": {"message": "Incorrect API key provided."}})
    with patch("nexus.providers.requests.post", return_value=err_resp):
        with patch.dict(os.environ, {"GROK_API_KEY": "bad-key"}):
            text, err = call_grok("hello")
    assert text is None
    assert "400" in err
    assert "Incorrect API key" in err


def test_call_grok_request_exception():
    with patch("nexus.providers.requests.post", side_effect=ConnectionError("timeout")):
        with patch.dict(os.environ, {"GROK_API_KEY": "xai-test-key"}):
            text, err = call_grok("hello")
    assert text is None
    assert "exception" in err.lower()


# ── call_claude ───────────────────────────────────────────────────────────────

def test_call_claude_no_key():
    env_backup = os.environ.pop("CLAUDE_API_KEY", None)
    try:
        text, err = call_claude("hello")
        assert text is None
        assert "CLAUDE_API_KEY" in err
    finally:
        if env_backup is not None:
            os.environ["CLAUDE_API_KEY"] = env_backup


def test_call_claude_success():
    ok_resp = _mock_response(200, {
        "content": [{"text": "Hi from Claude"}]
    })
    with patch("nexus.providers.requests.post", return_value=ok_resp):
        with patch.dict(os.environ, {"CLAUDE_API_KEY": "sk-ant-test"}):
            text, err = call_claude("hello")
    assert text == "Hi from Claude"
    assert err is None
