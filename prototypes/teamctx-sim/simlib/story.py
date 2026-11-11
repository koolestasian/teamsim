"""Story events for the live view: pure functions from the harness files to a short story.

Inputs are the parsed `.state/timeline.jsonl` events, `map.json` items, `state.json` and the
demo dataset. The output is a list of *story events* (the only thing the page ever sees):

    act, message, edit, delete, stored, host, command, reply, ask, answer, done

Rules this module keeps:

* Deterministic and prefix-stable. The story of the first N timeline events never changes
  when more events are appended, so `since=<n>` paging works while a run is in progress.
* Whitelisting. Only the fields named in the spec are copied. Ids that identify things in the
  emulator or in Discord (snowflakes, jump links, tokens) are never copied; messages get short
  story ids (`s1`, `s2`, ...).
* The last step is the harness redactor plus a snowflake scrub, applied to every string.
* All chat text is untrusted data. It is passed through as data and never interpreted here.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from . import envfile, script as S

ACT_TITLES = {1: "Kick-off", 2: "Pricing and scope", 3: "teamctx goes offline", 4: "Beta crunch"}
ACT_DATES = {1: "Mar 2 \u2013 Mar 15", 2: "Mar 16 \u2013 Mar 31", 3: "Apr 1 \u2013 Apr 14", 4: "Apr 15 \u2013 Apr 24"}
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
BOT_MEMBER = "107"
PRIVATE_CHANNEL = S.LEADS_CHANNEL
FINISH_MARK = "(end of run)"
LIVE_WINDOW_SECONDS = 30.0
RECONNECT_BURST = 3  # the harness posts this many messages right after each gateway disconnect

# Plain words for the checks, shown (only when one did not pass) in the closing summary.
CHECK_WORDS = {
    "0": "Posting matched the emulator",
    "1": "Starting up",
    "2": "Every message was stored",
    "3": "Offline gap and reconnects",
    "4": "Commands and the record",
    "5": "Search quality",
    "6": "The private channel stayed private",
    "7": "Injection messages were ignored",
    "8": "Answers to questions over the API",
    "9": "Export",
    "10": "Agent access",
    "11": "Realistic chat: fragments, reactions, images",
    "12": "Names versus handles",
    "13": "A secret pasted in chat",
    "14": "Catch-up after being away",
    "15": "Relative due dates (tomorrow, a weekday)",
}
PRODUCT_DECISION = "product decision, not a bug: "  # evidence prefix the checker uses for findings that need the maintainer

SNOWFLAKE = re.compile(r"(?<!\d)\d{17,20}(?!\d)")
JUMP_URL = re.compile(r"/channels/\d+/\d+/(\d+)")
STAMP = re.compile(r"<t:(\d+)(?::[a-zA-Z])?>")
MD_LINK = re.compile(r"\[([^\]]*)\]\((?:https?://[^)\s]*)\)")
BARE_URL = re.compile(r"https?://\S+")
ESCAPED = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|~<>:&\"'=@/$%^,;?])")
CITE_MARK = re.compile(r"[ \t]*\[(?:m:\d+|[DTQ]-\d+)\]")
RECORD_HEAD = re.compile(r"^(?:Recorded|Answered|Done)(?: as an? (?:decision|task|question))?:\s+\*\*([DTQ])\\?-(\d+)\*\*\s+\u00b7\s+(.*)$")
KINDS = {"D": "decision", "T": "task", "Q": "question"}


# ---- text cleaning -----------------------------------------------------------------------


def epoch_of(iso: str) -> float:
    """Timeline timestamps look like 2026-11-11T01:18:35.167Z."""
    try:
        return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return 0.0


def short_date(seconds: float) -> str:
    moment = dt.datetime.fromtimestamp(float(seconds), dt.UTC)
    return f"{MONTHS[moment.month - 1]} {moment.day}"


def clean_markup(text: str, keep_lines: bool = False) -> str:
    """Discord markup to plain words: dates, links, bold, escapes, whitespace.

    `<t:UNIX:d>` becomes "Apr 3"; `[jump](url)` links and bare URLs are dropped; `**`, `__` and
    backslash escapes go; whitespace collapses (line breaks survive when `keep_lines`).
    """
    text = STAMP.sub(lambda m: short_date(int(m.group(1))), text or "")
    text = re.sub(r"[ \t]*\u00b7?[ \t]*\[jump\]\([^)]*\)", "", text)
    text = MD_LINK.sub(lambda m: m.group(1), text)
    text = BARE_URL.sub("", text)
    text = text.replace("**", "").replace("__", "")
    text = ESCAPED.sub(r"\1", text)
    if keep_lines:
        lines = [re.sub(r"[ \t]+", " ", line).strip(" \u00b7") for line in text.splitlines()]
        return "\n".join(line for line in lines if line)
    return re.sub(r"\s+", " ", text).strip(" \u00b7")


def shorten(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    if " " in cut[limit // 2:]:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,;:.-") + "\u2026"


def strip_stamp(line: str) -> str:
    """'Title \u2014 Wren Calloway, Nov 11' -> 'Title \u2014 Wren Calloway' (the date is the run date, not project time)."""
    return re.sub(r"(\s\u2014\s[^,\u2014\n]+),\s[A-Z][a-z]{2}\s\d{1,2}(?=$|[\s;(])", r"\1", line)


def emu_ids_in(text: str) -> list[str]:
    return JUMP_URL.findall(text or "")


# ---- parsing teamctx replies -------------------------------------------------------------


def parse_record(text: str, actor: str) -> dict | None:
    """The record a command reply created or changed, or None for a listing / refusal."""
    first = (text or "").split("\n", 1)[0]
    head = RECORD_HEAD.match(first)
    if not head:
        return None
    kind = KINDS[head.group(1)]
    ref = f"{head.group(1)}-{head.group(2)}"
    rest = head.group(3)
    status = {"decision": "active", "task": "open", "question": "open"}[kind]
    replaces = None
    m = re.search(r";\s*it replaces ([DTQ]-\d+)\s*$", rest)
    if m:
        replaces, rest = m.group(1), rest[: m.start()]
    m = re.search(r"\s+\((answered|done)\)(?:;.*)?$", rest)
    if m:
        status, rest = m.group(1), rest[: m.start()]
    elif first.startswith("Answered"):
        status = "answered"
    elif first.startswith("Done"):
        status = "done"
    rest = re.sub(r"\s+\u00b7\s+\[jump\].*$", "", rest)
    rest = re.sub(r"\.\s*Due date:.*$", "", rest)
    who, owner, due, title = actor, None, None, rest
    m = re.match(r"^(.*)\s+\u2014\s+(?:owner\s+(.+?),\s+due\s+<t:(\d+)(?::\w)?>|(.+?),\s+<t:(\d+)(?::\w)?>)\s*$", rest)
    if m:
        title = m.group(1)
        if m.group(2):
            owner, due = m.group(2), short_date(int(m.group(3)))
        else:
            who = m.group(4)
    else:
        m = re.match(r"^(.*?),\s+due\s+<t:(\d+)(?::\w)?>\s*$", rest)
        if m:
            title, due = m.group(1), short_date(int(m.group(2)))
    return {"ref": ref, "kind": kind, "title": shorten(clean_markup(title), 120), "status": status,
            "replaces": replaces, "who": clean_markup(who) if who else who,
            "owner": clean_markup(owner) if owner else owner, "due": due}


def reply_text(text: str, record: dict | None) -> str:
    """Plain words for the reply bubble."""
    if record is not None:
        first = text.split("\n", 1)[0]
        first = re.sub(r"\s+\u00b7\s+\[jump\].*$", "", first)
        first = re.sub(r"\.\s*Due date:.*$", "", first)
        first = re.sub(r"\s+\((?:answered|done)\)(?:;\s*answer.*)?$", "", first)
        first = re.sub(r";\s*it replaces ([DTQ]-\d+)\s*$", r" (replaces \1)", first)
        return strip_stamp(clean_markup(first))
    lines = clean_markup(text, keep_lines=True).split("\n")
    return "\n".join(strip_stamp(line) for line in lines)


def answer_body(text: str) -> str:
    """The prose of a /ask answer: no disclaimer line, no source list, no [m:12] marks."""
    body = text or ""
    body = re.sub(r"^Answer generated by a language model[^\n]*\n", "", body)
    body = re.split(r"\n\s*\n?\s*\\?\*{0,2}Sources\\?\*{0,2}:?", body, maxsplit=1)[0]
    body = clean_markup(body, keep_lines=True)
    body = CITE_MARK.sub("", body)
    body = re.sub(r"[ \t]+([.,;:!?])", r"\1", body)
    return "\n".join(line.rstrip() for line in body.split("\n")).strip()


def command_label(capture: dict) -> tuple[str, bool]:
    """('/decide', False) or ('Mark as decision', True) for a context menu."""
    request = capture.get("request") or {}
    if request.get("command_type") == 3 and request.get("command"):
        return str(request["command"]), True
    label = capture.get("label") or ""
    m = re.match(r"menu:\s*(Mark as \w+)", label)
    if request.get("type") == "modal_submit" and m:
        return m.group(1), True
    if request.get("command"):
        sub = request.get("subcommand")
        return "/" + str(request["command"]) + (f" {sub}" if sub else ""), False
    m = re.match(r"^/(\w+)(?: (\w+))?", capture.get("text_form") or "")
    if m:
        return "/" + m.group(1) + (f" {m.group(2)}" if m.group(2) else ""), False
    return "a command", False


# ---- the builder -------------------------------------------------------------------------


def _first(name: str) -> str:
    return (name or "").split(" ")[0]


class _Builder:
    def __init__(self, mapping: dict, state: dict, dataset: dict) -> None:
        self.items: dict = (mapping or {}).get("items", mapping or {})
        self.state = state or {}
        self.dataset = dataset or {"members": [], "messages": []}
        self.members = {m["id"]: m for m in self.dataset.get("members", [])}
        # Realism runs show handles (what Discord shows); the dataset name stays as a small secondary label.
        realism = self.state.get("mode") == "realism"
        self.shown: dict[str, str] = {}
        self.real: dict[str, str] = {}
        self.short: dict[str, str] = {}
        for mid, m in self.members.items():
            handle = S.HANDLES.get(mid) if realism and not m.get("is_bot") else None
            self.shown[mid] = handle or m["display_name"]
            self.real[mid] = m["display_name"] if handle else ""
            self.short[mid] = handle or _first(m["display_name"])
        self.users = {str(S.BASE + int(mid)): self.shown[mid] for mid in self.members if str(mid).isdigit()}
        self.prev_msg: tuple | None = None
        self.dmsg = {m["id"]: m for m in self.dataset.get("messages", [])}
        self.out: list[dict] = []
        self.act = 0
        self.seq = 0
        self.asks = 0
        self.by_key: dict[str, str] = {}
        self.by_emu: dict[str, str] = {}
        self.info: dict[str, dict] = {}
        self.host = "offline"
        self.host_note = ""
        self.was_offline = False
        self.pending: list[str] = []
        self.recon: int | None = None
        self.last_date = ""
        self.checks: dict[tuple, tuple[str, str]] = {}
        self.http_asks_seen = False
        self.last_t = 0.0
        self.finished = False

    # -- emit helpers

    def emit(self, kind: str, t: float, **fields: Any) -> dict:
        event = {"type": kind, "t": round(t, 3), **fields}
        if kind in ("act", "command", "reply", "ask", "answer"):
            self.prev_msg = None  # something else happened in between: the next message gets its own header
        self.out.append(event)
        return event

    def name_of(self, member: str | None) -> str:
        return self.shown.get(str(member or ""), "Someone")

    def short_of(self, member: str | None) -> str:
        return self.short.get(str(member or ""), "Someone")

    def ensure_act(self, n: int, t: float) -> None:
        if n and n != self.act and n in ACT_TITLES:
            self.act = n
            self.emit("act", t, n=n, title=ACT_TITLES[n], project_dates=ACT_DATES[n])

    def set_host(self, state: str, t: float, note: str = "") -> None:
        if state == self.host and note == self.host_note:
            return
        self.host, self.host_note = state, note
        if state == "offline":
            self.was_offline = True
        self.emit("host", t, state=state, note=note)

    def stored(self, ids: list[str], t: float, note: str = "") -> None:
        if ids:
            self.emit("stored", t, ids=list(ids), note=note)

    def flush_pending(self, t: float, note: str = "") -> None:
        ids, self.pending = self.pending, []
        self.stored(ids, t, note)

    def end_reconnect(self, t: float) -> None:
        if self.recon is None:
            return
        self.recon = None
        self.set_host("online", t, "reconnected")
        self.flush_pending(t)

    # -- timeline kinds

    def message(self, e: dict, t: float) -> None:
        key = e.get("key")
        entry = self.items.get(key) or {}
        ds = self.dmsg.get(key) or {}
        text = entry.get("content_posted")
        if text is None:
            text = ds.get("content")
        if text is None:
            return
        member = entry.get("poster_member") or ds.get("author_id")
        act = int(entry.get("act") or e.get("act") or self.act or 1)
        self.ensure_act(act, t)
        self.seq += 1
        sid = f"s{self.seq}"
        self.by_key[key] = sid
        if e.get("emu_id"):
            self.by_emu[str(e["emu_id"])] = sid
        elif entry.get("emu_id"):
            self.by_emu[str(entry["emu_id"])] = sid
        if ds.get("created_at"):
            self.last_date = short_date(ds["created_at"] / 1000)
        parent = self.by_emu.get(str(entry.get("reply_to_emu"))) if entry.get("reply_to_emu") else None
        channel = entry.get("channel") or "general"
        person = self.name_of(member)
        self.info[sid] = {"person": person, "short": self.short_of(member), "project_date": self.last_date}
        # Like Discord: the same author's consecutive messages share one header (fragments, bursts).
        prev = self.prev_msg
        cont = bool(prev and prev[0] == str(member) and prev[1] == channel and not parent and t - prev[2] < 120)
        self.prev_msg = (str(member), channel, t)
        self.emit("message", t, id=sid, person=person, short=self.short_of(member), real_name=self.real.get(str(member), ""),
                  person_id=str(member or ""), channel=channel, text=text, reply_to=parent, project_date=self.last_date,
                  is_bot=str(member) == BOT_MEMBER, private=channel == PRIVATE_CHANNEL, cont=cont, media=not text.strip())
        if self.recon is not None:
            self.pending.append(sid)
            self.recon += 1
            if self.recon >= RECONNECT_BURST:
                self.end_reconnect(t)
        elif self.host == "online":
            self.stored([sid], t)
        else:
            self.pending.append(sid)

    def edit(self, e: dict, t: float) -> None:
        sid = self.by_key.get(e.get("key"))
        if not sid:
            return
        ds = self.dmsg.get(e.get("key"))
        text = ds["content"] if ds else None
        if text is None:
            entry = self.items.get(e.get("key")) or {}
            text = re.sub(re.escape(S.EDIT_SUFFIX) + r"$", "", entry.get("content_posted") or "")
        self.emit("edit", t, id=sid, text=text)

    def delete(self, e: dict, t: float) -> None:
        sid = self.by_key.get(e.get("key"))
        if sid:
            self.pending = [p for p in self.pending if p != sid]
            self.emit("delete", t, id=sid)

    def react(self, e: dict, t: float) -> None:
        sid = self.by_key.get(e.get("key"))
        m = re.match(r"\s*(\d+)", e.get("summary") or "")
        if sid:
            self.emit("react", t, id=sid, count=int(m.group(1)) if m else 1)

    def host_event(self, e: dict, t: float) -> None:
        summary = (e.get("summary") or "").lower()
        if "gateway connected" in summary:
            self.set_host("online", t, "")
        elif "run started" in summary:
            self.set_host("reconnecting", t, "restarting and catching up" if self.was_offline else "starting up")
        elif "run stopped" in summary:
            if "offline gap" in summary:
                self.ensure_act(3, t)
                self.set_host("offline", t, "teamctx is offline")
            elif FINISH_MARK in summary:
                self.finish(t)
            else:
                self.set_host("offline", t, "teamctx stopped")

    def disconnect(self, e: dict, t: float) -> None:
        self.end_reconnect(t)
        mode = e.get("mode")
        note = "session invalidated, reconnecting" if mode == "invalidate" else "connection dropped, reconnecting"
        self.set_host("reconnecting", t, note)
        self.recon = 0

    def sync(self, e: dict, t: float) -> None:
        self.end_reconnect(t)
        self.flush_pending(t)

    def gap(self, e: dict, t: float) -> None:
        m = re.search(r"stored ([\d.]+) s", e.get("summary") or "")
        ids, self.pending = self.pending, []
        if not ids:
            return
        note = f"caught up {len(ids)} messages" + (f" in {m.group(1)} s" if m else "")
        self.stored(ids, t, note)

    def check(self, e: dict, t: float) -> None:
        summary = e.get("summary") or ""
        ident = summary.split(" ", 1)[0]
        status = e.get("status") or summary.rsplit(": ", 1)[-1]
        self.checks[(ident, e.get("act"))] = (status, ident)

    def finish(self, t: float) -> None:
        self.finished = True  # whatever the harness does after the final stop (re-checks) is not part of the story
        if not self.http_asks_seen:
            self.synthesize_http_asks(t)
        # The saved checks are the latest truth (a check can be re-run); the timeline is the fallback.
        for c in self.state.get("checks") or []:
            self.checks[(str(c.get("id")), c.get("act"))] = (c.get("status"), str(c.get("id")))
        if not self.checks:
            return
        evidence = {(str(c.get("id")), c.get("act")): c.get("evidence") or "" for c in self.state.get("checks") or []}
        failed, decisions = [], []
        order = sorted(self.checks.items(), key=lambda kv: (int(kv[0][0]) if kv[0][0].isdigit() else 99, kv[0][1] or 0))
        for (ident, act), (status, _) in order:
            if status != "fail":
                continue
            name = CHECK_WORDS.get(ident, f"Check {ident}")
            # A finding the maintainer has to decide on is not a failure of the harness or a bug.
            (decisions if PRODUCT_DECISION in evidence.get((ident, act), "") else failed).append(name)
        passed = sum(1 for status, _ in self.checks.values() if status == "pass")
        self.emit("done", t + 0.5, passed=passed, total=len(self.checks), failed=failed, decisions=decisions)

    # -- commands and replies

    def user_name(self, value: Any) -> str | None:
        return self.users.get(str(value)) or (self.name_of(str(value)) if str(value) in self.members else None)

    def describe_args(self, capture: dict) -> str:
        options = (capture.get("request") or {}).get("options") or {}
        if options.get("text"):
            return shorten(str(options["text"]), 110)
        parts = []
        if options.get("id"):
            parts.append(str(options["id"]))
        if options.get("owner"):
            owner = self.user_name(options["owner"])
            if owner:
                parts.append(f"owner {_first(owner)}")
        if options.get("include_superseded"):
            parts.append("including replaced ones")
        if options.get("public"):
            parts.append("shown to everyone")
        return ", ".join(parts)

    def capture(self, e: dict, t: float) -> None:
        cap = (self.state.get("captures") or {}).get(e.get("key"))
        if not cap:
            return
        actor = str(cap.get("actor"))
        person = self.name_of(actor)
        command, menu = command_label(cap)
        request = cap.get("request") or {}
        text = cap.get("text") or ""
        target = None
        for emu in [str(request.get("target_id") or ""), str((request.get("options") or {}).get("message_link") or ""),
                    *emu_ids_in(text)]:
            found = self.by_emu.get(emu) or next((self.by_emu[x] for x in emu_ids_in(emu) if x in self.by_emu), None)
            if found:
                target = found
                break
        cid = str(e.get("key"))
        self.emit("command", t, id=cid, person=person, short=self.short_of(actor), person_id=actor, command=command,
                  argument="" if menu else self.describe_args(cap), target_message=target, menu=menu)
        record = parse_record(text, person)
        private = person if cap.get("ephemeral") else None
        self.emit("reply", t, command_id=cid, text=reply_text(text, record), private_to=private,
                  private_short=self.short_of(actor) if private else None, record=record,
                  ok=bool(cap.get("ok")) and not cap.get("error"))

    # -- asks

    def citations(self, urls_or_ids: list[str]) -> list[dict]:
        out, seen = [], set()
        for raw in urls_or_ids:
            sid = self.by_emu.get(raw)
            if sid and sid not in seen:
                seen.add(sid)
                info = self.info.get(sid, {})
                out.append({"person": info.get("person", ""), "short": info.get("short", ""), "project_date": info.get("project_date", ""), "message_id": sid})
        return out

    def ask_pair(self, t: float, person: str, question: str, text: str, found: bool, emu_ids: list[str],
                 private_to: str | None, short: str | None = None) -> None:
        self.asks += 1
        aid = f"a{self.asks}"
        self.emit("ask", t, id=aid, person=person, short=short or person, question=shorten(question, 200))
        if found:
            body = answer_body(text)
            cites = self.citations(emu_ids)
        else:
            body = clean_markup((text or "").split("\n", 1)[0])
            cites = []
        self.emit("answer", t, ask_id=aid, text=body, citations=cites, found=found, private_to=private_to,
                  private_short=(short or private_to) if private_to else None)

    def catchup_absent(self, e: dict, q: dict, t: float) -> None:
        """The member who was away comes back and asks for a catch-up: a story beat of its own."""
        actor = str(q.get("actor"))
        cid = str(e.get("key"))
        text = reply_text(q.get("text") or "", None)
        self.emit("command", t, id=cid, person=self.name_of(actor), short=self.short_of(actor), person_id=actor,
                  command="/catchup", argument="after being away", target_message=None, menu=False)
        self.emit("reply", t, command_id=cid, text=text, private_to=self.name_of(actor) if q.get("ephemeral") else None,
                  private_short=self.short_of(actor) if q.get("ephemeral") else None, record=None, ok=bool(q.get("ok")))

    def query(self, e: dict, t: float) -> None:
        q = (self.state.get("queries") or {}).get(e.get("key"))
        if q and (q.get("request") or {}).get("command") == "catchup" and "absent" in str(e.get("key")):
            return self.catchup_absent(e, q, t)
        if not q or (q.get("request") or {}).get("command") != "ask":
            return
        question = ((q.get("request") or {}).get("options") or {}).get("question") or ""
        text = q.get("text") or ""
        found = bool(q.get("ok")) and not re.match(r"^I couldn.t find", text.strip())
        person = self.name_of(str(q.get("actor")))
        self.ask_pair(t, person, question, text, found, emu_ids_in(text), person if q.get("ephemeral") else None,
                      self.short_of(str(q.get("actor"))))

    def http_ask(self, e: dict, t: float) -> None:
        self.http_asks_seen = True
        urls = [emu for c in (e.get("citations") or []) for emu in emu_ids_in(c.get("url") or "")]
        self.ask_pair(t, "agent", e.get("question") or "", e.get("text") or "", bool(e.get("found")), urls, None)

    def synthesize_http_asks(self, t: float) -> None:
        """Runs recorded before `ask` timeline events existed: read the answers from state.json."""
        asks = self.state.get("asks") or {}
        for n, key in enumerate(sorted(asks, key=lambda k: (k.startswith("inj"), k))):
            a = asks[key]
            urls = [emu for c in (a.get("citations") or []) for emu in emu_ids_in(c.get("url") or "")]
            self.ask_pair(t - 0.5 + n * 0.01, "agent", a.get("question") or "", a.get("text") or "", bool(a.get("found")),
                          urls, None)
        self.http_asks_seen = True

    # -- main loop

    def run(self, timeline: list[dict]) -> list[dict]:
        start = 0
        for i, e in enumerate(timeline):
            if e.get("kind") == "run":
                start = i
        handlers = {"message": self.message, "edit": self.edit, "delete": self.delete, "host": self.host_event,
                    "disconnect": self.disconnect, "sync": self.sync, "gap": self.gap, "capture": self.capture,
                    "query": self.query, "ask": self.http_ask, "check": self.check, "react": self.react}
        for e in timeline[start:]:
            t = epoch_of(e.get("t") or "")
            self.last_t = t
            handler = handlers.get(e.get("kind"))
            if handler:
                handler(e, t)
            if self.finished:
                break
        return self.out


def scrub(value: Any) -> Any:
    """Last step: harness redaction plus a snowflake scrub on every string, recursively."""
    if isinstance(value, str):
        return SNOWFLAKE.sub("\u2026", envfile.redact(value))
    if isinstance(value, list):
        return [scrub(v) for v in value]
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items()}
    return value


def build_story(timeline: list[dict], mapping: dict, state: dict, dataset: dict) -> list[dict]:
    """All story events for the run recorded in `timeline` (from its last `run` event)."""
    envfile.REDACTOR.add(S.SIM_SECRET)  # the fake key the realism run pastes into chat; shape patterns cover it too
    return scrub(_Builder(mapping, state, dataset).run(timeline))


# ---- live or replay ----------------------------------------------------------------------


def run_finished(timeline: list[dict]) -> bool:
    """A run is over once the host's final stop ("(end of run)") is on the timeline."""
    start = 0
    for i, e in enumerate(timeline):
        if e.get("kind") == "run":
            start = i
    return any(e.get("kind") == "host" and FINISH_MARK in (e.get("summary") or "") for e in timeline[start:])


def detect_mode(timeline: list[dict], file_age: float | None, active: bool = False) -> str:
    """'live' while a run is in progress, else 'replay'.

    In progress means: the viz was started together with a run (`active`), or the timeline is
    not empty, has no final "(end of run)" stop, and was written to within the last 30 seconds.
    A run that crashed leaves a timeline that goes stale and is shown as a replay. A finished
    run is always a replay, even if its file was touched a moment ago.
    """
    if timeline and run_finished(timeline):
        return "replay"
    if active:
        return "live"
    if timeline and file_age is not None and file_age <= LIVE_WINDOW_SECONDS:
        return "live"
    return "replay"


def count_types(events: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for e in events:
        out[e["type"]] = out.get(e["type"], 0) + 1
    return out


def setup_note(timeline: list[dict]) -> str | None:
    """A friendly progress line while a run is being set up (before the first message), else None."""
    start = 0
    for i, e in enumerate(timeline):
        if e.get("kind") == "run":
            start = i
    seen = timeline[start:]
    if any(e.get("kind") == "message" for e in seen):
        return None
    if any(e.get("kind") == "host" for e in seen):
        return "teamctx is connecting…"
    if seen:
        return "Setting up the team…"
    return "Starting the run…"
