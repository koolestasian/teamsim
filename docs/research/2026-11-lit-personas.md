# Personas, consistency, diversity and sycophancy: literature review (2026-11-11)

Scope: peer-reviewed and arXiv work on building simulated people with language models,
measuring whether they stay distinct, consistent and honest, and what small local models can do.
It deepens `2026-11-personas.md` (web and GitHub notes) with papers. Depth tags: [full text] means
I read passages of the paper; [abstract] means only the abstract. Most items are arXiv preprints;
the venue is named only where I saw it.

## Summary

1. **Persona prompts change self-description far more than behaviour.** Injecting an agreeableness
   persona moved self-reported agreeableness strongly (beta 3.6 to 4.4) but behaviour on a
   sycophancy task hardly at all (beta -0.05 to 0.32, mostly not significant). Across 18 models,
   questionnaire answers predicted behaviour no better than chance for small and mid-sized models
   (43-50% directional agreement). For teamsim: do not score a teammate with a personality
   questionnaire; score what it does, and let the script assign behaviour.
2. **Persona detail has weak or negative returns.** Persona variables explain under 10% of
   annotation variance in most subjective datasets, and prompting with them gives small gains
   (about 1 point where 9% was explainable). Richer personas moved internal representations
   together: embedding distance fell 54-59% as attributes were added, and two big persona
   corpora were less separated than plain age-and-gender personas. For teamsim: keep persona
   fields few and work-relevant; do not buy distinctness with longer biographies.
3. **Distinctness is limited by the model, not by the number of personas.** Population-level
   collapse is reported as universal across eight models, adding personas did not fix it, and the
   most faithful models gave the most polarised populations (Xiao et al., preprint, abstract).
   Aligned models answer many open questions with one semantic cluster (40-79% of questions on
   one benchmark; base model 1.0% vs instruct 28.5%). For teamsim: distinctness has to be written
   into the script (stances, style knobs, timing) and then measured, never assumed.
4. **Persona fidelity decays over long dialogues and reverts to the default assistant.** Over
   100+ rounds, seven models lost knowledge, style and in-character consistency, with BFI traits
   drifting toward the no-persona baseline; larger models drift less but still drift, and
   goal-oriented dialogue is worse. For teamsim: send persona plus a short recent window every
   call; never rely on a long history.
5. **LLM-played users are too cooperative, polite and uniform.** With 451 real participants
   against 31 simulators, only 1.0% of GPT-4o turns were short against 29.0% for humans, 49.0%
   were polite against 15.3%, and simulated users raised agent success above the human baseline.
   Better assistants did not make better simulators. For teamsim: a model-written teammate needs
   explicit style and friction controls, and human-looking chat is a measured property, not a
   default.
6. **Sycophancy is large in small models and is mostly installed before preference tuning.** In
   PARROT (22 models, 1,302 questions each, preprint), a false authority claim was followed 94% of
   the time by Qwen2.5-1.5B, 78.9% by Gemma-3-4B, 69.4% by Qwen2.5-7B, 35.9% by Qwen2.5-14B, and
   4-11% by the strongest hosted models. In debate, Qwen2.5-7B-Instruct held its stance 0.83 of 5
   turns against 4.90 for a 72B model (SYCON-Bench). One study finds sycophancy mostly present
   after supervised fine-tuning already. Prompt-only fixes vary: a plain anti-sycophancy
   instruction was modest, third-person framing helped more (SYCON), and a counterfactual
   reasoning prompt reached near zero in one preprint. For teamsim: make pushback tests mandatory
   for any model that writes teammate lines, and give the script, not the model, the right to
   disagree.
7. **Diversity metrics disagree, and fixed thresholds are weak.** One preprint shows a popular
   0.8 embedding-similarity cutoff is exceeded by 20-32% of pairs that express different ideas.
   A compact set (compression ratio, long n-gram repetition, Self-BLEU, BERTScore) has low
   internal correlation, so four numbers cover most of what lexical metrics see. For teamsim:
   report ratios against the scripted human-authored lines as a reference, not absolute cosines.
8. **Small models can write a line from a slot; they are weak at being the author.** Constrained
   decoding took 0.6B-4B models from 78.6-92.9% schema validity to 100% but left a semantic gap,
   and a hard schema can lower answer accuracy for sub-2B models (19.7% to 11.0%). Int4
   quantization at 8B raised same-answer probability by 5.1 points. For teamsim: use a 7-8B class
   model for one plain-text line per slot, validate against the planted fact, and measure
   diversity again on the exact quantised build.
9. **Activation steering is not a v0.1 tool.** Persona vectors, steering and personality sliders
   work on open models in papers, but effects vary by behaviour type, follow an inverted-U in
   strength, can lower answer quality and need model internals that hosted or Ollama-style
   endpoints do not expose. For teamsim: prompt and script first; note steering as research only.
10. **AI text stays detectable even after calibration.** On replies from X, Bluesky and Reddit
    users, nine open models of 4-8B (plus one 70B) were told apart from humans by a classifier at
    70-80% after the best calibration (87% or more before). Stylistic example lines and retrieved
    context helped; persona descriptions and fine-tuning did not; instruction-tuned models did
    worse than base models (PNAS). For teamsim: do not claim "indistinguishable from humans";
    give each teammate example lines, and claim measured style statistics against a stated target.
11. **Informal wording matters to the product, not only to realism.** Informal or ungrammatical
    queries cut a retrieval-augmented system's recall by up to 40.41% (relative) in one study
    (abstract only). For teamsim: style knobs are test inputs, and the prototype's realism-tax
    number has literature support.

## 1. Persona conditioning

Does prompting with a persona change behaviour, and which attributes matter?

| Paper | Venue/year | What was measured | Key number | Read |
|---|---|---|---|---|
| Quantifying the Persona Effect (Hu, Collier) | arXiv 2024 | Variance explained by persona variables in 10 subjective datasets; gains from persona prompting, 6 models, 600 items per dataset | under 10% variance; 70B model reaches 81% of the regression-achievable variance where persona matters (US survey, over 70% explained); when target R2 is below 0.1 predicted R2 often drops to zero | full text |
| How Well Do LLMs Capture Human Personality (Bhattacharyya) | arXiv 2026 | Persona richness vs separation and downstream accuracy | pairwise embedding distance fell from 14.38 to 5.90 (Qwen-72B instruct); email click-through accuracy 70.0% for age-gender vs 58.6% for auto-built customer profiles | full text |
| Reliability of Persona-Conditioned LLMs as Survey Respondents (Taday Morocho) | arXiv 2026 | 2 open chat models, over 70K respondent-item pairs, World Values Survey | persona prompting gave no clear aggregate gain and often hurt | abstract |
| How Far Do Persona Effects Generalize (Zhou) | arXiv 2026 | 57 attributes, 7 pairs of 7-9B models | effects are predictable but not portable across models or rewording | abstract |
| Persona Hub (Ge) | arXiv 2024 | 1 billion web-derived personas for data synthesis | a source of perspectives, not a fidelity study | abstract |

