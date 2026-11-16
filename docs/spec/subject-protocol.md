# Subject protocol, version 1

- Status: specification. Neither transport is implemented yet;
  [ADR 0009](../adr/0009-version-0-built-in-workspace-subject-protocol-python-floor.md)
  requires this document to exist first.
- Date: 2026-11-16
- Protocol version described: `v: 1`

The subject is the software under test. The engine plays synthetic users on virtual time and
tells the subject what they do; the subject answers with what it does. This document defines
the messages, their order, the limits, and what the engine does when a subject breaks a rule.
It is meant to be enough to write a subject in any language, or a second engine.

The shape of the engine is decided in [ADR 0006](../adr/0006-core-shape.md). Terms used here:
an **actor** is a synthetic user; a **surface** is a place where actors and the subject act
(`channel`: many members; `direct`: one actor and the subject); the **run record** is the
engine's log of what happened; an **observation** is a record entry about something the
subject did or failed to do.

## 1. Transports

There is one message set and two ways to carry it.

- **In process.** A Python object with one method, `handle(message) -> list[message]`. Each
  message is a `dict` holding the fields defined in section 4. Used for control subjects,
  tests and subjects written in Python. Section 8 lists what differs.
- **Child process.** The engine starts the subject as a child process and exchanges one JSON
  object per line over the child's standard input (engine to subject) and standard output
  (subject to engine). Any language can implement it. Sections 3 and 7 define the bytes and
  the process environment.

Version 1 opens no socket.

The exchange is in lockstep. The engine sends one message and waits for the subject to say it
has finished with it. Virtual time advances only between messages, never while one is
outstanding.

## 2. Values

Every value in every message, in both directions and on both transports, is one of: string,
integer, boolean, array, object. There is no floating-point number and no null. An optional
field that has no value is left out.

- An integer is in the range -(2^53 - 1) to 2^53 - 1. On the wire it is written as a JSON
  number without fraction or exponent: `1.0` and `1e3` are not integers.
- A string is Unicode in Normalisation Form C and contains no lone surrogate. The engine
  rejects other strings; it never normalises them.
- An object key matches `[a-z0-9_.:-]+`. No key appears twice in one object.
- Arrays and objects nest at most 32 deep, counting the message object as level 1.

The field `type` names the message. All times are virtual milliseconds from the start of the
scenario, as integers, in fields whose names end in `_ms`. The one exception is
`wall_timeout_ms`, which is wall-clock milliseconds.

## 3. Framing (child-process transport)

- A message is one line: the UTF-8 encoding of one JSON object, followed by one line feed
  (byte `0A`). No byte order mark.
- The engine writes each object with keys sorted, no whitespace, and non-ASCII characters as
  themselves, and ends the line with a line feed alone. A subject must not depend on key
  order.
- The engine accepts from the subject any JSON object that obeys section 2: keys in any
  order, whitespace between tokens, `\u` escapes. It accepts a line that ends in a carriage
  return and a line feed (`0D 0A`) and ignores that one carriage return. A carriage return
  alone does not end a line.
- A line, terminator included, is at most 1,048,576 bytes (1 MiB) in either direction.
- JSON requires control characters inside strings to be escaped (RFC 8259, section 7 [5]),
  so a correctly encoded string never contains a raw line feed. A subject must also not put
  a line feed between tokens: one object, one line.
- An empty line, a line that is not valid UTF-8, or one that does not parse to a single object
  obeying section 2 is malformed (section 6).
- Bytes after the last line feed when the stream ends are an incomplete line and are
  discarded.

Both sides open the pipes in binary mode and do their own encoding. Text-mode streams change
bytes on some systems: section 13 records a Python child on Windows whose default text
streams wrote `0D 0A` and decoded its input with a legacy code page.

A subject must flush its output after `ready`, `done` and `error`. Output left in a buffer
looks like silence, and the watchdog ends the session.

