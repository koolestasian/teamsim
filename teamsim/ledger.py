"""The derived exposure ledger (engine spec section 6.1; engine-modules section 3).

Nothing in a pack states who knows what. The ledger computes it from the pack
and the log alone:

- an actor is *exposed* to a fact through a delivery of an event that discloses
  the fact and lists the actor in ``recipients``; the subject is exposed through
  such a delivery that carries a ``seq`` (so never while it was down, never when
  it was not a member and never after its session ended);
- membership of each surface is replayed from the delivered ``join``, ``leave``,
  ``subject_join`` and ``subject_leave`` events over the pack's initial members;
- a fact is a *candidate* for ``current`` for someone when one of the deliveries
  that exposed them to it was of an event by an actor in the fact's authority.
  ``current`` is the candidate that no other candidate supersedes, directly or
  through a chain. Should two unrelated candidates of one key remain, the one
  with the latest authoritative exposure wins, then the smaller fact id;
- ``allowed`` evaluates the fact's audience at a time: ``*``, a listed actor, or
  ``group:<surface>`` meaning a member of that surface at that time;
- ``missed(who, t0, t1)`` lists the keys whose ``current`` value for ``who``
  differs between ``t0`` and ``t1``.

Times are inclusive: a delivery at exactly ``t`` counts as at ``t``. The checks
also need positions in the log, so the ``*_cut`` methods take an entry number
``n`` as well as, or instead of, a time; an entry cut counts deliveries up to
and including entry ``n``.

This is an exposure ledger, not a model of knowledge: it does not model
inference, forgetting or attention, and an actor who joins a surface later is
not exposed to its earlier events (no history replay). Pure: no clock, random
source, ``hash()`` or floating point.
"""

from bisect import bisect_right

from . import model
from .model import Delivery, LogEntry, Note, Pack

__all__ = ["Ledger"]

_SUBJECT_KINDS = frozenset(
    {
        model.EVENT_SUBJECT_JOIN,
        model.EVENT_SUBJECT_LEAVE,
        model.EVENT_SUBJECT_DOWN,
        model.EVENT_SUBJECT_UP,
    }
)
_MEMBERSHIP = _SUBJECT_KINDS | {model.EVENT_JOIN, model.EVENT_LEAVE}
_ENDING = (model.SHUTDOWN_ERROR, model.SHUTDOWN_WATCHDOG)