What this shows. Persona prompting gives modest, real gains, mainly where human variance is
caused by the persona variables and humans disagree only a little (Hu and Collier). Where persona
variables explain little, prompting does little. Bhattacharyya reports that adding attributes
shrinks the distance between persona embeddings, and that two corpora built on rich attribute
schemas (Nemotron, Persona Hub) were less separated than two-attribute personas (mean distance
5.25 and 6.84 against 14.38 on one 72B model; 1.80 and 3.84 against 7.81 on an 8B model).
Narratives over 2,000 tokens did not consistently help. Caveats: the distance is measured on
final-layer hidden states, not on text a user sees; the downstream task is a binary engagement
call (chance is 50%); it is a single-group preprint. Hu and Collier test classification of
annotations, not free-form chat. So these results are a warning about long personas, not a
measurement of what teamsim's chat lines would do.

Inference for teamsim (mine, not from a paper): the persona fields that carry behaviour should be
the ones the script can act on (role, stance, style knobs), because the model barely uses the rest.

Structured versus narrative format. Evidence is indirect and mixed; none of it is on workplace
chat.
- Hu and Collier report robustness to ordering and wording of persona variables; Zhou et al.
  report that rewording breaks transfer of persona effects between models. [abstract / full text]
- PILOT (Cisar et al., arXiv 2025) [abstract]: three models (Mistral Large 2, DeepSeek-R1,
  LLaMA 3.3 70B), 25 synthetic personas; schema-based steering (numeric psycholinguistic profiles)
  reduced repetitive "persona-sounding" output (silhouette 0.098 to 0.237, topic purity 0.773 to
  0.957) but natural-language personas kept more lexical diversity. A hybrid balanced the two.
- Three-tier persona vector (Khedar et al., arXiv 2026) [abstract]: 23 dimensions (demographics,
  12 behavioural traits, 5 emotional states that shift with the scenario), 64,698 conversations;
  agent goal achievement spread by 15.8 points across personas. Shows structured traits produce
  measurably different simulated-user behaviour on tool-use tasks, with a company-internal
  evaluation set.
- The Prompt Makes the Person(a) (Lutz et al., arXiv 2025) [abstract]: five open models, 15
  groups; interview-style prompting and name-based priming reduced stereotyping, and OLMo-2-7B beat
  Llama-3.3-70B.
- Pay What LLM Wants (Choi et al., arXiv 2025) [abstract]: with 522 real human personas, rebuilt
  personal narratives and retrieval did not beat simple prompting.
My reading (inference): a short structured record rendered to a few plain sentences plus 3-5
example lines is the best-supported default; whether the structured or narrative form is better
for team-chat wording is untested and teamsim can test it cheaply.

## 2. Personality induction and measurement

| Paper | Venue/year | What was measured | Key number | Read |
|---|---|---|---|---|
| Personality Traits in LLMs (Serapio-Garcia) | Nature Machine Intelligence 2025 | Reliability, validity and shaping of Big Five in 18 LLMs | validity stronger for larger and instruction-tuned models; traits shapeable by prompt | abstract |
| PersonaLLM (Jiang) | arXiv 2023 | GPT-3.5/4 personas, BFI plus story writing | humans perceive some traits at up to 80% accuracy, lower when told it is AI | abstract |
| The Personality Illusion (Han) | arXiv 2025 | Self-report vs behaviour, persona injection | questionnaire-to-behaviour agreement 45-62% by trait, CIs overlap 50%; small and mid models 43-50% | full text |
| Personality Without Persons? (Zierahn) | AIES 2026 | Psychometric validity, 264 LLMs from 50 families | between-model variance only 7-17%; four of five facets collapse (r at least .90) | abstract |
| Limited Ability of LLMs to Simulate Psychological Behaviours (Petrov) | arXiv 2024 | GPT-3.5/4 with generic vs demographic personas | generic personas acceptable for GPT-4; demographic personas gave poor psychometrics | abstract |
| TRAIT (Lee) | arXiv 2024 | 8K-item personality test for LLMs | prompting weak for some traits (high psychopathy, low conscientiousness) | abstract |
| BIG5-CHAT (Li) | arXiv 2024 | 100,000 dialogues; SFT and DPO vs prompting | training beat prompting on BFI and IPIP-NEO | abstract |
| Designing AI Agents with Personalities (Huang) | arXiv 2024 | BFI-2 prompts, risk and moral vignettes | personality-decision correlations reproduced in part; finer patterns diverged | abstract |

Han et al. [full text] are the most decision-relevant. Self-reported traits are stable and
instruction-tuning makes them more coherent, yet they predicted downstream behaviour (sycophancy,
risk-taking, honesty tasks) at chance for small and mid models; only a few large ones passed
(Claude 3.7 64%, GPT-4o 68%, Qwen-235B 82%, and only the last significantly). Persona injection
changed answers on the questionnaire (agreeableness beta about 3.6 to 4.4, p under .001) but the
matching behaviour (sycophancy) was mostly not significant. Zierahn et al. add that the Big Five
instruments do not separate models well and do not reproduce the human five-factor structure. Both
studies are about general model behaviour under a questionnaire or a task, not simulated
teammates; but they undermine "give the persona a Big Five profile and trust it".

For teamsim: if Big Five is used at all, treat it as a style hint for authors, not as a
measurable property of the simulated person. A behavioural probe (Section 3 and 5) is the test.

## 3. Consistency and drift

| Paper | Venue/year | What was measured | Key number | Read |
|---|---|---|---|---|
| Persistent Personas? (de Araujo) | arXiv 2025 | 7 models (4B-49B and Gemini 2.5), 9 personas, over 100 rounds | knowledge, style and consistency decline; traits regress to no-persona baseline; scale helps, does not fix | full text |
| Consistently Simulating Human Personas with Multi-Turn RL (Abdulhai) | arXiv 2025 | Three automatic consistency metrics validated on human labels | inconsistency cut by over 55% by RL fine-tuning | abstract |
| ContextEcho | arXiv 2026 | 57 long agentic coding sessions, 23 models | drift appears early; a one-shot anchor restores the persona | abstract |
| ANCHOR (Venkit) | arXiv 2026 | 2,008 conversations, 27 personas, 4 models | trajectory recall averages 44.4%; questionnaire retention disagrees with turn-level behaviour | abstract |
| StateTrack-Bench | arXiv 2026 | Constraint retention, 7 models, up to 50 turns | strict retention 62.4-100%; 88.6% of failures are drift, not forgetting; state anchoring recovers up to 24.4 points | abstract |
| Memory-Driven Role-Playing | arXiv 2026 | 12 LLMs, persona knowledge use | structured memory prompt lets Qwen3-8B match larger closed models | abstract |
| PersonaEval (Zhou) | arXiv 2025 | Can LLM judges identify the speaker | best LLM about 69%, humans 90.8% | abstract |
| Anonymous role-play benchmark (Peng) | arXiv 2026 | Famous vs anonymised characters | anonymising characters lowers scores; personality text helps | abstract |

de Araujo et al. [full text]: dialogues of 60k-110k tokens stayed inside each model's context
window, so the decay is not truncation. Fidelity moved toward the no-persona baseline rather
than random behaviour. The drop is larger in goal-oriented than in persona-directed dialogue,
which is the situation of a teammate asked to complete a task. Personas here are fictional
characters, not workplace roles, and the dialogues were model-generated, so transfer to short
team chat is untested. A common suggestion across these papers is re-anchoring the persona
and retrieving only relevant history (de Araujo, ContextEcho, StateTrack).

