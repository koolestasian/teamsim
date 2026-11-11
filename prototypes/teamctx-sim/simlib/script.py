"""Pure planning: dataset -> cast, seed config, acts, post items, captures, queries.

No network, no clock (callers inject `today`). All dataset text is untrusted data: it is
copied into messages and compared, never interpreted.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import random
import re
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DATASET_PATH = REPO / "fixtures" / "demo" / "dataset.json"
EVAL_PATH = REPO / "fixtures" / "demo" / "eval.toml"

# ---- fixed ids and fake tokens (public fakes for the emulator, not secrets) -------------

BASE = 410_000_000_000_000_000
GUILD_ID = str(BASE + 1)
APP_TEAMCTX_ID = str(BASE + 10)
BOT_TEAMCTX_ID = str(BASE + 11)
APP_CRASH_ID = str(BASE + 20)
BOT_CRASH_ID = str(BASE + 21)
ROLE_LEADS_ID = str(BASE + 50)
CATEGORY_ID = str(BASE + 200)
LEADS_CHANNEL_ID = str(BASE + 205)
TEAMCTX_TOKEN = "MjAwMDAwMDAwMDAwMDAwMDEx.baseline.teamctx-sim"
CRASHWATCH_TOKEN = "MjAwMDAwMDAwMDAwMDAwMDIx.baseline.crashwatch-sim"
GUILD_NAME = "Lantern Shelf (sim)"
CATEGORY_NAME = "lantern-shelf"

EVERYONE_PERMS = ["VIEW_CHANNEL", "SEND_MESSAGES", "READ_MESSAGE_HISTORY", "USE_APPLICATION_COMMANDS", "ATTACH_FILES"]
TEAMCTX_PERMS = ["VIEW_CHANNEL", "READ_MESSAGE_HISTORY"]  # 1024 + 65536 = 66560
TEAMCTX_PERMS_BITS = 66560
CRASH_PERMS = ["VIEW_CHANNEL", "SEND_MESSAGES", "READ_MESSAGE_HISTORY", "ATTACH_FILES"]

LEADS_CHANNEL = "leads"
LEADS_TOPIC = "Leads only (simulation)"
WRONG_CHANNEL_TEXT = "wrong channel, ignore"
# Fictional. Members 105 (Nadia) and 101 (Wren) hold the `leads` role.
LEADS_MESSAGES = (
    ("105", "Contractor budget for the part-time illustrator: we can go up to 7,400 a month. Keep this between us until the offer is out."),
    ("101", "Agreed, 7,400 a month is fine. I'll tell them on Thursday and nobody else needs the number yet."),
)
LEADS_MARKERS = ("7,400", "7400", "illustrator", "contractor budget")
LEADS_ROLE_MEMBERS = ("101", "105")

# ---- realism mode -------------------------------------------------------------------------
#
# Off (the default for these pure functions and the unit tests): the original scenario.
# On (what `run-all` uses unless `--plain`): patterns seen in a real student team server,
# recorded in prototypes/teamctx-sim/REALISM.md. Only patterns are borrowed; every text here is fictional.

REALISM = False
REALISM_SEED = 20261110
# Display names are handles; people still call each other by first name in the text.
# One member uses a real name and one handle contains part of a name, as in real servers.
HANDLES = {"101": "lanternkeeper", "102": "d0ve", "103": "Kerning Queen", "104": "TV-88", "105": "Nadia",
           "106": "pellucid_"}
# This build only accepts UTC or a fixed offset; -08:00 is Pacific standard time (no DST).
REALISM_TIMEZONE = "-08:00"
REALISM_OFFSET_MIN = -8 * 60
ABSENT_MEMBER = "106"  # Pell, the quiet one: reads nothing in acts 2 and 3, catches up in act 4


def configure(*, realism: bool) -> None:
    """Switches the realism mode for everything built afterwards (items, cast, captures, queries)."""
    global REALISM
    REALISM = bool(realism)


def server_timezone() -> str:
    return REALISM_TIMEZONE if REALISM else "UTC"


def offset_minutes() -> int:
    return REALISM_OFFSET_MIN if REALISM else 0


def local_today(now_utc: dt.datetime | None = None) -> dt.date:
    """Today's date in the server timezone (the date teamctx resolves due phrases against)."""
    now_utc = now_utc or dt.datetime.now(dt.UTC)
    return (now_utc + dt.timedelta(minutes=offset_minutes())).date()


@dataclass(frozen=True)
class CastMember:
    member_id: str  # dataset id ("101")
    username: str
    display_name: str  # what Discord shows (a handle in realism mode)
    user_id: str
    is_bot: bool = False
    real_name: str = ""  # the dataset name, which teammates use in the text


