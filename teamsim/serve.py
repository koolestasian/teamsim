"""A local page that runs the engine and shows what it did (``ideas/specs/run-ui-v0.md``).

``python -m teamsim.serve [--port 8765] [--tailnet-host NAME]`` serves ``teamsim/web`` and a
small JSON interface on ``127.0.0.1``. It runs only the built-in subjects, so a page can never
start a program of its own choosing. Standard library only.

Every request is checked before it is handled: the ``Host`` header must name this server (or the
tailnet host, and then only with a ``Tailscale-User-Login`` header), and a POST must be JSON
from the same origin. One run or validation is in flight at a time; a second gets 409.

This module reads the ``packs`` directory and the ``web`` directory and keeps results in memory.
"""

import argparse
import json
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from teamsim import cli, controls, pack, report
from teamsim.model import At

ROOT = Path(__file__).resolve().parent.parent
PACKS_DIR = ROOT / "packs"
WEB_DIR = Path(__file__).resolve().parent / "web"
BODY_LIMIT = 4096
DAY_MS = 86_400_000
LOGIN_HEADER = "Tailscale-User-Login"

CSP = (
    "default-src 'self'; style-src 'self'; script-src 'self'; "
    "img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'"
)

# Fixed allowlist: the URL path picks a key, never a file name.
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}


class HttpError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class Busy(Exception):
    """Another run or validation holds the lock."""


# --- the work ----------------------------------------------------------------------


class Workbench:
    """The packs, the matrix cache and the lock that allows one run at a time."""

    def __init__(self, packs_dir: Path = PACKS_DIR):
        self.packs = {}
        for path in sorted(p for p in packs_dir.iterdir() if p.is_dir()):
            try:
                self.packs[path.name] = pack.load(path)
            except (pack.PackError, OSError):
                continue
        self.matrices = {}  # pack hash -> matrix
        self.lock = threading.Lock()

    def get(self, name) -> object:
        if not isinstance(name, str) or name not in self.packs:
            raise HttpError(400, "unknown pack; choose one of: %s" % ", ".join(self.packs))
        return self.packs[name]

    def subjects(self) -> list:
        return list(cli.BUILTINS)

    def summary(self, name: str) -> dict:
        p = self.packs[name]
        return {
            "name": name,
            "id": p.header.id,
            "title": p.header.title,
            "purpose": p.header.purpose,
            "users": len(p.actors),
            "days": _days(p),
            "surfaces": len(p.surfaces),
            "facts": len(p.facts),
            "checks": len(p.checks),
            "limits": list(p.header.limits),
        }

    def detail(self, name: str) -> dict:
        p = self.get(name)
        return {
            "name": name,
            "id": p.header.id,
            "actors": [a.to_obj() for a in p.actors],
            "surfaces": [s.to_obj() for s in p.surfaces],
            "facts": [f.to_obj() for f in p.facts],
            "checks": [c.to_obj() for c in p.checks],
            "events": [_event_obj(e) for e in p.events],
        }

    def run(self, name, subject) -> dict:
        p = self.get(name)
        if not isinstance(subject, str) or subject not in cli.BUILTINS:
            raise HttpError(400, "unknown subject; choose one of: %s" % ", ".join(cli.BUILTINS))
        if not self.lock.acquire(blocking=False):
            raise Busy()
        try:
            result, _ = cli._run_once(p, cli._builtin_subject(subject))
        finally:
            self.lock.release()
        matrix = self.matrices.get(pack.pack_hash(p))
        return {
            "report": report.json_obj(result, matrix=matrix),
            "entries": [e.to_obj() for e in result.entries],
            "digest": result.digest,
        }

    def validate(self, name) -> dict:
        p = self.get(name)
        if not self.lock.acquire(blocking=False):
            raise Busy()
        try:
            key = pack.pack_hash(p)
            if key not in self.matrices:
                self.matrices[key] = controls.matrix(p)
            matrix = self.matrices[key]
            lines = [cli._line(x) for x in controls.validate(p)]
        finally:
            self.lock.release()
        problems = [x for x in lines if not any(m in x for m in cli._INFORMATION)]
        return {
            "matrix": _matrix_obj(matrix),
            "lines": lines,
            "problems": problems,
        }


def _matrix_obj(matrix) -> dict:
    return {
        control: {check: {"verdict": v, **({"reason": r} if r else {})} for check, (v, r) in row.items()}
        for control, row in matrix.items()
    }


