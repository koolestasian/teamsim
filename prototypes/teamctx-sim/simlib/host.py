"""The teamctx host under test: binary, config, process, token, JSON API client, DB reader.

The harness never builds Rust. It runs a binary it is given. The bot token (an emulator
fake) and the LLM key reach only the child process environment.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import time
import tomllib
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import envfile
from .net import Response, Transport, assert_loopback_url

BINARY_SETTING = "TEAMSIM_TEAMCTX_BINARY"


def _configured_binary() -> Path:
    """The teamctx binary under test: the environment, else the repo's gitignored .env. Never a
    hard-coded personal path, so the code can go public as is."""
    value = os.environ.get(BINARY_SETTING, "")
    env_file = Path(__file__).resolve().parents[3] / ".env"
    if not value and env_file.is_file():
        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            key, sep, rest = line.partition("=")
            if sep and key.strip() == BINARY_SETTING:
                value = rest.strip().strip('"').strip("'")
    return Path(value) if value else Path(f"<{BINARY_SETTING} not set>")


DEFAULT_BINARY = _configured_binary()
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_PROBE_MODEL = "anthropic/claude-haiku-5.5"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "anthropic/claude-sonnet-5.5"
LMSTUDIO_MODELS = "http://127.0.0.1:1234/v1/models"
LLM_TOKEN_BUDGET = 150_000
CHILD_ENV_KEEP = ("PATH", "SYSTEMROOT", "SystemRoot", "TEMP", "TMP", "USERPROFILE", "HOMEDRIVE", "HOMEPATH",
                  "APPDATA", "LOCALAPPDATA", "COMSPEC", "WINDIR", "PATHEXT", "PROGRAMDATA")
MARK = "<team-chat-data>"
MARK_END = "</team-chat-data>"


class HostError(Exception):
    pass


def resolve_binary(arg: str | None) -> Path:
    path = Path(arg) if arg else DEFAULT_BINARY
    if not path.is_file():
        raise HostError(
            f"teamctx binary not found at {path}. Build teamctx with the loopback `[discord] api_url` setting, "
            f"then set {BINARY_SETTING} in the repo's .env or pass --teamctx PATH; the harness never builds Rust itself."
        )
    return path


# ---- config -----------------------------------------------------------------------------


def set_toml_key(text: str, table: str, key: str, literal: str) -> str:
    """Sets `key = literal` inside `[table]` (replacing an existing key, else adding it)."""
    lines = text.splitlines()
    header = f"[{table}]"
    start = next((i for i, l in enumerate(lines) if l.strip() == header), None)
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines += [header, f"{key} = {literal}"]
        return "\n".join(lines) + "\n"
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].lstrip().startswith("["):
            end = i
            break
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    for i in range(start + 1, end):
        if pattern.match(lines[i]):
            lines[i] = f"{key} = {literal}"
            return "\n".join(lines) + "\n"
    last = start
    for i in range(start + 1, end):
        if lines[i].strip() and not lines[i].lstrip().startswith("#"):
            last = i
    lines.insert(last + 1, f"{key} = {literal}")
    return "\n".join(lines) + "\n"


def toml_str(value: str) -> str:
    return json.dumps(value)  # a JSON string is a valid TOML basic string for our values


@dataclass
class ModelChoice:
    kind: str  # openrouter | lmstudio | none
    reason: str
    table: dict | None = None  # [llm] keys
    env: dict[str, envfile.Secret] = field(default_factory=dict)  # child env additions, kept as Secrets
    probe_status: int | None = None


def apply_llm(text: str, choice: ModelChoice) -> str:
    if choice.table is None:
        return text
    out = text
    for key, value in choice.table.items():
        literal = toml_str(value) if isinstance(value, str) else str(value)
        out = set_toml_key(out, "llm", key, literal)
    return out


def build_config(init_output: str, *, api_url: str, choice: ModelChoice, bind: str | None = None) -> str:
    """Turns the binary's `init` output into the harness config. Validates it parses as TOML."""
    assert_loopback_url(api_url)
    text = "\n".join(l for l in init_output.splitlines() if not l.startswith("# Invite")) + "\n"
    text = set_toml_key(text, "discord", "api_url", toml_str(api_url))
    if bind:
        text = set_toml_key(text, "server", "bind", toml_str(bind))
    text = apply_llm(text, choice)
    tomllib.loads(text)  # raises on a broken file
    return text