## 4. Messages

In the tables, "yes" under Required means the message is invalid without the field. A
receiver ignores fields it does not know (section 10).

### 4.1 Engine to subject

#### `hello`

Sent once, first.

| Field | Type | Required | Values and meaning |
|---|---|---|---|
| `type` | string | yes | `hello` |
| `v` | integer | yes | `1`. The protocol version of the whole session. |
| `subject_id` | string | yes | The id under which the subject appears in `members` lists. |
| `t_ms` | integer | yes | Virtual time at which the session starts. 0 or more. |
| `surfaces` | array of objects | yes | The surfaces the subject is a member of at `t_ms`, in ascending code-point order of `id`. May be empty. |
| `wall_timeout_ms` | integer | yes | Wall-clock time the subject has to finish answering each message. More than 0. The default is 30,000. |

Each element of `surfaces`:

| Field | Type | Required | Values and meaning |
|---|---|---|---|
| `id` | string | yes | Surface id. |
| `kind` | string | yes | `channel` or `direct`. |
| `members` | array of strings | yes | Ids of the members at `t_ms`, in ascending code-point order, the subject included. |

#### `event`

Something happened that the subject can see, or a wake-up the subject asked for.

| Field | Type | Required | Values and meaning |
|---|---|---|---|
| `type` | string | yes | `event` |
| `seq` | integer | yes | 1 or more, strictly greater than every earlier `seq` in the session. Not necessarily consecutive. |
| `t_ms` | integer | yes | Virtual time of the event. Never less than the `t_ms` of an earlier message. |
| `kind` | string | yes | One of the kinds below. |
| `payload` | object | yes | Depends on `kind`. |

For every kind except `tick` the payload has these fields:

| Field | Type | Required | Values and meaning |
|---|---|---|---|
| `id` | string | yes | Id of the event. |
| `surface` | string | yes | Id of the surface it happened on. |
| `actor` | string | yes | Id of the actor who did it. |

and these, by kind:

| `kind` | More payload fields | Meaning |
|---|---|---|
| `post` | `text` (string) | The actor posted `text`. |
| `edit` | `target` (string), `text` (string) | The actor replaced the text of the post with id `target`. |
| `delete` | `target` (string) | The actor deleted the post with id `target`. |
| `react` | `target` (string), `emoji` (string) | The actor reacted to the post with id `target`. |
| `join`, `leave` | none | The actor joined or left the surface. |
| `away`, `back` | none | The actor became unavailable or available. |
| `op` | `op` (string), `args` (object) | The actor performed the named operation on the product, on a `direct` surface. Names and arguments are defined by the scenario. |
| `subject_join`, `subject_leave` | none | The subject was added to or removed from the surface. |
| `subject_down`, `subject_up` | none | The subject became unreachable or reachable. It receives nothing in between. |
| `tick` | none; the payload is `{}` | A wake-up the subject asked for with `wake_at_ms`. |

The engine delivers an event only if the subject is a member of the event's surface at that
time and is not down. A subject answers every event, including one whose kind it does not
know, with `done` or `error`.

#### `shutdown`

The session is over. The subject sends nothing more and exits.

| Field | Type | Required | Values and meaning |
|---|---|---|---|
| `type` | string | yes | `shutdown` |
| `reason` | string | yes | `end_of_run`: the scenario finished. `error`: the session ended because of a fault (section 6). `watchdog`: the subject did not answer in time. |
| `t_ms` | integer | yes | Virtual time at which the session ends. |

### 4.2 Subject to engine

#### `ready`

The answer to `hello`.

| Field | Type | Required | Values and meaning |
|---|---|---|---|
| `type` | string | yes | `ready` |
| `v` | integer | yes | `1`. Must equal the `v` of `hello`. |
| `name` | string | yes | Name of the subject, for the run record. |
| `version` | string | yes | Version of the subject, for the run record. |

#### `action`

