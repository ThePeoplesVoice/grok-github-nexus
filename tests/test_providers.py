from __future__ import annotations

import unittest
from unittest.mock import patch

from nexus.providers import DEFAULT_GROK_MODEL, call_grok, format_api_error


class _SuccessResponse:
    status_code = 200

    def json(self):
        return {"choices": [{"message": {"content": "ok"}}]}


class _ErrorResponse:
    status_code = 400

    def __init__(self, payload):
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


class ProvidersTests(unittest.TestCase):
    def test_call_grok_sends_bearer_token_and_default_model(self) -> None:
        captured = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            captured["timeout"] = timeout
            return _SuccessResponse()

        with patch("nexus.providers.requests.post", side_effect=fake_post):
            text, err = call_grok("hello", api_key="test-key", timeout=12)

        self.assertEqual(text, "ok")
        self.assertIsNone(err)
        self.assertTrue(captured["headers"]["Authorization"].startswith("Bearer "))
        self.assertTrue(captured["headers"]["Authorization"].endswith("test-key"))
        self.assertEqual(captured["headers"]["Content-Type"], "application/json")
        self.assertEqual(captured["json"]["model"], DEFAULT_GROK_MODEL)
        self.assertEqual(captured["timeout"], 12)

    def test_format_api_error_surfaces_provider_message(self) -> None:
        response = _ErrorResponse({"error": {"message": "request body invalid"}})

        self.assertEqual(
            format_api_error("Grok", response),
            "Grok API 400: request body invalid",
        )


if __name__ == "__main__":
    unittest.main()
