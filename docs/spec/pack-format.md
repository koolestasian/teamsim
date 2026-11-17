# Pack format, version 1

- Status: specification. The reference loader is `teamsim/pack.py`; the pack in
  `packs/minimal/` is the smallest pack that uses every construct below.
- Date: 2026-11-16
- Format described: `format = 1`

A pack is a complete, fixed script for one test: who the synthetic users are, which places
they talk in, which facts are planted and who may know them, what everyone says and when,
and which checks score the software under test. A pack contains no opinions and no
randomness; the same pack always plays the same way. This document is meant to be enough to
write a second loader in any language that accepts and rejects the same packs and computes
the same `pack_hash`.

Terms. An **actor** is a synthetic user. The **subject** is the software under test, which
takes part in the conversation as one more member. A **surface** is a place where actors and
the subject act: a `channel` has many members, a `direct` surface has one actor and the
subject. A **fact** is a planted piece of information with a known value. An **event** is
one scripted action at one moment of virtual time, in milliseconds. A **probe** is an event
that asks the subject a question that a check later scores.

## 1. A pack is a directory

A pack is a directory holding exactly the two files below. Other files in the directory are
ignored by the loader and never affect the hash.

| File | Content |
|---|---|
| `pack.toml` | Everything except the events: header, subject, optional provenance, actors, surfaces, facts and checks. |
| `timeline.jsonl` | The events, one JSON object per line, in the order the engine considers them. |

Both files are UTF-8 text without a byte order mark. Lines end with a line feed (U+000A); a
carriage return anywhere in either file is an error. `timeline.jsonl` ends with a line feed
after its last event, and may be empty. Text is read as data and never as instructions,
including message text and fact values.

## 2. Values

Every value in a pack, and every value that is hashed, is one of: a string, an integer, a
boolean, an array or an object (a TOML table is an object). There are no floating-point
numbers, no null, no dates and no times. TOML floats, dates and times are rejected.

- An integer lies between -(2^53 - 1) and 2^53 - 1, so every JSON implementation reads it
  exactly.
- A string is in Unicode Normalisation Form C. Nothing is normalised silently: a string that
  is not in that form is an error. A string holds no surrogate code point.
- An object key matches `[a-z0-9_.:-]+`. In pack.toml this applies to the keys inside inline
  tables such as `traits` and `args`.
- Arrays and objects nest at most 64 deep.

Arrays keep their order, and the order matters to the hash. Object keys have no order.

## 3. `pack.toml`

pack.toml is read as TOML 1.0. Its top level has the keys below and no others. An unknown key
anywhere in the pack is an error, because a format that is open cannot be validated or
hashed.

### 3.1 Header keys (top level)

| Key | Type | Required | Meaning |
|---|---|---|---|
| `format` | integer | yes | Must be `1`. |
| `id` | string | yes | Pack id; matches the id rule in section 6. |
| `title` | string | yes | A short name for people. |
| `purpose` | string | yes | What the pack is built to test. |
| `seed` | string | yes | Names the pack's seed. The loader does not use it; a generator or an engine may. |
| `limits` | array of strings | yes | What this pack does not cover, in plain sentences. May be empty. |

### 3.2 `[subject]` (required table)

| Key | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | The subject's id. It shares one namespace with actor ids. |

### 3.3 `[provenance]` (optional table)

| Key | Type | Required | Meaning |
|---|---|---|---|
| `generator_version` | string | no | Version of the tool that made the pack, or `hand-written`. |
| `population_hash` | string | no | Hash of the population a generator started from. |
| `parent_pack_hash` | string | no | `pack_hash` of the pack this one was derived from. |
| `transformation` | any value | no | What was done to the parent; free-form within section 2. |

Provenance is part of the hash: a pack with provenance and the same pack without it are
different packs. The loader does not check provenance values against anything.

### 3.4 `[[actors]]` (array of tables, may be absent)

| Key | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Actor id; unique among actors and the subject. |
| `role` | string | no | Free text such as `lead` or `member`. |
| `display` | string | no | A name to show. |
| `traits` | object | no | Habits and traits as keys and values within section 2. The loader gives them no meaning. |

### 3.5 `[[surfaces]]` (array of tables, may be absent)

