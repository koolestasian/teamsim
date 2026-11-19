"""Tests for the pack loader, hash and writer, and the rules of pack format 1."""

import copy
import dataclasses
import json
import pathlib
import re
import tempfile
import tomllib
import unittest
from unittest import mock

from teamsim import canon, model, pack
from teamsim.pack import PackError

ROOT = pathlib.Path(__file__).parent.parent
MINIMAL = ROOT / "packs" / "minimal"
DOC = ROOT / "docs" / "spec" / "pack-format.md"

# Pinned: the hash of packs/minimal. A change to the pack, the canonical form or the
# hash definition changes it on purpose, never by accident.
MINIMAL_HASH = "f20422fcec9c7a9645a60fc80bc8879151c6bade2f0ec581bb918f95c256b7fe"

BASE_TOML = tomllib.loads((MINIMAL / "pack.toml").read_text(encoding="utf-8"))
BASE_EVENTS = [
    json.loads(line)
    for line in (MINIMAL / "timeline.jsonl").read_text(encoding="utf-8").splitlines()
]


def dump_toml(obj, reverse=False, comments=False):
    """Write a plain object as pack.toml text; a different but equal spelling."""
    key = pack._toml_string
    pairs = list(obj.items())
    scalars = [(k, v) for k, v in pairs if type(v) is not dict and not _is_tables(v)]
    tables = [(k, v) for k, v in pairs if type(v) is dict]
    arrays = [(k, v) for k, v in pairs if _is_tables(v)]
    if reverse:
        scalars.reverse()
        tables.reverse()
        arrays.reverse()
    out = []
    if comments:
        out.append("# a comment before everything")
    for k, v in scalars:
        out.append(f"{key(k)} = {pack._toml_value(v)}" + ("  # trailing" if comments else ""))
    for k, v in tables:
        out.append("")
        out.append(f"[{key(k)}]")
        items = list(v.items())
        out.extend(f"{key(a)} = {pack._toml_value(b)}" for a, b in (reversed(items) if reverse else items))
    for k, v in arrays:
        for item in v:
            out.append("")
            out.append(f"[[{key(k)}]]")
            items = list(item.items())
            out.extend(
                f"{key(a)} = {pack._toml_value(b)}" for a, b in (reversed(items) if reverse else items)
            )
    return "\n".join(out) + "\n"


def _is_tables(value):
    return type(value) is list and bool(value) and all(type(i) is dict for i in value)


def rules_section():
    text = DOC.read_text(encoding="utf-8")
    return text.split("<!-- rules:start -->")[1].split("<!-- rules:end -->")[0]


def event(events, event_id):
    return next(e for e in events if e["id"] == event_id)


def table(obj, name, item_id):
    return next(t for t in obj[name] if t["id"] == item_id)


class TempCase(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.tmp = pathlib.Path(holder.name)
        self.counter = 0

    def fresh(self):
        self.counter += 1
        path = self.tmp / f"p{self.counter}"
        path.mkdir()
        return path

    def make(self, toml=None, events=None, toml_text=None, timeline_text=None):
        """Write a pack directory from the base pack with edits applied."""
        path = self.fresh()
        obj = copy.deepcopy(BASE_TOML)
        evs = copy.deepcopy(BASE_EVENTS)
        if toml is not None:
            toml(obj)
        if events is not None:
            events(evs)
        text = toml_text if toml_text is not None else dump_toml(obj)
        lines = (
            timeline_text
            if timeline_text is not None
            else "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in evs)
        )
        (path / "pack.toml").write_bytes(text.encode("utf-8") if isinstance(text, str) else text)
        (path / "timeline.jsonl").write_bytes(
            lines.encode("utf-8") if isinstance(lines, str) else lines
        )
        return path

    def fails(self, code, **edits):
        path = self.make(**edits)
        with self.assertRaises(PackError) as caught:
            pack.load(path)
        self.assertEqual(caught.exception.code, code, str(caught.exception))
        return caught.exception

    def loads(self, **edits):
        return pack.load(self.make(**edits))


class MinimalPack(TempCase):
    def test_loads_and_hash_is_pinned(self):
        loaded = pack.load(MINIMAL)
        self.assertEqual(pack.pack_hash(loaded), MINIMAL_HASH)

    def test_uses_every_construct(self):
        loaded = pack.load(MINIMAL)
        self.assertEqual({e.kind for e in loaded.events}, set(model.EVENT_KINDS))
        self.assertEqual({type(e.when) for e in loaded.events}, {model.At, model.After, model.On})
        self.assertEqual(
            {type(e.when.trigger) for e in loaded.events if isinstance(e.when, model.On)},
            {model.SubjectPost, model.SubjectMentions},
        )
        self.assertEqual({c.kind for c in loaded.checks}, set(model.CHECK_KINDS))
        self.assertEqual({s.kind for s in loaded.surfaces}, set(model.SURFACE_KINDS))
        self.assertTrue(any(f.supersedes for f in loaded.facts))
        self.assertTrue(any(f.kind == model.FACT_SECRET for f in loaded.facts))
        self.assertTrue(any(f.kind == model.FACT_CLAIM for f in loaded.facts))
        self.assertTrue(any(a.startswith("group:") for f in loaded.facts for a in f.audience))
        self.assertTrue(any(e.depends_on for e in loaded.events))
        self.assertTrue(any(e.args for e in loaded.events))
        self.assertTrue(any(not c.isascii() for e in loaded.events for c in (e.text or "")))
        self.assertIsNotNone(loaded.provenance)
        self.assertTrue(any(a.traits for a in loaded.actors))
        self.assertTrue(any(c.tags for c in loaded.checks))

    def test_hash_matches_the_definition(self):
        loaded = pack.load(MINIMAL)
        expected = canon.hash_of({"pack": BASE_TOML, "timeline": BASE_EVENTS})
        # The loader's object equals the TOML read directly, once the four arrays exist.
        self.assertEqual(loaded.to_obj(), BASE_TOML)
        self.assertEqual(pack.pack_hash(loaded), expected)


class WorkedExample(unittest.TestCase):
    """The worked example in the document is checked, not just printed."""

    def block(self, label):
        text = DOC.read_text(encoding="utf-8")
        match = re.search(
            rf"<!-- worked-example: {re.escape(label)} -->\n```[a-z]*\n(.*?)```", text, re.S
        )
        self.assertIsNotNone(match, label)
        return match.group(1)

    def test_example_hash_and_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "pack.toml").write_bytes(self.block("pack.toml").encode("utf-8"))
            (root / "timeline.jsonl").write_bytes(self.block("timeline.jsonl").encode("utf-8"))
            loaded = pack.load(root)
        canonical = canon.canon({"pack": loaded.to_obj(), "timeline": loaded.timeline_objs()})
        self.assertEqual(canonical.decode("utf-8"), self.block("canonical").rstrip("\n"))
        self.assertEqual(pack.pack_hash(loaded), self.block("hash").strip())


