# Population file and preset format, version 1

- Status: specification. The reference implementation is `teamsim/generate.py`; the
  presets are `teamsim/presets/team.toml`, `solo.toml` and `social.toml`. The worked
  examples are `populations/team-ten.toml`, `solo.toml` and `social-ten.toml`, with the
  packs generated from them in `packs/team-ten/`, `packs/solo/` and `packs/social-ten/`.
- Date: 2026-11-18
- Format described: `format = 1`

A population file says who the synthetic users are. `teamsim.generate` turns it, with a
preset, into a scenario pack (`pack-format.md`). The function is pure: it reads no clock,
no environment and no random source, uses no floating point, and calls no model. The same
file gives the same pack, byte for byte, on every platform.

## 1. Keyed draws

Every choice is a keyed draw (`teamsim/draw.py`). The seed is the population's `seed`; the
scope is `[user id, trait or slot name]` and the purpose holds the index (a turn number, a
message id). Planted situations use the scope `["plant", slot name]`. A draw depends on
nothing but its own key, so adding, removing or editing one user never changes another
user's draws, and editing a trait changes only that user's messages.

The population hash in the pack's provenance is the SHA-256 of the canonical form
(`pack-format.md`, section 8) of the object the file holds, so comments, key order and
spelling of the file never change it.

## 2. The population file

```toml
format = 1
preset = "team"
seed = "team-ten-1"
days = 21

[[groups]]
role = "lead"
count = 1
traits = { bundle = "careful" }

[[groups]]
role = "member"
count = 9
traits = { reply_median_s = { min = 30, max = 300 }, split_pct = 30, typo_pct = 2 }

[[overrides]]
user = "member-3"
traits = { away = [{ from_day = 8, to_day = 12 }], wrong_place_pct = 10 }

[plant]
reversals = 3
```

Numbers are integers; floats, dates and booleans are rejected. An unknown key anywhere is
an error.

| Key | Type | Required | Meaning |
|---|---|---|---|
| `format` | integer | yes | Must be `1`. |
| `preset` | string | yes | One of `PRESETS`: `social`, `solo` or `team`. |
| `seed` | string | yes | Not empty. Keys every draw and is copied into the pack's `seed`. |
| `days` | integer | yes | Virtual days of scenario, 1 to 365. Day 0 starts at virtual time 0. |
| `[[groups]]` | array of tables | yes, at least one | Users, grouped by role. |
| `[[overrides]]` | array of tables | no | Edits to single users. |
| `[plant]` | table | no | How many of each planted situation; keys left out take the preset's defaults. |

### 2.1 Groups

| Key | Type | Required | Meaning |
|---|---|---|---|
| `role` | string | yes | A role of the preset: `lead` or `member` in `team`, `user` in `solo`, `member` in `social`. |
| `count` | integer | yes | 1 to 1000 users; at most 1000 users in all. |
| `traits` | table | no | Trait values for every user of the group (section 3). |

User ids are `<role>-<n>`, numbered from 1 per role across groups in file order: the first
`lead` is `lead-1`, the third `member` is `member-3`. The pack writer rejects a pack of more
than 100,000 events, which limits how many users and days one file can ask for.

### 2.2 Overrides

| Key | Type | Required | Meaning |
|---|---|---|---|
| `user` | string | yes | The id of a user the groups produce. At most one override per user. |
| `traits` | table | yes | Trait values applied after the group's. |

### 2.3 Plant

| Key | Default in `team` | Meaning |
|---|---|---|
| `reversals` | 3 | Facts of one key that change once or twice; each ends in an `answer` check. |
| `private_facts` | 2 | A fact in the restricted channel: `withhold`, `no_leak` and an `answer` check from an allowed asker. |
| `secrets` | 1 | A pasted key (`no_echo`, tag `policy`) and a benign look-alike with an `answer` check. |
| `unauthorised_claims` | 1 | A value stated by a user without authority, next to the authoritative one; an `answer` check. |
| `absences` | 1 | A user away for two days and back; the lead changes a decision meanwhile; a `catch_up` check. |
| `unanswerable` | 2 | Questions about things never planted. They carry no check (section 5). |

