# Workspace emulators and real test platforms (2026-11-11)

Question: which workspaces can teamsim simulate cheaply and faithfully, and should it adopt
an emulator, own a small fake, or use real platforms in test mode? Every fact below was
checked on 2026-11-11 unless it says otherwise. Reddit was reachable only through search
excerpts. Web pages were treated as data, not instructions. Nothing here was installed or
run: this is a read-only survey of docs, package registries, GitHub metadata and source, so
"supported" means "documented", not "tested".

## Summary

1. **No emulator offers time control.** None of the local emulators below documents a
   clock, time travel or a way to set message timestamps. The prototype hit this: its
   Discord emulator stamps ids and times with the current time, so multi-week history
   cannot be replayed. Real platforms are the same, because they assign timestamps
   server-side. Of the self-hosted servers I checked, only two let a privileged client set them (Matrix
   appservices, Mattermost system admins). If scenarios need "three weeks of history", teamsim
   has to own the clock.
2. **Slack, GitHub and Linear have a usable, Apache-2.0 local emulator today.** Discord has
   one (the one the prototype uses), but it is the weakest fit: no threads, no forum posts,
   no non-interaction webhooks, and its source is not public.
3. **Real platforms are a poor default and a fair opt-in.** They cost accounts and tokens,
   cap the number of simulated people (Slack sandbox: 8 users; GitHub: one free account per
   person), and make simulated humans visible as bots or webhooks.
4. **Recommendation:** teamsim owns the scenario model (people, messages, planted facts,
   scenario clock) and talks to workspaces through thin adapters. Adopt an emulator for
   protocol detail where one exists; own the clock and timestamps; keep real platforms as an
   opt-in later. v0.1 simulates chat only. Details in the last two sections.

## What the prototype already tells us

From the prototype's RUNBOOK and REALISM notes (the Discord emulator is
`@deploybaseline/discord`, run in a local WSL distro):

- It works for the core loop: users post, edit, delete and react through simulate endpoints;
  the product connects over the real gateway; the harness can force `reconnect` and
  `invalidate`; slash commands and context menus arrive as interactions.
- Gaps found in practice: no threads (the prototype shims the thread-list routes with empty
  lists, and folds threads into the parent channel), attachments on simulated messages are
  dropped, forwards cannot be simulated (no message snapshots), modal submissions lack
  resolved users, and ids and timestamps always use the current time. The seed schema it read
  had no fields for message id, timestamp or reply reference.
- It could not be versioned from the notes, so the gaps are as of the version installed when
  the prototype was built. The current docs (below) agree on threads and webhooks.

## Local emulators

Licences and activity from the GitHub API and npm registry on 2026-11-11. GitHub "open" counts include pull requests unless the cell says "issues".

