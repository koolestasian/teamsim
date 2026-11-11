# Architecture decision records

An architecture decision record (ADR) captures one decision about how teamsim is built: the
context, the choice, the alternatives weighed, and what follows from it. ADRs explain why the
code is the way it is, so nobody has to guess or reopen settled questions.

## Format

Copy [`0000-template.md`](0000-template.md). Each ADR has a title `# NNNN. Title`, a header
(Status, Date, Deciders, Plan reference) and four sections: **Context**, **Decision**,
**Alternatives considered** and **Consequences**. Keep it to one page and cite a dated source
for any fact that is not obvious. Until there is a design plan, leave "Plan reference" as
"none".

Statuses: `Proposed`, `Accepted`, `Superseded by NNNN`, `Deprecated`.

## Adding or changing an ADR

- **New decision:** take the next free number, name the file `NNNN-kebab-title.md`, add a row
  below, and submit it in a pull request.
- **Changing a decision:** do not rewrite an accepted ADR. Write a new one that says what it
  replaces and set the old one's status to `Superseded by NNNN`.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-dual-licence.md) | Dual licence: MIT OR Apache-2.0 | Accepted |
| [0002](0002-start-from-the-teamctx-prototype.md) | Start from the teamctx simulation prototype; decide the stack after research | Accepted (goals amended by 0003) |
| [0003](0003-scope-tests-and-simulated-feedback.md) | Scope: scored tests and simulated feedback | Accepted |
