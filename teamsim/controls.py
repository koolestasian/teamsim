"""Control subjects and pack validation (engine spec section 7; engine-modules section 7).

The controls are in-process subjects built from the pack's own ledger. They test
the pack and the checks; they never stand in for a real product. They are the only
subjects that read the pack, and they send nothing outside the process and write no
file.

How a control knows what to say. ``make`` runs the pack once against a silent
subject and builds a ``Ledger`` from that log. The silent run delivers the same
events as any run in which the session does not end early, so the ledger says what
the subject was told by each probe. A control then answers each probe from the
checks that name it. Limit: a pack whose trigger-fired events disclose facts only
after a subject action is not covered by this reference run; ``validate`` reports
the mismatch it causes.

The controls.

``null`` never acts. ``oracle`` answers each probe with the form the checks expect.
Each ``defect:*`` control is the oracle with exactly one change:

- ``stale``: answers a key with the nearest superseded value it was exposed to.
- ``gullible``: answers a key with a claim made by someone outside the fact's
  authority, when it saw one.
- ``leaky``: at a probe that carries a ``withhold`` check, also says the withheld
  fact, which readers outside its audience may see.
- ``echo``: repeats a secret in the surface where it saw it.
- ``amnesiac``: answers a catch-up probe without the changes it missed.
- ``deaf``: does nothing for events on one surface, the first surface of the pack
  that is not ``direct``.

``expected`` is derived from the ledger of the silent run and the table in engine
spec section 7, not from a table of verdicts. A defect that changes no expectation
in a pack is *not exercised* by that pack. Pure: no clock, random source,
``hash()`` or floating point.
"""

from . import checks, engine, match, model
from .ledger import Ledger
from .model import Pack
from .subject import InProcess

__all__ = ["NAMES", "expected", "make", "matrix", "validate"]

NAMES = (
    "null",
    "oracle",
    "defect:stale",
    "defect:gullible",
    "defect:leaky",
    "defect:echo",
    "defect:amnesiac",
    "defect:deaf",
)

_PASS = (model.VERDICT_PASS, None)
_NA = (model.VERDICT_NOT_APPLICABLE, None)
_LIVE, _NOT_APPLICABLE = "live", "not_applicable"

_REFUSAL = "I do not have that."
_NOTHING_NEW = "Nothing new that I know of."


class _Silent:
    """The handler of the reference run: answers every message and does nothing."""

    def handle(self, message):
        kind = message.get("type")
        if kind == "hello":
            return [{"type": "ready", "v": message["v"], "name": "silent", "version": "0"}]
        if kind == "event":
            return [{"type": "done", "in_reply_to": message["seq"]}]
        return []


