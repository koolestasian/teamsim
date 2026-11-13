# Control-agent audit: design

Status: design, 2026-11-12. Nothing here has been run. It implements step 1 of
[ADR 0005](../adr/0005-scope-instrument-first.md) and defines the control subjects that
[ADR 0006](../adr/0006-core-shape.md) requires for every scenario pack.

## Question

For a public benchmark in which an agent works alongside other participants: do its graders
give the right verdict to agents whose correct verdict is known in advance?

A grader is only informative if an agent that did nothing fails, an agent that did the right
thing passes, and an agent that did the right thing wrongly fails. All three can be tested
with scripts, without a model.

## Targets

A benchmark qualifies if its code and tasks are public, its licence permits running and
reporting on it, and it can be run locally. Candidates are listed in the benchmark design
once the closest ones have been read in full. Start with one; add a second only after the
first is finished.

## Control subjects

| Control | What it does | Correct verdict | A wrong verdict shows |
|---|---|---|---|
| Null | Ends at once without acting | Fail, except tasks where doing nothing is right | Passes that require no work |
| Noise | Posts short, plausible, task-irrelevant messages and performs harmless actions | Fail | Graders that reward activity or keywords |
| Flood | Does everything broadly: replies to everyone, repeats all visible text, performs every available action once | Fail wherever a side effect or disclosure is forbidden | Graders that check for a wanted outcome but not for unwanted ones |
| Key-seeker | Uses only the access the task gives the agent to look for expected answers, grader files, environment variables and admin routes | Finds nothing | A reachable answer key or a resettable state |
| Reference | Performs the task's published or derived solution | Pass | False failures, undelivered task content, flakiness |
| Faulty reference | The reference with one defect: a wrong value, the right value in the wrong place, a superseded decision, or a correct result plus a forbidden side effect | Fail | Assertions too weak to tell right from nearly right |

Each task states its expected verdict per control before anything is run. Where a task has no
published solution, the reference is written from the task text and marked as derived.

## Measurements

- False passes per control and task; false failures of the reference.
- Tasks where planted content was never delivered to the agent.
- **Harness variation:** every control is a script, so repeating it five times should give
  five identical results. Any difference is variation in the environment or grader itself,
  measured separately from any model.
- What the key-seeker could reach, with the path or route.

Report counts with intervals, by task id, with the benchmark's commit hash. State which tasks
were not run and why. Make no claim about tasks or benchmarks that were not tested, and none
about the quality of the benchmark as a whole.

## Limits on what the controls may do

- Run only locally, on public code, within its licence.
- The key-seeker uses only what the task's own sandbox exposes to an agent. It does not attack
  hosted services, other tenants or the host machine.
- If a target can only be run against its authors' hosted infrastructure, it is out of scope.

## Disclosure

1. Send findings and reproduction scripts to the authors privately, with proposed fixes where
   they are simple.
2. Wait 30 days, or until they reply, before publishing anything.
3. Publish with their response included. Findings they have fixed are reported as fixed.

## Reuse

The same six controls become the validation gate for teamsim's own packs: a pack is not valid
until its controls produce their expected verdicts. Running them against other benchmarks
first tests the controls themselves.

## Open points

- The exact target list and task counts.
- How a reference solution is derived when none is published, and who reviews it.
- Whether the flood control needs task-specific limits to avoid trivially tripping rate
  limits instead of graders.
