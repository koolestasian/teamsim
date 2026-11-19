"""The engine: drives one session through a pack and returns the log
(``docs/spec/engine-modules.md`` section 2).

``run(pack, session)`` is the only code that talks to the session. Everything
else is a pure step function over an explicit state, so a test can drive it
without a session:

- ``make_plan(pack, wall_timeout_ms)`` builds the read-only ``Plan`` (indexes
  of the pack).
- ``begin(plan)`` returns the first ``State`` and the first ``Send`` (``hello``).
- ``step(plan, state, reply)`` consumes the ``Reply`` to the outstanding
  message (``None`` when nothing is outstanding), advances virtual time as far
  as it can, and returns the new ``State`` and the next ``Send``, or ``None``
  when the run is over. The state passed in is never changed.
- ``entries(state)`` returns the log so far.

A ``Send`` names the session call (``start``, ``exchange`` or ``stop``) and the
protocol message for it. Large parts of a ``State`` are persistent maps that
share structure between steps, so a step costs time in what it changes and not
in the size of the run.

Choices where the contract is silent (each the stricter reading):

- An event whose dependency (``depends_on``, ``after`` anchor, ``target``) has
  not happened when it falls due never happens; it is not postponed.
- A trigger fires only when every dependency, ``target`` included, has
  happened; the window opens at the last ``depends_on`` time.
- Pending ticks are a set of times: each requested time gets one tick, requests
  for the same time merge, and a later request does not cancel an earlier one.
- A ``wake_at_ms`` that is not later than the message time is recorded and
  ignored, and leaves the pending ticks in place (the transport already ends a
  session whose subject sends one, as ``invalid_message``).
- Ticks pending when the session ends early (a fault or a stalled subject) are
  dropped without a note; at the normal end of the run each is dropped with a
  ``tick_dropped`` note.
- The detail of a ``rejected_action`` is ``surface`` or ``reply_to``, the
  field that failed (the surface is checked first).
- ``subject_down`` and ``subject_up`` reach a live subject whatever surface
  they name; ``subject_leave`` reaches it only if it was a member.
- A reply whose ending does not fit the message raises ``ValueError``.

Imports are the standard library and the core modules only. Nothing here reads
a clock, a file, the environment or a random source.
"""

from bisect import insort
from dataclasses import dataclass

from teamsim import match
from teamsim.model import (
    ACTION_POST,
    After,
    At,
    CODE_REJECTED_ACTION,
    CODE_TIMEOUT,
    Action,
    Delivery,
    EVENT_AWAY,
    EVENT_BACK,
    EVENT_DELETE,
    EVENT_EDIT,
    EVENT_JOIN,
    EVENT_LEAVE,
    EVENT_OP,
    EVENT_POST,
    EVENT_REACT,
    EVENT_SUBJECT_DOWN,
    EVENT_SUBJECT_JOIN,
    EVENT_SUBJECT_LEAVE,
    EVENT_SUBJECT_UP,
    Event,
    Fault,
    NOTE_NOT_FIRED,
    NOTE_SHUTDOWN,
    NOTE_START,
    NOTE_TICK_DROPPED,
    Note,
    OBS_ACTION,
    OBS_DONE,
    OBS_ERROR,
    OBS_READY,
    OBS_STALLED,
    Observation,
    On,
    Pack,
    REPLY_CLOSED,
    REPLY_DONE,
    REPLY_ENDED,
    REPLY_READY,
    Reply,
    SHUTDOWN_END_OF_RUN,
    SHUTDOWN_ERROR,
    SHUTDOWN_WATCHDOG,
    STALL_CODES,
    SubjectMentions,
    SubjectPost,
    TICK,
)

__all__ = ["Plan", "Send", "State", "begin", "entries", "make_plan", "run", "step"]

PROTOCOL_VERSION = 1

_MISSING = object()
_TOP_LIMIT = 64


class _Map:
    """A persistent map: ``set`` returns a new map and shares the old base."""

    __slots__ = ("_base", "_top")

    def __init__(self, base=None, top=None):
        self._base = {} if base is None else base
        self._top = {} if top is None else top

    def get(self, key, default=None):
        value = self._top.get(key, _MISSING)
        if value is _MISSING:
            return self._base.get(key, default)
        return value

    def set(self, key, value) -> "_Map":
        top = dict(self._top)
        top[key] = value
        if len(top) > _TOP_LIMIT:
            base = dict(self._base)
            base.update(top)
            return _Map(base, {})
        return _Map(self._base, top)

    def _merged(self) -> dict:
        merged = dict(self._base)
        merged.update(self._top)
        return merged

    def __eq__(self, other):
        if not isinstance(other, _Map):
            return NotImplemented
        return self._merged() == other._merged()

    __hash__ = None


