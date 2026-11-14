# 0006. Core shape: a deterministic event engine, a knowledge ledger and scenario packs

- Status: Accepted; amended by [0007](0007-scope-simulated-teammates-sandbox.md)
  (optional model-driven teammates, control subjects)
- Date: 2026-11-12
- Deciders: maintainer
- Plan reference: none

## Context

[ADR 0005](0005-scope-instrument-first.md) rests the project on exact repeatability. Three
things follow from that and are expensive to retrofit:

- Reducing a failing scenario to the few events that cause it means removing events and
  re-running. If all randomness comes from one shared stream, removing one event changes
  every later draw, and the reduced scenario is a different scenario.
- [The prototype audit](../research/2026-11-prototype-audit.md) found no multi-week simulated
  time, presets written as code, and checks coupled to one product.
- Graders need controls ([literature synthesis](../research/2026-11-lit-synthesis.md),
  finding 4): a harness whose answer key is reachable, or whose planted event never arrived,
  produces scores that mean nothing.

Terms: the **subject** is whatever is being tested (an agent or a product). An **actor** is a
simulated teammate. A **surface** is a place events happen (a channel, a direct message).

## Decision

### 1. A pure engine

The engine is a discrete-event simulation with no input or output of its own. It takes a
state and one input (a due scripted event, or an observation of something the subject did) and
returns a new state and the events to deliver. It never reads the wall clock, the environment,
the file system or a global random source. Adapters at the edge do all I/O:

- a **workspace adapter** delivers events to a workspace and reports what it observes there;
- a **subject adapter** starts and stops the subject and reports its actions.

Time is virtual: integer milliseconds from the scenario's start. An adapter maps virtual time
to real time at a chosen scale, so weeks of scenario can run in seconds where the workspace
allows it. The core uses no floating-point numbers. Ties are broken by `(time, actor id,
event id)`.

### 2. Keyed randomness

There is no random stream. Every random choice is a function of its own identity:

```
draw(seed, scope, purpose) = first 8 bytes of SHA-256(canonical(seed, scope, purpose))
```

where `scope` names what is choosing (an actor id, an event id) and `purpose` names the
choice. Removing, adding or reordering other events cannot change the result. Helpers for a
bounded integer, a choice and a shuffle are defined once in terms of `draw` and covered by
golden tests. The language's built-in generator and built-in string hashing are not used in
the core: their results are not guaranteed stable across versions or processes.

### 3. Scenario packs are data

A pack is a directory:

- `pack.toml`: format version, purpose, actors, surfaces and their members, facts, checks,
  control expectations, and stated validity limits.
- `timeline.jsonl`: one event per line.

An event has a stable `id` chosen by the author, a virtual time or a trigger, an actor, a
surface, a kind (post, edit, delete, react, join, leave, and later task or file changes), a
payload, the ids of events it depends on, and the ids of facts it discloses. Message text is
fixed in the pack. A pack is identified by the hash of its canonical form.

**Triggers are structural.** A reactive event fires on a condition over observed state: the
subject posted on a surface, mentioned or messaged an actor, performed an action, matched a
pattern the pack declares, or a time passed. Nothing interprets free text at run time. The
limit is stated plainly: an actor cannot answer an arbitrary question, and tasks must not
need it to.

**Variation is a pack-to-pack step.** Rewording, noise or model-written text produce a new
pack, offline, with the transformation recorded in it. A run never calls a model.

### 4. The knowledge ledger is derived, not written

Facts are declared once: id, kind (decision, assignment, date, secret and so on), value, the
fact it supersedes if any, who has authority over it, and who may know it. Who actually knows
what, and since when, is computed from the events that disclose each fact and the membership
of the surface at that moment. Checks read this derived state. There is one source of truth,
and a scenario cannot contradict its own answer key.

### 5. Checks, verdicts and controls

- A check is a pure function of the ledger, the final observed state and the run record. It
  declares how its expectation is known: exact, a relation between two runs, or a calibrated
  judge. Only the first two are in the first release.
- Four verdicts: **pass**, **fail**, **not applicable** (the planted event was never
  delivered, or the precondition did not hold) and **harness error**. A fact that did not
  arrive is never scored as the subject's failure.
- Every check states its expected verdict for each control subject: one that does nothing, one
  that performs the reference solution, and at least one faulty variant of that solution. A
  pack whose controls do not produce their expected verdicts does not validate. The control
  subjects are listed in [ADR 0007](0007-scope-simulated-teammates-sandbox.md).
- The ledger, the checks and the expected values are never reachable from the subject: not
  mounted, not served, not in its environment. Grading happens outside the subject's process
  and network.

### 6. Run records, replay and reduction

A run writes one record: pack hash, seed, engine version, every delivered event, every
observation with its virtual time, and every verdict. Replaying a record feeds the recorded
observations back to the engine and must reproduce the same events and verdicts exactly.

Reduction removes events that the failing check does not pin, together with their dependents,
re-runs, and keeps the removal if the failure persists in at least a stated share of repeats.
Its output is a smaller valid pack.

### 7. The determinism contract

For one engine major version: the same pack hash and seed produce a byte-identical stream of
delivered events. Golden run records in the repository enforce this in CI on all three
operating systems. The contract covers the engine, not the subject; a subject's variation is
measured by repeats and reported.

Out of scope here: model-driven turns at run time, simulated feedback, realism calibration,
and the export to other harnesses' task formats (decided with the benchmark design).

## Alternatives considered

- **One seeded generator.** Simplest to write and enough for reruns. It makes reduction and
  comparison between pack versions unsound, which removes the main reason for a scripted team.
- **Model-chosen replies with a cache.** Lets actors answer anything. The cache key includes
  the subject's text, so any change in the subject produces new, unrecorded behaviour, and a
  judge model enters the grading path.
- **Scenarios as code.** More expressive and quicker to start with. Packs then cannot be
  validated, reduced, hashed or run by another implementation.
- **A hand-written knowledge table per scenario.** Easier to read. It can disagree with the
  timeline, and the disagreement surfaces as a wrong score.

## Consequences

### Good

- A failure report is one file that anyone can replay.
- Removing an event leaves the rest of the scenario unchanged, so reduction is sound.
- Multi-week scenarios cost seconds where the workspace accepts a virtual clock.
- Another implementation, in any language, can run the same packs and be checked against the
  golden records.

### Bad

- Authoring is stricter: stable ids, explicit dependencies and declared triggers.
- Actors are less flexible than model-driven ones, by design.
- Workspaces that stamp their own wall-clock times limit time compression; the adapter must
  report what it could not honour.
- Reduction against a subject that varies between runs needs repeats, and may not converge.

### Follow-ups

- Specify the canonical form, the `draw` helpers and the pack schema with golden tests before
  other code.
- Port the prototype's reusable modules behind the two adapter boundaries.
- Test reduction on a recorded failure from the prototype before it is advertised.
