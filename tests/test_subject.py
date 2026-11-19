"""Tests for teamsim.subject: both transports, the shared rules and the child-process limits."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from teamsim import pack as packmod
from teamsim import subject
from teamsim.model import (
    CODE_EXITED, CODE_INVALID_MESSAGE, CODE_LATE_ACTION, CODE_LINE_TOO_LONG,
    CODE_MALFORMED_LINE, CODE_NO_EXIT, CODE_OUTPUT_AFTER_SHUTDOWN, CODE_REPORTED, CODE_TIMEOUT,
    CODE_TOO_MANY_ACTIONS, CODE_VERSION_MISMATCH, CODE_WRONG_IN_REPLY_TO, Action, Fault, Reply)
from tests.subjects.scripted import Logic

HERE = Path(__file__).resolve().parent
SCRIPTED = str(HERE / "subjects" / "scripted.py")
MODES = str(HERE / "subjects" / "modes.py")
ROOT = HERE.parent


def hello(wall=2000):
    return {"type": "hello", "v": 1, "subject_id": "subject", "t_ms": 0, "wall_timeout_ms": wall,
            "surfaces": [{"id": "general", "kind": "channel", "members": ["ana", "subject"]}]}


def event(seq, text="hi", t_ms=None):
    return {"type": "event", "seq": seq, "t_ms": seq * 1000 if t_ms is None else t_ms,
            "kind": "post", "payload": {"id": "e%02d" % seq, "surface": "general",
                                        "actor": "ana", "text": text}}


def child(mode, arg="", **options):
    argv = [sys.executable, "-I", MODES, mode] + ([arg] if arg else [])
    options.setdefault("wall_timeout_ms", 2000)
    return subject.ChildProcess(argv, **options)


def scripted_child(scenario):
    return subject.ChildProcess([sys.executable, "-I", SCRIPTED, scenario], wall_timeout_ms=3000)


def drive(session, events=2):
    """start, up to ``events`` exchanges (stopping at an end), then stop."""
    replies = []
    try:
        replies.append(session.start(hello()))
        for seq in range(1, events + 1):
            if replies[-1].end == "ended":
                break
            replies.append(session.exchange(event(seq)))
        replies.append(session.stop("error" if replies[-1].end == "ended" else "end_of_run", 9000))
    finally:
        session.stop("error", 9000)
    return replies


def codes(reply):
    return [item.code for item in reply.items if isinstance(item, Fault)]


class SameThroughBothTransports(unittest.TestCase):
    """Done when 1: one scripted logic, equal replies from InProcess and ChildProcess."""

    EXPECT = {
        "normal": ("done", []),
        "wake": ("done", []),
        "late": ("done", [CODE_LATE_ACTION]),
        "wrong": ("done", [CODE_WRONG_IN_REPLY_TO] * 2),
        "many": ("ended", [CODE_TOO_MANY_ACTIONS]),
        "invalid": ("ended", [CODE_INVALID_MESSAGE]),
        "float": ("ended", [CODE_MALFORMED_LINE]),
        "error": ("ended", [CODE_REPORTED]),
    }

    def run_scenario(self, name):
        inproc = drive(subject.InProcess(Logic(name)))
        proc = drive(scripted_child(name))
        self.assertEqual(inproc, proc)
        return inproc

    def test_scenarios(self):
        for name, (end, expected) in self.EXPECT.items():
            with self.subTest(name):
                replies = self.run_scenario(name)
                self.assertEqual(replies[0].end, "ready")
                self.assertEqual(replies[2].end, end)
                self.assertEqual(codes(replies[2]), expected)
                self.assertEqual(replies[-1].end, "closed")

    def test_actions_and_wake(self):
        replies = self.run_scenario("wake")
        self.assertEqual(replies[1].items, (Action("post", "general", "re 1"),))
        self.assertEqual(replies[1].wake_at_ms, None)
        self.assertEqual(replies[2].wake_at_ms, 2005)
        self.assertEqual((replies[0].name, replies[0].version), ("scripted", "1"))

    def test_too_many_keeps_first_hundred(self):
        replies = self.run_scenario("many")
        actions = [i for i in replies[2].items if isinstance(i, Action)]
        self.assertEqual(len(actions), 100)

    def test_version_mismatch(self):
        replies = self.run_scenario("version")
        self.assertEqual(replies[0].end, "ended")
        self.assertEqual(codes(replies[0]), [CODE_VERSION_MISMATCH])

    def test_reported_error_text(self):
        replies = self.run_scenario("error")
        self.assertEqual(replies[2].items[-1], Fault(CODE_REPORTED, "boom: it broke"))


class InProcessOnly(unittest.TestCase):
    def test_handler_exception_ends_with_type_name(self):
        class Bad:
            def handle(self, m):
                raise KeyError("secret text")
        reply = subject.InProcess(Bad()).start(hello())
        self.assertEqual(reply, Reply("ended", (Fault(CODE_EXITED, "KeyError"),)))

    def test_list_without_done_ends(self):
        class Silent:
            def handle(self, m):
                if m["type"] == "hello":
                    return [{"type": "ready", "v": 1, "name": "n", "version": "1"}]
                return []
        s = subject.InProcess(Silent())
        self.assertEqual(s.start(hello()).end, "ready")
        self.assertEqual(s.exchange(event(1)), Reply("ended", (Fault(CODE_EXITED, "no_done"),)))

    def test_output_after_shutdown(self):
        class Chatty(Logic):
            def handle(self, m):
                if m["type"] == "shutdown":
                    return [{"type": "log", "level": "info", "text": "x"}]
                return super().handle(m)
        s = subject.InProcess(Chatty("normal"))
        s.start(hello())
        self.assertEqual(codes(s.stop("end_of_run", 5)), [CODE_OUTPUT_AFTER_SHUTDOWN])

    def test_over_long_message_is_refused(self):
        class Big(Logic):
            def handle(self, m):
                if m["type"] == "event":
                    return [{"type": "action", "in_reply_to": m["seq"], "kind": "post",
                             "surface": "general", "text": "x" * subject.LINE_LIMIT}]
                return super().handle(m)
        s = subject.InProcess(Big("normal"))
        s.start(hello())
        self.assertEqual(codes(s.exchange(event(1))), [CODE_LINE_TOO_LONG])

    def test_max_actions_parameter(self):
        s = subject.InProcess(Logic("many"), max_actions=3)
        s.start(hello())
        s.exchange(event(1))
        self.assertEqual(codes(s.exchange(event(2))), [CODE_TOO_MANY_ACTIONS])


class ValidateMessage(unittest.TestCase):
    def test_states(self):
        ready = {"type": "ready", "v": 1, "name": "n", "version": "1"}
        self.assertIs(subject.validate_message(ready, "starting"), ready)
        for obj, state in ((ready, "busy"), ({"type": "done", "in_reply_to": 1}, "starting"),
                           ({"type": "log", "level": "info", "text": ""}, "idle")):
            with self.assertRaises(subject.Invalid) as raised:
                subject.validate_message(obj, state)
            self.assertEqual(raised.exception.code, CODE_INVALID_MESSAGE)

    def test_fields(self):
        bad = [
            {"type": "action", "in_reply_to": 1, "kind": "post", "surface": "s"},
            {"type": "action", "in_reply_to": True, "kind": "post", "surface": "s", "text": ""},
            {"type": "action", "in_reply_to": 1, "kind": "shout", "surface": "s", "text": ""},
            {"type": "action", "in_reply_to": 1, "kind": "react", "surface": "s", "text": "+1"},
            {"type": "done", "in_reply_to": 1, "wake_at_ms": "soon"},
            {"type": "log", "level": "loud", "text": ""},
            {"type": "nope"},
        ]
        for obj in bad:
            with self.subTest(obj), self.assertRaises(subject.Invalid):
                subject.validate_message(obj, "busy")

    def test_unknown_type_detail_is_repr_and_short(self):
        with self.assertRaises(subject.Invalid) as raised:
            subject.validate_message({"type": "x" * 500}, "busy")
        self.assertLess(len(raised.exception.detail), 100)
        self.assertIn("'x", raised.exception.detail)

    def test_wake_must_be_later(self):
        class Early(Logic):
            def handle(self, m):
                if m["type"] == "event":
                    return [{"type": "done", "in_reply_to": m["seq"], "wake_at_ms": m["t_ms"]}]
                return super().handle(m)
        s = subject.InProcess(Early("normal"))
        s.start(hello())
        self.assertEqual(codes(s.exchange(event(1))), [CODE_INVALID_MESSAGE])


class ParseLine(unittest.TestCase):
    def test_refusals(self):
        for raw in (b"not json", b"", b'{"a":', b"\xff\xfe{}", b"[1]", b'{"n":1.5}', b'{"n":1e3}',
                    b'{"n":NaN}', b'{"n":null}', b'{"a":1,"a":2}', b'{"t":"\\ud800"}',
                    b'{"t":"e\\u0301"}', b'{"n":9007199254740992}', b'{"Bad":1}',
                    b'{"a":' + b"[" * 32 + b"]" * 32 + b"}", b"[" * 200000):
            with self.subTest(raw[:30]), self.assertRaises(subject.Invalid) as raised:
                subject.parse_line(raw)
            self.assertEqual(raised.exception.code, CODE_MALFORMED_LINE)

    def test_accepts_crlf_and_depth_32(self):
        self.assertEqual(subject.parse_line(b'{"a":1}\r'), {"a": 1})
        subject.parse_line(b'{"a":' + b"[" * 31 + b"]" * 31 + b"}")


class ChildOnly(unittest.TestCase):
    """Done when 2."""

    def run_child(self, mode, wall=2000, events=1, stop_reason="error"):
        session = child(mode, wall_timeout_ms=wall)
        try:
            replies = [session.start(hello())]
            for seq in range(1, events + 1):
                if replies[-1].end == "ended":
                    break
                replies.append(session.exchange(event(seq)))
            replies.append(session.stop(stop_reason, 9000))
            return replies
        finally:
            session.stop("watchdog", 0)

    def test_timeout_on_hello(self):
        replies = self.run_child("stall_hello", wall=300)
        self.assertEqual(replies[0].items[-1].code, CODE_TIMEOUT)
        self.assertEqual(replies[0].end, "ended")

    def test_timeout_on_event(self):
        replies = self.run_child("stall_event", wall=1500, stop_reason="watchdog")
        self.assertEqual(replies[0].end, "ready")
        self.assertEqual(codes(replies[1]), [CODE_TIMEOUT])
        self.assertEqual(replies[2], Reply("closed"))

    def test_malformed_line(self):
        replies = self.run_child("malformed")
        self.assertEqual(codes(replies[1]), [CODE_MALFORMED_LINE])

    def test_over_long_line(self):
        replies = self.run_child("overlong")
        self.assertEqual(codes(replies[1]), [CODE_LINE_TOO_LONG])

    def test_early_exit_with_code(self):
        replies = self.run_child("exit")
        self.assertEqual(replies[1].items, (Fault(CODE_EXITED, "exit code 3"),))

    def test_early_exit_with_grandchild_holding_the_pipe(self):
        replies = self.run_child("grandchild", wall=5000)
        self.assertEqual(codes(replies[1]), [CODE_EXITED])

    def test_no_exit_after_shutdown(self):
        replies = self.run_child("no_exit", wall=700, stop_reason="end_of_run")
        self.assertEqual(replies[-1].items, (Fault(CODE_NO_EXIT, "still running"),))

    def test_output_after_shutdown(self):
        replies = self.run_child("after", stop_reason="end_of_run")
        self.assertEqual(codes(replies[-1]), [CODE_OUTPUT_AFTER_SHUTDOWN])

    def test_output_after_error_shutdown_is_discarded(self):
        replies = self.run_child("after", stop_reason="error")
        self.assertEqual(replies[-1], Reply("closed"))

    def test_missing_program(self):
        reply = subject.ChildProcess(["/no/such/program-teamsim"]).start(hello())
        self.assertEqual(reply.end, "ended")
        self.assertEqual(codes(reply), [CODE_EXITED])

    def test_stop_is_idempotent(self):
        session = child("plain")
        session.start(hello())
        self.assertEqual(session.stop("end_of_run", 1), Reply("closed"))
        self.assertEqual(session.stop("end_of_run", 1), Reply("closed"))


class Environment(unittest.TestCase):
    """Done when 3."""

    def test_only_allowed_names_and_new_directory(self):
        patch = {"TS_ALLOWED": "yes", "TS_SECRET": "no", "TS_UNSET_NAME": "x"}
        with mock.patch.dict(os.environ, patch):
            session = child("env", env_names=("TS_ALLOWED", "TS_NOT_SET"))
            reply = session.start(hello())
            try:
                cwd = reply.version
                info = json.loads(reply.name)
                self.assertTrue(os.path.isdir(cwd))
                self.assertNotEqual(os.path.normcase(os.path.realpath(cwd)),
                                    os.path.normcase(os.path.realpath(os.getcwd())))
                self.assertEqual(info["ls"], [])
            finally:
                session.stop("end_of_run", 1)
        names = {name.upper() for name in info["env"]}
        allowed = {"PATH", "SYSTEMROOT", "TS_ALLOWED", "LC_CTYPE", "__CF_USER_TEXT_ENCODING"}
        self.assertLessEqual(names, allowed)
        self.assertEqual(info["env"].get("TS_ALLOWED"), "yes")
        self.assertNotIn("TS_SECRET", names)
        self.assertNotIn("TS_UNSET_NAME", names)
        self.assertFalse(os.path.exists(cwd))

    def test_directory_removed_after_failure(self):
        session = child("exit")
        session.start(hello())
        cwd = session._cwd
        self.assertEqual(session.exchange(event(1)).end, "ended")
        self.assertTrue(os.path.isdir(cwd))
        session.stop("error", 1)
        self.assertFalse(os.path.exists(cwd))


def process_alive(pid):
    """True while the process ``pid`` exists (a zombie counts as gone)."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False  # no such process
        try:
            code = wintypes.DWORD()
            return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        with open("/proc/%d/stat" % pid, "rb") as stat:
            return stat.read().rsplit(b")", 1)[1].split()[0] != b"Z"
    except OSError:
        return True


