import datetime as dt
import json
import random
import tempfile
import unittest
from pathlib import Path

import fakes
from fakes import FakeEmulator, json_bytes, snowflake
from simlib import driver as D, envfile, script as S
from simlib.emu import EmuClient, EmuError
from simlib.net import PolicyError, Response
from simlib.state import JsonStore, Paths, Recorder

DS = S.load_dataset()
IDS = D.IdMap.from_dataset(DS)
TODAY = dt.date(2026, 11, 11)


def item(key, channel="general", author="101", content="hello", **kw):
    return S.PostItem(key=key, act=kw.pop("act", 1), channel=channel, author=author, content=content,
                      final_content=kw.pop("final_content", content), **kw)


class Clock:
    def __init__(self):
        self.now = 1000.0
        self.slept = []

    def __call__(self):
        return self.now

    def sleep(self, secs):
        self.slept.append(secs)
        self.now += secs


class DriverBase(unittest.TestCase):
    def make(self, items, fake=None, **kw):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.paths = Paths(Path(self.tmp.name))
        self.paths.ensure()
        self.fake = fake or FakeEmulator()
        self.clock = Clock()
        self.emu = EmuClient(self.fake, "http://localhost:4000", sleep=self.clock.sleep)
        self.map = JsonStore(self.paths.map_json)
        self.state = JsonStore(self.paths.state_json)
        self.rec = Recorder(self.paths, echo=False)
        return D.Driver(self.emu, self.map, self.state, items, IDS, DS, self.rec,
                        crash_token=envfile.Secret("MjAw.crash.token-fake"), teamctx_token=envfile.Secret("MjAw.teamctx.token-fake"),
                        clock=self.clock, sleep=self.clock.sleep, rng=random.Random(1), today=TODAY, **kw)

    def posts(self):
        return [c for c in self.fake.calls if c["path"] == "/_discord/simulate/message"]


