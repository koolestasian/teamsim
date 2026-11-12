# Real team chat, judging synthetic chat, and learning from real teams: literature review (2026-11-11)

Full-text check updated 2026-11-12: [method and limits](2026-11-lit-fulltext-check.md).
Depth tags retain the initial reading pass unless updated; current source access is
recorded per paper in the [bibliography](bibliography/).

Scope: what real developer and team chat looks like in numbers, how remote work changes communication, how
synthetic multi-party dialogue is made and judged, how to define realism targets, and how to learn patterns
from a real team without leaking it. 49 papers are cited; 9 were read in full text (marked [full text],
some only in part); the rest at abstract level ([abstract]) or from a web page ([web page]). Numbers marked "derived"
are my own arithmetic on reported numbers. Statements marked "inference" are mine, not the papers'.

## Summary

1. **Developer chat is short, fast and fragmentary, and about a quarter of questions get no answer.** In eight Gitter
   developer communities (1.4M messages, 173K model-separated dialogs) the mean time to the first reply was 220 s,
   80% of dialogs had a first reply within 343 s, and 24% of dialogs were unanswered monologues [full text]. For
   teamsim: presets should contain unanswered questions at about this rate; a bot that is only tested on questions
   that always get answered is under-tested.
2. **There is no single "average chat". Rates differ a lot by channel type.** Across 4,300 Slack channels of one
   company, project channels averaged 16.4 words per message and 2.0 messages per thread; IT-support channels 23.0
   words and 4.1 messages per thread; social channels had about 18% of messages with reactions, project channels
   about 5.5% (derived) [full text]. For teamsim: calibrate per channel type (project, social, support, bot).
3. **Conversations interleave and links between messages are mostly implicit.** In Ubuntu IRC only about 48% of
   messages name the person they answer, 83.4% of conversations have fewer than 10 messages, and of the
   conversation starters that get a reply, 37.7% get more than one [full text]. For teamsim: scripted threads should interleave and
   use implicit replies, and scoring must not assume one tidy thread per topic.
4. **Timing is bursty with heavy tails; the day and week cycle explains part of it, not all.** Cycles plus a
   tendency to continue an activity reproduce the email heavy tail; other work finds a residual tail that cycles do
   not explain [abstracts]. For teamsim: a timing model needs a time-of-week profile plus within-burst,
   within-conversation and between-conversation gaps. A single exponential gap is not enough.
5. **Participation is unequal, but the size of the inequality is community-specific.** Reported top-group shares range
   from about 25% of messages for the top poster in a typical Slack project channel (derived) to about 75% of
   content from the top group in four health forums, while a support-group trial found flatter engagement than the
   1% rule predicts [full text and abstracts]. For teamsim: set a top-poster share target per preset, not a universal rule.
6. **LLM-written group chat can fool a quick human check but lacks the mess of real talk.** In a Reddit study,
   LLM threads were mistaken for human ones 39% of the time (for the better model, Llama 3 70B, judges picked the
   human thread only 56% of the time, close to chance) [full text]. A 2026 benchmark of professional conversations found LLM simulations contain far fewer
   misunderstandings, repetition and off-topic turns than human ones; prompting for them overshot, and fine-tuning
   made the model repeat itself [full text]. For teamsim: "reads well" is not a realism test. Test frequencies of
   specific behaviours.
7. **Remote work changes who talks to whom.** Large email studies found more modular (siloed) networks in 2020 and an
   estimated loss of more than 4,800 weak ties over 18 months at one university, with only a slight recovery under
   hybrid work, which the authors call an initial finding [abstracts]. For teamsim: a "remote team" preset should lower cross-group ties, not only shift hours.
8. **Validating against several patterns at once is the established method, with a known trap.** Pattern-oriented
   modelling uses several observed patterns to choose among models; a worked tropical-forest case matched up to
   five of six patterns together but not two specific ones at once, and a field-vole case warns of over-fitting to
   patterns [abstracts, web page]. For teamsim: make realism a set of distributional targets that must pass together,
   report which pair conflicts, and hold out a second real source.
9. **Text anonymisation is weak against modern attacks; aggregates are the safe output.** An LLM pipeline re-identified
   Hacker News accounts from LinkedIn profiles with 45.1% recall at 99% precision (987 queries, 89K candidates) [full text];
   stylometry attribution of Instagram posts was 81% on real and 16.5% to 29.7% on LLM-generated posts [full text]; a
   public Discord dataset of 2.05B messages says its hashing and pseudonyms cannot guarantee anonymity [full text].
   For teamsim: derive only numbers, locally, with consent, and never keep text, names, IDs or per-person profiles.
10. **Student-team chat is thin and bursty, and consent is partial.** One course project had a median of 9 messages
    per student per 1 to 2 week deliverable window and about 14.8 words per message (derived); only 94 of 186
    students consented, so teams were partly observed [full text]. For teamsim: a student preset has far fewer
    messages per person than an industry channel, and any calibration data will cover fewer people than the team.

## 1. Datasets and studies of developer and team chat