Something the subject does in answer to the outstanding event.

| Field | Type | Required | Values and meaning |
|---|---|---|---|
| `type` | string | yes | `action` |
| `in_reply_to` | integer | yes | The `seq` of the outstanding event. |
| `kind` | string | yes | `post`, `react` or `result`. |
| `surface` | string | yes | A surface the subject is a member of. |
| `text` | string | yes | `post`: the text posted. `react`: the emoji. `result`: a readable form of the result; may be empty. |
| `data` | object | no | `result`: the structured result of an operation. Recorded but not interpreted for other kinds. |
| `reply_to` | string | `react`: yes; otherwise no | The id of an event delivered to the subject on the same surface. `post`: the post being answered. `react`: the post reacted to. `result`: the `op` event whose result this is. |

The engine applies each valid action when it arrives, in the order of arrival, at the virtual
time of the outstanding event.

#### `done`

The subject has finished with the outstanding event and is idle.

| Field | Type | Required | Values and meaning |
|---|---|---|---|
| `type` | string | yes | `done` |
| `in_reply_to` | integer | yes | The `seq` of the outstanding event. |
| `wake_at_ms` | integer | no | A virtual time later than the event's `t_ms` at which the subject wants a `tick`. |

#### `log`

A diagnostic line. Never scored and never shown to an actor.

| Field | Type | Required | Values and meaning |
|---|---|---|---|
| `type` | string | yes | `log` |
| `level` | string | yes | `debug`, `info`, `warning` or `error`. |
| `text` | string | yes | The line. |

The engine keeps the first 100 `log` messages received while one message is outstanding and
records how many more it dropped.

#### `error`

The subject cannot continue.

| Field | Type | Required | Values and meaning |
|---|---|---|---|
| `type` | string | yes | `error` |
| `in_reply_to` | integer | yes | The `seq` of the outstanding event, or 0 in answer to `hello`. |
| `code` | string | yes | A short name chosen by the subject. |
| `text` | string | yes | A description for the run record. |

## 5. The exchange

### 5.1 States

| State | What is outstanding | The subject may send | Left by |
|---|---|---|---|
| starting | `hello` | `log`, then `ready` or `error` | `ready` (to idle), a fault |
| idle | nothing | nothing | the engine sending `event` (to busy) or `shutdown` (to closing) |
| busy | one `event` | `action` and `log` in any number within the limits, then `done` or `error` | `done` (to idle), a fault |
| closing | nothing; `shutdown` was sent | nothing | the subject's exit, or the engine stopping it (to closed) |

One event is outstanding at a time. The engine sends the next message only after the
previous one was answered. It processes the subject's output only while a message is
outstanding; anything the subject writes while idle is handled as part of the next exchange
and judged by the rules of section 6.

### 5.2 Start-up

1. The engine starts the subject (section 7) and sends `hello`. The watchdog starts.
2. The subject answers `ready` with the same `v`. It may send `log` messages first.
3. A subject that does not implement the `v` it was given answers `error` with
   `in_reply_to` 0 and code `version_mismatch`, then exits.
4. If `ready` carries another `v`, the engine ends the session with code `version_mismatch`.

Version 1 has no negotiation: the engine speaks one version and says which.

### 5.3 Events

1. The engine sends `event` with a new `seq`.
2. The subject sends zero or more `action` and `log` messages. Each `action` names that
   `seq` in `in_reply_to`.
3. The subject sends `done` with the same `seq`. The event is then complete.
4. Virtual time advances only after `done`, after `error`, or after the engine has ended the
   session for a fault or a timeout.

At most 100 `action` messages are accepted for one event. An `action` that arrives after the
`done` for its `seq` is a violation: it is logged and not applied.

### 5.4 Wake-ups

A subject with timers does not read the wall clock. It asks for a wake-up in virtual time.

