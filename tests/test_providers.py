"""Tests for nexus.providers — error formatting and API call guards."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import requests

import pytest

from nexus.providers import (
    DEFAULT_GROK_MODEL,
    call_claude,
    call_grok,
    format_api_error,
)


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


# ── format_api_error ──────────────────────────────────────────

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


def test_format_api_error_provider_message():
    resp = _mock_response(400, {"error": {"message": "request body invalid"}})
    assert format_api_error("Grok", resp) == "Grok API 400: request body invalid"


def test_format_api_error_claude_low_credits():
    resp = _mock_response(
        400,
        {"error": {"message": "Your credit balance is too low to process this request."}},
    )
    msg = format_api_error("Claude", resp)
    assert "insufficient credits" in msg.lower()
    assert "Grok-only" in msg


# ── call_grok ────────────────────────────────────────────────

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


def test_call_grok_request_contract(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _mock_response(200, {"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.delenv("GROK_MODEL", raising=False)
    with patch("nexus.providers.requests.post", side_effect=fake_post):
        text, err = call_grok("hello", api_key="test-key", timeout=12)

    assert text == "ok"
    assert err is None
    assert captured["headers"]["Authorization"].startswith("Bearer ")
    assert captured["headers"]["Authorization"].endswith("test-key")
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["json"]["model"] == DEFAULT_GROK_MODEL
    assert captured["timeout"] == 12


def test_call_grok_empty_content_retries_then_reports_error():
    empty_resp = _mock_response(200, {"choices": [{"message": {"content": ""}}]})
    with patch("nexus.providers.requests.post", return_value=empty_resp) as post:
        text, err = call_grok("hello", api_key="test-key", retries=1)
    assert text is None
    assert err == "Grok response empty content"
    assert post.call_count == 2


def test_call_grok_passes_requested_response_format():
    ok_resp = _mock_response(200, {"choices": [{"message": {"content": "{}"}}]})
    with patch("nexus.providers.requests.post", return_value=ok_resp) as post:
        call_grok(
            "hello",
            api_key="test-key",
            response_format={"type": "json_object"},
        )
    assert post.call_args.kwargs["json"]["response_format"] == {"type": "json_object"}


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


# ── call_claude ──────────────────────────────────────────────

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


def test_call_grok_retries_timeout_then_succeeds():
    timeout_exc = requests.exceptions.ReadTimeout("Read timed out. (read timeout=90)")
    ok_resp = _mock_response(200, {"choices": [{"message": {"content": "recovered"}}]})
    with patch("nexus.providers.requests.post", side_effect=[timeout_exc, ok_resp]):
        with patch.dict(os.environ, {"GROK_API_KEY": "xai-test-key"}):
            text, err = call_grok("hello", retries=1)
    assert text == "recovered"
    assert err is None
