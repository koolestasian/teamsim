"""Convert the Lantern Shelf fixture into a pack (pack format 1).

    python fixtures/demo/make_pack.py [-o packs/lantern-shelf]

Reads ``dataset.json`` and ``eval.toml`` beside this file and writes the pack with
``teamsim.pack.write``. The output is deterministic: two runs give identical bytes.
Standard library only. All dataset text is fictional and untrusted; it is copied
into the pack as data and no text is invented here except the pack's own header.

Mapping
-------
* Actors: the six people and the bot ``crashwatch``. The dataset has no roles or
  traits for the people, so none are written.
* Surfaces: each of the four channels, each followed by its threads; every surface
  has all seven actors and the subject as members.
* Timeline: one ``post`` per message, in dataset order, at ``created_at`` minus the
  first message's ``created_at``. ``reply_to`` and ``edited_at`` are dropped: the
  pack format has no field for either. An empty message would use its attachment
  names as ``[attachment: <name>]``.
* Facts: one fact per record entry that an eval case asks about. Entries linked by
  ``replaces`` form one chain with one key (derived from the newest entry's id) and
  are joined with ``supersedes``, oldest to newest. The value is the case's
  ``answer_contains``; it must appear in one of the case's expected messages, and
  those messages are the events that disclose the fact. A case about a superseded
  entry gives the old value only and has no check. A case whose fragment appears in
  none of its expected messages is read from the nearest earlier message of the same
  channel that has it verbatim and is written by one of the expected authors (case
  rev-11, "I'd say API 26", confirmed there by "26 it is"); otherwise it is skipped
  and listed with its reason, unless ``VERBATIM_SPANS`` names a span of an expected message
  that states the same answer: the span is then the value and the fragment a form. When a case gives a different value for an entry that
  already has one, it asks about another aspect of that entry (owner or due date, say):
  it gets its own key, ``<entry key>.<category>`` (``.<case id>`` if that is taken), and
  its own fact, without a ``supersedes`` link.
* Checks: one ``harness`` check and one ``answer`` check per kept case. The probe
  is a new ``post`` after the last transcript message, 5 minutes apart in case
  order, asking the case's question on the surface of its first expected message,
  by a person other than the disclosing authors (round robin over the six people).
"""

import argparse
import json
import sys
import tomllib
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from teamsim import pack as packlib  # noqa: E402
from teamsim.model import (  # noqa: E402
    Actor,
    At,
    Check,
    Event,
    Fact,
    Pack,
    PackHeader,
    Provenance,
    Subject,
    Surface,
)

# Cases whose eval fragment is in none of the expected messages, which state the answer in
# other words. Each maps a case id to the span of an expected message that states the same
# answer. The span is the fact value and the fragment becomes a form of it. Every span
# occurs in exactly one message of the dataset (checked by hand when this table was
# written). No fuzzy matching: a case not listed here is skipped.
VERBATIM_SPANS = {
    # "ship it, but opt-in, in the page turn settings. the default stays slide"
    "para-10": "opt-in, in the page turn settings",
    # "why not pull the cover out of the EPUB itself and make a thumbnail on import?"
    "para-21": "out of the EPUB",
    # "downloads only on Wi-Fi by default."
    "rev-09": "only on Wi-Fi",
    # "no curl. slide and fade only."
    "rev-10": "no curl",
}

PROBE_GAP_MS = 5 * 60 * 1000
KIND_OF_ENTRY = {"decision": "decision", "task": "assignment", "question": "item"}
PREFIX = {"decision": "d", "task": "t", "question": "q"}


def _nfc(text):
    if unicodedata.normalize("NFC", text) != text:
        raise SystemExit("text is not in Unicode Normalisation Form C")
    return text


