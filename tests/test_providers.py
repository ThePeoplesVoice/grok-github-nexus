import os
from unittest import TestCase
from unittest.mock import Mock, patch

from nexus.providers import DEFAULT_GROK_MODEL, call_grok


class CallGrokTests(TestCase):
    @patch.dict(os.environ, {"GROK_MODEL": "grok-3"}, clear=False)
    @patch("nexus.providers.requests.post")
    def test_call_grok_falls_back_from_retired_env_model(self, post: Mock) -> None:
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
        }
        post.return_value = response

        text, err = call_grok("hello", api_key="test-key")

        self.assertEqual(text, "ok")
        self.assertIsNone(err)
        _, kwargs = post.call_args
        self.assertEqual(kwargs["json"]["model"], DEFAULT_GROK_MODEL)

    @patch("nexus.providers.requests.post")
    def test_call_grok_falls_back_from_retired_explicit_model(self, post: Mock) -> None:
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
        }
        post.return_value = response

        text, err = call_grok("hello", api_key="test-key", model="grok-3")

        self.assertEqual(text, "ok")
        self.assertIsNone(err)
        _, kwargs = post.call_args
        self.assertEqual(kwargs["json"]["model"], DEFAULT_GROK_MODEL)
