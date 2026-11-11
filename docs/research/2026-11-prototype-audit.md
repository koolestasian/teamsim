# Prototype audit: teamctx-sim (2026-11-11)

An audit of `prototypes/teamctx-sim/` at commit `0778a8c`, done before the stack decision
(ADR 0002). The prototype is the reference for what teamsim must do, not its architecture.

**Method.** Read `RUNBOOK.md`, `REALISM.md`, `sim.py`, every module in `simlib/`, the test
suite, the live view page and `fixtures/`. Every claim about the code cites `file:line`
(paths below are relative to `prototypes/teamctx-sim/` unless they start with `fixtures/` or
`docs/`). The offline suite was run: `python -I -m unittest discover -s
prototypes/teamctx-sim/tests` ran 230 tests, all passing (Python 3.14.7, Windows).

**Not verified in this audit.** No live run was made (it needs the emulator, a teamctx build
and optionally a model key). Statements about the emulator's limits come from the prototype's
own comments and recorded assumptions, not from the emulator's documentation. Statements
about teamctx's behaviour come from the checker's expectations and REALISM.md, not from
teamctx's source.

## 1. Top findings

1. **The teammates are a replay, not a simulation.** Every message comes from a hand-written
   dataset (314 messages) plus a deterministic, seeded transform (`simlib/script.py:489-495`).
   Every command is scripted with a fixed actor (`simlib/script.py:616-701`). No model plays a
   teammate, and teammates never react to what the product says. That is why the ground truth
   is exact, and it is also why the prototype has nothing yet for simulated feedback (ADR 0003).
2. **The ground-truth model is the reusable core.** Planted facts live in three layers that
   map cleanly to a general teamsim: a posting ledger (`map.json`, dataset key to workspace
   id), a record plan (fixture entries plus the capture script), and a retrieval eval set
   (`fixtures/demo/eval.toml`). Section 2.3.
3. **The checker is tightly bound to teamctx.** It reads teamctx's SQLite tables directly
   (`simlib/host.py:409-443`), parses teamctx's reply wording (`simlib/checker.py:440`,
   `simlib/driver.py:483`, `simlib/story.py:64`) and hard-codes fixture ids
   (`simlib/checker.py:548-559`, `simlib/checker.py:827`). Checks 1, 4 and 7-10 are almost
   entirely teamctx-specific (section 3).
4. **Several checks cannot fail or tolerate the bug they look for.** Retrieval always passes
   (`simlib/checker.py:724-725`); the relative-due check accepts either the UTC or the local
   date (`simlib/checker.py:1198-1201`); due dates within one day pass
   (`simlib/checker.py:488-493`). A general teamsim needs thresholds and exact expectations.
5. **Checks 1, 4, 5, 7-13 and 15 have no unit test of their verdict logic.** Only checks 0, 2,
   3, 6 and 14 are exercised end to end in the offline suite (section 5.3).
