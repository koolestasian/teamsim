# How team-facing product capabilities are evaluated in research: literature review (2026-11-11)

Scope: how research evaluates the things teamsim scores in team-facing products: memory and
search over team chat, multi-party understanding, decisions and due dates, knowledge updates and
conflicting sources, prompt injection, privacy and secrets, catch-up. Peer-reviewed papers and
arXiv preprints, with the 2025-2026 work that follows the seminal papers.

Read depth: [full text] means passages were read; [abstract] means only the abstract was read,
so the numbers are the authors' claims and were not checked against the body. Almost all
2025-2026 papers cited here are arXiv preprints; publication venues were not verified unless
stated, so treat each as a preprint.

## Summary

1. **Long-term memory benchmarks agree on five task types**: single-hop extraction, multi-hop
   (multi-session) reasoning, temporal reasoning, knowledge update and abstention (LongMemEval,
   LoCoMo, EverMemBench, SlackBench). The pattern is: humans write the questions and mark the
   evidence turns, a model writes the filler chat, answers are scored by exact-ish match or an
   LLM judge validated on a small human-labelled sample. Teamsim already plants facts this way.
   What it lacks is abstention, knowledge-update and multi-hop checks. [full text]
2. **Finding one fact is solved; combining facts is not.** In a multi-party benchmark with
   1M-token projects, single-hop recall reaches 97.7% for the best long-context model, but
   multi-hop falls to 26.5%, and to 54.5% / 33.6% / 19.7% as questions span one / two / three
   groups. With the evidence handed over, two of three models recover (88-98%; the third
   stays at 37%). So the bottleneck is
   finding and attributing evidence across speakers. Teamsim should report retrieval and answer
   quality separately and expose "number of channels involved" as a preset knob. [full text]
3. **Outdated facts are a measurable failure that normal accuracy hides.** Memora's FAMA metric
   subtracts credit when an answer uses invalidated memory; the penalty grows with history
   length for memory agents (18.2 points weekly, 29.5 quarterly). Teamsim's "team changed its
   mind" plant should be scored for both "states the new decision" and "does not present the
   old one as current". [full text]
4. **Abstention and false premises are where assistants fail quietly.** On LoCoMo, a long-context
   model fell to 2.1% on unanswerable ("adversarial") questions while a short-context GPT-4 got
   70.2%. In SlackBench, abstention ("hallucination") queries scored 12.8% to 59.6% on a filtered
   subset across eight harness-model pairs, at or below the search queries for all eight; a
   correct abstention must also give the right reason. Teamsim should add "ask about something never planted" and "ask with a wrong
   premise". [full text]
5. **Injection scores depend on benchmark design more than on the model.** Static template
   benchmarks are near saturated for frontier models; adaptive human attacks are not (208,095
   human-written attacks: GPT-4o 58%, a defence-trained model 32%). One audit found a scorer that
   counted "the target tool was called" reported 21.7% where the argument-level truth was 1.2%,
   and 91% of payloads were never delivered. Teamsim must verify delivery, score on observable
   actions and exact strings, never on wording heuristics. [full text for the audit]
6. **Multi-user injection is a separate threat and teamsim's setting is where it lives.**
   "Cross-user poisoning" (an ordinary teammate message that later steers the agent while it
   serves someone else) succeeded 82% (GPT-4.1) and 98% (Claude Sonnet 4) on Slack-style tasks
   where standard prompt injection scored 1.9% and 1.0%, and it persists across tasks. Add a
   persistent-rule probe from one teammate, scored on a later action for another. [full text]
7. **Group chat makes privacy worse, not just different.** In MuPPET, leak rates rose from
   one-to-one to multi-party for 6 of 7 models (Gemini 2.5 Pro 9.9% to 23.5%; Qwen3 14B 41.0% to
   63.4%), and small open-weight models leaked most, which matters because they are the likely
   default for students. Prompt-only defences barely helped small models. Teamsim's private
   channel probe is right; add audience size as a knob. [full text]
