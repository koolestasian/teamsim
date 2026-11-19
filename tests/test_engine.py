"""Tests for the engine (docs/spec/engine-modules.md section 2)."""

import ast
import json
import pathlib
import sys
import time
import unittest

from teamsim import canon, engine, pack as packmod
from teamsim.model import (
    Actor,
    After,
    At,
    Delivery,
    Event,
    Note,
    Observation,
    On,
    Pack,
    PackHeader,
    Subject,
    Surface,
    SubjectMentions,
    SubjectPost,
)
from tests import fakes
from tests.fakes import FakeSession, done, ended, fault, post

ROOT = pathlib.Path(__file__).parent.parent
SOURCE = ROOT / "teamsim" / "engine.py"


def ev(id, actor="ana", surface="s", kind="post", at=None, after=None, on=None, **kw):
    if at is not None:
        when = At(at)
    elif after is not None:
        when = After(*after)
    else:
        when = On(on)
    if kind in ("post", "edit") and "text" not in kw:
        kw["text"] = "hello"
    return Event(id=id, when=when, actor=actor, surface=surface, kind=kind, **kw)


def make_pack(events, surfaces=None, actors=("ana", "bo", "cy"), displays=None):
    surfaces = surfaces or {"s": ["ana", "bo", "subject"]}
    displays = displays or {}
    return Pack(
        header=PackHeader(1, "secret-pack-id", "t", "p", "secret-seed", ()),
        subject=Subject("subject"),
        actors=tuple(Actor(a, display=displays.get(a)) for a in actors),
        surfaces=tuple(Surface(k, "channel", tuple(v)) for k, v in surfaces.items()),
        facts=(),
        checks=(),
        events=tuple(events),
    )


def eid(message):
    return message.get("payload", {}).get("id")


def deliveries(log):
    return {e.event: e for e in log if isinstance(e, Delivery) and e.event}


def notes(log, code):
    return [e for e in log if isinstance(e, Note) and e.code == code]


def order(log):
    return [e.event for e in log if isinstance(e, Delivery)]


class Ordering(unittest.TestCase):
    def test_time_actor_id_by_code_point(self):
        events = [
            ev("b", actor="a", at=5),
            ev("z", actor="Z", at=5),  # "Z" sorts before "a"
            ev("a", actor="a", at=5),
            ev("c", actor="a", at=1),
        ]
        log = engine.run(make_pack(events, actors=("a", "Z")), FakeSession())
        self.assertEqual(order(log), ["c", "z", "a", "b"])

    def test_after_event_sorts_into_the_current_time(self):
        events = [
            ev("x1", actor="b", at=10),
            ev("x2", actor="c", at=10),
            ev("early", actor="a", after=("x1", 0)),
            ev("late", actor="d", after=("x1", 0)),
        ]
        log = engine.run(make_pack(events, actors=("a", "b", "c", "d")), FakeSession())
        self.assertEqual(order(log), ["x1", "early", "x2", "late"])

    def test_fired_trigger_sorts_into_the_current_time(self):
        trig = SubjectPost("s", 100)
        events = [
            ev("x1", actor="b", at=10),
            ev("x2", actor="c", at=10),
            ev("fired", actor="a", on=trig),
        ]

        def handler(message):
            if eid(message) == "x1":
                return done(post("s", "hi"))

        pk = make_pack(events, surfaces={"s": ["a", "b", "c", "subject"]}, actors=("a", "b", "c"))
        log = engine.run(pk, FakeSession(handler))
        self.assertEqual(order(log), ["x1", "fired", "x2"])

    def test_tick_sorts_after_scripted_events_at_its_time(self):
        events = [ev("a", at=10), ev("b", at=20), ev("c", at=20, actor="bo")]

        def handler(message):
            if eid(message) == "a":
                return done(wake_at_ms=20)

        log = engine.run(make_pack(events + [ev("d", at=30)]), FakeSession(handler))
        self.assertEqual(order(log), ["a", "b", "c", None, "d"])
        tick = [e for e in log if isinstance(e, Delivery)][3]
        self.assertEqual((tick.kind, tick.t_ms, tick.event, tick.recipients), ("tick", 20, None, ()))

    def test_tick_before_a_later_event(self):
        events = [ev("a", at=10), ev("b", at=30)]

        def handler(message):
            if eid(message) == "a":
                return done(wake_at_ms=20)

        log = engine.run(make_pack(events), FakeSession(handler))
        self.assertEqual(order(log), ["a", None, "b"])

    def test_numbering_and_seq(self):
        log = engine.run(make_pack([ev("a", at=1), ev("b", at=2)]), FakeSession())
        self.assertEqual([e.n for e in log], list(range(1, len(log) + 1)))
        seqs = [e.seq for e in log if isinstance(e, Delivery)]
        self.assertEqual(seqs, [1, 2])

    def test_seq_counts_only_messages_sent(self):
        events = [
            ev("a", at=1),
            ev("other", surface="t", at=2, actor="ana"),
            ev("b", at=3),
        ]
        pk = make_pack(events, surfaces={"s": ["ana", "bo", "subject"], "t": ["ana", "bo"]})
        log = engine.run(pk, FakeSession())
        d = deliveries(log)
        self.assertEqual((d["a"].seq, d["other"].seq, d["b"].seq), (1, None, 2))

    def test_empty_timeline(self):
        log = engine.run(make_pack([]), FakeSession())
        self.assertEqual([type(e).__name__ for e in log], ["Note", "Observation", "Note"])
        self.assertEqual(log[-1].t_ms, 0)
        self.assertEqual(log[-1].detail, "end_of_run")


