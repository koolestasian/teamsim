"""The Discord emulator: simulate/REST client and the WSL process manager.

The emulator (`@deploybaseline/discord`) only ever runs inside the isolated WSL distro
`sbx-ubuntu` (never on Windows). This module talks to it over loopback HTTP and starts or
stops it through `wsl.exe`, touching nothing in the distro except `~/emu` and the
emulator process. The control token the emulator prints is a local secret: it is parsed
only to be registered with the redactor, never stored or shown.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import envfile
from .net import PolicyError, Response, Transport, assert_loopback_url, multipart

DEFAULT_BASE = "http://127.0.0.1:4000"  # the spec says localhost; see net._ipv4_loopback
DISTRO = "sbx-ubuntu"
WSL_USER = "dev"
REMOTE_SEED = "~/emu/seed.json"
REMOTE_LOG = "~/emu/emu.log"
START_SCRIPT = f"cd ~/emu && exec npx baseline start --service discord --seed {REMOTE_SEED} > {REMOTE_LOG} 2>&1"
STOP_SCRIPT = "pkill -f '[b]aseline start --service discord'; pkill -f '[@]deploybaseline/discord/dist/provider.js'; sleep 1; true"
RETRY_LIMIT = 8


class EmuError(Exception):
    def __init__(self, status: int, what: str, body: str = "") -> None:
        super().__init__(f"{what}: HTTP {status} {envfile.redact(body)[:300]}")
        self.status = status
        self.what = what
        self.body = envfile.redact(body)


@dataclass
class StartupInfo:
    ready: bool
    failed: bool
    control_token: str | None


def parse_startup_log(text: str) -> StartupInfo:
    """Reads the emulator's startup banner. Registers the control token for redaction."""
    token = None
    m = re.search(r"Token:\s+(\S+)\s+\(header X-Baseline-Control-Token\)", text)
    if m:
        token = m.group(1)
        envfile.REDACTOR.add(token)
    ready = bool(re.search(r"^\s*Ready\.\s*$", text, re.M))
    failed = bool(re.search(r"(?i)\b(error|invalid seed|ELIFECYCLE|EADDRINUSE)\b", text)) and not ready
    return StartupInfo(ready=ready, failed=failed, control_token=token)


