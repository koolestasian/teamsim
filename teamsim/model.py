"""Shared types and names for a pack and its timeline (pack format 1).

Types only. Nothing here reads a file, and nothing checks one object against
another: that an id exists, that times are ordered or that a check names a real
probe is the loader's work. ``from_obj`` checks one object on its own: that it
is a canonical value (see ``teamsim.canon``), that the required fields are
present, that no unknown field is, that each field has the right type and that
a kind is one of the allowed names.

Every type converts to and from the plain canonical object with ``to_obj`` and
``from_obj``. A hash is always taken over the plain object, never over a class.
The conversion loses nothing: ``T.from_obj(obj).to_obj() == obj`` for every
object ``from_obj`` accepts. To keep that true, an optional field that is absent
is ``None``, and a field that is present is kept as written, so an empty list
stays an empty list. Lists become tuples on the way in and lists again on the
way out.

The dataclasses are frozen. The free-form values some of them carry (an actor's
``traits``, the ``args`` of an operation, a provenance ``transformation``) are
plain canonical values, copied on the way in and on the way out; treat them as
read-only. They take no part in hashing an instance.
"""

from dataclasses import dataclass, field
from types import MappingProxyType

from . import canon

__all__ = [
    "AUDIENCE_ALL",
    "AUDIENCE_GROUP_PREFIX",
    "After",
    "At",
    "Actor",
    "CHECK_ANSWER",
    "CHECK_CATCH_UP",
    "CHECK_HARNESS",
    "CHECK_KINDS",
    "CHECK_NO_ECHO",
    "CHECK_NO_LEAK",
    "CHECK_WITHHOLD",
    "Check",
    "EVENT_AWAY",
    "EVENT_BACK",
    "EVENT_DELETE",
    "EVENT_EDIT",
    "EVENT_JOIN",
    "EVENT_KINDS",
    "EVENT_LEAVE",
    "EVENT_OP",
    "EVENT_POST",
    "EVENT_REACT",
    "EVENT_SUBJECT_DOWN",
    "EVENT_SUBJECT_JOIN",
    "EVENT_SUBJECT_LEAVE",
    "EVENT_SUBJECT_UP",
    "Event",
    "FACT_ASSIGNMENT",
    "FACT_CLAIM",
    "FACT_DATE",
    "FACT_DECISION",
    "FACT_ITEM",
    "FACT_KINDS",
    "FACT_PREFERENCE",
    "FACT_SECRET",
    "FAIL_REASONS",
    "FORMAT",
    "Fact",
    "ModelError",
    "On",
    "PACK_HEADER_FIELDS",
    "PACK_LISTS",
    "PACK_TABLES",
    "PackHeader",
    "Provenance",
    "REASONS",
    "REASON_ECHOED",
    "REASON_LEAKED",
    "REASON_MISSED",
    "REASON_MISSING",
    "REASON_NOT_DELIVERED",
    "REASON_NO_RESPONSE",
    "REASON_OUT_OF_ORDER",
    "REASON_STALE",
    "REASON_UNAUTHORISED",
    "SURFACE_CHANNEL",
    "SURFACE_DIRECT",
    "SURFACE_KINDS",
    "Subject",
    "SubjectMentions",
    "SubjectPost",
    "Surface",
    "TAG_POLICY",
    "TIME_FORMS",
    "TRIGGER_KINDS",
    "TRIGGER_SUBJECT_MENTIONS",
    "TRIGGER_SUBJECT_POST",
    "Trigger",
    "VERDICTS",
    "VERDICT_FAIL",
    "VERDICT_HARNESS_ERROR",
    "VERDICT_NOT_APPLICABLE",
    "VERDICT_PASS",
    "When",
    "trigger_from_obj",
    "when_from_obj",
]

# --- names -----------------------------------------------------------------

FORMAT = 1

# Top-level layout of ``pack.toml`` read as one object: the header fields, then
# one table each for the subject and the provenance, then four arrays of tables.
PACK_HEADER_FIELDS = ("format", "id", "title", "purpose", "seed", "limits")
PACK_TABLES = ("subject", "provenance")
PACK_LISTS = ("actors", "surfaces", "facts", "checks")

SURFACE_CHANNEL = "channel"
SURFACE_DIRECT = "direct"
SURFACE_KINDS = (SURFACE_CHANNEL, SURFACE_DIRECT)