| Platform | Tool | What it covers | Documented gaps | Licence and activity |
|---|---|---|---|---|
| Discord | Baseline `@deploybaseline/discord` | REST v10 (100 operations), gateway with intents, RESUME, sharding, interactions, OAuth2, rate limits; simulate endpoints for message, edit, delete, reaction, member join and leave, interaction, gateway disconnect | Threads, forum posts, stickers, polls, audit logs, invites; "No webhooks other than interaction webhooks"; no voice; presence not dispatched; sessions and rate counters reset on restart; no clock | Apache-2.0. npm: 2 versions, latest 0.14.0 published 2026-10-22. No public source: the GitHub org has 0 public repos and the repo linked from npm returns 404. Org created 2026-09-03 |
| Discord | `verifo` (dksingh1997/verifo) | REST v10 fake with threads and webhooks | No gateway ("The full `Client` ... is not emulated") | MIT. 8 stars, last commit 2026-09-26 |
| Discord | Spacebar server | A re-implementation of the Discord backend, including gateway and CDN | Status "Development"; compatibility with bots not checked here | AGPL-3.0. 182 open issues, no GitHub releases, last push 2026-11-06 |
| Slack | Baseline Slack | Web API, OAuth v2, incoming webhooks, Events API (signed), Socket Mode, slash commands, block actions and modals; `thread_ts` and `conversations.replies`; reactions; modern file upload; scheduled messages | Slack Connect, Grid admin, user groups, reminders, canvases, lists, workflows; "exact rate limiting"; no way to move the clock; no dedicated "post as user" call (seed a user token and call `chat.postMessage`) | Apache-2.0 for the CLI and Discord packages (npm); other packages not checked. Same source caveat as above |
| Slack, GitHub, Linear | `vercel-labs/emulate` | Same family of services; the Slack part is documented with threads, reactions, files, events and signed callbacks; snapshot, restore and reset in the programmatic API | The package README at the commit I read lists Socket Mode and slash commands as not implemented, unlike Baseline's page | Apache-2.0, public. 1,978 stars. v0.13.1 released 2026-11-08, 32 open issues, 90 open PRs, 26 PRs merged in the last 30 days. No Discord or Jira |
| GitHub | `emulate` and Baseline | Repos, contents, commits, issues, PRs, reviews, comments, labels, milestones, branches, releases, orgs and teams, search, Actions, checks, GitHub Apps; repo webhooks with "real HTTP delivery to registered URLs on all state changes" | Reactions, git smart-HTTP clone and push are not listed (not verified either way); no clock | Apache-2.0 |
| GitLab | `verifo` (docs list GitLab) | Not examined in depth | Unknown | MIT, small project |
| Linear | `emulate` and Baseline | GraphQL issues, comments, labels, projects, cycles, OAuth, webhooks | "Full schema coverage ... notification inbox ... customer APIs ... not implemented". Open issue: webhook deliveries omit `Linear-Timestamp` and Issue payloads lack `state` | Apache-2.0 |
| Jira | Baseline Jira | REST, JQL, Agile boards and sprints, OAuth 3LO, webhooks (docs page only) | Not examined | Apache-2.0 |

Notes:

- **Baseline and `emulate` look related.** They use the same tagline ("Local drop-in
  replacement services for CI and no-network sandboxes") and the same default ports for the
  services they share (GitHub 4001, Google 4002, Slack 4003 and so on). I did not verify
  whether one derives from the other. It matters because only `emulate` has public source,
  issues and a release history I could inspect.
- **Setup cost.** Baseline needs Node 24 or later (npm `engines` and its docs) and starts
  with `npx`. Its docs say nothing about native Windows support beyond one flag that is documented as unsupported on Windows; the prototype runs it in WSL by project choice, which this survey
  cannot tell apart from a Windows limitation. `emulate` declares no engine; its repo pins a
  Node version I did not check. Both bind to 127.0.0.1 and use plain HTTP.
- **Closed or hosted options were rejected.** Rystic (rystic.ai) offers Slack, Linear, Jira
  and GitHub Pulls simulators and self-reports 95.0% agreement with the live API across 884
  checks for Slack, but its install doc requires an account and a network connection while a
  simulator runs (it checks in with the vendor), and states no software licence. A hosted
  mock (sandboxapis.dev) was also seen. Neither fits an offline, open-source default.
- **Unit-test libraries are not emulators.** `discord.js` mocks, `dpytest`-style tools and
  Slack mock clients replace the SDK, not the server, so a product that opens its own gateway
  connection cannot use them. Slack's own `steno` tool is archived (GitHub, last push
  2021-08-10).

## Self-hosted real chat servers

These run the real product, so API fidelity is high by definition. The catch is that the
product under test must already integrate with that chat system.

