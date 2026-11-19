"""Tests for the run record and replay (docs/spec/engine-modules.md section 5)."""

import ast
import pathlib
import tempfile
import unittest

from teamsim import canon, record
from teamsim import pack as packmod
from teamsim.model import (
    Action,
    Delivery,
    Fault,
    Note,
    Observation,
    RecordHeader,
    Reply,
    Verdict,
)
from tests import fakes
from tests.fakes import FakeSession, done, ended, fault, post
from tests.test_engine import make_pack

ROOT = pathlib.Path(__file__).parent.parent
GOLDEN = ROOT / "tests" / "golden" / "record-tiny.jsonl"
SOURCE = ROOT / "teamsim" / "record.py"
HASH = "0123456789abcdef" * 4


def tiny_header():
    return RecordHeader(
        format=1,
        engine="0.1.0",
        pack_id="tiny",
        pack_hash=HASH,
        seed="tiny-seed",
        subject={"command": "naive_bot"},
        mode="scripted",
        limits=("one channel, two actors",),
    )


def tiny_entries():
    act = Action("post", "general", "Thursday 16 April", reply_to="e1")
    return (
        Note(1, 0, "start"),
        Observation(2, 0, 0, "ready", name="naive_bot", version="1"),
        Delivery(3, 1000, "post", "e1", "ana", "general", ("ana", "bo"), 1),
        Observation(4, 1000, 1, "action", action=act, readers=("ana", "bo")),
        Observation(5, 1000, 1, "done"),
        Note(6, 1000, "shutdown", detail="end_of_run"),
    )


def tiny_verdicts():
    return (
        Verdict("c1", "harness", "pass"),
        Verdict("c2", "answer", "pass", events=("e1",), entries=(4,)),
    )


def tiny_result():
    return record.build(tiny_header(), tiny_entries(), tiny_verdicts())


