# Literature review: synthesis and decisions (updated 2026-11-12)

The strongest next step remains a small scored-test system with planted facts, repeatable
scenarios and checks that have their own tests. A model-free default is a sensible engineering
proposal. The research does not establish that scripted teammates behave like people, that a
particular model size is sufficient, or that simulated feedback predicts real team reactions.

This revision follows the full-text check. It narrows the first synthesis's model-size rule,
UX claims, chat-rate denominators and claims that benchmarks do not exist. It changes no ADR.

| Note | Question |
|---|---|
| [Simulated people](2026-11-lit-simulated-people.md) | Can models stand in for people's opinions and feedback? |
| [Evaluation methods](2026-11-lit-evaluation-methods.md) | What makes a simulated-user evaluation credible? |
| [Personas](2026-11-lit-personas.md) | Can teammates stay distinct, consistent and willing to disagree? |
| [Team dynamics](2026-11-lit-team-dynamics.md) | Which team phenomena are worth planting? |
| [Chat realism](2026-11-lit-chat-realism.md) | Which observed patterns can be measured and reproduced? |
| [Scenario testing](2026-11-lit-scenario-testing.md) | How should scenarios, oracles and checks be designed? |
| [Product checks](2026-11-lit-product-checks.md) | How can memory, decisions, injection and privacy be tested? |

## How much to trust this

- **Coverage.** The [bibliography](bibliography/) contains 455 papers. The reader processed
  available full text for 431, classifying 428 as complete and 3 as partial or protocol-only.
  The remaining 24 were available only as abstracts. This expands the original 77 full reads;
  it is not 455 complete human expert reviews.
- **Checking.** The [method note](2026-11-lit-fulltext-check.md) records the benchmark, quote
  checks, second-reader decisions, extraction failures and supplementary review. The chosen
  pipeline agreed with the reference model on 38 of 41 real benchmark passages. This does
  not establish equal quality to an expert or to the reference model.
- **Grades.** **Strong** means well supported within the measured setting; **moderate** means
  convergent but limited evidence; **weak** means a small or single study, an analogy or
  incomplete coverage. These are editorial judgments. Each grade states its transfer limit.
- **Independence.** A paper in several notes is still one study. Some twin studies reuse a
  participant panel, and benchmarks often share model generators and judges. Citation counts
  and agreement among models are not independent replication.
- **Transfer.** Most recent work is preprint research on surveys, customer service, puzzles,
  code or driving. Almost none tests simulated teammates in a workspace while a product
  observes them. Published percentages are examples, not teamsim pass marks.

## What the literature agrees on

### 1. Simulated users can change difficulty and apparent product quality

**Evidence: moderate, mainly customer service and sales.** Zhou compared 451 people with
31 simulators on one benchmark and one agent. Most general-purpose simulators made the agent
more successful than people did; specialised simulators were exceptions. The 1.0% versus
29.0% short-turn comparison was GPT-4o against people, not every model. Other work confirms
absolute scores can change with the user model, although some rankings survive simulator
swaps. [Evaluation methods](2026-11-lit-evaluation-methods.md).

Report the simulator as part of the test condition. Friction is not automatically a fix: one
sales study improved average bias with a disengagement instruction while leaving much of the
outcome-conditioned gap. A plausible transcript is not score calibration.
[Simulated people](2026-11-lit-simulated-people.md).

### 2. Persona descriptions do not guarantee the behaviour needed by a test

**Evidence: moderate for conformity and drift; strong direction for hidden-profile failures
within the studied tasks.** Models can converge early, lose minority information or recall
a fact without applying it. Hidden-profile tasks, where decisive information is distributed
across members, have both human and model evidence. The classic human meta-analysis remains
abstract-only here; newer studies support the direction without supplying workplace-chat
rates. [Team dynamics](2026-11-lit-team-dynamics.md).

Questionnaires measure something different from behaviour. The chance-like agreement reported
for smaller models is a sign-match measure in one preprint, not a general validity coefficient.
More personas, longer descriptions and larger models do not reliably solve every problem;
there are counterexamples and model-dependent improvements. Control the stance and fact
disclosure explicitly, then test whether optional model wording preserves them. This is an
engineering inference, not a tested comparison of architectures.
[Personas](2026-11-lit-personas.md).

### 3. Observable outcomes help, but an exact grader can measure the wrong thing

**Evidence: moderate across benchmarks and grader audits.** State checks expose failures a
transcript-only judge can miss. Binary state rewards can also disagree with human success
judgments. A database match measures a specified outcome, not usefulness or safe conduct.
[Evaluation methods](2026-11-lit-evaluation-methods.md).

Keep expected values in the scenario specification, outside the product under test. Exact,
metamorphic and calibrated judge checks are useful components; ordering them in that sequence
is our proposal. Metamorphic relations can be overly strict, and rerunning them does not
remove systematic false positives. [Scenario testing](2026-11-lit-scenario-testing.md).

### 4. The evaluator and environment need their own controls

