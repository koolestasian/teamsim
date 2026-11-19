"""Tests for the derived exposure ledger (engine-modules section 3).

Logs are built in memory by ``simulate``, a small stand-in for the engine that
follows engine-modules section 2 for static timelines (no triggers fire).
"""

import ast
import dataclasses
import pathlib
import unittest

from teamsim import canon, model, pack
from teamsim.ledger import Ledger
from teamsim.model import Action, Delivery, Event, Fact, Note, Observation

ROOT = pathlib.Path(__file__).parent.parent
MINIMAL = ROOT / "packs" / "minimal"
SOURCE = ROOT / "teamsim" / "ledger.py"

_SUBJECT_KINDS = (
    model.EVENT_SUBJECT_JOIN,
    model.EVENT_SUBJECT_LEAVE,
    model.EVENT_SUBJECT_DOWN,
    model.EVENT_SUBJECT_UP,
)


def say(text, surface="general", **kw):
    return Action(kind="post", surface=surface, text=text, **kw)


def simulate(p, replies=None, end_after=None):
    """Build the log of a run with static times. ``replies`` maps the id of the
    event being handled to a list of ``Action`` (applied) or ``("reject", Action)``.
    ``end_after`` names an event after whose reply the session ends with an error."""
    replies = replies or {}
    subject = p.subject.id
    members = {s.id: set(s.members) for s in p.surfaces}
    log = []

    def add(cls, **kw):
        entry = cls(n=len(log) + 1, **kw)
        log.append(entry)
        return entry

    add(Note, t_ms=0, code=model.NOTE_START)
    add(Observation, t_ms=0, seq=0, kind=model.OBS_READY, name="stub", version="1")
    done, times = set(), {}
    down = ended = False
    seq = 0

    def due(e):
        if any(d not in done for d in (e.depends_on or ())):
            return None
        when = e.when
        if isinstance(when, model.At):
            return when.ms
        if isinstance(when, model.After) and when.event in done:
            return times[when.event] + when.delay_ms
        return None

    while True:
        ready = [(due(e), e.actor, e.id, e) for e in p.events if e.id not in done]
        ready = [r for r in ready if r[0] is not None and (r[3].target is None or r[3].target in done)]
        if not ready:
            break
        t, _, _, e = min(ready, key=lambda r: r[:3])
        done.add(e.id)
        times[e.id] = t
        surface = members[e.surface]
        before = set(surface)
        subject_kind = e.kind in _SUBJECT_KINDS
        if e.kind in (model.EVENT_JOIN, model.EVENT_SUBJECT_JOIN):
            surface.add(e.actor)
        if e.kind == model.EVENT_SUBJECT_UP:
            down = False
        if subject_kind:
            sent = not down and not ended
        else:
            sent = subject in surface and not down and not ended
        if e.kind in (model.EVENT_LEAVE, model.EVENT_SUBJECT_LEAVE):
            surface.discard(e.actor)
        if e.kind == model.EVENT_SUBJECT_DOWN:
            down = True
        actors = sorted((before | surface) - {subject})
        if sent:
            seq += 1
        add(
            Delivery,
            t_ms=t,
            kind=e.kind,
            event=e.id,
            actor=e.actor,
            surface=e.surface,
            recipients=tuple(actors),
            seq=seq if sent else None,
        )
        if not sent:
            continue
        for item in replies.get(e.id, ()):
            rejected = isinstance(item, tuple)
            action = item[1] if rejected else item
            if rejected:
                add(
                    Observation,
                    t_ms=t,
                    seq=seq,
                    kind=model.OBS_ERROR,
                    code=model.CODE_REJECTED_ACTION,
                    action=action,
                    detail="surface",
                )
            else:
                readers = tuple(sorted(members[action.surface] - {subject}))
                add(Observation, t_ms=t, seq=seq, kind=model.OBS_ACTION, action=action, readers=readers)
        add(Observation, t_ms=t, seq=seq, kind=model.OBS_DONE)
        if e.id == end_after:
            add(Note, t_ms=t, code=model.NOTE_SHUTDOWN, detail=model.SHUTDOWN_ERROR)
            ended = True
    end = max(times.values(), default=0)
    if not ended:
        add(Note, t_ms=end, code=model.NOTE_SHUTDOWN, detail=model.SHUTDOWN_END_OF_RUN)
    for e in p.events:
        if e.id not in done:
            add(Note, t_ms=end, code=model.NOTE_NOT_FIRED, event=e.id)
    return tuple(log)