class Files(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = pathlib.Path(self._tmp.name)

    def path(self, name="record.jsonl"):
        return self.dir / name

    def put(self, data: bytes, name="record.jsonl"):
        p = self.path(name)
        p.write_bytes(data)
        return p


class Roundtrip(Files):
    def test_write_then_read_gives_an_equal_result(self):
        result = tiny_result()
        record.write(result, self.path())
        self.assertEqual(record.read(self.path()), result)

    def test_writing_twice_is_byte_identical(self):
        record.write(tiny_result(), self.path("a.jsonl"))
        record.write(tiny_result(), self.path("b.jsonl"))
        self.assertEqual(self.path("a.jsonl").read_bytes(), self.path("b.jsonl").read_bytes())

    def test_digest_of_a_tiny_record_matches_a_hand_computed_value(self):
        # The two lines below are the canonical bytes typed by hand. The expected
        # value is the SHA-256 of '[' + header + ',' + note + ']', computed with
        # GNU coreutils sha256sum and not with teamsim.
        header_line = (
            '{"engine":"0.1.0","format":1,"limits":["one channel, two actors"],'
            '"mode":"scripted","pack_hash":"' + HASH + '","pack_id":"tiny",'
            '"seed":"tiny-seed","subject":{"command":"naive_bot"},"type":"header"}'
        )
        note_line = '{"code":"start","n":1,"t_ms":0,"type":"note"}'
        expected = "5ab2862b482a5bdef40344009a6a16248078752ed3777cf71e6fbf4d96bbe589"
        result = record.build(tiny_header(), (Note(1, 0, "start"),), ())
        self.assertEqual(result.digest, expected)
        self.assertEqual(canon.canon(result.lines()[0]).decode(), header_line)
        self.assertEqual(canon.canon(result.lines()[1]).decode(), note_line)
        self.assertEqual(record.digest(result.lines()[:-1]), expected)

    def test_the_file_is_lf_only_utf8_without_bom_and_ends_with_the_digest(self):
        entries = tiny_entries()[:1] + (Note(2, 0, "shutdown", detail="end_of_run \u00e9"),)
        record.write(record.build(tiny_header(), entries, ()), self.path())
        data = self.path().read_bytes()
        self.assertFalse(data.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r", data)
        self.assertTrue(data.endswith(b"\n"))
        self.assertIn("\u00e9".encode(), data)
        lines = data.split(b"\n")[:-1]
        self.assertEqual(len(lines), 4)
        self.assertEqual(canon.parse(lines[-1])["type"], "digest")

    def test_write_refuses_a_result_with_a_wrong_digest(self):
        bad = tiny_result()
        bad = type(bad)(bad.header, bad.entries, bad.verdicts, "0" * 64)
        with self.assertRaises(ValueError):
            record.write(bad, self.path())

    def test_timing_goes_to_its_own_file_and_never_changes_the_record(self):
        record.write(tiny_result(), self.path())
        before = self.path().read_bytes()
        record.write_timing([{"event": "e1", "wall_ms": 12}], self.path("timing.jsonl"))
        self.assertEqual(self.path().read_bytes(), before)
        self.assertEqual(
            self.path("timing.jsonl").read_bytes(), b'{"event":"e1","wall_ms":12}\n'
        )
        self.assertEqual(record.read(self.path()).digest, tiny_result().digest)

    def test_golden_record_is_checked_byte_for_byte(self):
        record.write(tiny_result(), self.path())
        self.assertEqual(self.path().read_bytes(), GOLDEN.read_bytes())
        self.assertEqual(record.read(GOLDEN), tiny_result())


class Header(unittest.TestCase):
    def setUp(self):
        self.pack = make_pack([])

    def test_builds_from_the_pack(self):
        h = record.header(self.pack, {"builtin": "null"}, engine="0.1.0")
        self.assertEqual(h.pack_id, "secret-pack-id")
        self.assertEqual(h.pack_hash, packmod.pack_hash(self.pack))
        self.assertEqual((h.seed, h.mode, h.subject), ("secret-seed", "scripted", {"builtin": "null"}))
        self.assertEqual(
            record.header(self.pack, {"command": "bot.exe"}, engine="0.1.0").subject,
            {"command": "bot.exe"},
        )

    def test_rejects_anything_but_a_bare_builtin_or_command_name(self):
        bad = [
            {"builtin": "a", "command": "b"},
            {"args": "x"},
            {"command": "C:\\tools\\bot.exe"},
            {"command": "/usr/bin/bot"},
            {"command": "bot --key=1"},
            {"command": "bot", "args": ["x"]},
            {"command": ".."},
            {"command": ""},
            {"command": 5},
            {},
            "bot",
            None,
        ]
        for subject in bad:
            with self.subTest(subject=subject):
                with self.assertRaises(ValueError):
                    record.header(self.pack, subject, engine="0.1.0")


class Rejections(Files):
    def lines(self):
        return GOLDEN.read_bytes().split(b"\n")[:-1]

    def fails(self, data: bytes, code: str, line: int):
        with self.assertRaises(record.RecordError) as caught:
            record.read(self.put(data))
        self.assertEqual((caught.exception.code, caught.exception.line), (code, line))
        self.assertIsInstance(caught.exception, ValueError)

    def join(self, lines):
        return b"".join(line + b"\n" for line in lines)

    def test_the_unchanged_golden_reads(self):
        self.assertEqual(record.read(GOLDEN).digest, tiny_result().digest)

    def test_missing_digest(self):
        lines = self.lines()
        self.fails(self.join(lines[:-1]), "missing_digest", len(lines) - 1)

    def test_wrong_digest(self):
        lines = self.lines()
        lines[-1] = b'{"digest":"' + b"0" * 64 + b'","type":"digest"}'
        self.fails(self.join(lines), "digest_mismatch", len(lines))

    def test_a_changed_line_breaks_the_digest(self):
        lines = self.lines()
        lines[4] = lines[4].replace(b"Thursday", b"Tuesday ")
        self.fails(self.join(lines), "digest_mismatch", len(lines))

    def test_malformed_digest(self):
        lines = self.lines()
        lines[-1] = b'{"digest":"abc","type":"digest"}'
        self.fails(self.join(lines), "bad_digest", len(lines))
        lines[-1] = b'{"digest":"' + b"A" * 64 + b'","type":"digest"}'
        self.fails(self.join(lines), "bad_digest", len(lines))

    def test_line_that_is_not_canonical(self):
        lines = self.lines()
        lines[1] = b'{"code": "start","n":1,"t_ms":0,"type":"note"}'
        self.fails(self.join(lines), "not_canonical", 2)
        lines = self.lines()
        lines[1] = b'{"n":1,"code":"start","t_ms":0,"type":"note"}'
        self.fails(self.join(lines), "not_canonical", 2)

    def test_line_that_is_not_json(self):
        lines = self.lines()
        lines[2] = b"not json"
        self.fails(self.join(lines), "not_canonical", 3)

    def test_line_that_is_not_utf8(self):
        lines = self.lines()
        lines[2] = b'{"a":"\xff"}'
        self.fails(self.join(lines), "not_utf8", 3)

    def test_header_not_first(self):
        lines = self.lines()
        lines[0], lines[1] = lines[1], lines[0]
        self.fails(self.join(lines), "header_not_first", 1)

    def test_second_header(self):
        lines = self.lines()
        lines.insert(3, lines[0])
        self.fails(self.join(lines), "header_not_first", 4)

    def test_entry_after_verdict(self):
        lines = self.lines()
        verdict_at = [i for i, line in enumerate(lines) if b'"type":"verdict"' in line][0]
        lines.insert(verdict_at + 1, lines[1])
        self.fails(self.join(lines), "entry_after_verdict", verdict_at + 2)

    def test_verdict_after_digest(self):
        lines = self.lines()
        lines.append(lines[-2])
        self.fails(self.join(lines), "verdict_after_digest", len(lines))

    def test_anything_after_digest(self):
        lines = self.lines()
        lines.append(lines[1])
        self.fails(self.join(lines), "after_digest", len(lines))
        lines = self.lines()
        lines.append(lines[-1])
        self.fails(self.join(lines), "after_digest", len(lines))

    def test_byte_order_mark(self):
        self.fails(b"\xef\xbb\xbf" + GOLDEN.read_bytes(), "bom", 1)

    def test_carriage_return(self):
        lines = self.lines()
        data = self.join(lines).replace(lines[3] + b"\n", lines[3] + b"\r\n")
        self.fails(data, "carriage_return", 4)

    def test_empty_file_blank_line_and_missing_line_end(self):
        self.fails(b"", "empty", 0)
        lines = self.lines()
        lines.insert(2, b"")
        self.fails(self.join(lines), "blank_line", 3)
        self.fails(self.join(self.lines()).rstrip(b"\n"), "missing_newline", len(self.lines()))

    def test_a_line_that_is_not_a_record_line(self):
        lines = self.lines()
        lines[2] = b'{"type":"mystery"}'
        self.fails(self.join(lines), "invalid_line", 3)
        lines[2] = b'{"code":"bogus","n":1,"t_ms":0,"type":"note"}'
        self.fails(self.join(lines), "invalid_line", 3)


# --- replay ------------------------------------------------------------------


def log_of(*entries):
    """Number the entries from 1, whatever their placeholder numbers."""
    out = []
    for n, e in enumerate(entries, 1):
        fields = {name: getattr(e, name) for name in e.__slots__}
        fields["n"] = n
        out.append(type(e)(**fields))
    return tuple(out)


def delivery(seq, t=1000):
    return Delivery(0, t, "post", f"e{seq}", "ana", "s", ("ana", "bo"), seq)


class Sessions(unittest.TestCase):
    A = Action("post", "s", "hello", reply_to="e1")

    def test_normal_run(self):
        log = log_of(
            Note(0, 0, "start"),
            Observation(0, 0, 0, "ready", name="bot", version="2"),
            delivery(1),
            Observation(0, 1000, 1, "action", action=self.A, readers=("ana", "bo")),
            Observation(0, 1000, 1, "done", wake_at_ms=5000),
            delivery(2, 2000),
            Observation(0, 2000, 2, "done"),
            Note(0, 2000, "shutdown", detail="end_of_run"),
        )
        s = record.ReplaySession(log)
        self.assertEqual(s.start({}), Reply("ready", name="bot", version="2"))
        self.assertEqual(s.exchange({"seq": 1}), Reply("done", items=(self.A,), wake_at_ms=5000))
        self.assertEqual(s.exchange({"seq": 2}), Reply("done"))
        self.assertEqual(s.stop("end_of_run", 2000), Reply("closed"))

    def test_rejected_action_comes_back_as_an_action(self):
        bad = Action("post", "elsewhere", "hi")
        log = log_of(
            Note(0, 0, "start"),
            Observation(0, 0, 0, "ready", name="bot", version="1"),
            delivery(1),
            Observation(0, 1000, 1, "subject_error", action=bad, code="rejected_action", detail="surface"),
            Observation(0, 1000, 1, "action", action=self.A, readers=("ana",)),
            Observation(0, 1000, 1, "done"),
        )
        reply = record.ReplaySession(log).exchange({"seq": 1})
        self.assertEqual(reply, Reply("done", items=(bad, self.A)))
        self.assertIsInstance(reply.items[0], Action)

    def test_non_ending_fault(self):
        log = log_of(
            Note(0, 0, "start"),
            Observation(0, 0, 0, "ready", name="bot", version="1"),
            delivery(1),
            Observation(0, 1000, 1, "subject_error", code="late_action", detail="x"),
            Observation(0, 1000, 1, "done"),
        )
        reply = record.ReplaySession(log).exchange({"seq": 1})
        self.assertEqual(reply, Reply("done", items=(Fault("late_action", "x"),)))

    def test_ending_fault_then_stop(self):
        log = log_of(
            Note(0, 0, "start"),
            Observation(0, 0, 0, "ready", name="bot", version="1"),
            delivery(1),
            Observation(0, 1000, 1, "action", action=self.A, readers=("ana",)),
            Observation(0, 1000, 1, "subject_error", code="exited", detail="ValueError"),
            Note(0, 1000, "shutdown", detail="error"),
            Observation(0, 1000, 0, "subject_stalled", code="no_exit", detail="still running"),
        )
        s = record.ReplaySession(log)
        s.start({})
        self.assertEqual(
            s.exchange({"seq": 1}),
            Reply("ended", items=(self.A, Fault("exited", "ValueError"))),
        )
        self.assertEqual(s.stop("error", 1000), Reply("closed", items=(Fault("no_exit", "still running"),)))

    def test_stall(self):
        log = log_of(
            Note(0, 0, "start"),
            Observation(0, 0, 0, "ready", name="bot", version="1"),
            delivery(1),
            Observation(0, 1000, 1, "subject_stalled", code="timeout", detail="30000 ms"),
            Note(0, 1000, "shutdown", detail="watchdog"),
        )
        s = record.ReplaySession(log)
        self.assertEqual(s.exchange({"seq": 1}), Reply("ended", items=(Fault("timeout", "30000 ms"),)))
        self.assertEqual(s.stop("watchdog", 1000), Reply("closed"))

    def test_failed_start_ends_the_session(self):
        log = log_of(
            Note(0, 0, "start"),
            Observation(0, 0, 0, "subject_error", code="version_mismatch", detail="v"),
            Note(0, 0, "shutdown", detail="error"),
        )
        s = record.ReplaySession(log)
        self.assertEqual(s.start({}), Reply("ended", items=(Fault("version_mismatch", "v"),)))

    def test_empty_session(self):
        s = record.ReplaySession(())
        self.assertEqual(s.start({}), Reply("ready"))
        self.assertEqual(s.exchange({"seq": 1}), Reply("done"))
        self.assertEqual(s.stop("end_of_run", 0), Reply("closed"))

    def test_unknown_seq_gets_the_plain_reply(self):
        log = log_of(Note(0, 0, "start"), Observation(0, 0, 0, "ready", name="b", version="1"))
        self.assertEqual(record.ReplaySession(log).exchange({"seq": 9}), Reply("done"))


class Replay(Files):
    """``replay`` with injected fakes, and once with the real engine and checks."""

    @staticmethod
    def fake_run(pack, session):
        entries = [Note(1, 0, "start")]
        reply = session.start({"type": "hello"})
        entries.append(Observation(2, 0, 0, "ready", name=reply.name, version=reply.version))
        entries.append(Delivery(3, 10, "post", "e1", "ana", "s", ("ana",), 1))
        reply = session.exchange({"type": "event", "seq": 1})
        for item in reply.items:
            entries.append(Observation(len(entries) + 1, 10, 1, "action", action=item, readers=("ana",)))
        entries.append(Observation(len(entries) + 1, 10, 1, "done"))
        entries.append(Note(len(entries) + 1, 10, "shutdown", detail="end_of_run"))
        session.stop("end_of_run", 10)
        return tuple(entries)

    @staticmethod
    def fake_evaluate(pack, entries):
        acted = [e.n for e in entries if isinstance(e, Observation) and e.kind == "action"]
        return (Verdict("c1", "harness", "pass", entries=tuple(acted)),)

    def recorded(self, text, name):
        pack = make_pack([])
        script = [fakes.ready(), done(post("s", text, reply_to="e1"))]
        entries = self.fake_run(pack, FakeSession(script))
        result = record.build(record.header(pack, {"builtin": "null"}, engine="0.1.0"),
                              entries, self.fake_evaluate(pack, entries))
        record.write(result, self.path(name))
        return pack, result

    def test_reproduces_the_digest(self):
        pack, result = self.recorded("Thursday", "a.jsonl")
        again = record.replay(self.path("a.jsonl"), pack, run=self.fake_run, evaluate=self.fake_evaluate)
        self.assertEqual(again.digest, result.digest)
        self.assertEqual(again, result)

    def test_a_changed_observation_changes_the_digest(self):
        pack, a = self.recorded("Thursday", "a.jsonl")
        _, b = self.recorded("Tuesday", "b.jsonl")
        self.assertNotEqual(a.digest, b.digest)
        again = record.replay(self.path("b.jsonl"), pack, run=self.fake_run, evaluate=self.fake_evaluate)
        self.assertEqual(again.digest, b.digest)
        self.assertNotEqual(again.digest, a.digest)

    def test_a_record_from_another_pack_is_refused(self):
        pack, _ = self.recorded("Thursday", "a.jsonl")
        other = make_pack([], actors=("ana", "bo"))
        with self.assertRaises(record.RecordError) as caught:
            record.replay(self.path("a.jsonl"), other, run=self.fake_run, evaluate=self.fake_evaluate)
        self.assertEqual(caught.exception.code, "pack_mismatch")

    def test_a_damaged_record_is_refused(self):
        pack, _ = self.recorded("Thursday", "a.jsonl")
        data = self.path("a.jsonl").read_bytes().replace(b"Thursday", b"Tuesday ")
        self.put(data, "bad.jsonl")
        with self.assertRaises(record.RecordError) as caught:
            record.replay(self.path("bad.jsonl"), pack, run=self.fake_run, evaluate=self.fake_evaluate)
        self.assertEqual(caught.exception.code, "digest_mismatch")

    def test_real_engine_and_checks_reproduce_a_record(self):
        from teamsim import checks, engine

        pack = packmod.load(ROOT / "packs" / "minimal")
        probes = {"e15", "e16", "e18", "e21", "e22"}

        def handler(message):
            p = message.get("payload", {})
            if p.get("id") in probes:
                text = "ana: room-5520" if p["id"] == "e18" else "Thursday 16 April"
                return done(post(p["surface"], text, reply_to=p["id"]))
            return None

        # A rejected action, a late fault and a normal answer in one run.
        def script(message):
            p = message.get("payload", {})
            if p.get("id") == "e15":
                return done(post("nowhere", "x"), fault("late_action", "x"), post(p["surface"], "ok", reply_to="e15"))
            return handler(message)

        entries = engine.run(pack, FakeSession(script))
        self.assertTrue(
            any(isinstance(e, Observation) and e.code == "rejected_action" for e in entries)
        )
        result = record.build(
            record.header(pack, {"builtin": "scripted"}, engine="0.1.0"),
            entries,
            checks.evaluate(pack, entries),
        )
        record.write(result, self.path())
        again = record.replay(self.path(), pack)
        self.assertEqual(again.digest, result.digest)
        self.assertEqual(again.entries, result.entries)
        self.assertEqual(again.verdicts, result.verdicts)


class Hygiene(unittest.TestCase):
    def test_no_clock_random_or_environment(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.add((node.module or "").split(".")[0])
        for banned in ("random", "time", "datetime", "os", "secrets", "uuid"):
            self.assertNotIn(banned, names)
        self.assertNotIn("hash(", SOURCE.read_text(encoding="utf-8").replace("pack_hash(", "").replace("hash_of(", ""))

    def test_imports_without_the_engine_or_checks(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        modules = {getattr(n, "module", None) or n.names[0].name for n in top}
        self.assertNotIn("teamsim.engine", modules)
        self.assertNotIn("teamsim.checks", modules)


if __name__ == "__main__":
    unittest.main()