def build(dataset, cases):
    members = dataset["members"]
    actor_id = {
        m["id"]: ("crashwatch" if m["is_bot"] else m["display_name"].split()[0].lower()) for m in members
    }
    people = [actor_id[m["id"]] for m in members if not m["is_bot"]]
    actors = tuple(
        Actor(id=actor_id[m["id"]], display=m["display_name"], role="bot" if m["is_bot"] else None)
        for m in members
    )

    channels = dataset["channels"]
    ordered = []
    for parent in (c for c in channels if c["parent_id"] is None):
        ordered.append(parent)
        ordered.extend(c for c in channels if c["parent_id"] == parent["id"])
    surface_name = {c["id"]: c["name"] for c in channels}
    everyone = tuple(actor_id[m["id"]] for m in members) + ("subject",)
    surfaces = tuple(Surface(id=c["name"], kind="channel", members=everyone) for c in ordered)

    messages = dataset["messages"]
    origin = messages[0]["created_at"]
    events = []
    event_of = {}
    for m in messages:
        text = m["content"]
        if not text:
            text = " ".join("[attachment: %s]" % n for n in m["attachment_names"])
        event_id = "m.%s" % m["id"]
        event_of[m["id"]] = event_id
        events.append(
            {
                "id": event_id,
                "ms": m["created_at"] - origin,
                "actor": actor_id[m["author_id"]],
                "surface": surface_name[m["channel_id"]],
                "text": _nfc(text),
            }
        )
    last_ms = events[-1]["ms"]
    by_message = {m["id"]: m for m in messages}
    event_by_id = {e["id"]: e for e in events}

    # Entry chains: each entry's older entry and the newest entry of its chain.
    entries = {e["id"]: e for e in dataset["entries"]}
    older = {e["id"]: e["replaces"] for e in dataset["entries"] if e["replaces"]}

    def newest(entry_id):
        while entries[entry_id]["superseded_by"]:
            entry_id = entries[entry_id]["superseded_by"]
        return entry_id

    summary = {"skipped": [], "kept": [], "old_only": [], "aspects": [], "fallback": [], "spans": []}
    facts = {}  # (entry id, aspect or None) -> value, kind, first case, disclosing message ids
    case_entry = {}
    order = {m["id"]: i for i, m in enumerate(messages)}
    for case in cases:
        entry_id = int(case["expected_entries"][0].split("-")[1])
        fragment = case["answer_contains"]
        disclosing = [
            mid for mid in case["expected_messages"] if fragment.lower() in by_message[mid]["content"].lower()
        ]
        spelling = None
        if not disclosing and case["id"] in VERBATIM_SPANS:
            spelling = fragment
            fragment = VERBATIM_SPANS[case["id"]]
            disclosing = [
                mid for mid in case["expected_messages"] if fragment.lower() in by_message[mid]["content"].lower()
            ]
            summary["spans"].append((case["id"], fragment))
        if not disclosing:
            # The expected messages may only confirm a value that an earlier message of the
            # same channel proposed in the words of the fragment.
            first = by_message[case["expected_messages"][0]]
            authors = {by_message[mid]["author_id"] for mid in case["expected_messages"]}
            earlier = [
                m
                for m in messages[: order[first["id"]]]
                if m["channel_id"] == first["channel_id"]
                and m["author_id"] in authors
                and fragment.lower() in m["content"].lower()
            ]
            if earlier:
                disclosing = [earlier[-1]["id"]]
                summary["fallback"].append((case["id"], disclosing[0]))
        if not disclosing:
            summary["skipped"].append(
                (case["id"], "no message states %r: the expected messages put it in other words" % fragment)
            )
            continue
        entry = entries[entry_id]
        kind = "date" if case["category"] == "date" else KIND_OF_ENTRY[entry["kind"]]
        slot = (entry_id, None)
        have = facts.get(slot)
        if have is not None and have["value"].lower() != fragment.lower():
            aspect = case["category"]
            if (entry_id, aspect) in facts:
                aspect = case["id"]
            slot = (entry_id, aspect)
            summary["aspects"].append((case["id"], "%s-%d.%s" % (PREFIX[entry["kind"]], entry_id, aspect)))
        if slot not in facts:
            facts[slot] = {"value": fragment, "kind": kind, "case": case["id"], "messages": [], "forms": []}
        if spelling is not None and spelling not in facts[slot]["forms"]:
            facts[slot]["forms"].append(spelling)
        for mid in disclosing:
            if mid not in facts[slot]["messages"]:
                facts[slot]["messages"].append(mid)
        case_entry[case["id"]] = slot
        if case["expected_status"] == "superseded":
            summary["old_only"].append(case["id"])

    def key_of(entry_id):
        top = newest(entry_id)
        return "%s-%d" % (PREFIX[entries[top]["kind"]], top)

    def fact_id(slot):
        entry_id, aspect = slot
        suffix = "" if aspect is None else ".%s" % aspect
        return "f.%s-%d%s" % (PREFIX[entries[entry_id]["kind"]], entry_id, suffix)

    def fact_key(slot):
        entry_id, aspect = slot
        return key_of(entry_id) + ("" if aspect is None else ".%s" % aspect)

    fact_list = []
    for slot in sorted(facts, key=lambda t: (fact_key(t), t[0])):
        f = facts[slot]
        entry_id, aspect = slot
        # The nearest older entry in the chain that has a fact (not for another aspect).
        prev = older.get(entry_id) if aspect is None else None
        while prev is not None and (prev, None) not in facts:
            prev = older.get(prev)
        authors = []
        for mid in f["messages"]:
            a = actor_id[by_message[mid]["author_id"]]
            if a not in authors:
                authors.append(a)
        fact_list.append(
            Fact(
                id=fact_id(slot),
                key=fact_key(slot),
                kind=f["kind"],
                value=_nfc(f["value"]),
                forms=tuple(f["forms"]) or None,
                authority=tuple(authors),
                audience=("*",),
                supersedes=fact_id((prev, None)) if prev is not None else None,
            )
        )
        for mid in f["messages"]:
            event_by_id[event_of[mid]].setdefault("discloses", []).append(fact_id(slot))

    # Probes and checks.
    checks = [Check(id="c.harness", kind="harness")]
    probes = []
    cursor = 0
    for case in cases:
        slot = case_entry.get(case["id"])
        if slot is None or case["expected_status"] == "superseded":
            continue
        chain = [slot[0]]
        while slot[1] is None and chain[-1] in older:
            chain.append(older[chain[-1]])
        depends = []
        authors = set()
        for c in chain:
            if (c, slot[1]) not in facts:
                continue
            for mid in facts[(c, slot[1])]["messages"]:
                depends.append(event_of[mid])
                authors.add(actor_id[by_message[mid]["author_id"]])
        asker = people[cursor % len(people)]
        step = 0
        while asker in authors and step < len(people):
            step += 1
            asker = people[(cursor + step) % len(people)]
        first = by_message[case["expected_messages"][0]]
        probe_id = "q.%s" % case["id"]
        probes.append(
            {
                "id": probe_id,
                "ms": last_ms + PROBE_GAP_MS * (cursor + 1),
                "actor": asker,
                "surface": surface_name[first["channel_id"]],
                "text": _nfc(case["question"]),
                "depends_on": tuple(dict.fromkeys(depends)),
            }
        )
        checks.append(Check(id=case["id"], kind="answer", key=fact_key(slot), probe=probe_id))
        summary["kept"].append(case["id"])
        cursor += 1

    event_objs = []
    for e in events:
        event_objs.append(
            Event(
                id=e["id"],
                when=At(e["ms"]),
                actor=e["actor"],
                surface=e["surface"],
                kind="post",
                text=e["text"],
                discloses=tuple(e["discloses"]) if "discloses" in e else None,
            )
        )
    for p in probes:
        event_objs.append(
            Event(
                id=p["id"],
                when=At(p["ms"]),
                actor=p["actor"],
                surface=p["surface"],
                kind="post",
                text=p["text"],
                depends_on=p["depends_on"],
                probe=True,
            )
        )

    header = PackHeader(
        format=1,
        id="lantern-shelf",
        title="Lantern Shelf: six people and a crash bot build an e-reader app",
        purpose="Test an assistant that joins a team chat: it must recall the current value of decisions, task owners and dates after plans changed over eight weeks.",
        seed="lantern-shelf-1",
        limits=(
            "The chat is a fixed hand-written transcript, so it is the same in every run.",
            "Every channel is public, so there are no privacy, secret or catch-up checks.",
            "Answers are matched against the evidence fragments of the eval set, not judged for meaning.",
            "Replies and message edits in the original chat are not kept: the pack format has no field for them.",
        ),
    )
    provenance = Provenance(
        generator_version="fixtures/demo/make_pack.py",
        transformation="converted from fixtures/demo/dataset.json and fixtures/demo/eval.toml",
    )
    the_pack = Pack(
        header=header,
        subject=Subject(id="subject"),
        actors=actors,
        surfaces=surfaces,
        facts=tuple(fact_list),
        checks=tuple(checks),
        events=tuple(event_objs),
        provenance=provenance,
    )
    return the_pack, summary


