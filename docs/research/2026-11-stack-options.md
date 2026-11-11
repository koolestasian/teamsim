# Stack options (2026-11-11)

Input for the stack decision that ADR 0002 left open. It compares three stacks against what the
run-1 notes found, recommends one, and lists the decisions that only the maintainer can make.
It decides nothing: no ADR, no code, no dependencies. Nothing below was installed or run;
external facts come from official docs, package registries and the GitHub API, each checked on
2026-11-11 (see Sources).

## Summary

**Options**

| | Stack | One command |
|---|---|---|
| A | Python, standard library core, shipped with uv | `uvx teamsim ...` |
| B | TypeScript on Node.js LTS | `npx teamsim ...` |
| C | Go, one static binary | `teamsim ...` |

**Recommendation: A.** It keeps the prototype's tested core (ground truth, checks, security
patterns, 230 tests), adds no third-party code to the core, and uv installs Python for the
user. Its cost: runs that use a workspace emulator also need Node.js 24 or later, because every
usable emulator is a Node package. B removes that second runtime but rewrites everything. C
gives the simplest install of the tool itself but still needs Node for emulators and rewrites
everything.

**Decisions for the maintainer** (details in "Decisions for the maintainer"):

1. Default run: model-free and scripted (recommended), with a model-driven hybrid as an opt-in.
2. v0.1 teammate actions: chat only (recommended), with tasks and issues in v0.2.
3. First user: builders of team-facing software (recommended), with students as the reason the
   install must be easy.

**What would change the recommendation:** a clean-machine install test where Python plus Node
proves much harder than Node alone (go to B); a first user who needs Slack, GitHub or Linear
in v0.1 and fast per-test resets (go to B); a need for a single downloadable binary that
outweighs the rewrite (go to C). Details under "What would change it".

## What any stack has to carry

These requirements come from the run-1 notes, not from a preference for a language.

1. **No model in an ordinary scored run.** The team is scripted and seeded; a model is an
   opt-in layer with recorded calls (`2026-11-prior-art.md`, "What this means for teamsim"
   point 3; `2026-11-personas.md`, "Summary and recommendation" point 2).
