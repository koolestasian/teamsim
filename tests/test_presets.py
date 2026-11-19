"""Tests for the solo and social presets: their populations, committed packs and planted situations.

The team preset has its own tests in ``test_generate.py``. Here every planted situation of the
population specification's section 4 is read back from a generated pack, and a small toy
subject (a product that keeps posts and follows) is run through the engine and the checks to
show that the checks can be passed and failed.
"""

import copy
import pathlib
import re
import tempfile
import time
import unittest

from teamsim import checks, engine, generate, match, pack
from teamsim.generate import PopulationError
from tests.fakes import FakeSession, done, post

ROOT = pathlib.Path(__file__).parent.parent

# Pinned: the hash of each committed pack. A change to the generator, a preset or a population
# changes it on purpose, never by accident.
SOLO_HASH = "584b0fc42ff7511266604001517ec739ad493a8d96527dd5635bf8da7e0d312e"
SOCIAL_TEN_HASH = "eef012e948131cf4cbc9383b45a81c0ea9cfbbd5544d240534fd183828000940"

PACKS = {
    "solo": (ROOT / "populations" / "solo.toml", ROOT / "packs" / "solo", SOLO_HASH),
    "social-ten": (ROOT / "populations" / "social-ten.toml", ROOT / "packs" / "social-ten", SOCIAL_TEN_HASH),
}


def solo(**changes):
    obj = {"format": 1, "preset": "solo", "seed": "s-1", "days": 21, "groups": [{"role": "user", "count": 1}]}
    obj.update(copy.deepcopy(changes))
    return obj


def social(count=10, **changes):
    obj = {"format": 1, "preset": "social", "seed": "o-1", "days": 21, "groups": [{"role": "member", "count": count}]}
    obj.update(copy.deepcopy(changes))
    return obj


def events_by_id(built):
    return {e.id: e for e in built.events}


def checks_by_id(built):
    return {c.id: c for c in built.checks}


class CommittedPackTests(unittest.TestCase):
    def test_each_committed_pack_loads_validates_and_has_its_pinned_hash(self):
        for name, (_, directory, expected) in PACKS.items():
            with self.subTest(pack=name):
                loaded = pack.load(directory)
                pack.validate(loaded)
                self.assertEqual(pack.pack_hash(loaded), expected)

    def test_two_generations_are_byte_identical_and_equal_the_committed_directory(self):
        for name, (population, directory, _) in PACKS.items():
            with self.subTest(pack=name), tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
                generate.generate_file(population, one)
                generate.generate_file(population, two)
                for file in (pack.TOML_FILE, pack.TIMELINE_FILE):
                    first = (pathlib.Path(one) / file).read_bytes()
                    self.assertEqual(first, (pathlib.Path(two) / file).read_bytes())
                    self.assertEqual(first, (directory / file).read_bytes(), file)
                    self.assertNotIn(b"\r", first)

    def test_the_hash_does_not_depend_on_the_spelling_of_the_population_file(self):
        for name, (population, _, expected) in PACKS.items():
            with self.subTest(pack=name):
                obj = generate.load_population(population)
                reordered = {k: obj[k] for k in reversed(list(obj))}
                self.assertEqual(pack.pack_hash(generate.generate(reordered)), expected)

    def test_generation_and_validation_take_under_ten_seconds(self):
        for name, (population, _, _) in PACKS.items():
            with self.subTest(pack=name):
                obj = generate.load_population(population)
                started = time.perf_counter()
                pack.validate(generate.generate(obj))
                elapsed = time.perf_counter() - started
                print(f"[{name} generate+validate {elapsed:.2f}s]")
                self.assertLess(elapsed, 10)

    def test_the_provenance_names_the_population_and_the_header_the_preset(self):
        for name, (population, directory, _) in PACKS.items():
            with self.subTest(pack=name):
                loaded = pack.load(directory)
                obj = generate.load_population(population)
                self.assertEqual(loaded.provenance.population_hash, generate.canon.hash_of(obj))
                self.assertEqual(loaded.header.id, f"{obj['preset']}-{sum(g['count'] for g in obj['groups'])}")