| Source | Venue/year | What it is | Key numbers | Read |
|---|---|---|---|---|
| Wang et al., Group chat ecology on Slack | ACM-format journal paper (arXiv v5; venue not verified) | 4,300 channels, one R&D department, 100 hand-coded | 9 channel types; project n=32 | full text |
| Shi et al., First look at developers' live chat on Gitter | arXiv preprint 2021 (conference version not verified) | 8 communities, 1,402,894 utterances, 95,416 users, 173,278 dialogs | first reply 220 s mean; 24% unanswered | full text |
| Kummerfeld et al., Large-scale corpus for conversation disentanglement | arXiv preprint 2018 (ACL 2019 per listing; not re-verified) | 77,563 IRC messages with reply links | 48% name the addressee | full text |
| Aquino et al., Discord Unveiled | arXiv preprint 2025 | 2.05B messages, 4.74M users, 3,167 public servers | 17% of messages from bots | full text (partial) |
| Subash et al., DISCO | MSR 2022 data showcase | 28,712 conversations, 1,508,093 messages, 323,562 users, 4 developer communities, 1 year | disentangled by a model | web page only |
| Song et al., Who plays which role when | arXiv preprint 2026 | 6,307 Slack messages, 55 students, 18 teams, one semester | median 9 messages per student per window | full text |
| Garcia and Treude, gender and student teams | arXiv preprint 2025 | 39 students, 8 teams, 8 weeks of Slack | men wrote most replies coded as delayed (80.77%, n=21); response times were not compared by gender | abstract |
| Damianova and Berrezueta-Guzman, student Scrum team | arXiv preprint 2026 | one 8-person student team, Discord, Notion, GitHub, one year | tool-mediated coordination | abstract |
| Fathollahzadeh et al., SENIR | arXiv preprint 2025 | LLM labels on DISCO, resolution by intent | resolution AUC 0.7 to 0.8, on resolution labels the same LLM pipeline assigned (validated at 89% F-score on 400 hand-labelled conversations) | abstract |
| Perera et al., team collaborative dialogue | arXiv preprint 2023 | Slack chat of one 8-person team in one shared channel, dialogue acts | method paper | abstract |
| Stray and Moe, meetings and Slack | arXiv preprint 2020 | longitudinal case study | 7 h 45 min scheduled plus 8 h 54 min unscheduled meetings a week | abstract |
| Li et al., SlackBench | arXiv preprint 2026 | 140 queries over privacy-preserving reenactments of real research projects | best agent about 80% | abstract |

### Slack (enterprise)

Wang et al. coded 100 of 4,300 channels into 9 types (inter-coder kappa 0.83). For project channels (n=32, mean 355.9
messages, 11.1 members, 16.4 words per message) the shares below are my division of their reported mean counts
(derived; ratios of means, not medians):

| Feature (project channels) | Mean count | Share of messages (derived) |
|---|---|---|
| Messages with an @user mention | 79.1 | 22% |
| Messages with a URL | 34.2 | 9.6% |
| Messages with a file | 60.4 | 17% |
| Messages from bots | 52.1 | 15% |
| Messages with an emoji | 11.9 | 3.3% |
| Messages with a reaction | 19.5 | 5.5% |
| Messages with a code segment | 6.5 | 1.8% |
| Top poster's messages | 90.2 | 25% |

Social channels (n=10, 3,059 messages, 84 members) had about 9% of messages with emoji and 18% with reactions
(derived). IT-support channels (n=8, 4,537 messages) had 4.1 messages per thread and about 31% bot messages (derived).
18 of the 100 coded channels were "test" channels with about 8 messages in total. The authors also note that an older
study reported 156.7 words per thread, against 32.8 here for project channels (16.4 words times 2.0 messages), and that
an earlier synthetic-thread paper assumed 10 to 100 messages per thread while real means were 2 to 35.
Caveats: one company's R&D department, 2019 data, one product, channel means dominated by a few large channels, no
distributions reported.

### Gitter, IRC, Discord (developer communities)

Gitter (Shi et al.): peak hours UTC 9 to 10, 13 to 14 and 18 to 21, low activity UTC 1 to 6; more chat on weekdays,
most on Wednesday and Thursday; first reply mean 220 s, 80% within 343 s, and a reported maximum of 1,264 s, which
suggests long gaps were cut, so the mean is probably a lower bound (inference). Initiators-only made up 54.5% to
81.7% of participants depending on the community. 89.05% of dialogs were on the community's domain and 10.95% off
topic or social; API usage was the top topic (29.37%). About 1/4 of dialogs got no reply. Caveats: dialogs came
from a model with F1 0.47 and NMI 0.74 on their hand-labelled sample, so dialog-level numbers carry that error;
the hand-labelled sample excluded code-heavy, non-English and low-quality dialogs; public help rooms are question
and answer, not a closed team's chat.

IRC (Kummerfeld et al.): see item 3 and section 2.3. Caveats: one technical support channel plus one other channel;
link agreement kappa between annotators (before adjudication) was 0.71 to 0.74, so interleaving counts carry label noise.

Discord: the large public dataset (Aquino et al.) is a sample of servers listed in Discord's discovery feature (about
10% of those listed); gaming is the top description keyword (15.28% of descriptions), programming is about 1.17%. It suits
platform-level numbers (bots wrote 17% of messages) but not a small student team server. DISCO is closer to the
target, but I could read only its listing, so I cannot report distributions from it.

None of the sources reports full message-length distributions or inter-message gap distributions for team chat; they
give means, shares and a few histograms.

### Student teams

Song et al.: 6,307 messages and 93,474 words from 55 students (about 14.8 words per message, derived), median 9
messages and 116 words per student per deliverable window (1 to 2 weeks), teams of 4 to 6. Students enacted a mean
of 2.3 communication roles per window, role diversity rose over the semester, role use peaked at phase-specific
moments (for example "gatekeeper" in the final week), and explicit conflict mediation was rare on Slack (4 of 424
student-windows, 0.9%), possibly because it moves off-platform. Caveats: one course, one university, consent from
94 of 186 students and only 55 analysed, individual-level consent so teams are partly observed.

