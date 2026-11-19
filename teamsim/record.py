"""The run record and its replay (``docs/spec/engine-modules.md`` section 5).

``record.jsonl`` holds one canonical JSON object per line: the header, every log
entry in order, every verdict, and last the digest, which is ``canon.hash_of``
over the list of all earlier lines. Files are written in binary with ``\\n`` line
ends and UTF-8 without a byte-order mark, so a record is byte-identical on every
platform. Timings go to a separate ``timing.jsonl`` and never enter the digest.

- ``header(pack, subject, engine=...)`` builds the first line. The subject
  descriptor is ``{"builtin": name}`` or ``{"command": basename}`` and nothing
  else, so no argument, path or environment value reaches a record.
- ``build`` computes the digest; ``write`` and ``read`` convert to and from a file.
  ``read`` checks the whole shape and the digest and raises ``RecordError`` with a
  stable ``code`` and the 1-based ``line`` at fault.
- ``ReplaySession`` answers the engine from recorded observations in place of a
  subject. ``replay`` runs the engine with it, evaluates the checks again and
  returns a new ``RunResult``; the record is reproduced when the digests match.

Codes of ``RecordError``: ``empty``, ``bom``, ``carriage_return``, ``not_utf8``,
``blank_line``, ``missing_newline``, ``not_canonical``, ``header_not_first``,
``invalid_line``, ``entry_after_verdict``, ``verdict_after_digest``,
``after_digest``, ``missing_digest``, ``bad_digest``, ``digest_mismatch`` and
``pack_mismatch`` (replay against another pack).

Imports are the standard library and the core modules only. Nothing here reads a
clock or a random source. ``engine`` and ``checks`` are imported inside ``replay``.
"""

import re

from teamsim import canon
from teamsim.model import (
    CODE_REJECTED_ACTION,
    ENDS_SESSION,
    ENTRY_DELIVERY,
    ENTRY_DIGEST,
    ENTRY_HEADER,
    ENTRY_NOTE,
    ENTRY_OBSERVATION,
    ENTRY_VERDICT,
    MODE_SCRIPTED,
    NOTE_SHUTDOWN,
    NOTE_START,
    OBS_ACTION,
    OBS_DONE,
    OBS_ERROR,
    OBS_READY,
    OBS_STALLED,
    RECORD_FORMAT,
    REPLY_CLOSED,
    REPLY_DONE,
    REPLY_ENDED,
    REPLY_READY,
    Delivery,
    Fault,
    ModelError,
    Note,
    Observation,
    RecordHeader,
    Reply,
    RunResult,
    Verdict,
    entry_from_obj,
)
from teamsim.pack import pack_hash

__all__ = [
    "RecordError",
    "ReplaySession",
    "build",
    "digest",
    "header",
    "read",
    "replay",
    "write",
    "write_timing",
]

_LOG_TYPES = (ENTRY_DELIVERY, ENTRY_OBSERVATION, ENTRY_NOTE)
_HEX64 = re.compile(r"[0-9a-f]{64}")
_NOT_A_NAME = re.compile(r"[\\/\s\x00-\x1f\x7f]")


class RecordError(ValueError):
    """A record that cannot be trusted. ``code`` is stable; ``line`` counts from 1
    (0 when no line is at fault)."""

    def __init__(self, code: str, line: int, message: str) -> None:
        text = f"line {line}: {message} [{code}]" if line else f"{message} [{code}]"
        super().__init__(text)
        self.code = code
        self.line = line
        self.message = message


# --- building --------------------------------------------------------------


def _plain_name(value: object, what: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"subject {what} must be a non-empty string")
    if value in (".", "..") or _NOT_A_NAME.search(value):
        raise ValueError(f"subject {what} must be a bare name: no separators, spaces or arguments")
    return value


def _subject(subject: object) -> dict:
    message = 'subject must be {"builtin": name} or {"command": basename}'
    if type(subject) is not dict or len(subject) != 1:
        raise ValueError(message)
    ((key, value),) = subject.items()
    if key not in ("builtin", "command"):
        raise ValueError(message)
    return {key: _plain_name(value, key)}


