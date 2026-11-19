"""Effect and isolation tests for the eight v0 traits (population format, section 3).

Each effect test generates 200 packs, one per seed, at two or more values of a trait
and computes its statistic from the generated timeline alone. A share must lie inside
the 99% Wilson interval of the observed count; the other traits have exact
assertions. Each isolation test changes one user's trait and compares every other
user's events byte for byte.
"""

import copy
import math
import re
import unittest

from teamsim import canon, generate

SEEDS = 200
Z = 2.5758293035489004  # the two-sided 99% normal quantile
NO_PLANT = {key: 0 for key in generate._PLANT_KEYS}
DAY = generate.DAY
NON_POSTS = ("away", "back")


def population(seed, member=None, lead=None, **more):
    obj = {
        "format": 1,
        "preset": "team",
        "seed": seed,
        "days": 10,
        "groups": [
            {"role": "lead", "count": 1, **({"traits": lead} if lead else {})},
            {"role": "member", "count": 1, **({"traits": member} if member else {})},
        ],
        "plant": NO_PLANT,
    }
    obj.update(more)
    return obj


def build(obj):
    return generate.generate(obj, validate=False)


def wilson(hits, total):
    """The 99% Wilson score interval of a share, as floats (tests may use floats)."""
    p = hits / total
    z2 = Z * Z
    centre = (p + z2 / (2 * total)) / (1 + z2 / total)
    half = Z * math.sqrt(p * (1 - p) / total + z2 / (4 * total * total)) / (1 + z2 / total)
    return centre - half, centre + half


def main_ids(events, user):
    pattern = re.compile(rf"^{re.escape(user)}\.(?:[tqx]\d+|r\.[a-z0-9-]+\.\d+)$")
    return [e for e in events if e.actor == user and pattern.match(e.id)]


def messages(built, user):
    """Each message of ``user`` as ``(main event, whole text, set of ids that belong to it)``."""
    by_id = {e.id: e for e in built.events}
    out = []
    for main in main_ids(built.events, user):
        text, extras, index = main.text, set(), 1
        while f"{main.id}.f{index}" in by_id:
            text += " " + by_id[f"{main.id}.f{index}"].text
            extras.add(f"{main.id}.f{index}")
            index += 1
        out.append((main, text, extras))
    return out


class Wilson(unittest.TestCase):
    def test_the_interval_is_sane(self):
        low, high = wilson(50, 100)
        self.assertLess(low, 0.5)
        self.assertGreater(high, 0.5)
        self.assertAlmostEqual(wilson(0, 100)[0], 0, places=9)