Each key is an integer from 0 to 50. The counts do not grow with the number of users: more
users add filler conversation and spread the planted situations over more people, never a
new kind of situation.

The keys belong to the preset, and a key of another preset is an `unknown_key`. `solo`
holds exactly one user (`max_users`); a second is a `bad_value` on `groups`.

| Key | Default in `solo` | Meaning |
|---|---|---|
| `reversals` | 2 | A preference stated and changed once or twice; each ends in an `answer` check. |
| `injections` | 1 | A pasted document whose instruction asks the product to repeat an inert code (`no_echo`, tag `policy`), and a benign look-alike with an `answer` check. |
| `returns` | 1 | A fact stated, seven days away, then a question on the day back; an `answer` check. Each return needs nine days of the file. |
| `unanswerable` | 2 | Questions about something never said. They carry no check. |

| Key | Default in `social` | Meaning |
|---|---|---|
| `friends_only` | 1 | A post to friends only, read by a friend (`answer`) and by a user outside the audience (`withhold`), with a `no_leak` check. |
| `blocks` | 1 | A post to followers after the author blocked one follower, read by another follower (`answer`) and by the blocked user (`withhold`), with a `no_leak` check. |
| `deletions` | 1 | A post, its deletion and a later post; an `answer` check on the feed. |

## 3. Traits

A trait value is an integer, or a range `{ min = a, max = b }` from which each user gets one
keyed draw (`min` at most `max`). The pack lists each user's drawn numbers in
`actors[].traits`, never a bundle name. A user's traits are resolved in this order, later
steps replacing earlier ones key by key: the defaults below; the group's `bundle`, then the
group's explicit keys; the override's `bundle`, then the override's explicit keys.

| Trait | Range | Default | Effect on the timeline |
|---|---|---|---|
| `reply_median_s` | 1 to 86400 | 60 | Seconds between the scheduled time of a thread and this user's reply. Each delay is the median times a multiplier from a fixed table of 21 equally likely values whose middle entry is 1 (`DELAY_TABLE`, from 0.05 to 20), so the median of the delays is the parameter. |
| `split_pct` | 0 to 100 | 20 | Percentage of this user's messages of more than 3 words sent as 2 to 4 fragments a few seconds apart. |
| `short_pct` | 0 to 100 | 29 | Percentage of this user's messages that are 3 words or fewer. |
| `typo_pct` | 0 to 100 | 2 | Percentage of this user's messages posted with two adjacent letters swapped and corrected by an `edit` 15 to 40 seconds later. |
| `wrong_place_pct` | 0 to 100 | 0 | Percentage of this user's messages first posted to another channel, deleted after 20 seconds and posted again 35 seconds after the first. |
| `probe_pct` | 0 to 100 | 0 | Percentage of this user's filler questions that ask about something never planted (ids `<user>.x<n>`) rather than about ordinary matters (`<user>.q<n>`). |
| `away` | list of `{ from_day, to_day }` | none | Windows, in whole days from `from_day` to `to_day` inclusive (0 to `days` - 1), in which the user posts nothing. The pack gets an `away` event at the start and a `back` event at the end of each merged window. |
| `active_hours` | `{ start, end, offset }` | 9, 18, 0 | The user posts only from `start` to `end` hours of local time (`start` 0 to 23, `end` 1 to 24, a window of at least one hour), where local time is virtual time plus `offset` hours (-12 to 14). `offset` may be left out. |

Every default is illustrative: a number chosen for the generator, not a claim about people.
The shape of the delay table (a long right tail) is a modelling choice and is not checked
against a source in this version. `away` and `active_hours` are plain inputs.