FACT_DECISION = "decision"
FACT_ASSIGNMENT = "assignment"
FACT_DATE = "date"
FACT_PREFERENCE = "preference"
FACT_SECRET = "secret"
FACT_CLAIM = "claim"
FACT_ITEM = "item"
FACT_KINDS = (
    FACT_DECISION,
    FACT_ASSIGNMENT,
    FACT_DATE,
    FACT_PREFERENCE,
    FACT_SECRET,
    FACT_CLAIM,
    FACT_ITEM,
)

# In a fact's audience: everyone, or the members of a surface ("group:<surface id>").
AUDIENCE_ALL = "*"
AUDIENCE_GROUP_PREFIX = "group:"

EVENT_POST = "post"
EVENT_EDIT = "edit"
EVENT_DELETE = "delete"
EVENT_REACT = "react"
EVENT_JOIN = "join"
EVENT_LEAVE = "leave"
EVENT_AWAY = "away"
EVENT_BACK = "back"
EVENT_OP = "op"
EVENT_SUBJECT_JOIN = "subject_join"
EVENT_SUBJECT_LEAVE = "subject_leave"
EVENT_SUBJECT_DOWN = "subject_down"
EVENT_SUBJECT_UP = "subject_up"
EVENT_KINDS = (
    EVENT_POST,
    EVENT_EDIT,
    EVENT_DELETE,
    EVENT_REACT,
    EVENT_JOIN,
    EVENT_LEAVE,
    EVENT_AWAY,
    EVENT_BACK,
    EVENT_OP,
    EVENT_SUBJECT_JOIN,
    EVENT_SUBJECT_LEAVE,
    EVENT_SUBJECT_DOWN,
    EVENT_SUBJECT_UP,
)

# The field that says when an event happens; an event has exactly one of them.
TIME_FORMS = ("at", "after", "on")

TRIGGER_SUBJECT_POST = "subject_post"
TRIGGER_SUBJECT_MENTIONS = "subject_mentions"
TRIGGER_KINDS = (TRIGGER_SUBJECT_POST, TRIGGER_SUBJECT_MENTIONS)

CHECK_HARNESS = "harness"
CHECK_ANSWER = "answer"
CHECK_WITHHOLD = "withhold"
CHECK_NO_LEAK = "no_leak"
CHECK_NO_ECHO = "no_echo"
CHECK_CATCH_UP = "catch_up"
CHECK_KINDS = (
    CHECK_HARNESS,
    CHECK_ANSWER,
    CHECK_WITHHOLD,
    CHECK_NO_LEAK,
    CHECK_NO_ECHO,
    CHECK_CATCH_UP,
)

# A check carrying this tag is reported separately from defects.
TAG_POLICY = "policy"

VERDICT_PASS = "pass"
VERDICT_FAIL = "fail"
VERDICT_NOT_APPLICABLE = "not_applicable"
VERDICT_HARNESS_ERROR = "harness_error"
VERDICTS = (
    VERDICT_PASS,
    VERDICT_FAIL,
    VERDICT_NOT_APPLICABLE,
    VERDICT_HARNESS_ERROR,
)

REASON_NOT_DELIVERED = "not_delivered"
REASON_OUT_OF_ORDER = "out_of_order"
REASON_NO_RESPONSE = "no_response"
REASON_STALE = "stale"
REASON_UNAUTHORISED = "unauthorised"
REASON_MISSING = "missing"
REASON_LEAKED = "leaked"
REASON_ECHOED = "echoed"
REASON_MISSED = "missed"
REASONS = (
    REASON_NOT_DELIVERED,
    REASON_OUT_OF_ORDER,
    REASON_NO_RESPONSE,
    REASON_STALE,
    REASON_UNAUTHORISED,
    REASON_MISSING,
    REASON_LEAKED,
    REASON_ECHOED,
    REASON_MISSED,
)

# The reason codes a failing check of each kind may give.
FAIL_REASONS = MappingProxyType(
    {
        CHECK_HARNESS: (REASON_NOT_DELIVERED, REASON_OUT_OF_ORDER),
        CHECK_ANSWER: (
            REASON_NO_RESPONSE,
            REASON_STALE,
            REASON_UNAUTHORISED,
            REASON_MISSING,
        ),
        CHECK_WITHHOLD: (REASON_LEAKED,),
        CHECK_NO_LEAK: (REASON_LEAKED,),
        CHECK_NO_ECHO: (REASON_ECHOED,),
        CHECK_CATCH_UP: (REASON_NO_RESPONSE, REASON_MISSED),
    }
)


