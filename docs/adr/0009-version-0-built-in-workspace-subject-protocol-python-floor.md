# 0009. Version 0: a built-in workspace, a subject protocol, the package at the repository root, Python 3.12

- Status: Accepted
- Date: 2026-11-15
- Deciders: maintainer
- Plan reference: none

## Context

[ADR 0006](0006-core-shape.md) fixes the shape of the core and
[ADR 0008](0008-scope-synthetic-users-any-software.md) its scope, but neither says what the
first runnable version contains. Four questions were open:

- **Which workspace comes first.** [ADR 0007](0007-scope-simulated-teammates-sandbox.md) named
  the Discord emulator the prototype uses. [The emulator survey](../research/2026-11-emulators.md)
  found that no local emulator offers time control (finding 1: for weeks of history "teamsim
  has to own the clock") and that the Discord emulator is the weakest fit and closed source
  (finding 2). It also needs Node, a cost [ADR 0004](0004-python-standard-library-core.md)
  already lists. [The prototype audit](../research/2026-11-prototype-audit.md) found the
  prototype's emulator handling tied to one Windows and WSL setup.
- **How the software under test connects.** ADR 0006 puts a subject adapter at the edge of the
  engine and leaves its protocol open. ADR 0008 left the first direct interface to a prior-art
  pass.
- **Where the code lives.** A new user should be able to clone the repository and run a
  scenario with nothing but Python.
- **Which Python.** ADR 0004 requires 3.14 or later. Ubuntu 24.04 LTS ships Python 3.12.3
  ([packages.ubuntu.com](https://packages.ubuntu.com/noble/python3), read 2026-11-15), so a
  3.14 floor means installing another interpreter there before a first run. The oldest
  standard-library module the design needs is `tomllib`, added in 3.11
  ([Python documentation](https://docs.python.org/3/library/tomllib.html), read 2026-11-15).
  Python 3.12 receives security fixes until October 2028
  ([PEP 693](https://peps.python.org/pep-0693/), read 2026-11-15). The prototype's 230 tests
  pass unchanged on CPython 3.12.10, 3.13.0 and 3.14 (Windows, run 2026-11-13).

## Decision

1. **The first workspace is built into the engine.** Version 0 has no external workspace and
   no workspace adapter. Surfaces, membership, presence and the message store are engine
   state, on virtual time. There are two kinds of surface: `channel` (many members) and
   `direct` (one actor and the subject, carrying text or structured operations, which also
   covers a user operating the product directly). The workspace adapter boundary of ADR 0006
   stays in the design; porting the Discord adapter is deferred.
2. **The subject connects through one small protocol with two transports.** In process, a
   Python object that handles one message and returns its replies. Out of process, a child
   the engine starts, exchanging one JSON object per line over standard input and output.
   The exchange is in lockstep: the engine delivers one event and advances virtual time only
   after the subject answers `done`, which may carry a later virtual time at which the subject
   wants to be woken. A wall-clock watchdog stops a stalled subject without touching virtual
   time. Version 0 opens no socket. The protocol is specified in `docs/spec/` before the
   transports are written. The engine is deterministic; the subject is not claimed to be.
3. **The first direct interface after version 0 is a loopback HTTP adapter** that turns
   structured operations into requests against a product's own API. A long-poll transport and
   a Model Context Protocol server are later adapters over the same engine step. None of them
   is required for version 0.
4. **The package sits at the repository root** as `teamsim/`, with `tests/`, `packs/` and
   `examples/` beside it, so `python -m teamsim` works from a clone without an install step.
   The prototype stays in `prototypes/` unchanged, as the case study it is.
5. **The Python floor is 3.12.** The core uses only language and library features present in
   3.12, and CI tests the oldest and the newest supported versions (3.12 and 3.14) on all
   three operating systems.
6. **Version 0 is scripted runs only**: packs, the engine, the ledger and checks, control
   subjects, run records with replay, a pack generator with three population presets, and a
   command line. Model-driven users, browser and command-line adapters, simulated feedback
   and a calibrated judge are out.

This amends ADR 0004 (the floor moves from 3.14 to 3.12; everything else stands) and ADR 0007
(the first workspace is the built-in one, not the Discord emulator). It narrows ADR 0006 for
version 0 without changing it, and settles the first direct interface that ADR 0008 left open.

## Alternatives considered

- **Port the prototype's Discord adapter first.** It would show teamsim against a real chat
  protocol from the start. It needs Node and an emulator that cannot set timestamps, so
  multi-week scenarios and byte-identical records would wait on a workspace teamsim does not
  control.
- **A webhook-style HTTP protocol as the base.** Familiar to anyone who has written a bot. A
  subject built that way acknowledges a request at once and acts later, so the response says
  nothing about whether the subject is idle, and the engine could not know when to advance
  the clock. HTTP stays as an adapter for products that already expose an API.
- **A Model Context Protocol server as the base.** It fits agents that already speak it and
  nothing else: a bot or a multi-user application would need a wrapper to take part.
- **Keep the 3.14 floor.** One version to test and the newest language features. Nothing in
  the design needs them, and the cost falls on the users the project is meant for.
- **A `src/` layout.** The usual packaging advice, and it prevents importing the working tree
  by accident. It also makes the first run depend on an install step.

## Consequences

### Good

- A first run needs only Python 3.12 or later: no Node, no emulator and no network.
- The engine owns the clock, so a scenario of several weeks does not wait on real time and
  its record can be byte-identical across machines.
- Any language that can read and write lines can be a subject.

### Bad

- The built-in workspace is not a real chat product. Behaviour that depends on a platform's
  own rules (rate limits, threads, permissions) is not exercised until an adapter exists, and
  reports must say so.
- A subject that runs on its own wall-clock timers or background threads does not follow
  virtual time; it has to use the wake request and the delivered time, or accept real-time
  runs.
- A child process is not a sandbox. The answer key is never sent to it, but untrusted subject
  code can still read the disk; the documentation says to run such code in a container.
- Two Python versions on three operating systems double the CI matrix.

### Follow-ups

- Write the canonical form, the keyed draws, the pack format and the subject protocol with
  golden tests before other code (the first follow-up of ADR 0006).
- Add the new test command to CI and the contributor documents when the first core code
  lands (a follow-up of ADR 0004).
- Measure a first run on a clean Windows and a clean macOS or Linux machine (the spike named
  in ADR 0004, now without a second runtime).