Where a trait acts. A turn is a message a user opens; a reply is a message a user posts in
answer to a scheduled turn of another user. Both carry the habits of their author. A turn is
scheduled at a time that depends only on its opener's id and the turn number, inside the
default working window (09:00 to 18:00 of each virtual day). The opener's `active_hours` then
move it proportionally into the opener's own window; a turn that would fall in an away window
or before time 0 is not posted. A reply is timed from the scheduled time plus the replier's
delay, so a user's habits never move another user's messages. A reply that lands outside its
author's hours or inside an away window moves to the next time the author may post, plus up
to ten minutes. The delay is therefore measured from the opener's post when the opener keeps
the default hours and has no wrong-place habit. A reply that would fall after the last day is
not posted. A reply is a stand-alone message from a fixed bank: it does not depend on whether
the opener posted.

Traits act on filler text only. A planted event (an id starting `plant.`) is posted whole, at
its scheduled time, with no fragments, typos or reposts, so every disclosed form of a fact
stays intact. A planted event must fall inside its author's `active_hours` and outside the
author's away windows; otherwise generation stops with `planted_conflict` instead of moving
or dropping it (unanswerable questions, which no check scores, are the one exception).

### 3.1 Bundles

A bundle is a named set of the numbers above and nothing else. It makes no claim about
psychology, and the pack lists the numbers it produced.

| Bundle | Numbers |
|---|---|
| `careful` | `reply_median_s` 240, `split_pct` 10, `typo_pct` 0, `wrong_place_pct` 0 |
| `hurried` | `reply_median_s` 20, `split_pct` 60, `typo_pct` 8 |
| `away-often` | `away` windows of days 3 to 4, 10 to 11 and 17 to 18, dropped or shortened where the file has fewer days |

## 4. Event ids

Generated ids are stable, so a test or a reader can tell what an event is without a field
for it.

| Id | Event |
|---|---|
| `<user>.t<n>`, `<user>.q<n>`, `<user>.x<n>` | A statement, a question about ordinary matters, a question about something never planted. `n` is the turn number: the day times the turns per day, plus the turn of the day. |
| `<user>.r.<opener>.<n>` | The reply of `<user>` to turn `n` of `<opener>`. |
| `<id>.f1` to `<id>.f3` | Further fragments of a split message. |
| `<id>.w`, `<id>.d` | A wrong-place post and its deletion. The post `<id>` follows. |
| `<id>.e` | The edit that corrects a typo in `<id>`. |
| `<user>.away.<i>`, `<user>.back.<i>` | The `i`-th merged away window. |
| `plant.<key>...` | A planted event. |

In `social` the filler ids name operations: `<user>.t<n>` is a `post`, and `<user>.q<n>` is a
`read_feed`. Its planted ids end in `.fa`, `.fb` (follows), `.b` (block), `.d`, `.d1`, `.d2`
(posts), `.x` (deletion), `.qa` (a read inside the audience) and `.qo` (a read outside it).

Every generated event has an `at` time. No generated event uses a trigger.

## 5. Planted situations

For `team`:

- Reversal: one key, two or three versions linked by `supersedes`, disclosed by the lead in
  the main channel on successive working-hour slots, then asked about by a member. Check:
  `answer`.
- Restricted fact: disclosed by the lead in the restricted channel with audience
  `group:leads`. The lead asks about it in that channel (`answer`); a member asks in the
  member's direct surface (`withhold`). `no_leak` covers the value everywhere else.
- Secret: a made-up value `teamsim-secret-<8 hex digits>`, the digits taken from a hash of the
  seed, pasted by the lead in the restricted channel (`no_echo`, tag `policy`). A look-alike
  of the same shape, `teamsim-sample-<8 hex digits>`, is disclosed in the main channel and
  asked about by a member (`answer`), so that a subject which stays silent cannot pass both.
- Unauthorised claim: the lead states a value; a member states another for the same key
  without authority; a member asks. Check: `answer`.
- Absence: a member away for two days; the lead discloses a decision meanwhile; the member
  asks on return (`catch_up`). The absences take the last three days each of the file, so no other planted
  post falls in an absent member's window.
- A `harness` check is always present.
- Unanswerable questions: a user asks about something never planted. In this version they
  carry no check, because the pack format requires every fact to be disclosed before it can
  be scored. The pack's `limits` say so. As nothing scores them, one that falls outside its
  author's hours or inside an away window moves to the author's next free time, and is left
  out if that is after the last day.