class RoundTrip(TempCase):
    def test_write_then_load_is_equal_and_stable(self):
        first = pack.load(MINIMAL)
        a = self.tmp / "a"
        b = self.tmp / "b"
        pack.write(first, a)
        second = pack.load(a)
        self.assertEqual(second, first)
        self.assertEqual(pack.pack_hash(second), MINIMAL_HASH)
        pack.write(second, b)
        for name in ("pack.toml", "timeline.jsonl"):
            self.assertEqual((a / name).read_bytes(), (b / name).read_bytes(), name)

    def test_written_files_are_plain(self):
        pack.write(pack.load(MINIMAL), self.tmp / "w")
        for name in ("pack.toml", "timeline.jsonl"):
            data = (self.tmp / "w" / name).read_bytes()
            self.assertFalse(data.startswith(b"\xef\xbb\xbf"))
            self.assertNotIn(b"\r", data)
            self.assertTrue(data.endswith(b"\n"))
            data.decode("utf-8")

    def test_timeline_lines_are_canonical(self):
        pack.write(pack.load(MINIMAL), self.tmp / "w")
        for line in (self.tmp / "w" / "timeline.jsonl").read_bytes().split(b"\n")[:-1]:
            self.assertEqual(canon.canon(canon.parse(line)), line)

    def test_write_creates_the_directory_and_overwrites(self):
        target = self.tmp / "deep" / "er"
        pack.write(pack.load(MINIMAL), target)
        pack.write(pack.load(MINIMAL), target)
        self.assertEqual(pack.pack_hash(pack.load(target)), MINIMAL_HASH)

    def test_write_refuses_an_invalid_pack(self):
        loaded = pack.load(MINIMAL)
        bad = dataclasses.replace(loaded, events=loaded.events[:-1] + (
            dataclasses.replace(loaded.events[-1], actor="nobody", kind="post", text="x"),
        ))
        with self.assertRaises(PackError):
            pack.write(bad, self.tmp / "never")
        self.assertFalse((self.tmp / "never").exists())

    def test_reordered_keys_and_comments_keep_the_hash(self):
        for reverse, comments in ((True, False), (False, True), (True, True)):
            text = dump_toml(BASE_TOML, reverse=reverse, comments=comments)
            events = [dict(reversed(list(e.items()))) if reverse else e for e in BASE_EVENTS]
            loaded = self.loads(
                toml_text=text,
                timeline_text="".join(json.dumps(e) + "\n" for e in events),
            )
            self.assertEqual(pack.pack_hash(loaded), MINIMAL_HASH, (reverse, comments))

    def test_spaces_and_whitespace_in_timeline_keep_the_hash(self):
        text = "".join(json.dumps(e, indent=None, separators=(", ", ": ")) + "\n" for e in BASE_EVENTS)
        self.assertEqual(pack.pack_hash(self.loads(timeline_text=text)), MINIMAL_HASH)

    def test_an_absent_array_equals_an_empty_one(self):
        def drop(obj):
            obj["checks"] = []

        text = dump_toml({**BASE_TOML, "checks": []}).replace("[[checks]]", "")
        a = self.loads(toml=drop)
        self.assertEqual(a.checks, ())
        self.assertEqual(self.loads(toml_text=text).checks, ())

    def test_any_single_change_changes_the_hash(self):
        loaded = pack.load(MINIMAL)
        e0 = loaded.events[0]
        changes = {
            "seed": dataclasses.replace(
                loaded, header=dataclasses.replace(loaded.header, seed="other")
            ),
            "limit": dataclasses.replace(
                loaded, header=dataclasses.replace(loaded.header, limits=("x",))
            ),
            "fact value": dataclasses.replace(
                loaded,
                facts=(dataclasses.replace(loaded.facts[0], value="Monday"),) + loaded.facts[1:],
            ),
            "actor trait": dataclasses.replace(
                loaded,
                actors=(dataclasses.replace(loaded.actors[0], traits={"reply_delay": "slow"}),)
                + loaded.actors[1:],
            ),
            "check": dataclasses.replace(loaded, checks=loaded.checks[1:]),
            "event text": dataclasses.replace(
                loaded, events=(dataclasses.replace(e0, text="Plan for demo day: Monday."),) + loaded.events[1:]
            ),
            "event time": dataclasses.replace(
                loaded, events=(dataclasses.replace(e0, when=model.At(1)),) + loaded.events[1:]
            ),
            "event order": dataclasses.replace(
                loaded, events=(loaded.events[1], loaded.events[0]) + loaded.events[2:]
            ),
            "provenance": dataclasses.replace(loaded, provenance=None),
            "probe flag": dataclasses.replace(
                loaded, events=(dataclasses.replace(e0, probe=False),) + loaded.events[1:]
            ),
        }
        seen = {MINIMAL_HASH}
        for name, changed in changes.items():
            digest = pack.pack_hash(changed)
            self.assertNotIn(digest, seen, name)
            seen.add(digest)


