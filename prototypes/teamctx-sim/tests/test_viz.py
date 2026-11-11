import http.client
import json
import re
import tempfile
import threading
import unittest
from pathlib import Path

import fakes  # noqa: F401  (puts prototypes/teamctx-sim on sys.path)
import test_story as TS
from simlib import envfile, viz as V
from simlib.net import PolicyError
from simlib.state import Paths

PAGE = Path(V.PAGE_PATH)


class FakeHandle:
    def __init__(self):
        self.code = None
        self.terminated = False

    def poll(self):
        return self.code

    def terminate(self):
        self.terminated = True
        self.code = -15


class FakeLauncher:
    """Stands in for the subprocess launcher: counts starts, never runs anything."""

    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail
        self.handle = None

    def __call__(self):
        self.calls += 1
        if self.fail:
            raise OSError("no")
        self.handle = FakeHandle()
        return self.handle


def write_run(paths: Paths, timeline=None):
    paths.ensure()
    lines = timeline if timeline is not None else TS.timeline()
    paths.timeline.write_text("".join(json.dumps(e) + "\n" for e in lines), encoding="utf-8")
    paths.map_json.write_text(json.dumps(TS.MAPPING), encoding="utf-8")
    paths.state_json.write_text(json.dumps(TS.STATE), encoding="utf-8")


