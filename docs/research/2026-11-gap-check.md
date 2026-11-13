# Gap check on the run-1 research (2026-11-12)

A short second pass over what the earlier notes left open or did not look at. It covers four
things: a market the notes never mention, the working name, two emulator facts and the demand
evidence. It decides nothing. Everything below was read from the linked pages, registries and
source on 2026-11-12; nothing was installed or run.

## Summary

| Gap | Finding | Effect |
|---|---|---|
| Market | A funded market sells simulated workplaces with simulated users to AI labs and enterprises. The earlier notes do not mention it | The "training environments" direction is crowded; it is also the clearest sign that someone pays for this kind of thing |
| Name | "TeamSim" is an existing commercial team-training simulator, and two other training products use the name | Pick another name before going public |
| Emulators | A Python mock Slack with reset and snapshots over HTTP exists (env0, AGPL-3.0). `emulate` still shows no reset route for its built-in services | The claim that every usable emulator is a Node package no longer holds for Slack |
| Demand | Still no direct request found for multi-user testing of team chat agents | The demand check stays the largest open risk |

## 1. The simulated-workplace market

The prior-art note covers research benchmarks, open-source simulators and opinion-prediction
companies. It does not cover companies that sell "RL environments": a task, simulated software
to do it in and a grader. Several of them describe their product in terms close to teamsim's.

| Company | What its own site or a directory says | Open source |
|---|---|---|
| Veris AI | "A simulated copy of your systems, data, APIs, and users"; priced per bench or annual licence, on request [V1] | Not stated |
| Collinear | A "Simulation Lab": a world with users, tools, data and tasks; simulated users with unscripted interruptions, objections and preference shifts [C1] | Not stated |
| Plato | Simulated workplaces for browser agents; a $16M Series A dated 2026-10-28 [P1] | Not stated |
| Deeptune | Training "gyms" simulating tools such as Slack and Salesforce; acquisition by a human-data company announced 2026-07 [R1] | Not stated |
| BenchFlow | ClawsBench and env0: mock Gmail, Slack, Calendar, Docs and Drive with graded state [B1][B2] | env0, AGPL-3.0 |
| Harbor | A framework for running agent tasks in containers, from the Terminal-Bench authors; one article counts more than 80 benchmarks ported to its task format [H1][H2] | Apache-2.0 |

The funding figures and the directory descriptions come from vendor-written lists [P1][R1].
They were not checked against primary announcements; treat them as leads.

What this changes:

- **The buyers differ from teamsim's first user.** These companies sell to AI labs and
  enterprises, with pricing on request. None of the pages read offers a free local tool for a
  student or a small team testing its own bot. That gap is what teamsim is aimed at, but
  "nobody does this" is no longer a safe sentence for the README.
- **None of the pages read describes several scripted coworkers with planted facts and a
  per-fact answer key.** They describe simulated users and verifiers in general terms. Their
  products are closed, so this is absence of a claim, not proof of absence.
- **Training environments for agents should not be ranked first among later directions**
  without new evidence. It is the direction with the most funded competitors, and one article
  puts a complex product replica at about $300,000 [T1].
- **A task format already has adoption.** If teamsim scenarios could be exported as Harbor
  tasks, they would run in tooling people already use. This is a question for the preset
  format decision, not a recommendation: Harbor targets agents working inside a container,
  and whether a multi-user chat scenario fits was not examined.

## 2. The working name

| Where | Result |
|---|---|
| PyPI, npm, crates.io | `teamsim` unclaimed (HTTP 404 on each registry API) |
| GitHub | No notable project. `jaegerpl/TeamSim` (3 stars) is a multi-agent model of knowledge sharing; a handful of inactive personal repositories |
| Products | **TeamSim** by Surgical Science, an operating-room team-training simulator, written with a registered-trademark sign in a 2021 securities filing [N1][N2]. **D2 TEAM-Sim**, a training-simulation developer [N3]. **TeamSIM**, a university teamwork training programme for medical students [N4] |
| Domains | `teamsim.com` resolves. The `.dev`, `.io`, `.ai` and `.org` names did not resolve, which does not show they are unregistered |