class ProcessTree(unittest.TestCase):
    """The whole tree dies at stop, not only the child (protocol section 5.6)."""

    def test_a_grandchild_is_killed_at_stop(self):
        import time

        session = child("tree", wall_timeout_ms=5000)
        try:
            reply = session.start(hello(5000))
            self.assertEqual(reply.end, "ready")
            pid = int(reply.name)
            self.assertTrue(process_alive(pid))
            session.stop("end_of_run", 1)
            deadline = time.monotonic() + 5
            while process_alive(pid) and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertFalse(process_alive(pid), "the grandchild outlived stop")
        finally:
            session.stop("watchdog", 0)


class LogMessages(unittest.TestCase):
    """Subject ``log`` messages go to the redacted standard-error file (protocol 4.2)."""

    def run_log(self, text, secrets, events=0):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "err.log")
            session = child("log", text, stderr_path=path, redact=secrets)
            try:
                session.start(hello())
                for seq in range(1, events + 1):
                    session.exchange(event(seq))
            finally:
                session.stop("end_of_run", 1)
            return Path(path).read_bytes().decode("utf-8")

    def test_a_log_line_is_written_redacted(self):
        data = self.run_log("token is hunter2 now", ("hunter2",))
        self.assertIn("token is [redacted] now", data)
        self.assertNotIn("hunter2", data)

    def test_only_the_first_hundred_are_kept_and_the_dropped_count_is_written(self):
        data = self.run_log("hello", (), events=1)
        self.assertIn("line 99", data)
        self.assertNotIn("line 100", data)
        self.assertIn("3 log lines dropped", data)