class Membership(unittest.TestCase):
    def test_recipients_exclude_the_subject_and_are_sorted(self):
        pk = make_pack([ev("a", at=1)], surfaces={"s": ["cy", "subject", "ana"]})
        d = deliveries(engine.run(pk, FakeSession()))
        self.assertEqual(d["a"].recipients, ("ana", "cy"))

    def test_join_and_leave_include_the_actor(self):
        events = [
            ev("j", actor="cy", kind="join", at=1),
            ev("p", at=2),
            ev("l", actor="bo", kind="leave", at=3),
            ev("q", at=4),
        ]
        d = deliveries(engine.run(make_pack(events), FakeSession()))
        self.assertEqual(d["j"].recipients, ("ana", "bo", "cy"))
        self.assertEqual(d["p"].recipients, ("ana", "bo", "cy"))
        self.assertEqual(d["l"].recipients, ("ana", "bo", "cy"))
        self.assertEqual(d["q"].recipients, ("ana", "cy"))

    def test_away_and_back_do_not_change_recipients(self):
        events = [
            ev("aw", actor="bo", kind="away", at=1),
            ev("p", at=2),
            ev("bk", actor="bo", kind="back", at=3),
        ]
        d = deliveries(engine.run(make_pack(events), FakeSession()))
        self.assertEqual(d["aw"].recipients, ("ana", "bo"))
        self.assertEqual(d["p"].recipients, ("ana", "bo"))
        self.assertEqual(d["bk"].recipients, ("ana", "bo"))
        self.assertTrue(all(d[k].seq for k in d))

    def test_subject_join_and_up_are_delivered_after_they_apply(self):
        events = [
            ev("p0", at=1),
            ev("sj", actor="subject", kind="subject_join", at=2),
            ev("p1", at=3),
        ]
        pk = make_pack(events, surfaces={"s": ["ana", "bo"]})
        d = deliveries(engine.run(pk, FakeSession()))
        self.assertIsNone(d["p0"].seq)
        self.assertEqual((d["sj"].seq, d["p1"].seq), (1, 2))

    def test_subject_up_is_delivered_and_down_before_it_applies(self):
        events = [
            ev("p0", at=1),
            ev("dn", actor="subject", kind="subject_down", at=2),
            ev("p1", at=3),
            ev("up", actor="subject", kind="subject_up", at=4),
            ev("p2", at=5),
        ]
        d = deliveries(engine.run(make_pack(events), FakeSession()))
        self.assertEqual([d[k].seq for k in ("p0", "dn", "p1", "up", "p2")], [1, 2, None, 3, 4])

    def test_subject_leave_is_delivered_before_it_applies(self):
        events = [
            ev("sl", actor="subject", kind="subject_leave", at=2),
            ev("p1", at=3),
        ]
        d = deliveries(engine.run(make_pack(events), FakeSession()))
        self.assertEqual((d["sl"].seq, d["p1"].seq), (1, None))

    def test_action_on_a_surface_after_leaving_is_accepted_during_the_leave_exchange(self):
        events = [ev("sl", actor="subject", kind="subject_leave", at=2)]
        session = FakeSession(lambda m: done(post("s", "bye")) if m.get("kind") == "subject_leave" else None)
        log = engine.run(make_pack(events), session)
        self.assertEqual([o.kind for o in log if isinstance(o, Observation)][1:3], ["action", "done"])

    def test_subject_events_when_not_member_or_down(self):
        events = [
            ev("dn", actor="subject", kind="subject_down", at=1),
            ev("dn2", actor="subject", kind="subject_down", at=2),
            ev("sl", actor="subject", kind="subject_leave", at=3),
            ev("up", actor="subject", kind="subject_up", at=4),
            ev("sl2", actor="subject", kind="subject_leave", at=5),
            ev("sl3", actor="subject", kind="subject_leave", at=6),
        ]
        d = deliveries(engine.run(make_pack(events), FakeSession()))
        self.assertEqual(
            [d[k].seq for k in ("dn", "dn2", "sl", "up", "sl2", "sl3")],
            [1, None, None, 2, None, None],  # sl applied while down, so sl2 is not a member
        )

    def test_not_in_the_surface_gets_nothing(self):
        pk = make_pack([ev("p", surface="t", at=1)], surfaces={"s": ["ana", "subject"], "t": ["ana", "bo"]})
        log = engine.run(pk, FakeSession())
        self.assertIsNone(deliveries(log)["p"].seq)
        self.assertEqual(len(FakeSession().messages), 0)

    def test_action_on_a_foreign_surface_is_rejected_and_kept(self):
        pk = make_pack([ev("p", at=1)], surfaces={"s": ["ana", "subject"], "t": ["ana", "bo"]})
        act = post("t", "sneaky")
        log = engine.run(pk, FakeSession(lambda m: done(act) if m.get("kind") == "post" else None))
        obs = [o for o in log if isinstance(o, Observation) and o.kind == "subject_error"]
        self.assertEqual(len(obs), 1)
        self.assertEqual((obs[0].code, obs[0].action, obs[0].seq, obs[0].t_ms), ("rejected_action", act, 1, 1))
        self.assertFalse([o for o in log if isinstance(o, Observation) and o.kind == "action"])

    def test_reply_to_must_name_a_delivered_event(self):
        events = [
            ev("p", at=1),
            ev("hidden", surface="t", at=2),
            ev("q", at=3),
        ]
        pk = make_pack(events, surfaces={"s": ["ana", "subject"], "t": ["ana", "subject2"]})

        def handler(m):
            if eid(m) == "q":
                return done(
                    post("s", "ok", reply_to="p"),
                    post("s", "no", reply_to="hidden"),
                    post("s", "nope", reply_to="ghost"),
                    post("s", "self", reply_to="q"),
                )

        log = engine.run(pk, FakeSession(handler))
        kinds = [(o.kind, o.code) for o in log if isinstance(o, Observation) and o.seq == 2]
        self.assertEqual(
            kinds,
            [("action", None), ("subject_error", "rejected_action"), ("subject_error", "rejected_action"),
             ("action", None), ("done", None)],
        )

    def test_readers_are_the_actor_members_at_that_time(self):
        events = [ev("j", actor="cy", kind="join", at=1), ev("p", at=2)]
        log = engine.run(make_pack(events), FakeSession(lambda m: done(post("s", "x")) if eid(m) == "p" else None))
        act = [o for o in log if isinstance(o, Observation) and o.kind == "action"][0]
        self.assertEqual(act.readers, ("ana", "bo", "cy"))

    def test_event_from_a_non_member_is_still_applied(self):
        d = deliveries(engine.run(make_pack([ev("p", actor="cy", at=1)]), FakeSession()))
        self.assertEqual(d["p"].recipients, ("ana", "bo"))
        self.assertEqual(d["p"].seq, 1)


