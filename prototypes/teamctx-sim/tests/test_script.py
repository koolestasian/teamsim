import datetime as dt
import json
import unittest

import fakes  # noqa: F401
from simlib import script as S


class SeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ds = S.load_dataset()
        cls.seed = S.build_seed(cls.ds)["discord"]
        cls.guild = cls.seed["guilds"][0]

    def test_six_people_two_applications(self):
        self.assertEqual(len(self.seed["users"]), 6)
        self.assertEqual([u["username"] for u in self.seed["users"]], ["wren", "dov", "imke", "tavish", "nadia", "pell"])
        self.assertEqual([u["global_name"] for u in self.seed["users"]][:2], ["Wren Calloway", "Dov Kestrel"])
        self.assertEqual({a["name"] for a in self.seed["applications"]}, {"teamctx-sim", "crashwatch"})
        self.assertEqual(self.guild["owner"], "wren")
        ids = [u["id"] for u in self.seed["users"]]
        self.assertEqual(len(set(ids)), 6)

    def test_teamctx_gets_exactly_view_channel_and_read_history(self):
        bots = {b["application"]: b for b in self.guild["bots"]}
        bits = {"VIEW_CHANNEL": 1 << 10, "READ_MESSAGE_HISTORY": 1 << 16}
        self.assertEqual(sum(bits[p] for p in bots["teamctx-sim"]["permissions"]), 66560)
        self.assertEqual(S.TEAMCTX_PERMS_BITS, 66560)
        self.assertEqual(set(bots["crashwatch"]["permissions"]),
                         {"VIEW_CHANNEL", "SEND_MESSAGES", "READ_MESSAGE_HISTORY", "ATTACH_FILES"})

    def test_only_message_content_is_a_privileged_intent_for_teamctx(self):
        app = next(a for a in self.seed["applications"] if a["name"] == "teamctx-sim")
        self.assertEqual(app["privileged_intents"], ["message_content"])
        self.assertNotIn("commands", app)  # teamctx registers its own commands on READY

    def test_channels_category_topics_and_leads_overwrites(self):
        channels = {c["name"]: c for c in self.guild["channels"]}
        self.assertEqual(set(channels), {"lantern-shelf", "general", "engineering", "design", "release-ops", "leads"})
        self.assertEqual(channels["lantern-shelf"]["type"], "category")
        for name in ("general", "engineering", "design", "release-ops"):
            self.assertEqual(channels[name]["parent"], "lantern-shelf")
            dataset_topic = next(c["topic"] for c in self.ds["channels"] if c["name"] == name)
            self.assertEqual(channels[name]["topic"], dataset_topic)
        overwrites = channels["leads"]["permission_overwrites"]
        self.assertIn({"role": "@everyone", "deny": ["VIEW_CHANNEL"]}, overwrites)
        self.assertTrue(any(o.get("role") == "leads" and "VIEW_CHANNEL" in o["allow"] for o in overwrites))
        self.assertTrue(any(o.get("user") == "teamctx-sim" for o in overwrites), "the product bot must see #leads")
        self.assertNotIn("permission_overwrites", channels["general"])
        self.assertEqual([r["name"] for r in self.guild["roles"]], ["leads"])
        leads_members = [m["user"] for m in self.guild["members"] if isinstance(m, dict)]
        self.assertEqual(sorted(leads_members), ["nadia", "wren"])

    def test_everyone_permissions_and_no_seed_messages(self):
        self.assertEqual(set(self.guild["everyone_permissions"]),
                         {"VIEW_CHANNEL", "SEND_MESSAGES", "READ_MESSAGE_HISTORY", "USE_APPLICATION_COMMANDS", "ATTACH_FILES"})
        self.assertEqual(self.guild["messages"], [])

    def test_seed_is_json_serialisable_and_stable(self):
        self.assertEqual(json.dumps(S.build_seed(self.ds), sort_keys=True), json.dumps(S.build_seed(self.ds), sort_keys=True))

    def test_with_history_does_not_mutate_the_seed(self):
        base = S.build_seed(self.ds)
        out = S.with_history(base, [{"channel": "general", "author": "wren", "content": "x", "id": "1"}])
        self.assertEqual(len(out["discord"]["guilds"][0]["messages"]), 1)
        self.assertEqual(base["discord"]["guilds"][0]["messages"], [])


class ActTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ds = S.load_dataset()
        cls.items = S.build_items(cls.ds)

    def test_act_split_counts(self):
        counts = S.act_counts(self.items)
        self.assertEqual({a: counts[a]["dataset"] for a in counts}, {1: 103, 2: 104, 3: 70, 4: 37})
        self.assertEqual(sum(c["dataset"] for c in counts.values()), 314)
        self.assertEqual({a: counts[a]["extras"] for a in counts}, {1: 0, 2: 3, 3: 0, 4: 1})
        self.assertEqual(counts[4]["bot"], 2)
        self.assertEqual(sum(c["edits"] for c in counts.values()), 2)

    def test_act_boundaries_use_the_original_utc_date(self):
        def ms(day):
            return int(dt.datetime(2026, *day, 12, tzinfo=dt.UTC).timestamp() * 1000)
        self.assertEqual([S.act_of(ms(d)) for d in [(3, 2), (3, 15), (3, 16), (3, 31), (4, 1), (4, 14), (4, 15), (4, 24)]],
                         [1, 1, 2, 2, 3, 3, 4, 4])

    def test_items_are_in_created_order_within_acts(self):
        acts = [i.act for i in self.items]
        self.assertEqual(acts, sorted(acts))
        dataset_items = [i for i in self.items if i.kind == "dataset"]
        stamps = [i.original_ms for i in dataset_items]
        self.assertEqual(stamps, sorted(stamps))

    def test_threads_are_folded_into_their_parent_channel_with_content_unchanged(self):
        names, threads, folded = S.channel_plan(self.ds)
        self.assertEqual(sorted(folded), ["211", "212", "213", "214", "215", "216"])
        self.assertEqual(names["211"], "engineering")
        self.assertEqual(names["214"], "general")
        by_id = {m["id"]: m for m in self.ds["messages"]}
        for item in self.items:
            if item.kind == "dataset":
                original = by_id[item.key]
                self.assertEqual(item.final_content, original["content"])
                self.assertEqual(item.folded_from is not None, original["channel_id"] in folded)
                self.assertIn(item.channel, {"general", "engineering", "design", "release-ops"})

    def test_replies_point_at_an_earlier_item_in_the_same_channel(self):
        seen = {}
        for item in self.items:
            if item.reply_to:
                self.assertIn(item.reply_to, seen, item.key)
                self.assertEqual(seen[item.reply_to].channel, item.channel)
            seen[item.key] = item

    def test_edited_messages_are_posted_as_drafts_first(self):
        edited = [i for i in self.items if i.edit_later]
        self.assertEqual(len(edited), 2)
        for item in edited:
            self.assertTrue(item.content.endswith(" (draft)"))
            self.assertEqual(item.content[: -len(" (draft)")], item.final_content)

    def test_extras(self):
        wrong = [i for i in self.items if i.kind == "wrong_channel"]
        self.assertEqual([(i.act, i.delete_later) for i in wrong], [(2, True), (4, True)])
        self.assertTrue(all(i.content == "wrong channel, ignore" for i in wrong))
        leads = [i for i in self.items if i.kind == "leads"]
        self.assertEqual([i.author for i in leads], ["105", "101"])
        self.assertTrue(all(i.channel == "leads" and i.act == 2 for i in leads))
        self.assertTrue(all(any(m.lower() in i.content.lower() for m in S.LEADS_MARKERS) for i in leads))
        self.assertTrue(all(m not in json.dumps(self.ds).lower() for m in ("7,400", "illustrator")))

    def test_attachment_messages_and_bot_posts(self):
        self.assertEqual(sum(bool(i.attachments) for i in self.items), 5)
        self.assertEqual([i.key for i in self.items if i.via_bot_token], ["1493868499641173910", "1494593303881058303"])


class CaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ds = S.load_dataset()
        cls.caps = S.build_captures(cls.ds)

    def test_about_twenty_captures_covering_every_command(self):
        self.assertGreaterEqual(len(self.caps), 20)
        commands = {(c.kind, c.command, c.sub) for c in self.caps}
        for needed in [("menu", "Mark as decision", None), ("menu", "Mark as question", None), ("menu", "Mark as task", None),
                       ("slash", "decide", None), ("slash", "todo", "add"), ("slash", "todo", "list"),
                       ("slash", "todo", "done"), ("slash", "question", None), ("slash", "answer", None),
                       ("slash", "decisions", None)]:
            self.assertIn(needed, commands)
        self.assertTrue(any(c.public for c in self.caps))
        self.assertTrue(any(c.options.get("include_superseded") for c in self.caps))
        self.assertTrue(any(c.command == "decide" and "replaces" in c.options for c in self.caps))

    def test_beta_date_chain_is_captured_in_order(self):
        by_entry = {c.entry: c for c in self.caps if c.effect == "create"}
        self.assertEqual(by_entry[50].options["replaces"], "$alias:1")
        self.assertEqual(by_entry[56].options["replaces"], "$alias:50")
        keys = [c.key for c in self.caps]
        self.assertLess(keys.index(by_entry[1].key), keys.index(by_entry[50].key))
        self.assertLess(keys.index(by_entry[50].key), keys.index(by_entry[56].key))

    def test_every_alias_is_created_before_it_is_used(self):
        created = set()
        for c in self.caps:
            for value in c.options.values():
                if isinstance(value, str) and value.startswith("$alias:"):
                    self.assertIn(int(value.split(":")[1]), created, c.key)
            if c.effect == "create":
                created.add(c.entry)

    def test_menu_captures_target_messages_posted_in_or_before_their_act(self):
        by_id = {m["id"]: m for m in self.ds["messages"]}
        for c in self.caps:
            if c.target:
                self.assertLessEqual(S.act_of(by_id[c.target]["created_at"]), c.act)

    def test_captures_run_as_the_entrys_creator_where_the_entry_has_one(self):
        entries = {e["id"]: e for e in self.ds["entries"]}
        for c in self.caps:
            if c.effect == "create":
                self.assertEqual(c.actor, entries[c.entry]["created_by"], c.key)

    def test_due_placeholders(self):
        self.assertEqual(S.due_from_offset("$due:+21", dt.date(2026, 11, 11)), "2026-12-02")
        with self.assertRaises(ValueError):
            S.due_from_offset("friday", dt.date(2026, 11, 11))

    def test_search_queries_have_hits_in_their_act(self):
        by_id = {m["id"]: m for m in self.ds["messages"]}
        for q in S.build_searches():
            hits = [m for m in self.ds["messages"] if S.act_of(m["created_at"]) <= q.act
                    and all(w in m["content"].lower() for w in q.words)]
            self.assertTrue(hits, q.text)
        _ = by_id


class MetricTests(unittest.TestCase):
    def test_recall_and_mrr_on_a_tiny_fixture(self):
        ranked = ["a", "b", "c", "d"]
        self.assertEqual(S.recall_at(ranked, {"b", "z"}, 10), 0.5)
        self.assertEqual(S.reciprocal_rank(ranked, {"c"}, 10), 1 / 3)
        self.assertEqual(S.reciprocal_rank(ranked, {"z"}, 10), 0.0)
        self.assertEqual(S.recall_at(ranked, {"d"}, 3), 0.0)  # cut at k
        self.assertEqual(S.reciprocal_rank(ranked, {"d"}, 3), 0.0)
        self.assertIsNone(S.recall_at(ranked, set()))
        self.assertIsNone(S.reciprocal_rank(ranked, set()))
        self.assertEqual(S.recall_at(["a", "a", "b"], {"a", "b"}, 10), 1.0)  # duplicates count once

    def test_case_ready_needs_every_expected_message(self):
        case = {"expected_messages": ["1", "2"]}
        self.assertFalse(S.case_ready(case, {"1"}))
        self.assertTrue(S.case_ready(case, {"1", "2", "3"}))


if __name__ == "__main__":
    unittest.main()