@dataclass(frozen=True, slots=True)
class Send:
    """What the loop must hand the session: ``call`` is ``start``, ``exchange``
    or ``stop``; ``message`` is the protocol message (``hello``, ``event`` or
    ``shutdown``) as a fresh dictionary."""

    call: str
    message: dict


@dataclass(frozen=True, slots=True)
class _Awaiting:
    what: str  # "start", "event" (a delivered event or tick) or "stop"
    seq: int
    t_ms: int
    reason: str | None = None  # for "stop"
    after_event: str | None = None  # a subject change applied once answered


@dataclass(frozen=True, slots=True, eq=False)
class Plan:
    """Read-only indexes of a pack."""

    pack: Pack
    wall_timeout_ms: int
    events: dict
    static: tuple  # (time, actor, id) of every ``at`` event, sorted
    anchored: dict  # anchor event id -> ``after`` events, in timeline order
    triggered: tuple  # ``on`` events, in timeline order
    displays: dict  # actor id -> display name or None


@dataclass(frozen=True, slots=True)
class State:
    """The whole state of a run between two steps."""

    time: int
    last_applied: int
    seq: int
    n: int
    log: object  # a chain of (entry, previous), newest first
    static_idx: int
    dyn: tuple  # due keys of ``after`` and fired events, sorted
    members: _Map  # surface id -> frozenset of actor ids
    subject_in: _Map  # surface id -> bool
    away: _Map  # actor id -> bool
    down: bool
    live: bool
    ticks: tuple  # pending tick times, ascending, without duplicates
    happened: _Map  # event id -> time
    fired: _Map  # event id -> True
    delivered: _Map  # (surface id, event id) -> True, for the subject
    awaiting: _Awaiting | None
    done: bool


_FIELDS = tuple(State.__dataclass_fields__)


class _Work:
    """A mutable copy of a ``State`` used inside one step."""

    __slots__ = _FIELDS

    def __init__(self, state: State):
        for name in _FIELDS:
            setattr(self, name, getattr(state, name))

    def freeze(self) -> State:
        return State(**{name: getattr(self, name) for name in _FIELDS})


def _plain(value):
    if type(value) is dict:
        return {key: _plain(item) for key, item in value.items()}
    if type(value) is list:
        return [_plain(item) for item in value]
    return value


def _deps(event: Event) -> tuple:
    deps = tuple(event.depends_on or ())
    if isinstance(event.when, After):
        deps += (event.when.event,)
    if event.target is not None:
        deps += (event.target,)
    return deps


def make_plan(pack: Pack, wall_timeout_ms: int = 30000) -> Plan:
    if type(wall_timeout_ms) is not int or wall_timeout_ms <= 0:
        raise ValueError("wall_timeout_ms must be a positive integer")
    events = {}
    for event in pack.events:
        if event.id in events:
            raise ValueError(f"duplicate event id {event.id!r}")
        events[event.id] = event
    static = sorted(
        (event.when.ms, event.actor, event.id)
        for event in pack.events
        if isinstance(event.when, At)
    )
    anchored: dict = {}
    for event in pack.events:
        if isinstance(event.when, After):
            anchored.setdefault(event.when.event, []).append(event)
    return Plan(
        pack=pack,
        wall_timeout_ms=wall_timeout_ms,
        events=events,
        static=tuple(static),
        anchored={key: tuple(value) for key, value in anchored.items()},
        triggered=tuple(e for e in pack.events if isinstance(e.when, On)),
        displays={actor.id: actor.display for actor in pack.actors},
    )


def _initial(plan: Plan) -> State:
    subject = plan.pack.subject.id
    members = _Map()
    subject_in = _Map()
    for surface in plan.pack.surfaces:
        members = members.set(
            surface.id, frozenset(m for m in surface.members if m != subject)
        )
        subject_in = subject_in.set(surface.id, subject in surface.members)
    return State(
        time=0,
        last_applied=0,
        seq=0,
        n=0,
        log=None,
        static_idx=0,
        dyn=(),
        members=members,
        subject_in=subject_in,
        away=_Map(),
        down=False,
        live=True,
        ticks=(),
        happened=_Map(),
        fired=_Map(),
        delivered=_Map(),
        awaiting=None,
        done=False,
    )