2. **Workspaces behind thin adapters; emulators are external.** Adopt an emulator where one
   exists, own the scenario clock and message model, keep real platforms as a later opt-in
   (`2026-11-emulators.md`, "Own a minimal fake or adopt an emulator" and "Recommendation for
   v0.1"). Every emulator worth adopting is a Node package: Baseline's Discord needs Node 24 or
   later, and `emulate` is TypeScript (same note, "Local emulators", refs B2 and E1).
3. **A product adapter boundary** for starting the product, reading its state and mapping its
   ids back to the ledger (`2026-11-prototype-audit.md`, section 6 "Change").
4. **Models through an OpenAI-compatible base URL**, local first, hosted only when configured,
   with the model id, seed and prompt version recorded (`2026-11-personas.md`, section 4;
   `2026-11-prototype-audit.md`, section 6 "Change").
5. **Determinism and replay**: seeds, a generation cache keyed on the full request, and
   explicit replay of a recorded run (`2026-11-personas.md`, section 5;
   `2026-11-prior-art.md`, "Notes", determinism).
6. **The prototype's security patterns**: `Secret`, a redactor on every output, a
   host-allowlisted transport that also checks redirects, loopback-only servers with
   Host/Origin/nonce guards, a filtered child environment (`2026-11-prototype-audit.md`,
   sections 5.4 and 6 "Keep").
7. **Offline tests** with fake transports and injectable clocks, on Windows, macOS and Linux
   (`2026-11-prototype-audit.md`, sections 2.1 and 6 "Keep").
8. **Presets as data, not code** (`2026-11-prototype-audit.md`, section 6 "Change").
9. **Licence fit**: MIT OR Apache-2.0 (ADR 0001); no AGPL code copied, AGPL servers only as
   separate programs (`2026-11-prior-art.md`, "Notes", licences; `2026-11-emulators.md`,
   "Licences, if teamsim ever ships or bundles one").

## The process model all three options share

The run-1 notes fix the shape; the options differ only in the language of the first box and in
whether an emulator can run inside it.

| Process | Role | Started by |
|---|---|---|
| teamsim | Scenario engine (plan, clock, ledger), workspace and product adapters, model client, checker, report, live view | The user |
| Workspace emulator | Discord, Slack, GitHub or Linear on loopback | teamsim, as a child process |
| Product under test | The bot or tool being scored, pointed at the emulator | teamsim or the user |
| Model server (optional) | Ollama, LM Studio or llama.cpp at an OpenAI-compatible URL | The user |

The checker reads three things: teamsim's own ledger, the workspace state through the workspace
adapter, and the product's public read surfaces through the product adapter. Direct database
reads stay an optional, product-specific extra (`2026-11-prototype-audit.md`, section 6 "Drop").

## Option A: Python, standard library core, shipped with uv

- **Language and runtime.** Python 3.14, as the prototype and CI use today. 3.14 has been in
  bugfix status since 2025-10-07 with end of life scheduled for 2030-10; 3.15 was released
  2026-10-09 (Python devguide). Add 3.15 to the CI matrix rather than raise the floor.
- **Process model.** As above. Emulators run as child processes started with `npx`, which is
  what the prototype already does, minus its WSL coupling (`2026-11-prototype-audit.md`,
  section 4 "Windows host plus WSL only").
- **Install and run.** One prerequisite, then one command:
  - Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`,
    or `winget install --id=astral-sh.uv -e`.
  - macOS and Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`, or `brew install uv`.
  - Then on all three: `uvx teamsim run --preset demo` (illustrative command). uv downloads a
    Python if none is found ("By default, uv will automatically download Python versions if they
    cannot be found on the system", uv docs). Before a PyPI release, `uvx --from git+<repo URL>`
    runs it from the repository. `pipx install teamsim` also works for people who already use
    Python.
  - Runs that use an emulator also need Node 24 or later: the Windows `.msi` installer, nvm or
    the standalone binary (nodejs.org download page). teamsim should check for `node` at start
    and print what to install, never install it silently.
- **Emulators.** HTTP and JSON over loopback, through the prototype's emulator client pattern.
  `emulate` is started with its CLI (`npx emulate --service slack --seed config.yaml`). Its
  snapshot, reset and restore are documented in the JavaScript API; from the CLI the README
  documents reset through its inspector only. So a clean state between scenarios means
  restarting the process with its seed, which the prototype already does for Discord
  (`2026-11-prototype-audit.md`, section 2.2 step 2). Whether `emulate` exposes reset over
  HTTP was not checked.
- **Local models.** `urllib` through the prototype's host-allowlisted transport, given a base URL
  and a model name. The redirect hole must be fixed first (`2026-11-prototype-audit.md`,
  section 5.4).
- **Testing.** `unittest` from the standard library, the existing `FakeTransport` and
  injectable clocks, the existing three-OS CI matrix. The 230 offline tests are the starting
  suite.
- **Licence fit.** Core code needs no third-party package. uv is Apache-2.0 on GitHub and is
  the user's installer, not part of teamsim. Fixtures in TOML are read with `tomllib`, standard
  since 3.11.
- **What carries over.** Most of it: the modules marked reusable in
  `2026-11-prototype-audit.md` section 3 (planning and the realism transform, the posting
  ledger, checks 0, 2, 3, 6 and 14, `net`, `envfile`, `state`, the report, the live view), their
  tests, and the fixtures. They get ported behind the new adapter boundaries, not copied
  whole, which answers ADR 0002's worry that generalising the prototype directly would lock in
  its emulator, process model and teamctx coupling.
- **Costs.** Two runtimes for emulator-backed runs. The standard library has no WebSocket
  server, so owning a Discord fake would mean hand-written framing (`2026-11-emulators.md`,
  "Own a minimal fake or adopt an emulator", build effort). Publishing to PyPI is outward-facing
  and needs the maintainer.

## Option B: TypeScript on Node.js LTS

- **Language and runtime.** Node 24 (LTS, first released 2025-05-06) or Node 26 (LTS, first
  released 2026-05-05). From Node 27 every major release becomes LTS (Node release page).
  Baseline's Discord package needs Node 24 or later. Node runs `.ts` files directly when they
  use only erasable syntax, with no type checking (Node 26 docs), so the TypeScript compiler is
  a dev dependency for CI checks only.
- **Process model.** `emulate` can run inside the teamsim process (`createEmulator`, with
  `snapshot()`, `reset()` and `restore()` in its README). That is B's main technical gain:
  fast, exact resets between scenarios. Baseline's Discord still runs as a child process; I did
  not check whether it has a programmatic API.
- **Install and run.** One prerequisite, then one command:
  - Windows: the `.msi` installer or the `.zip` archive. macOS and Linux: nvm or the standalone
    binary (nodejs.org download page).
  - Then on all three: `npx teamsim run --preset demo` (illustrative). No second runtime for any
    emulator.
- **Emulators.** In-process for `emulate`; HTTP over loopback for Baseline. The published
  `emulate` 0.13.1 declares three runtime dependencies (npm registry); its full dependency
  tree was not checked.
- **Local models.** Built-in `fetch` (stable since Node 21). The allowlist and redirect rule
  from the audit have to be rewritten and re-tested.
- **Testing.** `node:test`, stable since Node 20, with no extra package.
- **Licence fit.** `emulate` and Baseline's packages are Apache-2.0, compatible with ADR 0001.
  Each npm dependency adds licence and supply-chain review; the repo's Dependabot covers only
  GitHub Actions today and would need an npm entry.
- **What carries over.** The design (ledger, checks, statuses, probes), the fixtures (JSON as
  is; the TOML eval files need a parser package or a conversion to JSON, since Node's API docs
  list no TOML module), and the live view page, which is already plain JavaScript. The roughly
  5,800 lines of `simlib/` and 2,900 lines of tests are rewritten
  (`2026-11-prototype-audit.md`, section 2.1).
- **Costs.** A full rewrite of a working, tested core, including the security patterns. Node
  also has no WebSocket server in core (its `WebSocket` global is a browser-compatible client),
  so a teamsim-owned Discord fake would still need a package or hand-written framing.

## Option C: Go, one static binary

- **Language and runtime.** Go 1.27, released 2026-08-19 (Go release history). Licence
  BSD-3-Clause.
- **Process model.** As in A: emulators are child processes started with `npx`.
- **Install and run.** Download one binary from a release page and run `teamsim run --preset
  demo` (illustrative); Go users can `go install`. No language runtime. Emulator-backed runs
  still need Node 24 or later. I did not check how Windows SmartScreen and macOS Gatekeeper
  treat an unsigned command-line binary downloaded through a browser; signing is a likely cost.
- **Emulators.** HTTP over loopback, like A.
- **Local models.** `net/http`; its `Client.CheckRedirect` hook makes the audit's redirect rule
  straightforward.
- **Testing.** `go test` and `net/http/httptest` from the standard library.
- **Licence fit.** Fine. The Go standard library has no TOML and no WebSocket package (pkg.go.dev
  standard library index), so fixtures move to JSON or a module is added.
- **What carries over.** The design and the fixtures only. Everything else is rewritten, as in B,
  without B's in-process emulators.
- **Costs.** The rewrite, plus release engineering (cross-compiled binaries, likely signing)
  before the first user can run it.

Rust was considered for the same single-binary reason (the product the prototype tests is
written in Rust). It is not written up as a fourth option: it shares C's rewrite and release
costs, and nothing found in run 1 needs what it would add.

## Comparison

| | A Python | B Node | C Go |
|---|---|---|---|
| Runtimes for an emulator run | uv + Node | Node | binary + Node |
| Prototype code kept | Most | Design, view | Design |
| Core third-party code | None | `emulate` + deps | None if JSON |
| In-process emulator reset | No | Yes | No |
| Tests from day one | 230 | 0 | 0 |

## Decisions for the maintainer

These are the open contradictions between the run-1 notes. Each changes how much the stack
choice matters.

### 1. Model-free scripted default, or a model-driven hybrid?

- **The disagreement.** `2026-11-prior-art.md` ("What this means for teamsim" point 3) wants a
  scripted, seeded, model-free default and no "local model by default" promise until a model
  is shown to play a teammate. `2026-11-personas.md` ("Where the run-1 notes disagree" point 2)
  agrees on the default and adds a hybrid (script owns stance and facts, the model writes the
  words, every line recorded) whenever generation is on. Both differ from ADR 0003's wording
  "a local model by default".
- **Recommendation:** model-free scripted default for scored tests; the hybrid as an opt-in for
  reactive teammates and simulated feedback, local model first in that mode. Reword ADR 0003's
  "local model by default" to "local model by default when a model is used", which is a change
  to an accepted ADR and needs your approval.
- **Why.** Small local models are weak simulators (tau2 #710, MiroFish #847, TinyTroupe's
  "experimental" Ollama support, per `2026-11-prior-art.md` "Notes"), and a 3-4B model on a
  laptop CPU writes about 7 tokens a second, enough for tens of lines per run, not hundreds
  (`2026-11-personas.md`, section 4). A default that needs no model is the easiest to run.
- **Stack effect.** None of the options needs a model SDK; each needs only an HTTP client. This
  decision does not pick the stack.

### 2. v0.1 teammate actions: chat only, or chat plus tasks and issues?

- **The disagreement.** `2026-11-prior-art.md` ("What teammates can do in v0.1") and
  `2026-11-emulators.md` ("Input to the v0.1 actions question") say chat only, issues in v0.2.
  `2026-11-personas.md` (section 7) says chat plus tasks and issues, and its own "Where the
  run-1 notes disagree" point 1 concedes that argument ignores the emulator, fixture and
  scoring work.
- **Recommendation:** chat only for v0.1, with the workspace adapter interface written so an
  issue tracker fits in v0.2 without changing the core.
- **Why.** All of the prototype's checks are chat checks; tasks and issues need planted facts,
  believable teammate updates and scoring of their own, plus a choice between GitHub, Linear and
  Jira that depends on the first user (`2026-11-emulators.md`, same section).
- **Stack effect.** Chat only with Discord first keeps v0.1 on Baseline as a child process in
  every option, so B's in-process `emulate` gives nothing until v0.2. If you choose chat plus
  issues, or Slack first, B gains weight.

### 3. Who is the first user?

- **The question.** ADR 0003 left it to research. `2026-11-prior-art.md` ("(b) First user")
  recommends builders of team-facing software, with students as the group "easy to run" is for;
  it calls its own evidence indirect, and the only known user is the maintainer. The other notes
  do not contradict it but treat it as open (`2026-11-emulators.md`, "Recommendation for v0.1"
  point 1).
- **Recommendation:** builders of team-facing software (bots, integrations, agents in team
  chat), with students as the install-cost constraint. Validate with a recorded demo shown to a
  few builders, which is outward-facing and needs you.
- **Why.** It is the only segment where the measurable core applies today, the pain is
  documented (the bolt-js testing issue open since 2020, Slack's archived test tool), and it
  stays out of the funded, weakly evidenced opinion market (`2026-11-prior-art.md`, "(b) First
  user").
- **Stack effect.** If students are first and install friction dominates, B or C gain weight. If
  Slack-bot builders are first, B gains weight through `emulate`.

## Recommendation

**Option A: Python with a standard-library core, shipped with uv; emulators as child processes
behind the workspace adapter.**

1. The audit's "Change" list is refactoring of working code behind new boundaries, not a
   rewrite (`2026-11-prototype-audit.md`, section 6). A keeps the ground-truth model, five
   checks with end-to-end tests, the security patterns and the 230 tests.
2. The default run needs no model and no third-party code, so the core's supply-chain surface
   stays at zero, in line with the project's standard-library preference.
3. The emulator note's middle path already puts every emulator behind a process boundary
   (`2026-11-emulators.md`, "Own a minimal fake or adopt an emulator"), so the emulators being
   Node packages does not force the core into Node.
4. uv turns "install Python" into one installer the user runs once, on all three systems.
5. The nearest projects in `2026-11-prior-art.md` (tau2, Sotopia, convy, TinyTroupe, OASIS) are
   Python and install with uv or pip, so their users meet familiar tools.

The cost to state plainly in the README: an emulator-backed run needs uv and Node 24 or later.

### What would change it

- **Install test.** Run the full install on clean Windows, macOS and Linux machines (uv, Node,
  emulator, demo run) and time it against Node alone. If the second runtime is the step that
  fails or takes much longer, switch to B.
- **First user and workspace.** If the first user needs Slack, GitHub or Linear in v0.1 and a
  restart of `emulate` between scenarios is too slow, B's in-process `reset()` matters. Measure
  restart time first.
- **Emulator risk.** If Baseline's Discord package stops working (it has no public source,
  `2026-11-emulators.md` ref B3) and teamsim must own a Discord fake with a WebSocket gateway,
  re-weigh: none of the three standard libraries has a WebSocket server, but Node and Go have
  established packages for it.
- **Distribution.** If users mostly want a single download with no installer, for example in CI
  for non-Python teams, C becomes worth its rewrite.

## What I could not verify

- Nothing was installed or run; install commands and behaviour are from official docs.
- Whether `emulate` exposes reset or snapshot over HTTP when started from the CLI, and its full
  transitive dependency tree.
- Whether Baseline's Discord package has a programmatic API, and whether either emulator runs
  natively on Windows (also open in `2026-11-emulators.md`).
- How SmartScreen and Gatekeeper treat an unsigned Go binary, and what signing would cost.
- How long uv plus Node takes to set up on a student laptop compared with Node alone; no
  measurement exists yet.
- Contributor familiarity with each language among students; no survey data was read for this
  note.
- `teamsim` was unclaimed on PyPI and npm on 2026-11-11 (registry returned 404); it is a working
  name and could be taken at any time.

## Sources

All checked 2026-11-11.

- Python versions and dates: <https://devguide.python.org/versions/>
- `tomllib` ("Added in version 3.11"): <https://docs.python.org/3/library/tomllib.html>
- uv install commands: <https://docs.astral.sh/uv/getting-started/installation/>
- uv tools, `uvx`, `--from git+`: <https://docs.astral.sh/uv/guides/tools/>
- uv automatic Python downloads: <https://docs.astral.sh/uv/concepts/python-versions/>
- uv licence: <https://api.github.com/repos/astral-sh/uv> (`license.spdx_id`: Apache-2.0)
- Node release lines and the Node 27 schedule change:
  <https://nodejs.org/en/about/previous-releases>
- Node install methods: <https://nodejs.org/en/download>
- Node TypeScript type stripping (v26.13.1 docs): <https://nodejs.org/api/typescript.html>
- `node:test` stable since v20: <https://nodejs.org/api/test.html>
- `fetch` stable since v21, `WebSocket` client since v22: <https://nodejs.org/api/globals.html>
- Node API index (no TOML module): <https://nodejs.org/api/index.html>
- Go releases: <https://go.dev/doc/devel/release>; licence:
  <https://api.github.com/repos/golang/go>
- Go `Client.CheckRedirect`: <https://pkg.go.dev/net/http>; standard library index:
  <https://pkg.go.dev/std>
- `emulate` README (CLI, programmatic API, snapshot, reset, inspector), tip of `main` at
  `26a8fe7e32db3346b0ac928586422ac2709b922b`: <https://github.com/vercel-labs/emulate>;
  repository `engines` (`node >=24`) in its root `package.json`
- `emulate` 0.13.1 on npm (three runtime dependencies, no `engines`):
  <https://registry.npmjs.org/emulate/latest>
- Baseline Discord 0.14.0 on npm (`node >=24`):
  <https://registry.npmjs.org/@deploybaseline/discord/latest>
- Name availability: <https://pypi.org/pypi/teamsim/json>, <https://registry.npmjs.org/teamsim>
- Run-1 notes in this folder: `2026-11-prototype-audit.md`, `2026-11-prior-art.md`,
  `2026-11-emulators.md`, `2026-11-personas.md`; ADRs 0001-0003 in `docs/adr/`.
