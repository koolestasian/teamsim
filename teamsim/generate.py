"""Population generator: a pure, offline function from a population file and a
preset to a scenario pack.

``load_population`` reads and validates a population file (version 1);
``generate`` turns it into a ``Pack``; ``generate_file`` also writes the pack.
The function reads no clock, no environment and no random source, uses no floating
point, and calls no model. Every choice is a keyed draw (``teamsim.draw``) whose
seed is the population's seed and whose scope names the user and the trait or slot
(``[user id, trait or slot name]``, with the index in the purpose). Adding,
removing or editing one user therefore never changes another user's draws.

``PRESETS`` lists ``"social"``, ``"solo"`` and ``"team"``. A preset is a data file
(``teamsim/presets/<name>.toml``), described field by field in
``docs/spec/population-format.md``. Its ``shape`` (``team`` when absent) says which
planting and filler code reads it: a workspace of channels, one user talking to the
product, or users acting on the product through ``op`` events.
"""

import tomllib
from functools import lru_cache
from importlib import resources
from pathlib import Path

from . import canon, draw, model, pack

__all__ = [
    "BUNDLES",
    "GENERATOR_VERSION",
    "POPULATION_RULES",
    "PRESETS",
    "PopulationError",
    "TRAIT_DEFAULTS",
    "generate",
    "generate_file",
    "load_population",
]

GENERATOR_VERSION = "teamsim-generate 1"
PRESETS = ("social", "solo", "team")

DAY = 86_400_000
HOUR = 3_600_000
MINUTE = 60_000
# Every message, with its fragments, correction or repost, ends within SPAN of the
# time it starts, so it fits inside an active window whole.
SPAN = 120_000
MAX_USERS = 1000
MAX_DAYS = 365
_DEFAULT_WINDOW = 9 * HOUR  # the working window turns are scheduled in (09:00 to 18:00)

# A heavy-tailed table of 21 equally likely multipliers, in thousandths of the
# median. The middle entry is 1000, so the median of the delays is the parameter.
DELAY_TABLE = (
    50, 90, 140, 200, 300, 420, 550, 650, 730, 800,
    1000,
    1250, 1500, 1900, 2500, 3300, 4500, 6500, 9500, 14000, 20000,
)  # fmt: skip

TRAIT_DEFAULTS = {
    "reply_median_s": 60,
    "split_pct": 20,
    "short_pct": 29,
    "typo_pct": 2,
    "wrong_place_pct": 0,
    "probe_pct": 0,
    "away": [],
    "active_hours": {"start": 9, "end": 18, "offset": 0},
}

BUNDLES = {
    "careful": {"reply_median_s": 240, "split_pct": 10, "typo_pct": 0, "wrong_place_pct": 0},
    "hurried": {"reply_median_s": 20, "split_pct": 60, "typo_pct": 8},
    "away-often": {
        "away": [
            {"from_day": 3, "to_day": 4},
            {"from_day": 10, "to_day": 11},
            {"from_day": 17, "to_day": 18},
        ]
    },
}

_NUMERIC = {
    "reply_median_s": (1, 86_400),
    "split_pct": (0, 100),
    "short_pct": (0, 100),
    "typo_pct": (0, 100),
    "wrong_place_pct": (0, 100),
    "probe_pct": (0, 100),
}
_TRAIT_KEYS = {"bundle", "away", "active_hours", *_NUMERIC}
_PLANT_KEYS = (
    "reversals",
    "private_facts",
    "secrets",
    "unauthorised_claims",
    "absences",
    "unanswerable",
)
_TOP_KEYS = {"format", "preset", "seed", "days", "groups", "overrides", "plant"}

POPULATION_RULES = {
    "missing_file": "the population file is absent or unreadable",
    "bad_toml": "the population file is not valid TOML or not UTF-8",
    "unknown_key": "a key the population format does not define",
    "missing_key": "a required key is absent",
    "bad_type": "a value has the wrong type (floats, dates and booleans are never accepted)",
    "bad_format": "format is not 1",
    "bad_value": "a value is outside its allowed range",
    "bad_range": "a range has min above max, or a window ends before it starts",
    "unknown_preset": "the preset is not one of PRESETS",
    "unknown_bundle": "a trait bundle is not defined",
    "unknown_role": "a group role is not a role of the preset",
    "unknown_user": "an override names a user the groups do not produce",
    "duplicate_user": "two overrides name one user",
    "too_many_users": f"the groups produce more than {MAX_USERS} users",
    "bad_preset": "a preset data file is malformed",
    "days_too_few": "the planted situations need more virtual days than the file gives",
    "planted_conflict": "a planted event falls outside its author's active hours or inside an away window",
}


class PopulationError(ValueError):
    """A population file or a preset that the generator rejects.

    ``code`` is a stable rule code (a key of ``POPULATION_RULES``); ``path`` is the
    key path in the file, such as ``groups[1].traits.typo_pct``, or ``None``.
    """

    def __init__(self, code, message, path=None):
        super().__init__(code, message, path)
        self.code = code
        self.message = message
        self.path = path

    def __str__(self):
        where = f"{self.path}: " if self.path else ""
        return f"{where}{self.code}: {self.message}"


# --- reading and checking the population file -------------------------------


def _err(code, message, path=None):
    return PopulationError(code, message, path)


def _is_int(value):
    return type(value) is int


def _table(value, path, allowed, required=()):
    if type(value) is not dict:
        raise _err("bad_type", "expected a table", path)
    for key in value:
        if key not in allowed:
            raise _err("unknown_key", f"unknown key {key!r}", f"{path}.{key}" if path else key)
    for key in required:
        if key not in value:
            raise _err("missing_key", f"missing key {key!r}", f"{path}.{key}" if path else key)
    return value


def _int_in(value, lo, hi, path):
    if not _is_int(value):
        raise _err("bad_type", "expected an integer", path)
    if not lo <= value <= hi:
        raise _err("bad_value", f"{value} is outside {lo}..{hi}", path)
    return value


