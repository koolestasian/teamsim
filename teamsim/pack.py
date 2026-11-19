"""Load, check, hash and write a pack (pack format 1).

A pack is a directory holding ``pack.toml`` and ``timeline.jsonl``. The format is
specified in ``docs/spec/pack-format.md``; this module and that document must
agree, and ``tests/test_pack.py`` checks that every rule code below has a test and
a line in the document.

``load(path)`` reads both files, rejects anything outside the format with one
``PackError`` (the first problem found, in the order the document states) and
returns a ``model.Pack``. ``pack_hash(pack)`` is the hash defined in section 3.2 of
the engine specification. ``write(pack, path)`` writes both files in one fixed
spelling, so writing a loaded pack twice gives identical bytes.
"""

import re
import tomllib
from collections import deque
from pathlib import Path

from . import canon, model
from .model import (
    Actor,
    After,
    At,
    Check,
    Event,
    Fact,
    ModelError,
    On,
    Pack,
    PackHeader,
    Provenance,
    Subject,
    Surface,
)

__all__ = [
    "MAX_ACTORS",
    "MAX_CHECKS",
    "MAX_EVENTS",
    "MAX_FACTS",
    "MAX_LINE_BYTES",
    "MAX_SURFACES",
    "MAX_TIMELINE_BYTES",
    "MAX_TIME_MS",
    "MAX_TOML_BYTES",
    "PackError",
    "RULES",
    "load",
    "pack_hash",
    "validate",
    "write",
]

TOML_FILE = "pack.toml"
TIMELINE_FILE = "timeline.jsonl"

# Size limits. Each keeps a hostile pack from exhausting memory or time.
MAX_TOML_BYTES = 1 << 20  # 1 MiB: far above a hand-written pack, bounds the parser
MAX_TIMELINE_BYTES = 64 << 20  # 64 MiB: bounds memory before any line is parsed
MAX_LINE_BYTES = 64 << 10  # 64 KiB: no chat message needs more, bounds one event
MAX_EVENTS = 100_000  # ten times the engine's 10,000-event performance target
MAX_ACTORS = 1_000
MAX_SURFACES = 1_000
MAX_FACTS = 10_000
MAX_CHECKS = 10_000
# 2**40 ms is about 34 years; a sum of two such times stays far below 2**53.
MAX_TIME_MS = 1 << 40

# Rule codes with a one-line meaning. The document lists the same codes.
RULES = {
    "missing_file": "pack.toml or timeline.jsonl is absent",
    "bad_text": "a file is not UTF-8, begins with a byte order mark or holds a carriage return",
    "limit_exceeded": "a size limit is exceeded",
    "bad_toml": "pack.toml is not valid TOML",
    "non_canonical": "a pack.toml value is outside the canonical form",
    "bad_line": "a timeline line is blank, unterminated or not one canonical JSON object",
    "unknown_field": "a key or field the format does not define",
    "missing_field": "a required key or field is absent",
    "bad_type": "a value has the wrong type",
    "bad_format": "format is not 1",
    "bad_kind": "a kind is not one of the allowed names",
    "time_form": "an event does not have exactly one of at, after and on",
    "negative_time": "a time, delay or window is negative",
    "bad_id": "an id or key does not match the id rule",
    "duplicate_id": "two items of one kind share an id",
    "unknown_actor": "a reference names an actor that is not declared",
    "unknown_surface": "a reference names a surface that is not declared",
    "unknown_fact": "a reference names a fact id that is not declared",
    "unknown_event": "a reference names an event id that is not in the timeline",
    "unknown_fact_key": "a check names a fact key that no fact has",
    "bad_surface": "a surface or an event on a surface breaks the rules for its kind",
    "bad_audience": "a fact audience is empty, repeats an entry or misuses *",
    "bad_authority": "a fact authority is empty or repeats an actor",
    "bad_fact": "a fact value or form is empty or a form is repeated",
    "bad_supersedes": "a supersedes link is to another key, repeated or circular",
    "bad_actor": "an event names the subject or an actor where the kind requires the other",
    "bad_payload": "an event carries the wrong payload for its kind",
    "bad_target": "a target is not a post, or is on another surface or by another actor",
    "not_a_member": "an actor acts on a surface it can never be a member of",
    "dependency_cycle": "events depend on each other in a cycle",
    "time_order": "static times run backwards in the file or against a dependency",
    "fact_never_disclosed": "no event discloses a fact",
    "not_a_probe": "a check names an event that is not a probe post or op",
    "bad_check": "a check has the wrong fields for its kind or an unknown tag",
    "missing_control": "a check lacks the paired positive-control check",
}

