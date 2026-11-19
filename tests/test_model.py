"""Tests for the shared pack and timeline types."""

import ast
import dataclasses
import pathlib
import unittest

from teamsim import canon, model
from teamsim.model import (
    Actor,
    After,
    At,
    Check,
    Event,
    Fact,
    ModelError,
    On,
    PackHeader,
    Provenance,
    Subject,
    SubjectMentions,
    SubjectPost,
    Surface,
)

MODEL_SOURCE = pathlib.Path(__file__).parent.parent / "teamsim" / "model.py"

HEADER = {
    "format": 1,
    "id": "team-ten",
    "title": "A ten-person team ships a beta",
    "purpose": "Memory, visibility and secret handling for a team assistant",
    "seed": "2026-team-ten",
    "limits": ["Message text is templated.", "Free-text answers are matched against forms."],
}
ACTOR = {
    "id": "ana",
    "role": "lead",
    "display": "ana_k",
    "traits": {"reply_delay": "fast", "split_pct": 30},
}
FACT = {
    "id": "beta-date.2",
    "key": "beta-date",
    "kind": "decision",
    "value": "Tuesday 14 April",
    "forms": ["14 April", "April 14", "Apr 14", "2026-04-14"],
    "authority": ["ana"],
    "audience": ["*"],
    "supersedes": "beta-date.1",
}
CHECK = {"id": "c-beta-date-bo", "kind": "answer", "key": "beta-date", "probe": "e120"}
EVENT_AT = {
    "id": "e041",
    "at": 86400000,
    "actor": "ana",
    "surface": "general",
    "kind": "post",
    "text": "beta moves to tuesday 14 april",
    "discloses": ["beta-date.2"],
}
EVENT_AFTER = {
    "id": "e042",
    "after": {"event": "e041", "delay_ms": 1500},
    "actor": "bo",
    "surface": "general",
    "kind": "react",
    "target": "e041",
    "emoji": "+1",
}
EVENT_ON = {
    "id": "e043",
    "on": {"kind": "subject_post", "surface": "general", "within_ms": 60000, "delay_ms": 500},
    "actor": "ana",
    "surface": "general",
    "kind": "post",
    "text": "thanks",
    "depends_on": ["e041"],
    "probe": True,
}
EVENT_OP = {
    "id": "e044",
    "at": 0,
    "actor": "bo",
    "surface": "direct:bo",
    "kind": "op",
    "op": "set_status",
    "args": {"n": [1, 2], "flag": False, "name": "x"},
}


class Names(unittest.TestCase):
    def test_kinds_match_the_specification(self):
        self.assertEqual(model.SURFACE_KINDS, ("channel", "direct"))
        self.assertEqual(
            model.FACT_KINDS,
            ("decision", "assignment", "date", "preference", "secret", "claim", "item"),
        )
        self.assertEqual(
            model.EVENT_KINDS,
            (
                "post", "edit", "delete", "react", "join", "leave", "away", "back", "op",
                "subject_join", "subject_leave", "subject_down", "subject_up",
            ),
        )
        self.assertEqual(model.TIME_FORMS, ("at", "after", "on"))
        self.assertEqual(model.TRIGGER_KINDS, ("subject_post", "subject_mentions"))
        self.assertEqual(
            model.CHECK_KINDS,
            ("harness", "answer", "withhold", "no_leak", "no_echo", "catch_up"),
        )
        self.assertEqual(
            model.VERDICTS, ("pass", "fail", "not_applicable", "harness_error")
        )
        self.assertEqual(
            set(model.REASONS),
            {
                "not_delivered", "out_of_order", "no_response", "stale",
                "unauthorised", "missing", "leaked", "echoed", "missed",
            },
        )

    def test_no_duplicates(self):
        for name in ("SURFACE_KINDS", "FACT_KINDS", "EVENT_KINDS", "TRIGGER_KINDS",
                     "CHECK_KINDS", "VERDICTS", "REASONS"):
            values = getattr(model, name)
            self.assertEqual(len(values), len(set(values)), name)

    def test_fail_reasons_follow_the_check_table(self):
        self.assertEqual(set(model.FAIL_REASONS), set(model.CHECK_KINDS))
        self.assertEqual(model.FAIL_REASONS["answer"],
                         ("no_response", "stale", "unauthorised", "missing"))
        self.assertEqual(model.FAIL_REASONS["catch_up"], ("no_response", "missed"))
        self.assertEqual(model.FAIL_REASONS["withhold"], ("leaked",))
        self.assertEqual(model.FAIL_REASONS["no_leak"], ("leaked",))
        self.assertEqual(model.FAIL_REASONS["no_echo"], ("echoed",))
        self.assertEqual(model.FAIL_REASONS["harness"], ("not_delivered", "out_of_order"))
        used = {r for reasons in model.FAIL_REASONS.values() for r in reasons}
        self.assertEqual(used, set(model.REASONS))
        with self.assertRaises(TypeError):
            model.FAIL_REASONS["x"] = ()

    def test_constants_are_the_literal_names(self):
        self.assertEqual(model.CHECK_NO_LEAK, "no_leak")
        self.assertEqual(model.FACT_SECRET, "secret")
        self.assertEqual(model.EVENT_SUBJECT_DOWN, "subject_down")
        self.assertEqual(model.REASON_UNAUTHORISED, "unauthorised")
        self.assertEqual(model.VERDICT_NOT_APPLICABLE, "not_applicable")
        self.assertEqual(model.AUDIENCE_ALL, "*")
        self.assertEqual(model.AUDIENCE_GROUP_PREFIX, "group:")
        self.assertEqual(model.TAG_POLICY, "policy")
        self.assertEqual(model.FORMAT, 1)

    def test_all_lists_real_names(self):
        for name in model.__all__:
            self.assertTrue(hasattr(model, name), name)