def action_on(event_id, *actions):
    def handler(message):
        if message.get("payload", {}).get("id") == event_id:
            return done(*actions)

    return handler


class Triggers(unittest.TestCase):
    def pk(self, trigger, extra=(), **kw):
        events = [ev("start", at=0), *extra, ev("fire", actor="cy", on=trigger, **kw)]
        return make_pack(events, surfaces={"s": ["ana", "bo", "cy", "subject"]})

    def test_subject_post_fires_inside_the_window_with_default_delay(self):
        pk = self.pk(SubjectPost("s", 100))
        log = engine.run(pk, FakeSession(action_on("start", post("s", "hi"))))
        self.assertEqual(deliveries(log)["fire"].t_ms, 0)

    def test_subject_post_ignores_other_surface_and_kinds(self):
        pk = make_pack(
            [ev("start", at=0), ev("fire", on=SubjectPost("s", 100))],
            surfaces={"s": ["ana", "subject"], "t": ["ana", "subject"]},
        )
        acts = (post("t", "x"), post("s", "y", kind="react"), post("s", "z", kind="result"))
        log = engine.run(pk, FakeSession(action_on("start", *acts)))
        self.assertNotIn("fire", deliveries(log))

    def test_delay_is_added(self):
        pk = self.pk(SubjectPost("s", 100, 7))
        log = engine.run(pk, FakeSession(action_on("start", post("s", "hi"))))
        self.assertEqual(deliveries(log)["fire"].t_ms, 7)

    def test_window_boundaries_are_inclusive(self):
        for gap, fires in ((50, True), (51, False)):
            with self.subTest(gap=gap):
                events = [
                    ev("arm", at=100),
                    ev("probe", at=100 + gap),
                    ev("fire", actor="cy", on=SubjectPost("s", 50), depends_on=("arm",)),
                ]
                pk = make_pack(events, surfaces={"s": ["ana", "cy", "subject"]})
                log = engine.run(pk, FakeSession(action_on("probe", post("s", "hi"))))
                self.assertEqual("fire" in deliveries(log), fires)

    def test_not_before_armed(self):
        events = [
            ev("early", at=10),
            ev("arm", at=100),
            ev("fire", actor="cy", on=SubjectPost("s", 500), depends_on=("arm",)),
        ]
        pk = make_pack(events, surfaces={"s": ["ana", "cy", "subject"]})
        log = engine.run(pk, FakeSession(action_on("early", post("s", "hi"))))
        self.assertNotIn("fire", deliveries(log))

    def test_armed_time_is_the_last_dependency(self):
        events = [
            ev("d1", at=100),
            ev("d2", at=300),
            ev("probe", at=350),
            ev("fire", actor="cy", on=SubjectPost("s", 100), depends_on=("d1", "d2")),
        ]
        pk = make_pack(events, surfaces={"s": ["ana", "cy", "subject"]})
        log = engine.run(pk, FakeSession(action_on("probe", post("s", "hi"))))
        self.assertEqual(deliveries(log)["fire"].t_ms, 350)

    def test_fires_at_most_once(self):
        pk = self.pk(SubjectPost("s", 100))
        log = engine.run(pk, FakeSession(action_on("start", post("s", "a"), post("s", "b"))))
        self.assertEqual(order(log).count("fire"), 1)

    def test_mention_by_id_and_by_display_name(self):
        for text, fires in (("ping bo please", True), ("ping Bobby now", True), ("ping bobbyx", False), ("ping", False)):
            with self.subTest(text=text):
                events = [ev("start", at=0), ev("fire", actor="cy", on=SubjectMentions("bo", 100))]
                pk = make_pack(events, surfaces={"s": ["ana", "bo", "cy", "subject"]}, displays={"bo": "Bobby"})
                act = post("s", text, kind="react")  # any action kind counts
                log = engine.run(pk, FakeSession(action_on("start", act)))
                self.assertEqual("fire" in deliveries(log), fires)

    def test_mention_window(self):
        events = [ev("start", at=0), ev("late", at=200), ev("fire", actor="cy", on=SubjectMentions("bo", 100))]
        pk = make_pack(events, surfaces={"s": ["ana", "bo", "cy", "subject"]})
        log = engine.run(pk, FakeSession(action_on("late", post("s", "bo"))))
        self.assertNotIn("fire", deliveries(log))

    def test_rejected_action_fires_nothing(self):
        pk = make_pack(
            [ev("start", at=0), ev("fire", on=SubjectPost("t", 100))],
            surfaces={"s": ["ana", "subject"], "t": ["ana"]},
        )
        log = engine.run(pk, FakeSession(action_on("start", post("t", "hi"))))
        self.assertNotIn("fire", deliveries(log))

    def test_not_fired_notes_follow_timeline_order_and_dependents(self):
        events = [
            ev("start", at=0),
            ev("never", on=SubjectPost("s", 100)),
            ev("child", after=("never", 5)),
            ev("depends", at=50, depends_on=("never",)),
            ev("edits", at=60, kind="edit", target="never"),
            ev("ok", at=70),
        ]
        log = engine.run(make_pack(events), FakeSession())
        self.assertEqual([n.event for n in notes(log, "not_fired")], ["never", "child", "depends", "edits"])
        self.assertEqual(notes(log, "not_fired")[0].t_ms, 70)
        self.assertEqual(log[-4:][0].code, "not_fired")

    def test_after_event_follows_its_anchor(self):
        events = [ev("a", at=10), ev("b", after=("a", 5))]
        d = deliveries(engine.run(make_pack(events), FakeSession()))
        self.assertEqual(d["b"].t_ms, 15)

    def test_after_event_with_unmet_dependency_never_happens(self):
        events = [ev("a", at=10), ev("t", on=SubjectPost("s", 5)), ev("b", after=("a", 0), depends_on=("t",))]
        log = engine.run(make_pack(events), FakeSession())
        self.assertNotIn("b", deliveries(log))
        self.assertIn("b", [n.event for n in notes(log, "not_fired")])