## 2. Quantitative patterns

### 2.1 Timing: bursts, heavy tails, cycles

All [abstract] unless noted.

| Paper | Venue/year | Finding |
|---|---|---|
| Barabasi, origin of bursts and heavy tails | arXiv 2005 | Priority-based task queueing gives heavy-tailed waits; random-priority execution gives uniform ones. |
| Vazquez et al., modeling bursts and heavy tails | Phys. Rev. E 2006 | Five human activity types are non-Poisson. |
| Malmgren et al., Poissonian explanation | PNAS 2008 | Email inter-event power law (exponent near 1) follows from daily and weekly cycles plus a tendency to continue an activity. |
| Jo et al., circadian pattern and burstiness | arXiv 2011 | After removing circadian and weekly patterns from phone data, heavy tails remain. |
| Ross and Jones, heavy-tailed dynamics | Phys. Rev. E 2015 | On a large social-media set, cycles and burstiness explain part but not all of the tail. |
| Wu et al., bimodal distribution | PNAS 2010 | Events split into bursts of frequent mutual exchange in short times and random initiations after long gaps. |
| Cui et al., QQ and WeChat | PLOS ONE 2018 | Inter-event times are piecewise: exponential at short scales, power law at long ones, but only at a 0.001 s time resolution; exponent differs between two cities. |
| Aoki et al., spike-train analysis | arXiv 2016 | In SMS data, people answer incoming messages much faster than phone or email users do; a Hawkes-type model needs a negative self-excitation term (a refractory effect after sending) to fit the data. |
| Martin et al., response times in WhatsApp and Instagram | arXiv 2026 | 3.4M messages, 889 chats from 97 participants: about 70% of WhatsApp and 44% of Instagram messages answered within 5 min; partners' response speeds are close (regression slope about 0.79). |

Which side is stronger? Malmgren (cycles coupled to cascading activity explain the tail) and Barabasi (priority queueing) give different causes. Jo et
al. and Ross and Jones tested on large data and found a residual that cycles do not explain, so a pure cycle account
is too simple. For teamsim the cause does not matter, the shape does: a mixture of in-burst gaps (seconds),
within-conversation gaps (minutes) and between-conversation gaps (hours to days) modulated by time of week
(inference). None of these is a team-chat dataset: they are email, phone, blog, social media and private messaging.
Developer-chat anchors: Gitter first reply 220 s mean; IRC 94.9% of consecutive in-conversation messages within 2
minutes and 94.8% of conversations with a first response within 3 minutes (both [full text], section 2.3).

### 2.2 Participation inequality

| Paper | Venue/year | Population | Finding | Read |
|---|---|---|---|---|
| van Mierlo, 1% rule in four digital health networks | J. Med. Internet Res. 2014 | 63,990 actors, 578,349 posts | under 25% of actors posted; superusers wrote 74.7% of content | abstract |
| Geramita et al., 1% rule in a support group trial | J. Med. Internet Res. 2018 | 302 patients | superusers (1%) wrote 42.3% of posts; engagement "more broadly distributed than predicted" | abstract |
| Kim and Noh, news comments | arXiv 2025 | 260M comments, 6.2M users | highly skewed Gini and Palma; skew rises in elections | abstract |
| Chelkowski et al., Apache commits | PLOS ONE 2016 | 263 projects | contributor engagement follows a power law | abstract |
| Wang et al. (Slack) | above | 4,300 channels | top poster about 25% of messages in project channels (derived) | full text |

The two health-community papers disagree: the large observational study shows strong concentration, the trial a
flatter distribution. Neither is team chat, so I use them only as evidence that inequality is common and its size
varies; the Slack figure is the closest anchor.

### 2.3 Conversation structure, interleaving, unanswered questions

[full text] for Kummerfeld and Shi; the rest [abstract].

- Addressing: 48% of IRC messages name the addressee. If all of a user's directed messages are in one
  conversation, the undirected ones are in it 52.2% of the time.
- Length: 83.4% of conversations have fewer than 10 messages, and 40.8% of those have more than one author; 88.5%
  of messages under 5 words belong to conversations with more than one author, so short messages are not outliers.
- Gaps within a conversation: 94.9% of consecutive messages are within 2 minutes (98% in a second channel, so it is
  channel dependent); 88.3% are 8 messages or fewer apart; 99.4% are within 100 messages. First response within 3
  minutes in 94.8% of conversations; of the conversation starters that get a reply, 37.7% get several; 6.8% of
  conversations start with a directed message.
- Disentangling is hard: Kummerfeld et al.'s annotators agree on exactly matching conversations at F1 about 50 on
  Ubuntu and 28 on a second channel (inter-annotator agreement, not model scores); their model's F-score varies from
  11 to 40 across samples; the heuristic behind a widely used corpus gives only 10.8% fully correct conversations
  (precision). Five popular methods "do not perform well" on software chat; the best reaches an average F1 of only
  0.47 (Jiang et al., arXiv 2021, abstract).
- Unanswered: 24% of Gitter dialogs; self-answered monologues 1%. In DISCO, resolution varies by question intent
  (API usage higher; "discrepancy" and "review" lower; SENIR abstract).
- Slack threads: 2.0 messages per thread in project channels, 4.1 in IT support.

### 2.4 Content features: reactions, emoji, code, links, files, bots, off-topic

