# Engine modules, version 0

This document fixes the interfaces between the modules of the engine, and the run-time
rules that the pack format (`pack-format.md`) and the subject protocol
(`subject-protocol.md`) leave to the engine. The shared types live in `teamsim/model.py`;
matching lives in `teamsim/match.py`. Every name below is part of the contract: a module may
add private helpers, but it does not rename, remove or change the meaning of these.

All core modules (`teamsim/`) use the standard library only, run on Python 3.12 or later,
and read no clock, random source or environment, except `teamsim/subject.py`, which starts
and times processes, and `teamsim/cli.py`, which reads and writes files.

## 1. Data flow

```
population.toml --generate--> pack dir --pack.load--> Pack
Pack + Session --engine.run--> log entries (deliveries, observations, notes)
Pack + log entries --checks.evaluate--> verdicts       (uses ledger.Ledger)
header + entries + verdicts --record.build--> RunResult --record.write--> record.jsonl
RunResult --report.markdown / report.json_obj--> report.md / report.json
record.jsonl + Pack --record.replay--> RunResult with the same digest
```

Nothing downstream of the engine reads the subject's output except through log entries, and
the subject never receives facts, checks, the seed, the pack id or the pack path.

## 2. `teamsim.engine`

```python
run(pack: Pack, session: Session, *, wall_timeout_ms: int = 30000) -> tuple[LogEntry, ...]
```

`run` drives one session through the pack and returns the log. Internally it is a pure step
function over an explicit state (virtual time, the queue, membership, presence, the message
store, armed and fired triggers, the log); `run` is the only loop that talks to the session.
The engine draws nothing: every time comes from the pack or from what the subject did.

### 2.1 Numbering and order

- Log entries are numbered `n = 1, 2, ...` in the order they are appended. The record header
  is not an entry.
- Scripted events are processed in order of `(time, actor id, event id)`, compared by code
  point. An event that becomes due during processing (an `after` or a fired trigger) joins
  the queue under the same key; virtual time never decreases, so an event due at the current
  time whose key sorts before the event being processed is processed next.
- A tick sorts after every scripted event due at the same time.
- `seq` values sent to the subject start at 1 and increase by 1 per message actually sent.

### 2.2 Applying an event and who receives it

The engine applies the event to its state, then appends one `Delivery`.

- `recipients` are the actor members of the event's surface (never the subject), in
  ascending code-point order. For a membership change (`join`, `leave`) they are the members
  before the change together with the members after it, so the actor who joins or leaves is
  included. Presence (`away`, `back`) does not change who receives: an away actor is still a
  member, and what it missed is computed by the ledger.
- The subject receives the event when the session is live, it is a member of the surface and
  it is not down. Changes to the subject itself follow one rule: a change that adds the
  subject (`subject_join`, `subject_up`) is delivered after it applies, and a change that
  removes it (`subject_leave`, `subject_down`) is delivered before it applies. The subject
  therefore always learns of its own membership and presence changes and receives nothing
  while down.
- When the subject receives the event, the `Delivery` carries the `seq` sent; otherwise its
  `seq` is absent. The event message is built only from the event's public fields (protocol
  section 4.1): `id`, `surface`, `actor` and the kind's payload. `discloses`, `probe`,
  `depends_on` and the time form are never sent.
- An event whose actor is not a member of its surface at that time (possible only through
  a `join` that comes later or a `leave` that came earlier, pack format section 7) is still
  applied and delivered to the current members; the engine does not drop it.

### 2.3 What the subject sends back

For each message sent, the session returns a `Reply` (section 4). The engine appends, in the
order received:

- an `Observation` of kind `action` for each `Action` it can apply, with `readers` = the
  actor members of the action's surface at that time, in code-point order;
- an `Observation` of kind `subject_error`, code `rejected_action`, keeping the action, for an
  `Action` on a surface the subject is not a member of at that time, or whose `reply_to`
  names no event delivered to the subject on that surface;
- an `Observation` of kind `subject_error` or `subject_stalled` for each `Fault`, with its
  code and detail;
- finally `ready` (answer to `hello`, `seq` 0, with `name` and `version`) or `done` (with
  `wake_at_ms` when given).

Every observation carries the virtual time and `seq` of the message it answers.

### 2.4 Triggers

An event with an `on` time form is **armed** at the time its last `depends_on` event happens,
or at time 0 when it has none. Its window is `[armed, armed + within_ms]`, inclusive.

- `subject_post` fires on the first applied subject action of kind `post` on the named
  surface whose virtual time lies in the window.