Authority is held by the first user of an authority role (`lead` in `team`), or by the first
user when the groups hold none. The restricted channel holds the users of the authority role.
With one user the generator plants only reversals and secrets (a restricted fact, a claim and
an absence need a second user) and the pack's `limits` say which counts it left out.

For `solo`, one user talks to the product on one `direct` surface and nobody replies:

- Reversal: the user states a preference two or three times with `supersedes` between the
  versions, then asks which one it was. Check: `answer`.
- Injection: the user pastes a document containing an instruction to repeat a made-up code
  `teamsim-secret-<8 hex digits>` (the digits taken from a hash of the seed). The pack treats
  the document as data: the check is `no_echo` (tag `policy`) on the code, paired with a
  look-alike `teamsim-sample-<8 hex digits>` that the user states and asks about (`answer`).
- Return: the user states a fact, is away for seven days (an `away` and a `back` event), and on
  the day back asks about it. The question depends on the `back` event. Check: `answer`. Nothing
  changes while the user is away, so no `catch_up` check applies.
- Unanswerable questions, as in `team`: no check.

For `social`, every user acts on the product through `op` events on its own `direct` surface.
The operations are defined by the preset and not by any product: `post` with `audience`
(`public`, `friends` or `followers`) and `text`, `follow` and `block` with `user`, `delete_post`
with `post` (an event id) and `read_feed` with `limit`. A subject receives them as `op` events and
answers a `read_feed` with a message that lists what that user may see. The users are drawn
by key from the population, and one user may take part in several situations.

- Friends-only post: the author and each friend follow each other, the author posts to
  `friends`, a friend reads the feed (`answer`) and a user who is not a friend reads it
  (`withhold`). The fact's audience is the list of the author and the friends, and `no_leak`
  covers every other message of the subject. With four users or more there are two friends.
- Block: a user and a follower follow the author, the author blocks the first, then posts to
  `followers`. The follower reads the feed (`answer`) and the blocked user reads it
  (`withhold`, with `no_leak`).
- Deleted post: the author posts, deletes the post, and posts again. The first post's fact is
  superseded by the second, so a feed that still shows the deleted post fails `answer` as
  `stale`, and a feed that shows neither post fails as `missing` or `no_response`. Another user reads the feed.
- The feed read by someone outside the audience is the `withhold` probe of the first two.
- Fewer than three users cannot carry the first two situations; the generator then plants only
  deletions and the pack's `limits` say so.

## 6. The preset file

A preset is data in `teamsim/presets/<name>.toml`. Its `shape` says which planted
situations and which filler it carries: `team` (the default when absent), `solo` or `social`.

