# Ground truth, test oracles and scenario-based simulation testing: literature review (2026-11-11)

Full-text check updated 2026-11-12: [method and limits](2026-11-lit-fulltext-check.md).
Depth tags retain the initial reading pass unless updated; current source access is
recorded per paper in the [bibliography](bibliography/).

Scope: how to design teamsim's planted facts, scenarios, presets and checks so that the scores
mean something. Covers the oracle problem, metamorphic testing, scenario-based testing in
driving and robotics, mutation analysis of check suites, combinatorial coverage, chatbot
testing, documentation and validation of simulation models, and flakiness. Papers only
(peer-reviewed or arXiv). Run-1 notes on prior art are not repeated.

Reading depth is marked in the tables: "full" means passages of the full text were read,
"abstract" means only the abstract (and metadata) was read. Statements marked "Inference" are
mine, not the papers'.

## Summary

1. **A planted fact is a specified oracle, the strongest kind.** The oracle survey (Barr et al.)
   separates specified oracles (from a specification), derived oracles (from other versions,
   properties or past runs), implicit oracles (crashes) and human oracles. One 2026 preprint
   shows that an oracle whose expected value flows from the system under test cannot detect
   faults that move that value (one system, one author).
   teamsim plants the facts itself, so its expected values come from outside the product.
   *For teamsim: keep every expected value in the preset; never derive it from the product's
   output, and never let a model's reading of the product's output set the expected value.*
2. **Fuzzy outputs need layers of oracle, ordered by how defensible they are.** Exact and
   structural checks first (id, owner, date, status, "the answer cites message X"), metamorphic
   relations second, a model judge last and labelled. A 2026 review of 83 studies of LLM
   oracles found just over half reach a verdict with no specification, and quality is mostly
   judged by resemblance to a known oracle, not by injected faults. *For teamsim: every check
   states its oracle tier in the report.*
3. **Metamorphic relations find faults that labels miss, but they are noisy.** In about
   561,000 groups (36 relations, 3 LLMs) the mean violation rate was 18%, but only 62% of 967
   sampled violations were true positives, and 28% of initially failing groups failed in all
   10 reruns (others flipped). The best multi-turn dialogue method reached 75.8% precision on
   120 sampled bugs. *For teamsim: a relation ships only with a measured false-positive rate
   on a known-good product, and its failures are advisory until that rate is known.*
4. **Multi-turn relations beat single-turn ones on question-answer dialogues.** MORTAR found
   164% more bugs and 51% more bugs per test case than the best of two single-turn methods
   (METAL and QAAsker) adapted to multi-turn use, on CoQA dialogues and 8 systems. It has no
   multi-turn baseline and was not tested on team chat. *For teamsim (inference): relations
   over the whole chat (reorder, split, paraphrase earlier messages, rename handles) may fit
   a team chat better than per-question relations; MORTAR's own perturbations are round
   shuffle, reduction and duplication, and the fit of the others is untested.*
5. **Driving offers useful scenario layers, with validation still open.** Scenic
   treats a scenario as a distribution and a test as a sample; the driving literature separates
   logical scenarios (parameter ranges) from concrete ones and ties coverage to an Operational
   Design Domain. A 2026 survey names the absence of standard evaluation metrics as a gap.
   *For teamsim: a preset is an abstract scenario with named parameter ranges; a run is
   (preset version, parameters, seed); coverage is reported over the stated ranges.*
6. **Measure check quality with mutants, not with coverage.** In a 2026 study of multi-agent
   workflows (29,601 agent runs, 1,084 mutants) the best baseline test suite killed 0.717 of
   structural mutants and 0.559 of safety mutants; removing a restriction was the least
   detected fault (0.19 to 0.28 under the outcome criterion) because it is silent unless a test probes it directly.
   *For teamsim: ship a small library of deliberately broken reference products and report the
   share of them the checks catch, plus a negative probe for every "must not happen" check
   (inference: the paper shows the need for restriction faults only).*
7. **Simulation tests are flaky and the field has measured it.** In driving simulators the
   upper bound of hard flaky rates across five test setups ranged from 1% to 74%; setups with
   more moving actors or an end-to-end model were flakier than a bare lane-keeping setup. *For teamsim: the
   scripted, seeded team removes the simulator's share of flakiness; what remains comes from
   the product, timing and any model, so rerun failures and report a pass rate.*
8. **A documentation standard exists and is being extended for LLM agents.** ODD has seven
   elements and a rule: describe what the program does, not what you think it does. A Nov 2026
   workshop preprint finds 77% of binding and resolution items undetermined in 28 published
   LLM-agent simulations, and shows one overlooked instruction flipping a result (0.35 to
   1.00, 20 seeds). It is a single-coder, single-case study. *For teamsim: document every
   preset in ODD order, and add the LLM blocks only for presets where a model plays teammates.*
9. **Validate against several patterns and for a stated purpose.** Pattern-oriented modelling
   (Grimm et al., 2005) and a 2026 proposal for LLM social simulation (shown only on three
   hypothetical traces) check intermediate patterns, not only the end state. Sargent's validation tutorial: a model is valid for a set
   of experimental conditions within an accuracy range fixed before building; passing many
   conditions does not make it valid everywhere. *For teamsim: simulated feedback (ADR 0003)
   needs a stated purpose, an accuracy range set in advance and several patterns at different scales.*
