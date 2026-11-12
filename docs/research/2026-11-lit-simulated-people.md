# Validity of LLM simulations of people and of simulated feedback: literature review (2026-11-11)

Scope: peer-reviewed papers and arXiv preprints on whether LLM-simulated people (survey
respondents, experiment participants, digital twins, synthetic users) match real people, and what
that means for teamsim's simulated feedback (ADR 0003). Read depth is marked per paper:
[full text] means I read passages of the paper body; [abstract] means abstract only. Most
2026 items are preprints and are marked as such.

## Summary

1. **Aggregates on well-documented topics are often close; individuals, subgroups and spread are
   not.** LLM samples reproduce average views, then lose variance, rare views and the links between
   answers. Across several 2026 audits, non-LLM baselines (a demographic lookup, a Gaussian copula,
   a random forest) match or beat LLM respondents (Chen 2026 [full text], Lukauskas 2026 [full
   text], Kumagae 2026 [abstract]). *For teamsim:* never present a panel of simulated teammates as
   a sample of any population, and always show a no-LLM baseline next to the result.
2. **Experiments: direction is often right, size is wrong.** In 156 vignette experiments, three
   LLMs replicated 73-81% of main effects but produced effects 2-3x larger, and found significant
   effects in 68-83% of cases where the human result was null (Cui 2025 [full text]). A large
   preregistered archive is more positive (Ashokkumar/Hewitt, Nature 2026 [abstract]; r = 0.85
   reported in secondary sources, not verified). Realistic-looking response distributions did
   not predict accurate effect estimates (Li and Ji 2026 [full text]). *For teamsim:* simulated
   feedback may rank or flag, never size an effect or a percentage.
3. **Individual-level twins are weak.** Interview-grounded agents reach 83-86% of human two-week
   test-retest on General Social Survey items (Park 2024 [full text]), but a construct-level
   table in the same paper lists per-game correlations of 0.03 to 0.11 (one negative), and a
   19-study preregistered test found mean r = 0.20 with five distortions (Peng, Science Advances
   2026 [full text]). In product concept tests, interview-based agents matched 67% of human
   self-consistency on individual answers, and an agent with no information scored almost the same
   (Wang and Siu 2026 [full text]). *For teamsim:* do not claim a teammate "is like" a real
   person.
4. **The distortions are consistent across studies:** collapse to the modal answer,
   over-determination by demographics (models treat identity as 2-4x more decisive than it is),
   caricature, US/WEIRD skew, benevolence and social-desirability bias, hyper-rationality, and
   effect inflation. *For teamsim:* these are the failure modes to measure on every run.
5. **Simulated users are easier and kinder than real ones.** In a 451-human, 31-simulator study,
   simulators were too cooperative and polite and gave uniformly more positive feedback
   (Zhou 2026 [full text]); simulated non-buyers showed half the resistance of real ones (Liang
   Chen 2026, 793 real conversations, [abstract]). *For teamsim:* sycophancy is the default, so the sycophancy check must be a
   gate with a planted bad case, not a report line.
6. **Evidence for product and UX use is thin.** UX-agent papers mostly report heuristic evaluations
   with a few researchers. The best human comparison found LLM walkthroughs completed more tasks
   (97-100% vs 88%) and raised far fewer issues than humans (0.5-0.6 vs 7.5 per run), and needed
   explicit failure-point prompting to match the human-found problems (Zhong 2025 [full text]).
   *For teamsim:* defect-finding is the one capability with supporting evidence, and it is
   measurable against planted ground truth.
7. **Elicitation method matters as much as the model.** Asking for a number gives narrow,
   skewed answers; asking for text and mapping it, or asking the model to describe the
   distribution, fixes much of it. One industry preprint on 57 personal-care concept tests reports
   90% of the human test-retest ranking correlation, with caveats (Maier 2025 [full text]).
   *For teamsim:* no direct numeric ratings from simulated teammates.
8. **Fidelity improvements need human data.** Fine-tuning on human responses, retrieval over
   real histories and post-hoc calibration help, but each requires real human responses; and
   calibration guarantees need assumptions that are hard to meet (Tigre 2026, Hullman 2026).
   *For teamsim:* offer an optional "bring a few real answers" check, never a built-in fidelity
   claim.
9. **I found no study showing simulated users separate a good product from a bad one against real
   outcomes.** The nearest are concept-ranking and A/B-style tests with narrow ranges. *For
   teamsim:* the only honest discrimination test is a planted control (a known-worse variant),
   which tests the simulator's sensitivity, not the real-world verdict.
10. **Answer to the ADR 0003 question.** Yes, a restricted form can meet the bar as written
    (measured diversity, sycophancy check, comparison with published human results on proxy
    tasks). No form can meet a bar of "predicts how a real team would react". Details in
    "Implications".

## 1. Algorithmic fidelity and silicon samples

