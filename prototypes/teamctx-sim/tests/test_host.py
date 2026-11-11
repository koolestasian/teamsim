import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

import fakes
from fakes import json_bytes
from simlib import envfile, host as H, net
from simlib.emu import EmuClient, Wsl, parse_startup_log, wait_ready, START_SCRIPT, STOP_SCRIPT, REMOTE_SEED
from simlib.net import FakeTransport, PolicyError, Response, UrllibTransport, assert_loopback_url, multipart

INIT_OUTPUT = """# Offline template. Review and save as teamctx.toml; no file was written.
# LLM off unless [llm] is configured. When enabled, retrieved chat excerpts are sent to the configured provider.
# Invite (open manually after team agreement): https://discord.com/oauth2/authorize?client_id=1&scope=bot
[server]
bind = "127.0.0.1:7420"
timezone = "UTC"

[discord]
guild_id = "410000000000000001"
token_env = "TEAMCTX_DISCORD_TOKEN"
include_channels = []
exclude_channels = []

[discord.reaction_capture]
enabled = false
decision = "\U0001F4CC"

[sync]
backfill_days = 90
recheck_window_hours = 48

[retention]
max_age_days = 0
"""

FAKE_KEY = "sk-or-v1-NOTAREALKEY0123456789abcdef"


class TomlTests(unittest.TestCase):
    def test_set_key_inserts_inside_the_table_before_subtables(self):
        out = H.set_toml_key(INIT_OUTPUT, "discord", "api_url", '"http://localhost:4000"')
        data = tomllib.loads(out)
        self.assertEqual(data["discord"]["api_url"], "http://localhost:4000")
        self.assertEqual(data["discord"]["reaction_capture"]["enabled"], False)
        self.assertLess(out.index("api_url"), out.index("[discord.reaction_capture]"))

    def test_set_key_replaces_an_existing_key_and_adds_new_tables(self):
        out = H.set_toml_key(INIT_OUTPUT, "server", "bind", '"127.0.0.1:9000"')
        self.assertEqual(tomllib.loads(out)["server"]["bind"], "127.0.0.1:9000")
        self.assertEqual(out.count("bind ="), 1)
        out = H.set_toml_key(INIT_OUTPUT, "llm", "model", '"m"')
        self.assertEqual(tomllib.loads(out)["llm"], {"model": "m"})

    def test_build_config_sets_api_url_and_llm_and_drops_the_invite_line(self):
        choice = H.ModelChoice("openrouter", "r", table={"provider": "openai_compatible", "base_url": H.OPENROUTER_BASE,
                                                        "model": H.OPENROUTER_MODEL, "api_key_env": "TEAMCTX_LLM_KEY",
                                                        "max_questions_per_member_per_hour": 40, "max_tokens_per_day": 150000})
        text = H.build_config(INIT_OUTPUT, api_url="http://localhost:4000", choice=choice)
        data = tomllib.loads(text)
        self.assertEqual(data["discord"]["api_url"], "http://localhost:4000")
        self.assertEqual(data["llm"]["provider"], "openai_compatible")
        self.assertEqual(data["llm"]["model"], "anthropic/claude-sonnet-5.5")
        self.assertEqual(data["llm"]["max_tokens_per_day"], 150000)
        self.assertEqual(data["llm"]["api_key_env"], "TEAMCTX_LLM_KEY")
        self.assertNotIn("Invite", text)
        self.assertNotIn(FAKE_KEY, text)

    def test_build_config_without_a_model_has_no_llm_table(self):
        text = H.build_config(INIT_OUTPUT, api_url="http://127.0.0.1:4000", choice=H.ModelChoice("none", "why"))
        self.assertNotIn("llm", tomllib.loads(text))

    def test_build_config_refuses_a_non_loopback_api_url(self):
        with self.assertRaises(PolicyError):
            H.build_config(INIT_OUTPUT, api_url="https://discord.com", choice=H.ModelChoice("none", "x"))