class PresetListTests(unittest.TestCase):
    def test_presets_are_listed_in_the_documented_order(self):
        self.assertEqual(generate.PRESETS, ("social", "solo", "team"))

    def test_preset_text_is_fictional_and_plain(self):
        for name in ("solo", "social"):
            with self.subTest(preset=name):
                strings = []

                def walk(value):
                    if type(value) is str:
                        strings.append(value)
                    elif type(value) is list:
                        for item in value:
                            walk(item)
                    elif type(value) is dict:
                        for item in value.values():
                            walk(item)

                walk(generate._preset(name))
                for text in strings:
                    self.assertNotRegex(text, r"https?://|@|\\|[A-Za-z]:/")
                bank = generate._preset(name)["text"]["statement_long"]
                self.assertEqual(len(set(bank)), len(bank))

    def test_a_preset_for_one_shape_does_not_take_the_plant_keys_of_another(self):
        for obj, key in ((solo(plant={"secrets": 1}), "plant.secrets"), (social(plant={"reversals": 1}), "plant.reversals")):
            with self.assertRaises(PopulationError) as caught:
                generate.generate(obj)
            self.assertEqual((caught.exception.code, caught.exception.path), ("unknown_key", key))

    def test_solo_holds_one_user(self):
        with self.assertRaises(PopulationError) as caught:
            generate.generate(solo(groups=[{"role": "user", "count": 2}]))
        self.assertEqual((caught.exception.code, caught.exception.path), ("bad_value", "groups"))

    def test_roles_of_another_preset_are_rejected(self):
        with self.assertRaises(PopulationError) as caught:
            generate.generate(social(groups=[{"role": "lead", "count": 1}]))
        self.assertEqual(caught.exception.code, "unknown_role")


class CountAndDayTests(unittest.TestCase):
    def test_social_gives_a_valid_pack_for_one_ten_and_a_hundred_users(self):
        for total in (1, 10, 100):
            with self.subTest(users=total):
                built = generate.generate(social(total))
                pack.validate(built)
                self.assertEqual(len(built.actors), total)
                self.assertEqual(len([s for s in built.surfaces if s.kind == "direct"]), total)

    def test_solo_gives_a_valid_pack_for_fourteen_and_thirty_days(self):
        for days in (14, 30):
            with self.subTest(days=days):
                built = generate.generate(solo(days=days))
                pack.validate(built)
                self.assertGreater(max(e.when.ms for e in built.events), (days - 2) * 86_400_000)

    def test_a_hundred_users_take_under_ten_seconds(self):
        started = time.perf_counter()
        pack.validate(generate.generate(social(100)))
        elapsed = time.perf_counter() - started
        print(f"[social 100 users generate+validate {elapsed:.2f}s]")
        self.assertLess(elapsed, 10)

    def test_more_users_add_filler_and_not_new_kinds_of_situation(self):
        small, large = generate.generate(social(10)), generate.generate(social(100))
        self.assertEqual([c.kind for c in small.checks], [c.kind for c in large.checks])
        self.assertEqual(len(small.facts), len(large.facts))
        self.assertGreater(len(large.events), 5 * len(small.events))

    def test_solo_needs_nine_days_for_its_return(self):
        with self.assertRaises(PopulationError) as caught:
            generate.generate(solo(days=8))
        self.assertEqual(caught.exception.code, "days_too_few")
        built = generate.generate(solo(days=8, plant={"returns": 0}))
        pack.validate(built)

    def test_a_seed_changes_the_pack_and_the_same_seed_does_not(self):
        for make in (solo, social):
            with self.subTest(preset=make.__name__):
                one = pack.pack_hash(generate.generate(make()))
                self.assertEqual(one, pack.pack_hash(generate.generate(make())))
                self.assertNotEqual(one, pack.pack_hash(generate.generate(make(seed="other"))))


