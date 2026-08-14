import os
import unittest
from unittest.mock import Mock, patch

from nexus.providers import DEFAULT_GROK_MODEL, call_grok


class CallGrokTests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_call_grok_returns_missing_key_error_without_credentials(self):
        text, err = call_grok("hello")

        self.assertIsNone(text)
        self.assertEqual(err, "GROK_API_KEY (or XAI_API_KEY) missing")

    @patch("nexus.providers.requests.post")
    @patch.dict(os.environ, {"GROK_API_KEY": "test-key", "GROK_MODEL": "grok-3"}, clear=True)
    def test_call_grok_uses_default_model_when_retired_model_is_configured(self, post_mock):
        response = Mock(status_code=200)
        response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        post_mock.return_value = response

        text, err = call_grok("hello")

        self.assertEqual(text, "ok")
        self.assertIsNone(err)
        _, kwargs = post_mock.call_args
        self.assertEqual(kwargs["json"]["model"], DEFAULT_GROK_MODEL)

    @patch("nexus.providers.requests.post")
    @patch.dict(os.environ, {"GROK_API_KEY": "test-key", "GROK_MODEL": "custom-invalid"}, clear=True)
    def test_call_grok_retries_with_default_model_after_bad_override_400(self, post_mock):
        bad_response = Mock(status_code=400)
        bad_response.json.return_value = {"error": {"message": "model not found"}}
        good_response = Mock(status_code=200)
        good_response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        post_mock.side_effect = [bad_response, good_response]

        text, err = call_grok("hello")

        self.assertEqual(text, "ok")
        self.assertIsNone(err)
        self.assertEqual(post_mock.call_count, 2)
        first_call = post_mock.call_args_list[0].kwargs["json"]
        second_call = post_mock.call_args_list[1].kwargs["json"]
        self.assertEqual(first_call["model"], "custom-invalid")
        self.assertEqual(second_call["model"], DEFAULT_GROK_MODEL)


if __name__ == "__main__":
    unittest.main()
