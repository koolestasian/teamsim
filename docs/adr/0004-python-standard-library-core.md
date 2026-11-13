# 0004. Stack: Python core on the standard library, shipped with uv

- Status: Accepted
- Date: 2026-11-12
- Deciders: maintainer
- Plan reference: none

## Context

[ADR 0002](0002-start-from-the-teamctx-prototype.md) left the stack open until the research
was done. [The stack-options note](../research/2026-11-stack-options.md) compared Python,
TypeScript and Go and recommended Python. Two later facts bear on the choice:

- The note counted a second runtime as Python's main cost, because every emulator it found
  was a Node package. [The gap check](../research/2026-11-gap-check.md) found a Python mock
  Slack (env0), so that cost is no longer certain for every workspace.
- The task harness with the widest adoption for agent evaluation (Harbor) and env0 are Python
  projects (GitHub repository metadata, read 2026-11-12). Scenario packs that should run in
  those tools are easier to support from the same language.

Nothing in the stack comparison has been installed or timed.

## Decision

- The core is Python, 3.14 or later, using only the standard library. Adding a third-party
  package to the core needs its own ADR.
- Distribution is through uv (`uvx`), with `pipx` as the alternative for people who already
  use Python.
- Workspace emulators, the subject under test and any model server are separate processes.
  The core never imports them.
- Test tooling stays `unittest` on the three-OS CI matrix.
- One spike confirms the decision before the first release: time a first run on a clean
  Windows and a clean macOS or Linux machine. If Python plus a needed second runtime takes
  much longer than a Node-only install would, this ADR is revisited.

## Alternatives considered

- **TypeScript on Node.** One runtime when the emulator is a Node package, and in-process
  reset for some emulators. It means rewriting the tested prototype core and adds a build
  step for every release.
- **Go, one static binary.** The simplest install of the tool itself. It also means a full
  rewrite, still needs another runtime for emulators, and unsigned binaries meet operating
  system warnings.

## Consequences

### Good

- The prototype's ledger, checks, security patterns and 230 tests carry over by porting, not
  rewriting.
- No third-party code in the core, so the supply-chain surface is the interpreter.
- The same language as the harnesses scenario packs are meant to run in.

### Bad

- Runs that use a Node-based emulator need Node as well. The tool must detect this and say
  what to install, never install it silently.
- The standard library has no WebSocket server; owning a Discord-style fake means writing
  the framing by hand.

### Follow-ups

- The clean-machine install spike.
- Check whether env0's mock Slack delivers events to a bot and runs on Windows.
- Add the stack's checks to CI and to the contributor docs when the first core code lands.
