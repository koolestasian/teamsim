"""Tests for the population generator: the population file, the team preset and the pack."""

import copy
import pathlib
import re
import tempfile
import time
import unittest

from teamsim import canon, generate, match, pack
from teamsim.generate import PopulationError

ROOT = pathlib.Path(__file__).parent.parent
POPULATION = ROOT / "populations" / "team-ten.toml"
PACK_DIR = ROOT / "packs" / "team-ten"
DOC = ROOT / "docs" / "spec" / "population-format.md"

# Pinned: the hash of packs/team-ten. A change to the generator, the preset or the
# population changes it on purpose, never by accident.
TEAM_TEN_HASH = "afd80b27536a354bf5ba67171e2b0c64f8162287d5871c5c5f767e0fec8814bd"

BASE = {
    "format": 1,
    "preset": "team",
    "seed": "t-1",
    "days": 21,
    "groups": [
        {"role": "lead", "count": 1},
        {"role": "member", "count": 9},
    ],
}


def population(**changes):
    obj = copy.deepcopy(BASE)
    obj.update(copy.deepcopy(changes))
    return obj


def traits_of(pack_obj, user):
    return next(a for a in pack_obj.actors if a.id == user).traits


class LoadPopulationTests(unittest.TestCase):
    def write(self, text):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = pathlib.Path(folder.name) / "population.toml"
        path.write_bytes(text.encode("utf-8"))
        return path

    def code(self, obj):
        with self.assertRaises(PopulationError) as caught:
            generate._validate(obj)
        return caught.exception

    def test_team_ten_file_loads(self):
        obj = generate.load_population(POPULATION)
        self.assertEqual(obj["preset"], "team")
        self.assertEqual(sum(g["count"] for g in obj["groups"]), 10)

    def test_missing_and_malformed_files(self):
        with self.assertRaises(PopulationError) as caught:
            generate.load_population(ROOT / "populations" / "nope.toml")
        self.assertEqual(caught.exception.code, "missing_file")
        with self.assertRaises(PopulationError) as caught:
            generate.load_population(self.write("format = ["))
        self.assertEqual(caught.exception.code, "bad_toml")
        with self.assertRaises(PopulationError) as caught:
            generate.load_population(self.write('format = 1\nseed = "x"\nfloat = 1.5\n'))
        self.assertEqual(caught.exception.code, "bad_type")

    def test_every_documented_key_is_accepted(self):
        obj = population(
            groups=[
                {
                    "role": "lead",
                    "count": 1,
                    "traits": {
                        "bundle": "careful",
                        "reply_median_s": {"min": 30, "max": 300},
                        "split_pct": 10,
                        "short_pct": 20,
                        "typo_pct": 1,
                        "wrong_place_pct": 2,
                        "probe_pct": 3,
                        "away": [{"from_day": 1, "to_day": 2}],
                        "active_hours": {"start": 8, "end": 17, "offset": -8},
                    },
                },
                {"role": "member", "count": 2},
            ],
            overrides=[{"user": "member-2", "traits": {"typo_pct": 9}}],
            plant={
                "reversals": 1,
                "private_facts": 1,
                "secrets": 1,
                "unauthorised_claims": 1,
                "absences": 1,
                "unanswerable": 1,
            },
        )
        generate._validate(obj)

    def test_rejections_carry_their_code_and_path(self):
        cases = [
            (population(extra=1), "unknown_key", "extra"),
            (population(format=2), "bad_format", "format"),
            (population(format="1"), "bad_type", "format"),
            (population(preset="nope"), "unknown_preset", "preset"),
            (population(preset=3), "bad_type", "preset"),
            (population(seed=""), "bad_value", "seed"),
            (population(seed=4), "bad_type", "seed"),
            (population(days=0), "bad_value", "days"),
            (population(days=True), "bad_type", "days"),
            (population(days=1.5), "bad_type", "days"),
            (population(groups=[]), "bad_value", "groups"),
            (population(groups=[{"role": "boss", "count": 1}]), "unknown_role", "groups[0].role"),
            (population(groups=[{"role": "lead"}]), "missing_key", "groups[0].count"),
            (population(groups=[{"role": "lead", "count": 0}]), "bad_value", "groups[0].count"),
            (population(groups=[{"role": "lead", "count": 1001}]), "bad_value", "groups[0].count"),
            (
                population(groups=[{"role": "lead", "count": 600}, {"role": "member", "count": 600}]),
                "too_many_users",
                "groups",
            ),
            (
                population(groups=[{"role": "lead", "count": 1, "traits": {"bundle": "relaxed"}}]),
                "unknown_bundle",
                "groups[0].traits.bundle",
            ),
            (
                population(groups=[{"role": "lead", "count": 1, "traits": {"mood": 3}}]),
                "unknown_key",
                "groups[0].traits.mood",
            ),
            (
                population(groups=[{"role": "lead", "count": 1, "traits": {"typo_pct": 101}}]),
                "bad_value",
                "groups[0].traits.typo_pct",
            ),
            (
                population(groups=[{"role": "lead", "count": 1, "traits": {"typo_pct": "5"}}]),
                "bad_type",
                "groups[0].traits.typo_pct",
            ),
            (
                population(groups=[{"role": "lead", "count": 1, "traits": {"split_pct": {"min": 50, "max": 40}}}]),
                "bad_range",
                "groups[0].traits.split_pct",
            ),
            (
                population(groups=[{"role": "lead", "count": 1, "traits": {"split_pct": {"min": 5}}}]),
                "missing_key",
                "groups[0].traits.split_pct.max",
            ),
            (
                population(groups=[{"role": "lead", "count": 1, "traits": {"reply_median_s": 0}}]),
                "bad_value",
                "groups[0].traits.reply_median_s",
            ),
            (
                population(groups=[{"role": "lead", "count": 1, "traits": {"away": [{"from_day": 5, "to_day": 4}]}}]),
                "bad_range",
                "groups[0].traits.away[0]",
            ),
            (
                population(groups=[{"role": "lead", "count": 1, "traits": {"away": [{"from_day": 5, "to_day": 21}]}}]),
                "bad_value",
                "groups[0].traits.away[0].to_day",
            ),
            (
                population(groups=[{"role": "lead", "count": 1, "traits": {"active_hours": {"start": 10, "end": 10}}}]),
                "bad_range",
                "groups[0].traits.active_hours",
            ),
            (
                population(groups=[{"role": "lead", "count": 1, "traits": {"active_hours": {"start": 9}}}]),
                "missing_key",
                "groups[0].traits.active_hours.end",
            ),
            (population(overrides=[{"user": "member-10", "traits": {}}]), "unknown_user", "overrides[0].user"),
            (
                population(overrides=[{"user": "lead-1", "traits": {}}, {"user": "lead-1", "traits": {}}]),
                "duplicate_user",
                "overrides[1].user",
            ),
            (population(overrides=[{"user": "lead-1"}]), "missing_key", "overrides[0].traits"),
            (population(plant={"reversals": -1}), "bad_value", "plant.reversals"),
            (population(plant={"stories": 1}), "unknown_key", "plant.stories"),
            (population(plant={"secrets": "1"}), "bad_type", "plant.secrets"),
        ]
        for obj, code, path in cases:
            with self.subTest(code=code, path=path):
                error = self.code(obj)
                self.assertEqual((error.code, error.path), (code, path))

    def test_documented_rule_codes_match_the_code(self):
        text = DOC.read_text(encoding="utf-8")
        documented = set(re.findall(r"^\| `([a-z_]+)` \|", text.split("<!-- rules:start -->")[1].split("<!-- rules:end -->")[0], re.M))
        self.assertEqual(documented, set(generate.POPULATION_RULES))

    def test_presets_list(self):
        self.assertEqual(generate.PRESETS, ("team",))