10. **Judge reliability does not establish construct sensitivity.** One study reports mean
    invariance S = 0.945 and sensitivity R = 0.319 across judges at matched invariance, using
    human-directed edits to claim scope and strength; another finds most LLM validators accept over 96% of valid outputs
    but typically reject under 25% of invalid ones. *For teamsim: any model-judged check must report both invariance and
    sensitivity measured on planted known-bad answers.*

## 1. Test oracles and fuzzy outputs

**What the survey says.** Barr et al. (IEEE TSE 2015) define an oracle as a procedure that
distinguishes correct from incorrect behaviour, and call automation of the oracle a bottleneck
for test automation. They organise oracles as specified, derived, implicit and human.
Pseudo-oracles (independently built alternative versions whose outputs must agree) and
metamorphic relations (checking properties across related runs) sit in the derived group.
When no oracle is available, partial oracles and reducing the human cost are the remedies.
[full text]

**What later work adds.**

| Paper | Venue, year | Finding | Depth |
|---|---|---|---|
| Mughal and Bilal, LLM-based test oracles | IEEE Access, 2026 | 2,436 records, 54 studies, 83 with snowballing. Just over half reach a verdict with no specification. Oracle quality mostly judged by resemblance to a known oracle, rarely by whether injected faults are caught. | abstract |
| Canedo, Oracles that cannot fail | arXiv preprint, 2026 | An expectation that flows from the code under mutation cannot detect a fault that moves it together with the measurement, when the anchored value sizes the comparison; where it only places a scenario or feeds a loose bound the paper calls the self-reference latent, with no measured loss. 366 mutants, 4 modules, one system, one author. Re-anchoring one oracle on published procedure recovered 8 of 46 mutants. | abstract |
| Jain et al., Mind the gap | arXiv preprint, 2023 | The "oracle gap" (coverage minus mutation score) flags weak oracles; observational study over Maven projects. | abstract |
| Hossain and Dwyer, oracle-based adequacy | arXiv preprint, 2022 | Survey of 7 publications. Code coverage says nothing about oracle quality; the reviewed studies report that oracle-based coverage metrics detect more faults. One user study of state coverage could not confirm a significant link to fault detection. No new experiments. | abstract |
| Balli, Test oracle problem in LLM-as-judge corpora | arXiv preprint, 2026 | Corpora built by deterministic perturbation of a gold answer carry an item-level oracle; LLM-generated negatives do not. A silent generation fault produced a fake 32-point effect that replicated from N=50 to N=500. | abstract |
| Kim et al., Metamorphic testing of RAG under corpus change | arXiv preprint, 2026 | 11 mutation operators on index and retrieved context, 28k mutants, violation rates 4.9% to 10.2%. Oracle F1 was 0.927 on RepLiQA and 1.000 on financial datasets, where exact numeric matching coincides with ground truth; best RAGAS F1 was 0.570 on RepLiQA. | full |

Inference: teamsim's planted facts are the "perturbation of a gold answer" case, the safe one.
The Canedo and Balli results are single-author preprints; treat them as warning patterns, not
effect sizes. The Kim result is self-reported on their own mutants.

## 2. Metamorphic testing for NLP, LLM and chat systems

| Paper | Venue, year | What was measured | Key number | Depth |
|---|---|---|---|---|
| Cho et al., Metamorphic testing of LLMs for NLP | ICSME 2025 | 191 relations from 44 papers (24 tasks); 36 run on 3 LLMs, 4 tasks | 561,267 groups; mean violation 18% (QA 12%, NLI 17%, sentiment 25%, relation extraction 32%); true-positive rate 62% of 967; 28% of 99,099 failing groups failed in all 10 reruns | full |
| Guo et al., MORTAR | IEEE TSE, 2026 | Multi-turn, 7 dialogue-level perturbations, 4 relations, no LLM judge, 8 systems, 500 seed dialogues | +164% bugs, +51% bugs per test case vs best single-turn; precision 75.8% vs 60.8% and 49.2% (120 sampled each); dropping any relation costs over 11% of bugs | full |
| Zheng et al., MT and LLMs survey | arXiv preprint, 2026 | 93 primary studies, incl. dialogue, RAG, agents | taxonomy, challenges and future directions | full |
| Manino et al., Systematicity and transitivity | arXiv preprint, 2022 | Relations over several source inputs raise the number of test cases polynomially | n/a | abstract |

**Fault-detection power.** Cho et al. compared relation-based testing with label-based testing
on the same items: both passed about 53%; labels caught a wrong answer that the relation
missed in about 27%; the relation flagged a case the label had marked correct in about 11%;
both failed in about 10%. They conclude labels find more faults overall and relations add
faults labels miss. Hence relations complement, not replace,
planted ground truth. [full]

**Limits the authors state.** Possible data leakage; one of the tested models also generated
the transformations; one model had no seed option; only 36 of 191 relations were run. Their
paper also has small internal inconsistencies in counts (549,548 vs 561,267 groups), so
treat counts as approximate. [full]