class Ticks(unittest.TestCase):
    def test_a_later_request_does_not_cancel_an_earlier_one(self):
        events = [ev("a", at=10), ev("b", at=11), ev("c", at=100)]

        def handler(m):
            return {"a": done(wake_at_ms=50), "b": done(wake_at_ms=20)}.get(eid(m))

        log = engine.run(make_pack(events), FakeSession(handler))
        ticks = [e for e in log if isinstance(e, Delivery) and e.kind == "tick"]
        self.assertEqual([t.t_ms for t in ticks], [20, 50])

    def test_requests_for_the_same_time_give_one_tick(self):
        events = [ev("a", at=10), ev("b", at=11), ev("c", at=100)]

        def handler(m):
            return {"a": done(wake_at_ms=50), "b": done(wake_at_ms=50)}.get(eid(m))

        log = engine.run(make_pack(events), FakeSession(handler))
        ticks = [e for e in log if isinstance(e, Delivery) and e.kind == "tick"]
        self.assertEqual([t.t_ms for t in ticks], [50])

    def test_wake_not_later_is_ignored(self):
        events = [ev("a", at=10), ev("b", at=100)]
        session = FakeSession(lambda m: done(wake_at_ms=10) if eid(m) == "a" else None)
        log = engine.run(make_pack(events), session)
        self.assertFalse([e for e in log if isinstance(e, Delivery) and e.kind == "tick"])
        done_obs = [o for o in log if isinstance(o, Observation) and o.kind == "done"]
        self.assertEqual(done_obs[0].wake_at_ms, 10)  # recorded as given

    def test_tick_dropped_while_down(self):
        events = [
            ev("a", at=10),
            ev("dn", actor="subject", kind="subject_down", at=20),
            ev("b", at=100),
        ]
        session = FakeSession(lambda m: done(wake_at_ms=50) if m.get("payload", {}).get("id") == "a" else None)
        log = engine.run(make_pack(events), session)
        dropped = notes(log, "tick_dropped")
        self.assertEqual([(n.t_ms, n.detail) for n in dropped], [(50, "down")])
        self.assertFalse([e for e in log if isinstance(e, Delivery) and e.kind == "tick"])

    def test_tick_after_the_end_is_dropped(self):
        events = [ev("a", at=10)]
        session = FakeSession(lambda m: done(wake_at_ms=500) if eid(m) == "a" else None)
        log = engine.run(make_pack(events), session)
        names = [(type(e).__name__, getattr(e, "code", None), getattr(e, "detail", None)) for e in log[-2:]]
        self.assertEqual(names, [("Note", "shutdown", "end_of_run"), ("Note", "tick_dropped", "after_end")])
        self.assertEqual(log[-1].t_ms, 10)

    def test_tick_message_has_an_empty_payload(self):
        events = [ev("a", at=10), ev("b", at=100)]
        session = FakeSession(lambda m: done(wake_at_ms=50) if eid(m) == "a" else None)
        engine.run(make_pack(events), session)
        tick = [m for m in session.messages if m.get("kind") == "tick"][0]
        self.assertEqual(tick, {"type": "event", "seq": 2, "t_ms": 50, "kind": "tick", "payload": {}})