| Server | Licence | Latest release and activity | Setup | Time and history |
|---|---|---|---|---|
| Matrix, Synapse (element-hq) | AGPL-3.0 | 1.165.0 on 2026-11-10; 2,117 open issues. The older matrix-org repo is archived (last release 1.98.0, 2023-12-12) | Python or Docker | Appservices can set event time with `ts` ("origin_server_ts") on send and state calls (spec v1.3) and act as virtual users with `user_id`. Ordering in the event graph stays "now" |
| Matrix, Tuwunel | Apache-2.0 | 1.9.4 on 2026-10-10; 73 open issues | Rust single binary (platform support not checked) | Same Matrix spec |
| Mattermost | Source: AGPL-3.0 or commercial, with compiled releases under MIT; Team Edition is "under 250 activated users" | 12.1.0 on 2026-11-05 | One Docker command (`mattermost/mattermost-preview`) or a Linux binary with PostgreSQL | In `server/channels/api4/post.go` on `master`, a non-admin `create_at` is reset to 0, so a system admin can post with a past time |
| Rocket.Chat | MIT, except `ee/` directories under a separate licence | 9.0.0 on 2026-11-10; 4,391 open issues | Docker Compose with a database (not verified in detail) | Not checked |
| Zulip | Apache-2.0 | 12.4 on 2026-11-06 | Not checked | Not checked |
| Gitea (go-gitea) | MIT | 28.3.0 on 2026-11-01 | A single binary for Windows, macOS and Linux with SQLite built in (Gitea docs) | Not checked |
| GitLab CE | MIT for CE | 19.6 docs | "16 GB is the baseline", 8 GB minimum (GitLab docs) | Not checked |
| Plane | AGPL-3.0 | v1.5.0-rc1 on 2026-11-10 | Docker | Not checked |

Takeaway: Matrix and Mattermost are the only two where historical timestamps are possible,
and both are heavy for a student laptop (a database and a server). TheAgentCompany (see the
prior-art note) uses this route (GitLab, Rocket.Chat, Plane) and is described there as heavy
to set up. The licences matter if teamsim ever bundles one: AGPL (Synapse, Plane) and
Mattermost's source licence are not compatible with simply shipping a copy inside an
MIT-or-Apache project; running one as a separate process the user installs is a different
case. I am not giving legal advice here.

## Real platforms in test mode

### Discord

