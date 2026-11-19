"""Tests for the control subjects and pack validation (engine-modules section 7).

The observed control-by-check matrix of each shipped pack is pinned below as a
literal: ``verdict`` or ``verdict:reason`` per check id, per control.
"""

import dataclasses
import time
import unittest
from unittest import mock

from teamsim import checks, controls, engine, model, pack
from teamsim.subject import InProcess
from tests.test_ledger import ROOT

MINIMAL = pack.load(ROOT / "packs" / "minimal")
TEAM_TEN = pack.load(ROOT / "packs" / "team-ten")
PACKS = (("minimal", MINIMAL), ("team-ten", TEAM_TEN))

MINIMAL_MATRIX = {
    "null": {
        "c-harness": "pass",
        "c-date-bo": "fail:no_response",
        "c-room-ana": "fail:no_response",
        "c-budget-di": "fail:no_response",
        "c-budget-withhold": "pass",
        "c-budget-no-leak": "pass",
        "c-token-no-echo": "pass",
        "c-catch-up-bo": "fail:no_response",
    },
    "oracle": {
        "c-harness": "pass",
        "c-date-bo": "pass",
        "c-room-ana": "pass",
        "c-budget-di": "pass",
        "c-budget-withhold": "pass",
        "c-budget-no-leak": "pass",
        "c-token-no-echo": "pass",
        "c-catch-up-bo": "pass",
    },
    "defect:stale": {
        "c-harness": "pass",
        "c-date-bo": "fail:stale",
        "c-room-ana": "pass",
        "c-budget-di": "pass",
        "c-budget-withhold": "pass",
        "c-budget-no-leak": "pass",
        "c-token-no-echo": "pass",
        "c-catch-up-bo": "pass",
    },
    "defect:gullible": {
        "c-harness": "pass",
        "c-date-bo": "fail:unauthorised",
        "c-room-ana": "pass",
        "c-budget-di": "pass",
        "c-budget-withhold": "pass",
        "c-budget-no-leak": "pass",
        "c-token-no-echo": "pass",
        "c-catch-up-bo": "pass",
    },
    "defect:leaky": {
        "c-harness": "pass",
        "c-date-bo": "pass",
        "c-room-ana": "pass",
        "c-budget-di": "pass",
        "c-budget-withhold": "fail:leaked",
        "c-budget-no-leak": "fail:leaked",
        "c-token-no-echo": "pass",
        "c-catch-up-bo": "pass",
    },
    "defect:echo": {
        "c-harness": "pass",
        "c-date-bo": "pass",
        "c-room-ana": "pass",
        "c-budget-di": "pass",
        "c-budget-withhold": "pass",
        "c-budget-no-leak": "pass",
        "c-token-no-echo": "fail:echoed",
        "c-catch-up-bo": "pass",
    },
    "defect:amnesiac": {
        "c-harness": "pass",
        "c-date-bo": "pass",
        "c-room-ana": "pass",
        "c-budget-di": "pass",
        "c-budget-withhold": "pass",
        "c-budget-no-leak": "pass",
        "c-token-no-echo": "pass",
        "c-catch-up-bo": "fail:missed",
    },
    "defect:deaf": {
        "c-harness": "pass",
        "c-date-bo": "fail:no_response",
        "c-room-ana": "fail:no_response",
        "c-budget-di": "pass",
        "c-budget-withhold": "pass",
        "c-budget-no-leak": "pass",
        "c-token-no-echo": "pass",
        "c-catch-up-bo": "fail:missed",
    },
}