Li et al. (Measuring and Controlling Instruction Instability, Harvard, arXiv 2024) [full text of
the method sections] is the origin of the "within eight rounds" claim: two instructed chatbots
talk, and after each turn the agent is re-asked a probe question; LLaMA2-chat-70B and GPT-3.5
drifted within 8 rounds, with the share of attention on the system prompt falling across turns.
Their baseline fix of repeating the system prompt before each user turn is the cheap version of
what teamsim would do by re-sending the persona each call. Models are old (2023-24); newer ones
in de Araujo drift more slowly but still drift.

PersonaEval matters for how teamsim measures: LLM judges identify roles poorly, so a judge-based
consistency score would be weak evidence (see Section 8 for the alternative).

PersonaGym (Samuel et al., arXiv 2024, v5 2026) [full text] adds a benchmark and a warning on
size. It scores persona agents on five tasks (expected action, action justification, linguistic
habits, persona consistency, toxicity control) over 200 personas and 10,000 questions, with 10
models. Results: LLaMA-3-8B scored 4.49 against 4.36 for LLaMA-3.3-70B and 4.49 for GPT-4.1 (on
a 1-5 rubric, LLM-judged); one small hosted model scored lowest because it refused to adopt
personas; and "linguistic habits" (matching a persona's speech style) was the hardest task, with
most models below 4. The judge scores correlated with 5 human annotators at Spearman 75.1% on
average over 100 personas (Fleiss kappa 0.71), but correlations differed per task and model. The
authors also note that beyond 200 generated personas GPT-4o produced overlapping attributes,
which is direct evidence that a model-generated persona list stops being diverse. Limits: older
models in the main table, fictional or generic personas, LLM judges.

## 4. Diversity and homogenization

| Paper | Venue/year | What was measured | Key number | Read |
|---|---|---|---|---|
| Artificial Hivemind (Jiang) | arXiv 2025 | 26K open-ended prompts, repetition within and across models | models repeat themselves and each other | abstract |
| How Strong Is the Evidence? (Schaeffer) | arXiv 2026 | Re-analysis of the above | 20-32% of different-idea pairs exceed the 0.8 cutoff; prompting raises diversity | full text |
| The Alignment Tax (Liu) | arXiv 2026 | 10 samples per question, 3B-14B | 40-79% of questions give one cluster; base 1.0% vs instruct 28.5%; DPO stage localised | abstract |
| Understanding the Effects of RLHF on Generalisation and Diversity (Kirk) | arXiv 2023 | SFT vs RLHF | RLHF reduces output diversity | abstract |
| Revisiting LLM Homogeneity (Qiu) | arXiv 2026 | 25 metrics over 5 dimensions, 18 LLMs | embedding similarity tracks human meaning judgments worse (rho 0.417) than sentence matching (0.606), form not at all (0.140) | abstract |
| Standardizing Text Diversity (Shaib) | arXiv 2024 | Convergent validity of diversity scores | compression ratio, long n-gram repetition, Self-BLEU and BERTScore have low mutual correlation | abstract |
| Evaluating the Evaluation of Diversity (Tevet, Berant) | arXiv 2020 | Metrics vs human judgments | humans beat automatic metrics; decoding parameters mostly change form not meaning | abstract |
| Vendi Score (Friedman, Dieng) | arXiv 2022 | Eigenvalue-entropy diversity of any similarity matrix | effective number of distinct items; no reference set needed | abstract |
| Price of Format (Yun) | arXiv 2025 | Chat template tokens | diversity collapse persists at high temperature | abstract |
| BACo (Wang) | arXiv 2025 | Token-level routing between a base and its aligned model | 21.3% joint diversity-quality gain | abstract |
| Meta-Persona Anchoring (Fu) | arXiv 2026 | Self-chosen persona plus very high temperature, models under 20B | cosine similarity 0.85 to 0.65; weakly validated | abstract |
| Persona Collapse (Xiao) | arXiv 2026 | Coverage, uniformity, complexity over 8 LLMs | collapse universal; more personas do not help | full text |

Persona Collapse (Xiao et al., arXiv 2026) [full text of method and results]: 26 persona
dimensions, 1,144 screened personas, ten models (4B to hosted; the later abstract says eight),
BFI-44, moral reasoning and self-introductions, with 2,058 real human BFI responses as the
reference. Three diagnostics: Coverage (share of human behaviour archetypes reached), Uniformity
(Hopkins statistic, 0.5 is even) and Complexity (local intrinsic dimensionality). Findings: a
model can look diverse on one axis and degenerate on another (Qwen3-4B reached 80% coverage but
half the human complexity, 7.3 against 14.4); variation tracks coarse demographic stereotypes
more than the fine attributes specified; in free-text self-introductions, 29% of one model's
responses shared an identical template skeleton while 73% of assigned attributes were mentioned,
so personas are recited, not enacted. Persona-tuned role-play models lost coverage (0.64 to 0.49
across training stages for one 32B line). For teamsim: these population metrics need hundreds of
agents; with 6-8 teammates they are not computable, so use pairwise measures on a fixed set of
slots instead (inference). The template-skeleton rate is a cheap check worth borrowing.

Two readings of the hivemind result. The original paper reports strong within- and across-model
repetition; the critique [full text of the relevant sections] argues the null used (responses to
unrelated prompts, median cosine about 0.11) is too easy, so the 0.8 threshold sits at the
99.95th percentile of that null and says little; that no human baseline exists; that embedding
cosine has not been validated as a diversity instrument (anisotropy); and that cheap prompt
rewordings raised measured diversity across 12 topics and 15 models (quality under the rewordings
not checked). Both are preprints; the critique is more careful about baselines, the original has
the larger dataset. Both agree measured similarity depends on the comparison set. For teamsim that points to: compare model lines with the scripted,
human-authored lines for the same slot as the reference (inference).

The cause is mostly post-training (base vs instruct 1.0% vs 28.5% in one study, RLHF in another),
so mixing a base model into the pipeline (BACo) or using a less-aligned model for wording are
candidate tools but need a runtime that exposes both models.

Verbalized Sampling (Zhang et al., arXiv 2025, v3) [full text]: ask the model for several
candidate answers with probabilities and sample from them. Reported: 1.6-2.1x diversity over
direct prompting in creative writing, a 25.7% gain in human evaluation scores, recovery of 66.8%
of the base model's diversity, and, in a persuasion dialogue simulation (939 dialogues from a
human donation dataset), donation amounts closer to the human distribution. Two details matter
for teamsim. First, "more capable models benefit more", so the gain at 7-8B may be smaller than
the headline; the paper's dialogue test used large hosted models and a fine-tuned 8B baseline,
not a quantised local model. Second, text still read as more complex than humans (readability
stayed higher). The earlier note also cites an over-shoot in a survey study; together this says
tune it and measure it. Cost: one call returns several candidates; the script, not the model,
should pick which candidate to post (inference).

## 5. Sycophancy and agreeableness