class Limits(unittest.TestCase):
    def test_the_line_queue_is_small(self):
        # 64 queued lines of up to 1 MiB would hold 64 MiB; the queue must stay near one line
        self.assertLessEqual(subject.ChildProcess([sys.executable])._lines.maxsize, 2)

    def test_the_watchdog_comes_from_hello(self):
        import time

        session = child("stall_hello", wall_timeout_ms=30000)  # the constructor value is a default
        began = time.monotonic()
        try:
            reply = session.start(hello(300))
            self.assertEqual(codes(reply), [CODE_TIMEOUT])
            self.assertLess(time.monotonic() - began, 10)
        finally:
            session.stop("watchdog", 0)


class Transcript(unittest.TestCase):
    """Done when 4: no fact value reaches the subject except in an event that discloses it."""

    def transcript(self, ids):
        pack = packmod.load(ROOT / "packs" / "minimal")
        by_id = {e.id: e for e in pack.events}
        h = hello()
        h["surfaces"] = [{"id": "direct:bo", "kind": "direct", "members": ["bo", "subject"]},
                         h["surfaces"][0]]
        session = child("mirror")
        lines = []
        try:
            reply = session.start(h)
            self.assertEqual(reply.name.encode("utf-8") + b"\n", subject.encode(h))
            lines.append((None, reply.name))
            for seq, eid in enumerate(ids, 1):
                e = by_id[eid]
                fields = (("id", e.id), ("surface", e.surface), ("actor", e.actor),
                          ("text", e.text))
                msg = {"type": "event", "seq": seq, "t_ms": seq * 1000, "kind": e.kind,
                       "payload": {k: v for k, v in fields if v is not None}}
                reply = session.exchange(msg)
                self.assertEqual(reply.end, "done")
                self.assertEqual(reply.items[0].text.encode("utf-8") + b"\n", subject.encode(msg))
                lines.append((eid, reply.items[0].text))
        finally:
            session.stop("end_of_run", 1)
        return pack, lines

    def check(self, pack, lines):
        for owner, text in lines:
            allowed = set()
            if owner is not None:
                allowed = set(next(e for e in pack.events if e.id == owner).discloses or ())
            for fact in pack.facts:
                if fact.value in text:
                    self.assertIn(fact.id, allowed, (owner, fact.id))

    def test_without_the_restricted_events(self):
        pack, lines = self.transcript(["e01", "e02", "e04", "e11", "e13", "e16", "e18"])
        self.check(pack, lines)
        blob = "\n".join(text for _, text in lines)
        for fact_id in ("f.budget", "f.token"):
            self.assertNotIn(next(f.value for f in pack.facts if f.id == fact_id), blob)
        self.assertIn("Tuesday 14 April", blob)

    def test_with_the_leads_events_after_joining(self):
        pack, lines = self.transcript(["e01", "e09", "e10", "e22"])
        self.check(pack, lines)
        self.assertTrue(any("12 units" in text for _, text in lines))