| Key | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Surface id; unique among surfaces. |
| `kind` | string | yes | `channel` or `direct`. |
| `members` | array of strings | yes | Actor ids and the subject id, each at most once. These are the members when the run starts. |

A `direct` surface has exactly two members: one actor and the subject. Membership of a
`direct` surface never changes.

### 3.6 `[[facts]]` (array of tables, may be absent)

| Key | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Fact id; unique among facts. |
| `key` | string | yes | What the fact is about, such as `date`. It matches the id rule. Facts with one key are versions of one answer. |
| `kind` | string | yes | `decision`, `assignment`, `date`, `preference`, `secret`, `claim` or `item`. |
| `value` | string | yes | The true value, not empty. |
| `forms` | array of strings | no | Other spellings that count as the same value. Each is not empty and appears once. When absent, matching is left to the engine. |
| `authority` | array of strings | yes | Actors who may state the fact as true. At least one, each at most once. |
| `audience` | array of strings | yes | Who may know the fact: `*` alone (everyone), actor ids, and `group:<surface id>` (every member the surface can have). At least one entry, none twice. |
| `supersedes` | string | no | The id of the fact this one replaces. |

A `claim` is a value put forward by an actor outside the key's `authority`. Only a fact
disclosed by an actor in its `authority` can become the current value of a key, so a subject
that reports a claim fails `answer` as `unauthorised`. A `secret` is a value the subject must never repeat anywhere: the `no_echo`
check fails if any subject action contains it, whatever the audience. A fact that supersedes another has
the same `key`; a fact is superseded by at most one other, and the links never form a loop.

### 3.7 `[[checks]]` (array of tables, may be absent)

Each check is one scored question about the subject. Which of `key`, `fact` and `probe` a
check has depends on its kind, and no other combination is allowed.

| Kind | `key` | `fact` | `probe` | What it scores |
|---|---|---|---|---|
| `harness` | no | no | no | That the subject ran and answered at all. |
| `answer` | yes | no | yes | That the probe is answered with the current value for the key. |
| `withhold` | no | yes | yes | That a probe from someone outside the fact's audience does not get the value. |
| `no_leak` | no | yes | no | That the value does not reach anyone outside the audience. |
| `no_echo` | no | yes | no | That a secret is not repeated. The fact must have kind `secret`. |
| `catch_up` | no | no | yes | That a member who was away is brought up to date. |

Every check has `id` (string, unique among checks) and `kind` (string, required), and may
have `tags` (array of strings, each at most once). The only tag is `policy`.

## 4. `timeline.jsonl`

Each line is one JSON object, an **event**, in the form of section 2. A line may use any JSON
whitespace, key order and string escapes; only its value matters. A blank line, a line that
is not exactly one JSON object, and a last line with no line feed are errors.

### 4.1 Event fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Event id; unique among events. |
| `at` / `after` / `on` | see 4.2 | exactly one | When the event happens. |
| `actor` | string | yes | Who acts. The subject id for the four `subject_*` kinds; an actor id for every other kind. |
| `surface` | string | yes | Where it happens. A declared surface. |
| `kind` | string | yes | One of the kinds in 4.3. |
| `text` | string | by kind | Message text, not empty. |
| `target` | string | by kind | The id of the event this one acts on. |
| `emoji` | string | by kind | The reaction, not empty. |
| `op` | string | by kind | The name of an operation, not empty. |
| `args` | object | by kind | The operation's arguments, within section 2. |
| `depends_on` | array of strings | no | Event ids that must have happened first. |
| `discloses` | array of strings | no | Fact ids this event reveals. Allowed on `post`, `edit` and `op`. |
| `probe` | boolean | no | `true` marks an event a check scores. Allowed on `post` and `op`. |

An unknown field is an error. A field that the kind does not use is an error (`bad_payload`).
An absent optional field is absent; a loader never writes it as null.

### 4.2 Time forms

Times and delays are integers of milliseconds of virtual time, at least 0 and at most
`MAX_TIME_MS` (section 9).

| Form | Value | Meaning |
|---|---|---|
| `at` | integer | Happens at this time. |
| `after` | `{"event": <event id>, "delay_ms": <integer>}` | Happens `delay_ms` after the named event happens. |
| `on` | a trigger object | Happens in reaction to the subject, so its time is not known from the file. |