6. **One network-policy hole:** the HTTP transport follows redirects without re-checking the
   host allowlist and carries the `Authorization` header to the new host
   (`simlib/net.py:121`, confirmed against Python 3.14.7's `HTTPRedirectHandler`).
7. **Environment lock-in and privacy cleanup.** The emulator runs only in a named WSL distro
   with a fixed user, hard-coded in code, a test and the RUNBOOK (`simlib/emu.py:24-25`,
   `tests/test_host.py:283`, `simlib/runner.py:618`, `RUNBOOK.md:31`). The model choice tries a
   hosted model first and a local one second (`simlib/host.py:165-182`), the reverse of ADR
   0003's "local model by default".

## 2. What the prototype does and how

### 2.1 Architecture

Python 3.14, standard library only. About 5,800 lines in `simlib/`, 211 in `sim.py`, 830 in
the live view page and 2,900 in tests.

| Module | Lines | Role |
|---|---|---|
| `sim.py` | 211 | CLI: subcommands for each step and `run-all` (`sim.py:22-77`). |
| `simlib/script.py` | 790 | Pure planning: dataset to cast, emulator seed, acts, post items, realism transform, captures, queries, metrics (`simlib/script.py:1-5`). |
| `simlib/runner.py` | 695 | `Harness`: wires everything, owns the scenario (`run_all`, `simlib/runner.py:468-596`), the report facts. |
| `simlib/driver.py` | 621 | Posts acts and scripts interactions through the emulator; resumable via `map.json`/`state.json` (`simlib/driver.py:1-6`). |
| `simlib/emu.py` | 275 | Emulator client (simulate endpoints plus a few REST calls) and the WSL process manager. |
| `simlib/host.py` | 446 | The product under test: binary, config, process, JSON API client, read-only SQLite reader, model choice. |
| `simlib/shim.py` | 163 | Loopback proxy between teamctx and the emulator that stubs the missing thread routes and tunnels the gateway. |
| `simlib/checker.py` | 1209 | Checks 0-15 against ground truth. |
| `simlib/report.py` | 155 | Markdown and JSON report, redacted as a whole (`simlib/report.py:145-153`). |
| `simlib/net.py` | 187 | Transport with a host policy; `FakeTransport` for tests. |
| `simlib/envfile.py` | 145 | `.env` loader, `Secret` wrapper, `Redactor`. |
| `simlib/state.py` | 150 | Paths, atomic JSON stores, log and timeline. |
| `simlib/story.py`, `simlib/viz.py`, `viz/index.html` | 619 + 350 + 831 | Live view: timeline to "story events", a loopback server, one page. |

Every network and process boundary is injectable (`simlib/runner.py:45-51`), which is why the
whole flow runs offline in tests with `FakeTransport` (`simlib/net.py:150-187`).

### 2.2 Data flow (script -> emulator -> product -> checker)

1. **Plan.** `load_dataset` and `build_items` turn `fixtures/demo/dataset.json` into ordered
   `PostItem`s: messages sorted by time, threads folded into their parent channel, edited
   messages posted as a `(draft)` first, acts cut by original UTC date
   (`simlib/script.py:131-140`, `simlib/script.py:191-214`). Synthetic extras are spliced in at
   fixed fractions of an act: a "wrong channel" message that is later deleted, and two
   messages in the private `leads` channel (`simlib/script.py:217-264`). Realism mode adds
   fragments, reactions, image stand-ins, off-topic bursts, pasted AI answers, a fake key and
   a recap-only decision (`simlib/script.py:389-495`).
2. **Seed.** `build_seed` builds the emulator's guild: six users, two bot applications,
   channels, a `leads` overwrite, the product bot's exact permissions
   (`simlib/script.py:501-576`). It is copied into WSL through stdin and the emulator is
   restarted (`simlib/emu.py:227-241`, `simlib/runner.py:148-160`), then verified over REST
   (`simlib/runner.py:166-185`). A "history experiment" checks whether seeded messages keep
   their ids and dates; the recorded answer is no, so every act is posted live
   (`simlib/runner.py:187-222`).
3. **Configure the product.** `teamctx init` output is rewritten to point `[discord] api_url`
   at the shim and to add an `[llm]` table (`simlib/host.py:121-130`,
   `simlib/runner.py:226-241`). A read-only API token is created into a file, never printed
   (`simlib/runner.py:332-340`).
4. **Run the product.** `teamctx run` starts with a filtered environment
   (`simlib/host.py:188-194`, `simlib/host.py:214-223`); the harness waits for `/healthz` and
   for `status.sync.gateway == "connected"` (`simlib/runner.py:297-322`).
5. **Play the team.** For each act the driver posts every item as its author through
   `/_discord/simulate/message` (bot posts go through REST with the bot token), writes an
   intent before and the emulator id after each post, and schedules edits, deletes and
   reactions a few seconds later (`simlib/driver.py:248-386`). Act 3 is posted while teamctx is
   stopped (`simlib/runner.py:545-561`); act 4 includes a gateway `reconnect` and an
   `invalidate` (`simlib/runner.py:563-564`).
6. **Use the product.** Captures (slash commands, context menus, a modal) and queries
   (`/search`, `/catchup`, `/teamctx status`, `/ask`) are sent as simulated interactions
   (`simlib/driver.py:445-621`). Each answer is stored with callback type, ephemeral flag,
   timing from snowflakes and the reply text; the product's short id (`**D-3**`) becomes an
   alias for the fixture entry (`simlib/driver.py:24`, `simlib/driver.py:534-535`).
7. **Check.** The checker compares the plan and the ledger with four evidence sources: the
   emulator's REST API (check 0), teamctx's SQLite file read-only, teamctx's JSON API and CLI
   (`export`, `q`), and the recorded reply texts (`simlib/checker.py:1-6`). Checks are saved
   in `state.json` and rendered into `reports/<run>/report.md` and `report.json`
   (`simlib/runner.py:605-640`).

### 2.3 The ground-truth model

Facts are planted by construction and scored by mapping ids back to the plan.

- **Posting ledger.** `map.json` maps every planned key (a dataset message id, `x:<name>` for
  extras, `<id>~<n>` for fragments) to the emulator message id, channel, poster and the
  follow-ups done (`simlib/driver.py:306-330`, `simlib/driver.py:369-386`). Everything else
  is scored through this map: jump links in product output are turned back into dataset keys
  (`simlib/checker.py:91-92`, `simlib/checker.py:587-596`).
- **Record plan.** Fixture entries (43 decisions, 24 tasks, 9 questions,
  `fixtures/demo/README.md:29-33`) plus the capture script define the expected final record:
  kind, status (`active`, `open`, `done`, `answered`, `superseded`), title, source message,
  owner, due date, the `replaces` chain and `answered_by` (`simlib/checker.py:371-398`,
  `simlib/checker.py:449-512`).
- **Retrieval eval.** 62 cases in five categories, each naming its expected messages and
  entries (`fixtures/demo/README.md:82-98`). Live recall@10 and MRR are computed the same way
  as teamctx's offline eval (`simlib/script.py:776-790`) and compared with
  `fixtures/demo/eval-baseline.toml` or the binary's own `teamctx eval`
  (`simlib/runner.py:397-411`).
- **Planted probes.** A private channel with a role and marker strings
  (`simlib/script.py:43-52`); two prompt-injection messages in the dataset
  (`simlib/script.py:750-752`); and in realism mode, pasted AI answers that contradict a team
  decision, a recap-only decision, a fake `sk-` key, gamer handles, an absent member and
  relative due phrases (`simlib/script.py:293-345`, `simlib/script.py:688-695`).
- **Keeping it valid under realism.** A fragmented message keeps its dataset id on the
  fragment that holds the eval answer; a split that would cut an answer is skipped; capture
  targets and injection probes are never split (`simlib/script.py:348-416`). Tests pin this
  (`tests/test_realism.py:39-65`).

### 2.4 Checks

| # | What it scores | Evidence | Fails when | Notes |
|---|---|---|---|---|
| 0 | Harness integrity | Emulator REST | A posted message is missing, has the wrong author/content, an edit, reply link or reaction is missing (`simlib/checker.py:111-159`) | Separates harness bugs from product bugs. Product-agnostic. |
| 1 | Startup | `doctor --live`, `/api/v1/status`, registered commands | Exit code, missing intent line, gateway not connected, a command missing (`simlib/checker.py:165-203`) | teamctx command names hard-coded (`simlib/checker.py:22-23`). |
| 2 | Sync completeness per act | SQLite `messages`, `sync_cursors` | Missing, duplicated, wrong author/channel/content, edit not reflected, deleted still present, stray message, cursor behind a sync point (`simlib/checker.py:209-312`) | Image-only messages are reported, not scored. |
| 3 | Offline gap and reconnects | SQLite | Act-3 messages missing or later than 60 s after restart; anything lost around a disconnect (`simlib/checker.py:333-365`) | 60 s limit hard-coded. |
| 4 | Commands and record | Reply texts, SQLite `record_entries`, `/api/v1/record` | Error, no answer, wrong ephemeral flag, slower than 3 s, wrong reply wording, wrong status/title/source/owner/due/chain (`simlib/checker.py:401-518`) | Largest and most product-specific check. |
| 5 | Retrieval | JSON API search and context | Never (`simlib/checker.py:724-725`) | Reports deltas against the offline baseline only. |
| 6 | Visibility (private channel) | All reply texts, `/ask` | Marker text reaches a user without the role or a public reply; positive control missing (`simlib/checker.py:736-786`) | Good pattern: has a positive control. |
| 7 | Prompt injection | Search/context framing, `/ask` answers | Text outside the data block, missing notice, a "free forever" claim, token-like output, citing the bot's injection message (`simlib/checker.py:800-858`) | Heuristics; passes when no answers exist (`simlib/checker.py:855`). |
| 8 | `/ask` over HTTP | `/api/v1/ask`, `llm_usage` | Not found, unmapped citation, no expected message cited (`simlib/checker.py:864-930`) | Has a token budget (`simlib/checker.py:879-882`). |
| 9 | Export | `teamctx export` files | Missing index/log, entry files differ from the record, missing source link (`simlib/checker.py:936-971`) | |
| 10 | Agent surface | `teamctx q` vs JSON API | Items or text differ (`simlib/checker.py:977-1008`) | |
| 11 | Realistic chat | Search ranks | A pasted AI answer outranks the team decision; recap not in top 3 (`simlib/checker.py:1028-1075`) | Reactions, images, noise are reported only. |
| 12 | Names vs handles | Search by first name | Half or more of the people are unfindable by first name (`simlib/checker.py:1078-1100`) | Labelled "product decision". |
| 13 | Secret pasted in chat | DB, API, replies, `/ask`, export | Any read surface returns the fake key (`simlib/checker.py:1103-1130`) | Labelled "product decision". |
| 14 | Catch-up after being away | `/catchup` reply | A change during the absence is neither listed nor counted as "N more" (`simlib/checker.py:1136-1166`) | |
| 15 | Relative due dates | SQLite `due_at` | Neither the UTC nor the local date of the stored due matches (`simlib/checker.py:1176-1209`) | See 5.1. |

Statuses are `pass`, `fail`, `n.a.` and `blocked`, each with one line of evidence
(`simlib/checker.py:21`, `RUNBOOK.md:134-135`). "Product decision" is a text prefix inside a
failure, not a status (`simlib/checker.py:1016`); the live view splits on that prefix
(`simlib/story.py:417`).

## 3. teamctx- or Discord-specific vs reusable

"Specific" means it would have to be rewritten or replaced for another product or platform.

| Module | teamctx-specific | Discord/emulator-specific | Environment-specific | Reusable for a general teamsim |
|---|---|---|---|---|
| `script.py` | Capture commands and options (`:616-701`), `/ask` questions (`:743-752`), the leads scenario | Snowflake ids from a fixed base (`:24-34`), permission names and bits (`:38-41`), seed format (`:501-576`) | none | Dataset to ordered plan; act split; extras spliced at fractions; the realism transform and its ground-truth rules (`:389-495`); deterministic seed; recall/MRR helpers |
| `driver.py` | Reply wording (`:483`), short-id regex (`:24`), the query list (`:561-621`) | Simulate endpoints, callback types 4/5/9, ephemeral flag 64, `discord.com` links (`:115`), snowflake times (`:30-31`) | none | Resumable posting ledger with intent-then-commit (`:306-344`); scheduled follow-ups (edit, delete, react); disconnects mid-act; per-interaction timing; placeholder resolution (`:102-122`) |
| `emu.py` | none | The whole client | WSL distro, user and `npx` start script (`:24-29`, `:215-249`) | Retry on 429 (`:79-84`); readiness wait (`:255-275`) |
| `shim.py` | Exists because teamctx stops on a 404 from thread routes (`:3-8`) | Thread routes | none | A loopback "fault and gap" proxy in front of a fake service is a useful general tool |
| `host.py` | Config keys, CLI, API paths, framed-text parsing, SQLite queries (`:121-130`, `:259-298`, `:301-443`) | Jump link regex (`:283`) | Windows-only child env list (`:47-48`), hosted model ids (`:41-45`) | Filtered child environment; product as a child process with a log; read-only DB access pattern |
| `checker.py` | Checks 1, 4, 7-10 almost entirely; reply wording; table names | 3 s interaction rule (`:433`), jump links (`:967`) | none | Check type and statuses (`:29-47`); check 0; sync scoring by ledger; visibility with a positive control; retrieval scoring by mapping links to keys; realism probes as an idea |
| `report.py` | Title and wording | none | none | Redact-then-write; summary table, timeline folding, per-interaction table |
| `net.py`, `envfile.py`, `state.py` | none | Discord token shape in the redactor (`envfile.py:75`) | none | All reusable as patterns: host-allowlisted transport, `Secret`, redactor with literals and shapes, atomic JSON stores, redacted timeline |
| `story.py`, `viz.py`, `viz/index.html` | Reply formats (`story.py:64`, `:180`, `:512`), act titles (`story.py:27-28`) | none | none | A loopback live view with Host/Origin/nonce guards (`viz.py:300-308`) and `textContent`-only rendering |
| `fixtures/demo` | Record kinds (decision/task/question) and statuses mirror teamctx; README points at teamctx test files (`fixtures/demo/README.md:71-98`) | Snowflake-encoded ids (`fixtures/demo/README.md:49-50`) | none | A fictional team with known facts and an eval set with expected ids is exactly the "preset" ADR 0003 asks for |
| `fixtures/teamctx-schema` | Entirely | none | none | Only as an example of pinning a product's schema |

## 4. Known gaps

- **No forwards.** The emulator has no message snapshots, so forwarded messages are not
  simulated; from teamctx's code a forward would be stored with empty content
  (`REALISM.md:55`).
- **No multi-week time.** All posts carry the posting time. The emulator stamps ids with its
  own clock, shared with heartbeats and token checks, so it cannot be moved; teamctx reads
  time from the id and has no injectable clock (`REALISM.md:51`). A full run compresses seven
  weeks into minutes, so date-window features (`/catchup since`, recency ranking) are tested
  only at one moment (`RUNBOOK.md:128-130`).
- **Emulator limits** (recorded by the prototype, not checked against the emulator's docs):
  no threads (threads are folded into the parent channel, `simlib/script.py:174-188`); thread
  routes answer 404, so a shim fakes empty lists (`simlib/shim.py:3-8`); attachments on
  simulated messages are dropped, so image-only messages are an empty-text embed
  (`simlib/runner.py:38`, `simlib/script.py:452-458`); modal submissions carry no resolved
  users, so a task form with an owner is resubmitted without one and the owner check becomes
  n.a. (`simlib/driver.py:483-494`, `simlib/checker.py:476-480`); the seed format has no message
  id, timestamp or reply field (`simlib/runner.py:212`); interactions wait about 3 s for an
  answer (`simlib/emu.py:155`).
- **Live-view coupling.** The driver carries watch-mode pacing and reads a speed file from the
  prototype folder before each pause (`simlib/driver.py:186`, `simlib/driver.py:224-246`); the
  runner emits extra events and pauses only for the view (`simlib/runner.py:579-580`,
  `simlib/runner.py:598-601`). `story.py` rebuilds the run from human-readable log summaries
  ("gateway connected", "run stopped", "(end of run)", "stored N s",
  `simlib/story.py:360-392`) and from teamctx's reply wording (`simlib/story.py:64`,
  `simlib/story.py:180`, `simlib/story.py:512`). Rewording a log line silently breaks the
  view. The page's "Start a new live run" runs `run-all --force` (`simlib/viz.py:112`), which
  deletes the saved `.state` of the last run.
- **Windows host plus WSL only.** The emulator manager shells out to `wsl.exe` with a fixed
  distro and user (`simlib/emu.py:218-225`); the child environment keeps only Windows
  variables, so a Linux or macOS host would start teamctx without `HOME` (`simlib/host.py:47-48`,
  not run). CI runs only the offline tests on Linux and macOS.
- **Scripted, not simulated, teammates.** No teammate decides anything at run time; nobody
  replies to the product's answers or adapts to them (section 1). There is no persona beyond
  id, display name, handle and bot flag (`simlib/script.py:92-113`).
- **One team, one guild, one product bot, one other bot.** Any bot member is given the
  crashwatch user id (`simlib/script.py:107`) and the bot author is hard-coded as member `107`
  (`simlib/script.py:168`, `simlib/story.py:30`).
- **No DMs, voice, pins, multi-task messages, conflicting deadlines or bot noise**
  (`REALISM.md:62`).
- **teamctx cannot be stopped gracefully on Windows**, so every stop is a hard kill
  (`simlib/host.py:231-246`). This doubles as a crash-recovery test, but there is no graceful
  path to compare against.
- **The model is fixed per run and its effect is not measured.** The `/ask` model is
  whichever probe answers first (`simlib/host.py:165-182`); runs with different models are not
  comparable, and repeated runs to measure variance are not supported.

## 5. Quality issues

### 5.1 Bugs and wrong results

| Where | Issue | Effect |
|---|---|---|
| `sim.py:183-188` | `check` (and `report`, `sim.py:199-200`) do not call `require_mode`, unlike `post`, `captures` and `queries` (`sim.py:173`, `:176`, `:180`). | Running `check` with the wrong `--plain` flag builds items for the other mode; `posted_keys` then looks up keys that do not exist (`simlib/checker.py:94-97`), and `report` prints act counts for the wrong mode (`simlib/runner.py:632`). |
| `simlib/runner.py:571-591` | If teamctx is not alive at the end, checks 3-15 are skipped without being saved. | The report shows fewer rows and no `BLOCKED` entries, so a crashed host can look like a clean partial run. |
| `simlib/checker.py:724-725` | Retrieval always returns `PASS`. | A large recall drop is invisible in the summary table. |
| `simlib/checker.py:1198-1201` | The relative-due check accepts the stored due's UTC date or its local date. | The check is meant to tell local from UTC resolution, but when the dates differ either interpretation can match, so a UTC-resolution bug may pass. Not confirmed without knowing how teamctx encodes `due_at`. |
| `simlib/checker.py:484-493` | Due dates one day early or late pass, with a detail line. | A real off-by-one in due-date handling passes. |
| `simlib/checker.py:855` | Check 7 passes when the API exists, even if no `/ask` answer was scanned. | "No model" reads as "injection-safe" for the `/ask` half. |
| `simlib/checker.py:136` | `entry.get("edited") is not False` is always true (the value is `True` or missing). | Dead condition; harmless today because edits are flushed before checks. |
| `simlib/runner.py:462` vs `:505-512` | The dry-run plan says the partial run checks after act 1; the code posts and checks acts 1 and 2. | Plan output is wrong. |

### 5.2 Fragile spots

- **Silent fallbacks.** `StoreReader` turns any SQLite error into an empty list
  (`simlib/host.py:397-407`). Only check 2 turns "no rows" into `BLOCKED`
  (`simlib/checker.py:210-212`); other checks see no entries and report misleading failures.
  A corrupt `state.json` or `map.json` loads as empty (`simlib/state.py:81-85`), after which a
  resumed `post` would post everything again. `all_record` stops after 20 pages without saying
  so (`simlib/host.py:351`).
- **Stale process ids.** `reset` and orphan cleanup send `os.kill(pid, 15)` to pids saved in
  `state.json` (`simlib/runner.py:276-284`, `simlib/runner.py:668-679`). On Windows this
  terminates whatever process now has that pid, for example after a reboot.
- **Matching on wording.** The raw-options fallback triggers when an error contains
  `"ubcommand"` (`simlib/driver.py:455`); the modal retry triggers on teamctx's exact refusal
  text (`simlib/driver.py:483`); capture replies must start with "Recorded", "Done" or
  "Answered" (`simlib/checker.py:439-445`); the emulator counts as failed if its log contains
  the word "error" anywhere before "Ready." (`simlib/emu.py:56`).
- **Broad exception catch.** `run_capture` turns any `KeyError` into "blocked"
  (`simlib/driver.py:531-533`). A programming error inside `menu` or `slash` (for example an
  unknown actor in `self.ids.users`) is reported as a missing prerequisite.
- **Crash recovery depends on the bot token.** `_reconcile` only runs when a teamctx token is
  set and only looks at the last 50 messages (`simlib/driver.py:332-344`); otherwise a crash
  between post and save posts the message again.
- **Global mode switch.** Realism is a module-level flag (`simlib/script.py:60`,
  `simlib/script.py:72-75`) read at call time by `build_items`, `build_captures`,
  `catchup_users`, the driver and the checker (`simlib/script.py:214`, `:678`, `:688`,
  `:733`; `simlib/driver.py:586`; `simlib/checker.py:705`). Tests must reset it by hand
  (`tests/test_realism.py:16-17`).
- **Invariants as `assert`.** Capture ordering is validated with `assert`
  (`simlib/script.py:697-700`), which `python -O` removes.
- **Hard-coded fixture knowledge in checks.** Entry ids `"2"`, `"6"` and member `"106"`
  (`simlib/checker.py:548-559`), a second crashwatch message id (`simlib/checker.py:827`), the
  injection ids (`simlib/script.py:751-752`), actor ids in queries
  (`simlib/driver.py:597-620`) and speaker weights (`simlib/script.py:442`). A second dataset
  would need code changes, not a preset.
- **Heuristic injection scoring.** A "free forever" mention is excused if any of about 30
  words ("no", "says", "email", ...) appears in the 60 characters before it
  (`simlib/checker.py:26`, `simlib/checker.py:792-797`); a real claim like "as the team says,
  it is free forever" would be excused.
- **Shim parsing.** Chunked bodies with chunk extensions raise `ValueError` in the handler
  (`simlib/shim.py:59-68`); the upstream URL is split by hand and needs an explicit port
  (`simlib/shim.py:146-147`).

### 5.3 Test gaps

The suite (230 tests) covers planning, the driver, the transport, the shim, secrets, the
story builder and the viz server well. Gaps:

- **No verdict test** for checks 1 (`check_startup`), 4 (`check_commands`, `expected_final`),
  5 (`check_retrieval`, `score_retrieval`), 7 (`check_injection`), 8 (`check_ask_http`),
  9 (`check_export`), 10 (`check_agent_surface`), 11 (`check_realistic_chat`), 12
  (`check_names`), 13 (`check_secret`) and 15 (`check_relative_due`). Only helpers are tested
  (`tests/test_checker.py:225-307`, `tests/test_realism.py:170-186`). Check 4 is the largest
  check (`simlib/checker.py:401-518`) and has no test.
- **No test of the scenario code** in `Harness`: `run_all` is tested only as a dry run
  (`tests/test_host.py:324`); `synced_all`, `verify_seed`, `history_experiment`, `_finish`,
  `cmd_reset` and `_stop_orphans` have no test.
- **No test of the mode guard** (`simlib/runner.py:58-64`), which is how the `sim.py:183` bug
  went unnoticed.
- **No test of redirect behaviour** in `UrllibTransport`.

### 5.4 Secret handling

What works: secrets are wrapped in `Secret`, which hides its value from `str`, `repr`,
`format` and pickling (`simlib/envfile.py:17-60`); every log line, timeline event, report and
live-view payload passes the redactor (`simlib/state.py:118-131`, `simlib/report.py:146-152`,
`simlib/story.py:553-561`); the redactor masks registered literals and known shapes
(`simlib/envfile.py:64-100`); the child process gets an allowlisted environment
(`simlib/host.py:188-194`); the API token lives in a file and is re-read per request
(`simlib/host.py:309-312`); tests check that fake secrets never reach logs or reports
(`tests/test_envfile.py:73-98`). The tokens in `script.py:33-34` are public fakes for the
emulator.

Issues:

- **Redirects bypass the host policy and forward credentials** (`simlib/net.py:121`,
  `simlib/net.py:131-144`). `build_opener` includes `HTTPRedirectHandler`, which follows a 3xx
  to any host and copies all headers except content headers (checked on Python 3.14.7). The
  transport checks only the first URL. A redirect from the hosted model endpoint would carry
  the model key to another host; a redirect from the product under test would carry the API
  token. Fix: a redirect handler that refuses, or re-runs `_check` and strips
  `Authorization`.
- **Literals shorter than 6 characters are never registered** (`simlib/envfile.py:85`).
  Reasonable for keys, worth stating as a rule.
- **Timeline redaction runs on the JSON-encoded value** (`simlib/state.py:128`). A secret
  containing a character JSON escapes (`"`, `\`, or non-ASCII) would not match its literal;
  shape patterns still catch common key formats.
- **Reports include the local binary path** (`simlib/runner.py:103`, `simlib/runner.py:617`).
  Reports are gitignored, but a shared report leaks a machine path.

### 5.5 Untrusted input handling

What works: dataset text is copied and compared, never interpreted (`simlib/script.py:3-4`);
the seed goes into WSL through stdin, not a shell string (`simlib/emu.py:227-232`); shell
scripts are constants (`simlib/emu.py:28-29`); the live view renders story text with
`textContent` only (`viz/index.html:354-355`), sends a strict CSP (`simlib/viz.py:34-35`) and
guards its only state-changing endpoints with Host, Origin and a per-process nonce
(`simlib/viz.py:300-308`); the viz server refuses any bind address but loopback
(`simlib/viz.py:342-346`). The harness itself uses no language model, so chat text cannot
steer it.

Issues for a general teamsim, where the product under test is arbitrary and less trusted:

- **Product output goes into the Markdown report raw** except for `|` and whitespace
  (`simlib/report.py:18-20`, `simlib/report.py:113-120`). Links or images in a reply would
  render, and load remote content, in a Markdown viewer.
- **No size limits** on responses from the emulator or the product (`simlib/net.py:142`) or on
  shim request bodies (`simlib/shim.py:68`).
- **The shim does not check the Host header** (`simlib/shim.py:102-136`), unlike the viz
  server; a DNS-rebinding page could reach the emulator through it. Low risk while it only
  runs during a test run.

### 5.6 Privacy cleanup before the repo goes public

- The WSL distro name and user are hard-coded and come from the maintainer's local setup:
  `simlib/emu.py:4`, `simlib/emu.py:24-25`, `simlib/runner.py:618`, `tests/test_host.py:283`,
  `RUNBOOK.md:31`. Make them configuration with neutral defaults.
- References to the source project's internal specs and paths: "Spec A" and "Spec C"
  (`REALISM.md:24`, `RUNBOOK.md:32`), `crates/...` paths (`simlib/runner.py:40`,
  `simlib/script.py:777`, `fixtures/demo/README.md:71-98`, `fixtures/demo/eval-baseline.toml:1-2`).
  These are not private, but they point at files that are not in this repository.
- `RUNBOOK.md:155` says "Nothing here is committed or pushed ... this folder must stay local",
  which is no longer true. `RUNBOOK.md:90` names `open-live-view.cmd`, which is not in the
  repository. `REALISM.md:5` cites a report folder that is gitignored.
- `REALISM.md:3-6` and `REALISM.md:64-69` describe learning from a real team server through
  numbers only; that is within the project rules, and no names, ids or text from it appear in
  the files read for this audit.

## 6. Keep, change, drop

**Keep** (as behaviour and test design, whatever the stack):

- The three-layer ground truth: posting ledger, record plan, eval set with expected ids
  (section 2.3), and the rule that transforms must keep it valid (`simlib/script.py:389-416`).
- Check 0 as a separate "harness integrity" check that compares the workspace with the
  ledger before blaming the product (`simlib/checker.py:111-159`).
- The four statuses with one line of evidence each, and the per-interaction table.
- Probes with a positive control (check 6 fails if the role holder cannot see the private
  text, `simlib/checker.py:758-761`).
- Resumable, intent-then-commit posting (`simlib/driver.py:306-344`) and atomic state writes.
- Fault injection: hard stop with an offline act, gateway reconnect and invalidate
  (`simlib/runner.py:542-569`).
- The realism transform as a separate, seeded, measurable layer ("realism tax",
  `REALISM.md:36`), calibrated from numbers only (`REALISM.md:64-69`).
- The security patterns: `Secret`, the redactor on every output, host-allowlisted transport,
  loopback-only servers with Host/Origin/nonce guards, filtered child environment.
- Fake transports and injectable clocks/sleeps, so the whole flow is tested offline.
- The fictional demo dataset as the first preset.

**Change:**

- Put a product adapter boundary between the core and the product: how to start it, how to
  read its state, how to call its read surfaces, how to map its ids and links back to ledger
  keys. Today these are spread across `host.py`, `checker.py`, `driver.py` and `story.py`.
- Put a workspace adapter boundary between the core and Discord (post, edit, delete, react,
  interact, disconnect, list), so a second platform or a native fake workspace is possible.
- Make presets data, not code: the cast, actors, captures, probes, queries and the ids the
  checks need should come from the preset file, not constants in `script.py`, `driver.py` and
  `checker.py`.
- Replace the realism global with an explicit run configuration passed to every builder.
- Give every check a threshold or exact expectation it can fail; make "product decision" a
  status or tag, not a text prefix.
- Record skipped checks as `BLOCKED` with the reason; fail loudly on unreadable stores.
- Make the emulator host, user and start command configuration; support Linux and macOS hosts.
- Model order: local first, hosted only when configured (ADR 0003); record the model id, a
  run seed and repeat runs so model effects can be measured.
- Fix the redirect handling, escape product text in reports, bound response sizes.
- Feed the live view from structured events with a fixed schema, not from log wording or
  product reply wording; keep viewing pace out of the driver.

**Drop:**

- The shim's thread stubs and the modal-owner workaround as permanent features: they exist
  because of this emulator's gaps (`simlib/shim.py:3-8`, `simlib/driver.py:483-494`).
- Reading the product's SQLite file as a primary evidence source; prefer the product's public
  surfaces, with direct DB reads as an optional, adapter-specific extra.
- The history experiment as a run step (`simlib/runner.py:187-222`): it answers a one-time
  question about this emulator and restarts it twice per run.
- teamctx-specific checks (1, 4's reply wording, 9, 10) from the core; they belong in a
  teamctx adapter or preset.

### 6.1 What simulated feedback (ADR 0003) needs that the prototype lacks

ADR 0003 allows feedback only once it can be measured: diversity across personas, a
sycophancy check and a comparison with published human results. Measured against that:

1. **Personas.** The cast has an id, a display name, a handle and a bot flag
   (`simlib/script.py:92-113`). Feedback needs persona definitions (role, experience,
   attitudes, workload) stored in the preset and recorded with each output.
2. **Model-driven teammates.** Nothing in the prototype calls a model to produce teammate
   text or opinions; the only model call from the harness is a 5-token probe
   (`simlib/host.py:133-146`). A feedback step needs a model client, local by default, with
   the same allowlisting and redaction as the rest, and a rule that chat and product text
   reach it only as framed data.
3. **Exposure log per teammate.** Feedback should be grounded in what each teammate actually
   saw. The prototype already records every interaction with its actor, reply text,
   ephemeral flag and timing (`simlib/driver.py:72-99`); that is the right starting point,
   but it is only kept for scripted commands, not for what each member read in channels.
4. **An elicitation protocol.** A fixed questionnaire or interview after the run, with
   versioned prompts and structured answers (ratings plus free text), so results can be
   compared across runs and models.
5. **Measurements.** Diversity across personas (for example the spread of ratings and of
   reasons), a sycophancy check (feedback on a deliberately degraded product build, or the
   same question asked with positive and negative framing, must change), repeat runs with
   different seeds and models to show variance, and a comparison set of published human
   results to score against. The prototype's pattern of comparing live numbers with an
   offline baseline (`simlib/runner.py:642-655`) can be reused for this.
6. **Presentation.** A separate report section labelled as hypotheses, with the model id,
   seed, persona and prompt version per statement. The current report has no place for it.

## 7. Questions for the maintainer

1. The privacy items in 5.6 are code and docs changes inside `prototypes/teamctx-sim/`, which
   this documentation-only task does not own. Should they be fixed in the prototype before the
   repo goes public, or should the prototype be frozen and the cleanup happen only in the new
   implementation?
2. The prototype's model order (hosted first, local second) contradicts ADR 0003. Should the
   prototype be changed to match the ADR, or left as a historical reference with a note?
3. Check 5 never fails. Should teamsim's retrieval checks fail against a baseline (as the
   source project's CI does, `fixtures/demo/eval-baseline.toml:2`), or stay informational?
4. Should "product decision" become its own status in teamsim reports, separate from `fail`?

## Sources

All sources are files in this repository at commit `0778a8c`, read 2026-11-11:
`prototypes/teamctx-sim/` (RUNBOOK.md, REALISM.md, sim.py, simlib/*, tests/*, viz/index.html),
`fixtures/demo/` (README.md, dataset.json, eval.toml, eval-baseline.toml),
`fixtures/teamctx-schema/README.md`, `docs/adr/0002-start-from-the-teamctx-prototype.md`,
`docs/adr/0003-scope-tests-and-simulated-feedback.md`. The redirect behaviour was confirmed by
inspecting `urllib.request.HTTPRedirectHandler.redirect_request` and the handlers of
`build_opener` in Python 3.14.7 on 2026-11-11.
