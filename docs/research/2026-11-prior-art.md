# Prior art (first pass 2026-11-10, deep pass 2026-11-11)

The first pass came from search results and a few primary pages. The deep pass (2026-11-11)
read the source of the projects below with the GitHub API (README, code layout, issues, recent
merged pull requests) and added papers found through paper search. Dates are the day a source
was checked (2026-11-11) unless a date is given. Reddit threads were seen only as search
excerpts. Nothing was installed or run: setup cost below comes from READMEs and docs, not from
hands-on runs. A list of what could not be verified is at the end.

## Opinion prediction: well funded, weak evidence

- **Simile**, founded by researchers behind Stanford's generative agents, raised a $100M
  Series A and then a $200M Series B at a $2B valuation (2026-07-30). Enterprise customers
  include CVS Health, Deloitte and Gallup.
  Source: designwhine.com/synthetic-user-research-accuracy-ai-respondents (2026-10-29), citing
  TechCrunch.
- **Synthetic Users**, **Aaru** and **Viewpoints.ai** sell surveys of synthetic audiences.
  Sources: syntheticusers.com, aimultiple.com/synthetic-users.
- **MiroFish** (github.com/666ghj/MiroFish): about 85k stars, AGPL-3.0, top of GitHub trending
  in March 2026. Thousands of LLM agents role-play a social network (built on camel-ai/OASIS) to
  "predict anything". Setup needs Node 18+, Python 3.11-3.12, uv, an LLM key and a Zep Cloud
  key, and it warns about token cost. Reviews say plausible is not accurate, and there is no
  evidence its predictions are right. Sources: the repository README; jervis.kr/en/insights/mirofish;
  yourstory.com (hype vs reality).

## What the evidence says about simulated people

- **NN/g (2024-06-21):** synthetic users are sycophantic, too favourable and flat. They care
  about everything equally and outperform real people on tasks. Use them for hypotheses and
  pilots, never for decisions. nngroup.com/articles/synthetic-users
- **NN/g follow-up (2026-10-16):** 120 synthetic and 604 human respondents gave the same
  headline answer, but the synthetic group varied far less.
- **Pew (2026-09):** digital twins were off by 12.4 points on average, more for subgroups.
- **SSDataBench (2026):** models compress populations into cleaner, more typical patterns.
- A synthetic test participant described pricing tiers that did not exist on the page.
  (The last three via the designwhine article above.)
- **"Lost in Simulation"** (arXiv 2601.17087, 2026-01): on tau-bench, agent success varies by up
  to 9 points depending on which LLM plays the user. Results are miscalibrated, and simulated
  users are a worse proxy for AAVE and Indian English speakers. They add conversational
  artefacts and fail differently from humans.

## Simulated people who act on software

- **TheAgentCompany** (CMU, arXiv 2412.14161, NeurIPS 2025): a self-hosted fake company
  (GitLab, OwnCloud, RocketChat, Plane), 175 tasks, and simulated colleagues with profiles built
  on Sotopia. A benchmark for AI agents, heavy to set up. Closest to teamsim's "actions" idea.
- **OASIS** (camel-ai/oasis, Apache-2.0): up to a million agents on fake X and Reddit. A
  research tool.
- **TinyTroupe** (Microsoft, MIT): a Python library for persona simulation.
- **Chat-agent testers:** promptfoo's simulated user, MLflow conversation simulation, AWS Strands
  ActorSimulator and the Cognigy Simulator. Code-first, and they test chatbots only.
- **AI QA agents** explore a web UI with a single agent, no team: Explorbot (open source, small
  models), autoexplore, Finalrun (Android). Sources: testomat.io/blog/autonomous-testing,
  wopee.io/blog/ai-testing-agents.

## Deep pass: source-level comparison