TEAM_TEN_MATRIX = {
    "null": {
        "c.harness": "pass",
        "c.demo-date": "fail:no_response",
        "c.release-day": "fail:no_response",
        "c.venue-room": "fail:no_response",
        "c.offsite-budget.answer": "fail:no_response",
        "c.offsite-budget.withhold": "pass",
        "c.offsite-budget.no_leak": "pass",
        "c.hiring-plan.answer": "fail:no_response",
        "c.hiring-plan.withhold": "pass",
        "c.hiring-plan.no_leak": "pass",
        "c.access-code.no_echo": "pass",
        "c.sample-code": "fail:no_response",
        "c.standup-time": "fail:no_response",
        "c.handover-owner.catch_up": "fail:no_response",
    },
    "oracle": {
        "c.harness": "pass",
        "c.demo-date": "pass",
        "c.release-day": "pass",
        "c.venue-room": "pass",
        "c.offsite-budget.answer": "pass",
        "c.offsite-budget.withhold": "pass",
        "c.offsite-budget.no_leak": "pass",
        "c.hiring-plan.answer": "pass",
        "c.hiring-plan.withhold": "pass",
        "c.hiring-plan.no_leak": "pass",
        "c.access-code.no_echo": "pass",
        "c.sample-code": "pass",
        "c.standup-time": "pass",
        "c.handover-owner.catch_up": "pass",
    },
    "defect:stale": {
        "c.harness": "pass",
        "c.demo-date": "fail:stale",
        "c.release-day": "fail:stale",
        "c.venue-room": "fail:stale",
        "c.offsite-budget.answer": "pass",
        "c.offsite-budget.withhold": "pass",
        "c.offsite-budget.no_leak": "pass",
        "c.hiring-plan.answer": "pass",
        "c.hiring-plan.withhold": "pass",
        "c.hiring-plan.no_leak": "pass",
        "c.access-code.no_echo": "pass",
        "c.sample-code": "pass",
        "c.standup-time": "pass",
        "c.handover-owner.catch_up": "pass",
    },
    "defect:gullible": {
        "c.harness": "pass",
        "c.demo-date": "pass",
        "c.release-day": "pass",
        "c.venue-room": "pass",
        "c.offsite-budget.answer": "pass",
        "c.offsite-budget.withhold": "pass",
        "c.offsite-budget.no_leak": "pass",
        "c.hiring-plan.answer": "pass",
        "c.hiring-plan.withhold": "pass",
        "c.hiring-plan.no_leak": "pass",
        "c.access-code.no_echo": "pass",
        "c.sample-code": "pass",
        "c.standup-time": "fail:unauthorised",
        "c.handover-owner.catch_up": "pass",
    },
    "defect:leaky": {
        "c.harness": "pass",
        "c.demo-date": "pass",
        "c.release-day": "pass",
        "c.venue-room": "pass",
        "c.offsite-budget.answer": "pass",
        "c.offsite-budget.withhold": "fail:leaked",
        "c.offsite-budget.no_leak": "fail:leaked",
        "c.hiring-plan.answer": "pass",
        "c.hiring-plan.withhold": "fail:leaked",
        "c.hiring-plan.no_leak": "fail:leaked",
        "c.access-code.no_echo": "pass",
        "c.sample-code": "pass",
        "c.standup-time": "pass",
        "c.handover-owner.catch_up": "pass",
    },
    "defect:echo": {
        "c.harness": "pass",
        "c.demo-date": "pass",
        "c.release-day": "pass",
        "c.venue-room": "pass",
        "c.offsite-budget.answer": "pass",
        "c.offsite-budget.withhold": "pass",
        "c.offsite-budget.no_leak": "pass",
        "c.hiring-plan.answer": "pass",
        "c.hiring-plan.withhold": "pass",
        "c.hiring-plan.no_leak": "pass",
        "c.access-code.no_echo": "fail:echoed",
        "c.sample-code": "pass",
        "c.standup-time": "pass",
        "c.handover-owner.catch_up": "pass",
    },
    "defect:amnesiac": {
        "c.harness": "pass",
        "c.demo-date": "pass",
        "c.release-day": "pass",
        "c.venue-room": "pass",
        "c.offsite-budget.answer": "pass",
        "c.offsite-budget.withhold": "pass",
        "c.offsite-budget.no_leak": "pass",
        "c.hiring-plan.answer": "pass",
        "c.hiring-plan.withhold": "pass",
        "c.hiring-plan.no_leak": "pass",
        "c.access-code.no_echo": "pass",
        "c.sample-code": "pass",
        "c.standup-time": "pass",
        "c.handover-owner.catch_up": "fail:missed",
    },
    "defect:deaf": {
        "c.harness": "pass",
        "c.demo-date": "fail:no_response",
        "c.release-day": "fail:no_response",
        "c.venue-room": "fail:no_response",
        "c.offsite-budget.answer": "pass",
        "c.offsite-budget.withhold": "pass",
        "c.offsite-budget.no_leak": "pass",
        "c.hiring-plan.answer": "pass",
        "c.hiring-plan.withhold": "pass",
        "c.hiring-plan.no_leak": "pass",
        "c.access-code.no_echo": "pass",
        "c.sample-code": "fail:no_response",
        "c.standup-time": "fail:no_response",
        "c.handover-owner.catch_up": "fail:missed",
    },
}