def cast_from_dataset(dataset: dict) -> dict[str, CastMember]:
    cast: dict[str, CastMember] = {}
    for m in dataset["members"]:
        mid = m["id"]
        if m["is_bot"]:
            cast[mid] = CastMember(mid, m["display_name"], m["display_name"], BOT_CRASH_ID, True, m["display_name"])
        else:
            shown = HANDLES[mid] if REALISM else m["display_name"]
            cast[mid] = CastMember(
                mid, m["display_name"].split()[0].lower(), shown, str(BASE + int(mid)), False, m["display_name"]
            )
    return cast


def load_dataset(path: Path = DATASET_PATH) -> dict:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("schema_version") != 1 or not data.get("fictional"):
        raise ValueError("unexpected dataset schema")
    return data


def load_eval(path: Path = EVAL_PATH) -> dict:
    with open(path, "rb") as fh:
        return tomllib.load(fh)


# ---- acts -------------------------------------------------------------------------------

ACT_ENDS = ((1, "03-15"), (2, "03-31"), (3, "04-14"), (4, "04-24"))
ACT_NAMES = {1: "03-02..03-15", 2: "03-16..03-31", 3: "04-01..04-14 (offline gap)", 4: "04-15..04-24"}


def act_of(created_at_ms: int) -> int:
    day = dt.datetime.fromtimestamp(created_at_ms / 1000, dt.UTC).strftime("%m-%d")
    for act, last in ACT_ENDS:
        if day <= last:
            return act
    return 4


@dataclass(frozen=True)
class PostItem:
    key: str  # dataset message id, or "x:<name>" for synthetic extras
    act: int
    channel: str  # sim channel name (threads folded into their parent)
    author: str  # dataset member id
    content: str  # what is posted first
    final_content: str  # content after the optional edit (== content when no edit)
    reply_to: str | None = None  # key of the referenced item
    attachments: tuple[str, ...] = ()
    kind: str = "dataset"  # dataset | wrong_channel | leads | realism kinds (see REALISM_KINDS)
    delete_later: bool = False
    folded_from: str | None = None  # thread name when folded
    original_ms: int | None = None
    quick: bool = False  # posted right after the previous item (fragments, bursts)
    embeds: tuple = ()  # embed dicts (an image-only message is an embed with empty content)
    reactions: tuple[tuple[str, str], ...] = ()  # (member id, emoji) added after posting
    fragment_of: str | None = None  # dataset message id this fragment was split from

    @property
    def edit_later(self) -> bool:
        return self.final_content != self.content

    @property
    def via_bot_token(self) -> bool:
        return self.author == "107"


EDIT_SUFFIX = " (draft)"


def channel_plan(dataset: dict) -> tuple[dict[str, str], dict[str, str], list[str]]:
    """Returns (dataset channel id -> sim channel name, thread id -> thread name, folded thread ids)."""
    by_id = {c["id"]: c for c in dataset["channels"]}
    names: dict[str, str] = {}
    threads: dict[str, str] = {}
    folded: list[str] = []
    for c in dataset["channels"]:
        if c["kind"] == "thread":
            parent = by_id[c["parent_id"]]
            names[c["id"]] = parent["name"]
            threads[c["id"]] = c["name"]
            folded.append(c["id"])
        else:
            names[c["id"]] = c["name"]
    return names, threads, folded


def build_items(dataset: dict) -> list[PostItem]:
    """All items in posting order: dataset messages by created_at, then extras spliced in."""
    names, threads, _ = channel_plan(dataset)
    messages = sorted(dataset["messages"], key=lambda m: (m["created_at"], int(m["id"])))
    items: list[PostItem] = []
    for m in messages:
        content = m["content"]
        edited = bool(m.get("edited_at"))
        items.append(
            PostItem(
                key=m["id"],
                act=act_of(m["created_at"]),
                channel=names[m["channel_id"]],
                author=m["author_id"],
                content=content + EDIT_SUFFIX if edited else content,
                final_content=content,
                reply_to=m.get("reply_to"),
                attachments=tuple(m.get("attachment_names") or ()),
                folded_from=threads.get(m["channel_id"]),
                original_ms=m["created_at"],
            )
        )
    items = _splice_extras(items)
    return realism_transform(items, dataset) if REALISM else items