Eight projects named in the milestone, then newer ones (created on GitHub since 2026-09-01,
found by GitHub repository search and the Reddit and web searches listed at the end). Stars and
push dates are from the GitHub API on 2026-11-11. "Ground truth" means the simulator knows what
is right and scores against it, not an LLM's opinion.

| Project (licence, stars) | What it simulates | Setup cost (from README) | Ground truth | Learn or avoid |
|---|---|---|---|---|
| [TinyTroupe](https://github.com/microsoft/TinyTroupe) (MIT, 7.6k) | Personas in a small world; focus groups, ads, test input to chatbots | Python 3.10+, OpenAI or Azure key (default gpt-5-mini). Ollama is "experimental". Built-in cost tracking | None for the world. Has an empirical validator (t-test, KS-test) against real survey data | Learn: ship the validator against human data. Avoid: API churn ("expect frequent changes") and notebook-first use |
| [OASIS](https://github.com/camel-ai/oasis) (Apache-2.0, 5.4k) | Up to 1M agents on fake X and Reddit with recommender feeds | `pip install camel-oasis`, OpenAI key. README table: 100 agents, 1 step, every agent active = 335,600 input and 16,750 output tokens | None | Learn: publish a token-use table. Avoid: scale as the pitch; a team has 5 to 50 people |
| [MiroFish](https://github.com/666ghj/MiroFish) (AGPL-3.0, 85k) | Social network of LLM agents plus a knowledge graph, to "predict anything" | Node 18+, Python 3.11-3.12, uv, LLM key, Zep Cloud key; README warns of high token use and suggests under 40 rounds first | None seen. Open issues: entity extraction not deterministic at temperature 0 (#759), a different persona cohort on every run (#751), finished runs stuck as "running" (#855, #845), local vLLM without tool calling fails silently (#847) | Learn: determinism and visible failure are what users hit first. Avoid: a cloud dependency, prediction claims, AGPL code |
| [TheAgentCompany](https://github.com/TheAgentCompany/TheAgentCompany) (MIT, 813) | Fake software company: GitLab, ownCloud, RocketChat, Plane; LLM colleagues (NPCs) | Docker, 30+ GB disk, baselines ran on a t3.2xlarge. Needs an "environment LLM" at least GPT-4o or Claude 3.5 Sonnet class to play NPCs and grade. Last push 2025-11-17 | Yes: 175 tasks, each a Docker image with init and grader scripts (graders encrypted); some checks use an LLM | Learn: a task is data plus a grader. Avoid: weight, and needing a strong model just to play a colleague |
| [Sotopia](https://github.com/sotopia-lab/sotopia) (MIT, 342) | LLM agents with private goals in social scenarios | `uv sync`, OpenAI key, Redis by default (Docker) or a local JSON store | No planted facts; an LLM evaluator scores goal completion, plus rule-based end conditions | Learn: scenario = characters, goals and relationship as data. Avoid: scoring only with an LLM judge |
| [tau-bench](https://github.com/sierra-research/tau-bench) and [tau2-bench](https://github.com/sierra-research/tau2-bench) (MIT, 1.5k and 2.4k) | An LLM user talks to a tool-using agent (airline, retail, telecom, banking); 2.0 adds six languages and voice | `uv sync`, `.env` with a key. `--dry-run` prints the plan; `--num-tasks 2` is a 12-call smoke test | Yes: the final database state is compared with the expected state (the tau-bench code hashes it). Newer communication checks use an LLM judge, and the docs mark some judges "unvalidated" | Learn: state-based truth, frozen versioned task sets, a stated validation status per judge, no rate shown from fewer than 10 events. Avoid: trusting one user LLM (open issues: simulator adds a passenger not in the task #172, ends too early #182, writes several turns in one message with gpt-oss-120b #710) |
| [promptfoo simulated user](https://github.com/promptfoo/promptfoo) (MIT, 27k) | One LLM user in a 1:1 chat with your agent | `npx`, YAML: `instructions`, `maxTurns` (default 10), `###STOP###`, optional `initialMessages` to start mid-conversation | Only what your own asserts check | Learn: scenario as a few lines of YAML; start from a saved state. Avoid: sending data to a vendor API by default (issue #5808, 2025-10-03; I did not check whether the simulated-user part was changed) |
| [Gnomi](https://github.com/svichas/Gnomi) (AGPL-3.0, 1; created after 2026-09-01) | Personas explore your idea, staging app or design, talk, and leave findings | Desktop installers (unsigned) or Node 24.15; provider key, or `GNOMI_FAKE_LLM=1` for free scripted personas | None. Trust labels: Observed (instrumented), Reported (persona said it), Confirmed (they match) | Learn: its [interpreting-simulations](https://github.com/svichas/Gnomi/blob/main/docs/interpreting-simulations.md) page is the best honesty wording found. Avoid: AGPL code |
| [MarketMirror](https://github.com/DarkWorldCoder/market-mirror) (AGPL-3.0, 16; new) | Synthetic buyers (built on MiroFish and OASIS) react to ads, prices and pitches | Linux, macOS or WSL, uv, Python 3.12, a model provider; the quickstart already makes paid model calls | None for the run. Ships a bench that scores simulated answers against open human data | Learn: publish a bench with misses included (see below). Avoid: the persona-panel design the bench itself undermines |
| [simulacra](https://github.com/misakaikato/simulacra) (Apache-2.0, 2; new) | Typed, event-sourced social simulation with a robustness audit | Bun 1.3+; a `mock` provider runs offline with no key; any OpenAI-compatible endpoint | None; same scenario and seed give the same digest; LLM calls recorded and replayed byte for byte | Learn: seeds, record and replay, failures counted as data. Avoid: social-science scope |
| [convy](https://github.com/deyna256/convy) (MIT, 5; new) | Simulated user talks to your agent through its API; a judge checks claims | `uvx convy init`; 4 dependencies, no account; `--smoke` run calls no model | Only an LLM judge on plain-language claims | Learn: free smoke mode, small dependency list, pass rate over repeated attempts. Avoid: judge-only scoring |
| [chaosfolk](https://github.com/loukan42/chaosfolk) (MIT, 20; new, alpha 0.8.0) | Simulated users explore a web app in a real browser | One-line installer; driven from a coding agent | None planted; a catalogue of 116 checks, replayable browser evidence | Learn: evidence you can replay. Avoid: coupling to one workflow |
| [Agent Proof Lab](https://github.com/shivanathd/google-ax-agent-proof-lab) (MIT, 2; new) | Emulated Slack with scripted people (one asks, another approves) and local queues | One laptop; no workspace or key for the local core | Yes: an independent collector with its own read-only credentials checks the ticket, receipt and thread | Learn: score from the world's state, not from what the agent says. Avoid: single hand-written scenarios |
| [emulate](https://github.com/vercel-labs/emulate) (Apache-2.0, 2.0k; created 2026-03-20, adjacent) | Stateful local copies of Slack, GitHub, Linear, Google, Stripe and others (no Discord in its list) | `npx emulate`, loopback ports, signed Slack callbacks | n/a: an environment, no people | Learn: reuse instead of rebuilding API emulators. Fidelity was not tested |
| [sarangbang](https://github.com/SpringWindsTeam/sarangbang) (Apache-2.0, 11; new) | Group-chat simulation of citizens discussing a topic (Korean) | `pip`, one dependency (httpx); one preset switches between hosted APIs and local vLLM or Ollama models | None | Learn: model presets as one switch; prompts and post-processing needed tuning per model to curb repetition and invented content |

Also seen, not read in depth: cryer/agent-eval (MIT, CI for LLM agents with statistics), LangWatch
Scenario and AWS Strands ActorSimulator (code-first user simulators, see
langwatch.ai/blog/how-to-evaluate-multi-turn-conversations and the AWS machine-learning blog on
Strands Evals), ArkSim (Reddit excerpt, r/LLMDevs).

### Notes

- **Nobody plays a team with planted facts.** Every project above simulates one user talking to
  one agent (promptfoo, convy, tau2, Scenario, Strands), a crowd for opinions (OASIS, MiroFish,
  Gnomi, MarketMirror, TinyTroupe), or scripted flows (Agent Proof Lab). TheAgentCompany has
  colleagues but only to serve an agent's task, and costs 30 GB. The combination teamsim
  proposes (a team, a workspace, planted ground truth, one command) was not found.
  The caveat: the search was by keywords on GitHub, Reddit and the web; a private or
  unindexed project would not show up.
- **Cost is dominated by the model, so the default should not need one.** OASIS: 336k input
  tokens for 100 agents for one step. MiroFish and TheAgentCompany both require strong hosted
  models. Small local models are weak simulators: tau2 issue #710 (gpt-oss-120b writes several
  turns in one message), MiroFish #847, TinyTroupe's own "experimental" Ollama note, and
  sarangbang's per-model prompt tuning. The prototype avoids this: its team is scripted and
  seeded (the model is used only by the product under test).
- **Determinism is the first thing users hit.** MiroFish #759 and #751 (same input, different
  result). simulacra solves it with seeds and recorded calls; tau2 with frozen task sets.
- **Honest labelling is becoming normal.** Gnomi's trust labels, MarketMirror's A-D evidence
  grade and "misses included" results file, and tau2's "unvalidated judge" flags all say what a
  number does not show.
- **Licences.** MiroFish, Gnomi and MarketMirror are AGPL-3.0. teamsim is MIT OR Apache-2.0
  (ADR 0001), so their code cannot be copied in; ideas and published numbers can be used with credit.
- **Activity.** TheAgentCompany is quiet since 2025-11-17. tau2, OASIS, TinyTroupe and promptfoo
  merged changes in the last month. tau-bench (v1) says its tasks are outdated and points to tau2.
- **The new projects are small** (all under 30 stars, weeks old). They show where builders are
  heading, not that any of them works.

## (a) Simulated feedback: can it meet ADR 0003's bar?

### Evidence on reliability

Abstracts only (full texts not read). Preprints unless noted.

- **Flat and compressed.** "Plausible but Not Valid" (arXiv 2608.14606; 37 LLMs, 263 employees):
  synthetic respondents compress the response scale (within-person SD 0.79 vs 1.19 for humans),
  lose predictive validity on held-out humans (R2 -0.14 vs 0.28), and a simple classifier tells
  every LLM sample from humans (AUC 0.99). Statistical baselines with no language model match
  or beat them. "The Chameleon's Limit" (2604.24698): persona collapse is universal; sampling
  more personas does not fix it; the models with the best per-persona fidelity give the most
  polarised populations. NN/g's 2026 follow-up reports the same: same conclusion, less variation,
  rare answers missing (nngroup.com/articles/synthetic-users-vs-human-respondents/, search excerpt
  only).
- **Personas often do not help.** Maiorano et al., 2026 (2609.25010): on Upworthy headlines a
  plain "generic reader" prompt beat a 10-persona panel (top-1 54.8% vs 39.1% with Gemini,
  61.7% vs 42.0% with GPT-4.1). MarketMirror-Bench's own first run (2026-11-01, 50 tests and 20
  people, wide ranges): no persona 64% vs persona panel 44%; the panel agreed (at least 80%
  picking one headline) in 66 to 75% of tests; every method predicted far more buying (64 to 70%)
  than real people reported (43%). Source: its benchmarks/bench/RESULTS.md. "What Would GPT
  Click" (2605.18302; 12 first-click tests, n = 3,431): distributions differed significantly from
  real data in 53% of tasks, and personas or reasoning only inflated believability.
- **Modest signal at best.** Bojic et al. (Scientific Reports, 2026, arXiv 2604.19787): persona
  agents predicted individual social-media reactions above chance (MCC 0.29) but a TF-IDF
  classifier did better (0.36), and the choice of LLM moved accuracy by 13 points. A paper
  titled "Digital twins are funhouse mirrors" (preregistered, 19 studies, 164 outcomes) reports
  an average correlation of 0.20 with humans and five distortions, including stereotyping and
  hyper-rationality (venue and link not verified; seen through paper search 2026-09-04).
  "Silicon Sampling via Cross-Survey Transfer" (2607.03091): 52% on unseen survey items, within
  6 points of a supervised random forest.
- **Sycophancy and kindness.** ELEPHANT (2505.13995): across 11 models, LLMs preserve the user's
  "face" 45 points more than humans. "Too Nice to Tell the Truth" (2604.10733): the more
  agreeable the persona, the more sycophantic, with correlations up to 0.87 in 9 of 13 small
  models. That matters here because teammates should vary in agreeableness.
- **Simulated users are easier than real ones.** "Mind the Sim2Real Gap" (2603.11245; 451
  humans, 165 tasks, 31 simulators): simulators are too cooperative and stylistically uniform,
  creating an "easy mode", and give uniformly more positive feedback than humans. "Simulated
  Customers Never Walk Away" (2606.20708; 793 conversations with verified payments): simulators
  halve the resistance real non-buyers express (25.1% to 13.5%). Both fit the NN/g finding.
- **What does help.** Grounding behaviour in real data, not demographics: RealUserSim
  (2605.20204) raised style match with real users from 24.2% to 45.3%; Persona Policies
  (2605.12894) made simulated users look human to annotators 80.4% of the time, about twice the
  baseline. Both change how people behave (impatient, vague, reluctant), not who they are.
  "When Can You Trust Your Synthetic Users?" (2609.13148) says correcting a synthetic panel needs
  real human outcomes, and its intervals covered only 88 to 94% in some regimes.

### How people measure it

| What | Method | Source |
|---|---|---|
| Diversity | Coverage, Uniformity, Complexity of responses across personas | 2604.24698 |
| Diversity | Mean pairwise cosine similarity and effective rank of agents' answers (0.888 and 2.17 of 3 in one committee) | 2604.03809 |
| Diversity | Within-person spread vs humans; share of tests where at least 80% of agents agree (herding) | 2608.14606; MarketMirror-Bench |
| Sycophancy | Social-sycophancy benchmark; sycophancy rate vs persona agreeableness | 2505.13995; 2604.10733 |
| Human match | Same task as an open human dataset, with intervals and a no-persona baseline: Twin-2K-500 and the Upworthy archive (both CC BY 4.0 per MarketMirror-Bench) | MarketMirror-Bench RESULTS.md |
| Human match | Statistical tests of simulation vs real survey data (t-test, KS-test) | TinyTroupe `SimulationExperimentEmpiricalValidator` |
| Human match | A User-Sim Index scoring how a simulator resembles real users | 2603.11245 |
| Test-retest | Normalise accuracy by the humans' own test-retest agreement (0.838 in Twin-2K-500) | MarketMirror-Bench RESULTS.md |

### What an honest, measurable feedback feature needs

1. **Baselines first.** Every result is shown next to a no-persona prompt and a trivial
   baseline; a persona panel is not credited unless it beats them (it often does not).
2. **A diversity report in every output**, from at least one measure above, with a limit chosen
   before running.
3. **A sycophancy check:** a deliberately bad idea or product that teammates should reject, and
   a flip-on-pushback probe. Report the agreement rate.
4. **Planted-issue recall (this is teamsim's own contribution, not from the literature).**
   Plant known defects or confusions in the product description or workspace and score how
   many the teammates raise unprompted, and how many invented ones they add. This needs no
   human data, uses the ground truth teamsim already has, and measures the part simulation does
   well (finding defects) instead of the part it does badly (predicting preference).
5. **Behaviour, not demographics.** Vary patience, vagueness and reluctance (RealUserSim,
   Persona Policies), and give each teammate a stated agreeableness that is measured, not
   assumed.
6. **Human comparison only where open data exist,** on proxy tasks (headline choice, price
   answers), reported with intervals. This validates the method, not the product.
7. **Labels and counts.** Each output says "simulated, unvalidated"; every rate shows the
   events behind it and is hidden under 10 (tau2's rule); seeds, model id and recorded calls
   are saved so a run can be replayed.

### Verdict

Partly yes, and not for v0.1. Against ADR 0003's three conditions:

- **Measured diversity:** yes. Instruments exist and are cheap (embedding similarity, coverage,
  herding rate). The evidence says the numbers will be poor, which is the point of showing them.
- **A sycophancy check:** yes, by planted bad ideas and pushback probes. Also expected to look bad.
- **Comparison with published human results:** only on proxy tasks. I found no open dataset of
  how a team reacts to a software product or a bot's behaviour, so the main use case cannot be
  calibrated. Say so in the output.

So the feature can meet the bar as written, as a measured hypothesis generator (planted-issue
recall, plus diversity and sycophancy reports) and not as an opinion or adoption forecast. The
bar in the ADR says what to measure but not what result is good enough; thresholds should be
set from the baselines before the first run. Ship it after the scored tests, behind its
reports, and wait if the reports look bad.

## (b) First user

| Segment | Evidence for the need | Evidence against or gaps |
|---|---|---|
| **Builders of team-facing software** (bots, integrations, agents that live in team chat) | Slack's own bolt-js issue "How To Add Testing" (#638) has been open since 2020-09-22 (last activity 2024-09-15) and Slack's test tool Steno is archived (GitHub API, 2026-11-11). A dev.to post dated 2026-11-11 lists the workarounds (a second bot plus ngrok, patching HTTP, the real API in CI); the author sells a small mock library, so treat it as a lead. A Reddit thread (r/Discord_Bots, excerpt only) has a team told to add tests with no idea how. Supply is arriving: emulate (2.0k stars, Slack, GitHub and Linear emulators) and small October 2026 projects (a Slack and Linear sandbox, a Slack emulator, Agent Proof Lab) | All of those emulate APIs or script flows; none plays people with ground truth. Demand is inferred from tools being built and old issues, not measured. The chat-agent testers (promptfoo, Scenario, Strands, convy, ArkSim) already serve the 1:1 case, and a Reddit excerpt says most teams chat with their agent a few times and ship |
| **Students testing a bot or agent** | The prototype itself was built for a student team server (one case, the maintainer's own). Students cannot run what exists: MiroFish needs two runtimes and two keys, TheAgentCompany 30 GB and a strong hosted model | Thinnest evidence: no forum, issue or post found that asks for this. A student is a builder of team-facing software with less money; the need is the same, the constraint is cost and setup |
| **Solo builders wanting early feedback** | Strongest appetite: by title, about 24 of the 100 most recent MiroFish issues are business ideas typed into the issue tracker by people (mostly non-English, apparently non-developers) who treat the repo as the product. Simile raised $200M; Gnomi, MarketMirror and Synthetic Users target them | The segment with the strongest evidence of unreliability (section above), the most funding and the most competitors. A Reddit excerpt (r/SideProject) warns that AI validators just encourage. Scored tests do not serve them |

**Recommendation: builders of team-facing software**, with students as the group the "easy to
run" goal is for, not a separate product. Reasons: (1) it is the only segment where the
measurable core applies today, because the person has a product and wants to know whether it
handles a team's messy chat; (2) the pain is documented and long-standing; (3) the prototype
already does this for one product; (4) emulators exist but nobody plays the people in them; (5)
it stays out of the funded, weakly evidenced opinion market.

**Weak points of this evidence.** It is indirect (tools being built, one old issue, one promotional
post, Reddit excerpts), there were no interviews or surveys, and the one known user is the
maintainer. X returned nothing useful. The size of the segment is unknown. Validating it means
showing a recorded run to real builders, which is outward-facing and needs the maintainer.

### What teammates can do in v0.1 (input to the open decision)

Evidence points to **chat only** first: the prototype's checks are chat checks, scripted and
seeded teammates need no model, and tasks and issues are a separate emulator problem (emulate
already covers GitHub and Linear; TheAgentCompany shows the cost of building a full tracker).
Tasks and issues next, through an adapter to an existing emulator rather than a new one. A code
repository last. Moderate confidence: this comes from what exists and what is cheap, not from
asking users.

## What this means for teamsim

1. Stay with ADR 0003's order: scored tests are the core; simulated feedback comes later, as a
   measured hypothesis generator (see the verdict), never as a forecast.
2. First user: builders of team-facing software. Students are served by the one-command, no-key
   goal, not by a separate design.
3. A scripted, seeded team is the default and costs no model calls. LLM-played teammates are an
   optional layer with recorded calls (simulacra's pattern). This resolves a tension with "local
   model by default": the evidence says small local models are poor simulators, so the default
   should be no model, and a local model should be added only as a measured option.
4. Score from the world's state, as tau2 and Agent Proof Lab do, and avoid LLM judges in the
   core. Pin scenario sets by version, label anything unvalidated, and show the count behind
   every rate.
5. Do not build emulators that exist. Reusing emulate would add a Node dependency; that cost
   belongs in the stack ADR. Discord is not in its list, and its fidelity is untested.
6. Do not copy AGPL code (MiroFish, Gnomi, MarketMirror). Their ideas and published results are
   usable with credit.
7. Stay out of crowd-scale simulation. A team has a handful of people, and 100 simulated users
   for one step already cost 336k tokens in OASIS.
8. Make determinism and visible failures a feature: seeds, replay, failures counted rather than
   hidden.

## Open questions

- **Hands-on cost.** Nobody ran MiroFish, TinyTroupe or tau2's `--dry-run` for this pass. A
  one-hour run of each would replace README claims with measured setup cost.
- **Who plays the people?** Test which small local models can play a teammate at all (one
  message per turn, staying in role) before any "local model by default" promise.
- **Human data for feedback.** Is there any open dataset of how a team reacts to a tool? If not,
  would the maintainer collect a small one? Without it the feedback feature stays unvalidated.
- **Thresholds.** Which diversity measure (coverage and uniformity, or embedding effective rank)
  and what limit make feedback shippable? Try both on the prototype's six-person team first.
- **Is any LLM judge needed in the core?** The prototype scores without one; keep it that way
  unless a check cannot be stated as state.
- **Emulators.** Which emulator does the prototype's Discord run use, and how faithful is it?
  Is emulate's Slack emulator faithful enough to test a real Slack bot?
- **Demand.** Would ten builders of Slack or Discord bots use a recorded demo? This needs the
  maintainer, because it is public.

## What I could not verify

- Reddit was seen only through search excerpts (r/Discord_Bots, r/AI_Agents, r/SideProject,
  r/LLMDevs); X gave nothing useful. Social posts are leads.
- Papers were read as abstracts. Most are preprints; Bojic et al. is in Scientific Reports.
  The "digital twins" paper has no link or venue confirmed.
- NN/g's 2026 follow-up, Pew and SSDataBench are second-hand or excerpt-only.
- MarketMirror-Bench is its authors' own small run and may be affected by the model having seen
  the headlines; Gnomi and MarketMirror claims come from their READMEs.
- The MiroFish "about 24 of 100" count is by issue title and approximate.
- Whether promptfoo changed its simulated-user remote call after issue #5808 was not checked.
- The dev.to post comes from a vendor of a competing mock library.
