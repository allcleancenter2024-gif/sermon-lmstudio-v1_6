import json
import socket
import unittest
from unittest.mock import patch

from app.core import LMStudioClient


class FakeStreamResponse:
    def __init__(self, lines, content_type="text/event-stream"):
        self.lines = lines
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def __iter__(self):
        return iter(self.lines)

    def read(self):
        return b"".join(self.lines)


class BrokenStreamResponse(FakeStreamResponse):
    def __iter__(self):
        yield b'data: {"choices":[{"delta":{"content":"part"}}]}\n\n'
        raise socket.timeout("interrupted")


class V44StreamingInferenceTests(unittest.TestCase):
    def test_chat_uses_sse_and_collects_content_chunks(self):
        response = FakeStreamResponse([
            b'data: {"choices":[{"delta":{"content":"hello "}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"world"}}]}\n\n',
            b'data: [DONE]\n\n',
        ])
        client = LMStudioClient("http://127.0.0.1:12345/v1")
        with patch("app.core.urllib.request.urlopen", return_value=response) as open_url:
            text = client.chat("ready-model", "system", "user", max_tokens=1400)
        self.assertEqual(text, "hello world")
        request = open_url.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertTrue(payload["stream"])
        self.assertEqual(payload["max_tokens"], 1400)
        self.assertEqual(open_url.call_args.kwargs["timeout"], 900)

    def test_chat_accepts_non_stream_json_fallback(self):
        body = json.dumps({"choices": [{"message": {"content": "fallback"}}]}).encode()
        response = FakeStreamResponse([body], "application/json")
        client = LMStudioClient("http://127.0.0.1:12345/v1")
        with patch("app.core.urllib.request.urlopen", return_value=response):
            self.assertEqual(client.chat("ready-model", "system", "user"), "fallback")

    def test_partial_stream_disconnect_is_not_automatically_retried(self):
        client = LMStudioClient("http://127.0.0.1:12345/v1")
        with patch("app.core.urllib.request.urlopen", return_value=BrokenStreamResponse([])) as open_url:
            with self.assertRaisesRegex(ConnectionError, "일부 토큰"):
                client.chat("ready-model", "system", "user")
        self.assertEqual(open_url.call_count, 1)

    def test_reasoning_chunks_are_ignored_until_final_content_arrives(self):
        response = FakeStreamResponse([
            b'data: {"choices":[{"delta":{"reasoning_content":"thinking"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"final answer"}}]}\n\n',
            b'data: [DONE]\n\n',
        ])
        client = LMStudioClient("http://127.0.0.1:12345/v1")
        with patch("app.core.urllib.request.urlopen", return_value=response):
            self.assertEqual(client.chat("ready-model", "system", "user"), "final answer")

    def test_reasoning_only_stream_has_actionable_error(self):
        response = FakeStreamResponse([
            b'data: {"choices":[{"delta":{"reasoning_content":"thinking"}}]}\n\n',
            b'data: {"choices":[{"delta":{},"finish_reason":"length"}]}\n\n',
            b'data: [DONE]\n\n',
        ])
        client = LMStudioClient("http://127.0.0.1:12345/v1")
        with patch("app.core.urllib.request.urlopen", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "내부 추론만 생성"):
                client.chat("ready-model", "system", "user")

    def test_reasoning_only_stream_retries_with_thinking_disabled(self):
        thinking = FakeStreamResponse([
            b'data: {"choices":[{"delta":{"reasoning_content":"thinking"}}]}\n\n',
            b'data: {"choices":[{"delta":{},"finish_reason":"length"}]}\n\n',
            b'data: [DONE]\n\n',
        ])
        final = FakeStreamResponse([
            b'data: {"choices":[{"delta":{"content":"final sermon"}}]}\n\n',
            b'data: [DONE]\n\n',
        ])
        client = LMStudioClient("http://127.0.0.1:12345/v1")
        with patch("app.core.urllib.request.urlopen", side_effect=[thinking, final]) as open_url:
            self.assertEqual(client.chat("qwen/qwen3.5-9b", "system", "user"), "final sermon")
        retry_payload = json.loads(open_url.call_args_list[1].args[0].data.decode("utf-8"))
        self.assertEqual(retry_payload["chat_template_kwargs"], {"enable_thinking": False})


if __name__ == "__main__":
    unittest.main()