_ID = re.compile(r"[a-z0-9_.:-]{1,64}")
_GROUP = model.AUDIENCE_GROUP_PREFIX
_SUBJECT_KINDS = (
    model.EVENT_SUBJECT_JOIN,
    model.EVENT_SUBJECT_LEAVE,
    model.EVENT_SUBJECT_DOWN,
    model.EVENT_SUBJECT_UP,
)
_PAYLOAD = {
    model.EVENT_POST: ("text",),
    model.EVENT_EDIT: ("target", "text"),
    model.EVENT_DELETE: ("target",),
    model.EVENT_REACT: ("target", "emoji"),
    model.EVENT_OP: ("op", "args"),
}
_PAYLOAD_FIELDS = ("text", "target", "emoji", "op", "args")
_DISCLOSING = (model.EVENT_POST, model.EVENT_EDIT, model.EVENT_OP)
_PROBING = (model.EVENT_POST, model.EVENT_OP)
_ACTING = (
    model.EVENT_POST,
    model.EVENT_EDIT,
    model.EVENT_DELETE,
    model.EVENT_REACT,
    model.EVENT_OP,
    model.EVENT_LEAVE,
)
_MEMBERSHIP = (
    model.EVENT_JOIN,
    model.EVENT_LEAVE,
    model.EVENT_SUBJECT_JOIN,
    model.EVENT_SUBJECT_LEAVE,
)
_CHECK_FIELDS = {
    model.CHECK_HARNESS: (),
    model.CHECK_ANSWER: ("key", "probe"),
    model.CHECK_WITHHOLD: ("fact", "probe"),
    model.CHECK_NO_LEAK: ("fact",),
    model.CHECK_NO_ECHO: ("fact",),
    model.CHECK_CATCH_UP: ("probe",),
}

# Emission order of keys in pack.toml. Optional keys are left out when absent.
_ORDER = {
    "actors": ("id", "role", "display", "traits"),
    "surfaces": ("id", "kind", "members"),
    "facts": (
        "id",
        "key",
        "kind",
        "value",
        "forms",
        "authority",
        "audience",
        "supersedes",
    ),
    "checks": ("id", "kind", "key", "fact", "probe", "tags"),
    "provenance": ("generator_version", "population_hash", "parent_pack_hash", "transformation"),
}


class PackError(ValueError):
    """A pack that the format rejects.

    ``code`` is a stable rule code (a key of ``RULES``). ``file`` is the file at
    fault. ``path`` is a TOML key path such as ``facts[1].audience[0]``, or, for the
    timeline, a field name. ``line`` and ``event`` locate a timeline event. ``location``
    joins them in one string.
    """

    def __init__(self, code, file, message, *, path=None, line=None, event=None):
        super().__init__(code, file, message)
        self.code = code
        self.file = file
        self.message = message
        self.path = path
        self.line = line
        self.event = event

    @property
    def location(self) -> str:
        if self.line is None:
            return self.path or ""
        text = f"line {self.line}"
        if self.event is not None:
            text += f" event {self.event}"
        if self.path:
            text += f" field {self.path}"
        return text

    def __str__(self) -> str:
        where = self.location
        return f"{self.file}: {where + ': ' if where else ''}{self.code}: {self.message}"


def _err(code, file, message, path=None, line=None, event=None):
    return PackError(code, file, message, path=path, line=line, event=event)


# --- reading ---------------------------------------------------------------


def _read_file(root: Path, name: str, limit: int) -> str:
    path = root / name
    try:
        if not path.is_file():
            raise _err("missing_file", name, f"{name} is not a file in the pack directory")
        size = path.stat().st_size
        if size > limit:
            raise _err("limit_exceeded", name, f"{size} bytes exceeds the limit of {limit}")
        data = path.read_bytes()
    except OSError as error:
        raise _err("missing_file", name, f"cannot read {name}: {error.strerror}") from None
    if data.startswith(b"\xef\xbb\xbf"):
        raise _err("bad_text", name, "begins with a byte order mark")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise _err("bad_text", name, f"not UTF-8 (byte {error.start})") from None
    if "\r" in text:
        raise _err("bad_text", name, "contains a carriage return; lines end with a line feed")
    return text


_PATH_PART = re.compile(r'\["([^"]*)"\]|\[(\d+)\]')


def _key_path(canon_path: str) -> str:
    """Turn a canon path such as ``$["actors"][2]["id"]`` into ``actors[2].id``."""
    out = ""
    for name, index in _PATH_PART.findall(canon_path):
        out += f"[{index}]" if index else ("." if out else "") + name
    return out


_FIELD = re.compile(r"field '([^']+)'")


