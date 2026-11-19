"""Tests for the Markdown and JSON reports (docs/spec/engine-modules.md section 8)."""

import dataclasses
import json
import pathlib
import re
import unittest

import teamsim
from teamsim import checks, controls, engine, pack, record, report
from teamsim.model import Verdict
from teamsim.subject import InProcess

ROOT = pathlib.Path(__file__).parent.parent
MINIMAL = pack.load(ROOT / "packs" / "minimal")
HOSTILE = (
    "x [link](http://evil.example/a) ![img](http://evil.example/i.png) "
    "<script>alert(1)</script> a|b\n# pwned\n- item"
)
BIDI_AND_C1 = (0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069, 0x200E, 0x200F, 0x61C, 0x80, 0x9F)
PIPE = re.compile(r"(?<!\\)\|")


def run_result(name="oracle"):
    entries = engine.run(MINIMAL, InProcess(controls.make(name, MINIMAL)))
    head = record.header(MINIMAL, {"builtin": name}, engine=teamsim.__version__)
    return record.build(head, entries, checks.evaluate(MINIMAL, entries))


def hostile_result():
    base = run_result()
    head = dataclasses.replace(base.header, limits=(HOSTILE,), seed=HOSTILE)
    first = base.verdicts[1]
    bad = Verdict(HOSTILE, first.kind, "pass", detail=(HOSTILE,), events=(HOSTILE,))
    return dataclasses.replace(base, header=head, verdicts=(bad,) + base.verdicts[1:])


class ReportTests(unittest.TestCase):
    def test_markdown_states_the_run(self):
        result = run_result()
        text = report.markdown(result)
        self.assertIn(result.digest, text)
        self.assertIn(result.header.pack_hash, text)
        for v in result.verdicts:
            self.assertIn(report.escape(v.check), text)
        self.assertIn("## Limits", text)
        self.assertNotIn("Control matrix", text)

    def test_counts_and_matrix(self):
        result = run_result("null")
        matrix = controls.matrix(MINIMAL)
        text = report.markdown(result, matrix=matrix)
        self.assertIn("## Control matrix", text)
        obj = report.json_obj(result, matrix=matrix)
        self.assertEqual(set(obj["matrix"]), set(controls.NAMES))
        total = sum(sum(row.values()) for row in obj["counts"].values())
        self.assertEqual(total, len(result.verdicts))
        self.assertEqual(json.loads(json.dumps(obj)), obj)

    def test_repeats_section(self):
        results = [run_result("oracle"), run_result("null")]
        self.assertIn("## Repeats", report.markdown(results[0], repeats=results))
        obj = report.json_obj(results[0], repeats=results)
        self.assertTrue(all(r["repeats"] == 2 for r in obj["repeats"]))

    def test_repeats_count_not_applicable_as_not_failing_like_the_command_line(self):
        from teamsim import cli

        base = run_result("oracle")
        quiet = dataclasses.replace(base.verdicts[3], verdict="not_applicable", reason=None)
        result = dataclasses.replace(base, verdicts=base.verdicts[:3] + (quiet,) + base.verdicts[4:])
        self.assertFalse(cli._failed(result))
        obj = report.json_obj(result, repeats=[result, result])
        row = next(r for r in obj["repeats"] if r["check"] == quiet.check)
        self.assertEqual((row["not_failed"], row["repeats"]), (2, 2))
        text = report.markdown(result, repeats=[result, result])
        self.assertIn("Not failed in", text)
        self.assertIn("Checks not failed in every repeat: %d of %d" % (len(result.verdicts), len(result.verdicts)), text)

    def test_hostile_text_is_inert(self):
        text = report.markdown(hostile_result(), matrix=controls.matrix(MINIMAL))
        self.assertNotIn("](", text)
        self.assertNotIn("<", text)
        self.assertNotIn("\n# pwned", text)
        self.assertNotIn("\n- item", text)
        self.assertIn("&lt;script&gt;", text)
        # every row of the check table keeps its six cells despite the pipe in the text
        rows = [x for x in text.splitlines() if "pwned" in x and x.startswith("| ")]
        self.assertTrue(rows)
        for line in rows:
            self.assertIn(len(PIPE.findall(line)), (7, 10), line)

    def test_json_round_trips_hostile_text(self):
        obj = report.json_obj(hostile_result())
        self.assertEqual(json.loads(json.dumps(obj)), obj)
        self.assertEqual(obj["limits"], [HOSTILE])

    def test_escape_replaces_bidirectional_and_c1_controls(self):
        hostile = "a" + "x".join(chr(c) for c in BIDI_AND_C1) + "o"
        out = report.escape(hostile)
        for char in out:
            self.assertFalse(
                ord(char) in BIDI_AND_C1
                or 0x80 <= ord(char) <= 0x9F,
                hex(ord(char)),
            )
        self.assertEqual(out.replace(" ", ""), "a" + "x" * (len(BIDI_AND_C1) - 1) + "o")

    def test_escape_leaves_no_text_that_a_markdown_renderer_would_link_as_an_email(self):
        out = report.escape("mail me: someone@example.com or x.y+z@sub.example.org")
        self.assertNotIn("@", out)  # the GFM extended email autolink needs a literal @ in the text
        self.assertIn("&#64;", out)

    def test_escape_makes_one_line(self):
        self.assertNotIn("\n", report.escape("a\r\nb c"))
        self.assertEqual(report.escape("a&b"), "a&amp;b")


if __name__ == "__main__":
    unittest.main()