def entries(state: State) -> tuple:
    """The log so far, oldest first."""
    out = []
    node = state.log
    while node is not None:
        out.append(node[0])
        node = node[1]
    out.reverse()
    return tuple(out)


# --- logging ---------------------------------------------------------------


def _append(w: _Work, make) -> None:
    w.n += 1
    w.log = (make(w.n), w.log)


def _note(w: _Work, t: int, code: str, event=None, detail=None) -> None:
    _append(w, lambda n: Note(n=n, t_ms=t, code=code, event=event, detail=detail))


def _observe(w: _Work, t: int, seq: int, kind: str, **fields) -> None:
    _append(w, lambda n: Observation(n=n, t_ms=t, seq=seq, kind=kind, **fields))


# --- start -----------------------------------------------------------------


def begin(plan: Plan) -> tuple:
    """Start a run: the state after ``Note(start)`` and the ``hello`` to send."""
    w = _Work(_initial(plan))
    _note(w, 0, NOTE_START)
    surfaces = []
    for surface in sorted(plan.pack.surfaces, key=lambda s: s.id):
        if w.subject_in.get(surface.id):
            surfaces.append(
                {
                    "id": surface.id,
                    "kind": surface.kind,
                    "members": sorted(surface.members),
                }
            )
    hello = {
        "type": "hello",
        "v": PROTOCOL_VERSION,
        "subject_id": plan.pack.subject.id,
        "t_ms": 0,
        "surfaces": surfaces,
        "wall_timeout_ms": plan.wall_timeout_ms,
    }
    w.awaiting = _Awaiting("start", 0, 0)
    return w.freeze(), Send("start", hello)


# --- the step --------------------------------------------------------------


def step(plan: Plan, state: State, reply: Reply | None = None) -> tuple:
    """Consume the reply to the outstanding message and advance; see the
    module docstring."""
    if state.done:
        raise ValueError("the run is over")
    w = _Work(state)
    send = None
    if state.awaiting is None:
        if reply is not None:
            raise ValueError("no message is outstanding, so there is no reply")
    else:
        if reply is None:
            raise ValueError("a message is outstanding and needs its reply")
        send = _consume(plan, w, reply)
    if send is None:
        send = _advance(plan, w)
    return w.freeze(), send


def _consume(plan: Plan, w: _Work, reply: Reply):
    aw = w.awaiting
    w.awaiting = None
    allowed = {
        "start": (REPLY_READY, REPLY_ENDED),
        "event": (REPLY_DONE, REPLY_ENDED),
        "stop": (REPLY_CLOSED,),
    }[aw.what]
    if reply.end not in allowed:
        raise ValueError(f"a reply ending {reply.end!r} does not answer {aw.what!r}")
    t, seq = aw.t_ms, aw.seq
    for item in reply.items:
        if isinstance(item, Action):
            _action(plan, w, item, t, seq)
        else:
            _fault(w, item, t, seq)
    if aw.what == "stop":
        w.live = False
        return None
    if aw.after_event is not None:
        _apply_after(w, plan.events[aw.after_event])
    if reply.end == REPLY_ENDED:
        last = reply.items[-1] if reply.items else None
        reason = SHUTDOWN_ERROR
        if isinstance(last, Fault) and last.code == CODE_TIMEOUT:
            reason = SHUTDOWN_WATCHDOG
        w.ticks = ()
        _note(w, t, NOTE_SHUTDOWN, detail=reason)
        w.awaiting = _Awaiting("stop", 0, t, reason)
        return Send("stop", {"type": "shutdown", "reason": reason, "t_ms": t})
    if aw.what == "start":
        _observe(w, 0, 0, OBS_READY, name=reply.name, version=reply.version)
        return None
    _observe(w, t, seq, OBS_DONE, wake_at_ms=reply.wake_at_ms)
    if reply.wake_at_ms is not None and reply.wake_at_ms > t:
        w.ticks = tuple(sorted({*w.ticks, reply.wake_at_ms}))
    return None


def _fault(w: _Work, fault: Fault, t: int, seq: int) -> None:
    kind = OBS_STALLED if fault.code in STALL_CODES else OBS_ERROR
    _observe(w, t, seq, kind, code=fault.code, detail=fault.detail)