The existing uses are all simulation software for training teams, which is close to one of
teamsim's own later directions (training simulators for people). No trademark register was
searched, and this is not legal advice. The practical reading: keep "teamsim" as the working
name while the repository is private and choose a different one before anything is public.

## 3. Emulator facts

- **env0** [B2] is a Python project (23 stars, last push 2026-10-24, AGPL-3.0). Its README
  lists a mock Slack implementing 57 Slack Web API methods, plus admin routes over HTTP for
  reset, named snapshot and restore, a diff against the seed and an action log. The stack
  note said every usable emulator is a Node package and counted the second runtime as the main
  cost of a Python core. For Slack that is now open to question. Not checked: whether the mock
  delivers events to a bot (Events API or Socket Mode), which a team-chat bot needs; whether it
  runs on Windows; how it installs outside its own repository. AGPL means it could only ever
  run as a separate program, as the emulator note already requires.
- **emulate** [E1] (1,985 stars, Apache-2.0, Node 24 or later, at commit `2df53fc`). The stack
  note left open whether reset is available over HTTP from the CLI. A search of the source
  finds a reset route only in the custom-emulator inspector; the help text says custom
  emulators support reset, snapshots and restore, and that `--watch` reloads reset to the
  seed. For the built-in Slack, GitHub and Linear emulators, restarting the process remains
  the only route found. This was a text search, not a full read.

Still unmeasured: how long a clean Windows or macOS machine takes to get from nothing to a
first run with each candidate stack. That needs a machine, not more reading.

## 4. Demand

Two more searches for people asking how to test a team-chat agent with several users before
deploying it found tutorials, vendor pages and one new supply-side signal (an open-source
bridge for bringing agents into team chat [D1]), but no request. The prior-art note's verdict
stands: demand is inferred, not observed. The market in section 1 shows that simulated
environments are bought, by a different buyer, for a different purpose.

## Not verified

- Any vendor's product beyond its public home page; funding amounts and dates.
- Whether any closed product plants facts across several simulated coworkers.
- Trademark registrations in any jurisdiction; domain ownership.
- env0's event delivery, Windows support and Slack fidelity; nothing was run.
- Whether `emulate` has an undocumented reset route for built-in services.
- Reddit and X were not searched directly in this pass.

## Sources

All read 2026-11-12.

- [V1] Veris AI home page: <https://veris.ai/>
- [C1] Collinear home page: <https://www.collinear.ai/>
- [P1] Patronus AI, "RL Environment Startups to Watch in 2026" (vendor-written list):
  <https://www.patronus.ai/resources/rl-environment-startups>
- [R1] RL List, vendor directory: <https://www.rl-list.com/>
- [T1] Taskade, "RL Environments Explained", citing Epoch AI for costs (second-hand):
  <https://www.taskade.com/blog/reinforcement-learning-environments>
- [B1] ClawsBench, arXiv:2604.05172: <https://arxiv.org/abs/2604.05172>
- [B2] env0 repository and README: <https://github.com/benchflow-ai/env0>
- [H1] Harbor repository: <https://github.com/harbor-framework/harbor>
- [H2] "The Sandbox is Inside the Score" (adapter count, second-hand):
  <https://medium.com/google-cloud/your-agent-is-only-as-good-as-the-sandbox-you-measured-it-in-f391b908418c>
- [E1] emulate repository: <https://github.com/vercel-labs/emulate>
- [N1] Financial Times company summary, Surgical Science Sweden AB:
  <https://markets.ft.com/data/equities/tearsheet/summary?s=SUS:STO>
- [N2] SEC filing mentioning "TeamSim®" (search excerpt only):
  <https://www.sec.gov/Archives/edgar/data/1820222/000119983521000394/form-s1a.htm>
- [N3] D2 TEAM-Sim press release, 2018: <http://www.prweb.com/releases/2018/03/prweb15332850.htm>
- [N4] Kolbe et al., 2023, Frontiers in Psychology:
  <https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2023.1214091/full>
- [D1] SandboxAQ, Switch announcement:
  <https://www.sandboxaq.com/press/sandboxaq-open-sources-switch-bring-any-ai-agent-into-any-team-chat>