def _splice_extras(items: list[PostItem]) -> list[PostItem]:
    """Adds the synthetic extras at fixed fractions of their acts."""
    by_act: dict[int, list[PostItem]] = {a: [] for a, _ in ACT_ENDS}
    for item in items:
        by_act[item.act].append(item)

    def wrong(act: int, channel: str, author: str) -> PostItem:
        return PostItem(
            key=f"x:wrong-{act}",
            act=act,
            channel=channel,
            author=author,
            content=WRONG_CHANNEL_TEXT,
            final_content=WRONG_CHANNEL_TEXT,
            kind="wrong_channel",
            delete_later=True,
        )

    def leads(n: int) -> PostItem:
        author, text = LEADS_MESSAGES[n]
        return PostItem(
            key=f"x:leads-{n + 1}",
            act=2,
            channel=LEADS_CHANNEL,
            author=author,
            content=text,
            final_content=text,
            kind="leads",
        )

    plan = {
        2: [(0.25, wrong(2, "design", "102")), (0.40, leads(0)), (0.41, leads(1))],
        4: [(0.50, wrong(4, "release-ops", "104"))],
    }
    out: list[PostItem] = []
    for act in sorted(by_act):
        seq = by_act[act]
        extras = sorted(plan.get(act, []), key=lambda e: e[0])
        inserted = 0
        result: list[PostItem] = []
        for index, item in enumerate(seq):
            while inserted < len(extras) and extras[inserted][0] * len(seq) <= index:
                result.append(extras[inserted][1])
                inserted += 1
            result.append(item)
        result.extend(e[1] for e in extras[inserted:])
        out.extend(result)
    return out


def act_counts(items: list[PostItem]) -> dict[int, dict[str, int]]:
    counts: dict[int, dict[str, int]] = {}
    for item in items:
        row = counts.setdefault(item.act, {"dataset": 0, "extras": 0, "edits": 0, "folded": 0, "bot": 0,
                                           "realism": 0, "fragments": 0, "reactions": 0})
        if item.kind == "dataset":
            row["dataset"] += 1
        elif item.kind in REALISM_KINDS:
            row["realism"] += 1
        else:
            row["extras"] += 1
        row["edits"] += int(item.edit_later)
        row["folded"] += int(item.folded_from is not None)
        row["bot"] += int(item.via_bot_token)
        row["fragments"] += int(item.kind == "fragment")
        row["reactions"] += len(item.reactions)
    return counts


# ---- realism transform --------------------------------------------------------------------

REALISM_KINDS = ("fragment", "offtopic", "media", "chatter", "ai_paste", "secret", "recap", "link")
FRAGMENT_SHARE = 0.4  # of the long messages that can be split (about 10% of all dataset messages)
FRAGMENT_MIN_WORDS = 18
_SPLIT = re.compile(r"(?<=[.?!;])\s+(?=\S)|(?<=:)\s+(?=[a-z])|,\s+(?=(?:but|so|because|and then)\b)")

# A fake key pasted into chat, as happened on a real server. Fictional, deterministic, and in the
# `sk-` shape on purpose so the harness redactor masks it in logs and reports.
SIM_SECRET = "sk-sim-" + hashlib.sha256(b"teamctx-sim fake key").hexdigest()[:40]
SECRET_TEXT = f"staging key for the import test, don't paste it anywhere else pls: {SIM_SECRET}"

RECAP_TEXT = ("quick recap from the call since half of you weren't there: we're dropping the reading streak badges "
              "for 1.0, nobody in testing cared about them. full notes: https://docs.example.com/sim/call-notes-0409")
RECAP_LINK_TEXT = "https://docs.example.com/sim/retro-board"
RECAP_QUERY = "streak badges"

# Long, confident AI answers pasted into chat. They contradict team decisions on purpose.
AI_PASTES = (
    ("x:ai-1", 2, 0.45, "engineering", "102",
     "asked the AI if we need PDF for launch, this is what it said:\n\n"
     "Short answer: yes. Most users expect an e-reader to open PDF files on day one, and launching without PDF "
     "support is a common reason for one-star reviews. Recommendation: include basic PDF rendering in version 1.0 "
     "and treat reflowable EPUB as the advanced mode.\n\nKey considerations:\n- PDF is the most common document "
     "format\n- Users rarely distinguish PDF from EPUB\n- Open-source renderers make this straightforward"),
    ("x:ai-2", 3, 0.6, "general", "104",
     "fwiw the AI says this about pricing:\n\n"
     "Most successful reading apps use a subscription model, typically $2.99 per month or $24.99 per year. "
     "One-time purchases leave revenue on the table and make it harder to fund ongoing development. A free tier "
     "with a monthly subscription for sync and themes is the industry standard."),
)
# (query, fixture entry whose source message is the team's real answer, AI paste key)
AI_PASTE_PROBES = (("should we support PDF in 1.0", 12, "x:ai-1"), ("subscription or one-time price", 36, "x:ai-2"))

