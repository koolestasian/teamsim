"""The live view server: loopback only, one page, one story API, one guarded start endpoint.

    GET  /               the page (with a per-process nonce embedded)
    GET  /api/story      {mode, next, events, run, ...} built by simlib/story.py from the .state files
    POST /api/start      starts the whole scenario in a subprocess owned by this server

`/api/start` is the only endpoint that changes anything. It refuses unless the request is a POST,
the Host header and the Origin are exactly this server's own `127.0.0.1:<port>`, and the
`X-Viz-Nonce` header carries the random nonce that was embedded in the served page (so another
local web page cannot trigger a run). Only one run can be active at a time.
"""

from __future__ import annotations

import hmac
import json
import secrets
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import script as S, story
from .net import PolicyError
from .state import Paths, atomic_write_text

LOOPBACK = "127.0.0.1"
PAGE_PATH = Path(__file__).resolve().parents[1] / "viz" / "index.html"
SIM_PY = Path(__file__).resolve().parents[1] / "sim.py"
NONCE_PLACEHOLDER = "__VIZ_NONCE__"
CSP = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; "
       "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


# ---- run control -------------------------------------------------------------------------


class RunController:
    """Owns at most one run. `launcher()` returns a Popen-like handle (`poll`, `terminate`).

    Tests pass a fake launcher, so no real run ever starts from a test. `set_external` marks a run
    that is driven by this same process (`run-all --watch`): it blocks starts but is not owned.
    """

    def __init__(self, launcher=None, clock=time.time) -> None:
        self.launcher = launcher
        self.clock = clock
        self.handle = None
        self.external = False
        self.started_at: float | None = None
        self.error: str | None = None
        self._lock = threading.Lock()

    @property
    def active(self) -> bool:
        return self.external or (self.handle is not None and self.handle.poll() is None)

    def set_external(self, active: bool) -> None:
        with self._lock:
            if active:
                self.started_at = self.clock()
                self.error = None
            self.external = active

    def start(self) -> str:
        """'started', 'busy' or 'failed'."""
        with self._lock:
            if self.active:
                return "busy"
            if self.launcher is None:
                return "failed"
            self.error = None
            self.started_at = self.clock()
            try:
                self.handle = self.launcher()
            except OSError:
                self.handle = None
                self.error = "The run could not be started."
                return "failed"
            return "started"

    def finished_badly(self) -> str | None:
        """A friendly error once an owned run has exited with a failure."""
        if self.handle is not None and not self.external:
            code = self.handle.poll()
            if code not in (None, 0):
                return "The run stopped before it finished."
        return self.error

    def stop(self) -> None:
        handle = self.handle
        if handle is not None and handle.poll() is None:
            try:
                handle.terminate()
            except OSError:
                pass


def subprocess_launcher(root: Path):
    """Starts `sim.py run-all --force --paced` as a child of this server process.

    The child stays attached to the server (same console, no DETACHED flags), so the emulator it
    starts lives as long as the long-lived server window does."""
    log_path = root / "viz-run.log"

    def launch():
        log = open(log_path, "ab")
        try:
            return subprocess.Popen([sys.executable, "-I", str(SIM_PY), "run-all", "--force", "--paced"], cwd=str(root),
                                    stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        finally:
            log.close()

    return launch


# ---- reading the files -------------------------------------------------------------------


def _stat(path: Path) -> tuple[int, int] | None:
    try:
        st = path.stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def read_speed(path: Path) -> int:
    """The saved live pace (1, 2, 4 or 8); 1 when unset or unreadable."""
    try:
        value = int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return 1
    return value if value in (1, 2, 4, 8) else 1


def read_timeline(path: Path) -> list[dict]:
    """Complete lines only: a line the harness is still writing is left for the next request."""
    try:
        raw = path.read_bytes()
    except OSError:
        return []
    chunks = raw.split(b"\n")
    if chunks and chunks[-1] != b"":
        chunks.pop()
    events = []
    for chunk in chunks:
        try:
            value = json.loads(chunk.decode("utf-8"))
        except ValueError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


class StoryService:
    """Builds the story from the harness files on every request (cached until a file changes)."""

    def __init__(self, paths: Paths, dataset_path: Path = S.DATASET_PATH, controller: RunController | None = None,
                 clock=time.time) -> None:
        self.paths = paths
        self.dataset_path = dataset_path
        self.controller = controller
        self.clock = clock
        self._cache: tuple | None = None
        self._dataset: tuple | None = None
        self._lock = threading.Lock()

    def dataset(self) -> dict:
        key = _stat(self.dataset_path)
        if self._dataset is None or self._dataset[0] != key:
            self._dataset = (key, read_json(self.dataset_path, {"members": [], "messages": []}))
        return self._dataset[1]

    def payload(self, since: int = 0, with_events: bool = True) -> dict:
        with self._lock:
            now = self.clock()
            ctl = self.controller
            key = (_stat(self.paths.timeline), _stat(self.paths.map_json), _stat(self.paths.state_json),
                   ctl.started_at if ctl else None)
            if self._cache is None or self._cache[0] != key:
                timeline = read_timeline(self.paths.timeline)  # first: the harness saves state before it logs
                if ctl is not None and ctl.started_at is not None:
                    timeline = [e for e in timeline if story.epoch_of(e.get("t") or "") >= ctl.started_at - 1.0]
                mapping = read_json(self.paths.map_json, {"items": {}})
                state = read_json(self.paths.state_json, {})
                events = story.build_story(timeline, mapping, state, self.dataset())
                self._cache = (key, timeline, events)
            _, timeline, events = self._cache
            stat = key[0]
            age = None if stat is None else max(0.0, now - stat[0] / 1e9)
            active = bool(ctl and ctl.active)
            mode = story.detect_mode(timeline, age, active)
            total = len(events)
            reset = with_events and since > total
            first = 0 if reset else max(0, since)
            run = {"active": active, "note": story.setup_note(timeline) if active else None,
                   "error": ctl.finished_badly() if ctl else None, "can_start": bool(ctl and ctl.launcher is not None),
                   "speed": read_speed(self.paths.root / "watch-speed")}
            return {"mode": mode, "next": total, "total": total, "reset": reset,
                    "events": events[first:] if with_events else [],
                    "run": run, "has_run": bool(timeline), "server_time": round(now, 3)}


# ---- HTTP --------------------------------------------------------------------------------


class VizServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, address, handler, *, service: StoryService, controller: RunController, nonce: str,
                 page_path: Path = PAGE_PATH) -> None:
        super().__init__(address, handler)
        self.service = service
        self.controller = controller
        self.nonce = nonce
        self.page_path = page_path

    @property
    def port(self) -> int:
        return self.server_address[1]

    @property
    def url(self) -> str:
        return f"http://{LOOPBACK}:{self.port}/"