# --- reading plain objects -------------------------------------------------


class ModelError(ValueError):
    """A plain object that does not have the shape of the type being read."""


def _open(obj: object, what: str, required: tuple, optional: tuple = ()) -> dict:
    """Check that ``obj`` is a canonical object with exactly the allowed fields."""
    if type(obj) is not dict:
        raise ModelError(f"{what}: expected an object, not {type(obj).__name__}")
    canon.check(obj)
    for name in obj:
        if name not in required and name not in optional:
            raise ModelError(f"{what}: unknown field {name!r}")
    for name in required:
        if name not in obj:
            raise ModelError(f"{what}: missing field {name!r}")
    return obj


def _text(obj: dict, name: str, what: str) -> str:
    value = obj[name]
    if type(value) is not str:
        raise ModelError(f"{what}: field {name!r} must be a string")
    return value


def _whole(obj: dict, name: str, what: str) -> int:
    value = obj[name]
    if type(value) is not int:
        raise ModelError(f"{what}: field {name!r} must be an integer")
    return value


def _flag(obj: dict, name: str, what: str) -> bool:
    value = obj[name]
    if type(value) is not bool:
        raise ModelError(f"{what}: field {name!r} must be true or false")
    return value


def _texts(obj: dict, name: str, what: str) -> tuple[str, ...]:
    value = obj[name]
    if type(value) is not list or any(type(item) is not str for item in value):
        raise ModelError(f"{what}: field {name!r} must be an array of strings")
    return tuple(value)


def _table(obj: dict, name: str, what: str) -> dict:
    value = obj[name]
    if type(value) is not dict:
        raise ModelError(f"{what}: field {name!r} must be an object")
    return _copy(value)


def _any(obj: dict, name: str, what: str) -> object:
    return _copy(obj[name])


def _kind(obj: dict, what: str, allowed: tuple) -> str:
    value = _text(obj, "kind", what)
    if value not in allowed:
        raise ModelError(
            f"{what}: kind {value!r} is not one of {', '.join(allowed)}"
        )
    return value


def _maybe(read, obj: dict, name: str, what: str):
    return read(obj, name, what) if name in obj else None


def _copy(value: object) -> object:
    """Copy a canonical value, so no instance shares a list or dict with a caller."""
    if type(value) is list:
        return [_copy(item) for item in value]
    if type(value) is dict:
        return {key: _copy(item) for key, item in value.items()}
    return value


def _put(obj: dict, name: str, value: object) -> None:
    """Write an optional field: nothing when absent, a list for a tuple."""
    if value is None:
        return
    obj[name] = list(value) if type(value) is tuple else _copy(value)


# --- the pack --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PackHeader:
    """The top-level fields of ``pack.toml``.

    ``format`` is the pack format version (``FORMAT``). ``seed`` keys every
    draw. ``limits`` are the validity limits the pack states about itself.
    """

    format: int
    id: str
    title: str
    purpose: str
    seed: str
    limits: tuple[str, ...]

    def to_obj(self) -> dict:
        return {
            "format": self.format,
            "id": self.id,
            "title": self.title,
            "purpose": self.purpose,
            "seed": self.seed,
            "limits": list(self.limits),
        }

    @classmethod
    def from_obj(cls, obj: object) -> "PackHeader":
        what = "pack header"
        obj = _open(obj, what, PACK_HEADER_FIELDS)
        return cls(
            format=_whole(obj, "format", what),
            id=_text(obj, "id", what),
            title=_text(obj, "title", what),
            purpose=_text(obj, "purpose", what),
            seed=_text(obj, "seed", what),
            limits=_texts(obj, "limits", what),
        )


@dataclass(frozen=True, slots=True)
class Subject:
    """The software under test, as the pack names it."""

    id: str

    def to_obj(self) -> dict:
        return {"id": self.id}

    @classmethod
    def from_obj(cls, obj: object) -> "Subject":
        what = "subject"
        obj = _open(obj, what, ("id",))
        return cls(id=_text(obj, "id", what))


