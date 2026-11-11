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
   server-side. Of the self-hosted servers I checked, three can back-date history (Matrix appservices,
   Mattermost system admins, Rocket.Chat's CSV importer), but none offers live clock control. If scenarios need "three weeks of history", teamsim
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

All facts in this section and the next were checked on 2026-11-11. Each row ends with
reference keys, listed under the table. Counts (stars, open issues and PRs, merged PRs) are
snapshots from the GitHub REST and search APIs on that date, and GitHub "open" counts include
pull requests unless a cell says "issues". Where a claim depends on source code or a README,
the commit SHA is given. Baseline's docs are not versioned, so its rows cite the page as read
on the check date.

| Platform | Tool | What it covers | Documented gaps | Licence and activity |
|---|---|---|---|---|
| Discord | Baseline `@deploybaseline/discord` | REST v10 (100 operations), gateway with intents, RESUME, sharding, interactions, OAuth2, rate limits; simulate endpoints for message, edit, delete, reaction, member join and leave, interaction, gateway disconnect | Threads, forum posts, stickers, polls, audit logs, invites; "No webhooks other than interaction webhooks"; no voice; presence not dispatched; sessions and rate counters reset on restart; no clock | Apache-2.0. npm: 2 versions, latest 0.14.0 published 2026-10-22. No public source: the GitHub org has 0 public repos and the repo linked from npm returns 404. Org created 2026-09-03 Refs: B1, B2, B3. |
| Discord | `verifo` (dksingh1997/verifo) | REST v10 fake with threads and webhooks | No gateway ("The full `Client` ... is not emulated") | MIT. 8 stars, last commit 2026-09-26 Refs: V1. |
| Discord | Spacebar server | A re-implementation of the Discord backend, including gateway and CDN | Status "Development"; compatibility with bots not checked here | AGPL-3.0. 182 open issues, no GitHub releases, last push 2026-11-06 Refs: P1. |
| Slack | Baseline Slack | Web API, OAuth v2, incoming webhooks, Events API (signed), Socket Mode, slash commands, block actions and modals; `thread_ts` and `conversations.replies`; reactions; modern file upload; scheduled messages | Slack Connect, Grid admin, user groups, reminders, canvases, lists, workflows; "exact rate limiting"; no way to move the clock; no dedicated "post as user" call (seed a user token and call `chat.postMessage`) | Apache-2.0 for the CLI and Discord packages (npm); other packages not checked. Same source caveat as above Refs: B2, B4. |
| Slack, GitHub, Linear | `vercel-labs/emulate` | Same family of services; the Slack part is documented with threads, reactions, files, events and signed callbacks; snapshot, restore and reset in the programmatic API | The package README at the commit I read lists Socket Mode and slash commands as not implemented, unlike Baseline's page | Apache-2.0, public. 1,978 stars. v0.13.1 released 2026-11-08, 32 open issues, 90 open PRs, 26 PRs merged in the last 30 days. No Discord or Jira Refs: E1, E2, E3. |
| GitHub | `emulate` and Baseline | Repos, contents, commits, issues, PRs, reviews, comments, labels, milestones, branches, releases, orgs and teams, search, Actions, checks, GitHub Apps; repo webhooks with "real HTTP delivery to registered URLs on all state changes" | Reactions, git smart-HTTP clone and push are not listed (not verified either way); no clock | Apache-2.0 Refs: E1, B4. |
| GitLab | `verifo` (docs list GitLab) | Not examined in depth | Unknown | MIT, small project Refs: V1 (repo description only; the GitLab doc page was not read). |
| Linear | `emulate` and Baseline | GraphQL issues, comments, labels, projects, cycles, OAuth, webhooks | "Full schema coverage ... notification inbox ... customer APIs ... not implemented". Open issue: webhook deliveries omit `Linear-Timestamp` and Issue payloads lack `state` | Apache-2.0 Refs: E1, E4, B4. |
| Jira | Baseline Jira | REST, JQL, Agile boards and sprints, OAuth 3LO, webhooks (docs page only) | Not examined | Apache-2.0 Refs: B4. |

Notes:

Reference keys (all checked 2026-11-11):

- B1: Baseline Discord docs, <https://docs.deploybaseline.com/discord> (the "100 HTTP
  operations" figure, supported routes, simulate endpoints, the limits list including "No
  webhooks other than interaction webhooks"). The docs name the vendor spec as
  `discord/discord-api-spec` at `ed01408`.
- B2: npm registry records,
  <https://registry.npmjs.org/@deploybaseline/discord> and
  <https://registry.npmjs.org/@deploybaseline/cli> (licence Apache-2.0, `engines` node
  >=24, two versions each, `0.14.0` published 2026-10-22). Package page:
  <https://www.npmjs.com/package/@deploybaseline/discord>, which returned HTTP 403 to my
  fetcher, so the registry JSON is what I read.