class ModelChoiceTests(unittest.TestCase):
    def transports(self, or_status=None, lm=None):
        orr = FakeTransport()
        if or_status is not None:
            orr.route("POST", "openrouter.ai", (or_status, {"choices": []}))
        local = FakeTransport()
        if lm is not None:
            local.route("GET", "127.0.0.1:1234/v1/models", (200, {"data": [{"id": m} for m in lm]}))
        return orr, local

    def test_openrouter_200_wins_and_probe_shape_is_minimal(self):
        orr, local = self.transports(200, ["qwen"])
        key = envfile.Secret(FAKE_KEY)
        choice = H.choose_model(orr, local, key)
        self.assertEqual(choice.kind, "openrouter")
        self.assertEqual(choice.table["model"], "anthropic/claude-sonnet-5.5")
        self.assertEqual(choice.table["base_url"], "https://openrouter.ai/api/v1")
        call = orr.calls[0]
        self.assertEqual(call["json"]["model"], "anthropic/claude-haiku-5.5")
        self.assertEqual(call["json"]["max_tokens"], 5)
        self.assertTrue(call["headers"]["Authorization"].startswith("Bearer "))
        self.assertEqual(len(orr.calls), 1, "exactly one probe")
        self.assertEqual(local.calls, [], "LM Studio is not probed when OpenRouter works")
        self.assertNotIn(FAKE_KEY, repr(choice))

    def test_falls_back_to_lm_studio_first_chat_model(self):
        orr, local = self.transports(401, ["text-embedding-nomic", "qwen-chat", "other"])
        choice = H.choose_model(orr, local, envfile.Secret(FAKE_KEY))
        self.assertEqual(choice.kind, "lmstudio")
        self.assertEqual(choice.table["model"], "qwen-chat")
        self.assertEqual(choice.table["base_url"], "http://127.0.0.1:1234/v1")
        self.assertIn("401", choice.reason)

    def test_no_key_skips_openrouter_and_none_available_is_reported(self):
        orr, local = self.transports(None, None)
        choice = H.choose_model(orr, local, None)
        self.assertEqual(choice.kind, "none")
        self.assertEqual(orr.calls, [])
        self.assertIn("no TEAMCTX_LLM_KEY", choice.reason)
        self.assertIsNone(choice.table)

    def test_a_real_transport_refuses_other_hosts(self):
        t = UrllibTransport()
        with self.assertRaises(PolicyError):
            t.request("GET", "https://discord.com/api/v10/users/@me")
        with self.assertRaises(PolicyError):
            t.request("POST", "https://openrouter.ai/api/v1/chat/completions")  # loopback-only transport
        UrllibTransport(allow_loopback=False, extra_hosts=frozenset({"openrouter.ai"}))._check("https://openrouter.ai/x")
        with self.assertRaises(PolicyError):
            UrllibTransport(allow_loopback=False, extra_hosts=frozenset({"openrouter.ai"}))._check("http://localhost:4000/")


class TokenAndApiTests(unittest.TestCase):
    def test_extract_token_finds_the_value_and_registers_it(self):
        envfile.REDACTOR.clear()
        out = "created\n  tctx_ABCDEF0123456789abcdef_-xyz\nconnect Claude: TEAMCTX_TOKEN=...\n"
        token = H.extract_token(out)
        self.assertEqual(token, "tctx_ABCDEF0123456789abcdef_-xyz")
        self.assertEqual(envfile.redact(f"x {token} y"), "x *** y")
        self.assertIsNone(H.extract_token("no token here"))

    def test_api_reads_the_token_file_and_never_exposes_it(self):
        with tempfile.TemporaryDirectory() as d:
            tf = Path(d) / "api-token"
            tf.write_text("tctx_FILETOKEN0123456789\n", encoding="utf-8")
            fake = FakeTransport().route("GET", "/api/v1/status", (200, {"status": "ok", "sync": {"gateway": "connected"}}))
            fake.route("POST", "/api/v1/ask", (200, {"found": True}))
            api = H.Api(fake, "http://127.0.0.1:7420", tf)
            self.assertEqual(api.status()["sync"]["gateway"], "connected")
            self.assertEqual(fake.calls[0]["headers"]["Authorization"], "Bearer tctx_FILETOKEN0123456789")
            api.ask("hi")
            self.assertEqual(fake.calls[1]["json"], {"question": "hi"})
            self.assertNotIn("tctx_FILETOKEN0123456789", repr(api.__dict__).replace(str(tf), ""))
            with self.assertRaises(PolicyError):
                H.Api(fake, "http://example.com:7420", tf)

    def test_all_record_follows_cursors_and_attaches_links(self):
        import json
        def page(lines, items, cursor):
            text = "notice\n\n<team-chat-data>\n" + json.dumps("\n".join(lines)) + "\n</team-chat-data>\n\nfoot"
            return (200, {"text": text, "items": items, "next_cursor": cursor})
        with tempfile.TemporaryDirectory() as d:
            tf = Path(d) / "t"
            tf.write_text("tctx_xxxxxxxxxx", encoding="utf-8")
            responses = [page(["D-1 decision active | 2026-11-11 | one"], [{"id": "D-1", "kind": "decision", "link": "https://discord.com/channels/1/2/3"}], "c1"),
                         page(["T-2 task open | 2026-11-11 | owner Pell | due 2026-12-01 | two"], [{"id": "T-2", "kind": "task"}], None)]
            fake = FakeTransport().route("GET", "/api/v1/record", responses)
            rows = H.Api(fake, "http://127.0.0.1:7420", tf).all_record()
            self.assertEqual([r["id"] for r in rows], ["D-1", "T-2"])
            self.assertEqual(rows[0]["link"], "https://discord.com/channels/1/2/3")
            self.assertEqual(rows[1]["due"], "2026-12-01")
            self.assertIn("cursor=c1", fake.calls[1]["url"])