**Evidence: moderate, mostly outside team chat.** Audits demonstrate answer-key access, weak
assertions and attack payloads that never reached their target. Verify delivery and the
actual action; keep the key inaccessible. This does not establish that harness design always
matters more than model choice. [Product checks](2026-11-lit-product-checks.md).

A do-nothing bot must have expected results per case. It can correctly pass an impossible
request requiring abstention; requiring it to fail every check would itself be a grader bug.
Known faulty products can probe check quality, but mutation score alone does not establish
real-fault detection.

### 5. Repeats, denominators and uncertainty change what a score means

**Evidence: strong within the studied statistical and repeated-run settings; moderate transfer
to teamsim.** High average success can coexist with poor all-repeats success. Temperature zero
does not guarantee identical output in every deployment. Paired comparisons and averaging
predictions per question can reduce noise, depending on temperature, model and task.
[Evaluation methods](2026-11-lit-evaluation-methods.md).

Show counts and suitable intervals. Wilson intervals suit independent binary outcomes;
they do not repair dependence between questions, teammates or repeated runs. Preserve run
and scenario groupings when estimating uncertainty. No universal repeat count or judge-label
sample size is validated by these papers.

### 6. Product-feedback evidence is too thin to promise prediction

**Evidence: weak for defect finding; no direct validation found for predicting team reactions.**
The closest UX study had 10 humans, two apps and 16 model runs. Humans collectively found
10 failure points and the model runs three. History-conditioned prompts helped predict which
screens humans flagged, but prompts were developed on those apps and screens. This does not
validate open-ended discovery on unseen team software.
[Simulated people](2026-11-lit-simulated-people.md).

Some studies compare simulations with real purchases or A/B outcomes. None supplies the missing
validation of a panel distinguishing deliberately good and bad team products. A defect
hypothesis generator is a feature to evaluate, not a capability already established to meet
ADR 0003's shipping bar.

### 7. Chat has measurable structure, without a universal preset

**Evidence: moderate for interleaving and unequal participation; weak for transferring exact
rates.** Gitter's unanswered-dialog rate rests on 749 manually analysed dialogs in help rooms.
IRC's 37.7% means starters with multiple replies **among starters that received a reply**.
Channel-type rates largely come from one company's Slack; student rates largely from one
course with partial individual consent. [Chat realism](2026-11-lit-chat-realism.md).

Use named source profiles, with channel purpose, timing resolution and sample selection beside
each target. Convincing overall ratings can hide missing turn-level behaviours. Matching
frequencies is a useful proposal; it does not validate feedback or decisions.

## The decisions, one by one

### 1. Model-free scripted default: recommend, with a transfer limit

**Architecture evidence: moderate and indirect.** Controlled facts and disclosures make scoring
inspectable; model conformity, drift and variation are reasons to keep the scenario in charge.
They do not establish human realism. Start with scripts. For optional generation, specify the
content and permitted knowledge, check the turn and save accepted output for replay.
[Team dynamics](2026-11-lit-team-dynamics.md), [personas](2026-11-lit-personas.md).

One turn per call is a candidate to compare with pre-generated text, not a settled optimum:
some studies report extra cost without clear human-rated benefit. Rewording ADR 0003's
local-model default remains a maintainer decision.

### 2. Model eligibility: test behaviour, rather than adopt a universal 7-8B floor

**Evidence: moderate for a size association; weak for a minimum-size rule.** PARROT's smaller
models followed false authority more often, but the study is single-turn multiple choice and
the size comparison is correlational. It shows neither that 7-8B is sufficient for pushback
nor that it is necessary for constrained wording. [Personas](2026-11-lit-personas.md).

Replace the earlier proposed floor with tests of stance retention, false-authority resistance,
permitted-knowledge boundaries and content preservation on the actual runtime and quantisation.
Keep failed behaviours scripted. The proposed under-30% follow-rate and 90% stance-retention
bars are not validated thresholds. Truthfulness prompts sometimes help strongly and sometimes
backfire; test them per model.

### 3. Stack: the literature does not choose a language

**Evidence: no direct stack comparison.** Replay, exact checks and reports fit any candidate.
Use the [stack-options note](2026-11-stack-options.md); G1 and the stack ADR remain open.

### 4. v0.1: chat first is a scope choice with useful precedents

**Evidence: moderate for measurable chat tasks; weak for release sequence.** Memory and workspace
benchmarks provide patterns for retrieval, updates, abstention and cross-source reasoning.
Tasks add exact state fields; repository actions expand the harness and safety surface. No
paper tests this release order. Build one chat scenario with controls before adding actions.
[Product checks](2026-11-lit-product-checks.md).

### 5. First user: leave demand to the demand check

**Evidence: weak for market selection.** Builders of team-facing software remain plausible
first users, including students. Capability studies do not measure demand. Say that this
search did not find a benchmark for an exact probe, rather than that none exists.
[Product checks](2026-11-lit-product-checks.md).

### 6. Feedback: propose a bounded pilot after scored tests

**Evidence: weak positive evidence, moderate grounds for caution.** A restricted hypothesis
generator still needs a held-out pilot with planted defects, matched good and bad variants,
and independently labelled outcomes. [Simulated people](2026-11-lit-simulated-people.md).