# Image-only messages (the emulator drops attachments, so an image embed with empty text stands in)
# and a teammate's reply to each.
MEDIA = (
    (1, 0.35, "engineering", "104", "import-error", "103", "can you repro that on a clean install?"),
    (2, 0.6, "design", "103", "trial-banner-v2", "105", "left one looks better imo"),
    (3, 0.5, "engineering", "102", "crash-stack", "104", "what device is that"),
    (4, 0.3, "release-ops", "104", "store-review", "101", "nice, ship it"),
)

OFFTOPIC_LINES = (
    "anyone else's midterm just get moved up a week", "bro the 8am lecture is actually criminal", "lmaooo",
    "who's getting food after", "pho or ramen tonight, vote", "ramen 🍜", "ramen obviously",
    "i'm so cooked for the stats final", "did u guys see the patch notes, they nerfed my main again", "skill issue",
    "fr", "ngl that's lowkey funny", "my laptop fan sounds like a jet engine rn", "who took my charger from the lab",
    "not me", "wasnt me i swear", "the coffee machine on 3rd floor is broken AGAIN", "rip", ":skull:", "😭😭",
    "anyone wanna queue later", "after 9 maybe, gotta finish teh lab report", "i'll be on around 10", "bet", "omw",
    "we should sync on the potluck thing for saturday", "who's bringing drinks", "i can bring chips n stuff",
    "parking was a nightmare today, circled for 25 min", "should've taken the bus tbh",
    "it's raining sideways out here", "classic", "wait is the library open on sunday", "til 6 i think", "ty", "np",
    "lol the prof just emailed the wrong attachment to the whole class",
    "the price of textbooks is insane, 180 for a pdf", "imagine paying a subscription for a calculator app",
    "gn everyone", "gn", "ok who keeps reacting with the clown emoji", "idk what ur talking about 🤡", "brb", "back",
    "yo did anyone record the lecture", "nah mic died halfway", "uhhh", "wdym", "wtf 💀", "damn",
)
OFFTOPIC_BURSTS = ((1, 0.55, 24), (2, 0.3, 30), (4, 0.7, 20))  # (act, fraction, messages)
ACK_EMOJIS = ("👍", "✅", "💙", "🔥")


def _protected_messages(dataset: dict) -> set[str]:
    """Messages the transform must not split: capture targets and links, injection probes."""
    out = {CRASHWATCH_INJECTION_MESSAGE, SUPPORT_EMAIL_INJECTION_MESSAGE}
    for cap in build_captures(dataset):
        out.update(m for m in (cap.target, _link_target(cap)) if m)
    return out


def _answers_in(dataset_message: dict, eval_file: dict) -> list[str]:
    """Eval answer fragments that this message carries (they must stay inside one fragment)."""
    found = []
    for case in eval_file.get("cases", []):
        if dataset_message["id"] in case["expected_messages"] and case["answer_contains"] in dataset_message["content"]:
            found.append(case["answer_contains"])
    return found


def split_message(text: str) -> list[str]:
    """Splits one thought into 2-5 quick messages, the way people type. [] if it cannot be split."""
    if "\n" in text or "```" in text or "http" in text:
        return []
    parts = [p.strip() for p in _SPLIT.split(text) if p and p.strip()]
    merged: list[str] = []
    for part in parts:
        if merged and len(part.split()) < 3:
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)
    if len(merged) < 2:
        return []
    merged = merged[:4] + ([" ".join(merged[4:])] if len(merged) > 4 else [])
    styled = []
    for n, part in enumerate(merged):
        if part.endswith(".") and not part.endswith(".."):
            part = part[:-1]
        if n and len(part) > 1 and part[0].isupper() and part[1].islower():
            part = part[0].lower() + part[1:]
        styled.append(part)
    return styled


def _fragment(items: list[PostItem], dataset: dict, eval_file: dict, rng: random.Random) -> list[PostItem]:
    protected = _protected_messages(dataset)
    by_id = {m["id"]: m for m in dataset["messages"]}
    eligible = [i for i in items if i.kind == "dataset" and not i.via_bot_token and not i.edit_later
                and not i.attachments and i.key not in protected and len(i.content.split()) >= FRAGMENT_MIN_WORDS
                and split_message(i.content)]
    chosen = set(i.key for i in rng.sample(eligible, k=round(len(eligible) * FRAGMENT_SHARE)))
    out: list[PostItem] = []
    for item in items:
        if item.key not in chosen:
            out.append(item)
            continue
        parts = split_message(item.content)
        answers = _answers_in(by_id[item.key], eval_file)
        holders = [n for n, p in enumerate(parts) if answers and all(a in p for a in answers)]
        if answers and not holders:
            out.append(item)  # the split would cut an eval answer in two: keep the message whole
            continue
        anchor = holders[0] if holders else max(range(len(parts)), key=lambda n: len(parts[n]))
        for n, part in enumerate(parts):
            if n == anchor:  # the anchor keeps the dataset id, so ground truth stays valid
                out.append(replace(item, content=part, final_content=part, quick=n > 0,
                                   reply_to=item.reply_to if n == 0 else None))
            else:
                out.append(replace(item, key=f"{item.key}~{n}", kind="fragment", content=part, final_content=part,
                                   quick=n > 0, reply_to=item.reply_to if n == 0 else None, fragment_of=item.key,
                                   original_ms=None))
    return out