def header(pack, subject: dict, *, engine: str) -> RecordHeader:
    """The record header for a run of ``pack`` by ``subject``."""
    if type(engine) is not str or not engine:
        raise ValueError("engine must be a non-empty version string")
    return RecordHeader(
        format=RECORD_FORMAT,
        engine=engine,
        pack_id=pack.header.id,
        pack_hash=pack_hash(pack),
        seed=pack.header.seed,
        subject=_subject(subject),
        mode=MODE_SCRIPTED,
        limits=tuple(pack.header.limits),
    )


def digest(lines: list) -> str:
    """``canon.hash_of`` over every line before the digest line."""
    return canon.hash_of(list(lines))


def build(header: RecordHeader, entries, verdicts) -> RunResult:
    """A ``RunResult`` with its digest computed."""
    entries = tuple(entries)
    verdicts = tuple(verdicts)
    lines = [header.to_obj()]
    lines.extend(entry.to_obj() for entry in entries)
    lines.extend(verdict.to_obj() for verdict in verdicts)
    return RunResult(header=header, entries=entries, verdicts=verdicts, digest=digest(lines))


# --- files -----------------------------------------------------------------


def _encode(lines) -> bytes:
    return b"".join(canon.canon(line) + b"\n" for line in lines)


def write(result: RunResult, path) -> None:
    """Write ``result`` as a record file. Raises ``ValueError`` when its digest
    is not the digest of its own lines."""
    lines = result.lines()
    if lines[-1]["digest"] != digest(lines[:-1]):
        raise ValueError("the result's digest does not match its lines")
    data = _encode(lines)
    with open(path, "wb") as handle:
        handle.write(data)


def write_timing(rows: list, path) -> None:
    """Write wall-clock rows, one canonical object per line. Not part of any digest."""
    data = _encode(rows)
    with open(path, "wb") as handle:
        handle.write(data)


def read(path) -> RunResult:
    """Read a record file and verify it; raise ``RecordError`` on any fault."""
    with open(path, "rb") as handle:
        data = handle.read()
    if not data:
        raise RecordError("empty", 0, "the record is empty")
    if data.startswith(b"\xef\xbb\xbf"):
        raise RecordError("bom", 1, "a byte-order mark is not allowed")
    parts = data.split(b"\n")
    if parts[-1] != b"":
        raise RecordError("missing_newline", len(parts), "the last line has no line end")
    parts.pop()
    head = None
    entries: list = []
    verdicts: list = []
    objs: list = []
    found = None
    stage = "header"  # then "entries", "verdicts", "done"
    for number, raw in enumerate(parts, 1):
        if b"\r" in raw:
            raise RecordError("carriage_return", number, "lines end with a line feed only")
        if not raw:
            raise RecordError("blank_line", number, "a blank line")
        try:
            obj = canon.parse(raw)
        except canon.CanonError as error:
            code = "not_utf8" if "not UTF-8" in error.reason else "not_canonical"
            raise RecordError(code, number, str(error)) from None
        if canon.canon(obj) != raw:
            raise RecordError("not_canonical", number, "the line is not in canonical form")
        kind = obj.get("type") if type(obj) is dict else None
        if stage == "done":
            if kind == ENTRY_VERDICT:
                raise RecordError("verdict_after_digest", number, "a verdict follows the digest")
            raise RecordError("after_digest", number, "a line follows the digest")
        if number == 1:
            if kind != ENTRY_HEADER:
                raise RecordError("header_not_first", number, "the first line must be the header")
            try:
                head = RecordHeader.from_obj(obj)
            except ModelError as error:
                raise RecordError("invalid_line", number, str(error)) from None
            objs.append(obj)
            stage = "entries"
            continue
        if kind == ENTRY_HEADER:
            raise RecordError("header_not_first", number, "the header must be the first line")
        if kind == ENTRY_DIGEST:
            if set(obj) != {"type", "digest"} or type(obj["digest"]) is not str:
                raise RecordError("bad_digest", number, "the digest line is malformed")
            if not _HEX64.fullmatch(obj["digest"]):
                raise RecordError("bad_digest", number, "the digest is not 64 lower-case hex digits")
            if obj["digest"] != digest(objs):
                raise RecordError(
                    "digest_mismatch", number, "the digest does not match the lines before it"
                )
            stage = "done"
            found = obj["digest"]
            continue
        if kind == ENTRY_VERDICT:
            try:
                verdicts.append(Verdict.from_obj(obj))
            except ModelError as error:
                raise RecordError("invalid_line", number, str(error)) from None
            stage = "verdicts"
        elif kind in _LOG_TYPES:
            if stage == "verdicts":
                raise RecordError("entry_after_verdict", number, "a log entry follows a verdict")
            try:
                entries.append(entry_from_obj(obj))
            except ModelError as error:
                raise RecordError("invalid_line", number, str(error)) from None
        else:
            raise RecordError("invalid_line", number, f"line type {kind!r} is not allowed here")
        objs.append(obj)
    if stage != "done":
        raise RecordError("missing_digest", len(parts), "the record does not end with a digest")
    return RunResult(header=head, entries=tuple(entries), verdicts=tuple(verdicts), digest=found)


