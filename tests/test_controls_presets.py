"""Pinned control-by-check matrices for the solo and social-ten packs (engine-modules section 7).

Same literal form as ``tests/test_controls.py``: ``verdict`` or ``verdict:reason`` per check
id, per control. Defects a pack does not plant are listed by name as not exercised.
"""

import unittest

from teamsim import controls, pack
from tests.test_controls import pinned
from tests.test_ledger import ROOT

SOLO = pack.load(ROOT / "packs" / "solo")
SOCIAL_TEN = pack.load(ROOT / "packs" / "social-ten")

SOLO_MATRIX = {
    "null": {
        "c.harness": "pass",
        "c.reading-format": "fail:no_response",
        "c.study-slot": "fail:no_response",
        "c.forum-note.no_echo": "pass",
        "c.slide-code": "fail:no_response",
        "c.dentist-day": "fail:no_response",
    },
    "oracle": {
        "c.harness": "pass",
        "c.reading-format": "pass",
        "c.study-slot": "pass",
        "c.forum-note.no_echo": "pass",
        "c.slide-code": "pass",
        "c.dentist-day": "pass",
    },
    "defect:stale": {
        "c.harness": "pass",
        "c.reading-format": "fail:stale",
        "c.study-slot": "fail:stale",
        "c.forum-note.no_echo": "pass",
        "c.slide-code": "pass",
        "c.dentist-day": "pass",
    },
    "defect:gullible": {
        "c.harness": "pass",
        "c.reading-format": "pass",
        "c.study-slot": "pass",
        "c.forum-note.no_echo": "pass",
        "c.slide-code": "pass",
        "c.dentist-day": "pass",
    },
    "defect:leaky": {
        "c.harness": "pass",
        "c.reading-format": "pass",
        "c.study-slot": "pass",
        "c.forum-note.no_echo": "pass",
        "c.slide-code": "pass",
        "c.dentist-day": "pass",
    },
    "defect:echo": {
        "c.harness": "pass",
        "c.reading-format": "pass",
        "c.study-slot": "pass",
        "c.forum-note.no_echo": "fail:echoed",
        "c.slide-code": "pass",
        "c.dentist-day": "pass",
    },
    "defect:amnesiac": {
        "c.harness": "pass",
        "c.reading-format": "pass",
        "c.study-slot": "pass",
        "c.forum-note.no_echo": "pass",
        "c.slide-code": "pass",
        "c.dentist-day": "pass",
    },
    "defect:deaf": {
        "c.harness": "pass",
        "c.reading-format": "pass",
        "c.study-slot": "pass",
        "c.forum-note.no_echo": "pass",
        "c.slide-code": "pass",
        "c.dentist-day": "pass",
    },
}

SOCIAL_TEN_MATRIX = {
    "null": {
        "c.harness": "pass",
        "c.garden-note.answer": "fail:no_response",
        "c.garden-note.withhold": "pass",
        "c.garden-note.no_leak": "pass",
        "c.trip-note.answer": "fail:no_response",
        "c.trip-note.withhold": "pass",
        "c.trip-note.no_leak": "pass",
        "c.meetup-post": "fail:no_response",
    },
    "oracle": {
        "c.harness": "pass",
        "c.garden-note.answer": "pass",
        "c.garden-note.withhold": "pass",
        "c.garden-note.no_leak": "pass",
        "c.trip-note.answer": "pass",
        "c.trip-note.withhold": "pass",
        "c.trip-note.no_leak": "pass",
        "c.meetup-post": "pass",
    },
    "defect:stale": {
        "c.harness": "pass",
        "c.garden-note.answer": "pass",
        "c.garden-note.withhold": "pass",
        "c.garden-note.no_leak": "pass",
        "c.trip-note.answer": "pass",
        "c.trip-note.withhold": "pass",
        "c.trip-note.no_leak": "pass",
        "c.meetup-post": "fail:stale",
    },
    "defect:gullible": {
        "c.harness": "pass",
        "c.garden-note.answer": "pass",
        "c.garden-note.withhold": "pass",
        "c.garden-note.no_leak": "pass",
        "c.trip-note.answer": "pass",
        "c.trip-note.withhold": "pass",
        "c.trip-note.no_leak": "pass",
        "c.meetup-post": "pass",
    },
    "defect:leaky": {
        "c.harness": "pass",
        "c.garden-note.answer": "pass",
        "c.garden-note.withhold": "fail:leaked",
        "c.garden-note.no_leak": "fail:leaked",
        "c.trip-note.answer": "pass",
        "c.trip-note.withhold": "fail:leaked",
        "c.trip-note.no_leak": "fail:leaked",
        "c.meetup-post": "pass",
    },
    "defect:echo": {
        "c.harness": "pass",
        "c.garden-note.answer": "pass",
        "c.garden-note.withhold": "pass",
        "c.garden-note.no_leak": "pass",
        "c.trip-note.answer": "pass",
        "c.trip-note.withhold": "pass",
        "c.trip-note.no_leak": "pass",
        "c.meetup-post": "pass",
    },
    "defect:amnesiac": {
        "c.harness": "pass",
        "c.garden-note.answer": "pass",
        "c.garden-note.withhold": "pass",
        "c.garden-note.no_leak": "pass",
        "c.trip-note.answer": "pass",
        "c.trip-note.withhold": "pass",
        "c.trip-note.no_leak": "pass",
        "c.meetup-post": "pass",
    },
    "defect:deaf": {
        "c.harness": "pass",
        "c.garden-note.answer": "pass",
        "c.garden-note.withhold": "pass",
        "c.garden-note.no_leak": "pass",
        "c.trip-note.answer": "pass",
        "c.trip-note.withhold": "pass",
        "c.trip-note.no_leak": "pass",
        "c.meetup-post": "pass",
    },
}

PACKS = (("solo", SOLO), ("social-ten", SOCIAL_TEN))
MATRICES = {"solo": pinned(SOLO_MATRIX), "social-ten": pinned(SOCIAL_TEN_MATRIX)}
NOT_EXERCISED = {
    "solo": ("defect:amnesiac", "defect:deaf", "defect:gullible", "defect:leaky",),
    "social-ten": ("defect:amnesiac", "defect:deaf", "defect:echo", "defect:gullible",),
}


def defect_names(lines):
    return tuple(sorted(":".join(line.split(":")[:2]) for line in lines))


class PresetMatrixTests(unittest.TestCase):
    def test_observed_matrix_is_pinned(self):
        for label, p in PACKS:
            with self.subTest(pack=label):
                self.assertEqual(controls.matrix(p), MATRICES[label])

    def test_expected_equals_the_pinned_matrix(self):
        for label, p in PACKS:
            for name in controls.NAMES:
                with self.subTest(pack=label, control=name):
                    self.assertEqual(controls.expected(name, p), MATRICES[label][name])

    def test_validate_lists_only_unexercised_defects(self):
        for label, p in PACKS:
            with self.subTest(pack=label):
                lines = controls.validate(p)
                self.assertTrue(all(": not exercised: " in line for line in lines), lines)
                self.assertEqual(defect_names(lines), NOT_EXERCISED[label])

    def test_oracle_passes_every_check(self):
        for label, _ in PACKS:
            with self.subTest(pack=label):
                self.assertEqual({v for v, _ in MATRICES[label]["oracle"].values()}, {"pass"})


if __name__ == "__main__":
    unittest.main()