class SoloSituationTests(unittest.TestCase):
    def setUp(self):
        self.pack = generate.generate(solo())
        self.events = events_by_id(self.pack)
        self.checks = checks_by_id(self.pack)

    def test_one_user_one_direct_surface(self):
        self.assertEqual([a.id for a in self.pack.actors], ["user-1"])
        self.assertEqual([(s.id, s.kind) for s in self.pack.surfaces], [("direct:user-1", "direct")])
        self.assertTrue(all(e.surface == "direct:user-1" for e in self.pack.events))
        self.assertGreaterEqual(max(e.when.ms for e in self.pack.events), 14 * 86_400_000)

    def test_a_preference_is_stated_then_changed_and_answered_with_a_chain(self):
        chains = [f for f in self.pack.facts if f.supersedes]
        self.assertGreaterEqual(len(chains), 2)
        facts = {f.id: f for f in self.pack.facts}
        for fact in chains:
            self.assertEqual(facts[fact.supersedes].key, fact.key)
            self.assertEqual(fact.kind, "preference")
            answers = [c for c in self.pack.checks if c.kind == "answer" and c.key == fact.key]
            self.assertEqual(len(answers), 1)
            self.assertTrue(self.events[answers[0].probe].probe)
        # the question comes after the last change
        for answer in (c for c in self.pack.checks if c.kind == "answer" and c.key in {f.key for f in chains}):
            last = max(
                self.events[e.id].when.ms
                for e in self.pack.events
                if any(facts[d].key == answer.key for d in e.discloses or ())
            )
            self.assertGreater(self.events[answer.probe].when.ms, last)

    def test_a_pasted_document_with_an_instruction_is_scored_by_no_echo_on_an_inert_code(self):
        echo = [c for c in self.pack.checks if c.kind == "no_echo"]
        self.assertEqual(len(echo), 1)
        self.assertEqual(echo[0].tags, ("policy",))
        secret = next(f for f in self.pack.facts if f.id == echo[0].fact)
        self.assertEqual(secret.kind, "secret")
        self.assertRegex(secret.value, r"^teamsim-secret-[0-9a-f]{8}$")
        disclosure = next(e for e in self.pack.events if secret.id in (e.discloses or ()))
        self.assertIn(secret.value, disclosure.text)
        self.assertRegex(disclosure.text, r"(?i)ignore|must repeat")
        # the control that lets a silent subject fail
        self.assertTrue(any(c.kind == "answer" and not any(f.kind == "secret" for f in self.pack.facts if f.key == c.key) for c in self.pack.checks))

    def test_a_return_after_a_week_is_scored_by_recall_of_a_fact_stated_before_leaving(self):
        away = next(e for e in self.pack.events if e.kind == "away")
        back = next(e for e in self.pack.events if e.kind == "back")
        self.assertGreaterEqual(back.when.ms - away.when.ms, 7 * 86_400_000)
        probe = next(e for e in self.pack.events if e.probe and back.id in (e.depends_on or ()))
        said = next(e for e in self.pack.events if e.id in probe.depends_on and e.discloses)
        self.assertLess(said.when.ms, away.when.ms)
        self.assertGreater(probe.when.ms, back.when.ms)
        check = next(c for c in self.pack.checks if c.probe == probe.id)
        self.assertEqual(check.kind, "answer")
        self.assertEqual(check.key, next(f.key for f in self.pack.facts if f.id in said.discloses))
        # nothing the user did falls inside the window
        self.assertFalse([e.id for e in self.pack.events if away.when.ms < e.when.ms < back.when.ms])

    def test_a_question_about_something_never_said_carries_no_check_and_the_limits_say_so(self):
        questions = [e for e in self.pack.events if e.id.startswith("plant.un")]
        self.assertEqual(len(questions), 2)
        probes = {c.probe for c in self.pack.checks if c.probe}
        for event in questions:
            self.assertNotIn(event.id, probes)
            self.assertFalse(event.probe or event.discloses)
        self.assertTrue(any("never said carry no check" in line for line in self.pack.header.limits))
        self.assertTrue(any("not by a catch-up check" in line for line in self.pack.header.limits))

    def test_planted_events_are_whole_and_their_values_are_found_by_the_matcher(self):
        facts = {f.id: f for f in self.pack.facts}
        disclosed = set()
        for event in self.pack.events:
            for fact_id in event.discloses or ():
                disclosed.add(fact_id)
                self.assertTrue(match.contains(event.text, facts[fact_id].value), fact_id)
        self.assertEqual(disclosed, set(facts))
        ids = set(self.events)
        for event in self.pack.events:
            if event.id.startswith("plant."):
                for suffix in (".w", ".d", ".f1", ".e"):
                    self.assertNotIn(event.id + suffix, ids)

    def test_the_code_is_derived_from_the_seed(self):
        one, two = generate.generate(solo(seed="a")), generate.generate(solo(seed="b"))
        values = lambda p: [f.value for f in p.facts if f.kind == "secret"]
        self.assertNotEqual(values(one), values(two))

    def test_the_traits_that_apply_to_one_user_still_act(self):
        habits = {"split_pct": 100, "typo_pct": 100, "short_pct": 0}
        built = generate.generate(solo(groups=[{"role": "user", "count": 1, "traits": habits}]))
        ids = {e.id for e in built.events}
        self.assertTrue(any(i.endswith(".e") for i in ids))
        self.assertTrue(any(i.endswith(".f1") for i in ids))
        self.assertFalse(any(i.endswith(".w") for i in ids))

    def test_a_planted_event_inside_an_away_window_is_a_conflict(self):
        obj = solo(groups=[{"role": "user", "count": 1, "traits": {"away": [{"from_day": 0, "to_day": 20}]}}])
        with self.assertRaises(PopulationError) as caught:
            generate.generate(obj)
        self.assertEqual(caught.exception.code, "planted_conflict")


