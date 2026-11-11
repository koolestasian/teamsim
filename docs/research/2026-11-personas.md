# Personas, realism and local models (2026-11-11)

Research for ADR 0003: how to make simulated teammates distinct, honest and measurable, cheaply
and locally. All pages were read on 2026-11-11. Where a number comes from a search excerpt or a
secondary page and not from the paper itself, it says so. Reddit was seen only as search
excerpts through a mirror site, so it is used for leads, never as evidence.

## Summary and recommendation

1. **Do not let the model invent the teammates' opinions.** Persona collapse, sycophancy and
   drift are measured, universal and not fixed by more personas. The script should own who each
   teammate is, what stance they hold and when they speak. The model only writes the words.
2. **Use a hybrid when generation is on.** Scripted timeline for ground truth and reproducibility
   (what the prototype does today), a model for wording and for replies to the product, with
   every accepted line recorded so a run can be replayed exactly. **An ordinary scored-test run
   needs no model at all** in this proposal: the scripted team stays the default, and generation
   is an option that feedback and reactive teammates need.
3. **Simulated feedback is measurable, but only partly.** Diversity and sycophancy can be scored
   with numbers on every run. Agreement with humans can be checked only at the level of the persona
   engine (public surveys), not for a given product. Ship feedback behind an "experimental" label
   until it passes a bar set in advance (see "Gate for simulated feedback").
4. **"Local by default" applies only when generation is on, and it is feasible only for a
   minority of messages.** A 3-4B model on an ordinary laptop
   CPU writes about 7 tokens per second. That is fine for tens of generated messages per run, too
   slow for hundreds. Talk to any OpenAI-compatible endpoint so the user picks the runtime.
5. **v0.1 teammate actions: chat plus tasks/issues, with repo events scripted only.** Details at
   the end.

## What the prototype does today

- Teammates are **fully scripted**. About 314 fictional messages from 6 people and a bot are posted
  from `fixtures/demo/dataset.json`, then a seeded transform adds fragments, reactions, off-topic
  bursts, image-only posts, pasted AI answers and a pasted fake secret
  (`simlib/script.py`, `REALISM.md`). There is no model call anywhere in the teammate code. The
  only model the prototype talks to is the one configured *inside the product under test*.