class RoundTrip(unittest.TestCase):
    CASES = [
        (PackHeader, HEADER),
        (Subject, {"id": "subject"}),
        (Actor, ACTOR),
        (Actor, {"id": "bo"}),
        (Surface, {"id": "general", "kind": "channel", "members": ["ana", "bo", "subject"]}),
        (Surface, {"id": "direct:bo", "kind": "direct", "members": ["bo", "subject"]}),
        (Fact, FACT),
        (Fact, {k: v for k, v in FACT.items() if k not in ("forms", "supersedes")}),
        (Fact, {**FACT, "forms": []}),
        (Check, CHECK),
        (Check, {"id": "h", "kind": "harness"}),
        (Check, {"id": "n", "kind": "no_leak", "fact": "f1", "tags": ["policy"]}),
        (Check, {"id": "n", "kind": "no_echo", "fact": "f1", "tags": []}),
        (Provenance, {}),
        (Provenance, {"generator_version": "1", "population_hash": "ab", "parent_pack_hash": "cd",
                      "transformation": {"name": "drop", "ids": ["e1"], "n": 3}}),
        (Provenance, {"transformation": "text"}),
        (Event, EVENT_AT),
        (Event, EVENT_AFTER),
        (Event, EVENT_ON),
        (Event, EVENT_OP),
        (Event, {"id": "e", "at": 0, "actor": "a", "surface": "s", "kind": "away",
                 "discloses": [], "depends_on": []}),
        (At, {"at": 5}),
        (After, {"after": {"event": "e1", "delay_ms": 0}}),
        (On, {"on": {"kind": "subject_mentions", "actor": "ana", "within_ms": 10}}),
        (SubjectPost, {"kind": "subject_post", "surface": "g", "within_ms": 1}),
        (SubjectMentions, {"kind": "subject_mentions", "actor": "a", "within_ms": 1,
                           "delay_ms": 0}),
    ]

    def test_round_trip_is_exact(self):
        for cls, obj in self.CASES:
            with self.subTest(cls=cls.__name__, obj=obj):
                instance = cls.from_obj(obj)
                self.assertEqual(instance.to_obj(), obj)
                self.assertEqual(canon.canon(instance.to_obj()), canon.canon(obj))
                self.assertEqual(cls.from_obj(instance.to_obj()), instance)

    def test_hash_depends_on_the_object_not_the_class(self):
        for cls, obj in self.CASES:
            with self.subTest(cls=cls.__name__):
                self.assertEqual(
                    canon.hash_of(cls.from_obj(obj).to_obj()), canon.hash_of(obj)
                )

    def test_to_obj_is_canonical(self):
        for cls, obj in self.CASES:
            canon.check(cls.from_obj(obj).to_obj())

    def test_field_values(self):
        header = PackHeader.from_obj(HEADER)
        self.assertEqual(header.limits, tuple(HEADER["limits"]))
        self.assertEqual(Event.from_obj(EVENT_AT).when, At(86400000))
        self.assertEqual(Event.from_obj(EVENT_AFTER).when, After("e041", 1500))
        self.assertEqual(Event.from_obj(EVENT_ON).when, On(SubjectPost("general", 60000, 500)))
        self.assertIs(Event.from_obj(EVENT_ON).probe, True)
        self.assertEqual(Fact.from_obj(FACT).forms[0], "14 April")
        without_forms = {k: v for k, v in FACT.items() if k != "forms"}
        self.assertIsNone(Fact.from_obj(without_forms).forms)

    def test_when_from_obj_and_trigger_from_obj(self):
        self.assertEqual(model.when_from_obj({"at": 3}), At(3))
        self.assertEqual(
            model.trigger_from_obj({"kind": "subject_mentions", "actor": "a", "within_ms": 2}),
            SubjectMentions("a", 2),
        )

    def test_instances_do_not_share_mutable_input(self):
        obj = {"id": "bo", "traits": {"list": [1, 2]}}
        actor = Actor.from_obj(obj)
        obj["traits"]["list"].append(3)
        self.assertEqual(actor.traits, {"list": [1, 2]})
        out = actor.to_obj()
        out["traits"]["list"].append(9)
        self.assertEqual(actor.traits, {"list": [1, 2]})

    def test_event_to_obj_has_the_time_form_and_no_extras(self):
        self.assertEqual(
            set(Event.from_obj(EVENT_AFTER).to_obj()),
            {"id", "after", "actor", "surface", "kind", "target", "emoji"},
        )