class TomlEmitter(unittest.TestCase):
    def read_back(self, value):
        return tomllib.loads(f"v = {pack._toml_value(value)}")["v"]

    def test_strings_survive(self):
        samples = [
            "",
            "plain",
            'quote " and \\ backslash',
            "tab\there",
            "new\nline",
            "bell\x07 nul\x00 esc\x1b del\x7f",
            "café 中文 \U0001f600",
            "  line separator",
            "'single' and \"double\"",
            "[brackets] {braces} # hash = equals",
            "\\u0041 is not an escape here",
        ]
        for text in samples:
            self.assertEqual(self.read_back(text), text, repr(text))

    def test_values_survive(self):
        for value in (
            0,
            -(2**53 - 1),
            2**53 - 1,
            True,
            False,
            [],
            [1, "a", [True]],
            {},
            {"a": 1, "b.c": {"d:e": ["x"]}, "z-z": []},
        ):
            self.assertEqual(self.read_back(value), value)

    def test_rejects_other_types(self):
        for value in (1.5, None, (1,)):
            with self.assertRaises(canon.CanonError):
                pack._toml_value(value)


class Rules(TempCase):
    """One test per rule code, named ``test_rule_<code>``."""

    def test_rule_missing_file(self):
        with self.assertRaises(PackError) as caught:
            pack.load(self.tmp / "absent")
        self.assertEqual(caught.exception.code, "missing_file")
        self.assertEqual(caught.exception.file, "pack.toml")
        path = self.fresh()
        (path / "pack.toml").write_bytes(b"format = 1\n")
        with self.assertRaises(PackError) as caught:
            pack.load(path)
        self.assertEqual(
            (caught.exception.code, caught.exception.file), ("missing_file", "timeline.jsonl")
        )

    def test_rule_bad_text(self):
        error = self.fails("bad_text", toml_text=b"\xef\xbb\xbf" + b"format = 1\n")
        self.assertEqual(error.file, "pack.toml")
        error = self.fails("bad_text", timeline_text=b"\xff\xfe\n")
        self.assertEqual(error.file, "timeline.jsonl")
        self.fails("bad_text", toml_text="format = 1\r\nid = \"x\"\r\n")
        self.fails("bad_text", timeline_text=b"\xef\xbb\xbf" + b'{"id":"a"}\n')
        self.fails("bad_text", timeline_text='{"id":"a"}\r\n')

    def test_rule_limit_exceeded(self):
        with mock.patch.object(pack, "MAX_TOML_BYTES", 100):
            self.assertEqual(self.fails("limit_exceeded").file, "pack.toml")
        with mock.patch.object(pack, "MAX_TIMELINE_BYTES", 100):
            self.assertEqual(self.fails("limit_exceeded").file, "timeline.jsonl")
        lengths = [len(json.dumps(e, ensure_ascii=False).encode("utf-8")) for e in BASE_EVENTS]
        longest = max(lengths)
        with mock.patch.object(pack, "MAX_LINE_BYTES", longest - 1):
            error = self.fails("limit_exceeded")
            self.assertEqual(error.line, lengths.index(longest) + 1)
        with mock.patch.object(pack, "MAX_EVENTS", 5):
            self.fails("limit_exceeded")
        with mock.patch.object(pack, "MAX_ACTORS", 3):
            self.assertEqual(self.fails("limit_exceeded").path, "actors")
        with mock.patch.object(pack, "MAX_FACTS", 3):
            self.fails("limit_exceeded")
        with mock.patch.object(pack, "MAX_SURFACES", 2):
            self.fails("limit_exceeded")
        with mock.patch.object(pack, "MAX_CHECKS", 2):
            self.fails("limit_exceeded")
        error = self.fails(
            "limit_exceeded", events=lambda evs: evs[0].update(at=pack.MAX_TIME_MS + 1)
        )
        self.assertEqual((error.event, error.path), ("e01", "at"))
        error = self.fails(
            "limit_exceeded",
            events=lambda evs: event(evs, "e15")["after"].update(delay_ms=pack.MAX_TIME_MS),
        )
        self.assertEqual(error.event, "e15")

    def test_rule_bad_toml(self):
        self.assertEqual(self.fails("bad_toml", toml_text="format = \n").file, "pack.toml")
        self.fails("bad_toml", toml_text="a = 1\na = 2\n")
        self.fails("bad_toml", toml_text="x = " + "[" * 5000 + "]" * 5000 + "\n")

    def test_rule_non_canonical(self):
        base = dump_toml(BASE_TOML)
        error = self.fails("non_canonical", toml_text="weight = 1.5\n" + base)
        self.assertEqual(error.path, "weight")
        self.fails("non_canonical", toml_text="when = 1979-05-27\n" + base)
        self.fails("non_canonical", toml_text="when = 07:32:00\n" + base)
        self.fails("non_canonical", toml_text="when = 1979-05-27T07:32:00Z\n" + base)
        self.fails("non_canonical", toml_text="big = 9007199254740992\n" + base)
        self.fails("non_canonical", toml_text="deep = " + "[" * 100 + "]" * 100 + "\n" + base)
        self.fails("non_canonical", toml=lambda o: o.update(title="é"))
        error = self.fails("non_canonical", toml=lambda o: o["facts"][0].update(value="é"))
        self.assertEqual(error.path, "facts[0].value")
        self.fails("non_canonical", toml=lambda o: o["actors"][0]["traits"].update({"Bad": "x"}))

    def test_rule_bad_line(self):
        lines = "".join(json.dumps(e) + "\n" for e in BASE_EVENTS).split("\n")
        blank = "\n".join(lines[:2] + [""] + lines[2:])
        error = self.fails("bad_line", timeline_text=blank)
        self.assertEqual(error.line, 3)
        error = self.fails("bad_line", timeline_text=json.dumps(BASE_EVENTS[0]))
        self.assertEqual(error.line, 1)
        error = self.fails("bad_line", timeline_text="[1]\n")
        self.assertEqual(error.line, 1)
        error = self.fails("bad_line", timeline_text=json.dumps(BASE_EVENTS[0]) + "\nnot json\n")
        self.assertEqual(error.line, 2)
        self.fails("bad_line", timeline_text='{"id":"a","at":1.5}\n')
        self.fails("bad_line", timeline_text='{"id":null}\n')
        self.fails("bad_line", timeline_text='{"id":"a"} {"id":"b"}\n')

    def test_rule_unknown_field(self):
        error = self.fails("unknown_field", toml=lambda o: o.update(colour="red"))
        self.assertEqual(error.path, "colour")
        error = self.fails("unknown_field", toml=lambda o: o["actors"][1].update(colour="red"))
        self.assertEqual(error.path, "actors[1].colour")
        self.fails("unknown_field", toml=lambda o: o["subject"].update(name="x"))
        self.fails("unknown_field", toml=lambda o: o["provenance"].update(made_by="x"))
        error = self.fails("unknown_field", events=lambda evs: evs[3].update(colour="red"))
        self.assertEqual((error.line, error.event, error.path), (4, "e04", "colour"))
        self.fails(
            "unknown_field", events=lambda evs: event(evs, "e15")["after"].update(extra=1)
        )
        self.fails(
            "unknown_field", events=lambda evs: event(evs, "e17")["on"].update(extra=1)
        )

    def test_rule_missing_field(self):
        error = self.fails("missing_field", toml=lambda o: o.pop("seed"))
        self.assertEqual(error.path, "seed")
        self.fails("missing_field", toml=lambda o: o.pop("subject"))
        error = self.fails("missing_field", toml=lambda o: o["actors"][2].pop("id"))
        self.assertEqual(error.path, "actors[2].id")
        error = self.fails("missing_field", toml=lambda o: o["checks"][1].pop("kind"))
        self.assertEqual(error.path, "checks[1].kind")
        error = self.fails("missing_field", events=lambda evs: evs[2].pop("actor"))
        self.assertEqual((error.line, error.event, error.path), (3, "e03", "actor"))

    def test_rule_bad_type(self):
        error = self.fails("bad_type", toml=lambda o: o.update(id=5))
        self.assertEqual(error.path, "id")
        self.fails("bad_type", toml=lambda o: o.update(limits="one"))
        self.fails("bad_type", toml=lambda o: o.update(actors={"id": "x"}))
        self.fails("bad_type", toml=lambda o: o["surfaces"][0].update(members="ana"))
        self.fails("bad_type", toml=lambda o: o.update(subject="subject"))
        self.fails("bad_type", toml=lambda o: o.update(format="1"))
        error = self.fails("bad_type", events=lambda evs: evs[0].update(text=7))
        self.assertEqual((error.event, error.path), ("e01", "text"))
        self.fails("bad_type", events=lambda evs: evs[0].update(at="0"))
        self.fails("bad_type", events=lambda evs: evs[0].update(probe=1))

    def test_rule_bad_format(self):
        error = self.fails("bad_format", toml=lambda o: o.update(format=2))
        self.assertEqual(error.path, "format")
        self.fails("bad_format", toml=lambda o: o.update(format=0))

    def test_rule_bad_kind(self):
        error = self.fails("bad_kind", toml=lambda o: o["surfaces"][0].update(kind="room"))
        self.assertEqual(error.path, "surfaces[0].kind")
        self.fails("bad_kind", toml=lambda o: o["facts"][0].update(kind="rumour"))
        self.fails("bad_kind", toml=lambda o: o["checks"][0].update(kind="vibes"))
        error = self.fails("bad_kind", events=lambda evs: evs[0].update(kind="shout"))
        self.assertEqual((error.event, error.path), ("e01", "kind"))
        self.fails("bad_kind", events=lambda evs: event(evs, "e17")["on"].update(kind="subject_sleeps"))

    def test_rule_time_form(self):
        error = self.fails("time_form", events=lambda evs: evs[0].update(on={"kind": "subject_post", "surface": "general", "within_ms": 1}))
        self.assertEqual(error.event, "e01")
        self.fails("time_form", events=lambda evs: evs[0].pop("at"))
        self.fails("time_form", events=lambda evs: evs[0].update(after={"event": "e02", "delay_ms": 0}))

    def test_rule_negative_time(self):
        error = self.fails("negative_time", events=lambda evs: evs[0].update(at=-1))
        self.assertEqual((error.event, error.path), ("e01", "at"))
        error = self.fails(
            "negative_time",
            events=lambda evs: event(evs, "e15")["after"].update(delay_ms=-1),
        )
        self.assertEqual(error.path, "after.delay_ms")
        self.fails("negative_time", events=lambda evs: event(evs, "e17")["on"].update(within_ms=-1))
        self.fails("negative_time", events=lambda evs: event(evs, "e17")["on"].update(delay_ms=-5))

    def test_rule_bad_id(self):
        error = self.fails("bad_id", toml=lambda o: table(o, "actors", "ana").update(id="Ana"))
        self.assertEqual(error.path, "actors[0].id")
        self.fails("bad_id", toml=lambda o: o.update(id="has space"))
        self.fails("bad_id", toml=lambda o: o["subject"].update(id="group:x"))
        self.fails("bad_id", toml=lambda o: o["subject"].update(id="s" * 65))
        self.fails("bad_id", toml=lambda o: o["facts"][0].update(key="Date"))
        self.fails("bad_id", toml=lambda o: o["surfaces"][0].update(id=""))
        error = self.fails("bad_id", events=lambda evs: evs[0].update(id="E 1"))
        self.assertEqual(error.line, 1)
        self.fails("bad_id", toml=lambda o: o["actors"][0].update(id="group:a"))

    def test_rule_duplicate_id(self):
        error = self.fails("duplicate_id", toml=lambda o: o["actors"][1].update(id="ana"))
        self.assertEqual(error.path, "actors[1].id")
        self.fails("duplicate_id", toml=lambda o: o["actors"][1].update(id="subject"))
        self.fails("duplicate_id", toml=lambda o: o["surfaces"][1].update(id="general"))
        self.fails("duplicate_id", toml=lambda o: o["facts"][1].update(id="f.date.1"))
        self.fails("duplicate_id", toml=lambda o: o["checks"][1].update(id="c-harness"))
        error = self.fails("duplicate_id", events=lambda evs: evs[4].update(id="e01"))
        self.assertEqual((error.line, error.event), (5, "e01"))

    def test_rule_unknown_actor(self):
        error = self.fails("unknown_actor", toml=lambda o: o["surfaces"][0]["members"].append("zed"))
        self.assertEqual(error.path, "surfaces[0].members[4]")
        self.fails("unknown_actor", toml=lambda o: o["facts"][0].update(authority=["zed"]))
        self.fails("unknown_actor", toml=lambda o: o["facts"][0].update(audience=["zed"]))
        self.fails("unknown_actor", toml=lambda o: o["facts"][0].update(authority=["subject"]))
        error = self.fails("unknown_actor", events=lambda evs: evs[0].update(actor="zed"))
        self.assertEqual((error.event, error.path), ("e01", "actor"))
        self.fails("unknown_actor", events=lambda evs: event(evs, "e19")["on"].update(actor="zed"))

    def test_rule_unknown_surface(self):
        error = self.fails("unknown_surface", events=lambda evs: evs[0].update(surface="nowhere"))
        self.assertEqual((error.event, error.path), ("e01", "surface"))
        error = self.fails(
            "unknown_surface", toml=lambda o: o["facts"][4].update(audience=["group:nowhere"])
        )
        self.assertEqual(error.path, "facts[4].audience[0]")
        self.fails(
            "unknown_surface", events=lambda evs: event(evs, "e17")["on"].update(surface="nowhere")
        )

    def test_rule_unknown_fact(self):
        error = self.fails("unknown_fact", events=lambda evs: evs[0].update(discloses=["f.zzz"]))
        self.assertEqual((error.event, error.path), ("e01", "discloses"))
        error = self.fails("unknown_fact", toml=lambda o: o["facts"][1].update(supersedes="f.zzz"))
        self.assertEqual(error.path, "facts[1].supersedes")
        error = self.fails("unknown_fact", toml=lambda o: table(o, "checks", "c-budget-withhold").update(fact="f.zzz"))
        self.assertEqual(error.path, "checks[4].fact")

    def test_rule_unknown_event(self):
        error = self.fails(
            "unknown_event",
            events=lambda evs: event(evs, "e15").update(after={"event": "e99", "delay_ms": 0}),
        )
        self.assertEqual((error.event, error.path), ("e15", "after.event"))
        self.fails("unknown_event", events=lambda evs: evs[0].update(depends_on=["e99"]))
        error = self.fails("unknown_event", events=lambda evs: event(evs, "e06").update(target="e99"))
        self.assertEqual(error.path, "target")
        error = self.fails("unknown_event", toml=lambda o: o["checks"][1].update(probe="e99"))
        self.assertEqual(error.path, "checks[1].probe")

    def test_rule_unknown_fact_key(self):
        error = self.fails("unknown_fact_key", toml=lambda o: o["checks"][1].update(key="nothing"))
        self.assertEqual(error.path, "checks[1].key")

    def test_rule_bad_surface(self):
        error = self.fails(
            "bad_surface", toml=lambda o: o["surfaces"][2].update(members=["bo", "cy", "subject"])
        )
        self.assertEqual(error.path, "surfaces[2].members")
        self.fails("bad_surface", toml=lambda o: o["surfaces"][2].update(members=["bo", "cy"]))
        self.fails("bad_surface", toml=lambda o: o["surfaces"][2].update(members=["subject", "subject"]))
        error = self.fails("bad_surface", toml=lambda o: o["surfaces"][0]["members"].append("ana"))
        self.assertEqual(error.path, "surfaces[0].members[4]")
        error = self.fails(
            "bad_surface", events=lambda evs: event(evs, "e20").update(surface="direct:bo", actor="bo")
        )
        self.assertEqual(error.event, "e20")
        error = self.fails("bad_surface", events=lambda evs: event(evs, "e21").update(surface="general", actor="bo"))
        self.assertEqual((error.event, error.path), ("e21", "surface"))
        self.fails(
            "bad_surface",
            events=lambda evs: event(evs, "e08").update(surface="direct:bo"),
        )

    def test_rule_bad_audience(self):
        error = self.fails("bad_audience", toml=lambda o: o["facts"][0].update(audience=[]))
        self.assertEqual(error.path, "facts[0].audience")
        self.fails("bad_audience", toml=lambda o: o["facts"][0].update(audience=["*", "ana"]))
        error = self.fails("bad_audience", toml=lambda o: o["facts"][0].update(audience=["ana", "ana"]))
        self.assertEqual(error.path, "facts[0].audience[1]")

    def test_rule_bad_authority(self):
        error = self.fails("bad_authority", toml=lambda o: o["facts"][0].update(authority=[]))
        self.assertEqual(error.path, "facts[0].authority")
        self.fails("bad_authority", toml=lambda o: o["facts"][0].update(authority=["ana", "ana"]))

    def test_rule_bad_fact(self):
        error = self.fails("bad_fact", toml=lambda o: o["facts"][0].update(value=""))
        self.assertEqual(error.path, "facts[0].value")
        self.fails("bad_fact", toml=lambda o: o["facts"][0].update(forms=["a", ""]))
        error = self.fails("bad_fact", toml=lambda o: o["facts"][0].update(forms=["a", "a"]))
        self.assertEqual(error.path, "facts[0].forms[1]")

    def test_rule_bad_supersedes(self):
        error = self.fails("bad_supersedes", toml=lambda o: o["facts"][1].update(supersedes="f.room"))
        self.assertEqual(error.path, "facts[1].supersedes")
        self.fails("bad_supersedes", toml=lambda o: o["facts"][1].update(supersedes="f.date.2"))

        def two_successors(o):
            o["facts"][2]["supersedes"] = "f.date.1"

        self.fails("bad_supersedes", toml=two_successors)

        def circle(o):
            o["facts"][0]["supersedes"] = "f.claim"
            o["facts"][2]["supersedes"] = "f.date.2"

        self.fails("bad_supersedes", toml=circle)

    def test_rule_bad_actor(self):
        error = self.fails("bad_actor", events=lambda evs: evs[0].update(actor="subject"))
        self.assertEqual((error.event, error.path), ("e01", "actor"))
        error = self.fails("bad_actor", events=lambda evs: event(evs, "e24").update(actor="ana"))
        self.assertEqual(error.event, "e24")

    def test_rule_bad_payload(self):
        error = self.fails("bad_payload", events=lambda evs: evs[0].pop("text"))
        self.assertEqual((error.event, error.path), ("e01", "text"))
        self.fails("bad_payload", events=lambda evs: evs[0].update(target="e02"))
        self.fails("bad_payload", events=lambda evs: evs[0].update(text=""))
        self.fails("bad_payload", events=lambda evs: event(evs, "e03").pop("emoji"))
        self.fails("bad_payload", events=lambda evs: event(evs, "e21").pop("args"))
        self.fails("bad_payload", events=lambda evs: event(evs, "e21").update(text="x"))
        self.fails("bad_payload", events=lambda evs: event(evs, "e03").update(discloses=["f.room"]))
        self.fails("bad_payload", events=lambda evs: event(evs, "e12").update(probe=True))
        self.fails("bad_payload", events=lambda evs: event(evs, "e12").update(text="x"))
        self.fails("bad_payload", events=lambda evs: evs[0].update(discloses=["f.date.1", "f.date.1"]))
        self.fails("bad_payload", events=lambda evs: event(evs, "e07").pop("target"))

    def test_rule_bad_target(self):
        error = self.fails("bad_target", events=lambda evs: event(evs, "e07").update(target="e06"))
        self.assertEqual((error.event, error.path), ("e07", "target"))
        self.fails("bad_target", events=lambda evs: event(evs, "e03").update(target="e09"))
        self.fails("bad_target", events=lambda evs: event(evs, "e06").update(target="e04", actor="cy") if False else event(evs, "e06").update(actor="ana"))

    def test_rule_not_a_member(self):
        error = self.fails("not_a_member", events=lambda evs: event(evs, "e04").update(surface="leads"))
        self.assertEqual((error.event, error.path), ("e04", "actor"))

    def test_rule_dependency_cycle(self):
        def two(evs):
            evs[0]["depends_on"] = ["e02"]
            evs[1]["depends_on"] = ["e01"]

        error = self.fails("dependency_cycle", events=two)
        self.assertEqual(error.event, "e01")
        self.fails("dependency_cycle", events=lambda evs: evs[0].update(depends_on=["e01"]))

        def anchor(evs):
            evs[0].pop("at")
            evs[0]["after"] = {"event": "e02", "delay_ms": 0}
            evs[1].pop("at")
            evs[1]["after"] = {"event": "e01", "delay_ms": 0}

        self.fails("dependency_cycle", events=anchor)

    def test_rule_time_order(self):
        def swap(evs):
            evs[0], evs[1] = evs[1], evs[0]

        error = self.fails("time_order", events=swap)
        self.assertEqual(error.event, "e01")
        self.fails("time_order", events=lambda evs: event(evs, "e07").update(at=120000))
        self.fails("time_order", events=lambda evs: evs[0].update(depends_on=["e02"]))

        def chain(evs):
            # After-chains rooted at a fixed time have a known time too.
            event(evs, "e15").update(after={"event": "e14", "delay_ms": 100000})

        self.fails("time_order", events=chain)

    def test_rule_fact_never_disclosed(self):
        error = self.fails(
            "fact_never_disclosed", events=lambda evs: event(evs, "e13").pop("discloses")
        )
        self.assertEqual(error.path, "facts[1].id")

    def test_rule_not_a_probe(self):
        error = self.fails("not_a_probe", toml=lambda o: o["checks"][1].update(probe="e01"))
        self.assertEqual(error.path, "checks[1].probe")
        self.fails("not_a_probe", events=lambda evs: event(evs, "e16").pop("probe"))
        self.fails("not_a_probe", events=lambda evs: event(evs, "e16").update(probe=False))

    def test_rule_bad_check(self):
        error = self.fails("bad_check", toml=lambda o: o["checks"][1].pop("key"))
        self.assertEqual(error.path, "checks[1].key")
        self.fails("bad_check", toml=lambda o: o["checks"][0].update(key="date"))
        self.fails("bad_check", toml=lambda o: o["checks"][5].update(probe="e01"))
        self.fails("bad_check", toml=lambda o: o["checks"][6].update(fact="f.budget"))
        self.fails("bad_check", toml=lambda o: o["checks"][6].update(tags=["policy", "policy"]))
        error = self.fails("bad_check", toml=lambda o: o["checks"][6].update(tags=["loud"]))
        self.assertEqual(error.path, "checks[6].tags[0]")
        self.fails("bad_check", toml=lambda o: o["checks"][7].update(key="date"))

    def test_rule_missing_control(self):
        def no_asker(o):
            # The only answer check on budget is by an actor outside the audience.
            table(o, "checks", "c-budget-di")["probe"] = "e16"

        error = self.fails("missing_control", toml=no_asker)
        self.assertEqual(error.path, "checks[4]")

        def no_answer(o):
            o["checks"] = [c for c in o["checks"] if c["id"] != "c-budget-di"]

        self.fails("missing_control", toml=no_answer)

        def echo_alone(o):
            o["checks"] = [c for c in o["checks"] if c["kind"] not in ("answer", "withhold", "no_leak")]

        error = self.fails("missing_control", toml=echo_alone)
        self.assertEqual(error.path, "checks[1]")

    def test_error_text_names_file_and_location(self):
        error = self.fails("unknown_actor", events=lambda evs: evs[0].update(actor="zed"))
        self.assertEqual(error.location, "line 1 event e01 field actor")
        self.assertIn("timeline.jsonl", str(error))
        self.assertIn("unknown_actor", str(error))
        self.assertIsInstance(error, ValueError)
        error = self.fails("bad_format", toml=lambda o: o.update(format=3))
        self.assertEqual(error.location, "format")