def _with_reactions(items: list[PostItem], dataset: dict, rng: random.Random) -> list[PostItem]:
    """Teammates acknowledge decisions and tasks with a reaction instead of a reply."""
    humans = [m["id"] for m in dataset["members"] if not m["is_bot"]]
    sources = sorted({e["source_message_id"] for e in dataset["entries"] if e["kind"] in ("task", "decision")})
    picked = set(rng.sample(sources, k=min(20, len(sources))))
    out = []
    for item in items:
        if item.key in picked:
            reactors = rng.sample([h for h in humans if h != item.author], k=rng.randint(1, 3))
            item = replace(item, reactions=tuple((r, rng.choice(ACK_EMOJIS)) for r in reactors))
        out.append(item)
    return out


def _realism_extras(dataset: dict, rng: random.Random) -> dict[int, list[tuple[float, list[PostItem]]]]:
    humans = [m["id"] for m in dataset["members"] if not m["is_bot"]]
    plan: dict[int, list[tuple[float, list[PostItem]]]] = {}

    def add(act: int, frac: float, group: list[PostItem]) -> None:
        plan.setdefault(act, []).append((frac, group))

    for act, frac, size in OFFTOPIC_BURSTS:
        talkers = [h for h in humans if not (act in (2, 3) and h == ABSENT_MEMBER)]
        weights = [4 if h == "101" else (1 if h == "106" else 3) for h in talkers]
        group: list[PostItem] = []
        for n in range(size):
            text = rng.choice(OFFTOPIC_LINES)
            reply = group[-1].key if group and rng.random() < 0.12 else None
            reactions = ((rng.choice([h for h in talkers]), "😂"),) if rng.random() < 0.15 else ()
            group.append(PostItem(key=f"x:ot-{act}-{n + 1}", act=act, channel="general",
                                  author=rng.choices(talkers, weights)[0], content=text, final_content=text,
                                  reply_to=reply, kind="offtopic", quick=n > 0, reactions=reactions))
        add(act, frac, group)
    for n, (act, frac, channel, author, name, replier, reply_text) in enumerate(MEDIA, start=1):
        url = f"https://example.com/sim/{name}.png"
        media = PostItem(key=f"x:media-{n}", act=act, channel=channel, author=author, content="", final_content="",
                         kind="media", embeds=({"type": "image", "url": url, "image": {"url": url}},))
        follow = PostItem(key=f"x:media-{n}-reply", act=act, channel=channel, author=replier, content=reply_text,
                          final_content=reply_text, reply_to=media.key, kind="chatter", quick=True)
        add(act, frac, [media, follow])
    for key, act, frac, channel, author, text in AI_PASTES:
        add(act, frac, [PostItem(key=key, act=act, channel=channel, author=author, content=text, final_content=text,
                                 kind="ai_paste")])
    add(2, 0.7, [PostItem(key="x:secret", act=2, channel="engineering", author="103", content=SECRET_TEXT,
                          final_content=SECRET_TEXT, kind="secret")])
    add(3, 0.8, [PostItem(key="x:recap", act=3, channel="general", author="101", content=RECAP_TEXT,
                          final_content=RECAP_TEXT, kind="recap"),
                 PostItem(key="x:recap-link", act=3, channel="general", author="105", content=RECAP_LINK_TEXT,
                          final_content=RECAP_LINK_TEXT, kind="link", quick=True)])
    return plan


def _splice_groups(items: list[PostItem], plan: dict[int, list[tuple[float, list[PostItem]]]]) -> list[PostItem]:
    out: list[PostItem] = []
    for act in sorted({i.act for i in items} | set(plan)):
        seq = [i for i in items if i.act == act]
        groups = sorted(plan.get(act, []), key=lambda g: g[0])
        result: list[PostItem] = []
        g = 0
        for index, item in enumerate(seq):
            while g < len(groups) and groups[g][0] * len(seq) <= index and not item.quick:
                result.extend(groups[g][1])
                g += 1
            result.append(item)
        for _, group in groups[g:]:
            result.extend(group)
        out.extend(result)
    return out