class _Ref:
    """The silent run of a pack and its ledger."""

    def __init__(self, pack: Pack):
        self.pack = pack
        self.subject = pack.subject.id
        self.entries = engine.run(pack, InProcess(_Silent()))
        self.ledger = Ledger(pack, self.entries)
        self.events = {e.id: e for e in pack.events}
        self.facts = {f.id: f for f in pack.facts}
        self.deaf = next((s.id for s in pack.surfaces if s.kind != model.SURFACE_DIRECT), None)

    def delivery(self, event_id):
        return self.ledger.delivery(event_id)

    def cut(self, d):
        return {"t": d.t_ms, "n": d.n}

    def exposed_at(self, fact_id, d) -> bool:
        return self.ledger.exposed_cut(self.subject, fact_id, **self.cut(d))

    def current(self, key, d):
        return self.ledger.current_cut(key, self.subject, **self.cut(d))

    def seen(self, key, d):
        """Facts of ``key`` the subject was exposed to by the probe delivery ``d``."""
        return [f for f in self.pack.facts if f.key == key and self.exposed_at(f.id, d)]

    def stale_pick(self, key, d):
        """The nearest superseded fact the subject took from an authority, or ``None``."""
        current = self.current(key, d)
        if current is None:
            return None
        candidates = set(self.ledger.candidates_cut(key, self.subject, **self.cut(d)))
        seen, link = set(), self.facts[current].supersedes
        while link is not None and link in self.facts and link not in seen:
            seen.add(link)
            if link in candidates:
                return self.facts[link]
            link = self.facts[link].supersedes
        for fact in self.pack.facts:
            if fact.id in candidates and fact.id != current:
                return fact
        return None

    def claim_pick(self, key, d):
        """The first fact of ``key`` the subject saw only from outside its authority."""
        for fact in self.seen(key, d):
            if not self.ledger.authoritative_cut(self.subject, fact.id, **self.cut(d)):
                return fact
        return None

    def required(self, event, d):
        """The facts a catch-up probe expects, by key; ``None`` when it does not apply."""
        led, asker = self.ledger, event.actor
        away = back = None
        for earlier in led.deliveries:
            if earlier.n >= d.n:
                break
            if earlier.actor != asker:
                continue
            if earlier.kind == model.EVENT_AWAY:
                away, back = earlier, None
            elif earlier.kind == model.EVENT_BACK and away is not None and back is None:
                back = earlier
        if away is None:
            return None
        end = back if back is not None else d
        found = {}
        for key in led.missed_cut(asker, n0=away.n, n1=end.n):
            fact_id = led.current_cut(key, asker, n=end.n)
            if (
                fact_id is not None
                and led.exposed_cut(self.subject, fact_id, **self.cut(d))
                and led.allowed_cut(asker, fact_id, **self.cut(d))
            ):
                found[key] = self.facts[fact_id]
        return found or None

    def received(self, event_id) -> bool:
        d = self.delivery(event_id)
        return d is not None and d.seq is not None

    def readers(self, event, d):
        """Actors who read an action the subject posts on the surface of ``event``."""
        members = self.ledger.members(event.surface, n=d.n)
        return sorted(m for m in members if m != self.subject)

    def outsiders(self, fact_id, event, d):
        return [r for r in self.readers(event, d) if not self.ledger.allowed_cut(r, fact_id, n=d.n)]

    def leaks(self):
        """``(probe event, delivery, fact)`` for each fact ``defect:leaky`` says."""
        out = []
        for check in self.pack.checks:
            if check.kind != model.CHECK_WITHHOLD or check.probe not in self.events:
                continue
            event, d = self.events[check.probe], self.delivery(check.probe)
            if d is not None and d.seq is not None and self.exposed_at(check.fact, d):
                out.append((event, d, self.facts[check.fact]))
        return out

    def echoes(self):
        """``(event, delivery, fact)`` for each secret that ``defect:echo`` repeats."""
        out = []
        for d in self.ledger.deliveries:
            event = self.events.get(d.event) if d.event is not None else None
            if event is None or d.seq is None or event.text is None:
                continue
            for fact in self.pack.facts:
                if fact.kind == model.FACT_SECRET and _mentions(event.text, fact):
                    out.append((event, d, fact))
        return out


def _forms(fact):
    return (fact.value,) + tuple(fact.forms or ())


def _mentions(text, fact) -> bool:
    return any(match.normalise(form) and match.contains(text, form) for form in _forms(fact))


# --- what each control says ------------------------------------------------


def _pieces(name, ref, event, d):
    """The sentences ``name`` uses to answer probe ``event`` delivered as ``d``."""
    asker, out = event.actor, []
    for check in ref.pack.checks:
        if check.probe != event.id:
            continue
        if check.kind == model.CHECK_ANSWER:
            current = ref.facts.get(ref.current(check.key, d) or "")
            if current is not None and not ref.ledger.allowed_cut(asker, current.id, **ref.cut(d)):
                current = None
            fact = current
            if name == "defect:stale":
                fact = ref.stale_pick(check.key, d) or current
            elif name == "defect:gullible":
                fact = ref.claim_pick(check.key, d) or current
            if fact is not None:
                out.append(fact.value)
        elif check.kind == model.CHECK_CATCH_UP:
            if name == "defect:amnesiac":
                out.append(_NOTHING_NEW)
            else:
                out.extend(f.value for f in (ref.required(event, d) or {}).values())
        elif check.kind == model.CHECK_WITHHOLD and name == "defect:leaky":
            if ref.exposed_at(check.fact, d):
                out.append(ref.facts[check.fact].value)
    return list(dict.fromkeys(out))