- `done` may carry `wake_at_ms`, later than the `t_ms` of the event it answers.
- At that virtual time the engine sends an `event` of kind `tick` whose `t_ms` is the time
  asked for.
- A later request does not cancel an earlier one. Requests for the same time give one
  `tick`.
- When scripted events are due at the same virtual time as a `tick`, they are delivered
  first.
- A `tick` that falls while the subject is down is dropped, not postponed.
- The engine does not extend a run to deliver a `tick`.

### 5.5 Watchdog

The watchdog is a wall-clock limit of `wall_timeout_ms` on each outstanding message, `hello`
included. It starts when the engine hands the message to the transport, so it also covers a
subject that never reads its input. Nothing but the completing answer (`ready`, `done`,
`error`) stops it: `action` and `log` messages do not extend it.

When it expires the engine logs `subject_stalled`, sends `shutdown` with reason `watchdog`
without waiting for the subject to read it, and stops the subject.

The watchdog does not touch virtual time. The observation carries the virtual time of the
outstanding message. No wall-clock reading is used to order or to stamp anything in the run
record, and virtual time does not move while the engine waits.

### 5.6 Shutdown

1. The engine sends `shutdown` and closes the subject's standard input.
2. The subject sends nothing more and exits. Its exit code is recorded and not judged.
3. For the reasons `end_of_run` and `error` the engine waits up to `wall_timeout_ms` for the
   exit. If the subject is still running then, the engine logs `subject_stalled` with code
   `no_exit`. For the reason `watchdog` it does not wait.
4. The engine then stops every process that belongs to the subject, including processes the
   subject started, and removes the working directory.

Lines not yet processed when `shutdown` is sent, and everything read afterwards, are
discarded. After `end_of_run`, if there was any such output, the engine logs one
`subject_error` with code `output_after_shutdown`.

## 6. Violations

Everything a subject sends is untrusted. No violation is skipped silently: each one produces
an observation, `subject_stalled` or `subject_error`, with a code, at the virtual time of the
outstanding message. Actions applied before a violation stay applied.

There are two outcomes. **Rejected**: the message is not applied, the session continues, the
watchdog keeps running, and the message counts towards the limit of 100. **Ends the session**:
the engine sends `shutdown` with the reason shown and follows section 5.6.

| Case | Observation | Code | Outcome |
|---|---|---|---|
| Late action: an `action` whose `in_reply_to` names an event that is already complete | `subject_error` | `late_action` | Rejected |
| Wrong `in_reply_to`: any other `action` or `done` whose `in_reply_to` is not the outstanding `seq` | `subject_error` | `wrong_in_reply_to` | Rejected. A mismatched `done` does not complete the event. |
| An `action` that is well formed but cannot be applied: a surface the subject is not a member of, or a `reply_to` that names no event delivered to it on that surface | `subject_error` | `rejected_action` | Rejected |
| More than 100 actions: the 101st `action` or rejected message for one event | `subject_error` | `too_many_actions` | Ends the session, reason `error`. The first 100 are not undone. |
| Unknown message type | `subject_error` | `invalid_message` | Ends the session, reason `error` |
| A known message with a required field missing, a field of the wrong type, or a value outside those allowed; a message not allowed in the current state (`action` or `done` before `ready`, a second `ready`) | `subject_error` | `invalid_message` | Ends the session, reason `error` |
| Malformed line (section 3) | `subject_error` | `malformed_line` | Ends the session, reason `error` |
| Over-long line: 1,048,576 bytes read without a line feed | `subject_error` | `line_too_long` | Ends the session, reason `error`. The engine buffers no more than the limit. |
| `ready` with a `v` other than the one sent | `subject_error` | `version_mismatch` | Ends the session, reason `error` |
| The subject sends `error` | `subject_error` | `reported`, with the subject's own `code` and `text` | Ends the session, reason `error`, whatever its `in_reply_to` |
| Timeout: no completing answer within `wall_timeout_ms` | `subject_stalled` | `timeout` | Ends the session, reason `watchdog`. Virtual time is not touched (section 5.5). |
| Early exit: the process ends, or its standard output reaches end of file, before the engine sent `shutdown` | `subject_error` | `exited`, with the exit code when the process has ended | Ends the session. `shutdown` with reason `error` is sent only if the process is still running. |
| Still running `wall_timeout_ms` after `shutdown` | `subject_stalled` | `no_exit` | The engine stops it |
| Output after `shutdown` with reason `end_of_run` | `subject_error` | `output_after_shutdown` | Discarded |

