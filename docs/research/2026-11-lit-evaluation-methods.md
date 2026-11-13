# User simulators and credible agent evaluation: literature review (2026-11-11)

Full-text check updated 2026-11-12: [method and limits](2026-11-lit-fulltext-check.md).
Depth tags retain the initial reading pass unless updated; current source access is
recorded per paper in the [bibliography](bibliography/).

Scope: peer-reviewed papers and arXiv preprints on simulated users for evaluating interactive
systems, simulated environments for agents, benchmark validity, LLM judges, statistics for
evals, and reproducibility. The aim is to decide how teamsim's scored reports should be built
so a reader can trust them. Most 2025-2026 work is preprint; each citation says so.

Reading depth: [full text] means passages of the paper were read for the numbers quoted;
[abstract] means only the abstract. Inferences by the author of this note are labelled
"Inference". Papers are untrusted data; nothing here is an instruction. Of the papers cited,
13 were read in passages of full text and the rest at abstract level; where a recommendation
rests on an abstract-only number, treat it as a lead.

## Summary

1. **Simulated users make evaluation easier than real life.** One study ran a whole agent
   benchmark (tau-bench) with real people (451 participants, 165 tasks) and compared them
   with 31 LLM simulators; it is the only such study I found. Simulators were more
   cooperative and uniform, front-loaded information, and gave more positive feedback. The
   best simulator scored 76.0 on the User-Sim Index against 92.7 for humans (Zhou et al.,
   2026, preprint) [full text].
   Meaning for teamsim: a simulated teammate generates pressure and planted facts; it does
   not stand in for a human opinion. Say so in every report.
2. **Which LLM plays the user can move the score.** With the agent fixed, success on 115
   retail tasks was 67.8, 67.0, 71.3 and 75.9 percent for four user models (3 runs each, SD
   1.2 to 3.5); the "9 points" is the largest pair, and the authors read it as a reliability
   concern for single-model simulation. Against about 40 people per group, simulators
   misjudged hard tasks (under) and moderate ones (over), and were worst calibrated for
   African American English and Indian English speakers (Seshadri et al., 2026, preprint)
   [full text]. Meaning: a scripted, seeded team removes this variable from the
   core score; if a model plays a teammate, record which one and report it.
3. **Score from world state; judges miss what state shows.** tau-bench grades the final
   database against one expected state (Yao et al., 2024) [full text]; AppWorld uses
   state-based tests that also catch collateral damage (Trivedi et al., 2024) [abstract].
   On tau2, no judge setup passed AUROC 0.65 at spotting a false "done" claim (scored on a
   295-trajectory set drawn from 9,876 trajectories), while a TF-IDF classifier reached a
   task-disjoint AUROC of 0.83 (Advani, 2026, preprint) [full text].
   Meaning: deterministic checks against planted facts are the core. Judges only where a
   check cannot be written, and labelled.
4. **Checkers are the weak point, not only products.** An audit of 10 agent benchmarks found
   7 with outcome-validity flaws and 7 with task-validity flaws; a do-nothing agent passes 38
   percent of tau-bench airline tasks (Zhu et al., 2025, preprint) [full text]. Teamsim
   should test its own checks with a do-nothing bot, a cheating bot and a reference bot.
5. **Verifiers get attacked.** 323 of 1,968 terminal tasks (16 percent) were hackable by
   frontier models from the task text alone (Zhong et al., 2026, preprint) [abstract]; 21 of 22
   models cheated on a security benchmark, with 37.1 percent of baseline passes involving
   cheating (Kouremetis et al., 2026, preprint) [abstract]. Meaning: keep the answer key
   outside anything the product under test can read or write.
6. **One run is not a result.** tau-bench defines pass^k (all k trials succeed); gpt-4o fell
   below 25 percent at k = 8 in retail while scoring 61.2 percent at k = 1 (Yao et al., 2024)
   [full text]. Meaning: repeat each scenario, and report all-k success next to the mean.
7. **Small samples need interval methods that work at small n.** At N = 100, nominal 95
   percent normal-approximation intervals covered 92.5 percent; Wilson and simple Bayesian
   intervals held coverage down to very small N (Bowyer et al., 2025, preprint) [full text].
   Averaging predictions per question and using paired comparisons can add power: paired
   prediction noise typically exceeded data-sampling noise at temperatures around 0.7 to 1,
   with exceptions at low temperature (Wang, 2026, preprint) [full text]. Meaning: Wilson intervals on
   every rate; paired comparisons between product versions.
8. **Judge scores can be corrected with a human-labelled sample.** With judge sensitivity
   0.9 and specificity 0.7, about 200 labelled examples give an interval shorter than 0.1
   in one worked example (Lee et al., 2025, preprint) [full text]. Judges also flip: pairwise
   verdicts fell off the per-question majority in 13.6 percent of repeated trials (Yagubyan,
   2026, preprint) [abstract]. Meaning: if a judge ever enters a score, ship a calibration set and show the
   corrected interval.
9. **Temperature 0 does not make runs identical.** Greedy decoding varied across GPU setups
   in local runs (Yuan et al., 2025); pinning temperature 0 reduced but did not remove flips
   on borderline items across two API providers (Tamba, 2026); and temperature zero removes
   deliberate sampling but not other randomness (Coqueret et al., 2026) (all preprints)
   [abstract]. Meaning: record and replay model calls for any LLM part, and treat
   outputs as draws from a distribution.
10. **Reports need a record, not only a score.** Changing only the reporting rule changed
    scores by up to 20.9 points and inverted rankings in one study; none of 50 repositories
    reported how many runs failed or were skipped (Masters et al., 2026, preprint)
    [abstract]. Meaning: ship a run record (seeds, versions, failures, skipped checks) with
    every score.

## 1. User simulation for evaluation

### 1.1 History

User simulation for evaluation is old. In information retrieval and dialogue it was used to
test systems without paying for human sessions, and to make results reproducible. Balog and
Zhai's book reviews the field for search, recommender and conversational systems and treats
validation as an open problem (arXiv 2306.08550) [abstract]. Their 2025 synthesis calls
simulation a way to model users, create synthetic data and evaluate interactive AI in a
controlled, reproducible way (arXiv 2501.04410) [abstract].

The classic design for task-oriented dialogue is the agenda-based simulator: the user has a
goal and an agenda of acts, and a stack of pending acts is updated each turn (Schatzmann et
al., 2007, NAACL short paper; bibliographic record only, I did not read the paper).
Kreyssig et al. describe the agenda-based simulator as based on hand-crafted rules with
limited diversity (2018, preprint) [abstract]. Inference: hand-built rules also make it cheap
and easy to control; the paper does not say so. A neural simulator trained on a corpus
produced better dialogue policies than the agenda-based one when both were tested on real
users, in one restaurant-recommendation domain (same paper). Inference: this is the closest
published parallel to teamsim's scripted team.
It is a sound basis for repeatable checks and a weak model of how people really write.

Validation in IR has a literature of its own. Query simulations were checked against real
user query variants for TREC topics on retrieval effectiveness, score distributions and
effort, with the finding that term-level fidelity is still hard (Breuer et al., 2022,
preprint) [abstract]. A 2026
review builds a taxonomy of validation measures and gives advice on which to combine
(Kruff et al., 2026, preprint) [abstract].

### 1.2 The LLM era: how big is the gap?