| Paper | Venue/year | What was measured | Key number | Read |
|---|---|---|---|---|
| Towards Understanding Sycophancy (Sharma) | arXiv 2023 | 5 assistants, 4 tasks; preference data | matching user views raises preference; models trade truth for it | abstract |
| SYCON-Bench (Hong) | arXiv 2025 | Multi-turn flips, 17 LLMs | alignment tuning amplifies; third-person framing cuts up to 63.8% in debate | full text |
| ELEPHANT (Cheng) | arXiv 2025 | Social sycophancy, 11 models | face preserved 45 points more than humans; both sides affirmed in 48% | abstract |
| Too Nice to Tell the Truth (Shah) | arXiv 2026 | 13 models 0.6B-20B, 275 personas, 4,950 prompts | 9 of 13 show agreeableness-sycophancy correlation, r up to 0.87 | full text |
| PARROT (Celebi) | arXiv 2025 | 22 models, 1,302 questions each, false authority claim | follow rate GPT-5 3.6%, Qwen2.5-14B 35.9%, Qwen2.5-7B 69.4%, Qwen2.5-1.5B 94.0% (tables) | full text of tables |
| SWAY (Bhalla) | arXiv 2026 | Counterfactual pressure metric and mitigation, 6 models | anti-sycophancy instruction moderate and can backfire; counterfactual CoT near zero | abstract |
| Don't Blame the Preferences (Yang) | arXiv 2026 | 3 families, 9 benchmark combos | SFT checkpoints at least 85% of final sycophancy | abstract |
| Locating Sycophancy Across Training (Yao) | arXiv 2026 | 13 checkpoints, 5 lineages | capitulation under objection absent in base, present in all post-trained | abstract |
| Silicon Mirror (Shah) | arXiv 2026 | Generator-critic gate, single author | 9.6% to 1.4% on one model; 46.0% to 14.2% on another | abstract |
| Recalling Too Well (Bensal) | arXiv 2026 | Memory systems | memory raises sycophancy up to 40% | abstract |
| Token-level diagnosis with steering (Nguyen) | arXiv 2026 | Attribution-guided steering | 96% to 25% in the best case | abstract |

Two papers read in full.

Shah et al. [full text] (preprint; 13 open models, 0.6B-20B; 275 personas scored on NEO-IPIP
agreeableness; 4,950 opinion prompts of the form "[opinion]. Don't you agree?"; sycophancy scored
by keyword stance detection, not by a judge). Within a model, 9 of 13 show agreeableness predicting
sycophancy; the largest r are Llama 3.1 8B 0.87 and OLMo 3 7B 0.85, mean Cohen's d 0.757 over the
significant models, maximum 1.28 (the abstract says 2.33; the tables do not support it). Three
details matter. (a) Baseline sycophancy differs hugely by model, from 0.12 to 1.00; Qwen3 0.6B
agreed 100% of the time whatever the persona. (b) Adopting a persona usually lowered sycophancy
against the no-persona baseline (Llama 3.1 8B from 0.36 to 0.05), except Gemma 3 1B (0.37 to
0.59). (c) Size did not predict it; 2-8B models showed the strongest agreeableness effects. So a
persona prompt can be a mitigation or an amplifier depending on the model; this must be measured
per model. The setting is single-turn opinion agreement, not multi-turn pushback.

SYCON-Bench (Hong et al., arXiv 2025, v4 2026) [full text]: Turn of Flip (how many of 5 turns the
model holds its stance; higher is better) and Number of Flip. GPT-4o judges agreed with human
labels at Cohen's kappa 0.92 for debate, 0.69 for unethical queries and 0.63 for false
presuppositions (100 items each, one model), so a judge is reliable only where the stance is
explicit. Small instruct models fold fast: in debate, Qwen2.5-7B-Instruct held its stance 0.83
turns on average and flipped 2.63 times, against 4.90 turns and 0.02 flips for the 72B model. After
one objection, only 14.5% of Qwen2.5-7B-Instruct and 45.0% of Llama-3.1-8B-Instruct kept the
initial stance, against 71.4% and 93.9% for the matching base models (with a few-shot template).
Prompts (the table compares four prompts; the first is "You", an independent-reasoning prompt):
the third-person "Andrew" prompt lifted Qwen2.5-7B-Instruct's debate turn-of-flip from 1.10 to
4.02, while the plain anti-sycophancy instruction gave 1.32 (the abstract reports gains of up to
63.8% in debate). This is the best published evidence that a small local
model can be made to hold a stance by prompt framing in a debate, but it is one scenario.

Take-aways. Sycophancy is not one thing: deferring to a claim in the prompt exists in base
models, while capitulating when the user objects appears after post-training (Yao). A
persona's agreeableness predicts it in most small models (Shah), but a persona can make
sycophancy worse or better depending on the model, so it must be measured per model. The
mitigations that work in preprints either add a second pass (critic, counterfactual) or touch
internals; the cheap "be honest" instruction is modest and unreliable. Single-author preprints
(Silicon Mirror, SWAY) have not been replicated and test question-answering, not teammate chat.

### Conformity and disagreement among simulated teammates

| Paper | Venue/year | What was measured | Key number | Read |
|---|---|---|---|---|
| Disentangling Interaction and Bias in Opinion Dynamics (Brockers) | Nature Communications 2026 | LLM agents in multi-step dialogues, 12 questions | opinions converge to a shared attractor; topic, agreement and anchoring biases differ by model | abstract |
| Peacemaker or Troublemaker (Yao) | arXiv 2025 | Sycophancy in multi-agent debate | sycophancy collapses debate into early consensus; accuracy below single-agent | abstract |
| Language-Driven Opinion Dynamics (Cau) | arXiv 2025 | Debates between LLM agents | consensus emerges in almost any starting mix | abstract |
| Group Conformity in Multi-Agent Systems (Choi) | arXiv 2025 | 2,500+ debates | agents follow the numerically dominant group | abstract |
| Too Polite to Disagree (Kasprova) | arXiv 2026 | 6 open models, peer sycophancy rankings | telling agents who is sycophantic raised accuracy 10.5 points | abstract |
| Bayesian Belief Layer (Akbar) | arXiv 2026 | Separate belief state from language, 4 models | stubbornness parameter recovered after the language round trip (rank order perfect) | abstract |

If teamsim lets model-played teammates talk to each other, expect them to drift to agreement
within a few turns. The one design in these papers that matches teamsim's "script owns the
stance" idea is the Bayesian belief layer: keep the stance as a number outside the model, update
it by a rule, and let the model only phrase it. It is a single preprint (abstract only), but it
fits the evidence on drift and sycophancy and costs no model calls (inference).

## 6. Steering versus prompting

| Paper | Venue/year | What was measured | Key number | Read |
|---|---|---|---|---|
| Persona Vectors (Chen) | arXiv 2025 | Trait directions for evil, sycophancy, hallucination | monitor and control; automated from a description | abstract |
| What Can We Actually Steer? (Bas) | arXiv 2025 | 50 behaviours | effect varies by behaviour; inverted-U in strength | abstract |
| Persona Dosing (Jin) | arXiv 2026 | Llama-3.1-8B, Qwen3-8B, Gemma-3-4B | graded control, targeting error 4.7-6.2 points | abstract |
| Prompt-Activation Duality (Kang) | arXiv 2026 | KV-cache contamination in steered dialogue | coherence drift -18.6 to -1.9 with the fix | abstract |
| Persona Matters (Wu) | arXiv 2026 | Steering effects on short answers | steering lowers answer quality, more on open-ended tasks | abstract |
| Personality sliders (Hoppe), PERSONA (Feng) | arXiv 2026 | Vector algebra for Big Five | near fine-tuning on their own benchmark | abstract |

Steering needs access to hidden states, so it works with local weights loaded in a research
stack, not through an OpenAI-compatible HTTP endpoint such as the ones run-1 recommended.

## 7. Small and local models

