"""The driver: posts the acts through the emulator and scripts every interaction.

Everything here goes through `EmuClient`, so tests run it against a fake transport. State
(`map.json`, `state.json`) is saved after every message so `post` can resume without
posting anything twice.
"""

from __future__ import annotations

import datetime as dt
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import envfile, script as S
from .emu import EmuClient, EmuError
from .state import JsonStore, Recorder, now_iso

DISCORD_EPOCH_MS = 1420070400000
PLACEHOLDER = b"placeholder for a fictional simulation"
SHORT_ID = re.compile(r"\*\*([DTQ]-\d+)\*\*")
EPHEMERAL = 64
WATCH_PAUSE = 2.0
WATCH_SPEEDS = (1.0, 2.0, 4.0, 8.0)


def snowflake_ms(snowflake: str | int) -> int:
    return (int(snowflake) >> 22) + DISCORD_EPOCH_MS


def iso_to_ms(value: str) -> int:
    return int(dt.datetime.fromisoformat(value).timestamp() * 1000)


def flatten_message(message: dict | None) -> str:
    """Content plus embed text, newline separated (for evidence and substring checks)."""
    if not message:
        return ""
    parts = [message.get("content") or ""]
    for embed in message.get("embeds") or []:
        for key in ("title", "description"):
            if embed.get(key):
                parts.append(embed[key])
        for field_ in embed.get("fields") or []:
            parts.append(f"{field_.get('name', '')}: {field_.get('value', '')}")
        footer = (embed.get("footer") or {}).get("text")
        if footer:
            parts.append(footer)
    return "\n".join(p for p in parts if p)


@dataclass
class IdMap:
    """Seeded ids the driver needs. Built from the dataset and checked against the emulator."""

    guild: str
    channels: dict[str, str]  # sim channel name -> id
    users: dict[str, str]  # dataset member id -> emulator user id
    app: str = S.APP_TEAMCTX_ID

    @classmethod
    def from_dataset(cls, dataset: dict) -> "IdMap":
        cast = S.cast_from_dataset(dataset)
        channels = {c["name"]: str(S.BASE + int(c["id"])) for c in dataset["channels"] if c["kind"] == "text"}
        channels[S.LEADS_CHANNEL] = S.LEADS_CHANNEL_ID
        return cls(S.GUILD_ID, channels, {m: c.user_id for m, c in cast.items()})