See the Slack table for shares by channel type; Gitter off-topic 10.95%; Discord bots 17% of all messages. I did not
find, in the papers searched, a measured rate of edits or deletes, of attachment-only messages, or of decisions and
action items per 100 messages. Those would have to be measured by teamsim (open problems).

## 3. Remote and hybrid work, time zones

| Paper | Venue/year | Population | Finding | Read |
|---|---|---|---|---|
| Yang et al., effects of remote work on collaboration | 2022 (venue not verified) | information workers at one large firm | after a shift to remote work, employees talked less often with a smaller number of weak ties (as cited by Zuzul et al.; the text I retrieved was an early preprint without this result) | abstract (partial) |
| Zuzul et al., Dynamic silos | arXiv preprint 2021 | 360 billion emails, 4,361 organisations, plus one organisation's IM and calls | modularity up in 2020; people move between groups more but talk within their group | abstract |
| Carmody et al., co-location and communication networks | arXiv preprint 2022 (journal version not verified) | email network of one North American university | an estimated loss of more than 4,800 weak ties over 18 months (model-based counterfactual); a slight recovery under hybrid work, reported as an initial finding | abstract |
| Soda et al., generative AI and collaboration | arXiv preprint 2026 | 12,000+ knowledge workers, 13 months | Copilot rollout raised collaboration time and broadened networks | abstract |
| Stray and Moe | arXiv 2020 | global software teams | unbalanced activity on Slack across sites was a barrier | abstract |

Inference for teamsim: a distributed-team preset should reduce cross-group messages, keep within-group messages,
and show weak-tie loss, rather than only moving hours. None of these gives chat rates by time zone; Gitter's UTC
profile is the only hour-of-day anchor I read. The studies are email-based or about large firms, so transfer to a
5-person student team is untested.

## 4. Synthetic multi-party dialogue and how realism was judged

| Paper | Venue/year | Method | Realism evaluation | Key result | Read |
|---|---|---|---|---|---|
| Bouleimen et al., Collective Turing test | Scientific Reports 2026 (arXiv 2025) | Llama 3 70B and GPT-4o write threads on Reddit topics | 251 participants; 1,205 valid pair judgments from 203 of them after exclusions | mistaken for human 39%; Llama 3 spotted 56%, GPT-4o 66% | full text |
| Kamoi et al., CoCoEval | arXiv preprint 2026 | turn-level detection of 10 inconsistent or uncollaborative behaviours; GPT-4.1, GPT-5.1, Claude Opus 4 | frequency comparison with 300 human conversations from 6 meeting and debate sets | LLM output has far fewer such behaviours; prompting overshoots; SFT repeats | full text |
| Penzo et al., multi-party with constraints | arXiv preprint 2025 | whole-chat generator vs turn-by-turn party | structure, compliance, human and LLM judge | turn-by-turn conforms better, more variety | abstract |
| Kazemi et al., social patterns in synthetic data | arXiv preprint 2026 | cyberbullying chats from GPT-4o, Grok-2, Llama-3.3-70B, compared with 10 authentic teen role-play conversations | structure, style, affect, escalation, human eval | structure kept; magnitudes and timing distorted | abstract |
| Zhang et al., MPCEval | arXiv preprint 2026 | reference-free metrics: participation balance, progression, speaker consistency | metrics applied to human-written and model-generated chats; no human judgments (listed as future work) | single scores hide differences | abstract |
| Nama et al., When2Speak | arXiv preprint 2026 | synthetic transcripts with speak or stay silent labels | none against real chat; accuracy on a held-out split of its own synthetic data | SFT models stay over-conservative (missed interventions 0.50 on average); RL with asymmetric reward cut them to 0.19 to 0.22 | abstract |
| Ge et al., EMSDialog | arXiv preprint 2026 | multi-LLM pipeline from real reports, rule checks | human and LLM eval, downstream training | 4,414 dialogues; training on them helped | abstract |
| Li et al., SlackBench | arXiv preprint 2026 | privacy-preserving reenactments of real projects | task accuracy of agents | best about 80%, most under 66% | abstract |

What the evidence says:

- Human side-by-side judgment is a weak test. In the Collective Turing Test, the 58 best judges (success 0.8 or more)
  named style cues most (82.5% of their comments; text formality alone 49.1%), then content (49.1%: conformity 19.3%,
  verbosity or over-explaining 15.8%, no personal anecdotes 12.3%) and fewer typos and slang (21.1%). Judges did
  worse at 16 posts, close to chance. Models were asked to match human word counts and were still seen as verbose.
- Frequency comparison finds what readers miss. CoCoEval shows that a conversation-level 1 to 10 rating found no gap for
  a fine-tuned model, while turn-level counts showed it overproduced repetition and redundancy. Generating 30 turns in
  one call suppressed such behaviours; one turn per call increased them. Asking the model to include them at human
  frequencies made it overshoot (for example two speakers locked in persistent disagreement).
- Per-turn generation (one turn per call) gives better constraint conformance and variety (Penzo, abstract; CoCoEval
  [full text] agrees on the direction of the effect).
- Downstream training gains (EMSDialog) and held-out accuracy on the same synthetic data (When2Speak) are used when
  synthetic data trains a model. Neither tells you whether the chat looks like a team's.
- Evidence is thin for software-team chat. Nothing I found evaluates synthetic developer or student-team chat against a
  real team with distributions.

## 5. Pattern-oriented validation