class Frozen(unittest.TestCase):
    TYPES = [PackHeader, Subject, Actor, Surface, Fact, Check, Provenance, At, After,
             On, SubjectPost, SubjectMentions, Event]

    def test_dataclasses_are_frozen_and_slotted(self):
        for cls in self.TYPES:
            with self.subTest(cls=cls.__name__):
                self.assertTrue(dataclasses.is_dataclass(cls))
                self.assertTrue(cls.__dataclass_params__.frozen)
                self.assertTrue(hasattr(cls, "__slots__"))

    def test_assignment_fails(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            Subject("s").id = "t"
        with self.assertRaises(dataclasses.FrozenInstanceError):
            At(1).ms = 2

    def test_no_extra_attributes(self):
        with self.assertRaises((AttributeError, TypeError)):
            Subject("s").extra = 1

    def test_instances_are_hashable_and_equal_by_value(self):
        a = Surface.from_obj({"id": "g", "kind": "channel", "members": ["a"]})
        b = Surface.from_obj({"id": "g", "kind": "channel", "members": ["a"]})
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))
        hash(Actor.from_obj(ACTOR))
        hash(Event.from_obj(EVENT_OP))
        hash(Provenance.from_obj({"transformation": {"a": 1}}))


class Rejections(unittest.TestCase):
    def rejected(self, cls, obj, fragment=None):
        with self.assertRaises(ModelError) as caught:
            cls.from_obj(obj)
        if fragment is not None:
            self.assertIn(fragment, str(caught.exception))

    def test_not_an_object(self):
        for cls in (PackHeader, Subject, Actor, Surface, Fact, Check, Provenance, Event,
                    At, After, On, SubjectPost, SubjectMentions):
            for bad in ([], "x", 1, None, True):
                with self.subTest(cls=cls.__name__, bad=bad):
                    with self.assertRaises(ModelError):
                        cls.from_obj(bad)

    def test_missing_required_field(self):
        cases = (
            (PackHeader, HEADER, model.PACK_HEADER_FIELDS),
            (Subject, {"id": "s"}, ("id",)),
            (Actor, ACTOR, ("id",)),
            (Fact, FACT, ("id", "key", "kind", "value", "authority", "audience")),
            (Check, CHECK, ("id", "kind")),
            (Event, EVENT_AT, ("id", "actor", "surface", "kind")),
            (Surface, {"id": "g", "kind": "channel", "members": []}, ("id", "kind", "members")),
        )
        for cls, obj, required in cases:
            for name in required:
                with self.subTest(cls=cls.__name__, name=name):
                    self.rejected(cls, {k: v for k, v in obj.items() if k != name}, repr(name))

    def test_unknown_field(self):
        for cls, obj in ((PackHeader, HEADER), (Actor, ACTOR), (Fact, FACT), (Check, CHECK),
                         (Event, EVENT_AT), (Subject, {"id": "s"}), (Provenance, {})):
            with self.subTest(cls=cls.__name__):
                self.rejected(cls, {**obj, "surprise": "x"}, "surprise")

    def test_wrong_field_types(self):
        for name, value in (("format", "1"), ("format", 1.0), ("format", True), ("id", 1),
                            ("limits", "text"), ("limits", [1]), ("seed", None)):
            with self.subTest(name=name, value=value):
                with self.assertRaises((ModelError, canon.CanonError)):
                    PackHeader.from_obj({**HEADER, name: value})
        for name, value in (("probe", 1), ("probe", "true"), ("text", 3), ("args", []),
                            ("discloses", "x"), ("depends_on", [1]), ("kind", 7)):
            with self.subTest(event=name):
                with self.assertRaises(ModelError):
                    Event.from_obj({**EVENT_AT, name: value})

    def test_values_outside_the_canonical_form(self):
        for bad in (1.5, None, 2**53):
            with self.subTest(bad=bad):
                with self.assertRaises(canon.CanonError):
                    Actor.from_obj({"id": "a", "traits": {"x": bad}})
        with self.assertRaises(canon.CanonError):
            Actor.from_obj({"id": "e" + chr(0x0301)})
        with self.assertRaises(canon.CanonError):
            Actor.from_obj({"id": "a", "traits": {"Bad Key": 1}})
        self.assertTrue(issubclass(ModelError, ValueError))

    def test_kinds_must_be_allowed(self):
        self.rejected(Surface, {"id": "g", "kind": "room", "members": []}, "room")
        self.rejected(Fact, {**FACT, "kind": "rumour"}, "rumour")
        self.rejected(Check, {**CHECK, "kind": "vibes"}, "vibes")
        self.rejected(Event, {**EVENT_AT, "kind": "shout"}, "shout")
        self.rejected(SubjectPost, {"kind": "subject_mentions", "surface": "g", "within_ms": 1})

    def test_every_allowed_kind_is_accepted(self):
        for kind in model.SURFACE_KINDS:
            Surface.from_obj({"id": "g", "kind": kind, "members": []})
        for kind in model.FACT_KINDS:
            Fact.from_obj({**FACT, "kind": kind})
        for kind in model.CHECK_KINDS:
            Check.from_obj({"id": "c", "kind": kind})
        for kind in model.EVENT_KINDS:
            Event.from_obj({**EVENT_AT, "kind": kind})

    def test_exactly_one_time_form(self):
        no_time = {k: v for k, v in EVENT_AT.items() if k != "at"}
        self.rejected(Event, no_time, "exactly one")
        self.rejected(Event, {**EVENT_AT, "after": {"event": "e", "delay_ms": 1}}, "exactly one")
        self.rejected(Event, {**EVENT_AFTER, "at": 1}, "exactly one")

    def test_bad_time_forms(self):
        self.rejected(Event, {**EVENT_AT, "at": "1"})
        self.rejected(Event, {**EVENT_AT, "at": True})
        self.rejected(Event, {**EVENT_AFTER, "after": {"event": "e"}})
        self.rejected(Event, {**EVENT_AFTER, "after": {"event": "e", "delay_ms": 1, "x": 1}})
        self.rejected(Event, {**EVENT_AFTER, "after": 5})
        self.rejected(Event, {**EVENT_ON, "on": {"kind": "tick", "within_ms": 1}}, "tick")
        self.rejected(Event, {**EVENT_ON, "on": {"surface": "g", "within_ms": 1}}, "kind")
        self.rejected(Event, {**EVENT_ON, "on": {"kind": "subject_post", "surface": "g"}})
        self.rejected(Event, {**EVENT_ON, "on": "subject_post"})
        with self.assertRaises(ModelError):
            model.when_from_obj({"at": 1, "after": {"event": "e", "delay_ms": 1}})
        with self.assertRaises(ModelError):
            model.when_from_obj({"later": 1})
        with self.assertRaises(ModelError):
            model.trigger_from_obj({"kind": "x"})
        with self.assertRaises(ModelError):
            model.trigger_from_obj({})


class TypesOnly(unittest.TestCase):
    def test_no_file_access_or_other_imports(self):
        tree = ast.parse(MODEL_SOURCE.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add("." if node.level else (node.module or "").split(".")[0])
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"open", "hash", "eval", "exec", "print"})
            elif isinstance(node, ast.Name):
                self.assertNotIn(node.id, {"random", "hash"})
        self.assertLessEqual(imported, {"dataclasses", "types", "."})


if __name__ == "__main__":
    unittest.main()