class BundleTests(unittest.TestCase):
    def test_bundles_expand_to_their_documented_numbers(self):
        expected = {
            "careful": {"reply_median_s": 240, "split_pct": 10, "typo_pct": 0, "wrong_place_pct": 0},
            "hurried": {"reply_median_s": 20, "split_pct": 60, "typo_pct": 8},
            "away-often": {"away": [{"from_day": 3, "to_day": 4}, {"from_day": 10, "to_day": 11}, {"from_day": 17, "to_day": 18}]},
        }
        self.assertEqual(generate.BUNDLES, expected)
        text = DOC.read_text(encoding="utf-8")
        for name, numbers in expected.items():
            traits = {"bundle": name}
            obj = population(
                groups=[{"role": "member", "count": 1, "traits": traits}], plant={k: 0 for k in generate._PLANT_KEYS}
            )
            drawn = traits_of(generate.generate(obj), "member-1")
            want = dict(generate.TRAIT_DEFAULTS)
            want["active_hours"] = {"start": 9, "end": 18, "offset": 0}
            want.update(numbers)
            self.assertEqual(drawn, want, name)
            self.assertNotIn("bundle", drawn)
            self.assertIn(f"`{name}`", text)

    def test_explicit_numbers_beat_the_bundle_and_an_override_beats_the_group(self):
        obj = population(
            groups=[{"role": "member", "count": 2, "traits": {"bundle": "hurried", "typo_pct": 1}}],
            overrides=[{"user": "member-2", "traits": {"bundle": "careful"}}],
            plant={k: 0 for k in generate._PLANT_KEYS},
        )
        built = generate.generate(obj)
        self.assertEqual(traits_of(built, "member-1")["typo_pct"], 1)
        self.assertEqual(traits_of(built, "member-1")["split_pct"], 60)
        self.assertEqual(traits_of(built, "member-2")["reply_median_s"], 240)

    def test_a_range_gives_one_draw_per_user_inside_it(self):
        obj = population(
            groups=[{"role": "member", "count": 12, "traits": {"reply_median_s": {"min": 30, "max": 300}}}],
            plant={k: 0 for k in generate._PLANT_KEYS},
        )
        values = [traits_of(generate.generate(obj), f"member-{i}")["reply_median_s"] for i in range(1, 13)]
        self.assertTrue(all(30 <= v <= 300 for v in values))
        self.assertGreater(len(set(values)), 6)

    def test_bundle_away_windows_are_clipped_to_the_days(self):
        obj = population(
            days=12,
            groups=[{"role": "member", "count": 1, "traits": {"bundle": "away-often"}}],
            plant={k: 0 for k in generate._PLANT_KEYS},
        )
        windows = traits_of(generate.generate(obj), "member-1")["away"]
        self.assertEqual(windows, [{"from_day": 3, "to_day": 4}, {"from_day": 10, "to_day": 11}])


class TeamTenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.population = generate.load_population(POPULATION)
        cls.pack = generate.generate(cls.population)

    def test_shape(self):
        obj = self.population
        self.assertEqual(obj["days"], 21)
        roles = [a.role for a in self.pack.actors]
        self.assertEqual(roles.count("lead"), 1)
        self.assertEqual(roles.count("member"), 9)
        self.assertTrue(any(type(v) is dict for g in obj["groups"] for v in g.get("traits", {}).values()))
        override = obj["overrides"][0]
        self.assertTrue(override["traits"]["away"])
        self.assertEqual([s.id for s in self.pack.surfaces if s.kind == "channel"], ["general", "planning", "random", "leads"])
        self.assertEqual(sum(1 for s in self.pack.surfaces if s.kind == "direct"), 10)

    def test_every_check_kind_and_the_planted_situations(self):
        kinds = {}
        for check in self.pack.checks:
            kinds[check.kind] = kinds.get(check.kind, 0) + 1
        self.assertEqual(kinds["harness"], 1)
        for kind in ("answer", "withhold", "no_leak", "no_echo", "catch_up"):
            self.assertGreaterEqual(kinds[kind], 1, kind)
        self.assertTrue(any(f.supersedes for f in self.pack.facts))
        self.assertTrue(any(f.kind == "claim" for f in self.pack.facts))
        self.assertTrue(any(f.kind == "secret" for f in self.pack.facts))
        self.assertTrue(any(a.startswith("group:") for f in self.pack.facts for a in f.audience))
        chains = [sum(1 for f in self.pack.facts if f.key == k) for k in {f.key for f in self.pack.facts if f.supersedes}]
        self.assertTrue(all(c in (2, 3) for c in chains))

    def test_traits_are_numbers_not_bundle_names(self):
        for actor in self.pack.actors:
            self.assertNotIn("bundle", actor.traits)
            self.assertEqual(
                set(actor.traits),
                {"reply_median_s", "split_pct", "short_pct", "typo_pct", "wrong_place_pct", "probe_pct", "away", "active_hours"},
            )
        text = (PACK_DIR / "pack.toml").read_text(encoding="utf-8")
        for name in generate.BUNDLES:
            self.assertNotIn(name, text)

    def test_the_lead_took_the_careful_bundle(self):
        lead = traits_of(self.pack, "lead-1")
        for key, value in generate.BUNDLES["careful"].items():
            self.assertEqual(lead[key], value)

    def test_the_override_is_applied(self):
        member = traits_of(self.pack, "member-3")
        self.assertEqual(member["away"], [{"from_day": 8, "to_day": 12}])
        self.assertEqual(member["wrong_place_pct"], 10)

    def test_provenance(self):
        self.assertEqual(self.pack.provenance.generator_version, generate.GENERATOR_VERSION)
        self.assertEqual(self.pack.provenance.population_hash, canon.hash_of(self.population))

    def test_the_stated_limits_are_in_the_pack(self):
        limits = self.pack.header.limits
        self.assertTrue(any("templated" in line for line in limits))
        self.assertTrue(any("single-user" in line for line in limits))
        self.assertTrue(any("few hundred users" in line for line in limits))
        self.assertTrue(any("never planted carry no check" in line for line in limits))

    def test_validates_and_is_byte_identical_twice(self):
        pack.validate(self.pack)
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            generate.generate_file(POPULATION, one)
            generate.generate_file(POPULATION, two)
            for name in (pack.TOML_FILE, pack.TIMELINE_FILE):
                self.assertEqual((pathlib.Path(one) / name).read_bytes(), (pathlib.Path(two) / name).read_bytes())

    def test_the_committed_pack_equals_a_fresh_generation_and_its_hash_is_pinned(self):
        with tempfile.TemporaryDirectory() as fresh:
            generate.generate_file(POPULATION, fresh)
            for name in (pack.TOML_FILE, pack.TIMELINE_FILE):
                self.assertEqual((pathlib.Path(fresh) / name).read_bytes(), (PACK_DIR / name).read_bytes(), name)
        loaded = pack.load(PACK_DIR)
        pack.validate(loaded)
        self.assertEqual(pack.pack_hash(loaded), TEAM_TEN_HASH)
        self.assertEqual(pack.pack_hash(self.pack), TEAM_TEN_HASH)

    def test_the_committed_pack_holds_no_carriage_return(self):
        for name in (pack.TOML_FILE, pack.TIMELINE_FILE):
            self.assertNotIn(b"\r", (PACK_DIR / name).read_bytes())

    def test_the_formatting_of_the_population_file_does_not_change_the_pack(self):
        reordered = {k: self.population[k] for k in reversed(list(self.population))}
        self.assertEqual(pack.pack_hash(generate.generate(reordered)), TEAM_TEN_HASH)

    def test_generate_and_validate_take_under_ten_seconds(self):
        started = time.perf_counter()
        built = generate.generate(copy.deepcopy(self.population))
        pack.validate(built)
        elapsed = time.perf_counter() - started
        print(f"[team-ten generate+validate {elapsed:.2f}s]")
        self.assertLess(elapsed, 10)