| Paper | Venue/year | Point | Read |
|---|---|---|---|
| Grimm et al., Pattern-oriented modeling of agent-based complex systems | Science 2005 | use several patterns at different scales to select and calibrate bottom-up models; single-pattern models are too simple, all-data models too complex | web page (secondary summary) |
| Hartig et al., Statistical inference for stochastic simulation models | Ecology Letters 2011 | approximate Bayesian computation and pattern-oriented modelling bypass an intractable likelihood | abstract |
| May et al., Beyond abundance distributions | Proc. R. Soc. B 2015 | a tropical-forest model matched each of 6 patterns alone and up to 5 together, but not species-area and beta-diversity together | abstract |
| Topping et al., Post-hoc pattern-oriented testing | PLOS ONE 2012 | useful for testing a highly complex model; warns against over-fitting to patterns that lack their driving factors; fitting was long and complicated | abstract |

Reading for teamsim (inference): realism targets should be several patterns at several levels (message, conversation,
channel, team), checked together. Expect some pairs to conflict and say so. Do not tune a preset on one real source and
then claim realism; Topping's over-fitting warning fits a project whose only real source so far is one 8-person server.
The Gitter and IRC papers show how much one statistic moves between samples (IRC within-2-minute share 94.9% in one
channel and 98% in another; F1 11 to 40 across samples), so a tolerance should come from real-versus-real spread, not
from a fixed percentage.

## 6. Privacy of learning from real teams

| Paper | Venue/year | Finding | Read |
|---|---|---|---|
| Lermen et al., Large-scale online deanonymization with LLMs | arXiv preprint 2026 | HN to LinkedIn matching: 45.1% recall at 99% precision (987 queries); 55.2% recall at 90% precision with 89K candidates; classical baseline 0.1%; Reddit movie communities 2.8% at 99% precision (9,781 queries). Authors did not release code or data; ETH ethics approval | full text |
| Tari and Iamnitchi, Privacy vs fidelity in synthetic social media | arXiv preprint 2026 | authorship attribution (RoBERTa-large) 81% on real Dutch Instagram posts, 16.5% to 29.7% on LLM-generated ones; higher fidelity gives more leakage; metadata and reply graphs not tested | full text |
| Aquino et al., Discord Unveiled | arXiv preprint 2025 | names replaced by pseudonyms, IDs hashed with SHA-256 truncated to 12 characters; authors state no method guarantees anonymity | full text |
| Bobicev et al., Can anonymous posters on medical forums be reidentified | J. Med. Internet Res. 2013 | author attribution F-score 75% to 80% for messages of 100 to 150 words and 97.9% for 300+ words, among 30 to 50 candidates | abstract |
| Khan et al., I Am No One | arXiv preprint 2026 | style-guided LLM rewriting cut attribution F1 by 60% to 70% on blog and review data and, per the authors, outperformed DP baselines (strict DP gave lower F1 on one blog set, but with far worse perplexity) | abstract |
| Cano and Habernal, DP text generation degrades quality | arXiv preprint 2025 | under strong DP, text was at least 77% shorter, 9% less grammatical, 10% less diverse | abstract |
| Sun et al., SynBench | arXiv preprint 2026 | DP synthetic text "remains an unsolved challenge"; for one method (AUG-PE) at a tight budget (epsilon 0.5) the audit found measurable membership signal on three datasets, though overall AUC was low | abstract |
| Zhang et al., scoping review of ethics reporting | J. Med. Internet Res. 2024 | of 108 social-media text studies, 59.3% sought ethical approval, 12.9% explicitly obtained consent, 18.5% used aggregate analysis | abstract |
| Hemphill et al., Comparative sensitivity of social media data | Scientific Data 2022 | 1,018 people rate social media data moderately sensitive; prefer explicit consent and clear benefits | abstract |
| Song et al. (student Slack) | arXiv preprint 2026 | IRB approval; 94 of 186 students consented; analysis at individual level; raw messages not released | full text |
| Martin et al., WhatsApp and Instagram | arXiv preprint 2026 | donated chats from 97 participants; only response timing analysed | abstract |
| Li et al., SlackBench | arXiv preprint 2026 | "privacy-preserving reenactments" of real projects instead of real logs | abstract |

What follows from this (mix of evidence and inference):

- Removing names does not anonymise text. Attribution works on short messages within a closed candidate set (Bobicev:
  25-word texts reached F above 0.60, rising with length), and LLM pipelines make it cheap for whole post histories
  (Lermen: the novelty is lower cost, not new signals; their profiles are built from many posts, and they did not
  test single short messages). A small team is a small candidate pool, so risk is higher
  there than in the 89K-candidate test (inference).
- Hashing identifiers is weak when the identifier space is small or structured (inference; Aquino hashed Discord IDs,
  which are structured numbers, and truncated the hash).
- Synthetic text from a real corpus is not automatically safe: Tari found non-zero attribution accuracy on LLM output,
  and fidelity and leakage rise together. DP generation is the formal answer, but it costs length, grammar and
  diversity, and a 2026 benchmark calls it unsolved.
- Aggregates are the practical route: only 18.5% of the reviewed studies used them, but they leak far less. Even then,
  per-person profiles and rare cells are risky (inference).
- Consent practice in this area is uneven: most papers did not obtain explicit consent, while the people surveyed prefer
  it. The student-chat study asked for individual consent, got half, and published no raw text.
- Platform rules matter: the Discord dataset relied on the platform's public-server terms. I did not verify Discord's
  current developer terms for research use, so this needs a check before any collection from a Discord server.

## Implications for teamsim

### Realism targets for presets (first version)

