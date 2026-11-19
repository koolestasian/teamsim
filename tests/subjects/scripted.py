"""Scripted subject logic, used in process and, run as a program, over standard input and output.

The scenario names what the subject does wrong (or right) on its second event.
"""
import json
import sys


def say(**fields):
    return fields


class Logic:
    def __init__(self, scenario):
        self.scenario = scenario

    def handle(self, m):
        kind = m["type"]
        if kind == "hello":
            v = 2 if self.scenario == "version" else 1
            return [say(type="log", level="info", text="starting"),
                    say(type="ready", v=v, name="scripted", version="1")]
        if kind != "event":
            return []
        seq, surface = m["seq"], m["payload"].get("surface", "general")
        post = say(type="action", in_reply_to=seq, kind="post", surface=surface, text="re %d" % seq)
        done = say(type="done", in_reply_to=seq)
        if seq != 2 or self.scenario in ("normal", "version"):
            return [post, done]
        s = self.scenario
        if s == "wake":
            return [post, dict(done, wake_at_ms=m["t_ms"] + 5)]
        if s == "late":
            return [dict(post, in_reply_to=1), post, done]
        if s == "wrong":
            return [dict(post, in_reply_to=99), dict(done, in_reply_to=99), post, done]
        if s == "many":
            return [post] * 101 + [done]
        if s == "invalid":
            return [say(type="bogus")]
        if s == "float":
            return [say(type="action", in_reply_to=seq, kind="result", surface=surface,
                        text="x", data={"n": 1.5}), done]
        if s == "error":
            return [say(type="error", in_reply_to=seq, code="boom", text="it broke")]
        raise ValueError(s)


def main(scenario):
    logic, out = Logic(scenario), sys.stdout.buffer
    for raw in sys.stdin.buffer:
        m = json.loads(raw)
        for reply in logic.handle(m):
            out.write(json.dumps(reply, sort_keys=True).encode() + b"\n")
        out.flush()
        if m["type"] == "shutdown":
            break


if __name__ == "__main__":
    main(sys.argv[1])