Two details matter for a second engine:

- An early exit must be detected from the process itself and not only from end of file. A
  process started by the subject can inherit the pipes and keep them open after the subject
  has gone (measured in section 13).
- An exit that happens while no message is outstanding is acted on when the engine next has
  a message to send. The observation then carries that message's virtual time, so the record
  does not depend on when the engine happened to notice.

After a session has ended the engine delivers nothing more to the subject. Whether the run
continues without the subject or stops there is the engine's rule, not this protocol's.

## 7. What a subject is given

### 7.1 Never sent

No message contains, and nothing given to the subject's process reveals:

- the seed of the run;
- the pack's id, hash or path (a pack is the scenario, as data);
- facts, checks or expected values;
- which events disclose a fact, which events are probes, and how events depend on each other
  or are scheduled.

A subject sees a planted fact only as part of the text or arguments of an event delivered to
it. The answer key stays in the engine's process: it is not sent, not placed in the working
directory and not put in the environment.

### 7.2 Environment

The child's environment is an allowlist. It contains `PATH`, on Windows also `SystemRoot`,
and the variables the person running the scenario names; each is copied from the engine's
environment if set there. Nothing else is passed. Names are compared without regard to case
on Windows. The engine adds no variable of its own.

`SystemRoot` is in the base list because of a measurement (section 13): without it a Python
child on Windows started but could not create a socket.

### 7.3 Working directory

The child starts in a new, empty temporary directory made for the session. The engine removes
it after the subject has stopped. A subject must not expect to find its program files there,
and anything it wants to keep must be written elsewhere.

### 7.4 Standard streams

Standard input and output are pipes and carry only protocol lines. Standard error is
redirected to a log file. It has no meaning in the protocol and is never scored. Its content
passes through the engine's redactor before it is stored with a run or shown.

## 8. In-process transport

`handle(message)` is called once for `hello`, once for each `event` and once for `shutdown`.
The messages and rules are those above, with these differences:

- There is no framing. The return value is a list of messages in the order sent. Each
  returned message is checked like a parsed line, including the size limit applied to its
  encoded form, so both transports accept the same messages. A value that breaks section 2
  is logged with code `malformed_line`, as it would be on the wire.
- The answer to `hello` ends with `ready` or `error`. The answer to an `event` ends with
  `done` or `error`. The answer to `shutdown` is an empty list; anything else is
  `output_after_shutdown`.
- Messages that follow the first `done` or `error` in a returned list are treated as if they
  had arrived while the next message was outstanding, which is where the child-process
  transport would read them.
- A list that ends without `done` or `error` is logged as `subject_stalled` with code
  `no_done` and ends the session.
- An exception raised by `handle` is logged as `subject_error` with code `raised` and ends
  the session.
- There is no watchdog, because a call cannot be interrupted from outside. A `handle` that
  does not return stops the run. In-process subjects run inside the engine's process and are
  trusted code.

## 9. Limits of the design

- The engine is deterministic. The subject is not made deterministic. A subject that reads
  the wall clock, runs its own timers or threads, or calls a model can differ between runs.
  Such a run is replayed from its recorded actions, not by running the subject again.
- A subject that acts on its own wall-clock timers cannot take part in compressed time. It
  must use `wake_at_ms` and the `t_ms` it is given.