def _model_error(error: ModelError, file, path, line=None, event=None):
    message = str(error)
    field = _FIELD.search(message)
    name = field.group(1) if field else None
    if "unknown field" in message:
        code = "unknown_field"
    elif "missing field" in message:
        code = "missing_field"
    elif "needs exactly one of" in message:
        code, name = "time_form", None
    elif "is not one of" in message:
        code, name = "bad_kind", "kind"
    else:
        code = "bad_type"
    if line is None:
        full = path if not name else (f"{path}.{name}" if path else name)
        return _err(code, file, message, path=full)
    return _err(code, file, message, path=name, line=line, event=event)


def _read_typed(cls, obj, file, path, line=None, event=None):
    try:
        return cls.from_obj(obj)
    except ModelError as error:
        raise _model_error(error, file, path, line, event) from None
    except canon.CanonError as error:
        raise _err("non_canonical", file, str(error), path=path, line=line, event=event) from None


def _build_header(obj: dict) -> PackHeader:
    allowed = set(model.PACK_HEADER_FIELDS) | set(model.PACK_TABLES) | set(model.PACK_LISTS)
    for key in obj:
        if key not in allowed:
            raise _err("unknown_field", TOML_FILE, f"unknown key {key!r}", path=key)
    sub = {key: obj[key] for key in model.PACK_HEADER_FIELDS if key in obj}
    return _read_typed(PackHeader, sub, TOML_FILE, "")


def _items(obj: dict, name: str, cls) -> tuple:
    value = obj.get(name, [])
    if type(value) is not list:
        raise _err("bad_type", TOML_FILE, f"{name} must be an array of tables", path=name)
    return tuple(
        _read_typed(cls, item, TOML_FILE, f"{name}[{index}]") for index, item in enumerate(value)
    )


def _build_pack(toml_obj: dict, events: tuple) -> Pack:
    header = _build_header(toml_obj)
    if "subject" not in toml_obj:
        raise _err("missing_field", TOML_FILE, "missing table 'subject'", path="subject")
    subject = _read_typed(Subject, toml_obj["subject"], TOML_FILE, "subject")
    provenance = None
    if "provenance" in toml_obj:
        provenance = _read_typed(Provenance, toml_obj["provenance"], TOML_FILE, "provenance")
    return Pack(
        header=header,
        subject=subject,
        actors=_items(toml_obj, "actors", Actor),
        surfaces=_items(toml_obj, "surfaces", Surface),
        facts=_items(toml_obj, "facts", Fact),
        checks=_items(toml_obj, "checks", Check),
        events=events,
        provenance=provenance,
    )


def _read_timeline(text: str):
    """Return the events and the line number of each."""
    if not text:
        return (), []
    if not text.endswith("\n"):
        raise _err(
            "bad_line",
            TIMELINE_FILE,
            "the last line has no line feed",
            line=text.count("\n") + 1,
        )
    # The text ends with a line feed, so the count of line feeds is the count of
    # lines; check it before splitting so a hostile file builds no huge list.
    if text.count("\n") > MAX_EVENTS:
        raise _err("limit_exceeded", TIMELINE_FILE, f"more than {MAX_EVENTS} events")
    lines = text.split("\n")[:-1]
    events = []
    for number, line in enumerate(lines, 1):
        if len(line.encode("utf-8")) > MAX_LINE_BYTES:
            raise _err(
                "limit_exceeded",
                TIMELINE_FILE,
                f"a line is longer than {MAX_LINE_BYTES} bytes",
                line=number,
            )
        if not line.strip():
            raise _err("bad_line", TIMELINE_FILE, "blank line", line=number)
        try:
            obj = canon.parse(line)
        except canon.CanonError as error:
            raise _err("bad_line", TIMELINE_FILE, str(error), line=number) from None
        if type(obj) is not dict:
            raise _err("bad_line", TIMELINE_FILE, "the line is not a JSON object", line=number)
        event_id = obj.get("id") if type(obj.get("id")) is str else None
        events.append(_read_typed(Event, obj, TIMELINE_FILE, None, number, event_id))
    return tuple(events), list(range(1, len(lines) + 1))


def load(path) -> Pack:
    """Read the pack in directory ``path``; raise ``PackError`` if it breaks a rule."""
    root = Path(path)
    toml_text = _read_file(root, TOML_FILE, MAX_TOML_BYTES)
    timeline_text = _read_file(root, TIMELINE_FILE, MAX_TIMELINE_BYTES)
    try:
        toml_obj = tomllib.loads(toml_text)
    except (ValueError, RecursionError) as error:  # includes TOMLDecodeError and the int digit limit
        raise _err("bad_toml", TOML_FILE, str(error)) from None
    try:
        canon.check(toml_obj)
    except canon.CanonError as error:
        raise _err("non_canonical", TOML_FILE, error.reason, path=_key_path(error.path)) from None
    events, lines = _read_timeline(timeline_text)
    pack = _build_pack(toml_obj, events)
    validate(pack, lines)
    return pack