class SessionEnd(unittest.TestCase):
    def pk(self):
        return make_pack([ev("a", at=1), ev("b", at=2), ev("c", at=3)])

    def test_ending_fault(self):
        for code, reason in (("exited", "error"), ("timeout", "watchdog")):
            with self.subTest(code=code):
                session = FakeSession(lambda m, code=code: ended(post("s", "last"), fault(code, "x")) if m.get("payload", {}).get("id") == "b" else None)
                log = engine.run(self.pk(), session)
                self.assertEqual(session.calls[-1], ("stop", {"type": "shutdown", "reason": reason, "t_ms": 2}))
                self.assertEqual(len([c for c in session.calls if c[0] == "stop"]), 1)
                d = deliveries(log)
                self.assertEqual((d["a"].seq, d["b"].seq, d["c"].seq), (1, 2, None))
                self.assertEqual(d["c"].recipients, ("ana", "bo"))
                kinds = [type(e).__name__ + ":" + (getattr(e, "code", None) or getattr(e, "kind", "")) for e in log]
                i = kinds.index("Note:shutdown")
                self.assertEqual(kinds[i - 2 : i], ["Observation:action", "Observation:" + code])
                self.assertEqual(log[i - 1].kind, "subject_stalled" if code == "timeout" else "subject_error")
                self.assertEqual(log[i].detail, reason)
                self.assertNotIn("Note:shutdown", kinds[i + 1 :])  # no second shutdown
                self.assertEqual([n.detail for n in notes(log, "shutdown")], [reason])

    def test_stop_reply_items_are_appended_after_shutdown(self):
        session = FakeSession([None, None, ended(fault("exited")), closed_with_no_exit()])
        log = engine.run(self.pk(), session)
        names = [(type(e).__name__, getattr(e, "code", None)) for e in log]
        i = names.index(("Note", "shutdown"))
        self.assertEqual(names[i + 1], ("Observation", "no_exit"))
        self.assertEqual(log[i + 1].kind, "subject_stalled")
        self.assertEqual((log[i + 1].seq, log[i + 1].t_ms), (0, 2))

    def test_failed_start_continues_without_the_subject(self):
        session = FakeSession([ended(fault("version_mismatch", "v"))])
        log = engine.run(self.pk(), session)
        self.assertEqual([e.seq for e in log if isinstance(e, Delivery)], [None, None, None])
        self.assertEqual(notes(log, "shutdown")[0].t_ms, 0)

    def test_normal_end(self):
        session = FakeSession()
        log = engine.run(self.pk(), session)
        self.assertEqual(session.calls[-1], ("stop", {"type": "shutdown", "reason": "end_of_run", "t_ms": 3}))
        self.assertEqual((log[-1].code, log[-1].detail, log[-1].t_ms), ("shutdown", "end_of_run", 3))

    def test_end_of_run_stop_reply_is_logged(self):
        session = FakeSession([None, None, None, None, closed_with_no_exit()])
        log = engine.run(self.pk(), session)
        self.assertEqual((log[-1].code, log[-1].t_ms, log[-1].seq), ("no_exit", 3, 0))

    def test_mismatched_reply_end_is_an_error(self):
        with self.assertRaises(ValueError):
            engine.run(self.pk(), FakeSession([fakes.done()]))


