"""Regression tests for the second review of populations, presets, packs, controls, examples,
the command line and the report. Each class names the finding it guards."""

import copy
import pathlib
import re
import unittest

from teamsim import checks, controls, engine, generate, pack
from teamsim.generate import PopulationError
from teamsim.subject import InProcess
from tests.social_ideal import Ideal

ROOT = pathlib.Path(__file__).parent.parent


def social(count=10, **changes):
    obj = {"format": 1, "preset": "social", "seed": "o-1", "days": 21, "groups": [{"role": "member", "count": count}]}
    obj.update(copy.deepcopy(changes))
    return obj


def failures(built, subject):
    verdicts = checks.evaluate(built, engine.run(built, InProcess(subject)))
    return [(v.check, v.verdict, v.reason) for v in verdicts if v.verdict != "pass"]


class SocialAudienceTests(unittest.TestCase):
    def test_a_correct_product_passes_every_check_for_200_seeds_and_plant_counts_one_to_three(self):
        bad = {}
        for n in range(200):
            count = 1 + n % 3
            population = social(seed=f"s{n}", plant={"friends_only": count, "blocks": count, "deletions": count})
            built = generate.generate(population)
            found = failures(built, Ideal())
            if found:
                bad[population["seed"]] = found
        self.assertEqual(bad, {})

    def test_the_users_of_different_situations_are_disjoint(self):
        for n in range(40):
            built = generate.generate(social(seed=f"d{n}", plant={"friends_only": 2, "blocks": 2, "deletions": 2}))
            seen = {}
            for event in built.events:
                if event.id.startswith("plant.") and event.kind == "op":
                    situation = event.id.split(".")[1]
                    seen.setdefault(event.actor, set()).add(situation)
            # a situation's key is the second id part: one user, one situation
            self.assertTrue(all(len(s) == 1 for s in seen.values()), (n, seen))

    def test_a_pool_that_runs_out_plants_fewer_and_the_limits_say_so(self):
        built = generate.generate(social(5, plant={"friends_only": 3, "blocks": 3, "deletions": 3}))
        self.assertTrue(any(line.startswith("Not planted") and "users" in line for line in built.header.limits), built.header.limits)
        self.assertEqual(failures(built, Ideal()), [])


class FeedLimitTests(unittest.TestCase):
    def test_a_correct_product_passes_every_check_with_a_hundred_users(self):
        built = generate.generate(social(100))
        self.assertEqual(failures(built, Ideal()), [])

    def test_a_correct_product_passes_every_check_with_thirty_users(self):
        built = generate.generate(social(30, seed="s80"))
        self.assertEqual(failures(built, Ideal()), [])


def population_file(name):
    return generate.load_population(ROOT / "populations" / f"{name}.toml")


def with_seed(population, seed):
    obj = copy.deepcopy(population)
    obj["seed"] = seed
    return obj


class PlantedRolesFitTheirUsersTests(unittest.TestCase):
    def test_the_team_population_generates_for_200_seeds(self):
        base = population_file("team-ten")
        for n in range(200):
            with self.subTest(seed=f"s{n}"):
                generate.generate(with_seed(base, f"s{n}"), validate=False)

    def test_the_social_population_generates_for_200_seeds_and_counts_three_and_twenty(self):
        base = population_file("social-ten")
        for count in (3, 10, 20):
            for n in range(200):
                obj = with_seed(base, f"s{n}")
                obj["groups"][0]["count"] = count
                with self.subTest(count=count, seed=f"s{n}"):
                    generate.generate(obj, validate=False)

    def test_one_member_with_shifted_hours_or_often_away_does_not_stop_generation(self):
        for traits in ({"active_hours": {"start": 9, "end": 18, "offset": -8}}, {"bundle": "away-often"}):
            for member in range(1, 10):
                obj = population_file("team-ten")
                obj["overrides"] = [{"user": f"member-{member}", "traits": traits}]
                with self.subTest(member=member, traits=traits):
                    generate.generate(obj)

    def test_a_planted_role_never_goes_to_a_user_who_cannot_act_at_that_time(self):
        obj = population_file("team-ten")
        obj["overrides"] = [{"user": "member-1", "traits": {"active_hours": {"start": 9, "end": 18, "offset": -8}}}]
        built = generate.generate(obj)  # pack.validate refuses a planted post outside its author's hours
        self.assertEqual(built.header.id, "team-10")

    def test_a_population_whose_every_member_is_unavailable_still_raises_planted_conflict(self):
        for traits in ({"active_hours": {"start": 9, "end": 18, "offset": -8}}, {"bundle": "away-often"}):
            obj = population_file("team-ten")
            obj["groups"][1]["traits"].update(traits)
            obj.pop("overrides")
            with self.subTest(traits=traits):
                with self.assertRaises(PopulationError) as caught:
                    generate.generate(obj)
                self.assertEqual(caught.exception.code, "planted_conflict")