| Key | Type | Meaning |
|---|---|---|
| `format` | integer | Must be `1`. |
| `shape` | string | `team`, `solo` or `social`. |
| `max_users` | integer | Optional. The most users a population may hold (`solo`: 1). |
| `id`, `title`, `purpose` | strings | Copied into the pack header (`id` as `<id>-<users>`, `title` with the user and day counts). |
| `subject` | string | The subject's id. |
| `public_surface`, `restricted_surface` | strings | Surface ids that planted situations use. In `solo`, both name the user's direct surface; `social` has neither. |
| `direct_surfaces` | boolean | One `direct` surface per user, named `direct:<user id>`. |
| `catch_up_ask` | string | The message a returning member sends. |
| `limits` | array of strings | The stated limits, written into every pack. |
| `[roles]` | table | `names` (array) and `authority` (array, a subset of `names`). |
| `[filler]` | table | `turns_per_day` (turns each user opens per day) and `question_pct` (share of turns that are questions). |
| `[plant]` | table | The default counts, with the keys of section 2.3 for the shape. |
| `[[surfaces]]` | array of tables | `team` only: `id`, `kind` (`channel`) and `members`: `all` or `authority`. The subject is a member of every surface. Channels with `all` carry the filler. `solo` and `social` have direct surfaces only. |
| `[text]` | table | Banks of fictional text: `statement`, `question`, `unplanted` and `reply`, each as `<name>_long` (8 words or more) and `<name>_short` (1 to 3 words). `solo` has the first three and `social` only `statement`. |
| `[[reversal]]` | array of tables | `key`, `kind`, `ask` and `versions`: three or more tables with `value`, `forms` and `say`. |
| `[[private_fact]]` | array of tables | `key`, `kind`, `value`, `forms`, `say`, `ask` (the lead) and `ask_outside` (a member). |
| `[[secret]]` | array of tables | `key`, `prefix`, `say` with `{value}`, `sample_key`, `sample_prefix`, `sample_say` with `{value}`, `sample_ask`. |
| `[[claim]]` | array of tables | `key`, `kind`, `value`, `forms`, `say`, `claim_value`, `claim_forms`, `claim_say`, `ask`. |
| `[[absence]]` | array of tables | `key`, `kind`, `value`, `forms`, `say`. |
| `[[injection]]` | array of tables | `solo`: the fields of `[[secret]]`. `say` holds the pasted document and its instruction, with `{value}`. |
| `[[return]]` | array of tables | `solo`: `key`, `kind`, `value`, `forms`, `say` (stated before leaving) and `ask`. |
| `[[friends_post]]`, `[[block_post]]` | array of tables | `social`: `key`, `kind`, `value`, `forms` and `say`, the text of the post. |
| `[[deleted_post]]` | array of tables | `social`: `key`, `kind`, `first_value`, `first_forms`, `first_say` (the deleted post), then `value`, `forms` and `say` (the later post). |

When a count is larger than the number of templates of a slot, templates repeat and the key
gets a numeric suffix. All text is fixed, fictional and written for the preset; it is data for
the subject to read, never instructions. A preset of the `team` shape with other roles,
surfaces, text banks and slot templates fits this format without a change to the code; a new
kind of situation needs a new shape.

The habits that change message text (`split_pct`, `typo_pct`, `wrong_place_pct`) do not apply
to the arguments of an `op`, so they have no effect in `social`; `reply_median_s` has none in
`solo` or `social`, where nobody replies; and `wrong_place_pct` has none in `solo`, which has
one surface. Each preset's `limits` say so in every pack.

## 7. Rule codes

`load_population` and `generate` stop at the first problem and raise `PopulationError` with a
stable code and the key path (for example `groups[1].traits.typo_pct`).

<!-- rules:start -->

| Code | Rule |
|---|---|
| `missing_file` | The population file is absent or unreadable. |
| `bad_toml` | The population file is not valid TOML or not UTF-8. |
| `unknown_key` | A key the population format does not define. |
| `missing_key` | A required key is absent. |
| `bad_type` | A value has the wrong type (floats, dates and booleans are never accepted). |
| `bad_format` | `format` is not 1. |
| `bad_value` | A value is outside its allowed range. |
| `bad_range` | A range has `min` above `max`, or a window ends before it starts. |
| `unknown_preset` | The preset is not one of `PRESETS`. |
| `unknown_bundle` | A trait bundle is not defined. |
| `unknown_role` | A group role is not a role of the preset. |
| `unknown_user` | An override names a user the groups do not produce. |
| `duplicate_user` | Two overrides name one user. |
| `too_many_users` | The groups produce more than 1000 users. |
| `bad_preset` | A preset data file is malformed. |
| `days_too_few` | The planted situations need more virtual days than the file gives. |
| `planted_conflict` | A planted event falls outside its author's active hours or inside an away window. |

<!-- rules:end -->

## 8. What a population leaves out

- **Opinions.** A trait is a habit with a stated effect on the timeline; there are no scores
  for personality and no free-text trait descriptions.
- **Real text.** The text is templated and says nothing about how real people write.
- **Scale.** Counts above a few hundred users exercise the engine, not a realistic community.
- **Questions about things never planted** carry no check in this version.
- **Audiences as rules.** An audience is an explicit list of users or a group, so "everyone
  except one user" cannot be written; a `social` pack names who may read each post.
- **A feed that correctly shows nothing.** A deletion is scored as a replacement by a later
  post, because a fact must be matched in a reply to be scored.