def _action(plan: Plan, w: _Work, action: Action, t: int, seq: int) -> None:
    rejected = None
    if not w.subject_in.get(action.surface, False):
        rejected = "surface"
    elif action.reply_to is not None and not w.delivered.get(
        (action.surface, action.reply_to)
    ):
        rejected = "reply_to"
    if rejected is not None:
        _observe(
            w, t, seq, OBS_ERROR, code=CODE_REJECTED_ACTION, detail=rejected,
            action=action,
        )
        return
    readers = tuple(sorted(w.members.get(action.surface, frozenset())))
    _observe(w, t, seq, OBS_ACTION, action=action, readers=readers)
    for event in plan.triggered:
        if w.fired.get(event.id):
            continue
        trigger = event.when.trigger
        if isinstance(trigger, SubjectPost):
            if action.kind != ACTION_POST or action.surface != trigger.surface:
                continue
        elif isinstance(trigger, SubjectMentions):
            if not _mentions(plan, action.text, trigger.actor):
                continue
        else:
            continue
        armed = 0
        ready = True
        for dep in event.depends_on or ():
            when = w.happened.get(dep)
            if when is None:
                ready = False
                break
            armed = max(armed, when)
        if not ready:
            continue
        if event.target is not None and w.happened.get(event.target) is None:
            continue
        if not armed <= t <= armed + trigger.within_ms:
            continue
        w.fired = w.fired.set(event.id, True)
        _enqueue(w, (t + (trigger.delay_ms or 0), event.actor, event.id))


def _mentions(plan: Plan, text: str, actor: str) -> bool:
    if match.contains(text, actor):
        return True
    display = plan.displays.get(actor)
    return bool(display) and match.contains(text, display)


def _enqueue(w: _Work, key: tuple) -> None:
    dyn = list(w.dyn)
    insort(dyn, key)
    w.dyn = tuple(dyn)


# --- advancing virtual time ------------------------------------------------


def _advance(plan: Plan, w: _Work):
    static = plan.static
    while True:
        head = None
        from_static = False
        if w.static_idx < len(static):
            head = static[w.static_idx]
            from_static = True
        if w.dyn and (head is None or w.dyn[0] < head):
            head = w.dyn[0]
            from_static = False
        if head is None:
            break
        if w.ticks and w.ticks[0] < head[0]:
            send = _tick(w)
            if send is not None:
                return send
            continue
        if from_static:
            w.static_idx += 1
        else:
            w.dyn = w.dyn[1:]
        send = _process(plan, w, head)
        if send is not None:
            return send
    if w.live:
        t = w.last_applied
        _note(w, t, NOTE_SHUTDOWN, detail=SHUTDOWN_END_OF_RUN)
        w.awaiting = _Awaiting("stop", 0, t, SHUTDOWN_END_OF_RUN)
        return Send(
            "stop", {"type": "shutdown", "reason": SHUTDOWN_END_OF_RUN, "t_ms": t}
        )
    _finish(plan, w)
    return None


def _finish(plan: Plan, w: _Work) -> None:
    t = w.last_applied
    for _ in w.ticks:
        _note(w, t, NOTE_TICK_DROPPED, detail="after_end")
    w.ticks = ()
    for event in plan.pack.events:
        if w.happened.get(event.id) is None:
            _note(w, t, NOTE_NOT_FIRED, event=event.id)
    w.done = True


def _tick(w: _Work):
    t = w.ticks[0]
    w.ticks = w.ticks[1:]
    w.time = t
    if w.down:
        _note(w, t, NOTE_TICK_DROPPED, detail="down")
        return None
    seq = w.seq + 1
    w.seq = seq
    _append(
        w,
        lambda n: Delivery(
            n=n, t_ms=t, kind=TICK, event=None, actor=None, surface=None,
            recipients=(), seq=seq,
        ),
    )
    w.awaiting = _Awaiting("event", seq, t)
    return Send(
        "exchange",
        {"type": "event", "seq": seq, "t_ms": t, "kind": TICK, "payload": {}},
    )


def _payload(event: Event) -> dict:
    payload = {"id": event.id, "surface": event.surface, "actor": event.actor}
    kind = event.kind
    if kind in (EVENT_POST, EVENT_EDIT):
        payload["text"] = event.text
    if kind in (EVENT_EDIT, EVENT_DELETE, EVENT_REACT):
        payload["target"] = event.target
    if kind == EVENT_REACT:
        payload["emoji"] = event.emoji
    if kind == EVENT_OP:
        payload["op"] = event.op
        payload["args"] = _plain(event.args) if event.args is not None else {}
    return payload


