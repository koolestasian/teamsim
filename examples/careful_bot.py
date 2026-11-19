"""careful_bot: an example subject that tracks who saw what, who stated what, and what replaced what.

It reads only protocol messages (who said what, where, when, membership and presence). Its
rules are plain heuristics, and they can be wrong; where a check shows that, the check has
found something about this bot, not about the scenario.

Visibility. A statement is remembered with the members of its surface at the moment it was
delivered. The bot repeats it only on the surface where it was said, or on a surface whose
members all saw it. Otherwise it declines. A surface the bot joined later has no member list in
the protocol, so its members are the actors seen acting there.

Authority. The first person to state something on a topic is its authority. A later statement
on the same topic by someone else is ignored, and so is any statement that hedges ("I think",
"maybe", "not sure") or asks a question. Two statements are on the same topic when they share
three content words, or one when the later one says it changes something ("update", "moved",
"slips", "is now").

Supersession. A later statement on a topic by its authority replaces the earlier one. A person
who has replaced their own statement is treated as someone who makes decisions.

Catch-up. Asked what someone missed, the bot lists the current statements of decision makers
made while that person was away, keeping only those with a number or a name in them.

Secrets. A statement that mentions a password, token or secret, or asks not to be repeated, is
never stored, and any word of an outgoing text that looks like one is replaced.
"""
import json
import re
import sys

NAME = "careful_bot"
VERSION = "1"

STOP = frozenset(
    "a an and are as at be but by can did do does for from had has have how i if in is it its "
    "me my of on or so that the this to was we were what when where which who why will with "
    "you your".split())
CUE_WORDS = frozenset(
    "update moves moved moving slips slipped changed instead correction last move now longer".split())
CUE = re.compile(r"\b(update|moves|moved|moving|slips|slipped|changed|change of plan|last move|"
                 r"instead|no longer|correction|is now)\b", re.I)
HEDGE = re.compile(r"\b(i think|i thought|maybe|perhaps|probably|might|not sure|i guess)\b", re.I)
SENSITIVE = re.compile(r"(do not|don't|dont) (repeat|share)|secret|passw|passcode|token|credential|"
                       r"api[ -]?key", re.I)
SECRET_WORD = re.compile(r"secret|passw|token|credential|api[-_]?key|^(sk|pk|ghp|xox[a-z])[-_]\w{10,}",
                         re.I)
REFUSAL = "I can't share that here."
FIRST_PERSON = ("I", "I'm", "I'll", "I've", "I'd")


def words(text):
    """The topic words of ``text``: lower case, letters and digits, without stop and cue words."""
    return {w for w in re.findall(r"[a-z0-9]+", text.casefold())
            if w not in STOP and w not in CUE_WORDS}


def scrub(text):
    """``text`` with every word that looks like a secret replaced."""
    return " ".join("[hidden]" if SECRET_WORD.search(w) else w for w in text.split(" "))


def concrete(text):
    """True when ``text`` holds a number or a name (a capital letter that does not start it)."""
    if re.search(r"\d", text):
        return True
    names = re.findall(r"[A-Za-z][\w'-]*", text)[1:]
    return any(n[0].isupper() and n not in FIRST_PERSON for n in names)