# --- hash ------------------------------------------------------------------


def pack_hash(pack: Pack) -> str:
    """``hash({"pack": <pack.toml as an object>, "timeline": [<events in file order>]})``."""
    return canon.hash_of({"pack": pack.to_obj(), "timeline": pack.timeline_objs()})


# --- semantic rules --------------------------------------------------------


def validate(pack: Pack, lines=None) -> None:
    """Check every rule that needs more than one value; raise ``PackError``.

    ``lines`` gives the timeline line number of each event; by default event ``i``
    is on line ``i + 1``. The first problem found is raised, in the order the
    format document states.
    """
    _Validator(pack, lines).run()


class _Validator:
    def __init__(self, pack: Pack, lines):
        self.p = pack
        self.lines = lines if lines is not None else list(range(1, len(pack.events) + 1))

    # errors
    def t(self, code, path, message):
        return _err(code, TOML_FILE, message, path=path)

    def e(self, code, index, message, field=None):
        event = self.p.events[index]
        return _err(
            code, TIMELINE_FILE, message, path=field, line=self.lines[index], event=event.id
        )

    def run(self):
        p = self.p
        self.limits()
        try:
            canon.check(p.to_obj())
            canon.check(p.timeline_objs())
        except canon.CanonError as error:
            raise _err("non_canonical", TOML_FILE, str(error)) from None
        # pack_hash() wraps both in one object, which adds depth; every pack that
        # loads must hash, so check the wrapped value too.
        try:
            canon.check({"pack": p.to_obj(), "timeline": p.timeline_objs()})
        except canon.CanonError as error:
            file = TIMELINE_FILE if error.path.startswith('$["timeline"]') else TOML_FILE
            raise _err("non_canonical", file, str(error)) from None
        if p.header.format != model.FORMAT:
            raise self.t("bad_format", "format", f"format is {p.header.format}, not {model.FORMAT}")
        self.ids()
        self.index()
        self.surfaces()
        self.facts()
        self.events()
        self.graph()
        self.disclosure()
        self.checks()
        self.pairing()

    # 1 limits
    def limits(self):
        p = self.p
        for name, count, cap in (
            ("actors", len(p.actors), MAX_ACTORS),
            ("surfaces", len(p.surfaces), MAX_SURFACES),
            ("facts", len(p.facts), MAX_FACTS),
            ("checks", len(p.checks), MAX_CHECKS),
        ):
            if count > cap:
                raise self.t("limit_exceeded", name, f"{count} {name} exceeds the limit of {cap}")
        if len(p.events) > MAX_EVENTS:
            raise _err("limit_exceeded", TIMELINE_FILE, f"more than {MAX_EVENTS} events")

    # 2 ids
    def check_id(self, value, path, event=None):
        if not _ID.fullmatch(value):
            message = f"{value!r} does not match [a-z0-9_.:-]{{1,64}}"
            if event is None:
                raise self.t("bad_id", path, message)
            raise self.e("bad_id", event, message, path)

    def ids(self):
        p = self.p
        self.check_id(p.header.id, "id")
        self.check_id(p.subject.id, "subject.id")
        if p.subject.id.startswith(_GROUP):
            raise self.t("bad_id", "subject.id", f"an id may not start with {_GROUP!r}")
        seen = {p.subject.id}
        for index, actor in enumerate(p.actors):
            path = f"actors[{index}].id"
            self.check_id(actor.id, path)
            if actor.id.startswith(_GROUP):
                raise self.t("bad_id", path, f"an id may not start with {_GROUP!r}")
            if actor.id in seen:
                raise self.t("duplicate_id", path, f"actor id {actor.id!r} is already used")
            seen.add(actor.id)
        for name, items in (("surfaces", p.surfaces), ("facts", p.facts), ("checks", p.checks)):
            seen = set()
            for index, item in enumerate(items):
                path = f"{name}[{index}].id"
                self.check_id(item.id, path)
                if item.id in seen:
                    raise self.t("duplicate_id", path, f"{name} id {item.id!r} is already used")
                seen.add(item.id)
        for index, fact in enumerate(p.facts):
            self.check_id(fact.key, f"facts[{index}].key")
        seen = set()
        for index, event in enumerate(p.events):
            self.check_id(event.id, "id", index)
            if event.id in seen:
                raise self.e("duplicate_id", index, f"event id {event.id!r} is already used", "id")
            seen.add(event.id)

    def index(self):
        p = self.p
        self.actor_ids = {a.id for a in p.actors}
        self.surface = {s.id: s for s in p.surfaces}
        self.fact = {f.id: f for f in p.facts}
        self.fact_keys = {f.key for f in p.facts}
        self.event_at = {e.id: i for i, e in enumerate(p.events)}
        self.initial = {s.id: set(s.members) for s in p.surfaces}
        self.joins = {
            (e.actor, e.surface)
            for e in p.events
            if e.kind in (model.EVENT_JOIN, model.EVENT_SUBJECT_JOIN)
        }

    # 3 surfaces
    def surfaces(self):
        subject = self.p.subject.id
        for index, surface in enumerate(self.p.surfaces):
            base = f"surfaces[{index}]"
            seen = set()
            for position, member in enumerate(surface.members):
                path = f"{base}.members[{position}]"
                if member != subject and member not in self.actor_ids:
                    raise self.t("unknown_actor", path, f"{member!r} is not a declared actor")
                if member in seen:
                    raise self.t("bad_surface", path, f"member {member!r} is listed twice")
                seen.add(member)
            if surface.kind == model.SURFACE_DIRECT:
                others = [m for m in surface.members if m != subject]
                if len(surface.members) != 2 or subject not in surface.members or len(others) != 1:
                    raise self.t(
                        "bad_surface",
                        f"{base}.members",
                        "a direct surface has exactly one actor and the subject",
                    )
            elif surface.kind != model.SURFACE_CHANNEL:
                raise self.t("bad_kind", f"{base}.kind", f"surface kind {surface.kind!r}")

    # 4 facts
    def facts(self):
        for index, fact in enumerate(self.p.facts):
            base = f"facts[{index}]"
            if fact.kind not in model.FACT_KINDS:
                raise self.t("bad_kind", f"{base}.kind", f"fact kind {fact.kind!r}")
            if not fact.value:
                raise self.t("bad_fact", f"{base}.value", "the value is empty")
            forms = fact.forms or ()
            seen_forms = set()
            for position, form in enumerate(forms):
                path = f"{base}.forms[{position}]"
                if not form:
                    raise self.t("bad_fact", path, "a form is empty")
                if form in seen_forms:
                    raise self.t("bad_fact", path, f"form {form!r} is listed twice")
                seen_forms.add(form)
            self.authority(fact, base)
            self.audience(fact, base)
        successors = set()
        for index, fact in enumerate(self.p.facts):
            if fact.supersedes is None:
                continue
            path = f"facts[{index}].supersedes"
            if fact.supersedes not in self.fact:
                raise self.t("unknown_fact", path, f"{fact.supersedes!r} is not a declared fact")
            target = self.fact[fact.supersedes]
            if target.key != fact.key:
                raise self.t("bad_supersedes", path, "a fact supersedes only a fact with its key")
            if fact.supersedes in successors:
                raise self.t("bad_supersedes", path, "the fact is already superseded by another")
            successors.add(fact.supersedes)
            seen = {fact.id}
            walk = target
            while True:
                if walk.id in seen:
                    raise self.t("bad_supersedes", path, "supersedes links form a cycle")
                seen.add(walk.id)
                if walk.supersedes is None or walk.supersedes not in self.fact:
                    break
                walk = self.fact[walk.supersedes]

    def authority(self, fact, base):
        if not fact.authority:
            raise self.t("bad_authority", f"{base}.authority", "the authority is empty")
        for position, name in enumerate(fact.authority):
            path = f"{base}.authority[{position}]"
            if name not in self.actor_ids:
                raise self.t("unknown_actor", path, f"{name!r} is not a declared actor")
            if name in fact.authority[:position]:
                raise self.t("bad_authority", path, f"{name!r} is listed twice")

    def audience(self, fact, base):
        entries = fact.audience
        if not entries:
            raise self.t("bad_audience", f"{base}.audience", "the audience is empty")
        if model.AUDIENCE_ALL in entries and len(entries) != 1:
            raise self.t("bad_audience", f"{base}.audience", "* must be the only entry")
        for position, entry in enumerate(entries):
            path = f"{base}.audience[{position}]"
            if entry in entries[:position]:
                raise self.t("bad_audience", path, f"{entry!r} is listed twice")
            if entry == model.AUDIENCE_ALL:
                continue
            if entry.startswith(_GROUP):
                if entry[len(_GROUP) :] not in self.surface:
                    raise self.t("unknown_surface", path, f"{entry!r} names no declared surface")
            elif entry not in self.actor_ids:
                raise self.t("unknown_actor", path, f"{entry!r} is not a declared actor")

    # 5 events
    def events(self):
        for index, event in enumerate(self.p.events):
            self.event(index, event)
        for index, event in enumerate(self.p.events):
            self.event_refs(index, event)
        for index, event in enumerate(self.p.events):
            self.membership(index, event)

    def event(self, index, event):
        subject = self.p.subject.id
        if event.kind not in model.EVENT_KINDS:
            raise self.e("bad_kind", index, f"event kind {event.kind!r}", "kind")
        when = event.when
        if isinstance(when, At):
            self.time(index, when.ms, "at")
        elif isinstance(when, After):
            self.time(index, when.delay_ms, "after.delay_ms")
        elif isinstance(when, On):
            trigger = when.trigger
            self.time(index, trigger.within_ms, "on.within_ms")
            if trigger.delay_ms is not None:
                self.time(index, trigger.delay_ms, "on.delay_ms")
            if isinstance(trigger, model.SubjectPost):
                if trigger.surface not in self.surface:
                    raise self.e(
                        "unknown_surface", index, f"{trigger.surface!r} is not declared", "on.surface"
                    )
            elif trigger.actor not in self.actor_ids:
                raise self.e("unknown_actor", index, f"{trigger.actor!r} is not declared", "on.actor")
        else:
            raise self.e("time_form", index, "the event has no time form")
        if event.kind in _SUBJECT_KINDS:
            if event.actor != subject:
                raise self.e("bad_actor", index, f"a {event.kind} event names the subject", "actor")
        elif event.actor == subject:
            raise self.e("bad_actor", index, f"a {event.kind} event is by an actor", "actor")
        elif event.actor not in self.actor_ids:
            raise self.e("unknown_actor", index, f"{event.actor!r} is not declared", "actor")
        if event.surface not in self.surface:
            raise self.e("unknown_surface", index, f"{event.surface!r} is not declared", "surface")
        self.payload(index, event)
        surface = self.surface[event.surface]
        if event.kind == model.EVENT_OP and surface.kind != model.SURFACE_DIRECT:
            raise self.e("bad_surface", index, "an op event belongs on a direct surface", "surface")
        if event.kind in _MEMBERSHIP and surface.kind == model.SURFACE_DIRECT:
            raise self.e(
                "bad_surface", index, "membership of a direct surface does not change", "surface"
            )

    def time(self, index, value, field):
        if value < 0:
            raise self.e("negative_time", index, f"{field} is negative", field)
        if value > MAX_TIME_MS:
            raise self.e("limit_exceeded", index, f"{field} exceeds {MAX_TIME_MS}", field)

    def payload(self, index, event):
        wanted = _PAYLOAD.get(event.kind, ())
        for name in _PAYLOAD_FIELDS:
            value = getattr(event, name)
            if name in wanted and value is None:
                raise self.e("bad_payload", index, f"a {event.kind} event needs {name}", name)
            if name not in wanted and value is not None:
                raise self.e("bad_payload", index, f"a {event.kind} event has no {name}", name)
            if name in ("text", "emoji", "op") and value == "":
                raise self.e("bad_payload", index, f"{name} is empty", name)
        if event.discloses is not None and event.kind not in _DISCLOSING:
            raise self.e("bad_payload", index, f"a {event.kind} event cannot disclose", "discloses")
        if event.probe is not None and event.kind not in _PROBING:
            raise self.e("bad_payload", index, f"a {event.kind} event cannot be a probe", "probe")

    def event_refs(self, index, event):
        when = event.when
        if isinstance(when, After) and when.event not in self.event_at:
            raise self.e("unknown_event", index, f"{when.event!r} is not an event", "after.event")
        for name, values in (("depends_on", event.depends_on), ("discloses", event.discloses)):
            seen = set()
            for value in values or ():
                known = self.event_at if name == "depends_on" else self.fact
                if value not in known:
                    code = "unknown_event" if name == "depends_on" else "unknown_fact"
                    raise self.e(code, index, f"{value!r} is not declared", name)
                if value in seen:
                    raise self.e("bad_payload", index, f"{value!r} is listed twice", name)
                seen.add(value)
        if event.target is not None:
            if event.target not in self.event_at:
                raise self.e("unknown_event", index, f"{event.target!r} is not an event", "target")
            target = self.p.events[self.event_at[event.target]]
            if target.kind != model.EVENT_POST:
                raise self.e("bad_target", index, "the target is not a post", "target")
            if target.surface != event.surface:
                raise self.e("bad_target", index, "the target is on another surface", "target")
            if event.kind != model.EVENT_REACT and target.actor != event.actor:
                raise self.e("bad_target", index, "the target is another actor's post", "target")

    def can_be_member(self, who, surface):
        return who in self.initial[surface] or (who, surface) in self.joins

    def membership(self, index, event):
        surface = event.surface
        if event.kind in _ACTING or event.kind == model.EVENT_SUBJECT_LEAVE:
            if not self.can_be_member(event.actor, surface):
                raise self.e(
                    "not_a_member",
                    index,
                    f"{event.actor!r} is never a member of {surface!r}",
                    "actor",
                )

    # 6 dependency graph, cycles, static time
    def deps(self, event):
        out = []
        if isinstance(event.when, After):
            out.append(event.when.event)
        if event.target is not None:
            out.append(event.target)
        out.extend(event.depends_on or ())
        return [self.event_at[name] for name in out]

    def graph(self):
        events = self.p.events
        count = len(events)
        deps = [self.deps(e) for e in events]
        waiting = [len(set(d)) for d in deps]
        dependents = [[] for _ in range(count)]
        for i, d in enumerate(deps):
            for j in set(d):
                dependents[j].append(i)
        queue = deque(i for i in range(count) if waiting[i] == 0)
        order = []
        while queue:
            i = queue.popleft()
            order.append(i)
            for k in dependents[i]:
                waiting[k] -= 1
                if waiting[k] == 0:
                    queue.append(k)
        if len(order) != count:
            done = set(order)
            at = next(i for i in range(count) if i not in done)
            seen = set()
            while at not in seen:
                seen.add(at)
                at = next(j for j in deps[at] if j not in done)
            raise self.e("dependency_cycle", at, "the event is part of a dependency cycle")
        times = [None] * count
        for i in order:
            when = events[i].when
            if isinstance(when, At):
                times[i] = when.ms
            elif isinstance(when, After):
                base = times[self.event_at[when.event]]
                times[i] = None if base is None else base + when.delay_ms
            if times[i] is not None and times[i] > MAX_TIME_MS:
                raise self.e("limit_exceeded", i, f"the time exceeds {MAX_TIME_MS}", "after")
        latest = None
        for i, event in enumerate(events):
            if times[i] is not None:
                if latest is not None and times[i] < latest:
                    raise self.e("time_order", i, "static times must not decrease down the file")
                latest = times[i]
            wanted = [self.event_at[n] for n in (event.depends_on or ())]
            if event.target is not None:
                wanted.append(self.event_at[event.target])
            for j in wanted:
                if times[i] is not None and times[j] is not None and times[j] >= times[i]:
                    raise self.e(
                        "time_order",
                        i,
                        f"the event is not later than {events[j].id!r}, which it depends on",
                    )

    # 7 disclosure
    def disclosure(self):
        disclosed = {f for e in self.p.events for f in (e.discloses or ())}
        for index, fact in enumerate(self.p.facts):
            if fact.id not in disclosed:
                raise self.t(
                    "fact_never_disclosed", f"facts[{index}].id", f"no event discloses {fact.id!r}"
                )

    # 8 checks
    def checks(self):
        for index, check in enumerate(self.p.checks):
            base = f"checks[{index}]"
            if check.kind not in model.CHECK_KINDS:
                raise self.t("bad_kind", f"{base}.kind", f"check kind {check.kind!r}")
            wanted = _CHECK_FIELDS[check.kind]
            for name in ("key", "fact", "probe"):
                value = getattr(check, name)
                if name in wanted and value is None:
                    raise self.t("bad_check", f"{base}.{name}", f"a {check.kind} check needs {name}")
                if name not in wanted and value is not None:
                    raise self.t("bad_check", f"{base}.{name}", f"a {check.kind} check has no {name}")
            for position, tag in enumerate(check.tags or ()):
                if tag != model.TAG_POLICY or tag in (check.tags or ())[:position]:
                    raise self.t(
                        "bad_check", f"{base}.tags[{position}]", f"tag {tag!r} is not allowed here"
                    )
            if check.key is not None and check.key not in self.fact_keys:
                raise self.t("unknown_fact_key", f"{base}.key", f"no fact has key {check.key!r}")
            if check.fact is not None:
                if check.fact not in self.fact:
                    raise self.t("unknown_fact", f"{base}.fact", f"{check.fact!r} is not declared")
                if check.kind == model.CHECK_NO_ECHO and self.fact[check.fact].kind != model.FACT_SECRET:
                    raise self.t("bad_check", f"{base}.fact", "a no_echo check names a secret")
            if check.probe is not None:
                if check.probe not in self.event_at:
                    raise self.t("unknown_event", f"{base}.probe", f"{check.probe!r} is not an event")
                probe = self.p.events[self.event_at[check.probe]]
                if probe.probe is not True or probe.kind not in _PROBING:
                    raise self.t(
                        "not_a_probe", f"{base}.probe", f"{check.probe!r} is not a probe post or op"
                    )

    # 9 pairing
    def allowed(self, who, fact):
        for entry in fact.audience:
            if entry == model.AUDIENCE_ALL or entry == who:
                return True
            if entry.startswith(_GROUP) and self.can_be_member(who, entry[len(_GROUP) :]):
                return True
        return False

    def pairing(self):
        answers = [c for c in self.p.checks if c.kind == model.CHECK_ANSWER]
        for index, check in enumerate(self.p.checks):
            path = f"checks[{index}]"
            if check.kind in (model.CHECK_WITHHOLD, model.CHECK_NO_LEAK):
                fact = self.fact[check.fact]
                if not any(
                    a.key == fact.key
                    and self.allowed(self.p.events[self.event_at[a.probe]].actor, fact)
                    for a in answers
                ):
                    raise self.t(
                        "missing_control",
                        path,
                        f"no answer check on key {fact.key!r} is asked by an actor allowed to know it",
                    )
            elif check.kind == model.CHECK_NO_ECHO:
                if not any(
                    all(f.kind != model.FACT_SECRET for f in self.p.facts if f.key == a.key)
                    for a in answers
                ):
                    raise self.t(
                        "missing_control", path, "no answer check on a key that has no secret fact"
                    )