def _apply_before(w: _Work, event: Event) -> None:
    """Changes that take effect before the subject is told."""
    kind = event.kind
    surface = event.surface
    if kind == EVENT_JOIN:
        members = w.members.get(surface, frozenset())
        w.members = w.members.set(surface, members | {event.actor})
    elif kind == EVENT_LEAVE:
        members = w.members.get(surface, frozenset())
        w.members = w.members.set(surface, members - {event.actor})
    elif kind == EVENT_AWAY:
        w.away = w.away.set(event.actor, True)
    elif kind == EVENT_BACK:
        w.away = w.away.set(event.actor, False)
    elif kind == EVENT_SUBJECT_JOIN:
        w.subject_in = w.subject_in.set(surface, True)
    elif kind == EVENT_SUBJECT_UP:
        w.down = False


def _apply_after(w: _Work, event: Event) -> None:
    """Changes that take effect once the subject has answered."""
    kind = event.kind
    surface = event.surface
    if kind == EVENT_SUBJECT_LEAVE:
        w.subject_in = w.subject_in.set(surface, False)
    elif kind == EVENT_SUBJECT_DOWN:
        w.down = True


_NO_SURFACE_NEEDED = (EVENT_SUBJECT_DOWN, EVENT_SUBJECT_UP)


def _process(plan: Plan, w: _Work, key: tuple):
    t, _, event_id = key
    event = plan.events[event_id]
    for dep in _deps(event):
        if w.happened.get(dep) is None:
            return None  # never happens; reported as not_fired at the end
    w.time = t
    w.last_applied = t
    surface = event.surface
    kind = event.kind

    members = w.members.get(surface, frozenset())
    _apply_before(w, event)
    after = w.members.get(surface, frozenset())
    recipients = tuple(sorted(members | after))

    receives = w.live and not w.down
    if receives and kind not in _NO_SURFACE_NEEDED:
        receives = bool(w.subject_in.get(surface, False))
    seq = None
    message = None
    if receives:
        seq = w.seq + 1
        w.seq = seq
        w.delivered = w.delivered.set((surface, event.id), True)
        message = {
            "type": "event",
            "seq": seq,
            "t_ms": t,
            "kind": kind,
            "payload": _payload(event),
        }
    _append(
        w,
        lambda n: Delivery(
            n=n, t_ms=t, kind=kind, event=event.id, actor=event.actor,
            surface=surface, recipients=recipients, seq=seq,
        ),
    )
    w.happened = w.happened.set(event.id, t)
    for follower in plan.anchored.get(event.id, ()):
        _enqueue(w, (t + follower.when.delay_ms, follower.actor, follower.id))
    if message is None:
        _apply_after(w, event)
        return None
    pending = event.id if kind in (EVENT_SUBJECT_LEAVE, EVENT_SUBJECT_DOWN) else None
    w.awaiting = _Awaiting("event", seq, t, None, pending)
    return Send("exchange", message)


# --- the loop --------------------------------------------------------------


def _call(session, send: Send) -> Reply:
    if send.call == "start":
        return session.start(send.message)
    if send.call == "exchange":
        return session.exchange(send.message)
    return session.stop(send.message["reason"], send.message["t_ms"])


def run(pack: Pack, session, *, wall_timeout_ms: int = 30000) -> tuple:
    """Drive ``session`` through ``pack`` and return the log entries.

    If the loop raises (an interrupt, a step error, a transport error) after the
    session started and before it was stopped, the session is stopped with reason
    ``error`` at the time of the last applied event, any error from that stop is
    suppressed and the original exception is raised again.
    """
    plan = make_plan(pack, wall_timeout_ms)
    state, send = begin(plan)
    started = stopped = False
    try:
        while send is not None:
            if send.call == "stop":
                stopped = True
            reply = _call(session, send)
            started = started or send.call == "start"
            state, send = step(plan, state, reply)
    except BaseException:
        # An interrupt or an error in the loop must not leave the subject running.
        if started and not stopped:
            try:
                session.stop(SHUTDOWN_ERROR, state.last_applied)
            except Exception:
                pass
        raise
    return entries(state)