class Bot:
    def __init__(self):
        self.me = None
        self.members = {}     # surface id -> set of actor ids, the bot included
        self.away = {}        # actor id -> list of [start_ms, end_ms or None]
        self.statements = {}  # event id -> dict
        self.topics = []      # dicts: author, ids (event ids, oldest first)
        self.deciders = set()

    # -- protocol ---------------------------------------------------------------------------

    def handle(self, message):
        kind = message.get("type")
        if kind == "hello":
            self.me = message["subject_id"]
            for surface in message["surfaces"]:
                self.members[surface["id"]] = set(surface["members"])
            return [{"type": "ready", "v": message["v"], "name": NAME, "version": VERSION}]
        if kind != "event":
            return []
        seq, t, payload = message["seq"], message["t_ms"], message.get("payload", {})
        out = self.respond(message["kind"], t, payload)
        return [dict(a, in_reply_to=seq) for a in out] + [{"type": "done", "in_reply_to": seq}]

    # -- state ------------------------------------------------------------------------------

    def observe(self, kind, t, payload):
        """Update what the bot knows from one event."""
        surface, actor = payload.get("surface"), payload.get("actor")
        if kind == "subject_join":
            self.members.setdefault(surface, {self.me})
        elif kind in ("join", "leave", "post", "edit", "delete", "react", "away", "back"):
            people = self.members.setdefault(surface, {self.me})
            if kind == "leave":
                people.discard(actor)
            else:
                people.add(actor)
        if kind == "away":
            self.away.setdefault(actor, []).append([t, None])
        elif kind == "back":
            for span in self.away.get(actor, []):
                if span[1] is None:
                    span[1] = t
        elif kind == "edit" and payload["target"] in self.statements:
            self.statements[payload["target"]]["text"] = payload["text"]
        elif kind == "delete":
            self.statements.pop(payload["target"], None)
        elif kind == "post" and "?" not in payload["text"]:
            self.remember(t, payload)

    def remember(self, t, payload):
        text, author = payload["text"], payload["actor"]
        if SENSITIVE.search(text) or HEDGE.search(text):
            return
        topic = self.same_topic(text)
        if topic is not None and topic["author"] != author:
            return  # someone without authority on this topic
        if topic is not None:
            self.deciders.add(author)
        self.statements[payload["id"]] = {
            "text": text, "t": t, "surface": payload["surface"], "author": author,
            "viewers": frozenset(self.members[payload["surface"]])}
        if topic is None:
            topic = {"author": author, "ids": []}
            self.topics.append(topic)
        topic["ids"].append(payload["id"])

    def same_topic(self, text):
        mine, best, best_score = words(text), None, 0
        for topic in self.topics:
            current = self.current(topic)
            if current is None:
                continue
            score = len(mine & words(current["text"]))
            if score > best_score:
                best, best_score = topic, score
        enough = best_score >= 3 or (best_score >= 1 and CUE.search(text))
        return best if enough else None

    def current(self, topic):
        for event_id in reversed(topic["ids"]):
            if event_id in self.statements:
                return self.statements[event_id]
        return None

    # -- answering --------------------------------------------------------------------------

    def respond(self, kind, t, payload):
        self.observe(kind, t, payload)
        if kind == "post" and "?" in payload["text"]:
            query, action = payload["text"], "post"
        elif kind == "op":
            query, action = " ".join(str(v) for v in payload.get("args", {}).values()), "result"
        else:
            return []
        readers = self.members[payload["surface"]] - {self.me}
        if action == "post" and self.is_catch_up(query):
            text = self.catch_up(payload["actor"], payload["surface"], readers)
        else:
            text = self.lookup(query, payload["surface"], readers)
        if text is None:
            return []
        return [{"type": "action", "kind": action, "surface": payload["surface"],
                 "text": scrub(text), "reply_to": payload["id"]}]

    @staticmethod
    def visible(statement, surface, readers):
        return statement["surface"] == surface or readers <= statement["viewers"]

    def lookup(self, query, surface, readers):
        wanted, best, best_key = words(query), None, (0, 0)
        for topic in self.topics:
            current = self.current(topic)
            if current is None:
                continue
            key = (len(wanted & words(current["text"])), current["t"])
            if key[0] > 0 and key > best_key:
                best, best_key = current, key
        if best is None:
            return None
        return best["text"] if self.visible(best, surface, readers) else REFUSAL

    @staticmethod
    def is_catch_up(text):
        q = text.casefold()
        return "catch up" in q or "catch me up" in q or (
            "miss" in q and re.search(r"away|out|gone|back|while", q) is not None)

    def catch_up(self, asker, surface, readers):
        spans = self.away.get(asker)
        if not spans:
            return "I did not see you go away."
        start, items = spans[-1][0], []
        for topic in self.topics:
            s = self.current(topic)
            if (s is not None and s["t"] > start and s["author"] in self.deciders
                    and concrete(s["text"]) and self.visible(s, surface, readers)
                    and s["text"] not in [i["text"] for i in items]):
                items.append(s)
        if not items:
            return "Nothing I saw changed while you were away."
        return " ".join(s["text"] for s in sorted(items, key=lambda s: s["t"]))


def main():
    bot, out = Bot(), sys.stdout.buffer
    for raw in sys.stdin.buffer:
        message = json.loads(raw.decode("utf-8"))
        for reply in bot.handle(message):
            out.write(json.dumps(reply, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n")
        out.flush()
        if message.get("type") == "shutdown":
            break


if __name__ == "__main__":
    main()
