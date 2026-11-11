"""Orchestration: the commands behind `sim.py` and the whole scenario (`run-all`)."""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import checker as C, envfile, host as H, report as R, script as S
from .driver import Driver, IdMap
from .emu import DEFAULT_BASE, EmuClient, EmuError, Wsl, parse_startup_log, wait_ready
from .net import PolicyError, UrllibTransport, assert_loopback_url
from .state import JsonStore, Paths, Recorder, atomic_write_text, now_iso

ENV_FILE = S.REPO / ".env"
API_URL = "http://127.0.0.1:7420"
SHIM_PORT = 4001
SHIM_URL = f"http://127.0.0.1:{SHIM_PORT}"
FACTS_ASSUMPTIONS = [
    "Subcommand interactions: the emulator accepts `command`, `subcommand` and a flat `options` map (the documented nested map is refused); "
    "raw option arrays are the fallback. Confirmed against the emulator with a stand-in bot, not against teamctx.",
    "Modal submission values for the owner user-select are sent as a list of user ids. Confirmed live: the emulator accepts teamctx's Label-based modal, "
    "echoes the values in the Label layout, but sends no `data.resolved` users, which teamctx needs to name the owner; so a form with an owner is "
    "answered with teamctx's fixed 'could not read that command' text and the harness resubmits without an owner (marked degraded, owner n.a.). "
    "Real Discord includes `resolved` for user selects; whether it does so inside modal submissions is not confirmed from docs.",
    "The emulator lacks the thread-list routes (404). teamctx stops syncing the guild on a 404 there, so a loopback shim between teamctx and the "
    "emulator answers those routes with the empty lists Discord returns for a guild without threads. Everything else is forwarded unchanged; the gateway is tunnelled.",
    "`localhost` resolves to ::1 first on this machine and costs about 2 s per new connection through the WSL forwarder, so everything uses 127.0.0.1 "
    "(the spec says http://localhost:4000; both reach the same emulator).",
    "teamctx's live message events do not advance `sync_cursors.newest_seen`; only REST sync runs (start, reconnect, invalidate) do. The cursor check is therefore "
    "required only where a sync run must have happened (after the restart and after a disconnect).",
    "Reply timing is measured from the interaction snowflake to the reply message snowflake (emulator clock), not from the wall time "
    "of the simulate call, which includes the emulator's own wait for the answer.",
    "The emulator ignores attachments on simulated messages (JSON and multipart), so attachment names stay unverified (n.a.).",
    "teamctx's graceful shutdown handles only Ctrl-C in its own console; the harness hard-stops the process on Windows.",
    "The `q` client and API shapes were read from source (crates/teamctx-server, crates/teamctx/src/q.rs); `status.sync.gateway` and "
    "the `record` line format are assumed to match the source at the time of reading.",
]


