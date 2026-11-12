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
