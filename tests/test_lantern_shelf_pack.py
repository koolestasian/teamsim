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
        # No message of the dataset states these values; nothing is invented for them.
        self.assertEqual(
            sorted(c for c, _ in summary["skipped"]), ["para-10", "para-21", "rev-09", "rev-10"]
        )
        self.assertEqual(len(summary["aspects"]), 10)
        facts = {f.key: f for f in self.pack.facts if "." in f.key}
        self.assertEqual(len(facts), 10)
        for fact in facts.values():
            self.assertIsNone(fact.supersedes)
        self.assertEqual(summary["fallback"][0][0], "rev-11")

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