def closed_with_no_exit():
    return fakes.closed(fault("no_exit", "still running"))


class Minimal(unittest.TestCase):
    PROBES = {"e15", "e16", "e18", "e21", "e22"}

    def handler(self, message):
        p = message.get("payload", {})
        if p.get("id") in self.PROBES:
            text = "ana: room-5520" if p["id"] == "e18" else "Thursday 16 April"
            return done(post(p["surface"], text, reply_to=p["id"]))

    def run_minimal(self):
        pk = packmod.load(ROOT / "packs" / "minimal")
        session = FakeSession(self.handler)
        return pk, session, engine.run(pk, session)

    def test_runs_end_to_end(self):
        pk, session, log = self.run_minimal()
        d = deliveries(log)
        # e17 depends on e16 and e19 on e18, so a subject that answers those probes
        # (a post on general; a reply that names ana) fires both triggers.
        self.assertEqual(len(d), len(pk.events))
        self.assertEqual(notes(log, "not_fired"), [])
        times = {k: v.t_ms for k, v in d.items()}
        self.assertEqual((times["e17"], times["e19"]), (402000, 455000))
        actions = [o for o in log if isinstance(o, Observation) and o.kind == "action"]
        self.assertEqual(len(actions), 5)

    def test_pinned_log_hash(self):
        _, _, log = self.run_minimal()
        digest = canon.hash_of([e.to_obj() for e in log])
        self.assertEqual(digest, PINNED_HASH)


