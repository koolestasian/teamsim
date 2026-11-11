# Prior art (first pass, 2026-11-10)

A first pass from search results and a few primary pages. Reddit threads were seen only as
search excerpts. A deeper pass is the first milestone.

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

## What this means for teamsim

1. Stay out of opinion prediction. It is crowded and well funded, and the evidence says it is
   unreliable. (Changed 2026-11-11: [ADR 0003](../adr/0003-scope-tests-and-simulated-feedback.md)
   brings simulated feedback into scope, on the condition that it can be measured.)
2. The gap is simulated people for testing whether software works. A test teammate does not
   need to be an accurate human. It needs to be varied, messy, reproducible and checkable. The
   known weaknesses (compression, sycophancy, too-clean behaviour) still matter, so build in
   counter-measures: behaviour knobs, injected chaos, seeds.
3. Ground truth makes it a test tool: the simulator knows what it planted, so it can score the
   product.
4. Ease of use is a real gap. MiroFish shows it: wide interest, but two runtimes, two cloud keys
   and a cost warning. Target one command, a local model by default, presets and no code.
5. For actions, the simulator owns a small fake world (chat, issues, repository) and the product
   plugs in through MCP or an HTTP API. Driving a browser UI comes later.

## Open questions for the next pass

- Who is the first user: a student testing a bot or agent, or someone building a team tool?
- How to measure that personas do not all sound the same.
- Hands-on: run MiroFish or TinyTroupe for an hour to feel their setup cost first-hand.
- Which local Discord, Slack and GitHub emulators exist, and how faithful they are.
