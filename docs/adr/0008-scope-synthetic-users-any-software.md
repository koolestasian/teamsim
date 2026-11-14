# 0008. Scope: synthetic users for any software, from one person to an organisation

- Status: Accepted
- Date: 2026-11-13
- Deciders: maintainer
- Plan reference: none

## Context

[ADR 0007](0007-scope-simulated-teammates-sandbox.md) limited teamsim to software built for
teams and described the simulated people as a team. The maintainer's intent is wider. Someone
building any product, at any point in its development, should be able to put synthetic users
in front of it. One person using a single-user tool, ten people using a new social feature
and a ten-person company team working on a project are the same request at different sizes,
and the person running the test decides how many users there are and what each one is like.

Three facts shape how the scope can widen:

- The engine in [ADR 0006](0006-core-shape.md) does not depend on the number of actors or on
  chat. Only its wording does ("an actor is a simulated teammate").
- Evidence that simulated users can give useful product feedback is weak, and no study was
  found that validates predicting how people react to a product
  ([literature synthesis](../research/2026-11-lit-synthesis.md), finding 6).
- A persona description does not guarantee the behaviour a test needs (same synthesis,
  finding 2). A trait that exists only as a sentence in a prompt cannot be relied on.

## Decision

- **teamsim is a sandbox of synthetic users for testing your own software.** The software
  under test can be anything that can be run locally and observed through an adapter: a
  single-user tool, a product with social or multi-user features, or software a whole team
  works in. The scenario matches the product: one user, a pair, a community, or an
  organisation with roles and reporting lines.
- **It applies from the first runnable build.** The smallest scenario is one synthetic user
  and one planted fact. Nothing requires a finished product or an existing test setup.
- **The population is configurable.** The person running the test sets the number of
  synthetic users and, for each one, a role, habits and personality traits. Presets cover
  common shapes (a solo user, a small team, a community) and every field of a preset can be
  changed.
- **Traits change what a synthetic user does, never what it thinks of the product.** A trait
  is a named parameter with a measurable effect on behaviour: how quickly the user responds,
  how much it writes, how carefully it follows instructions, how often it makes a mistake,
  whether it probes limits. In scripted runs, traits are resolved into a scenario pack offline
  with keyed draws (ADR 0006, sections 2 and 3), so a run still repeats exactly. In
  model-driven runs, traits also condition the wording, under the rules of ADR 0007. A trait
  ships only with a test showing that the behaviour it produces differs in the stated way.
- **Scoring is unchanged.** teamsim plants facts it knows and checks the software's
  observable state against them, at every population size. For one user the facts are things
  such as what the user entered, asked for, changed their mind about or is not allowed to see.
  Synthetic users do not give opinions, ratings or adoption predictions; simulated feedback
  stays parked under the bar of [ADR 0003](0003-scope-tests-and-simulated-feedback.md).
- **Environments go beyond a chat workspace.** A synthetic user may act in an emulated
  workspace the software joins (as the prototype does) or operate the software directly
  through an interface adapter such as an API, a command line or a browser. Chat stays the
  first environment. Which direct interface comes first is decided after a prior-art pass.
- **Unchanged from ADR 0007:** scripted, seeded behaviour is the default; model-driven users
  are optional, recorded for replay and never decide a verdict; the audit and benchmark work
  stays out of this repository; runs are local.

This amends ADR 0007 (its restriction to team-facing software is removed) and ADR 0006 (an
**actor** is a synthetic user of any kind; a **surface** is any place an actor can act,
including the software under test itself). ADR 0004 is unchanged.

## Alternatives considered

- **Stay with team-facing software only.** A smaller scope and one environment to build. It
  turns away most people who would use the tool: a builder whose product has one user, or
  whose multi-user feature is not a team feature, has the same need.
- **Add opinion feedback for single-user products** ("was this confusing?"). It is what
  single-user testing tools usually offer and it needs no planted facts. The evidence does
  not support it, and it would give up the one property that makes a teamsim result
  checkable.
- **Free-text personas given to a model, by default.** The quickest way to make every user
  editable. Runs would not repeat from a seed, and the research found that a description
  alone does not produce the behaviour reliably.

## Consequences

### Good

- One tool covers a product as it grows: a solo test first, more users when it gains
  multi-user features.
- Results stay comparable across sizes, because the scoring method is the same.
- The engine design needs no change, only wider terms.

### Bad

- Operating software directly (a browser, a command line) is a new adapter family with its
  own cost and reliability problems, and none of it is designed yet.
- For some single-user products few facts can be planted, and teamsim will test little of
  them. This limit has to be stated, not hidden behind opinions.
- Each trait needs its own measurement, which slows down adding them.
- The working name describes only part of the scope.

### Follow-ups

- Research direct interface adapters (API, command line, browser) and choose the first.
- Specify the population part of the pack schema: count, roles, traits and presets.
- Define the first traits with the test that measures each one.
- Write one single-user scenario with planted facts, to show the method holds at size one.
- Update the README and contributor documents (done with this ADR).