class CountTests(unittest.TestCase):
    def test_one_ten_and_a_hundred_users_each_give_a_valid_pack(self):
        for total in (1, 10, 100):
            with self.subTest(users=total):
                groups = [{"role": "lead", "count": 1}]
                if total > 1:
                    groups.append({"role": "member", "count": total - 1})
                built = generate.generate(population(groups=groups))
                pack.validate(built)
                self.assertEqual(len(built.actors), total)

    def test_members_only_populations_work_too(self):
        for total in (1, 10):
            with self.subTest(users=total):
                built = generate.generate(population(groups=[{"role": "member", "count": total}]))
                pack.validate(built)

    def test_one_user_plants_only_what_one_user_can_carry_and_says_so(self):
        built = generate.generate(population(groups=[{"role": "lead", "count": 1}]))
        kinds = {c.kind for c in built.checks}
        self.assertEqual(kinds, {"harness", "answer", "no_echo"})
        self.assertFalse(any(f.kind == "claim" for f in built.facts))
        self.assertTrue(any("need a user outside the authority group" in line for line in built.header.limits))
        self.assertTrue(any(f.supersedes for f in built.facts))

    def test_two_users_carry_every_situation(self):
        built = generate.generate(population(groups=[{"role": "lead", "count": 1}, {"role": "member", "count": 1}]))
        self.assertEqual({c.kind for c in built.checks}, {"harness", "answer", "withhold", "no_leak", "no_echo", "catch_up"})
        self.assertFalse(any("need a user outside" in line for line in built.header.limits))

    def test_too_few_days_for_the_situations_is_an_error(self):
        with self.assertRaises(PopulationError) as caught:
            generate.generate(population(days=2))
        self.assertEqual(caught.exception.code, "days_too_few")

    def test_a_planted_event_in_an_away_window_is_a_conflict_not_a_silent_drop(self):
        obj = population(overrides=[{"user": "lead-1", "traits": {"away": [{"from_day": 0, "to_day": 20}]}}])
        with self.assertRaises(PopulationError) as caught:
            generate.generate(obj)
        self.assertEqual(caught.exception.code, "planted_conflict")

    def test_the_same_population_gives_the_same_pack_and_a_new_seed_gives_another(self):
        one = pack.pack_hash(generate.generate(population()))
        self.assertEqual(one, pack.pack_hash(generate.generate(population())))
        self.assertNotEqual(one, pack.pack_hash(generate.generate(population(seed="t-2"))))