def event(obj):
    return Event.from_obj(obj)


def with_events(p, extra=(), drop_discloses=(), **replace):
    """A copy of ``p`` with extra events appended and ``discloses`` removed from some."""
    events = []
    for e in p.events:
        if e.id in drop_discloses:
            e = dataclasses.replace(e, discloses=None)
        events.append(e)
    events.extend(event(o) for o in extra)
    return dataclasses.replace(p, events=tuple(events), **replace)


def with_facts(p, *facts):
    return dataclasses.replace(p, facts=p.facts + tuple(Fact.from_obj(f) for f in facts))


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = pack.load(MINIMAL)
        cls.log = simulate(cls.pack)
        cls.ledger = Ledger(cls.pack, cls.log)


class Exposure(Base):
    def test_actor_exposed_through_recipients(self):
        self.assertTrue(self.ledger.exposed("ana", "f.date.1", 0))
        self.assertTrue(self.ledger.exposed("bo", "f.room", 20000))
        self.assertFalse(self.ledger.exposed("bo", "f.room", 19999))

    def test_restricted_surface_reaches_only_its_members(self):
        self.assertTrue(self.ledger.exposed("di", "f.budget", 220000))
        self.assertTrue(self.ledger.exposed("ana", "f.budget", 220000))
        self.assertFalse(self.ledger.exposed("bo", "f.budget", 10**9))
        self.assertFalse(self.ledger.exposed("cy", "f.token", 10**9))

    def test_subject_exposed_through_seq(self):
        self.assertTrue(self.ledger.exposed("subject", "f.date.1", 0))
        self.assertFalse(self.ledger.exposed("subject", "f.room", 19999))
        self.assertTrue(self.ledger.exposed("subject", "f.room", 20000))

    def test_subject_not_exposed_before_it_joins(self):
        # e08 adds the subject to "leads" at 200000; the budget comes at 220000.
        self.assertTrue(self.ledger.exposed("subject", "f.budget", 220000))
        early = with_events(
            self.pack, drop_discloses=("e09",), extra=[
                {"id": "e09b", "at": 100000, "actor": "ana", "surface": "leads", "kind": "post",
                 "text": "x", "discloses": ["f.budget"]}
            ]
        )
        ledger = Ledger(early, simulate(early))
        self.assertTrue(ledger.exposed("ana", "f.budget", 100000))
        self.assertFalse(ledger.exposed("subject", "f.budget", 10**9))

    def test_later_joiner_is_not_exposed_to_earlier_events(self):
        # di joins "general" at 500000; the date was posted there earlier.
        self.assertFalse(self.ledger.exposed("di", "f.date.1", 10**9))
        self.assertFalse(self.ledger.exposed("di", "f.date.2", 10**9))

    def test_unknown_names_are_not_exposed(self):
        self.assertFalse(self.ledger.exposed("nobody", "f.date.1", 10**9))
        self.assertFalse(self.ledger.exposed("ana", "no.such.fact", 10**9))

    def _late_fact(self, **sim):
        late = with_facts(
            self.pack,
            {"id": "f.late", "key": "late", "kind": "item", "value": "late-item",
             "authority": ["ana"], "audience": ["*"]},
        )
        late = with_events(
            late,
            extra=[{"id": "e25b", "at": 610000, "actor": "ana", "surface": "general", "kind": "post",
                    "text": "late", "discloses": ["f.late"]}],
        )
        return late, Ledger(late, simulate(late, **sim))

    def test_subject_not_exposed_while_down(self):
        # e24 down at 580000, e26 up at 620000: 610000 falls inside.
        late, ledger = self._late_fact()
        self.assertTrue(ledger.exposed("ana", "f.late", 610000))
        self.assertTrue(ledger.exposed("bo", "f.late", 610000))
        self.assertFalse(ledger.exposed("subject", "f.late", 10**9))

    def test_subject_not_exposed_after_the_session_ended(self):
        late = with_facts(
            self.pack,
            {"id": "f.late", "key": "late", "kind": "item", "value": "late-item",
             "authority": ["ana"], "audience": ["*"]},
        )
        late = with_events(
            late,
            extra=[{"id": "e30", "at": 700000, "actor": "ana", "surface": "general", "kind": "post",
                    "text": "late", "discloses": ["f.late"]}],
        )
        ledger = Ledger(late, simulate(late, end_after="e16"))
        self.assertTrue(ledger.exposed("ana", "f.late", 700000))
        self.assertFalse(ledger.exposed("subject", "f.late", 10**9))
        self.assertTrue(ledger.exposed("subject", "f.date.2", 10**9))  # before the end

    def test_membership_is_replayed(self):
        ledger = self.ledger
        self.assertEqual(ledger.members("general", t=0), {"ana", "bo", "cy", "subject"})
        self.assertEqual(ledger.members("general", t=500000), {"ana", "bo", "cy", "subject", "di"})
        self.assertEqual(ledger.members("general", t=560000), {"ana", "bo", "cy", "subject"})
        self.assertEqual(ledger.members("leads", t=199999), {"ana", "di"})
        self.assertEqual(ledger.members("leads", t=200000), {"ana", "di", "subject"})
        self.assertEqual(ledger.members("leads", t=640000), {"ana", "di"})
        self.assertEqual(ledger.members("nowhere", t=0), frozenset())