class SocialSituationTests(unittest.TestCase):
    def setUp(self):
        self.pack = generate.generate(social())
        self.events = events_by_id(self.pack)
        self.facts = {f.id: f for f in self.pack.facts}

    def op(self, name):
        return [e for e in self.pack.events if e.kind == "op" and e.op == name]

    def test_ten_users_each_with_a_direct_surface_and_no_channel(self):
        self.assertEqual(len(self.pack.actors), 10)
        self.assertTrue(all(s.kind == "direct" and len(s.members) == 2 for s in self.pack.surfaces))
        self.assertTrue(all(e.kind in ("op", "away", "back") for e in self.pack.events))
        self.assertTrue(all(e.surface == f"direct:{e.actor}" for e in self.pack.events))

    def test_a_friends_only_post_is_read_inside_and_outside_its_audience(self):
        post_event = next(e for e in self.op("post") if e.args["audience"] == "friends")
        fact = self.facts[post_event.discloses[0]]
        self.assertNotIn("*", fact.audience)
        self.assertTrue(match.contains(post_event.args["text"], fact.value))
        self.assertEqual(fact.authority, (post_event.actor,))
        by_kind = {c.kind: c for c in self.pack.checks if c.id.startswith(f"c.{fact.key}.")}
        self.assertEqual(set(by_kind), {"answer", "withhold", "no_leak"})
        inside, outside = self.events[by_kind["answer"].probe], self.events[by_kind["withhold"].probe]
        self.assertEqual((inside.op, outside.op), ("read_feed", "read_feed"))
        self.assertIn(inside.actor, fact.audience)
        self.assertNotIn(outside.actor, fact.audience)
        self.assertEqual(by_kind["withhold"].fact, fact.id)
        self.assertEqual(by_kind["no_leak"].fact, fact.id)
        # the audience's follows come before the post
        follows = {(e.actor, e.args["user"]) for e in self.op("follow") if e.id in post_event.depends_on}
        for friend in fact.audience[1:]:
            self.assertIn((post_event.actor, friend), follows)
            self.assertIn((friend, post_event.actor), follows)

    def test_a_block_comes_before_the_post_and_the_blocked_user_reads_the_feed(self):
        block = next(e for e in self.op("block"))
        blocked = block.args["user"]
        post_event = next(e for e in self.op("post") if e.args["audience"] == "followers")
        self.assertEqual(post_event.actor, block.actor)
        self.assertIn(block.id, post_event.depends_on)
        self.assertLess(block.when.ms, post_event.when.ms)
        fact = self.facts[post_event.discloses[0]]
        self.assertNotIn(blocked, fact.audience)
        withhold = next(c for c in self.pack.checks if c.kind == "withhold" and c.fact == fact.id)
        probe = self.events[withhold.probe]
        self.assertEqual((probe.actor, probe.op), (blocked, "read_feed"))
        # the blocked user followed the author first
        self.assertTrue(any(e.actor == blocked and e.args["user"] == block.actor for e in self.op("follow")))
        self.assertTrue(any(e.id in block.depends_on and e.actor == blocked for e in self.op("follow")))

    def test_a_deleted_post_is_replaced_and_the_feed_must_show_the_later_post(self):
        gone = next(e for e in self.op("delete_post"))
        deleted = self.events[gone.args["post"]]
        self.assertEqual((deleted.actor, deleted.op), (gone.actor, "post"))
        self.assertIn(deleted.id, gone.depends_on)
        first = self.facts[deleted.discloses[0]]
        second = next(f for f in self.pack.facts if f.supersedes == first.id)
        self.assertEqual(second.key, first.key)
        later = next(e for e in self.pack.events if second.id in (e.discloses or ()))
        self.assertGreater(later.when.ms, gone.when.ms)
        answer = next(c for c in self.pack.checks if c.kind == "answer" and c.key == first.key)
        probe = self.events[answer.probe]
        self.assertEqual(probe.op, "read_feed")
        self.assertGreater(probe.when.ms, later.when.ms)
        self.assertNotEqual(probe.actor, gone.actor)

    def test_every_check_kind_but_the_unused_ones_appears(self):
        self.assertEqual({c.kind for c in self.pack.checks}, {"harness", "answer", "withhold", "no_leak"})

    def test_filler_is_posts_and_feed_reads_and_nobody_replies(self):
        filler = [e for e in self.pack.events if e.kind == "op" and not e.id.startswith("plant.")]
        self.assertGreater(len(filler), 300)
        self.assertEqual({e.op for e in filler}, {"post", "read_feed"})
        for event in filler:
            if event.op == "post":
                self.assertEqual(event.args["audience"], "public")
                self.assertTrue(event.args["text"])
                self.assertFalse(event.discloses or event.probe)
        self.assertFalse(any(".r." in e.id for e in self.pack.events))

    def test_a_population_with_too_few_users_plants_only_what_it_can_carry_and_says_so(self):
        # every situation takes users that no other situation takes
        for total in (1, 2):
            with self.subTest(users=total):
                built = generate.generate(social(total))
                self.assertEqual({c.kind for c in built.checks}, {"harness", "answer"})
                note = next(line for line in built.header.limits if line.startswith("Not planted"))
                self.assertIn("friends-only posts", note)
                self.assertIn("blocks", note)
                self.assertTrue(any(f.supersedes for f in built.facts))
        three = generate.generate(social(3))
        self.assertEqual({c.kind for c in three.checks}, {"harness", "answer", "withhold", "no_leak"})
        note = next(line for line in three.header.limits if line.startswith("Not planted"))
        self.assertNotIn("friends-only posts", note)
        self.assertIn("blocks", note)
        self.assertIn("deleted posts", note)
        ten = generate.generate(social())
        self.assertFalse(any(line.startswith("Not planted") for line in ten.header.limits))

    def test_away_windows_keep_a_user_from_acting(self):
        away = next(a for a in generate.generate(social()).actors if a.id == "member-3")
        self.assertEqual(away.traits["away"], [])
        obj = social(overrides=[{"user": "member-3", "traits": {"away": [{"from_day": 3, "to_day": 4}]}}])
        built = generate.generate(obj)
        inside = [e for e in built.events if e.actor == "member-3" and 3 * 86_400_000 < e.when.ms < 5 * 86_400_000 and e.kind == "op"]
        self.assertEqual(inside, [])
        self.assertTrue(any(e.id == "member-3.back.0" and e.surface == "direct:member-3" for e in built.events))
        pack.validate(built)

    def test_the_limits_state_what_the_pack_cannot_score(self):
        text = " ".join(self.pack.header.limits)
        for phrase in ("defined by this preset", "explicit list of users", "replaced by a later one", "reply_median_s"):
            self.assertIn(phrase, text)

    def test_one_day_is_enough_for_every_situation(self):
        built = generate.generate(social(days=1))
        pack.validate(built)
        self.assertEqual(len([c for c in built.checks if c.kind == "answer"]), 3)


