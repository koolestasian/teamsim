"""Regression tests for the second review of populations, presets, packs, controls, examples,
the command line and the report. Each class names the finding it guards."""

import copy
import pathlib
import unittest

from teamsim import checks, engine, generate
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


if __name__ == "__main__":
    unittest.main()