- B3: GitHub organisation, <https://api.github.com/orgs/deploybaseline> (`public_repos: 0`,
  created 2026-09-03); the repository the npm records link to,
  <https://github.com/deploybaseline/baseline-cli>, returns 404.
- B4: Baseline docs, <https://docs.deploybaseline.com/slack> (supported methods, Events API,
  Socket Mode, the unsupported list including "exact rate limiting"),
  <https://docs.deploybaseline.com/providers> (provider list with GitHub, Linear and Jira)
  and <https://docs.deploybaseline.com> (Node 24 or later, default ports).
- E1: `vercel-labs/emulate` README at commit
  `26a8fe7e32db3346b0ac928586422ac2709b922b` (tip of `main` on 2026-11-11), sections
  "GitHub API", "Slack API" and "Linear API". Licence, stars (1,978) and activity:
  <https://api.github.com/repos/vercel-labs/emulate>. Release:
  <https://github.com/vercel-labs/emulate/releases/tag/v0.13.1> (published 2026-11-08).
  Issue and PR counts (32 open issues, 90 open PRs, 26 PRs merged since 2026-10-11) come from
  GitHub search queries `repo:vercel-labs/emulate is:issue is:open`, `is:pr is:open` and
  `is:pr is:merged merged:>2026-10-11`.
- E2: the Slack package README, which also lists Socket Mode and slash commands as not
  implemented, at
  <https://github.com/vercel-labs/emulate/blob/9cb8659c75cf44fd327f727327618c321bf1480d/packages/@emulators/slack/README.md>.
  The same limits sentence is in E1 ("Current Slack limits").
- E3: the repository has no `discord` or `jira` package under `packages/@emulators` (contents
  API listing at the same commit as E1).
- E4: Linear limits sentence in E1 ("Current Linear limits"), and the open issue
  <https://github.com/vercel-labs/emulate/issues/323>.
- V1: `dksingh1997/verifo` `docs/discord.md` at commit
  `e85a1c132267bbd225a0c6e300bc7cf37da0f51f`; licence and star count from
  <https://api.github.com/repos/dksingh1997/verifo>; last commit 2026-09-26.
- P1: `spacebarchat/server` README at commit `96571d975d08641e6a1c4602aafe728b171f8bc3`
  (status badge "Development"); licence, last push and 182 open issues from
  <https://api.github.com/repos/spacebarchat/server> and the search API; the releases
  endpoint returns 0 releases.