class IsolationTests(unittest.TestCase):
    def test_editing_one_social_user_leaves_the_planted_text_and_other_users_filler_alone(self):
        base = generate.generate(social())
        edited = generate.generate(social(overrides=[{"user": "member-7", "traits": {"short_pct": 100}}]))
        other = lambda p: [e.to_obj() for e in p.events if e.actor != "member-7" and not e.id.startswith("plant.")]
        self.assertEqual(other(base), other(edited))
        self.assertNotEqual(
            [e.to_obj() for e in base.events if e.actor == "member-7"],
            [e.to_obj() for e in edited.events if e.actor == "member-7"],
        )


# --- a toy product, run through the engine and the checks ------------------------


class Feed:
    """A small social product: posts with an audience, follows, blocks and a feed read."""

    def __init__(self, enforce):
        self.enforce = enforce
        self.posts = {}  # event id -> {author, audience, text, deleted}
        self.followers = {}  # user -> set of users following them

    def visible(self, reader, post_):
        if post_["deleted"] and self.enforce:
            return False
        if not self.enforce or post_["author"] == reader or post_["audience"] == "public":
            return True
        followers = self.followers.get(post_["author"], set())
        if post_["audience"] == "followers":
            return reader in followers
        return reader in followers and post_["author"] in self.followers.get(reader, set())

    def handle(self, message):
        if message.get("type") != "event" or message["kind"] != "op":
            return None
        payload = message["payload"]
        actor, args, name = payload["actor"], payload["args"], payload["op"]
        if name == "post":
            self.posts[payload["id"]] = {"author": actor, "audience": args["audience"], "text": args["text"], "deleted": False}
        elif name == "delete_post":
            self.posts[args["post"]]["deleted"] = True
        elif name == "follow":
            self.followers.setdefault(args["user"], set()).add(actor)
        elif name == "block":
            self.followers.setdefault(actor, set()).discard(args["user"])
        elif name == "read_feed":
            shown = [p["text"] for p in self.posts.values() if self.visible(actor, p)]
            return done(post(payload["surface"], " | ".join(shown) or "No posts yet.", reply_to=payload["id"]))
        return None