@dataclass(frozen=True, slots=True)
class Actor:
    """A synthetic user. ``traits`` records how the actor was generated and is
    never read at run time."""

    id: str
    role: str | None = None
    display: str | None = None
    traits: dict | None = field(default=None, hash=False)

    def to_obj(self) -> dict:
        obj: dict = {"id": self.id}
        _put(obj, "role", self.role)
        _put(obj, "display", self.display)
        _put(obj, "traits", self.traits)
        return obj

    @classmethod
    def from_obj(cls, obj: object) -> "Actor":
        what = "actor"
        obj = _open(obj, what, ("id",), ("role", "display", "traits"))
        return cls(
            id=_text(obj, "id", what),
            role=_maybe(_text, obj, "role", what),
            display=_maybe(_text, obj, "display", what),
            traits=_maybe(_table, obj, "traits", what),
        )


@dataclass(frozen=True, slots=True)
class Surface:
    """A place an actor can act. ``members`` is the membership at time 0 and
    may include the subject's id."""

    id: str
    kind: str
    members: tuple[str, ...]

    def to_obj(self) -> dict:
        return {"id": self.id, "kind": self.kind, "members": list(self.members)}

    @classmethod
    def from_obj(cls, obj: object) -> "Surface":
        what = "surface"
        obj = _open(obj, what, ("id", "kind", "members"))
        return cls(
            id=_text(obj, "id", what),
            kind=_kind(obj, what, SURFACE_KINDS),
            members=_texts(obj, "members", what),
        )


@dataclass(frozen=True, slots=True)
class Fact:
    """Something the pack plants and knows.

    ``key`` names what the fact is about; facts with one key are successive
    values of it, linked by ``supersedes`` (a fact id). ``forms`` are the
    spellings a check accepts. ``authority`` lists who may set the key.
    ``audience`` lists who may know the value: actor ids, ``AUDIENCE_ALL``, or
    ``AUDIENCE_GROUP_PREFIX`` followed by a surface id.
    """

    id: str
    key: str
    kind: str
    value: str
    authority: tuple[str, ...]
    audience: tuple[str, ...]
    forms: tuple[str, ...] | None = None
    supersedes: str | None = None

    def to_obj(self) -> dict:
        obj: dict = {
            "id": self.id,
            "key": self.key,
            "kind": self.kind,
            "value": self.value,
            "authority": list(self.authority),
            "audience": list(self.audience),
        }
        _put(obj, "forms", self.forms)
        _put(obj, "supersedes", self.supersedes)
        return obj

    @classmethod
    def from_obj(cls, obj: object) -> "Fact":
        what = "fact"
        obj = _open(
            obj,
            what,
            ("id", "key", "kind", "value", "authority", "audience"),
            ("forms", "supersedes"),
        )
        return cls(
            id=_text(obj, "id", what),
            key=_text(obj, "key", what),
            kind=_kind(obj, what, FACT_KINDS),
            value=_text(obj, "value", what),
            authority=_texts(obj, "authority", what),
            audience=_texts(obj, "audience", what),
            forms=_maybe(_texts, obj, "forms", what),
            supersedes=_maybe(_text, obj, "supersedes", what),
        )


@dataclass(frozen=True, slots=True)
class Check:
    """One scored expectation.

    Which of ``key`` (a fact key), ``fact`` (a fact id) and ``probe`` (an event
    id) a check needs depends on its kind; the loader decides. ``tags`` may hold
    ``TAG_POLICY``.
    """

    id: str
    kind: str
    key: str | None = None
    fact: str | None = None
    probe: str | None = None
    tags: tuple[str, ...] | None = None

    def to_obj(self) -> dict:
        obj: dict = {"id": self.id, "kind": self.kind}
        _put(obj, "key", self.key)
        _put(obj, "fact", self.fact)
        _put(obj, "probe", self.probe)
        _put(obj, "tags", self.tags)
        return obj

    @classmethod
    def from_obj(cls, obj: object) -> "Check":
        what = "check"
        obj = _open(obj, what, ("id", "kind"), ("key", "fact", "probe", "tags"))
        return cls(
            id=_text(obj, "id", what),
            kind=_kind(obj, what, CHECK_KINDS),
            key=_maybe(_text, obj, "key", what),
            fact=_maybe(_text, obj, "fact", what),
            probe=_maybe(_text, obj, "probe", what),
            tags=_maybe(_texts, obj, "tags", what),
        )


