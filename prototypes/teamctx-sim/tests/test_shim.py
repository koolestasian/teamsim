import http.client
import http.server
import json
import socket
import threading
import unittest

import fakes  # noqa: F401
from simlib import envfile
from simlib.net import PolicyError
from simlib.shim import Shim, thread_stub


class Upstream(http.server.BaseHTTPRequestHandler):
    seen = []
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _reply(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-RateLimit-Remaining", "49")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        Upstream.seen.append(("GET", self.path, self.headers.get("Authorization")))
        if "threads" in self.path:
            return self._reply(404, {"message": "404: Not Found", "code": 0})
        if self.path.endswith("/missing"):
            return self._reply(404, {"message": "Unknown Channel", "code": 10003})
        if self.headers.get("Upgrade", "").lower() == "websocket":
            self.close_connection = True
            return
        self._reply(200, {"ok": True, "path": self.path})

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        Upstream.seen.append(("POST", self.path, body.decode()))
        self._reply(200, {"echo": json.loads(body or b"{}")})


class ShimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.up = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        cls.up.daemon_threads = True
        threading.Thread(target=cls.up.serve_forever, daemon=True).start()
        cls.shim = Shim(0, f"http://127.0.0.1:{cls.up.server_address[1]}").start()

    @classmethod
    def tearDownClass(cls):
        cls.shim.stop()
        cls.up.shutdown()
        cls.up.server_close()

    def get(self, path, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.shim.port, timeout=5)
        c.request("GET", path, headers=headers or {})
        r = c.getresponse()
        out = r.status, r.read(), dict(r.getheaders())
        c.close()
        return out

    def test_thread_routes_become_empty_lists_when_upstream_404s(self):
        for path, key in (("/api/v10/guilds/1/threads/active", "threads"), ("/api/v10/channels/2/threads/archived/public?limit=100", "has_more"),
                          ("/api/v10/channels/2/threads/archived/private", "has_more"), ("/api/v10/channels/2/users/@me/threads/archived/private", "has_more")):
            status, body, _ = self.get(path)
            self.assertEqual(status, 200, path)
            self.assertIn(key, json.loads(body))
            self.assertEqual(json.loads(body)["threads"], [])
        self.assertGreaterEqual(self.shim.stats["thread_stubs"], 4)

    def test_other_404s_pass_through_unchanged(self):
        status, body, _ = self.get("/api/v10/channels/9/messages/missing")
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body)["code"], 10003)

    def test_requests_are_forwarded_with_headers_and_bodies(self):
        status, body, headers = self.get("/api/v10/users/@me", {"Authorization": "Bot fake-token-value"})
        self.assertEqual(status, 200)
        self.assertEqual(headers["X-RateLimit-Remaining"], "49")
        self.assertIn(("GET", "/api/v10/users/@me", "Bot fake-token-value"), Upstream.seen)
        c = http.client.HTTPConnection("127.0.0.1", self.shim.port, timeout=5)
        c.request("POST", "/api/v10/x", body=json.dumps({"a": 1}), headers={"Content-Type": "application/json"})
        r = c.getresponse()
        self.assertEqual(json.loads(r.read()), {"echo": {"a": 1}})
        c.close()

    def test_keep_alive_connection_serves_several_requests(self):
        c = http.client.HTTPConnection("127.0.0.1", self.shim.port, timeout=5)
        for _ in range(3):
            c.request("GET", "/api/v10/ping")
            r = c.getresponse()
            r.read()
            self.assertEqual(r.status, 200)
        c.close()

    def test_websocket_upgrade_is_tunnelled_raw(self):
        echo = socket.socket()
        echo.bind(("127.0.0.1", 0))
        echo.listen(1)
        seen = {}

        def serve():
            conn, _ = echo.accept()
            data = b""
            while b"\r\n\r\n" not in data:
                data += conn.recv(1024)
            seen["head"] = data
            conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n\r\nHELLO")
            conn.recv(5)
            conn.sendall(b"PONG!")
            conn.close()

        threading.Thread(target=serve, daemon=True).start()
        shim = Shim(0, f"http://127.0.0.1:{echo.getsockname()[1]}").start()
        try:
            s = socket.create_connection(("127.0.0.1", shim.port), timeout=5)
            s.sendall(b"GET /?v=10&encoding=json HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: abc\r\n\r\n")
            buf = b""
            while b"HELLO" not in buf:
                buf += s.recv(1024)
            s.sendall(b"PING!")
            tail = b""
            while b"PONG!" not in tail:
                chunk = s.recv(1024)
                if not chunk:
                    break
                tail += chunk
            self.assertIn(b"101 Switching Protocols", buf)
            self.assertIn(b"PONG!", tail)
            self.assertIn(b"/?v=10&encoding=json", seen["head"])
            self.assertEqual(shim.stats["websocket_tunnels"], 1)
        finally:
            s.close()
            shim.stop()
            echo.close()

    def test_non_loopback_upstream_is_refused(self):
        with self.assertRaises(PolicyError):
            Shim(0, "http://discord.com:80")

    def test_thread_stub_matching(self):
        self.assertIsNotNone(thread_stub("/api/v10/guilds/123/threads/active"))
        self.assertIsNone(thread_stub("/api/v10/guilds/123/channels"))
        self.assertIsNone(thread_stub("/api/v10/channels/1/messages"))

    def test_redactor_does_not_eat_prose(self):
        text = "Guild: visible to the bot\nMessage Content intent: enabled"
        self.assertEqual(envfile.redact(text), text)


if __name__ == "__main__":
    unittest.main()
