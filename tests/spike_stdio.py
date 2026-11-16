"""Spike: can the child-process transport of the subject protocol be built on the standard
library alone, with Windows as the hard case?

Run it directly:

    python tests/spike_stdio.py

It prints one line per case and exits 0 only if every case behaved. The file name keeps it out
of unittest discovery on purpose. This is a measurement, not the transport: the transport is
written separately, against docs/spec/subject-protocol.md.

What the "engine" side does here, and why:

- Pipes are opened in binary mode and unbuffered. One thread reads the child's standard
  output in bounded chunks and splits lines; one thread writes to its standard input. The
  main thread only ever waits on a queue with a deadline, so no pipe can block it.
- A line may be at most LIMIT bytes, terminator included. The reader never buffers more.
- Every process started for one child is kept in one group that can be stopped as a whole:
  a job object on Windows (the child is created suspended, put in the job, then resumed, so
  that nothing it starts can be outside the job), a new session and process group elsewhere.
  The code for systems other than Windows is written but has not been run.
"""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import tracemalloc
import unicodedata

WINDOWS = sys.platform == "win32"
LIMIT = 1024 * 1024  # bytes in one line, terminator included
CHUNK = 64 * 1024  # largest single read
WALL_MS = 1000  # watchdog used here; the protocol default is 30 s
EVENTS = 2000
MAX_DEPTH = 32
MAX_INT = 2**53 - 1
KEY = re.compile(r"[a-z0-9_.:-]+")
BASE_ENV = ("PATH", "SYSTEMROOT")  # the only variables passed on, compared in upper case
RUNTIME_ADDED = ("LC_CTYPE", "__CF_USER_TEXT_ENCODING")  # set by some runtimes themselves
CANARY = "TEAMSIM_SPIKE_CANARY"
CHILD_LIFE_S = 90  # a child that "never" answers still ends by itself
FAILSAFE_S = 55
TEXT = unicodedata.normalize(
    "NFC", "naïve café, 東京, Ελληνικά, "
    "\U0001f642, tab\there, CR LF\r\ninside"
)
STDERR_BYTES = "diagnostic on standard error: café 東京\n".encode("utf-8")
HELLO = {
    "type": "hello", "v": 1, "subject_id": "subject", "t_ms": 0, "wall_timeout_ms": WALL_MS,
    "surfaces": [{"id": "general", "kind": "channel", "members": ["ana", "subject"]}],
}
SHUTDOWN = {"type": "shutdown", "reason": "end_of_run", "t_ms": 0}
BAD_LINES = (
    b"this is not json",
    b"",
    b'{"type":"done","in_reply_to":1',
    b"\xff\xfe{}",
    b'\xef\xbb\xbf{"type":"log","level":"info","text":"byte order mark"}',
    b"[1,2,3]",
    b'{"type":"log","level":"info","text":"x","n":1.5}',
    b'{"type":"log","level":"info","text":"x","n":1e3}',
    b'{"type":"log","level":"info","text":"x","n":NaN}',
    b'{"type":"log","level":"info","text":null}',
    b'{"type":"log","type":"done"}',
    b'{"type":"log","level":"info","text":"\\ud800"}',
    b'{"type":"log","level":"info","text":"e\\u0301"}',
    b'{"type":"log","n":9007199254740992}',
    b'{"Type":"log"}',
    b'{"a":' + b"[" * MAX_DEPTH + b"]" * MAX_DEPTH + b"}",
    b"[" * 200000,
)


def event(seq, text):
    payload = {"id": "e%04d" % seq, "surface": "general", "actor": "ana", "text": text}
    return {"type": "event", "seq": seq, "t_ms": seq * 1000, "kind": "post", "payload": payload}