class PostingTests(DriverBase):
    def test_message_request_shape_and_map_entry(self):
        d = self.make([item("k1", content="hello world", author="102", channel="design")])
        d.post_act(1)
        (call,) = self.posts()
        self.assertEqual(call["json"], {"user_id": IDS.users["102"], "channel_id": IDS.channels["design"], "content": "hello world"})
        entry = self.map["items"]["k1"]
        self.assertEqual(entry["state"], "posted")
        self.assertEqual(entry["channel_id"], IDS.channels["design"])
        self.assertEqual(entry["poster"], IDS.users["102"])
        self.assertIn(entry["emu_id"], self.fake.messages)
        self.assertTrue(entry["posted_at"].startswith("2026-"))

    def test_reply_uses_the_mapped_emulator_id(self):
        d = self.make([item("a"), item("b", reply_to="a", author="103")])
        d.post_act(1)
        a, b = (self.map["items"][k]["emu_id"] for k in ("a", "b"))
        self.assertEqual(self.posts()[1]["json"]["message_reference"], {"message_id": a, "channel_id": IDS.channels["general"]})
        self.assertEqual(self.fake.messages[b]["message_reference"]["message_id"], a)

    def test_bot_author_posts_through_rest_with_its_own_token(self):
        d = self.make([item("bot1", channel="release-ops", author="107", content="digest")])
        d.post_act(1)
        rest = [c for c in self.fake.calls if c["path"].endswith("/messages") and c["method"] == "POST"]
        self.assertEqual(len(rest), 1)
        self.assertEqual(rest[0]["path"], f"/api/v10/channels/{IDS.channels['release-ops']}/messages")
        self.assertTrue(rest[0]["headers"]["Authorization"].startswith("Bot "))
        self.assertEqual(rest[0]["json"], {"content": "digest"})
        self.assertEqual(self.posts(), [])

    def test_edit_flow_posts_draft_then_updates_to_final_content(self):
        d = self.make([item("e1", content="text (draft)", final_content="text")])
        d.post_act(1)
        upd = [c for c in self.fake.calls if c["path"].endswith("message-update")]
        self.assertEqual(len(upd), 1)
        self.assertEqual(upd[0]["json"]["content"], "text")
        self.assertEqual(upd[0]["json"]["user_id"], IDS.users["101"])
        self.assertEqual(self.fake.messages[self.map["items"]["e1"]["emu_id"]]["content"], "text")
        self.assertTrue(self.map["items"]["e1"]["edited"])
        self.assertTrue(2.0 <= sum(self.clock.slept) <= 6.5, self.clock.slept)  # edit waits 2-5 s after the post

    def test_delete_flow_removes_the_message_after_a_delay(self):
        d = self.make([item("w1", content="wrong channel, ignore", delete_later=True, kind="wrong_channel")])
        d.post_act(1)
        self.assertEqual(self.fake.messages, {})
        self.assertTrue(self.map["items"]["w1"]["deleted"])
        deletes = [c for c in self.fake.calls if c["path"].endswith("message-delete")]
        self.assertEqual(set(deletes[0]["json"]), {"user_id", "message_id"})

    def test_pace_jitter_is_between_0_3_and_1_2_seconds_and_zero_when_fast(self):
        d = self.make([item(f"m{i}") for i in range(30)])
        d.post_act(1)
        gaps = [s for s in self.clock.slept]
        self.assertTrue(gaps and all(0.3 <= g <= 1.2 for g in gaps), gaps)
        d2 = self.make([item(f"m{i}") for i in range(5)], pace=0.0)
        d2.post_act(1)
        self.assertEqual(self.clock.slept, [])

    def test_rate_limit_is_retried_with_retry_after(self):
        fake = FakeEmulator()
        fake.rate_limit_next = 2
        d = self.make([item("r1")], fake=fake)
        d.post_act(1)
        self.assertEqual(len(self.posts()), 3)  # two 429s then success
        self.assertEqual(len(fake.messages), 1)
        self.assertEqual(len([s for s in self.clock.slept if abs(s - 0.06) < 1e-6]), 2)  # retry_after 0.01 + 0.05 twice

    def test_resume_does_not_post_twice(self):
        items = [item("a"), item("b"), item("c")]
        d = self.make(items)
        d.post_act(1)
        first = len(self.posts())
        d2 = D.Driver(self.emu, JsonStore(self.paths.map_json), JsonStore(self.paths.state_json), items, IDS, DS, self.rec,
                      clock=self.clock, sleep=self.clock.sleep, rng=random.Random(2), today=TODAY)
        out = d2.post_act(1)
        self.assertEqual(out, {"act": 1, "posted": 0, "skipped": 3})
        self.assertEqual(len(self.posts()), first)
        self.assertEqual(len(self.fake.messages), 3)

    def test_resume_after_a_crash_between_post_and_save_adopts_the_existing_message(self):
        fake = FakeEmulator()
        fake.fail_after_post = 2  # the second POST is stored by the emulator, then the client call dies
        items = [item("a"), item("b"), item("c")]
        d = self.make(items, fake=fake)
        with self.assertRaises(OSError):
            d.post_act(1)
        self.assertEqual(len(fake.messages), 2)
        self.assertEqual(self.map["items"]["b"]["state"], "posting")
        d2 = D.Driver(self.emu, JsonStore(self.paths.map_json), JsonStore(self.paths.state_json), items, IDS, DS, self.rec,
                      teamctx_token=envfile.Secret("MjAw.teamctx.token-fake"), clock=self.clock, sleep=self.clock.sleep,
                      rng=random.Random(3), today=TODAY)
        d2.post_act(1)
        self.assertEqual(len(fake.messages), 3, "b must be adopted, not posted again")
        self.assertEqual({v["state"] for v in d2.map["items"].values()}, {"posted"})

    def test_resume_finishes_pending_followups(self):
        d = self.make([item("e", content="x (draft)", final_content="x")])
        d.post_act(1)
        self.map["items"]["e"]["edited"] = False  # as if the run died before the edit
        self.fake.messages[self.map["items"]["e"]["emu_id"]]["content"] = "x (draft)"
        d.post_act(1)
        self.assertEqual(self.fake.messages[self.map["items"]["e"]["emu_id"]]["content"], "x")

    def test_attachments_are_tried_once_and_recorded_as_unsupported(self):
        items = [item("p1", attachments=("a.png",)), item("p2", attachments=("b.png",)), item("p3")]
        d = self.make(items)
        d.post_act(1)
        self.assertIs(self.state["attachments_supported"], False)
        multipart = [c for c in self.posts() if c["data"] is not None]
        self.assertEqual(len(multipart), 1, "after the first miss the rest are posted without files")
        self.assertIn(b"placeholder for a fictional simulation", multipart[0]["data"])
        self.assertIn(b'filename="a.png"', multipart[0]["data"])

    def test_attachments_supported_when_the_emulator_returns_them(self):
        fake = FakeEmulator()
        fake.attachments_supported = True
        d = self.make([item("p1", attachments=("a.png",)), item("p2", attachments=("b.png",))], fake=fake)
        d.post_act(1)
        self.assertIs(self.state["attachments_supported"], True)
        self.assertEqual(len([c for c in self.posts() if c["data"] is not None]), 2)

    def test_disconnects_are_called_with_the_application_id_and_burst_posted(self):
        items = [item(f"m{i}") for i in range(9)]
        d = self.make(items)
        d.post_act(1, disconnects=[(1 / 3, "reconnect"), (2 / 3, "invalidate")])
        calls = [c["json"] for c in self.fake.disconnects and [{"json": x} for x in self.fake.disconnects]]
        self.assertEqual([c["mode"] for c in calls], ["reconnect", "invalidate"])
        self.assertTrue(all(c["application_id"] == IDS.app for c in calls))
        records = self.state["disconnects"]
        self.assertEqual([r["mode"] for r in records], ["reconnect", "invalidate"])
        self.assertTrue(all(len(r["keys"]) == 3 for r in records), records)
        # resumed run does not disconnect again
        d.post_act(1, disconnects=[(1 / 3, "reconnect"), (2 / 3, "invalidate")])
        self.assertEqual(len(self.fake.disconnects), 2)

    def test_dry_run_plan_makes_no_calls_and_no_state(self):
        d = self.make([item("a"), item("b", content="t (draft)", final_content="t"), item("c", delete_later=True),
                       item("d", attachments=("z.png",), reply_to="a")])
        lines = d.plan_calls(1)
        self.assertEqual(self.fake.calls, [])
        self.assertEqual(self.map["items"], {})
        self.assertTrue(any("message-update" in l for l in lines))
        self.assertTrue(any("message-delete" in l for l in lines))
        self.assertTrue(any("attachments" in l for l in lines))


