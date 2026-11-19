"""Tests for the command line (docs/spec/engine-modules.md section 8)."""

import contextlib
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from teamsim import cli, controls, pack, record

ROOT = pathlib.Path(__file__).parent.parent
TEAM_TEN = ROOT / "packs" / "team-ten"
MINIMAL = ROOT / "packs" / "minimal"


def call(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class Silent:
    def handle(self, message):
        if message.get("type") == "hello":
            return [{"type": "ready", "v": message["v"], "name": "stub", "version": "0"}]
        if message.get("type") == "event":
            return [{"type": "done", "in_reply_to": message["seq"]}]
        return []


class Tmp(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.tmp = pathlib.Path(holder.name)


class DemoTests(Tmp):
    def test_demo_with_stubbed_bots(self):
        with mock.patch.object(cli, "_example_bot", lambda name: Silent()):
            code, out, err = call("demo", "--out", str(self.tmp / "d"))
        self.assertEqual((code, err), (0, ""))
        for name in ("naive_bot", "careful_bot"):
            for stem in ("record-%s.jsonl", "report-%s.md", "report-%s.json", "timing-%s.jsonl"):
                self.assertTrue((self.tmp / "d" / (stem % name)).is_file())
            self.assertIn(name + ":", out)
        self.assertIn("validation passed", out)

    def test_real_demo(self):
        code, out, err = call("demo", "--out", str(self.tmp / "d"))
        self.assertEqual((code, err), (0, ""))
        naive = json.loads((self.tmp / "d" / "report-naive_bot.json").read_text("utf-8"))
        careful = json.loads((self.tmp / "d" / "report-careful_bot.json").read_text("utf-8"))
        scored = ("withhold", "no_leak")
        self.assertTrue(
            any(c["verdict"] == "fail" for c in naive["checks"] if c["kind"] in scored)
        )
        self.assertTrue([c for c in careful["checks"] if c["kind"] in scored])
        self.assertEqual([c["check"] for c in careful["checks"] if c["verdict"] != "pass"], [])
        self.assertIn("matrix", naive)


class CommandTests(Tmp):
    def test_validate(self):
        code, out, err = call("validate", str(TEAM_TEN))
        self.assertEqual(code, 0, err)
        self.assertIn("oracle", out)
        self.assertIn("validation passed", out)

    def _validate_with(self, lines):
        with mock.patch.object(controls, "validate", lambda p: lines):
            return call("validate", str(MINIMAL))

    def test_validate_line_forms(self):
        info = [
            "defect:stale: not exercised: no check of this pack plants its situation",
            "defect:echo: not detected: no check tells it from the oracle",
        ]
        code, out, _ = self._validate_with(info)
        self.assertEqual(code, 0)
        for line in info:
            self.assertIn(line, out)
        mismatch = "null: check c-x: expected pass, observed fail (leaked)"
        code, out, err = self._validate_with(info + [mismatch])
        self.assertEqual(code, 1)
        self.assertIn(mismatch, out)
        self.assertIn("1 mismatch", err)

    def test_inspect(self):
        code, out, _ = call("inspect", str(MINIMAL))
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("who"))
        self.assertGreater(len(out.splitlines()), 1)

    def test_generate_run_replay_end_to_end(self):
        gen = self.tmp / "gen"
        code, out, _ = call("generate", str(ROOT / "populations" / "team-ten.toml"), "-o", str(gen))
        self.assertEqual(code, 0)
        self.assertEqual(pack.pack_hash(pack.load(gen)), pack.pack_hash(pack.load(TEAM_TEN)))
        for name in ("pack.toml", "timeline.jsonl"):
            self.assertEqual((gen / name).read_bytes(), (TEAM_TEN / name).read_bytes())
        out_dir = self.tmp / "run"
        code, out, err = call("run", str(gen), "--builtin", "oracle", "--out", str(out_dir))
        self.assertEqual((code, err), (0, ""))
        rec = out_dir / "record-oracle.jsonl"
        digest = record.read(rec).digest
        code, out, err = call("replay", str(rec), "--pack", str(gen))
        self.assertEqual((code, err), (0, ""))
        self.assertIn(digest, out)

    def test_run_failing_subject_exits_1_and_repeats(self):
        code, out, _ = call(
            "run", str(MINIMAL), "--builtin", "null", "--repeats", "2", "--out", str(self.tmp / "r")
        )
        self.assertEqual(code, 1)
        self.assertTrue((self.tmp / "r" / "record-null-2.jsonl").is_file())
        self.assertIn("0 of 2 repeats", out)

    def test_replay_mismatch_exits_1(self):
        out_dir = self.tmp / "r"
        call("run", str(MINIMAL), "--builtin", "oracle", "--out", str(out_dir))
        rec = out_dir / "record-oracle.jsonl"
        code, _, _ = call("replay", str(rec), "--pack", str(TEAM_TEN))
        self.assertEqual(code, 1)
        rec.write_bytes(rec.read_bytes().replace(b"pass", b"fail", 1))
        code, _, err = call("replay", str(rec), "--pack", str(MINIMAL))
        self.assertEqual(code, 1)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_errors_are_one_line(self):
        for argv in (
            ["validate", str(self.tmp / "nope")],
            ["run", str(MINIMAL), "--builtin", "nonesuch"],
            ["replay", str(self.tmp / "none.jsonl"), "--pack", str(MINIMAL)],
            ["generate", str(self.tmp / "none.toml"), "-o", str(self.tmp / "o")],
            ["reduce"],
            [],
        ):
            code, _, err = call(*argv)
            self.assertEqual(code, 2, argv)
            self.assertNotIn("Traceback", err)
        code, _, err = call("validate", str(self.tmp / "nope"))
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_missing_example_exits_2(self):
        with mock.patch.dict(sys.modules, {"examples.naive_bot": None}):
            code, _, err = call(
                "run", str(MINIMAL), "--builtin", "naive_bot", "--out", str(self.tmp / "o")
            )
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)


