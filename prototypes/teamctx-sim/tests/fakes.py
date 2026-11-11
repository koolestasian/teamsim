"""Test doubles: a stateful fake emulator transport and helpers. No network."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simlib.net import Response  # noqa: E402


def snowflake(seq: int) -> str:
    # 2026-ish timestamp bits plus a sequence, so snowflake_ms() works on the fakes.
    ms = 1794358300000 - 1420070400000 + seq
    return str((ms << 22) | (seq & 0xFFF))


class FakeEmulator:
    """Just enough of the emulator for the driver: simulate endpoints and message listing."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.messages: dict[str, dict] = {}  # id -> message
        self.seq = 0
        self.rate_limit_next = 0
        self.attachments_supported = False
        self.interaction_log: list[dict] = []
        self.responder = None  # callable(body) -> {"response":..., "message":...} or None
        self.original = {}  # token -> message dict for deferred replies
        self.disconnects: list[dict] = []
        self.fail_after_post: int | None = None  # raise after storing the n-th post (simulates a crash)

    # -- Transport
    def request(self, method, url, *, headers=None, json=None, data=None, timeout=15.0) -> Response:  # noqa: A002
        path = re.sub(r"^https?://[^/]+", "", url)
        json = copy.deepcopy(json)
        call = {"method": method, "path": path, "json": json, "data": data, "headers": dict(headers or {})}
        self.calls.append(call)
        if self.rate_limit_next > 0 and "/simulate/" in path:
            self.rate_limit_next -= 1
            return Response(429, {"Retry-After": "0.01"}, b'{"message":"You are being rate limited.","retry_after":0.01,"global":false,"code":0}')
        if method == "GET" and path == "/":
            return Response(200, {}, b"<html></html>")
        if path == "/_discord/simulate/message" and method == "POST":
            return self._simulate_message(json, data)
        if path == "/_discord/simulate/message-update":
            return self._update(json)
        if path == "/_discord/simulate/message-delete":
            return self._delete(json)
        if path == "/_discord/simulate/reaction":
            msg = self.messages.get(json["message_id"])
            if not msg:
                return Response(404, {}, b'{"message":"Unknown Message","code":10008}')
            msg.setdefault("reactions", []).append({"emoji": {"name": json["emoji"]}, "count": 1, "user": json["user_id"]})
            return Response(204, {}, b"")
        if path == "/_discord/simulate/gateway-disconnect":
            self.disconnects.append(json)
            return Response(200, {}, b"{}")
        if path == "/_discord/simulate/interaction":
            return self._interaction(json)
        m = re.match(r"/api/v10/channels/(\d+)/messages(\?.*)?$", path)
        if m and method == "POST":
            return self._bot_post(m.group(1), json, headers or {})
        if m and method == "GET":
            return self._list(m.group(1), m.group(2) or "")
        m = re.match(r"/api/v10/webhooks/(\d+)/([^/]+)/messages/@original", path)
        if m and method == "GET":
            msg = self.original.get(m.group(2))
            return Response(200, {}, json_bytes(msg)) if msg else Response(404, {}, b'{"message":"Unknown Webhook","code":10015}')
        return Response(404, {}, b'{"message":"404: Not Found","code":0}')

    # -- internals
    def _new(self, channel_id: str, author_id: str, content: str, reference=None, bot=False, attachments=None) -> dict:
        self.seq += 1
        mid = snowflake(self.seq)
        msg = {"id": mid, "channel_id": channel_id, "content": content, "timestamp": f"2026-11-11T00:{self.seq // 60 % 60:02d}:{self.seq % 60:02d}.000000+00:00",
               "edited_timestamp": None, "author": {"id": author_id, "username": "u", "bot": bot}, "attachments": attachments or [],
               "embeds": []}
        if reference:
            msg["message_reference"] = {"message_id": reference, "channel_id": channel_id}
        self.messages[mid] = msg
        return msg

    def _simulate_message(self, body, data) -> Response:
        attachments = []
        if data is not None:  # multipart
            text = data.decode("utf-8", "replace")
            m = re.search(r'name="payload_json"[^\r]*\r\nContent-Type: application/json\r\n\r\n(.*?)\r\n--', text, re.S)
            body = json.loads(m.group(1))
            if self.attachments_supported:
                attachments = [{"filename": a["filename"]} for a in body.get("attachments", [])]
        ref = (body.get("message_reference") or {}).get("message_id")
        msg = self._new(body["channel_id"], body["user_id"], body["content"], ref, attachments=attachments)
        msg["embeds"] = list(body.get("embeds") or [])
        if self.fail_after_post is not None:
            self.fail_after_post -= 1
            if self.fail_after_post <= 0:
                self.fail_after_post = None
                raise OSError("connection dropped after the emulator stored the message")
        return Response(200, {}, json_bytes(msg))

    def _bot_post(self, channel_id, body, headers) -> Response:
        if not headers.get("Authorization", "").startswith("Bot "):
            return Response(401, {}, b'{"message":"401: Unauthorized","code":0}')
        msg = self._new(channel_id, "BOT", body["content"], (body.get("message_reference") or {}).get("message_id"), bot=True)
        return Response(200, {}, json_bytes(msg))

    def _update(self, body) -> Response:
        msg = self.messages.get(body["message_id"])
        if not msg or msg["author"]["id"] != body["user_id"]:
            return Response(404, {}, b'{"message":"Unknown Message","code":10008}')
        msg["content"] = body["content"]
        msg["edited_timestamp"] = "2026-11-11T01:00:00.000000+00:00"
        return Response(200, {}, json_bytes(msg))

    def _delete(self, body) -> Response:
        if body["message_id"] not in self.messages:
            return Response(404, {}, b'{"message":"Unknown Message","code":10008}')
        del self.messages[body["message_id"]]
        return Response(204, {}, b"")

    def _list(self, channel_id, query) -> Response:
        limit = int((re.search(r"limit=(\d+)", query) or [0, 50])[1] if re.search(r"limit=(\d+)", query) else 50)
        before = re.search(r"before=(\d+)", query)
        msgs = [m for m in self.messages.values() if m["channel_id"] == channel_id]
        if before:
            msgs = [m for m in msgs if int(m["id"]) < int(before.group(1))]
        msgs.sort(key=lambda m: -int(m["id"]))
        return Response(200, {}, json_bytes(msgs[:limit]))

    def _interaction(self, body) -> Response:
        self.interaction_log.append(body)
        if self.responder is None:
            return Response(200, {}, json_bytes({"interaction": {"id": snowflake(9000 + len(self.interaction_log)), "token": "tok"},
                                                 "delivery": "gateway", "status": None, "response": None, "message": None}))
        out = self.responder(body)
        if isinstance(out, Response):
            return out
        return Response(200, {}, json_bytes(out))


def json_bytes(obj) -> bytes:
    return json.dumps(obj).encode("utf-8")