| Paper | Venue, year | What | Key number | Read |
|---|---|---|---|---|
| Argyle, Out of One, Many (2209.06899) | arXiv 2022 | GPT-3 conditioned on survey backstories | Subgroup distributions emulated ("algorithmic fidelity") | abstract |
| Santurkar, Whose Opinions (2303.17548) | arXiv 2023 | OpinionQA, 60 US groups | Misalignment on par with the Democrat-Republican gap on climate; persists after steering | abstract |
| Durmus, GlobalOpinionQA (2306.16388) | arXiv 2023 | Cross-national surveys | Default answers resemble USA, Europe, S. America; country prompts can yield stereotypes | abstract |
| Dominguez-Olmedo (2306.07951) | arXiv 2023 | 43 LLMs, US Census survey | After removing ordering bias, answers trend to uniform random | abstract |
| Tjuatja (2311.04076) | arXiv 2023 | 9 models, response biases | RLHF models least human-like; sensitive to changes that do not move humans | abstract |
| Rupprecht (2507.07188) | arXiv 2025 | 9 LLMs, WVS, 167k interviews | All show recency bias; paraphrase-sensitive | abstract |
| Li, Das Man (2507.02919) | arXiv 2025 | GPT-4, Llama 3.1, ANES 2020 | Severe homogenization | abstract |
| Taday Morocho (2602.18462) | arXiv 2026 | 70k respondent-item cases, WVS | Persona prompting often degrades alignment | abstract |
| Chen, Zhu, Zheng (2607.26348) | arXiv 2026 | 4 models, GSS and WVS | No LLM beats best baseline per individual; see below | full text |
| Rennard (2608.23005) | arXiv 2026 | 21M distributions, Pew ATP, 8 models | One identity feature carries the persona; a third adds almost nothing | abstract |
| Ozkan (2607.18310) | arXiv 2026 | WVS Turkey, 2,414 respondents | Concentration 0.36 to 0.69, entropy 1.46 to 0.77; fix overshoots (SD ratio 0.4-0.56 to 1.26-1.37) | abstract |
| Jang (2607.25292) | arXiv 2026 | Instruction-tuned models | Same persona gives same answer on over half of items; describing the distribution more than halves the error | abstract |
| Kumagae (2610.30900) | arXiv 2026 | Respondent coverage gap, 6 LLMs | Every LLM worse than a Gaussian copula at covering real respondents | abstract |
| Lukauskas (2608.14606) | arXiv 2026 | 37 LLMs, n = 263 employees | Best LLM level with a copula that has no LLM; see below | full text |
| Chen, Wang, Bhatia (NHB 2026) | Nature Human Behaviour | 67,201 people, 74 countries, 20 LLMs | Title: "weak proxies" for economic preferences | abstract |
| Ku (2607.03091) | arXiv 2026 | TEDS 2024, open models | 52% on unseen items, within 6 points of a random forest | abstract |

**Chen, Zhu, Zheng (full text).** Individual accuracy on GSS: best LLM 0.589 against 0.568 for
the question marginal and 0.622 for a logistic model; on WVS the best LLM scored 0.277 against
0.348 for the marginal. Aggregate fit is good if the model is asked for a distribution (JS
divergence 0.011-0.023 on GSS, against 0.056-0.090 when asked for one answer). Models
over-determine demographics: on one GSS item political views explain about 1.5% of real variation
and up to 67% of the model's. On a segment-targeting task the gap between segments was inflated
2-4x, the wrong segment was chosen in 50-72% of cases, and a non-existent split appeared in up to
41% of cross-cultural questions. A bigger model did not help.

**Lukauskas (full text, v1 of the preprint).** A held-out human ceiling of PSS 0.825; a Gaussian copula 0.688; the
best LLM 0.714. An ensemble that averaged the LLMs fell to 0.305, below every individual LLM,
because averaging removed the persona signal. Conditioning a statistical baseline on the same
profile fields did not help either. Version note: the abstract text has changed between arXiv
versions (v1 reported copula 0.69 against best LLM 0.71; the latest abstract reports 0.82 against
0.81); the conclusion is the same in both.

**Reading.** The positive 2022 result was one model on US political attitudes with rich
backstories. Wider audits find the same pattern: the model knows the average view of well-covered
topics and loses spread and structure. Analytic choices also move conclusions: 252 configurations
of the same silicon-sample design gave human-silicon agreement from poor to good, and re-running
Argyle's third study with 66 alternatives gave r = .23 to .84 (Cummins 2025, 2509.13397,
[abstract]). Reliability studies suggest population-level results stabilise only around 50-100
simulated individuals and that systematic bias is not reduced by more coverage (Wang, ReliMap
2609.25066 [abstract]). A panel of 5-30 teammates is below that range.

Counter-evidence worth stating: some work is more positive. Persona agents grounded in retrieved
real histories improve distribution alignment for stable attitudes (Jia 2605.10659 [abstract]); a
Chilean survey study found F1 above 0.90 on trust items with large item-to-item variation
(Gonzalez-Bustamante 2509.09871 [abstract]). Both are single-topic or single-country results with
real survey data behind the personas.

## 2. Replicating human-subject experiments