class EmuClient:
    """Simulate endpoints and the few REST calls the harness needs. Loopback only."""

    def __init__(
        self,
        transport: Transport,
        base: str = DEFAULT_BASE,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base = assert_loopback_url(base).rstrip("/")
        self.transport = transport
        self.sleep = sleep

    # -- plumbing

    def _call(self, method: str, path: str, *, json_body=None, data=None, headers=None, what: str, timeout=15.0) -> Response:
        url = self.base + path
        hdrs = dict(headers or {})
        for attempt in range(RETRY_LIMIT):
            resp = self.transport.request(method, url, headers=hdrs, json=json_body, data=data, timeout=timeout)
            if resp.status != 429:
                return resp
            self.sleep(_retry_after(resp) + 0.05)
        raise EmuError(429, what, "rate limited after retries")

    def _ok(self, resp: Response, what: str):
        if not resp.ok:
            raise EmuError(resp.status, what, resp.text)
        return resp.json()

    @staticmethod
    def _bot(token: "envfile.Secret | str") -> dict[str, str]:
        value = token.reveal() if isinstance(token, envfile.Secret) else token
        return {"Authorization": f"Bot {value}"}

    # -- health

    def alive(self) -> bool:
        try:
            return self.transport.request("GET", self.base + "/", timeout=3.0).status == 200
        except (OSError, PolicyError):
            return False

    def sessions(self) -> list[dict]:
        data = self._ok(self._call("GET", "/_discord/gateway/sessions", what="gateway sessions"), "gateway sessions")
        return data.get("sessions", []) if isinstance(data, dict) else []

    # -- users acting in channels

    def post_message(self, user_id: str, channel_id: str, content: str, *, reply_to: str | None = None,
                     attachments: list[tuple[str, bytes]] | None = None, embeds: list[dict] | None = None) -> dict:
        body: dict = {"user_id": user_id, "channel_id": channel_id, "content": content}
        if reply_to:
            body["message_reference"] = {"message_id": reply_to, "channel_id": channel_id}
        if embeds:
            body["embeds"] = list(embeds)
        if attachments:
            body["attachments"] = [{"id": i, "filename": name} for i, (name, _) in enumerate(attachments)]
            payload, ctype = multipart(body, attachments)
            resp = self._call("POST", "/_discord/simulate/message", data=payload,
                              headers={"Content-Type": ctype}, what="simulate message (multipart)")
        else:
            resp = self._call("POST", "/_discord/simulate/message", json_body=body, what="simulate message")
        return self._ok(resp, "simulate message")

    def update_message(self, user_id: str, message_id: str, content: str) -> dict:
        body = {"user_id": user_id, "message_id": message_id, "content": content}
        return self._ok(self._call("POST", "/_discord/simulate/message-update", json_body=body,
                                   what="simulate message-update"), "simulate message-update")

    def react(self, user_id: str, message_id: str, emoji: str) -> None:
        body = {"user_id": user_id, "message_id": message_id, "emoji": emoji}
        resp = self._call("POST", "/_discord/simulate/reaction", json_body=body, what="simulate reaction")
        if not resp.ok:
            raise EmuError(resp.status, "simulate reaction", resp.text)

    def delete_message(self, user_id: str, message_id: str) -> None:
        body = {"user_id": user_id, "message_id": message_id}
        resp = self._call("POST", "/_discord/simulate/message-delete", json_body=body, what="simulate message-delete")
        if not resp.ok:
            raise EmuError(resp.status, "simulate message-delete", resp.text)

    def disconnect(self, mode: str, application_id: str | None = None) -> dict:
        if mode not in ("close", "reconnect", "invalidate"):
            raise ValueError(f"bad disconnect mode {mode!r}")
        body: dict = {"mode": mode}
        if application_id:
            body["application_id"] = application_id
        resp = self._call("POST", "/_discord/simulate/gateway-disconnect", json_body=body, what="gateway-disconnect")
        if not resp.ok:
            raise EmuError(resp.status, "gateway-disconnect", resp.text)
        return resp.json() or {}

    def interaction(self, body: dict) -> dict:
        """POST /_discord/simulate/interaction. Waits up to 3 s for the application's answer."""
        resp = self._call("POST", "/_discord/simulate/interaction", json_body=body, what="simulate interaction", timeout=20.0)
        if not resp.ok:
            raise EmuError(resp.status, "simulate interaction", resp.text)
        return resp.json() or {}

    # -- REST (bot token)

    def bot_post_message(self, token, channel_id: str, content: str, *, reply_to: str | None = None) -> dict:
        body: dict = {"content": content}
        if reply_to:
            body["message_reference"] = {"message_id": reply_to}
        resp = self._call("POST", f"/api/v10/channels/{channel_id}/messages", json_body=body,
                          headers=self._bot(token), what="bot post message")
        return self._ok(resp, "bot post message")

    def rest_get(self, token, path: str, what: str = "REST GET"):
        resp = self._call("GET", "/api/v10" + path, headers=self._bot(token), what=what)
        return self._ok(resp, what)

    def channel_messages(self, token, channel_id: str, *, limit: int = 100, before: str | None = None) -> list[dict]:
        path = f"/channels/{channel_id}/messages?limit={limit}" + (f"&before={before}" if before else "")
        data = self.rest_get(token, path, "list channel messages")
        return data if isinstance(data, list) else []

    def all_channel_messages(self, token, channel_id: str) -> list[dict]:
        out: list[dict] = []
        before = None
        while True:
            page = self.channel_messages(token, channel_id, before=before)
            out.extend(page)
            if len(page) < 100:
                return out
            before = min((m["id"] for m in page), key=int)

    def original_response(self, application_id: str, interaction_token: str) -> Response:
        return self._call("GET", f"/api/v10/webhooks/{application_id}/{interaction_token}/messages/@original",
                          what="original response")

    def guild_commands(self, token, application_id: str, guild_id: str):
        return self.rest_get(token, f"/applications/{application_id}/guilds/{guild_id}/commands", "guild commands")


def _retry_after(resp: Response) -> float:
    try:
        body = resp.json()
        if isinstance(body, dict) and "retry_after" in body:
            return min(float(body["retry_after"]), 30.0)
    except (ValueError, TypeError):
        pass
    header = resp.header("Retry-After")
    try:
        return min(float(header), 30.0) if header else 1.0
    except ValueError:
        return 1.0


# ---- WSL process manager -----------------------------------------------------------------


class Wsl:
    """Starts, stops and feeds the emulator through wsl.exe. `runner` is injectable for tests."""

    def __init__(self, state_dir: Path, *, runner=subprocess, distro: str = DISTRO, user: str = WSL_USER) -> None:
        self.state_dir = state_dir
        self.runner = runner
        self.distro = distro
        self.user = user

    def args(self, script: str) -> list[str]:
        return ["wsl.exe", "-d", self.distro, "-u", self.user, "--", "bash", "-lc", script]

    def copy_seed(self, seed: dict) -> None:
        """Writes ~/emu/seed.json through stdin (the distro has no Windows drives)."""
        payload = json.dumps(seed, indent=2).encode("utf-8")
        proc = self.runner.run(self.args(f"cat > {REMOTE_SEED}"), input=payload, capture_output=True, timeout=60)
        if proc.returncode != 0:
            raise RuntimeError("could not copy the seed into WSL: " + envfile.redact(_decode(proc.stderr)))

    def start(self) -> "subprocess.Popen":
        """Starts the emulator detached from this process. Its output goes to ~/emu/emu.log
        inside the distro (a pipe through wsl.exe loses the banner); `read_log` fetches it."""
        flags = 0
        if hasattr(subprocess, "DETACHED_PROCESS"):
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        return self.runner.Popen(self.args(START_SCRIPT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 stdin=subprocess.DEVNULL, creationflags=flags)

    def read_log(self) -> str:
        proc = self.runner.run(self.args(f"cat {REMOTE_LOG} 2>/dev/null; true"), capture_output=True, timeout=30)
        return _decode(proc.stdout)

    def stop(self) -> None:
        self.runner.run(self.args(STOP_SCRIPT), capture_output=True, timeout=60)


def _decode(data: bytes | None) -> str:
    return (data or b"").replace(b"\x00", b"").decode("utf-8", "replace")


def wait_ready(client: EmuClient, read_log: Callable[[], str], *, timeout: float = 60.0, clock=time.monotonic,
               sleep=time.sleep, token: str | None = None) -> StartupInfo:
    """Polls the banner and the HTTP port until the emulator answers or the timeout passes."""
    deadline = clock() + timeout
    info = StartupInfo(False, False, None)
    while clock() < deadline:
        info = parse_startup_log(read_log())
        if info.failed:
            return info
        if info.ready and client.alive():
            if token is None:
                return info
            try:
                resp = client.transport.request("GET", client.base + "/api/v10/gateway/bot",
                                                headers={"Authorization": f"Bot {token}"}, timeout=5.0)
                if resp.status == 200:
                    return info
            except OSError:
                pass
        sleep(0.5)
    return info
