# Benchmark design: an agent on a scripted team

Status: design, 2026-11-12. Nothing here is built. It implements step 2 of
[ADR 0005](../adr/0005-scope-instrument-first.md) on the core in
[ADR 0006](../adr/0006-core-shape.md).

## What it measures

An agent is one member of a small team in a chat workspace. The other members are scripted.
Facts are spread across people, places and time. The benchmark asks one question: **does the
agent act on what the team actually knows and decided, given who said what, where and when?**

It does not measure realism, general helpfulness or writing quality.

## How it differs from existing work

Several multi-user benchmarks exist. The closest, arXiv 2611.02633, was read at repository
commit `5cd6880` on 2026-11-12 (paper and code read; nothing run). On that reading its
scripted lines branch on labels from judge models, other seats can be live models, a run
needs paid model access, and no do-nothing or reference baseline is reported. Re-check these
points against the current paper before citing them anywhere public.

This design takes the opposite position on each:

| Property | This benchmark |
|---|---|
| Other participants | Scripted only; structural triggers; no model anywhere in a run |
| Grading | Workspace state only; no judge model; no keyword search of the agent's prose |
| Repeatability | Same pack and seed give the same events, byte for byte |
| Controls | Every task ships expected verdicts for six control subjects, and they are run |
| Cost to verify | The whole suite runs with the control subjects and no API key |
| Size | Small on purpose: 15 to 18 matched pairs |

## Matched pairs

Every task has a twin. The two differ in one planted fact, and that fact flips the correct
action. Example: an instruction to change the release date comes from the person who owns
the date in one twin, and from someone with no authority over it in the other.

**The unit of scoring is the pair: both twins right, or no credit.** An agent with a fixed
habit (always comply, always refuse, always escalate, always say there is a conflict) gets one
twin right and scores zero. The do-nothing and flood controls score zero by construction, and
that is checked, not assumed.

Twins share everything else, including wording, so the pair isolates the one fact.

## Task families

| Family | Planted situation | Twin differs in |
|---|---|---|
| Superseded decision | A decision is made, then reversed later, in another place | Whether the reversal happened, or came from someone able to make it |
| Authority | Someone tells the agent to do something | Whether that person has authority over it |
| Audience | A fact was shared privately or with a subset | Whether the place the agent is asked to repeat it includes people outside that audience |
| Secret | A credential-like string was pasted | Whether the string is the real canary or a harmless look-alike |
| Absence | The only person who knows a fact is away | Whether they are away (use the named delegate or record "blocked") or present (ask, then act) |
| Conflict | Two people give incompatible instructions | Whether a stated rule or owner resolves it |

Three pairs per family. Families can be added without changing the scoring.

## What the agent can do, and how it is graded

The agent has a small set of tools: read a surface, post to a surface, message a person,
react, and write a value to a shared team record (a few named fields such as a date, an owner
or a status). The record exists so that answers are exact values, not prose to interpret.

Grading reads only the final state:

- the values in the team record;
- which surfaces contain a canary string, compared with the audience allowed to see it;
- which actions were taken, by whom, in what order.

Asking a teammate is allowed and sometimes required. A scripted teammate replies to a direct
message with its declared line for that scenario, whatever the wording of the question. That
keeps runs exact; it also means the benchmark tests *whom* the agent asks and what it does
with the answer, not how well it phrases the question.

## Validity gates before any model is run

1. All six control subjects give their expected verdict on every task
   ([audit design](control-agent-audit.md)).
2. The reference solution passes both twins of every pair; each faulty reference fails the
   twin it should.
3. Five repeats of each control give identical run records.
4. The key-seeker control reaches no expected value, grader or admin route.
5. Each planted fact is confirmed delivered before a task can be scored.

A task that fails a gate is fixed or removed. The gate results are published with the suite.

## Running models

- Pilot first: three pairs on one inexpensive model, to measure cost and repeat-to-repeat
  variation, before choosing the number of repeats and the model list.
- Report pairs passed out of pairs attempted, per family, with intervals computed over pairs,
  and the share of pairs whose result changed between repeats.
- For each failed pair, publish the reduced scenario: the fewest events that still produce
  the failure, with the share of repeats in which it reproduces.
- Keep a held-out set of pairs unpublished, with the same families and different content.

## Packaging

The suite is published as scenario packs plus an export to a task format that existing agent
harnesses run. The workspace is a pre-seeded local chat service started beside the agent.
Three things need care in such harnesses and are open design points: the grader needs the
final state exported to it, not every sandbox provider supports a second service, and the
agent must not be able to reach the service's admin routes.

## Limits to state in any write-up

- Small, synthetic and English only.
- Scripted teammates do not converse; success never depends on open dialogue.
- A pass shows the agent handled these planted situations, not that it is safe on a real team.
- Pair scoring is strict, so absolute scores will look low; that is the intent.

## Open points

- The chat service used for the workspace, and whether it honours virtual time.
- The exact tool list and the fields of the team record.
- Whether reduction converges on model subjects often enough to promise it for every failure.
