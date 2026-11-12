# Literature review: synthesis and decisions (2026-11-11)

The run-1 notes looked at tools, repositories and posts. This pass looked at the research
literature: peer-reviewed papers and arXiv preprints, the older foundations and the 2025-2026
work. Seven notes cover seven questions; this one puts them together, says what they mean for the
open decisions, and lists what to build first.

| Note | Question |
|---|---|
| [lit-simulated-people](2026-11-lit-simulated-people.md) | Can an LLM stand in for a person's opinions and feedback? |
| [lit-evaluation-methods](2026-11-lit-evaluation-methods.md) | How do you build an evaluation with simulated users that people can trust? |
| [lit-personas](2026-11-lit-personas.md) | How do you make distinct, consistent, non-sycophantic teammates, and what can small models do? |
| [lit-team-dynamics](2026-11-lit-team-dynamics.md) | What team phenomena are worth planting, and can models produce them? |
| [lit-chat-realism](2026-11-lit-chat-realism.md) | What does real team chat look like in numbers, and how can patterns be learned safely? |
| [lit-scenario-testing](2026-11-lit-scenario-testing.md) | How should scenarios, oracles and checks be designed so a score means something? |
| [lit-product-checks](2026-11-lit-product-checks.md) | How does research score what team-facing products do (memory, decisions, injection, privacy)? |

## How much to trust this

- **Size.** 455 distinct papers cited by arXiv ID or DOI (the full list is in [bibliography/](bibliography/)), plus a few journal and web pages without
  one. 77 were read in full text; the rest are cited from their abstracts and marked as such in
  each note. Numbers that drive a recommendation come from full-text reads where possible.
- **Citations checked.** Every arXiv ID and DOI in the seven notes was looked up against arXiv and
  Crossref on 2026-11-11. All of them exist, and the cited names were checked against the official
  titles.
- **Mostly preprints.** Most 2025-2026 work is on arXiv and not yet peer reviewed. The notes say
  which venues were checked. Directions that many independent groups report are more trustworthy
  than any single number.
- **Other domains.** Almost no paper studies a simulated team chatting in a workspace while a
  product watches. The numbers come from customer-service simulators, surveys, debate, memory
  benchmarks, driving simulators and developer chat. Read them as ranges and directions, not as
  pass marks for teamsim.

## What the literature agrees on

These come up in several notes, from independent groups. They are the solid ground.

1. **Simulated people are an "easy mode".** The one study that ran a full agent benchmark with
   real people (451 participants, 31 LLM simulators) found simulators too cooperative, too
   polite, too uniform and uniformly positive in feedback; only 1.0% of GPT-4o's turns were short,
   against 29.0% for people. Bigger models were not better simulators. Cited in four of the seven
   notes, and other studies in the same notes point the same way.
2. **Models do not reliably produce group behaviour.** LLM groups conform more, lock in earlier,
   lose facts that only one member holds, and average expert and non-expert views. Persona prompts
   change what a model says about itself, not what it does (questionnaire-to-behaviour agreement
   at chance for small and mid models). Personas drift back to the default assistant over long
   dialogues.
3. **Ground truth beats judges.** Benchmarks that score the final state of the world are more
   trustworthy than LLM judges, which miss false "done" claims (AUROC at most 0.65 in one large
   study) and are reliable more than they are valid (stable under irrelevant edits, but sensitive
   to real faults only 32% of the time in one study).
4. **Checkers fail too.** Audits of agent benchmarks found most with validity flaws; a do-nothing
   agent passed 38% of one well-known task set, and a scorer counting "the tool was called"
   reported 21.7% attack success where the true rate was 1.2%. A test suite needs its own tests.
5. **One run is not a result.** Repeated runs fall off sharply (pass^k), temperature 0 is not
   deterministic, and changing only the reporting rule moved scores by up to 21 points.
6. **Simulated feedback can find planted defects, but cannot forecast real reactions.** No study
   showed simulated users telling a good product from a bad one against real outcomes. The best
   human comparison found LLM walkthroughs raised 0.5-0.6 issues per run against 7.5 for people,
   and only matched people when prompted at known failure points.
7. **Real chat is messy in specific, countable ways.** About a quarter of developer-chat questions
   get no reply; only about half of messages name the person they answer; conversations interleave;
   timing is bursty with heavy tails; rates differ by channel type (reactions differ about 3x
   between project and social channels). LLM-written chat lacks exactly this mess, and prompting
   for it overshoots.

## The decisions, one by one

### 1. Model-free scripted default: strongly supported

Every note that touches it supports the run-1 proposal that an ordinary scored-test run needs no
model. The script should own who speaks, when, what each teammate believes, which facts appear and
when a mind changes. Reasons: ground truth needs no model; models conform, drift and flatten;
reproducibility needs seeds and replay, which models break.

A model, when used, writes wording only: one turn per call, from a short persona record and a few
example lines, checked against the planted fact it must carry, roughened by a scripted friction
layer, and recorded for replay.