def encode(message):
    """One message as one line: UTF-8, sorted keys, no spare whitespace, one line feed."""
    text = json.dumps(message, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return text.encode("utf-8") + b"\n"


def _not_integer(_text):
    raise ValueError("a number that is not an integer")


def _pairs(pairs):
    found = {}
    for key, value in pairs:
        if key in found:
            raise ValueError("duplicate key")
        found[key] = value
    return found


def _check(value, depth):
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        if not -MAX_INT <= value <= MAX_INT:
            raise ValueError("integer out of range")
    elif isinstance(value, str):
        value.encode("utf-8")  # refuses a lone surrogate
        if not unicodedata.is_normalized("NFC", value):
            raise ValueError("string is not NFC")
    elif isinstance(value, (list, dict)):
        if depth >= MAX_DEPTH:
            raise ValueError("nested too deeply")
        if isinstance(value, dict):
            for key in value:
                if not KEY.fullmatch(key):
                    raise ValueError("bad key")
            value = value.values()
        for item in value:
            _check(item, depth + 1)
    else:
        raise ValueError("null")


def parse(raw):
    """Read one line without its line feed. Returns (message, None) or (None, reason)."""
    if raw.endswith(b"\r"):
        raw = raw[:-1]
    try:
        value = json.loads(
            raw.decode("utf-8"),
            parse_float=_not_integer, parse_constant=_not_integer, object_pairs_hook=_pairs,
        )
        if not isinstance(value, dict):
            raise ValueError("not an object")
        _check(value, 0)
    except (ValueError, RecursionError) as exc:
        return None, "%s: %s" % (type(exc).__name__, str(exc)[:60])
    return value, None


# --------------------------------------------------------------------------------------------
# Stopping a whole process tree
# --------------------------------------------------------------------------------------------

if WINDOWS:
    import ctypes
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    def _api(name, restype, *argtypes):
        function = getattr(_kernel32, name)
        function.restype, function.argtypes = restype, argtypes
        return function

    _HANDLE, _DWORD, _BOOL = wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL
    _CreateJobObject = _api("CreateJobObjectW", _HANDLE, wintypes.LPVOID, wintypes.LPCWSTR)
    _SetInformationJobObject = _api(
        "SetInformationJobObject", _BOOL, _HANDLE, ctypes.c_int, wintypes.LPVOID, _DWORD)
    _QueryInformationJobObject = _api(
        "QueryInformationJobObject", _BOOL, _HANDLE, ctypes.c_int, wintypes.LPVOID, _DWORD,
        wintypes.LPDWORD)
    _AssignProcessToJobObject = _api("AssignProcessToJobObject", _BOOL, _HANDLE, _HANDLE)
    _TerminateJobObject = _api("TerminateJobObject", _BOOL, _HANDLE, wintypes.UINT)
    _OpenProcess = _api("OpenProcess", _HANDLE, _DWORD, _BOOL, _DWORD)
    _OpenThread = _api("OpenThread", _HANDLE, _DWORD, _BOOL, _DWORD)
    _ResumeThread = _api("ResumeThread", _DWORD, _HANDLE)
    _WaitForSingleObject = _api("WaitForSingleObject", _DWORD, _HANDLE, _DWORD)
    _CloseHandle = _api("CloseHandle", _BOOL, _HANDLE)
    _CreateToolhelp32Snapshot = _api("CreateToolhelp32Snapshot", _HANDLE, _DWORD, _DWORD)

    class _ThreadEntry(ctypes.Structure):
        _fields_ = [
            ("dwSize", _DWORD), ("cntUsage", _DWORD), ("th32ThreadID", _DWORD),
            ("th32OwnerProcessID", _DWORD), ("tpBasePri", wintypes.LONG),
            ("tpDeltaPri", wintypes.LONG), ("dwFlags", _DWORD),
        ]

    _Thread32First = _api("Thread32First", _BOOL, _HANDLE, ctypes.POINTER(_ThreadEntry))
    _Thread32Next = _api("Thread32Next", _BOOL, _HANDLE, ctypes.POINTER(_ThreadEntry))

    class _BasicLimits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
            ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
            ("LimitFlags", _DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", _DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", _DWORD),
            ("SchedulingClass", _DWORD),
        ]

    class _IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in "abcdef"]

    class _ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimits),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    class _Accounting(ctypes.Structure):
        _fields_ = [
            ("TotalUserTime", wintypes.LARGE_INTEGER),
            ("TotalKernelTime", wintypes.LARGE_INTEGER),
            ("ThisPeriodTotalUserTime", wintypes.LARGE_INTEGER),
            ("ThisPeriodTotalKernelTime", wintypes.LARGE_INTEGER),
            ("TotalPageFaultCount", _DWORD),
            ("TotalProcesses", _DWORD),
            ("ActiveProcesses", _DWORD),
            ("TotalTerminatedProcesses", _DWORD),
        ]

    _CREATE_SUSPENDED = 0x00000004
    _KILL_ON_JOB_CLOSE = 0x00002000
    _EXTENDED_LIMIT_INFORMATION = 9
    _BASIC_ACCOUNTING_INFORMATION = 1
    _PROCESS_TERMINATE, _PROCESS_SET_QUOTA, _SYNCHRONIZE = 0x0001, 0x0100, 0x00100000
    _THREAD_SUSPEND_RESUME = 0x0002
    _SNAPSHOT_THREADS = 0x00000004
    _INVALID_HANDLE = _HANDLE(-1).value

    def _failed(what):
        return ctypes.WinError(ctypes.get_last_error(), what)

    def _resume(pid):
        """Resume the one thread of a process that was created suspended."""
        snapshot = _CreateToolhelp32Snapshot(_SNAPSHOT_THREADS, 0)
        if snapshot in (None, _INVALID_HANDLE):
            raise _failed("CreateToolhelp32Snapshot")
        resumed = 0
        try:
            entry = _ThreadEntry()
            entry.dwSize = ctypes.sizeof(entry)
            more = _Thread32First(snapshot, ctypes.byref(entry))
            while more:
                if entry.th32OwnerProcessID == pid:
                    thread = _OpenThread(_THREAD_SUSPEND_RESUME, False, entry.th32ThreadID)
                    if not thread:
                        raise _failed("OpenThread")
                    try:
                        if _ResumeThread(thread) == 0xFFFFFFFF:
                            raise _failed("ResumeThread")
                    finally:
                        _CloseHandle(thread)
                    resumed += 1
                more = _Thread32Next(snapshot, ctypes.byref(entry))
        finally:
            _CloseHandle(snapshot)
        if resumed != 1:
            raise OSError("expected one suspended thread, found %d" % resumed)


