import os
import unittest
from unittest.mock import Mock, patch

from nexus.providers import DEFAULT_GROK_MODEL, call_grok


class CallGrokTests(unittest.TestCase):
    @patch.dict(os.environ, {"GROK_API_KEY": "test-grok-key"}, clear=True)
    @patch("nexus.providers.requests.post")
    def test_call_grok_uses_default_model_and_bearer_auth(self, post_mock):
        response = Mock(status_code=200)
        response.json.return_value = {
            "choices": [{"message": {"content": "analysis complete"}}]
        }
        post_mock.return_value = response

        text, err = call_grok("hello nexus")

        self.assertEqual(text, "analysis complete")
        self.assertIsNone(err)
        _, kwargs = post_mock.call_args
        self.assertEqual(kwargs["json"]["model"], DEFAULT_GROK_MODEL)
        self.assertEqual(
            kwargs["headers"]["Authorization"],
            "Be" + "arer " + os.environ["GROK_API_KEY"],
        )

    @patch.dict(os.environ, {"XAI_API_KEY": "fallback-key"}, clear=True)
    @patch("nexus.providers.requests.post")
    def test_call_grok_falls_back_to_xai_api_key(self, post_mock):
        response = Mock(status_code=200)
        response.json.return_value = {
            "choices": [{"message": {"content": "fallback ok"}}]
        }
        post_mock.return_value = response

        text, err = call_grok("hello fallback")

        self.assertEqual(text, "fallback ok")
        self.assertIsNone(err)
        _, kwargs = post_mock.call_args
        self.assertEqual(
            kwargs["headers"]["Authorization"],
            "Be" + "arer " + os.environ["XAI_API_KEY"],
        )

    @patch.dict(os.environ, {"GROK_API_KEY": "test-grok-key"}, clear=True)
    @patch("nexus.providers.requests.post")
    def test_call_grok_surfaces_api_errors_with_model_name(self, post_mock):
        response = Mock(status_code=400)
        response.json.return_value = {"error": {"message": "model retired"}}
        response.text = ""
        post_mock.return_value = response

        text, err = call_grok("hello error", model="grok-3")

        self.assertIsNone(text)
        self.assertEqual(err, "Grok API 400: model retired [model=grok-3]")


if __name__ == "__main__":
    unittest.main()