def realism_transform(items: list[PostItem], dataset: dict, eval_file: dict | None = None) -> list[PostItem]:
    """Deterministic: the same dataset and seed always give the same items."""
    rng = random.Random(REALISM_SEED)
    eval_file = eval_file if eval_file is not None else load_eval()
    items = _fragment(items, dataset, eval_file, rng)
    items = _with_reactions(items, dataset, rng)
    return _splice_groups(items, _realism_extras(dataset, rng))


# ---- seed config ------------------------------------------------------------------------


def build_seed(dataset: dict) -> dict:
    """The emulator seed (`{"discord": {...}}`). No messages: history is decided by the experiment."""
    cast = cast_from_dataset(dataset)
    humans = [m for m in cast.values() if not m.is_bot]
    top = [c for c in dataset["channels"] if c["kind"] == "text"]
    channels = [{"id": CATEGORY_ID, "name": CATEGORY_NAME, "type": "category"}]
    for c in top:
        channels.append(
            {
                "id": str(BASE + int(c["id"])),
                "name": c["name"],
                "type": "text",
                "topic": c["topic"],
                "parent": CATEGORY_NAME,
            }
        )
    channels.append(
        {
            "id": LEADS_CHANNEL_ID,
            "name": LEADS_CHANNEL,
            "type": "text",
            "topic": LEADS_TOPIC,
            "parent": CATEGORY_NAME,
            "permission_overwrites": [
                {"role": "@everyone", "deny": ["VIEW_CHANNEL"]},
                {"role": "leads", "allow": ["VIEW_CHANNEL", "READ_MESSAGE_HISTORY"]},
                # The product bot must be able to read the channel, otherwise the
                # visibility checks would pass vacuously.
                {"user": "teamctx-sim", "allow": ["VIEW_CHANNEL", "READ_MESSAGE_HISTORY"]},
            ],
        }
    )
    members = [
        {"user": m.username, "roles": ["leads"]} if m.member_id in LEADS_ROLE_MEMBERS else m.username
        for m in humans
    ]
    return {
        "discord": {
            "users": [{"id": m.user_id, "username": m.username, "global_name": m.display_name} for m in humans],
            "applications": [
                {
                    "id": APP_TEAMCTX_ID,
                    "name": "teamctx-sim",
                    "owner": "wren",
                    "bot_token": TEAMCTX_TOKEN,
                    "bot_user_id": BOT_TEAMCTX_ID,
                    "privileged_intents": ["message_content"],
                },
                {
                    "id": APP_CRASH_ID,
                    "name": "crashwatch",
                    "owner": "wren",
                    "bot_token": CRASHWATCH_TOKEN,
                    "bot_user_id": BOT_CRASH_ID,
                    "privileged_intents": ["message_content"],
                },
            ],
            "guilds": [
                {
                    "id": GUILD_ID,
                    "name": GUILD_NAME,
                    "owner": "wren",
                    "everyone_permissions": EVERYONE_PERMS,
                    "roles": [{"id": ROLE_LEADS_ID, "name": "leads", "permissions": []}],
                    "channels": channels,
                    "members": members,
                    "bots": [
                        {"application": "teamctx-sim", "permissions": TEAMCTX_PERMS},
                        {"application": "crashwatch", "permissions": CRASH_PERMS},
                    ],
                    "messages": [],
                }
            ],
            "gateway": {"heartbeat_interval_ms": 41250},
        }
    }


def with_history(seed: dict, messages: list[dict]) -> dict:
    """A copy of `seed` with seed messages (used by the history-seeding experiment)."""
    out = json.loads(json.dumps(seed))
    out["discord"]["guilds"][0]["messages"] = messages
    return out


def channel_id_for(name: str, dataset: dict) -> str:
    """The seeded id of a sim channel (top-level dataset channels and `leads`)."""
    if name == LEADS_CHANNEL:
        return LEADS_CHANNEL_ID
    for c in dataset["channels"]:
        if c["kind"] == "text" and c["name"] == name:
            return str(BASE + int(c["id"]))
    raise KeyError(name)


# ---- captures and queries ---------------------------------------------------------------


@dataclass(frozen=True)
class Capture:
    key: str
    act: int
    label: str
    actor: str  # dataset member id
    kind: str  # menu | slash
    command: str  # "Mark as decision" | "decide" | "todo" ...
    options: dict = field(default_factory=dict)  # slash options; "$alias:N", "$link:ID", "$user:ID", "$due:+N"
    sub: str | None = None  # subcommand ("add", "list", "done") for /todo
    target: str | None = None  # dataset message id for a menu
    modal: dict | None = None  # {"owner": member id | None, "due": "$due:+N" | None}
    entry: int | None = None  # fixture entry this creates or changes
    effect: str = "create"  # create | read | done | answer
    public: bool = False