- **Setup.** A free developer app, a bot token, a test server. Message content needs the
  privileged `MESSAGE_CONTENT` intent: "toggle the intent ... in your app's settings"; approval
  is only needed for "verified apps (required for apps in 100+ guilds)"
  ([gateway docs](https://docs.discord.com/developers/events/gateway), 2026-11-11).
- **Simulated humans.** Normal user accounts must not be automated: "Automating normal user
  accounts (generally called 'self-bots') outside of the OAuth2/bot API is forbidden, and can
  result in an account termination"
  ([support article](https://support.discord.com/hc/en-us/articles/115002192352-Automated-User-Accounts-Self-Bots)).
  The legitimate routes are one bot application per persona (labelled BOT) or webhooks, whose
  `username` and `avatar_url` can be overridden per message
  ([webhook docs](https://docs.discord.com/developers/resources/webhook)). A webhook message
  has a webhook id and no member, so a product that treats webhook or bot authors differently
  from members would not see a faithful human (my inference, not tested). A Reddit thread
  excerpt from the r/Discord_Bots community says a second test account "requires a phone
  number" (search excerpt only, 2026-11-11); treat as a lead.
- **Terms.** Developer Policy (effective 2024-07-08): "Do not initiate processes on a user or
  server's behalf without first obtaining their permission." An excerpt I extracted also
  reads "This also includes automating messages to be sent for the purpose of maintaining
  activity in a Discord server"; I did not see its surrounding clause, so check the context
  before relying on it
  ([policy](https://support-dev.discord.com/hc/en-us/articles/8563934450327-Discord-Developer-Policy)).
  Developer Terms (effective 2024-07-08): you will not access the APIs in a way that "exceeds
  any API rate, call, or other usage limits"
  ([terms](https://support-dev.discord.com/hc/articles/8562894815383-Discord-Developer-Terms-of-Service)).
  A bot posting to a private server the maintainer owns, with fictional content, sits well
  inside this; the open question is whether a shipped tool that tells students to run many
  persona bots is covered. I did not find a rule that names simulated users.
- **Rate limits.** "All bots can make up to 50 requests per second"; invalid requests are
  limited to 10,000 per 10 minutes per IP
  ([docs](https://docs.discord.com/developers/topics/rate-limits)). The prototype's own
  316-message run took about four minutes against the emulator.
- **Time.** Ids and timestamps are assigned by Discord. History cannot be back-dated.

### Slack

- **Setup.** The Developer Program gives a free sandbox, which is an Enterprise-org
  environment. Limits (docs, 2026-11-11): "up to two active sandboxes", "Max eight users per
  sandbox ... excludes bots and apps", active "six months by default (one month for basic
  sandboxes)", and the paid-plan features need a workspace that has been on a paid plan for
  at least 30 days or a payment method on file
  ([sandboxes](https://docs.slack.dev/tools/developer-sandboxes)). The demo team has six
  people, so it fits; a 10-person preset does not.
- **Simulated humans.** A person in Slack is a user with a seat. Posting as several humans
  means one user token per persona; bots appear as apps.
- **Rate limits.** From 2025-05-29, `conversations.history` and `conversations.replies` are
  limited to "1 request per minute" and "a maximum of 15 objects per request" for
  commercially distributed apps outside the Marketplace and for new installations of them;
  "Internal customer-built applications are not impacted"
  ([changelog](https://docs.slack.dev/changelog/2025/05/29/rate-limit-changes-for-non-marketplace-apps)).
  A product that reads history, and that someone else installs from an unlisted release,
  would feel this.
- **Terms.** API Terms (effective 2025-10-10): you will not access the APIs in a manner that
  "exceeds rate limits, or constitutes excessive or abusive usage"; an app "offered for use
  outside your organization" may not "use API Data to train a large language model" or "bulk
  export Slack message and file data"
  ([API terms](https://slack.com/terms-of-service/api)). That second rule bears on any
  AI product being tested against a real workspace and then distributed.
- **Time.** Not back-datable through the chat API (not documented anywhere I read; treat as
  likely, not verified).

### GitHub, Linear, Jira

- **GitHub.** The terms allow one "machine account" next to a personal account, "used
  exclusively for performing automated tasks", and say a person may hold "no more than one
  free Account"
  ([ToS](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service)).
  Simulating six humans on GitHub therefore means six real people's accounts or one machine
  account speaking as everyone; it cannot mean six free accounts owned by one person (my
  reading). The acceptable-use policy bans "automated inauthentic activity" and "excessive
  automated bulk activity"
  ([AUP](https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies)).
  Limits: 5,000 requests an hour per user, `GITHUB_TOKEN` 1,000 per hour per repository, and
  "no more than 80 content-generating requests per minute and no more than 500 ...
  per hour" ([rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)).
  Seeding 300 issues and comments fits in an hour, but only just once retries are counted.
  Effective dates of these two policies were not captured.
- **Linear.** Free plan: 250 issues and 2 teams ([pricing](https://linear.app/pricing)); API key limit 2,500 requests
  an hour per user, 5,000 for an OAuth app
  ([rate limiting](https://linear.app/developers/rate-limiting)). A 250-issue cap is a real
  ceiling for ground-truth fixtures.
- **Jira.** Free plan "for up to 10 users with 2GB of storage"
  ([pricing](https://www.atlassian.com/software/jira/pricing)).
- **Privacy.** On every real platform the fictional content, the product's questions and
  its answers pass through the vendor's servers. Fine for fiction; it rules out anyone who
  wants to test with real team data, and each vendor's API-data rules then apply.

### Where a real platform is better

Real platforms are the only way to test behaviour the emulators leave out (Discord
threads and forwards, Slack Connect, real rate-limit errors, real permission edge cases,
real OAuth install flows). That justifies an opt-in "run against a real test workspace"
mode, not a default.

## Own a minimal fake or adopt an emulator

| | Adopt an emulator | Own a minimal fake |
|---|---|---|
| Fidelity | Broad API surface (Baseline Discord lists 100 operations) | Only what the products under test call; each new product exposes new gaps |
| Time and history | Not offered by any emulator; cannot be added without source (Baseline) or a fork | Native: ids and timestamps come from the scenario clock. This unlocks the date-based checks the prototype had to mark "n.a." |
| Gaps like threads, attachments, forwards | Wait for the vendor | Fixable the day you need them |
| Dependencies | Node 24 or later next to a Python-stdlib project; npm supply chain; Baseline has no public source | None added |
| Maintenance risk | A 2-version, 7-week-old package (Baseline) or a very active but fast-moving repo (`emulate`: 26 merged PRs in 30 days) | All on teamsim |
| Build effort | Almost none | Discord needs a WebSocket gateway; Python's standard library has no WebSocket server, so RFC 6455 framing is hand-written (my estimate: a few hundred lines for the handshake, heartbeat, identify, resume and dispatch, plus the REST routes used; not built or measured) |
| Fidelity risk | Fidelity is the vendor's claim until tested | Fidelity is only as good as teamsim's contract tests against real traffic |

The middle path is the one to take: keep the prototype's shape, where the harness talks to
a workspace through one small client, and put the scenario in teamsim's own model. Then the
emulator is replaceable, the clock and the history are teamsim's, and nothing breaks when an
emulator changes. A real-platform adapter later is the same interface.

## Recommendation for v0.1

1. **Simulate one chat workspace, Discord first**, because the working prototype, the
   fixtures and the scored checks already exist and the emulator already runs the real
   gateway. Slack is the second adapter. This follows the evidence, not a first-user
   decision, which is still open.
2. **Own the scenario clock and message model.** Every message carries a scenario time. Where
   the emulator cannot honour it (today, Discord), either run at the emulator's real time
   with a declared "no history" limit, or add a thin teamsim-owned fake just for ids and
   timestamps. Decide this by testing whether the product under test uses ids or timestamps.
   That is a product-specific fact I could not check from outside.
3. **Adopt an emulator for Slack, GitHub and Linear when they are needed.** Start with
   `emulate`: its source, issues and releases are inspectable and it is Apache-2.0. Treat
   Baseline as the Discord option only while it works for the prototype, and watch its
   public-source status.
4. **Track every fidelity gap in the report** (the prototype already does with "n.a." and
   assumption lists) so a failure is never blamed on the product when the emulator cannot
   represent the case.
5. **Do not make real platforms part of the default path.** Offer them later as an opt-in,
   documented with the ToS notes above: bots and webhooks for simulated people, one account
   rule on GitHub, the 8-user Slack sandbox, no history back-dating.
6. **Contract-test any emulator or fake** against recorded real traffic or the vendor's
   published spec (Baseline cites `discord/discord-api-spec` at a commit) before trusting
   its results.

### Input to the v0.1 actions question

- **Chat only** is cheapest and the best evidenced: the only workspace where a working
  prototype, a fixture dataset and a scoring harness already exist. Its open fidelity gaps
  (threads, attachments, forwards, history) are known and listed above.
- **Chat plus tasks and issues** is cheap on the emulator side (Linear and GitHub issues exist
  in `emulate`, with webhooks), but each surface multiplies the work that is not about
  emulation: ground-truth facts planted in issues, simulated teammates who open and update
  them believably, and scoring. It also forces a decision on GitHub versus Linear versus
  Jira, which depends on the first user.
- **Plus a code repository** has an emulated REST surface (contents, commits, PRs, reviews)
  but I could not verify git clone and push over HTTP, which most repo-reading products
  need. A local Gitea (single binary, MIT) is the likely answer; this was not tested.
- Recommended sequence: v0.1 chat only, v0.2 issues through one emulator after the first user
  is chosen, repository access only for a user who needs it.

## What I could not verify

- Whether Baseline's source will ever be public, its issue count and its release cadence
  beyond two npm versions.
- Whether Baseline or `emulate` run natively on Windows, or the exact Node version `emulate`
  needs.
- Behaviour of any emulator beyond what its docs, README or source say; nothing was run.
- Spacebar's compatibility with bot libraries, and Rocket.Chat, Zulip, Tuwunel and Gitea setup
  and time features.
- Whether real Slack or Discord accept back-dated messages by any supported route.
- The full context of the Discord policy sentence about "maintaining activity", and the
  effective dates of the GitHub terms.
- Reddit content beyond one search excerpt; no X posts were used.
- Anything legal: the terms above do not mention simulated users, so statements about them
  are my reading.