class Handler(BaseHTTPRequestHandler):
    server_version = "viz"
    sys_version = ""
    server: VizServer

    def log_message(self, format, *args) -> None:  # noqa: A002 - quiet
        return

    # -- plumbing

    def _send(self, status: int, body: bytes = b"", ctype: str = "application/json; charset=utf-8", extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CSP)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, obj, extra: dict | None = None) -> None:
        self._send(status, json.dumps(obj).encode("utf-8"), extra=extra)

    def _own(self) -> str:
        return f"{LOOPBACK}:{self.server.port}"

    def _host_ok(self) -> bool:
        return self.headers.get("Host") == self._own()

    # -- verbs

    def do_GET(self) -> None:
        if not self._host_ok():
            return self._json(403, {"error": "open this page at " + self.server.url})
        parts = urlsplit(self.path)
        if parts.path in ("/", "/index.html"):
            try:
                page = self.server.page_path.read_text(encoding="utf-8").replace(NONCE_PLACEHOLDER, self.server.nonce)
            except OSError:
                return self._json(500, {"error": "page file missing"})
            return self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
        if parts.path == "/api/story":
            try:
                since = int(parse_qs(parts.query).get("since", ["0"])[0])
            except ValueError:
                since = 0
            info_only = "info" in parse_qs(parts.query)  # no events: just the run state, cheap to poll
            return self._json(200, self.server.service.payload(max(0, since), with_events=not info_only))
        if parts.path == "/api/start":
            return self._json(405, {"error": "POST only"}, {"Allow": "POST"})
        if parts.path == "/favicon.ico":
            return self._send(204)
        return self._json(404, {"error": "not found"})

    do_HEAD = do_GET

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path not in ("/api/start", "/api/speed"):
            return self._json(404, {"error": "not found"})
        origin = self.headers.get("Origin") or ""
        nonce = self.headers.get("X-Viz-Nonce") or ""
        if (not self._host_ok() or origin != f"http://{self._own()}"
                or not hmac.compare_digest(nonce.encode("utf-8"), self.server.nonce.encode("utf-8"))):
            return self._json(403, {"error": "refused"})
        try:  # drain what was declared (bounded) so the connection closes cleanly
            body = self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 4096))
        except (ValueError, OSError):
            body = b""
        if path == "/api/speed":
            return self._set_speed(body)
        if self.server.service.payload(0, with_events=False)["mode"] == "live":
            # A run started from a terminal is writing to the same .state right now: never start a second one.
            return self._json(409, {"error": "A run is already in progress."})
        result = self.server.controller.start()
        if result == "started":
            return self._json(202, {"started": True})
        if result == "busy":
            return self._json(409, {"error": "A run is already in progress."})
        return self._json(500, {"error": "The run could not be started."})

    def _set_speed(self, body: bytes) -> None:
        """Live pace for watched runs: the run's driver reads this file before every pause."""
        try:
            speed = float(json.loads(body.decode("utf-8") or "{}").get("speed"))
        except (ValueError, TypeError, AttributeError, UnicodeDecodeError):
            return self._json(400, {"error": "speed must be 1, 2, 4 or 8"})
        if speed not in (1.0, 2.0, 4.0, 8.0):
            return self._json(400, {"error": "speed must be 1, 2, 4 or 8"})
        atomic_write_text(self.server.service.paths.root / "watch-speed", str(int(speed)))
        return self._json(200, {"speed": int(speed)})

    def _not_allowed(self) -> None:
        self._json(405, {"error": "method not allowed"}, {"Allow": "GET, POST"})

    do_PUT = do_DELETE = do_PATCH = _not_allowed


def make_server(paths: Paths, port: int = 4100, host: str = LOOPBACK, *, controller: RunController | None = None,
                nonce: str | None = None, dataset_path: Path = S.DATASET_PATH, page_path: Path = PAGE_PATH) -> VizServer:
    """A loopback-only server. Any other bind address is refused."""
    if host != LOOPBACK:
        raise PolicyError(f"the live view binds to {LOOPBACK} only, not {host!r}")
    controller = controller or RunController()
    service = StoryService(paths, dataset_path, controller)
    return VizServer((host, port), Handler, service=service, controller=controller,
                     nonce=nonce or secrets.token_urlsafe(24), page_path=page_path)