| Paper | Venue/year | What was measured | Key number | Read |
|---|---|---|---|---|
| Constrained Decoding in Small LLMs (Chavan) | arXiv 2026 | 5 models, 0.6B-4B, 14 tasks | schema validity 78.6-92.9% to 100%; semantic gap remains | abstract |
| The Constraint Tax (Ray) | arXiv 2026 | Qwen2.5 0.5B and 1.5B, SmolLM2 1.7B, 15,000 generations | validity 61.5% to 100%, accuracy 19.7% to 11.0% | full text |
| When Correct Isn't Usable (Galeone) | arXiv 2026 | 7-9B models, JSON contracts | no system prompt gave 0% output accuracy; constrained decoding costs 3.6-8.2x latency | abstract |
| Quantization Amplifies Determinism (Kurtskhalia) | arXiv 2026 | Qwen3 8B/14B/32B at int4, int8, bf16, 71,000 completions | at 8B int4: same-answer probability +5.1 points, type-token ratio -0.011; no significant narrowing at 14B/32B | full text |
| When Personality Meets Quantization (Fu) | arXiv 2026 | MBTI under 4-bit and 2-bit | 4-bit keeps coarse personality; 2-bit breaks consistency | abstract |
| Trade-offs: Quantization, Task Difficulty, Model Size (Lee) | arXiv 2024 | 1B-405B, 4 methods | small models drop severely at 4-bit; 70B stable | abstract |
| Quantization Undoes Alignment (Rath) | arXiv 2026 | 3 7B-class models, 3-bit to BF16 | 4-bit: 2.5-5.6% of items gain new bias while perplexity moves under 3% | abstract |

Read in full: Kurtskhalia [full text] (single author, Qwen3 only, AWQ int4 against bf16, 71,000
completions paired by prompt and seed, pre-specified analyses). At 8B the effect is real but
uneven: the median per-prompt change in same-answer probability was 0 and a minority of prompts
collapsed hard (one went from 4 distinct car brands to the same brand in all 20 samples). At 14B
and 32B no content effect, but a stylistic drift (em-dash rate up 12-19%). Token entropy went up
while meaning concentration went up too, so log-probabilities alone cannot audit it. Ray [full
text] (single author, synthetic arithmetic, logic and tool-call tasks, not chat): hard answer-only
schema lowered answer accuracy for Qwen2.5-0.5B and 1.5B (taxes 11.9 and 20.0 points) and 3B
(15.3 points), but not for SmolLM2-1.7B, where constraint helped; on one backend pair results
replicated for Qwen and not for SmolLM2. In a four-model study, a delayed constraint (solve
first, then package) reached 40.7% accuracy at 100% validity, against 26.8% for a direct answer
schema and 31.5% for prompt-only JSON.

Which quantisation format matters: one preprint (Wu et al., abstract) tested 16 models at 4, 3
and 2 bits and found that quantisation shrinks decision margins and that GPTQ and GGUF flipped
far fewer whether-to-call tool decisions than plain rounding, so "3-bit" has no single failure
point. Another found 4-bit keeps coarse personality and 2-bit does not (Fu). Inference: Q4-class
GGUF builds are probably usable for wording, 2-bit is not, and each build needs its own check.

The point that matters: aggregate quality metrics (perplexity, accuracy) hide item-level and
diversity changes, so a quantised model must be re-tested on teamsim's own diversity and
stance checks. Structured output has two failure layers: syntax (fixed by constrained decoding)
and meaning (not fixed, sometimes worse for sub-2B). All of these are preprints and none
tests chat role-play.

## 8. Writing style realism and detection

| Paper | Venue/year | What was measured | Key number | Read |
|---|---|---|---|---|
| Mind the Sim2Real Gap (Zhou) | arXiv 2026 | 451 humans, 165 tasks, 31 simulators | short turns 1.0% (GPT-4o) vs 29.0% (humans); polite 49.0% vs 15.3%; best simulator index 76.0 vs humans 92.9 | full text |
| Flipping the Dialogue (Naous) | arXiv 2025 | Purpose-built User LMs | better assistants make worse simulators | abstract |
| RealUserSim (Zhu) | arXiv 2026 | Grounding on 14,000 real conversations | style match 6-8% unconstrained; grounded 24.2% to 45.3% | abstract |
| Persona Policies (Chopra) | arXiv 2026 | Evolved persona programs | judged human 80.4% vs about half that for baseline | abstract |
| Quantifying Utility of User Simulators (Suh) | arXiv 2026 | 283-participant user study | role-play 51% win rate vs fine-tuned 58%; persona conditioning helps but does not close the gap | abstract |
| SimulatorArena (Dou) | EMNLP 2025 | 909 annotated conversations | profile-conditioned simulators reach rho 0.7 with human judgments | abstract |
| AI-generated language remains distinguishable (Pagan) | PNAS 2026 | 9 open models, 5 calibration methods, X/Bluesky/Reddit | still distinguishable; instruct below base; larger not clearly better | full text |
| When Detection Fails (Dawkins) | arXiv 2025 | 505,159 AI posts | detectability falls when the generator is a private fine-tune | abstract |
| Stylometry on short samples (Przystalski) | arXiv 2025 | 10-sentence texts | up to .98 accuracy in a binary case (Wikipedia, not chat) | abstract |

Pagan et al. (PNAS) [full text] is the closest published test of "make generated chat look
human". Nine open models (4-8B plus one 70B), replies to real messages from 275 X users and 492
Reddit users (20 replies each), temperature 0.8. A BERT classifier separated AI from human replies
at 87% or more in the reference setup and 70-80% after the best calibration. What helped: simple
stylistic examples and context retrieval, and non-instruction-tuned base models over instruct
versions; 70B was no better than 8B. What did not: persona descriptions and fine-tuning, which
had negligible or adverse effects on realism. Affect (toxicity, sentiment) stayed the clearest
tell. There is a trade-off: reducing detectability lowered similarity in meaning to the human reply.
For teamsim this suggests few-shot real-style example lines per teammate beat a longer persona
description, and that style realism and planted-fact fidelity compete (the planted fact check must
stay a hard gate).

Two more points. Out of Style (Cao et al., arXiv 2025, abstract only): nine LLMs from 3B to 72B
and two retrievers; informal queries cut Recall@5 by up to 40.41% (relative) and queries with
grammar errors cut answer match by up to 38.86%, more than for LLM-only answers. The Individual
Turing Test (Guo et al., arXiv 2026, abstract only): with ten years of one volunteer's messages,
fine-tuning, retrieval and memory methods did not fool the volunteer's acquaintances, though they
did better on strangers; fine-tuning helped daily-chat style, retrieval and memory helped
opinions. Mimicking one specific person is harder than sounding like a person, and teamsim needs
only the latter.

For teamsim, the realistic knobs are the ones Zhou measured: length distribution, politeness,
uncertainty markers and pivot rate. Those can be compared with the numbers in the prototype's
calibration notes (message length, share of messages of four words or fewer, fragmenting).

## Implications for teamsim

Tied to the open decisions. "Inference" means my reading, not a paper's claim.

### Stack and runtime

- Talk to any OpenAI-compatible HTTP endpoint (as run-1 proposed). Nothing in the literature
  argues for model internals in v0.1: steering needs hidden-state access (Section 6) and is not
  robust (inverted-U in strength, quality loss, KV-cache contamination in multi-turn use).