class SafetyTests(DriverBase):
    def test_non_loopback_emulator_url_is_refused(self):
        for url in ("http://discord.com", "http://example.com:4000", "https://10.0.0.5:4000", "http://localhost.evil.com:4000",
                    "http://user:pw@localhost:4000", "ftp://localhost"):
            with self.assertRaises(PolicyError, msg=url):
                EmuClient(FakeEmulator(), url)
        for url in ("http://localhost:4000", "http://127.0.0.1:4000", "http://127.9.9.9:1", "http://[::1]:4000"):
            EmuClient(FakeEmulator(), url)


class InteractionTests(DriverBase):
    def answer(self, body, **over):
        out = {"interaction": {"id": snowflake(100), "token": "tok1"}, "delivery": "gateway", "status": None,
               "response": {"type": 4, "data": {"content": "Recorded: **D-7** · x", "flags": 64}},
               "message": {"id": snowflake(100 + 3000), "content": "Recorded: **D-7** · x", "flags": 64, "embeds": []}}
        out.update(over)
        return out

    def test_decide_request_shape_and_result(self):
        d = self.make([])
        self.fake.responder = lambda body: self.answer(body)
        r = d.slash("101", "general", "decide", {"text": "Beta ships"}, key="c1", label="decide")
        body = self.fake.interaction_log[-1]
        self.assertEqual(body, {"user_id": IDS.users["101"], "channel_id": IDS.channels["general"], "command": "decide",
                                "options": {"text": "Beta ships"}})
        self.assertTrue(r.ok and r.ephemeral and not r.deferred)
        self.assertEqual(r.first_type, 4)
        self.assertEqual(r.refs, ["D-7"])
        self.assertEqual(r.answer_ms, 3000.0)

    def test_public_flag_is_not_ephemeral(self):
        d = self.make([])
        self.fake.responder = lambda body: self.answer(body, response={"type": 4, "data": {"content": "x"}})
        r = d.slash("101", "general", "decisions", {"public": True})
        self.assertFalse(r.ephemeral)

    def test_subcommand_uses_the_subcommand_field_and_falls_back_to_raw_options(self):
        d = self.make([])
        calls = []

        def responder(body):
            calls.append(body)
            if "subcommand" in body:
                return Response(400, {}, json_bytes({"message": "Invalid Form Body", "errors": {"subcommand": {"_errors": []}}}))
            return self.answer(body)

        self.fake.responder = responder
        r = d.slash("101", "general", "todo", {"text": "t", "owner": IDS.users["106"], "due": "2026-12-01"}, "add")
        self.assertEqual(calls[0]["subcommand"], "add")
        self.assertEqual(calls[1]["options"], [{"name": "add", "type": 1, "options": [
            {"name": "text", "type": 3, "value": "t"}, {"name": "owner", "type": 6, "value": IDS.users["106"]},
            {"name": "due", "type": 3, "value": "2026-12-01"}]}])
        self.assertNotIn("subcommand", calls[1])
        self.assertTrue(r.ok)

    def test_context_menu_request_targets_the_mapped_message(self):
        d = self.make([item("m1", channel="design")])
        d.post_act(1)
        target = self.map["items"]["m1"]["emu_id"]
        self.fake.responder = lambda body: self.answer(body)
        r = d.menu("105", "design", "Mark as decision", target)
        body = self.fake.interaction_log[-1]
        self.assertEqual(body["command_type"], 3)
        self.assertEqual(body["target_id"], target)
        self.assertEqual(body["command"], "Mark as decision")
        self.assertEqual(body["channel_id"], IDS.channels["design"])
        self.assertTrue(r.ok)

    def test_task_menu_opens_a_form_then_submits_modal_values(self):
        d = self.make([])
        seen = []

        def responder(body):
            seen.append(body)
            if body.get("type") == "modal_submit":
                return self.answer(body, response={"type": 4, "data": {"content": "Recorded as a task: **T-3**", "flags": 64}},
                                   message={"id": snowflake(3100), "content": "Recorded as a task: **T-3**", "flags": 64})
            return self.answer(body, response={"type": 9, "data": {"custom_id": "task:1:2", "components": []}}, message=None)

        self.fake.responder = responder
        r = d.menu("105", "general", "Mark as task", "123", modal={"owner": "106", "due": "2026-12-04"}, key="c5")
        self.assertEqual(seen[1]["type"], "modal_submit")
        self.assertEqual(seen[1]["interaction_id"], snowflake(100))
        self.assertEqual(seen[1]["values"], {"owner": [IDS.users["106"]], "due": "2026-12-04"})
        self.assertTrue(r.modal_opened and r.ok)
        self.assertEqual(r.refs, ["T-3"])

    def test_modal_with_an_unreadable_owner_is_resubmitted_without_it_and_marked_degraded(self):
        d = self.make([])
        seen = []

        def responder(body):
            seen.append(body)
            if body.get("type") == "modal_submit":
                text = "I could not read that command. Please try again." if "owner" in body["values"] else "Recorded as a task: **T-3**"
                return self.answer(body, response={"type": 4, "data": {"content": text, "flags": 64}},
                                   message={"id": snowflake(3100), "content": text, "flags": 64})
            return self.answer(body, response={"type": 9, "data": {}}, message=None)

        self.fake.responder = responder
        r = d.menu("105", "general", "Mark as task", "123", modal={"owner": "106", "due": "2026-12-04"})
        self.assertEqual([("owner" in b.get("values", {})) for b in seen[1:]], [True, False])
        self.assertTrue(r.degraded and r.ok)
        self.assertEqual(r.refs, ["T-3"])
        self.assertIn("owner dropped", r.note)

    def test_deferred_reply_is_polled_until_edited(self):
        d = self.make([])
        polls = {"n": 0}

        def responder(body):
            self.fake.original["tok1"] = {"id": "9", "content": "", "embeds": [], "edited_timestamp": None, "timestamp": "2026-11-11T00:00:00.000+00:00"}
            return self.answer(body, response={"type": 5, "data": {"flags": 64}},
                               message={"id": snowflake(3100), "content": "", "flags": 64, "timestamp": "2026-11-11T00:00:00.000+00:00"})

        self.fake.responder = responder
        original_call = self.fake.request

        def request(method, url, **kw):
            if "@original" in url:
                polls["n"] += 1
                if polls["n"] == 3:
                    self.fake.original["tok1"] = {"id": "9", "content": "", "flags": 64, "embeds": [
                        {"title": "Search results", "description": "line one"}], "edited_timestamp": "2026-11-11T00:00:02.500+00:00",
                        "timestamp": "2026-11-11T00:00:00.000+00:00"}
            return original_call(method, url, **kw)

        self.fake.request = request
        r = d.slash("102", "general", "search", {"query": "pdf"})
        self.assertTrue(r.deferred and r.edited and r.ok and not r.error)
        self.assertIn("Search results", r.text)
        self.assertEqual(r.edit_ms, 2500.0)
        self.assertGreaterEqual(polls["n"], 3)

    def test_deferred_reply_that_is_never_edited_is_reported(self):
        d = self.make([])
        self.fake.original["tok1"] = {"id": "9", "content": "", "embeds": [], "edited_timestamp": None}
        self.fake.responder = lambda body: self.answer(body, response={"type": 5, "data": {}}, message={"id": snowflake(3100)})
        r = d.slash("102", "general", "catchup", {}, wait=3.0)
        self.assertTrue(r.deferred and not r.edited)
        self.assertIn("not edited", r.error)

    def test_no_answer_and_http_errors_become_errors_not_exceptions(self):
        d = self.make([])
        r = d.slash("101", "general", "decide", {"text": "x"})
        self.assertFalse(r.ok)
        self.assertIn("no answer", r.error)
        self.fake.responder = lambda body: Response(403, {}, b'{"message":"Missing Permissions","code":50013}')
        r2 = d.slash("101", "general", "decide", {"text": "x"})
        self.assertIn("403", r2.error)

    def test_placeholders_are_resolved(self):
        mapping = {"1477970509244268610": {"emu_id": "999", "channel_id": IDS.channels["general"]}}
        kw = dict(aliases={"1": "D-4"}, ids=IDS, mapping=mapping, today=TODAY)
        self.assertEqual(D.resolve_value("$alias:1", **kw), "D-4")
        self.assertEqual(D.resolve_value("$user:106", **kw), IDS.users["106"])
        self.assertEqual(D.resolve_value("$due:+10", **kw), "2026-11-21")
        self.assertEqual(D.resolve_value("$link:1477970509244268610", **kw),
                         f"https://discord.com/channels/{S.GUILD_ID}/{IDS.channels['general']}/999")
        self.assertIs(D.resolve_value(True, **kw), True)
        self.assertEqual(D.resolve_value("plain", **kw), "plain")
        with self.assertRaises(KeyError):
            D.resolve_value("$alias:99", **kw)

    def test_capture_records_alias_and_resumes_without_rerunning(self):
        d = self.make([])
        cap = S.build_captures(DS)[0]  # /decide beta date
        self.fake.responder = lambda body: self.answer(body)
        r = d.run_capture(cap)
        self.assertEqual(self.state["aliases"]["1"], "D-7")
        count = len(self.fake.interaction_log)
        again = d.run_capture(cap)
        self.assertEqual(len(self.fake.interaction_log), count)
        self.assertTrue(again.ok)
        self.assertEqual(r.refs, again.refs)

    def test_a_capture_whose_prerequisite_is_missing_is_blocked_not_sent(self):
        d = self.make([])
        cap = next(c for c in S.build_captures(DS) if c.options.get("replaces") == "$alias:1")
        r = d.run_capture(cap)
        self.assertIn("blocked", r.error)
        self.assertEqual(self.fake.interaction_log, [])

    def test_flatten_message_includes_embeds(self):
        text = D.flatten_message({"content": "c", "embeds": [{"title": "T", "description": "D", "fields": [{"name": "n", "value": "v"}],
                                                              "footer": {"text": "F"}}]})
        self.assertEqual(text.split("\n"), ["c", "T", "D", "n: v", "F"])

    def test_snowflake_ms_matches_discord_epoch(self):
        self.assertEqual(D.snowflake_ms(0), 1420070400000)
        self.assertEqual(D.snowflake_ms(1 << 22), 1420070400001)