class SubjectTests(Tmp):
    def test_missing_program_exits_2(self):
        code, _, err = call(
            "run", str(MINIMAL), "--subject", "no-such-program-xyz --flag", "--out", str(self.tmp / "o")
        )
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_command_subject_record_holds_program_name_only(self):
        script = (ROOT / "examples" / "careful_bot.py").as_posix()
        exe = pathlib.Path(sys.executable).as_posix()
        out_dir = self.tmp / "o"
        code, out, err = call(
            "run", str(MINIMAL), "--subject", '"%s" -I "%s"' % (exe, script), "--out", str(out_dir)
        )
        self.assertEqual((code, err), (0, ""))
        path = next(out_dir.glob("record-*.jsonl"))
        self.assertEqual(list(record.read(path).header.subject), ["command"])
        text = path.read_text("utf-8")
        self.assertNotIn("careful_bot.py", text)
        self.assertNotIn(pathlib.Path(sys.executable).parent.name, text)
        self.assertNotIn(" -I", text)


class RelativeSubjectTests(Tmp):
    """The subject command names files relative to the caller's directory, as typed."""

    def setUp(self):
        super().setUp()
        if shutil.which("python") is None:
            self.skipTest("no program named python on the path")
        before = os.getcwd()
        self.addCleanup(os.chdir, before)

    def _verdicts(self, out_dir):
        path = next(pathlib.Path(out_dir).glob("report-*.json"))
        return json.loads(path.read_text("utf-8"))["checks"]

    def test_a_relative_script_path_runs_from_the_repository_root(self):
        os.chdir(ROOT)
        code, out, err = call(
            "run", "packs/minimal", "--subject", "python examples/careful_bot.py", "--out", str(self.tmp / "o")
        )
        self.assertEqual((code, err), (0, ""))
        self.assertEqual([c["check"] for c in self._verdicts(self.tmp / "o") if c["verdict"] != "pass"], [])

    def test_a_script_in_the_current_directory_runs_as_the_readme_shows(self):
        work = self.tmp / "work"
        work.mkdir()
        shutil.copy(ROOT / "examples" / "careful_bot.py", work / "my_bot.py")
        os.chdir(work)
        code, out, err = call("run", str(MINIMAL), "--subject", "python my_bot.py", "--out", str(self.tmp / "o"))
        self.assertEqual((code, err), (0, ""))
        self.assertEqual([c["check"] for c in self._verdicts(self.tmp / "o") if c["verdict"] != "pass"], [])
        header = next(pathlib.Path(self.tmp / "o").glob("record-*.jsonl")).read_text("utf-8")
        self.assertNotIn("my_bot.py", header)

    def test_a_backslash_in_the_command_is_refused_on_windows_with_one_line(self):
        with mock.patch.object(os, "name", "nt"):
            code, _, err = call(
                "run", str(MINIMAL), "--subject", "python examples\\careful_bot.py", "--out", str(self.tmp / "o")
            )
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn("forward slash", err)

    def test_a_subject_that_never_says_ready_names_its_stderr_file(self):
        script = self.tmp / "mute.py"
        script.write_text("import sys\nprint('boom', file=sys.stderr)\n", encoding="utf-8")
        code, out, err = call(
            "run", str(MINIMAL), "--subject", 'python "%s"' % script.as_posix(), "--out", str(self.tmp / "o")
        )
        self.assertEqual(code, 1)
        lines = [line for line in err.strip().splitlines() if "ready" in line]
        self.assertEqual(len(lines), 1, err)
        self.assertIn("stderr-python.txt", lines[0])


class HelpTests(unittest.TestCase):
    def test_help(self):
        commands = ("demo", "run", "validate", "inspect", "replay", "generate")
        for argv in [["--help"]] + [[c, "--help"] for c in commands]:
            code, out, _ = call(*argv)
            self.assertEqual(code, 0, argv)
            self.assertIn("usage", out)

    def test_module_help(self):
        code = (
            "import runpy, sys; sys.path.insert(0, sys.argv[1]); sys.argv = ['teamsim', '--help']; "
            "runpy.run_module('teamsim', run_name='__main__')"
        )
        done = subprocess.run(
            [sys.executable, "-I", "-c", code, str(ROOT)], capture_output=True, text=True
        )
        self.assertEqual(done.returncode, 0)
        self.assertIn("demo", done.stdout)


if __name__ == "__main__":
    unittest.main()
