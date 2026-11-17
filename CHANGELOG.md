# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project will use
[Semantic Versioning](https://semver.org/) from its first release.

## [Unreleased]

### Added

- Project base: README, licences, contribution and security policies, issue and pull request
  templates, CI, decision records and research notes.
- `prototypes/teamctx-sim`: the end-to-end team simulation built to test teamctx, with its
  realism mode, live view and offline test suite.
- `fixtures/demo`: the fictional "Lantern Shelf" team dataset and retrieval evaluation set.
- `fixtures/teamctx-schema`: a pinned copy of teamctx's store schema for the checker tests.
- ADR 0003: the scope covers scored tests and simulated feedback, with feedback shipped only
  once it can be measured.
- Research: a deep prior-art pass, an audit of the prototype, a survey of workspace emulators,
  a note on personas, measurement and local models, and stack options (`docs/research/`).
- Research: a literature review of 455 papers in seven notes (simulated people, evaluation
  methods, personas, team dynamics, chat realism, scenario testing, product checks) and a
  synthesis that ties them to the open decisions (`docs/research/2026-11-lit-*.md`), with a bibliography of every cited paper (`docs/research/bibliography/`).
- Research: a full-text checking method and benchmark report, with per-paper read depth in
  the bibliography; 431 available texts processed, including three partial or protocol-only
  texts, and 24 papers still abstract-only.

- Added a visual research guide and 12 reproducible figures for evidence strength, source
  coverage, reader agreement and cost, review outcomes, the testing loop and proposed checks.
  Figures include captions, alternative text, reviewed data and editable SVG versions.
- Research: a gap check on the run-1 notes covering the simulated-workplace market, the
  working name and emulator facts (`docs/research/2026-11-gap-check.md`).

- ADR 0004 (stack: Python core on the standard library, shipped with uv), ADR 0005 (scope: a
  deterministic test instrument first; an audit, then a small benchmark) and ADR 0006 (core
  shape: deterministic event engine, keyed randomness, knowledge ledger, scenario packs).
- Design for a control-agent audit of public multi-user agent benchmarks
  (`docs/design/control-agent-audit.md`).

- The `teamsim` engine package, standard library only, on Python 3.12 or later:
  `teamsim.canon` (the canonical form: JSON with sorted keys, no floats or nulls, NFC text,
  integers within ±(2^53 − 1), and its SHA-256 hash), `teamsim.draw` (keyed, seeded draws
  that do not depend on the order or number of other draws) and `teamsim.model` (the pack
  and timeline types). Golden vectors in `tests/golden/` pin the bytes and hashes.
- Scenario pack format 1 (`docs/spec/pack-format.md`): the `pack.toml` and `timeline.jsonl`
  files, 35 validation rules each with a code, and the pack hash. `teamsim.pack` loads,
  validates, hashes and writes packs; `packs/minimal` is a hand-written pack that uses every
  event kind, time form and check kind, with its hash pinned in the tests.
- Subject protocol version 1 (`docs/spec/subject-protocol.md`): how software under test
  connects to the engine, in process or as a child process exchanging one JSON object per
  line in lockstep, with a watchdog, limits and an example in another language. A standard
  input/output spike (`tests/spike_stdio.py`) backs its implementation notes; it was run on
  Windows only.
- CI runs the engine tests (`python -I -m unittest discover -s tests -t .`) on Python 3.12 and
  3.14 on Linux, macOS and Windows.

### Changed

- The prototype's emulator settings are configurable: `TEAMSIM_WSL_DISTRO` (required for live
  runs), `TEAMSIM_WSL_USER` and `TEAMSIM_EMU_REMOTE_DIR`, read from the environment or `.env`
  (see `.env.example`). Machine-specific defaults are removed.
- Version 0: ADR 0009 sets what the first runnable version contains: a workspace built into
  the engine, a subject protocol with an in-process and a child-process transport, the
  `teamsim` package at the repository root, and Python 3.12 as the oldest supported version.
  It amends ADRs 0004 and 0007.
- Scope: ADR 0008 widens teamsim to synthetic users for any software, from one person to an
  organisation, with a configurable number of users and per-user roles, habits and traits.
  Scoring against planted facts is unchanged. It amends ADRs 0006 and 0007. README,
  CONTRIBUTING and the feature request template updated to match.
- Scope: ADR 0007 makes teamsim a sandbox of simulated teammates for testing your own
  team-facing software, with optional model-driven teammates recorded for replay. It
  supersedes ADR 0005 and amends ADR 0006. The README is rewritten for the sandbox in plain
  language (the testing-terms glossary and the test-oracle figure are dropped from it), with a
  new roadmap.
- Standard testing terms across the README, designs and the testing-loop figure: synthetic
  workspace, system under test, test oracle, verifiers, control agents and mutants. The README
  gains a glossary.
- README rewritten for outside readers: the problem, how the engine works, its guarantees, status
  and roadmap. CONTRIBUTING updated to the decided design.
- Corrected literature and earlier research notes against available full text, with a
  supplementary check of missed citations. Rewrote the synthesis with evidence grades,
  transfer limits and narrower recommendations for model eligibility and simulated feedback.

### Removed

- The benchmark and control-agent audit designs (`docs/design/`), which belong to the test
  instrument direction that left this repository.