class ProcessTests(unittest.TestCase):
    def test_host_process_command_line_env_and_stop(self):
        events = {}

        class FakePopen:
            def __init__(self, args, **kw):
                events["args"], events["kw"] = args, kw
                self.returncode = None
                self.terminated = False

            def poll(self):
                return self.returncode

            def terminate(self):
                self.terminated = True
                self.returncode = 1

            def wait(self, timeout=None):
                return self.returncode

            def kill(self):
                self.returncode = -9

        class Runner:
            Popen = FakePopen

        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            proc = H.HostProcess(Path("teamctx.exe"), d / "c.toml", d / "x.db", d / "host.log", {"TEAMCTX_DISCORD_TOKEN": "t"}, runner=Runner)
            proc.start()
            self.assertEqual(events["args"][1:], ["run", "--config", str(d / "c.toml"), "--db", str(d / "x.db")])
            self.assertEqual(events["kw"]["env"], {"TEAMCTX_DISCORD_TOKEN": "t"})
            self.assertTrue(proc.alive())
            self.assertEqual(proc.stop(), 1)
            self.assertIn("stopped by harness", (d / "host.log").read_text())

    def test_missing_binary_message_names_the_path_and_the_rule(self):
        with self.assertRaises(H.HostError) as cm:
            H.resolve_binary(r"C:\definitely\not\there\teamctx.exe")
        self.assertIn("never builds Rust", str(cm.exception))


class NetTests(unittest.TestCase):
    def test_loopback_assertion(self):
        for ok in ("http://localhost:4000", "http://127.0.0.1:3999", "ws://localhost:4000/?v=10", "http://[::1]:1", "http://127.1.2.3:1"):
            self.assertEqual(assert_loopback_url(ok), ok)
        for bad in ("http://discord.com", "http://0.0.0.0:4000", "http://192.168.1.5:4000", "http://localhost.example.com:4000",
                    "http://127.0.0.1.nip.io:4000", "http://user@localhost:4000", "file:///x", "http://"):
            with self.assertRaises(PolicyError, msg=bad):
                assert_loopback_url(bad)

    def test_multipart_has_payload_json_and_files(self):
        body, ctype = multipart({"content": "c"}, [("a.png", b"DATA")])
        self.assertTrue(ctype.startswith("multipart/form-data; boundary="))
        self.assertIn(b'name="payload_json"', body)
        self.assertIn(b'name="files[0]"; filename="a.png"', body)
        self.assertIn(b"DATA", body)

    def test_fake_transport_routes_lists_and_callables(self):
        f = FakeTransport().route("GET", "/a", [(200, {"n": 1}), (200, {"n": 2})]).route("GET", "/b", lambda call: (201, {"u": call["url"]}))
        self.assertEqual(f.request("GET", "http://x/a").json(), {"n": 1})
        self.assertEqual(f.request("GET", "http://x/a").json(), {"n": 2})
        self.assertEqual(f.request("GET", "http://x/b").status, 201)
        self.assertEqual(f.request("GET", "http://x/zzz").status, 404)


