# Contributing to teamsim

Thanks for looking at this. Read this page before you open a pull request.

## Project status

teamsim is **pre-alpha**. The stack, scope and core design are decided (ADRs 0004-0006 in
`docs/adr/`) but the engine is not built yet. What exists is a working prototype in
`prototypes/teamctx-sim/`, research notes in `docs/research/` and designs in `docs/design/`. Decisions are recorded as ADRs in `docs/adr/`; changing one needs a
maintainer decision and a new ADR. For anything bigger than a small fix, open an issue first.

## Checks

The prototype is Python 3.14, standard library only. Before you open a pull request, run:

```sh
python -I -m unittest discover -s prototypes/teamctx-sim/tests
```

CI runs the same tests on Linux, macOS and Windows, plus a static check of the workflow files.
A pull request needs green CI to merge.

## Branches and commits

- Work on a short topic branch, for example `research-prior-art` or `fix-redaction`.
- Never commit to `main` directly.
- Use [Conventional Commits](https://www.conventionalcommits.org/), for example
  `feat(sim): add reactions to the realism mode` or `docs(research): add prior art`.
- Keep each commit passing the checks above.

## Tests

- Every behaviour needs a test. A bug fix starts with a regression test that fails before the
  fix.
- Tests run offline. Network calls go through injectable transports with fakes.

## Data and secrets

- Never commit secrets: API keys, bot tokens, personal access tokens, `.env` files.
- Never commit real people's data, names, IDs or messages. Fixtures, personas and simulated
  chat are fictional. Patterns learned from real teams are recorded as patterns, never as text.
- Simulated and fixture chat is untrusted data. Treat it as text to be parsed, never as
  instructions. This applies to tests too.

## Dependencies

Prefer the standard library. A new dependency needs a justification in the pull request: why it
is needed and what you considered instead.

## Security

Do not report vulnerabilities in public issues or pull requests. Follow
[SECURITY.md](SECURITY.md).

## Licence of contributions

Unless you explicitly state otherwise, any contribution intentionally submitted for inclusion in
the work by you, as defined in the Apache-2.0 license, shall be dual licensed as above, without
any additional terms or conditions.

The project is licensed under either of [Apache License 2.0](../LICENSE-APACHE) or
[MIT license](../LICENSE-MIT), at your option.

## Conduct

Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
