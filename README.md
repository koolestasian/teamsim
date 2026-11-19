# teamsim (working name)

**Synthetic users for testing your software: one person, a team or a whole community.**

[![CI](https://github.com/koolestasian/teamsim/actions/workflows/ci.yml/badge.svg)](https://github.com/koolestasian/teamsim/actions/workflows/ci.yml)
![Status: pre-alpha](https://img.shields.io/badge/status-pre--alpha-orange)
![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)
![Licence: MIT or Apache-2.0](https://img.shields.io/badge/licence-MIT%20or%20Apache--2.0-lightgrey)

Testing a product properly needs people using it: someone who enters things, changes their
mind, makes mistakes and comes back a week later, or a group who post, decide, message each
other privately and paste things they shouldn't. Most people building software, students
especially, don't have those people to test with.

teamsim gives you them. You choose who uses your product (how many synthetic users, and each
one's role, habits and traits), teamsim plays them in a local sandbox, plants facts it knows
(a decision, a reversal, a private message, a pasted password, an absence) and scores your
software against them. It runs on your machine, with no real accounts and no real servers.

> **Pre-alpha.** The engine runs scenarios end to end from the command line: generate a pack
> from a population file, run software against it, score it and replay the run. Software
> connects in process (Python) or as a child process over standard input and output. There is
> no package release yet. See [Try it](#try-it) and [Status](#status).

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
   know each one. Packs are data files, not code. Three presets (`solo`, `team`, `social`)
   generate a pack from a short population file that sets the number of users and each one's
   role, habits and traits.
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
[ADR 0008](docs/adr/0008-scope-synthetic-users-any-software.md) (scope), and
[ADR 0009](docs/adr/0009-version-0-built-in-workspace-subject-protocol-python-floor.md)
(what version 0 contains).

## Status

| Part | State |
|---|---|
| [`prototypes/teamctx-sim/`](prototypes/teamctx-sim/) | **Working.** An end-to-end simulation built to test [teamctx](https://github.com/koolestasian/discord-team-context): a six-person simulated team chats through a local Discord emulator while the product syncs it, and a checker scores sync, commands, search quality, visibility, prompt injection, catch-up after an absence and due dates across time zones. 235 offline tests |
| Research | **Done for now.** Prior art, workspace emulators, a review of 455 papers, stack options and a market check ([docs/research/](docs/research/)) |
| Design | **Decided.** Stack, engine shape, scope and version 0 ([ADRs 0004 and 0006 to 0009](docs/adr/)) |
| Engine ([`teamsim/`](teamsim/)) | **Version 0 runs.** Tested on Python 3.12 and 3.14: the [scenario pack format](docs/spec/pack-format.md), the population generator with `solo`, `team` and `social` presets, the scheduler and built-in workspace, both [subject protocol](docs/spec/subject-protocol.md) transports, the record of who was exposed to what, six check kinds, control subjects that test the checks, run records with replay, and the command line. Not built yet: reduction of a failing run, an HTTP adapter, model-driven users, a package release |

### Roadmap

1. Version 0 of the engine ([ADR 0009](docs/adr/0009-version-0-built-in-workspace-subject-protocol-python-floor.md)):
   simulated time, a workspace built into the engine, the record of who knows what, checks,
   run records and replay, with software under test connected in process or as a child
   process over standard input and output, and presets that generate packs. Runs now;
   reduction of a failing run and a package release remain.
2. One product other than teamctx tested end to end, with the prototype's checks ported.
3. Synthetic users that operate software directly (an API, a command line, a browser), after
   research into existing tools.
4. Optional model-driven users, recorded for replay.

## Try it

The engine needs Python 3.12 or later and nothing else. From a clone:

```sh
git clone https://github.com/koolestasian/teamsim.git
cd teamsim
python -m teamsim demo
```

`demo` checks the `team-ten` pack with the control subjects, then runs two example subjects
against it and writes a record and a Markdown and JSON report for each to `teamsim-demo/`.
[`naive_bot`](examples/naive_bot.py) stores everything and answers by word overlap;
[`careful_bot`](examples/careful_bot.py) tracks who could see what, who decided and what
replaced what. Neither reads the answer key. On `team-ten`, `naive_bot` repeats the private
offsite budget and hiring plan to people who should not see them and gives stale answers;
`careful_bot` passes every check. Its cue lists were written against the `team` preset's wording:
on the `solo` pack it fails two checks, `c.reading-format` and `c.study-slot`, both as `stale`.
Neither bot implements the `social` operations, so on `social-ten` both get `no_response` on every
answer check.

The other commands:

```sh
python -m teamsim generate populations/team-ten.toml -o my-pack   # population file -> pack
python -m teamsim validate packs/team-ten                          # do the checks catch the seeded defects?
python -m teamsim run packs/team-ten --builtin careful_bot         # one subject, one pack
python -m teamsim run packs/team-ten --subject "python my_bot.py"  # your program, over stdin/stdout
python -m teamsim inspect packs/team-ten                           # who was exposed to which fact, when
python -m teamsim replay teamsim-demo/record-naive_bot.jsonl --pack packs/team-ten
```

See a run in the browser: `python -m teamsim serve`, then open http://127.0.0.1:8765. Pick a pack and one of the built-in
bots; the page lists the checks with the messages behind them. It listens on loopback only.

Each command's `--help` lists its options. How a program speaks to the engine is in the
[subject protocol](docs/spec/subject-protocol.md).

## Try the prototype

Both test suites run offline on Linux, macOS and Windows with Python 3.12 or later and
nothing else installed:

```sh
python -I -m unittest discover -s prototypes/teamctx-sim/tests   # the prototype
python -I -m unittest discover -s tests -t .                     # the engine
```

A live run needs the Discord emulator and a teamctx build; the
[runbook](prototypes/teamctx-sim/RUNBOOK.md) covers setup. Its realism mode reproduces patterns
seen in real student team chat, never its content: handles instead of names, one thought split
over several messages, reactions instead of replies, pasted AI answers, a pasted password
([REALISM.md](prototypes/teamctx-sim/REALISM.md)).

## Repository layout

| Path | Contents |
|---|---|
| [`teamsim/`](teamsim/) | The engine package (standard library only) |
| [`tests/`](tests/) | Engine tests and golden vectors |
| [`packs/`](packs/) | Scenario packs: `minimal` (hand-written), `lantern-shelf` (converted from the fictional fixture in `fixtures/demo/`) and `team-ten`, `solo`, `social-ten` (generated) |
| [`populations/`](populations/) | Population files the packs are generated from |
| [`examples/`](examples/) | Example subjects: `naive_bot` and `careful_bot` |
| [`docs/spec/`](docs/spec/) | Formats and protocols the engine implements |
| [`docs/adr/`](docs/adr/) | Architecture decision records |
| [`docs/research/`](docs/research/) | Research notes with sources and dates, the bibliography and figures |
| [`prototypes/teamctx-sim/`](prototypes/teamctx-sim/) | The working prototype |
| [`fixtures/`](fixtures/) | The fictional demo team dataset and a pinned teamctx schema |

## Contributing and security

The project is pre-alpha and the engine is incomplete, so open an issue before starting
anything larger than a small fix. See [CONTRIBUTING.md](.github/CONTRIBUTING.md) and the
[code of conduct](.github/CODE_OF_CONDUCT.md). Report vulnerabilities privately as described
in [SECURITY.md](.github/SECURITY.md).

teamsim is a working name and will change before the first release.

## Licence

Licensed under either of [Apache License 2.0](LICENSE-APACHE) or [MIT license](LICENSE-MIT),
at your option. All names, messages and IDs in fixtures and prototypes are fictional.
