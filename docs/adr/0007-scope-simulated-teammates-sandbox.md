# 0007. Scope: a sandbox of simulated teammates; the audit and benchmark leave

- Status: Accepted
- Date: 2026-11-13
- Deciders: maintainer
- Plan reference: none

## Context

[ADR 0005](0005-scope-instrument-first.md) narrowed teamsim to a deterministic test instrument
whose public work was an audit of other people's multi-user agent benchmarks, then a small
benchmark, and only third a tool for testing your own product. On 2026-11-13 that instrument
direction was split into a separate project with its own repository and plan. Two projects
pursuing one plan in two places would split effort and confuse contributors, so this
repository returns to the idea it started with
([ADR 0002](0002-start-from-the-teamctx-prototype.md)): a sandbox in which you pick a team,
teamsim plays it in a local fake workspace, plants known facts and scores the software under
test against them, for people without a professional test setup.

The research in `docs/research/` stays shared; it was written before the split and serves
both projects.

## Decision

- **teamsim is a sandbox for testing your own team-facing software**: bots, agents and
  multi-user tools. The first user is a builder of such software, including students. The
  first workspace is chat (the Discord emulator the prototype uses).
- **Out of scope here:** auditing other people's benchmarks, publishing a benchmark, and
  disclosure work. The audit and benchmark designs leave this repository.
- **Scripted, seeded teammates are the default** and follow
  [ADR 0006](0006-core-shape.md) as written.
- **Model-driven teammates are an optional layer.** A pack may mark an actor as model-driven,
  so that it can answer what the subject actually says. Each model reply is stored in the run
  record like an observation, so a run replays exactly from its record. A run that uses the
  layer is not reproducible from pack and seed alone and is reported as such. Model replies
  never decide a verdict: checks still read the ledger and the final state.
- **Simulated feedback** keeps the bar from [ADR 0003](0003-scope-tests-and-simulated-feedback.md):
  measured or not shipped. Nothing is built for it before scored tests are in use.
- **First milestone:** the general engine from ADR 0006, used to test one product other than
  teamctx end to end.

This supersedes ADR 0005 and amends ADR 0006 as follows:

- Section 3's "A run never calls a model" and section 7's "out of scope: model-driven turns at
  run time" hold for scripted runs only.
- The determinism contract (section 7) covers runs without the model layer.
- The control subjects of section 5 are the null agent, the reference solution and its mutants
  (one deliberate defect each), plus noise, flood and oracle-probing agents where a check
  depends on them.

ADR 0004 is unchanged.

## Alternatives considered

- **Keep ADR 0005 here as well.** Both projects would then claim the same plan, and every
  contributor or agent would have to work out which repository owns it.
- **Model-driven teammates by default** (ADR 0003's "a local model by default"). It makes the
  team feel more real, but gives up exact replay from a seed in the common case, and
  [the literature synthesis](../research/2026-11-lit-synthesis.md) found no direct validation
  that simulated feedback predicts team reactions.
- **No model at any point.** Simplest and fully deterministic. A sandbox for testing an agent
  that converses then cannot test the conversation, which is what many of its users build.

## Consequences

### Good

- One plan per repository: this one is the sandbox, the instrument lives elsewhere.
- Scripted runs keep every guarantee of ADR 0006.
- Agents that need a reply to an open question can be tested, with the cost stated.

### Bad

- Two run modes with different guarantees; reports must say which mode produced them.
- The model layer needs a model endpoint, a budget and a redaction path for the run record.

### Follow-ups

- Specify the model-driven actor in the pack schema and the run-record format before
  building it.
- Choose the second product to test, and record why.
- Rewrite the README for the sandbox (done with this ADR).
