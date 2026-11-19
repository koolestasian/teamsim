"""Tests for the local page server (ideas/specs/run-ui-v0.md): routes, request checks, one run at a time."""

import http.client
import json
import pathlib
import threading
import unittest

from teamsim import cli, controls, pack, serve

ROOT = pathlib.Path(__file__).parent.parent
TAILNET = "box.example.ts.net"
JSON_TYPE = {"Content-Type": "application/json"}


class ServerTest(unittest.TestCase):
    runner = None
    tailnet = TAILNET

    @classmethod
    def setUpClass(cls):
        cls.bench = serve.Workbench()
        cls.server = serve.make_server(0, tailnet_host=cls.tailnet, bench=cls.bench, runner=cls._run)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    @classmethod
    def _run(cls, bench, name, subject):
        if cls.runner is not None:
            return cls.runner(bench, name, subject)
        return bench.run(name, subject)

    def request(self, method, path, body=None, headers=None, raw=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        sent = dict(headers or {})
        data = raw
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            sent.setdefault("Content-Type", "application/json")
        conn.request(method, path, body=data, headers=sent)
        response = conn.getresponse()
        payload = response.read()
        result = (response.status, dict(response.getheaders()), payload)
        conn.close()
        return result

    def get_json(self, path):
        status, _, payload = self.request("GET", path)
        self.assertEqual(status, 200, payload)
        return json.loads(payload)

    def post_json(self, path, body, headers=None):
        status, head, payload = self.request("POST", path, body=body, headers=headers)
        return status, json.loads(payload), head


class RoutesTest(ServerTest):
    def test_packs_lists_the_shipped_packs(self):
        data = self.get_json("/api/packs")
        self.assertEqual([p["name"] for p in data["packs"]], ["lantern-shelf", "minimal", "social-ten", "solo", "team-ten"])
        team = next(p for p in data["packs"] if p["name"] == "team-ten")
        self.assertEqual((team["users"], team["days"]), (10, 21))
        self.assertEqual(data["subjects"], list(cli.BUILTINS))

    def test_pack_detail_has_timeline_and_actors(self):
        data = self.get_json("/api/pack?name=minimal")
        self.assertTrue(data["events"] and data["actors"] and data["facts"] and data["checks"])
        self.assertIn("text", data["events"][0])
        react = [e for e in data["events"] if e["kind"] == "react"]
        self.assertEqual(react[0]["emoji"], "+1")

    def test_run_matches_the_command_line_path(self):
        status, data, head = self.post_json("/api/run", {"pack": "team-ten", "subject": "naive_bot"})
        self.assertEqual(status, 200)
        the_pack = pack.load(ROOT / "packs" / "team-ten")
        result, _ = cli._run_once(the_pack, cli._builtin_subject("naive_bot"))
        self.assertEqual(data["digest"], result.digest)
        self.assertEqual(
            [(c["check"], c["verdict"], c["reason"]) for c in data["report"]["checks"]],
            [(v.check, v.verdict, v.reason) for v in result.verdicts],
        )
        self.assertEqual(len(data["entries"]), len(result.entries))
        self.assertEqual(head["Cache-Control"], "no-store")

    def test_validate_matrix_equals_controls_matrix(self):
        status, data, _ = self.post_json("/api/validate", {"pack": "minimal"})
        self.assertEqual(status, 200)
        the_pack = pack.load(ROOT / "packs" / "minimal")
        expected = controls.matrix(the_pack)
        got = {
            name: {cid: (c["verdict"], c.get("reason")) for cid, c in row.items()}
            for name, row in data["matrix"].items()
        }
        self.assertEqual(got, {n: {k: tuple(v) for k, v in row.items()} for n, row in expected.items()})
        self.assertEqual(data["problems"], [])

    def test_a_run_after_validate_carries_the_matrix(self):
        self.post_json("/api/validate", {"pack": "minimal"})
        _, data, _ = self.post_json("/api/run", {"pack": "minimal", "subject": "oracle"})
        self.assertIn("matrix", data["report"])

    def test_bad_names_are_400(self):
        for body in (
            {"pack": "nope", "subject": "oracle"},
            {"pack": "../packs/minimal", "subject": "oracle"},
            {"pack": "minimal", "subject": "python -c 1"},
            {"pack": "minimal", "subject": "nope"},
            {"pack": ["minimal"], "subject": "oracle"},
            {"subject": "oracle"},
        ):
            status, data, _ = self.post_json("/api/run", body)
            self.assertEqual(status, 400, body)
            self.assertEqual(len(data["error"].splitlines()), 1)
        self.assertEqual(self.request("GET", "/api/pack?name=../x")[0], 400)
        self.assertEqual(self.request("GET", "/api/pack")[0], 400)
        self.assertEqual(self.post_json("/api/validate", {"pack": "../x"})[0], 400)

    def test_malformed_bodies(self):
        self.assertEqual(self.request("POST", "/api/run", raw=b"not json", headers=JSON_TYPE)[0], 400)
        self.assertEqual(self.request("POST", "/api/run", raw=b"[1]", headers=JSON_TYPE)[0], 400)
        self.assertEqual(self.request("POST", "/api/run", raw=b"x" * 5000, headers=JSON_TYPE)[0], 413)

    def test_unknown_paths_and_methods(self):
        self.assertEqual(self.request("GET", "/nope")[0], 404)
        self.assertEqual(self.request("GET", "/teamsim/serve.py")[0], 404)
        self.assertEqual(self.request("GET", "/../README.md")[0], 404)
        self.assertEqual(self.request("GET", "/%2e%2e/README.md")[0], 404)
        self.assertEqual(self.request("GET", "/api/run")[0], 405)
        self.assertEqual(self.request("PUT", "/api/run", body={})[0], 405)

    def test_static_files_carry_the_csp(self):
        for path, kind in (("/", "text/html"), ("/app.js", "text/javascript"), ("/style.css", "text/css"),
                           ("/dm-sans.woff2", "font/woff2"), ("/dmsans-OFL.txt", "text/plain")):
            status, head, body = self.request("GET", path)
            self.assertEqual(status, 200, path)
            self.assertTrue(body)
            self.assertTrue(head["Content-Type"].startswith(kind))
            self.assertIn("default-src 'self'", head["Content-Security-Policy"])
            self.assertIn("frame-ancestors 'none'", head["Content-Security-Policy"])
            self.assertEqual(head["X-Content-Type-Options"], "nosniff")

    def test_page_has_no_external_requests_or_inline_script(self):
        page = (serve.WEB_DIR / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("http://", page)
        self.assertNotIn("https://", page)
        self.assertNotIn("<style", page)
        self.assertNotIn("onclick", page)
        script = (serve.WEB_DIR / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("innerHTML", script)
        self.assertNotIn("insertAdjacentHTML", script)


class RequestChecksTest(ServerTest):
    def test_bad_host_is_403(self):
        for host in ("evil.example", "127.0.0.1", "127.0.0.1:1", "localhost", "127.0.0.1.evil.example:%d" % 1):
            self.assertEqual(self.request("GET", "/api/packs", headers={"Host": host})[0], 403, host)
        self.assertEqual(self.request("GET", "/", headers={"Host": "evil.example"})[0], 403)

    def test_localhost_host_is_allowed(self):
        self.assertEqual(self.request("GET", "/api/packs", headers={"Host": "localhost:%d" % self.port})[0], 200)

    def test_tailnet_host_needs_the_login_header(self):
        self.assertEqual(self.request("GET", "/api/packs", headers={"Host": TAILNET})[0], 403)
        self.assertEqual(self.request("GET", "/api/packs", headers={"Host": TAILNET, "Tailscale-User-Login": " "})[0], 403)
        for host in (TAILNET, TAILNET + ":8443"):
            status = self.request(
                "GET", "/api/packs", headers={"Host": host, "Tailscale-User-Login": "someone@example.com"}
            )[0]
            self.assertEqual(status, 200, host)
        self.assertEqual(
            self.request(
                "GET", "/api/packs", headers={"Host": "evil." + TAILNET, "Tailscale-User-Login": "someone@example.com"}
            )[0],
            403,
        )

    def test_cross_origin_post_is_403(self):
        for origin in ("http://evil.example", "http://127.0.0.1:1", "null"):
            status, _, _ = self.post_json(
                "/api/run", {"pack": "minimal", "subject": "oracle"}, headers={"Origin": origin}
            )
            self.assertEqual(status, 403, origin)

    def test_same_origin_post_is_allowed(self):
        origin = "http://127.0.0.1:%d" % self.port
        status, _, _ = self.post_json("/api/run", {"pack": "minimal", "subject": "oracle"}, headers={"Origin": origin})
        self.assertEqual(status, 200)

    def test_wrong_content_type_is_415(self):
        body = b'{"pack": "minimal", "subject": "oracle"}'
        for headers in ({}, {"Content-Type": "text/plain"}, {"Content-Type": "application/x-www-form-urlencoded"}):
            self.assertEqual(self.request("POST", "/api/run", raw=body, headers=headers)[0], 415, headers)
        self.assertEqual(
            self.request("POST", "/api/run", raw=body, headers={"Content-Type": "application/json; charset=utf-8"})[0],
            200,
        )

    def test_errors_never_carry_a_traceback(self):
        def boom(bench, name, subject):
            raise RuntimeError("secret internals")

        type(self).runner = staticmethod(boom)
        try:
            status, data, _ = self.post_json("/api/run", {"pack": "minimal", "subject": "oracle"})
        finally:
            type(self).runner = None
        self.assertEqual(status, 500)
        self.assertEqual(data, {"error": "internal error"})


class HardeningTest(ServerTest):
    def raw(self, data):
        import socket

        with socket.create_connection(("127.0.0.1", self.port), timeout=10) as sock:
            sock.sendall(data)
            return sock.recv(65536)

    def test_malformed_request_line_logs_nothing_and_does_not_raise(self):
        import contextlib
        import io

        self.server.app.verbose = True
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err):
                reply = self.raw(b"GET / FOO\r\n\r\n")
                self.raw(b"GET /\x1b[2J HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n")
        finally:
            self.server.app.verbose = False
        self.assertTrue(reply.startswith(b"HTTP/"))
        self.assertNotIn("Traceback", err.getvalue())
        self.assertNotIn("\x1b", err.getvalue())

    def test_other_methods_check_the_host_first(self):
        self.assertEqual(self.request("HEAD", "/", headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(self.request("OPTIONS", "/api/run", headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(self.request("HEAD", "/")[0], 405)
        self.assertEqual(self.request("DELETE", "/")[0], 405)

    def test_handler_has_a_socket_timeout(self):
        self.assertTrue(0 < serve.Handler.timeout <= 30)


class OneRunTest(ServerTest):
    def test_second_concurrent_run_is_409(self):
        started, release = threading.Event(), threading.Event()

        def slow(bench, name, subject):
            if not bench.lock.acquire(blocking=False):
                raise serve.Busy()
            try:
                started.set()
                release.wait(10)
            finally:
                bench.lock.release()
            return {"ok": True}

        type(self).runner = staticmethod(slow)
        first = {}

        def go():
            first["result"] = self.post_json("/api/run", {"pack": "minimal", "subject": "oracle"})

        worker = threading.Thread(target=go)
        worker.start()
        try:
            self.assertTrue(started.wait(10))
            status, data, _ = self.post_json("/api/run", {"pack": "minimal", "subject": "oracle"})
            self.assertEqual(status, 409)
            self.assertEqual(len(data["error"].splitlines()), 1)
            self.assertEqual(self.post_json("/api/validate", {"pack": "minimal"})[0], 409)
        finally:
            release.set()
            worker.join()
            type(self).runner = None
        self.assertEqual(first["result"][0], 200)
        self.assertEqual(self.post_json("/api/run", {"pack": "minimal", "subject": "oracle"})[0], 200)


class BindTest(unittest.TestCase):
    def test_server_binds_loopback_only(self):
        server = serve.make_server(0)
        try:
            self.assertEqual(server.server_address[0], "127.0.0.1")
        finally:
            server.server_close()


if __name__ == "__main__":
    unittest.main()