class Ledger:
    def __init__(self, pack: Pack, entries: tuple[LogEntry, ...]):
        self.pack = pack
        self.entries = tuple(entries)
        self.subject = pack.subject.id
        self.events = {e.id: e for e in pack.events}
        self.facts = {f.id: f for f in pack.facts}
        self._by_key: dict[str, list] = {}
        for fact in pack.facts:
            self._by_key.setdefault(fact.key, []).append(fact)
        self.deliveries = tuple(e for e in self.entries if isinstance(e, Delivery))
        self._by_event: dict[str, Delivery] = {}
        for d in self.deliveries:
            if d.event is not None:
                self._by_event.setdefault(d.event, d)
        self._by_seq = {d.seq: d for d in self.deliveries if d.seq is not None}
        # first note that ended the session, as an entry number
        self.ended_n: int | None = None
        for e in self.entries:
            if isinstance(e, Note) and e.code == model.NOTE_SHUTDOWN and e.detail in _ENDING:
                self.ended_n = e.n
                break
        self._build_membership()
        self._build_exposure()

    # -- building -----------------------------------------------------------

    def _build_membership(self) -> None:
        members = {s.id: set(s.members) for s in self.pack.surfaces}
        self._snap = {sid: ([0], [0], [frozenset(m)]) for sid, m in members.items()}
        sub_in = {sid for sid, m in members.items() if self.subject in m}
        down = False
        self._should: dict[int, bool] = {}
        for d in self.deliveries:
            if d.kind == model.TICK or d.event is None:
                continue
            kind, surface = d.kind, d.surface
            if kind == model.EVENT_SUBJECT_JOIN:
                self._should[d.n] = not down
                sub_in.add(surface)
            elif kind == model.EVENT_SUBJECT_LEAVE:
                self._should[d.n] = not down
                sub_in.discard(surface)
            elif kind == model.EVENT_SUBJECT_DOWN:
                self._should[d.n] = not down
                down = True
            elif kind == model.EVENT_SUBJECT_UP:
                down = False
                self._should[d.n] = True
            else:
                self._should[d.n] = surface in sub_in and not down
            if kind in _MEMBERSHIP and surface in members and d.actor is not None:
                if kind in (model.EVENT_JOIN, model.EVENT_SUBJECT_JOIN):
                    members[surface].add(d.actor)
                elif kind in (model.EVENT_LEAVE, model.EVENT_SUBJECT_LEAVE):
                    members[surface].discard(d.actor)
                else:
                    continue
                ns, ts, sets = self._snap[surface]
                ns.append(d.n)
                ts.append(d.t_ms)
                sets.append(frozenset(members[surface]))

    def _build_exposure(self) -> None:
        self._exp: dict[tuple[str, str], list] = {}
        for d in self.deliveries:
            event = self.events.get(d.event) if d.event is not None else None
            if event is None or not event.discloses:
                continue
            who = list(d.recipients)
            if d.seq is not None:
                who.append(self.subject)
            for fact_id in event.discloses:
                if fact_id not in self.facts:
                    continue
                for w in who:
                    self._exp.setdefault((w, fact_id), []).append((d.n, d.t_ms, event.id, event.actor))

    # -- lookups used by the checks -------------------------------------------

    def delivery(self, event_id: str) -> Delivery | None:
        return self._by_event.get(event_id)

    def delivery_of_seq(self, seq: int) -> Delivery | None:
        return self._by_seq.get(seq)

    def should_receive(self, n: int) -> bool | None:
        """Whether the subject should have been sent the event delivered at entry
        ``n`` (a member of its surface and not down; the four subject kinds
        ignore the surface). ``None`` for a tick or an unknown entry."""
        return self._should.get(n)

    def members(self, surface: str, *, t: int | None = None, n: int | None = None) -> frozenset:
        snap = self._snap.get(surface)
        if snap is None:
            return frozenset()
        ns, ts, sets = snap
        index = bisect_right(ns, n) - 1 if n is not None else bisect_right(ts, t) - 1
        return sets[max(index, 0)]

    @staticmethod
    def _in(row, t, n) -> bool:
        return (t is None or row[1] <= t) and (n is None or row[0] <= n)

    def _rows(self, who, fact_id, t, n) -> list:
        return [r for r in self._exp.get((who, fact_id), ()) if self._in(r, t, n)]

    # -- cut-based queries ---------------------------------------------------------

    def exposed_cut(self, who: str, fact_id: str, *, t: int | None = None, n: int | None = None) -> bool:
        return bool(self._rows(who, fact_id, t, n))

    def authoritative_cut(self, who: str, fact_id: str, *, t: int | None = None, n: int | None = None) -> bool:
        fact = self.facts.get(fact_id)
        if fact is None:
            return False
        return any(r[3] in fact.authority for r in self._rows(who, fact_id, t, n))

    def allowed_cut(self, who: str, fact_id: str, *, t: int | None = None, n: int | None = None) -> bool:
        fact = self.facts.get(fact_id)
        if fact is None:
            return False
        for entry in fact.audience:
            if entry == model.AUDIENCE_ALL or entry == who:
                return True
            if entry.startswith(model.AUDIENCE_GROUP_PREFIX):
                surface = entry[len(model.AUDIENCE_GROUP_PREFIX) :]
                if who in self.members(surface, t=t, n=n):
                    return True
        return False

    def candidates_cut(self, key: str, who: str, *, t: int | None = None, n: int | None = None) -> tuple:
        """Fact ids of ``key`` that ``who`` was exposed to through an authority."""
        return tuple(
            f.id for f in self._by_key.get(key, ()) if self.authoritative_cut(who, f.id, t=t, n=n)
        )

    def current_cut(self, key: str, who: str, *, t: int | None = None, n: int | None = None) -> str | None:
        cands = self.candidates_cut(key, who, t=t, n=n)
        if not cands:
            return None
        superseded = set()
        for fact_id in cands:
            seen = set()
            link = self.facts[fact_id].supersedes
            while link is not None and link not in seen and link in self.facts:
                seen.add(link)
                superseded.add(link)
                link = self.facts[link].supersedes
        left = [f for f in cands if f not in superseded]
        if not left:
            return None

        def rank(fact_id):
            fact = self.facts[fact_id]
            rows = [r for r in self._rows(who, fact_id, t, n) if r[3] in fact.authority]
            return (-max(r[0] for r in rows), fact_id)

        return min(left, key=rank)

    def missed_cut(self, who: str, *, t0=None, n0=None, t1=None, n1=None) -> tuple[str, ...]:
        keys = sorted({self.facts[f].key for (w, f) in self._exp if w == who})
        out = []
        for key in keys:
            if self.current_cut(key, who, t=t1, n=n1) != self.current_cut(key, who, t=t0, n=n0):
                out.append(key)
        return tuple(out)

    # -- the contract ------------------------------------------------------------------

    def exposed(self, who: str, fact_id: str, t_ms: int) -> bool:
        return self.exposed_cut(who, fact_id, t=t_ms)

    def current(self, key: str, who: str, t_ms: int) -> str | None:
        return self.current_cut(key, who, t=t_ms)

    def allowed(self, who: str, fact_id: str, t_ms: int) -> bool:
        return self.allowed_cut(who, fact_id, t=t_ms)

    def missed(self, who: str, t0_ms: int, t1_ms: int) -> tuple[str, ...]:
        return self.missed_cut(who, t0=t0_ms, t1=t1_ms)

    def table(self) -> tuple[dict, ...]:
        """One row per (who, fact) pair with an exposure, for ``inspect``.

        ``n``, ``t_ms``, ``event`` and ``by`` describe the first exposure;
        ``authoritative`` is true when any exposure was by an actor in the fact's
        authority; ``allowed`` is the audience test at the first exposure. Sorted
        by ``who``, ``t_ms``, ``n`` and ``fact``. Canonical values only.
        """
        rows = []
        for (who, fact_id), exposures in self._exp.items():
            fact = self.facts[fact_id]
            first = min(exposures)
            rows.append(
                {
                    "who": who,
                    "fact": fact_id,
                    "key": fact.key,
                    "n": first[0],
                    "t_ms": first[1],
                    "event": first[2],
                    "by": first[3],
                    "authoritative": any(r[3] in fact.authority for r in exposures),
                    "allowed": self.allowed_cut(who, fact_id, n=first[0]),
                }
            )
        rows.sort(key=lambda r: (r["who"], r["t_ms"], r["n"], r["fact"]))
        return tuple(rows)