class Current(Base):
    def test_supersession(self):
        self.assertEqual(self.ledger.current("date", "bo", 270000), "f.date.1")
        self.assertEqual(self.ledger.current("date", "bo", 300000), "f.date.2")
        self.assertEqual(self.ledger.current("date", "subject", 1), "f.date.1")
        self.assertEqual(self.ledger.current("date", "subject", 10**9), "f.date.2")

    def test_nothing_before_exposure(self):
        self.assertIsNone(self.ledger.current("date", "bo", -1))
        self.assertIsNone(self.ledger.current("room", "bo", 19999))
        self.assertIsNone(self.ledger.current("no-such-key", "bo", 10**9))
        self.assertIsNone(self.ledger.current("budget", "bo", 10**9))

    def test_a_claim_by_a_non_authority_is_never_current(self):
        # e11: bo (not in the authority of f.claim) states 13 April; f.date.1 stays current.
        self.assertTrue(self.ledger.exposed("subject", "f.claim", 260000))
        self.assertEqual(self.ledger.current("date", "subject", 270000), "f.date.1")

    def test_a_fact_by_its_authority_is_current(self):
        changed = with_events(self.pack, drop_discloses=("e01", "e13"))
        ledger = Ledger(changed, simulate(changed))
        self.assertIsNone(ledger.current("date", "bo", 10**9))  # only the claim, by bo
        ok = with_events(
            self.pack,
            drop_discloses=("e01", "e13", "e11"),
            extra=[{"id": "e28", "at": 700000, "actor": "ana", "surface": "general", "kind": "post",
                    "text": "13 April", "discloses": ["f.claim"]}],
        )
        self.assertEqual(Ledger(ok, simulate(ok)).current("date", "bo", 10**9), "f.claim")

    def _chain(self, drop=()):
        chained = with_facts(
            self.pack,
            {"id": "f.date.3", "key": "date", "kind": "date", "value": "Friday 17 April",
             "forms": ["17 April"], "authority": ["ana"], "audience": ["*"], "supersedes": "f.date.2"},
        )
        chained = with_events(
            chained,
            drop_discloses=drop,
            extra=[{"id": "e28", "at": 700000, "actor": "ana", "surface": "general", "kind": "post",
                    "text": "Friday 17 April", "discloses": ["f.date.3"]}],
        )
        return Ledger(chained, simulate(chained))

    def test_chain_of_two_levels(self):
        ledger = self._chain()
        self.assertEqual(ledger.current("date", "ana", 650000), "f.date.2")
        self.assertEqual(ledger.current("date", "ana", 700000), "f.date.3")

    def test_chain_skips_an_unexposed_link(self):
        # e13 no longer discloses f.date.2, yet f.date.3 still supersedes f.date.1.
        ledger = self._chain(drop=("e13",))
        self.assertEqual(ledger.current("date", "ana", 650000), "f.date.1")
        self.assertEqual(ledger.current("date", "ana", 700000), "f.date.3")