def load_sources():
    dataset = json.loads((HERE / "dataset.json").read_text(encoding="utf-8"))
    cases = tomllib.loads((HERE / "eval.toml").read_text(encoding="utf-8"))["cases"]
    return dataset, cases


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-o", "--out", default=str(ROOT / "packs" / "lantern-shelf"))
    args = parser.parse_args(argv)
    dataset, cases = load_sources()
    the_pack, summary = build(dataset, cases)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    packlib.write(the_pack, out)
    print("wrote %s (pack_hash %s)" % (out, packlib.pack_hash(the_pack)))
    print(
        "actors %d, surfaces %d, events %d, facts %d, checks %d"
        % (len(the_pack.actors), len(the_pack.surfaces), len(the_pack.events), len(the_pack.facts), len(the_pack.checks))
    )
    print("kept cases (%d): %s" % (len(summary["kept"]), " ".join(summary["kept"])))
    print("cases about an old value, no check (%d): %s" % (len(summary["old_only"]), " ".join(summary["old_only"])))
    print("cases with their own key, another aspect of an entry (%d):" % len(summary["aspects"]))
    for case_id, key in summary["aspects"]:
        print("  %s: %s" % (case_id, key))
    print("cases disclosed by an earlier message of the channel (%d):" % len(summary["fallback"]))
    for case_id, mid in summary["fallback"]:
        print("  %s: m.%s" % (case_id, mid))
    print("cases stated by a verbatim span of an expected message (%d):" % len(summary["spans"]))
    for case_id, span in summary["spans"]:
        print("  %s: %r" % (case_id, span))
    print("skipped cases (%d):" % len(summary["skipped"]))
    for case_id, why in summary["skipped"]:
        print("  %s: %s" % (case_id, why))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