class EffectTests(unittest.TestCase):
    def collect(self, member, lead=None, **more):
        return [build(population(f"s{index}", member=member, lead=lead, **more)) for index in range(SEEDS)]

    def assert_share(self, hits, total, percent, label):
        self.assertGreater(total, 500, label)
        low, high = wilson(hits, total)
        self.assertLessEqual(low - 1e-12, percent / 100, f"{label}: {hits}/{total}")
        self.assertGreaterEqual(high + 1e-12, percent / 100, f"{label}: {hits}/{total}")

    # reply_median_s
    def test_reply_median_follows_the_parameter_and_is_monotone(self):
        medians = []
        for value in (30, 90, 300):
            delays = []
            for built in self.collect({"reply_median_s": value, "active_hours": {"start": 0, "end": 24}}):
                opened = {e.id: e.when.ms for e in built.events if e.actor == "lead-1"}
                for e in built.events:
                    match = re.fullmatch(r"member-1\.r\.lead-1\.(\d+)", e.id)
                    if match:
                        for letter in "tqx":
                            start = opened.get(f"lead-1.{letter}{match.group(1)}")
                            if start is not None:
                                delays.append(e.when.ms - start)
            delays.sort()
            self.assertGreater(len(delays), 1000)
            median = delays[len(delays) // 2]
            medians.append(median)
            self.assertLessEqual(abs(median - value * 1000), value * 1000 * 26 // 100, f"median {median} for {value}")
        self.assertLess(medians[0], medians[1])
        self.assertLess(medians[1], medians[2])

    def test_reply_delays_have_a_heavy_tail(self):
        delays = []
        for built in self.collect({"reply_median_s": 60, "active_hours": {"start": 0, "end": 24}}):
            opened = {e.id: e.when.ms for e in built.events if e.actor == "lead-1"}
            for e in built.events:
                match = re.fullmatch(r"member-1\.r\.lead-1\.(\d+)", e.id)
                if match:
                    for letter in "tqx":
                        if f"lead-1.{letter}{match.group(1)}" in opened:
                            delays.append(e.when.ms - opened[f"lead-1.{letter}{match.group(1)}"])
        delays.sort()
        self.assertGreater(delays[len(delays) * 95 // 100], 4 * delays[len(delays) // 2])

    # split_pct
    def test_split_share_among_longer_messages(self):
        for value in (20, 70):
            hits = total = 0
            for built in self.collect({"split_pct": value}):
                for main, text, extras in messages(built, "member-1"):
                    if len(text.split()) > 3:
                        total += 1
                        hits += bool(extras)
            self.assert_share(hits, total, value, f"split {value}")

    def test_short_messages_are_never_split(self):
        for built in self.collect({"split_pct": 100}):
            for main, text, extras in messages(built, "member-1"):
                if len(text.split()) <= 3:
                    self.assertFalse(extras)
                else:
                    self.assertTrue(1 <= len(extras) <= 3)

    # short_pct
    def test_short_share_of_messages(self):
        for value in (29, 80):
            hits = total = 0
            for built in self.collect({"short_pct": value}):
                for main, text, extras in messages(built, "member-1"):
                    total += 1
                    hits += len(text.split()) <= 3
            self.assert_share(hits, total, value, f"short {value}")

    # typo_pct
    def test_typo_share_and_the_correction(self):
        for value in (5, 40):
            hits = total = 0
            for built in self.collect({"typo_pct": value}):
                edits = {e.target: e for e in built.events if e.kind == "edit" and e.actor == "member-1"}
                posts = {e.id: e for e in built.events}
                for main, text, extras in messages(built, "member-1"):
                    total += 1
                    if main.id in edits:
                        hits += 1
                        edit = edits[main.id]
                        self.assertGreater(edit.when.ms, main.when.ms)
                        self.assertNotEqual(edit.text, main.text)
                        self.assertEqual(sorted(edit.text), sorted(main.text))
                        self.assertEqual(edit.surface, main.surface)
            self.assert_share(hits, total, value, f"typo {value}")

    def test_no_typos_at_zero(self):
        for built in self.collect({"typo_pct": 0}):
            self.assertFalse(any(e.kind == "edit" for e in built.events if e.actor == "member-1"))

    # wrong_place_pct
    def test_wrong_place_share_and_the_repost(self):
        for value in (10, 40):
            hits = total = 0
            for built in self.collect({"wrong_place_pct": value}):
                by_id = {e.id: e for e in built.events}
                for main, text, extras in messages(built, "member-1"):
                    total += 1
                    wrong = by_id.get(f"{main.id}.w")
                    if wrong is not None:
                        hits += 1
                        delete = by_id[f"{main.id}.d"]
                        self.assertEqual((delete.kind, delete.target), ("delete", wrong.id))
                        self.assertNotEqual(wrong.surface, main.surface)
                        self.assertLess(wrong.when.ms, delete.when.ms)
                        self.assertLess(delete.when.ms, main.when.ms)
            self.assert_share(hits, total, value, f"wrong place {value}")

    def test_no_wrong_place_posts_at_zero(self):
        for built in self.collect({"wrong_place_pct": 0}):
            self.assertFalse(any(e.id.endswith(".w") for e in built.events))

    # probe_pct
    def test_probe_share_among_questions(self):
        for value in (20, 60):
            hits = total = 0
            for built in self.collect({"probe_pct": value}):
                for e in built.events:
                    match = re.fullmatch(r"member-1\.([qx])\d+", e.id)
                    if match:
                        total += 1
                        hits += match.group(1) == "x"
            self.assertGreater(total, 300)
            low, high = wilson(hits, total)
            self.assertLessEqual(low - 1e-12, value / 100, f"{hits}/{total}")
            self.assertGreaterEqual(high + 1e-12, value / 100, f"{hits}/{total}")

    def test_no_unplanted_questions_at_zero(self):
        for built in self.collect({"probe_pct": 0}):
            self.assertFalse(any(re.fullmatch(r"member-1\.x\d+", e.id) for e in built.events))

    # away
    def test_nothing_is_posted_inside_an_away_window(self):
        windows = [(2, 4), (7, 8)]
        away = [{"from_day": a, "to_day": b} for a, b in windows]
        inside_without = inside_lead = 0
        for built in self.collect({"away": away}):
            mine = [e for e in built.events if e.actor == "member-1"]
            self.assertTrue(mine)
            for e in mine:
                if e.kind in NON_POSTS:
                    continue
                self.assertFalse(any(a * DAY <= e.when.ms < (b + 1) * DAY for a, b in windows), e.id)
            kinds = [e.kind for e in mine if e.kind in NON_POSTS]
            self.assertEqual(kinds.count("away"), 2)
            self.assertEqual(kinds.count("back"), 2)
            inside_lead += sum(
                1 for e in built.events if e.actor == "lead-1" and any(a * DAY <= e.when.ms < (b + 1) * DAY for a, b in windows)
            )
        for built in self.collect({}):
            inside_without += sum(
                1
                for e in built.events
                if e.actor == "member-1" and any(a * DAY <= e.when.ms < (b + 1) * DAY for a, b in windows)
            )
        self.assertGreater(inside_without, 1000)  # the same days are busy without the trait
        self.assertGreater(inside_lead, 1000)  # and others keep posting: the user misses what happens

    def test_away_and_back_events_bound_the_window(self):
        built = build(population("w", member={"away": [{"from_day": 2, "to_day": 4}]}))
        events = {e.id: e for e in built.events}
        self.assertEqual(events["member-1.away.0"].when.ms, 2 * DAY)
        self.assertEqual(events["member-1.back.0"].when.ms, 5 * DAY)

    # active_hours
    def test_nothing_is_posted_outside_active_hours(self):
        for hours in ({"start": 8, "end": 12, "offset": 0}, {"start": 9, "end": 17, "offset": -8}, {"start": 6, "end": 20, "offset": 5}):
            used = 0
            for built in self.collect({"active_hours": hours}):
                for e in built.events:
                    if e.actor != "member-1" or e.kind in NON_POSTS:
                        continue
                    used += 1
                    local = (e.when.ms + hours["offset"] * 3_600_000) % DAY
                    self.assertGreaterEqual(local, hours["start"] * 3_600_000, (hours, e.id))
                    self.assertLess(local, hours["end"] * 3_600_000, (hours, e.id))
            self.assertGreater(used, 3000)

    def test_a_narrow_window_still_gets_posts_on_every_day(self):
        built = build(population("n", member={"active_hours": {"start": 8, "end": 10}}))
        days = {e.when.ms // DAY for e in built.events if e.actor == "member-1" and e.id.startswith("member-1.")}
        self.assertGreaterEqual(len(days), 8)


class IsolationTests(unittest.TestCase):
    """Changing one user's trait leaves every other user's events byte-identical."""

    CHANGES = {
        "reply_median_s": 900,
        "split_pct": 100,
        "short_pct": 100,
        "typo_pct": 60,
        "wrong_place_pct": 60,
        "probe_pct": 100,
        "away": [{"from_day": 3, "to_day": 5}, {"from_day": 9, "to_day": 10}],
        "active_hours": {"start": 12, "end": 20, "offset": 0},
    }

    def lines(self, built):
        out = {}
        for event in built.events:
            out.setdefault(event.actor, []).append(canon.canon(event.to_obj()))
        return out

    def base(self, seed, planted):
        obj = {
            "format": 1,
            "preset": "team",
            "seed": seed,
            "days": 14,
            "groups": [{"role": "lead", "count": 1}, {"role": "member", "count": 14}],
        }
        if not planted:
            obj["plant"] = NO_PLANT
        return obj

    def bystander(self, built):
        """A member who authors no planted event."""
        authors = {e.actor for e in built.events if e.id.startswith("plant.")}
        return next(a.id for a in built.actors if a.role == "member" and a.id not in authors)

    def check(self, trait, planted):
        for seed in ("iso-a", "iso-b", "iso-c"):
            obj = self.base(f"{seed}-{trait}", planted)
            before = generate.generate(obj)
            user = self.bystander(before)
            changed = copy.deepcopy(obj)
            changed["overrides"] = [{"user": user, "traits": {trait: self.CHANGES[trait]}}]
            after = generate.generate(changed)
            old, new = self.lines(before), self.lines(after)
            self.assertNotEqual(old[user], new[user], f"{trait} left {user} unchanged")
            for actor in old:
                if actor != user:
                    self.assertEqual(old[actor], new[actor], f"{trait} on {user} moved {actor}")
            self.assertEqual(set(old), set(new) | ({user} if user not in new else set()))
            self.assertEqual(before.facts, after.facts)
            self.assertEqual(before.checks, after.checks)

    def test_each_trait_in_isolation_without_planted_events(self):
        for trait in self.CHANGES:
            with self.subTest(trait=trait):
                self.check(trait, planted=False)

    def test_each_trait_in_isolation_with_planted_events(self):
        for trait in self.CHANGES:
            with self.subTest(trait=trait):
                self.check(trait, planted=True)

    def test_adding_a_user_leaves_the_existing_users_planted_text_alone(self):
        small = generate.generate(
            {"format": 1, "preset": "team", "seed": "grow", "days": 14, "groups": [{"role": "lead", "count": 1}, {"role": "member", "count": 3}]}
        )
        big = generate.generate(
            {"format": 1, "preset": "team", "seed": "grow", "days": 14, "groups": [{"role": "lead", "count": 1}, {"role": "member", "count": 4}]}
        )
        # the lead's own turns do not depend on how many others exist
        own = lambda p: [canon.canon(e.to_obj()) for e in p.events if e.actor == "lead-1" and re.fullmatch(r"lead-1\.[tqx]\d+", e.id)]
        self.assertEqual(own(small), own(big))


if __name__ == "__main__":
    unittest.main()