@dataclass
class InteractionResult:
    key: str
    label: str
    actor: str
    text_form: str  # e.g. "/decide text:..." (chat text is the user's typing: fine to keep)
    ok: bool = False  # the application answered
    error: str | None = None
    first_type: int | None = None  # callback type of the first answer (4, 5, 9)
    ephemeral: bool | None = None
    deferred: bool = False
    edited: bool = False
    modal: bool = False  # the first answer was the form (callback type 9)
    modal_opened: bool = False  # this result is the submission of a form
    opened_ms: float | None = None  # time to open the form
    note: str | None = None  # something the reader should know (a degraded step)
    degraded: bool = False
    answer_ms: float | None = None  # interaction -> first answer, from snowflake times
    edit_ms: float | None = None  # first answer -> edit, for deferred
    wall_ms: float = 0.0
    text: str = ""
    refs: list[str] = field(default_factory=list)
    interaction_id: str | None = None
    request: dict | None = None
    meta: dict = field(default_factory=dict)  # e.g. the local and UTC dates when a due phrase was sent

    def to_json(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def resolve_value(value, *, aliases: dict, ids: IdMap, mapping: dict, today: dt.date):
    """Replaces the `$alias:`, `$link:`, `$user:` and `$due:` placeholders in an option value."""
    if not isinstance(value, str) or not value.startswith("$"):
        return value
    kind, _, arg = value[1:].partition(":")
    if kind == "alias":
        if arg not in aliases:
            raise KeyError(f"no captured entry for fixture entry {arg}")
        return aliases[arg]
    if kind == "link":
        item = mapping.get(arg)
        if not item or not item.get("emu_id"):
            raise KeyError(f"message {arg} not posted")
        return f"https://discord.com/channels/{ids.guild}/{item['channel_id']}/{item['emu_id']}"
    if kind == "user":
        return ids.users[arg]
    if kind == "due":
        return S.due_from_offset(value, today)
    if kind == "weekday":
        return S.weekday_phrase(value, today)
    raise ValueError(f"unknown placeholder {value!r}")


def raw_options(options: dict, sub: str | None, user_names=("owner", "author"), channel_names=("channel",)) -> list[dict]:
    """The Discord option array for `options` (used when the map form is refused)."""

    def one(name: str, value) -> dict:
        if isinstance(value, bool):
            return {"name": name, "type": 5, "value": value}
        if name in user_names:
            return {"name": name, "type": 6, "value": value}
        if name in channel_names:
            return {"name": name, "type": 7, "value": value}
        return {"name": name, "type": 3, "value": value}

    flat = [one(k, v) for k, v in options.items()]
    return [{"name": sub, "type": 1, "options": flat}] if sub else flat


def describe_command(capture_or_cmd: str, sub: str | None, options: dict) -> str:
    parts = [f"/{capture_or_cmd}" + (f" {sub}" if sub else "")]
    for k, v in options.items():
        text = str(v)
        parts.append(f"{k}:{text if len(text) <= 60 else text[:57] + '...'}")
    return " ".join(parts)


class Driver:
    def __init__(
        self,
        emu: EmuClient,
        mapping: JsonStore,
        state: JsonStore,
        items: list[S.PostItem],
        ids: IdMap,
        dataset: dict,
        rec: Recorder,
        *,
        crash_token=None,
        teamctx_token=None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        rng: random.Random | None = None,
        pace: float = 1.0,
        today: dt.date | None = None,
        watch: bool = False,
        speed_file: Path | None = None,
    ) -> None:
        self.speed_file = speed_file
        self.emu = emu
        self.map = mapping
        self.state = state
        self.items = items
        self.by_key = {i.key: i for i in items}
        self.ids = ids
        self.dataset = dataset
        self.cast = S.cast_from_dataset(dataset)
        self.rec = rec
        self.crash_token = crash_token
        self.teamctx_token = teamctx_token
        self.clock = clock
        self.sleep = sleep
        self.rng = rng or random.Random(20261110)
        self.pace = pace
        self.watch = watch  # watchable pace for the live view: 2-4 s between messages, 2 s around commands and asks
        self.today = today or S.local_today()  # the server timezone's date (UTC in plain mode)
        self.map.setdefault("items", {})
        self.state.setdefault("aliases", {})
        self.state.setdefault("captures", {})
        self.state.setdefault("disconnects", [])
        self.state.setdefault("posted_acts", [])

    # -- posting ---------------------------------------------------------------------

    @property
    def posted(self) -> dict:
        return self.map["items"]

    def act_items(self, act: int) -> list[S.PostItem]:
        return [i for i in self.items if i.act == act]

    def plan_calls(self, act: int) -> list[str]:
        """What `post` would do, without touching the network or the state (for --dry-run)."""
        lines = []
        for item in self.act_items(act):
            who = "crashwatch (bot token, REST)" if item.via_bot_token else f"user {self.cast[item.author].username}"
            line = f"POST #{item.channel} as {who}: {item.key} ({len(item.content)} chars)"
            if item.reply_to:
                line += f" reply_to={item.reply_to}"
            if item.attachments:
                line += f" attachments={list(item.attachments)}"
            if item.embeds:
                line += f" embeds={len(item.embeds)} (image-only stand-in)"
            lines.append(line)
            if item.edit_later:
                lines.append(f"  then message-update {item.key} to the dataset text 2-5 s later")
            if item.delete_later:
                lines.append(f"  then message-delete {item.key} 2-5 s later")
            if item.reactions:
                lines.append(f"  then {len(item.reactions)} reaction(s) 1-6 s later")
        return lines

    def _delay(self, upcoming: S.PostItem | None = None) -> float:
        quick = upcoming is not None and upcoming.quick  # fragments and bursts follow the previous message fast
        if self.watch:
            base = self.rng.uniform(0.6, 1.2) if quick else self.rng.uniform(2.0, 4.0)
            return base / self.watch_speed()
        if self.pace <= 0:
            return 0.0
        return self.rng.uniform(0.05, 0.35) * self.pace if quick else self.rng.uniform(0.3, 1.2) * self.pace

    def _watch_pause(self) -> None:
        """Two quiet seconds before and after a command or an ask, so a person can follow it (watch mode only)."""
        if self.watch:
            self.sleep(WATCH_PAUSE / self.watch_speed())

    def watch_speed(self) -> float:
        """The live view's speed choice (1, 2, 4 or 8), read fresh each time so it applies mid-run."""
        if self.speed_file is None:
            return 1.0
        try:
            value = float(self.speed_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return 1.0
        return value if value in WATCH_SPEEDS else 1.0

    def post_act(self, act: int, *, disconnects: list[tuple[float, str]] | None = None) -> dict:
        items = self.act_items(act)
        pending: list[tuple[float, str, S.PostItem]] = []
        done = skipped = 0
        points = {int(frac * len(items)): mode for frac, mode in (disconnects or [])}
        burst = 0  # messages to post back to back right after a disconnect
        around: list[dict] = []
        for index, item in enumerate(items):
            self._run_due(pending)
            if index in points and not self._disconnect_done(act, points[index]):
                around.append(self._disconnect(act, points[index]))
                burst = 3
            entry = self.posted.get(item.key)
            if entry and entry.get("state") == "posted":
                skipped += 1
                self._schedule_followups(pending, item, entry, immediate=True)
                continue
            msg = self._post_item(item)
            done += 1
            for rec in around:
                if len(rec["keys"]) < 3 and burst > 0:
                    rec["keys"].append(item.key)
            self.state.save()
            self._schedule_followups(pending, item, self.posted[item.key])
            if burst > 0:
                burst -= 1
            else:
                pause = self._delay(items[index + 1] if index + 1 < len(items) else None)
                if pause > 0:
                    self.sleep(pause)
            _ = msg
        self._flush(pending)
        if act not in self.state["posted_acts"]:
            self.state["posted_acts"].append(act)
        self.state.save()
        self.rec.event("post", f"act {act}: {done} posted, {skipped} already posted", act=act)
        return {"act": act, "posted": done, "skipped": skipped}

    def _disconnect_done(self, act: int, mode: str) -> bool:
        return any(d["act"] == act and d["mode"] == mode for d in self.state["disconnects"])

    def _disconnect(self, act: int, mode: str) -> dict:
        started = self.clock()
        self.emu.disconnect(mode, self.ids.app)
        record = {"act": act, "mode": mode, "at": now_iso(started), "epoch": started, "keys": []}
        self.state["disconnects"].append(record)
        self.state.save()
        self.rec.event("disconnect", f"gateway-disconnect mode={mode} (act {act})", mode=mode, act=act)
        return record

    def _post_item(self, item: S.PostItem) -> dict:
        existing = self.posted.get(item.key) or {}
        channel_id = self.ids.channels[item.channel]
        author = self.cast[item.author]
        reply = None
        if item.reply_to:
            ref = self.posted.get(item.reply_to)
            reply = ref["emu_id"] if ref and ref.get("emu_id") else None
        intent = {"state": "posting", "channel": item.channel, "channel_id": channel_id, "act": item.act,
                  "poster": author.user_id, "poster_member": item.author, "intent_at": self.clock()}
        if existing.get("state") == "posting":
            found = self._reconcile(item, existing)
            if found:
                return found
        self.posted[item.key] = intent
        self.map.save()
        if item.via_bot_token:
            msg = self.emu.bot_post_message(self.crash_token, channel_id, item.content, reply_to=reply)
        else:
            files = None
            if item.attachments and self.state.get("attachments_supported", True):
                files = [(name, PLACEHOLDER) for name in item.attachments]
            msg = self.emu.post_message(author.user_id, channel_id, item.content, reply_to=reply, attachments=files,
                                        embeds=list(item.embeds) or None)
            if files:
                supported = bool(msg.get("attachments"))
                self.state["attachments_supported"] = supported
                intent["attachments_returned"] = [a.get("filename") for a in msg.get("attachments", [])]
        intent.update({"state": "posted", "emu_id": msg["id"], "posted_at": msg.get("timestamp"),
                       "reply_to_emu": reply, "content_posted": item.content})
        self.map.save()
        self.rec.event("message", f"posted {item.key} in #{item.channel}", key=item.key, emu_id=msg["id"], act=item.act)
        return msg

    def _reconcile(self, item: S.PostItem, existing: dict) -> dict | None:
        """A previous run crashed between POST and save: adopt the message if it exists."""
        token = self.teamctx_token
        if token is None:
            return None
        for msg in self.emu.channel_messages(token, existing["channel_id"], limit=50):
            if msg.get("content") == item.content and msg.get("author", {}).get("id") == (
                S.BOT_CRASH_ID if item.via_bot_token else existing["poster"]
            ) and iso_to_ms(msg["timestamp"]) / 1000 >= existing["intent_at"] - 5:
                existing.update({"state": "posted", "emu_id": msg["id"], "posted_at": msg.get("timestamp")})
                self.map.save()
                return msg
        return None

    def _schedule_followups(self, pending, item: S.PostItem, entry: dict, immediate: bool = False) -> None:
        now = self.clock()
        if item.edit_later and not entry.get("edited"):
            pending.append((now if immediate else now + self.rng.uniform(2, 5) * max(self.pace, 0.0), "edit", item))
        if item.delete_later and not entry.get("deleted"):
            pending.append((now if immediate else now + self.rng.uniform(2, 5) * max(self.pace, 0.0), "delete", item))
        if item.reactions and not entry.get("reacted"):
            pending.append((now if immediate else now + self.rng.uniform(1, 6) * max(self.pace, 0.0), "react", item))

    def _run_due(self, pending: list) -> None:
        now = self.clock()
        for task in [p for p in pending if p[0] <= now]:
            pending.remove(task)
            self._followup(task[1], task[2])

    def _flush(self, pending: list) -> None:
        for due, kind, item in sorted(pending, key=lambda p: p[0]):
            wait = due - self.clock()
            if wait > 0:
                self.sleep(wait)
            self._followup(kind, item)
        pending.clear()

    def _followup(self, kind: str, item: S.PostItem) -> None:
        entry = self.posted[item.key]
        if kind == "edit":
            self.emu.update_message(entry["poster"], entry["emu_id"], item.final_content)
            entry["edited"] = True
            entry["edited_at"] = now_iso(self.clock())
            self.rec.event("edit", f"edited {item.key}", key=item.key, emu_id=entry["emu_id"])
        elif kind == "react":
            for member, emoji in item.reactions:
                self.emu.react(self.ids.users[member], entry["emu_id"], emoji)
            entry["reacted"] = len(item.reactions)
            self.rec.event("react", f"{len(item.reactions)} reaction(s) on {item.key}", key=item.key)
        else:
            self.emu.delete_message(entry["poster"], entry["emu_id"])
            entry["deleted"] = True
            entry["deleted_at"] = now_iso(self.clock())
            self.rec.event("delete", f"deleted {item.key}", key=item.key, emu_id=entry["emu_id"])
        self.map.save()

    def posted_keys(self) -> set[str]:
        return {k for k, v in self.posted.items() if v.get("state") == "posted"}

    # -- interactions ----------------------------------------------------------------

    def _tick(self, key: str, label: str, actor: str, text_form: str) -> InteractionResult:
        return InteractionResult(key=key, label=label, actor=actor, text_form=text_form)

    def _send(self, body: dict, result: InteractionResult, *, wait: float) -> dict | None:
        started = self.clock()
        try:
            raw = self.emu.interaction(body)
        except EmuError as exc:
            result.error = str(exc)
            result.wall_ms = (self.clock() - started) * 1000
            return None
        result.wall_ms = (self.clock() - started) * 1000
        interaction = raw.get("interaction") or {}
        result.interaction_id = interaction.get("id")
        response = raw.get("response")
        message = raw.get("message")
        if not response:
            result.error = f"no answer from the application (delivery={raw.get('delivery')})"
            return raw
        result.ok = True
        result.first_type = response.get("type")
        data = response.get("data") or {}
        result.ephemeral = bool((data.get("flags") or 0) & EPHEMERAL)
        if message and message.get("id") and result.interaction_id:
            result.answer_ms = float(snowflake_ms(message["id"]) - snowflake_ms(result.interaction_id))
        if result.first_type == 9:
            result.modal = True
        elif result.first_type == 5:
            result.deferred = True
            self._await_edit(raw, result, wait)
        else:
            result.text = flatten_message(message) or flatten_message(data)
        result.refs = SHORT_ID.findall(result.text)
        return raw

    def _await_edit(self, raw: dict, result: InteractionResult, wait: float) -> None:
        token = (raw.get("interaction") or {}).get("token")
        first = raw.get("message") or {}
        deadline = self.clock() + wait
        while self.clock() < deadline:
            resp = self.emu.original_response(self.ids.app, token)
            if resp.ok:
                msg = resp.json() or {}
                if msg.get("edited_timestamp"):
                    result.edited = True
                    result.text = flatten_message(msg)
                    if first.get("timestamp"):
                        result.edit_ms = float(iso_to_ms(msg["edited_timestamp"]) - iso_to_ms(first["timestamp"]))
                    return
            self.sleep(0.5)
        result.error = (result.error or "") + f"deferred reply was not edited within {wait:.0f} s"

    def slash(self, actor: str, channel: str, command: str, options: dict, sub: str | None = None, *,
              key: str = "", label: str = "", wait: float = 30.0) -> InteractionResult:
        user_id = self.ids.users[actor]
        channel_id = self.ids.channels[channel]
        body = {"user_id": user_id, "channel_id": channel_id, "command": command, "options": options}
        if sub:
            body["subcommand"] = sub
        result = self._tick(key, label or command, actor, describe_command(command, sub, options))
        result.request = {k: v for k, v in body.items() if k != "user_id"}
        raw = self._send(body, result, wait=wait)
        if raw is None and result.error and "ubcommand" in result.error:
            body["options"] = raw_options(options, sub)
            body.pop("subcommand", None)
            result.error = None
            self._send(body, result, wait=wait)
        return result

    def menu(self, actor: str, channel: str, command: str, target_emu_id: str, *, key: str = "", label: str = "",
             modal: dict | None = None, wait: float = 30.0) -> InteractionResult:
        user_id = self.ids.users[actor]
        channel_id = self.ids.channels[channel]
        body = {"user_id": user_id, "channel_id": channel_id, "command": command, "command_type": 3,
                "target_id": target_emu_id}
        result = self._tick(key, label or command, actor, f"[menu] {command}")
        result.request = {k: v for k, v in body.items() if k != "user_id"}
        raw = self._send(body, result, wait=wait)
        if raw is None or not result.modal or modal is None:
            return result
        values: dict = {}
        if modal.get("owner"):
            values["owner"] = [self.ids.users[modal["owner"]]]
        if modal.get("due"):
            values["due"] = modal["due"]
        submit = {"type": "modal_submit", "user_id": user_id, "channel_id": channel_id,
                  "interaction_id": result.interaction_id, "values": values}
        final = self._tick(key, label or command, actor, f"[modal] {command}")
        final.request = {k: v for k, v in submit.items() if k != "user_id"}
        self._send(submit, final, wait=wait)
        if modal.get("owner") and final.text.startswith("I could not read that command"):
            # teamctx could not read the form: the emulator sends no `resolved` users for a user select in a
            # modal submission, which teamctx needs to name the owner. Submit again without the owner.
            first_error = final.text
            values.pop("owner", None)
            retry = self._tick(key, label or command, actor, f"[modal] {command} (owner dropped)")
            retry.request = {**{k: v for k, v in submit.items() if k != "user_id"}, "values": dict(values)}
            self._send({**submit, "values": values}, retry, wait=wait)
            retry.degraded = True
            retry.note = ("owner dropped: teamctx answered the first submission with its fixed 'could not read' reply "
                          "(" + first_error[:60] + "); the emulator sends no resolved users for a user select in a modal submission")
            final = retry
        final.modal_opened = True  # the first answer was the form; this result is the submission
        final.opened_ms = result.answer_ms
        return final

    # -- captures --------------------------------------------------------------------

    def run_capture(self, cap: S.Capture, *, synced: Callable[[str], bool] | None = None) -> InteractionResult:
        done = self.state["captures"].get(cap.key)
        if done and done.get("ok"):
            return InteractionResult(**{k: done[k] for k in InteractionResult.__dataclass_fields__ if k in done})
        aliases = self.state["aliases"]
        if cap.target and synced is not None:
            self._wait_synced(cap.target, synced)
        self._watch_pause()
        channel = "general"
        try:
            if cap.kind == "menu":
                entry = self.posted[cap.target]
                channel = entry["channel"]
                modal = None
                if cap.modal:
                    modal = {"owner": cap.modal.get("owner"),
                             "due": resolve_value(cap.modal["due"], aliases=aliases, ids=self.ids,
                                                  mapping=self.posted, today=self.today) if cap.modal.get("due") else None}
                result = self.menu(cap.actor, channel, cap.command, entry["emu_id"], key=cap.key, label=cap.label,
                                   modal=modal)
            else:
                sent_at = dt.datetime.now(dt.UTC)
                today = S.local_today(sent_at) if cap.effect == "create_relative" else self.today
                options = {k: resolve_value(v, aliases=aliases, ids=self.ids, mapping=self.posted, today=today)
                           for k, v in cap.options.items()}
                result = self.slash(cap.actor, channel, cap.command, options, cap.sub, key=cap.key, label=cap.label)
                if cap.effect == "create_relative":
                    # What the server timezone's calendar said when the phrase was sent, for the checker.
                    result.meta = {"due_phrase": options.get("due"), "local_date": today.isoformat(),
                                   "utc_date": sent_at.date().isoformat(), "offset_min": S.offset_minutes()}
        except KeyError as exc:
            result = InteractionResult(key=cap.key, label=cap.label, actor=cap.actor, text_form=cap.command,
                                       error=f"blocked: {exc}")
        if result.ok and cap.entry is not None and cap.effect == "create" and result.refs:
            aliases[str(cap.entry)] = result.refs[0]
        self.state["captures"][cap.key] = result.to_json()
        self.state.save()
        self.rec.event("capture", f"{cap.key} {cap.label} by {self.cast[cap.actor].display_name}: "
                       + ("ok" if result.ok and not result.error else f"problem: {result.error}"),
                       key=cap.key, refs=result.refs, answer_ms=result.answer_ms)
        self._watch_pause()
        return result

    def _wait_synced(self, orig_key: str, synced: Callable[[str], bool], timeout: float = 45.0) -> None:
        deadline = self.clock() + timeout
        while self.clock() < deadline:
            if synced(orig_key):
                return
            self.sleep(1.0)
        self.rec.info(f"warning: message {orig_key} was not seen in teamctx within {timeout:.0f} s")

    def run_captures(self, act: int, **kw) -> list[InteractionResult]:
        out = []
        for cap in S.build_captures(self.dataset):
            if cap.act == act:
                out.append(self.run_capture(cap, **kw))
        return out

    # -- per-act queries -------------------------------------------------------------

    def run_queries(self, act: int, *, llm: bool, ask_wait: float = 120.0) -> list[InteractionResult]:
        results: list[InteractionResult] = []
        store = self.state.setdefault("queries", {})

        def remember(name: str, result: InteractionResult) -> None:
            store[name] = result.to_json()
            self.state.save()
            self.rec.event("query", f"{name}: " + ("ok" if result.ok and not result.error else f"problem: {result.error}"),
                           key=name, answer_ms=result.answer_ms)
            results.append(result)

        def remember_ask(name: str, actor: str, options: dict, label: str, wait: float) -> None:
            self._watch_pause()
            remember(name, self.slash(actor, "general", "ask", options, key=name, label=label, wait=wait))
            self._watch_pause()

        for n, q in enumerate([s for s in S.build_searches() if s.act == act], start=1):
            name = f"act{act}-search{n}"
            if name not in store:
                remember(name, self.slash("102", "general", "search", {"query": q.text}, key=name, label=f"/search {q.text}"))
        for n, member in enumerate(S.catchup_users(act), start=1):
            name = f"act{act}-catchup{n}"
            if name not in store:
                remember(name, self.slash(member, "general", "catchup", {}, key=name,
                                          label=f"/catchup as {self.cast[member].display_name}"))
        if act == 4 and S.REALISM:
            # The member who was away for acts 2-3 comes back and catches up once.
            name = "act4-catchup-absent"
            if name not in store:
                member = S.ABSENT_MEMBER
                remember(name, self.slash(member, "general", "catchup", {}, key=name,
                                          label=f"/catchup as {self.cast[member].display_name} after being away"))
        name = f"act{act}-status"
        if name not in store:
            remember(name, self.slash("103", "general", "teamctx", {}, "status", key=name, label="/teamctx status"))
        if act == 2:
            # Visibility: Dov (no leads role) and Wren (leads) both search for the leads content.
            for member, tag in (("102", "dov"), ("101", "wren")):
                name = f"act{act}-leads-search-{tag}"
                if name not in store:
                    remember(name, self.slash(member, "general", "search", {"query": "budget illustrator"}, key=name,
                                              label=f"/search budget illustrator as {self.cast[member].display_name}"))
            name = f"act{act}-leads-search-public"
            if name not in store:
                remember(name, self.slash("101", "general", "search", {"query": "budget illustrator", "public": True},
                                          key=name, label="/search budget illustrator public:true as Wren"))
        if act == 4 and llm:
            name = "act4-catchup-summarize"
            if name not in store:
                remember(name, self.slash("105", "general", "catchup", {"summarize": True}, key=name,
                                          label="/catchup summarize:true", wait=ask_wait))
            for n, question in enumerate(S.ASK_DISCORD, start=1):
                name = f"act4-ask{n}"
                if name not in store:
                    remember_ask(name, "103", {"question": question}, f"/ask {question}", ask_wait)
            for n, member in enumerate(("102", "101"), start=1):
                name = f"act4-ask-leads{n}"
                if name not in store:
                    remember_ask(name, member, {"question": "What is the contractor illustrator budget?"},
                                 f"/ask contractor budget as {self.cast[member].display_name}", ask_wait)
        return results