class Allowed(Base):
    def test_everyone_and_listed_actors(self):
        self.assertTrue(self.ledger.allowed("cy", "f.date.1", 0))
        self.assertTrue(self.ledger.allowed("di", "f.token", 0))
        self.assertTrue(self.ledger.allowed("ana", "f.token", 0))
        self.assertFalse(self.ledger.allowed("bo", "f.token", 10**9))
        self.assertFalse(self.ledger.allowed("subject", "f.token", 10**9))

    def test_group_is_evaluated_at_the_time(self):
        self.assertTrue(self.ledger.allowed("ana", "f.budget", 0))
        self.assertFalse(self.ledger.allowed("bo", "f.budget", 10**9))
        self.assertFalse(self.ledger.allowed("subject", "f.budget", 199999))
        self.assertTrue(self.ledger.allowed("subject", "f.budget", 200000))
        self.assertTrue(self.ledger.allowed("subject", "f.budget", 639999))
        self.assertFalse(self.ledger.allowed("subject", "f.budget", 640000))

    def test_unknown_fact(self):
        self.assertFalse(self.ledger.allowed("ana", "no.such.fact", 0))


class Missed(Base):
    def test_away_window(self):
        # bo is away 280000-320000; e13 at 300000 changes the date.
        self.assertEqual(self.ledger.missed("bo", 280000, 320000), ("date",))

    def test_empty_when_nothing_changed(self):
        self.assertEqual(self.ledger.missed("bo", 320000, 400000), ())
        self.assertEqual(self.ledger.missed("bo", 280000, 299999), ())
        self.assertEqual(self.ledger.missed("nobody", 0, 10**9), ())

    def test_keys_are_sorted_and_per_actor(self):
        self.assertEqual(self.ledger.missed("ana", 0, 10**9), ("access-code", "budget", "date", "room"))
        self.assertEqual(self.ledger.missed("bo", 0, 10**9), ("date", "room"))
        # a change that never reached the actor is not missed by them
        self.assertEqual(self.ledger.missed("cy", 220000, 260000), ())


class Table(Base):
    def test_rows_are_canonical_and_sorted(self):
        rows = self.ledger.table()
        canon.check(list(rows))
        keys = [(r["who"], r["t_ms"], r["n"], r["fact"]) for r in rows]
        self.assertEqual(keys, sorted(keys))
        first = {(r["who"], r["fact"]): r for r in rows}
        row = first[("subject", "f.budget")]
        self.assertEqual((row["event"], row["by"], row["t_ms"]), ("e09", "ana", 220000))
        self.assertTrue(row["allowed"] and row["authoritative"])
        self.assertFalse(first[("bo", "f.claim")]["authoritative"])
        self.assertNotIn(("bo", "f.budget"), first)

    def test_minimal_null_log_hash_is_pinned(self):
        self.assertEqual(canon.hash_of(list(self.ledger.table())), TABLE_HASH)


class Source(unittest.TestCase):
    def test_imports_and_calls(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules.add("." * node.level + (node.module or ""))
        self.assertEqual(modules, {"bisect", ".", ".model"})
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        self.assertFalse(names & {"hash", "float", "random", "time", "datetime"})
        self.assertFalse(
            [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, float)]
        )


TABLE_HASH = "004ec3c14f218c7254f0a27300fff0c1ef5fd622c169d9b17d716ba1448880d8"


if __name__ == "__main__":
    unittest.main()
