"""Misbehaving or probing child subjects. Usage: modes.py MODE [ARG]."""
import json
import os
import subprocess
import sys
import time

mode = sys.argv[1]
arg = sys.argv[2] if len(sys.argv) > 2 else ""
inp, out, err = sys.stdin.buffer, sys.stdout.buffer, sys.stderr.buffer


def send(**fields):
    out.write(json.dumps(fields).encode() + b"\n")
    out.flush()


def hello(raw):
    if mode == "stall_hello":
        time.sleep(60)
    if mode == "env":
        info = {"env": dict(os.environ), "ls": os.listdir(".")}
        send(type="ready", v=1, name=json.dumps(info), version=os.getcwd())
    elif mode == "mirror":
        send(type="ready", v=1, name=raw.decode(), version="1")
    elif mode == "stderr":
        for part in arg.split("|"):
            err.write(part.encode())
            err.flush()
            time.sleep(0.15)
        send(type="ready", v=1, name="stderr", version="1")
    else:
        send(type="ready", v=1, name=mode, version="1")


def event(m, raw):
    seq, surface = m["seq"], m["payload"]["surface"]
    if mode == "mirror":
        send(type="action", in_reply_to=seq, kind="post", surface=surface, text=raw.decode())
    elif mode == "stall_event":
        time.sleep(60)
    elif mode == "malformed":
        out.write(b"this is not json\n")
        out.flush()
        return
    elif mode == "overlong":
        out.write(b"x" * (1024 * 1024 + 10))
        out.flush()
        return
    elif mode == "exit":
        os._exit(3)
    elif mode == "grandchild":
        subprocess.Popen([sys.executable, "-I", "-c", "import time; time.sleep(60)"])
        os._exit(0)
    send(type="done", in_reply_to=seq)


for raw in inp:
    m = json.loads(raw)
    if m["type"] == "hello":
        hello(raw.rstrip(b"\n"))
    elif m["type"] == "event":
        event(m, raw.rstrip(b"\n"))
    else:
        if mode == "no_exit":
            time.sleep(60)
        if mode == "after":
            send(type="log", level="info", text="late")
        break