# --- writing ---------------------------------------------------------------

_TOML_ESCAPES = {'"': '\\"', "\\": "\\\\", "\b": "\\b", "\t": "\\t", "\n": "\\n", "\f": "\\f", "\r": "\\r"}


def _toml_string(text: str) -> str:
    out = []
    for char in text:
        if char in _TOML_ESCAPES:
            out.append(_TOML_ESCAPES[char])
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            out.append(f"\\u{ord(char):04x}")
        else:
            out.append(char)
    return '"' + "".join(out) + '"'


def _toml_value(value) -> str:
    kind = type(value)
    if kind is str:
        return _toml_string(value)
    if kind is bool:
        return "true" if value else "false"
    if kind is int:
        return str(value)
    if kind is list:
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if kind is dict:
        if not value:
            return "{}"
        body = ", ".join(f"{_toml_string(k)} = {_toml_value(value[k])}" for k in sorted(value))
        return "{ " + body + " }"
    raise canon.CanonError("$", f"unsupported type {kind.__name__}")


def _toml_table(obj: dict, order: tuple) -> list:
    return [f"{name} = {_toml_value(obj[name])}" for name in order if name in obj]


def toml_text(pack: Pack) -> str:
    """The canonical ``pack.toml`` text of ``pack``."""
    obj = pack.to_obj()
    blocks = [_toml_table(obj, model.PACK_HEADER_FIELDS), ["[subject]", *_toml_table(obj["subject"], ("id",))]]
    if "provenance" in obj:
        blocks.append(["[provenance]", *_toml_table(obj["provenance"], _ORDER["provenance"])])
    for name in model.PACK_LISTS:
        for item in obj[name]:
            blocks.append([f"[[{name}]]", *_toml_table(item, _ORDER[name])])
    return "\n\n".join("\n".join(block) for block in blocks) + "\n"


