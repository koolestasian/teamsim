"""HTTP transport with a host policy, plus a scripted fake for offline tests."""

from __future__ import annotations

import ipaddress
import json as jsonlib
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Callable, Protocol


class PolicyError(Exception):
    """A request or URL broke the host policy (non-loopback emulator, stray host...)."""


def is_loopback_host(host: str) -> bool:
    host = host.strip("[]").lower()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def assert_loopback_url(url: str) -> str:
    """Returns the URL, or raises PolicyError unless its host is loopback."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https", "ws", "wss"):
        raise PolicyError(f"unsupported scheme in URL: {parsed.scheme!r}")
    if parsed.username or parsed.password:
        raise PolicyError("URL must not carry credentials")
    host = parsed.hostname or ""
    if not is_loopback_host(host):
        raise PolicyError(f"host {host!r} is not loopback")
    return url


@dataclass
class Response:
    status: int
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", "replace")

    def json(self):
        if not self.body:
            return None
        return jsonlib.loads(self.body.decode("utf-8"))

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    def header(self, name: str, default: str | None = None) -> str | None:
        lowered = name.lower()
        for k, v in self.headers.items():
            if k.lower() == lowered:
                return v
        return default


class Transport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: object | None = None,
        data: bytes | None = None,
        timeout: float = 15.0,
    ) -> Response: ...


def multipart(payload: dict, files: list[tuple[str, bytes]]) -> tuple[bytes, str]:
    """Builds a Discord-style multipart body (payload_json + files[n]). Returns (body, content type)."""
    boundary = uuid.uuid4().hex
    chunks = [
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="payload_json"\r\n'
            f"Content-Type: application/json\r\n\r\n{jsonlib.dumps(payload)}\r\n"
        ).encode()
    ]
    for index, (name, content) in enumerate(files):
        chunks.append(
            (
                f'--{boundary}\r\nContent-Disposition: form-data; name="files[{index}]"; '
                f'filename="{name}"\r\nContent-Type: application/octet-stream\r\n\r\n'
            ).encode()
            + content
            + b"\r\n"
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _ipv4_loopback(url: str) -> str:
    """`localhost` resolves to ::1 first on this machine, which costs about 2 s per new connection
    (WSL forwards IPv4 only). Connect to 127.0.0.1 instead; the Host header is not affected."""
    parts = urllib.parse.urlsplit(url)
    if (parts.hostname or "").lower() == "localhost":
        netloc = "127.0.0.1" + (f":{parts.port}" if parts.port else "")
        return urllib.parse.urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    return url


class UrllibTransport:
    """Real transport. `allowed` hosts are enforced on every request; proxies are off."""

    def __init__(self, *, allow_loopback: bool = True, extra_hosts: frozenset[str] = frozenset()) -> None:
        self.allow_loopback = allow_loopback
        self.extra_hosts = frozenset(h.lower() for h in extra_hosts)
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _check(self, url: str) -> None:
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
        if host in self.extra_hosts:
            return
        if self.allow_loopback and is_loopback_host(host):
            return
        raise PolicyError(f"host {host!r} is not allowed by this transport")

    def request(self, method, url, *, headers=None, json=None, data=None, timeout=15.0) -> Response:
        self._check(url)
        url = _ipv4_loopback(url)
        hdrs = dict(headers or {})
        body = data
        if json is not None:
            body = jsonlib.dumps(json).encode("utf-8")
            hdrs.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
        try:
            with self._opener.open(req, timeout=timeout) as resp:
                return Response(resp.status, dict(resp.headers.items()), resp.read())
        except urllib.error.HTTPError as exc:
            return Response(exc.code, dict(exc.headers.items()), exc.read())


Handler = Callable[[str, str, dict], "Response | tuple | None"]


class FakeTransport:
    """Scripted transport for tests. Routes: (method, regex on URL) -> response or callable."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self._routes: list[tuple[str, re.Pattern[str], object]] = []

    def route(self, method: str, pattern: str, response) -> "FakeTransport":
        """`response` is a Response, (status, json), a list of those (consumed in order), or a callable(call)->same."""
        self._routes.append((method.upper(), re.compile(pattern), response))
        return self

    def request(self, method, url, *, headers=None, json=None, data=None, timeout=15.0) -> Response:
        call = {
            "method": method.upper(),
            "url": url,
            "headers": dict(headers or {}),
            "json": json,
            "data": data,
        }
        self.calls.append(call)
        for m, pattern, response in self._routes:
            if m == call["method"] and pattern.search(url):
                if callable(response):
                    response = response(call)
                elif isinstance(response, list):
                    response = response.pop(0) if len(response) > 1 else response[0]
                return self._coerce(response)
        return Response(404, {}, b'{"message":"no fake route","code":0}')

    @staticmethod
    def _coerce(response) -> Response:
        if isinstance(response, Response):
            return response
        status, payload = response
        if isinstance(payload, (bytes, bytearray)):
            return Response(status, {}, bytes(payload))
        return Response(status, {"Content-Type": "application/json"}, jsonlib.dumps(payload).encode())