| Paper | Venue, year | What | Key number | Read |
|---|---|---|---|---|
| Aher, Turing Experiments (2208.10264) | arXiv 2022 | Ultimatum Game, Garden Path, Milgram, Wisdom of Crowds | First three replicated; "hyper-accuracy distortion" in the fourth | abstract |
| Horton, Homo silicus (2301.07543) | arXiv 2023 | Classic economic experiments | Qualitatively similar; differences "generative" | abstract |
| Cui (2409.00128) | Nature Comput. Sci. 2025 | 156 experiments, 3 LLMs | Main effects 73-81%, interactions 46-63%; effects 2-3x | full text |
| Ashokkumar, Hewitt (Nature 2026) | Nature 2026 | 70 preregistered survey experiments, 469 effects, 119,330 people | Authors report accurate predictions; sizes overestimated (secondary sources) | abstract |
| Lippert (RSOS 2024) | Royal Soc. Open Sci. 2024 | GPT-4 forecasts of one study | r = 0.89 vs 0.87 for 119 experts | abstract |
| Li and Ji (2604.02458) | arXiv 2026 | 59,508 people, 62 countries, 3 replications | Realism and effect accuracy weakly related | full text |
| Kolluri, Socrates (2509.05830) | arXiv 2025 | Fine-tuning on 210 experiments | 26% better distributional alignment on unseen studies | abstract |
| Chen, Hu, Lu (2504.01167) | arXiv 2025 | 276 field experiments | 78% accuracy; weaker on ethnicity, norms, ethics | abstract |

**Cui (full text).** Replication dropped where race or gender were varied (GPT-4 main effects 41.5%
with race variables against 76.8% without). Effects were larger because between-condition
differences grew (+147% for GPT-4) while within-condition spread shrank (-45%). Direction agreed
with humans for 79.7% of main effects. Exposure to the original papers (pre/post 2022, citations)
did not explain results. Cautions: scenario-based vignette studies only; 1:1 sample matching.

**Li and Ji (full text).** Models reproduced attitudinal outcomes reasonably, but descriptive
fit did not predict causal accuracy; the divergence was larger for behavioural outcomes, where the
models imposed a tighter attitude-to-action link than people show, and an instruction to
decouple them did not fix it.

**Reading.** Directional prediction of published effects is the strongest positive finding in
the whole literature. Its limits matter for teamsim: it was shown on text vignettes, in
well-studied domains, with effects inflated and sensitive topics weaker. Teamsim's "would your
team adopt this" is a behavioural outcome on a novel stimulus, which is where the evidence is
weakest.

## 3. Digital twins and individual-level simulation

| Paper | Venue, year | Key number | Read |
|---|---|---|---|
| Park, Self-Report Agents (2411.10109) | arXiv 2024 | 1,052 people. GSS normalized accuracy 0.83 (interview), 0.82 (survey), 0.86 (both), 0.74 (demographics) | full text |
| Toubia, Twin-2K-500 (2505.17479) | arXiv 2025 | 2,058 people, about 500 questions, retest wave | abstract |
| Peng, Funhouse Mirrors (2509.19088) | Science Advances 2026 | 19 studies, 164 outcomes. Mean r = 0.197; accuracy 0.748 | full text |
| Wang and Siu (2603.29890) | arXiv 2026 | 51 knowledge workers, 4 AI concepts, 3,060 responses. Accuracy 0.300 vs 0.446 human-human | full text |
| Jia (2605.10659) | arXiv 2026 | LISS panel; fails to recover multivariate structure | abstract |
| Wang, substitutability (2609.07987) | arXiv 2026 | Twins reproduce average effects, say little about who differs | abstract |
| Deng (2609.29143) | arXiv 2026 | Twins from AI interviews beat demographics-only, not static interviews | abstract |
| Ye, BDE profiles (2611.08730) | arXiv 2026 | Better structure gives about 1-1.4 points | abstract |

**Park (full text).** Normalising by each person's own retest consistency (79.5% on GSS) is the
right idea and teamsim should copy it. The same paper shows limits: Big Five normalized
correlation 0.80 for interview agents and economic-game normalized correlation 0.66, but a
construct-level table lists per-game correlations of 0.11, 0.08, 0.03, -0.05 and 0.10 (the
passages do not say which agent variant that table covers, so read it as a caution, not a
headline). Cutting 80% of the interview kept 0.79 on GSS.

**Peng (full text).** Full-persona twins reached r = 0.197 against 0.145 for demographics only,
0.080 for an empty persona, and 0.001 for random. Twin and human means differed significantly on
64% of outcomes; the mean gap was 0.35 SD. Distortions: insufficient individuation, stereotyping,
representation bias, ideological bias and hyper-rationality (twins show perfect knowledge, miss
attraction and compromise effects, but show classic effects that are in the training corpus, which
is leakage). The best of several models and temperatures reached r = 0.232. The authors suggest
twins are better treated as hyper-rational, well-informed advisors than as clones.

**Wang and Siu (full text).** The most relevant paper for product use: agents were
"distribution-calibrated but identity-imprecise". Interview agents got 67% of the human-human
accuracy; the no-information agent got 57% and collapsed to one answer (6 on a 7-point scale, 8
on NPS). Interview agents were the only design reproducing low scores. Themes matched; texture,
nuance and voice did not. N = 51 knowledge workers, one product area, LLM judges with Cohen's
kappa 0.53.

## 4. Known distortions

- **Homogenization and misportrayal.** Wang, Morgenstern, Dickerson 2402.01908 [abstract]:
  3,200 participants, 16 identities, four LLMs; models both misportray and flatten groups. Li
  2507.02919; Rennard 2608.23005.
- **Caricature.** CoMPosT, Cheng 2310.11501 [abstract]: GPT-4 simulations of political and
  marginalised groups are most susceptible to caricature (individuation and exaggeration).
  Chen, Zhu, Zheng's over-determination finding is the same effect measured on survey data.