def run_checks(built, handler):
    entries = engine.run(built, FakeSession(handler, record=False))
    return {v.check: v for v in checks.evaluate(built, entries)}


class ToyProductTests(unittest.TestCase):
    def test_a_product_that_keeps_audiences_and_deletions_passes_every_check(self):
        built = generate.generate(social())
        verdicts = run_checks(built, Feed(enforce=True).handle)
        failed = {k: (v.verdict, v.reason) for k, v in verdicts.items() if v.verdict != "pass"}
        self.assertEqual(failed, {})

    def test_a_product_that_ignores_audiences_and_deletions_fails_the_audience_checks(self):
        built = generate.generate(social())
        verdicts = run_checks(built, Feed(enforce=False).handle)
        by_kind = {}
        for check in built.checks:
            by_kind.setdefault(check.kind, []).append(verdicts[check.id])
        self.assertTrue(all(v.verdict == "fail" and v.reason == "leaked" for v in by_kind["withhold"]))
        self.assertTrue(all(v.verdict == "fail" and v.reason == "leaked" for v in by_kind["no_leak"]))
        # it lists the deleted original beside the current post, so the current value is there
        # (engine spec 6.3: stale means a superseded value and not the current one)
        self.assertEqual((verdicts["c.meetup-post"].verdict, verdicts["c.meetup-post"].reason), ("pass", None))
        self.assertEqual(verdicts["c.harness"].verdict, "pass")

    def test_a_product_that_shows_only_the_oldest_post_fails_the_answer_as_stale(self):
        class OldestOnly(Feed):
            def handle(self, message):
                reply = super().handle(message)
                if reply is not None and message["payload"]["op"] == "read_feed":
                    old = [p["text"] for p in self.posts.values() if "Saturday market" in p["text"]]
                    if old:
                        return done(post(message["payload"]["surface"], old[0], reply_to=message["payload"]["id"]))
                return reply

        built = generate.generate(social())
        verdict = run_checks(built, OldestOnly(enforce=False).handle)["c.meetup-post"]
        self.assertEqual((verdict.verdict, verdict.reason), ("fail", "stale"))

    def test_a_silent_product_fails_every_answer_so_that_withholding_means_something(self):
        built = generate.generate(social())
        verdicts = run_checks(built, None)
        for check in built.checks:
            if check.kind == "answer":
                self.assertEqual((verdicts[check.id].verdict, verdicts[check.id].reason), ("fail", "no_response"))
            if check.kind == "withhold":
                self.assertEqual(verdicts[check.id].verdict, "pass")


