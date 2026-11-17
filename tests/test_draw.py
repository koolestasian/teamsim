"""Tests for keyed draws: golden vectors, independence, uniformity, rejected input."""

import ast
import hashlib
import itertools
import json
import pathlib
import unittest
from unittest import mock

from teamsim import draw as draw_module
from teamsim.draw import below, chance, choice, draw, order, quantile, weighted

GOLDEN = pathlib.Path(__file__).parent / "golden" / "draw_vectors.json"
CORE = pathlib.Path(__file__).parent.parent / "teamsim"
TWO_64 = 2**64


def reference_draw(seed, scope, purpose):
    """An independent draw: standard-library JSON for the canonical text.

    Valid only for the plain ASCII-and-integer arguments the vectors use, where
    ``json.dumps`` with these options equals the canonical form.
    """
    text = json.dumps(
        ["draw-v1", seed, scope, purpose],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def reference_below(seed, scope, purpose, n):
    """Return (value, attempts) by the rule in the specification."""
    limit = TWO_64 - TWO_64 % n
    attempt = 0
    while True:
        x = reference_draw(seed, scope, purpose + ["try", attempt])
        attempt += 1
        if x < limit:
            return x % n, attempt


def load_vectors():
    with GOLDEN.open(encoding="ascii") as handle:
        return json.load(handle)


class LiteralVectors(unittest.TestCase):
    """Three draws checked against SHA-256 of bytes spelled out in this file.

    The digests were computed with GNU coreutils ``sha256sum`` over the same
    bytes, not with the code under test.
    """

    def check(self, seed, scope, purpose, preimage, digest, result):
        self.assertEqual(hashlib.sha256(preimage).hexdigest(), digest)
        self.assertEqual(int.from_bytes(bytes.fromhex(digest)[:8], "big"), result)
        self.assertEqual(draw(seed, scope, purpose), result)

    def test_short_names(self):
        self.check(
            "s",
            ["a", 1],
            ["p"],
            b'["draw-v1","s",["a",1],["p"]]',
            "2f19150219ca863f45f9ada026a9340ef4721bea570a4aaf278ae5ba52b427cd",
            3393766892967200319,
        )

    def test_empty_everything(self):
        self.check(
            "",
            [],
            [],
            b'["draw-v1","",[],[]]',
            "7d7778490c0eb5e533c7ce99f4ab446bd2d5e01de7f0a43b144858b3bcc38ec0",
            9040827032099796453,
        )

    def test_pack_style_names(self):
        self.check(
            "2026-team-ten",
            ["ana", "e041"],
            ["reply_delay"],
            b'["draw-v1","2026-team-ten",["ana","e041"],["reply_delay"]]',
            "001700385c692db983f8c449c06d7e1426063a79e8e48fe2efc7ddbdbf6f3668",
            6474166532910521,
        )


class GoldenVectors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vectors = load_vectors()

    def test_file_has_every_helper(self):
        self.assertEqual(
            set(self.vectors),
            {"draw", "below", "chance", "choice", "weighted", "order", "quantile"},
        )
        for name, rows in self.vectors.items():
            self.assertGreaterEqual(len(rows), 9, name)

    def test_draw(self):
        for row in self.vectors["draw"]:
            with self.subTest(row=row):
                preimage = bytes.fromhex(row["preimage_hex"])
                digest = hashlib.sha256(preimage).hexdigest()
                self.assertEqual(digest, row["sha256"])
                self.assertEqual(int.from_bytes(bytes.fromhex(digest)[:8], "big"), int(row["result"]))
                text = json.dumps(
                    ["draw-v1", row["seed"], row["scope"], row["purpose"]],
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                self.assertEqual(text.encode("utf-8"), preimage)
                self.assertEqual(
                    draw(row["seed"], row["scope"], row["purpose"]), int(row["result"])
                )

    def test_below(self):
        for row in self.vectors["below"]:
            with self.subTest(row=row):
                n = int(row["n"])
                value, tries = reference_below(row["seed"], row["scope"], row["purpose"], n)
                self.assertEqual((value, tries), (int(row["result"]), row["tries"]))
                self.assertEqual(
                    below(row["seed"], row["scope"], row["purpose"], n), int(row["result"])
                )

    def test_below_vectors_include_rejection(self):
        self.assertTrue(any(row["tries"] > 1 for row in self.vectors["below"]))

    def test_chance(self):
        for row in self.vectors["chance"]:
            with self.subTest(row=row):
                expected = (
                    reference_below(row["seed"], row["scope"], row["purpose"], row["den"])[0]
                    < row["num"]
                )
                self.assertEqual(expected, row["result"])
                self.assertIs(
                    chance(row["seed"], row["scope"], row["purpose"], row["num"], row["den"]),
                    row["result"],
                )

    def test_choice(self):
        for row in self.vectors["choice"]:
            with self.subTest(row=row):
                items = row["items"]
                index = reference_below(row["seed"], row["scope"], row["purpose"], len(items))[0]
                self.assertEqual(items[index], row["result"])
                self.assertEqual(
                    choice(row["seed"], row["scope"], row["purpose"], items), row["result"]
                )

    def test_weighted(self):
        for row in self.vectors["weighted"]:
            with self.subTest(row=row):
                weights = row["weights"]
                r = reference_below(row["seed"], row["scope"], row["purpose"], sum(weights))[0]
                index = 0
                while r >= weights[index]:
                    r -= weights[index]
                    index += 1
                self.assertEqual(index, row["result"])
                self.assertEqual(
                    weighted(row["seed"], row["scope"], row["purpose"], weights), row["result"]
                )

    def test_order(self):
        for row in self.vectors["order"]:
            with self.subTest(row=row):
                items = row["items"]
                base = row["purpose"]
                expected = sorted(
                    items,
                    key=lambda i: (
                        reference_draw(row["seed"], row["scope"], base + ["order", i]),
                        (0, i, "") if type(i) is int else (1, 0, i),
                    ),
                )
                self.assertEqual(expected, row["result"])
                self.assertEqual(
                    order(row["seed"], row["scope"], row["purpose"], items), row["result"]
                )

    def test_quantile(self):
        for row in self.vectors["quantile"]:
            with self.subTest(row=row):
                table = row["table"]
                index = reference_below(row["seed"], row["scope"], row["purpose"], len(table))[0]
                self.assertEqual(table[index], row["result"])
                self.assertEqual(
                    quantile(row["seed"], row["scope"], row["purpose"], table), row["result"]
                )


class Independence(unittest.TestCase):
    """A draw is a function of its own key: nothing else can move it."""

    KEYS = [
        ("seed-a", ["ana", f"e{i:03}"], ["delay", j])
        for i in range(8)
        for j in range(4)
    ] + [("seed-b", ["bo"], ["split"]), ("seed-a", [], [])]

    def results(self, keys):
        return {(s, tuple(c), tuple(p)): draw(s, c, p) for s, c, p in keys}

    def test_extra_draws_change_nothing(self):
        before = self.results(self.KEYS)
        for i in range(50):
            draw("seed-a", ["other", i], ["noise"])
            below("seed-a", ["other", i], ["noise"], 7)
        self.assertEqual(self.results(self.KEYS), before)

    def test_removing_draws_changes_nothing(self):
        full = self.results(self.KEYS)
        for drop in range(len(self.KEYS)):
            kept = self.KEYS[:drop] + self.KEYS[drop + 1 :]
            self.assertEqual(self.results(kept), {k: v for k, v in full.items() if k in self.results(kept)})

    def test_reordering_draws_changes_nothing(self):
        before = self.results(self.KEYS)
        self.assertEqual(self.results(list(reversed(self.KEYS))), before)
        for seed in range(5):
            shuffled = sorted(
                self.KEYS, key=lambda key: draw("shuffle", [seed], [repr(key)])
            )
            self.assertEqual(self.results(shuffled), before)

    def test_helpers_are_pure(self):
        for _ in range(3):
            self.assertEqual(below("s", ["a"], ["p"], 1000), below("s", ["a"], ["p"], 1000))
            self.assertEqual(order("s", ["a"], ["p"], [3, 1, 2]), order("s", ["a"], ["p"], [3, 1, 2]))

    def test_every_part_of_the_key_matters(self):
        base = draw("s", ["a", 1], ["p", 2])
        others = [
            draw("t", ["a", 1], ["p", 2]),
            draw("s", ["b", 1], ["p", 2]),
            draw("s", ["a", 2], ["p", 2]),
            draw("s", ["a", "1"], ["p", 2]),
            draw("s", ["a", 1], ["q", 2]),
            draw("s", ["a", 1], ["p", 3]),
            draw("s", ["a", 1], ["p", "2"]),
            draw("s", ["a"], [1, "p", 2]),
            draw("s", [], ["a", 1, "p", 2]),
        ]
        self.assertNotIn(base, others)
        self.assertEqual(len(set(others)), len(others))

    def test_tuples_and_lists_are_the_same_key(self):
        self.assertEqual(draw("s", ("a", 1), ("p",)), draw("s", ["a", 1], ["p"]))

    def test_below_attempt_zero_is_the_draw_with_a_try_suffix(self):
        # For n = 5 attempt 0 is accepted unless the draw is >= 2**64 - 1.
        x = draw("s", ["a"], ["p", "try", 0])
        self.assertLess(x, TWO_64 - TWO_64 % 5)
        self.assertEqual(below("s", ["a"], ["p"], 5), x % 5)


class NoRandomNoHash(unittest.TestCase):
    """The core never imports ``random`` or calls the built-in ``hash``."""

    def parse(self, name):
        return ast.parse((CORE / name).read_text(encoding="utf-8"), filename=name)

    def test_no_random_import_and_no_builtin_hash(self):
        for name in ("draw.py", "canon.py"):
            tree = self.parse(name)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotEqual(alias.name.split(".")[0], "random", name)
                elif isinstance(node, ast.ImportFrom):
                    self.assertNotEqual((node.module or "").split(".")[0], "random", name)
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotEqual(node.func.id, "hash", name)
                elif isinstance(node, ast.Name):
                    self.assertNotEqual(node.id, "hash", name)
                    self.assertNotEqual(node.id, "random", name)

    def test_draw_module_has_no_state(self):
        # Nothing mutable at module level: constants only.
        tree = self.parse("draw.py")
        for node in tree.body:
            if isinstance(node, ast.Assign) and node.targets[0].id != "__all__":
                self.assertIsInstance(node.value, (ast.Constant, ast.BinOp))


class Frequency(unittest.TestCase):
    def test_below_7_over_100000_draws(self):
        """Counts of ``below(7)`` stay within 600 of the mean.

        With n = 100,000 and p = 1/7, the count of each value has mean 14,285.7
        and standard deviation sqrt(n p (1 - p)) = 110.5. A tolerance of 600 is
        5.4 standard deviations, so an unbiased source would fall outside it for
        any one value with probability below 1e-7. The draws are fixed by the
        seed, so this test passes or fails identically on every run; the
        tolerance is wide enough that it only catches a gross bias (a modulo
        bias on a 64-bit word is about 1e-19 and cannot be seen at this size).
        """
        counts = [0] * 7
        for i in range(100_000):
            counts[below("frequency", ["run"], ["seven", i], 7)] += 1
        self.assertEqual(sum(counts), 100_000)
        for value, count in enumerate(counts):
            with self.subTest(value=value):
                self.assertLessEqual(abs(count - 100_000 / 7), 600)

    def test_low_bits_and_high_bits_are_unbiased(self):
        ones_low = sum(draw("bits", ["x"], [i]) & 1 for i in range(10_000))
        ones_high = sum(draw("bits", ["x"], [i]) >> 63 for i in range(10_000))
        # sd = 50; tolerance 300 is six sd.
        self.assertLessEqual(abs(ones_low - 5_000), 300)
        self.assertLessEqual(abs(ones_high - 5_000), 300)


class RejectionBranch(unittest.TestCase):
    def test_rejected_attempts_are_skipped(self):
        # For n = 3, 2**64 mod 3 = 1, so only 2**64 - 1 is rejected.
        script = [TWO_64 - 1, TWO_64 - 1, 8]
        calls = []

        def fake(seed, scope, purpose):
            calls.append(list(purpose))
            return script[len(calls) - 1]

        with mock.patch.object(draw_module, "draw", fake):
            self.assertEqual(below("s", ["a"], ["p"], 3), 8 % 3)
        self.assertEqual(
            calls,
            [["p", "try", 0], ["p", "try", 1], ["p", "try", 2]],
        )

    def test_accepted_boundary(self):
        limit = TWO_64 - TWO_64 % 3
        with mock.patch.object(draw_module, "draw", side_effect=[limit - 1]):
            self.assertEqual(below("s", ["a"], ["p"], 3), (limit - 1) % 3)
        with mock.patch.object(draw_module, "draw", side_effect=[limit, 4]):
            self.assertEqual(below("s", ["a"], ["p"], 3), 1)

    def test_power_of_two_never_rejects(self):
        with mock.patch.object(draw_module, "draw", side_effect=[TWO_64 - 1]) as fake:
            self.assertEqual(below("s", ["a"], ["p"], 2**63), (TWO_64 - 1) % 2**63)
        self.assertEqual(fake.call_count, 1)

    def test_real_rejection_in_golden_data(self):
        # n = 2**63 + 1 rejects about half of all attempts, so a short scan finds one.
        n = 2**63 + 1
        tries = [reference_below("s", ["a"], ["reject", i], n)[1] for i in range(40)]
        self.assertGreater(max(tries), 1)
        for i in range(40):
            self.assertEqual(
                below("s", ["a"], ["reject", i], n),
                reference_below("s", ["a"], ["reject", i], n)[0],
            )


class Helpers(unittest.TestCase):
    def test_below_range_and_one(self):
        for i in range(200):
            self.assertEqual(below("s", ["a"], [i], 1), 0)
            self.assertIn(below("s", ["a"], [i], 5), range(5))

    def test_chance_extremes(self):
        for i in range(100):
            self.assertFalse(chance("s", ["a"], [i], 0, 10))
            self.assertTrue(chance("s", ["a"], [i], 10, 10))

    def test_weighted_never_picks_zero_weight(self):
        for i in range(500):
            self.assertEqual(weighted("s", ["a"], [i], [0, 3, 0, 1]) in (1, 3), True)
        self.assertEqual(weighted("s", ["a"], ["x"], [0, 0, 5]), 2)

    def test_weighted_proportions(self):
        counts = [0, 0, 0]
        for i in range(30_000):
            counts[weighted("w", ["a"], [i], [1, 2, 3])] += 1
        # means 5000, 10000, 15000; sd at most 91; tolerance 500.
        for got, want in zip(counts, (5_000, 10_000, 15_000)):
            self.assertLessEqual(abs(got - want), 500)

    def test_choice_and_quantile_pick_members(self):
        for i in range(100):
            self.assertIn(choice("s", ["a"], [i], ["x", "y", "z"]), ["x", "y", "z"])
            self.assertIn(quantile("s", ["a"], [i], [10, 20, 30]), [10, 20, 30])
        self.assertEqual(choice("s", ["a"], ["p"], ("only",)), "only")

    def test_quantile_table_values_may_be_large(self):
        self.assertEqual(quantile("s", ["a"], ["p"], [2**53 - 1]), 2**53 - 1)


class OrderRemovalStable(unittest.TestCase):
    ACTORS = ["ana", "bo", "cy", "dee", "eli", "fay", "gus", "hana", "ivo", "jun", "kai", "lin"]

    def test_removing_any_one_item_keeps_the_rest_in_order(self):
        full = order("seed", ["g"], ["speak"], self.ACTORS)
        self.assertEqual(sorted(full), sorted(self.ACTORS))
        for gone in self.ACTORS:
            rest = [a for a in self.ACTORS if a != gone]
            self.assertEqual(
                order("seed", ["g"], ["speak"], rest), [a for a in full if a != gone], gone
            )

    def test_removing_any_subset_keeps_the_rest_in_order(self):
        items = self.ACTORS[:7]
        full = order("seed", ["g"], ["speak"], items)
        for size in range(len(items) + 1):
            for subset in itertools.combinations(items, size):
                with self.subTest(subset=subset):
                    self.assertEqual(
                        order("seed", ["g"], ["speak"], list(subset)),
                        [a for a in full if a in subset],
                    )

    def test_input_order_does_not_matter(self):
        full = order("seed", ["g"], ["speak"], self.ACTORS)
        self.assertEqual(order("seed", ["g"], ["speak"], self.ACTORS[::-1]), full)
        self.assertEqual(order("seed", ["g"], ["speak"], tuple(self.ACTORS)), full)

    def test_adding_an_item_keeps_the_others_in_order(self):
        small = self.ACTORS[:6]
        before = order("seed", ["g"], ["speak"], small)
        after = order("seed", ["g"], ["speak"], self.ACTORS)
        self.assertEqual([a for a in after if a in small], before)

    def test_purpose_changes_the_order(self):
        orders = {
            tuple(order("seed", ["g"], ["speak", i], self.ACTORS)) for i in range(20)
        }
        self.assertGreater(len(orders), 15)

    def test_mixed_strings_and_integers(self):
        # "1" and 1 are different ids: they get different draws and may both appear.
        items = [1, "1", "a", 2, "b", -3]
        result = order("seed", ["g"], ["mixed"], items)
        self.assertEqual(len(result), 6)
        self.assertEqual({repr(i) for i in result}, {repr(i) for i in items})
        self.assertEqual(order("seed", ["g"], ["mixed"], list(reversed(items))), result)

    def test_ties_break_by_id(self):
        # Force equal draws: integers sort before strings, then by value or code point.
        with mock.patch.object(draw_module, "draw", lambda s, c, p: 7):
            self.assertEqual(order("s", [], ["p"], ["b", 3, "a", -1, 2]), [-1, 2, 3, "a", "b"])

    def test_empty_and_single(self):
        self.assertEqual(order("s", [], ["p"], []), [])
        self.assertEqual(order("s", [], ["p"], ["x"]), ["x"])

    def test_order_does_not_modify_its_input(self):
        items = ["c", "a", "b"]
        order("s", [], ["p"], items)
        self.assertEqual(items, ["c", "a", "b"])


class Rejected(unittest.TestCase):
    def raises(self, function, *args):
        with self.assertRaises(ValueError):
            function(*args)

    def test_seed_must_be_a_string(self):
        for seed in (1, None, b"s", ["s"], True):
            with self.subTest(seed=seed):
                self.raises(draw, seed, [], [])

    def test_scope_and_purpose_must_be_lists_of_str_or_int(self):
        for bad in ("abc", None, 5, {"a": 1}, {"a"}):
            with self.subTest(bad=bad):
                self.raises(draw, "s", bad, [])
                self.raises(draw, "s", [], bad)
        for element in (1.5, None, True, False, b"x", ["x"], {"a": 1}):
            with self.subTest(element=element):
                self.raises(draw, "s", [element], [])
                self.raises(draw, "s", [], ["p", element])

    def test_integer_elements_must_be_in_canonical_range(self):
        self.raises(draw, "s", [2**53], [])
        self.raises(draw, "s", [], [-(2**53)])

    def test_strings_must_be_canonical(self):
        self.raises(draw, "s", [chr(0xD800)], [])
        self.raises(draw, "s", ["e" + chr(0x0301)], [])
        self.raises(draw, chr(0xD800), [], [])

    def test_below_rejects_bad_n(self):
        for n in (0, -1, TWO_64 + 1, 1.5, "3", None, True):
            with self.subTest(n=n):
                self.raises(below, "s", [], ["p"], n)

    def test_below_propagates_bad_key(self):
        self.raises(below, 1, [], ["p"], 3)
        self.raises(below, "s", [1.5], ["p"], 3)

    def test_chance_rejects_bad_fractions(self):
        for num, den in ((1, 0), (1, -1), (-1, 5), (6, 5), (1.0, 5), (1, 5.0), (True, 5)):
            with self.subTest(num=num, den=den):
                self.raises(chance, "s", [], ["p"], num, den)

    def test_choice_rejects_empty_and_non_sequences(self):
        for items in ([], (), None, "abc", 5):
            with self.subTest(items=items):
                self.raises(choice, "s", [], ["p"], items)

    def test_weighted_rejects_bad_weights(self):
        for weights in ([], [0], [0, 0], [-1, 2], [1, -1], [1.5], [True, 1], ["1"], None):
            with self.subTest(weights=weights):
                self.raises(weighted, "s", [], ["p"], weights)

    def test_order_rejects_duplicates_and_bad_ids(self):
        self.raises(order, "s", [], ["p"], ["a", "b", "a"])
        self.raises(order, "s", [], ["p"], [1, 2, 1])
        self.raises(order, "s", [], ["p"], [1.5])
        self.raises(order, "s", [], ["p"], [None])
        self.raises(order, "s", [], ["p"], "abc")
        self.raises(order, "s", [], ["p"], [True])

    def test_quantile_rejects_bad_tables(self):
        for table in ([], [1.5], ["1"], [True], None):
            with self.subTest(table=table):
                self.raises(quantile, "s", [], ["p"], table)


if __name__ == "__main__":
    unittest.main()