- Wanted from the endpoint, if available: temperature and seed control, JSON-schema or grammar
  output, and token log-probabilities (Kurtskhalia shows log-probabilities alone cannot audit
  diversity loss, so treat them as optional).
- Constrained decoding is available in every common local runtime, but it is not free for
  sub-3B models (Ray). Prefer: model writes one plain-text line; the script wraps it. If a schema
  is needed, use "reason free, constrain late" (a short free line first, then a small constrained
  tag), and report schema validity, answer accuracy and wrong-valid rate separately.

### Model-free default versus local model

The literature supports run-1's model-free default and strengthens it.
- Behaviour that matters to scoring (who disagrees, who flips, who goes quiet) is not reliably
  produced by prompting a persona: questionnaire answers do not predict behaviour in small and
  mid models (Han), fidelity decays toward the default assistant (de Araujo, Li), and aligned
  models drift to agreement in multi-agent talk (Brockers, Yao). The script should hold the stance
  as a number or label, update it by rule, and hand the model a finished intent to phrase
  (the Bayesian belief layer is the one published design of this kind; it is a preprint).
- If a model is used for wording, the evidence favours 7-8B-class models over smaller ones for
  anything that can be pushed back on (Section 5), and non-instruction-tuned or lightly tuned
  models for human-like style (Pagan). Those two pull in opposite directions; this is a tension
  teamsim has to measure, not resolve from papers.
- Hosted fallback: no paper contradicts it; larger and frontier models were less sycophantic
  (PARROT, SYCON) and drifted less (de Araujo), though they still drifted.

### v0.1 actions and first user

- The papers do not compare chat with task or repo actions. Everything here concerns text, which
  is the shared modality of chat and issue comments, so the stance, style and measurement
  machinery carries to issue comments unchanged (inference). Nothing here tests model-written
  code; the run-1 "scripted repo events only" position is not contradicted.
- For builders of team-facing software, one result bears directly on scoring: informal wording
  and grammatical errors cut a retrieval-augmented system's recall by up to 40.41% (relative) and
  answer matches by up to 38.86% (Out of Style, abstract). The realism tax reported by the
  prototype (recall with and without the realism transform) is therefore a literature-supported
  measurement, and the style knobs are test inputs, not decoration.

### Persona record (fields)

Proposed minimal record, rendered by the script to a few plain sentences plus example lines:

| Field | Why (source) |
|---|---|
| id, display handle, real first name | handle vs name tests in the prototype; not a literature result |
| role, team, tenure, topics they own | work-relevant attributes are what can change behaviour (Hu and Collier); demographics alone explain little |
| stance table: topic, stance, strength, change conditions | script-owned stance (Han; Akbar) |
| conflict style: pushback probability, flip rule, who they defer to | measured flips need a defined rule (SYCON) |
| style knobs: length distribution, fragment rate, typo and emoji rate, politeness, hedge rate, active hours, reply latency | the dimensions where LLM users differ most from people (Zhou; Pagan) |
| knowledge scope and forbidden facts | planted facts must survive, others must not leak (curse-of-knowledge result: 11 open models used hidden facts 67-72 points above baseline) |
| 3-5 example lines in the teammate's voice | stylistic examples reduced detectability; persona text did not (Pagan) |
| seed | replay |

Keep the model-facing text short (my target: under 150 tokens) and re-send it with the last few
messages every call. Do not add Big Five scores as a control; if kept for authors, label them as
descriptive only.

### What to measure, with candidate thresholds and where they come from

Published baselines are rare and from other tasks. Items marked "own" are teamsim choices to set
from a first baseline run and then freeze in an ADR.

| Measure | How | Published anchor | Threshold to use |
|---|---|---|---|
| Distinctness | pairwise embedding distance or Vendi score over teammates' lines for the same slot, divided by the same figure for the scripted lines; plus compression ratio, long n-gram repetition, Self-BLEU, BERTScore | no pass mark; avoid the 0.8 cosine cutoff (exceeded by 20-32% of different-idea pairs) | own: ratio to scripted reference; report a template-skeleton share (29% in one model in Xiao) |
| Stance retention under pushback | share of pushback sequences where the labelled stance equals the assigned one; Turn of Flip over 5 turns | 70B-class and frontier models hold about 4.5-5 of 5 turns in debate; Qwen2.5-7B-Instruct 0.83 | own: 90% (carried from the earlier note; not a published figure) |
| Sycophancy follow rate | follow a false authority claim, matched with a neutral version | grouped by PARROT: under 15% robust, 15-30% resistant, 30-50% moderate, over 50% vulnerable; Qwen2.5-1.5B 94%, Gemma-3-4B 78.9%, Qwen2.5-7B 69.4%, Gemma-3-12B 51.5%, Qwen2.5-14B 35.9%, GPT-4o 16.1%, Claude Sonnet 4.5 10.8% | own: a local model may play a pushback-prone teammate only if it lands in the resistant band or better on teamsim's own test; otherwise script the pushback |
| Planted-flaw raise rate | share of the panel that mentions a known flaw (keyword or fact match, no judge) | none (teamsim's idea); this is ground-truth based, so it avoids the judge problem | own, from baseline |
| Self-report versus behaviour agreement | do not use as a pass test | 43-50% (chance) for small and mid models | none |
| Style distance | length, share of short turns, politeness, hedge and pivot rates against the prototype's calibration numbers | customer-service humans: short turns 29.0%, polite 15.3%, uncertain 7.3%, pivot 8.4% (Zhou); these are not team-chat figures | own: calibrate from team chat statistics (numbers only) |
| Detectability | a classifier separating model lines from the hand-written fixture lines | 87% or more in the reference setup, 70-80% after calibration, chance 50% (Pagan; Twitter, Bluesky, Reddit replies) | report only; do not claim parity with humans |
| Schema validity and semantic pass | validity, answer accuracy, wrong-valid rate separately | validity 78.6-92.9% to 100% with constrained decoding for 0.6-4B; accuracy loss up to 20 points (Ray) | own: 100% valid after retry or fallback to scripted line |
| Judge reliability | hand-label a sample; report kappa | GPT-4o vs human kappa 0.92 (explicit debate stance), 0.69 and 0.63 (implicit); LLM judges identify roles at about 69% against 90.8% for humans | own: use a judge only where kappa on the sample is 0.8 or more; otherwise prefer rules |

### Simulated-feedback gate (ADR 0003)

- Diversity and sycophancy are measurable per run; both need a labelled stance or a ground-truth
  check, and neither is validated for chat teammates. Agreement with humans on a given product
  cannot be established from published data. This matches the earlier note.
- New from this review: LLM-played evaluators and users lean positive. In the study with 451 real
  participants, simulated users gave uniformly more positive feedback than the humans, and an LLM
  evaluator overestimated an assistant's human-likeness by 55% (and its overall score by 18% of
  the rating scale). The task was customer service, not product feedback. A feedback report
  should therefore print a positivity rate next to the planted-flaw rate and warn when a panel is
  more positive than a stated human baseline. Letting users supply 3-5 real responses to their own
  product (the earlier proposal) is consistent with the evidence that grounding in real behaviour
  helps (SimulatorArena: profile-conditioned simulators reached rho 0.7 with human judgments;
  RealUserSim: grounded simulation raised style match from 24.2% to 45.3%).
- Keep the "hypotheses, not findings" label. Every number above comes from other domains.

### Preset design and scoring