# --- replay ----------------------------------------------------------------


def _items(observations) -> tuple:
    """Turn recorded observations into reply items, in order."""
    items = []
    for obs in observations:
        if obs.kind == OBS_ACTION and obs.action is not None:
            items.append(obs.action)
        elif obs.kind == OBS_ERROR and obs.code == CODE_REJECTED_ACTION and obs.action is not None:
            items.append(obs.action)
        elif obs.kind in (OBS_ERROR, OBS_STALLED) and obs.code is not None:
            items.append(Fault(obs.code, obs.detail))
    return tuple(items)


def _reply(observations, call: str) -> Reply:
    items = _items(observations)
    if call == "stop":
        return Reply(REPLY_CLOSED, items=items)
    for obs in observations:
        if call == "start" and obs.kind == OBS_READY:
            return Reply(REPLY_READY, items=items, name=obs.name, version=obs.version)
        if call == "exchange" and obs.kind == OBS_DONE:
            return Reply(REPLY_DONE, items=items, wake_at_ms=obs.wake_at_ms)
    if items and type(items[-1]) is Fault and items[-1].code in ENDS_SESSION:
        return Reply(REPLY_ENDED, items=items)
    return Reply(REPLY_READY if call == "start" else REPLY_DONE, items=items)


class ReplaySession:
    """A ``Session`` that answers from a recorded log instead of a subject.

    Observations are grouped by the message they answered (section 5): those after
    ``Note(start)`` answer ``start``; those after a ``Delivery`` with a ``seq``
    answer that ``exchange``; those after ``Note(shutdown)`` answer ``stop``. A
    message with no recorded observations gets the plain reply (``ready`` or
    ``done`` with no items, ``closed``).
    """

    def __init__(self, entries) -> None:
        self._start: list = []
        self._stop: list = []
        self._exchange: dict = {}
        target = None
        for entry in entries:
            if type(entry) is Note and entry.code == NOTE_START:
                target = self._start
            elif type(entry) is Note and entry.code == NOTE_SHUTDOWN:
                target = self._stop
            elif type(entry) is Delivery and entry.seq is not None:
                target = self._exchange.setdefault(entry.seq, [])
            elif type(entry) is Observation and target is not None:
                target.append(entry)

    def start(self, hello: dict) -> Reply:
        return _reply(self._start, "start")

    def exchange(self, event: dict) -> Reply:
        return _reply(self._exchange.get(event.get("seq"), ()), "exchange")

    def stop(self, reason: str, t_ms: int) -> Reply:
        return _reply(self._stop, "stop")


def replay(record_path, pack, *, run=None, evaluate=None) -> RunResult:
    """Run the engine against the recorded observations and return the new result.

    ``run`` and ``evaluate`` default to ``teamsim.engine.run`` and
    ``teamsim.checks.evaluate``. The header is the recorded one, so the record is
    reproduced exactly when the returned digest equals the recorded digest.
    Raises ``RecordError`` for a bad record, or one made from a different pack.
    """
    if run is None:
        from teamsim.engine import run
    if evaluate is None:
        from teamsim.checks import evaluate
    recorded = read(record_path)
    if recorded.header.pack_hash != pack_hash(pack):
        raise RecordError("pack_mismatch", 1, "the record was made from a different pack")
    entries = run(pack, ReplaySession(recorded.entries))
    return build(recorded.header, entries, evaluate(pack, entries))