def oracle(built, *, secret_echo=False, stale=False):
    """A subject that answers each probe from the pack's facts (a control, not a product)."""
    chains = {}
    for event in built.events:
        for fact_id in event.discloses or ():
            chains.setdefault(next(f.key for f in built.facts if f.id == fact_id), []).append(next(f for f in built.facts if f.id == fact_id))
    answers = {c.probe: c.key for c in built.checks if c.kind == "answer"}
    secrets = [f.value for f in built.facts if f.kind == "secret"]

    def handle(message):
        if message.get("type") != "event":
            return None
        payload = message["payload"]
        text = ""
        key = answers.get(payload["id"])
        if key is not None:
            versions = chains[key]
            text = (versions[0] if stale else versions[-1]).value
        if secret_echo:
            text = " ".join([text, *secrets])
        if not text:
            return None
        return done(post(payload["surface"], text, reply_to=payload["id"]))

    return handle


class ToySoloSubjectTests(unittest.TestCase):
    def test_an_oracle_passes_every_check(self):
        built = generate.generate(solo())
        verdicts = run_checks(built, oracle(built))
        self.assertEqual({k: v.verdict for k, v in verdicts.items() if v.verdict != "pass"}, {})

    def test_a_subject_that_repeats_the_code_fails_the_policy_check(self):
        built = generate.generate(solo())
        verdicts = run_checks(built, oracle(built, secret_echo=True))
        echo = next(c for c in built.checks if c.kind == "no_echo")
        self.assertEqual((verdicts[echo.id].verdict, verdicts[echo.id].reason, verdicts[echo.id].policy), ("fail", "echoed", True))

    def test_a_subject_that_remembers_the_first_version_fails_the_chains(self):
        built = generate.generate(solo())
        verdicts = run_checks(built, oracle(built, stale=True))
        reasons = {v.check: v.reason for v in verdicts.values() if v.verdict == "fail"}
        chain_keys = {f.key for f in built.facts if f.supersedes}
        self.assertEqual(set(reasons), {f"c.{k}" for k in chain_keys})
        self.assertEqual(set(reasons.values()), {"stale"})

    def test_a_silent_subject_fails_recall_after_the_return(self):
        built = generate.generate(solo())
        verdicts = run_checks(built, None)
        self.assertEqual(verdicts["c.dentist-day"].reason, "no_response")
        self.assertEqual(verdicts["c.forum-note.no_echo"].verdict, "pass")


class DocumentTests(unittest.TestCase):
    def test_the_format_document_describes_both_presets_and_their_ops(self):
        text = (ROOT / "docs" / "spec" / "population-format.md").read_text(encoding="utf-8")
        for phrase in ("solo.toml", "social.toml", "delete_post", "read_feed", "friends_only", "injections", "max_users"):
            self.assertIn(phrase, text)
        self.assertNotRegex(text, re.compile(r"Only `team` exists|`solo` and `social` are not defined"))


if __name__ == "__main__":
    unittest.main()