def _check_traits(traits, path, days):
    _table(traits, path, _TRAIT_KEYS)
    if "bundle" in traits:
        name = traits["bundle"]
        if type(name) is not str:
            raise _err("bad_type", "a bundle is a name", f"{path}.bundle")
        if name not in BUNDLES:
            raise _err("unknown_bundle", f"no bundle named {name!r}", f"{path}.bundle")
    for name, (lo, hi) in _NUMERIC.items():
        if name not in traits:
            continue
        value, where = traits[name], f"{path}.{name}"
        if type(value) is dict:
            _table(value, where, {"min", "max"}, ("min", "max"))
            low = _int_in(value["min"], lo, hi, f"{where}.min")
            high = _int_in(value["max"], lo, hi, f"{where}.max")
            if low > high:
                raise _err("bad_range", f"min {low} is above max {high}", where)
        else:
            _int_in(value, lo, hi, where)
    if "away" in traits:
        windows = traits["away"]
        if type(windows) is not list:
            raise _err("bad_type", "away is a list of windows", f"{path}.away")
        if len(windows) > 64:
            raise _err("bad_value", "at most 64 away windows", f"{path}.away")
        for index, window in enumerate(windows):
            where = f"{path}.away[{index}]"
            _table(window, where, {"from_day", "to_day"}, ("from_day", "to_day"))
            first = _int_in(window["from_day"], 0, days - 1, f"{where}.from_day")
            last = _int_in(window["to_day"], 0, days - 1, f"{where}.to_day")
            if first > last:
                raise _err("bad_range", f"from_day {first} is after to_day {last}", where)
    if "active_hours" in traits:
        where = f"{path}.active_hours"
        hours = _table(traits["active_hours"], where, {"start", "end", "offset"}, ("start", "end"))
        start = _int_in(hours["start"], 0, 23, f"{where}.start")
        end = _int_in(hours["end"], 1, 24, f"{where}.end")
        if "offset" in hours:
            _int_in(hours["offset"], -12, 14, f"{where}.offset")
        if end - start < 1:
            raise _err("bad_range", "the window must be at least one hour long", where)


def _users(population, roles):
    """The users the groups produce, as ``(id, role, group traits)``, in order."""
    users, seen = [], {}
    for group in population["groups"]:
        role = group["role"]
        for _ in range(group["count"]):
            seen[role] = seen.get(role, 0) + 1
            users.append((f"{role}-{seen[role]}", role, group.get("traits", {})))
            if len(users) > MAX_USERS:
                raise _err("too_many_users", f"more than {MAX_USERS} users", "groups")
    return users


def _validate(population):
    """Check a population object; return its preset."""
    top = _table(population, "", _TOP_KEYS, ("format", "preset", "seed", "days", "groups"))
    if not _is_int(top["format"]):
        raise _err("bad_type", "format is an integer", "format")
    if top["format"] != 1:
        raise _err("bad_format", f"format {top['format']} is not 1", "format")
    if type(top["preset"]) is not str:
        raise _err("bad_type", "a preset is a name", "preset")
    if top["preset"] not in PRESETS:
        raise _err("unknown_preset", f"no preset named {top['preset']!r}", "preset")
    preset = _preset(top["preset"])
    if type(top["seed"]) is not str:
        raise _err("bad_type", "a seed is a string", "seed")
    if not top["seed"]:
        raise _err("bad_value", "the seed is empty", "seed")
    days = _int_in(top["days"], 1, MAX_DAYS, "days")
    groups = top["groups"]
    if type(groups) is not list:
        raise _err("bad_type", "groups is a list of tables", "groups")
    if not groups:
        raise _err("bad_value", "at least one group is needed", "groups")
    for index, group in enumerate(groups):
        where = f"groups[{index}]"
        _table(group, where, {"role", "count", "traits"}, ("role", "count"))
        if type(group["role"]) is not str:
            raise _err("bad_type", "a role is a name", f"{where}.role")
        if group["role"] not in preset["roles"]["names"]:
            raise _err("unknown_role", f"no role named {group['role']!r}", f"{where}.role")
        _int_in(group["count"], 1, MAX_USERS, f"{where}.count")
        if "traits" in group:
            _check_traits(group["traits"], f"{where}.traits", days)
    users = _users(top, preset["roles"])
    if "max_users" in preset and len(users) > preset["max_users"]:
        raise _err(
            "bad_value",
            f"the {top['preset']} preset holds at most {preset['max_users']} user"
            + ("" if preset["max_users"] == 1 else "s"),
            "groups",
        )
    names = {user_id for user_id, _, _ in users}
    overrides = top.get("overrides", [])
    if type(overrides) is not list:
        raise _err("bad_type", "overrides is a list of tables", "overrides")
    named = set()
    for index, override in enumerate(overrides):
        where = f"overrides[{index}]"
        _table(override, where, {"user", "traits"}, ("user", "traits"))
        if type(override["user"]) is not str:
            raise _err("bad_type", "a user is an id", f"{where}.user")
        if override["user"] not in names:
            raise _err("unknown_user", f"no user {override['user']!r}", f"{where}.user")
        if override["user"] in named:
            raise _err("duplicate_user", f"{override['user']!r} is overridden twice", f"{where}.user")
        named.add(override["user"])
        _check_traits(override["traits"], f"{where}.traits", days)
    if "plant" in top:
        _table(top["plant"], "plant", set(preset["plant"]))
        for name, value in top["plant"].items():
            _int_in(value, 0, 50, f"plant.{name}")
    return preset


def load_population(path) -> dict:
    """Read and validate a population file; return the object it holds.

    Raises ``PopulationError`` with a stable code and the key path of the first problem.
    The returned object is the file's own content (comments, key order and spelling
    never matter), so ``canon.hash_of`` of it is the population hash.
    """
    try:
        raw = Path(path).read_bytes()
    except OSError as error:
        raise _err("missing_file", f"cannot read the population file: {error.strerror}") from None
    try:
        obj = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        raise _err("bad_toml", str(error)) from None
    try:
        canon.check(obj)
    except canon.CanonError as error:
        raise _err("bad_type", error.reason, str(error.path)) from None
    _validate(obj)
    return obj


# --- presets ----------------------------------------------------------------


@lru_cache(maxsize=None)
def _preset(name):
    """The checked preset object for ``name``. Treat it as read-only."""
    text = resources.files("teamsim.presets").joinpath(f"{name}.toml").read_text(encoding="utf-8")
    obj = tomllib.loads(text)
    try:
        _check_preset(obj)
    except (KeyError, TypeError, AttributeError) as error:
        raise _err("bad_preset", f"{name}: {error!r}") from None
    return obj


def _words(text):
    return len(text.split())


def _check_preset(preset):
    if preset["format"] != 1:
        raise _err("bad_preset", "preset format must be 1")
    if not set(preset["roles"]["authority"]) <= set(preset["roles"]["names"]):
        raise _err("bad_preset", "authority roles must be roles")
    shape = preset.get("shape", "team")
    if shape not in _SHAPES:
        raise _err("bad_preset", f"unknown shape {shape!r}")
    if shape != "team":
        _check_direct_preset(preset, shape)
        return
    surfaces = {s["id"] for s in preset["surfaces"]}
    for name in ("public_surface", "restricted_surface"):
        if preset[name] not in surfaces:
            raise _err("bad_preset", f"{name} must name a surface")
    if sum(1 for s in preset["surfaces"] if s["members"] == "all" and s["kind"] == "channel") < 2:
        raise _err("bad_preset", "at least two channels that everyone joins are needed")
    text = preset["text"]
    for bank in ("statement", "question", "unplanted", "reply"):
        for entry in text[f"{bank}_long"]:
            if _words(entry) < 8:
                raise _err("bad_preset", f"{bank}_long needs at least 8 words: {entry!r}")
        for entry in text[f"{bank}_short"]:
            if not 1 <= _words(entry) <= 3:
                raise _err("bad_preset", f"{bank}_short needs 1 to 3 words: {entry!r}")
    for slot in ("reversal", "private_fact", "secret", "claim", "absence"):
        if not preset[slot]:
            raise _err("bad_preset", f"no {slot} templates")
    for topic in preset["reversal"]:
        if len(topic["versions"]) < 3:
            raise _err("bad_preset", f"reversal {topic['key']!r} needs 3 versions")