- Ground truth lives in ids and `answer_contains` strings. The fragment step shows the pattern a
  hybrid needs: when a message is split, the piece holding an eval answer keeps the dataset id, and
  a split that would cut the answer in two is skipped. The same check ("the planted fact survives
  the rewrite") generalises to model-written text.
- Reproducible by construction: one seed, same items every run.
- What it cannot do: teammates never read or react to what the product posts. Feedback
  ("this was confusing") needs that.

## 1. Techniques for distinct, non-sycophantic personas

| Technique | Evidence of effect | Cost | Use |
|---|---|---|---|
| Ground the persona in specific data, not just demographics | Agents built from interviews or surveys of 1,052 people reached 82-86% of the humans' own two-week retest consistency on held-out General Social Survey items; demographics-only agents reached 74% (Park et al., arXiv 2411.10109, v3 2026-06-28) | Interviews are expensive; teamsim can write short fictional life/work histories instead | Persona = role, habits, stated preferences, a list of stances. Not "35-year-old developer" |
| Persona prompts at all | Raise lexical diversity over no persona, more so in bigger models; very fine detail added little beyond a length limit (Kambhatla et al., EMNLP Findings 2025) | Free | Keep personas short; do not rely on detail for variety |
| Verbalized Sampling (ask for several answers with probabilities) | 1.6-2.1x diversity in creative writing, per the authors' abstract (arXiv 2510.01171, revised 2026-07-15). In a World Values Survey study it lifted fidelity 7-10 points but over-shot: spread ratio 0.4-0.56 (collapsed) became 1.26-1.37 (too wide) (Ozkan, arXiv 2607.18310, 2026-07-17; single author, one country, preprint) | One call returns several candidates | Useful for picking among candidate lines; tune it, do not trust it blindly |
| Re-inject the persona every turn | Both models tested drifted from their instructions within eight rounds (Li et al., COLM 2024, arXiv 2402.10962). The paper's fix, split-softmax, needs model internals | Stateless calls with a short history cost nothing extra | Never carry a long chat history; send persona + the last few messages each time |
| Truthfulness guard on agreeable personas | Recommended by Shah et al. (ACL 2026, arXiv 2604.10733, 13 small open models, 275 personas): agreeableness predicted sycophancy in 9 of 13 models (r up to 0.87) | Free | Add "be supportive but prioritise accuracy" to warm personas; measure first, effects differ per model |
| Third-person framing | Cut sycophancy by up to 63.8% in one debate scenario of SYCON-Bench (17 models, Findings of EMNLP 2025) | Free | Ask the model to write what the persona would say, not to be the persona. Check on small models |
| Script-assigned stance | Not a published technique; follows from the above. Persona collapse is universal and sampling more personas does not reduce it (Xiao et al., arXiv 2604.24698, 2026-10-16) | Free | The script decides "Dana thinks the import flow is confusing"; the model words it |

Two warnings from the same papers. Models with the best per-persona fidelity produced the most
polarised populations, so fidelity and diversity trade off (Xiao et al.). And a 0.6B model was
100% sycophantic whatever the persona (Shah et al.), so there is a floor below which a model
cannot play a critical teammate.

Caveats on the evidence: Shah et al. judge sycophancy by keyword stance detection on a forced
AGREE/DISAGREE format, not by an LLM or human judge, and its abstract (d up to 2.33) disagrees
with its tables (maximum 1.28). Read as direction, not size. PersonaGym (EMNLP Findings 2025,
arXiv 2407.18416) found GPT-4.1 and LLaMA-3-8b with the same PersonaScore, so a small model is
not automatically a worse persona; it also reports model size does not guarantee better persona
behaviour.

## 2. Measuring diversity and sycophancy with numbers

Cheap to run on every run, with no human in the loop, but not free. Knowing the *assigned* stance
does not tell you the stance the *free text* expresses, so every generated line first needs a
label. Two ways, and the choice sets the cost:
- *Constrained output:* the generator returns the line plus a stance tag in a fixed schema.
  Cheap, but the model grades itself, so validate the tags on a hand-labelled sample.
- *Separate judge or classifier:* one extra call per scored line. SYCON-Bench itself uses GPT-4o
  to judge each response (arXiv 2505.23840v4). Calibrate on hand-labelled lines.
Only the arithmetic after labelling (counts, entropy, TVD, flips) is standard-library code.
Lexical metrics and the planted-flaw check need no stance label (see below).

**Diversity**
1. *Lexical:* distinct-n and Self-BLEU over the teammates' lines for the same prompt. Cheap, but
   fooled by random words, so never use alone (precision/recall paper, arXiv 2402.10693).
2. *Stance spread:* label the stance each line expresses (see above), then compare with the
   assigned distribution. Use concentration, entropy and total variation distance, the
   collapse measures in Ozkan (concentration 0.36 to 0.69, entropy 1.46 to 0.77 when collapsed).
3. *Spread ratio:* standard deviation of the simulated answers divided by the human one. Collapse
   sits near 0.4-0.56, over-dispersion near 1.26-1.37 (same paper), so a pass band between them
   is defensible.
4. *Coverage and uniformity of the persona space:* the framework of Xiao et al. (three metrics:
   coverage, uniformity, complexity). Needs embeddings; optional.
5. *Embedding distance:* mean pairwise cosine distance between teammates' replies. Needs a small
   embedding model, which is a dependency question for the stack ADR.

**Sycophancy**
1. *Stance flip under pressure:* SYCON-Bench's Turn of Flip and Number of Flip. teamsim knows
   each teammate's assigned stance, so a flip is a labelled stance that differs from it; the
   label comes from the generator tag or a judge. SycEval (Stanford, AIES
   2025) reports 58% sycophantic behaviour across three frontier models with rebuttals, so
   expect non-zero flips.
2. *Planted-flaw test (teamsim's own idea, untested):* describe the product with one known flaw
   in its docs or behaviour. Score the share of teammates who raise it (a keyword or fact match
   against the planted flaw, so no stance label is needed). A sycophantic panel
   praises a product it was handed evidence against. Ground truth makes this a number.
3. *Validation rate:* ELEPHANT (arXiv 2505.13995, ICLR 2026) measures validation, indirectness,
   framing and moral sycophancy with human-validated LLM scorers; across 11 models users' face
   was preserved about 45 points more than humans did. Heavier: needs a judge model.

**Cost.** Lexical metrics, the spread ratio over labelled answers and the planted-flaw match are
arithmetic on text the run already has. Stance metrics add either a schema tag on each generated
line (no extra call, needs a validation sample) or one judge call per scored line (up to about
400 for a run the size of the prototype's). With a scripted, model-free run the stance is the
assigned one by construction, so these metrics only become informative once a model writes or
reacts.

**Judges are not neutral.** PersonaEval reports that role-play studies often lean on unvalidated
LLM judges (via search excerpt; not opened). Prefer rule-based and ground-truth checks, and
calibrate any judge on a few hand-labelled lines.

## 3. Scoring simulated feedback (ADR 0003)

ADR 0003 asks for three things before feedback ships. What the research supports:

| Requirement | Verdict |
|---|---|
| Diversity | Measurable per run, section 2 |
| Sycophancy | Measurable per run, section 2 |
| Agreement with published human results | Only for the persona engine, not for a given product |

I found **no public dataset of humans giving feedback on an arbitrary piece of software** that
could be a baseline. What exists is opinion data, usable to calibrate the engine:

| Dataset | What | Licence | Fit |
|---|---|---|---|
| Stack Overflow Developer Survey, 2011-2026 | Developer attitudes and tool use, ~49,000 respondents in 2025 | ODbL 1.0 (survey page) | Best topical fit: developers' trust in AI tools (2025: 46% distrust accuracy per the press release; secondary reports quote different prior-year baselines, so use the raw data). Whether row-level fields allow persona building is unverified |
| Twin-2K-500 (arXiv 2505.17479) | 2,058 US adults, ~500 questions over four waves, wave 4 repeats earlier items for test-retest | CC BY 4.0 | Individual-level calibration with a retest ceiling, as in Park et al. Not software feedback |
| OpinionQA (arXiv 2303.17548, ICML 2023) | 1,498 Pew American Trends Panel questions, 60 demographic groups | Not stated in the repo; check Pew terms | Group-level opinion distributions; mostly social and political topics |
| GlobalOpinionQA | 2,556 questions from Pew Global Attitudes and World Values Survey, per country | CC BY-NC-SA 4.0 | Non-commercial: fetch on demand, never bundle |

Usability studies are small. UXAgent's authors position LLM agents as a pilot step before human
studies, not a replacement (arXiv 2502.12561). A search excerpt mentions one persona study where
agents overlapped broadly with nine humans on ordinary interfaces and missed context-specific
issues; I could not open it, so treat it as a lead.

Evidence the bar is real: synthetic and human respondents give the same headline with
different spread (NN/g 2026-10-16, via the prior-art note); simulated users shift agent success
by up to 9 points depending on the model and are poor proxies for some English varieties
(Lost in Simulation, arXiv 2601.17087, 2026-01-23).

### Gate for simulated feedback (proposal, not evidence-derived thresholds)

Ship feedback as "experimental hypotheses" only if, on the shipped presets and default model:
- spread ratio against a public human survey is inside 0.8-1.25 on the calibration items;
- teammates keep their assigned stance in at least 90% of pushback sequences;
- the planted-flaw test is raised by a stated minimum share of the panel;
- every report prints these numbers and a line saying they test the engine, not the product.
Set the actual thresholds from a first baseline run, write them in an ADR, and let users supply
3-5 real human responses to their own product as an optional baseline.

## 4. Local models

All three common runtimes expose an OpenAI-compatible HTTP API, so teamsim only needs a base URL
and a model name (the prototype's host code already points a product at such a loopback
endpoint). Runtime choice stays with the user.

| Runtime | Install effort | Notes |
|---|---|---|
| Ollama (MIT, latest v0.40.16 on 2026-11-09) | Windows: `OllamaSetup.exe`, no admin, 4 GB disk; also a PowerShell one-liner. macOS and Linux: one shell command. Windows 10 22H2 or newer | API on `localhost:11434`; JSON-schema output via `format` or `response_format`; docs advise temperature 0 for steadier output |
| LM Studio | GUI installer; headless daemon `llmster` plus `lms` CLI for servers | Free for work use since 2025-07-08. JIT model loading |
| llama.cpp (MIT) | Prebuilt binaries, install script, Docker or source; `llama serve -hf <repo>` starts an OpenAI-compatible server | CPU, CUDA, Metal, Vulkan and more. The most control, the most to learn |

Ollama and LM Studio both run llama.cpp underneath, so for the same weights speed differs by a
few percent in community tests (secondary blogs; the figures conflict, treat as indicative).

**Speed on modest hardware** (generation, Q4 quantised). Memory bandwidth, not core count, is the
limit.
- 12 GB RAM Intel i5 laptop, CPU only, Ollama (itsfoss, 2026-05-15): Qwen3 0.6B 34-36 tokens/s,
  Gemma 3 1B 18.6, Gemma 4 E2B 9.9, Granite 4 3B 8.5-9, Phi 4 Mini 3.8B 6.9, 7-8B models 3-4.
  The author calls 15-30 tokens/s responsive.
- Apple silicon, Llama 2 7B Q4_0 (llama.cpp community thread, commit 8e672ef): M1 14, M2 22,
  M3 21, M4 24, M4 Pro 50 tokens/s.
- NVIDIA GPUs are far faster (an RTX 5090 at about 290 tokens/s on the same test) but cannot be
  assumed for students.
- Disk: 1B about 0.8 GB, 3B about 2 GB, 8B about 6 GB (same article).

My arithmetic from those numbers: a run that generates 60 lines of 60 tokens is 3,600 tokens, about
9 minutes at 6.9 tokens/s. Generating all 400 lines is about an hour of decoding alone, before
reading the prompts. Hence: local for a minority of lines, or on better hardware.

**Quality for role-play at small sizes.** Thin evidence; decide by teamsim's own metrics.
- Shah et al.: sycophancy varies widely across 13 models from 0.6B to 20B with no clear
  size trend; mid-sized 2B-8B models showed the strongest agreeableness effects.
- RPA-Check (arXiv 2604.11655, search excerpt): in one game, adequately tuned small models matched
  larger ones on behavioural consistency. A single setting.
- Structured output is the practical risk. In TinyTroupe issue 41 a user running a 1B Gemma model
  hit JSON extraction errors, and the library's maintainer wrote that non-OpenAI models "remain very much
  unstable" in that library (2026). Constrain output with a JSON schema and keep replies to one
  short plain-text line, not nested JSON.
- Reddit leads (mirror excerpts, anecdotes only): Gemma-family small models are praised for
  staying in character; Qwen gets mixed reviews. No head-to-head test found.
- No public role-play leaderboard I found ranks small local models credibly: RP-Bench's top
  entries are 26B+, and the other listings are vendor-run or proxy blends.

**Hosted fallback.** Anthropic's pricing page lists a small model at $0.10 per million input and
$0.50 per million output tokens (page read 2026-11-11). Estimate for 400 generated lines at
1,500 input and 60 output tokens each: about $0.07 per run. Needs a user key and sends fixture
text off the machine, so it must be an explicit opt-in with a visible notice. Any other vendor
with an OpenAI-compatible endpoint works the same way.

**Reproducibility.** Fixed seed plus temperature 0 is the standard advice, but it is best effort:
practitioner reports show different outputs across versions and hardware (blogs and forums; I did
not find an Ollama issue on it). Do not rely on it. Record and replay instead (next section).

## 5. Scripted, free LLM or hybrid

| | Scripted (prototype) | Free LLM | Hybrid (recommended) |
|---|---|---|---|
| Ground truth | By construction | Must be extracted afterwards; can be lost or invented | Planted by the script; a check confirms the fact survives the wording |
| Reproducible | Yes, seeded | No, even at temperature 0 | Yes, if generated lines are recorded and replayed |
| Cost | Zero | Every line, every run | Only the generated lines, once, then cached |
| Reacts to the product | No | Yes | Yes, for scripted reply slots |
| Realism of wording | Limited by what the author wrote | High but flat and agreeable | Script's variety, model's phrasing |
| Persona diversity | Written in | Collapses (Xiao, Ozkan) | Written in as stances; model adds wording |

Mechanics:
- The script emits *slots*: speaker, intent, stance, facts that must appear, length, time. A model
  fills a slot; a checker rejects it if a required fact is missing, a forbidden fact appears, or the
  stance label (generator tag or classifier) disagrees with the assigned one; reject, retry, then fall back to the scripted line.
- Two different stores. (1) A *generation cache* keyed on the complete request: model, prompt
  version, persona, slot, seed, the full conversation context given to the model, and the scenario
  version. For a reactive reply that context includes the product's message, so a changed product
  response is a cache miss and never reuses a reply written for an earlier one. TinyTroupe also
  caches model responses (its README, release 0.7.0, 2026-03). (2) An explicit *replay* of a
  recorded run: the whole sequence of posted lines is saved, and replaying it posts them as they
  were without calling a model or reading the product's output. Replay reproduces what the team
  said; it cannot show how the same team would answer a different product.
- A reactive teammate (replying to the product) gets a slot filled at run time with the product's
  message as untrusted data. Product output is untrusted input to the persona, as chat is to the
  product.
- Keep a no-model mode (scripted lines only) so the core test works with nothing installed.

## 6. How the realism patterns generalise

The prototype's 14 patterns come from one read-only sample of about 250 messages from one
8-person student team (REALISM.md). Treat them as hypotheses about habits, with n = 1, until
calibrated on more teams (numbers only, never text). Each pattern has a platform-neutral form:

| Pattern (from REALISM.md) | Chat | Tasks and issues | Repo |
|---|---|---|---|
| Bursty time, silence, time zones | Late-night bursts | Comment clusters near deadlines; relative due dates | Commits at odd hours, authored vs committed time |
| One thought in several posts | Message fragments | Several short comments in a row | Many small commits, "fixup" |
| Agreement by reaction | Thumbs-up on a request | Reaction on the issue, no comment | Approval with no review text |
| Information only in an attachment | Screenshot, log file | Screenshot in the issue body | Binary or generated files |
| Handle versus real name | Gamer handle in chat | Login differs from the name used in text | Git author name differs from account |
| Off-topic noise and slang | Banter bursts | "+1", "any update?" bumps | Typos in messages |
| Pasted AI answer | Quoted long answer | AI-written issue or comment | AI-written PR description |
| Decision outside the tool, then a recap or link | Call recap plus link | "Discussed on the call" with no detail | Decision only in a PR thread |
| Multi-task message, owner list | One post, several tasks | Checklist in one issue | One PR, several concerns |
| Conflicting dates, never resolved | Chat vs sheet | Milestone vs comment | Release notes vs tag |
| Member goes quiet, catches up | Absent then recap | Review requested, no answer | Unreviewed PR |
| Other bots, trolled | Bot answers | CI and dependency bots | Bot commits |
| Secret pasted in the open | Key in a channel | Token in an issue or log | Key in a commit |

Each row is already a *test of the product* (did it capture, rank, redact, or cope?) and is
scored the same way regardless of platform: the script knows where it planted the pattern. I did
not verify public corpora for calibrating the issue and repo columns; GitHub's public event archive
is a lead to check.

## 7. v0.1 teammate actions (persona side)

| Option | Persona and measurement impact |
|---|---|
| Chat only | Smallest surface; one text channel to score diversity and sycophancy on; everything in the prototype already fits |
| Chat plus tasks/issues | Same text modality and the same stance machinery, so the persona cost is near zero. Adds what many team products actually act on: assignments, status changes, due dates, comment threads. The extra cost is workspace-side state, covered by another task |
| Plus repo | Needs code written by the teammate. Small models are the weak point and there is no check of "teammate wrote correct code" cheaper than running it |

**Recommendation (a competing proposal, see "Where the run-1 notes disagree"):** chat plus
tasks/issues, with a small closed set of teammate actions chosen by
the script (post, reply, react, edit, delete, create a task, assign, change status, comment).
Repo support in v0.1 should be scripted events only (commit, open PR, review, merge) with no
model-written code. Ship scored tests first. Build the diversity and sycophancy meters into v0.1
because they also test the chat teammates, but keep simulated feedback behind the gate in
section 3 until it passes.

## Where the run-1 notes disagree

Two points where this note differs from the other run-1 notes (the prior-art and emulator notes).
They are competing proposals for the maintainer to decide, not settled.

1. **v0.1 teammate actions.** The prior-art and emulator notes recommend **chat only** for v0.1,
   with issues next through an existing emulator and repo last (the emulator note: v0.2 issues,
   after the first user is chosen). This note recommends chat **plus tasks/issues** from the
   persona side, because the persona cost is near zero. That argument ignores the emulator,
   fixture and scoring work the other notes count, which is where the real cost sits. If that
   cost is as they say, chat only first is the safer order and nothing in the persona work
   changes: the stance machinery carries over to issue comments later.
2. **Model by default.** The prior-art note recommends a scripted, seeded, **model-free default**
   with LLM-played teammates as an optional layer, and no "local model by default" promise until
   a model is shown able to play a teammate. This note agrees on the default: an ordinary
   scored-test run needs no model. Where it adds to that note: if generation is on (reactive
   teammates, simulated feedback), prefer a hybrid with recorded lines, and "local by default"
   applies only in that mode, only for a minority of lines on laptop CPUs, and only after the
   candidate models pass the diversity and sycophancy checks here.

## What I could not verify

- Whether Stack Overflow survey rows carry the fields needed to build personas and whether the
  raw download is CSV; the survey page names the licence and the years only.
- Pew terms for redistributing OpinionQA responses; the repo states no licence.
- The persona-study overlap figure (agents vs nine humans) and the 73-77% usability-issue figure
  that appeared in search excerpts; neither source was opened.
- Reproducibility claims for Ollama beyond blogs and forums; no issue found.
- Any role-play benchmark ranking of local models of 8B or below.
- CPU speeds beyond one laptop (itsfoss) and Apple silicon (Llama 2 7B, not an 8B model); other
  CPUs and newer chips are unmeasured here.
- The paper numbers come from arXiv abstract pages or fetched paper text summarised by a reading
  tool, not from my reading of the PDFs. Park et al. changed from 85% (v1) to 82-86% (v3).
- Reddit and X: only search excerpts, nothing from X.

## Sources (all read 2026-11-11)

Papers: arXiv 2407.18416 (PersonaGym), 2505.13995 (ELEPHANT), 2502.08177 (SycEval), 2505.23840
(SYCON-Bench), 2604.10733 (Shah et al.), 2604.24698 (Persona Collapse), 2607.18310 (Ozkan), 2510.01171
(Verbalized Sampling), 2411.10109 (Park et al.), 2402.10962 (persona drift), 2511.00222
(persona consistency metrics), 2601.17087 (Lost in Simulation), 2502.12561 (UXAgent), 2505.17479
(Twin-2K-500), 2303.17548 (OpinionQA), 2306.16388 (GlobalOpinionQA), 2402.10693 (diversity
metrics), 2604.11655 (RPA-Check, excerpt). Kambhatla et al.: aclanthology.org/2025.findings-emnlp.1146.

Tools and data: github.com/microsoft/TinyTroupe (README, issue 41), github.com/sotopia-lab/sotopia,
github.com/ollama/ollama, docs.ollama.com/windows, docs.ollama.com/capabilities/structured-outputs,
github.com/ggml-org/llama.cpp (README, discussion 4167), lmstudio.ai/docs/developer/core/headless,
lmstudio.ai/blog/free-for-work, itsfoss.com/testing-local-llms-without-gpu, survey.stackoverflow.co,
stackoverflow.co/company/press/archive/stack-overflow-2025-developer-survey,
huggingface.co/datasets/LLM-Digital-Twin/Twin-2K-500,
huggingface.co/datasets/Anthropic/llm_global_opinions, github.com/tatsu-lab/opinions_qa,
platform.claude.com/docs/en/about-claude/pricing.
