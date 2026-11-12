"""Exercise the real HTTP transport against a local stub of the documented
Chat Completions envelope. This proves wire handling, NOT live Muse access."""
from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from server.providers import MuseConfig, ProviderError
from server.providers.transport import ChatRequest, MetaChatCompletionsTransport, parse_chat_completion


class Stub(BaseHTTPRequestHandler):
    responses: list[tuple[int, dict[str, str], bytes]] = []
    seen: list[dict] = []

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        Stub.seen.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
        status, headers, payload = Stub.responses.pop(0)
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_a):
        return


def completion(content: str, model: str = "muse-spark-1.3", finish: str = "stop") -> bytes:
    return json.dumps({"model": model, "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": finish}]}).encode()


class TransportTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Stub.responses.clear()
        Stub.seen.clear()
        cfg = MuseConfig(api_key="k-test", timeout_s=2.0)
        # The config enforces https for real use; the stub is plain http on loopback.
        object.__setattr__(cfg, "base_url", f"http://127.0.0.1:{self.server.server_port}/v1")
        self.transport = MetaChatCompletionsTransport(cfg)
        self.request = ChatRequest(developer="rules", user="data", schema_name="t",
                                   schema={"type": "object"}, max_output_tokens=100,
                                   temperature=0.0, timeout_s=2.0)

    async def test_request_shape_matches_documented_fields(self):
        Stub.responses.append((200, {}, completion('{"a":1}')))
        res = await self.transport.complete(self.request)
        self.assertEqual(res.text, '{"a":1}')
        self.assertEqual(res.model, "muse-spark-1.3")
        seen = Stub.seen[0]
        self.assertEqual(seen["path"], "/v1/chat/completions")
        self.assertEqual(seen["auth"], "Bearer k-test")
        body = seen["body"]
        self.assertEqual(body["model"], "muse-spark-1.3")
        self.assertEqual([m["role"] for m in body["messages"]], ["developer", "user"])
        self.assertEqual(body["response_format"]["type"], "json_schema")
        self.assertEqual(body["response_format"]["json_schema"]["name"], "t")
        self.assertIn("max_completion_tokens", body)
        self.assertNotIn("reasoning_effort", body)

    async def test_status_classification(self):
        cases = [
            (429, {"Retry-After": "2"}, "rate_limited", 2.0),
            (401, {}, "auth", None),
            (400, {}, "invalid_request", None),
            (503, {"Retry-After": "60"}, "unavailable", 60.0),
            (504, {}, "timeout", None),
            (500, {}, "unavailable", None),
        ]
        for status, headers, kind, retry_after in cases:
            Stub.responses.append((status, headers, b'{"error":{"message":"private detail"}}'))
            with self.assertRaises(ProviderError) as ctx:
                await self.transport.complete(self.request)
            self.assertEqual(ctx.exception.kind, kind, status)
            self.assertEqual(ctx.exception.retry_after_s, retry_after)
            self.assertNotIn("private detail", ctx.exception.message)

    async def test_unreachable_host_is_unavailable(self):
        cfg = MuseConfig(api_key="k", timeout_s=1.0)
        object.__setattr__(cfg, "base_url", "http://127.0.0.1:9/v1")
        with self.assertRaises(ProviderError) as ctx:
            await MetaChatCompletionsTransport(cfg).complete(self.request)
        self.assertIn(ctx.exception.kind, ("unavailable", "timeout"))
        if ctx.exception.kind == "unavailable":
            self.assertIn("connection_refused", ctx.exception.message)

    def test_network_cause_labels(self):
        import socket
        import ssl
        import urllib.error

        from server.providers.transport import network_cause

        self.assertEqual(network_cause(urllib.error.URLError(ssl.SSLCertVerificationError("x"))), "tls_certificate_verify_failed")
        self.assertEqual(network_cause(urllib.error.URLError(socket.gaierror(8, "nodename"))), "dns_lookup_failed")
        self.assertEqual(network_cause(urllib.error.URLError(ConnectionRefusedError(61, "refused"))), "connection_refused")

    def test_envelope_parsing(self):
        with self.assertRaises(ProviderError):
            parse_chat_completion(b"<html>")
        with self.assertRaises(ProviderError):
            parse_chat_completion(json.dumps({"choices": []}).encode())
        with self.assertRaises(ProviderError) as ctx:
            parse_chat_completion(completion('{"a":', finish="length"))
        self.assertEqual(ctx.exception.kind, "malformed_output")
        # Observed live: reasoning exhausted the budget, content null, finish_reason "length".
        truncated = json.dumps({"choices": [{"message": {"content": None}, "finish_reason": "length"}]}).encode()
        with self.assertRaises(ProviderError) as ctx:
            parse_chat_completion(truncated)
        self.assertIn("budget exhausted", ctx.exception.message)


if __name__ == "__main__":
    unittest.main()
