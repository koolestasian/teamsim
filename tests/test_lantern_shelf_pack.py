"""The Lantern Shelf pack is the fixture converted by fixtures/demo/make_pack.py."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

from teamsim import controls, pack

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "packs" / "lantern-shelf"
DEMO = ROOT / "fixtures" / "demo"
FILES = ("pack.toml", "timeline.jsonl")


def _converter():
    spec = importlib.util.spec_from_file_location("make_pack", ROOT / "fixtures" / "demo" / "make_pack.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LanternShelfPackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.converter = _converter()
        cls.dataset, cls.cases = cls.converter.load_sources()
        cls.pack = pack.load(PACK)

    def test_regenerating_gives_identical_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.converter.main(["-o", tmp]), 0)
            for name in FILES:
                self.assertEqual((Path(tmp) / name).read_bytes(), (PACK / name).read_bytes(), name)

    def test_shape(self):
        the_pack = self.pack
        self.assertEqual(len(the_pack.actors), 7)
        self.assertEqual(len(the_pack.surfaces), 10)
        answers = [c for c in the_pack.checks if c.kind == "answer"]
        probes = [e for e in the_pack.events if e.probe]
        self.assertEqual(len(probes), len(answers))
        self.assertEqual(len(the_pack.events), len(self.dataset["messages"]) + len(answers))
        self.assertEqual(len(self.dataset["messages"]), 314)
        # One answer check per case that was kept: cases about an old value have none.
        _, summary = self.converter.build(self.dataset, self.cases)
        self.assertEqual(len(answers), len(summary["kept"]))
        by_id = {c["id"]: c for c in self.cases}
        for case_id in summary["kept"]:
            self.assertNotEqual(by_id[case_id]["expected_status"], "superseded")
        self.assertEqual(
            len(self.cases), len(summary["kept"]) + len(summary["old_only"]) + len(summary["skipped"])
        )

    def test_skipped_cases_and_aspect_keys(self):
        _, summary = self.converter.build(self.dataset, self.cases)
        self.assertEqual(summary["skipped"], [])
        self.assertEqual(sorted(c for c, _ in summary["spans"]), ["para-10", "para-21", "rev-09", "rev-10"])
        # Each span stands in the pack as the value, with the eval fragment as a form.
        facts_by_value = {f.value: f for f in self.pack.facts}
        for case_id, span in summary["spans"]:
            fragment = next(c for c in self.cases if c["id"] == case_id)["answer_contains"]
            self.assertIn(fragment, facts_by_value[span].forms)
        self.assertEqual(len(summary["aspects"]), 11)
        # Aspect facts stand alone: no supersedes link, and their key is shared with no other fact.
        keys = [f.key for f in self.pack.facts]
        alone = [f for f in self.pack.facts if keys.count(f.key) == 1 and f.supersedes is None]
        self.assertGreaterEqual(len(alone), 11)
        self.assertEqual(summary["fallback"][0][0], "rev-11")

    def test_keys_are_readable_slugs_from_the_table(self):
        slugs = self.converter.KEY_SLUGS
        self.assertEqual(len(set(slugs.values())), len(slugs))
        used = {f.key for f in self.pack.facts}
        self.assertEqual(used, set(slugs.values()))
        for fact in self.pack.facts:
            words = fact.key.split("-")
            self.assertTrue(2 <= len(words) <= 4, fact.key)
            self.assertRegex(fact.key, r"^[a-z]+(-[a-z]+)+$")
            self.assertNotIn(fact.value.lower(), fact.key)
            self.assertNotIn(fact.value.lower().replace(" ", "-"), fact.key)
        for check in self.pack.checks:
            if check.key is not None:
                self.assertIn(check.key, used)

    def test_a_case_missing_from_the_table_fails_loudly(self):
        original = dict(self.converter.KEY_SLUGS)
        try:
            del self.converter.KEY_SLUGS["d-36"]
            with self.assertRaises(SystemExit):
                self.converter.build(self.dataset, self.cases)
        finally:
            self.converter.KEY_SLUGS.clear()
            self.converter.KEY_SLUGS.update(original)

    def test_day_one_keeps_its_utc_clock_time(self):
        first = self.dataset["messages"][0]["created_at"]
        self.assertEqual(self.pack.events[0].when.ms, first % 86_400_000)

    def test_every_value_is_in_its_disclosing_message(self):
        facts = {f.id: f for f in self.pack.facts}
        disclosed = set()
        for event in self.pack.events:
            for fact_id in event.discloses or ():
                disclosed.add(fact_id)
                self.assertIn(facts[fact_id].value.lower(), event.text.lower(), (fact_id, event.id))
                self.assertIn(event.actor, facts[fact_id].authority)
        self.assertEqual(disclosed, set(facts))

    def test_control_matrix(self):
        matrix = controls.matrix(self.pack)
        answers = [c.id for c in self.pack.checks if c.kind == "answer"]
        for check in self.pack.checks:
            self.assertEqual(matrix["oracle"][check.id][0], "pass", check.id)
        for check_id in answers:
            self.assertEqual(matrix["null"][check_id][0], "fail", check_id)
        mismatches = [
            line for line in controls.validate(self.pack) if ": not exercised: " not in line and ": not detected: " not in line
        ]
        self.assertEqual(mismatches, [])

    def test_dataset_files_are_untouched(self):
        # Converting only reads the fixture; its own hash tests pin the content.
        names = ("dataset.json", "eval.toml")
        before = [(DEMO / n).read_bytes() for n in names]
        with tempfile.TemporaryDirectory() as tmp:
            self.converter.main(["-o", tmp])
        self.assertEqual(before, [(DEMO / n).read_bytes() for n in names])


if __name__ == "__main__":
    unittest.main()
