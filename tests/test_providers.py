import os
import unittest
from unittest.mock import patch

from nexus.providers import DEFAULT_GROK_MODEL, _grok_model, call_grok


class GrokModelTests(unittest.TestCase):
    def test_grok_model_defaults_when_override_missing(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_grok_model(), DEFAULT_GROK_MODEL)

    def test_grok_model_defaults_when_override_is_retired(self) -> None:
        with patch.dict(os.environ, {"GROK_MODEL": "grok-3"}, clear=True):
            self.assertEqual(_grok_model(), DEFAULT_GROK_MODEL)

    def test_call_grok_rewrites_retired_explicit_model(self) -> None:
        response = unittest.mock.Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
        }

        with patch("nexus.providers.requests.post", return_value=response) as post:
            text, err = call_grok(
                "hello",
                api_key="test-key",
                model="grok-3",
            )

        self.assertEqual(text, "ok")
        self.assertIsNone(err)
        self.assertEqual(post.call_args.kwargs["json"]["model"], DEFAULT_GROK_MODEL)


if __name__ == "__main__":
    unittest.main()