class _Control:
    """The handler a control gives to ``subject.InProcess``."""

    def __init__(self, name: str, ref: _Ref):
        self.name = name
        self._ref = ref
        self._secrets = [f for f in ref.pack.facts if f.kind == model.FACT_SECRET]

    def handle(self, message: dict) -> list:
        kind = message.get("type")
        if kind == "hello":
            return [{"type": "ready", "v": message["v"], "name": self.name, "version": "0"}]
        if kind != "event":
            return []
        seq = message["seq"]
        done = {"type": "done", "in_reply_to": seq}
        if self.name == "null" or message["kind"] == model.TICK:
            return [done]
        payload = message["payload"]
        surface = payload["surface"]
        if self.name == "defect:deaf" and surface == self._ref.deaf:
            return [done]
        out = []
        event = self._ref.events.get(payload["id"])
        d = self._ref.delivery(payload["id"])
        if event is not None and event.probe is True and d is not None:
            out.append(self._answer(seq, event, d))
        if self.name == "defect:echo":
            for fact in self._secrets:
                if _mentions(payload.get("text", ""), fact):
                    out.append(self._action(seq, surface, "post", "Noted: " + fact.value, payload["id"]))
        return out + [done]

    @staticmethod
    def _action(seq, surface, kind, text, reply_to):
        return {
            "type": "action",
            "in_reply_to": seq,
            "kind": kind,
            "surface": surface,
            "text": text,
            "reply_to": reply_to,
        }

    def _answer(self, seq, event, d):
        pieces = _pieces(self.name, self._ref, event, d)
        kind = model.ACTION_RESULT if event.kind == model.EVENT_OP else model.ACTION_POST
        return self._action(seq, event.surface, kind, "; ".join(pieces) or _REFUSAL, event.id)


def make(name: str, pack: Pack):
    """The handler of control ``name`` for ``pack``, for ``subject.InProcess``."""
    if name not in NAMES:
        raise ValueError("unknown control: %s" % name)
    return _Control(name, _Ref(pack))


# --- what each control should get --------------------------------------------


def _state(ref, check):
    """``"not_applicable"`` when the check has nothing to score, else ``"live"``.

    A check whose probe never reached the subject is left ``"live"``: the pack is
    then at fault, and ``validate`` reports it as a mismatch.
    """
    kind = check.kind
    if kind == model.CHECK_HARNESS:
        return _LIVE
    if kind in (model.CHECK_NO_LEAK, model.CHECK_NO_ECHO):
        exposed = ref.ledger.exposed_cut(ref.subject, check.fact)
        return _LIVE if exposed else _NOT_APPLICABLE
    event, d = ref.events[check.probe], ref.delivery(check.probe)
    if d is None or (d.seq is None and ref.ledger.should_receive(d.n)):
        return _LIVE
    if kind == model.CHECK_ANSWER:
        return _LIVE if ref.seen(check.key, d) else _NOT_APPLICABLE
    if kind == model.CHECK_WITHHOLD:
        return _LIVE if ref.exposed_at(check.fact, d) else _NOT_APPLICABLE
    return _LIVE if ref.required(event, d) is not None else _NOT_APPLICABLE


def _no_response(kind):
    return (model.VERDICT_FAIL, model.REASON_NO_RESPONSE) if kind in (
        model.CHECK_ANSWER,
        model.CHECK_CATCH_UP,
    ) else _PASS