- **Baseline and `emulate` look related.** They use the same tagline ("Local drop-in
  replacement services for CI and no-network sandboxes") and the same default ports for the
  services they share (GitHub 4001, Google 4002, Slack 4003 and so on). I did not verify
  whether one derives from the other. It matters because only `emulate` has public source,
  issues and a release history I could inspect.
- **Setup cost.** Baseline needs Node 24 or later (npm `engines` and its docs) and starts
  with `npx`. Its docs say nothing about native Windows support beyond one flag that is documented as unsupported on Windows; the prototype runs it in WSL by project choice, which this survey
  cannot tell apart from a Windows limitation. `emulate` declares no engine; its repo pins a
  Node version I did not check. Both bind to 127.0.0.1 and use plain HTTP.
- **Closed or hosted options were rejected.** Rystic (<https://www.rystic.ai>, install doc <https://www.rystic.ai/docs/installation>) offers Slack, Linear, Jira
  and GitHub Pulls simulators and self-reports 95.0% agreement with the live API across 884
  checks for Slack, but its install doc requires an account and a network connection while a
  simulator runs (it checks in with the vendor), and states no software licence. A hosted
  mock (<https://sandboxapis.dev/docs/slack>) was also seen. Neither fits an offline, open-source default.
- **Unit-test libraries are not emulators.** `discord.js` mocks, `dpytest`-style tools and
  Slack mock clients replace the SDK, not the server, so a product that opens its own gateway
  connection cannot use them. Slack's own `steno` tool is archived (<https://api.github.com/repos/slackapi/steno>: `archived: true`, last push
  2021-08-10).

## Self-hosted real chat servers

These run the real product, so API fidelity is high by definition. The catch is that the
product under test must already integrate with that chat system.

| Server | Licence | Latest release and activity | Setup | Time and history |
|---|---|---|---|---|
| Matrix, Synapse (element-hq) | AGPL-3.0 | 1.165.0 on 2026-11-10 ([release](https://github.com/element-hq/synapse/releases/tag/v1.165.0)); 2,117 open issues and PRs. The older matrix-org repo is archived (last release [1.98.0](https://github.com/matrix-org/synapse/releases/tag/v1.98.0), 2023-12-12) | Python or Docker | Appservices can set event time with `ts` ("origin_server_ts") on send and state calls (spec v1.3) and act as virtual users with `user_id`. Ordering in the event graph stays "now" |
| Matrix, Tuwunel | Apache-2.0 | 1.9.4 on 2026-10-10 ([release](https://github.com/matrix-construct/tuwunel/releases/tag/v1.9.4)); 73 open issues and PRs | Rust single binary (platform support not checked) | Same Matrix spec |
| Mattermost | Source: AGPL-3.0 or commercial, with compiled releases under MIT ([LICENSE.txt](https://github.com/mattermost/mattermost/blob/238dcf33c618/LICENSE.txt)); Team Edition is "under 250 activated users" | 12.1.0 on 2026-11-05 ([release](https://github.com/mattermost/mattermost/releases/tag/v12.1.0)) | One Docker command (`mattermost/mattermost-preview`) or a Linux binary with PostgreSQL | In `server/channels/api4/post.go` on `master`, a non-admin `create_at` is reset to 0, so a system admin can post with a past time (source at commit `238dcf33c618`, line 125) |
| Rocket.Chat | MIT, except `ee/` directories under a separate licence | 9.0.0 on 2026-11-10 ([release](https://github.com/RocketChat/Rocket.Chat/releases/tag/9.0.0)); 4,391 open issues and PRs | Docker Compose with a database (not verified in detail) | The CSV importer's message file has a per-message timestamp in milliseconds (example line `"user","1479162481336","text"`), so history can be imported. Whether it can be seeded through the live API was not checked |
| Zulip | Apache-2.0 | 12.4 on 2026-11-06 ([release](https://github.com/zulip/zulip/releases/tag/12.4)) | Not checked | Not checked |
| Gitea (go-gitea) | MIT | 28.3.0 on 2026-11-01 ([release](https://github.com/go-gitea/gitea/releases/tag/v28.3.0)) | A single binary for Windows, macOS and Linux with SQLite built in (Gitea docs) | Not checked |
| GitLab CE | MIT for CE | 19.6 docs | "16 GB is the baseline", 8 GB minimum (GitLab docs) | Not checked |
| Plane | AGPL-3.0 | v1.5.0-rc1 on 2026-11-10 ([release](https://github.com/makeplane/plane/releases/tag/v1.5.0-rc1)) | Docker | Not checked |

Self-hosted references (checked 2026-11-11): licences and open counts from
`https://api.github.com/repos/<owner>/<repo>` for each repository above (the `license`
field; for Rocket.Chat, the repository's `LICENSE` at
<https://github.com/RocketChat/Rocket.Chat/blob/ad54cf373053099a0b3af84a0f5b305c5ee4c61f/LICENSE>);
Matrix `ts` and `user_id` behaviour,
<https://spec.matrix.org/latest/application-service-api/#timestamp-massaging> (spec page
version 1.19; "Added in v1.3"); Mattermost editions and the Docker preview command,
<https://docs.mattermost.com/product-overview/editions-and-offerings> and
<https://docs.mattermost.com/deployment-guide/server/deploy-containers>; Rocket.Chat CSV
format, <https://docs.rocket.chat/docs/import-from-csv>; Gitea,
<https://docs.gitea.com/installation/install-from-binary>; GitLab,
<https://docs.gitlab.com/install/requirements/>.

Two different things need separating:

- **Historical seeding** (back-dating messages once, before the product connects). Matrix
  appservices can set event time, Mattermost system admins can set `create_at`, and
  Rocket.Chat's CSV importer takes a per-message timestamp. I did not check Zulip, Gitea,
  GitLab or Plane for an equivalent, so "cannot" is not established for them.
- **Live clock control** (advancing time while the product runs, for example to expire tokens
  or trigger a digest). None of the emulators or servers I read documents it. Matrix keeps
  event ordering at "now" even with a changed timestamp.

All of these are heavy for a student laptop (a database and a server) except the Gitea
binary. TheAgentCompany (see the prior-art note) uses this route (GitLab, Rocket.Chat, Plane)
and is described there as heavy to set up.

**Licences, if teamsim ever ships or bundles one.** I am not giving legal advice; the
distinctions below come from the licence texts.

- *Aggregation (a separate, independent AGPL server shipped or installed next to
  teamsim).* AGPL-3.0 section 5 says that "Inclusion of a covered work in an aggregate does
  not cause this License to apply to the other parts of the aggregate", provided the
  compilation does not limit users' access or legal rights beyond what the separate works
  allow ([text](https://www.gnu.org/licenses/agpl-3.0.en.html)). So teamsim's MIT or
  Apache-2.0 code is not affected. Obligations apply to the AGPL component itself: if
  teamsim distributes a copy (an image, a bundled binary), it must carry the licence text and
  make the Corresponding Source for that component available. If the user installs it from
  upstream, teamsim only links to it and has no such duty. Merely running an unmodified
  server needs nothing further, because the section 13 network-source duty applies "if you
  modify the Program".
- *Copying or linking AGPL code into teamsim, or modifying the server.* That makes a covered
  work: the result must be offered under AGPL, and a modified server exposed to remote users
  must offer its source (section 13). That would conflict with an MIT-or-Apache teamsim, so
  avoid it. Writing against a server's public protocol (the Matrix spec, a REST API) does not
  copy its code.
- *Mattermost.* Its LICENSE.txt says compiled versions from Mattermost, Inc. are MIT, while
  building from source is AGPL or commercial, and use of the "Mattermost" mark needs prior
  written approval. Redistributing their compiled build is therefore an MIT question plus a
  trademark one. Team Edition is documented as meant for "under 250 activated users".
- Whether two things are "separate and independent" depends on how they are connected.
  Talking over a network protocol to a server the user installs is the safest case.

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
- Spacebar's compatibility with bot libraries; Rocket.Chat setup and whether its importer's
  timestamps are visible through the live API; Zulip, Tuwunel and Gitea setup and time features.
- Whether real Slack or Discord accept back-dated messages by any supported route.
- The full context of the Discord policy sentence about "maintaining activity", and the
  effective dates of the GitHub terms.
- Reddit content beyond one search excerpt; no X posts were used.
- Anything legal: the terms above do not mention simulated users, so statements about them
  are my reading.