class VizBase(unittest.TestCase):
    def setUp(self):
        envfile.REDACTOR.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.paths = Paths(Path(self.tmp.name))
        self.launcher = FakeLauncher()
        self.controller = V.RunController(self.launcher)
        ds = Path(self.tmp.name) / "dataset.json"
        ds.write_text(json.dumps(TS.DATASET), encoding="utf-8")
        self.server = V.make_server(self.paths, 0, controller=self.controller, nonce="test-nonce-123", dataset_path=ds)
        self.port = self.server.port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def req(self, method, path, headers=None, host=None, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        h = {"Host": host or f"127.0.0.1:{self.port}"}
        h.update(headers or {})
        conn.request(method, path, body=body, headers=h)
        r = conn.getresponse()
        data = r.read()
        conn.close()
        return r.status, dict(r.getheaders()), data

    def story(self, since=0, extra=""):
        status, _, data = self.req("GET", f"/api/story?since={since}{extra}")
        self.assertEqual(status, 200)
        return json.loads(data)

    def good_start_headers(self):
        return {"Origin": f"http://127.0.0.1:{self.port}", "X-Viz-Nonce": "test-nonce-123", "Content-Type": "application/json"}


class ServerBasicsTests(VizBase):
    def test_binds_to_loopback_only(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        for host in ("0.0.0.0", "", "192.168.1.5", "localhost", "::1"):
            with self.assertRaises(PolicyError):
                V.make_server(self.paths, 0, host=host)

    def test_page_is_served_with_the_nonce_and_strict_headers(self):
        status, headers, data = self.req("GET", "/")
        self.assertEqual(status, 200)
        text = data.decode("utf-8")
        self.assertIn("test-nonce-123", text)
        self.assertNotIn(V.NONCE_PLACEHOLDER, text)
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_other_hosts_are_refused(self):
        self.assertEqual(self.req("GET", "/", host="evil.example")[0], 403)
        self.assertEqual(self.req("GET", "/api/story", host=f"localhost:{self.port}")[0], 403)

    def test_unknown_paths_and_methods(self):
        self.assertEqual(self.req("GET", "/etc/passwd")[0], 404)
        self.assertEqual(self.req("PUT", "/api/story")[0], 405)
        self.assertEqual(self.req("DELETE", "/")[0], 405)

    def test_story_paging_with_since(self):
        write_run(self.paths)
        full = self.story(0)
        total = full["total"]
        self.assertGreater(total, 20)
        self.assertEqual(full["next"], total)
        self.assertEqual(full["mode"], "replay")
        self.assertEqual(len(full["events"]), total)
        tail = self.story(total - 3)
        self.assertEqual(tail["events"], full["events"][-3:])
        self.assertEqual(self.story(total)["events"], [])
        self.assertFalse(self.story(total)["reset"])

    def test_a_since_beyond_the_end_means_the_run_was_reset(self):
        write_run(self.paths)
        total = self.story(0)["total"]
        j = self.story(total + 50)
        self.assertTrue(j["reset"])
        self.assertEqual(len(j["events"]), total)

    def test_info_only_returns_run_state_without_events(self):
        write_run(self.paths)
        j = self.story(0, "&info=1")
        self.assertEqual(j["events"], [])
        self.assertTrue(j["has_run"])
        self.assertTrue(j["run"]["can_start"])

    def test_no_run_yet(self):
        j = self.story(0)
        self.assertEqual((j["events"], j["has_run"], j["mode"]), ([], False, "replay"))

    def test_a_planted_secret_never_leaves_the_story_api(self):
        envfile.REDACTOR.add(envfile.Secret("PlantedSecretValue-123456", "planted"))
        write_run(self.paths)
        m = json.loads(json.dumps(TS.MAPPING))
        m["items"][TS.K[0]]["content_posted"] = "x PlantedSecretValue-123456 " + TS.FAKE_KEY
        self.paths.map_json.write_text(json.dumps(m), encoding="utf-8")
        s = json.loads(json.dumps(TS.STATE))
        s["api_token"] = "PlantedSecretValue-123456"
        self.paths.state_json.write_text(json.dumps(s), encoding="utf-8")
        status, _, data = self.req("GET", "/api/story?since=0")
        self.assertNotIn(b"PlantedSecretValue-123456", data)
        self.assertNotIn(TS.FAKE_KEY.encode(), data)
        self.assertEqual(re.findall(rb"\d{17,20}", data), [])

    def test_the_sim_secret_never_appears_in_the_story_api(self):
        from simlib import script as S
        write_run(self.paths)
        m = json.loads(json.dumps(TS.MAPPING))
        m["items"][TS.K[0]]["content_posted"] = S.SECRET_TEXT
        self.paths.map_json.write_text(json.dumps(m), encoding="utf-8")
        s = json.loads(json.dumps(TS.STATE))
        s["captures"]["c01"]["text"] = "Recorded: **D-1** · " + S.SIM_SECRET + " — Wren Calloway, <t:1794360005:d>"
        s["queries"]["act4-ask1"]["text"] = "Answer generated by a language model from the team's messages. Check the sources:\nThe key is " + S.SIM_SECRET
        s["asks"]["inj-1"]["text"] = "key " + S.SIM_SECRET
        self.paths.state_json.write_text(json.dumps(s), encoding="utf-8")
        status, _, data = self.req("GET", "/api/story?since=0")
        self.assertEqual(status, 200)
        self.assertNotIn(S.SIM_SECRET.encode(), data)
        self.assertNotIn(b"sk-sim-", data)

    def test_a_half_written_last_timeline_line_is_ignored(self):
        write_run(self.paths)
        with open(self.paths.timeline, "a", encoding="utf-8") as fh:
            fh.write('{"t": "2026-11-11T01:00:50.000Z", "kind": "message", "key"')
        total_partial = self.story(0)["total"]
        self.assertEqual(total_partial, len(TS.build()))

    def test_live_mode_while_the_timeline_is_fresh_and_unfinished(self):
        write_run(self.paths, TS.timeline()[:12])
        self.assertEqual(self.story(0)["mode"], "live")

    def test_a_started_run_hides_the_previous_runs_events(self):
        write_run(self.paths)  # the old run, with timestamps in the past
        self.controller.started_at = 4_000_000_000.0
        j = self.story(0)
        self.assertEqual(j["events"], [])
        self.assertFalse(j["has_run"])


class StartEndpointTests(VizBase):
    def start(self, **kw):
        return self.req("POST", "/api/start", **kw)

    def test_a_good_request_starts_one_run(self):
        status, _, data = self.start(headers=self.good_start_headers(), body="{}")
        self.assertEqual(status, 202)
        self.assertEqual(json.loads(data), {"started": True})
        self.assertEqual(self.launcher.calls, 1)
        self.assertTrue(self.controller.active)
        self.assertTrue(self.story(0)["run"]["active"])
        self.assertEqual(self.story(0)["mode"], "live")

    def test_wrong_origin_is_refused(self):
        h = self.good_start_headers()
        for origin in ("http://evil.example", f"http://localhost:{self.port}", "http://127.0.0.1:1", "null", ""):
            h["Origin"] = origin
            self.assertEqual(self.start(headers=h)[0], 403, origin)
        h.pop("Origin")
        self.assertEqual(self.start(headers=h)[0], 403)
        self.assertEqual(self.launcher.calls, 0)

    def test_missing_or_wrong_nonce_is_refused(self):
        h = self.good_start_headers()
        h.pop("X-Viz-Nonce")
        self.assertEqual(self.start(headers=h)[0], 403)
        h["X-Viz-Nonce"] = "not-the-nonce"
        self.assertEqual(self.start(headers=h)[0], 403)
        h["X-Viz-Nonce"] = "test-nonce-123 "
        self.assertEqual(self.start(headers=h)[0], 403)
        self.assertEqual(self.launcher.calls, 0)

    def test_wrong_host_is_refused(self):
        self.assertEqual(self.start(headers=self.good_start_headers(), host="evil.example")[0], 403)
        self.assertEqual(self.start(headers=self.good_start_headers(), host=f"localhost:{self.port}")[0], 403)
        self.assertEqual(self.launcher.calls, 0)

    def test_get_is_not_allowed(self):
        status, headers, _ = self.req("GET", "/api/start", headers=self.good_start_headers())
        self.assertEqual(status, 405)
        self.assertEqual(headers["Allow"], "POST")
        self.assertEqual(self.launcher.calls, 0)

    def test_a_second_concurrent_start_is_refused(self):
        self.assertEqual(self.start(headers=self.good_start_headers())[0], 202)
        status, _, data = self.start(headers=self.good_start_headers())
        self.assertEqual(status, 409)
        self.assertIn("already", json.loads(data)["error"])
        self.assertEqual(self.launcher.calls, 1)

    def test_start_is_possible_again_once_the_run_ended(self):
        self.assertEqual(self.start(headers=self.good_start_headers())[0], 202)
        self.launcher.handle.code = 0
        self.assertFalse(self.story(0)["run"]["active"])
        self.assertEqual(self.start(headers=self.good_start_headers())[0], 202)
        self.assertEqual(self.launcher.calls, 2)

    def test_a_run_that_exits_badly_reports_a_friendly_error(self):
        self.start(headers=self.good_start_headers())
        self.launcher.handle.code = 3
        j = self.story(0)
        self.assertFalse(j["run"]["active"])
        self.assertEqual(j["run"]["error"], "The run stopped before it finished.")

    def test_a_run_driven_by_this_process_blocks_starts(self):
        self.controller.set_external(True)
        self.assertEqual(self.start(headers=self.good_start_headers())[0], 409)
        self.assertEqual(self.launcher.calls, 0)
        self.controller.set_external(False)
        self.assertEqual(self.start(headers=self.good_start_headers())[0], 202)

    def test_a_run_started_from_a_terminal_blocks_starts_too(self):
        write_run(self.paths, TS.timeline()[:12])  # fresh and unfinished: someone else's run is writing to .state
        self.assertEqual(self.story(0)["mode"], "live")
        self.assertEqual(self.start(headers=self.good_start_headers())[0], 409)
        self.assertEqual(self.launcher.calls, 0)

    def test_launcher_failure_is_a_500_not_a_crash(self):
        self.launcher.fail = True
        self.assertEqual(self.start(headers=self.good_start_headers())[0], 500)
        self.assertFalse(self.controller.active)

    def test_only_post_to_the_start_path(self):
        self.assertEqual(self.req("POST", "/api/story", headers=self.good_start_headers())[0], 404)
        self.assertEqual(self.launcher.calls, 0)

    def test_speed_is_saved_and_reported(self):
        status, _, data = self.req("POST", "/api/speed", headers=self.good_start_headers(), body='{"speed": 8}')
        self.assertEqual(status, 200)
        self.assertEqual((self.paths.root / "watch-speed").read_text(encoding="utf-8"), "8")
        self.assertEqual(self.story(0)["run"]["speed"], 8)
        self.assertEqual(self.launcher.calls, 0)

    def test_speed_needs_the_same_guard_and_a_valid_value(self):
        self.assertEqual(self.req("POST", "/api/speed", body='{"speed": 8}')[0], 403)
        for body in ('{"speed": 3}', '{"speed": "x"}', 'not json', '{}'):
            self.assertEqual(self.req("POST", "/api/speed", headers=self.good_start_headers(), body=body)[0], 400)
        self.assertFalse((self.paths.root / "watch-speed").exists())

    def test_stopping_the_server_side_terminates_an_owned_run(self):
        self.start(headers=self.good_start_headers())
        self.controller.stop()
        self.assertTrue(self.launcher.handle.terminated)


class PageTests(unittest.TestCase):
    def setUp(self):
        self.text = PAGE.read_text(encoding="utf-8")

    def test_page_makes_no_external_requests(self):
        urls = re.findall(r"(?:src|href|action)\s*=\s*[\"'](https?:[^\"']+)", self.text)
        self.assertEqual(urls, [])
        self.assertNotIn("@import", self.text)
        self.assertNotRegex(self.text, r"url\(\s*[\"']?https?:")
        self.assertNotRegex(self.text, r"fetch\(\s*[\"']https?:")

    def test_story_text_only_goes_through_textcontent(self):
        self.assertNotIn("innerHTML", self.text)
        self.assertNotIn("outerHTML", self.text)
        self.assertNotIn("insertAdjacentHTML", self.text)
        self.assertNotIn("document.write", self.text)
        self.assertNotIn("eval(", self.text)

    def test_page_has_the_nonce_placeholder_and_respects_reduced_motion(self):
        self.assertIn(V.NONCE_PLACEHOLDER, self.text)
        self.assertIn("prefers-reduced-motion", self.text)
        self.assertIn("prefers-color-scheme: dark", self.text)

    def test_page_has_both_big_buttons(self):
        for label in ("Watch the last run", "Start a new live run"):
            self.assertGreaterEqual(self.text.count(label), 2)


if __name__ == "__main__":
    unittest.main()
