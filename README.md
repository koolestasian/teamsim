# teamsim (working name)

A sandbox of simulated teammates for testing software that works with a team, without
recruiting a team first.

You pick a team: how many people, who they are, how they talk and work. teamsim plays them
in a local, fake workspace and plants known facts as they go (a decision made on day 3, a
task handed over with a reaction, a key pasted where it should not be). Your product watches
the workspace, and teamsim scores it against what it planted.

**Status: pre-alpha, research phase.** There is no release and no stable interface. The
stack and core design are decided ([ADR 0004](docs/adr/0004-python-standard-library-core.md),
[ADR 0006](docs/adr/0006-core-shape.md)); the research behind them is in
[docs/research/](docs/research/).

## What exists today

[`prototypes/teamctx-sim/`](prototypes/teamctx-sim/) is a working end-to-end simulation built
to test [teamctx](https://github.com/koolestasian/discord-team-context), a tool that turns a
team's Discord into a searchable record. A fictional six-person team chats through a local
Discord emulator while the real teamctx binary syncs it, and a checker scores every step:
sync, commands, search quality, visibility, prompt injection, catch-up after an absence,
due dates across time zones.

Its realism mode copies patterns seen in a real student team server (only patterns, never
content): handles instead of names, one thought split over several quick messages,
reactions instead of replies, image-only messages, off-topic bursts, pasted AI answers, a
pasted secret. See [REALISM.md](prototypes/teamctx-sim/REALISM.md).

The prototype is Python 3.14, standard library only. Its unit tests run offline:

```sh
python -I -m unittest discover -s prototypes/teamctx-sim/tests
```

A live run needs the Discord emulator and a teamctx build; see the
[runbook](prototypes/teamctx-sim/RUNBOOK.md).

## Direction

See [ADR 0005](docs/adr/0005-scope-instrument-first.md) for the scope and
[ADR 0006](docs/adr/0006-core-shape.md) for the core design.

- **A test instrument, not a realistic person.** The simulated team is scripted and seeded, so
  every run can be repeated exactly. The project does not claim its teammates behave like
  people; it claims to know what it planted.
- **Ground truth first.** Results are scores against planted facts, graded from workspace
  state, by graders that are themselves tested with control subjects.
- **No model at run time.** Any model-written text is produced beforehand and recorded in the
  scenario.
- **Order of work.** First an [audit of public benchmarks](docs/design/control-agent-audit.md)
  with control subjects, then a small benchmark, then the same engine as a tool for testing
  your own team-facing product.
- **Easy to run.** One command, scenario packs instead of code.

## Licence

Licensed under either of [Apache License 2.0](LICENSE-APACHE) or [MIT license](LICENSE-MIT),
at your option. All names, messages and IDs in fixtures and prototypes are fictional.