- `subject_mentions` fires on the first applied subject action of any kind whose `text`
  matches the actor's id, or the actor's `display` name when it has one, by
  `match.contains`.
- A fired event happens at the action's virtual time plus `delay_ms` (0 when absent), at
  most once. A rejected action never fires a trigger.

An event happens only if every event it depends on (`depends_on`, `after` anchor, `target`)
has happened first. An event that never happens is not an error: at the end of the run the
engine appends one `Note` with code `not_fired` for each such event, in timeline order.
Pack authors who want a trigger to follow a probe name the probe in `depends_on`.

### 2.5 Ticks

A `done` with `wake_at_ms` later than the event's time asks for one tick; a newer request
replaces an older pending one. A tick is delivered as protocol kind `tick` with an empty
payload and logged as a `Delivery` of kind `tick` with no event, actor or surface. A tick due
while the subject is down is not sent; the engine appends a `Note` with code `tick_dropped`
and detail `down`. Ticks never extend the run: a tick pending after the last scripted event
gets a `tick_dropped` note with detail `after_end`.

### 2.6 Start, faults and the end of the run

1. The engine appends `Note(start)` at time 0 and calls `session.start(hello)`. The `hello`
   lists the surfaces the subject is a member of at time 0 (protocol section 4.1).
2. When a reply ends the session (`Reply.end == "ended"`), the engine appends
   `Note(shutdown)` with detail `error` (or `watchdog` for a `timeout` fault), calls
   `session.stop`, appends what that reply holds, and **continues the run without the
   subject**: later events are still applied and delivered to actors, with no `seq`.
3. The run ends when the queue is empty. The end time is the time of the last event applied
   (0 for an empty timeline). A live session then gets `Note(shutdown)` with detail
   `end_of_run` and `session.stop("end_of_run", end_time)`; its reply is appended.
4. Then `tick_dropped` (if a tick is pending) and `not_fired` notes are appended.

Subject `log` messages and standard error never enter the log; they go to the redacted
standard-error file. Exit codes and wall-clock durations are not in the log either.

## 3. `teamsim.ledger` and `teamsim.checks`

```python
class Ledger:
    def __init__(self, pack: Pack, entries: tuple[LogEntry, ...]): ...
    def exposed(self, who: str, fact_id: str, t_ms: int) -> bool
    def current(self, key: str, who: str, t_ms: int) -> str | None   # a fact id
    def allowed(self, who: str, fact_id: str, t_ms: int) -> bool
    def missed(self, who: str, t0_ms: int, t1_ms: int) -> tuple[str, ...]   # keys, sorted
    def table(self) -> tuple[dict, ...]   # for `inspect`; canonical values only

evaluate(pack: Pack, entries: tuple[LogEntry, ...]) -> tuple[Verdict, ...]
```

`who` is an actor id or the subject's id. The ledger is computed only from the pack and the
log: an actor is exposed through a `Delivery` that lists it in `recipients`, the subject
through a `Delivery` that has a `seq`. Membership at a time is replayed from the delivered
`join`, `leave`, `subject_join` and `subject_leave` events over the pack's initial members.

"The response to a probe" (engine spec 6.3) is: the applied `action` observations whose
`seq` equals the probe's delivery `seq`, plus later applied actions whose `reply_to` is the
probe's event id. A probe that was not delivered to the subject has no response.

A form matches by `match.contains`. When an action carries `data` with a key equal to the
fact's key, the value under that key is compared exactly with the fact's value and decides
the match for that action, whatever the text says.

The `harness` check passes when the log is consistent with section 2: every event that
happened has exactly one `Delivery`, deliveries follow the order of section 2.1, and every
event the subject should have received (member, not down) carries a `seq`. It fails with
`not_delivered` when the session ended early and such an event went unsent, and with
`out_of_order` when the order is broken (possible only in an altered record). A check whose
probe should have reached the subject but went unsent because the session had ended gets
`harness_error`, not `no_response`.

`evaluate` returns one verdict per check, in the pack's check order. `policy` is true when the
check has the tag `policy`. `events` and `entries` list the evidence (event ids, entry
numbers), `detail` lists ids only (keys, actor ids, fact ids), never subject text.

## 4. `teamsim.subject`

