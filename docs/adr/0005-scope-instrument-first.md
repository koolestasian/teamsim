# 0005. Scope: a deterministic test instrument first; audit, then a small benchmark

- Status: Accepted
- Date: 2026-11-12
- Deciders: maintainer
- Plan reference: none

## Context

[ADR 0003](0003-scope-tests-and-simulated-feedback.md) set two outputs (scored tests and
simulated feedback), "a local model by default", and left the first user to research. The
research has since answered parts of this:

- [The literature synthesis](../research/2026-11-lit-synthesis.md) found no direct validation
  that simulated feedback predicts team reactions, and only indirect support for scripted
  teammates being realistic. It recommended a model-free default.
- Demand from builders of team bots is inferred, not observed
  ([prior art](../research/2026-11-prior-art.md), [gap check](../research/2026-11-gap-check.md)).
- Funded companies sell model-driven simulated workplaces, and several multi-user agent
  benchmarks exist (GroupMemBench, ClawsBench and MuPPET are in the literature notes; a closer
  one, arXiv 2611.02633, appeared in November 2026 and is being read before the benchmark is
  designed). Competing on realism or on size is not a contest a small project wins.
- Audits cited in [the product-checks note](../research/2026-11-lit-product-checks.md) show
  that graders themselves fail: reachable answer keys, weak assertions, payloads that never
  arrive.

What a scripted, seeded team can offer that model-driven simulation cannot is exact
repeatability, and with it failures that can be reduced to their cause and graders that can be
tested.

## Decision

- teamsim is a **test instrument**, in the sense a crash-test dummy is one: calibrated,
  repeatable and known, not a realistic person. The project makes no claim that its teammates
  behave like people.
- **No model at run time.** A run uses a scripted, seeded team. Any model-written text is
  produced beforehand as a recorded transformation of a scenario pack
  ([ADR 0006](0006-core-shape.md)). This replaces "a local model by default".
- **Simulated feedback is parked.** It is not removed from the long-term scope, but nothing
  is built for it until scored tests are in use, and then only as the bounded held-out pilot
  the synthesis describes. It stays subject to ADR 0003's bar: measured or not shipped.
- **Order of public work:**
  1. A control-agent audit of public multi-user agent benchmarks
     ([design](../design/control-agent-audit.md)), reported to their authors first.
  2. A small benchmark (20 to 30 tasks): an agent acts as one member of a scripted team, and
     is graded only from workspace state by graders that have passed the same controls.
     Published in a task format existing harnesses can run.
  3. The same engine as a tool for testing a team-facing bot or product.
- The first workspace is chat. Tasks, issues and repositories follow demand.
- Reports show counts with intervals and state their units and dependence; small samples are
  shown, not hidden.
- The scenario pack, not the runner, is treated as the public interface.

This supersedes ADR 0003. The rest of ADR 0002 stands.

## Alternatives considered

- **Keep ADR 0003 as written.** One run answers both "does it work" and "what would a team
  say". The second answer has no validation behind it, and a model in every run gives up
  repeatability, which is the one property others do not offer.
- **Tool for bot builders first.** It is what the prototype already does. Its demand is
  unproven, and a tool shows less about grader quality than a benchmark with tested graders.
- **A large benchmark.** More visible if it lands, but larger suites from better-resourced
  groups already exist; a small one with proven graders is a different contribution.

## Consequences

### Good

- Every published number can be reproduced from a seed and a pack.
- The audit needs no model budget: control agents are scripts.
- The project's claims shrink to ones it can demonstrate.

### Bad

- Scripted teammates cannot hold an open conversation. Tasks must be designed so success does
  not depend on one ([ADR 0006](0006-core-shape.md)).
- Running models against the benchmark costs API money; a five-task pilot must measure it
  before the full run.
- An audit of other people's work can be received badly. The design sets a disclosure
  process to reduce that.

### Follow-ups

- Read arXiv 2611.02633 and its code; write the benchmark design against it.
- Update the README "Direction" section (done with this ADR).
- Choose a final name before the repository is public: the working name collides with
  existing products ([gap check](../research/2026-11-gap-check.md)).