PINNED_HASH = "32b6c261cbf9c8d8a23845c540fc10439e4546ad2d3284a52267245ad78a844d"


class Determinism(unittest.TestCase):
    def test_same_pack_same_script_same_log(self):
        pk = packmod.load(ROOT / "packs" / "minimal")
        h = Minimal().handler
        a = engine.run(pk, FakeSession(h))
        b = engine.run(pk, FakeSession(h))
        self.assertEqual(a, b)

    def test_step_does_not_change_its_input(self):
        pk = packmod.load(ROOT / "packs" / "minimal")
        plan = engine.make_plan(pk)
        state, send = engine.begin(plan)
        first = engine.step(plan, state, fakes.ready())
        second = engine.step(plan, state, fakes.ready())
        self.assertEqual(first, second)
        self.assertEqual(engine.entries(state)[-1].code, "start")
        self.assertEqual(len(engine.entries(state)), 1)
        self.assertEqual(send.call, "start")


class Hygiene(unittest.TestCase):
    HELLO = {"type", "v", "subject_id", "t_ms", "surfaces", "wall_timeout_ms"}
    EVENT = {"type", "seq", "t_ms", "kind", "payload"}
    PAYLOAD = {
        "post": {"id", "surface", "actor", "text"},
        "edit": {"id", "surface", "actor", "text", "target"},
        "delete": {"id", "surface", "actor", "target"},
        "react": {"id", "surface", "actor", "target", "emoji"},
        "op": {"id", "surface", "actor", "op", "args"},
    }

    def test_only_protocol_fields_are_sent(self):
        pk = packmod.load(ROOT / "packs" / "minimal")
        session = FakeSession(Minimal().handler)
        engine.run(pk, session, wall_timeout_ms=1234)
        hello = session.messages[0]
        self.assertEqual(set(hello), self.HELLO)
        self.assertEqual(hello["wall_timeout_ms"], 1234)
        self.assertEqual(hello["t_ms"], 0)
        self.assertEqual(
            hello["surfaces"],
            [
                {"id": "direct:bo", "kind": "direct", "members": ["bo", "subject"]},
                {"id": "general", "kind": "channel", "members": ["ana", "bo", "cy", "subject"]},
            ],
        )
        seen = set()
        for message in session.messages[1:]:
            if message["type"] == "shutdown":
                self.assertEqual(set(message), {"type", "reason", "t_ms"})
                continue
            self.assertEqual(set(message), self.EVENT)
            kind = message["kind"]
            seen.add(kind)
            if kind in self.PAYLOAD:
                self.assertEqual(set(message["payload"]), self.PAYLOAD[kind])
            else:
                self.assertEqual(set(message["payload"]), {"id", "surface", "actor"})
        self.assertTrue({"post", "edit", "delete", "react", "op", "join", "leave"} <= seen)
        dump = json.dumps(session.messages)
        secrets = [pk.header.id, pk.header.seed, str(ROOT)]
        secrets += [f.id for f in pk.facts]
        secrets += [c.id for c in pk.checks] + ['"probe"', '"discloses"', '"depends_on"', "pack.toml"]
        for text in secrets:
            self.assertNotIn(text, dump, text)

    def test_discloses_probe_depends_on_never_sent(self):
        events = [
            ev("a", at=1, discloses=("f1",), probe=True),
            ev("b", at=2, depends_on=("a",)),
        ]
        session = FakeSession()
        engine.run(make_pack(events), session)
        dump = json.dumps(session.messages)
        for text in ("discloses", "probe", "depends_on", "f1", "secret-seed", "secret-pack-id"):
            self.assertNotIn(text, dump)

    def test_messages_are_independent_copies(self):
        args = {"k": [1, 2]}
        events = [ev("o", surface="d", kind="op", op="ask", args=args, at=1)]
        pk = make_pack(events, surfaces={"d": ["ana", "subject"]})

        class Mutator(FakeSession):
            def exchange(self, event):
                event["payload"]["args"]["k"].append(3)
                return super().exchange(event)

        engine.run(pk, Mutator())
        self.assertEqual(args, {"k": [1, 2]})


