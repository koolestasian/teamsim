# teamsim (working name)

**Synthetic users for testing your software: one person, a team or a whole community.**

[![CI](https://github.com/koolestasian/teamsim/actions/workflows/ci.yml/badge.svg)](https://github.com/koolestasian/teamsim/actions/workflows/ci.yml)
![Status: pre-alpha](https://img.shields.io/badge/status-pre--alpha-orange)
![Python 3.14+](https://img.shields.io/badge/python-3.14%2B-blue)
![Licence: MIT or Apache-2.0](https://img.shields.io/badge/licence-MIT%20or%20Apache--2.0-lightgrey)

Testing a product properly needs people using it: someone who enters things, changes their
mind, makes mistakes and comes back a week later, or a group who post, decide, message each
other privately and paste things they shouldn't. Most people building software, students
especially, don't have those people to test with.

teamsim gives you them. You choose who uses your product (how many synthetic users, and each
one's role, habits and traits), teamsim plays them in a local sandbox, plants facts it knows
(a decision, a reversal, a private message, a pasted password, an absence) and scores your
software against them. It runs on your machine, with no real accounts and no real servers.

> **Pre-alpha.** What runs today is a prototype built to test one product with a six-person
> simulated team. The general engine is designed but not yet built. See [Status](#status).

## Who it is for

Anyone building software, at any stage from the first runnable build:

- **A single-user tool:** one synthetic user works with it over days or weeks.
- **A social or multi-user feature:** ten synthetic users use it at once.
- **Software a team works in** (a bot, an AI agent, a shared workspace): a ten-person
  company team with roles, private conversations and people who are away.

The method is the same at every size, so a product can start with one user and add more as
it grows.

## What it catches

Software fails in ways a quick manual test never shows, because the right answer depends on
who knew what, where and when:

- acting on a decision that was reversed last week;
- following an instruction from someone with no say over it;
- repeating in a public place what was said in private;
- posting back a password someone pasted by mistake;
- missing what happened while someone was away, or getting a due date wrong across time zones.

## How it works

1. **Choose your users.** A scenario pack describes the synthetic users, the places they act,
   a timeline of what they do and the facts their actions carry, including who is allowed to
   know each one. Packs are data files, not code. Presets (a solo user, a small team, a
   community) with editable size, roles, habits and traits are planned.
2. **teamsim plays them** in a local sandbox while your software joins, watches or is used
   directly. Synthetic users are scripted and seeded by default, so a run repeats exactly. A
   user can optionally be model-driven, so it can answer what your software actually says;
   its replies are recorded, so that run can be replayed too.
3. **teamsim scores the result** from the final observable state against the planted facts.
   Each check returns pass, fail, not applicable (the fact never reached your software) or
   harness error. Model replies never decide a score.

A trait changes what a synthetic user does (how fast it responds, how carefully it follows
instructions, how often it makes a mistake), never what it thinks of your product.

The decisions behind this are in [ADR 0006](docs/adr/0006-core-shape.md) (engine),
[ADR 0007](docs/adr/0007-scope-simulated-teammates-sandbox.md) and
[ADR 0008](docs/adr/0008-scope-synthetic-users-any-software.md) (scope).


## Status

| Part | State |
|---|---|
| [`prototypes/teamctx-sim/`](prototypes/teamctx-sim/) | **Working.** An end-to-end simulation built to test [teamctx](https://github.com/koolestasian/discord-team-context): a six-person simulated team chats through a local Discord emulator while the product syncs it, and a checker scores sync, commands, search quality, visibility, prompt injection, catch-up after an absence and due dates across time zones. 230 offline tests |
| Research | **Done for now.** Prior art, workspace emulators, a review of 455 papers, stack options and a market check ([docs/research/](docs/research/)) |
| Design | **Decided.** Stack, engine shape and scope ([ADRs 0004, 0006, 0007 and 0008](docs/adr/)) |
| Engine | Not started |

### Roadmap

1. The general engine: scenario packs, simulated time, the record of who knows what, checks,
   run records and replay.
2. One product other than teamctx tested end to end, with the prototype's checks ported.
3. Presets: choose the number of synthetic users and each one's role, habits and traits
   instead of writing a pack by hand. A single-user scenario comes with this step.
4. Synthetic users that operate software directly (an API, a command line, a browser), after
   research into existing tools.
5. Optional model-driven users, recorded for replay.

## Try the prototype

The unit tests run offline on Linux, macOS and Windows:

```sh
git clone https://github.com/koolestasian/teamsim.git
cd teamsim
python -I -m unittest discover -s prototypes/teamctx-sim/tests
```

A live run needs the Discord emulator and a teamctx build; the
[runbook](prototypes/teamctx-sim/RUNBOOK.md) covers setup. Its realism mode reproduces patterns
seen in real student team chat, never its content: handles instead of names, one thought split
over several messages, reactions instead of replies, pasted AI answers, a pasted password
([REALISM.md](prototypes/teamctx-sim/REALISM.md)).

## Repository layout

| Path | Contents |
|---|---|
| [`docs/adr/`](docs/adr/) | Architecture decision records |
| [`docs/research/`](docs/research/) | Research notes with sources and dates, the bibliography and figures |
| [`prototypes/teamctx-sim/`](prototypes/teamctx-sim/) | The working prototype |
| [`fixtures/`](fixtures/) | The fictional demo team dataset and a pinned teamctx schema |

## Contributing and security

The project is pre-alpha and the engine does not exist yet, so open an issue before starting
anything larger than a small fix. See [CONTRIBUTING.md](.github/CONTRIBUTING.md) and the
[code of conduct](.github/CODE_OF_CONDUCT.md). Report vulnerabilities privately as described
in [SECURITY.md](.github/SECURITY.md).

teamsim is a working name and will change before the first release.

## Licence

Licensed under either of [Apache License 2.0](LICENSE-APACHE) or [MIT license](LICENSE-MIT),
at your option. All names, messages and IDs in fixtures and prototypes are fictional.