def probe_openrouter(transport: Transport, key: envfile.Secret | None) -> tuple[int | None, bool]:
    """One chat completion with max_tokens 5. Returns (HTTP status or None, ok). Never logs the key."""
    if not key:
        return None, False
    try:
        resp = transport.request(
            "POST", OPENROUTER_URL,
            headers={"Authorization": "Bearer " + key.reveal(), "Content-Type": "application/json"},
            json={"model": OPENROUTER_PROBE_MODEL, "max_tokens": 5, "messages": [{"role": "user", "content": "ping"}]},
            timeout=30.0,
        )
    except OSError:
        return None, False
    return resp.status, resp.status == 200


def probe_lmstudio(transport: Transport) -> str | None:
    """The first listed chat model of LM Studio on loopback, or None."""
    try:
        resp = transport.request("GET", LMSTUDIO_MODELS, timeout=3.0)
    except OSError:
        return None
    if resp.status != 200:
        return None
    try:
        models = [m.get("id") for m in (resp.json() or {}).get("data", []) if m.get("id")]
    except ValueError:
        return None
    chat = [m for m in models if "embed" not in m.lower()]
    return chat[0] if chat else None


def choose_model(or_transport: Transport, local_transport: Transport, key: envfile.Secret | None) -> ModelChoice:
    status, ok = probe_openrouter(or_transport, key)
    if ok:
        return ModelChoice(
            "openrouter", f"OpenRouter probe with {OPENROUTER_PROBE_MODEL} returned 200",
            table={"provider": "openai_compatible", "base_url": OPENROUTER_BASE, "model": OPENROUTER_MODEL,
                   "api_key_env": "TEAMCTX_LLM_KEY", "max_questions_per_member_per_hour": 40,
                   "max_tokens_per_day": LLM_TOKEN_BUDGET},
            env={"TEAMCTX_LLM_KEY": key} if key else {}, probe_status=status)
    why = "no TEAMCTX_LLM_KEY in .env" if not key else f"OpenRouter probe failed (HTTP {status})"
    model = probe_lmstudio(local_transport)
    if model:
        return ModelChoice(
            "lmstudio", f"{why}; LM Studio answers on loopback, using its first chat model",
            table={"provider": "openai_compatible", "base_url": "http://127.0.0.1:1234/v1", "model": model,
                   "api_key_env": "TEAMCTX_LOCAL_LLM_KEY", "max_questions_per_member_per_hour": 40,
                   "max_tokens_per_day": LLM_TOKEN_BUDGET}, probe_status=status)
    return ModelChoice("none", f"{why}; LM Studio does not answer on 127.0.0.1:1234", probe_status=status)


# ---- the process ------------------------------------------------------------------------


def child_env(base: dict[str, str], extra: "dict[str, str | envfile.Secret]") -> dict[str, str]:
    """A filtered environment for the child: only what it needs, plus `extra` (Secrets revealed here only)."""
    env = {k: v for k, v in base.items() if k in CHILD_ENV_KEEP}
    for key, value in extra.items():
        env[key] = value.reveal() if isinstance(value, envfile.Secret) else value
    env.setdefault("RUST_LOG", "info")
    return env