class Coverage(unittest.TestCase):
    def test_every_rule_has_a_test_and_a_line_in_the_document(self):
        document = rules_section()
        for code in pack.RULES:
            self.assertTrue(hasattr(Rules, f"test_rule_{code}"), f"no test for {code}")
            self.assertRegex(document, rf"(?m)^\| `{code}` \|", f"no line in the document for {code}")

    def test_every_code_raised_in_the_source_is_a_rule(self):
        source = (ROOT / "teamsim" / "pack.py").read_text(encoding="utf-8")
        raised = set(re.findall(r'(?:_err|self\.[te])\(\s*"([a-z_]+)"', source))
        raised |= set(re.findall(r'code, name = "([a-z_]+)"', source))
        raised |= set(re.findall(r'code = "([a-z_]+)"', source))
        self.assertTrue(raised)
        self.assertLessEqual(raised, set(pack.RULES))
        self.assertEqual(raised, set(pack.RULES), "a rule is listed but never raised")

    def test_every_rule_in_the_document_exists(self):
        document = rules_section()
        listed = set(re.findall(r"(?m)^\| `([a-z_]+)` \|", document))
        self.assertEqual(listed, set(pack.RULES))

    def test_limits_in_the_document_match(self):
        document = DOC.read_text(encoding="utf-8")
        for name in (
            "MAX_TOML_BYTES",
            "MAX_TIMELINE_BYTES",
            "MAX_LINE_BYTES",
            "MAX_EVENTS",
            "MAX_ACTORS",
            "MAX_SURFACES",
            "MAX_FACTS",
            "MAX_CHECKS",
            "MAX_TIME_MS",
        ):
            self.assertRegex(document, rf"(?m)^\| `{name}` \| {getattr(pack, name):,} ", name)

    def test_module_is_standard_library_only(self):
        source = (ROOT / "teamsim" / "pack.py").read_text(encoding="utf-8")
        for banned in (r"import random", r"(?<![\w.`])hash\(", r"time\.time", r"datetime", r"float\("):
            self.assertIsNone(re.search(banned, source), banned)