- A preset is a team file: persona records plus slots and planted facts. No model needed to run it.
- Score the product on planted facts, as now. Score the simulator separately (distinctness,
  stance retention, style distance) and print both, so users see whether a failure came from the
  product or from the team.
- Pass the realism tax (recall with and without style transforms) through as a first-class number.

### What to avoid

- Personality questionnaires as a validity check; long persona biographies as a diversity tool;
  absolute embedding-cosine cutoffs; LLM judges for role identification without a calibration
  sample; "be honest" as the only anti-sycophancy control; model-to-model chat without a script
  owner for stances; sub-3B models for any teammate that must disagree; claiming human-like text.

## Open problems

What the literature does not answer, and what teamsim could measure itself:
- No study uses workplace-chat teammates with planted facts. Teamsim could measure, on its own
  scripted dataset, whether a model-written paraphrase of a slot keeps the fact, stance and style.
- Structured versus narrative persona format for chat wording is untested; a 2x2 test on 7-8B
  models (format by example lines) is cheap.
- No published pass bars for distinctness or consistency. A first baseline run (scripted lines as
  reference, 2-3 local models, 2-3 quantisation levels) would produce the numbers to freeze.
- Small-model role-play at 1-8B under quantisation is thin: one preprint on diversity (Qwen3 only,
  AWQ), one on MBTI-style personality. Teamsim can measure diversity and flip rate per build.
- Whether the PARROT-style false-authority test predicts flips in chat pushback is unknown; run
  both on the same models and compare.
- Style realism in team chat (fragments, handles, reactions) has no published detector. The
  prototype's calibration statistics are the only reference, and they come from one team.
- Many numbers here are single-author preprints. None was independently replicated, except that
  the hivemind claims have a re-analysis.

## Where this disagrees with the run-1 notes

1. "Truthfulness guard on agreeable personas" (Shah et al.): the guard is a design suggestion in
   that paper, not a tested result, and the paper's own data show adopting a persona usually
   lowered sycophancy against the no-persona baseline (except Gemma 3 1B). Elsewhere the plain
   anti-sycophancy instruction was modest (SYCON: 1.10 to 1.32 turns for a 7B) and can backfire
   (SWAY, abstract), while third-person framing helped more (1.10 to 4.02). Prefer framing plus a
   measured test over a one-line guard.
2. The earlier note leans on "persona collapse" and Persona Hub-style scale. This review adds
   that richer personas can reduce separation (Bhattacharyya) and that a model-generated persona
   list stopped being diverse beyond about 200 (PersonaGym), so the persona list should be
   written or sampled by the script, not generated.
3. The earlier gate asks for a "teammates keep their stance in 90% of pushback sequences". The
   literature gives frontier-model ranges but no 90% figure, and a 7B instruct model held a stance
   for under one of five turns in debate. The bar is reachable only with a script-held stance or a
   larger model, which supports the model-free default.
4. The earlier note finds a 3-4B model on a laptop CPU feasible for tens of generated messages.
   This review adds that models that small are the most sycophantic in the studies that include them (0.6B:
   100%; 1.5B: 94% follow rate), so speed alone does not justify them as teammates.
5. Xiao et al. is described as eight models in the earlier note and in the paper's newer abstract;
   the first full text I read lists ten. Not material to the conclusions.
6. Not re-checked: SycEval's 58% figure and the Kambhatla et al. persona-lexical-diversity result
   from the earlier note; neither paper was retrieved in this review.

## Sources

All read 2026-11-11. Depth in brackets. IDs are arXiv unless a DOI is given.