- A child process is not a sandbox. The answer key is never sent to it, but code running as
  a child can read the disk and use the network with the rights of the person who started
  the run. Run code you do not trust in a container or a virtual machine.
- Stopping a subject stops the processes the engine can account for. Section 13 states what
  that covers on Windows.

Known gaps in version 1:

- The subject is not told the ids the engine gives to the subject's own actions, so a
  `target` may name an id the subject has not seen.
- `subject_join` does not carry the member list of the surface joined.
- There is no limit on the number of wake-ups a subject may request, and none on the size of
  the standard error log.

## 10. Versioning

- `v` is an integer. This document describes 1. `hello` states it and `ready` repeats it.
- A receiver ignores fields it does not know. Unknown fields must still obey section 2.
- These may be added without a new version: optional fields in any message, payload fields,
  event kinds, `shutdown` reasons, observation codes. A subject therefore answers an event
  of unknown kind with `done` and treats any `shutdown` as the end.
- These need `v: 2`: a new required field, a new message type or action kind sent by the
  subject, a change in the meaning of an existing field, a removal, a change to framing or
  to the limits.
- A subject must not send a message type that is not in the version of the session.

## 11. Example transcript

A complete session. `E` marks a line written by the engine and `S` one written by the
subject; the mark and the space after it are not part of the line. Each line ends with a
line feed. The subject's lines are shown with sorted keys, which is allowed and not required.
All names and text are invented.

```text
E {"subject_id":"subject","surfaces":[{"id":"direct:bo","kind":"direct","members":["bo","subject"]},{"id":"general","kind":"channel","members":["ana","bo","subject"]}],"t_ms":0,"type":"hello","v":1,"wall_timeout_ms":30000}
S {"level":"info","text":"index empty, starting","type":"log"}
S {"name":"example-notes","type":"ready","v":1,"version":"0.1.0"}
E {"kind":"post","payload":{"actor":"ana","id":"e041","surface":"general","text":"release moves to thursday 9 april, the importer is not ready"},"seq":1,"t_ms":86400000,"type":"event"}
S {"in_reply_to":1,"type":"done"}
E {"kind":"post","payload":{"actor":"bo","id":"e042","surface":"general","text":"@subject when is the release now?"},"seq":2,"t_ms":86460000,"type":"event"}
S {"in_reply_to":2,"kind":"post","reply_to":"e042","surface":"general","text":"Thursday 9 April, says ana.","type":"action"}
S {"in_reply_to":2,"type":"done","wake_at_ms":90000000}
E {"kind":"tick","payload":{},"seq":3,"t_ms":90000000,"type":"event"}
S {"in_reply_to":3,"kind":"post","surface":"general","text":"Reminder: the release is on Thursday 9 April.","type":"action"}
S {"in_reply_to":3,"type":"done"}
E {"kind":"op","payload":{"actor":"bo","args":{"limit":3,"query":"release date"},"id":"e050","op":"search","surface":"direct:bo"},"seq":4,"t_ms":90060000,"type":"event"}
S {"data":{"results":[{"source":"e041","text":"release moves to thursday 9 april, the importer is not ready"}]},"in_reply_to":4,"kind":"result","reply_to":"e050","surface":"direct:bo","text":"1 result","type":"action"}
S {"in_reply_to":4,"type":"done"}
E {"kind":"react","payload":{"actor":"ana","emoji":"👍","id":"e051","surface":"general","target":"e042"},"seq":5,"t_ms":93600000,"type":"event"}
S {"in_reply_to":5,"type":"done"}
E {"reason":"end_of_run","t_ms":172800000,"type":"shutdown"}
```

The subject then exits with code 0. In this session virtual time went from 0 to two days;
the wall-clock time taken is whatever the subject needed to answer.

## 12. Example subject in another language

A subject for Node.js that answers posts which mention it. **This example has not been run**:
it is not part of the project's tests, and Node.js was not installed where this document was
checked. Treat it as an illustration of the rules, not as tested code.

