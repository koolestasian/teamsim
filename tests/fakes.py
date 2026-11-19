"""An in-memory scripted ``Session`` for tests.

``FakeSession(script)`` answers the engine without a subject process.
``script`` is one of:

- ``None``: every message gets the default reply (``ready`` for ``start``,
  ``done`` for each event, ``closed`` for ``stop``).
- a list of ``Reply`` objects: the first message (``start``) gets the first
  reply, the next message the second, and so on across ``start``, ``exchange``
  and ``stop``; once the list is used up the defaults apply.
- a function from the message (a dictionary: ``hello``, ``event`` or
  ``shutdown``) to a ``Reply``; returning ``None`` gives the default.

Every message received is kept, deep-copied, in ``messages`` (pass
``record=False`` to skip that for speed). ``calls`` holds ``(call, message)``.
The builders ``ready``, ``done``, ``ended``, ``closed``, ``post`` and ``fault``
make the replies and actions.
"""

import copy

from teamsim.model import (
    ACTION_POST,
    Action,
    Fault,
    REPLY_CLOSED,
    REPLY_DONE,
    REPLY_ENDED,
    REPLY_READY,
    Reply,
)

__all__ = ["FakeSession", "closed", "done", "ended", "fault", "post", "ready"]


def ready(name: str = "fake", version: str = "0") -> Reply:
    return Reply(REPLY_READY, name=name, version=version)


def done(*items, wake_at_ms=None) -> Reply:
    return Reply(REPLY_DONE, items=tuple(items), wake_at_ms=wake_at_ms)


def ended(*items) -> Reply:
    """A reply that ends the session; the last item should be a ``Fault``."""
    return Reply(REPLY_ENDED, items=tuple(items))


def closed(*items) -> Reply:
    return Reply(REPLY_CLOSED, items=tuple(items))


def post(surface: str, text: str, reply_to=None, data=None, kind=ACTION_POST) -> Action:
    return Action(kind=kind, surface=surface, text=text, data=data, reply_to=reply_to)


def fault(code: str, detail=None) -> Fault:
    return Fault(code, detail)


class FakeSession:
    def __init__(self, script=None, *, record: bool = True):
        self._script = script
        self._index = 0
        self._record = record
        self.calls: list = []

    @property
    def messages(self) -> list:
        return [message for _, message in self.calls]

    def _reply(self, call: str, message: dict, default: Reply) -> Reply:
        if self._record:
            self.calls.append((call, copy.deepcopy(message)))
        script = self._script
        reply = None
        if callable(script):
            reply = script(message)
        elif script is not None and self._index < len(script):
            reply = script[self._index]
        self._index += 1
        return default if reply is None else reply

    def start(self, hello: dict) -> Reply:
        return self._reply("start", hello, ready())

    def exchange(self, event: dict) -> Reply:
        return self._reply("exchange", event, done())

    def stop(self, reason: str, t_ms: int) -> Reply:
        message = {"type": "shutdown", "reason": reason, "t_ms": t_ms}
        return self._reply("stop", message, closed())