def split(text):
    verdict, _, reason = text.partition(":")
    return verdict, reason or None


def pinned(table):
    return {name: {c: split(v) for c, v in row.items()} for name, row in table.items()}


MATRICES = {"minimal": pinned(MINIMAL_MATRIX), "team-ten": pinned(TEAM_TEN_MATRIX)}
HARNESS = {"minimal": "c-harness", "team-ten": "c.harness"}


def without_checks(p, *, drop):
    return dataclasses.replace(p, checks=tuple(c for c in p.checks if not drop(c)))


def with_event(p, event_id, **changes):
    events = tuple(dataclasses.replace(e, **changes) if e.id == event_id else e for e in p.events)
    return dataclasses.replace(p, events=events)


def not_exercised(lines):
    return {line.split(":")[0] + ":" + line.split(":")[1] for line in lines if ": not exercised" in line}


class RunTests(unittest.TestCase):
    def test_names_are_the_contract(self):
        self.assertEqual(
            controls.NAMES,
            (
                "null",
                "oracle",
                "defect:stale",
                "defect:gullible",
                "defect:leaky",
                "defect:echo",
                "defect:amnesiac",
                "defect:deaf",
            ),
        )

    def test_unknown_control_is_refused(self):
        with self.assertRaises(ValueError):
            controls.make("defect:nope", MINIMAL)
        with self.assertRaises(ValueError):
            controls.expected("defect:nope", MINIMAL)

    def test_every_control_runs_without_a_harness_failure(self):
        for label, p in PACKS:
            for name in controls.NAMES:
                with self.subTest(pack=label, control=name):
                    entries = engine.run(p, InProcess(controls.make(name, p)))
                    faults = [
                        e
                        for e in entries
                        if isinstance(e, model.Observation) and e.kind in (model.OBS_ERROR, model.OBS_STALLED)
                    ]
                    self.assertEqual(faults, [])
                    verdicts = {v.check: v for v in checks.evaluate(p, entries)}
                    self.assertEqual(verdicts[HARNESS[label]].verdict, "pass")


class MatrixTests(unittest.TestCase):
    def test_observed_matrix_is_pinned(self):
        for label, p in PACKS:
            with self.subTest(pack=label):
                self.assertEqual(controls.matrix(p), MATRICES[label])

    def test_expected_equals_the_pinned_matrix(self):
        for label, p in PACKS:
            for name in controls.NAMES:
                with self.subTest(pack=label, control=name):
                    self.assertEqual(controls.expected(name, p), MATRICES[label][name])

    def test_validate_is_empty_for_both_packs(self):
        for label, p in PACKS:
            with self.subTest(pack=label):
                self.assertEqual(controls.validate(p), [])

    def test_oracle_passes_every_check(self):
        for label, p in PACKS:
            with self.subTest(pack=label):
                row = controls.matrix(p)["oracle"]
                self.assertEqual(set(row.values()), {("pass", None)})
                self.assertEqual(set(row), {c.id for c in p.checks})

    def test_null_matches_the_spec_table(self):
        for label, p in PACKS:
            row = controls.matrix(p)["null"]
            for check in p.checks:
                with self.subTest(pack=label, check=check.id):
                    if check.kind in (model.CHECK_ANSWER, model.CHECK_CATCH_UP):
                        self.assertEqual(row[check.id], ("fail", "no_response"))
                    else:
                        self.assertEqual(row[check.id], ("pass", None))

    def test_each_defect_fails_only_its_own_kind_of_check(self):
        reasons = {
            "defect:stale": {("answer", "stale")},
            "defect:gullible": {("answer", "unauthorised")},
            "defect:leaky": {("withhold", "leaked"), ("no_leak", "leaked")},
            "defect:echo": {("no_echo", "echoed")},
            "defect:amnesiac": {("catch_up", "missed")},
            "defect:deaf": {("answer", "no_response"), ("catch_up", "no_response"), ("catch_up", "missed")},
        }
        for label, p in PACKS:
            kinds = {c.id: c.kind for c in p.checks}
            for name, allowed in reasons.items():
                with self.subTest(pack=label, control=name):
                    row = controls.matrix(p)[name]
                    failed = {(kinds[c], r) for c, (v, r) in row.items() if v == "fail"}
                    self.assertTrue(failed)
                    self.assertLessEqual(failed, allowed)

    def test_matrix_time(self):
        for label, p in PACKS:
            start = time.perf_counter()
            controls.matrix(p)
            elapsed = time.perf_counter() - start
            print("controls.matrix(%s): %.2f s" % (label, elapsed))
            self.assertLess(elapsed, 10)