class Harness:
    """Wires paths, transports, clients and state. Everything is injectable for tests."""

    def __init__(self, paths: Paths | None = None, *, binary: str | None = None, echo: bool = True,
                 emu_transport=None, local_transport=None, or_transport=None, wsl: Wsl | None = None,
                 pace: float = 1.0, base: str = DEFAULT_BASE, sleep=time.sleep, watch: bool = False,
                 realism: bool = False) -> None:
        self.paths = paths or Paths()
        self.paths.ensure()
        self.base = assert_loopback_url(base)
        self.rec = Recorder(self.paths, echo=echo)
        self.sleep = sleep
        self.state = JsonStore(self.paths.state_json)
        # One state folder holds one mode: mixing plain and realism posts would corrupt the ground truth.
        mode = "realism" if realism else "plain"
        built = self.state.get("mode") or ("plain" if self.state.get("stages") else mode)  # older states were plain
        self.mode_conflict = (f"the state in {self.paths.state} was built in {built} mode; run `reset` (or "
                              f"`run-all --force`) before a {mode} run") if built != mode and self.state.get("stages") else None
        if self.mode_conflict is None:
            self.state["mode"] = mode
        S.configure(realism=realism)
        self.realism = realism
        self.dataset = S.load_dataset()
        self.items = S.build_items(self.dataset)
        self.ids = IdMap.from_dataset(self.dataset)
        self.eval_file = S.load_eval()
        self.mapping = JsonStore(self.paths.map_json, {"items": {}})
        self.emu_transport = emu_transport or UrllibTransport()
        self.local_transport = local_transport or UrllibTransport()
        self.or_transport = or_transport or UrllibTransport(allow_loopback=False, extra_hosts=frozenset({"openrouter.ai"}))
        self.emu = EmuClient(self.emu_transport, self.base, sleep=sleep)
        self.wsl = wsl or Wsl(self.paths.state)
        self.pace = pace
        self.watch = watch
        self.binary_arg = binary
        self.teamctx_token = envfile.Secret(S.TEAMCTX_TOKEN, "teamctx bot token (emulator fake)")
        self.crash_token = envfile.Secret(S.CRASHWATCH_TOKEN, "crashwatch bot token (emulator fake)")
        envfile.REDACTOR.add(self.teamctx_token)
        envfile.REDACTOR.add(self.crash_token)
        self.llm_key = envfile.load_secret(ENV_FILE, "TEAMCTX_LLM_KEY")
        self.host_proc: H.HostProcess | None = None

    # -- helpers

    def binary(self) -> Path:
        """The binary under test. It is copied into .state/bin first, so a rebuild in the other
        worktree never hits a locked executable and the run uses one fixed build."""
        source = H.resolve_binary(self.binary_arg)
        dest_dir = self.paths.state / "bin"
        dest = dest_dir / source.name
        if self.paths.state in source.parents:
            return source
        dest_dir.mkdir(parents=True, exist_ok=True)
        st = source.stat()
        if not dest.exists() or dest.stat().st_size != st.st_size or int(dest.stat().st_mtime) < int(st.st_mtime):
            import shutil
            shutil.copy2(source, dest)
            import hashlib
            self.state["binary"] = {"source": str(source), "sha256": hashlib.sha256(dest.read_bytes()).hexdigest()[:16],
                                    "size": st.st_size}
            self.state.save()
        return dest

    def require_mode(self) -> None:
        """Commands that post or run against the state call this; dry runs and reports do not."""
        if self.mode_conflict:
            raise RuntimeError(self.mode_conflict)

    def driver(self) -> Driver:
        return Driver(self.emu, self.mapping, self.state, self.items, self.ids, self.dataset, self.rec,
                      crash_token=self.crash_token, teamctx_token=self.teamctx_token, sleep=self.sleep, pace=self.pace, watch=self.watch,
                      speed_file=self.paths.root / "watch-speed")

    def api(self) -> H.Api:
        return H.Api(self.local_transport, API_URL, self.paths.api_token)

    def store(self) -> H.StoreReader:
        return H.StoreReader(self.paths.db)

    def model(self) -> dict:
        return self.state.get("model") or {"kind": "none", "reason": "model not chosen yet"}

    def llm_on(self) -> bool:
        return self.model().get("kind") in ("openrouter", "lmstudio")

    def cli(self, args: list[str], extra_env: dict | None = None) -> tuple[int, str, str]:
        env = H.child_env(dict(os.environ), {"TEAMCTX_DISCORD_TOKEN": self.teamctx_token, **(extra_env or {})})
        proc = H.run_cli(self.binary(), args, env=env)
        out, err = H.text_of(proc)
        return proc.returncode, out, err

    # -- seed and emulator

    def cmd_seed(self) -> dict:
        seed = S.build_seed(self.dataset)
        atomic_write_text(self.paths.seed_json, json.dumps(seed, indent=2))
        self.wsl.copy_seed(seed)
        d = seed["discord"]
        facts = {"users": len(d["users"]), "applications": len(d["applications"]),
                 "channels": len(d["guilds"][0]["channels"]), "seed_messages": len(d["guilds"][0]["messages"])}
        self.rec.event("seed", f"seed built and copied into WSL: {facts}")
        return facts

    def emu_start(self, *, seed: dict | None = None) -> None:
        """(Re)starts the emulator with a seed (default: the real one) and waits for READY."""
        seed = seed or S.build_seed(self.dataset)
        self.wsl.stop()
        deadline = time.monotonic() + 15
        while self.emu.alive() and time.monotonic() < deadline:
            self.sleep(0.5)
        self.wsl.copy_seed(seed)
        self.wsl.start()
        info = wait_ready(self.emu, self.wsl.read_log, timeout=90, sleep=self.sleep, token=S.TEAMCTX_TOKEN)
        if not info.ready:
            raise RuntimeError("emulator did not become ready: " + envfile.redact(self.wsl.read_log())[-600:])
        self.rec.event("emulator", "emulator started with seed", ready=True)

    def emu_stop(self) -> None:
        self.wsl.stop()
        self.rec.event("emulator", "emulator stopped")

    def verify_seed(self) -> list[str]:
        """The emulator holds the cast: ids, channels, overwrites, commands not yet registered."""
        problems = []
        tok = self.teamctx_token
        me = self.emu.rest_get(tok, "/users/@me")
        if me.get("id") != S.BOT_TEAMCTX_ID:
            problems.append(f"bot user id is {me.get('id')}")
        channels = {c["name"]: c for c in self.emu.rest_get(tok, f"/guilds/{S.GUILD_ID}/channels")}
        for name, cid in self.ids.channels.items():
            if channels.get(name, {}).get("id") != cid:
                problems.append(f"channel #{name} not seeded with id {cid}")
        leads = channels.get(S.LEADS_CHANNEL, {})
        denies = [o for o in leads.get("permission_overwrites", []) if int(o.get("deny", 0)) & 1024]
        if not denies:
            problems.append("#leads has no @everyone VIEW_CHANNEL deny")
        roles = self.emu.rest_get(tok, f"/guilds/{S.GUILD_ID}/roles")
        managed = [r for r in roles if r.get("managed") and r["name"] == "teamctx-sim"]
        if not managed or int(managed[0]["permissions"]) != S.TEAMCTX_PERMS_BITS:
            problems.append(f"teamctx-sim role permissions are {managed[0]['permissions'] if managed else 'missing'}, expected {S.TEAMCTX_PERMS_BITS}")
        return problems

    def history_experiment(self) -> dict:
        """Seed messages with explicit dataset ids; does the emulator keep them?"""
        sample = [i for i in self.items if i.act == 1 and not i.via_bot_token][:6]
        cast = S.cast_from_dataset(self.dataset)
        msgs = [{"channel": i.channel, "author": cast[i.author].username, "content": i.content, "id": i.key} for i in sample]
        details: list[str] = []
        kept: bool | None = None
        stamps: list[str] = []
        try:
            self.emu_start(seed=S.with_history(S.build_seed(self.dataset), msgs))
        except RuntimeError as exc:
            details.append("emulator refused the seed with `id` on messages: " + str(exc)[:200])
            kept = False
        else:
            got: dict[str, str] = {}
            for name in sorted({i.channel for i in sample}):
                for m in self.emu.all_channel_messages(self.teamctx_token, self.ids.channels[name]):
                    got[m["id"]] = m["timestamp"]
            wanted = {i.key for i in sample}
            kept = wanted <= set(got)
            stamps = sorted(got.values())
            details.append(f"seeded {len(sample)} messages with explicit ids from March 2026 (snowflakes encode the original dates)")
            details.append(f"emulator returned {len(got)} messages; requested ids present: {kept}")
            if stamps:
                details.append(f"reported timestamps: {stamps[0]} .. {stamps[-1]} (all taken at seed time, not from the ids)")
            details.append("the seed schema has no field for message id, timestamp or reply reference (index.d.ts: channel, author, content)")
        decision = ("ids kept: Act 1 would be seeded as history" if kept else
                    "ids NOT kept and timestamps are seed time, so Act 1 is posted live like the others "
                    "(date-based eval cases stay n.a.)")
        result = {"ids_kept": bool(kept), "details": details, "decision": decision, "at": now_iso()}
        self.state["history"] = result
        self.state.save()
        atomic_write_text(self.paths.history_json, json.dumps(result, indent=2))
        self.rec.event("history", f"history-seeding experiment: ids kept = {kept}")
        self.emu_start()  # back to the real seed
        return result

    # -- configuration and model

    def cmd_config(self) -> dict:
        binary = self.binary()
        self.rec.info(f"using teamctx binary {binary}")
        code, out, err = self.cli(["init", "--application-id", S.APP_TEAMCTX_ID, "--guild-id", S.GUILD_ID,
                                   "--timezone", S.server_timezone()])
        if code != 0:
            raise H.HostError("teamctx init failed: " + envfile.redact(err)[:300])
        choice = H.choose_model(self.or_transport, self.local_transport, self.llm_key)
        self._choice = choice
        self.state["model"] = {"kind": choice.kind, "reason": choice.reason, "probe_status": choice.probe_status,
                               "table": {k: v for k, v in (choice.table or {}).items()}}
        text = H.build_config(out, api_url=SHIM_URL, choice=choice)
        atomic_write_text(self.paths.toml, text)
        self.state.save()
        self.rec.event("config", f"config written ({choice.kind}: {choice.reason})")
        return self.state["model"]

    def _model_env(self) -> dict:
        choice = getattr(self, "_choice", None)
        if choice is None and self.model().get("kind") == "openrouter" and self.llm_key:
            return {"TEAMCTX_LLM_KEY": self.llm_key}
        return dict(choice.env) if choice else {}

    # -- shim between teamctx and the emulator (adds the empty thread lists the emulator lacks)

    def shim_up(self) -> bool:
        import socket
        try:
            with socket.create_connection(("127.0.0.1", SHIM_PORT), timeout=1):
                return True
        except OSError:
            return False

    def shim_start(self) -> None:
        if self.shim_up():
            return
        flags = 0
        if hasattr(subprocess, "DETACHED_PROCESS"):
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        sim = Path(__file__).resolve().parents[1] / "sim.py"
        log = open(self.paths.state / "shim-process.log", "ab")
        proc = subprocess.Popen([sys.executable, "-I", str(sim), "shim"], stdout=log, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, creationflags=flags)
        log.close()
        self.state["shim_pid"] = proc.pid
        self.state.save()
        if self.wait_for(self.shim_up, 15, 0.2) is None:
            raise RuntimeError("the shim did not start on port %d" % SHIM_PORT)
        self.rec.event("shim", f"shim listening on {SHIM_URL} -> emulator (thread-list stubs, websocket tunnel)")

    def shim_stop(self) -> None:
        pid = self.state.get("shim_pid")
        if pid:
            try:
                os.kill(int(pid), 15)
            except OSError:
                pass
            self.state["shim_pid"] = None
            self.state.save()

    def shim_stubs(self) -> int:
        try:
            return sum(1 for _ in open(self.paths.state / "shim.log", encoding="utf-8"))
        except OSError:
            return 0

    # -- host

    def host_env(self) -> dict[str, str]:
        return H.child_env(dict(os.environ), {"TEAMCTX_DISCORD_TOKEN": self.teamctx_token, **self._model_env()})

    def host_start(self, *, wait: float = 90.0) -> None:
        self.shim_start()
        self.host_proc = H.HostProcess(self.binary(), self.paths.toml, self.paths.db, self.paths.host_log, self.host_env())
        self.host_proc.start()
        if self.host_proc.proc is not None:  # so a later reset can stop a host orphaned by a crash
            self.state["host_pid"] = self.host_proc.proc.pid
            self.state.save()
        self.rec.event("host", "teamctx run started")
        api = self.api()
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            if not self.host_proc.alive():
                raise H.HostError("teamctx exited during startup (exit %s): %s" % (self.host_proc.exit_code(), self.host_proc.log_tail(15)))
            if api.healthz():
                break
            self.sleep(0.5)
        else:
            raise H.HostError("teamctx did not answer /healthz in time")
        if self.paths.api_token.exists():
            while time.monotonic() < deadline:
                st = api.status()
                if st and (st.get("sync") or {}).get("gateway") == "connected":
                    self.rec.event("host", "gateway connected")
                    return
                self.sleep(1.0)
            raise H.HostError("gateway did not reach 'connected': " + self.host_proc.log_tail(15))

    def host_stop(self, note: str = "") -> int | None:
        if self.host_proc is None:
            return None
        code = self.host_proc.stop()
        self.rec.event("host", f"teamctx run stopped (exit {code}) {note}")
        self.host_proc = None
        return code

    def make_token(self) -> None:
        if self.paths.api_token.exists():
            return
        code, out, err = self.cli(["token", "create", "sim-checker", "--db", str(self.paths.db)])
        value = H.extract_token(out)
        if code != 0 or not value:
            raise H.HostError("could not create the API token: " + envfile.redact(err or out)[:200])
        atomic_write_text(self.paths.api_token, value)
        self.rec.event("token", "API token created and stored in .state/api-token")

    # -- synchronisation waits

    def wait_for(self, predicate, timeout: float, step: float = 1.0) -> float | None:
        """Polls until `predicate()` is true; returns the seconds waited, or None on timeout."""
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            if predicate():
                return time.monotonic() - start
            self.sleep(step)
        return None

    def synced_all(self, act: int) -> bool:
        keys = [k for k in self.mapping["items"] if self.mapping["items"][k].get("state") == "posted"
                and self.driver_by_key()[k].act <= act and not self.mapping["items"][k].get("deleted")]
        have = {m["id"]: m for m in self.store().messages()}
        by_key = self.driver_by_key()
        for k in keys:
            entry = self.mapping["items"][k]
            row = have.get(entry["emu_id"])
            if row is None:
                return False
            if by_key[k].edit_later and entry.get("edited") and row["content"] == by_key[k].content:
                return False
        deleted = [self.mapping["items"][k]["emu_id"] for k in self.mapping["items"] if self.mapping["items"][k].get("deleted")]
        return not any(d in have for d in deleted)

    def driver_by_key(self) -> dict:
        return {i.key: i for i in self.items}

    def synced_probe(self, key: str) -> bool:
        entry = self.mapping["items"].get(key)
        return bool(entry and entry.get("emu_id") in {m["id"] for m in self.store().messages()})

    # -- checks

    def context(self, *, with_host: bool = True) -> C.Context:
        offline = self.state.get("offline_eval")
        return C.Context(
            dataset=self.dataset, items=self.items, mapping=self.mapping["items"], state=self.state.data, ids=self.ids,
            store=self.store(), api=self.api() if with_host and self.paths.api_token.exists() else None,
            emu=self.emu, teamctx_token=self.teamctx_token, eval_file=self.eval_file, offline_eval=offline,
            today=S.local_today(), llm=self.llm_on(),
            cli=(lambda args, env=None: self.cli(args, env)) if with_host else None,
            export_dir=self.paths.export_dir,
            token_value=lambda: self.paths.api_token.read_text(encoding="utf-8").strip())

    def save_check(self, check: C.Check) -> C.Check:
        checks = self.state.setdefault("checks", [])
        checks[:] = [c for c in checks if not (c["id"] == check.id and c.get("act") == check.act)]
        checks.append(check.to_json())
        self.state.save()
        self.rec.info(f"check {check.id} {check.name}: {check.status.upper()}  {check.evidence}")
        self.rec.event("check", f"{check.id} {check.name}: {check.status}", status=check.status, act=check.act)
        return check

    def load_offline_eval(self) -> None:
        text = ""
        try:
            code, out, _ = self.cli(["eval"])
            text = out if code == 0 else ""
        except (H.HostError, OSError, subprocess.SubprocessError):
            text = ""
        parsed = C.parse_eval_table(text) if text else {}
        source = "teamctx eval (the binary under test)"
        if not parsed or not parsed.get("search"):
            parsed = C.load_baseline(S.REPO / "fixtures" / "demo" / "eval-baseline.toml")
            source = "fixtures/demo/eval-baseline.toml (same numbers `cargo xtask eval` prints)"
        self.state["offline_eval"] = parsed
        self.state["offline_eval_source"] = source
        self.state.save()

    # -- scenario

    def stage_done(self, name: str) -> bool:
        return name in self.state.setdefault("stages", [])

    def mark(self, name: str) -> None:
        stages = self.state.setdefault("stages", [])
        if name not in stages:
            stages.append(name)
        self.state.save()

    def plan_lines(self, *, stop_before_host: bool) -> list[str]:
        lines = [
            "preflight: assert emulator URL is loopback; load .env (value never printed)",
            "seed: build seed.json (6 users, 2 applications, guild, category, 5 channels, leads overwrite, role) and copy it into WSL via stdin",
            "history experiment: restart emulator with seed messages carrying explicit ids, read them back, restart with the real seed",
            "emulator: stop, copy seed, start detached via wsl.exe, wait for READY",
        ]
        if not stop_before_host:
            lines += [
                f"model: probe OpenRouter once ({H.OPENROUTER_PROBE_MODEL}, max_tokens 5), else LM Studio at 127.0.0.1:1234, else no [llm]",
                f"config: `teamctx init --application-id {S.APP_TEAMCTX_ID} --guild-id {S.GUILD_ID} --timezone {S.server_timezone()}`, then set [discord] api_url, add [llm]",
                "doctor --live against the emulator",
                "token create sim-checker -> .state/api-token (file only)",
                "host: teamctx run --config .state/teamctx.toml --db .state/teamctx.db (child env: bot token, LLM key)",
                "check 1 startup",
            ]
        d = self.driver()
        for act in (1, 2, 3, 4):
            lines.append(f"-- act {act} ({S.ACT_NAMES[act]}) --")
            if act == 3 and not stop_before_host:
                lines.append("stop teamctx (hard stop), then post act 3 while it is offline")
            plan = d.plan_calls(act)
            lines.append(f"post {len(plan)} planned calls; first: {plan[0] if plan else '-'}; last: {plan[-1] if plan else '-'}")
            if act == 4:
                lines.append("gateway-disconnect mode=reconnect at 1/3 of the act, mode=invalidate at 2/3; 3 messages posted right after each")
            if act == 3 and not stop_before_host:
                lines.append("start teamctx again; measure time until all act-3 messages are stored")
            if stop_before_host:
                continue
            for cap in S.build_captures(self.dataset):
                if cap.act == act:
                    lines.append(f"capture {cap.key} as {self.driver().cast[cap.actor].username}: {cap.command}"
                                 + (f" {cap.sub}" if cap.sub else "") + f" ({cap.label})")
            for q in [s for s in S.build_searches() if s.act == act]:
                lines.append(f"query /search {q.text!r}")
            lines.append(f"query /catchup as two users, /teamctx status" + (" ; /ask x3 + /catchup summarize:true" if act == 4 else ""))
            lines.append(f"check 2 sync completeness, check 0 harness integrity (act {act})")
        if stop_before_host:
            lines.append("stop here: no teamctx binary needed; check 0 (emulator ground truth) after act 1")
        else:
            lines += ["checks 3 to 10 (offline gap, commands, retrieval, visibility, injection, /ask over HTTP, export, agent surface)",
                      "stop host, write report to prototypes/teamctx-sim/reports/<run>/report.md"]
        return lines

    def run_all(self, *, stop_before_host: bool = False, force: bool = False) -> Path | None:
        if not stop_before_host:
            self.binary()  # fail early with a clear message
        if force:
            self.cmd_reset(keep_emulator=True)
        else:
            self.require_mode()
        self.rec.event("run", f"run-all start (stop_before_host={stop_before_host}, mode={self.state['mode']})")
        if not self.stage_done("seed"):
            self.cmd_seed()
            self.mark("seed")
        if not self.stage_done("history"):
            self.history_experiment()
            self.mark("history")
        elif not self.emu.alive():
            self.emu_start()
        problems = self.verify_seed()
        if problems:
            raise RuntimeError("seed verification failed: " + "; ".join(problems))
        self.rec.info("emulator seeded as planned (cast, channels, leads overwrite, 66560 bot role)")
        if stop_before_host:
            return self._partial_without_host()
        try:
            self._prepare_host()
            self._scenario()
            return self._finish()
        except BaseException as exc:
            # Never leave teamctx or the shim running after a crash: the next run's reset
            # cannot delete .state while teamctx.exe from .state/bin is still running.
            self.rec.event("error", "run failed: " + envfile.redact(f"{type(exc).__name__}: {exc}")[:300])
            try:
                self.host_stop("(run failed)")
            finally:
                self.shim_stop()
            raise

    # The no-teamctx partial run: seed, emulator, history experiment, post act 1, verify against the emulator.
    def _partial_without_host(self) -> Path:
        d = self.driver()
        d.post_act(1)
        check = self.save_check(C.check_harness(self.context(with_host=False), 1))
        d.post_act(2)
        self.save_check(C.check_harness(self.context(with_host=False), 2))
        _ = check
        return self._finish(scope="partial: emulator, seed, history experiment and posting only (no teamctx binary)")

    def _prepare_host(self) -> None:
        self.shim_start()
        if not self.stage_done("config"):
            self.cmd_config()
            self.load_offline_eval()
            self.mark("config")
        self.make_token()
        code, out, err = self.cli(["doctor", "--live", "--config", str(self.paths.toml)])
        self.state["doctor"] = [code, envfile.redact(out + err)]
        self.state.save()
        self.rec.event("doctor", f"doctor --live exit {code}")
        self.host_start()
        self.save_check(C.check_startup(self.context(), tuple(self.state["doctor"])))

    def _settle(self, act: int, label: str, timeout: float = 90.0) -> float | None:
        secs = self.wait_for(lambda: self.synced_all(act), timeout)
        self.rec.event("sync", f"{label}: " + (f"all messages stored after {secs:.1f} s" if secs is not None else f"not all stored within {timeout:.0f} s"))
        return secs

    def _act_cycle(self, act: int, **post_kw) -> None:
        d = self.driver()
        d.post_act(act, **post_kw)
        self._settle(act, f"act {act}")
        d.run_captures(act, synced=self.synced_probe)
        d.run_queries(act, llm=self.llm_on())
        self.save_check(C.check_sync(self.context(), act))
        self.save_check(C.check_harness(self.context(), act))

    def _scenario(self) -> None:
        self._act_cycle(1)
        self._act_cycle(2)
        # Act 3: the offline gap.
        d = self.driver()
        stopped = now_iso()
        self.host_stop("(offline gap: hard stop)")
        d.post_act(3)
        restarted = now_iso()
        started = time.monotonic()
        self.host_start()
        secs = self.wait_for(lambda: self.synced_all(3), 180)
        self.state["gap"] = {"stopped_at": stopped, "restarted_at": restarted, "sync_seconds": None if secs is None else round(time.monotonic() - started, 1),
                             "stop_note": "TerminateProcess; teamctx has no way to be shut down gracefully by a Windows parent"}
        self.state.save()
        self.rec.event("gap", f"offline gap closed: all act-3 messages stored {self.state['gap']['sync_seconds']} s after restart")
        d.run_captures(3, synced=self.synced_probe)
        d.run_queries(3, llm=self.llm_on())
        self.save_check(C.check_sync(self.context(), 3))
        self.save_check(C.check_harness(self.context(), 3))
        # Act 4 with a reconnect and an invalidated session.
        d4 = self.driver()
        d4.post_act(4, disconnects=[(1 / 3, "reconnect"), (2 / 3, "invalidate")])
        self._settle(4, "act 4", timeout=120.0)
        d4.run_captures(4, synced=self.synced_probe)
        d4.run_queries(4, llm=self.llm_on())
        self.save_check(C.check_sync(self.context(), 4))
        self.save_check(C.check_harness(self.context(), 4))

    def _finish(self, scope: str = "full scenario") -> Path:
        ctx = self.context(with_host=self.paths.api_token.exists() and self.host_proc is not None and self.host_proc.alive())
        asks: dict = {}
        if ctx.api is not None:
            self.save_check(C.check_offline_gap(ctx))
            self.save_check(C.check_commands(ctx))
            self.save_check(C.check_retrieval(ctx))
            self.save_check(C.check_visibility(ctx))
            self.save_check(C.check_ask_http(ctx, asks_out=asks, on_ask=self._ask_event,
                                             pause=(lambda: self.sleep(2.0)) if self.watch else None))
            self.state["asks"] = asks
            self.state.save()
            self.save_check(C.check_injection(ctx, asks))
            self.save_check(C.check_export(ctx))
            self.save_check(C.check_agent_surface(ctx, API_URL))
            if self.realism:
                self.save_check(C.check_realistic_chat(ctx))
                self.save_check(C.check_names(ctx))
                self.save_check(C.check_secret(ctx, asks))
                self.save_check(C.check_absent_catchup(ctx))
                self.save_check(C.check_relative_due(ctx))
        if self.host_proc is not None:
            self.host_stop("(end of run)")
        path = self.write_report(scope)
        self.shim_stop()
        return path

    def _ask_event(self, qid: str, item: dict) -> None:
        """Timeline entry for one /ask answered over HTTP, so the live view can show it as it happens."""
        self.rec.event("ask", f"asked over the API: {qid}", key=qid, question=item.get("question"), text=item.get("text"),
                       found=item.get("found"), citations=item.get("citations"))

    # -- report

    def write_report(self, scope: str | None = None) -> Path:
        checks = list(self.state.get("checks", []))
        order = lambda c: (0 if c["id"] == "0" else int(c["id"]), c.get("act") or 0)
        checks.sort(key=order)
        run_id = dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S")
        model = self.model()
        usage = self.store().llm_usage() if self.paths.db.exists() else {}
        try:
            version = self.cli(["--version"])[1].strip() if self.binary_arg or H.DEFAULT_BINARY.exists() else "not run"
        except (H.HostError, OSError, subprocess.SubprocessError):
            version = "not run"
        facts = {
            "teamctx binary": f"{(self.binary_arg or H.DEFAULT_BINARY)} ({version}); run from a copy in .state/bin, sha256 {(self.state.get('binary') or {}).get('sha256', 'n/a')}...",
            "emulator": "@deploybaseline/discord 0.14.0 in WSL distro sbx-ubuntu, http://localhost:4000 (inspector: that URL, no token needed)",
            "model for /ask": f"{model.get('kind')}: {model.get('reason')}" + (f"; model {model.get('table', {}).get('model')}" if model.get("table") else ""),
            "model tokens recorded by teamctx (llm_usage)": usage,
            "offline eval source": self.state.get("offline_eval_source", "not loaded"),
            "attachments": "supported by emulator" if self.state.get("attachments_supported") else "n.a. (emulator ignores attachments on simulated messages)"
            if self.state.get("attachments_supported") is False else "not tested",
            "shim": f"teamctx talks to a loopback shim ({SHIM_URL}) that forwards to the emulator and turns the emulator's 404 on thread-list routes into empty lists ({self.shim_stubs()} stubbed responses)",
            "folded thread ids": ", ".join(S.channel_plan(self.dataset)[2]),
            "mode": ("realism (patterns from a real team server, see prototypes/teamctx-sim/REALISM.md): handles as display names, quick "
                     "fragments, reactions, image-only messages, off-topic bursts, pasted AI answers, a pasted fake key, a "
                     "recap-only decision, an absent member, relative due dates" if self.realism else "plain (the original scenario)"),
            "server timezone": f"{S.server_timezone()} (this build accepts only UTC or a fixed offset)",
        }
        meta = {"run_id": run_id, "generated": now_iso(), "scope": scope or self.state.get("scope", "full scenario"), "facts": facts}
        extra = {"act_counts": S.act_counts(self.items), "history": self.state.get("history"),
                 "assumptions": FACTS_ASSUMPTIONS, "observations": self._observations(checks)}
        retrieval = [c for c in checks if c["id"] == "5" and c.get("data")]
        if retrieval:
            extra["retrieval"] = self._retrieval_rows(retrieval[-1]["data"])
        results = self.context(with_host=False).results()
        path = R.write_report(self.paths.reports, meta, checks, self.rec.load_events(), results, extra)
        self.rec.info(f"report written: {path}")
        return path

    def _retrieval_rows(self, data: dict) -> list[list]:
        rows = []
        offline = self.state.get("offline_eval") or {}
        for tool, off_tool in (("search", "search"), ("context", "context_for")):
            for group, m in data.get("summary", {}).get(tool, {}).items():
                if m["msg_r10"] is None:
                    continue
                off = C._offline_group(offline.get(off_tool) or {}, group)
                f = lambda x: "-" if x is None else f"{x:.4f}"
                rows.append([tool, group, m["cases"], f(m["msg_r10"]), f(m["msg_mrr"]),
                             f(off and off["msg_r10"]), f(off and off["msg_mrr"]),
                             "-" if not off else f"{m['msg_r10'] - off['msg_r10']:+.4f}",
                             "-" if not off else f"{m['msg_mrr'] - off['msg_mrr']:+.4f}"])
        return rows

    def _observations(self, checks: list[dict]) -> list[str]:
        obs = ["The product bot's effective permissions include everything in the guild's @everyone permissions (the spec's "
               "everyone_permissions include SEND_MESSAGES), so `doctor --live` may warn about permissions beyond 66560; "
               "the managed bot role itself is exactly 66560."]
        for c in checks:
            if c["id"] == "6":
                obs += [d for d in c.get("details", []) if d.startswith("observation:")]
        return obs

    # -- reset

    def _stop_orphans(self) -> None:
        """Stops a teamctx host and shim left behind by an earlier run that crashed."""
        self.shim_stop()
        pid = self.state.get("host_pid")
        if pid:
            try:
                os.kill(int(pid), 15)
            except OSError:
                pass
            self.state["host_pid"] = None
            self.state.save()
            self.sleep(1.0)

    def cmd_reset(self, *, keep_emulator: bool = False) -> None:
        if self.host_proc is not None:
            self.host_stop("(reset)")
        self._stop_orphans()
        if not keep_emulator:
            self.wsl.stop()
        import shutil
        if self.paths.state.exists():
            shutil.rmtree(self.paths.state)
        self.paths.ensure()
        self.state = JsonStore(self.paths.state_json)
        self.state["mode"] = "realism" if self.realism else "plain"
        self.mode_conflict = None
        self.mapping = JsonStore(self.paths.map_json, {"items": {}})
        self.rec.info("state reset (reports kept)")