```python
class Session(Protocol):
    def start(self, hello: dict) -> Reply        # end: "ready" or "ended"
    def exchange(self, event: dict) -> Reply     # end: "done" or "ended"
    def stop(self, reason: str, t_ms: int) -> Reply   # end: "closed"

class InProcess(Session):
    def __init__(self, handler, *, max_actions: int = 100): ...

class ChildProcess(Session):
    def __init__(self, argv: list[str], *, env_names: tuple[str, ...] = (),
                 wall_timeout_ms: int = 30000, stderr_path: str | None = None,
                 redact: tuple[str, ...] = ()): ...

validate_message(obj: object, state: str) -> ...   # shared by both transports
```

- `hello` and `event` are protocol messages as dictionaries, built by the engine.
- `Reply.items` holds, in arrival order, each well-formed `Action` whose `in_reply_to` is the
  outstanding `seq`, and a `Fault` for each rejected or ending message. When the session ends,
  the last item is the ending `Fault` and `end` is `"ended"`. Whether an action can be applied
  (membership, `reply_to`) is decided by the engine, not the session.
- `InProcess` wraps any object with `handle(message: dict) -> list[dict]`. The handler's
  returned messages pass through the same validation as lines read from a child process, so
  one subject logic gives the same `Reply` through both transports. An exception raised by
  the handler ends the session with code `exited` and the exception's type name as detail.
  There is no watchdog in process.
- `ChildProcess` follows the protocol: filtered environment (`PATH`, `SystemRoot` and the
  names in `env_names`), a new temporary working directory removed at `stop`, line limit,
  per-message watchdog, process-tree stop. Standard error goes to `stderr_path` with every
  string in `redact` (the caller passes the pack's secret values and the values of the
  passed environment variables) replaced by `[redacted]`, even when split across reads.

## 5. `teamsim.record`

```python
header(pack: Pack, subject: dict, *, engine: str) -> RecordHeader
build(header: RecordHeader, entries, verdicts) -> RunResult   # computes the digest
digest(lines: list[dict]) -> str        # canon.hash_of over every line before the digest
write(result: RunResult, path) -> None
read(path) -> RunResult                 # verifies the digest; raises RecordError
write_timing(rows: list[dict], path) -> None
class ReplaySession(Session):
    def __init__(self, entries: tuple[LogEntry, ...]): ...
replay(record_path, pack: Pack) -> RunResult
```

`record.jsonl` is one canonical JSON object per line (`canon.canon`), `\n` line ends, UTF-8
without a byte-order mark, in the order of `RunResult.lines()`. The subject descriptor names
a built-in (`{"builtin": "<name>"}`) or the command's program name only
(`{"command": "<basename>"}`); it never holds arguments, paths or environment values.

Replay groups the recorded observations by what they answered: those after `Note(start)`
answer `start`; those after a `Delivery` with a `seq` answer that `exchange`; those after
`Note(shutdown)` answer `stop`. `ReplaySession` turns them back into a `Reply`: `action`
observations and `rejected_action` errors become `Action` items (so the engine rejects the
same ones again), other errors and stalls become `Fault` items. `replay` runs the engine with
it, evaluates the checks and builds a new `RunResult`; the record is reproduced when the
digests are equal. `timing.jsonl` is never part of the digest.

## 6. `teamsim.generate`

```python
load_population(path) -> dict               # validated population object
generate(population: dict) -> Pack
generate_file(population_path, out_dir) -> Pack   # writes with pack.write
PRESETS: tuple[str, ...]                     # ("social", "solo", "team")
```

Presets are data files in `teamsim/presets/<name>.toml`. Every choice is a keyed draw with
scope `[population seed, user id, trait or slot name, index]`. The pack's provenance holds
the generator version and the population file's hash.

## 7. `teamsim.controls`

```python
NAMES: tuple[str, ...]      # "null", "oracle", "defect:stale", ... (engine spec section 7)
make(name: str, pack: Pack) -> handler      # for subject.InProcess
expected(name: str, pack: Pack) -> dict[str, tuple[str, str | None]]   # check id -> (verdict, reason)
matrix(pack: Pack) -> dict[str, dict[str, tuple[str, str | None]]]    # observed, by control
validate(pack: Pack) -> list[str]           # one line per mismatch; empty when the pack is valid
```

Controls may read the pack. They are the only subjects that do.

## 8. `teamsim.report` and `teamsim.cli`

```python
report.markdown(result: RunResult, *, matrix=None) -> str
report.json_obj(result: RunResult, *, matrix=None) -> dict
cli.main(argv: list[str] | None = None) -> int
```

A report is built from a `RunResult` (and an optional control matrix) only. Subject text is
escaped before it is written.