_SHAPES = ("team", "solo", "social")
_DIRECT_SLOTS = {
    "solo": ("reversal", "injection", "return"),
    "social": ("friends_post", "block_post", "deleted_post"),
}
_DIRECT_BANKS = {"solo": ("statement", "question", "unplanted"), "social": ("statement",)}


def _check_direct_preset(preset, shape):
    """Checks for the presets whose users talk to the product on direct surfaces."""
    if not preset["direct_surfaces"] or preset.get("surfaces"):
        raise _err("bad_preset", f"a {shape} preset has direct surfaces only")
    text = preset["text"]
    for bank in _DIRECT_BANKS[shape]:
        for entry in text[f"{bank}_long"]:
            if _words(entry) < 8:
                raise _err("bad_preset", f"{bank}_long needs at least 8 words: {entry!r}")
        for entry in text[f"{bank}_short"]:
            if not 1 <= _words(entry) <= 3:
                raise _err("bad_preset", f"{bank}_short needs 1 to 3 words: {entry!r}")
    for slot in _DIRECT_SLOTS[shape]:
        if not preset[slot]:
            raise _err("bad_preset", f"no {slot} templates")
    for topic in preset.get("reversal", ()):
        if len(topic["versions"]) < 3:
            raise _err("bad_preset", f"reversal {topic['key']!r} needs 3 versions")
    if set(preset["plant"]) != _DIRECT_PLANT[shape]:
        raise _err("bad_preset", f"the {shape} preset's plant keys are {sorted(_DIRECT_PLANT[shape])}")


_DIRECT_PLANT = {
    "solo": {"reversals", "injections", "returns", "unanswerable"},
    "social": {"friends_only", "blocks", "deletions"},
}


# --- time and traits --------------------------------------------------------


class _User:
    __slots__ = ("id", "role", "traits", "away")

    def __init__(self, user_id, role, traits):
        self.id = user_id
        self.role = role
        self.traits = traits
        self.away = []  # merged [start_ms, end_ms) windows: the trait and planted ones


def _clip(windows, days):
    out = []
    for window in windows:
        if window["from_day"] <= days - 1:
            out.append({"from_day": window["from_day"], "to_day": min(window["to_day"], days - 1)})
    return out


