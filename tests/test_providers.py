import unittest
from unittest.mock import Mock, patch

from nexus.providers import DEFAULT_GROK_MODEL, call_grok


class CallGrokTests(unittest.TestCase):
    @patch("nexus.providers.requests.post")
    def test_call_grok_uses_current_default_model(self, post: Mock) -> None:
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
        }
        post.return_value = response

        text, err = call_grok("hello", api_key="test-key")

        self.assertEqual(text, "ok")
        self.assertIsNone(err)
        self.assertEqual(post.call_args.kwargs["json"]["model"], DEFAULT_GROK_MODEL)

    @patch("nexus.providers.requests.post")
    def test_call_grok_accepts_xai_api_key_alias(self, post: Mock) -> None:
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
        }
        post.return_value = response

        with patch.dict("os.environ", {"XAI_API_KEY": "alias-key"}, clear=True):
            text, err = call_grok("hello")

        self.assertEqual(text, "ok")
        self.assertIsNone(err)
        self.assertEqual(post.call_args.kwargs["json"]["model"], DEFAULT_GROK_MODEL)
        self.assertEqual(post.call_args.kwargs["timeout"], 90)

    @patch("nexus.providers.requests.post")
    def test_call_grok_surfaces_error_message_and_model(self, post: Mock) -> None:
        response = Mock()
        response.status_code = 400
        response.json.return_value = {
            "error": {"message": "model `grok-3` has been retired"},
        }
        response.text = ""
        post.return_value = response

        text, err = call_grok("hello", api_key="test-key", model="grok-3")

        self.assertIsNone(text)
        self.assertEqual(
            err,
            "Grok API 400: model `grok-3` has been retired [model=grok-3]",
        )


if __name__ == "__main__":
    unittest.main()