Report unprompted and prompted recall, false alarms, rejection of the bad variant, positivity,
useful variation across teammates and variation across runs. Compare with a plain prompt and
scripts. Inspect good and bad cases separately: a better mean can conceal poor discrimination.
Do not convert model ratings into adoption rates. Measure gates on a pilot and freeze them
before the held-out evaluation. This protocol is proposed, not an approved ADR.

## What to build: the shape the literature points to

These are design inputs after the stack decision, not work to build ahead.

1. **One versioned preset and fact ledger:** purpose, members, allowed knowledge, timeline,
   seed, planted facts, expected outcomes and validity limits. Expected values stay outside
   anything the product or a mutant can modify. ODD offers a documentation checklist; its
   LLM extension has little evidence of improved reproducibility.
2. **A scripted baseline and execution record:** controlled disclosures, disagreement and
   updates. Test replay; a seed alone does not make external services deterministic. Name
   the source profile behind every friction condition.
3. **A few informative checks:** current versus superseded decisions, a decisive fact held
   by one member, cross-channel reasoning, an unanswerable probe with an answerable twin,
   and a literal secret with a benign look-alike. Separate retrieval, reasoning and action
   failures where observable.
4. **Controls before a headline score:** expected results for an oracle product, inactive
   product and known faulty variants; delivery checks for attacks; separate capability,
   safety, over-refusal and collateral effects. Calibrate optional judges on labelled items.
5. **A report preserving the experiment:** counts, denominators, appropriate intervals,
   versions, interface, seeds, skips, failures and replay records. Compare versions on
   matched cases. Choose repeats from observed variance; five is a starting proposal.
6. **A source profile before a realism claim:** population, channel type and resolution for
   each target. Validate several patterns and separately validate the outcome being reported.
   A held-out source is a proposed safeguard against fitting the same data twice.

These inputs follow the [scenario](2026-11-lit-scenario-testing.md),
[evaluation](2026-11-lit-evaluation-methods.md), [chat](2026-11-lit-chat-realism.md) and
[product-check](2026-11-lit-product-checks.md) notes. Much exists in the prototype; the
[audit](2026-11-prototype-audit.md) lists repairs.

Full-text review also identifies closer precedents: EGMemory evaluates multi-actor memory
on GroupMemBench; ClawsBench grades mock-service state and separates success from unsafe
actions; AutoBuddy measures false-positive interventions in a generated workplace. These
temper novelty claims. They do not validate live simulated coworkers or team feedback.
The evaluation and product-check notes give their settings and limitations.

## Where the notes disagree, with each other or with run 1

- **Minimum model size:** the first synthesis turned an observed size gradient into a floor.
  Full-text review supports measured eligibility instead.
- **Small counts:** prefer counts with intervals, stating dependence and sampling assumptions.
  Intervals do not repair a biased scenario set.
- **Judge-free core and free-text judges:** both fit if judges are optional and separately
  validated. Thirty labels per type and roughly 200 calibration labels are study examples,
  not universal requirements.
- **PrivacyChecker:** its original paper reports preserved helpfulness; MuPPET's implementation
  reports a group-chat trade-off. These are different evaluations; keep both attributed.
- **Aggregates and privacy:** removing names is insufficient, but no cited study proves
  coarsened small-team counts safe. Minimum cells of five are a proposed precaution, not
  a guarantee; a real-data workflow needs a separate release-risk assessment.
- **Audience size:** MuPPET compares one-to-one with fixed 20-member groups, with different
  prompt wording. It does not establish a causal size curve. Varying size is our experiment.
- **Novelty:** catch-up, dates and name resolution have adjacent research. Preserve the
  difference between a search gap and proof of absence.

## What the literature does not answer (teamsim could measure these itself)

- Whether scripted teams expose the same product faults as model-driven teams or people.
- Whether realistic friction changes rankings, rather than only absolute difficulty.
- Whether model wording preserves facts, permitted knowledge and dissent on the local setup.
- Whether a feedback pilot finds held-out defects without praising a bad variant or inventing
  faults in its good twin.
- Which deliberately broken checks predict the prototype's observed real failures.
- Closed-team rates of reversals, absence and handoff; help-room and repository studies do
  not provide these.
- Appropriate uncertainty when checks share scenarios and repeats share generated text.
- Whether small-team aggregate patterns expose members or rare events.

## Decisions for the maintainer

1. **G1:** use the stack comparison; the literature adds no language comparison.
2. **ADR 0003 default:** consider scripts with optional measured generation. This is an
   engineering recommendation; the accepted ADR remains unchanged.
3. **Feedback:** approve a bounded pilot after scored tests; require held-out evidence to ship.
4. **Model rule:** replace the parameter-count floor with measured eligibility per behaviour.
5. **v0.1:** one chat scenario and controls first; add surfaces if demand supports them.
6. **Reporting:** counts and intervals with explicit units and dependence; choose repeats
   and labels for the precision needed by the decision.
