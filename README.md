# teamsim (working name)

**Deterministic simulation testing for agents and bots that work in team chat: a scripted
team, a synthetic workspace and planted ground truth.**

[![CI](https://github.com/koolestasian/teamsim/actions/workflows/ci.yml/badge.svg)](https://github.com/koolestasian/teamsim/actions/workflows/ci.yml)
![Status: pre-alpha](https://img.shields.io/badge/status-pre--alpha-orange)
![Python 3.14+](https://img.shields.io/badge/python-3.14%2B-blue)
![Licence: MIT or Apache-2.0](https://img.shields.io/badge/licence-MIT%20or%20Apache--2.0-lightgrey)

![A scenario pack and an isolated test oracle feed state-based verifiers of a system under test in a synthetic workspace.](docs/research/figures/testing-loop.png)

An assistant in a shared channel works for several people at once. It can act on a decision
that was reversed last week, follow an instruction from someone with no authority over it,
repeat in public what it was told in private, or post back a credential someone pasted by
mistake. Single-user evaluations cannot express these failures, because they depend on who
knew what, where and when.

teamsim runs a small team of simulated teammates in a local, synthetic workspace. The team is
scripted and seeded: it posts, decides, reverses decisions, goes quiet and discloses facts on a
fixed timeline, and the simulator records the ground truth of every fact it plants. The system
under test, whether an agent acting as a teammate or a bot observing the channels, is scored
by state-based verifiers against that ground truth.

> **Pre-alpha.** What runs today is a prototype built to test one product. The general engine
> is designed but not yet built. See [Status](#status).

## How it works

1. **A scenario pack** declares the team, its channels, a timeline of events and the facts
   they carry: who disclosed what, where, and who is permitted to know it. Packs are versioned
   data, not code.
2. **A discrete-event engine plays the timeline** in virtual time. Teammates react to the
   system under test only through declared triggers (a mention, a direct message, an action),
   never by interpreting free text, so no language model runs during a test.
3. **Verifiers read the final state**: recorded values, where a canary secret ended up, which
   actions were taken and by whom. Each returns pass, fail, not applicable (the planted fact was
   never delivered) or harness error.
4. **Verifiers are validated before they are trusted.** Each one declares its expected verdict
   for a set of control agents: a null agent, a noise agent, a flood agent, a reward-hacking
   agent that probes for the oracle, a reference solution, and mutants of that solution that are
   almost right.

## Design guarantees

| Property | Mechanism |
|---|---|
| Exact replay | The same pack and seed produce a byte-identical event stream. No wall clock, no shared random stream, no model at run time |
| Minimal failing scenarios | Randomness is keyed per event, so removing one event leaves the rest unchanged; a failing run can be reduced by delta debugging to the few events that still trigger the failure |
| Oracle isolation | Expected values live outside the process, files and network of the system under test |
| Honest scores | Counts with confidence intervals; a planted fact that was never delivered is not scored against the system under test |
| Runs on a laptop | Python standard library only; no account, API key or GPU needed for the engine |

These are design commitments from [ADR 0006](docs/adr/0006-core-shape.md); the new engine does
not implement them yet.

## What teamsim is not

- **Not a model of real people.** The teammates are a calibrated instrument, like a crash-test
  dummy. They do not hold open conversations, and teamsim makes no claim that they behave like
  humans.
- **Not synthetic user research.** Simulated opinions are weakly supported by current evidence
  ([literature synthesis](docs/research/2026-11-lit-synthesis.md)); that direction is parked.
- **Not for real servers.** Runs happen in local emulated workspaces.

## Status

| Part | State |
|---|---|
| [`prototypes/teamctx-sim/`](prototypes/teamctx-sim/) | **Working.** An end-to-end simulation built to test [teamctx](https://github.com/koolestasian/discord-team-context): a six-person simulated team chats through a local Discord emulator while the product syncs it, and a checker scores sync, commands, search quality, visibility, prompt injection, catch-up after an absence and due dates across time zones. 230 offline tests |
| Research | **Done for now.** Prior art, workspace emulators, a review of 455 papers, stack options and a market check ([docs/research/](docs/research/)) |
| Design | **Decided.** Stack, scope and core shape ([ADRs 0004-0006](docs/adr/)), a [benchmark design](docs/design/benchmark.md) and an [audit design](docs/design/control-agent-audit.md) |
| Engine | Not started |

### Roadmap

1. The core engine: scenario packs, virtual time, the knowledge ledger, verifiers, run records
   and replay.
2. A verifier audit of public multi-user agent benchmarks using the control agents, with
   findings disclosed privately to their authors first.
3. A small benchmark: an agent joins a simulated team and is scored on matched pairs of tasks
   that differ in one planted fact (who holds authority, whether a decision was reversed, who
   may see a message). A pair counts only if both are right, so fixed habits such as "always
   comply" or "always refuse" score zero.
4. The same engine as a tool for testing your own team-facing bot or product.

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
over several messages, reactions instead of replies, pasted AI answers, a pasted credential
([REALISM.md](prototypes/teamctx-sim/REALISM.md)).

## Terms

| Term | Meaning here |
|---|---|
| System under test | The agent, bot or product being evaluated |
| Synthetic workspace | A local emulated chat workspace seeded by the scenario; no real accounts |
| Planted fact | A fact the scenario discloses at a known time and place, with its permitted audience |
| Test oracle | The expected outcomes derived from the planted facts, kept out of the system's reach |
| Verifier | A function of the final workspace state and the run record that returns a verdict |
| Control agent | A scripted agent whose correct verdict is known in advance, used to validate verifiers |
| Mutant | A reference solution with one deliberate defect, as in mutation testing |

## Repository layout

| Path | Contents |
|---|---|
| [`docs/adr/`](docs/adr/) | Architecture decision records |
| [`docs/design/`](docs/design/) | Designs for the benchmark and the verifier audit |
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
