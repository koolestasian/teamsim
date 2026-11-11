import copy
import io
import json
import pickle
import tempfile
import unittest
from pathlib import Path

import fakes  # noqa: F401  (puts prototypes/teamctx-sim on sys.path)
from simlib import envfile, host as H, report as R
from simlib.state import Paths, Recorder

FAKE_OR = "sk-or-v1-FAKEFAKEFAKEFAKEFAKE0123456789"
FAKE_TCTX = "tctx_FAKEFAKEFAKEFAKE0123456789"
FAKE_CONTROL = "FakeControlTokenValue0123456789abcdef"
FAKE_BOT = "MjAwMDAwMDAwMDAwMDAwMDEx.baseline.fake-sim-bot"


class EnvFileTests(unittest.TestCase):
    def test_parse_env_handles_comments_quotes_and_export(self):
        text = '# c\nA=1\nexport B="two words"\nC=\'q\'\nD=x # trailing\n\nbad line\nE=a=b\n'
        self.assertEqual(envfile.parse_env(text), {"A": "1", "B": "two words", "C": "q", "D": "x", "E": "a=b"})

    def test_load_secret_returns_a_masked_secret_and_registers_it(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / ".env"
            path.write_text(f"TEAMCTX_LLM_KEY={FAKE_OR}\nOTHER=1\n", encoding="utf-8")
            envfile.REDACTOR.clear()
            secret = envfile.load_secret(path, "TEAMCTX_LLM_KEY")
            self.assertIsNotNone(secret)
            self.assertEqual(secret.reveal(), FAKE_OR)
            for rendered in (str(secret), repr(secret), f"{secret}", f"{secret!r}", "%s" % secret, format(secret, ">20")):
                self.assertNotIn(FAKE_OR, rendered)
            self.assertEqual(envfile.redact(f"key is {FAKE_OR}!"), "key is ***!")
            self.assertIsNone(envfile.load_secret(path, "MISSING"))
            self.assertIsNone(envfile.load_secret(Path(d) / "nope", "X"))

    def test_secret_cannot_be_pickled_copied_or_mutated(self):
        s = envfile.Secret("abcdefgh")
        with self.assertRaises(TypeError):
            pickle.dumps(s)
        self.assertIs(copy.deepcopy(s), s)
        with self.assertRaises(AttributeError):
            s._value = "x"
        self.assertNotIn("abcdefgh", json.dumps({"k": str(s)}))


class RedactionTests(unittest.TestCase):
    def setUp(self):
        envfile.REDACTOR.clear()

    def test_shape_patterns_catch_unregistered_secrets(self):
        samples = [
            FAKE_OR, FAKE_TCTX, f"Authorization: Bearer {FAKE_TCTX}", f"Authorization: Bot {FAKE_BOT}", FAKE_BOT,
            f"http://localhost:3999/_baseline/control/inspector?token={FAKE_CONTROL}&x=1",
            f"X-Baseline-Control-Token: {FAKE_CONTROL}",
            f"    Token: {FAKE_CONTROL}  (header X-Baseline-Control-Token)",
            "sk-ant-api03-" + "A" * 30,
        ]
        for text in samples:
            out = envfile.redact(text)
            for secret in (FAKE_OR, FAKE_TCTX, FAKE_CONTROL, FAKE_BOT, "A" * 30):
                self.assertNotIn(secret, out, text)

    def test_registered_literals_are_masked_everywhere(self):
        envfile.REDACTOR.add(FAKE_CONTROL)
        self.assertEqual(envfile.redact(f"a {FAKE_CONTROL} b {FAKE_CONTROL}"), "a *** b ***")

    def test_plain_text_is_left_alone(self):
        text = "Mark as decision recorded D-12 in #general at 2026-11-11"
        self.assertEqual(envfile.redact(text), text)

    def test_logs_and_timeline_never_contain_fake_secrets(self):
        with tempfile.TemporaryDirectory() as d:
            paths = Paths(Path(d))
            paths.ensure()
            envfile.REDACTOR.add(FAKE_CONTROL)
            out = io.StringIO()
            rec = Recorder(paths, stream=out)
            rec.info(f"token is {FAKE_CONTROL} and key {FAKE_OR} and {FAKE_TCTX}")
            rec.event("x", f"saw {FAKE_OR}", detail={"auth": f"Bot {FAKE_BOT}", "n": 1})
            blob = out.getvalue() + paths.harness_log.read_text() + paths.timeline.read_text()
            for secret in (FAKE_OR, FAKE_TCTX, FAKE_CONTROL, FAKE_BOT):
                self.assertNotIn(secret, blob)

    def test_report_files_never_contain_fake_secrets(self):
        with tempfile.TemporaryDirectory() as d:
            envfile.REDACTOR.add(FAKE_CONTROL)
            checks = [{"id": "1", "name": "n", "status": "pass", "evidence": f"ok {FAKE_OR}",
                       "details": [f"x {FAKE_TCTX}", f"y {FAKE_CONTROL}"], "act": None, "data": {"k": FAKE_OR}}]
            meta = {"run_id": "t", "generated": "now", "scope": "test", "facts": {"key": FAKE_OR}}
            path = R.write_report(Path(d), meta, checks, [{"t": "1", "kind": "k", "summary": FAKE_TCTX}],
                                  {"a": {"label": "l", "actor": "1", "text": f"Bot {FAKE_BOT}"}}, {"observations": [FAKE_OR]})
            blob = path.read_text() + (path.parent / "report.json").read_text()
            for secret in (FAKE_OR, FAKE_TCTX, FAKE_CONTROL, FAKE_BOT):
                self.assertNotIn(secret, blob)
            self.assertIn("PASS", blob)

    def test_child_env_reveals_secrets_only_in_the_child_environment(self):
        key = envfile.Secret(FAKE_OR, "key")
        choice = H.ModelChoice("openrouter", "why", env={"TEAMCTX_LLM_KEY": key})
        self.assertNotIn(FAKE_OR, repr(choice))
        env = H.child_env({"PATH": "p", "SECRET_OTHER": "no"}, {"TEAMCTX_DISCORD_TOKEN": FAKE_BOT, **choice.env})
        self.assertEqual(env["TEAMCTX_LLM_KEY"], FAKE_OR)
        self.assertNotIn("SECRET_OTHER", env)


if __name__ == "__main__":
    unittest.main()
