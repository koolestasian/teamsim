"""Runtime state under prototypes/teamctx-sim/.state: JSON stores with atomic writes, log, timeline."""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

from . import envfile

ROOT = Path(__file__).resolve().parents[1]


class Paths:
    """All runtime file locations. `root` is injectable so tests use a temp dir."""

    def __init__(self, root: Path = ROOT) -> None:
        self.root = Path(root)
        self.state = self.root / ".state"
        self.reports = self.root / "reports"

    @property
    def state_json(self) -> Path: return self.state / "state.json"
    @property
    def map_json(self) -> Path: return self.state / "map.json"
    @property
    def ids_json(self) -> Path: return self.state / "ids.json"
    @property
    def seed_json(self) -> Path: return self.state / "seed.json"
    @property
    def emu_log(self) -> Path: return self.state / "emu.log"
    @property
    def host_log(self) -> Path: return self.state / "host.log"
    @property
    def toml(self) -> Path: return self.state / "teamctx.toml"
    @property
    def db(self) -> Path: return self.state / "teamctx.db"
    @property
    def api_token(self) -> Path: return self.state / "api-token"
    @property
    def timeline(self) -> Path: return self.state / "timeline.jsonl"
    @property
    def harness_log(self) -> Path: return self.state / "harness.log"
    @property
    def export_dir(self) -> Path: return self.state / "export"
    @property
    def history_json(self) -> Path: return self.state / "history-experiment.json"

    def ensure(self) -> None:
        self.state.mkdir(parents=True, exist_ok=True)
        self.reports.mkdir(parents=True, exist_ok=True)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    # On Windows a reader that has the target open (the live view polls these files) makes
    # the swap fail with "Access is denied" for a few milliseconds. Retry briefly, never crash.
    for attempt in range(60):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 59:
                raise
            time.sleep(0.05)


class JsonStore:
    """A dict persisted as JSON. `save()` after every change that matters (resume depends on it)."""

    def __init__(self, path: Path, default: dict | None = None) -> None:
        self.path = path
        self.data: dict[str, Any] = {}
        if path.exists():
            try:
                self.data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.data = {}
        for key, value in (default or {}).items():
            self.data.setdefault(key, value)

    def save(self) -> None:
        atomic_write_text(self.path, json.dumps(self.data, indent=2, sort_keys=True))

    def __getitem__(self, key): return self.data[key]
    def __setitem__(self, key, value): self.data[key] = value
    def __contains__(self, key): return key in self.data
    def get(self, key, default=None): return self.data.get(key, default)
    def setdefault(self, key, default): return self.data.setdefault(key, default)


def now_iso(now: float | None = None) -> str:
    moment = dt.datetime.fromtimestamp(now, dt.UTC) if now is not None else dt.datetime.now(dt.UTC)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class Recorder:
    """Console + file log and the timeline. Everything passes through the redactor."""

    def __init__(self, paths: Paths, *, echo: bool = True, stream=None, clock=None) -> None:
        self.paths = paths
        self.echo = echo
        self.stream = stream or sys.stdout
        self.clock = clock  # callable -> epoch seconds, for tests
        self.events: list[dict] = []
        self._lock = threading.Lock()

    def _now(self) -> str:
        return now_iso(self.clock() if self.clock else None)

    def info(self, message: str) -> None:
        line = envfile.redact(f"[{self._now()}] {message}")
        if self.echo:
            print(line, file=self.stream, flush=True)
        self._append(self.paths.harness_log, line + "\n")

    def event(self, kind: str, summary: str, **fields: Any) -> dict:
        """A timeline entry: something that happened, with the time. Fields are redacted."""
        record = {"t": self._now(), "kind": kind, "summary": envfile.redact(summary)}
        for key, value in fields.items():
            record[key] = json.loads(envfile.redact(json.dumps(value, default=str)))
        with self._lock:
            self.events.append(record)
        self._append(self.paths.timeline, json.dumps(record, default=str) + "\n")
        return record

    def _append(self, path: Path, text: str) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock, open(path, "a", encoding="utf-8") as fh:
                fh.write(text)
        except OSError:
            pass  # logging must never break the run

    def load_events(self) -> list[dict]:
        events = list(self.events)
        if not events and self.paths.timeline.exists():
            for line in self.paths.timeline.read_text(encoding="utf-8").splitlines():
                try:
                    events.append(json.loads(line))
                except ValueError:
                    continue
        return events
