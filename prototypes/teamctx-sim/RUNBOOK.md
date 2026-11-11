# RUNBOOK: teamctx end-to-end simulation (the first teamsim prototype)

Everything lives in `prototypes/teamctx-sim/`. Python 3.14, standard library only, always
`python -I`. Commands are run from the repo root in Git Bash or PowerShell. Nothing here
builds Rust: set `TEAMSIM_TEAMCTX_BINARY` in the repo's gitignored `.env` (or the
environment), or pass `--teamctx PATH`. The binary must be a teamctx build with the loopback
`[discord] api_url` setting. The harness copies it to `.state/bin/` first, so a rebuild
elsewhere never hits a locked file.

## What it does

A fictional six-person team ("Lantern Shelf", the demo dataset) chats through the Discord
emulator in WSL; the real `teamctx run` syncs it live over the gateway; the team captures
record entries with the real slash commands and context menus; the host goes offline for
Act 3 and catches up; then search, catch-up, `/ask`, the JSON API, `teamctx q` and export are
exercised. A checker scores every step and writes a report.

| Act | Original dates (UTC) | Dataset messages | Extras |
|---|---|---|---|
| 1 | 03-02..03-15 | 103 | none |
| 2 | 03-16..03-31 | 104 | 1 "wrong channel, ignore" (deleted), 2 messages in `leads` |
| 3 | 04-01..04-14 | 70 | none (teamctx is offline while it is posted) |
| 4 | 04-15..04-24 | 37 (2 from `crashwatch`) | 1 "wrong channel, ignore" (deleted) |

Dataset total 314 (+4 extras = 318 posts). Threads are folded into their parent channel. Two
messages are edited after posting (` (draft)` first). Act 4 includes a gateway `reconnect` and
an `invalidate`.

## Preconditions

- WSL distro `sbx-ubuntu` with the emulator installed in `~/emu` (already done; never reinstall).
- A teamctx binary with the loopback `[discord] api_url` setting (Spec C).
- Optional: `TEAMCTX_LLM_KEY` in the repo-root `.env` (OpenRouter) or LM Studio on
  `127.0.0.1:1234`. Without either, `/ask` checks are `blocked` and the rest runs.
- Ports free on Windows: 4000 (emulator via WSL), 4001 (shim), 7420 (teamctx).

## The one-command run

```text
python -I prototypes/teamctx-sim/sim.py run-all --dry-run          # print every planned step, no network
python -I prototypes/teamctx-sim/sim.py run-all --force            # full scenario, real pacing (about 8 minutes)
python -I prototypes/teamctx-sim/sim.py run-all --force --pace 0.15   # same, faster posting
python -I prototypes/teamctx-sim/sim.py run-all --force --fast        # no sleeping between messages
python -I prototypes/teamctx-sim/sim.py run-all --stop-before-host --fast --force   # no teamctx binary needed
```

Runs use **realism mode** by default (handles, quick fragments, reactions, image-only messages,
off-topic bursts, pasted AI answers, a pasted fake key, an absent member, `-08:00` timezone and
checks 11-15; see `REALISM.md`). Put `--plain` before the command for the original scenario,
for example `python -I prototypes/teamctx-sim/sim.py --plain run-all --force`. One `.state/` folder holds one
mode; switching modes needs `--force` or `reset`.

`--force` resets `.state/` and restarts the emulator, so the run starts from a clean seed.
Keep the command attached (or run it as a background task): the emulator is started detached
from the harness, but killing the shell that launched the harness can still take it down.
Without `--force`, `run-all` resumes where it stopped (state in `.state/state.json` and
`.state/map.json`; `post` never posts a message twice).

The report path is printed at the end and written to `prototypes/teamctx-sim/reports/LATEST.txt`.

## Step by step (same thing, manually)

```text
python -I prototypes/teamctx-sim/sim.py seed                       # build seed.json, copy it into WSL through stdin
python -I prototypes/teamctx-sim/sim.py history-experiment         # does the emulator keep message ids? (restarts it twice)
python -I prototypes/teamctx-sim/sim.py emu start                  # (re)start the emulator with the real seed
python -I prototypes/teamctx-sim/sim.py shim                       # in a second terminal: loopback shim 4001 -> 4000
python -I prototypes/teamctx-sim/sim.py config                     # teamctx init -> .state/teamctx.toml, pick the /ask model
python -I prototypes/teamctx-sim/sim.py token                      # API token into .state/api-token (never printed)
python -I prototypes/teamctx-sim/sim.py host start                 # teamctx run; waits for gateway "connected"
python -I prototypes/teamctx-sim/sim.py post --act 1 --pace 0.15
python -I prototypes/teamctx-sim/sim.py captures --act 1
python -I prototypes/teamctx-sim/sim.py queries --act 1
python -I prototypes/teamctx-sim/sim.py check --act 1
# act 2 the same; for act 3: host stop, post --act 3, host start, then captures/queries/check
python -I prototypes/teamctx-sim/sim.py post --act 4 --pace 0.15
python -I prototypes/teamctx-sim/sim.py captures --act 4
python -I prototypes/teamctx-sim/sim.py queries --act 4
python -I prototypes/teamctx-sim/sim.py report
python -I prototypes/teamctx-sim/sim.py host stop
python -I prototypes/teamctx-sim/sim.py reset                      # stop everything, delete .state/ (reports are kept)
```

