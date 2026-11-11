# teamsim (working name)

A sandbox of simulated teammates for testing software that works with a team, without
recruiting a team first.

You pick a team: how many people, who they are, how they talk and work. teamsim plays them
in a local, fake workspace and plants known facts as they go (a decision made on day 3, a
task handed over with a reaction, a key pasted where it should not be). Your product watches
the workspace, and teamsim scores it against what it planted.

**Status: pre-alpha, research phase.** There is no release and no stable interface. The
language and architecture are open and will be decided after the research in
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

See [ADR 0003](docs/adr/0003-scope-tests-and-simulated-feedback.md) for the scope.

- **Ground truth first.** The simulator knows what it planted, so test results are scores, not
  impressions. A test team does not need to be an accurate human; it needs to be varied,
  messy, reproducible and checkable.
- **Simulated feedback, measured or not shipped.** Teammates will also give opinions on the
  product. Simulated people are poor stand-ins for real opinions (see the research), so this
  feedback is a set of hypotheses to check with real people, and it ships only once its
  diversity and bias can be measured.
- **Easy to run.** One command, a local model by default, presets instead of code. It should
  work without a professional test setup.

## Licence

Licensed under either of [Apache License 2.0](LICENSE-APACHE) or [MIT license](LICENSE-MIT),
at your option. All names, messages and IDs in fixtures and prototypes are fictional.