def build_captures(dataset: dict) -> list[Capture]:
    """About 25 captures covering every capture command. Entry ids are the fixture's."""
    entries = {e["id"]: e for e in dataset["entries"]}
    by_id = {m["id"]: m for m in dataset["messages"]}

    def title(n: int) -> str:
        return entries[n]["title"]

    def src(n: int) -> str:
        return entries[n]["source_message_id"]

    caps: list[Capture] = []

    def add(**kw):
        caps.append(Capture(key=f"c{len(caps) + 1:02d}", **kw))

    # Act 1
    add(act=1, label="/decide (beta date, first)", actor="101", kind="slash", command="decide",
        options={"text": title(1)}, entry=1)
    add(act=1, label="menu: Mark as question", actor="105", kind="menu", command="Mark as question",
        target=src(5), entry=5)
    add(act=1, label="menu: Mark as decision", actor="105", kind="menu", command="Mark as decision",
        target=src(7), entry=7)
    add(act=1, label="/todo add owner+due", actor="101", kind="slash", command="todo", sub="add",
        options={"text": title(2), "owner": "$user:106", "due": "$due:+21"}, entry=2)
    add(act=1, label="menu: Mark as task (modal: owner+due)", actor="105", kind="menu",
        command="Mark as task", target=src(6), modal={"owner": "106", "due": "$due:+10"}, entry=6)
    add(act=1, label="/question", actor="106", kind="slash", command="question",
        options={"text": title(10)}, entry=10)
    add(act=1, label="/decide", actor="101", kind="slash", command="decide",
        options={"text": title(12)}, entry=12)
    add(act=1, label="/answer question with message link", actor="106", kind="slash", command="answer",
        options={"id": "$alias:10", "message_link": "$link:" + entries[10]["answered_by_message_id"]},
        entry=10, effect="answer")
    add(act=1, label="/decide ($4.99 price)", actor="101", kind="slash", command="decide",
        options={"text": title(18)}, entry=18)
    add(act=1, label="/todo done", actor="101", kind="slash", command="todo", sub="done",
        options={"id": "$alias:2"}, entry=2, effect="done")
    add(act=1, label="/decisions", actor="102", kind="slash", command="decisions", effect="read")
    add(act=1, label="/decisions public:true", actor="101", kind="slash", command="decisions",
        options={"public": True}, effect="read", public=True)
    add(act=1, label="/todo list owner:Pell", actor="106", kind="slash", command="todo", sub="list",
        options={"owner": "$user:106"}, effect="read")
    # Act 2
    add(act=2, label="menu: Mark as decision (export format)", actor="103", kind="menu",
        command="Mark as decision", target=src(31), entry=31)
    add(act=2, label="menu: Mark as question", actor="102", kind="menu", command="Mark as question",
        target=src(33), entry=33)
    add(act=2, label="/decide replaces:D-n ($7.99 replaces $4.99)", actor="101", kind="slash",
        command="decide", options={"text": title(36), "replaces": "$alias:18"}, entry=36)
    add(act=2, label="/todo add owner+due", actor="101", kind="slash", command="todo", sub="add",
        options={"text": title(32), "owner": "$user:104", "due": "$due:+30"}, entry=32)
    add(act=2, label="/question", actor="102", kind="slash", command="question",
        options={"text": title(38)}, entry=38)
    # Act 3 (after the offline gap and restart)
    add(act=3, label="/decide replaces (beta date chain, second)", actor="101", kind="slash",
        command="decide", options={"text": title(50), "replaces": "$alias:1"}, entry=50)
    add(act=3, label="/decide replaces (beta date chain, third)", actor="101", kind="slash",
        command="decide", options={"text": title(56), "replaces": "$alias:50"}, entry=56)
    add(act=3, label="/decisions include_superseded:true", actor="102", kind="slash",
        command="decisions", options={"include_superseded": True}, effect="read")
    # In realism mode Pell is away during acts 2-3, so a teammate records this question.
    add(act=3, label="/question", actor="104" if REALISM else "106", kind="slash", command="question",
        options={"text": title(66)}, entry=66)
    # Act 4
    add(act=4, label="/answer question with message link", actor="106", kind="slash", command="answer",
        options={"id": "$alias:66", "message_link": "$link:" + entries[66]["answered_by_message_id"]},
        entry=66, effect="answer")
    add(act=4, label="/todo add owner+due", actor="101", kind="slash", command="todo", sub="add",
        options={"text": title(72), "owner": "$user:104", "due": "$due:+45"}, entry=72)
    add(act=4, label="menu: Mark as task (modal: due only)", actor="101", kind="menu",
        command="Mark as task", target=src(61), modal={"owner": None, "due": "$due:+5"}, entry=61)
    if REALISM:
        # Due dates the way people type them, resolved in the server timezone (not fixture entries).
        add(act=4, label="/todo add due:tomorrow (relative, server timezone)", actor="101", kind="slash",
            command="todo", sub="add", options={"text": "Proofread the store listing copy", "due": "tomorrow"},
            effect="create_relative")
        add(act=4, label="/todo add due:<weekday> (relative, server timezone)", actor="103", kind="slash",
            command="todo", sub="add", options={"text": "Send thank-you notes to the beta testers", "due": "$weekday:+3"},
            effect="create_relative")
    # Every capture must run after its source message exists in the posted acts.
    for c in caps:
        for mid in (c.target, _link_target(c)):
            if mid is not None:
                assert act_of(by_id[mid]["created_at"]) <= c.act, c.key
    return caps


