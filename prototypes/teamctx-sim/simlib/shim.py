"""A loopback shim between teamctx and the emulator.

Why: the emulator has no thread endpoints (docs: "Not supported: threads, forum posts"), so
`GET /guilds/{id}/threads/active` answers 404, and teamctx's discovery treats a 404 there as
"the bot cannot see the configured Discord server" and stops syncing the whole guild.
Real Discord always answers those routes. The shim forwards every REST request unchanged and
only replaces a 404 on the thread-list routes with the empty list real Discord would return
for a server without threads. The gateway WebSocket is tunnelled byte for byte.

Loopback only: it listens on 127.0.0.1 and forwards to a loopback upstream.
"""

from __future__ import annotations

import http.client
import http.server
import json
import re
import socket
import socketserver
import threading
from pathlib import Path

from .net import assert_loopback_url

THREAD_ROUTES = (
    (re.compile(r"^/api/v\d+/guilds/\d+/threads/active/?$"), {"threads": [], "members": []}),
    (re.compile(r"^/api/v\d+/channels/\d+/threads/archived/(public|private)/?$"),
     {"threads": [], "members": [], "has_more": False}),
    (re.compile(r"^/api/v\d+/channels/\d+/users/@me/threads/archived/private/?$"),
     {"threads": [], "members": [], "has_more": False}),
)
HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding",
       "upgrade", "content-length", "host"}


def thread_stub(path: str) -> dict | None:
    """The empty thread list for a thread route, else None."""
    bare = path.split("?", 1)[0]
    for pattern, body in THREAD_ROUTES:
        if pattern.match(bare):
            return body
    return None


class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_handler(upstream: tuple[str, int], stats: dict, log_path: Path | None):
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):  # silence the default stderr logging
            return

        def _body(self) -> bytes:
            if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
                out = b""
                while True:
                    size = int(self.rfile.readline().strip() or b"0", 16)
                    if size == 0:
                        self.rfile.readline()
                        return out
                    out += self.rfile.read(size)
                    self.rfile.readline()
            return self.rfile.read(int(self.headers.get("Content-Length") or 0))

        def _tunnel(self) -> None:
            stats["websocket_tunnels"] = stats.get("websocket_tunnels", 0) + 1
            up = socket.create_connection(upstream, timeout=10)
            up.settimeout(None)
            head = f"{self.command} {self.path} HTTP/1.1\r\n" + "".join(f"{k}: {v}\r\n" for k, v in self.headers.items()) + "\r\n"
            up.sendall(head.encode("latin-1"))
            client = self.connection
            client.settimeout(None)

            def pump(src, dst):
                try:
                    while True:
                        data = src.recv(65536)
                        if not data:
                            break
                        dst.sendall(data)
                except OSError:
                    pass
                finally:
                    for s in (src, dst):
                        try:
                            s.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass

            t = threading.Thread(target=pump, args=(up, client), daemon=True)
            t.start()
            pump(client, up)
            t.join(timeout=2)
            up.close()
            self.close_connection = True

        def _forward(self) -> None:
            if self.headers.get("Upgrade", "").lower() == "websocket":
                return self._tunnel()
            body = self._body()
            headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
            conn = http.client.HTTPConnection(*upstream, timeout=30)
            try:
                conn.request(self.command, self.path, body=body or None, headers=headers)
                resp = conn.getresponse()
                payload = resp.read()
                status, resp_headers = resp.status, resp.getheaders()
            except OSError as exc:
                self.send_error(502, f"upstream: {type(exc).__name__}")
                return
            finally:
                conn.close()
            stub = thread_stub(self.path) if self.command == "GET" and status == 404 else None
            if stub is not None:
                payload = json.dumps(stub).encode()
                status = 200
                resp_headers = [("Content-Type", "application/json")]
                stats["thread_stubs"] = stats.get("thread_stubs", 0) + 1
                if log_path:
                    with open(log_path, "a", encoding="utf-8") as fh:
                        fh.write(json.dumps({"stub": self.path.split("?", 1)[0]}) + "\n")
            stats["forwarded"] = stats.get("forwarded", 0) + 1
            self.send_response(status)
            for k, v in resp_headers:
                if k.lower() not in HOP:
                    self.send_header(k, v)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = _forward

    return Handler


class Shim:
    """The running shim. `stats` counts forwarded requests, thread stubs and websocket tunnels."""

    def __init__(self, listen_port: int, upstream_url: str = "http://127.0.0.1:4000", log_path: Path | None = None) -> None:
        assert_loopback_url(upstream_url)
        host, _, port = upstream_url.split("//", 1)[1].partition(":")
        self.upstream = (host.strip("[]"), int(port.rstrip("/")))
        self.stats: dict = {}
        self.server = _Server(("127.0.0.1", listen_port), make_handler(self.upstream, self.stats, log_path))
        self.port = self.server.server_address[1]
        self.thread: threading.Thread | None = None

    def start(self) -> "Shim":
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def serve_forever(self) -> None:
        self.server.serve_forever()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