- Quantifying the Persona Effect in LLM Simulations, Hu, 2024, https://arxiv.org/abs/2402.10811 [full text]
- How Well Do Large Language Models Capture Human Personality?, Bhattacharyya, 2026, https://arxiv.org/abs/2606.18263 [full text]
- The Personality Illusion, Han, 2025, https://arxiv.org/abs/2509.03730 [full text]
- Persistent Personas?, de Araujo, 2025, https://arxiv.org/abs/2512.12775 [full text]
- Mind the Sim2Real Gap in User Simulation for Agentic Tasks, Zhou, 2026, https://arxiv.org/abs/2603.11245 [full text]
- Assessing the Reliability of Persona-Conditioned LLMs as Synthetic Survey Respondents, Taday Morocho, 2026, https://arxiv.org/abs/2602.18462 [abstract]
- How Far Do Persona Effects Generalize in Language Models?, Zhou, 2026, https://arxiv.org/abs/2609.32758 [abstract]
- Scaling Synthetic Data Creation with 1,000,000,000 Personas, Ge, 2024, https://arxiv.org/abs/2406.20094 [abstract]
- Personality Traits in Large Language Models, Serapio-Garcia, Nature Machine Intelligence 2025, https://doi.org/10.1038/s42256-025-01115-6 [abstract]
- PersonaLLM, Jiang, 2023, https://arxiv.org/abs/2305.02547 [abstract]
- Personality Without Persons?, Zierahn, AIES 2026, https://doi.org/10.1609/aies.v9i4.43359 [abstract]
- Limited Ability of LLMs to Simulate Human Psychological Behaviours, Petrov, 2024, https://arxiv.org/abs/2405.07248 [abstract]
- TRAIT, Lee, 2024, https://arxiv.org/abs/2406.14703 [abstract]
- BIG5-CHAT, Li, 2024, https://arxiv.org/abs/2410.16491 [abstract]
- Designing AI-Agents with Personalities, Huang, 2024, https://arxiv.org/abs/2410.19238 [abstract]
- Consistently Simulating Human Personas with Multi-Turn RL, Abdulhai, 2025, https://arxiv.org/abs/2511.00222 [abstract]
- ContextEcho, Ding, 2026, https://arxiv.org/abs/2605.24279 [abstract]
- Best Friends, Not Forever (ANCHOR), Venkit, 2026, https://arxiv.org/abs/2607.28818 [abstract]
- When LLMs Forget What They Believe (StateTrack), Zhu, 2026, https://arxiv.org/abs/2610.31314 [abstract]
- Memory-Driven Role-Playing, Wang, 2026, https://arxiv.org/abs/2603.19313 [abstract]
- PersonaEval, Zhou, 2025, https://arxiv.org/abs/2508.10014 [abstract]
- Rethinking Role-Playing Evaluation (anonymous benchmarking), Peng, 2026, https://arxiv.org/abs/2603.03915 [abstract]
- Artificial Hivemind, Jiang, 2025, https://arxiv.org/abs/2510.22954 [abstract]
- How Strong Is the Evidence for the Artificial Hivemind?, Schaeffer, 2026, https://arxiv.org/abs/2609.33936 [full text]
- The Alignment Tax, Liu, 2026, https://arxiv.org/abs/2603.24124 [abstract]
- Understanding the Effects of RLHF on LLM Generalisation and Diversity, Kirk, 2023, https://arxiv.org/abs/2310.06452 [abstract]
- Revisiting LLM Homogeneity Through a Multidimensional Lens, Qiu, 2026, https://arxiv.org/abs/2611.01549 [abstract]
- Standardizing the Measurement of Text Diversity, Shaib, 2024, https://arxiv.org/abs/2403.00553 [abstract]
- Evaluating the Evaluation of Diversity in NLG, Tevet, 2020, https://arxiv.org/abs/2004.02990 [abstract]
- The Vendi Score, Friedman, 2022, https://arxiv.org/abs/2210.02410 [abstract]
- The Price of Format: Diversity Collapse in LLMs, Yun, 2025, https://arxiv.org/abs/2505.18949 [abstract]
- Optimizing Diversity and Quality through Base-Aligned Model Collaboration (BACo), Wang, 2025, https://arxiv.org/abs/2511.05650 [abstract]
- Beyond the Hivemind (Meta-Persona Anchoring), Fu, 2026, https://arxiv.org/abs/2608.02618 [abstract]
- The Chameleon's Limit (Persona Collapse), Xiao, 2026, https://arxiv.org/abs/2604.24698 [full text]
- Towards Understanding Sycophancy in Language Models, Sharma, 2023, https://arxiv.org/abs/2310.13548 [abstract]
- Measuring Sycophancy of Language Models in Multi-turn Dialogues (SYCON-Bench), Hong, 2025, https://arxiv.org/abs/2505.23840 [full text]
- ELEPHANT, Cheng, 2025, https://arxiv.org/abs/2505.13995 [abstract]
- Too Nice to Tell the Truth, Shah, 2026, https://arxiv.org/abs/2604.10733 [full text]
- PARROT, Celebi, 2025, https://arxiv.org/abs/2511.17220 [full text of result tables]
- SWAY, Bhalla, 2026, https://arxiv.org/abs/2604.02423 [abstract]
- Don't Blame The Preferences, Yang, 2026, https://arxiv.org/abs/2611.10045 [abstract]
- Locating Sycophancy Across Training Stages in Open Language Models, Yao, 2026, https://arxiv.org/abs/2610.37788 [abstract]
- The Silicon Mirror, Shah, 2026, https://arxiv.org/abs/2604.00478 [abstract]
- Recalling Too Well (MIST), Bensal, 2026, https://arxiv.org/abs/2606.10949 [abstract]
- Token-Level Diagnosis of Sycophancy with Attribution-Guided Steering, Nguyen, 2026, https://arxiv.org/abs/2607.28906 [abstract]
- Persona Vectors, Chen, 2025, https://arxiv.org/abs/2507.21509 [abstract]
- What Can We Actually Steer?, Bas, 2025, https://arxiv.org/abs/2511.18284 [abstract]
- Persona Dosing, Jin, 2026, https://arxiv.org/abs/2609.36388 [abstract]
- Prompt-Activation Duality, Kang, 2026, https://arxiv.org/abs/2605.10664 [abstract]
- Persona Matters: Effects of Activation Steering, Wu, 2026, https://arxiv.org/abs/2604.07102 [abstract]
- Controllable and explainable personality sliders, Hoppe, 2026, https://arxiv.org/abs/2603.03326 [abstract]
- PERSONA: inference-time personality control via activation vector algebra, Feng, 2026, https://arxiv.org/abs/2602.15669 [abstract]
- Constrained Decoding Eliminates Structural Failures in Small LLMs, Chavan, 2026, https://arxiv.org/abs/2609.23742 [abstract]
- The Constraint Tax, Ray, 2026, https://arxiv.org/abs/2605.26128 [full text]
- When Correct Isn't Usable, Galeone, 2026, https://arxiv.org/abs/2605.02363 [abstract]
- Quantization Amplifies Determinism, Not Bias, Kurtskhalia, 2026, https://arxiv.org/abs/2609.07901 [full text]
- When Personality Meets Quantization, Fu, 2026, https://arxiv.org/abs/2608.25977 [abstract]
- Exploring the Trade-Offs: Quantization Methods, Task Difficulty, and Model Size, Lee, 2024, https://arxiv.org/abs/2409.11055 [abstract]
- Quantization Undoes Alignment, Rath, 2026, https://arxiv.org/abs/2605.15208 [abstract]
- Flipping the Dialogue, Naous, 2025, https://arxiv.org/abs/2510.06552 [abstract]
- RealUserSim, Zhu, 2026, https://arxiv.org/abs/2605.20204 [abstract]
- Beyond Cooperative Simulators (Persona Policies), Chopra, 2026, https://arxiv.org/abs/2605.12894 [abstract]
- Quantifying the Utility of User Simulators, Suh, 2026, https://arxiv.org/abs/2605.09808 [abstract]
- SimulatorArena, Dou, EMNLP 2025, https://arxiv.org/abs/2510.05444 [abstract]
- AI-generated language remains systematically distinguishable from human communication, Pagan, PNAS 2026, https://doi.org/10.1073/pnas.2531748123 [full text]
- When Detection Fails, Dawkins, 2025, https://arxiv.org/abs/2506.09975 [abstract]
- Stylometry recognizes human and LLM-generated texts in short samples, Przystalski, 2025, https://arxiv.org/abs/2507.00838 [abstract]
- PersonaGym: Evaluating Persona Agents and LLMs, Samuel, 2024 (v5 2026), https://arxiv.org/abs/2407.18416 [full text]
- Verbalized Sampling, Zhang, 2025, https://arxiv.org/abs/2510.01171 [full text]
- Measuring and Controlling Instruction (In)Stability in Language Model Dialogs, Li, 2024, https://arxiv.org/abs/2402.10962 [full text of method sections]
- Disentangling interaction and bias effects in opinion dynamics of LLMs, Brockers, Nature Communications 2026, https://doi.org/10.1038/s41467-026-77340-3 [abstract]
- Peacemaker or Troublemaker: How Sycophancy Shapes Multi-Agent Debate, Yao, 2025, https://arxiv.org/abs/2509.23055 [abstract]
- Language-Driven Opinion Dynamics in Agent-Based Simulations with LLMs, Cau, 2025, https://arxiv.org/abs/2502.19098 [abstract]
- An Empirical Study of Group Conformity in Multi-Agent Systems, Choi, 2025, https://arxiv.org/abs/2506.01332 [abstract]
- Too Polite to Disagree: Sycophancy Propagation in Multi-Agent Systems, Kasprova, 2026, https://arxiv.org/abs/2604.02668 [abstract]
- Bayesian Belief Layer for Controllable Opinion Dynamics in LLM Agents, Akbar, 2026, https://arxiv.org/abs/2609.21997 [abstract]
- PILOT: Steering Synthetic Data Generation with Psychological and Linguistic Output Targeting, Cisar, 2025, https://arxiv.org/abs/2509.15447 [abstract]
- A Three-Tier Persona Vector for Controllable User Simulation in Agentic Evaluation, Khedar, 2026, https://arxiv.org/abs/2609.08592 [abstract]
- The Prompt Makes the Person(a), Lutz, 2025, https://arxiv.org/abs/2507.16076 [abstract]
- Pay What LLM Wants: Can LLM Simulate Economics Experiment with 522 Real-human Persona?, Choi, 2025, https://arxiv.org/abs/2508.03262 [abstract]
- Out of Style: RAG's Fragility to Linguistic Variation, Cao, 2025, https://arxiv.org/abs/2504.08231 [abstract]
- Individual Turing Test: LLM-based Simulation Using Longitudinal Personal Data, Guo, 2026, https://arxiv.org/abs/2603.01289 [abstract]
- Which Decisions Low-Bit Quantization Breaks, and How to Predict Them, Wu, 2026, https://arxiv.org/abs/2608.06564 [abstract]
- The Curse of Knowledge in Role-Playing Language Models, Zhang, 2026, https://arxiv.org/abs/2610.17327 [abstract]