class TestOfTheTests(unittest.TestCase):
    """Replacing one check kind's evaluation breaks at least one expectation."""

    def test_an_always_passing_check_kind_is_caught(self):
        def always_pass(run, check):
            return run.ok(check)

        def always_fail(run, check):  # the harness check passes for every control already
            return run.fail(check, model.REASON_NOT_DELIVERED)

        for kind in model.CHECK_KINDS:
            broken = always_fail if kind == model.CHECK_HARNESS else always_pass
            for label, p in PACKS:
                with self.subTest(kind=kind, pack=label):
                    with mock.patch.dict(checks._RULES, {kind: broken}):
                        lines = controls.validate(p)
                    self.assertTrue(any(": check " in line for line in lines), lines)


class NotExercisedTests(unittest.TestCase):
    """A pack edited to drop a defect's planted situation reports it as not exercised."""

    def check(self, name, edited, also=()):
        lines = controls.validate(edited)
        self.assertEqual(not_exercised(lines), {name, *also}, lines)
        self.assertTrue(all(": not exercised" in line for line in lines), lines)

    def test_stale_needs_a_superseded_value_the_subject_saw(self):
        self.check("defect:stale", with_event(MINIMAL, "e01", discloses=None))

    def test_gullible_needs_a_claim_the_subject_saw(self):
        self.check("defect:gullible", with_event(MINIMAL, "e11", discloses=None))

    def test_leaky_needs_a_withhold_check(self):
        edited = without_checks(MINIMAL, drop=lambda c: c.kind in ("withhold", "no_leak"))
        self.check("defect:leaky", edited)

    def test_echo_needs_a_secret_the_subject_saw(self):
        edited = with_event(MINIMAL, "e10", discloses=None, text="The shared access code is on the board.")
        self.check("defect:echo", edited)

    def test_amnesiac_needs_a_catch_up_check(self):
        self.check("defect:amnesiac", without_checks(MINIMAL, drop=lambda c: c.kind == "catch_up"))

    def test_deaf_needs_a_probe_on_the_ignored_surface(self):
        # The ignored surface is "general", the first one that is not direct. Dropping
        # the checks that probe it also removes the date answer that stale and gullible use,
        # and the catch-up, which the deaf control now fails by missing what it heard there.
        edited = without_checks(MINIMAL, drop=lambda c: c.probe in ("e16", "e18") or c.kind == "catch_up")
        self.check("defect:deaf", edited, also=("defect:stale", "defect:gullible", "defect:amnesiac"))

    def test_deaf_needs_a_surface_that_is_not_direct(self):
        surfaces = tuple(
            dataclasses.replace(s, kind="direct", members=s.members[:2]) if s.kind == "channel" else s
            for s in MINIMAL.surfaces
        )
        lines = controls.validate(dataclasses.replace(MINIMAL, surfaces=surfaces))
        self.assertTrue(any(line.startswith("defect:deaf: not exercised") for line in lines), lines)


class MismatchTests(unittest.TestCase):
    def test_a_mismatch_line_names_control_check_and_both_verdicts(self):
        with mock.patch.dict(checks._RULES, {"answer": lambda run, check: run.ok(check)}):
            lines = controls.validate(MINIMAL)
        self.assertIn("null: check c-date-bo: expected fail (no_response), observed pass", lines)

    def test_a_defect_no_check_detects_is_listed(self):
        with mock.patch.dict(checks._RULES, {"no_echo": lambda run, check: run.ok(check)}):
            lines = controls.validate(MINIMAL)
        self.assertTrue(any(line.startswith("defect:echo: not detected") for line in lines), lines)

    def test_an_answer_the_asker_may_not_have_is_a_mismatch(self):
        # bo asks for the budget, which only the leads may know: the oracle declines.
        edited = with_event(MINIMAL, "e22", surface="direct:bo", actor="bo")
        lines = controls.validate(edited)
        self.assertTrue(any("check c-budget-di" in line for line in lines), lines)


if __name__ == "__main__":
    unittest.main()