- **Positivity.** Salecha (PNAS Nexus 2024, 2405.06058) [abstract]: when LLMs infer they are being
  assessed they shift Big Five answers by about 1 human SD toward the desirable end. Li 2608.24912
  [abstract]: 18 models lean to the kinder answer, bias grows with size, and aligned models cannot
  play less kind people. Weeber 2610.22409 [abstract]: vignettes reduce social desirability in
  humans but not in LLMs.
- **Acquiescence.** Lukauskas 2608.14606 [full text, v1]: +0.84 SD acquiescence shift; fabricated
  mediation effects on 3 of 10 null paths (the latest abstract says 4 of 7).
- **WEIRD skew.** Durmus 2306.16388; Sen 2511.01864 [abstract]: a review of 211 papers found 29%
  report positive conclusions, over a third define no target population, and of those that do,
  most study only the US.
- **Ethical and epistemic critiques.** Lin, Six Fallacies (AMPPS 2025, 2402.04470) [abstract]
  recommends treating LLMs as simulation tools validated against human data, not replacements.
  Kapania 2409.19430 [abstract]: 19 qualitative researchers judged LLM participants to foreclose
  consent and agency and to lack contextual depth. Anthis 2504.02234 [abstract], a position paper
  by 8 authors, argues simulations can already serve pilot and exploratory studies, and names
  context-rich prompting and fine-tuning as promising.
- **Miklian 2603.00059 [abstract]:** five LLMs against a human survey of 420 Silicon Valley
  developers: plausible, harmonised results, none captured the counterintuitive findings, and the
  deviations clustered so that the human data was the outlier. Nearest study to teamsim's users.

## 5. Synthetic users for product, UX and market research

| Paper | Year | Compared with humans? | Result | Read |
|---|---|---|---|---|
| UXAgent 2504.09407 | 2025 | No; 16 UX researchers judged it | Praised, with concerns | abstract |
| Zhong, Synthetic CW 2512.03568 | 2025 | Yes, 10 humans, 2 apps | See below | full text |
| Sun 2509.21501 | 2025 | Yes, 40 humans, a shopping assistant | Action patterns aligned; similar design feedback; agents explored more | abstract |
| AgentA/B 2504.09723 | 2025 | Real shopping behaviour, 1,000 agents | "Can emulate human-like patterns" | abstract |
| Maier, SSR 2510.08338 | 2025 | Yes, 57 concept tests, 9,300 people | 90% of retest ranking correlation | full text |
| Wang and Siu 2603.29890 | 2026 | Yes, 51 people, 4 concepts | Population calibrated, individually imprecise | full text |
| Pandey 2607.24649 | 2026 | Yes, 94 people, 3 concepts | Simulated reasons often echo the concept board | abstract |
| Tsai 2609.25677 | 2026 | Six human visual-marketing effects | No setting reproduced more than 2 of 6 | abstract |
| Moon 2606.09013 | 2026 | Yes, a non-public 2010 noodle choice experiment | For purchase quantity no model beat a baseline that matches the pooled human distribution | abstract |
| Maiorano 2608.13563 | 2026 | Proxy corpora only | Estimates unstable under resampling | abstract |

Lead, not cited as evidence: the Brand, Israeli and Ngwe working paper on willingness to pay
(first "Using GPT for Market Research", later "Using LLMs for Market Research"). I could not
retrieve its text. A search summary says the latest revision finds willingness-to-pay estimates
sometimes close to human studies, often inaccurate and occasionally of the wrong sign; verify
before relying on it.

**Zhong (full text).** 10 humans and 16 LLM runs (GPT-4, Gemini 2.5 Pro) on two mobile apps.
Completion: humans 88.2%, GPT 100%, Gemini 97.2%. Steps: humans 10.4, LLMs 7.5. Issues per run:
humans 7.5, GPT 0.6, Gemini 0.5; humans together found 10 failure points, all LLM runs together
3. A follow-up prompt that asked for failure points with the walkthrough history consistently
predicted the human-found ones; without history it was less consistent. The authors note their
own prompt may have made the model more rational.

**Maier, SSR (full text).** 57 surveys of personal-care concepts, 150-400 people each. Mean human
purchase intent was 4.0 with SD 0.2 across concepts, so the concepts barely differed. Direct
Likert ratings gave unrealistic distributions; textual answers mapped by embedding similarity
reached KS similarity 0.88 and 88-90% of the retest correlation ceiling, beating a LightGBM
trained on half the surveys (65%). Limits stated by the authors: reference statements were hand
tuned on these 57 surveys, gender, region and ethnicity patterns were not replicated, and the
authors are from a company that sells synthetic research (inference: conflict of interest;
preprint).

**Reading.** The favourable results are for concept ranking among similar concepts and for
population-level distribution; the unfavourable ones are for individual prediction, stimulus
reasoning, and novel or sensitive stimuli. For defects, there is one signal worth building on:
models walking an interface raised few issues unprompted, but prompted for failure points they
matched the human-found ones.

## 6. Methods that improve fidelity, and by how much

