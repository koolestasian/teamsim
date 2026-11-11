# Making the sim more realistic (2026-11-10)

Source: a read-only sample of about 250 messages from a real 8-person student team server
(general, announcements, changelog, resources, ask-bot, pins), compared with the Lantern Shelf
dataset and the 2026-11-11 sim run (prototypes/teamctx-sim/reports/20261111-012414). Only patterns are
recorded here, never names, IDs or message text. Real chat stays out of the repo and fixtures.

## Gaps between the sim and a real team

| # | Real pattern | Sim / dataset today | What it would test |
|---|---|---|---|
| 1 | Activity spread over weeks, with late-night bursts and days of silence. Most activity is 00:00-06:00 UTC, which is the previous evening in Pacific time. | 316 messages posted in about 4 minutes. Emulator stamps everything "now". Server timezone is UTC. | Date queries (all 9 are n.a.), `/catchup` "since" windows, relative due dates ("tmrw", "thurs") across the UTC/local date line. |
| 2 | One thought split across 3-6 quick messages by the same author. | Mostly one message per thought. | Capturing a decision from one fragment; retrieval when the answer is spread over fragments. |
| 3 | Agreement shown by a reaction (thumbs up on "can you write X") instead of a reply. | No reactions posted. teamctx ignores reactions. | Whether a task acknowledged only by a reaction is missed (a product decision, not a bug). |
| 4 | Attachment-only messages (screenshots, screen recordings, log .txt files) that carry the real information. | 5 attachment names; the emulator drops attachments. | Empty-content messages in search, context and /ask; how a reply to an image reads. |
| 5 | Forwarded messages (Discord's forward feature): the text lives in a snapshot, not in `content`. | None. teamctx has no handling for message snapshots. | Likely stored as an empty message. Verify against Discord docs before building anything. |
| 6 | Display names are gamer handles; people refer to each other by real first names, with spelling variants. | Display name = real name. Name eval scores 0.89, which is inflated. | "What is <first name> working on?" when the stored name is a handle. teamctx keeps one display name and no aliases. |
| 7 | Long off-topic stretches (exams, food, games, jokes), slang, profanity, lowercase, emoji codes, non-native English typos. | 8 polite, on-vocabulary distractors and a few typos. | Ranking and /ask under real noise; paraphrase recall is already 0.045. |
| 8 | Long, well-formatted AI output pasted into chat ("the AI said..."), with a different voice from the person posting. | None. | Whether pasted AI text is ranked or cited as a team decision. |
| 9 | Decisions made in voice calls and outside tools, then posted as a "recap" message, or only as a link (Google Doc, Drive, meeting-notes app). | Three meeting-note blocks pasted in full. | Records whose only Discord trace is a link or a short recap. |
| 10 | Assignments as one bolded owner list (several tasks in one message), @everyone deadline posts, pinned speaker/role lists. | Mostly one task per message; no pins. | Multi-task capture from one message; pins as an importance signal (not supported). |
| 11 | Contradicting deadlines ("the sheet says Tue, the team assumes Wed") that are never resolved. | Reversals are clean `replaces` chains. | Answers that should surface a conflict instead of picking one date. |
| 12 | A member disappears for days, then "caught up on the recap" and takes work. | Every member is active in every act. | The main `/catchup` user story, with a long gap for one member. |
| 13 | Another bot in the server posts long formatted answers; people troll it with off-topic and emoji-only messages. | One bot (crashwatch), 2 messages. | Bot noise in search, and in /ask with and without include_bot_authors (Spec A). |
| 14 | An API key pasted in plain text into a resources channel. | One injection test asks for "admin tokens"; no real-looking secret in chat. | teamctx has no secret redaction for chat content, so a pasted key is indexed, searchable, exported and sent to the model. |

## Proposed changes, in order of value

1. **Time realism (1).** Run the sim with `--timezone America/Los_Angeles` and place most posts at 16:00-23:00 local time, so many fall on the next UTC day. For dates, try making the loopback shim rewrite message timestamps (and the id-derived time, if teamctx reads it) from map.json to the dataset dates. Check first which field teamctx uses for `created_at`. If that works, the 9 date cases come back.
2. **Realism transform over the dataset (2, 3, 4, 7, 8).** A deterministic, seeded step in script.py that keeps ground truth through map.json:
   - split about 15% of long messages into 2-5 fragments by the same author, 5-40 s apart;
   - add thumbs-up and other reactions as acknowledgements;
   - add attachment-only messages, with placeholder files if the emulator ever accepts them;
   - add off-topic bursts of 20-60 messages with slang;
   - paste a few AI-style walls of text.
   Report recall with and without the transform: the difference is the realism tax.
3. **Handles and aliases (6).** Give the sim cast gamer-style display names and keep real names only in message text. Add name eval cases that ask by first name. This will likely fail today; whether to support aliases is a product decision.
4. **Secret in chat (14).** Add one fake key in the `sk-...` shape to a message. Check search, export and /ask, and decide whether teamctx should mask secret-shaped strings at ingest or at display. This needs a maintainer decision and probably an ADR.
5. **Forwarded messages (5).** Read Discord's docs on message snapshots, add a gateway fixture, and see what teamctx stores. If it stores an empty message, that is a real bug for live use.
6. **Absent member + recap-only decisions (9, 12).** Script one member to go silent for an act and then run `/catchup`. Add one decision that exists only as a link plus a short recap.
7. Later: conflicting deadlines (11), multi-task messages (10), bot noise (13).

## Implementation status (2026-11-10)

Realism mode is the default for `sim.py` (`--plain` runs the original scenario; one state folder
holds one mode). Code: `simlib/script.py` (realism section), driver, checker checks 11-15,
tests in `tests/test_realism.py`.

| # | Status |
|---|---|
| 1 Time | Partly. Date eval cases are now scored (they never depended on timestamps). Server timezone is `-08:00`; relative due phrases ("tomorrow", a weekday) are checked against the local calendar (check 15). Multi-week time is **not** simulated: the emulator stamps IDs with `Date.now()`, and its heartbeat, interaction and token checks share that clock, so jumping it breaks sessions; teamctx reads time from the ID and has no injectable clock. Needs a product change (a test clock) to go further. |
| 2 Fragments | Done: 40% of long, splittable messages become 2-5 quick fragments; the fragment holding an eval answer keeps the dataset id, so ground truth stays valid. Capture targets and injection probes are never split. |
| 3 Reactions | Done: about 55 acknowledgements on decision and task messages, plus some on chatter. teamctx ignores reactions (reported in check 11). |
| 4 Image-only | Done with a stand-in: an image embed with empty text (the emulator drops real attachments). Reported, not scored, in check 2. |
| 5 Forwards | Not simulatable: the emulator has no message snapshots. From code: teamctx does not treat a forward as a reply, but stores its empty `content`, so the forwarded text is lost. Not run. |
| 6 Handles | Done: gamer-style display names; check 12 searches each first name. |
| 7 Noise | Done: three off-topic bursts (74 messages) with slang, typos, emoji and some product-like words. |
| 8 Pasted AI | Done: two confident AI answers that contradict team decisions; check 11 compares their rank with the team's decision. |
| 9 Recap-only | Done: one decision only in a call recap plus a link; check 11 needs it in the top 3. |
| 12 Absent member | Done: Pell reads nothing in acts 2-3 and catches up in act 4 (check 14). |
| 14 Secret | Done: a fake `sk-` key pasted in #engineering; check 13 lists every read surface that returns it. |
| 10, 11, 13 | Not done yet (multi-task messages and pins, conflicting deadlines, bot noise). |

## Calibrating against the real server without copying it

Compute statistics locally from the real server through the read-only MCP: message length
distribution, gap between consecutive messages, hour of day, share of messages of 4 words
or fewer, reply and reaction rates, share of attachment-only messages. Use those numbers to
tune the transform. Keep only the numbers; never save text, names or IDs.
