"""Subject transports: the in-process handler and the child process, with one set of rules.

This module implements ``docs/spec/subject-protocol.md`` and section 4 of
``docs/spec/engine-modules.md``. ``InProcess`` and ``ChildProcess`` both turn what a subject
sends into a ``Reply``; the message checks and the exchange rules (``_Round``) are shared, so one
subject logic gives equal replies through either transport.

Everything a subject sends is untrusted. It is parsed, checked and copied, never evaluated, and
no text from it is put into an exception message. This module starts processes and reads the
wall clock for the watchdog; the watchdog never touches virtual time.
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
import unicodedata
from typing import Protocol

from teamsim.model import (
    ACTION_KINDS,
    CODE_EXITED,
    CODE_INVALID_MESSAGE,
    CODE_LATE_ACTION,
    CODE_LINE_TOO_LONG,
    CODE_MALFORMED_LINE,
    CODE_NO_EXIT,
    CODE_OUTPUT_AFTER_SHUTDOWN,
    CODE_REPORTED,
    CODE_TIMEOUT,
    CODE_TOO_MANY_ACTIONS,
    CODE_VERSION_MISMATCH,
    CODE_WRONG_IN_REPLY_TO,
    REPLY_CLOSED,
    REPLY_DONE,
    REPLY_ENDED,
    REPLY_READY,
    SHUTDOWN_END_OF_RUN,
    SHUTDOWN_WATCHDOG,
    Action,
    Fault,
    Reply,
)

WINDOWS = sys.platform == "win32"
LINE_LIMIT = 1024 * 1024  # bytes in one line, terminator included (protocol section 3)
MAX_LOGS = 100  # log messages kept for one outstanding message (protocol section 4.2)
MAX_ACTIONS = 100  # actions and rejected messages for one event (protocol section 6)
MAX_DEPTH = 32  # nesting, the message object being level 1 (protocol section 2)
MAX_INT = 2**53 - 1
DETAIL_LIMIT = 200  # characters of subject text kept in a Fault detail
_CHUNK = 64 * 1024  # largest single read
_POLL_S = 0.05  # how often a waiting loop looks at the process itself
_KEY = re.compile(r"[a-z0-9_.:-]+")
_BASE_ENV = ("PATH", "SystemRoot")
_LOG_LEVELS = ("debug", "info", "warning", "error")
_REDACTED = b"[redacted]"

STATE_STARTING = "starting"
STATE_BUSY = "busy"
STATE_IDLE = "idle"


class Session(Protocol):
    """What the engine drives: ``start``, then ``exchange`` per event, then ``stop``."""

    def start(self, hello: dict) -> Reply: ...  # end: "ready" or "ended"

    def exchange(self, event: dict) -> Reply: ...  # end: "done" or "ended"

    def stop(self, reason: str, t_ms: int) -> Reply: ...  # end: "closed"


# --------------------------------------------------------------------------------------------
# Values and messages (protocol sections 2, 3 and 4)
# --------------------------------------------------------------------------------------------


class Invalid(Exception):
    """A message that breaks a rule. ``code`` is a violation code; ``detail`` is short text in
    which subject text appears only in ``repr`` form, truncated."""

    def __init__(self, code: str, detail: str | None = None):
        super().__init__(code, detail)
        self.code = code
        self.detail = detail


def _show(value: object) -> str:
    """Subject text for a detail: ``repr``, truncated."""
    text = repr(value)
    return text if len(text) <= 60 else text[:57] + "..."


def encode(message: object) -> bytes:
    """One message as one line: UTF-8, sorted keys, no spare whitespace, one line feed."""
    text = json.dumps(message, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return text.encode("utf-8") + b"\n"


def _not_integer(_text: str):
    raise ValueError("a number that is not an integer")


def _pairs(pairs):
    found = {}
    for key, value in pairs:
        if key in found:
            raise ValueError("duplicate key")
        found[key] = value
    return found


def _check_value(value: object, depth: int) -> None:
    """Protocol section 2, for a value that is already parsed or built in memory."""
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
                if not isinstance(key, str) or not _KEY.fullmatch(key):
                    raise ValueError("bad key")
            value = value.values()
        for item in value:
            _check_value(item, depth + 1)
    elif isinstance(value, float):
        raise ValueError("a number that is not an integer")
    else:
        raise ValueError("a value that is not a string, integer, boolean, array or object")


def parse_line(raw: bytes) -> dict:
    """Read one line, without its line feed, as the child-process transport does. Returns the
    object, or raises ``Invalid`` with code ``malformed_line``."""
    if raw.endswith(b"\r"):
        raw = raw[:-1]
    try:
        value = json.loads(
            raw.decode("utf-8"),
            parse_float=_not_integer, parse_constant=_not_integer, object_pairs_hook=_pairs,
        )
        if not isinstance(value, dict):
            raise ValueError("not an object")
        _check_value(value, 0)
    except (ValueError, RecursionError) as exc:
        raise Invalid(CODE_MALFORMED_LINE, "%s: %s" % (type(exc).__name__, str(exc)[:60])) from None
    return value


def _as_line(message: object) -> dict:
    """A message returned by an in-process handler, checked as a line would be: the same size
    limit on its encoded form, then the same parse."""
    if not isinstance(message, dict):
        raise Invalid(CODE_MALFORMED_LINE, "not an object: %s" % type(message).__name__)
    try:
        _check_value(message, 0)
        line = encode(message)
    except (ValueError, RecursionError, TypeError) as exc:
        raise Invalid(CODE_MALFORMED_LINE, "%s: %s" % (type(exc).__name__, str(exc)[:60])) from None
    if len(line) > LINE_LIMIT:
        raise Invalid(CODE_LINE_TOO_LONG, "%d bytes" % len(line))
    return parse_line(line[:-1])


def _is_int(value: object) -> bool:
    return type(value) is int


def _is_str(value: object) -> bool:
    return type(value) is str


def _is_obj(value: object) -> bool:
    return type(value) is dict


# type -> (states that allow it, required fields, optional fields)
_SPEC = {
    "ready": ((STATE_STARTING,), {"v": _is_int, "name": _is_str, "version": _is_str}, {}),
    "action": (
        (STATE_BUSY,),
        {"in_reply_to": _is_int, "kind": _is_str, "surface": _is_str, "text": _is_str},
        {"data": _is_obj, "reply_to": _is_str},
    ),
    "done": ((STATE_BUSY,), {"in_reply_to": _is_int}, {"wake_at_ms": _is_int}),
    "log": ((STATE_STARTING, STATE_BUSY), {"level": _is_str, "text": _is_str}, {}),
    "error": (
        (STATE_STARTING, STATE_BUSY),
        {"in_reply_to": _is_int, "code": _is_str, "text": _is_str},
        {},
    ),
}


def validate_message(obj: object, state: str) -> dict:
    """Check one message from the subject (protocol sections 4.2 and 5.1) against the state of
    the exchange (``starting``, ``busy`` or ``idle``). Returns the message, or raises ``Invalid``
    with code ``invalid_message``. Section 2 is checked before this, by ``parse_line``."""
    if not isinstance(obj, dict):
        raise Invalid(CODE_INVALID_MESSAGE, "not an object")
    kind = obj.get("type")
    if not _is_str(kind) or kind not in _SPEC:
        raise Invalid(CODE_INVALID_MESSAGE, "unknown type %s" % _show(kind))
    states, required, optional = _SPEC[kind]
    if state not in states:
        raise Invalid(CODE_INVALID_MESSAGE, "%s not allowed while %s" % (kind, state))
    for name, ok in required.items():
        if name not in obj:
            raise Invalid(CODE_INVALID_MESSAGE, "%s lacks %s" % (kind, name))
        if not ok(obj[name]):
            raise Invalid(CODE_INVALID_MESSAGE, "%s: wrong type for %s" % (kind, name))
    for name, ok in optional.items():
        if name in obj and not ok(obj[name]):
            raise Invalid(CODE_INVALID_MESSAGE, "%s: wrong type for %s" % (kind, name))
    if kind == "action":
        if obj["kind"] not in ACTION_KINDS:
            raise Invalid(CODE_INVALID_MESSAGE, "action: kind %s" % _show(obj["kind"]))
        if obj["kind"] == "react" and "reply_to" not in obj:
            raise Invalid(CODE_INVALID_MESSAGE, "action: react lacks reply_to")
    elif kind == "log" and obj["level"] not in _LOG_LEVELS:
        raise Invalid(CODE_INVALID_MESSAGE, "log: level %s" % _show(obj["level"]))
    elif kind == "done" and "wake_at_ms" in obj and obj["wake_at_ms"] < 0:
        raise Invalid(CODE_INVALID_MESSAGE, "done: wake_at_ms is negative")
    return obj


def _clip(text: str) -> str:
    return text if len(text) <= DETAIL_LIMIT else text[:DETAIL_LIMIT]


class _Round:
    """The rules for one outstanding message, shared by both transports (protocol sections 5.2,
    5.3 and 6). ``take`` is given each parsed message in arrival order and returns the ``Reply``
    when the exchange is finished, otherwise ``None``."""

    def __init__(self, completed: set, max_actions: int, *, v=None, seq=None, t_ms=0):
        self.completed = completed
        self.max_actions = max_actions
        self.state = STATE_STARTING if seq is None else STATE_BUSY
        self.v, self.seq, self.t_ms = v, seq, t_ms
        self.items: list = []
        self.count = 0
        self.logs: list = []  # the first MAX_LOGS (level, text) pairs
        self.log_dropped = 0

    def fail(self, code: str, detail: str | None = None) -> Reply:
        self.items.append(Fault(code, None if detail is None else _clip(detail)))
        return Reply(REPLY_ENDED, tuple(self.items))

    def _reject(self, code: str, detail: str) -> Reply | None:
        if self.count >= self.max_actions:
            return self.fail(CODE_TOO_MANY_ACTIONS)
        self.count += 1
        self.items.append(Fault(code, detail))
        return None

    def take(self, obj: dict) -> Reply | None:
        try:
            validate_message(obj, self.state)
        except Invalid as bad:
            return self.fail(bad.code, bad.detail)
        kind = obj["type"]
        if kind == "log":
            if len(self.logs) < MAX_LOGS:
                self.logs.append((obj["level"], obj["text"]))
            else:
                self.log_dropped += 1
            return None
        if kind == "error":
            return self.fail(CODE_REPORTED, "%s: %s" % (obj["code"], obj["text"]))
        if kind == "ready":
            if obj["v"] != self.v:
                return self.fail(CODE_VERSION_MISMATCH, "v %d" % obj["v"])
            return Reply(REPLY_READY, tuple(self.items), name=obj["name"], version=obj["version"])
        if kind == "action":
            if obj["in_reply_to"] != self.seq:
                late = obj["in_reply_to"] in self.completed
                return self._reject(
                    CODE_LATE_ACTION if late else CODE_WRONG_IN_REPLY_TO,
                    "in_reply_to %d" % obj["in_reply_to"])
            if self.count >= self.max_actions:
                return self.fail(CODE_TOO_MANY_ACTIONS)
            self.count += 1
            self.items.append(Action(
                kind=obj["kind"], surface=obj["surface"], text=obj["text"],
                data=obj.get("data"), reply_to=obj.get("reply_to")))
            return None
        # done
        if obj["in_reply_to"] != self.seq:
            return self._reject(CODE_WRONG_IN_REPLY_TO, "in_reply_to %d" % obj["in_reply_to"])
        wake = obj.get("wake_at_ms")
        if wake is not None and wake <= self.t_ms:
            return self.fail(CODE_INVALID_MESSAGE, "done: wake_at_ms is not later than t_ms")
        self.completed.add(self.seq)
        return Reply(REPLY_DONE, tuple(self.items), wake_at_ms=wake)


def _start_round(completed: set, max_actions: int, hello: dict) -> _Round:
    return _Round(completed, max_actions, v=hello.get("v"))


def _event_round(completed: set, max_actions: int, event: dict) -> _Round:
    return _Round(completed, max_actions, seq=event["seq"], t_ms=event["t_ms"])


# --------------------------------------------------------------------------------------------
# In process
# --------------------------------------------------------------------------------------------


class InProcess(Session):
    """Wraps any object with ``handle(message: dict) -> list[dict]`` (protocol section 8).

    A handler is trusted code that runs inside this process: there is no watchdog. What it
    returns goes through the checks a line from a child gets.
    """

    def __init__(self, handler, *, max_actions: int = MAX_ACTIONS):
        self._handler = handler
        self._max_actions = max_actions
        self._completed: set = set()
        self._pending: list = []  # returned after a done, read as the next message's output
        self._ended = False
        self._stopped = False

    def _run(self, rnd: _Round, message: dict) -> Reply:
        if self._ended:
            raise RuntimeError("the session has ended")
        try:
            out = self._handler.handle(message)
        except Exception as exc:  # the handler is trusted code; only its type name is kept
            return self._end(rnd.fail(CODE_EXITED, type(exc).__name__))
        if type(out) is not list:
            return self._end(rnd.fail(CODE_MALFORMED_LINE, "handler returned %s" % type(out).__name__))
        queued = self._pending + out
        self._pending = []
        for index, raw in enumerate(queued):
            try:
                reply = rnd.take(_as_line(raw))
            except Invalid as bad:
                reply = rnd.fail(bad.code, bad.detail)
            if reply is not None:
                if reply.end == REPLY_ENDED:
                    return self._end(reply)
                self._pending = queued[index + 1:]
                return reply
        return self._end(rnd.fail(CODE_EXITED, "no_done"))

    def _end(self, reply: Reply) -> Reply:
        self._ended = True
        self._pending = []
        return reply

    def start(self, hello: dict) -> Reply:
        return self._run(_start_round(self._completed, self._max_actions, hello), hello)

    def exchange(self, event: dict) -> Reply:
        return self._run(_event_round(self._completed, self._max_actions, event), event)

    def stop(self, reason: str, t_ms: int) -> Reply:
        if self._stopped:
            return Reply(REPLY_CLOSED)
        self._stopped = True
        message = {"type": "shutdown", "reason": reason, "t_ms": t_ms}
        late = len(self._pending)
        items: list = []
        try:
            out = self._handler.handle(message)
        except Exception as exc:
            items.append(Fault(CODE_EXITED, type(exc).__name__))
            out = []
        late += len(out) if type(out) is list else 1
        self._pending = []
        if late and reason == SHUTDOWN_END_OF_RUN:
            items.append(Fault(CODE_OUTPUT_AFTER_SHUTDOWN))
        return Reply(REPLY_CLOSED, tuple(items))


# --------------------------------------------------------------------------------------------
# Stopping a whole process tree (measured in protocol section 13)
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
    _PROCESS_TERMINATE, _PROCESS_SET_QUOTA = 0x0001, 0x0100
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


class _Tree:
    """Every process started for one child, so that all of them can be stopped together.

    The child must have been created suspended (Windows) or in a new session (elsewhere). The
    code for systems other than Windows has not been run."""

    def __init__(self, proc):
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

    def kill(self) -> None:
        if WINDOWS:
            _TerminateJobObject(self.job, 1)
            return
        try:
            os.killpg(self.group, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def active(self) -> int:
        """How many processes of the tree still run (elsewhere: 1 means "some")."""
        if WINDOWS:
            counts = _Accounting()
            if not _QueryInformationJobObject(
                    self.job, _BASIC_ACCOUNTING_INFORMATION, ctypes.byref(counts),
                    ctypes.sizeof(counts), None):
                raise _failed("QueryInformationJobObject")
            return counts.ActiveProcesses
        try:
            os.killpg(self.group, 0)
        except ProcessLookupError:
            return 0
        except PermissionError:
            pass
        return 1

    def wait_empty(self, wait_ms: int) -> bool:
        deadline = time.monotonic_ns() + wait_ms * 1_000_000
        while self.active():
            if time.monotonic_ns() >= deadline:
                return False
            time.sleep(0.005)
        return True

    def close(self) -> None:
        if WINDOWS:
            _CloseHandle(self.job)


# --------------------------------------------------------------------------------------------
# Child process
# --------------------------------------------------------------------------------------------


class ChildProcess(Session):
    """Runs the subject as a child process and speaks the protocol over its standard streams.

    The environment is an allowlist (``PATH``, ``SystemRoot`` and ``env_names``, each copied if
    set); the working directory is a new temporary directory, removed at ``stop``. One thread
    reads standard output, one writes standard input and one reads standard error, so no pipe
    can block the caller, which only waits on a queue with a deadline. ``wall_timeout_ms`` is the
    watchdog of each message; it starts when the message is handed to the writer.
    """

    def __init__(self, argv: list[str], *, env_names: tuple[str, ...] = (),
                 wall_timeout_ms: int = 30000, stderr_path: str | None = None,
                 redact: tuple[str, ...] = ()):
        if not argv or not all(type(part) is str for part in argv):
            raise ValueError("argv must be a non-empty list of strings")
        if type(wall_timeout_ms) is not int or wall_timeout_ms <= 0:
            raise ValueError("wall_timeout_ms must be a positive integer")
        self._argv = list(argv)
        self._env_names = tuple(env_names)
        self._timeout_ms = wall_timeout_ms
        self._stderr_path = stderr_path
        self._secrets = tuple(sorted(
            {text.encode("utf-8") for text in redact if text}, key=len, reverse=True))
        self._completed: set = set()
        self._proc = None
        self._cwd: str | None = None
        self._tree = None
        self._ended = False
        self._stopped = False
        self._stopping = threading.Event()
        self._lines: queue.Queue = queue.Queue(maxsize=2)  # a line can be 1 MiB: keep few
        self._outbox: queue.Queue = queue.Queue()
        self._threads: list = []
        self._err_lock = threading.Lock()
        self._err_out = None

    # -- starting ------------------------------------------------------------------------

    def _environment(self) -> dict:
        names = {name.upper() if WINDOWS else name for name in _BASE_ENV + self._env_names}
        return {key: value for key, value in os.environ.items()
                if (key.upper() if WINDOWS else key) in names}

    def _launch(self) -> None:
        self._cwd = tempfile.mkdtemp(prefix="teamsim-subject-")
        options = {"creationflags": _CREATE_SUSPENDED} if WINDOWS else {"start_new_session": True}
        self._proc = subprocess.Popen(
            self._argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            bufsize=0, env=self._environment(), cwd=self._cwd, **options)
        try:
            self._tree = _Tree(self._proc)
        except BaseException:
            self._proc.kill()  # still suspended: it has run nothing and started nothing
            self._proc.wait()
            raise
        if self._stderr_path is not None:
            try:
                self._err_out = open(self._stderr_path, "wb")
            except OSError:
                self._err_out = None
        for target in (self._read_loop, self._write_loop, self._stderr_loop):
            thread = threading.Thread(target=target, daemon=True)
            self._threads.append(thread)
            thread.start()

    def start(self, hello: dict) -> Reply:
        if self._ended or self._proc is not None:
            raise RuntimeError("the session was already started")
        wall = hello.get("wall_timeout_ms")
        if type(wall) is int and wall > 0:
            self._timeout_ms = wall  # the hello is the authority; the constructor value is a default
        try:
            self._launch()
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            self._ended = True
            self._cleanup()
            return Reply(REPLY_ENDED, (Fault(CODE_EXITED, "cannot start: " + type(exc).__name__),))
        return self._converse(hello, _start_round(self._completed, MAX_ACTIONS, hello))

    def exchange(self, event: dict) -> Reply:
        if self._ended or self._proc is None:
            raise RuntimeError("the session is not live")
        return self._converse(event, _event_round(self._completed, MAX_ACTIONS, event))

    # -- the three pipe threads ----------------------------------------------------------

    def _emit(self, item) -> None:
        while not self._stopping.is_set():
            try:
                self._lines.put(item, timeout=_POLL_S)
                return
            except queue.Full:
                pass

    def _read_loop(self) -> None:
        stream, held, refused = self._proc.stdout, bytearray(), False
        while True:
            try:
                chunk = stream.read(min(_CHUNK, LINE_LIMIT - len(held)))
            except (OSError, ValueError):
                chunk = b""
            if not chunk:
                break
            if refused or self._stopping.is_set():
                continue  # keep draining so the child cannot block, keep nothing
            held += chunk
            while True:
                end = held.find(b"\n")
                if end < 0:
                    break
                self._emit(("line", bytes(held[:end])))
                del held[:end + 1]
            if len(held) >= LINE_LIMIT:
                refused = True
                held.clear()
                self._emit(("overlong", b""))
        try:
            stream.close()
        except OSError:
            pass
        self._emit(("eof", b""))

    def _write_loop(self) -> None:
        stream = self._proc.stdin
        try:
            while True:
                data = self._outbox.get()
                if data is None:
                    break
                view = memoryview(data)
                while view:
                    view = view[stream.write(view):]
        except (OSError, ValueError):
            pass
        try:
            stream.close()
        except OSError:
            pass

    def _scrub(self, data: bytes) -> bytes:
        for secret in self._secrets:
            data = data.replace(secret, _REDACTED)
        return data

    def _stderr_loop(self) -> None:
        """Copy standard error to the log file with every secret replaced, also one that is
        split across two reads: the last ``longest secret - 1`` bytes are held back until the
        next read, so a secret cannot straddle the cut."""
        stream = self._proc.stderr
        keep = max((len(secret) for secret in self._secrets), default=1) - 1
        hold = b""

        write = self._write_err

        while True:
            try:
                chunk = stream.read(_CHUNK)
            except (OSError, ValueError):
                chunk = b""
            if not chunk:
                break
            data = self._scrub(hold + chunk)
            if keep:
                hold, data = data[-keep:], data[:-keep]
            write(data)
        write(self._scrub(hold))
        try:
            stream.close()
        except OSError:
            pass

    def _write_err(self, data: bytes) -> None:
        with self._err_lock:
            if self._err_out is not None and data:
                try:
                    self._err_out.write(data)
                    self._err_out.flush()
                except (OSError, ValueError):
                    self._err_out = None

    def _write_logs(self, rnd) -> None:
        """Subject ``log`` messages go through the redactor into the standard-error file."""
        lines = ["[log %s] %s\n" % pair for pair in rnd.logs]
        if rnd.log_dropped:
            lines.append("[teamsim: %d log lines dropped]\n" % rnd.log_dropped)
        if lines:
            self._write_err(self._scrub("".join(lines).encode("utf-8")))

    # -- one message ---------------------------------------------------------------------

    def _recv(self, deadline_ns: int):
        """Next thing from the child: ("line"|"overlong"|"eof", bytes), ("exit", b"") when the
        process has ended but its pipe is held open, or ("timeout", b"")."""
        ended_before = False
        while True:
            remaining = deadline_ns - time.monotonic_ns()
            if remaining <= 0:
                return "timeout", b""
            try:
                return self._lines.get(timeout=min(remaining / 1e9, _POLL_S))
            except queue.Empty:
                if self._proc.poll() is not None:
                    if ended_before:  # one more interval has passed with nothing to read
                        return "exit", b""
                    ended_before = True

    def _converse(self, message: dict, rnd: _Round) -> Reply:
        line = encode(message)
        if len(line) > LINE_LIMIT:
            raise ValueError("message longer than the line limit")
        deadline = time.monotonic_ns() + self._timeout_ms * 1_000_000
        self._outbox.put(line)
        reply = None
        while reply is None:
            kind, raw = self._recv(deadline)
            if kind == "line":
                try:
                    reply = rnd.take(parse_line(raw))
                except Invalid as bad:
                    reply = rnd.fail(bad.code, bad.detail)
            elif kind == "overlong":
                reply = rnd.fail(CODE_LINE_TOO_LONG, "no line feed in %d bytes" % LINE_LIMIT)
            elif kind == "timeout":
                reply = rnd.fail(CODE_TIMEOUT, "no answer within %d ms" % self._timeout_ms)
            else:
                try:
                    code = self._proc.wait(0.2)
                except subprocess.TimeoutExpired:
                    code = None
                reply = rnd.fail(CODE_EXITED, "standard output closed" if code is None
                                 else "exit code %d" % code)
        self._write_logs(rnd)
        if reply.end == REPLY_ENDED:
            self._ended = True
        return reply

    # -- stopping ------------------------------------------------------------------------

    def stop(self, reason: str, t_ms: int) -> Reply:
        if self._stopped:
            return Reply(REPLY_CLOSED)
        self._stopped = True
        items: list = []
        try:
            if self._proc is not None:
                if self._proc.poll() is None:
                    self._outbox.put(encode({"type": "shutdown", "reason": reason, "t_ms": t_ms}))
                self._outbox.put(None)  # closes standard input
                if reason != SHUTDOWN_WATCHDOG:
                    items = self._await_exit(reason)
        finally:
            self._ended = True
            self._cleanup()
        return Reply(REPLY_CLOSED, tuple(items))

    def _await_exit(self, reason: str) -> list:
        """Wait up to the watchdog time for the child to leave by itself (protocol section 5.6)."""
        deadline = time.monotonic() + self._timeout_ms / 1000
        saw_output = eof = False
        empties = 0
        items: list = []
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if self._proc.poll() is None:
                    items.append(Fault(CODE_NO_EXIT, "still running"))
                break
            try:
                kind, _ = self._lines.get(timeout=min(remaining, _POLL_S))
            except queue.Empty:
                kind = None
            if kind in ("line", "overlong"):
                saw_output = True
            elif kind == "eof":
                eof = True
            if self._proc.poll() is not None:
                empties = empties + 1 if kind is None else 0
                if eof or empties >= 2:
                    break
        if saw_output and reason == SHUTDOWN_END_OF_RUN:
            items.insert(0, Fault(CODE_OUTPUT_AFTER_SHUTDOWN))
        return items

    def _cleanup(self) -> None:
        """Stop every process of the tree, free the threads and remove the working directory."""
        self._stopping.set()
        if self._tree is not None:
            self._tree.kill()
        if self._proc is not None:
            try:
                self._proc.wait(5)
            except subprocess.TimeoutExpired:
                pass
            self._outbox.put(None)
            for thread in self._threads:
                thread.join(3)
            with self._err_lock:
                if self._err_out is not None:
                    self._err_out.close()
                    self._err_out = None
            if self._tree is not None:
                self._tree.wait_empty(3000)
                self._tree.close()
        if self._cwd is not None:
            for _ in range(100):  # a directory can stay busy for a moment after its user ends
                shutil.rmtree(self._cwd, ignore_errors=True)
                if not os.path.exists(self._cwd):
                    break
                time.sleep(0.01)