def timeline_bytes(pack: Pack) -> bytes:
    """The canonical ``timeline.jsonl`` bytes: one canonical event per line."""
    return b"".join(canon.canon(event) + b"\n" for event in pack.timeline_objs())


def write(pack: Pack, path) -> None:
    """Write ``pack.toml`` and ``timeline.jsonl`` into directory ``path``.

    The pack is validated first, so a pack that ``load`` would reject is not
    written. Both files are UTF-8 without a byte order mark and end lines with
    ``\\n``; they are opened in binary mode so no platform changes that.
    """
    validate(pack)
    text = toml_text(pack).encode("utf-8")
    lines = [canon.canon(event) + b"\n" for event in pack.timeline_objs()]
    events = b"".join(lines)
    # The writer's spelling can be longer than the source (escapes), so check the
    # bytes against the loader's limits before any file is touched.
    if len(text) > MAX_TOML_BYTES:
        raise _err("limit_exceeded", TOML_FILE, f"{len(text)} bytes exceeds the limit of {MAX_TOML_BYTES}")
    if len(events) > MAX_TIMELINE_BYTES:
        raise _err(
            "limit_exceeded", TIMELINE_FILE, f"{len(events)} bytes exceeds the limit of {MAX_TIMELINE_BYTES}"
        )
    for number, line in enumerate(lines, 1):
        if len(line) - 1 > MAX_LINE_BYTES:
            raise _err(
                "limit_exceeded",
                TIMELINE_FILE,
                f"a line is longer than {MAX_LINE_BYTES} bytes",
                line=number,
            )
    root = Path(path)
    root.mkdir(parents=True, exist_ok=True)
    (root / TOML_FILE).write_bytes(text)
    (root / TIMELINE_FILE).write_bytes(events)