`post --dry-run` prints the planned calls for an act. `check --emu-only` compares only against
the emulator (no teamctx needed). The final checks 3 to 10 run in `run-all`; the manual `check`
command runs checks 0 and 2 per act.

## Live view (no commands needed)

Double-click `prototypes/teamctx-sim/open-live-view.cmd` (or open <http://127.0.0.1:4100> if it is already up). It
starts the viz server in a minimised window (keep that window open: the run it starts is its child,
and the emulator lives as long as it does), then opens the browser. The page has two buttons:
"Watch the last run" (replay of `.state`, with play/pause, 1x-8x, restart) and "Start a new live
run" (the server starts `sim.py run-all --force --paced` itself and the page switches to LIVE). Only
one run at a time; a run started from a terminal also disables the buttons. CLI equivalents:
`python -I prototypes/teamctx-sim/sim.py viz [--port 4100] [--no-open]` and `run-all --watch`.
Safety: loopback bind only; Host and Origin must be exactly `127.0.0.1:<port>`; the only endpoint that
changes anything is `POST /api/start`, which also needs the per-process nonce embedded in the page.
Everything the page receives passes through the redactor; chat text is rendered with `textContent`.
The run's output goes to `prototypes/teamctx-sim/viz-run.log`.

## Watching it happen

- Emulator inspector: <http://localhost:4000/> (guilds, channels, messages, interactions with how
  they were delivered and answered, gateway sessions). It needs no token.
- teamctx log: `prototypes/teamctx-sim/.state/host.log`. Harness log: `.state/harness.log`; timeline:
  `.state/timeline.jsonl`.
- teamctx's own view: `http://127.0.0.1:7420/api/v1/status` (needs the API token in
  `.state/api-token` as a Bearer token; do not paste it into shared places).
- The emulator control token printed in its startup banner is a local secret. The harness never
  needs it and redacts it everywhere; use the inspector URL above instead of the control one.

## How to read the report

`reports/<run id>/report.md` (and `report.json`):

1. **Summary table**: one row per check, status `PASS`, `FAIL`, `n.a.` or `BLOCKED`, with the
   evidence in one line. Check 0 (harness integrity) compares the emulator with what the harness
   posted, so a failure there is a harness problem, not a teamctx problem.
2. **Run facts**: binary, model used for `/ask` and why, token use recorded by teamctx, the shim.
3. **Acts** and the **history-seeding experiment** outcome.
4. **Timeline**: posts are folded into runs; disconnects, restarts, captures and checks are listed
   with times.
5. **Checks in detail**: every problem found, with the message or entry involved.
6. **Interactions**: one row per scripted command: callback type (4 message, 5 deferred, 9 form),
   ephemeral flag, time to first answer (from snowflake timestamps), deferred-then-edited time,
   the entry id it produced and the reply text.
7. **Retrieval**: live recall@10 and MRR on messages per category next to the offline numbers
   from `teamctx eval` and the delta. Live numbers differ from offline ones because every message
   carries the posting time (recency scoring), the date category is n.a., and threads are folded.
8. **Observations** and **Assumptions about API shapes** (what could not be confirmed from source
   or docs).

Statuses mean: `PASS` verified with evidence; `FAIL` a real discrepancy (the detail names it);
`n.a.` cannot apply in the emulator; `BLOCKED` a precondition is missing (no binary, no model).

## Checks

0 harness integrity (emulator ground truth) / 1 startup (doctor --live, READY, commands) /
2 sync completeness per act / 3 offline gap, reconnect, invalidate / 4 commands and captured
record / 5 retrieval vs offline eval / 6 visibility (`leads` channel) / 7 prompt injection /
8 `/ask` over HTTP / 9 export / 10 agent surface (`teamctx q`).

## Safety

- The harness talks only to the emulator (`127.0.0.1:4000`/`3999`), the shim, the teamctx host on
  loopback, LM Studio on loopback, and OpenRouter (one probe; teamctx's own model calls are made
  by teamctx). The emulator URL is asserted loopback in code.
- The OpenRouter key, the API token and the emulator control token are never printed, logged or
  written to a report: every output passes through `simlib/envfile.py` (literals plus shape
  patterns for `sk-or-...`, `tctx_...`, `Bot ...`/`Bearer ...`, Discord-style tokens, control
  token). The key reaches only the teamctx child process environment and the one probe.
- The harness touches the WSL distro only in `~/emu` and the emulator process.
- Dataset text is untrusted data, including two prompt-injection messages; nothing follows it.
- Nothing here is committed or pushed. The repo is public; this folder must stay local.

## Known limits

- teamctx cannot be stopped gracefully by a Windows parent (it handles Ctrl-C in its own console
  only), so "stop" is a hard stop (also a crash-recovery test).
- The emulator has no threads, attachments on simulated messages, or resolved users in modal
  submissions; see the report's assumptions list for how each is handled.
- Run `python -I -m unittest discover -s prototypes/teamctx-sim/tests` after any change to this folder.
