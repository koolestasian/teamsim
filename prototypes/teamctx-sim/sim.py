"""teamctx end-to-end simulation harness (local only).

    python -I prototypes/teamctx-sim/sim.py --help

See RUNBOOK.md for the order of commands and how to read the report.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from simlib import host as H, script as S  # noqa: E402
from simlib.net import PolicyError  # noqa: E402
from simlib.runner import Harness  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sim.py", description="Run teamctx end to end against a local Discord emulator.")
    p.add_argument("--teamctx", metavar="PATH", help=f"teamctx binary (default: {H.DEFAULT_BINARY})")
    p.add_argument("--plain", action="store_true",
                   help="the original scenario without the realism layer (handles, fragments, reactions, noise, "
                        "pasted key, absent member, -08:00 timezone; see REALISM.md). A state folder holds one mode.")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("seed", help="build seed.json and copy it into the WSL distro")

    emu = sub.add_parser("emu", help="control the emulator in WSL")
    emu.add_argument("action", choices=["start", "stop", "status"])

    sub.add_parser("history-experiment", help="try seeding history with explicit message ids (restarts the emulator)")
    sub.add_parser("config", help="write .state/teamctx.toml from `teamctx init` and choose the /ask model")

    host = sub.add_parser("host", help="control the teamctx host process")
    host.add_argument("action", choices=["start", "stop", "status"])

    sub.add_parser("shim", help="run the loopback shim in the foreground (port 4001 -> emulator)")
    sub.add_parser("token", help="create the API token (file only, never printed)")

    post = sub.add_parser("post", help="post one act through the emulator (resumable)")
    post.add_argument("--act", type=int, choices=[1, 2, 3, 4], required=True)
    post.add_argument("--pace", type=float, default=1.0, help="scale of the 0.3-1.2 s jitter (default 1)")
    post.add_argument("--fast", action="store_true", help="no sleeping between messages")
    post.add_argument("--dry-run", action="store_true", help="print the planned calls, no network")

    caps = sub.add_parser("captures", help="run the scripted captures of one act")
    caps.add_argument("--act", type=int, choices=[1, 2, 3, 4], required=True)
    qs = sub.add_parser("queries", help="run the per-act /search, /catchup, /teamctx status (and /ask in act 4)")
    qs.add_argument("--act", type=int, choices=[1, 2, 3, 4], required=True)

    chk = sub.add_parser("check", help="run the checks for one act")
    chk.add_argument("--act", type=int, choices=[1, 2, 3, 4], required=True)
    chk.add_argument("--emu-only", action="store_true", help="only compare against the emulator (no teamctx)")

    run = sub.add_parser("run-all", help="the whole scenario, end to end, then the report")
    run.add_argument("--dry-run", action="store_true", help="print every planned step, no network")
    run.add_argument("--pace", type=float, default=1.0)
    run.add_argument("--fast", action="store_true")
    run.add_argument("--stop-before-host", action="store_true",
                     help="seed, emulator, history experiment and posting only (needs no teamctx binary)")
    run.add_argument("--force", action="store_true", help="reset state and the emulator first")
    run.add_argument("--watch", action="store_true",
                     help="start the live view, open the browser and post at a watchable pace (2-4 s per message)")
    run.add_argument("--paced", action="store_true", help="the watchable pace only (the live view starts runs this way)")
    run.add_argument("--port", type=int, default=4100, help="live view port for --watch (default 4100)")

    viz = sub.add_parser("viz", help="the live view: watch the last run, or start a new one, in the browser")
    viz.add_argument("--port", type=int, default=4100)
    viz.add_argument("--no-open", action="store_true", help="do not open the browser")

    sub.add_parser("report", help="write a report from the saved checks")
    sub.add_parser("reset", help="stop host and emulator, delete .state (reports are kept)")
    return p


def serve_viz(port: int, *, open_browser: bool, controller=None, thread: bool = False):
    """Runs the live view server. Blocks until Ctrl-C, unless `thread` (then returns server and controller)."""
    import threading
    import webbrowser
    from simlib import viz as V
    from simlib.state import Paths

    paths = Paths()
    controller = controller or V.RunController(V.subprocess_launcher(paths.root))
    server = V.make_server(paths, port, controller=controller)
    print(f"live view: {server.url}  (Ctrl-C to stop)", flush=True)
    if open_browser:
        webbrowser.open(server.url)
    if thread:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server, controller
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        controller.stop()
        server.server_close()
    return 0


def run_watched(h: Harness, args):
    """`run-all --watch`: the live view in a background thread, the run in this process."""
    from simlib import viz as V

    controller = V.RunController(None)
    server, controller = serve_viz(args.port, open_browser=True, controller=controller, thread=True)
    controller.set_external(True)
    try:
        return h.run_all(stop_before_host=args.stop_before_host, force=args.force)
    finally:
        controller.set_external(False)
        print(f"the run is over; the live view stays up at {server.url} until you press Ctrl-C", flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            server.shutdown()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pace = 0.0 if getattr(args, "fast", False) else getattr(args, "pace", 1.0)
    try:
        cmd = args.command
        if cmd == "viz":
            return serve_viz(args.port, open_browser=not args.no_open)
        h = Harness(binary=args.teamctx, pace=pace, watch=bool(getattr(args, "watch", False) or getattr(args, "paced", False)),
                    realism=not args.plain)
        if cmd == "seed":
            print(h.cmd_seed())
        elif cmd == "emu":
            if args.action == "start":
                h.emu_start()
                print("emulator ready: inspector at http://localhost:4000/ (no token needed)")
            elif args.action == "stop":
                h.emu_stop()
            else:
                print("emulator:", "running" if h.emu.alive() else "not running")
        elif cmd == "history-experiment":
            r = h.history_experiment()
            print(r["decision"])
            for line in r["details"]:
                print(" -", line)
        elif cmd == "config":
            print(h.cmd_config())
        elif cmd == "host":
            if args.action == "start":
                h.host_start()
            elif args.action == "stop":
                h.host_stop()
            else:
                print("host:", "healthy" if h.api().healthz() else "not answering")
        elif cmd == "shim":
            from simlib.shim import Shim
            from simlib.runner import SHIM_PORT
            shim = Shim(SHIM_PORT, log_path=h.paths.state / "shim.log")
            print(f"shim on http://127.0.0.1:{SHIM_PORT} -> http://127.0.0.1:4000", flush=True)
            shim.serve_forever()
        elif cmd == "token":
            h.make_token()
            print("token stored in .state/api-token")
        elif cmd == "post":
            d = h.driver()
            if args.dry_run:
                for line in d.plan_calls(args.act):
                    print(line)
                return 0
            h.require_mode()
            print(d.post_act(args.act))
        elif cmd == "captures":
            h.require_mode()
            for r in h.driver().run_captures(args.act, synced=h.synced_probe):
                print(r.key, "ok" if r.ok and not r.error else r.error)
        elif cmd == "queries":
            h.require_mode()
            for r in h.driver().run_queries(args.act, llm=h.llm_on()):
                print(r.key, "ok" if r.ok and not r.error else r.error)
        elif cmd == "check":
            from simlib import checker as C
            ctx = h.context(with_host=not args.emu_only)
            h.save_check(C.check_harness(ctx, args.act))
            if not args.emu_only:
                h.save_check(C.check_sync(ctx, args.act))
        elif cmd == "run-all":
            if args.dry_run:
                for line in h.plan_lines(stop_before_host=args.stop_before_host):
                    print(line)
                return 0
            if args.watch:
                path = run_watched(h, args)
            else:
                path = h.run_all(stop_before_host=args.stop_before_host, force=args.force)
            print("report:", path)
        elif cmd == "report":
            print(h.write_report())
        elif cmd == "reset":
            h.cmd_reset()
        return 0
    except (H.HostError, PolicyError, RuntimeError) as exc:
        from simlib.envfile import redact
        print("error:", redact(str(exc)), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