| Method | Evidence | Gain | Needs human data? |
|---|---|---|---|
| Rich grounding (interviews, histories) | Park 2024 [full text] | 74% to 83-86% of retest on GSS | Yes, per person |
| Same, product concepts | Wang and Siu [full text] | Only the low-score tail improved; no-info agent close on accuracy | Yes |
| Fine-tune on human responses | Kolluri 2509.05830; Choi 2606.28963 [abstract] | +26% alignment on unseen studies; small pilot samples help | Yes |
| Elicit text then map, or ask for the distribution | Maier [full text]; Jang; Meister 2411.05403 [abstract] | KS 0.88; error halved | No (SSR needs reference statements) |
| Post-hoc calibration | Fan 2604.07513 [abstract]; Persson 2606.17165 [abstract] | 46-57% lower distribution error; raw LLM recovered 39% of a real A/B effect | Yes |
| Ensembles and mixtures | Lukauskas [full text]; Terwiesch 2607.27553 [abstract] | Averaging responses hurt (PSS 0.305); pooling vendors raised idea diversity | No |
| Temperature | Pavlovic 2411.10080 [abstract]; Peng [full text] | Small, model-dependent; best twin setting was temperature 0 | No |
| Persona variables | Hu and Collier 2402.10811 [abstract] | Persona variables explain under 10% of annotation variance | No |

Two points on ensembles. Averaging many simulated respondents removes the individual signal
(Lukauskas); but combining models or prompts to generate *ideas* raises diversity (Terwiesch,
abstract), so the answer depends on whether the output is an answer or a list of issues.
Verbalized-sampling style fixes overshoot (Ozkan). The honest summary is that no method removes
the need for real human data; the methods trade bias for variance.

## 7. Measurement

What the literature uses, and what each costs:

| Measure | Source | What it checks |
|---|---|---|
| Individual accuracy against non-LLM baselines | Chen, Zhu, Zheng [full text]; Lukauskas [full text] | Does the model add information beyond marginals |
| Accuracy normalised by human retest | Park [full text]; Maier [full text] | Ceiling set by human noise |
| Distribution distance (JS, KS, Wasserstein) | Chen, Zhu, Zheng; Maier; Wang and Siu | Aggregate match |
| SD ratio, entropy, concentration | Ozkan [abstract]; Peng [full text] | Collapse or overshoot |
| Respondent coverage gap | Kumagae [abstract] | Whether simulated people cover real ones |
| Stereotyping index (eta squared gap) | Chen, Zhu, Zheng [full text] | Over-determination by identity |
| Self-correlation distance | Libovicky 2602.04033 [abstract] | Whether answer structure is human-like |
| Decision impact (gap inflation, wrong-segment rate) | Chen, Zhu, Zheng [full text] | Whether a decision would flip |
| Realism vs causal accuracy, separately | Li and Ji [full text] | Realism does not certify effects |
| Surrogacy falsification test | Persson 2606.17165 [abstract] | Whether LLM effect can stand in for human effect |
| Detectability (classifier AUC) | Lukauskas [full text] | Whether text is separable from human |
| User-Sim Index | Zhou 2026 [full text] | Behaviour, calibration and feedback alignment |
| Downstream utility | Suh 2605.09808 [abstract] | Training against a role-play simulator gave 51% win rate against the base, a fine-tuned simulator 58% (283 participants) |

On counterfactual validation (does the simulator tell good from bad?): the relevant evidence is
indirect. The SSR concept-ranking result is the closest (ranking among concepts that differ by
about 0.2 points), the visual marketing study shows effects not reproduced (Tsai [abstract]),
and the A/B surrogacy paper says an LLM A/B test "is correct only by assumption" and recovered
39% of the human effect when uncalibrated (Persson [abstract]). I searched for studies that
compare simulated verdicts on deliberately good and bad products with real outcomes and found
none; treat this as a gap, not as evidence of failure.

## Implications for teamsim

**Answer to ADR 0003.** Simulated feedback can meet the bar as written in a restricted form:
a hypothesis generator for defects and confusions, scored on planted ground truth, with
diversity and sycophancy reports and a human-data comparison only for the engine on proxy tasks.
It cannot meet a bar of predicting real team reactions, and should not claim to.

**What to build (ordered by evidence).**

1. **Planted-defect recall first.** Plant known defects or confusions in the product description
   or workspace. Score how many teammates raise them unprompted and when prompted, plus invented
   ones (false alarms). Support: Zhong shows the capability exists (prompted recall of human
   failure points) and the gap without prompting (0.5-0.6 vs 7.5 issues). Prompt with history
   (the "with context" variant in Zhong). This is teamsim's own contribution, not from the
   literature.
2. **A bad-product control and a known-worse variant in every feedback run.** A product with a
   deliberate, obvious flaw; or two versions where one is planted as worse. Pass if the panel
   rejects the bad one and ranks the worse one lower. This is the sycophancy gate and the only
   available discrimination test. Support: Zhou 2026 (uniform positivity), Chen 2026 (halved
   resistance), Salecha, Li 2608.24912.
3. **Behaviour personas, not demographic ones.** Vary patience, vagueness, reluctance, role and
   expertise. Do not condition on gender, race, age or nationality. Support: Taday Morocho, Rennard,
   Chen, Zhu, Zheng (2-4x over-determination), Wang, Morgenstern, Dickerson, and the Sim2Real "easy
   mode" results.
4. **Text first, never a number from the model.** Collect free text and, where a score is needed,
   map it with a fixed rubric or reference statements (Maier). Do not report means of model-given
   ratings.
5. **No aggregate claims.** A panel of 5-30 teammates is below the 50-100 where population-level
   results stabilise (Wang, ReliMap, abstract). Report counts of teammates, never percentages
   of "teams".