def _days(p) -> int:
    times = [e.when.ms for e in p.events if isinstance(e.when, At)]
    return (max(times) // DAY_MS + 1) if times else 0


def _event_obj(event) -> dict:
    obj = event.to_obj()
    out = {"id": obj["id"], "at": obj.get("at"), "actor": obj["actor"], "surface": obj["surface"], "kind": obj["kind"]}
    for name in ("text", "target", "discloses", "depends_on", "probe"):
        if name in obj:
            out[name] = obj[name]
    return out


# --- HTTP --------------------------------------------------------------------------


def _json_bytes(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _one_line(text: object) -> str:
    return " ".join(str(text).split())[:200]


class Handler(BaseHTTPRequestHandler):
    server_version = "teamsim-serve"
    sys_version = ""
    protocol_version = "HTTP/1.0"

    timeout = 10  # a client that stalls mid-request does not hold a thread forever

    def log_message(self, format, *args):  # never log bodies; one line per request, no query
        if self.server.app.verbose:
            path = urlsplit(getattr(self, "path", "") or "").path
            line = "%s %s" % (self.command or "-", path)
            sys.stderr.write("".join(c if " " <= c <= "~" else "?" for c in line) + "\n")

    # -- checks --
    def _check_host(self):
        host = self.headers.get("Host", "")
        app = self.server.app
        if host in app.local_hosts:
            return
        if app.tailnet_host and re.fullmatch(re.escape(app.tailnet_host) + r"(:\d{1,5})?", host):
            if self.headers.get(LOGIN_HEADER, "").strip():
                return
        raise HttpError(403, "host not allowed")

    def _check_post(self):
        content_type = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if content_type != "application/json":
            raise HttpError(415, "content type must be application/json")
        origin = self.headers.get("Origin")
        if origin is not None and urlsplit(origin).netloc != self.headers.get("Host", ""):
            raise HttpError(403, "cross-origin request refused")

    def _body(self) -> dict:
        length = self.headers.get("Content-Length")
        if length is None or not length.isdigit():
            raise HttpError(411, "a content length is required")
        if int(length) > BODY_LIMIT:
            raise HttpError(413, "request body too large")
        raw = self.rfile.read(int(length))
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise HttpError(400, "the body is not valid JSON") from None
        if not isinstance(obj, dict):
            raise HttpError(400, "the body must be a JSON object")
        return obj

    # -- replies --
    def _send(self, status: int, body: bytes, content_type: str, api: bool):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        if api:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _fail(self, status: int, message: str):
        self._send(status, _json_bytes({"error": _one_line(message)}), "application/json; charset=utf-8", True)

    def _handle(self, method: str):
        try:
            self._check_host()
            url = urlsplit(self.path)
            route = url.path
            app = self.server.app
            if method == "GET" and route in STATIC:
                name, content_type = STATIC[route]
                try:
                    body = (WEB_DIR / name).read_bytes()
                except OSError:
                    raise HttpError(404, "not found") from None
                return self._send(200, body, content_type, False)
            if method not in ("GET", "POST"):
                raise HttpError(405, "method not allowed")
            if route.startswith("/api/"):
                return self._api(method, route, parse_qs(url.query), app.bench)
            raise HttpError(404, "not found")
        except HttpError as error:
            self._fail(error.status, error.message)
        except Busy:
            self._fail(409, "another run is in progress")
        except Exception:  # never a traceback, never internals
            self._fail(500, "internal error")

    def _api(self, method, route, query, bench):
        if method == "GET" and route == "/api/packs":
            return self._ok({"packs": [bench.summary(n) for n in bench.packs], "subjects": bench.subjects()})
        if method == "GET" and route == "/api/pack":
            names = query.get("name", [])
            return self._ok(bench.detail(names[0] if len(names) == 1 else None))
        if method == "POST" and route in ("/api/run", "/api/validate"):
            self._check_post()
            body = self._body()
            if route == "/api/run":
                return self._ok(self.server.app.runner(bench, body.get("pack"), body.get("subject")))
            return self._ok(bench.validate(body.get("pack")))
        if route in ("/api/packs", "/api/pack", "/api/run", "/api/validate"):
            raise HttpError(405, "method not allowed")
        raise HttpError(404, "not found")

    def _ok(self, obj):
        self._send(200, _json_bytes(obj), "application/json; charset=utf-8", True)

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_HEAD(self):
        self._handle("HEAD")

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_HEAD


class _App:
    def __init__(self, port, tailnet_host, bench, runner):
        self.local_hosts = {"127.0.0.1:%d" % port, "localhost:%d" % port}
        self.tailnet_host = tailnet_host
        self.bench = bench
        self.runner = runner
        self.verbose = False


def _default_runner(bench, name, subject):
    return bench.run(name, subject)


def make_server(port: int = 8765, tailnet_host=None, runner=None, bench=None) -> ThreadingHTTPServer:
    """A server bound to loopback. ``runner(bench, pack, subject)`` may be replaced in tests."""
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.app = _App(server.server_address[1], tailnet_host, bench or Workbench(), runner or _default_runner)
    return server


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m teamsim.serve", description="Run the teamsim page.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--tailnet-host", default=None, help="extra Host name to accept (needs Tailscale-User-Login)")
    args = parser.parse_args(argv)
    server = make_server(args.port, args.tailnet_host)
    server.app.verbose = True
    print("teamsim page on http://127.0.0.1:%d" % server.server_address[1], flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