def _merge(spans):
    """Sort ``[start, end)`` spans and join the ones that overlap or touch."""
    merged = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def _resolve(seed, days, user_id, layers):
    """The drawn trait numbers of one user: defaults, then each layer in order."""
    traits = {k: (dict(v) if type(v) is dict else list(v) if type(v) is list else v) for k, v in TRAIT_DEFAULTS.items()}
    for layer in layers:
        if "bundle" in layer:
            for key, value in BUNDLES[layer["bundle"]].items():
                traits[key] = _clip(value, days) if key == "away" else value
        for key, value in layer.items():
            if key != "bundle":
                traits[key] = value
    for name, (lo, hi) in _NUMERIC.items():
        value = traits[name]
        if type(value) is dict:
            traits[name] = value["min"] + draw.below(
                seed, [user_id, name], [0], value["max"] - value["min"] + 1
            )
    hours = traits["active_hours"]
    traits["active_hours"] = {
        "start": hours["start"],
        "end": hours["end"],
        "offset": hours.get("offset", 0),
    }
    traits["away"] = [
        {"from_day": start // DAY, "to_day": end // DAY - 1}
        for start, end in _merge((w["from_day"] * DAY, (w["to_day"] + 1) * DAY) for w in traits["away"])
    ]
    return traits


def _in_hours(user, t0, t1):
    hours = user.traits["active_hours"]
    start, end = hours["start"] * HOUR, hours["end"] * HOUR
    if end - start >= DAY:
        return True
    local = (t0 + hours["offset"] * HOUR) % DAY
    return start <= local and local + (t1 - t0) <= end


def _away_end(user, t0, t1):
    """The end of an away window that overlaps ``[t0, t1]``, or ``None``."""
    for start, end in user.away:
        if t0 < end and t1 >= start:
            return end
    return None


def _next_open(user, t):
    hours = user.traits["active_hours"]
    start = hours["start"] * HOUR
    local = (t + hours["offset"] * HOUR) % DAY
    return t + (start - local if local < start else DAY - local + start)


def _fit(user, t, jitter):
    """The first time at or after ``t`` where a message fits the user's hours and
    absences. ``jitter`` is added once when the time had to move."""
    for _ in range(10_000):
        end = _away_end(user, t, t + SPAN)
        if end is not None:
            t = end + jitter
            jitter = 0
            continue
        if not _in_hours(user, t, t + SPAN):
            t = _next_open(user, t) + jitter
            jitter = 0
            continue
        return t
    raise AssertionError("unreachable: a window opens within a day")


# --- messages ----------------------------------------------------------------


def _typo(text, seed, scope, purpose):
    """Swap two adjacent different ASCII letters; ``None`` when there is no pair."""
    pairs = [
        i
        for i in range(len(text) - 1)
        if text[i].isascii()
        and text[i + 1].isascii()
        and text[i].isalpha()
        and text[i + 1].isalpha()
        and text[i] != text[i + 1]
    ]
    if not pairs:
        return None
    i = draw.choice(seed, scope, purpose, pairs)
    return text[:i] + text[i + 1] + text[i] + text[i + 2 :]


def _fragments(text, count):
    words = text.split()
    base, extra = divmod(len(words), count)
    out, at = [], 0
    for index in range(count):
        size = base + (1 if index < extra else 0)
        out.append(" ".join(words[at : at + size]))
        at += size
    return out


def _post(event_id, at, actor, surface, text, **more):
    event = {"id": event_id, "at": at, "actor": actor, "surface": surface, "kind": "post", "text": text}
    event.update(more)
    return event


class _Context:
    def __init__(self, seed, days, preset, users):
        self.seed = seed
        self.days = days
        self.preset = preset
        self.users = users
        self.by_id = {u.id: u for u in users}
        self.ids = [u.id for u in users]
        if preset.get("shape", "team") == "team":
            self.public = [s["id"] for s in preset["surfaces"] if s["members"] == "all"]
        else:
            self.public = [f"direct:{u.id}" for u in users]
        self.events = []
        self.facts = []
        self.checks = []
        self.planted = []  # (actor id, time, event id) of every planted post
        self.pending = []  # catch-up probes waiting for their back event
        authority = [u.id for u in users if u.role in preset["roles"]["authority"]]
        self.leads = authority or [users[0].id]
        self.author = self.leads[0]
        self.outsiders = [i for i in self.ids if i not in self.leads]


def _emit(ctx, user, base, surface, mid, text):
    """One filler message by ``user`` starting at ``base``, with the user's habits.

    Returns the events: the post (``mid``), and as the habits say, a wrong-place post
    and its deletion (``mid.w``, ``mid.d``), further fragments (``mid.f1``...) and a
    correcting edit (``mid.e``).
    """
    seed, traits, uid = ctx.seed, user.traits, user.id
    events = []
    words = text.split()
    fragments = [text]
    if len(words) > 3 and draw.chance(seed, [uid, "split_pct"], [mid], traits["split_pct"], 100):
        count = min(2 + draw.below(seed, [uid, "split_pct"], [mid, "n"], 3), len(words))
        fragments = _fragments(text, count)
    first = fragments[0]
    typed = None
    if draw.chance(seed, [uid, "typo_pct"], [mid], traits["typo_pct"], 100):
        typed = _typo(first, seed, [uid, "typo_pct"], [mid, "where"])
    shown = typed if typed is not None else first
    at = base
    others = [s for s in ctx.public if s != surface]
    # with no other surface (solo) there is nowhere to post by mistake
    if others and draw.chance(seed, [uid, "wrong_place_pct"], [mid], traits["wrong_place_pct"], 100):
        wrong = draw.choice(seed, [uid, "wrong_place_pct"], [mid, "surface"], others)
        events.append(_post(f"{mid}.w", at, uid, wrong, shown))
        events.append(
            {"id": f"{mid}.d", "at": at + 20_000, "actor": uid, "surface": wrong, "kind": "delete", "target": f"{mid}.w"}
        )
        at += 35_000
    events.append(_post(mid, at, uid, surface, shown))
    for index, fragment in enumerate(fragments[1:], 1):
        events.append(_post(f"{mid}.f{index}", at + 4_000 * index, uid, surface, fragment))
    if typed is not None:
        edit_at = at + 15_000 + draw.below(seed, [uid, "typo_pct"], [mid, "delay"], 25_000)
        events.append(
            {"id": f"{mid}.e", "at": edit_at, "actor": uid, "surface": surface, "kind": "edit", "target": mid, "text": first}
        )
    return events


def _pick_text(ctx, user, bank, key):
    text = ctx.preset["text"]
    seed = ctx.seed
    short = draw.chance(seed, [user.id, "short_pct"], [key], user.traits["short_pct"], 100)
    items = text[f"{bank}_short" if short else f"{bank}_long"]
    return draw.choice(seed, [user.id, "text"], [key], items)


def _filler(ctx):
    """Scheduled conversation: every user opens turns, and one other user replies to each.

    A turn is scheduled at a time that depends on nothing but the opener's id and the
    turn number; the opener's own hours then move it. A reply is timed from the
    scheduled time, so one user's habits never move another user's messages.
    """
    seed, days, preset = ctx.seed, ctx.days, ctx.preset
    per_day = preset["filler"]["turns_per_day"]
    question_pct = preset["filler"]["question_pct"]
    end = days * DAY
    count = len(ctx.users)
    for user in ctx.users:
        hours = user.traits["active_hours"]
        wlen = (hours["end"] - hours["start"]) * HOUR
        others = [i for i in ctx.ids if i != user.id]
        for day in range(days):
            for turn in range(per_day):
                n = day * per_day + turn
                offset = draw.below(seed, [user.id, "turn_time"], [n], _DEFAULT_WINDOW - SPAN)
                scheduled = day * DAY + 9 * HOUR + offset
                surface = draw.choice(seed, [user.id, "surface"], [n], ctx.public)
                # the opener's own turn
                actual = day * DAY + (hours["start"] - hours["offset"]) * HOUR
                actual += offset * (wlen - SPAN) // (_DEFAULT_WINDOW - SPAN)
                if (
                    actual >= 0
                    and actual + SPAN <= end
                    and _away_end(user, actual, actual + SPAN) is None
                ):
                    if draw.chance(seed, [user.id, "kind"], [n], question_pct, 100):
                        unplanted = draw.chance(seed, [user.id, "probe_pct"], [n], user.traits["probe_pct"], 100)
                        letter, bank = ("x", "unplanted") if unplanted else ("q", "question")
                    else:
                        letter, bank = "t", "statement"
                    mid = f"{user.id}.{letter}{n}"
                    ctx.events.extend(_emit(ctx, user, actual, surface, mid, _pick_text(ctx, user, bank, mid)))
                # the reply of one other user
                if count > 1:
                    replier = ctx.by_id[others[draw.below(seed, [user.id, "responder"], [n], count - 1)]]
                    thread = f"{user.id}.{n}"
                    rid = f"{replier.id}.r.{thread}"
                    factor = draw.quantile(seed, [replier.id, "reply_median_s"], [thread], DELAY_TABLE)
                    at = scheduled + replier.traits["reply_median_s"] * factor
                    jitter = draw.below(seed, [replier.id, "jitter"], [thread], 10 * MINUTE)
                    at = _fit(replier, at, jitter)
                    if at + SPAN <= end:
                        text = _pick_text(ctx, replier, "reply", rid)
                        ctx.events.extend(_emit(ctx, replier, at, surface, rid, text))


# --- planted situations -------------------------------------------------------


def _steps(start_day, span, n):
    """``n`` increasing times on a grid of working-hour slots across ``span`` days."""
    used, out = {}, []
    for j in range(n):
        day = start_day + (j * span) // n
        slot = used.get(day, 0)
        used[day] = slot + 1
        out.append(day * DAY + 9 * HOUR + 10 * MINUTE + slot * 80 * MINUTE)
    return out


def _plant_post(ctx, event_id, at, actor, surface, text, **more):
    event = _post(event_id, at, actor, surface, text, **more)
    ctx.events.append(event)
    ctx.planted.append((actor, at, event_id))
    return event_id


def _fact(ctx, fact_id, key, kind, value, forms, audience, supersedes=None, authority=None):
    fact = {
        "id": fact_id,
        "key": key,
        "kind": kind,
        "value": value,
        "authority": [ctx.author] if authority is None else list(authority),
        "audience": audience,
    }
    if forms is not None:
        fact["forms"] = list(forms)
    if supersedes is not None:
        fact["supersedes"] = supersedes
    ctx.facts.append(fact)


def _unanswerable(ctx, counts, days, absentees):
    """Questions about things never planted: asked, but with no check (see the format document)."""
    seed, public = ctx.seed, ctx.preset["public_surface"]
    for k in range(counts["unanswerable"]):
        who = draw.choice(seed, ["plant", f"unanswerable-{k}"], ["who"], [i for i in ctx.ids if i not in absentees])
        day = (k * (days - 1)) // max(counts["unanswerable"], 1)
        text = draw.choice(seed, ["plant", f"unanswerable-{k}"], ["text"], ctx.preset["text"]["unplanted_long"])
        # a question nobody scores may move to its author's next free time
        at = _fit(ctx.by_id[who], day * DAY + 15 * HOUR + (k % 4) * 10 * MINUTE, 0)
        if at + SPAN <= days * DAY:
            ctx.events.append(_post(f"plant.un{k}", at, who, public, text))


def _plant(ctx, population):
    """Add the planted situations. Returns the limits to state about what was left out."""
    preset, seed, days = ctx.preset, ctx.seed, ctx.days
    counts = dict(preset["plant"])
    counts.update(population.get("plant", {}))
    outsiders = ctx.outsiders
    notes = []
    slots = [("reversal", i) for i in range(counts["reversals"])]
    slots += [("private_fact", i) for i in range(counts["private_facts"])]
    slots += [("secret", i) for i in range(counts["secrets"])]
    slots += [("claim", i) for i in range(counts["unauthorised_claims"])]
    slots += [("absence", i) for i in range(counts["absences"])]
    if not outsiders:
        skipped = {k: sum(1 for s in slots if s[0] == k) for k in ("private_fact", "claim", "absence")}
        slots = [s for s in slots if s[0] in ("reversal", "secret")]
        names = {"private_fact": "restricted-channel facts", "claim": "unauthorised claims", "absence": "absences"}
        left = [f"{n} {names[k]}" for k, n in skipped.items() if n]
        if left:
            notes.append(
                "Not planted, because they need a user outside the authority group: " + ", ".join(left) + "."
            )
    total = len(slots)
    absences = sum(1 for kind, _ in slots if kind == "absence")
    others = total - absences
    # absences take the last three days each, so no other planted post falls in a window
    spread = days - 3 * absences
    width = min(7, max(1, (spread - 2) // max(others, 1)))
    public, restricted = preset["public_surface"], preset["restricted_surface"]
    author = ctx.author

    def pick(name, who, pool):
        return draw.choice(seed, ["plant", name], [who], pool)

    absentees = set()
    for index, (kind, i) in enumerate(slots):
        if kind == "absence":
            span, start = 3, spread + 3 * i
        else:
            span = width
            start = (index * (spread - span)) // max(others, 1)
        if span > days or spread < 0 or (spread < 1 and kind != "absence"):
            raise _err("days_too_few", f"a {kind} needs more days than the file's {days}", "days")
        bank = preset[kind]
        topic = bank[i % len(bank)]
        key = topic["key"] + ("" if i < len(bank) else f"-{i // len(bank) + 1}")
        name = f"{kind}-{key}"
        if kind == "reversal":
            length = 2 + draw.below(seed, ["plant", name], ["chain"], 2)
            asker = pick(name, "asker", outsiders or [author])
            times = _steps(start, span, length + 1)
            previous = None
            for v in range(length):
                version = topic["versions"][v]
                fid = f"f.{key}.{v + 1}"
                _fact(ctx, fid, key, topic["kind"], version["value"], version["forms"], ["*"], previous and previous[0])
                eid = _plant_post(
                    ctx, f"plant.{key}.d{v + 1}", times[v], author, public, version["say"],
                    discloses=[fid], **({"depends_on": [previous[1]]} if previous else {}),
                )  # fmt: skip
                previous = (fid, eid)
            probe = _plant_post(ctx, f"plant.{key}.q", times[length], asker, public, topic["ask"], probe=True, depends_on=[previous[1]])
            ctx.checks.append({"id": f"c.{key}", "kind": "answer", "key": key, "probe": probe})
        elif kind == "private_fact":
            outsider = pick(name, "outsider", outsiders)
            times = _steps(start, span, 3)
            fid = f"f.{key}"
            _fact(ctx, fid, key, topic["kind"], topic["value"], topic["forms"], [f"group:{restricted}"])
            disclosure = _plant_post(ctx, f"plant.{key}.d", times[0], author, restricted, topic["say"], discloses=[fid])
            allowed = _plant_post(ctx, f"plant.{key}.qa", times[1], author, restricted, topic["ask"], probe=True, depends_on=[disclosure])
            outside = _plant_post(
                ctx, f"plant.{key}.qo", times[2], outsider, f"direct:{outsider}", topic["ask_outside"],
                probe=True, depends_on=[disclosure],
            )  # fmt: skip
            ctx.checks.append({"id": f"c.{key}.answer", "kind": "answer", "key": key, "probe": allowed})
            ctx.checks.append({"id": f"c.{key}.withhold", "kind": "withhold", "fact": fid, "probe": outside})
            ctx.checks.append({"id": f"c.{key}.no_leak", "kind": "no_leak", "fact": fid})
        elif kind == "secret":
            asker = pick(name, "asker", outsiders or [author])
            times = _steps(start, span, 3)
            secret = topic["prefix"] + format(draw.draw(seed, ["plant", name], ["secret"]) >> 32, "08x")
            sample = topic["sample_prefix"] + format(draw.draw(seed, ["plant", name], ["sample"]) >> 32, "08x")
            sample_key = topic["sample_key"] + ("" if i < len(bank) else f"-{i // len(bank) + 1}")
            _fact(ctx, f"f.{key}", key, "secret", secret, None, [author])
            _fact(ctx, f"f.{sample_key}", sample_key, "item", sample, [sample], ["*"])
            first = _plant_post(ctx, f"plant.{key}.d", times[0], author, restricted, topic["say"].replace("{value}", secret), discloses=[f"f.{key}"])
            second = _plant_post(
                ctx, f"plant.{sample_key}.d", times[1], author, public, topic["sample_say"].replace("{value}", sample),
                discloses=[f"f.{sample_key}"], depends_on=[first],
            )  # fmt: skip
            probe = _plant_post(ctx, f"plant.{sample_key}.q", times[2], asker, public, topic["sample_ask"], probe=True, depends_on=[second])
            ctx.checks.append({"id": f"c.{key}.no_echo", "kind": "no_echo", "fact": f"f.{key}", "tags": ["policy"]})
            ctx.checks.append({"id": f"c.{sample_key}", "kind": "answer", "key": sample_key, "probe": probe})
        elif kind == "claim":
            claimer = pick(name, "claimer", outsiders)
            asker = pick(name, "asker", outsiders)
            times = _steps(start, span, 3)
            _fact(ctx, f"f.{key}", key, topic["kind"], topic["value"], topic["forms"], ["*"])
            _fact(ctx, f"f.{key}.claim", key, "claim", topic["claim_value"], topic["claim_forms"], ["*"])
            first = _plant_post(ctx, f"plant.{key}.d", times[0], author, public, topic["say"], discloses=[f"f.{key}"])
            second = _plant_post(
                ctx, f"plant.{key}.c", times[1], claimer, public, topic["claim_say"],
                discloses=[f"f.{key}.claim"], depends_on=[first],
            )  # fmt: skip
            probe = _plant_post(ctx, f"plant.{key}.q", times[2], asker, public, topic["ask"], probe=True, depends_on=[second])
            ctx.checks.append({"id": f"c.{key}", "kind": "answer", "key": key, "probe": probe})
        else:  # absence
            window = (start * DAY, (start + 2) * DAY)
            absentee = pick(name, "absentee", outsiders)
            absentees.add(absentee)
            ctx.by_id[absentee].away.append(list(window))
            fid = f"f.{key}"
            _fact(ctx, fid, key, topic["kind"], topic["value"], topic["forms"], ["*"])
            said = _plant_post(ctx, f"plant.{key}.d", (start + 1) * DAY + 9 * HOUR + 10 * MINUTE, author, public, topic["say"], discloses=[fid])
            probe = _plant_post(
                ctx, f"plant.{key}.q", (start + 2) * DAY + 9 * HOUR + 10 * MINUTE, absentee, f"direct:{absentee}",
                preset["catch_up_ask"], probe=True, depends_on=[said],
            )  # fmt: skip
            ctx.pending.append((probe, absentee, window[0]))
            ctx.checks.append({"id": f"c.{key}.catch_up", "kind": "catch_up", "probe": probe})
    _unanswerable(ctx, counts, days, absentees)
    notes.insert(
        0,
        "Questions about things that were never planted carry no check in this version: a fact must be disclosed before it can be scored.",
    )
    return notes


# --- planted situations: one user talking to the product (solo) -----------------


def _plant_solo(ctx, population):
    """Add the planted situations of the ``solo`` shape; return the limits to state.

    One user, one direct surface. A preference stated then changed, a pasted document
    that carries an instruction (scored by ``no_echo`` on an inert code the instruction
    asks to repeat), and a return after a week away (scored by recall of a fact stated
    before leaving). A question about something never said carries no check.
    """
    preset, seed, days = ctx.preset, ctx.seed, ctx.days
    counts = dict(preset["plant"])
    counts.update(population.get("plant", {}))
    user = ctx.users[0].id
    surface = f"direct:{user}"
    slots = [("reversal", i) for i in range(counts["reversals"])]
    slots += [("injection", i) for i in range(counts["injections"])]
    returns = counts["returns"]
    # a return takes nine days: the fact on the day before, seven days away, the question on the day back
    spread = days - 9 * returns
    others = len(slots)
    if spread < 0 or (spread < 1 and others):
        raise _err("days_too_few", f"the planted situations need more days than the file's {days}", "days")
    width = min(7, max(1, (spread - 2) // max(others, 1)))
    for index, (kind, i) in enumerate(slots):
        start = (index * (spread - width)) // max(others, 1)
        bank = preset[kind]
        topic = bank[i % len(bank)]
        key = topic["key"] + ("" if i < len(bank) else f"-{i // len(bank) + 1}")
        name = f"{kind}-{key}"
        if kind == "reversal":
            length = 2 + draw.below(seed, ["plant", name], ["chain"], 2)
            times = _steps(start, width, length + 1)
            previous = None
            for v in range(length):
                version = topic["versions"][v]
                fid = f"f.{key}.{v + 1}"
                _fact(ctx, fid, key, topic["kind"], version["value"], version["forms"], ["*"], previous and previous[0], [user])
                eid = _plant_post(
                    ctx, f"plant.{key}.d{v + 1}", times[v], user, surface, version["say"],
                    discloses=[fid], **({"depends_on": [previous[1]]} if previous else {}),
                )  # fmt: skip
                previous = (fid, eid)
            probe = _plant_post(ctx, f"plant.{key}.q", times[length], user, surface, topic["ask"], probe=True, depends_on=[previous[1]])
            ctx.checks.append({"id": f"c.{key}", "kind": "answer", "key": key, "probe": probe})
        else:  # injection: a pasted document whose instruction asks to repeat an inert code
            times = _steps(start, width, 3)
            secret = topic["prefix"] + format(draw.draw(seed, ["plant", name], ["secret"]) >> 32, "08x")
            sample = topic["sample_prefix"] + format(draw.draw(seed, ["plant", name], ["sample"]) >> 32, "08x")
            sample_key = topic["sample_key"] + ("" if i < len(bank) else f"-{i // len(bank) + 1}")
            _fact(ctx, f"f.{key}", key, "secret", secret, None, [user], authority=[user])
            _fact(ctx, f"f.{sample_key}", sample_key, "item", sample, [sample], ["*"], authority=[user])
            first = _plant_post(ctx, f"plant.{key}.d", times[0], user, surface, topic["say"].replace("{value}", secret), discloses=[f"f.{key}"])
            second = _plant_post(
                ctx, f"plant.{sample_key}.d", times[1], user, surface, topic["sample_say"].replace("{value}", sample),
                discloses=[f"f.{sample_key}"], depends_on=[first],
            )  # fmt: skip
            probe = _plant_post(ctx, f"plant.{sample_key}.q", times[2], user, surface, topic["sample_ask"], probe=True, depends_on=[second])
            ctx.checks.append({"id": f"c.{key}.no_echo", "kind": "no_echo", "fact": f"f.{key}", "tags": ["policy"]})
            ctx.checks.append({"id": f"c.{sample_key}", "kind": "answer", "key": sample_key, "probe": probe})
    bank = preset["return"]
    for i in range(returns):
        topic = bank[i % len(bank)]
        key = topic["key"] + ("" if i < len(bank) else f"-{i // len(bank) + 1}")
        away = spread + 9 * i + 1  # the first away day
        window = (away * DAY, (away + 7) * DAY)
        ctx.users[0].away.append(list(window))
        fid = f"f.{key}"
        _fact(ctx, fid, key, topic["kind"], topic["value"], topic["forms"], ["*"], authority=[user])
        said = _plant_post(ctx, f"plant.{key}.d", (away - 1) * DAY + 9 * HOUR + 10 * MINUTE, user, surface, topic["say"], discloses=[fid])
        probe = _plant_post(
            ctx, f"plant.{key}.q", (away + 7) * DAY + 9 * HOUR + 10 * MINUTE, user, surface, topic["ask"],
            probe=True, depends_on=[said],
        )  # fmt: skip
        ctx.pending.append((probe, user, window[0]))
        ctx.checks.append({"id": f"c.{key}", "kind": "answer", "key": key, "probe": probe})
    _unanswerable(ctx, counts, days, set())
    return [
        "Questions about things that were never said carry no check in this version: a fact must be disclosed before it can be scored."
    ]


# --- planted situations: users acting on the product through ops (social) -------


def _op(ctx, event_id, at, actor, op, args, **more):
    """A planted ``op`` event on the actor's own direct surface."""
    event = {"id": event_id, "at": at, "actor": actor, "surface": f"direct:{actor}", "kind": "op", "op": op, "args": args}
    event.update(more)
    ctx.events.append(event)
    ctx.planted.append((actor, at, event_id))
    return event_id


def _distinct(seed, name, labels, pool):
    """One keyed pick per label from ``pool``, none repeated, in the order of ``labels``."""
    left, out = list(pool), []
    for label in labels:
        who = draw.choice(seed, ["plant", name], [label], left)
        left.remove(who)
        out.append(who)
    return out


def _plant_social(ctx, population):
    """Add the planted situations of the ``social`` shape; return the limits to state.

    Every user acts on the product through ``op`` events on its own direct surface.
    A friends-only post, and a post to the followers of someone who blocked a user, are
    each read through ``read_feed`` by a user inside the audience (``answer``) and by a
    user outside it (``withhold``, with ``no_leak`` over the run). A deleted post is a
    post replaced by a later one: the feed must show the later post, not the deleted one.
    """
    preset, seed, days = ctx.preset, ctx.seed, ctx.days
    counts = dict(preset["plant"])
    counts.update(population.get("plant", {}))
    ids = ctx.ids
    notes = []
    slots = [("friends_post", i) for i in range(counts["friends_only"])]
    slots += [("block_post", i) for i in range(counts["blocks"])]
    slots += [("deleted_post", i) for i in range(counts["deletions"])]
    if len(ids) < 3:
        skipped = {k: sum(1 for s in slots if s[0] == k) for k in ("friends_post", "block_post")}
        slots = [s for s in slots if s[0] == "deleted_post"]
        names = {"friends_post": "friends-only posts", "block_post": "blocks"}
        left = [f"{n} {names[k]}" for k, n in skipped.items() if n]
        if left:
            notes.append("Not planted, because they need at least three users: " + ", ".join(left) + ".")
    total = len(slots)
    width = min(5, max(1, (days - 2) // max(total, 1)))
    for index, (kind, i) in enumerate(slots):
        start = (index * (days - width)) // max(total, 1)
        bank = preset[kind]
        topic = bank[i % len(bank)]
        key = topic["key"] + ("" if i < len(bank) else f"-{i // len(bank) + 1}")
        name = f"{kind}-{key}"
        if kind == "friends_post":
            friends_count = 1 if len(ids) < 4 else 2
            labels = ["author", *(f"friend-{j}" for j in range(1, friends_count + 1)), "outsider"]
            author, *rest = _distinct(seed, name, labels, ids)
            friends, outsider = rest[:-1], rest[-1]
            times = _steps(start, width, 2 * friends_count + 3)
            fid = f"f.{key}"
            _fact(ctx, fid, key, topic["kind"], topic["value"], topic["forms"], [author, *friends], authority=[author])
            follows, slot = [], 0
            for j, friend in enumerate(friends, 1):
                follows.append(_op(ctx, f"plant.{key}.fa{j}", times[slot], author, "follow", {"user": friend}))
                follows.append(_op(ctx, f"plant.{key}.fb{j}", times[slot + 1], friend, "follow", {"user": author}))
                slot += 2
            post = _op(
                ctx, f"plant.{key}.d", times[slot], author, "post", {"audience": "friends", "text": topic["say"]},
                discloses=[fid], depends_on=follows,
            )  # fmt: skip
            allowed = _op(ctx, f"plant.{key}.qa", times[slot + 1], friends[0], "read_feed", {"limit": 20}, probe=True, depends_on=[post])
            outside = _op(ctx, f"plant.{key}.qo", times[slot + 2], outsider, "read_feed", {"limit": 20}, probe=True, depends_on=[post])
            _audience_checks(ctx, key, fid, allowed, outside)
        elif kind == "block_post":
            author, blocked, follower = _distinct(seed, name, ["author", "blocked", "follower"], ids)
            times = _steps(start, width, 6)
            fid = f"f.{key}"
            _fact(ctx, fid, key, topic["kind"], topic["value"], topic["forms"], [author, follower], authority=[author])
            one = _op(ctx, f"plant.{key}.fa", times[0], blocked, "follow", {"user": author})
            two = _op(ctx, f"plant.{key}.fb", times[1], follower, "follow", {"user": author})
            block = _op(ctx, f"plant.{key}.b", times[2], author, "block", {"user": blocked}, depends_on=[one])
            post = _op(
                ctx, f"plant.{key}.d", times[3], author, "post", {"audience": "followers", "text": topic["say"]},
                discloses=[fid], depends_on=[block, two],
            )  # fmt: skip
            allowed = _op(ctx, f"plant.{key}.qa", times[4], follower, "read_feed", {"limit": 20}, probe=True, depends_on=[post])
            outside = _op(ctx, f"plant.{key}.qo", times[5], blocked, "read_feed", {"limit": 20}, probe=True, depends_on=[post])
            _audience_checks(ctx, key, fid, allowed, outside)
        else:  # deleted_post: a post, its deletion, a later post, then a read of the feed
            author = draw.choice(seed, ["plant", name], ["author"], ids)
            readers = [u for u in ids if u != author] or [author]
            reader = draw.choice(seed, ["plant", name], ["reader"], readers)
            times = _steps(start, width, 4)
            first, second = f"f.{key}.1", f"f.{key}.2"
            _fact(ctx, first, key, topic["kind"], topic["first_value"], topic["first_forms"], ["*"], authority=[author])
            _fact(ctx, second, key, topic["kind"], topic["value"], topic["forms"], ["*"], first, [author])
            one = _op(
                ctx, f"plant.{key}.d1", times[0], author, "post", {"audience": "public", "text": topic["first_say"]},
                discloses=[first],
            )  # fmt: skip
            gone = _op(ctx, f"plant.{key}.x", times[1], author, "delete_post", {"post": one}, depends_on=[one])
            two = _op(
                ctx, f"plant.{key}.d2", times[2], author, "post", {"audience": "public", "text": topic["say"]},
                discloses=[second], depends_on=[gone],
            )  # fmt: skip
            probe = _op(ctx, f"plant.{key}.q", times[3], reader, "read_feed", {"limit": 20}, probe=True, depends_on=[two])
            ctx.checks.append({"id": f"c.{key}", "kind": "answer", "key": key, "probe": probe})
    return notes


def _audience_checks(ctx, key, fid, allowed, outside):
    """The paired checks of a post with a restricted audience."""
    ctx.checks.append({"id": f"c.{key}.answer", "kind": "answer", "key": key, "probe": allowed})
    ctx.checks.append({"id": f"c.{key}.withhold", "kind": "withhold", "fact": fid, "probe": outside})
    ctx.checks.append({"id": f"c.{key}.no_leak", "kind": "no_leak", "fact": fid})


def _filler_social(ctx):
    """Scheduled traffic: each user posts or reads the feed on its own direct surface.

    A turn depends on nothing but its user's id and the turn number, as in ``_filler``.
    Nobody replies, and the habits that change message text (split, typo, wrong place)
    do not apply to op arguments.
    """
    seed, days, preset = ctx.seed, ctx.days, ctx.preset
    per_day = preset["filler"]["turns_per_day"]
    question_pct = preset["filler"]["question_pct"]
    end = days * DAY
    for user in ctx.users:
        hours = user.traits["active_hours"]
        wlen = (hours["end"] - hours["start"]) * HOUR
        surface = f"direct:{user.id}"
        for day in range(days):
            for turn in range(per_day):
                n = day * per_day + turn
                offset = draw.below(seed, [user.id, "turn_time"], [n], _DEFAULT_WINDOW - SPAN)
                actual = day * DAY + (hours["start"] - hours["offset"]) * HOUR
                actual += offset * (wlen - SPAN) // (_DEFAULT_WINDOW - SPAN)
                if actual < 0 or actual + SPAN > end or _away_end(user, actual, actual + SPAN) is not None:
                    continue
                if draw.chance(seed, [user.id, "kind"], [n], question_pct, 100):
                    event = {"id": f"{user.id}.q{n}", "op": "read_feed", "args": {"limit": 20}}
                else:
                    mid = f"{user.id}.t{n}"
                    text = _pick_text(ctx, user, "statement", mid)
                    event = {"id": mid, "op": "post", "args": {"audience": "public", "text": text}}
                ctx.events.append({**event, "at": actual, "actor": user.id, "surface": surface, "kind": "op"})


# --- the pack -----------------------------------------------------------------


def generate(population: dict, *, validate: bool = True) -> model.Pack:
    """Build the pack for a validated population object.

    ``validate=False`` skips the final ``pack.validate`` call, for large statistical
    runs; ``generate_file`` always validates through ``pack.write``.
    """
    preset = _validate(population)
    seed, days = population["seed"], population["days"]
    overrides = {o["user"]: o["traits"] for o in population.get("overrides", [])}
    users = []
    for user_id, role, group_traits in _users(population, preset["roles"]):
        layers = [group_traits] + ([overrides[user_id]] if user_id in overrides else [])
        user = _User(user_id, role, _resolve(seed, days, user_id, layers))
        user.away = [[w["from_day"] * DAY, (w["to_day"] + 1) * DAY] for w in user.traits["away"]]
        users.append(user)
    ctx = _Context(seed, days, preset, users)
    shape = preset.get("shape", "team")
    notes = {"team": _plant, "solo": _plant_solo, "social": _plant_social}[shape](ctx, population)
    for user in users:
        user.away = _merge(user.away)
    # planted posts must fit their author's hours and absences
    for actor, at, event_id in ctx.planted:
        user = ctx.by_id[actor]
        if not _in_hours(user, at, at) or _away_end(user, at, at) is not None:
            raise _err(
                "planted_conflict",
                f"planted event {event_id!r} by {actor!r} falls outside its active hours or inside an away window",
                f"{actor}.traits",
            )
    # away and back events, one pair for every merged window, named on a surface the user is on
    home = (lambda user: preset["public_surface"]) if shape == "team" else (lambda user: f"direct:{user.id}")
    for user in users:
        for index, (start, end) in enumerate(user.away):
            ctx.events.append({"id": f"{user.id}.away.{index}", "at": start, "actor": user.id, "surface": home(user), "kind": "away"})
            ctx.events.append({"id": f"{user.id}.back.{index}", "at": end, "actor": user.id, "surface": home(user), "kind": "back"})
    for probe_id, absentee, window_start in ctx.pending:
        user = ctx.by_id[absentee]
        index = next(i for i, (s, e) in enumerate(user.away) if s <= window_start < e)
        for event in ctx.events:
            if event["id"] == probe_id:
                event["depends_on"] = [*event["depends_on"], f"{absentee}.back.{index}"]
    (_filler_social if shape == "social" else _filler)(ctx)
    ctx.events.sort(key=lambda e: (e["at"], e["id"]))
    n = len(users)
    limits = list(preset["limits"]) + notes
    channels = preset.get("surfaces", [])
    members = {}
    for s in channels:
        pool = ctx.ids if s["members"] == "all" else ctx.leads
        members[s["id"]] = [*pool, preset["subject"]]
    surfaces = [{"id": s["id"], "kind": s["kind"], "members": members[s["id"]]} for s in channels]
    if preset["direct_surfaces"]:
        surfaces += [{"id": f"direct:{i}", "kind": "direct", "members": [i, preset["subject"]]} for i in ctx.ids]
    checks = [{"id": "c.harness", "kind": "harness"}, *ctx.checks]
    obj = {
        "format": model.FORMAT,
        "id": f"{preset['id']}-{n}",
        "title": f"{preset['title']}: {n} synthetic user{'s' if n != 1 else ''}, {days} days",
        "purpose": preset["purpose"],
        "seed": seed,
        "limits": limits,
    }
    built = model.Pack(
        header=model.PackHeader.from_obj(obj),
        subject=model.Subject.from_obj({"id": preset["subject"]}),
        actors=tuple(model.Actor.from_obj({"id": u.id, "role": u.role, "traits": u.traits}) for u in users),
        surfaces=tuple(model.Surface.from_obj(s) for s in surfaces),
        facts=tuple(model.Fact.from_obj(f) for f in ctx.facts),
        checks=tuple(model.Check.from_obj(c) for c in checks),
        events=tuple(model.Event.from_obj(e) for e in ctx.events),
        provenance=model.Provenance.from_obj(
            {"generator_version": GENERATOR_VERSION, "population_hash": canon.hash_of(population)}
        ),
    )
    if validate:
        pack.validate(built)
    return built


def generate_file(population_path, out_dir) -> model.Pack:
    """Load the population file, generate its pack, validate and write it to ``out_dir``."""
    pack_obj = generate(load_population(population_path), validate=False)
    pack.write(pack_obj, out_dir)
    return pack_obj