def _verdict(name, ref, check):
    kind = check.kind
    if name == "null":
        return _no_response(kind)
    probe = ref.events.get(check.probe) if check.probe else None
    d = ref.delivery(check.probe) if check.probe else None
    if name == "defect:stale" and kind == model.CHECK_ANSWER and d is not None:
        if ref.stale_pick(check.key, d) is not None:
            return (model.VERDICT_FAIL, model.REASON_STALE)
    elif name == "defect:gullible" and kind == model.CHECK_ANSWER and d is not None:
        if ref.claim_pick(check.key, d) is not None:
            return (model.VERDICT_FAIL, model.REASON_UNAUTHORISED)
    elif name == "defect:leaky":
        if kind == model.CHECK_WITHHOLD:
            return (model.VERDICT_FAIL, model.REASON_LEAKED)
        if kind == model.CHECK_NO_LEAK and any(
            fact.id == check.fact and ref.outsiders(fact.id, event, d)
            for event, d, fact in ref.leaks()
        ):
            return (model.VERDICT_FAIL, model.REASON_LEAKED)
    elif name == "defect:echo":
        if kind == model.CHECK_NO_ECHO and any(f.id == check.fact for _, _, f in ref.echoes()):
            return (model.VERDICT_FAIL, model.REASON_ECHOED)
        if kind == model.CHECK_NO_LEAK and any(
            fact.id == check.fact and ref.outsiders(fact.id, event, d)
            for event, d, fact in ref.echoes()
        ):
            return (model.VERDICT_FAIL, model.REASON_LEAKED)
    elif name == "defect:amnesiac" and kind == model.CHECK_CATCH_UP:
        return (model.VERDICT_FAIL, model.REASON_MISSED)
    elif name == "defect:deaf" and probe is not None and probe.surface == ref.deaf:
        return _no_response(kind)
    return _PASS


def _expected(name, ref):
    out = {}
    for check in ref.pack.checks:
        if _state(ref, check) == _NOT_APPLICABLE:
            out[check.id] = _NA
        else:
            out[check.id] = _verdict(name, ref, check)
    return out


def expected(name: str, pack: Pack) -> dict:
    """Check id to ``(verdict, reason)`` that control ``name`` should get on ``pack``."""
    if name not in NAMES:
        raise ValueError("unknown control: %s" % name)
    return _expected(name, _Ref(pack))


def _observed(name, pack, ref):
    entries = engine.run(pack, InProcess(_Control(name, ref)))
    return {v.check: (v.verdict, v.reason) for v in checks.evaluate(pack, entries)}


def matrix(pack: Pack) -> dict:
    """Observed ``(verdict, reason)`` of every control on every check, by control."""
    ref = _Ref(pack)
    return {name: _observed(name, pack, ref) for name in NAMES}


def _show(pair):
    verdict, reason = pair
    return verdict if reason is None else "%s (%s)" % (verdict, reason)


def validate(pack: Pack) -> list:
    """One line per mismatch, per undetected defect and per defect the pack does not exercise.

    Empty when every control gets what the ledger says it should and every defect is
    exercised and detected. No percentage is given: the defects are few and were
    chosen by hand.
    """
    ref = _Ref(pack)
    want = {name: _expected(name, ref) for name in NAMES}
    seen = {name: _observed(name, pack, ref) for name in NAMES}
    lines = []
    for name in NAMES:
        for check in pack.checks:
            if want[name][check.id] != seen[name][check.id]:
                lines.append(
                    "%s: check %s: expected %s, observed %s"
                    % (name, check.id, _show(want[name][check.id]), _show(seen[name][check.id]))
                )
    for name in NAMES[2:]:
        if want[name] == want["oracle"]:
            lines.append("%s: not exercised: no check of this pack plants its situation" % name)
        elif seen[name] == seen["oracle"]:
            lines.append("%s: not detected: no check tells it from the oracle" % name)
    return lines