6. **Run-to-run stability as the ceiling.** Run each feedback task at least twice with different
   seeds and report agreement; treat it like human retest in Park and Maier (normalise by it).
   Inference: this is a cheap stand-in for human test-retest.
7. **A no-LLM baseline beside every result.** Scripted teammates (the run-1 default) serve as the
   baseline against which any model-written feedback must show added information (Chen, Zhu,
   Zheng; Lukauskas).
8. **Optional human check.** Let the user paste 3-20 real responses and report rank agreement and
   spread ratio as a check on the panel. Do not apply a statistical correction, because the
   assumptions (missing at random, a full invitation frame) are not met by a solo builder
   (Tigre, Hullman).
9. **Use only text-scale metrics that stdlib code can compute:** JS divergence, KS, SD ratio,
   entropy, Spearman or Kendall rank correlation, bootstrap intervals. No heavy dependency is
   needed, which keeps the stack decision independent of the feedback feature.

**Candidate thresholds.** None of these comes from a human validation of teammates; they are
design choices, each with the source it leans on.

| Measure | Candidate bar | Leans on |
|---|---|---|
| Spread ratio (simulated SD over human SD, on proxy-task items) | Between 0.8 and 1.25 | Collapse seen at 0.4-0.56 and overshoot at 1.26-1.37 (Ozkan); within-person SD 0.79 vs 1.19 (Lukauskas) |
| Stance entropy across teammates with distinct assigned stances | Not below 70% of the assigned entropy | Entropy fell from 1.46 to 0.77 under collapse (Ozkan); the 70% is my proposal |
| Planted-defect recall vs a no-persona prompt | Must exceed the baseline, with counts shown | Persona panels often do not beat plain prompts (Wang, Peng) |
| Bad-product control | Rejected by a majority of the panel in at least 90% of repeated runs | Uniform positivity (Zhou); the 90% mirrors the run-1 proposal, not a literature figure |
| Run-to-run agreement | Report; pass at 0.8 or above on rank agreement | Retest normalisation (Park, Maier); the 0.8 is a proposal |
| Proxy-task attainment (Twin-2K-500, retest-normalised) | Report vs the no-persona prompt and a demographic lookup; no bar | Chen, Zhu, Zheng; Park |

Rates are hidden when fewer than 10 events back them (the run-1 rule).

**What to avoid.**

- Population claims, adoption forecasts, effect sizes or percentages from the panel.
- Demographic personas and "representative team" language.
- LLM-as-judge without calibration on hand-labelled lines (the Wang and Siu judges reached only
  kappa 0.53).
- Averaging many simulated answers into a "consensus" (Lukauskas ensemble result).
- Treating a good distribution match as proof of a good conclusion (Li and Ji).
- Evaluating a bot only against cooperative scripted or LLM users: Zhou 2026 and Chen 2026 show
  this inflates success.

**Claims that must never be made.**

1. "Simulated teammates predict how real teams will react."
2. "X% of teams would adopt or like this."
3. "The simulated feedback is validated" without naming the proxy task, the data and the baseline.
4. "This teammate represents a real person, role-holder or demographic group."
5. "A bigger or newer model makes the feedback more reliable" (not supported by Zhou, Chen, Zhu,
   Zheng, Lukauskas 2610.14912).
6. Any ranking of products as a verdict. Rankings are hypotheses to check with real people.
7. That simulated praise is evidence of quality (sycophancy is the default).

Every output carries the label "simulated, unvalidated hypotheses" and the counts, seeds,
model id and baseline.

**Tie to open decisions.**

- *Model-free default vs local model:* The literature supports keeping the scored tests model-free
  (scripted adversarial behaviour avoids the easy-mode problem if the scripts include impatience,
  vagueness and reluctance, per Zhou). A model is needed only for free-text feedback and
  defect-finding. Capability does not buy fidelity (Zhou, Chen, Zhu, Zheng, Lukauskas 2610.14912),
  so a small local model is not obviously worse for this; inference, to be tested with the
  planted-defect recall.
- *v0.1 actions:* Chat-only is enough for planted-defect recall. Task and issue handling add
  behaviour the literature does not cover; no source here argues for repo actions.
- *First user:* A builder of team-facing software uses simulated feedback for defect-finding; the
  closest human study is the developer survey of Miklian (agree on harmonised, conventional
  answers).
- *Scoring:* Add a feedback block with the six measures above; keep it separate from the scored
  tests so a weak feedback result cannot change the ground-truth score.
- *Presets:* Presets vary behaviour and role, not demographics; ship with the planted-defect and
  bad-product cases per preset.

## Open problems

- No open data of real teams reacting to a software product or bot. Teamsim could publish its own
  small dataset only with consent and no real messages (project privacy rule); until then, the
  engine is only checkable on proxy tasks.
- Whether planted-defect recall transfers from UI walkthroughs (Zhong, 10 humans, 2 apps) to
  team-chat bots is untested.
- No counterfactual study of good against bad products with real outcomes. Teamsim can measure
  its own sensitivity (planted-worse variant) but not external validity.
- Whether a small local model matches a hosted one on defect recall: teamsim can measure it.
- How much hallucinated defects (false alarms) cost in practice; Zhong did not report false alarms.
- How strong the sycophancy is for persona-specific agreeableness; teamsim can measure it with
  paired good and bad products per agreeableness level.
