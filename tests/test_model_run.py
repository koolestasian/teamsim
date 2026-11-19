"""Tests for the run-time types: log entries, verdicts, the record header and a reply."""

import dataclasses
import unittest

from teamsim import canon, model
from teamsim.model import (
    Action,
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

ACTION = {
    "kind": "result",
    "surface": "direct:bo",
    "text": "3 open items",
    "data": {"count": 3, "items": ["a", "b", "c"]},
    "reply_to": "e17",
}
DELIVERY = {
    "type": "delivery",
    "n": 4,
    "t_ms": 60000,
    "kind": "post",
    "event": "e17",
    "actor": "bo",
    "surface": "general",
    "recipients": ["ana", "bo"],
    "seq": 3,
}
TICK = {"type": "delivery", "n": 9, "t_ms": 90000, "kind": "tick", "recipients": [], "seq": 7}
OBS_ACTION = {
    "type": "observation",
    "n": 5,
    "t_ms": 60000,
    "seq": 3,
    "kind": "action",
    "action": ACTION,
    "readers": ["bo"],
}
OBS_READY = {
    "type": "observation",
    "n": 2,
    "t_ms": 0,
    "seq": 0,
    "kind": "ready",
    "name": "naive_bot",
    "version": "1",
}
OBS_DONE = {"type": "observation", "n": 6, "t_ms": 60000, "seq": 3, "kind": "done", "wake_at_ms": 90000}
OBS_REJECTED = {
    "type": "observation",
    "n": 7,
    "t_ms": 60000,
    "seq": 3,
    "kind": "subject_error",
    "action": {"kind": "post", "surface": "secret-room", "text": "hi"},
    "code": "rejected_action",
    "detail": "not a member of secret-room",
}
OBS_STALLED = {
    "type": "observation",
    "n": 8,
    "t_ms": 60000,
    "seq": 3,
    "kind": "subject_stalled",
    "code": "timeout",
}
NOTE = {"type": "note", "n": 1, "t_ms": 0, "code": "start"}
NOTE_SHUTDOWN = {"type": "note", "n": 10, "t_ms": 99000, "code": "shutdown", "detail": "end_of_run"}
NOTE_NOT_FIRED = {"type": "note", "n": 11, "t_ms": 99000, "code": "not_fired", "event": "e30"}
VERDICT_FAIL = {
    "type": "verdict",
    "check": "c-answer-budget",
    "kind": "answer",
    "verdict": "fail",
    "reason": "stale",
    "events": ["e12", "e17"],
    "entries": [5],
    "detail": ["budget"],
    "policy": False,
}
VERDICT_PASS = {
    "type": "verdict",
    "check": "c-harness",
    "kind": "harness",
    "verdict": "pass",
    "events": [],
    "entries": [],
    "detail": [],
    "policy": True,
}
HEADER = {
    "type": "header",
    "format": 1,
    "engine": "0.1.0",
    "pack_id": "minimal",
    "pack_hash": "ab" * 32,
    "seed": "minimal-1",
    "subject": {"builtin": "null"},
    "mode": "scripted",
    "limits": ["Message text is templated."],
}

CASES = [
    (Action, ACTION),
    (Action, {"kind": "post", "surface": "general", "text": ""}),
    (Delivery, DELIVERY),
    (Delivery, TICK),
    (Delivery, {"type": "delivery", "n": 1, "t_ms": 0, "kind": "join", "event": "e1",
                "actor": "ana", "surface": "general", "recipients": ["ana"]}),
    (Observation, OBS_ACTION),
    (Observation, OBS_READY),
    (Observation, OBS_DONE),
    (Observation, OBS_REJECTED),
    (Observation, OBS_STALLED),
    (Note, NOTE),
    (Note, NOTE_SHUTDOWN),
    (Note, NOTE_NOT_FIRED),
    (Verdict, VERDICT_FAIL),
    (Verdict, VERDICT_PASS),
    (RecordHeader, HEADER),
]


class Names(unittest.TestCase):
    def test_protocol_literals(self):
        self.assertEqual(model.OBS_ERROR, "subject_error")
        self.assertEqual(model.OBS_STALLED, "subject_stalled")
        self.assertEqual(model.TICK, "tick")
        self.assertEqual(model.ACTION_KINDS, ("post", "react", "result"))
        self.assertEqual(model.SHUTDOWN_REASONS, ("end_of_run", "error", "watchdog"))
        self.assertEqual(model.MODE_SCRIPTED, "scripted")
        self.assertEqual(model.RECORD_FORMAT, 1)

    def test_violation_code_sets(self):
        codes = set(model.VIOLATION_CODES)
        self.assertEqual(len(codes), len(model.VIOLATION_CODES))
        self.assertLessEqual(model.ENDS_SESSION, codes)
        self.assertLessEqual(model.STALL_CODES, codes)
        rejected = {"late_action", "wrong_in_reply_to", "rejected_action"}
        self.assertFalse(rejected & model.ENDS_SESSION)
        self.assertNotIn("no_exit", model.ENDS_SESSION)
        self.assertNotIn("output_after_shutdown", model.ENDS_SESSION)

    def test_tick_is_not_a_pack_event_kind(self):
        self.assertNotIn(model.TICK, model.EVENT_KINDS)

    def test_entry_type_names_are_distinct(self):
        names = [
            model.ENTRY_HEADER,
            model.ENTRY_DELIVERY,
            model.ENTRY_OBSERVATION,
            model.ENTRY_NOTE,
            model.ENTRY_VERDICT,
            model.ENTRY_DIGEST,
        ]
        self.assertEqual(len(set(names)), len(names))


class RoundTrip(unittest.TestCase):
    def test_round_trip_is_exact(self):
        for cls, obj in CASES:
            with self.subTest(cls=cls.__name__, obj=obj):
                self.assertEqual(cls.from_obj(obj).to_obj(), obj)

    def test_to_obj_is_canonical(self):
        for cls, obj in CASES:
            with self.subTest(cls=cls.__name__):
                canon.check(cls.from_obj(obj).to_obj())

    def test_entry_from_obj_chooses_the_type(self):
        for obj, cls in [(DELIVERY, Delivery), (OBS_ACTION, Observation), (NOTE, Note)]:
            entry = entry_from_obj(obj)
            self.assertIs(type(entry), cls)
            self.assertEqual(entry.to_obj(), obj)

    def test_entry_from_obj_rejects_other_types(self):
        for obj in [VERDICT_PASS, HEADER, {"type": "digest", "digest": "x"}, {}, [], "note"]:
            with self.subTest(obj=obj), self.assertRaises(ModelError):
                entry_from_obj(obj)

    def test_frozen_and_slotted(self):
        for cls, obj in CASES:
            item = cls.from_obj(obj)
            self.assertTrue(dataclasses.is_dataclass(item))
            with self.assertRaises(dataclasses.FrozenInstanceError):
                setattr(item, dataclasses.fields(item)[0].name, None)
            self.assertFalse(hasattr(item, "__dict__"))

    def test_instances_do_not_share_mutable_input(self):
        obj = {**ACTION, "data": {"items": ["a"]}}
        action = Action.from_obj(obj)
        obj["data"]["items"].append("b")
        self.assertEqual(action.data, {"items": ["a"]})
        out = action.to_obj()
        out["data"]["items"].append("c")
        self.assertEqual(action.data, {"items": ["a"]})

    def test_nested_action_is_typed(self):
        obs = Observation.from_obj(OBS_ACTION)
        self.assertIsInstance(obs.action, Action)
        self.assertEqual(obs.action.reply_to, "e17")

    def test_run_result_lines_order_and_digest_last(self):
        result = RunResult(
            header=RecordHeader.from_obj(HEADER),
            entries=(Note.from_obj(NOTE), Delivery.from_obj(DELIVERY)),
            verdicts=(Verdict.from_obj(VERDICT_PASS),),
            digest="cd" * 32,
        )
        lines = result.lines()
        self.assertEqual(
            [line["type"] for line in lines],
            ["header", "note", "delivery", "verdict", "digest"],
        )
        self.assertEqual(lines[-1], {"type": "digest", "digest": "cd" * 32})
        canon.check(lines)

    def test_reply_defaults(self):
        reply = Reply(end=model.REPLY_DONE)
        self.assertEqual(reply.items, ())
        self.assertIsNone(reply.wake_at_ms)
        mixed = Reply(
            end=model.REPLY_ENDED,
            items=(Action.from_obj(ACTION), Fault(model.CODE_TOO_MANY_ACTIONS)),
        )
        self.assertIsInstance(mixed.items[-1], Fault)
        self.assertIn(mixed.end, model.REPLY_ENDS)


class Rejects(unittest.TestCase):
    def test_unknown_field(self):
        for cls, obj in CASES:
            with self.subTest(cls=cls.__name__), self.assertRaises(ModelError):
                cls.from_obj({**obj, "wall_ms": 12})

    def test_missing_required_field(self):
        for cls, obj, name in [
            (Delivery, DELIVERY, "recipients"),
            (Observation, OBS_DONE, "seq"),
            (Note, NOTE, "code"),
            (Verdict, VERDICT_PASS, "policy"),
            (RecordHeader, HEADER, "pack_hash"),
            (Action, ACTION, "text"),
        ]:
            broken = {k: v for k, v in obj.items() if k != name}
            with self.subTest(cls=cls.__name__, name=name), self.assertRaises(ModelError):
                cls.from_obj(broken)

    def test_wrong_type_tag(self):
        for cls, obj in CASES:
            if "type" not in obj:
                continue
            with self.subTest(cls=cls.__name__), self.assertRaises(ModelError):
                cls.from_obj({**obj, "type": "something_else"})

    def test_bad_kinds_and_codes(self):
        bad = [
            (Action, {**ACTION, "kind": "delete"}),
            (Delivery, {**DELIVERY, "kind": "wave"}),
            (Observation, {**OBS_DONE, "kind": "log"}),
            (Observation, {**OBS_STALLED, "code": "made_up"}),
            (Note, {**NOTE, "code": "made_up"}),
            (Verdict, {**VERDICT_PASS, "kind": "vibes"}),
            (Verdict, {**VERDICT_PASS, "verdict": "maybe"}),
            (RecordHeader, {**HEADER, "mode": "recorded"}),
        ]
        for cls, obj in bad:
            with self.subTest(cls=cls.__name__, obj=obj), self.assertRaises(ModelError):
                cls.from_obj(obj)

    def test_wrong_field_types(self):
        bad = [
            (Delivery, {**DELIVERY, "seq": "3"}),
            (Delivery, {**DELIVERY, "recipients": "ana"}),
            (Observation, {**OBS_ACTION, "readers": [1]}),
            (Observation, {**OBS_ACTION, "action": "post hi"}),
            (Verdict, {**VERDICT_FAIL, "entries": ["5"]}),
            (Verdict, {**VERDICT_FAIL, "policy": 0}),
            (RecordHeader, {**HEADER, "subject": "null"}),
            (Action, {**ACTION, "data": ["not", "an", "object"]}),
        ]
        for cls, obj in bad:
            with self.subTest(cls=cls.__name__, obj=obj), self.assertRaises(ModelError):
                cls.from_obj(obj)

    def test_verdict_reason_rules(self):
        with self.assertRaises(ModelError):
            Verdict.from_obj({**VERDICT_FAIL, "reason": "leaked"})  # not an answer reason
        with self.assertRaises(ModelError):
            Verdict.from_obj({k: v for k, v in VERDICT_FAIL.items() if k != "reason"})
        with self.assertRaises(ModelError):
            Verdict.from_obj({**VERDICT_PASS, "reason": "stale"})
        for kind, reasons in model.FAIL_REASONS.items():
            for reason in reasons:
                obj = {**VERDICT_FAIL, "kind": kind, "reason": reason}
                self.assertEqual(Verdict.from_obj(obj).to_obj(), obj)

    def test_not_canonical(self):
        with self.assertRaises(canon.CanonError):
            Delivery.from_obj({**DELIVERY, "t_ms": 1.5})


if __name__ == "__main__":
    unittest.main()