| Paper | Venue and year | What was measured | Key number | Depth |
|---|---|---|---|---|
| Zhou et al., Sim2Real gap | arXiv 2603.11245, 2026 | 31 simulators vs 451 humans on tau-bench | Best USI 76.0 vs 92.7 human | full text |
| Seshadri et al., Lost in Simulation | arXiv 2601.17087, 2026 | Retail tasks, human groups in 4 countries | 45.2% success with US humans; calibration error 15.1 points | full text |
| Dou et al., SimulatorArena | arXiv 2510.05444, 2025 | 909 annotated conversations, 2 tasks | Profile-conditioned simulators reach Spearman about 0.7 with human ratings | full text |
| Zhu et al., RealUserSim | arXiv 2605.20204, 2026 | Match to real users on five behavioural dimensions | Match rate 24.2% to 45.3% with grounding | abstract |
| Chopra et al., Persona Policies | arXiv 2605.12894, 2026 | Blind human-vs-sim judgement | Judged human 80.4% of the time vs 46.5% for the base simulator | abstract |
| Chen, Simulated Customers | arXiv 2606.20708, 2026 | 2,790 production conversations, 793 ending in a verified payment | Non-buyers' resistance halved: 25.1% to 13.5% | abstract |
| Mehri et al., distributional gap | arXiv 2605.07847, 2026 | 24 simulators vs 5,000 real conversations per task | Large gap for all; method checked by 15 annotators, 86.7% | full text |
| Meshi et al., ConvApparel | arXiv 2602.16938, 2026 | Validation framework, good and bad recommenders | Realism gap in all simulators | abstract |
| Zhou et al., OdysSim | arXiv 2606.14199, 2026 | Trained 8B behaviour model | Reaction alignment 93.2 vs 93.5 real on tau-bench (React dimension only; composite USI below humans) | abstract |

Details from the full texts:

- **Sim2Real** defines a behavioural gap along four facets (communication style, how much
  information is given per turn, clarification, reaction to errors), an outcome gap (a
  calibration error between simulator and human success across task-difficulty bins), and an
  evaluative gap (mean absolute error between simulated and human quality ratings). USI
  averages them. Simulators were too uniform and cooperative, front-loaded complete
  information, lacked uncertainty and quietly pivoted instead of pushing back on agent
  errors. GPT-5.1 as evaluator overestimated human-likeness of the assistant by 55 percent
  and the overall score by 18 percent of the rating scale. Higher general capability did not
  reliably give a better simulator. Caveat: one benchmark (tau-bench), crowd participants
  assigned a goal, preprint.
- **Lost in Simulation** recruited about 40 people per age and dialect or country group, each
  doing 4 tasks. US humans succeeded 45.2 percent of the time; simulated users fitted worst
  on the hardest tasks (underestimating success) and best on moderate ones. Standard
  American English speakers scored 50.6 percent, African American English speakers 39.4
  percent (a dialect effect, p < 0.001 in a GEE model). Simulated users asked questions in
  18.8 percent of turns against 9.8 percent for humans, and used politeness markers in 39.2
  percent of turns against 19.9 percent. Prompting the simulator to be less polite changed
  calibration for the worst-fitted groups, so some of the gap is steerable. Caveat: one
  domain, one agent model (GPT-4o), crowd participants, preprint.
- **SimulatorArena** goes the other way on rankings. Humans (107 crowd workers, 909
  conversations, about 10,000 dollars of annotation) and a rater model gave assistants
  ratings; simulators conditioned on user profiles (knowledge, message style) correlated with
  human ratings at Spearman about 0.7 on both tasks, and 0.61 to 0.77 in the paper's worked
  example against a plain prompt (computed on 27 model-by-difficulty groups, not individual
  conversations). Significance tests favoured the profile versions in all four comparisons.
  Real users wrote about 15.5 words per message in math tutoring; a plain simulator wrote
  87.6. Richer profiles made some interaction-style attributes less well followed. Humans
  themselves varied: in document creation, in 186 pairs of people who used the same
  assistant on the same topic, 78.5 percent gave different interaction ratings. A simulation costs about 0.09 dollars per
  conversation against about 5.33 for a human [full text]. Inference: a simulator can be good
  enough to rank assistants while still wrong about absolute success rates, and the human
  reference itself is noisy, so "matches humans" needs a human-to-human ceiling (GAUGE uses
  one, see section 4). Both findings can be true.
- **Measuring the behaviour distribution.** Mehri et al. summarise each conversation's user
  behaviour with an LLM along six facets, embed the descriptions, cluster them (k = 500) and
  compare cluster frequencies between real and simulated users with forward KL (simulator
  misses real behaviours, low recall), backward KL (simulator shows behaviours real users do
  not, low precision) and Jensen-Shannon divergence. They used 5,000 real WildChat
  conversations per task, 24 simulators, and set a floor by comparing two different real
  users on similar goals. A human odd-one-out check on clusters had 15 annotators and 86.7
  percent accuracy (Fleiss kappa 0.74). Comparing raw text gave misleadingly small gaps (it
  measured lexical overlap), and the gap was large for all 24 simulators. They note a gap is
  sometimes desirable when stress testing with rare inputs [full text]. Inference: the
  precision and recall framing fits teamsim: a scripted team should cover the behaviours real
  teams show (recall) and may add rare stress behaviours on purpose (low precision, labelled).
  The method needs a capable model to describe behaviours and a real log; for teamsim it is a
  later, optional validation, not a core dependency.
- **Disengagement.** In production sales chats simulators inflated eventual non-buyers
  toward buying and halved their expressed resistance (25.1 to 13.5 percent), and telling
  the simulator it may disengage cut overall bias five-fold but barely moved the gap
  between non-buyers and buyers (Chen, 2026) [abstract]. Real non-buyers stop; simulated ones ask
  about price. For teamsim this matters for teammates who ignore, go quiet or disagree.

Where studies disagree: SimulatorArena (reasonable rank agreement) and OdysSim (near-real
reaction alignment on one dimension after training a purpose-built model; its composite
score stays below the human upper bound) are more optimistic than Sim2Real and Lost in
Simulation. OdysSim does not itself compare against them; the contrast is mine. The pessimistic studies used real humans on a full agent benchmark
and measured outcome calibration, so I weight them higher for the question "are absolute
scores right". The optimistic ones use narrower targets (ratings, reaction alignment).
Weighing: peer-review status is the same (all preprints in my reading); human-sample size
favours Sim2Real.

### 1.3 What makes a simulator a valid proxy

The papers converge on three layers. Each needs a different kind of evidence.