def run_cli(binary: Path, args: list[str], *, env: dict[str, str] | None = None, timeout: float = 120.0,
            runner=subprocess) -> subprocess.CompletedProcess:
    """Runs a one-shot teamctx command and returns the finished process (bytes captured)."""
    return runner.run([str(binary), *args], capture_output=True, env=env, timeout=timeout,
                      creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def text_of(proc: subprocess.CompletedProcess) -> tuple[str, str]:
    return (proc.stdout or b"").decode("utf-8", "replace"), (proc.stderr or b"").decode("utf-8", "replace")


class HostProcess:
    def __init__(self, binary: Path, config: Path, db: Path, log: Path, env: dict[str, str], *, runner=subprocess) -> None:
        self.binary, self.config, self.db, self.log, self.env = binary, config, db, log, env
        self.runner = runner
        self.proc: subprocess.Popen | None = None

    def start(self) -> None:
        self.log.parent.mkdir(parents=True, exist_ok=True)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        handle = open(self.log, "ab")
        handle.write(f"\n--- start {time.strftime('%Y-%m-%dT%H:%M:%S')} ---\n".encode())
        handle.flush()
        self.proc = self.runner.Popen([str(self.binary), "run", "--config", str(self.config), "--db", str(self.db)],
                                      env=self.env, stdout=handle, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                      creationflags=flags)
        handle.close()

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def exit_code(self) -> int | None:
        return None if self.proc is None else self.proc.poll()

    def stop(self, timeout: float = 15.0) -> int | None:
        """Windows: teamctx's graceful shutdown listens only for Ctrl-C in its own console, which a
        harness cannot deliver, so this is a hard stop (also a free crash-recovery test)."""
        if self.proc is None:
            return None
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(10)
        code = self.proc.returncode
        with open(self.log, "ab") as fh:
            fh.write(f"--- stopped by harness, exit {code} ---\n".encode())
        return code

    def log_tail(self, lines: int = 40) -> str:
        try:
            text = self.log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return envfile.redact("\n".join(text.splitlines()[-lines:]))


# ---- the JSON API -----------------------------------------------------------------------


def parse_framed(text: str) -> tuple[list[str], str]:
    """Splits an API `text` into (lines of the framed block, tail written by the host).

    The block is: notice, blank line, `<team-chat-data>`, one JSON string, `</team-chat-data>`."""
    lines = text.split("\n")
    try:
        start = lines.index(MARK)
        end = lines.index(MARK_END)
    except ValueError:
        return [], text
    inner = "\n".join(lines[start + 1:end]).strip()
    try:
        decoded = json.loads(inner)
    except ValueError:
        return [], text
    tail = "\n".join(lines[end + 1:]).strip()
    return decoded.split("\n"), tail


MESSAGE_LINE = re.compile(r"^(?:\s*\(context\)\s*)?(m:\d+) \| (?P<author>.+?) in #(?P<channel>\S+) \| (?P<date>[^|]+?) \| (?P<text>.*)$")
ENTRY_LINE = re.compile(
    r"^(?P<id>[DTQ]-\d+) (?P<kind>decision|task|question) (?P<status>\w+) \| (?P<date>[^|]+?)"
    r"(?: \| owner (?P<owner>.+?))?(?: \| due (?P<due>\d{4}-\d{2}-\d{2}[^|]*?))? \| (?P<title>.*)$"
)
JUMP = re.compile(r"https://discord\.com/channels/(\d+)/(\d+)/(\d+)")


def parse_entry_line(line: str) -> dict | None:
    m = ENTRY_LINE.match(line)
    return m.groupdict() if m else None


def parse_message_line(line: str) -> dict | None:
    m = MESSAGE_LINE.match(line)
    return m.groupdict() if m else None


def jump_ids(link: str | None) -> tuple[str, str, str] | None:
    m = JUMP.search(link or "")
    return (m.group(1), m.group(2), m.group(3)) if m else None


class Api:
    """JSON API client (`/api/v1/*`). The token is read from a file on every call and never logged."""

    def __init__(self, transport: Transport, base: str, token_file: Path) -> None:
        self.base = assert_loopback_url(base).rstrip("/")
        self.transport = transport
        self.token_file = token_file

    def _headers(self) -> dict[str, str]:
        token = self.token_file.read_text(encoding="utf-8").strip()
        envfile.REDACTOR.add(token)
        return {"Authorization": f"Bearer {token}"}

    def get(self, path: str, params: dict | None = None) -> Response:
        query = "?" + urllib.parse.urlencode(params) if params else ""
        return self.transport.request("GET", f"{self.base}{path}{query}", headers=self._headers(), timeout=30.0)

    def healthz(self) -> bool:
        try:
            return self.transport.request("GET", self.base + "/healthz", timeout=3.0).status == 200
        except OSError:
            return False

    def status(self) -> dict | None:
        r = self.get("/api/v1/status")
        return r.json() if r.ok else None

    def search(self, q: str, cursor: str | None = None) -> Response:
        return self.get("/api/v1/search", {"q": q, **({"cursor": cursor} if cursor else {})})

    def context(self, text: str, limit: int = 10) -> Response:
        return self.get("/api/v1/context", {"text": text, "limit": limit})

    def record(self, **kw) -> Response:
        return self.get("/api/v1/record", {k: v for k, v in kw.items() if v is not None})

    def whats_new(self, since: str) -> Response:
        return self.get("/api/v1/whats-new", {"since": since})

    def read(self, ident: str, **kw) -> Response:
        return self.get("/api/v1/read", {"id": ident, **kw})

    def ask(self, question: str) -> Response:
        return self.transport.request("POST", self.base + "/api/v1/ask", headers=self._headers(),
                                      json={"question": question}, timeout=120.0)

    def all_record(self, **filters) -> list[dict]:
        """Every record entry (following cursors) as {id, kind, status, link, line parsed}."""
        out: list[dict] = []
        cursor = None
        for _ in range(20):
            r = self.record(**filters, cursor=cursor)
            if not r.ok:
                break
            body = r.json()
            lines, _ = parse_framed(body.get("text", ""))
            by_id = {i["id"]: i for i in body.get("items", [])}
            for line in lines:
                parsed = parse_entry_line(line)
                if parsed:
                    ref = by_id.get(parsed["id"], {})
                    parsed["link"] = ref.get("link")
                    out.append(parsed)
            cursor = body.get("next_cursor")
            if not cursor:
                break
        return out


def extract_token(output: str) -> str | None:
    """The `tctx_...` value from `token create` stdout (never printed by the caller)."""
    m = re.search(r"\btctx_[A-Za-z0-9_\-]+", output)
    if m:
        envfile.REDACTOR.add(m.group(0))
        return m.group(0)
    return None


# ---- the database (read-only) -----------------------------------------------------------


class StoreReader:
    """Reads the host's SQLite file read-only, for ground-truth checks the API cannot answer."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        uri = "file:" + urllib.parse.quote(str(self.path).replace("\\", "/")) + "?mode=ro"
        con = sqlite3.connect(uri, uri=True, timeout=5.0)
        con.row_factory = sqlite3.Row
        return con

    def exists(self) -> bool:
        return self.path.exists()

    def _rows(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        try:
            con = self._connect()
        except sqlite3.Error:
            return []
        try:
            return con.execute(sql, params).fetchall()
        except sqlite3.Error:
            return []
        finally:
            con.close()

    def messages(self) -> list[dict]:
        rows = self._rows(
            "SELECT m.external_id AS id, c.external_id AS channel_id, c.name AS channel, c.kind AS ckind, "
            "a.display_name AS author, a.external_id AS author_id, a.is_bot AS is_bot, m.content AS content, "
            "m.created_at AS created_at, m.edited_at AS edited_at, m.reply_to_ext AS reply_to, "
            "m.attachment_names AS attachments FROM messages m JOIN channels c ON c.id = m.channel_id "
            "LEFT JOIN members a ON a.id = m.author_id")
        return [dict(r) for r in rows]

    def entries(self) -> list[dict]:
        rows = self._rows(
            "SELECT e.id AS id, e.kind AS kind, e.status AS status, e.title AS title, e.title_is_copied AS copied, "
            "o.display_name AS owner, e.due_at AS due_at, sm.external_id AS source_ext, e.source_deleted AS source_deleted, "
            "e.superseded_by AS superseded_by, am.external_id AS answered_ext, e.created_via AS via, "
            "cb.display_name AS created_by FROM record_entries e "
            "LEFT JOIN members o ON o.id = e.owner_member_id LEFT JOIN messages sm ON sm.id = e.source_message_id "
            "LEFT JOIN messages am ON am.id = e.answered_by_message_id LEFT JOIN members cb ON cb.id = e.created_by_member_id")
        return [dict(r) for r in rows]

    def cursors(self) -> list[dict]:
        rows = self._rows("SELECT c.external_id AS channel_id, c.name AS name, s.newest_seen_ext AS newest, "
                          "s.oldest_backfilled_ext AS oldest, s.backfill_done AS done FROM sync_cursors s "
                          "JOIN channels c ON c.id = s.channel_id")
        return [dict(r) for r in rows]

    def channels(self) -> list[dict]:
        return [dict(r) for r in self._rows("SELECT external_id AS id, name, kind, is_included AS included FROM channels")]

    def llm_usage(self) -> dict:
        rows = self._rows("SELECT COALESCE(SUM(input_tokens),0) AS i, COALESCE(SUM(output_tokens),0) AS o, "
                          "COUNT(*) AS n, COALESCE(SUM(ok),0) AS ok FROM llm_usage")
        if not rows:
            return {"input": 0, "output": 0, "calls": 0, "ok": 0}
        r = rows[0]
        return {"input": r["i"], "output": r["o"], "calls": r["n"], "ok": r["ok"]}

    def message_ids(self) -> set[str]:
        return {m["id"] for m in self.messages()}