class WatchPaceTests(DriverBase):
    answer = InteractionTests.answer
    """`--watch`: a watchable pace (2-4 s between messages, 2 s around commands), not copy-pasted logic."""

    def test_watch_pace_sleeps_two_to_four_seconds_between_messages(self):
        d = self.make([item("a"), item("b"), item("c")], pace=0.0, watch=True)
        d.post_act(1)
        gaps = [s for s in self.clock.slept if s >= 1.9]
        self.assertEqual(len(gaps), 3)
        self.assertTrue(all(2.0 <= g <= 4.0 for g in gaps))

    def test_default_pace_is_unchanged(self):
        d = self.make([item("a"), item("b")], pace=0.0)
        d.post_act(1)
        self.assertEqual(self.clock.slept, [])

    def test_watch_pauses_two_seconds_before_and_after_a_command(self):
        d = self.make([], watch=True)
        cap = S.build_captures(DS)[0]
        self.fake.responder = lambda body: self.answer(body)
        d.run_capture(cap)
        self.assertEqual(self.clock.slept.count(D.WATCH_PAUSE), 2)

    def test_watch_speed_file_divides_the_pace(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "watch-speed"
            f.write_text("8", encoding="utf-8")
            d = self.make([item("a"), item("b")], pace=0.0, watch=True)
            d.speed_file = f
            d.post_act(1)
            gaps = [s for s in self.clock.slept if s > 0]
            self.assertTrue(gaps and all(0.25 <= g <= 0.5 for g in gaps))
            for bad in ("3", "abc", ""):
                f.write_text(bad, encoding="utf-8")
                self.assertEqual(d.watch_speed(), 1.0)

    def test_no_pause_without_watch(self):
        d = self.make([])
        cap = S.build_captures(DS)[0]
        self.fake.responder = lambda body: self.answer(body)
        d.run_capture(cap)
        self.assertEqual(self.clock.slept, [])


if __name__ == "__main__":
    unittest.main()
