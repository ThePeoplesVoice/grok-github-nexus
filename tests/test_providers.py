import json
import unittest
from unittest.mock import Mock, patch

from nexus.providers import DEFAULT_GROK_MODEL, call_grok


class CallGrokTests(unittest.TestCase):
    @patch('nexus.providers.requests.post')
    def test_call_grok_uses_default_model_and_xai_api_key_fallback(self, post: Mock) -> None:
        response = Mock(status_code=200)
        response.json.return_value = {
            'choices': [{'message': {'content': 'analysis ok'}}],
        }
        post.return_value = response

        with patch.dict('os.environ', {'XAI_API_KEY': 'xai-test-key'}, clear=True):
            text, error = call_grok('hello world', timeout=5)

        self.assertEqual(text, 'analysis ok')
        self.assertIsNone(error)
        _, kwargs = post.call_args
        self.assertEqual(kwargs['json']['model'], DEFAULT_GROK_MODEL)
        self.assertIn('Authorization', kwargs['headers'])
        self.assertTrue(kwargs['headers']['Authorization'])
        self.assertEqual(kwargs['headers']['Content-Type'], 'application/json')
        self.assertEqual(kwargs['timeout'], 5)

    @patch('nexus.providers.requests.post')
    def test_call_grok_surfaces_nonempty_error_payloads(self, post: Mock) -> None:
        response = Mock(status_code=400)
        response.json.return_value = {
            'error': {'code': 'retired_model'},
        }
        response.text = json.dumps(response.json.return_value)
        post.return_value = response

        text, error = call_grok('hello world', api_key='grok-test-key')

        self.assertIsNone(text)
        self.assertEqual(
            error,
            f'Grok API 400: retired_model [model={DEFAULT_GROK_MODEL}]',
        )


if __name__ == '__main__':
    unittest.main()