class Pure(unittest.TestCase):
    def test_imports_and_constructs(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        modules = set()
        names = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules.add(node.module)
                names[node.module] = {a.name for a in node.names}
            elif isinstance(node, ast.Constant) and isinstance(node.value, float):
                self.fail("floating point constant")
            elif isinstance(node, ast.Div):
                self.fail("true division")
            elif isinstance(node, ast.Name) and node.id in {"hash", "open", "input", "print"}:
                self.fail(node.id)
            elif isinstance(node, ast.Attribute) and node.attr in {"environ", "random", "getenv"}:
                self.fail(node.attr)
        self.assertEqual(modules, {"bisect", "dataclasses", "teamsim", "teamsim.model"})
        self.assertEqual(names["teamsim"], {"match"})


class Performance(unittest.TestCase):
    def test_ten_thousand_events_in_under_five_seconds(self):
        day = 86_400_000
        actors = [f"u{i}" for i in range(10)]
        surfaces = {f"s{i}": actors + ["subject"] for i in range(4)}
        events = []
        count = 10_000
        step = 30 * day // count
        for i in range(count):
            events.append(
                ev(f"e{i:05d}", actor=actors[i % 10], surface=f"s{i % 4}", at=i * step, text=f"message {i}")
            )
        events[5000] = ev("e05000", actor="u0", surface="s0", after=("e04999", 1), text="after")
        pk = make_pack(events, surfaces=surfaces, actors=actors)

        class Quick:
            def start(self, hello):
                return fakes.ready()

            def exchange(self, event):
                return fakes.done()

            def stop(self, reason, t_ms):
                return fakes.closed()

        started = time.perf_counter()
        log = engine.run(pk, Quick())
        elapsed = time.perf_counter() - started
        sys.stderr.write(f"\n[engine perf] 10000 events: {elapsed:.2f}s on {sys.version_info[:3]}\n")
        self.assertEqual(len([e for e in log if isinstance(e, Delivery)]), count)
        self.assertLess(elapsed, 5.0)


if __name__ == "__main__":
    unittest.main()


class Interrupted(unittest.TestCase):
    """A run that raises still stops the session (engine-modules section 2.6)."""

    class Boom(Exception):
        pass

    def wrap(self, inner, error, on=3):
        outer = self

        class Wrapper:
            def __init__(self):
                self.count = 0
                self.stops = []

            def start(self, hello):
                return inner.start(hello)

            def exchange(self, event):
                self.count += 1
                if self.count == on:
                    raise error
                return inner.exchange(event)

            def stop(self, reason, t_ms):
                self.stops.append((reason, t_ms))
                return inner.stop(reason, t_ms)

        return Wrapper()

    def test_the_session_is_stopped_when_the_loop_raises(self):
        pk = packmod.load(ROOT / "packs" / "minimal")
        for error in (KeyboardInterrupt(), self.Boom("x"), RuntimeError("transport")):
            with self.subTest(error=type(error).__name__):
                inner = FakeSession()
                wrapper = self.wrap(inner, error)
                with self.assertRaises(type(error)):
                    engine.run(pk, wrapper)
                self.assertEqual([s[0] for s in wrapper.stops], ["error"])
                self.assertEqual(wrapper.stops[0][1], 40000)  # the time of the third event, the last applied

    def test_a_failed_start_is_not_stopped(self):
        class Broken(FakeSession):
            def start(self, hello):
                raise RuntimeError("cannot start")

        inner = Broken()
        with self.assertRaises(RuntimeError):
            engine.run(make_pack([ev("a", at=1)]), inner)
        self.assertFalse([c for c in inner.calls if c[0] == "stop"])

    def test_a_stop_that_raises_does_not_hide_the_first_error(self):
        class BadStop(FakeSession):
            def stop(self, reason, t_ms):
                raise RuntimeError("stop failed")

        wrapper = self.wrap(BadStop(), KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            engine.run(packmod.load(ROOT / "packs" / "minimal"), wrapper)

    def test_the_child_process_and_its_directory_are_gone_after_an_interrupt(self):
        from teamsim import subject

        scripted = str(ROOT / "tests" / "subjects" / "scripted.py")
        child = subject.ChildProcess([sys.executable, "-I", scripted, "normal"], wall_timeout_ms=3000)
        wrapper = self.wrap(child, KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            engine.run(packmod.load(ROOT / "packs" / "minimal"), wrapper)
        self.assertIsNotNone(child._proc.poll())
        self.assertFalse(pathlib.Path(child._cwd).exists())