```js
// Subject protocol version 1: answers posts that mention the subject.
const readline = require("node:readline");

// One object, one line.
const send = (message) => process.stdout.write(JSON.stringify(message) + "\n");
const lines = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
let me = "";

lines.on("line", (line) => {
  const message = JSON.parse(line);
  if (message.type === "hello") {
    if (message.v !== 1) {
      send({ type: "error", in_reply_to: 0, code: "version_mismatch", text: "version 1 only" });
      lines.close();
      return;
    }
    me = message.subject_id;
    send({ type: "ready", v: 1, name: "example-echo", version: "0.1.0" });
  } else if (message.type === "event") {
    const { kind, payload } = message;
    if (kind === "post" && payload.actor !== me && payload.text.includes("@" + me)) {
      send({
        type: "action",
        in_reply_to: message.seq,
        kind: "post",
        surface: payload.surface,
        text: ("you said: " + payload.text).normalize("NFC"), // strings must be NFC
        reply_to: payload.id,
      });
    }
    // Every event is answered, whatever its kind. No number in any message is a fraction.
    send({ type: "done", in_reply_to: message.seq });
  } else if (message.type === "shutdown") {
    lines.close(); // stop reading; the process then ends by itself
  }
});
```

## 13. Implementation notes

`tests/spike_stdio.py` is a throwaway script that checks whether the child-process transport
can be built on the Python standard library. It is not the transport and is not collected by
the test suite. Run it with `python tests/spike_stdio.py`; it prints one line per case and
exits 0 only if every case behaved.

**Where it was run.** One machine with Windows 11 (build 26300), on 2026-11-16, with CPython
3.14.7 and CPython 3.12.10. Every case passed on both, in about 6 seconds per run. **It was
not run on macOS or Linux.** The script contains a code path for those systems (a new session
and process group, stopped with `SIGKILL`), and that path has never been executed. The
numbers below are from that one machine and are not a benchmark.

**How the engine side is built.** The child's pipes are opened unbuffered and in binary mode.
One thread reads standard output in chunks of at most 64 KiB and splits lines; one thread
writes to standard input; the main thread only waits on a bounded queue with a deadline. No
pipe operation can block the main thread.

**What was measured.**

| Case | Result on both Python versions |
|---|---|
| Lockstep | 2,000 events, each answered by one `action` and one `done`, in about 190 ms. Round trip per event: median about 90 microseconds, 99th percentile under 200, slowest under 300. |
| Text | Text in several scripts, an emoji, a tab and an escaped carriage return and line feed came back unchanged. In binary mode no carriage return was added. |
| Child using text streams | A Python child that used its default text streams ended its lines with `0D 0A`, which the engine accepted. It decoded its input as `cp1252`, the code page of that machine: accented text came back garbled, and text in other scripts came back as a lone surrogate, which was refused as malformed. |
| Watchdog | With a limit of 1,000 ms, a child that never answered was detected after 1,000 to 1,001 ms. Stopping it and freeing both threads took at most 3 ms more. |
| Child that never reads | The pipe accepted 4,096 of 262,306 bytes and the write then blocked. The watchdog still fired on time, and stopping the child released the writer thread. Writes therefore need their own thread. |
| Line limit | A line of 1,048,576 bytes was accepted and one of 1,048,577 refused. The reader never held more than 1,048,576 bytes. |
| Flood | Output without a line feed was refused at the limit. Peak traced memory in the engine process was under 1.4 MiB. |
| Malformed lines | 17 kinds were refused, each with a reason: not JSON, truncated, empty, not UTF-8, byte order mark, not an object, fraction, exponent, `NaN`, null, duplicate key, lone surrogate, not NFC, integer out of range, bad key, nesting deeper than 32, and 200,000 opening brackets. |
| Early exit | A child that exited in the middle of an event was seen as end of file within 10 ms, with its exit code. |
| Grandchild, child stalled | Killing only the child left the grandchild running and the reader blocked: no end of file 500 ms later. Stopping the whole tree ended both and freed the reader within 1 ms. |
| Grandchild, child exited | No end of file arrived, because the grandchild held the pipe. The exit was seen through the process handle after 100 to 125 ms (the script checks every 50 ms and waits one more interval for late output). |
| Environment | The child saw `PATH` and `SYSTEMROOT` and nothing else of the 93 variables set in the engine's environment. Its working directory was the new, empty one, removed afterwards. Its standard error arrived in the log file byte for byte. |
| Bare environment | With no variables at all the Python child started, but creating a socket failed with Windows error 10106. With `SystemRoot` alone it worked. |