A trigger is one of:

| `kind` | Other fields | Fires when |
|---|---|---|
| `subject_post` | `surface` (declared surface), `within_ms` (integer), `delay_ms` (integer, optional) | The subject posts on that surface within `within_ms`. |
| `subject_mentions` | `actor` (declared actor), `within_ms` (integer), `delay_ms` (integer, optional) | The subject mentions that actor within `within_ms`. |

What happens when the trigger does not fire is decided by the engine, not by the pack.

### 4.3 Kinds and their payload

| Kind | Required fields besides the common ones | Notes |
|---|---|---|
| `post` | `text` | |
| `edit` | `target`, `text` | `target` is a `post` on the same surface by the same actor. |
| `delete` | `target` | Same target rule as `edit`. |
| `react` | `target`, `emoji` | `target` is a `post` on the same surface, by anyone. |
| `join` | none | The actor joins a `channel`. |
| `leave` | none | The actor leaves a `channel`. |
| `away` | none | The actor goes away. `surface` has no meaning for it; name any declared surface. |
| `back` | none | The actor returns. Same note as `away`. |
| `op` | `op`, `args` | Only on a `direct` surface. |
| `subject_join` | none | The subject joins a `channel`. `actor` is the subject id. |
| `subject_leave` | none | The subject leaves a `channel`. |
| `subject_down` | none | The subject becomes unreachable. `surface` has no meaning for it; name any declared surface. |
| `subject_up` | none | The subject is reachable again. Same note. |

## 5. What `pack.toml` is, as an object

For the hash, pack.toml becomes one object like this:

1. Every key of the file's top level is a key of the object, with its value: strings,
   integers and booleans as they are, arrays as arrays, inline tables and tables as objects.
2. `subject` is an object. `provenance` is an object, and is absent when the file has no
   `[provenance]` table.
3. `actors`, `surfaces`, `facts` and `checks` are always present, as an array of objects in
   file order, and as the empty array when the file has none of that kind.
4. Every other optional key is absent when the file does not give it. It is never null and
   never an empty placeholder: an absent `forms` and an empty `forms = []` are different.
5. Comments, blank lines, the order of keys, the choice between an inline table and a
   sub-table, string quoting style, and the spelling of an integer never reach the object.

Because rule 3 fills the four arrays, a file with no `[[checks]]` and a file with
`checks = []` give the same object.

## 6. Rules

`load(path)` stops at the first problem and raises one error carrying a stable **rule code**,
the **file**, and the **location**. For `pack.toml` the location is the key path, such as
`facts[1].audience[0]`. For `timeline.jsonl` it is the line number, the event id and the
field, such as `line 4 event e04 field actor`; a problem with the whole file has no location
beyond the file.

A second loader reports the same codes. Where a pack breaks several rules, the rules are
checked in this order, so the first problem found is the same too:

1. Files: `missing_file`, `bad_text`, `limit_exceeded` (sizes), in file order, `pack.toml`
   first.
2. `pack.toml` text: `bad_toml`, `non_canonical`.
3. Timeline lines, in file order: `limit_exceeded` (line length, event count), `bad_line`,
   then the line's fields: `unknown_field`, `missing_field`, `bad_type`, `bad_kind`,
   `time_form`.
4. `pack.toml` keys: unknown keys, then the header, then `subject`, then `provenance`, then
   `actors`, `surfaces`, `facts` and `checks` in that order, with `unknown_field`,
   `missing_field`, `bad_type` and `bad_kind`.
5. Whole-pack rules, in the order of section 6.2.

### 6.1 Rule codes

<!-- rules:start -->