**Needs the maintainer:** ADR 0003 says "a local model by default". The evidence says "no model by
default; a model as a measured option". Changing an accepted ADR needs your OK.

### 2. If a model is used: 7-8B or larger, and only after a pushback test

This changes a run-1 assumption. The run-1 personas note sized local models for speed (3-4B on a
laptop CPU). The literature says small instruct models are the most sycophantic: a false authority
claim was followed 94% of the time by a 1.5B model, 79% by a 4B, 69% by a 7B and 36% by a 14B,
against 4-11% for frontier models. Small models also leaked private information most in group
chat. Recommendation: a model may play a teammate who must push back only if it lands in the
"resistant" band (under 30% follow rate) on teamsim's own test; otherwise that pushback is scripted.

### 3. Stack: the literature is neutral

Nothing in it favours a language. It does ask for a deterministic, replayable runtime, control
bots that run in CI, and simple statistics (Wilson intervals, rank correlation, histograms,
two-sample distances), all of which the standard library of any candidate stack covers. The R05
recommendation (Python core shipped with uv) is not affected. Gate G1 remains your call.

### 4. v0.1 teammate actions: chat first, then tasks and issues, repo last

Chat alone supports most of the checks the literature points to (retrieval, abstention, knowledge
update, injection by exact string, privacy, hidden profile, reversals, absence). Tasks and issues
add checks with exact answers (status, owner, due date) and evidence on bot noise in pull requests,
so they are a cheap second step. Repository actions add nondeterminism and are needed only for
argument-level injection scoring on real side effects. There are realism numbers for chat; for
tasks and repos the literature gives none, so do not claim realism there yet.

### 5. First user: builders of team-facing software, unchanged

The literature cannot measure demand, so this stays as run 1 left it. It adds two points. First,
what builders need most is what the literature says is missing from current evaluations: exact
oracles, negative probes, intervals and controls. Second, three checks have no published
benchmark at all (catch-up for an absent member, relative due dates across time zones, handles
versus names), so teamsim would be measuring something new.

### 6. Simulated feedback (ADR 0003): can meet the bar in a restricted form, after scored tests

The bar as written (measured diversity, a sycophancy check, comparison with published human
results) can be met by a narrow feature: **a defect-finding hypothesis generator**, scored on
planted ground truth. It cannot meet a bar of "predicts how a real team would react", and should
never claim to. What the gate should contain, combining four notes:

- **Planted-defect recall**, unprompted and prompted, with false alarms counted.
- **A bad-product control** in every run: a variant with an obvious planted flaw that the panel
  must reject. This is the sycophancy gate and the only discrimination test available.
- **A positivity rate** printed next to the defect recall, because simulated evaluators lean
  positive.
- **Diversity** across teammates, as a ratio to the scripted lines (not an absolute cosine cutoff;
  the common 0.8 cutoff is passed by 20-32% of pairs that say different things).
- **A no-model baseline** beside every result (a plain prompt or the scripted team), because in
  several audits simple baselines matched persona panels.
- **Run-to-run agreement** over at least two seeds, as a stand-in for human test-retest.
- **Text, not ratings.** No numeric scores from the model; map free text with a fixed rubric.
- **Behaviour personas, not demographic ones** (patience, vagueness, role, expertise), because
  models over-weight identity 2-4x and caricature groups.
- **A list of claims never to make**, printed with the output (see the simulated-people note):
  no adoption percentages, no "represents real users", no "validated" without naming the proxy
  task, no ranking as a verdict.

None of the thresholds in the notes come from a human validation of simulated teammates. They are
proposals tied to the nearest published figure, to be set from a baseline run and frozen in an ADR.
Order stays as ADR 0003 says: scored tests first, feedback later.

## What to build: the shape the literature points to

This is the design input for the first milestone after G1. Each item names the note it comes from.

1. **Preset format** (scenario-testing, chat-realism, team-dynamics). A versioned file in ODD
   order (the standard way to document agent-based models): purpose, realism targets, members,
   channels, timeline, named parameter ranges, seed, transforms, planted facts, checks, validity
   statement, and a model block only when a model plays teammates. A run is (preset version,
   parameters, seed). Presets list team phenomena with parameters: hidden-profile decisions,
   reversals, silent members, handoffs, bot noise, channels a question spans.
2. **Planted-fact ledger with oracle tiers** (scenario-testing, product-checks). Every expected
   value lives in the preset, never derived from the product's output. Each check is tagged:
   exact, then metamorphic (rename handles, reorder, split, paraphrase), then a labelled and
   validated judge for free text only.
3. **Scripted team engine with a friction layer** (chat-realism, team-dynamics, personas). Timing
   from a time-of-week profile plus burst gaps; unanswered questions; implicit replies;
   interleaving; short turns; per-channel-type rates. The script owns stances and changes them by
   rule.