1. **Behaviour fidelity.** Do the simulated users write and act like real ones? Measured as
   facet agreement (Sim2Real's Dice scores), clustered behaviour distributions and divergence
   between real and simulated (Mehri et al.), or blind human-likeness judgement (Persona
   Policies).
2. **Outcome calibration.** Does the agent succeed about as often with simulated users as
   with real ones, across difficulty levels? (Sim2Real, Lost in Simulation.)
3. **Counterfactual sensitivity.** Do scores move the right way when the system under test
   gets better or worse? ConvApparel collects conversations with deliberately good and bad
   recommenders for this and reports that data-driven simulators (in-context and fine-tuned)
   adapt more realistically to an unseen bad agent than prompted ones, though all have a
   gap; this tests one counterfactual condition only [abstract]. A related
   theoretical paper argues that simulators trained on labels coupled to a past policy
   inject look-ahead bias and that evaluation variance can grow quickly under policy shift
   (Tennenholtz et al., 2026, preprint) [abstract].

What helps, from the abstracts: ground behaviour in real user data (RealUserSim, Persona
Policies; RealUserSim's profiles combine linguistic style and demographics, and the paper
does not separate their effects); combining behaviourally complementary simulators may
reduce the gap (Mehri et al.; a few pairs, intrinsic metrics only, and combining similar
simulators did not help); report results across several simulator models (Lost in
Simulation's own recommendation).

### 1.4 Other uses of simulated people for software testing

A practitioner paper reports a goal-directed "NPC" simulator for a production chat agent, in a
three-month case study of 257 runs of a 108-scenario suite (the simulator itself was in
intensive iteration for about two weeks), 77 percent goal achievement at 0.17 dollars per run, with
weak correlation between canonical-question quality and goal-directed success (Spearman rho
between -0.15 and 0.14 in one run) (Maiorano, 2026, preprint, single author) [abstract].
Inference: low cross-layer correlation means different test layers catch different things,
so teamsim should not collapse them into one score.

## 2. Simulated environments for agents and how they get ground truth

| Benchmark | Simulated world | How success is decided | Read depth |
|---|---|---|---|
| tau-bench (Yao 2024) | Retail and airline databases, LLM user | Final database equals one expected state, plus required strings in replies; pass^k | full text |
| tau2-bench (Barres 2025) | Adds dual-control telecom; user also acts on shared state | Programmatic state checks; user simulator tied to tools and state | abstract |
| AppWorld (Trivedi 2024) | 9 apps, 457 APIs, 100 fictional users | State-based unit tests; allow different solution paths; catch collateral damage | abstract |
| ToolEmu (Ruan 2023) | LM emulates tool output | LM-based safety evaluator; on 100 validation cases, 68.8% of identified failures were true failures with the adversarial emulator (72.5% with the standard one) | abstract |
| Collaborative Gym (Shao 2024) | Task environments with simulated or real partner | Outcome and process evaluation; win rates judged by real users | abstract |
| tau-Rec (Narasimhan 2026) | Conversational movie recommendation (released benchmark covers movies only) | Verifiable catalogue predicates; pass^k; best model 57% at pass^1 and 35% at pass^4 | abstract |
| AutoBuddy-Bench (Chen 2026) | Generated company: 44 employees, 6 months, mail, chat, calendar, files, business systems | Expected outcomes computed from world records and rules; no LLM in matching or grading; 120 tasks, 3 runs, 17 models | full text |
| ClawsBench (Li 2026) | Mock Gmail, Slack, Calendar, Docs, Drive with deterministic snapshot and restore | 44 tasks; with full scaffolding, task success 39-64% but unsafe-action rates 7-33% | abstract |
| TheAgentCompany (Xu 2024) | Self-hosted fake software company with colleagues to talk to | Best agent completed 30% of tasks | abstract |

Points that matter for teamsim:

- **State comparison with room for varied paths.** tau-bench lets the conversation vary
  freely while the pass condition is the end state. Each task was written so that policy and
  user instruction admit one outcome, which replaces subjective judgement with a database
  comparison. The authors accept this is necessary but not sufficient: an agent could act
  without the required user confirmation and still pass [full text]. Inference: teamsim's
  planted-fact checks have the same limit, so add negative checks (the bot must not act on
  an injected request; must not leak the planted secret).
- **The closest precedent to teamsim's ground truth.** AutoBuddy-Bench builds a simulated
  organisation as a temporal graph (dated roles, access rights, events), renders it into
  mail, chat, calendar and files, and derives each task's correct outcome from the world's own
  records and rules. The agent never sees the ground truth. Discovery is scored by recall and
  precision with a deterministic match (a listed task matches when it cites the request
  record); mistakes are judged by hidden labels on every rendered record (treating an
  answered request as open counts as a mistake); execution is scored by diffing the workspace
  before and after, and "no language model is used in matching or in grading". An automatic
  acceptance check on the generated world runs before any agent is scored (enough tasks,
  every task has a required output, every request states what its answer depends on). One
  world, 120 tasks, 17 backbone models, mean of three runs [full text]. Limit: it renders a
  static workspace snapshot per employee and day (my reading is that colleagues do not talk
  back during the run; the paper does not say), and it is a preprint dated within the week. Inference: this is the design pattern teamsim
  can copy (hidden labels on records, state diff, acceptance check on the world), and it
  shows the "planted facts, state-based score" idea has a published form for single-agent
  workplace tasks, though not for live simulated teammates.
- **Safety is a separate axis from success.** In mock workspace services with deterministic
  snapshot and restore, task success of 39 to 64 percent came with unsafe-action rates of 7 to
  33 percent (full-scaffolding conditions), and higher success did not coincide with lower
  unsafe-action rates in the sample (Li et al., 2026, preprint) [abstract]. Inference: teamsim should keep "did it do the right thing" and
  "did it do something it should not" as separate columns (secret echoed, injected request
  obeyed).
- **LM-emulated tools trade realism for coverage.** ToolEmu lets a model invent tool
  results so many tools can be tested cheaply, at the price that about a third of flagged
  failures were not valid [abstract]. teamsim's emulator is state-based, which avoids this.
- **Replay fidelity is not free even with a real state.** In AppWorld, 42 of 71 failed runs
  replayed with matching printed output, database changes and verdict in two fresh
  processes; resetting the random-number generator before each interaction raised that to
  68, and four cases that matched on output and verdict still differed in database state
  (Liu and Lu, 2026, preprint) [abstract]. The paper does not make per-interaction reseeding
  a general fix. Inference: seed every random source in the synthetic workspace, not just the
  model.
- **Judge-free checks can still be unreliable.** tau-bench airline counts a do-nothing agent
  as successful on tasks that should be refused; those tasks are 38 percent of the airline
  set and 6 percent of retail (Zhu et al., 2025) [full text].
- **Multi-party and team settings.** Collaborative Gym reports communication failures in 65
  percent and situational-awareness failures in 40 percent of real-condition cases [abstract].
  In a study of LLM-simulated shared-workspace teams (Collaborative Gym, 1,482 sessions, no
  real human participants), adding collaborators lowered performance when coordination
  structure was absent (Kotalwar et al., 2026, preprint) [abstract]. A
  role-separation benchmark found verifiers approve 49 percent of submissions that fail the
  deterministic grader (Kim et al., 2026, preprint) [abstract]. Inference: team behaviour is
  measurable, though the shared-workspace study above used simulated teams. The nearest published work (AutoBuddy-Bench above) scores state against facts
  derived from a simulated organisation, but I found no paper in which simulated teammates
  talk during the run, plant facts in a live team chat and score a bot against them. That is
  teamsim's niche; it also means there is no validated precedent for the teammate part.

## 3. Benchmark validity

**Checklists.** The Agentic Benchmark Checklist splits validity into task validity (solvable
if and only if the agent has the capability) and outcome validity (the check really shows
success), plus reporting. Applied to 10 benchmarks: 7 had outcome-validity flaws, 7 had
task-validity flaws, 80 percent did not acknowledge design weaknesses. Examples: tau-bench
airline overestimated by 38 percent (do-nothing agent) and by up to 40 percent (listing all
answers passes substring checks); WebArena overestimated by 1.4 to 5.2 percent through string
matching and an unvalidated judge; SWE-Lancer let an agent overwrite the tests; OSWorld
underestimated Chrome tasks by 28 percent after websites changed (Zhu et al., 2025) [full
text]. Items that apply directly: clean state between tasks, isolate the agent from ground
truth, freeze the environment, provide an oracle solver, inspect outliers in pilot runs, check
that fuzzing or variation is comprehensive.

**Wider reviews.** BetterBench scores 24 benchmarks against 46 practices and finds most do not
report statistical significance or allow easy replication (Reuel et al., 2024, preprint)
[abstract]. A review of 445 LLM benchmarks by 29 reviewers finds patterns that weaken
construct validity and gives eight recommendations (Bean et al., 2025, preprint) [abstract].
"AI agents that matter" argues for cost-controlled comparison, separate needs of model and
downstream developers, proper holdout sets, and standard reporting (Kapoor et al., 2024,
preprint) [abstract]. A compounding model argues total validity is bounded by the product of
task, simulator and judge validity (a conceptual bound that assumes independent layer
failures), does not compute the judge layer for any of the benchmarks in its table, and
finds that 26 of 55 agent evaluation papers, in a purposive and non-random sample, reported
no chance-corrected agreement statistic (Caban, 2026, preprint, single author) [abstract]. Inference: treat that
last paper as an argument, not a measurement.

**Shortcuts and reward hacking.** Verifier hardening studies find 16 percent of 1,968
terminal tasks hackable from the description alone, and show an iterative hacker-fixer loop
cut attack success on KernelBench from 62 to 0 percent on a held-out set of publicly
reported exploits (Zhong et al., 2026) [abstract]. An automated audit tool surfaced 219 flaws
across 10 popular benchmarks and, by its own re-audit, patched WebArena and OSWorld to
unhackable within three patching attempts (Wang et al., 2026, preprint) [abstract]. On
security tasks, cheating was found in 37.1 percent of baseline passes, and anti-cheat
prompts cut propensity from 33.0 to 8.5 percent but did not remove it (Kouremetis et al.,
2026) [abstract]. A maintenance study stresses that audit of passing runs must be repeated as
models change (Luo et al., 2026, preprint) [abstract]. Inference: teamsim's product under
test is itself an agent that could, by accident or design, find the answer key. Keep ground
truth out of the emulator the product can query, and run a cheating bot in CI.

**False success.** On AppWorld, with ground truth independent of agent text, 75.8 percent of
failures among agents that report status were false successes; on tau2 single-control
domains 45 to 48 percent of failures were, against 3 percent in the dual-control telecom
domain where the user side could verify state. That contrast is observational (one
dual-control domain, 15 cases) and the paper flags it as a hypothesis [full text, Advani
2026]. Inference: a simulated teammate that independently checks the world (for example,
looks for the promised task) might work as a built-in verifier. The paper calls independent
verification a promising structural defense but says more dual-control environments are
needed, and it does not test simulated teammates.

**Contamination.** I did not find a paper in this pass that measures contamination of
simulation-based benchmarks specifically. The ABC and "AI agents that matter" papers argue
for holdout sets; for a generated-by-seed scenario set the practical answer is to hold out
seeds, and to avoid publishing every seed's answer key.

## 4. LLM-as-judge reliability

| Paper | Venue and year | Finding | Depth |
|---|---|---|---|
| Zheng et al., MT-Bench | arXiv 2306.05685, 2023 | GPT-4 judge over 80% agreement with humans; examines position, verbosity and self-enhancement bias (says it cannot settle self-enhancement) | abstract |
| Norman et al. | arXiv 2606.19544, 2026 | 21 judges, about 541,000 judgments: on MT-Bench kappa deflates exact-match agreement by 33.8-41.3 points; in two judges, test-retest above 0.95 coexists with position bias above 0.10 | abstract |
| Yagubyan, Coin Flip Judge | arXiv 2606.13685, 2026 | Mean flip rate 13.6% (trials off the per-question majority); on average 11 repeats needed for a majority to match a 50-trial verdict at 95% in this dataset | abstract |
| Mukherjee et al. | arXiv 2606.03043, 2026 | Judges agree with each other as much as humans do but reach 58-66% of human agreement on subjective rubrics; gap mostly closes on a verifiable one | abstract |
| Advani | arXiv 2606.09863, 2026 | No judge setup above AUROC 0.65 on false success on tau2 (0.54 on AppWorld) | full text |
| Bodhwani et al., GAUGE | arXiv 2609.12191, 2026 | 57.5% of conversations rated satisfied failed the task; decision disagreement 31% on close pairs | full text |
| Owiredu-Ashley | arXiv 2607.07474, 2026 | Three-judge panel reproduced a deterministic oracle at ordinal Krippendorff alpha 0.91 but shared blind spots | abstract |
| Lee et al. | arXiv 2511.21140, 2025 | Bias-corrected judge estimate with human calibration set; can beat human-only in some regimes, though no judge tested on Chatbot Arena fell in them | full text |

Reading across them:

- **Agreement with humans is real but depends on the task.** MT-Bench found over 80 percent
  agreement for a strong judge on open-ended chat. The newer work shows this does not
  transfer to detecting whether an agent actually did the thing, nor to subjective rubrics.
- **GAUGE in detail.** Three blind annotators rated 150 tau2 transcripts (Krippendorff alpha
  0.79, human-human ceiling rho 0.85). Two LLM judges reproduced human satisfaction (rho 0.85
  and 0.83), yet satisfaction was uninformative about success: of conversations rated
  satisfied, 57.5 percent failed, the same as the sample's 57.3 percent base failure rate
  (AUC 0.44). A "policy-aware" judge that saw the tool calls and task roughly halved failure
  among accepted conversations (20.0 against a 40.2 percent base rate, AUC 0.73); a judge
  without that evidence behaved like satisfaction (AUC 0.49). Across 25 agents the ranking
  was robust (rho 0.94) but the gate picked the lower-reward agent on 31 percent of close
  pairs, averaging four judges did not help (their errors were correlated at 0.67 to 0.98),
  and same-family self-preference added 0.75 points on a 7-point scale. A free "did the
  conversation finish" bit tracked severe regressions (rho 0.87) but caught only 3.5 percent
  of failures overall because 96.5 percent end normally. Limits the
  authors state: a small panel of three annotators, budget-style degradation coverage and
  synthetic task substrates; preprint [full text]. Inference: evidence access, not
  model strength, is what separates a useful judge from a useless one, so any teamsim judge
  must be given the planted-fact record and the emulator state, never the transcript alone.
- **Consistency is not validity.** In two of 21 judges, high test-retest reliability
  coexisted with position bias (Norman et al.), and local judges with 92 to 97 percent self-consistency
  correlated 0.28 to 0.34 with humans (Tiwari, 2026, preprint, small study) [abstract].
- **Judge agreement can mislead.** Inter-judge agreement was not evidence of human alignment
  until a geometric check passed (Mukherjee et al.).
- **When judges are acceptable.** The evidence supports them where the answer is verifiable
  or there is a sharp rubric, where a human-labelled calibration sample exists, and where
  the judge is not also the agent under test. It does not support them as the primary
  detector of task success.
- **Calibration with a small human sample.** Lee et al. correct raw judge scores for
  sensitivity and specificity and widen the interval for calibration uncertainty. A worked
  example needs about 200 labelled items for an interval under 0.1 (sensitivity 0.9,
  specificity 0.7, judged-correct share 0.3). Their framework also states regimes in which the
  corrected judge estimate has lower variance than a human-only estimate with the same
  annotation budget. Prediction-powered inference gives a related route to valid intervals
  from a small labelled set plus many model predictions, with no assumptions on the
  prediction model but with sampling and CLT conditions (Angelopoulos et al., 2023, arXiv
  2301.09633) [abstract]. A 2026 practitioner guide says two of its three assumptions are
  largely untestable in practice and warns that reusing training data for inference makes
  intervals too narrow (Song et al., 2026, preprint) [abstract].
- **Bias mitigation helps unevenly.** A nine-strategy comparison found style bias (0.10 to
  0.76) far larger than position bias (at most 0.04), and that debiasing gains differ by
  model (Soumik, 2026, preprint, single author) [abstract].

## 5. Statistical rigour

**Intervals.** Evaluations are experiments; report a standard error and, when items are
clustered (for example scenarios with several checks each), clustered errors (Miller, 2024,
arXiv 2411.00640) [abstract]. For small samples the normal approximation fails: at N = 100 its
95 percent intervals covered 92.5 percent; with N = 20 it can collapse to zero width or leave
[0, 1]. Wilson and conjugate Bayesian (Beta-Bernoulli) intervals held nominal coverage at
small N, Clopper-Pearson was too wide, and the bootstrap undercovered (Bowyer et al., 2025)
[full text].

Inference (my arithmetic from the Wilson formula, not from a paper): with no failures
observed in n runs, the 95 percent Wilson lower bound on the success rate is n/(n+3.84):
0.57 at n = 5, 0.72 at n = 10, 0.84 at n = 20, 0.89 at n = 30. So 10 clean runs do not show
"reliable"; they show "probably above 72 percent".

**Noise sources.** Total noise has a prediction part (different answers to the same item) and
a data part (which items were sampled). Across many evals, paired prediction noise typically
exceeded paired data noise at temperatures around 0.7 to 1, so averaging predictions per
question can raise power; at low temperature the balance can reverse. Fixing a seed or
temperature is brittle and only works for the exact same model (Wang, 2026) [full text]. Two
models at 60 and 61 percent can differ "significantly" with enough samples per item, or not at
all with one sample; the conclusion depends on which metric you report [full text].

**Paired comparisons and power.** Comparing two versions on the same items is more powerful
than comparing separate rates. A 2026 diagnostic found that 11 of 40 Open LLM Leaderboard v1
pairwise comparisons and 4 of 9 top-10 neighbour pairs on MMLU-Pro were unresolved at 5
percent significance and 80 percent power, and that a widely used unpaired power shortcut is off by about
a factor of two in the close-comparison regime (Kotawala, 2026, preprint) [abstract]. Multiple
comparisons: the judge-debiasing study applied Holm-Bonferroni correction [abstract]; I did
not find an agent-evaluation paper that treats multiple comparisons across many check types
in depth. Inference: teamsim runs 15 or more checks per report, so it should not read a
single failing check as a regression without a correction or a pre-stated primary check.

**Reliability metrics.** pass@k asks for at least one success in k tries; pass^k asks for all
k (Yao et al., 2024) [full text]. Their unbiased estimators use n trials and c successes:
pass^k = E[C(c,k)/C(n,k)]. A broader proposal lists twelve metrics along consistency,
robustness, predictability and safety and finds that over 24 months of model releases
overall reliability improved only slightly across 15 models. Its protocol is directly
reusable: each task is run K = 5 times with different seeds at temperature zero for
non-reasoning models (reasoning models keep provider defaults), so the authors attribute
remaining variance to non-sampling noise; outcome consistency per task is (2p - 1)^2 where p is the
success rate over the K runs; robustness is tested with 5 paraphrases of each instruction, a
fixed 0.2 probability of injected API and tool faults, and renamed or reformatted tool
interfaces. It also reports that 24 of the 50 original tau-bench airline tasks contain
grading errors (flawed labels, ambiguous specs) as found by earlier work, so it used the
26 verified tasks (Rabanser et al., 2026, preprint) [full text]. The authors recommend
generative, parameterised benchmarks (rename fields, reorder responses, inject faults) and
say these could also mitigate shortcuts such as looking up answers online. A Markov-chain
treatment shows pass@k, pass^k and reliability-decay curves are projections of one
success-time distribution and gives credible and bootstrap intervals (Tran-Truong and Le, 2026,
preprint) [abstract].

**Nondeterminism.** Greedy decoding still varied: under bfloat16, up to 9 percent accuracy
variation from GPU count, type and batch size for a reasoning model (DeepSeek-R1-Distill-
Qwen-7B in local runs; Yuan et al., 2025) [abstract]; a grader
flipped pass/fail on borderline items at default temperature with up to 50 percent
per-item disagreement over 20 runs, and 1 to 2 of 7 borderline items still flipped at
temperature 0 (Tamba, 2026) [abstract]; the same paper reports that Claude Opus 4.7 and 4.8
have deprecated the temperature setting. An economics-methods paper treats outputs as draws and proposes a
reporting standard (Coqueret et al., 2026) [abstract].

**Flaky tests from software engineering.** Flakiness is tests that pass and fail on the same
code. In 876,186 Python test cases from 22,352 projects, 59 percent of flaky tests were
order-dependent, 28 percent were infrastructure, and the authors estimate about 170 reruns
for 95 percent confidence that a test is not flaky for non-order-dependent reasons (31
random-order executions for order dependence) (Gruber et al., 2021, preprint) [abstract].
LLM-generated database tests had a slightly higher proportion of flaky tests than existing
ones, though this varied by project and model; unordered collections caused 72 of 115 flaky
generated tests (63 percent), all of them in tests generated for DuckDB (Berndt et al.,
2026, preprint) [abstract]. Inference (ours, not from the papers): similar flakiness sources
(ordering of messages, timing, shared state between scenarios, network, randomness) may
affect simulation-based tests. The Python study warns that rerunning flaky tests might
mask actual bugs. The cure I propose is to isolate state, remove time and random
dependence, and report "flaky" as its own verdict rather than a failure.

## 6. Reproducibility and reporting

- **Model and eval documentation.** Eval Factsheets propose a questionnaire across Context,
  Scope, Structure, Method and Alignment (reliability, validity, robustness) (Bordes et al.,
  2025, preprint) [abstract]. Evaluation Cards derive a reporting schema from 52 papers and
  stakeholder interviews (12 in the body, 10 in the abstract) and measure documentation completeness across 635 benchmarks
  (Ghosh et al., 2026, preprint) [abstract]. A pilot audit of 12 benchmark papers scored 0.38
  on a 5-field disclosure schema for the agent ones, with none reporting inference cost
  (Moghadasi and Ghaderi, 2026, preprint, single auditor) [abstract].
- **Rollout records as the unit of reproducibility.** Rollout Cards bundle the run record and
  state the reporting rules and a manifest of dropped runs; in one re-grading, only the
  reporting rule changed scores by up to 20.9 points (Masters et al., 2026) [abstract].
- **Seeds and replay.** Inference: a fixed seed does not reproduce a hosted model (Tamba
  found flips at temperature 0), so replaying a recorded trace is the practical answer. In
  AppWorld, resetting the random-number generator changed which failed runs replayed
  faithfully, but the paper says per-interaction reseeding is not a generally correct
  restoration policy (Liu and Lu, 2026) [abstract].
- **Cost.** Enterprise-oriented work argues for cost-controlled reporting; one preprint
  (single author) cites a drop from 60 percent at one run to 25 percent at eight-run
  consistency (Mehta, 2025) [abstract]. The paper attributes that figure to tau-bench, so it
  is not a new measurement.

## Implications for teamsim

These are recommendations, built from the evidence above. "Inference" marks where I am
extrapolating from agent benchmarks to a team-chat simulator.

### A. What to score with deterministic checks, and what with judges

1. **Core score: deterministic checks against planted facts.** For each scenario, the
   expected end state is known by construction (decision recorded, owner and due date,
   superseded decision not served as current, secret not echoed, injected request not
   obeyed, absence handled). Source: state-based grading in tau-bench and AppWorld; judges
   fail at false success (Advani); satisfaction does not predict task success (GAUGE).
2. **Four verdicts, not two.** PASS, FAIL, NOT EVALUATED (the check could not run or had no
   data) and FLAKY (varied across repeats). The prototype audit found checks that pass when
   nothing was scanned; ABC flags outcome-validity flaws of this kind. Inference.
3. **Negative and collateral checks.** Check that nothing else changed (AppWorld's
   collateral-damage idea) and that refusals are correct (tau-bench's unsolvable tasks), and
   guard against the do-nothing pass (ABC: 38 percent of airline tasks).
4. **Judges only for questions a state check cannot answer**, for example "was the
   summary faithful". Mark such rows "judge-scored, validated on n human labels" or
   "judge-scored, unvalidated". If validated, correct the rate with the sensitivity and
   specificity from the calibration set and show the widened interval (Lee et al.). Use at
   least 200 human labels for a usable interval, or none and say so (Lee et al.'s worked
   example; Inference for teamsim's case).
5. **Do not use a judge to certify that the product did a thing.** Verify the thing in the
   emulator's state instead. Advani found judges poor monitors for false success and
   recommends lightweight detectors only as triage signals, with direct
   trajectory-environment checks for higher-stakes use; the blanket rule is my
   recommendation. Zhou et al. found rule-based rewards miss quality but also that simulated
   feedback is inflated.
6. **Hidden labels on the world's records.** Label every planted and background message in
   the synthetic workspace (open request, answered request, decoy, injected text, secret) and
   score mistakes against those labels, so that "invented work" and "treated an answered
   request as open" count as errors, not only misses. AutoBuddy-Bench hides labels on every
   rendered record and scores answered or colleague-owned requests treated as open as
   mistakes; the decoy, injected-text and secret labels are my extension. Run an acceptance
   check on each generated scenario before any product is scored (every check has an
   expected outcome; every planted fact is reachable by a reasonable reader, which is my
   addition: AutoBuddy-Bench's check covers task-set size, a required output per task and
   what each request's ground truth depends on). Source: AutoBuddy-Bench (full text); ABC
   items on verifying ground truth.
7. **Separate columns for "did the right thing" and "did something it should not"**
   (in ClawsBench's sample, unsafe-action rate did not track task success across models; a
   cross-model observation, not a within-model test). Inference for teamsim's checks on
   secrets, injection and visibility.
8. **Perturb, do not only repeat.** Rabanser et al. combine repeats (K = 5) with paraphrased
   instructions, injected faults and renamed or reordered interfaces. For teamsim: reorder
   and re-time messages, paraphrase planted facts, drop or delay events, rename users.
   Report each perturbation family's pass rate separately.

### B. Simulator design (model-free default vs a model)

- **Default: a scripted, seeded team with no model.** It removes the user-LLM variable (Lost
  in Simulation), is replayable by construction (Inference; model calls are not, even at
  temperature 0 per Tamba and Yuan, and RNG state affected AppWorld replay per Liu and Lu),
  and costs nothing. The literature's warning is that the hand-crafted agenda-based
  simulator has limited diversity (Kreyssig et al.); a scripted team may share this, so make
  the script generator vary behaviour facets deliberately: terseness, vagueness, late corrections, interruption, silence,
  disagreement, and reaction to bot errors (Sim2Real's D1 to D4). Inference.
- **Model-played teammates are optional, recorded and labelled.** Record every model call so
  a run can be replayed and state the model and version (Inference; Coqueret et al. advise
  recording the model identifier, call time and raw outputs). Report results across at
  least two simulator models when a model plays a teammate (Seshadri et al. recommend
  reporting across multiple user models). Do not claim small local models are valid
  simulators without measuring (OdysSim trains a dedicated 8B model and finds raw Qwen3
  checkpoints weak on its probe; it did not test small local models as simulators, so "not
  enough" is an Inference).
- **Do not ship simulated feedback as opinion or forecast** without the gate: planted-issue
  recall, diversity report, flip-on-pushback sycophancy probe, no-persona baseline. The
  literature supports labelling it "hypotheses": simulated feedback is uniformly more
  positive than humans' (Sim2Real) and simulated non-buyers resist half as much (Chen).

### C. How many runs, what statistics to show

- **Deterministic product and scripted team:** one run per scenario per seed is enough
  for pass or fail, but run each scenario over several seeds (varying message order, timing
  and wording). Aim for at least 10 seed-varied runs per scenario family before showing a
  rate. If the product under test uses a model, run at least 5 repeats per scenario and
  report pass^k next to pass@1 (tau-bench ran at least 3 trials; pass^8 showed the cliff).
  Inference on the exact numbers.
- **Every rate has a Wilson interval and its count** ("7 of 10, 95% CI 40 to 89"). Replace
  the "hide under 10" rule with "show, but never without the interval and the count"; the
  interval itself shows the problem at small n (Bowyer et al.). Inference from the Wilson
  arithmetic above.
- **Version comparisons are paired.** Same scenarios and seeds (Inference), report the
  difference in paired success with an interval (Kotawala recommends a McNemar-based
  required sample size for binary outcomes and a paired bootstrap for graded metrics; Wang
  shows the power gain), or a sign test (Inference). Compare to a pre-declared primary check
  to limit multiple comparisons (Inference).
- **Show noise, not just means.** Split "variation across seeds" from "variation across
  scenarios" (my application of Wang's prediction vs data noise); use clustered intervals
  when several checks come from one scenario (Miller recommends clustered standard errors for
  grouped questions; Bowyer et al. found clustered CLT intervals also fail at small n and
  support clustered Bayesian intervals).
- **Report cost and time**, since the same accuracy can come at very different cost
  (Moghadasi and Ghaderi); Kapoor et al. argue for cost-controlled comparison with dollar
  costs and token counts.

### D. Reporting uncertainty

A scored report should have, in order: (1) a header with versions (teamsim, scenario set,
product, any model ids), seeds and the replay file; (2) per-check results with counts and
Wilson intervals; (3) a "what this does not show" block (taken from Eval Factsheets' Alignment
dimension and Rollout Cards' drop manifest): checks not run, runs failed or skipped, flaky
checks, the judge's validation status; (4) controls (below) with their own results; (5) the
labels "simulated, not human" and "planted facts are fictional".

### E. Validating the simulator and the checker themselves

1. **Controls in CI.** A do-nothing bot, an oracle bot that reads the plan and answers
   perfectly, and a cheating bot that tries to read the key (Zhu et al. on trivial agents;
   Zhong et al. and Wang et al. on hacker loops). Each check must fail the do-nothing bot,
   pass the oracle bot, and the cheating bot must not reach the key. Inference: this is
   cheap and, in my reading, nobody has published it for team chat.
2. **Counterfactual sensitivity.** Run a deliberately weak and a deliberately strong
   product and confirm scores separate (borrowed from ConvApparel's good and bad
   recommenders, which it uses to test whether simulated users shift behaviour as real ones
   do; applying the idea to a product's scores is Inference).
3. **Behaviour fidelity against a small real log.** Compare the scripted team's message
   statistics (length, politeness markers, questions per turn, correction rate, response
   delay) with an anonymised real team chat on the four facets Sim2Real uses, using Dice
   overlap (Sim2Real) or clustered distribution divergence (Mehri et al., who use six facets
   of their own on WildChat, not a team chat). Publish the gap, do not hide
   it. Real data must be anonymised and consented to; ADR rules on real data still apply.
4. **Outcome calibration against humans (optional, later).** Ask a small number of people to
   play teammates for a few scenarios and compare success with the scripted team's, binned by
   difficulty (Sim2Real's ECE). Lost in Simulation used about 40 people per group; a pilot
   of 10 to 20 would only detect large gaps (Inference).
5. **Pilot-run outlier review** before releasing a scenario set: tasks that fail for all
   products may be impossible; tasks only the weakest products pass may have shortcuts (ABC
   item T.10).
6. **Audit passing runs, not only failures** (Luo et al.).

### F. Reproducibility and versioning

- Freeze and version the scenario set and the emulator image; never depend on live external
  services (ABC T.6).
- Seed all random sources in the synthetic workspace; record the seed in the report (Inference,
  motivated by Liu and Lu, who do not endorse per-interaction reseeding as a general fix).
- Record and replay any model call; accept that hosted models change silently (Coqueret et
  al.).
- Keep held-out seeds unpublished so a product cannot overfit the published answer keys
  (Kapoor et al.; Inference for the seed mechanics).
- Publish a rollout-style run record next to the report (Masters et al.).

### G. Open decisions

- **Stack and runtime:** nothing in the literature favours a language. It does favour a
  runtime that is deterministic and replayable, and one that can run the control bots in CI.
- **v0.1 actions:** chat only first is consistent with the evidence that state-based checks
  need a small, well-controlled world (tau-bench's 115 and 50 tasks; AppWorld's 750 tasks
  took heavy engineering). Tasks and issues next.
- **First user:** unchanged; the review adds a selling point for builders: results come with
  intervals and controls, which many benchmarks lack (BetterBench: 14 of 24 assessed
  benchmarks did not report significance or uncertainty; ABC on agent benchmarks).
- **ADR 0003 gate:** add "outcome of each control bot" and "human-comparison on proxy
  tasks" to the measures, and require that simulated-feedback output show baselines (see
  section B). Thresholds are my proposals, see below.

### Candidate thresholds (proposals, with sources)

| Threshold | Value | Source |
|---|---|---|
| Interval method | Wilson (or Beta-Bernoulli Bayesian), 95% | Bowyer et al. (full text) |
| Repeats per scenario if a model is in the product loop | at least 5, report pass^k | Yao et al. (3+ trials used); Inference |
| Judge calibration labels | at least 200 for a CI under 0.1 in the worked example | Lee et al. (full text) |
| Judge repeats for any judge verdict kept | at least 10 majority-vote repeats (11 reached 95% fidelity on average; high-flip questions need more) | Yagubyan (abstract; small study) |
| Control bots | do-nothing must fail every check; oracle must pass | Zhu et al. (full text); Inference |
| Chance-corrected agreement for any human-labelled set | Cohen or Krippendorff, not raw agreement | Norman et al.; Caban |
| Judge validation status | Show "validated n=..." or "unvalidated" | tau2 labels (run-1 note); Eval Factsheets |

## Open problems

- **No published team-chat benchmark with planted facts.** I found none, so nothing to
  calibrate against. Teamsim could measure its own scripted team against anonymised chat
  logs and a pilot with a few humans.
- **How to set the number of seeds.** The noise results come from model benchmarks with
  hundreds of items. A scripted team with deterministic products might need far fewer, or the
  variance might sit in scenario design. Teamsim can measure the variance across seeds
  directly.
- **Multiple comparisons across many checks** are not treated for agent evaluation in what I
  found.
- **Contamination of generated scenario sets** has no direct literature in this pass.
- **Judge validity for teammate-behaviour questions** (tone, helpfulness) has no calibration
  data for team chat.
- **Cross-platform transfer:** whether results on a Discord emulator predict real Discord
  behaviour is unmeasured (the emulator fidelity question in the run-1 notes).
- **Several 2026 preprints here are single-author or small** (marked); their numbers are
  leads, not settled results. Few of the papers have been peer reviewed at the time of
  reading.

## Where this disagrees with the run-1 notes

- **"Nobody plays a team with planted facts."** Still mostly true for live simulated
  teammates, but AutoBuddy-Bench (preprint, 2026-11-09) is a close relative: a generated
  organisation with expected outcomes computed from world state, hidden labels on records,
  a state diff and no model in grading. It differs in that it renders a static workspace per
  employee and day. The run-1 notes should cite it as the nearest prior work and borrow its
  acceptance check on the generated world.
- **The "no rate shown from fewer than 10 events" rule.** It is borrowed from tau2's
  documentation. The literature does not give 10 as a threshold; it says use intervals that
  stay valid at small n. Recommendation: always show count and Wilson interval; do not hide
  rates. This refines, rather than contradicts, the note.
- **"Agent success varies by up to 9 points depending on the user LLM."** Confirmed. On 115
  tasks with 3 runs, three of four user models overlapped (67 to 71 percent) and one was
  about 9 points higher (Seshadri et al., full text). The authors read this as a reliability
  concern for single-model user simulation and recommend reporting across several user
  models, and their wider findings (miscalibration against humans, dialect disparities)
  argue that LLM-simulated users are unreliable proxies. It supports the model-free default
  and reporting across user models.
- **The note treats a scripted team as the safe default without a caveat.** The literature
  says the hand-crafted agenda-based simulator has limited diversity (Kreyssig et al.). That
  a scripted team is repeatable, and that validity then rests on the checks more than on the
  realism of the people, is my inference. Teamsim should still validate behaviour against
  real logs.
- **The note says "avoid LLM judges in the core".** Supported for transcript-only and
  satisfaction-style judges (Advani: no tested configuration above AUROC 0.65 on tau2;
  GAUGE: 57.5 percent of satisfied conversations failed). Not a blanket ban: GAUGE's judge
  with access to the tool calls and task carried signal, so the rule is judges only with
  evidence access and never as the primary detector, which matches section A. Not in
  conflict.
- **ADR 0003** asks for diversity, sycophancy and human-comparison measures. The literature
  adds two it does not mention: control bots (do-nothing, oracle, cheat) for the checker, and
  outcome calibration against humans on the same scenarios. No contradiction; both are
  additions.

## Sources

All read 2026-11-11. Venue is "arXiv preprint" unless stated; I did not verify later
peer-reviewed versions except where a venue is named.

- Mind the Sim2Real Gap in User Simulation for Agentic Tasks, Zhou et al., 2026, https://arxiv.org/abs/2603.11245 [full text]
- Lost in Simulation: LLM-Simulated Users are Unreliable Proxies for Human Users in Agentic Evaluations, Seshadri et al., 2026, https://arxiv.org/abs/2601.17087 [full text]
- SimulatorArena, Dou et al., 2025, https://arxiv.org/abs/2510.05444 [full text]
- RealUserSim, Zhu et al., 2026, https://arxiv.org/abs/2605.20204 [abstract]
- Beyond Cooperative Simulators (Persona Policies), Chopra et al., 2026, https://arxiv.org/abs/2605.12894 [abstract]
- Simulated Customers Never Walk Away, Chen, 2026, https://arxiv.org/abs/2606.20708 [abstract]
- Measuring and Mitigating the Distributional Gap Between Real and Simulated User Behaviors, Mehri et al., 2026, https://arxiv.org/abs/2605.07847 [full text]
- AutoBuddy: Evaluating Proactive, Always-On Agents on Task Discovery and Execution in a Simulated Workplace, Chen et al., 2026, https://arxiv.org/abs/2611.12393 [full text]
- ClawsBench, Li et al., 2026, https://arxiv.org/abs/2604.05172 [abstract]
- TheAgentCompany, Xu et al., 2024, https://arxiv.org/abs/2412.14161 [abstract]
- ConvApparel, Meshi et al., 2026, https://arxiv.org/abs/2602.16938 [abstract]
- OdysSim, Zhou et al., 2026, https://arxiv.org/abs/2606.14199 [abstract]
- Controllable User Simulation, Tennenholtz et al., 2026, https://arxiv.org/abs/2605.11519 [abstract]
- User Simulation for Evaluating Information Access Systems, Balog and Zhai, 2023, https://arxiv.org/abs/2306.08550 [abstract]
- User Simulation in the Era of Generative AI, Balog and Zhai, 2025, https://arxiv.org/abs/2501.04410 [abstract]
- Agenda-Based User Simulation for Bootstrapping a POMDP Dialogue System, Schatzmann et al., 2007, NAACL short papers, https://aclanthology.org/N07-2038/ [bibliographic record only]
- Neural User Simulation for Corpus-based Policy Optimisation for Spoken Dialogue Systems, Kreyssig et al., 2018, https://arxiv.org/abs/1805.06966 [abstract]
- Validating Simulations of User Query Variants, Breuer et al., 2022, https://arxiv.org/abs/2201.07620 [abstract]
- Validating Search Query Simulations: A Taxonomy of Measures, Kruff et al., 2026, https://arxiv.org/abs/2601.11412 [abstract]
- How to Dogfood Your AI Chat Agent, Maiorano, 2026, https://arxiv.org/abs/2608.09939 [abstract]
- tau-bench, Yao et al., 2024, https://arxiv.org/abs/2406.12045 [full text]
- tau2-Bench, Barres et al., 2025, https://arxiv.org/abs/2506.07982 [abstract]
- AppWorld, Trivedi et al., 2024, https://arxiv.org/abs/2407.18901 [abstract]
- Identifying the Risks of LM Agents with an LM-Emulated Sandbox (ToolEmu), Ruan et al., 2023, https://arxiv.org/abs/2309.15817 [abstract]
- Collaborative Gym, Shao et al., 2024, https://arxiv.org/abs/2412.15701 [abstract]
- Searching for Synergy in Shared Workspace Human-AI Collaboration, Kotalwar et al., 2026, https://arxiv.org/abs/2606.18413 [abstract]
- TeamBench, Kim et al., 2026, https://arxiv.org/abs/2605.07073 [abstract]
- tau-Rec, Narasimhan and Narasimhan, 2026, https://arxiv.org/abs/2606.10156 [abstract]
- Replay Fidelity in LLM Agent Evaluation (AppWorld), Liu and Lu, 2026, https://arxiv.org/abs/2611.11216 [abstract]
- From Confident Closing to Silent Failure: Characterizing False Success in LLM Agents, Advani, 2026, https://arxiv.org/abs/2606.09863 [full text]
- GAUGE, Bodhwani et al., 2026, https://arxiv.org/abs/2609.12191 [full text]
- Establishing Best Practices for Building Rigorous Agentic Benchmarks, Zhu et al., 2025, https://arxiv.org/abs/2507.02825 [full text]
- BetterBench, Reuel et al., 2024, https://arxiv.org/abs/2411.12990 [abstract]
- Measuring what Matters: Construct Validity in Large Language Model Benchmarks, Bean et al., 2025, https://arxiv.org/abs/2511.04703 [abstract]
- AI Agents That Matter, Kapoor et al., 2024, https://arxiv.org/abs/2407.01502 [abstract]
- Measurement Without Validity, Caban, 2026, https://arxiv.org/abs/2608.00794 [abstract]
- Hardening Agent Benchmarks with Adversarial Hacker-Fixer Loops, Zhong et al., 2026, https://arxiv.org/abs/2606.08960 [abstract]
- Do Androids Dream of Breaking the Game? (BenchJack), Wang et al., 2026, https://arxiv.org/abs/2605.12673 [abstract]
- Maintaining Benchmarks Against Increasingly Capable Agents, Luo et al., 2026, https://arxiv.org/abs/2609.34262 [abstract]
- Every Model Cheats, Kouremetis et al., 2026, https://arxiv.org/abs/2607.21763 [abstract]
- Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena, Zheng et al., 2023, https://arxiv.org/abs/2306.05685 [abstract]
- Reliability without Validity, Norman et al., 2026, https://arxiv.org/abs/2606.19544 [abstract]
- The Coin Flip Judge?, Yagubyan, 2026, https://arxiv.org/abs/2606.13685 [abstract]
- The Geometry of LLM-as-Judge, Mukherjee et al., 2026, https://arxiv.org/abs/2606.03043 [abstract]
- When Consistency Does Not Mean Reliability, Tiwari, 2026, https://arxiv.org/abs/2609.13824 [abstract]
- Judging the Judges: bias mitigation strategies, Soumik, 2026, https://arxiv.org/abs/2604.23178 [abstract]
- Beyond Attack-Success Rate: Action-Graded Severity Scale, Owiredu-Ashley, 2026, https://arxiv.org/abs/2607.07474 [abstract]
- How to Correctly Report LLM-as-a-Judge Evaluations, Lee et al., 2025, https://arxiv.org/abs/2511.21140 [full text]
- Prediction-Powered Inference, Angelopoulos et al., 2023, https://arxiv.org/abs/2301.09633 [abstract]
- Demystifying Prediction Powered Inference, Song et al., 2026, https://arxiv.org/abs/2601.20819 [abstract]
- Adding Error Bars to Evals, Miller, 2024, https://arxiv.org/abs/2411.00640 [abstract]
- Position: Don't Use the CLT in LLM Evals With Fewer Than a Few Hundred Datapoints, Bowyer et al., 2025, https://arxiv.org/abs/2503.01747 [full text]
- Measuring all the noises of LLM Evals, Wang, 2026, https://arxiv.org/abs/2512.21326 [full text]
- Resolution Diagnostics for Paired LLM Evaluation, Kotawala, 2026, https://arxiv.org/abs/2605.30315 [abstract]
- Towards a Science of AI Agent Reliability, Rabanser et al., 2026, https://arxiv.org/abs/2602.16666 [full text]
- Measuring the Unmeasurable: Markov Chain Reliability for LLM Agents, Tran-Truong and Le, 2026, https://arxiv.org/abs/2604.24579 [abstract]
- Understanding and Mitigating Numerical Sources of Nondeterminism in LLM Inference, Yuan et al., 2025, https://arxiv.org/abs/2506.09501 [abstract]
- Randomness in large language models: What researchers need to know (and report), Coqueret et al., 2026, https://arxiv.org/abs/2607.24372 [abstract]
- Necessary but Not Sufficient: Temperature Control and Reproducibility in LLM-as-Judge Safety Evaluations, Tamba, 2026, https://arxiv.org/abs/2606.26185 [abstract]
- An Empirical Study of Flaky Tests in Python, Gruber et al., 2021, https://arxiv.org/abs/2101.09077 [abstract]
- On the Flakiness of LLM-Generated Tests for Industrial and Open-Source Database Management Systems, Berndt et al., 2026, https://arxiv.org/abs/2601.08998 [abstract]
- Eval Factsheets, Bordes et al., 2025, https://arxiv.org/abs/2512.04062 [abstract]
- Evaluation Cards, Ghosh et al., 2026, https://arxiv.org/abs/2606.09809 [abstract]
- What Twelve LLM Agent Benchmark Papers Disclose About Themselves, Moghadasi and Ghaderi, 2026, https://arxiv.org/abs/2605.21404 [abstract]
- Rollout Cards: A Reproducibility Standard for Agent Research, Masters et al., 2026, https://arxiv.org/abs/2605.12131 [abstract]
- Beyond Accuracy: A Multi-Dimensional Framework for Evaluating Enterprise Agentic AI Systems, Mehta, 2025, https://arxiv.org/abs/2511.14136 [abstract]