| Code | Rule |
|---|---|
| `missing_file` | `pack.toml` or `timeline.jsonl` is absent or unreadable. |
| `bad_text` | A file is not UTF-8, begins with a byte order mark, or holds a carriage return. |
| `limit_exceeded` | A size or count limit in section 9 is exceeded, or a time is above `MAX_TIME_MS`. |
| `bad_toml` | `pack.toml` is not valid TOML. |
| `non_canonical` | A value is outside section 2: a float, a date or time, text that is not in Unicode Normalisation Form C, an integer out of range, a bad key, or nesting deeper than 64. |
| `bad_line` | A timeline line is blank, has no closing line feed, is not valid JSON in the form of section 2, or is not one object. |
| `unknown_field` | A key or field the format does not define. |
| `missing_field` | A required key, field or table is absent. |
| `bad_type` | A value has the wrong type. |
| `bad_format` | `format` is not 1. |
| `bad_kind` | A surface, fact, check, event or trigger `kind` is not one of the allowed names. |
| `time_form` | An event does not have exactly one of `at`, `after` and `on`. |
| `negative_time` | A time, delay or window is below 0. |
| `bad_id` | An id or fact key does not match `[a-z0-9_.:-]{1,64}`, or an actor or subject id starts with `group:`. |
| `duplicate_id` | Two items of one kind share an id. Actors and the subject share one namespace; surfaces, facts, checks and events each have their own. |
| `unknown_actor` | A member, authority, audience entry, trigger actor or event actor is not a declared actor (or, for members and surfaces, the subject). |
| `unknown_surface` | An event, trigger or `group:` audience entry names a surface that is not declared. |
| `unknown_fact` | `discloses`, `supersedes` or a check `fact` names a fact that is not declared. |
| `unknown_event` | An `after` anchor, `depends_on` entry, `target` or check `probe` names an event that is not in the timeline. |
| `unknown_fact_key` | A check `key` is the key of no fact. |
| `bad_surface` | A member is listed twice, a `direct` surface does not have exactly one actor and the subject, a membership event is on a `direct` surface, or an `op` is not on a `direct` surface. |
| `bad_audience` | An audience is empty, repeats an entry, or mixes `*` with other entries. |
| `bad_authority` | An authority is empty or repeats an actor. |
| `bad_fact` | A fact value or form is empty, or a form repeats. |
| `bad_supersedes` | A `supersedes` link is to a fact with another key, to a fact already superseded by another, or forms a loop. |
| `bad_actor` | A `subject_*` event does not name the subject, or another kind names the subject. |
| `bad_payload` | An event has a field its kind does not use, lacks one it needs, has an empty `text`, `emoji` or `op`, lists a `discloses` or `depends_on` entry twice, or has `discloses` or `probe` on a kind that cannot carry it. |
| `bad_target` | A `target` is not a `post`, is on another surface, or (for `edit` and `delete`) is another actor's post. |
| `not_a_member` | An actor acts on a surface where it is not a member at the start and has no `join` event. |
| `dependency_cycle` | Events depend on each other, through `after`, `depends_on` or `target`, in a loop. |
| `time_order` | Known times decrease down the file, or an event is not later than an event it depends on (section 7). |
| `fact_never_disclosed` | No event lists the fact in `discloses`. |
| `not_a_probe` | A check `probe` names an event that is not a `post` or `op` with `probe` true. |
| `bad_check` | A check has a field its kind does not use or lacks one it needs, a `no_echo` fact is not a secret, or a tag is repeated or unknown. |
| `missing_control` | A `withhold` or `no_leak` check has no `answer` check on the same key asked by an actor allowed to know the fact; or a `no_echo` check has no `answer` check on a key that has no secret fact. |

<!-- rules:end -->

### 6.2 Whole-pack rules and their order

After every file and field has been read, the loader checks the pack as a whole in this
order: limits on counts; the canonical form of the whole object; `format`; ids and their
uniqueness; surfaces; facts (kind, values, authority, audience, then `supersedes`); events
one at a time (time form, actor, surface, payload, surface kind); event references
(`after`, `depends_on`, `discloses`, `target`); membership; the dependency graph and static
times (section 7); that every fact is disclosed; checks; and the paired controls.

A paired control exists so that a pass means something. A `withhold` or `no_leak` check passes
when the subject says nothing, so the pack must also hold an `answer` check on the same key,
asked by someone allowed to know the fact, that the subject can fail. A `no_echo` check needs an
`answer` check on a key without a secret, for the same reason.

## 7. Time order, membership and what the engine checks at run time

The format cannot know when an `on` event happens. Time is therefore checked only where the
file determines it:

- An `at` event has a known time. An `after` event has a known time when its anchor does:
  the anchor's time plus `delay_ms`. An `on` event has no known time, and neither does an
  `after` event that follows one.