class EmulatorProcessTests(unittest.TestCase):
    BANNER = """
baseline

  discord  http://localhost:4000

  Control API: http://localhost:3999/_baseline/control  (also on any service port)
    Token: FakeControlTokenValue0123456789abcdef  (header X-Baseline-Control-Token)
    Inspector: http://localhost:3999/_baseline/control/inspector?token=FakeControlTokenValue0123456789abcdef  (faults)

  Ready.
"""

    def test_startup_log_parser_registers_the_control_token_for_redaction(self):
        envfile.REDACTOR.clear()
        info = parse_startup_log(self.BANNER)
        self.assertTrue(info.ready and not info.failed)
        self.assertEqual(info.control_token, "FakeControlTokenValue0123456789abcdef")
        self.assertNotIn("FakeControlTokenValue0123456789abcdef", envfile.redact(self.BANNER))
        self.assertFalse(parse_startup_log("starting...").ready)
        self.assertTrue(parse_startup_log("Error: EADDRINUSE").failed)

    def test_wsl_commands_touch_only_the_emulator_and_feed_the_seed_through_stdin(self):
        calls = []

        class Runner:
            @staticmethod
            def run(args, **kw):
                calls.append((args, kw))
                return subprocess.CompletedProcess(args, 0, stdout=b"log", stderr=b"")

            @staticmethod
            def Popen(args, **kw):
                calls.append((args, kw))
                return object()

        with tempfile.TemporaryDirectory() as d:
            wsl = Wsl(Path(d), runner=Runner)
            wsl.copy_seed({"discord": {"users": []}})
            wsl.start()
            wsl.stop()
            self.assertEqual(wsl.read_log(), "log")
        copy_args, copy_kw = calls[0]
        self.assertEqual(copy_args[:5], ["wsl.exe", "-d", "sbx-ubuntu", "-u", "dev"])
        self.assertEqual(copy_args[-1], f"cat > {REMOTE_SEED}")
        self.assertEqual(copy_kw["input"].decode()[:1], "{")
        start_args = calls[1][0]
        self.assertEqual(start_args[-1], START_SCRIPT)
        self.assertIn("exec npx baseline start --service discord", START_SCRIPT)
        self.assertIn("~/emu", START_SCRIPT)
        stop = calls[2][0][-1]
        self.assertEqual(stop, STOP_SCRIPT)
        self.assertNotIn("rm ", STOP_SCRIPT)
        self.assertIn("[b]aseline start --service discord", STOP_SCRIPT)

    def test_wait_ready_returns_when_banner_and_port_are_up(self):
        fake = fakes.FakeEmulator()
        fake.request_orig = fake.request

        def request(method, url, **kw):
            if url.endswith("/api/v10/gateway/bot"):
                return Response(200, {}, b"{}")
            return fake.request_orig(method, url, **kw)

        fake.request = request
        client = EmuClient(fake, "http://localhost:4000")
        ticks = iter(range(100))
        info = wait_ready(client, lambda: self.BANNER, timeout=5, clock=lambda: next(ticks) * 0.1, sleep=lambda s: None, token="x")
        self.assertTrue(info.ready)
        info = wait_ready(client, lambda: "booting", timeout=1, clock=lambda: next(ticks) * 0.5, sleep=lambda s: None)
        self.assertFalse(info.ready)


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        sim = Path(fakes.ROOT) / "sim.py"
        return subprocess.run([sys.executable, "-I", str(sim), *args], capture_output=True, text=True, timeout=60)

    def test_help_works_offline(self):
        out = self.run_cli("--help")
        self.assertEqual(out.returncode, 0)
        for command in ("seed", "emu", "post", "captures", "check", "run-all", "report", "reset", "token", "config", "host"):
            self.assertIn(command, out.stdout)

    def test_run_all_dry_run_prints_the_plan_without_network(self):
        out = self.run_cli("run-all", "--dry-run")
        self.assertEqual(out.returncode, 0, out.stderr)
        text = out.stdout
        for needle in ("-- act 1", "-- act 2", "-- act 3", "-- act 4", "history experiment", "gateway-disconnect", "stop teamctx",
                       "capture c01", "checks 3 to 10", "OpenRouter"):
            self.assertIn(needle, text)
        self.assertNotIn("sk-or", text)

    def test_post_dry_run_lists_calls(self):
        out = self.run_cli("post", "--act", "2", "--dry-run")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("message-delete", out.stdout)
        self.assertIn("#leads", out.stdout)


if __name__ == "__main__":
    unittest.main()