class PlantedTextTests(unittest.TestCase):
    """Traits never alter a planted fact's forms: they act on filler text only."""

    def test_planted_events_are_never_split_typoed_or_reposted(self):
        extreme = {"split_pct": 100, "typo_pct": 100, "wrong_place_pct": 100, "short_pct": 0}
        obj = population(
            groups=[{"role": "lead", "count": 1, "traits": extreme}, {"role": "member", "count": 6, "traits": extreme}]
        )
        built = generate.generate(obj)
        ids = {e.id for e in built.events}
        planted = [e for e in built.events if e.id.startswith("plant.")]
        self.assertGreater(len(planted), 10)
        for event in planted:
            for suffix in (".w", ".d", ".f1", ".e"):
                self.assertNotIn(event.id + suffix, ids)
        targets = {e.target for e in built.events if e.target}
        self.assertFalse(any(e.id in targets for e in planted))
        facts = {f.id: f for f in built.facts}
        for event in planted:
            for fact_id in event.discloses or ():
                fact = facts[fact_id]
                self.assertIn(fact.value, event.text)
                self.assertTrue(match.contains(event.text, fact.value))
        # while filler text did take the habits
        self.assertTrue(any(e.id.endswith(".e") for e in built.events))
        self.assertTrue(any(e.id.endswith(".w") for e in built.events))
        self.assertTrue(any(e.id.endswith(".f1") for e in built.events))

    def test_every_planted_value_is_found_in_its_disclosure_by_the_matcher(self):
        built = generate.generate(population())
        disclosures = {}
        for event in built.events:
            for fact_id in event.discloses or ():
                disclosures[fact_id] = event
        self.assertEqual(set(disclosures), {f.id for f in built.facts})
        for fact in built.facts:
            self.assertTrue(match.contains(disclosures[fact.id].text, fact.value), fact.id)

    def test_secrets_are_inert_and_derived_from_the_seed(self):
        one = generate.generate(population(seed="a"))
        two = generate.generate(population(seed="b"))
        secrets = lambda p: [f.value for f in p.facts if f.kind == "secret"]
        self.assertEqual(len(secrets(one)), 1)
        self.assertNotEqual(secrets(one), secrets(two))
        self.assertRegex(secrets(one)[0], r"^teamsim-secret-[0-9a-f]{8}$")

    def test_the_look_alike_has_the_shape_of_the_secret_and_is_not_one(self):
        built = generate.generate(population())
        sample = [f for f in built.facts if f.key == "sample-code"][0]
        self.assertRegex(sample.value, r"^teamsim-sample-[0-9a-f]{8}$")
        self.assertEqual(sample.kind, "item")
        self.assertTrue(any(c.kind == "answer" and c.key == "sample-code" for c in built.checks))

    def test_unanswerable_questions_carry_no_check(self):
        built = generate.generate(population())
        questions = [e for e in built.events if e.id.startswith("plant.un")]
        self.assertEqual(len(questions), 2)
        probes = {c.probe for c in built.checks if c.probe}
        for event in questions:
            self.assertNotIn(event.id, probes)
            self.assertFalse(event.probe)
            self.assertFalse(event.discloses)

    def test_a_reply_depends_on_nothing_that_can_be_missing(self):
        # no generated event uses a trigger or an after-anchor
        built = generate.generate(population())
        for event in built.events:
            self.assertEqual(type(event.when).__name__, "At")

    def test_preset_text_is_fictional_and_plain(self):
        preset = generate._preset("team")
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

        walk(preset)
        for text in strings:
            self.assertNotRegex(text, r"https?://|@|\\|[A-Za-z]:/")
        self.assertEqual(len(set(preset["text"]["statement_long"])), len(preset["text"]["statement_long"]))


if __name__ == "__main__":
    unittest.main()