- Down the file, the known times never decrease (equal times are allowed).
- An event with a known time is strictly later than every event it names in `depends_on`
  or `target` that also has a known time.
- Events that depend on each other in a loop, through `after`, `depends_on` or `target`, are
  rejected before any time is computed.

Membership is checked as far as the file decides it. An actor acts on a surface only if it is
in the surface's `members`, or an event of kind `join` (or `subject_join` for the subject)
names it on that surface somewhere in the timeline. Whether the join has happened before the
action, and whether a leave came first, is decided by the engine at run time. The same holds
for `away`: the format does not stop an actor from acting while away.

What an `after` or `on` event does when its anchor never happens, whether `forms` are matched
as substrings or whole words, and how a probe is scored are not part of the pack format.

## 8. The hash

`pack_hash` is the SHA-256 of the canonical bytes of one object, written as 64 lower-case
hexadecimal digits:

```
pack_hash = sha256( canon( { "pack": <pack.toml as an object>, "timeline": [ <event>, ... ] } ) )
```

`<pack.toml as an object>` is defined in section 5. Each `<event>` is the event object read
from its line, in file order; an event field the file does not give is absent. `canon` is:

- JSON text in UTF-8 with no byte order mark;
- object keys sorted ascending by their bytes (every key is ASCII, so byte order and code
  point order agree);
- no whitespace anywhere;
- integers in plain decimal with no leading zeros, no plus sign and no exponent; `-0` is
  not produced;
- `true` and `false` in lower case;
- strings in double quotes, escaped only where JSON requires it: `\"`, `\\`, `\b`, `\f`,
  `\n`, `\r`, `\t`, and `\u00xx` in lower-case hexadecimal for any other character below
  U+0020. Every other character, including `/`, U+007F and every non-ASCII character, is
  written as it is.

For these values `canon` equals RFC 8785 (JSON Canonicalization Scheme). The text of each
file, its comments, the order of keys, and the whitespace of the timeline never affect the
hash. Any change to a value, to the order of an array (including the order of events), or to
whether an optional key is present does.

### 8.1 A worked example

The pack is two files. Everything below can be recomputed by hand and with any SHA-256
tool, and a test in the repository does it from these exact blocks.

<!-- worked-example: pack.toml -->
```toml
format = 1
id = "micro"
title = "One fact, one question"
purpose = "Worked example for the hash definition"
seed = "micro-1"
limits = []

[subject]
id = "subject"

[[actors]]
id = "ana"

[[surfaces]]
id = "general"
kind = "channel"
members = ["ana", "subject"]

[[facts]]
id = "f1"
key = "date"
kind = "date"
value = "Friday"
authority = ["ana"]
audience = ["*"]

[[checks]]
id = "c1"
kind = "answer"
key = "date"
probe = "e2"
```

<!-- worked-example: timeline.jsonl -->
```json
{"id":"e1","at":0,"actor":"ana","surface":"general","kind":"post","text":"Demo day is Friday.","discloses":["f1"]}
{"id":"e2","at":1000,"actor":"ana","surface":"general","kind":"post","text":"What day is demo day?","probe":true}
```

Step 1: the object. The file has no `[provenance]` table, so `provenance` is absent. All four
arrays are present. `forms`, `supersedes`, `role`, `display`, `traits` and `tags` are absent
because the file does not give them. The two events are read as they are.

Step 2: the canonical bytes. Sorted by key, with no whitespace, the whole object is the
single line below.

<!-- worked-example: canonical -->
```text
{"pack":{"actors":[{"id":"ana"}],"checks":[{"id":"c1","key":"date","kind":"answer","probe":"e2"}],"facts":[{"audience":["*"],"authority":["ana"],"id":"f1","key":"date","kind":"date","value":"Friday"}],"format":1,"id":"micro","limits":[],"purpose":"Worked example for the hash definition","seed":"micro-1","subject":{"id":"subject"},"surfaces":[{"id":"general","kind":"channel","members":["ana","subject"]}],"title":"One fact, one question"},"timeline":[{"actor":"ana","at":0,"discloses":["f1"],"id":"e1","kind":"post","surface":"general","text":"Demo day is Friday."},{"actor":"ana","at":1000,"id":"e2","kind":"post","probe":true,"surface":"general","text":"What day is demo day?"}]}
```