- The effect of recorded replay on measured stability (replay hides sampling variance).
- Most 2026 results here are preprints; several are by single authors or companies and none of
  the product-research results is replicated.

## Where this disagrees with the run-1 notes

- The prior-art note cites the "Digital twins are funhouse mirrors" result with venue unverified.
  It is Science Advances 2026 (doi 10.1126/sciadv.aeh8260), and the numbers (r = 0.20; 19 studies;
  164 outcomes) hold in full text.
- The run-1 note says synthetic responses are flat and compressed. That holds for direct numeric
  elicitation; the SSR paper shows the compression is largely an elicitation artifact (KS 0.88
  with text-mapped ratings), and Chen, Zhu, Zheng show that asking for a distribution removes
  most of the aggregate gap. The persistent problems are at the individual and subgroup level and
  in over-determination, which the notes describe less. The planned diversity report is still
  right, but a diversity pass does not imply a validity pass (Li and Ji).
- The personas note proposes "teammates keep assigned stance in at least 90% of pushback
  sequences". No literature figure supports 90%; I keep it as a proposal alongside the others.
- The personas note treats persona agents as a way to improve realism. The evidence is mixed:
  rich grounding helps individuals a little (Park, Peng 0.197 vs 0.080 for an empty persona) but
  demographic personas can degrade results (Taday Morocho) and over-determine (Chen, Zhu, Zheng).
- The note's "Plausible but Not Valid" numbers differ slightly from the latest abstract (R2 -0.14
  vs -0.18 in v1; copula and best-LLM scores swapped order between versions). Cite the version.
- ADR 0003 stands. Its three conditions can all be measured; its "comparison with published human
  results" is only available on proxy tasks, as the notes already say.

## Sources

All read 2026-11-11. Link form https://arxiv.org/abs/ID unless a DOI is given. [F] = full text,
[A] = abstract only.

Survey and silicon-sample fidelity
- Argyle et al., Out of One, Many, 2022, arXiv 2209.06899 [A]
- Santurkar et al., Whose Opinions Do Language Models Reflect?, 2023, arXiv 2303.17548 [A]
- Durmus et al., Subjective Global Opinions in Language Models, 2023, arXiv 2306.16388 [A]
- Dominguez-Olmedo et al., Questioning the Survey Responses of LLMs, 2023, arXiv 2306.07951 [A]
- Tjuatja et al., Do LLMs exhibit human-like response biases?, 2023, arXiv 2311.04076 [A]
- Rupprecht et al., Prompt Perturbations Reveal Human-Like Biases, 2025, arXiv 2507.07188 [A]
- Li et al., ChatGPT is not A Man but Das Man, 2025, arXiv 2507.02919 [A]
- Ball et al., Human Preferences in LLM Latent Space, 2025, arXiv 2502.16280 [A]
- Gonzalez-Bustamante et al., Emulating Public Opinion (Chile), 2025, arXiv 2509.09871 [A]
- Cummins, The threat of analytic flexibility, 2025, arXiv 2509.13397 [A]
- Taday Morocho et al., Reliability of Persona-Conditioned LLMs, 2026, arXiv 2602.18462 [A]
- Libovicky, Credibility of Evaluating LLMs using Survey Questions, 2026, arXiv 2602.04033 [A]
- Chen, Zhu, Zheng, When Synthetic Users Fail, 2026, arXiv 2607.26348 [F]
- Rennard and Xypolopoulos, Intersectional Synthetic Identities, 2026, arXiv 2608.23005 [A]
- Ozkan, Distribution-First Population Simulation, 2026, arXiv 2607.18310 [A]
- Jang et al., Instruction-Tuned LMs Cannot Sample from Distributions They Can Describe, 2026, arXiv 2607.25292 [A]
- Meister et al., Benchmarking Distributional Alignment, 2024, arXiv 2411.05403 [A]
- Pavlovic and Poesio, Effect of Temperature on Alignment, 2024, arXiv 2411.10080 [A]
- Kumagae and Kaneko, Silicon Samples Match the Answers but Not the Respondents, 2026, arXiv 2610.30900 [A]
- Lukauskas and Sarkauskaite, Plausible but Not Valid, 2026, arXiv 2608.14606 [F]
- Lukauskas and Sarkauskaite, Probable but Not Valid, 2026, arXiv 2610.14912 [A]
- Ku et al., Silicon Sampling via Cross-Survey Transfer, 2026, arXiv 2607.03091 [A]
- Jia et al., When Can Digital Personas Reliably Approximate Human Survey Findings?, 2026, arXiv 2605.10659 [A]
- Wang et al., Understanding Reliability in LLM-based Human Behavior Simulation (ReliMap), 2026, arXiv 2609.25066 [A]
- Chen, Wang, Wang, Bhatia, Simulated responses from LLMs are weak proxies for human economic preferences across 74 countries, Nature Human Behaviour 2026, https://doi.org/10.1038/s41562-026-02611-4 [A]
- Hu and Collier, Quantifying the Persona Effect, 2024, arXiv 2402.10811 [A]
- Miklian et al., Stochastic Parrots or Singing in Harmony?, 2026, arXiv 2603.00059 [A]

