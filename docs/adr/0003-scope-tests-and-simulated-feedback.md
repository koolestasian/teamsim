# 0003. Scope: scored tests and simulated feedback

- Status: Superseded by 0005
- Date: 2026-11-11
- Deciders: maintainer
- Plan reference: none

## Context

The README and [ADR 0002](0002-start-from-the-teamctx-prototype.md) set three goals for
teamsim: testing rather than opinion prediction, ground truth first, and easy to run. The
first goal followed from the first prior-art pass
([2026-11-prior-art.md](../research/2026-11-prior-art.md)), which found opinion prediction
crowded and its evidence weak.

Reviewing the scope before the research milestone, the maintainer decided that teamsim should
also let its simulated teammates give feedback on the product under test, not only exercise
it. Someone testing a product alone wants to know both whether it works with a team and how a
team might react to it.

The evidence against simulated feedback still stands and has to be handled, not ignored:
synthetic respondents are sycophantic and flat (NN/g, 2024-06-21), vary far less than real
people (NN/g, 2026-10-16), and miss real results by double-digit margins (Pew, 2026-09). Which
model plays the user changes the outcome ("Lost in Simulation", arXiv 2601.17087). The project
rule that every user-facing feature is measurable applies here too.

## Decision

- teamsim produces two kinds of output:
  1. **Scored tests:** the simulator plants known facts and scores the product against them.
     This stays the core, and what the prototype already does.
  2. **Simulated feedback:** the simulated teammates give opinions on the product (useful,
     confusing, whether they would adopt it).
- Simulated feedback ships only when it can be measured. At a minimum that means measured
  diversity across personas, a sycophancy check, and a comparison with published human results
  where they exist. It is always presented as hypotheses to check with real people, never as a
  verdict. If the research finds no honest way to measure it, the feature waits.
- Ground truth and ease of use stay as goals: one command, a local model by default, and
  presets instead of code.
- Out of scope for now: hardware. Real platform accounts, driving a product's UI, and hosted
  models are not ruled out.
- Left to the research milestone, not decided here: the first user, and what teammates can do
  in the first version (chat only, tasks and issues, or a code repository too).
- This replaces "testing rather than opinion prediction" in the goals ADR 0002 refers to. The
  rest of ADR 0002 stands.

## Alternatives considered

- **Testing only (the 2026-11-10 direction):** keeps the project on the side with the stronger
  evidence and fewer competitors, but leaves out what a solo builder also wants to know: how
  a team might react to the product.
- **Feedback as a first-class verdict:** the most attractive pitch, but it repeats the claims
  the evidence does not support and would break the measurability rule.

## Consequences

### Good

- One run of the simulation can answer both "does it work with a team" and "what might a team
  say about it".
- Its known weaknesses are stated up front, and the feature has a bar to meet before it ships.

### Bad

- More scope before a first release, and a feature with a real chance of not meeting its bar.
- It moves teamsim closer to a crowded, well-funded market (opinion simulation).

### Follow-ups

- Research milestone: evidence on feedback reliability and how to measure it, and a
  recommendation on the first user.
- README "Direction" updated to match this ADR.