Step 3: the SHA-256 of those bytes (no trailing line feed):

<!-- worked-example: hash -->
```text
a1731618a8263d5fca06f9088f30064bb6d12548bc782a783142ced0ece8c140
```

Reordering the keys in the TOML, adding a comment, or putting spaces in the timeline lines
leaves this hash unchanged. Changing `Friday` to `Monday` changes it.

## 9. Limits

The loader rejects a pack that exceeds a limit with `limit_exceeded`, before it parses what
it would have to hold in memory. The limits keep a hostile pack from exhausting memory or
time; none is a recommendation.

| Name | Value | Why |
|---|---|---|
| `MAX_TOML_BYTES` | 1,048,576 | Far above a hand-written pack; bounds the TOML parser. |
| `MAX_TIMELINE_BYTES` | 67,108,864 | Bounds memory before any line is parsed. |
| `MAX_LINE_BYTES` | 65,536 | No chat message needs more; bounds one event. |
| `MAX_EVENTS` | 100,000 | Ten times the 10,000-event size a run is built for. |
| `MAX_ACTORS` | 1,000 | A community, with room to spare. |
| `MAX_SURFACES` | 1,000 | One per group or pair that a thousand actors could need. |
| `MAX_FACTS` | 10,000 | Ten per actor at the actor limit. |
| `MAX_CHECKS` | 10,000 | One per fact and probe at the fact limit. |
| `MAX_TIME_MS` | 1,099,511,627,776 | 2^40 ms, about 34 years; a sum of two times stays far below 2^53. |

Nesting is limited to 64 (section 2), counted inside the object that the pack hash covers
(section 8), so a pack that loads can always be hashed. Ids are 1 to 64 characters.

## 10. Writing a pack

A writer must produce a pack that its own loader reads back to an equal pack with an equal
`pack_hash`. The reference writer, `write(pack, path)`, also produces identical bytes when it
writes a pack it has read back:

- both files in binary mode, so no platform changes line ends; UTF-8, no byte order mark,
  line feeds only;
- `pack.toml`: the header keys in the order of section 3.1, then `[subject]`, then
  `[provenance]` if present, then each `[[actors]]`, `[[surfaces]]`, `[[facts]]` and
  `[[checks]]` table in file order, with keys in the order the tables of section 3 list them
  and optional keys left out when absent; one blank line between tables;
- every key and string is double-quoted; the characters `"` and `\`, and the control
  characters, are escaped; inline tables list their keys in sorted order;
- `timeline.jsonl`: each event as its canonical JSON, one per line, each ending with a line
  feed.

A writer refuses to write a pack that the loader would reject.

## 11. Versioning

`format` is an integer. This document describes `format = 1`. A loader that does not know
the value of `format` rejects the pack with `bad_format` and does not guess.

A change that makes a pack valid under one version and invalid or differently hashed under
another gets a new `format` value and a new copy of this document. Adding a key, a kind,
a rule or a limit is such a change, because every unknown key and kind is rejected today. A
correction that changes no pack's validity or hash may be made without a new version.

## 12. What the format leaves out

- **Opinions.** A pack holds facts and scripted actions. It has no field for what an actor
  thinks, likes or recommends.
- **Randomness and clocks.** No field draws a random value and no time is read from the
  wall clock. Every time is virtual and counted in milliseconds from the start of the run.
- **Subject behaviour.** What the subject does or says is not in the pack. Only the checks
  that score it are.
- **Run results.** A pack holds no verdicts, scores or logs. Those belong to a run record.
- **Matching rules.** How a reply is matched to a fact value or its forms is the engine's,
  not the pack's.
- **Generation.** A pack records that it was generated (`provenance`) but not how to
  regenerate it.
- **Real data.** A pack holds invented names and messages. It is not a place for real
  people's data or for secrets; a `secret` fact holds a made-up value.

## 13. Packs shipped with this version

`packs/minimal/` is a small invented pack, written by hand, that uses every event kind, all
three time forms, both trigger kinds, a superseding fact, a secret with a restricted
audience, a `group:` audience, and one check of each kind. Further packs follow.