class EngineTranscript(unittest.TestCase):
    """Done when 4, over the engine: nothing the subject is sent carries a fact outside the
    event that discloses it, for every shipped pack and for a silent and an honest subject."""

    def test_no_fact_reaches_the_subject_outside_its_disclosing_event(self):
        from teamsim import controls, engine, match

        class Recorder:
            def __init__(self, inner):
                self.inner, self.messages = inner, []

            def handle(self, message):
                self.messages.append(json.loads(json.dumps(message)))
                return self.inner.handle(message)

        for name in ("minimal", "team-ten", "solo", "social-ten"):
            pack = packmod.load(ROOT / "packs" / name)
            events = {e.id: e for e in pack.events}
            for control in ("null", "oracle"):
                with self.subTest(pack=name, control=control):
                    recorder = Recorder(controls.make(control, pack))
                    engine.run(pack, subject.InProcess(recorder))
                    self.assertGreater(len(recorder.messages), 2)
                    for message in recorder.messages:
                        blob = json.dumps(message, ensure_ascii=False)
                        source = message["payload"].get("id") if message["type"] == "event" else None
                        allowed = set(events[source].discloses or ()) if source in events else set()
                        for fact in pack.facts:
                            if fact.id in allowed:
                                continue
                            for form in (fact.value, *(fact.forms or ())):
                                self.assertFalse(
                                    match.contains(blob, form),
                                    (name, control, message.get("seq"), fact.id),
                                )


class Redaction(unittest.TestCase):
    """Done when 5."""

    def run_stderr(self, parts, secrets):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "err.log")
            session = child("stderr", "|".join(parts), stderr_path=path, redact=secrets)
            try:
                session.start(hello())
            finally:
                session.stop("end_of_run", 1)
            return Path(path).read_bytes()

    def test_whole_secret(self):
        self.assertEqual(self.run_stderr(["a hunter2 b"], ("hunter2",)), b"a [redacted] b")

    def test_secret_split_across_two_reads(self):
        data = self.run_stderr(["key: hun", "ter2 end"], ("hunter2",))
        self.assertEqual(data, b"key: [redacted] end")

    def test_two_secrets_and_clean_text(self):
        data = self.run_stderr(["one-abc ", "two-xyz ", "plain"], ("one-abc", "two-xyz"))
        self.assertEqual(data, b"[redacted] [redacted] plain")

    def test_no_secrets_passes_through(self):
        self.assertEqual(self.run_stderr(["café ok"], ()), "café ok".encode())


if __name__ == "__main__":
    unittest.main()