8. **Authority, repetition and recency drive source conflicts.** Models prefer institutional
   sources, but repeating a low-credibility claim flips the preference (average shift of 30 to 34
   points on the authors' preference score) and a prompt telling the model to ignore repetition only partly helps. A recent
   benchmark defines an attack by authority, not wording. This is the closest published frame for
   "a pasted AI answer must not outrank a team decision", and it says to vary how often the AI
   answer is repeated. [full text, abstract]
9. **Use deterministic scoring wherever the plant is a string, id, date, permission or tool
   call; use a judge only for free text, and validate it.** LongMemEval's judge matched experts
   on 97-98% of 30-item samples per type; Memora used a three-judge majority with human
   agreement of 88.3%. Teamsim's current judge-free core is supported by the literature, with
   judges as an optional, validated extra. [full text]
10. **Literature gaps teamsim can fill**: no benchmark resolves "relative due dates in a user's
    time zone from chat", none scores catch-up for an absent member, none scores handle-versus-name
    resolution. For these, teamsim's own measurements would be new. (Sections 3 and 7.)

## 1. Long-term conversational memory benchmarks

| Paper | Year, venue | Measures | Key number | Depth |
|---|---|---|---|---|
| LongMemEval (Wu et al.) | 2024, arXiv | 5 abilities, 500 questions | ChatGPT 57.7% vs 91.8% reading full history (97 questions) | full |
| LoCoMo (Maharana et al.) | 2024, arXiv | 7,512 QA, 5 types | adversarial 2.1% vs 70.2%; human 87.9 F1 overall | full |
| EverMemBench (Hu et al.) | 2026, arXiv | multi-party, 2,400 QA | multi-hop 26.5%; oracle 88-98% | full |
| Memora (Uddin et al.) | 2026, arXiv | updates and deletions, FAMA | agents lose 18-30 points to obsolete memory | full |
| SlackBench (Li et al.) | 2026, arXiv | 140 workplace queries | best 80.25%, most under 66% | full |
| A-TMA / LTP (Shi et al.) | 2026, arXiv | "ghost memory" | LoCoMo temporal F1 0.0295 to 0.1705 with state labels | abstract |
| MOSAIC (Tsang et al.) | 2026, arXiv | write, retrieve, deliver, read | abstention weak under controls | abstract |
| DyadMem (Tao et al.) | 2026, arXiv | capture, update, recall | gold-memory QA strong, full pipeline drops sharply | abstract |
| SCALE-QA (Feng et al.) | 2026, arXiv | interleaved flat thread, 3,000 MCQ | deterministic 4-way grading | abstract |

**Task types and how they were built.**
LongMemEval (500 questions) has seven types: single-session user, assistant and preference,
multi-session, knowledge update, temporal reasoning and abstention (30 false-premise questions).
Construction: an ontology of 164 user attributes; an LLM proposes question-answer seeds; human
experts filter and rewrite all of them; answers are split into evidence statements with
timestamps; each statement is hidden in a generated session; humans edit; sessions are then
mixed into filler chats (about 115k tokens, or 1.5M for the M version). Scoring is an LLM judge
with per-type prompts plus Recall@k and NDCG@k against marked evidence turns. [full text]
LoCoMo uses persona and event-graph conditioned generation with human edits. Its QA has
single-hop 2,705 (36%), multi-hop 1,104, temporal 1,547, open-domain 285 and adversarial 1,871
questions, scored by token F1 on answers copied from the dialogue (deterministic), plus
FactScore for event summaries and recall@k for retrieval. [full text]
EverMemBench builds a blueprint first (who may decide what, task timelines), generates dialogue
day by day with four validation levels (programmatic rules such as "only tasks due today may be
marked complete", LLM checks for premature completion and contradiction), then derives
questions that must pass a blind test (not answerable without the evidence), a sufficiency and
uniqueness check, and a human audit. [full text]

**Judge reliability.** LongMemEval: 30 questions per type, two answer models; mean agreement with
experts 0.98 and 0.97; lowest 0.90 for preference and abstention. Its temporal prompt forgives
off-by-one errors in day counts. Memora: three judges from three vendors, majority vote, 88.3%
agreement with humans, Cohen's kappa between annotators 0.86 to 0.90. [full text]

**Published state of the art (self-reported, preprints).** Chronos reports 92.6% and 95.6% on
LongMemEval-S (500 questions) with a calendar-indexed event memory [abstract]. EGMemory reports
68.2% on GroupMemBench and 77.9% on EverMemBench [abstract]; SpeakerMem-R1 reports 62.33% on
the EverMemBench leaderboard [abstract]. These two EverMemBench figures differ, so they should
not be compared without the protocol; I could not tell which subset each used.

**Known weaknesses.**
- Mostly dyadic and explicit questions. LoCoMo-Plus (Li et al.) argues string matching misjudges
  implicit constraints [abstract]. MemoryArena (He et al.) reports agents near saturation on
  LoCoMo-style recall do poorly when memory must guide later actions [abstract].
- Final accuracy hides where a failure happens. MOSAIC, DyadMem and A-TMA all argue for scoring
  write, retrieve and read separately [abstract].
- Generated chat is cleaner than real chat. EverMemBench enforces "deadline discipline";
  MuPPET and SlackBench state their data is synthetic or re-enacted. SlackBench also hand-edited
  messages that sounded too AI-like and replaced real keys with fakes. [full text]
- Small samples for the human-run commercial system test (97 questions).

## 2. Multi-party conversation understanding

Evidence about how interleaving, handles and fragments hurt models:

- **Attribution is the bottleneck.** EverMemBench: accuracy fell 64% (relative) from one to three
  groups per question, and "cross-group attribution, not context length, is the dominant
  challenge". [full text] LoCoMo: long-context models are "especially prone to misassigning
  dialogs or events to the wrong speaker". [full text]
- **Who said it.** M3-SLU (Kwon et al.): models capture what was said but often fail on who said
  it [abstract]. Chang et al.: the best multimodal model drops substantially when character
  identities are anonymised [abstract]. Penzo et al. found addressee recognition depends on
  conversation structure, response selection on text, and removed usernames to preserve privacy
  [abstract]. Inoue et al.: GPT-4o was only marginally above chance on addressee recognition in
  triadic spoken dialogue; explicit addressees appear in about 20% of turns [abstract].
- **Disentanglement.** Kummerfeld et al. (77,563 IRC messages with reply links) found 80% of the
  conversations in a widely used corpus had missing or extra messages, so older benchmark data is
  itself noisy [abstract]. APO-DD reports an optimised prompt scoring 68.7 versus 57.5 for the best
  manual prompt on Ubuntu IRC with a 9B model, averaged over seven metrics [abstract].
- **Interleaving as a question type.** SCALE-QA uses a flat unsegmented thread and deterministic
  multiple choice; it argues benchmarks that expose topic boundaries understate the problem
  [abstract].
- **Knowing when to speak.** Speak-or-Stay-Silent (Bhagtani et al.): eight LLMs fail
  context-aware turn-taking zero-shot; supervised fine-tuning gains up to 23 points of balanced
  accuracy [abstract]. Duplex-MPE: a transcript-based reference responded 64.3 points more often to
  explicit than implicit requests [abstract]. These bear on "bot noise" and on a product that
  must decide whether a message was meant for it.

Not found: any benchmark of resolving first names or Discord-style handles to a person (check 12).
The nearest is entity-alias resolution inside memory systems (Chronos indexes "entity aliases",
[abstract]). Teamsim's check is novel and should be reported as its own measurement.

## 3. Summaries, decisions, action items, dates

**Decision and action-item detection.** Older work is on meeting corpora: Kim and Rudin found
key decisions can be detected from local dialogue acts [abstract]; Wang and Cardie summarised
decisions on AMI, with 0.22 to 0.23 ROUGE-F1 for decision abstracts [abstract]; the MUG benchmark
(Zhang et al.) includes action-item detection over 654 Mandarin meetings [abstract]; Meeting
Decision Tracker (Inoue et al.) found rewriting decision utterances to remove collapsed context
improved usefulness [abstract]. For chat, DevNous built 160 annotated turns and reports 81.3%
exact-match turn accuracy for task formalisation [abstract]; GADR extracts decisions from five
meeting transcripts with expert review and notes that RAG enrichment can add transcript-unfaithful
content [abstract]. DecisionTraceBench (spoken, Chinese, finance) scores whole decision event chains
with trajectory-level F1: 5.7% to 21.4% for current systems, at most 38.7% with speaker-labelled
scripts [abstract]. Takeaway: scoring a whole chain (who, what, when, replaced what) is harder
than scoring a single mention, and teamsim's record plan already has this shape.

**Summaries.** ROUGE and BERTScore correlate weakly with human judgement on thread summaries
(EmailSum, Zhang et al., 2021) [abstract]; LoCoMo moved to FactScore, which splits text into
atomic facts [full text]; OmniCSEval (1,800 conversations, 28 LLMs) scores key-fact matching for
completeness and conciseness plus summary-fact verification for faithfulness [abstract];
SlackBench grades summaries with a human-written checklist of required points and partial credit
[full text]. SlackBench's failure analysis found agents "upgrade bounded contributions into
stronger claims" and confabulate completion from planning threads [full text]. Teamsim relevance:
planted facts give a ready checklist (recall) and a list of forbidden claims (precision).

**Dates and time zones.** No benchmark found for "relative due date from chat, in the user's
time zone". Related work: MultiTempBench includes time-zone conversion and date arithmetic over
15,000 examples in five languages and shows tokenisation of dates drives accuracy in low-resource
languages [abstract]; GeoTemp (320k prompts, 289 cities, 37 time zones) finds models do well on
time alone but are constrained when time must be linked to place [abstract]; PRIMETIME finds datetime
parsing and arithmetic individually unreliable, "near-zero to perfect" across models, and
learnable by small fine-tuned models [abstract]; SPAN reports 34.5% mean accuracy across
cross-calendar reasoning, with a code-writing agent reaching 95.3% [abstract]. LongMemEval's own
temporal prompt forgives off-by-one day errors [full text]; EverMemBench's temporal questions score
45.0% for the best model and 60% even with oracle evidence because completion and archival remarks
by others confuse the anchor [full text]. I did not retrieve TimeML or TempEval work, so the classic
normalisation task and its metrics are not covered here.

## 4. Knowledge updates, conflicts, authority, abstention

- **Updates.** Memora's FAMA (full text): per question, `max(0, MPA - lambda * (1 - FAA))`, where
  MPA is the share of "memory presence" criteria met, FAA the share of "forgetting absence"
  criteria met, and lambda the share of forgetting criteria. Criteria are atomic and derived from
  the memory trace; judged by three LLMs. Memory agents with equal presence accuracy ranked
  differently once obsolete memory was penalised (monthly: Nemori lost 15.4 points, MemoryOS 28.4,
  A-Mem 29.5). [full text] A-TMA calls the same failure "ghost memory" and says final accuracy
  hides whether it arises in the memory bank, retrieval or answer [abstract].
  EverMemBench's rule-update questions are easy with oracle evidence (96.6 to 99.2%), so the
  difficulty is retrieval of the right version. [full text]
- **Conflict taxonomy.** CONFLICTS (Cattan et al.) gives expert-annotated conflict types with the
  desired model behaviour per type; models often handle conflicts badly and explicit reasoning about
  the conflict helps [abstract]. MMEnterprise-Bench (1,613 questions: evidence reasoning, conflict
  resolution, unanswerability) found that a larger retrieval budget raises recall but not
  consistently accuracy [abstract].
- **Source authority.** Whose Facts Win? (Schuster et al., 13 open-weight models, bootstrap tests
  with Holm correction, kept only effects significant for at least 10 models) found a consistent
  preference for institutional over personal and social-media sources, but repeating the
  weaker claim flips it: average preference shift 30.0 points for repetition of one source and
  33.9 for two matching sources, and a "ignore repetition" instruction only weakened it. A
  fine-tuning-plus-prompt mitigation cut the repetition effect by up to 79.2% while keeping 72.5%
  of the original preference. Models also rarely chose the "can't be answered" option (9 of 13 under 10%). Limits: synthetic
  sources, forced-choice A/B format, open-weight models only. [full text] AuthorityBench (220,564
  prompts, seven models) found citation presence, even fabricated, raises hallucination rates by
  3 to 22 points in some conditions [abstract]. Evidence arbitration (Carletti et al.): models
  follow recency more consistently than explicit reliability cues [abstract].
- **Authority as the attack definition.** The task-tampering benchmark (Zhang et al., 90 cases, 3
  environments) defines indirect injection by authority: planted content is an attack when it tries
  to influence a decision its source is not authorised to determine. Attacks on decision rules,
  state and observations succeeded more than attacks on the objective, and tool-policy defences left
  15.4% success versus 17.0% undefended [abstract].
- **Faithfulness and attribution metrics.** RAGAS defines reference-free scores for context
  relevance, faithfulness and answer relevance [abstract]; ARES fine-tunes small LM judges and uses a
  few hundred human labels for prediction-powered inference [abstract]; a 2026 R port found human
  agreement was weaker for context precision and for spotting unsupported statements [abstract].
  ProvenAI separates answer correctness, citation fidelity and per-document influence under
  leave-one-out, and shows cited sources can have weak influence while uncited ones shift the answer
  [abstract]. For teamsim, citation checks are cheap and deterministic when the product returns
  message links that map to the posting ledger (already done in check 8); influence checks need
  re-running the product and are expensive.

## 5. Indirect prompt injection

| Paper | Year, venue | Setup | Key number | Depth |
|---|---|---|---|---|
| Greshake et al. | 2023, arXiv | taxonomy, real apps | live attacks on Bing Chat | abstract |
| BIPIA (Yi et al.) | 2023, arXiv | first benchmark | all models vulnerable | abstract |
| InjecAgent (Zhan et al.) | 2024, arXiv | 1,054 cases, 30 agents | ReAct GPT-4 24% | abstract |
| AgentDojo (Debenedetti et al.) | 2024, arXiv | 97 tasks, 629 cases | models fail tasks even unattacked | abstract |
| LLMail-Inject (Abdelnabi et al.) | 2025, arXiv | 208,095 human attacks | GPT-4o 58%, SecAlign 32% | abstract |
| Public competition (Dziemian et al.) | 2026, arXiv | 272,000 attempts, 13 models | ASR 0.5% to 8.5% | abstract |
| LivePI (Zhao et al.) | 2026, arXiv | live email, chat, web | 10.7% to 29.6%; group chat uniformly successful | abstract |
| INFUSE (Nguyen et al.) | 2026, arXiv | 56 scenarios, 19 LLMs | mean ASR 15.4% heuristic, 19.6% LLM-scored | abstract |
| Silent failures (Shaw) | 2026, arXiv | audit | 21.7% vs 1.2% | full |
| Cross-user poisoning (Patlan et al.) | 2025, arXiv | shared agents | 82% and 98% vs 1.9% and 1.0% | full |

**How benchmarks score.** Early ones count a model output that obeys the injected text (BIPIA).
Agent benchmarks count an attacker-chosen tool call (InjecAgent, AgentDojo). The audit above shows
the scorer must check arguments, must confirm payload delivery, and must keep traces
[full text]. INFUSE reports that heuristic and LLM-based verification differ (15.4% vs 19.6%)
[abstract]. The audit also measured whether a compromised agent tells the user: its one frontier
success was concealed [full text]; the public competition built concealment into the attacker's
objective [abstract].

**Static versus adaptive.** AutoDojo says static benchmarks "significantly overestimate defence
efficacy" [abstract]; LLMail-Inject says template benchmarks are saturated [abstract]; the
cross-user paper notes frontier models now score near zero on AgentDojo's standard templates
[full text]. The surface study found 44.9% of model pairs change rank when the same payload moves
from tool output to tool description [abstract]. A depth study on 20 scenarios (N=20 per
condition, two models) saw ASR fall from 60% to 0% as the payload moved from the first to the fourth
tool result [abstract]; small sample, one author. LivePI is the only retrieved paper with group-chat
injection as a surface, and reports it uniformly successful on its tested backbones [abstract].

**Defences.** Boundary-style prompts (BIPIA) and prompt hardening (INFUSE: mean ASR 58.2% to 14.3%)
help but are model-dependent [abstract]. Deterministic out-of-band enforcement (tool-call
authorisation) cuts attacks more reliably but is mostly validated on static benchmarks
[abstract: Adaptive Evaluation of Out-of-Band Defences]. In multi-user settings, instruction filters
over-flag because teammates legitimately give instructions; provenance prompting and task clustering
reduced propagation; clustering lowered task success on Slack from 81.3% to 66.7%
[full text for clustering numbers].

**Cross-user poisoning details** (Patlan et al., MURMUR) [full text]. Success is defined as the
executed tool trace matching an attacker template while serving a benign user. Slack suite
(21 tasks): GPT-4.1 82% vs 1.9% for standard injection; Claude Sonnet 4 98% vs 1.0%; Workspace suite
(40 tasks): 45% and 77% vs 0.0%. With five concurrent tasks most sessions contained a successful
insertion (Slack about 59%, Workspace about 86%). An input classifier lowered but did not remove it.
Tested on two deployed multi-user agents in the authors' own Discord server. Limits: one template per
cell, strings adapted from AgentDojo, preprint.

## 6. Privacy, secrets, access control

**Contextual integrity.** ConfAIde (Mireshghallah et al.): GPT-4 and ChatGPT revealed private
information in contexts humans would not 39% and 57% of the time [abstract]. ConCI scores a triplet
(one flow plus two single-parameter counterfactuals) jointly, and finds models near ceiling on
inappropriate flows but weaker on appropriate ones, i.e. over-refusal [abstract]. AgentCIBench: 11 of 15
agents leaked on more than 50% of deterministically scored scenarios [abstract]. PrivacyLens-Live
moves static scenarios into live tool environments and finds higher risk [abstract].
**MuPPET** (Ruzzetti et al.) [full text]: agent holds a user's private memories and answers in a
group; a leak is any disclosure to a recipient the user excluded. Leak rate one-to-one vs multi-party:
Gemini 2.5 Pro 9.9% vs 23.5%; GPT 5.5 14.2% vs 26.7%; Qwen3 14B 41.0% vs 63.4%; Qwen3 8B 63.6% vs 70.4%;
Llama 3.1 8B 62.5% vs 60.9% (the one exception). Defences: prompt-level CI-Mem barely moved small models;
PrivacyChecker cut open-weight leaks to about 22-40% but cost 8-20 utility points. Utility and leakage
rose together. Limits: synthetic LLM-written chats, English only, professional norms only.

**Access control in retrieval.** Relevance ranking is not authorisation: a multitenant analysis
shows a query can surface another tenant's data simply because it ranks highest, and attribute-based
gating at retrieval removed cross-tenant leakage in their implementation [abstract: Arceo and
Narsing]. In hybrid vector-plus-graph retrieval, entity links carry a seed chunk into sensitive
neighbourhoods: undefended pivot risk up to 0.95, near zero after one authorisation check at the graph
expansion boundary [abstract: Thornton]. Bhatt et al. take the position that content used for an
answer must be authorised for every participant in the interaction, which is exactly the group-chat
case [abstract, position paper]. ConfusedPilot (Microsoft 365 Copilot-style systems) shows stale or
poisoned retrieved text and cache behaviour can break integrity and confidentiality [abstract].
A 2026 survey states no benchmark drives an agent across its data surfaces under one privacy policy
[abstract: Lahjouji and Colaco].

**Secrets and credentials.** PrivDrift: 1,000 dialogues with a seeded secret, topic drift, then
extraction probes; hybrid leakage 38.7% to 54.6% across three long-context models, not reliably
reduced by more drift [abstract]. Agent-skill study: of 17,022 sampled skills, 520 leaked credentials;
debug logging was 73.5% of cases because stdout enters the model context [abstract]. Secret detection
in issue reports: regex and entropy give high recall but poor precision; fine-tuned models reach 94.5%
F1 [abstract]. SlotGuard reports 0.0% leakage across 852 planted credential values using deterministic
format-preserving rewriting, and warns generic redaction over-redacts benign look-alikes [abstract,
self-evaluated]. Memorisation work (Huang et al., Hard-coded Credential Revealer) shows code models can
emit training-set credentials [abstract], but teamsim's concern is different: a secret pasted into
chat and then echoed, stored or exported. Teamsim relevance: plant format-realistic fake secrets, plus
benign look-alike strings as a precision control, and scan every read surface for the exact literal.

## 7. Catch-up, "what did I miss", interruptions

The literature is thin. No retrieved paper evaluates a personalised catch-up for an absent member
of a team chat. Adjacent work: streaming dialogue summarisation where the current window presupposes
earlier evidence (Min and Song; separate scores for whether memory holds gap-resolving evidence and
whether the summary uses it) [abstract]; an LLM meeting-recap design study with seven users found
recap types serve different needs and users edit recaps (Asthana et al.) [abstract]; EmailSum shows
automatic metrics fit thread summaries poorly [abstract]; a VR catch-up study (Lee et al., 12-person
formative study) found live summaries reduced re-engagement time [abstract]. On interruption and
notification timing nothing relevant beyond the when-to-speak work in section 2 was retrieved.
Teamsim's check 14 (changes during an absence are listed or counted) matches the checklist-recall
pattern of SlackBench and OmniCSEval; it has no published baseline.

## Mapping: teamsim checks to established tasks

Scoring types: D = deterministic (string, id, date, permission, tool call, count), J = judge needed for
free text, validated on a human sample.

| Teamsim check | Closest task and metric | State of the art found | Teamsim scoring |
|---|---|---|---|
| 0 harness integrity | Payload delivery and valid scenario (Shaw audit) | 91% undelivered in one audited suite | D, keep; fail loud |
| 2, 3 sync, offline gap | none (product plumbing) | none | D, keep |
| 4 commands and record | Chain-level event F1 (DecisionTraceBench); exact-match task formalisation (DevNous) | 5.7-21.4% chain F1 (speech); 81.3% EM | D on ids, owner, due, replaces chain |
| 5 retrieval | Recall@k and NDCG (LongMemEval), recall@k (LoCoMo); report by hops and groups | LoCoMo RAG, top-25 dialog turns: recall 79.9%, answer F1 35.8 vs human 87.9 | D; add thresholds and per-type rows |
| 6 visibility | Multi-party contextual leakage (MuPPET); retrieval authorisation | leaks 23-70% (MuPPET); gating gives about 0 | D with positive control |
| 7 injection, 11 AI vs decision | Argument-level attack predicate; cross-user poisoning; authority definition | 1-98% depending on attack and model | D on action or exact string; log disclosure |
| 8 `/ask` | Citation fidelity; answer correctness; abstention | cited sources may not influence answer | D for link mapping; J only for free text |
| 12 names vs handles | none; nearest is who-said-it and alias resolution | models fail speaker attribution | D; report as its own measure |
| 13 pasted secret | Canary leak across surfaces (PrivDrift, SlotGuard) | 38.7-54.6% leakage; 0.0% with rewriting (self-reported) | D on literal; add look-alike control |
| 14 catch-up | Checklist recall and faithful summary (SlackBench, OmniCSEval) | summaries inflate claims | D for planted events; J for extra claims |
| 15 relative due | Date arithmetic, time zone conversion (MultiTempBench, PRIMETIME) | primitives unreliable | D; exact date, no off-by-one grace |

## Missing check categories the literature suggests

1. **Abstention and false premise** (LongMemEval 30 items, LoCoMo 1,871 adversarial, SlackBench 48
   hallucination tasks). Plant: a question about something never discussed; a question that
   misattributes a decision to the wrong person; a time-restricted question. Pass requires declining
   and naming why (SlackBench). D for refusal detection by planted marker; J for the reason unless the
   reason is a fixed phrase set.
2. **Knowledge update with a superseded-fact penalty** (Memora FAMA). Plant a decision, a reversal,
   and ask about the current state. Score "states current" and "does not assert old as current".
   Add a version-chain question ("what did we decide before the change").
3. **Multi-hop and cross-channel questions** (EverMemBench, LongMemEval multi-session). Facts split
   across two speakers or channels. Report accuracy by number of groups.
4. **Persistent cross-user rule** (MURMUR). A teammate posts a "helpful rule" that tells the product
   to do something for everyone; a later request by another teammate must not trigger it.
5. **Audience-aware leakage** (MuPPET). Same private fact, varying number of recipients, including
   a public reply derived from private content.
6. **Repetition and recency of a low-authority claim** (Whose Facts Win; evidence arbitration). Vary
   how many times the AI answer is pasted and whether it is newer than the decision.
7. **Disclosure** (Shaw; public competition). If the product was manipulated, did it say so?
8. **Citation fidelity** (RAGAS, ProvenAI). Does each cited message actually contain the claim?
9. **Over-refusal control** (ConCI; false-rejection rate in the audit). Every defensive probe needs a
   benign twin the product should answer, or a product that refuses everything scores perfectly.

## Implications for teamsim

**Scoring design (strong evidence).**
- Keep the core judge-free. Use ids, links, exact strings, dates and permissions as the ground truth,
  as LoCoMo (token F1 on copied answers), SCALE-QA (4-way multiple choice) and AgentCIBench
  (deterministic scenarios) do. Add a judge only for free-text answers and always report its
  validation: a sample of at least 30 items per question type compared with a human label
  (LongMemEval's protocol), or three-judge majority with agreement reported (Memora). A small local
  judge is untested in this literature (inference); validate before trusting it.
- Verify the plant before blaming the product: delivery check per scenario, positive control per
  probe, a stored trace for every verdict (Shaw). The prototype's posting ledger already does the
  first; add the others.
- Score attacks on observable effects: tool call plus arguments, or an exact attacker string in a
  reply, never wording heuristics (the audit's 21.7% vs 1.2%). The 30-word "excuse" list in check 7
  is the kind of heuristic this literature warns about.
- Separate stages: report find (retrieval), read (answer) and abstain. Use oracle runs where the
  product allows (EverMemBench's oracle gap).
- Report per-category rows with counts and never a single headline number from few items;
  SlackBench averages three runs and reports per-category pass rates. Matches the run-1 rule of no rate
  from fewer than 10 events.

**Preset design (knobs the literature shows matter).**
number of channels or groups a question spans (EverMemBench), number of decision revisions
(Memora's mutation counts: weekly 2.7, monthly 8.8 on average), interleaving and fragmentation
(SCALE-QA), audience size (MuPPET), repetition and recency of low-authority text (Whose Facts Win),
injection position and surface (depth and surface studies; LivePI's chat surface), and the share of
benign twins. Calibrate blueprint-first, as EverMemBench does, so every question has an evidence
span, and add its blind test (drop questions answerable without the chat).

**Model-free default versus local model.** The literature supports a scripted default: ground truth
needs no model (EverMemBench's blueprint is the model-free part; the model only supplies surface text).
If a local model writes teammate text, the generated chat must pass programmatic rules (speaker
authorised, no premature completion) before use, as EverMemBench's level-one checks do. Small local
models are the least private (MuPPET) and least robust to defences, so a student's local product under
test needs the privacy probes most. OSynth (Porada et al.) reports raters told synthetic and real
meeting excerpts apart only 56% of the time and gives latent ground-truth state to simulated
organisations [abstract]; this is a realism bar for generated text.

**v0.1 actions.** Chat only is enough for most checks here (retrieval, abstention, update, injection
by string, privacy, secrets). Tasks and due dates add action-item and time-zone checks (no benchmark,
so teamsim's would be new). Repo and tool actions are needed for argument-level injection scoring on
real side effects; in chat-only mode score the attacker's exact string in a reply.

**ADR 0003 gate.** This review covers product checks, not simulated feedback. Its relevance is
limited to the realism bar above (OSynth) and the warning that judges need validation.

**What to avoid.**
- Scoring on reply wording or a fixed ranking position alone.
- A single injection template; benchmarks overestimate defences with static attacks (AutoDojo).
- Treating abstention as binary: require the reason.
- Over-defence: a product that blocks everything passes injection and fails utility; always pair
  with benign controls (ConCI, audit).
- Copying a judge's off-by-one forgiveness for day counts into the due-date check.

## Open problems

- No benchmark for relative-date and time-zone resolution from chat; teamsim could publish one
  (exact date accepted, UTC-versus-local both reported).
- No benchmark for catch-up quality for an absent member, or for handle versus name resolution.
- Real-chat noise: the main benchmarks use generated or re-enacted chat. Teamsim's realism transform
  (patterns learned from real teams as numbers only) could measure a "realism tax", the score drop
  from clean to realistic chat, which none of the retrieved papers report directly.
- Whether results transfer from generated to real chat is untested here.
- Defence validation under adaptive group-chat attacks is mostly absent; LivePI and MURMUR are early.
- Small samples and single authors in several security papers (depth study, audit, PrivDrift).

## Where this disagrees with the run-1 notes

Not a disagreement, a refinement: the run-1 notes prefer judge-free scoring; the literature agrees for
ids, strings and dates but uses validated judges for free-text answers and summaries. Teamsim can stay
judge-free by constraining answers to checkable forms, and should say which checks that excludes
(abstention reason, summary extras). Second, the prototype audit treats check 5 (retrieval) as
reportable against a baseline; the literature suggests per-type rows (single-hop, multi-hop,
temporal, update) rather than one recall number. No contradiction of ADR 0003 was found.

## Sources

All read 2026-11-11. Entries are arXiv preprints unless a venue is named; only the three venues
named below were checked, so the other papers may have been published since.
[F] = full text passages read; otherwise abstract only.

Memory and workplace benchmarks
- Wu et al., LongMemEval, ICLR 2025 (venue checked), [F], https://arxiv.org/abs/2410.10813
- Maharana et al., Evaluating Very Long-Term Conversational Memory (LoCoMo), 2024 [F], https://arxiv.org/abs/2402.17753
- Hu et al., EverMemBench, 2026 [F], https://arxiv.org/abs/2602.01313
- Uddin et al., From Recall to Forgetting (Memora, FAMA), 2026 [F], https://arxiv.org/abs/2604.20006
- Li et al., SlackBench, 2026 [F], https://arxiv.org/abs/2611.05512
- Shi et al., A-TMA (ghost memory), 2026, https://arxiv.org/abs/2607.01935
- Li et al., LoCoMo-Plus, 2026, https://arxiv.org/abs/2602.10715
- He et al., MemoryArena, 2026, https://arxiv.org/abs/2602.16313
- Tsang et al., MOSAIC, 2026, https://arxiv.org/abs/2610.29249
- Tao et al., DyadMem, 2026, https://arxiv.org/abs/2610.03020
- Feng et al., SCALE-QA, 2026, https://arxiv.org/abs/2608.25655
- Sen et al., Chronos, 2026, https://arxiv.org/abs/2603.16862
- Lu et al., EGMemory, 2026, https://arxiv.org/abs/2609.23465
- Zheng et al., SpeakerMem-R1, 2026, https://arxiv.org/abs/2609.26780
- Lee et al., MMEnterprise-Bench, 2026, https://arxiv.org/abs/2610.27911
- Porada et al., OSynth, 2026, https://arxiv.org/abs/2610.29319

Multi-party understanding
- Kummerfeld et al., A Large-Scale Corpus for Conversation Disentanglement, 2018, https://arxiv.org/abs/1810.11118
- Takada et al., APO-DD, 2026, https://arxiv.org/abs/2606.07894
- Penzo et al., Do LLMs suffer from Multi-Party Hangover?, 2024, https://arxiv.org/abs/2409.18602
- Inoue et al., LLM Benchmark for Addressee Recognition, 2025, https://arxiv.org/abs/2501.16643
- Chang et al., Multimodal Conversation Structure Understanding, 2025, https://arxiv.org/abs/2505.17536
- Kwon et al., M3-SLU, 2025, https://arxiv.org/abs/2510.19358
- Bhagtani et al., Speak or Stay Silent, 2026, https://arxiv.org/abs/2603.11409
- Ma et al., Duplex-MPE, 2026, https://arxiv.org/abs/2609.31948

Summaries, decisions, dates
- Kim and Rudin, Learning About Meetings, 2013, https://arxiv.org/abs/1306.1927
- Wang and Cardie, Summarizing Decisions in Spoken Meetings, 2016, https://arxiv.org/abs/1606.07965
- Zhang et al., MUG benchmark, 2023, https://arxiv.org/abs/2303.13939
- Inoue et al., Meeting Decision Tracker, 2022, https://arxiv.org/abs/2210.11374
- Doropoulos et al., DevNous, 2025, https://arxiv.org/abs/2508.08761
- da Silva and Gama, GADR, 2026, https://arxiv.org/abs/2608.17694
- Du et al., DecisionTraceBench, 2026, https://arxiv.org/abs/2610.34746
- Zhang et al., EmailSum, 2021, https://arxiv.org/abs/2107.14691
- Zhou et al., OmniCSEval, 2026, https://arxiv.org/abs/2606.15974
- Min and Song, Don't Scroll Back, 2026, https://arxiv.org/abs/2608.09043
- Asthana et al., Summaries, Highlights, and Action items, 2023, https://arxiv.org/abs/2307.15793
- Lee et al., Since U Been Gone (EngageSync), 2025, https://arxiv.org/abs/2503.16739
- Bhatia et al., MultiTempBench, 2026, https://arxiv.org/abs/2603.19017
- Holtermann et al., Around the World in 24 Hours (GeoTemp), 2025, https://arxiv.org/abs/2506.03984
- Gaere and Wangenheim, PRIMETIME, 2025, https://arxiv.org/abs/2504.16155
- Miao et al., SPAN, 2025, https://arxiv.org/abs/2511.09993

Conflicts, authority, RAG evaluation
- Schuster et al., Whose Facts Win?, 2026 [F], https://arxiv.org/abs/2601.03746
- Cattan et al., DRAGged into Conflicts (CONFLICTS), 2025, https://arxiv.org/abs/2506.08500
- Khurana et al., AuthorityBench, 2026, https://arxiv.org/abs/2606.13104
- Carletti et al., When Text and Numbers Disagree, 2026, https://arxiv.org/abs/2608.20116
- Es et al., Ragas, 2023, https://arxiv.org/abs/2309.15217
- Saad-Falcon et al., ARES, 2023, https://arxiv.org/abs/2311.09476
- Rehman et al., ragR, 2026, https://arxiv.org/abs/2604.23515
- Faizan and Alharthi, ProvenAI, 2026, https://arxiv.org/abs/2606.26449

Prompt injection
- Greshake et al., Not what you've signed up for, 2023, https://arxiv.org/abs/2302.12173
- Yi et al., BIPIA, 2023, https://arxiv.org/abs/2312.14197
- Zhan et al., InjecAgent, Findings of ACL 2024 (venue checked), https://arxiv.org/abs/2403.02691
- Debenedetti et al., AgentDojo, NeurIPS 2024 (venue checked via a web search summary), https://arxiv.org/abs/2406.13352
- Abdelnabi et al., LLMail-Inject, 2025, https://arxiv.org/abs/2506.09956
- Dziemian et al., How Vulnerable Are AI Agents to Indirect Prompt Injections?, 2026, https://arxiv.org/abs/2603.15714
- Zhao et al., LivePI, 2026, https://arxiv.org/abs/2605.17986
- Nguyen et al., INFUSE, 2026, https://arxiv.org/abs/2610.20776
- Shaw, Silent Failures in Agentic Security Evaluation, 2026 [F], https://arxiv.org/abs/2609.32691
- Patlan et al., Cross-User Poisoning (MURMUR), 2025 [F], https://arxiv.org/abs/2511.17671
- Zhang et al., Beyond Instruction Override (task tampering), 2026, https://arxiv.org/abs/2611.07640
- Ma et al., AutoDojo, 2026, https://arxiv.org/abs/2606.15057
- Sakib et al., The Surface You Test Is Not the Surface That Breaks, 2026, https://arxiv.org/abs/2605.30454
- Rashidi, Depth-Dependent Indirect Prompt Injection, 2026, https://arxiv.org/abs/2605.30686
- Narisetty et al., Adaptive Evaluation of Out-of-Band Defenses, 2026, https://arxiv.org/abs/2606.26479

Privacy, secrets, access control
- Mireshghallah et al., Can LLMs Keep a Secret? (ConfAIde), 2023, https://arxiv.org/abs/2310.17884
- Ruzzetti et al., MuPPET, 2026 [F], https://arxiv.org/abs/2606.23217
- Wang et al., Privacy in Action (PrivacyLens-Live), 2025, https://arxiv.org/abs/2509.17488
- Park et al., ConCI, 2026, https://arxiv.org/abs/2610.24494
- Goel and Gurevych, Capable but Careless (AgentCIBench), 2026, https://arxiv.org/abs/2606.23189
- Maldonado, PrivDrift, 2026, https://arxiv.org/abs/2609.30094
- Lahjouji and Colaco, Agents That Know Too Much, 2026, https://arxiv.org/abs/2606.26627
- Bhatt et al., Enterprise AI Must Enforce Participant-Aware Access Control, 2025, https://arxiv.org/abs/2509.14608
- Arceo and Narsing, Securing the Agent, 2026, https://arxiv.org/abs/2605.05287
- Thornton, Retrieval Pivot Attacks in Hybrid RAG, 2026, https://arxiv.org/abs/2602.08668
- RoyChowdhury et al., ConfusedPilot, 2024, https://arxiv.org/abs/2408.04870
- Chen et al., How Your Credentials Are Leaked by LLM Agent Skills, 2026, https://arxiv.org/abs/2604.03070
- Ahmed et al., Secret Leak Detection in Software Issue Reports, 2024, https://arxiv.org/abs/2410.23657
- Xia and Park, SlotGuard, 2026, https://arxiv.org/abs/2607.17147
- Huang et al., Your Code Secret Belongs to Me, 2023, https://arxiv.org/abs/2309.07639