Values are what the cited source reports; "derived" is my division. Use them as starting ranges, not truths.

| Pattern | Value (source) | Population | Caveat |
|---|---|---|---|
| First reply time to a question | mean 220 s; 80% within 343 s (Shi) | 8 Gitter developer communities | public help rooms; model-separated dialogs; mean likely a lower bound |
| Questions with no reply | 24% (Shi) | same | same |
| Consecutive messages of one conversation within 2 min | 94.9% (Kummerfeld); 98% in a second channel | Ubuntu IRC, another IRC channel | IRC support channels |
| Messages that name an addressee | about 48% (Kummerfeld) | Ubuntu IRC | IRC convention |
| Conversations under 10 messages | 83.4% (Kummerfeld) | Ubuntu IRC | one channel |
| Conversation starters with more than one reply, among those with at least one reply | 37.7% (Kummerfeld) | Ubuntu IRC | one channel |
| Words per message | 16.4 project, 23.0 IT support, 12.8 social (Wang); about 14.8 (derived, Song) | one company's Slack; one course | channel means |
| Messages per thread | 2.0 project, 4.1 IT support (Wang) | one company's Slack | means |
| Messages with an @mention, project | about 22% (derived, Wang) | same | ratio of means |
| Messages with a URL, project | about 9.6% (derived) | same | same |
| Messages with code, project / IT support | about 1.8% / 1.8% (derived) | same | counts include test-heavy mix |
| Messages with a reaction, project / social | about 5.5% / 18% (derived) | same | same |
| Bot share, project / IT support / public Discord | 15% / 31% (derived, Wang); 17% (Aquino) | Slack; Discord | different platforms |
| Top poster's share, project channel | about 25% (derived, Wang) | same | ratio of means |
| Off-topic or social dialogs | 10.95% (Shi) | Gitter | help-room topics |
| Hours: peak / low | UTC 9 to 10, 13 to 14, 18 to 21 / UTC 1 to 6 (Shi) | Gitter, global open source | not a student team |
| Messages per student per 1 to 2 week window | median 9 (Song) | one UI-design course, teams of 4 to 6 | consenting students only |
| Explicit conflict mediation | 0.9% of student-windows (Song) | same | may happen off-platform |
| Roles enacted per student per window | mean 2.3, rising over the term (Song) | same | LLM and expert labels |

### Recommended realism validation method

1. **Targets file per preset.** Each target has: statistic, reference value or range, tolerance, source, population,
   hard or soft. Targets sit at four levels: message (words, links, code), conversation (unanswered share, thread
   length, interleaving), channel (top-poster share, bot share, reaction share), team (cross-group ties for remote
   presets, messages per person).
2. **Tolerance from real-versus-real spread.** Use the range between real communities or samples (examples above)
   where it exists; otherwise start wide, mark the target soft, and tighten when a second real source exists
   (inference, based on the sample variation in Kummerfeld and Shi; Topping et al. set their pass marks by hand,
   for example an arbitrary 10.0 on a summed log-scale deviation, so this is not their method).
3. **Joint check.** All hard targets must pass in the same run. Report each failing pair (May et al.).
4. **Behaviour-frequency check.** Count planted and incidental behaviours (unanswered questions, off-topic,
   repetition, misunderstandings, conflicting statements, fragments, attachment-only posts) per 100 messages. Because
   the script knows what it planted, most of these can be counted exactly; use an LLM detector only for free-form text
   and validate it first (CoCoEval).
5. **Discriminator guard, run locally.** A simple classifier on numeric message features (length, gap, type shares)
   trained to tell a private real team from a synthetic run; publish only its AUC. If the maintainer has no real team,
   skip. Do not ship the real features.
6. **Human reading as a sanity check only.** The Collective Turing results show readers are fooled often, so a pass
   proves little; use it to find obvious problems (formality, politeness, no slang, no anecdotes).
7. **Hold-out.** Keep at least one real source out of tuning.

### Decisions this feeds

- **Model-free default (run-1 recommendation): supported for structure.** Timing, lengths, shares, interleaving,
  unanswered questions and participation can all be set by a seeded script. What the literature says an LLM adds is
  fluent text, and what it fails at is the mess: verbosity, politeness, conformity, no slang, too few
  misunderstandings. If an LLM is used, generate one turn per call, cap length to the preset's word distribution, add
  noise after generation, and run the behaviour-frequency check. Record outputs for replay (already the plan).
- **Preset design.** A preset is a set of channel types, each with the targets above, plus a team profile (size,
  time zone spread, cross-group tie level). Calibrate channel types separately; a "project" and a "social" channel
  differ by 3 times in reaction share.
- **Scoring.** Include unanswered questions, implicit replies and interleaving in the ground truth so a product is
  scored on them; the 48% addressee rate means thread-by-reply-link alone will miss most structure.
- **v0.1 actions (chat first).** Chat targets are the best supported. For tasks and repo, the literature I read gives
  no numbers; do not claim realism there yet.
- **First user.** Builders of team-facing software need channel-type realism more than prose quality; students need
  low message volume per person (median 9 per window in the one student study).
- **Simulated feedback gate (ADR 0003).** The same lesson applies: judge by frequencies, not by how convincing a
  response reads. Conformity (agreeing with others) was the third most cited cue (19.3%) that gave away LLM threads, which
  supports a sycophancy check and a diversity check. This is consistent with the gate and does not change it.
- **Stack/runtime.** The distribution checks need only the standard library (histograms, quantiles, two-sample
  distances); no new dependency is needed for validation (inference).