class DeafControlTests(unittest.TestCase):
    """``defect:deaf`` ignores one surface: it must not use what it heard only there."""

    @classmethod
    def setUpClass(cls):
        cls.team = pack.load(ROOT / "packs" / "team-ten")

    def test_a_catch_up_needing_a_fact_heard_only_on_the_deaf_surface_is_missed(self):
        self.assertEqual(
            controls.expected("defect:deaf", self.team)["c.handover-owner.catch_up"], ("fail", "missed")
        )

    def test_the_observed_run_agrees_with_the_expectation_on_every_pack(self):
        for name in ("minimal", "team-ten", "solo", "social-ten"):
            built = pack.load(ROOT / "packs" / name)
            lines = [x for x in controls.validate(built) if "not exercised" not in x and "not detected" not in x]
            with self.subTest(pack=name):
                self.assertEqual(lines, [])

    def test_the_deaf_control_differs_from_the_oracle_only_through_the_deaf_surface(self):
        want = controls.expected("defect:deaf", self.team)
        oracle = controls.expected("oracle", self.team)
        self.assertNotEqual(want, oracle)
        self.assertEqual(controls.matrix(self.team)["defect:deaf"], want)


def solo(**traits):
    return {
        "format": 1,
        "preset": "solo",
        "seed": "tr-1",
        "days": 21,
        "groups": [{"role": "user", "count": 1, "traits": traits}],
    }


def team_ten():
    return generate.generate(population_file("team-ten"))


class StatedLimitsTests(unittest.TestCase):
    def test_the_team_limits_say_replies_can_answer_an_opener_that_was_never_posted(self):
        text = " ".join(team_ten().header.limits)
        self.assertIn("never posted", text)
        self.assertIn("wrong place", text)

    def test_the_social_limits_say_probe_pct_has_no_effect(self):
        text = " ".join(generate.generate(social()).header.limits)
        self.assertIn("probe_pct", text)

    def test_the_solo_limits_state_what_was_never_said_once(self):
        limits = generate.generate(solo()).header.limits
        self.assertEqual(sum("never said" in line for line in limits), 1, limits)


class SoloDaysTests(unittest.TestCase):
    def test_solo_needs_fourteen_virtual_days(self):
        for days in (1, 8, 13):
            with self.subTest(days=days):
                with self.assertRaises(PopulationError) as caught:
                    generate.generate(dict(solo(), days=days, plant={"returns": 0}))
                self.assertEqual(caught.exception.code, "days_too_few")
        self.assertEqual(generate.generate(dict(solo(), days=14)).header.id, "solo-1")


class SoloTraitEffectTests(unittest.TestCase):
    """The habits that change text act in the solo preset, which has one user and one surface."""

    def test_split_pct_makes_fragments_in_solo(self):
        none = generate.generate(solo(split_pct=0), validate=False)
        many = generate.generate(solo(split_pct=100), validate=False)
        fragments = lambda built: sum(1 for e in built.events if re.search(r"\.f\d+$", e.id))
        self.assertEqual(fragments(none), 0)
        self.assertGreater(fragments(many), 20)

    def test_typo_pct_makes_corrections_in_solo(self):
        none = generate.generate(solo(typo_pct=0), validate=False)
        many = generate.generate(solo(typo_pct=100), validate=False)
        edits = lambda built: sum(1 for e in built.events if e.kind == "edit")
        self.assertEqual(edits(none), 0)
        self.assertGreater(edits(many), 20)


if __name__ == "__main__":
    unittest.main()
