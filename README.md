# teamsim (working name)

**A simulated team for testing software that works with a team.**

[![CI](https://github.com/koolestasian/teamsim/actions/workflows/ci.yml/badge.svg)](https://github.com/koolestasian/teamsim/actions/workflows/ci.yml)
![Status: pre-alpha](https://img.shields.io/badge/status-pre--alpha-orange)
![Python 3.14+](https://img.shields.io/badge/python-3.14%2B-blue)
![Licence: MIT or Apache-2.0](https://img.shields.io/badge/licence-MIT%20or%20Apache--2.0-lightgrey)

If you build a bot, an AI agent or a tool for team chat, testing it properly needs a team:
people who post, decide, change their minds, go quiet for a week, message each other privately
and paste things they shouldn't. Most people building these tools, students especially, don't
have one to test with.

teamsim gives you one. You pick a team, teamsim plays it in a local fake workspace, plants
facts it knows (a decision, a reversal, a private message, a pasted password, an absence) and
scores your software against them. It runs on your machine, with no real accounts and no
real servers.

> **Pre-alpha.** What runs today is a prototype built to test one product. The general engine
> is designed but not yet built. See [Status](#status).

## What it catches

Team-facing software fails in ways a one-person test never shows, because the right answer
depends on who knew what, where and when:

- acting on a decision the team reversed last week;
- following an instruction from someone with no say over it;
- repeating in a public channel what was said in private;
- posting back a password someone pasted by mistake;
- missing what happened while someone was away, or getting a due date wrong across time zones.

## How it works

1. **Pick a team.** A scenario pack describes the team, its channels, a timeline of messages
   and the facts they carry, including who is allowed to know each one. Packs are data files,
   not code. Presets (choose size, roles and habits) are planned.
2. **teamsim plays it** in a local emulated workspace while your software joins or watches.
   Teammates are scripted and seeded by default, so a run repeats exactly. A teammate can
   optionally be model-driven, so it can answer what your software actually says; its replies
   are recorded, so that run can be replayed too.
3. **teamsim scores the result** from the final state of the workspace against the planted
   facts. Each check returns pass, fail, not applicable (the fact never reached your software)
   or harness error. Model replies never decide a score.

The decisions behind this are in [ADR 0006](docs/adr/0006-core-shape.md) (engine) and
[ADR 0007](docs/adr/0007-scope-simulated-teammates-sandbox.md) (scope).

## What teamsim is not

- **Not a claim about real people.** The teammates exist to exercise your software; teamsim
  makes no claim that they behave like humans.
- **Not user research.** Simulated opinions are weakly supported by current evidence
  ([literature synthesis](docs/research/2026-11-lit-synthesis.md)); that idea is parked until
  it can be measured.
- **Not for real servers.** Runs happen in local emulated workspaces.

## Status

| Part | State |
|---|---|
| [`prototypes/teamctx-sim/`](prototypes/teamctx-sim/) | **Working.** An end-to-end simulation built to test [teamctx](https://github.com/koolestasian/discord-team-context): a six-person simulated team chats through a local Discord emulator while the product syncs it, and a checker scores sync, commands, search quality, visibility, prompt injection, catch-up after an absence and due dates across time zones. 230 offline tests |
| Research | **Done for now.** Prior art, workspace emulators, a review of 455 papers, stack options and a market check ([docs/research/](docs/research/)) |
| Design | **Decided.** Stack, engine shape and scope ([ADRs 0004, 0006 and 0007](docs/adr/)) |
| Engine | Not started |

### Roadmap

1. The general engine: scenario packs, simulated time, the record of who knows what, checks,
   run records and replay.
2. One product other than teamctx tested end to end, with the prototype's checks ported.
3. Team presets: choose a team's size, roles and habits instead of writing a pack by hand.
4. Optional model-driven teammates, recorded for replay.

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