class ReviewRegressions(TempCase):
    def test_bare_newlines_stop_at_the_event_limit_with_bounded_memory(self):
        import tracemalloc

        text = "\n" * 3_000_000
        tracemalloc.start()
        try:
            with self.assertRaises(PackError) as caught:
                pack._read_timeline(text)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(caught.exception.code, "limit_exceeded")
        self.assertLess(peak, 5_000_000, "the timeline was split into a huge list")

    def test_huge_decimal_toml_integer_is_a_pack_error(self):
        text = dump_toml(BASE_TOML).replace('"format" = 1', '"format" = ' + "9" * 5000, 1)
        with self.assertRaises(PackError) as caught:
            pack.load(self.make(toml_text=text))
        self.assertEqual(caught.exception.code, "bad_toml")

    def test_huge_hex_toml_integer_is_a_pack_error(self):
        text = dump_toml(BASE_TOML).replace('"format" = 1', '"format" = 0x' + "f" * 5000, 1)
        with self.assertRaises(PackError) as caught:
            pack.load(self.make(toml_text=text))
        self.assertEqual(caught.exception.code, "non_canonical")
        self.assertLess(len(str(caught.exception)), 500)

    def _nested(self, depth):
        value = []
        for _ in range(depth - 1):
            value = [value]
        return value

    def test_every_loadable_pack_hashes_at_the_depth_limit(self):
        # Find the deepest transformation that loads; it must hash, one deeper must not load.
        deepest = None
        for depth in range(canon.MAX_DEPTH - 6, canon.MAX_DEPTH + 2):
            def edit(obj, depth=depth):
                obj["provenance"] = {"transformation": self._nested(depth)}

            try:
                loaded = pack.load(self.make(toml=edit))
            except PackError as error:
                self.assertEqual(error.code, "non_canonical")
                self.assertIsNotNone(deepest, "nothing loaded")
                self.assertEqual(depth, deepest + 1)
                break
            pack.pack_hash(loaded)
            deepest = depth
        else:
            self.fail("the depth limit was never reached")

    def test_deep_event_args_that_load_also_hash(self):
        for depth in range(canon.MAX_DEPTH - 6, canon.MAX_DEPTH + 1):
            def edit(evs, depth=depth):
                op = next(e for e in evs if e["kind"] == "op")
                op["args"] = {"a": self._nested(depth)}

            try:
                loaded = pack.load(self.make(events=edit))
            except PackError as error:
                self.assertEqual(error.code, "non_canonical")
                break
            pack.pack_hash(loaded)

    def test_write_refuses_a_pack_the_loader_would_reject_for_size(self):
        loaded = pack.load(MINIMAL)
        big = dataclasses.replace(loaded, header=dataclasses.replace(loaded.header, title="	" * 600_000))
        target = self.tmp / "out"
        with self.assertRaises(PackError) as caught:
            pack.write(big, target)
        self.assertEqual(caught.exception.code, "limit_exceeded")
        self.assertFalse(target.exists())
        # an existing pack is left untouched
        pack.write(loaded, target)
        before = (target / "pack.toml").read_bytes()
        with self.assertRaises(PackError):
            pack.write(big, target)
        self.assertEqual((target / "pack.toml").read_bytes(), before)

    def test_many_forms_load_and_a_repeat_is_still_located(self):
        forms = [f"form {n}" for n in range(20000)]

        def edit(obj):
            table(obj, "facts", "f.date.1")["forms"] = forms

        loaded = self.loads(toml=edit)
        self.assertEqual(len(next(f for f in loaded.facts if f.id == "f.date.1").forms), 20000)

        def repeat(obj):
            table(obj, "facts", "f.date.1")["forms"] = forms + ["form 17"]

        error = self.fails("bad_fact", toml=repeat)
        self.assertIn("forms[20000]", error.path)


if __name__ == "__main__":
    unittest.main()