@dataclass(frozen=True, slots=True)
class Provenance:
    """How a generated or transformed pack came about. Every field is optional."""

    generator_version: str | None = None
    population_hash: str | None = None
    parent_pack_hash: str | None = None
    transformation: object = field(default=None, hash=False)

    def to_obj(self) -> dict:
        obj: dict = {}
        _put(obj, "generator_version", self.generator_version)
        _put(obj, "population_hash", self.population_hash)
        _put(obj, "parent_pack_hash", self.parent_pack_hash)
        _put(obj, "transformation", self.transformation)
        return obj

    @classmethod
    def from_obj(cls, obj: object) -> "Provenance":
        what = "provenance"
        obj = _open(
            obj,
            what,
            (),
            (
                "generator_version",
                "population_hash",
                "parent_pack_hash",
                "transformation",
            ),
        )
        return cls(
            generator_version=_maybe(_text, obj, "generator_version", what),
            population_hash=_maybe(_text, obj, "population_hash", what),
            parent_pack_hash=_maybe(_text, obj, "parent_pack_hash", what),
            transformation=_maybe(_any, obj, "transformation", what),
        )


# --- the timeline ----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class At:
    """A fixed time: ``{"at": ms}``, virtual milliseconds from the start."""

    ms: int

    def to_obj(self) -> dict:
        return {"at": self.ms}

    @classmethod
    def from_obj(cls, obj: object) -> "At":
        what = "time form 'at'"
        obj = _open(obj, what, ("at",))
        return cls(ms=_whole(obj, "at", what))


@dataclass(frozen=True, slots=True)
class After:
    """A time relative to another event: ``{"after": {"event": id, "delay_ms": n}}``."""

    event: str
    delay_ms: int

    def to_obj(self) -> dict:
        return {"after": {"event": self.event, "delay_ms": self.delay_ms}}

    @classmethod
    def from_obj(cls, obj: object) -> "After":
        what = "time form 'after'"
        obj = _open(obj, what, ("after",))
        inner = _open(obj["after"], what, ("event", "delay_ms"))
        return cls(
            event=_text(inner, "event", what),
            delay_ms=_whole(inner, "delay_ms", what),
        )


@dataclass(frozen=True, slots=True)
class SubjectPost:
    """Trigger: the subject posted on ``surface`` within ``within_ms``."""

    surface: str
    within_ms: int
    delay_ms: int | None = None

    def to_obj(self) -> dict:
        obj: dict = {
            "kind": TRIGGER_SUBJECT_POST,
            "surface": self.surface,
            "within_ms": self.within_ms,
        }
        _put(obj, "delay_ms", self.delay_ms)
        return obj

    @classmethod
    def from_obj(cls, obj: object) -> "SubjectPost":
        what = f"trigger {TRIGGER_SUBJECT_POST!r}"
        obj = _open(obj, what, ("kind", "surface", "within_ms"), ("delay_ms",))
        _kind(obj, what, (TRIGGER_SUBJECT_POST,))
        return cls(
            surface=_text(obj, "surface", what),
            within_ms=_whole(obj, "within_ms", what),
            delay_ms=_maybe(_whole, obj, "delay_ms", what),
        )


@dataclass(frozen=True, slots=True)
class SubjectMentions:
    """Trigger: the subject mentioned ``actor`` within ``within_ms``."""

    actor: str
    within_ms: int
    delay_ms: int | None = None

    def to_obj(self) -> dict:
        obj: dict = {
            "kind": TRIGGER_SUBJECT_MENTIONS,
            "actor": self.actor,
            "within_ms": self.within_ms,
        }
        _put(obj, "delay_ms", self.delay_ms)
        return obj

    @classmethod
    def from_obj(cls, obj: object) -> "SubjectMentions":
        what = f"trigger {TRIGGER_SUBJECT_MENTIONS!r}"
        obj = _open(obj, what, ("kind", "actor", "within_ms"), ("delay_ms",))
        _kind(obj, what, (TRIGGER_SUBJECT_MENTIONS,))
        return cls(
            actor=_text(obj, "actor", what),
            within_ms=_whole(obj, "within_ms", what),
            delay_ms=_maybe(_whole, obj, "delay_ms", what),
        )


Trigger = SubjectPost | SubjectMentions