4. **New check categories** (product-checks, team-dynamics):
   - abstention when asked about something never planted, with the reason;
   - a wrong-premise question;
   - knowledge update, penalising the superseded decision when it is presented as current;
   - multi-hop questions across channels;
   - hidden profile: a key fact said once, by one person;
   - a confident wrong claim, including pasted AI text repeated several times;
   - cross-user poisoning: one teammate's message sets a rule that later steers the product for
     someone else (82-98% success in one study, against 1-2% for standard injection);
   - leakage as audience size grows;
   - bot noise, counted as messages per hour.
5. **Four verdicts and controls** (evaluation-methods, scenario-testing). PASS, FAIL, NOT
   EVALUATED, FLAKY. Every "must not happen" check has a positive control and a benign twin.
   Injection checks verify that the payload was delivered and score on observable actions or exact
   strings, never on wording.
6. **Tests of the checker** (evaluation-methods, scenario-testing). Control bots in CI: a
   do-nothing bot must fail every check, an oracle bot must pass, a cheating bot must not reach
   the answer key. A reference product plus a library of deliberately broken versions, with the
   share of breaks each check catches reported (no pass mark yet; the literature has none for chat
   checks).
7. **Reports** (evaluation-methods). Every rate with its count and a Wilson interval; pass^k next
   to the mean when a model is in the loop (at least 5 repeats); paired comparisons between product
   versions; a run record (versions, seeds, failures, skipped checks, replay file); a "what this
   does not show" block; labels "simulated, not human" and "planted facts are fictional".
8. **Realism validation** (chat-realism). A targets file per preset; all hard targets must pass
   together (pattern-oriented validation); behaviour frequencies per 100 messages, counted exactly
   because the script knows what it planted; one real source held out.
9. **A privacy-safe pattern extractor** (chat-realism). If patterns are ever learned from a real
   team: consent from every member, run locally, keep only coarsened aggregates (bins of at least
   5, no cell from fewer than 5 people), never text, names, IDs, hashes, per-person profiles or
   per-message timestamps. LLMs re-identified pseudonymous accounts at 45% recall and 99%
   precision in one study, so text anonymisation is not enough.

Most of items 1-8 exist in some form in the prototype. The audit in run 1 lists what to keep and
change; this list says what the literature adds.

## Where the notes disagree, with each other or with run 1

- **"Hide rates backed by fewer than 10 events"** (run 1, repeated in two notes) versus **"always
  show the count and a Wilson interval"** (evaluation-methods). The interval already shows the
  problem at small counts and hides nothing. Recommendation: show, never without count and interval.
- **Judge-free core** (run 1) versus **validated judges allowed for free text** (product-checks,
  evaluation-methods). Both hold: the core stays judge-free; a judge enters only as the labelled
  third tier, with at least 30 human-labelled items per question type (LongMemEval's protocol), or
  about 200 if the rate is to be corrected with a confidence interval.
- **The 90% stance-retention bar** used in run 1 has no published source. Keep it as a stated
  choice or replace it after a baseline run.
- **Small local models** (run 1) are the most sycophantic and the leakiest class (decision 2).
- **Realism details in the prototype** with no published support or that conflict with it: the
  fragment rate (15% planned, 40% shipped, no published rate), the hour-of-day profile (from one
  team, opposite to Gitter's quiet hours), off-topic share (about 19% against 11% in Gitter
  developer rooms). These come from one real team; they are not wrong, but they are one sample.
- **"Realism patterns generalise to tasks and repos"** (run 1): no evidence found either way.
- **A truthfulness guard as an anti-sycophancy fix** (run 1) is only a suggestion in its source;
  a plain instruction was weak, and third-person framing worked better.

## What the literature does not answer (teamsim could measure these itself)

- How a scripted team compares with an LLM-driven team as a test fixture. No study has done it.
- Base rates for decision reversal in real teams.
- Catch-up quality for absent members; relative due dates across time zones; handle-versus-name
  resolution. No benchmark exists.
- What share of deliberately broken products chat checks should catch.
- Any public human dataset of how teams react to a software product. Without it, product-level
  feedback cannot be calibrated, only the persona engine on proxy tasks.
- Realism numbers for task trackers and repositories in small teams.

## Decisions for the maintainer

1. **G1, stack.** Unchanged by this pass: the literature is neutral. Recommendation stays Python
   core with uv (R05).
2. **Reword ADR 0003** from "a local model by default" to "no model by default; a model as a
   measured option". Strongly supported; needs your OK because the ADR is accepted.
3. **Add the restricted feedback gate to ADR 0003** (or a follow-up ADR): defect recall,
   bad-product control, positivity rate, diversity ratio, no-model baseline, run-to-run agreement,
   and a "never claim" list. Feedback stays after scored tests.
4. **Model size rule:** 7-8B or larger for any model-written teammate who must push back, gated by
   teamsim's own pushback test.
5. **v0.1:** chat only, with the new check categories above; tasks and issues next.
6. **Reporting rule:** replace "hide under 10" with "always count plus Wilson interval".
