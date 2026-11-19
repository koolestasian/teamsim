"""naive_bot: an example subject that remembers every statement and answers by word overlap.

It keeps everything it is shown, in every surface, and answers a question with the stored
statement that shares the most words with it (the earliest one on a tie). It does not track
who may see what, who is entitled to say what, or which statement replaced which, so it is
expected to repeat restricted and superseded information. It reads only protocol messages.
"""
import json
import re
import sys

NAME = "naive_bot"
VERSION = "1"

# Words that carry no topic. Kept short on purpose: this bot is not meant to be clever.
STOP = frozenset(
    "a an and are as at be but by can did do does for from had has have how i if in is it its "
    "me my of on or so that the this to was we were what when where which who why will with "
    "you your".split())


def words(text):
    """The topic words of ``text``: lower case, letters and digits, without stop words."""
    return {w for w in re.findall(r"[a-z0-9]+", text.casefold()) if w not in STOP}


class Bot:
    def __init__(self):
        self.statements = []  # [event id, text], in order of arrival

    def handle(self, message):
        kind = message.get("type")
        if kind == "hello":
            return [{"type": "ready", "v": message["v"], "name": NAME, "version": VERSION}]
        if kind != "event":
            return []
        seq, payload = message["seq"], message.get("payload", {})
        out = []
        if message["kind"] == "post":
            text = payload["text"]
            if "?" in text:
                out = self.answer(seq, payload, text, "post")
            else:
                self.statements.append([payload["id"], text])
        elif message["kind"] == "edit":
            for entry in self.statements:
                if entry[0] == payload["target"]:
                    entry[1] = payload["text"]
        elif message["kind"] == "op":
            query = " ".join(str(v) for v in payload.get("args", {}).values())
            out = self.answer(seq, payload, query, "result")
        return out + [{"type": "done", "in_reply_to": seq}]

    def answer(self, seq, payload, query, kind):
        wanted = words(query)
        best, best_score = None, 0
        for _id, text in self.statements:
            score = len(wanted & words(text))
            if score > best_score:
                best, best_score = text, score
        if best is None:
            return []
        return [{"type": "action", "in_reply_to": seq, "kind": kind, "surface": payload["surface"],
                 "text": best, "reply_to": payload["id"]}]


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