Experiments and digital twins
- Aher, Arriaga, Kalai, Using LLMs to Simulate Multiple Humans (Turing Experiments), 2022, arXiv 2208.10264 [A]
- Horton, Filippas, Manning, Homo Silicus, 2023, arXiv 2301.07543 [A]
- Cui, Li, Zhou, A large-scale replication of scenario-based experiments, Nature Computational Science 2025, https://doi.org/10.1038/s43588-025-00840-7 (arXiv 2409.00128) [F]
- Ashokkumar, Hewitt, Ghezae, Willer, LLMs can predict the results of social science experiments, Nature 2026, https://doi.org/10.1038/s41586-026-10742-x [A]
- Lippert et al., Can LLMs help predict results from a complex behavioural science study?, Royal Society Open Science 2024, https://doi.org/10.1098/rsos.240682 [A]
- Li and Ji, When simulations look right but causal effects go wrong, 2026, arXiv 2604.02458 [F]
- Kolluri et al., Finetuning LLMs for Human Behavior Prediction (Socrates), 2025, arXiv 2509.05830 [A]
- Chen, Hu, Lu, Predicting Field Experiments with LLMs, 2025, arXiv 2504.01167 [A]
- Park et al., LLM Agents Grounded in Self-Reports Enable General-Purpose Simulation of Individuals, 2024, arXiv 2411.10109 [F]
- Toubia et al., Twin-2K-500, 2025, arXiv 2505.17479 [A]
- Peng et al., Digital twins are funhouse mirrors, Science Advances 2026, https://doi.org/10.1126/sciadv.aeh8260 (arXiv 2509.19088) [F]
- Wang et al., When Can LLM Digital Twins Reduce Human Measurement?, 2026, arXiv 2609.07987 [A]
- Deng et al., AI-Moderated Interviews and Digital Twins Calibration, 2026, arXiv 2609.29143 [A]
- Ye et al., Structuring Survey Histories for LLM Digital Twins, 2026, arXiv 2611.08730 [A]

Distortions and critiques
- Wang, Morgenstern, Dickerson, LLMs that replace human participants can harmfully misportray and flatten identity groups, 2024, arXiv 2402.01908 [A]
- Cheng, Piccardi, Yang, CoMPosT, 2023, arXiv 2310.11501 [A]
- Salecha et al., LLMs show human-like social desirability biases, PNAS Nexus 2024, https://doi.org/10.1093/pnasnexus/pgae533 [A]
- Li et al., Analyzing and Correcting Benevolence Bias, 2026, arXiv 2608.24912 [A]
- Weeber et al., Social Bias or Social Desirability?, 2026, arXiv 2610.22409 [A]
- Sen et al., Missing the Margins, 2025, arXiv 2511.01864 [A]
- Lin, Six Fallacies in Substituting LLMs for Human Participants, AMPPS 2025, https://doi.org/10.1177/25152459251357566 [A]
- Kapania et al., Simulacrum of Stories, 2024, arXiv 2409.19430 [A]
- Anthis et al., LLM Social Simulations Are a Promising Research Method, 2025, arXiv 2504.02234 [A]

Product, UX and user simulation
- Lu et al., UXAgent, 2025, arXiv 2504.09407 [A]
- Zhong, McDonald, Hsieh, Synthetic Cognitive Walkthrough, 2025, arXiv 2512.03568 [F]
- Sun et al., Can LLM Agents Simulate Customers to Evaluate Agentic-AI Shopping Assistants?, 2025, arXiv 2509.21501 [A]
- Lu et al., AgentA/B, 2025, arXiv 2504.09723 [A]
- Maiorano, Proxy-Validated LLM UX Micro-Simulations, 2026, arXiv 2608.13563 [A]
- Moon et al., Beyond Averages: Human Survey Replication at the Distributional Level, 2026, arXiv 2606.09013 [A]
- Maier et al., LLMs Reproduce Human Purchase Intent via Semantic Similarity Elicitation, 2025, arXiv 2510.08338 [F]
- Wang and Siu, Interview-Informed Generative Agents for Product Discovery, 2026, arXiv 2603.29890 [F]
- Pandey and Jajoo, Reason-Mediated Behavioral Models, 2026, arXiv 2607.24649 [A]
- Tsai and Lai, Seeing Is Not Perceiving, 2026, arXiv 2609.25677 [A]
- Terwiesch et al., AI and Its Impact on Creativity and Diversity, 2026, arXiv 2607.27553 [A]
- Zhou et al., Mind the Sim2Real Gap in User Simulation, 2026, arXiv 2603.11245 [F]
- Chen, Simulated Customers Never Walk Away, 2026, arXiv 2606.20708 [A]
- Suh et al., Quantifying the Utility of User Simulators, 2026, arXiv 2605.09808 [A]

Methods and statistics
- Choi et al., Beyond the Mean: Three-Axis Fidelity, 2026, arXiv 2606.28963 [A]
- Wang et al., Can Fine-tuning LLMs on Small Human Samples Increase Heterogeneity, 2025, arXiv 2511.21218 [A]
- Fan et al., SYN-DIGITS, 2026, arXiv 2604.07513 [A]
- Tigre and Souto, When Can You Trust Your Synthetic Users?, 2026, arXiv 2609.13148 [A]
- Persson et al., Statistical Foundations of LLM-based A/B Testing, 2026, arXiv 2606.17165 [A]
- Hullman et al., This human study did not involve human subjects, 2026, arXiv 2602.15785 [A]