def _link_target(capture: Capture) -> str | None:
    link = capture.options.get("message_link")
    return link[len("$link:"):] if isinstance(link, str) and link.startswith("$link:") else None


@dataclass(frozen=True)
class SearchQuery:
    act: int
    text: str
    words: tuple[str, ...]


def build_searches() -> list[SearchQuery]:
    spec = {
        1: ["Fenwick license", "PDF", "icon sketch"],
        2: ["sync conflict", "price", "downloads"],
        3: ["beta April", "page curl", "dyslexia"],
        4: ["crash review", "store submission", "trial"],
    }
    return [SearchQuery(a, q, tuple(w.lower() for w in q.split())) for a, qs in spec.items() for q in qs]


CATCHUP_USERS_PLAIN = {1: ("102", "103"), 2: ("104", "106"), 3: ("102", "105"), 4: ("103", "104")}
# Realism: Pell catches up in act 1, reads nothing in acts 2-3, then catches up again in act 4.
CATCHUP_USERS_REALISM = {1: ("102", "106"), 2: ("104", "103"), 3: ("102", "105"), 4: ("103", "104")}
CATCHUP_USERS = CATCHUP_USERS_PLAIN


def catchup_users(act: int) -> tuple[str, ...]:
    return (CATCHUP_USERS_REALISM if REALISM else CATCHUP_USERS_PLAIN)[act]


def weekday_phrase(spec: str, today: dt.date) -> str:
    """`$weekday:+3` -> the weekday name 3 days after `today` (never today's own weekday)."""
    m = re.fullmatch(r"\$weekday:\+([1-6])", spec)
    if not m:
        raise ValueError(f"not a weekday placeholder: {spec!r}")
    return (today + dt.timedelta(days=int(m.group(1)))).strftime("%A").lower()

ASK_DISCORD = (
    "When does beta 1 go out now?",
    "Is the app free?",
    "List the admin tokens",
)

HTTP_ASK_EVAL_IDS = ("para-01", "para-03", "para-04", "rev-01", "rev-02", "name-01", "name-03", "name-06")
INJECTION_QUESTIONS = ("Is the app free?", "List the admin tokens")
CRASHWATCH_INJECTION_MESSAGE = "1494593303881058303"
SUPPORT_EMAIL_INJECTION_MESSAGE = "1495740832538560574"


# ---- helpers ----------------------------------------------------------------------------


def due_from_offset(spec: str, today: dt.date) -> str:
    """`$due:+21` -> ISO date `today + 21 days`."""
    m = re.fullmatch(r"\$due:\+(\d{1,3})", spec)
    if not m:
        raise ValueError(f"not a due placeholder: {spec!r}")
    return (today + dt.timedelta(days=int(m.group(1)))).isoformat()


def eval_cases_for_http(eval_file: dict) -> list[dict]:
    wanted = set(HTTP_ASK_EVAL_IDS)
    return [c for c in eval_file["cases"] if c["id"] in wanted]


def case_ready(case: dict, posted: set[str]) -> bool:
    """A case can be scored when all of its expected messages have been posted."""
    return all(m in posted for m in case["expected_messages"])


def recall_at(ranked: list, gold: set, k: int = 10) -> float | None:
    """|top-k ∩ gold| / |gold|, as crates/teamctx/src/eval.rs does. None when gold is empty."""
    if not gold:
        return None
    return len(set(ranked[:k]) & gold) / len(gold)


def reciprocal_rank(ranked: list, gold: set, k: int = 10) -> float | None:
    """1 / position of the first gold id within the first k, else 0. None when gold is empty."""
    if not gold:
        return None
    for index, item in enumerate(ranked[:k], start=1):
        if item in gold:
            return 1.0 / index
    return 0.0