class Tree:
    """Every process started for one child, so that all of them can be stopped together.

    The child must have been created suspended (Windows) or in a new session (elsewhere).
    """

    def __init__(self, proc):
        self.total = None
        if not WINDOWS:
            self.group = proc.pid
            return
        self.job = _CreateJobObject(None, None)
        if not self.job:
            raise _failed("CreateJobObject")
        try:
            limits = _ExtendedLimits()
            limits.BasicLimitInformation.LimitFlags = _KILL_ON_JOB_CLOSE
            if not _SetInformationJobObject(
                    self.job, _EXTENDED_LIMIT_INFORMATION, ctypes.byref(limits),
                    ctypes.sizeof(limits)):
                raise _failed("SetInformationJobObject")
            # Popen holds a handle to the process, so its id cannot be reused meanwhile.
            process = _OpenProcess(_PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, proc.pid)
            if not process:
                raise _failed("OpenProcess")
            try:
                if not _AssignProcessToJobObject(self.job, process):
                    raise _failed("AssignProcessToJobObject")
            finally:
                _CloseHandle(process)
            _resume(proc.pid)
        except BaseException:
            _CloseHandle(self.job)
            raise

    def kill(self):
        if WINDOWS:
            _TerminateJobObject(self.job, 1)
            return
        try:
            os.killpg(self.group, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def active(self):
        """How many processes of the tree are still running (elsewhere: 1 means "some")."""
        if WINDOWS:
            counts = _Accounting()
            if not _QueryInformationJobObject(
                    self.job, _BASIC_ACCOUNTING_INFORMATION, ctypes.byref(counts),
                    ctypes.sizeof(counts), None):
                raise _failed("QueryInformationJobObject")
            self.total = counts.TotalProcesses
            return counts.ActiveProcesses
        try:
            os.killpg(self.group, 0)
        except ProcessLookupError:
            return 0
        except PermissionError:
            pass
        return 1

    def wait_empty(self, wait_ms):
        deadline = time.monotonic_ns() + wait_ms * 1_000_000
        while self.active():
            if time.monotonic_ns() >= deadline:
                return False
            time.sleep(0.005)
        return True

    def close(self):
        if WINDOWS:
            _CloseHandle(self.job)


class Watch:
    """Tells whether one process, named by its id while it was alive, has ended."""

    def __init__(self, pid):
        self.pid = pid
        if WINDOWS:
            self.handle = _OpenProcess(_SYNCHRONIZE, False, pid)
            if not self.handle:
                raise _failed("OpenProcess")

    def gone(self, wait_ms):
        if WINDOWS:
            return _WaitForSingleObject(self.handle, wait_ms) == 0
        deadline = time.monotonic_ns() + wait_ms * 1_000_000
        while True:
            try:
                os.kill(self.pid, 0)
            except ProcessLookupError:
                return True
            except PermissionError:
                pass
            if time.monotonic_ns() >= deadline:
                return False
            time.sleep(0.005)

    def close(self):
        if WINDOWS:
            _CloseHandle(self.handle)


# --------------------------------------------------------------------------------------------
# One child and its pipes
# --------------------------------------------------------------------------------------------

class Stop(Exception):
    """The exchange ended some other way than by the awaited message."""

    def __init__(self, kind, detail=""):
        super().__init__(kind, detail)
        self.kind, self.detail = kind, detail


class Session:
    live = []
    started = 0
    confirmed_empty = 0
    setup_us = []

    def __init__(self, role, root):
        self.cwd = tempfile.mkdtemp(prefix="cwd-", dir=root)
        self.cwd_real = os.path.normcase(os.path.realpath(self.cwd))
        self.err_path = self.cwd + ".stderr"
        self.err = open(self.err_path, "wb")
        env = {name: value for name, value in os.environ.items() if name.upper() in BASE_ENV}
        argv = [sys.executable, "-I", os.path.abspath(__file__), "--child", role]
        options = {"creationflags": _CREATE_SUSPENDED} if WINDOWS else {"start_new_session": True}
        self.proc = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.err, bufsize=0,
            env=env, cwd=self.cwd, **options)
        began = time.perf_counter_ns()
        try:
            self.tree = Tree(self.proc)
        except BaseException:
            self.proc.kill()  # still suspended: it has run nothing and started nothing
            self.proc.wait()
            raise
        Session.setup_us.append((time.perf_counter_ns() - began) // 1000)
        Session.started += 1
        Session.live.append(self)
        self.lines = queue.Queue(maxsize=64)
        self.outbox = queue.Queue()
        self.stopping = threading.Event()
        self.stopped = None
        self.writing = False
        self.accepted = 0
        self.bytes_read = 0
        self.peak = 0
        self.raws = []
        self.reader = threading.Thread(target=self._read_loop, daemon=True)
        self.writer = threading.Thread(target=self._write_loop, daemon=True)
        self.reader.start()
        self.writer.start()

    def _emit(self, item):
        while not self.stopping.is_set():
            try:
                self.lines.put(item, timeout=0.05)
                return
            except queue.Full:
                pass

    def _read_loop(self):
        stream, held, refused = self.proc.stdout, bytearray(), False
        while True:
            try:
                chunk = stream.read(min(CHUNK, LIMIT - len(held)))
            except (OSError, ValueError):
                chunk = b""
            if not chunk:
                break
            self.bytes_read += len(chunk)
            if refused or self.stopping.is_set():
                continue  # keep draining so the child cannot block, keep nothing
            held += chunk
            self.peak = max(self.peak, len(held))
            while True:
                end = held.find(b"\n")
                if end < 0:
                    break
                self._emit(("line", bytes(held[:end])))
                del held[:end + 1]
            if len(held) >= LIMIT:
                refused = True
                held.clear()
                self._emit(("overlong", b""))
        stream.close()
        self._emit(("eof", b""))

    def _write_loop(self):
        stream = self.proc.stdin
        try:
            while True:
                item = self.outbox.get()
                if item is None:
                    break
                data, piece = item
                view = memoryview(data)
                while view:
                    self.writing = True
                    sent = stream.write(view[:piece or len(view)])
                    self.writing = False
                    self.accepted += sent
                    view = view[sent:]
        except (OSError, ValueError):
            pass
        try:
            stream.close()
        except OSError:
            pass

    def send(self, message, piece=None):
        self.accepted = 0
        self.outbox.put((encode(message), piece))

    def recv(self, deadline_ns):
        """Next thing from the child: line, overlong, eof, exit (ended, pipe still open) or
        timeout."""
        ended_before = False
        while True:
            remaining = deadline_ns - time.monotonic_ns()
            if remaining <= 0:
                return "timeout", b""
            try:
                return self.lines.get(timeout=min(remaining, 50_000_000) / 1e9)
            except queue.Empty:
                if self.proc.poll() is not None:
                    if ended_before:  # one more interval has passed with nothing to read
                        return "exit", b""
                    ended_before = True

    def ask(self, message, until, piece=None):
        """Send one message, then read until a message of type `until` arrives."""
        deadline = time.monotonic_ns() + WALL_MS * 1_000_000
        self.send(message, piece)
        self.raws, got = [], []
        while True:
            kind, raw = self.recv(deadline)
            if kind != "line":
                raise Stop(kind)
            self.raws.append(raw)
            parsed, reason = parse(raw)
            if parsed is None:
                raise Stop("malformed", reason)
            got.append(parsed)
            if parsed.get("type") == until:
                return got

    def stop(self, orderly_ms=0):
        """End the session and report how it went. With orderly_ms, the child's standard input
        is closed first and it is given that long to leave by itself."""
        if self.stopped is not None:
            return self.stopped
        began = time.monotonic_ns()
        left_alone = False
        if orderly_ms:
            self.outbox.put(None)
            try:
                self.proc.wait(orderly_ms / 1000)
                left_alone = self.tree.wait_empty(orderly_ms)
            except subprocess.TimeoutExpired:
                pass
        self.stopping.set()
        self.tree.kill()
        try:
            code = self.proc.wait(5)
        except subprocess.TimeoutExpired:
            code = None
        self.outbox.put(None)
        self.reader.join(3)
        self.writer.join(3)
        freed = not (self.reader.is_alive() or self.writer.is_alive())
        empty = self.tree.wait_empty(3000)
        self.tree.close()
        self.err.close()
        with open(self.err_path, "rb") as handle:
            stderr = handle.read()
        removed = False
        for _ in range(100):  # a directory can stay busy for a moment after its user ends
            shutil.rmtree(self.cwd, ignore_errors=True)
            removed = not os.path.exists(self.cwd)
            if removed:
                break
            time.sleep(0.01)
        if empty:
            Session.confirmed_empty += 1
        Session.live.remove(self)
        self.stopped = {
            "code": code, "left_alone": left_alone, "freed": freed, "empty": empty,
            "removed": removed, "stderr": stderr, "total": self.tree.total,
            "ms": (time.monotonic_ns() - began) // 1_000_000,
            "clean": code is not None and freed and empty and removed,
        }
        return self.stopped


# --------------------------------------------------------------------------------------------
# The cases
# --------------------------------------------------------------------------------------------

def need(condition, what):
    if not condition:
        raise AssertionError(what)


def elapsed_ms(since_ns):
    return (time.monotonic_ns() - since_ns) // 1_000_000


def expect_stop(session, message, kinds, piece=None):
    try:
        session.ask(message, "done", piece)
    except Stop as stop:
        need(stop.kind in kinds, "expected %s, got %s %s" % (kinds, stop.kind, stop.detail))
        return stop
    raise AssertionError("expected %s, got a normal reply" % (kinds,))


def case_lockstep(root):
    session = Session("echo", root)
    session.ask(HELLO, "ready")
    times, began = [], time.monotonic_ns()
    for seq in range(1, EVENTS + 1):
        sent = time.perf_counter_ns()
        got = session.ask(event(seq, TEXT), "done")
        times.append(time.perf_counter_ns() - sent)
        need(len(got) == 2 and got[1]["in_reply_to"] == seq, "wrong reply to event %d" % seq)
        need(got[0]["text"] == TEXT, "text changed on the way at event %d" % seq)
        need(not any(b"\r" in raw for raw in session.raws), "a line feed was translated")
    total = elapsed_ms(began)
    session.send(SHUTDOWN)
    out = session.stop(orderly_ms=5000)
    need(out["left_alone"] and out["code"] == 0 and out["clean"], "no orderly exit: %s" % out)
    times.sort()
    return (
        "%d events in %d ms; round trip median %d us, 99th percentile %d us, slowest %d us; "
        "non-ASCII text intact, no carriage return added; child left by itself with code 0"
        % (EVENTS, total, times[len(times) // 2] // 1000, times[len(times) * 99 // 100] // 1000,
           times[-1] // 1000))


def case_text_mode(root):
    session = Session("naive", root)
    got = session.ask(HELLO, "ready")
    encoding = got[0]["text"]
    ending = "CR LF" if session.raws[-1].endswith(b"\r") else "LF"
    plain = "café"
    got = session.ask(event(1, plain), "done")
    first = "intact" if got[0]["text"] == plain else "garbled"
    try:
        got = session.ask(event(2, TEXT), "done")
        second = "intact" if got[0]["text"] == TEXT else "garbled"
    except Stop as stop:
        second = "reply refused (%s: %s)" % (stop.kind, stop.detail.split(":")[0] or "no line")
    out = session.stop()
    need(out["clean"], "not clean: %s" % out)
    utf8 = encoding.replace("-", "") == "utf8"
    need(not utf8 or (first, second) == ("intact", "intact"), "UTF-8 child lost text")
    return (
        "child using text streams: lines end in %s and are accepted; its input encoding is %s; "
        "accented Latin text came back %s, mixed scripts: %s" % (ending, encoding, first, second))


def case_watchdog(root):
    session = Session("stall", root)
    session.ask(HELLO, "ready")
    began = time.monotonic_ns()
    expect_stop(session, event(1, "x"), ("timeout",))
    waited = elapsed_ms(began)
    out = session.stop()
    need(waited <= WALL_MS + 250, "watchdog late: %d ms" % waited)
    need(out["clean"] and out["ms"] <= 1000, "not stopped cleanly: %s" % out)
    return ("no reply: watchdog fired after %d ms (limit %d); tree stopped and threads freed "
            "%d ms later" % (waited, WALL_MS, out["ms"]))


def case_deaf(root):
    session = Session("deaf", root)
    padded = dict(HELLO, pad="x" * (256 * 1024))
    size = len(encode(padded))
    began = time.monotonic_ns()
    try:
        session.ask(padded, "ready", piece=1024)
    except Stop as stop:
        need(stop.kind == "timeout", "expected timeout, got %s" % stop.kind)
    else:
        raise AssertionError("a child that never reads answered")
    waited = elapsed_ms(began)
    blocked, accepted = session.writing, session.accepted
    out = session.stop()
    need(blocked and accepted < size, "the write did not block (%d of %d)" % (accepted, size))
    need(waited <= WALL_MS + 250 and out["clean"], "not stopped cleanly: %s" % out)
    return ("child never reads: the pipe took %d of %d bytes and the write then blocked; "
            "watchdog fired after %d ms; stopping the tree freed the writer %d ms later"
            % (accepted, size, waited, out["ms"]))


def case_long_line(root):
    session = Session("big", root)
    session.ask(HELLO, "ready")
    session.ask(event(1, "x"), "done")
    longest = len(session.raws[0]) + 1
    need(longest == LIMIT, "the legal line had %d bytes" % longest)
    expect_stop(session, event(2, "x"), ("overlong",))
    out = session.stop()
    need(session.peak <= LIMIT and out["clean"], "peak %d, %s" % (session.peak, out))
    return ("a line of %d bytes is accepted; one of %d bytes is refused with never more than "
            "%d bytes buffered" % (LIMIT, LIMIT + 1, session.peak))


def case_flood(root):
    tracemalloc.start()
    try:
        session = Session("flood", root)
        session.ask(HELLO, "ready")
        began = time.monotonic_ns()
        expect_stop(session, event(1, "x"), ("overlong",))
        waited = elapsed_ms(began)
        out = session.stop()
        traced = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    need(session.peak <= LIMIT and traced < 4 * LIMIT, "peak %d, traced %d" % (session.peak,
                                                                             traced))
    need(out["clean"], "not clean: %s" % out)
    return ("output with no line feed is refused after %d ms; %d bytes read in all, never more "
            "than %d buffered, traced memory peak %d KiB"
            % (waited, session.bytes_read, session.peak, traced // 1024))


def case_malformed(root):
    deepest = {"a": 0}
    for _ in range(MAX_DEPTH - 1):
        deepest = {"a": deepest}
    need(parse(encode(deepest)[:-1])[0] == deepest, "nesting of %d was refused" % MAX_DEPTH)
    need(parse(encode({"a": deepest})[:-1])[0] is None, "deeper nesting was accepted")
    session = Session("garbage", root)
    session.ask(HELLO, "ready")
    for number, bad in enumerate(BAD_LINES, 1):
        stop = expect_stop(session, event(number, "x"), ("malformed",))
        need(session.raws[-1] == bad, "line %d arrived changed" % number)
        need(stop.detail, "no reason given")
    out = session.stop()
    need(out["clean"], "not clean: %s" % out)
    return ("%d of %d bad lines refused, each with a reason (not JSON, not UTF-8, byte order "
            "mark, not an object, fraction, exponent, NaN, null, duplicate key, lone surrogate, "
            "not NFC, integer out of range, bad key, nesting deeper than %d)"
            % (len(BAD_LINES), len(BAD_LINES), MAX_DEPTH))


def case_early_exit(root):
    session = Session("exit", root)
    session.ask(HELLO, "ready")
    began = time.monotonic_ns()
    stop = expect_stop(session, event(1, "x"), ("eof", "exit"))
    waited = elapsed_ms(began)
    code = session.proc.wait(5)
    out = session.stop()
    need(code == 7 and out["clean"], "exit code %s, %s" % (code, out))
    return ("child exits in the middle of an event: seen as %s after %d ms, exit code %d "
            "captured" % ("end of file" if stop.kind == "eof" else "exit", waited, code))


def case_grandchild_stall(root):
    session = Session("grandchild-stall", root)
    got = session.ask(HELLO, "ready")
    watch = Watch(int(got[0]["text"]))
    try:
        expect_stop(session, event(1, "x"), ("timeout",))
        session.proc.kill()  # the obvious kill: the child only
        session.proc.wait(5)
        time.sleep(0.5)
        need(session.lines.empty() and session.reader.is_alive(), "end of file after all")
        need(not watch.gone(0), "the grandchild did not survive the plain kill")
        out = session.stop()
        need(out["clean"] and watch.gone(3000), "tree not stopped: %s" % out)
    finally:
        watch.close()
    counted = "" if out["total"] is None else " (%d processes counted in the job)" % out["total"]
    return ("killing only the child: no end of file 500 ms later, grandchild still running and "
            "reader still blocked; stopping the tree: both ended and reader freed after %d ms%s"
            % (out["ms"], counted))


def case_grandchild_exit(root):
    session = Session("grandchild-exit", root)
    got = session.ask(HELLO, "ready")
    watch = Watch(int(got[0]["text"]))
    try:
        began = time.monotonic_ns()
        expect_stop(session, event(1, "x"), ("exit",))
        waited = elapsed_ms(began)
        code = session.proc.returncode
        need(code == 7 and session.reader.is_alive() and not watch.gone(0), "unexpected state")
        out = session.stop()
        need(out["clean"] and watch.gone(3000), "tree not stopped: %s" % out)
    finally:
        watch.close()
    return ("child exits with code %d while its grandchild holds the pipes: no end of file, "
            "exit seen after %d ms; stopping the tree freed the reader %d ms later"
            % (code, waited, out["ms"]))


def case_environment(root):
    os.environ[CANARY] = "must-not-reach-the-child"
    session = Session("env", root)
    got = session.ask(HELLO, "ready")
    report = json.loads(got[0]["text"])
    session.send(SHUTDOWN)
    out = session.stop(orderly_ms=5000)
    names = sorted(name.upper() for name in report["names"])
    extra = [name for name in names if name not in BASE_ENV + RUNTIME_ADDED]
    need(CANARY not in names and not extra, "child saw %s" % names)
    need(os.path.normcase(os.path.realpath(report["cwd"])) == session.cwd_real, "wrong directory")
    need(report["listing"] == [], "the directory was not empty: %s" % report["listing"])
    need(out["clean"] and out["left_alone"], "not clean: %s" % out)
    need(out["stderr"] == STDERR_BYTES, "standard error changed: %r" % out["stderr"])
    return ("child saw only %s of the %d variables here; its working directory was the new, "
            "empty temporary one, removed afterwards; its %d bytes of standard error are in the "
            "log file unchanged" % (" and ".join(names), len(os.environ), len(STDERR_BYTES)))


def _probe(env):
    code = ("import socket\ntry:\n    socket.socket().close()\n    print('socket opens')\n"
            "except OSError as exc:\n    print('socket fails with', exc.__class__.__name__,"
            " getattr(exc, 'winerror', exc.errno))")
    try:
        done = subprocess.run([sys.executable, "-I", "-c", code], env=env, capture_output=True,
                              timeout=20)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "does not start (%s)" % type(exc).__name__
    lines = (done.stdout or done.stderr).decode("ascii", "replace").strip().splitlines()
    return "interpreter starts, %s" % lines[-1] if done.returncode == 0 and lines else (
        "interpreter fails with code %d" % done.returncode)


def case_bare_environment(_root):
    kept = {name: value for name, value in os.environ.items() if name.upper() == "SYSTEMROOT"}
    return "with no variables at all: %s; with %s: %s" % (
        _probe({}), " and ".join(kept) or "no SystemRoot here", _probe(kept))


CASES = (
    ("lockstep", case_lockstep),
    ("text-mode child", case_text_mode),
    ("watchdog", case_watchdog),
    ("ignores input", case_deaf),
    ("long line", case_long_line),
    ("flood", case_flood),
    ("malformed", case_malformed),
    ("early exit", case_early_exit),
    ("grandchild, stalled", case_grandchild_stall),
    ("grandchild, exited", case_grandchild_exit),
    ("environment", case_environment),
    ("bare environment", case_bare_environment),
)


def _give_up():
    print("FAIL  spike still running after %d s; stopping everything it started" % FAILSAFE_S,
          flush=True)
    for session in list(Session.live):
        session.tree.kill()
    os._exit(3)


def main():
    began = time.monotonic_ns()
    failsafe = threading.Timer(FAILSAFE_S, _give_up)
    failsafe.daemon = True
    failsafe.start()
    root = tempfile.mkdtemp(prefix="teamsim-spike-")
    print("spike_stdio on Python %s, %s" % (sys.version.split()[0], sys.platform), flush=True)
    failures = 0
    try:
        for name, case in CASES:
            try:
                line = "ok    %s: %s" % (name, case(root))
            except Exception as exc:  # a failed case must not hide the others
                failures += 1
                line = "FAIL  %s: %s: %s" % (name, type(exc).__name__, exc)
            for session in list(Session.live):
                session.stop()
            print(line, flush=True)
    finally:
        for session in list(Session.live):
            session.tree.kill()
        shutil.rmtree(root, ignore_errors=True)
    stray = Session.started - Session.confirmed_empty
    setup = sorted(Session.setup_us)
    print("%s  %d cases, %d failed; %d child trees started, %d not confirmed empty; putting a "
          "child in its tree took %d us (median); %d ms in all"
          % ("FAIL" if failures or stray else "ok  ", len(CASES), failures, Session.started,
             stray, setup[len(setup) // 2] if setup else 0, elapsed_ms(began)), flush=True)
    failsafe.cancel()
    return 1 if failures or stray else 0


# --------------------------------------------------------------------------------------------
# The children (this same file, started with --child ROLE)
# --------------------------------------------------------------------------------------------

def child(role):
    stdin, stdout = sys.stdin.buffer, sys.stdout.buffer  # bytes: no translation of any kind

    def read():
        line = stdin.readline()
        return json.loads(line) if line else None

    def write(*messages):
        for message in messages:
            stdout.write(encode(message))
        stdout.flush()

    def ready(*before):
        write(*before, {"type": "ready", "v": 1, "name": role, "version": "0"})

    def log(text):
        return {"type": "log", "level": "info", "text": text}

    def done(seq):
        return {"type": "done", "in_reply_to": seq}

    if role == "deaf":
        time.sleep(CHILD_LIFE_S)
        return 0

    if role == "naive":  # text streams with whatever encoding and line ending the platform gives
        for line in sys.stdin:
            message = json.loads(line)
            if message["type"] == "hello":
                print(json.dumps(log(sys.stdin.encoding.lower())))
                print(json.dumps({"type": "ready", "v": 1, "name": role, "version": "0"}),
                      flush=True)
            elif message["type"] == "event":
                print(json.dumps({
                    "type": "action", "in_reply_to": message["seq"], "kind": "post",
                    "surface": "general", "text": message["payload"]["text"]}))
                print(json.dumps(done(message["seq"])), flush=True)
        return 0

    sleeper = None
    if role.startswith("grandchild"):
        sleeper = subprocess.Popen(
            [sys.executable, "-I", "-c", "import time; time.sleep(%d)" % CHILD_LIFE_S],
            stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)

    while True:
        message = read()
        if message is None or message["type"] == "shutdown":
            return 0
        if message["type"] == "hello":
            if role == "env":
                sys.stderr.buffer.write(STDERR_BYTES)
                sys.stderr.buffer.flush()
                ready(log(json.dumps({
                    "names": sorted(os.environ), "cwd": os.getcwd(), "listing": os.listdir(".")})))
            elif sleeper is not None:
                ready(log(str(sleeper.pid)))
            else:
                ready()
            continue
        seq = message["seq"]
        if role == "echo":
            payload = message["payload"]
            write({"type": "action", "in_reply_to": seq, "kind": "post",
                   "surface": payload["surface"], "text": payload["text"]}, done(seq))
        elif role in ("stall", "grandchild-stall"):
            time.sleep(CHILD_LIFE_S)
            return 0
        elif role in ("exit", "grandchild-exit"):
            return 7
        elif role == "big":
            room = LIMIT - len(encode(log("")))
            write(log("x" * (room + seq - 1)), done(seq))  # event 1: the limit; event 2: one over
        elif role == "flood":
            while True:
                stdout.write(b"x" * CHUNK)
                stdout.flush()
        elif role == "garbage":
            stdout.write(BAD_LINES[seq - 1] + b"\n")
            stdout.flush()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.exit(child(sys.argv[2]))
    sys.exit(main())