**Relations that fit a team chat (inference, built from these papers and teamsim's checks).**

- Paraphrase a message that holds a planted fact: same cited message, same record.
- Reorder independent messages: same final record.
- Rename or alias a handle consistently: same owner.
- Add off-topic noise: planted fact still retrieved, noise not stored as a decision.
- Split one message into fragments: same record (the prototype already guards this).
- Restart the product mid-run: same final state as an uninterrupted run.
- Insert a message that should be ignored (the bot's own output, an injection): record and
  answers unchanged.

Each needs a stated expected relation, a measured false-positive rate and a rerun policy.

## 3. Scenario-based testing from driving and robotics

| Paper | Venue, year | What it shows | Depth |
|---|---|---|---|
| Fremont et al., Scenic | arXiv preprint (submitted journal extension of PLDI 2019), 2020 | A scenario is a distribution over scenes and agent behaviours, with hard and soft constraints; sampling gives concrete tests | abstract |
| Feng et al., Scenario library generation | IEEE T-ITS, 2020 | Scenario criticality = maneuver challenge x exposure frequency; a library is a critical set for a given ODD | abstract |
| Birkemeyer et al., Is scenario generation ready for SOTIF? | arXiv preprint, 2023 | Existing generators do not meet SOTIF requirements; asks what real-world detail a scenario covers | abstract |
| Zhou et al., GenAI for ADS scenario generation | arXiv preprint, 2026 | 31 studies, 10 surveys; gaps: no standard evaluation metrics, weak ODD-specific coverage | abstract |
| Majumdar et al., Paracosm | arXiv preprint, 2019 | Coverage defined with combinatorial testing and low-dispersion sequences | abstract |
| Min et al., Full coverage in logical scenario space | Sensors, 2025 | 100% parameter-space coverage vs combinatorial 86.5%, Monte Carlo 84.3% | abstract |
| Saha et al., STADA | arXiv preprint, 2026 | Specification-based scenario generation; matches best baseline coverage with 6x fewer simulations | abstract |
| Alshahwan et al., Rich-state simulated populations at Meta | arXiv preprint, 2024 | Simulated users with accumulated state at Meta (Facebook, Messenger, Instagram): +38% average code coverage, +115% average faults found, the latter measured through crash counts over Alpha builds | abstract |

**What transfers (inference).**

- *Logical vs concrete.* A teamsim preset should hold ranges (how noisy, how long an absence,
  how many fragments) and a seed; the concrete chat is the output. This is Scenic's
  abstract/concrete split and the ADS "logical scenario" idea.
- *Criticality and exposure.* Feng's idea of ranking scenarios by challenge times how often
  they occur maps to ranking planted facts by how often real teams produce them and how bad a
  miss is. teamsim has no exposure data yet; take it from research on real teams as patterns
  only (project rule), not from guesswork.
- *Coverage needs a stated domain.* The ADS surveys stress ODD coverage. teamsim should state
  which team sizes, channel types, languages, noise levels and fact types a preset covers, and
  say "not covered" for the rest.
- *State matters.* The Meta result (industry, preprint) supports planting rich history before
  testing, which is what the dataset-first design already does.

**What does not transfer.** Driving scenarios have continuous physics and a clear safety
metric (collision, time-to-collision). A team chat has neither; correctness is categorical
(did the record change) and partly social. Criticality metrics from driving cannot be copied.

## 4. Mutation analysis and measuring check quality

| Paper | Venue, year | What it shows | Depth |
|---|---|---|---|
| Kahani and Bagherzadeh, Mutation testing for multi-agent workflows | arXiv preprint, 2026 | 14 operators in 4 families; 3 kill criteria; k=3 repeats with majority vote; 10 workflows, 29,601 runs. Structural criterion: developer smoke suite 0.717, random 10% sample 0.488, end-to-end task suite 0.560, all vs a coverage-driven suite at 1.000. Safety criterion: baselines 0.401 to 0.559. Restriction removal was the least detected fault (0.19 to 0.28 under the outcome criterion). | full |
| Clerissi et al., MUTABOT multi-platform | arXiv preprint, 2025 | Fault injection into chatbot conversations exposes weak suites generated by Botium | abstract |
| Rehan, TDAD | arXiv preprint, 2026 | Agent prompts compiled against tests; semantic mutation of prompts; hidden test split; mutation scores 86 to 100% (the body gives this range for the original v1 specs, all v2 runs 100%; the abstract says evolved specs) | abstract |
| Petrovic et al., Does mutation testing improve testing practices? | arXiv preprint, 2021 | Data from one company, non-randomised: almost 15 million mutants; coupling to real faults analysed on 1,502 bugs; developers shown mutants wrote more tests | abstract |
| Allamanis et al., Tailored mutants | arXiv preprint, 2016 | Tailored identifier and literal operators detect 8% more Defects4J defects at class scope and 14% more at line scope than traditional operators | abstract |
| Ojdanic et al., Syntactic vs semantic similarity | arXiv preprint, 2021 | Syntactic similarity to real faults does not imply semantic similarity | abstract |
| Zhao et al., Coverage and mutation of LLM-generated tests | arXiv preprint, 2026 | Metrics give useful signals across models when code is assumed bug-free; within-model correlations are weak, and the metrics are unreliable for finding existing bugs | full |
| Owotogbe et al., Chaos engineering MLR | arXiv preprint, 2024 | 96 sources; chaos engineering is controlled fault injection into running systems | abstract |

**Reading the evidence.**

- Mutation score is the established measure of whether tests catch faults. In one company's
  data of about 15 million mutants, a coupling analysis of 1,502 bugs found mutants coupled to
  real faults (Petrovic et al.). Realism is still not guaranteed: syntactic similarity to real
  faults does not reflect semantic similarity (Ojdanic et al.), so it cannot be judged by how a
  mutant looks. Mutants tailored to a project's own code coupled to more real faults than
  traditional operators (Allamanis et al.). Inference: generic mutants are a floor and faults
  taken from the product's bug history are probably better; neither paper tests that.
- Kahani et al. is the closest analogue: it mutates the structure of an LLM system, scores
  test suites with several kill criteria, and uses repeats and majority voting against
  nondeterminism. Its main lesson for teamsim: task-success-style suites caught only about half
  of permission violations, so checks for restrictions need explicit probes (negative
  polarity). The prototype's private-channel check already has a positive control; applying the
  same pattern to secrets, injections and visibility is my inference, which the paper does not
  test. Limits: one model
  (gpt-4.1-mini), workflows from one SDK, preprint.
- Chaos engineering is the same idea at system level (inject a fault, watch the behaviour).
  teamsim already injects gateway disconnects and offline gaps; those are fault-injection
  scenarios, and their checks can be mutation-tested the same way.

**A way to measure teamsim's own checks (inference).**

1. Build a tiny reference product with no model (stores messages, derives a record from tags).
2. Define mutation operators per check category (table in the next section).
3. Run every check against the unmutated product (must pass; this measures false positives)
   and against each mutant (must fail). Report kill rate per category and list survivors.
4. Mark equivalent mutants by hand once, and keep that list in the repository.
5. Repeat each run k=3 and use the majority, as Kahani et al. did.

## 5. Combinatorial coverage and prioritisation

| Paper | Venue, year | What it shows | Depth |
|---|---|---|---|
| Kuhn et al., Software fault interactions | IEEE TSE, 2004 | Failures in several domains came from few interacting conditions; per the NIST summary, up to 6 parameters, and 4-way to 6-way coverage caught all faults found by exhaustive testing in the studied systems | summary page only |
| Qin et al., Metrics for combinatorial test suites | arXiv preprint, 2026 | 8 projects, 32 scenarios, 295,624 suites; value-combination coverage (VCC) predicts fault detection | abstract |
| Yoon et al., Adaptive testing for LLM apps | arXiv preprint, 2025 | Adaptive random testing with string distances finds failures with smaller budgets | abstract |
| Gomes de Oliveira Neto et al., Behavioural diversity via mutation | arXiv preprint, 2020 | Mutation-based diversity raises APFD by 19% to 31% over artefact diversity (6 projects) | abstract |
| Ali et al., Coverage-guided road selection | SANER, 2026 | 89% smaller suite kept 79% of failing scenarios | abstract |

Inference for teamsim. Parameters (noise level, fragmentation, absence length, name variant,
fact type, channel visibility) are few and discrete, which is the case combinatorial testing
suits. Use pairwise (2-way) as the default sweep and 3-way for parameters tied to risky
checks (visibility, secrets, injection). The 4-to-6-way claim comes from a secondary summary
of one 2004 paper and from fault data in non-chat systems; do not rely on it for chat.
Prioritise by diversity first (ART or clustering), then by which mutants a scenario kills.

## 6. Testing conversational agents and chatbots

| Paper | Venue, year | What it shows | Depth |
|---|---|---|---|
| Clerissi et al., Task-based chatbots: how far are we? | arXiv, registered report, 2026 | Plans a study on chatbots selected from curated datasets of 193 Rasa and 185 Dialogflow bots, plus Amazon Lex. Hypothesis from earlier pilots: Botium-style tools explore mostly single request-response pairs and rely on exact-match or intent oracles; flakiness is one of 5 research questions. No results yet. | full (partial) |
| Clerissi et al., LexTester | arXiv preprint, 2026 | Dialog-graph model-based testing; 83% to 95% coverage of conversational elements; up to 4x fault detection vs Botium | abstract |
| Mao et al., MUCA | arXiv preprint, 2024 | Group chat bots must decide what, when and who to answer (3W) | abstract |
| Wang et al., Neo | arXiv preprint, 2025 | Probabilistic state model for test inputs; 4 of 120 malicious questions broke the target (3.3%) vs 7 of 120 (5.8%) for six human testers, no significance test; 180 questions in about 45 min vs 16 h | abstract |
| Houde et al., Controlling AI agent participation in groups | arXiv preprint, 2025 | Users disliked an agent that dominated a group conversation | abstract |

What this means (inference). The chatbot-testing literature is mostly single-user and
task-based. Group-chat testing, where silence is often the right answer, is thin; MUCA's
"when" and "who" dimensions suggest oracles for not responding and for addressing the right
person. The registered report is a plan, so its claims about tool weakness are the authors'
hypothesis, not a result. Coverage criteria used by these tools (conversational flows,
dialog-graph elements) are covered by the plain idea of "fact type x check x parameter".

## 7. Documentation and validation of simulation models

| Paper | Venue, year | What it shows | Depth |
|---|---|---|---|
| Grimm et al., ODD protocol, second update | JASSS, 2020 | 7 elements; "describe what the program does, not what you think the model does"; optional rationale per element; link ODD names to code; 5 to 10 pages typical, 30 to 40 complex | full (almost all) |
| Downes et al., ODD+LLM | arXiv, SocialAgent workshop, 2026 | 5 extra blocks (architecture, identity, inference config, call-site binding and resolution, validation); 28 papers coded; 77% of 306 binding and resolution item-scores below fully determined; system fingerprint unreported in all 28; one overlooked instruction (answer as an outside observer) moved convergence from 0.35 to 1.00 across 20 seeds, in a single reimplementation with a different model | full |
| Grimm et al., Pattern-oriented modeling | Science, 2005 | Use several patterns at different scales to design, test and calibrate | abstract |
| Topping et al., Post-hoc pattern-oriented testing | PLOS ONE, 2012 | Works on an existing large model; warns of over-fitting to patterns lacking explanatory detail | abstract |
| Lee and Seering, SLALOM | arXiv preprint, 2026 | Proposes validating the path through waypoints ("gates") not only the end state, using time-series alignment; demonstrated only on three hypothetical traces scored against AMI meeting data, no statistics | abstract |
| Sargent, Intro tutorial on V&V of simulation models | WSC, 2015 | Valid for a set of experimental conditions within an accuracy range fixed up front; 8-step procedure; a failed condition makes the model invalid | full |

**ODD elements (Grimm 2020).** 1 Purpose and patterns; 2 Entities, state variables, scales;
3 Process overview and scheduling; 4 Design concepts; 5 Initialization; 6 Input data;
7 Submodels. The authors state its limits: it is written for people, it is weaker for
discrete-event models, and there is no agreed delta-ODD for modified models. [full]

**Sargent's procedure (relevant steps).** Agree validation techniques with sponsors first;
fix the acceptable accuracy of output variables before building; do face validity on the
conceptual model; compare with system data for several sets of conditions; document;
schedule periodic review. [full]

Caveat on ODD+LLM: workshop preprint, single coder, no inter-rater reliability, one case
study with 20 seeds, one model, and the authors say it cannot guarantee reproducibility.
The direction (write down prompt assembly, parsing, retry) is plausible and cheap, but the
77% figure is indicative only.

## 8. Flakiness and nondeterminism in simulation tests

| Paper | Venue, year | What it shows | Depth |
|---|---|---|---|
| Amini et al., Flaky simulators in ADS testing | arXiv preprint, 2023 | Hard flaky rates (upper end per setup) 16%, 6%, 40%, 74% and 1% across five setups on two simulators; 4% to 68% of generated tests had noticeable fitness variation (one passage of the paper says 98%); the bare lane-keeping setup was least flaky; ML flagged flaky tests from one run (F1 85%, 82%, 96%) with a separate classifier per simulator and ADS pair, which may not generalise | full |
| Sorokin et al., MultiSim | Empirical Software Engineering, 2026 | Run each scenario on several simulators during the search and prioritise scenarios whose results agree across them; on average 66% higher rate of simulator-agnostic failures than single-simulator testing | abstract |
| Chance et al., Determinism of game engines | arXiv preprint, 2021 | Catalogues causes of nondeterminism. On one CARLA setup, variance stayed within tolerance only with restrictions (load at 75% or less, pre-collision data, or pedestrian-only scenarios); the authors say it may not transfer to other systems | abstract |
| Valle et al., Delta debugging with flaky executions | arXiv preprint, 2026 | Minimising a failing input often raised reproducibility | abstract |
| Cho et al. (section 2) | ICSME 2025 | 28% of failing groups failed on all 10 reruns; some models have no seed | full |

Takeaways. Seeds fix only part of the variation: timing, synchronisation and noise from the
environment remain (Amini et al.). Report variation explicitly, restrict the environment
where possible, and rerun. For LLM-based teammates, some providers offer no seed (Cho et
al.), so record outputs for replay rather than rely on seeds (inference, consistent with the
run-1 recommendation).

## Implications for teamsim

**Preset and scenario format (inference, from ODD, Scenic and Sargent).** A preset is a
versioned document plus data, with these fields:

| Field | Source idea |
|---|---|
| `purpose`: what the product class is, which questions the preset can answer | ODD 1, Sargent "intended purpose" |
| `patterns`: observable properties the simulated team must show (message length mix, share of chatter, reply latency) with numbers learned from real teams as patterns only | ODD 1, pattern-oriented modelling |
| `entities`: members (role, availability, handle and display-name variants), channels (visibility), bots | ODD 2 |
| `timeline`: acts, event types, scheduling rules, clock model | ODD 3 |
| `design_concepts`: only those that apply (adaptation: does anyone react to the product? stochasticity; observation) | ODD 4 |
| `parameters`: named ranges (noise, fragmentation, absence length, name variants) with defaults | logical scenario |
| `seed` and `generator_version` | concrete scenario = preset + parameters + seed |
| `inputs`: fixture files with provenance and a "fictional" flag | ODD 6 |
| `transforms`: each realism step with its validity rule ("never split an answer") | ODD 7 submodels |
| `planted_facts`: id, class, where planted, expected end state, visibility, which checks use it, oracle tier | ground truth ledger |
| `checks`: id, category, oracle type, positive control, negative probe, threshold, measured false-positive rate, mutants killed | check quality |
| `validity`: conditions covered, accuracy range, what is not covered, review date | Sargent |
| `llm_blocks` (only if a model plays teammates): model id, decoding, prompt assembly, parse and retry rules, fingerprint if offered, recorded outputs | ODD+LLM |

Keep the names in the document identical to the names in the code, as ODD advises.

**Oracle tier per check category (inference; prototype check numbers from the run-1 audit).**

| Category | Primary oracle | Add |
|---|---|---|
| Sync completeness, offline gap (2, 3) | Specified: ledger of planted messages | restart relation; timing threshold with reruns |
| Record fields: kind, status, owner, due, chain (4, 15) | Specified: expected final record, exact | fixed clock so due dates are exact; never accept "either of two dates" |
| Retrieval (5) | Specified: expected ids; recall and rank thresholds | paraphrase relation; a threshold, not "always pass" |
| Visibility, secrets (6, 13) | Specified negative: forbidden string never appears on any read surface | positive control; mutant that leaks |
| Prompt injection (7) | Specified structural (framing present) | metamorphic: record and answers unchanged with and without the injected message; do not pass when nothing was scanned |
| `/ask` answers (8) | Structural: cites an expected message | model judge only as labelled third tier, with invariance and sensitivity reported |
| Names vs handles (12) | Metamorphic: rename | n/a |
| Catch-up (14) | Specified: set of changes during absence | n/a |
| Group-chat behaviour | Specified negative: no reply where silence is expected | MUCA-style "when" and "who" cases |

**Check quality, concretely.** Build the reference product and mutant library (section 4).
Report per category: kill rate, survivors, false-positive rate on the unmutated product over
reruns. Do not set a pass bar for the kill rate at v0.1: the literature gives no number for
chat checks. Report it, and require only that every check kills at least one mutant and every
mutant is killed by at least one check or is listed as a survivor with a reason.

**Coverage metrics (inference).** Report four numbers per run: (1) fact-class x check
matrix coverage; (2) parameter coverage at 2-way (and 3-way for risky parameters) over the
preset's ranges, with value-combination coverage as the single summary (Qin et al.);
(3) mutant kill rate; (4) share of checks at each oracle tier. State uncovered conditions
explicitly.

**Flakiness policy.** Record seed, preset version, event log and any model outputs. Rerun
failing checks k=3 and take the majority (Kahani et al. repeat every test k=3 and take a
majority vote). Report three states, not two: pass, fail, flaky (my inference; they report
only a residual flaky-kill rate). A model-free default removes simulator variation; product and timing
variation remain.

**Simulated feedback gate (ADR 0003; I did not re-read the ADR text, only the brief).**
Evidence points to a gate with: a written purpose and accuracy range fixed in advance
(Sargent); validation against several patterns at different scales (Grimm 2005, Topping 2012; Topping et al. say their patterns were not independent) and
process fidelity, not only a final opinion (Lee and Seering, a proposal shown only on three hypothetical traces); a judge profile with both
invariance and sensitivity on human-directed construct-changing edits (Chen et al.; planted
known-bad inputs would be teamsim's adaptation); an agreeableness check
(Jain, Ahmed et al. 2025: most validators accepted over 96% of valid outputs and typically
rejected under 25% of invalid ones, on one code-feedback task); agreement corrected for chance, since exact-match agreement
overstated chance-corrected agreement by 33.8 to 41.3 points on MT-Bench across 21 judges (Norman et al.); and an ODD+LLM
description.
I found no published pass threshold for this use in these papers; teamsim must set and state its own.

**Stack and runtime.** The ideas above need no heavy stack: a scripted generator, a ledger,
a reference product and a report. That supports the run-1 lean toward a model-free default.

**v0.1 actions.** Chat-only keeps the oracle set small and mostly exact. Tasks and issues
add checks with exact oracles (status, owner, due) and cost little; repo actions add
nondeterminism and should wait.

**First user.** Builders of team-facing software need exact oracles and mutants more than
anything else; students need the same plus the plain-language "what this score means" text
below.

**Avoid.** Deriving expected values from product output; model-only judges as the headline;
single-run verdicts for anything timing- or model-dependent; relations without a measured
false-positive rate; coverage numbers without a stated domain; "always pass" checks.

## What a score does and does not prove

Suggested text for the report footer (inference; wording is mine):

> A pass means: under this preset (version V, parameters P, seed S), the product produced the
> expected result for the planted facts this check covers, and the check caught N of M known
> deliberate faults in a reference product. It does not mean the product is correct in
> general, that it handles team sizes, languages, platforms or noise levels outside the
> preset's stated range, or that failures of other kinds are absent. Checks marked
> "advisory" use relations or a model judge with a measured false-positive rate and do not
> count toward the headline. A fail with a flaky mark means the result changed on rerun.

## Open problems

- No published false-positive or kill-rate numbers for chat or group-chat checks; teamsim has
  to measure them.
- No standard coverage metric for scenario suites in driving (the 2026 survey says so), and
  none for team chat.
- Whether ODD+LLM improves reconstruction or costs authors much is untested (the authors say
  so); plain ODD is not covered by that paper.
- Group-chat bot testing, silence as correct behaviour, and multi-user oracles are thin.
- Exposure data (how often real teams produce each fact type) is missing; teamsim can only
  take patterns from real teams, not text.
- Whether mutants of a reference product predict real faults in teamctx-like products is
  unknown; compare against the four real failures from the live run as a first check.
- The literature on LLM test oracles is young and mostly preprints.

## Where this disagrees with the run-1 notes

I read the prototype audit and the demo fixtures, not every run-1 note. I found no
contradiction with the audit. Two refinements: (1) the audit proposes thresholds and exact
expectations for weak checks; the literature adds that checks for restrictions need explicit
negative probes (Kahani et al.; extending this to every "must not happen" check is my inference). (2) The audit's "model fixed per run,
effect not measured" point matches the evidence that results depend on prompt form (ODD+LLM's one-model
multiverse; it cites other work for model dependence), so model id and decoding settings belong in the run record.

## Sources

All read 2026-11-11. Depth is given in the tables above.

- Barr, Harman, McMinn, Shahbaz, Yoo. The Oracle Problem in Software Testing: A Survey. IEEE TSE 2015. https://doi.org/10.1109/TSE.2014.2372785
- Mughal, Bilal. LLM-Based Test Oracles: Source-of-Authority Taxonomy, A Systematic Literature Review. IEEE Access 2026. https://arxiv.org/abs/2607.05031
- Canedo. Oracles That Cannot Fail: Anchoring and the Expectation That Moves With the Fault. arXiv preprint 2026. https://arxiv.org/abs/2608.17214
- Hossain, Dwyer. A Brief Survey on Oracle-based Test Adequacy Metrics. arXiv preprint 2022. https://arxiv.org/abs/2212.06118
- Jain et al. Mind the Gap: The Difference Between Coverage and Mutation Score Can Guide Testing Efforts. arXiv preprint 2023. https://arxiv.org/abs/2309.02395
- Balli. The Test Oracle Problem in Synthetic LLM-as-Judge Corpora. arXiv preprint 2026. https://arxiv.org/abs/2607.13707
- Kim, Pasini, Tonella. When Knowledge Changes: Metamorphic Testing of RAG Systems with Mutations. arXiv preprint 2026. https://arxiv.org/abs/2607.26843
- Cho, Ruberto, Terragni. Metamorphic Testing of Large Language Models for Natural Language Processing. ICSME 2025. https://arxiv.org/abs/2511.02108
- Guo et al. MORTAR: Multi-turn Metamorphic Testing for LLM-based Dialogue Systems. IEEE Transactions on Software Engineering, 2026. https://arxiv.org/abs/2412.15557
- Zheng et al. Bidirectional Empowerment of Metamorphic Testing and LLMs: A Systematic Survey. arXiv preprint 2026. https://arxiv.org/abs/2605.13898
- Manino et al. Systematicity, Compositionality and Transitivity of Deep NLP Models: a Metamorphic Testing Perspective. arXiv preprint 2022. https://arxiv.org/abs/2204.12316
- Fremont et al. Scenic: A Language for Scenario Specification and Data Generation. arXiv preprint 2020. https://arxiv.org/abs/2010.06580
- Feng et al. Testing Scenario Library Generation for Connected and Automated Vehicles, Part I. IEEE T-ITS 2020. https://arxiv.org/abs/1905.03419
- Birkemeyer, King, Schaefer. Is Scenario Generation Ready for SOTIF? A Systematic Literature Review. arXiv preprint 2023. https://arxiv.org/abs/2308.02273
- Zhou et al. A Survey on the Applications of Generative AI in Automated Driving Systems Test Scenario Generation Methods. arXiv preprint 2026. https://arxiv.org/abs/2512.15422
- Majumdar et al. Paracosm: A Language and Tool for Testing Autonomous Driving Systems. arXiv preprint 2019. https://arxiv.org/abs/1902.01084
- Min et al. Full Coverage Testing Method for Automated Driving System in Logical Scenario Parameters Space. Sensors 2025. https://doi.org/10.3390/s25185764
- Saha et al. STADA: Specification-based Testing for Autonomous Driving Agents. arXiv preprint 2026. https://arxiv.org/abs/2603.10940
- Alshahwan et al. Enhancing Testing at Meta with Rich-State Simulated Populations. arXiv preprint 2024. https://arxiv.org/abs/2403.15374
- Kahani, Bagherzadeh. Mutation Testing for Multi-Agent Workflows. arXiv preprint 2026. https://arxiv.org/abs/2611.09895
- Clerissi, Masserini, Micucci, Mariani. Towards Multi-Platform Mutation Testing of Task-based Chatbots. arXiv preprint 2025. https://arxiv.org/abs/2509.01389
- Rehan. Test-Driven AI Agent Definition (TDAD): Compiling Tool-Using Agents from Behavioral Specifications. arXiv preprint 2026. https://arxiv.org/abs/2603.08806
- Petrovic, Ivankovic, Fraser, Just. Does mutation testing improve testing practices? arXiv preprint 2021. https://arxiv.org/abs/2103.07189
- Allamanis, Barr, Just, Sutton. Tailored Mutants Fit Bugs Better. arXiv preprint 2016. https://arxiv.org/abs/1611.02516
- Ojdanic et al. Syntactic Vs. Semantic similarity of Artificial and Real Faults in Mutation Testing Studies. arXiv preprint 2021. https://arxiv.org/abs/2112.14508
- Zhao, Zhou, Cohen. Do Coverage and Mutation Scores of LLM-Generated Test Suites Correlate with Their Effectiveness? arXiv preprint 2026. https://arxiv.org/abs/2607.22880
- Owotogbe et al. Chaos Engineering: A Multi-Vocal Literature Review. arXiv preprint 2024. https://arxiv.org/abs/2412.01416
- Kuhn, Wallace, Gallo. Software Fault Interactions and Implications for Software Testing. IEEE TSE 2004 (NIST record and summary read, not the full paper). https://csrc.nist.gov/pubs/journal/2004/06/software-fault-interactions-and-implications-for-s/final
- Qin et al. An Extensive Empirical Study on Evaluation Metrics for Combinatorial Interaction Testing. arXiv preprint 2026. https://arxiv.org/abs/2610.02560
- Yoon, Feldt, Yoo. Adaptive Testing for LLM-Based Applications: A Diversity-based Approach. arXiv preprint 2025. https://arxiv.org/abs/2501.13480
- Gomes de Oliveira Neto, Dobslaw, Feldt. Using mutation testing to measure behavioural test diversity. arXiv preprint 2020. https://arxiv.org/abs/2010.09144
- Ali, Stocco, Mariani, Riganelli. Coverage-Guided Road Selection and Prioritization for Efficient Testing in ADS. SANER 2026. https://arxiv.org/abs/2601.08609
- Clerissi, Masserini, Micucci, Mariani. Automated Testing of Task-based Chatbots: How Far Are We? arXiv registered report 2026. https://arxiv.org/abs/2602.13072
- Clerissi, Vasina, Mariani. A Model-based Testing Technique for Amazon Lex Task-based Chatbots. arXiv preprint 2026. https://arxiv.org/abs/2607.01094
- Mao et al. Multi-User Chat Assistant (MUCA): a Framework Using LLMs to Facilitate Group Conversations. arXiv preprint 2024. https://arxiv.org/abs/2401.04883
- Wang et al. Configurable multi-agent framework for scalable and realistic testing of LLM-based agents (Neo). arXiv preprint 2025. https://arxiv.org/abs/2507.14705
- Houde et al. Controlling AI Agent Participation in Group Conversations: A Human-Centered Approach. arXiv preprint 2025. https://arxiv.org/abs/2501.17258
- Grimm et al. The ODD protocol for describing agent-based and other simulation models: a second update. JASSS 23(2), 2020. https://www.jasss.org/23/2/7.html
- Downes, Milletich, Hirst. ODD+LLM: Specifying LLM-Agent Behavior for Reproducible Social Simulation. arXiv preprint (SocialAgent workshop) 2026. https://arxiv.org/abs/2611.08932
- Grimm et al. Pattern-oriented modeling of agent-based complex systems: lessons from ecology. Science 2005. https://doi.org/10.1126/science.1116681
- Topping, Dalkvist, Grimm. Post-hoc pattern-oriented testing and tuning of an existing large model: lessons from the field vole. PLOS ONE 2012. https://doi.org/10.1371/journal.pone.0045872
- Lee, Seering. SLALOM: Simulation Lifecycle Analysis via Longitudinal Observation Metrics for Social Simulation. arXiv preprint 2026. https://arxiv.org/abs/2604.11466
- Sargent. An Introductory Tutorial on Verification and Validation of Simulation Models. Winter Simulation Conference 2015. https://www.informs-sim.org/wsc15papers/182.pdf
- Amini, Naseri, Nejati. Evaluating the Impact of Flaky Simulators on Testing Autonomous Driving Systems. arXiv preprint 2023. https://arxiv.org/abs/2311.18768
- Sorokin, Biagiola, Stocco. Simulator Ensembles for Trustworthy Autonomous Driving Systems Testing. Empirical Software Engineering 2026. https://arxiv.org/abs/2503.08936
- Chance et al. On Determinism of Game Engines used for Simulation-based Autonomous Vehicle Verification. arXiv preprint 2021. https://arxiv.org/abs/2104.06262
- Valle, Ali, Arrieta. Delta Debugging for Cyber-Physical Systems with Flaky Test Executions. arXiv preprint 2026. https://arxiv.org/abs/2607.25695
- Chen et al. A Judge Should Know What Changed: Construct Validity for LLM-as-a-Judge Evaluation. arXiv preprint 2026. https://arxiv.org/abs/2608.24419
- Jain, Ahmed, Sahai, Leong. Beyond Consensus: Mitigating the Agreeableness Bias in LLM Judge Evaluations. arXiv preprint 2025. https://arxiv.org/abs/2510.11822
- Norman, Rivera, Hughes. Reliability without Validity: A Systematic, Large-Scale Evaluation of LLM-as-a-Judge Models. arXiv preprint 2026. https://arxiv.org/abs/2606.19544