**How the process tree is stopped on Windows.** Killing the child is not enough, as the two
grandchild cases show. The script uses a job object through `ctypes`, with no third-party
package:

1. Start the child with `CREATE_SUSPENDED`, so it has run no code.
2. Create a job object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` and put the child in it
   with `AssignProcessToJobObject`.
3. Resume the child's one thread. Every process it starts from then on belongs to the job.
4. To stop the subject, call `TerminateJobObject`. The job's accounting
   (`QueryInformationJobObject`) then shows whether any process is left; in the 11 child
   trees of each run none was.

Putting a child into its job took a median of 80 to 95 ms, nearly all of it spent finding
the suspended thread in a snapshot of every thread on the machine; this happens once per
subject start. Microsoft documents that child processes of a process in a job belong to that
job unless the job permits breakaway, which this one does not, that closing the last handle
to a job with the limit in step 2 terminates its processes, that processes created through
`Win32_Process.Create` are not associated with the job, and that nested jobs need Windows 8
or later [4]. The script does not test what happens to the subject when the engine itself
is killed.

**Not verified.** Any behaviour on macOS or Linux. A subject written in a language other than
Python. A subject that deliberately escapes its job through another service. Behaviour under
heavy load or on slow disks. The redactor, which does not exist yet: the script only shows
that standard error reaches a file unchanged.

## 14. Prior art

`done` is a conservative synchronisation barrier in the sense introduced by Chandy and Misra
[1]: the clock moves only when the subject has said it has nothing more to do at the current
time. The closest precedent read for this design is ARE [2], in which an agent calls a wait
tool and the simulation then moves from event to event, while time otherwise runs in real
time as the agent works; `wake_at_ms` gives a subject with timers the same kind of wait
without any wall-clock reading. tau2-bench [3] connects agents as in-process Python classes
that take turns with complete messages, and none of the harness documentation read for this
design describes a wire protocol for an external program that receives many events, which is
why the end of a turn is an explicit message here.

## References

1. K. M. Chandy and J. Misra, "Distributed Simulation: A Case Study in Design and Verification
   of Distributed Programs", IEEE Transactions on Software Engineering, SE-5(5), 440-452,
   September 1979. <https://doi.org/10.1109/TSE.1979.230182>. Bibliographic record checked
   2026-11-15; the text of the paper was not read for this document.
2. R. Froger, P. Andrews and others, "ARE: Scaling Up Agent Environments and Evaluations",
   arXiv:2509.17158, September 2025. <https://arxiv.org/abs/2509.17158>. Sections 2.1 and 2.4
   read 2026-11-15.
3. tau2-bench, orchestrator README.
   <https://github.com/sierra-research/tau2-bench/blob/main/src/tau2/orchestrator/README.md>.
   Read 2026-11-15.
4. Microsoft, "Job Objects", Win32 documentation.
   <https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects>. Read 2026-11-15.
5. T. Bray (editor), "The JavaScript Object Notation (JSON) Data Interchange Format",
   RFC 8259, December 2017. <https://www.rfc-editor.org/rfc/rfc8259>. Sections 2 and 7 read
   2026-11-15.