### Safe procedure for deriving patterns from a real team

Before: get explicit consent from every member of the team, and agree the output is numbers only; check the platform's
current rules for research use; run the extractor locally on the maintainer's machine; do not send real chat to a hosted
model; keep the raw export out of the repo and out of backups that sync.

Collect (computed locally, then discarded):

- Per channel type: histogram of words per message in log bins; histogram of gaps between consecutive messages
  (log bins, seconds to days); share of messages that are replies, in threads, with a mention, with a reaction, with a
  link, with a file or image only, with a code block, from a bot, edited, deleted.
- Per channel: thread-length histogram; share of questions with no reply within 24 hours (counted by the extractor,
  not by reading); number of active participants; sorted per-person message shares as a vector without identities,
  then only the top-1 share and Gini.
- Per team: activity by hour of week (normalised, in the team's local time), messages per person per week.
- Coarsen: bins of at least 5 events; suppress any cell that comes from fewer than 5 people or 20 messages; round
  shares to whole percent; publish pooled numbers only when 3 or more teams contribute (inference).

Never collect or keep: message text, quotes or paraphrases; names, handles, user or message IDs (hashes included);
channel, server or file names; link domains; per-message timestamps; reply graphs with identities; per-person time
profiles or per-person vocabularies; emoji or word frequencies per author (stylometry); direct messages; attachments.

After: a person reviews the numbers file before it leaves the machine; keep only the numbers and the extractor's source
(which can be public); record team size, period, and consent date, not the team's identity.

Evidence behind this: LLM-based re-identification needs only text (Lermen), short messages are attributable
(Bobicev, closed candidate sets; Tari), synthetic text leaks style (Tari), and no anonymisation method is a guarantee,
even with pseudonyms and hashed IDs (Aquino). I did not retrieve a
paper on differential privacy for chat histograms; adding noise to counts is the standard tool for aggregates and
worth considering if numbers from a very small team are ever published (inference).

## Open problems

- No source gives full distributions (not just means) of message length and gaps for team chat; teamsim could
  publish them, from consenting teams, as its own contribution.
- No rates found for edits, deletes, attachment-only posts, decisions or action items per 100 messages, nor how often
  a decision is stated once and never confirmed. These are the planted-fact types teamsim scores, so measure them.
- Student-team data is one course (Song) plus abstract-level studies; a student preset rests on thin evidence.
- Time-zone and distributed-team chat rates are missing; remote-work studies use email and very large firms.
- DISCO's distributions were not read; a full-text read would add developer-Discord numbers.
- Whether the Slack and Gitter means transfer to 5-person Discord teams is untested.
- Tolerances: the literature gives no accepted method for setting them for chat; the real-versus-real spread proposal is
  mine and should be tried on two real sources.
- Whether a numbers-only release from a small team can still identify it (for example through a distinctive hour-of-week
  profile) was not studied in what I read.

## Where this disagrees with the run-1 notes

- The prototype notes treat "most activity 00:00 to 06:00 UTC, late-night bursts" as a real pattern. In the one
  literature source with an hour profile (Gitter) UTC 1 to 6 is the quietest period. These are different populations
  (one student server on US Pacific time versus global open-source help rooms), so both can be true; the lesson is that
  the hour profile is a preset parameter, not a constant, and n=1 cannot set it.
- The notes plan "about 15% of long messages split into fragments", the shipped transform uses 40%. I found no
  published rate for message fragmentation in either direction, so neither number is literature-backed; measure it.
- The notes record a noise share of 74 off-topic messages. If those sit on top of about 316 dataset messages, that is
  roughly 19% off-topic (derived, unclear overlap), against 10.95% off-topic dialogs in Gitter. A student server may
  differ, but the number should be a labelled preset parameter.
- The personas note says realism patterns "generalise" across chat, tasks and repo (its section 6). The literature I read
  supports chat only; I found nothing on issue-comment or commit-message rates, so the other two columns remain untested.
- No contradiction with ADR 0003. The literature supports its requirement that simulated feedback be measured against
  published human results.

## Sources

All read 2026-11-11. Depth marked in the text.

- Wang et al., Group Chat Ecology in Enterprise Instant Messaging: How Employees Collaborate Through Multi-User Chat Channels on Slack: https://arxiv.org/abs/1906.01756
- Shi et al., A First Look at Developers' Live Chat on Gitter: https://arxiv.org/abs/2107.05823
- Kummerfeld et al., A Large-Scale Corpus for Conversation Disentanglement: https://arxiv.org/abs/1810.11118
- Aquino et al., Discord Unveiled: A Comprehensive Dataset of Public Communication (2015-2024): https://arxiv.org/abs/2502.00627
- Subash et al., DISCO: A Dataset of Discord Chat Conversations for Software Engineering Research (MSR 2022): https://zenodo.org/record/5909202
- Fathollahzadeh et al., Towards Refining Developer Questions using LLM-Based Named Entity Recognition (SENIR): https://arxiv.org/abs/2503.00673
- Perera et al., Fine-Grained Analysis of Team Collaborative Dialogue: https://arxiv.org/abs/2312.05471
- Stray and Moe, Understanding coordination in global software engineering: meetings and Slack: https://arxiv.org/abs/2007.02328
- Li et al., SlackBench: Benchmarking Agents on Collaborative Projects Grounded in Real Code Repositories: https://arxiv.org/abs/2611.05512
- Jiang et al., Dialogue Disentanglement in Software Engineering: How Far are We?: https://arxiv.org/abs/2105.08887
- Song et al., Who Plays Which Role When? Communication Role Dynamics for Peer Recognition and Team Performance Prediction: https://arxiv.org/abs/2606.28544
- Garcia and Treude, Gender Influence on Student Teams' Online Communication in Software Engineering Education: https://arxiv.org/abs/2502.14653
- Damianova and Berrezueta-Guzman, The Anatomy of a Successful Student Scrum Team: https://arxiv.org/abs/2601.03364
- Barabasi, The origin of bursts and heavy tails in human dynamics: https://arxiv.org/abs/cond-mat/0505371
- Vazquez et al., Modeling bursts and heavy tails in human dynamics: https://doi.org/10.1103/PhysRevE.73.036127
- Malmgren et al., A Poissonian explanation for heavy tails in e-mail communication: https://arxiv.org/abs/0901.0585
- Jo et al., Circadian pattern and burstiness in mobile phone communication: https://arxiv.org/abs/1101.0377
- Ross and Jones, Understanding the heavy tailed dynamics in human behavior: https://arxiv.org/abs/1505.01547
- Wu et al., Evidence for a bimodal distribution in human communication: https://doi.org/10.1073/pnas.1013140107
- Cui et al., Heterogeneous characters modeling of instant message services users' online behavior: https://doi.org/10.1371/journal.pone.0195518
- Aoki et al., Input-output relationship in social communications characterized by spike train analysis: https://arxiv.org/abs/1603.08144
- Martin et al., Sorry for the late reply: Response times and reciprocity in WhatsApp and Instagram chats: https://arxiv.org/abs/2605.03687
- van Mierlo, The 1% rule in four digital health social networks: https://doi.org/10.2196/jmir.2966
- Geramita et al., Association between patient engagement with an Internet support group and mental health outcomes (1% rule): https://doi.org/10.2196/10402
- Kim and Noh, Disproportionate Voices: Participation Inequality and Hostile Engagement in News Comments: https://arxiv.org/abs/2508.16040
- Chelkowski et al., Inequalities in Open Source Software Development: Contributors' Commits in Apache Projects: https://doi.org/10.1371/journal.pone.0152976
- Yang et al., The effects of remote work on collaboration among information workers: https://doi.org/10.1038/s41562-021-01196-4
- Zuzul et al., Dynamic Silos: Increased Modularity in Intra-organizational Communication Networks during the Covid-19 Pandemic: https://arxiv.org/abs/2104.00641
- Carmody et al., The effect of co-location on human communication networks: https://arxiv.org/abs/2201.02230
- Soda et al., The Effects of Generative AI on Collaboration and Social Networks Among Knowledge Workers: https://arxiv.org/abs/2610.32461
- Bouleimen et al., The Collective Turing Test: Large Language Models Can Generate Realistic Multi-User Discussions: https://arxiv.org/abs/2511.08592
- Kamoi et al., Evaluating LLM-Simulated Conversations in Modeling Inconsistent and Uncollaborative Behaviors in Human Social Interaction: https://arxiv.org/abs/2603.17094
- Penzo et al., Don't Stop the Multi-Party! On Generating Synthetic Written Multi-Party Conversations with Constraints: https://arxiv.org/abs/2502.13592
- Kazemi et al., Do Social Patterns Hold in Synthetic Data? Cyberbullying Dynamics in LLM-Generated and Authentic Dialogues: https://arxiv.org/abs/2609.17549
- Zhang et al., MPCEval: A Benchmark for Multi-Party Conversation Generation: https://arxiv.org/abs/2603.04969
- Nama et al., When2Speak: Temporal Participation and Turn-Taking in Multi-Party Conversations: https://arxiv.org/abs/2605.05626
- Ge et al., EMSDialog: Synthetic Multi-person Emergency Medical Service Dialogue Generation: https://arxiv.org/abs/2604.07549
- Grimm et al., Pattern-oriented modeling of agent-based complex systems: lessons from ecology (Science 310): https://doi.org/10.1126/science.1116681 (secondary web summary only)
- Hartig et al., Statistical inference for stochastic simulation models: theory and application: https://doi.org/10.1111/j.1461-0248.2011.01640.x
- May et al., Moving beyond abundance distributions: neutral theory and spatial patterns in a tropical forest: https://doi.org/10.1098/rspb.2014.1657
- Topping et al., Post-hoc pattern-oriented testing and tuning of an existing large model: lessons from the field vole: https://doi.org/10.1371/journal.pone.0045872
- Lermen et al., Large-scale online deanonymization with LLMs: https://arxiv.org/abs/2602.16800
- Tari and Iamnitchi, Measuring Privacy vs. Fidelity in Synthetic Social Media Datasets: https://arxiv.org/abs/2603.03906
- Bobicev et al., Can anonymous posters on medical forums be reidentified?: https://doi.org/10.2196/jmir.2514
- Khan et al., I Am No One: Style-Aware Paraphrasing for Text Anonymization: https://arxiv.org/abs/2609.12341
- Cano and Habernal, Differentially-private text generation degrades output language quality: https://arxiv.org/abs/2509.11176
- Sun et al., SynBench: A Benchmark for Differentially Private Text Generation: https://arxiv.org/abs/2509.14594
- Zhang et al., Reporting of Ethical Considerations in Qualitative Research Utilizing Social Media Data on Public Health Care: Scoping Review: https://doi.org/10.2196/51496
- Hemphill et al., Comparative sensitivity of social media data and their acceptable use in research: https://doi.org/10.1038/s41597-022-01773-w