def trigger_from_obj(obj: object) -> Trigger:
    """Read a trigger object, choosing the type by its ``kind``."""
    what = "trigger"
    if type(obj) is not dict:
        raise ModelError(f"{what}: expected an object, not {type(obj).__name__}")
    if "kind" not in obj:
        raise ModelError(f"{what}: missing field 'kind'")
    kind = obj["kind"]
    if kind == TRIGGER_SUBJECT_POST:
        return SubjectPost.from_obj(obj)
    if kind == TRIGGER_SUBJECT_MENTIONS:
        return SubjectMentions.from_obj(obj)
    raise ModelError(
        f"{what}: kind {kind!r} is not one of {', '.join(TRIGGER_KINDS)}"
    )


@dataclass(frozen=True, slots=True)
class On:
    """A triggered time: ``{"on": trigger}``. The event fires at most once, at
    the observed time plus the trigger's ``delay_ms``."""

    trigger: Trigger

    def to_obj(self) -> dict:
        return {"on": self.trigger.to_obj()}

    @classmethod
    def from_obj(cls, obj: object) -> "On":
        obj = _open(obj, "time form 'on'", ("on",))
        return cls(trigger=trigger_from_obj(obj["on"]))


When = At | After | On

_TIME_TYPES = MappingProxyType({"at": At, "after": After, "on": On})


def when_from_obj(obj: object) -> When:
    """Read a one-field time object, choosing the type by the field's name.

    The object is ``{"at": ...}``, ``{"after": ...}`` or ``{"on": ...}``.
    """
    what = "time form"
    if type(obj) is not dict or len(obj) != 1:
        raise ModelError(
            f"{what}: expected an object with one of {', '.join(TIME_FORMS)}"
        )
    (name,) = obj
    if name not in _TIME_TYPES:
        raise ModelError(f"{what}: unknown field {name!r}")
    return _TIME_TYPES[name].from_obj(obj)


_EVENT_REQUIRED = ("id", "actor", "surface", "kind")
_EVENT_OPTIONAL = (
    "text",
    "target",
    "emoji",
    "op",
    "args",
    "depends_on",
    "discloses",
    "probe",
)


@dataclass(frozen=True, slots=True)
class Event:
    """One line of ``timeline.jsonl``.

    ``when`` is the event's one time form. ``text``, ``target`` (an event id),
    ``emoji``, ``op`` and ``args`` are the payload; which of them a kind needs
    is for the loader to decide. ``depends_on`` lists event ids, ``discloses``
    fact ids. ``probe`` marks an event whose response a check reads.
    """

    id: str
    when: When
    actor: str
    surface: str
    kind: str
    text: str | None = None
    target: str | None = None
    emoji: str | None = None
    op: str | None = None
    args: dict | None = field(default=None, hash=False)
    depends_on: tuple[str, ...] | None = None
    discloses: tuple[str, ...] | None = None
    probe: bool | None = None

    def to_obj(self) -> dict:
        obj: dict = {"id": self.id}
        obj.update(self.when.to_obj())
        obj["actor"] = self.actor
        obj["surface"] = self.surface
        obj["kind"] = self.kind
        for name in _EVENT_OPTIONAL:
            _put(obj, name, getattr(self, name))
        return obj

    @classmethod
    def from_obj(cls, obj: object) -> "Event":
        what = "event"
        obj = _open(obj, what, _EVENT_REQUIRED, TIME_FORMS + _EVENT_OPTIONAL)
        present = [name for name in TIME_FORMS if name in obj]
        if len(present) != 1:
            raise ModelError(
                f"{what}: needs exactly one of {', '.join(TIME_FORMS)}, "
                f"found {len(present)}"
            )
        return cls(
            id=_text(obj, "id", what),
            when=when_from_obj({present[0]: obj[present[0]]}),
            actor=_text(obj, "actor", what),
            surface=_text(obj, "surface", what),
            kind=_kind(obj, what, EVENT_KINDS),
            text=_maybe(_text, obj, "text", what),
            target=_maybe(_text, obj, "target", what),
            emoji=_maybe(_text, obj, "emoji", what),
            op=_maybe(_text, obj, "op", what),
            args=_maybe(_table, obj, "args", what),
            depends_on=_maybe(_texts, obj, "depends_on", what),
            discloses=_maybe(_texts, obj, "discloses", what),
            probe=_maybe(_flag, obj, "probe", what),
        )
