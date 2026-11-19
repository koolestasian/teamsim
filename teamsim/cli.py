"""The command line: ``python -m teamsim`` (engine spec section 9).

Subcommands: ``demo``, ``run``, ``validate``, ``inspect``, ``replay`` and ``generate``.
``reduce`` is listed in the specification but is not part of version 0; it prints that and
exits 2.

Exit codes: 0 success; 1 a failed check (``run``), a validation mismatch or a replay that
does not reproduce the record; 2 a usage or input error. Errors are one line on standard
error, never a traceback.

``--subject "<command>"`` is split with ``shlex.split`` using POSIX rules on every
operating system, so on Windows a backslash in the command must be doubled or the path
quoted. The record names only the program's base name, never its arguments or path, and the
subject's standard error is written to ``stderr-<name>.txt`` with the pack's secret values
replaced by ``[redacted]``.

This module reads and writes files and a clock (for timings, which never enter a record).
It is the only core module that does.
"""

import argparse
import importlib
import os
import shlex
import shutil
import sys
import time
from pathlib import Path

from teamsim import checks, controls, engine, generate, ledger, model, pack, record, report
from teamsim.subject import ChildProcess, InProcess

ENGINE_VERSION = "0.1.0"
ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_BOTS = ("naive_bot", "careful_bot")
BUILTINS = tuple(controls.NAMES) + EXAMPLE_BOTS
DEMO_PACK = ROOT / "packs" / "team-ten"

OK, FAILED, USAGE = 0, 1, 2


class CliError(Exception):
    """An input or usage error: one line on standard error, exit code 2."""


def _line(text: object) -> str:
    return " ".join(str(text).split())


# --- subjects ----------------------------------------------------------------------


def _example_bot(name: str):
    if str(ROOT) not in sys.path:
        sys.path.append(str(ROOT))
    try:
        module = importlib.import_module("examples." + name)
        return module.Bot()
    except Exception as error:  # a missing or broken example is an input problem
        raise CliError(
            "built-in subject %s is not available (%s)" % (name, type(error).__name__)
        ) from None


def _secret_values(the_pack) -> tuple:
    return tuple(f.value for f in the_pack.facts if f.kind == model.FACT_SECRET)


def _file_label(name: str) -> str:
    return "".join(c if c.isalnum() or c in "_.-" else "-" for c in name)


def _program_name(argv0: str) -> str:
    return argv0.replace("\\", "/").rsplit("/", 1)[-1]


class _Subject:
    """What ``run`` needs about one subject: a label, a descriptor and a session factory."""

    def __init__(self, label, descriptor, make_session):
        self.label = label
        self.descriptor = descriptor
        self.make_session = make_session  # (the_pack, stderr_path) -> Session


def _builtin_subject(name: str) -> _Subject:
    if name not in BUILTINS:
        raise CliError("unknown built-in subject %r; choose one of: %s" % (name, ", ".join(BUILTINS)))

    def make(the_pack, stderr_path):
        if name in controls.NAMES:
            return InProcess(controls.make(name, the_pack))
        return InProcess(_example_bot(name))

    return _Subject(_file_label(name), {"builtin": name}, make)


def _command_subject(command: str) -> _Subject:
    try:
        argv = shlex.split(command)
    except ValueError as error:
        raise CliError("cannot read the subject command: %s" % _line(error)) from None
    if not argv:
        raise CliError("the subject command is empty")
    program = _program_name(argv[0])
    if shutil.which(argv[0]) is None:
        raise CliError("the subject program %r was not found" % program)

    def make(the_pack, stderr_path):
        return ChildProcess(
            argv, stderr_path=stderr_path, redact=_secret_values(the_pack)
        )

    return _Subject(_file_label(Path(program).stem or program), {"command": program}, make)


# --- running -----------------------------------------------------------------------


def _ms(start: int) -> int:
    return (time.monotonic_ns() - start) // 1_000_000


def _run_once(the_pack, subject: _Subject, stderr_path=None):
    """One run: ``(RunResult, timing rows)``."""
    head = record.header(the_pack, subject.descriptor, engine=ENGINE_VERSION)
    session = subject.make_session(the_pack, stderr_path)
    started = time.monotonic_ns()
    try:
        entries = engine.run(the_pack, session)
    except OSError as error:
        raise CliError(
            "the subject could not be started (%s)" % type(error).__name__
        ) from None
    engine_ms = _ms(started)
    started = time.monotonic_ns()
    verdicts = checks.evaluate(the_pack, entries)
    checks_ms = _ms(started)
    result = record.build(head, entries, verdicts)
    return result, [
        {"phase": "engine", "wall_ms": engine_ms},
        {"phase": "checks", "wall_ms": checks_ms},
    ]


def _write_outputs(out: Path, label: str, suffix: str, result, timing, *, matrix=None, repeats=None):
    stem = label + suffix
    paths = {
        "record": out / ("record-%s.jsonl" % stem),
        "report": out / ("report-%s.md" % stem),
        "json": out / ("report-%s.json" % stem),
        "timing": out / ("timing-%s.jsonl" % stem),
    }
    record.write(result, paths["record"])
    paths["report"].write_bytes(
        report.markdown(result, matrix=matrix, repeats=repeats).encode("utf-8")
    )
    paths["json"].write_bytes(
        (_dump(report.json_obj(result, matrix=matrix, repeats=repeats)) + "\n").encode("utf-8")
    )
    record.write_timing(
        [dict(row, subject=label, run=int(suffix.lstrip("-") or "1")) for row in timing],
        paths["timing"],
    )
    return paths


def _dump(obj) -> str:
    import json

    return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True)


def _summary(label: str, result) -> str:
    per_kind: dict = {}
    for v in result.verdicts:
        row = per_kind.setdefault(v.kind, {})
        row[v.verdict] = row.get(v.verdict, 0) + 1
    parts = []
    for kind in sorted(per_kind):
        row = per_kind[kind]
        text = "%s %d pass %d fail" % (kind, row.get("pass", 0), row.get("fail", 0))
        for verdict in ("not_applicable", "harness_error"):
            if row.get(verdict):
                text += " %d %s" % (row[verdict], verdict.replace("_", " "))
        parts.append(text)
    return "%s: %s" % (label, "; ".join(parts))


def _failed(result) -> bool:
    return any(v.verdict in (model.VERDICT_FAIL, model.VERDICT_HARNESS_ERROR) for v in result.verdicts)


def _run_subject(the_pack, subject: _Subject, out: Path, repeats: int, *, matrix=None, stdout):
    out.mkdir(parents=True, exist_ok=True)
    results, timings = [], []
    for index in range(1, repeats + 1):
        suffix = "" if repeats == 1 else "-%d" % index
        stderr_path = None
        if "command" in subject.descriptor:
            stderr_path = str(out / ("stderr-%s%s.txt" % (subject.label, suffix)))
        result, timing = _run_once(the_pack, subject, stderr_path)
        results.append(result)
        timings.append(timing)
    paths = []
    for index, (result, timing) in enumerate(zip(results, timings), 1):
        suffix = "" if repeats == 1 else "-%d" % index
        paths.append(
            _write_outputs(
                out, subject.label, suffix, result, timing,
                matrix=matrix, repeats=results if repeats > 1 else None,
            )
        )
    for result in results:
        print(_summary(subject.label, result), file=stdout)
    if repeats > 1:
        passed = sum(1 for r in results if not _failed(r))
        print(
            "%s: %d of %d repeats passed every check" % (subject.label, passed, repeats),
            file=stdout,
        )
    for p in paths:
        for key in ("record", "report", "json", "timing"):
            print("  %s" % p[key], file=stdout)
    return results


# --- the matrix --------------------------------------------------------------------


def _print_matrix(the_pack, matrix, stdout) -> None:
    names = list(matrix)
    width = max([len(c.id) for c in the_pack.checks] + [5])
    cells = {n: {cid: _cell(pair) for cid, pair in matrix[n].items()} for n in names}
    widths = {n: max([len(n)] + [len(v) for v in cells[n].values()]) for n in names}
    print("%-*s  %s" % (width, "check", "  ".join("%-*s" % (widths[n], n) for n in names)), file=stdout)
    for check in the_pack.checks:
        row = "  ".join("%-*s" % (widths[n], cells[n].get(check.id, "")) for n in names)
        print("%-*s  %s" % (width, check.id, row), file=stdout)


def _cell(pair) -> str:
    verdict, reason = pair
    if verdict == model.VERDICT_PASS:
        return "pass"
    if verdict == model.VERDICT_FAIL:
        return "fail:%s" % reason
    return {"not_applicable": "n/a"}.get(verdict, verdict)


# Lines of controls.validate that are information, not mismatches.
_INFORMATION = (": not exercised: ", ": not detected: ")


def _validate(the_pack, stdout, stderr) -> tuple:
    matrix = controls.matrix(the_pack)
    _print_matrix(the_pack, matrix, stdout)
    lines = controls.validate(the_pack)
    for line in lines:
        print(_line(line), file=stdout)
    problems = [x for x in lines if not any(m in x for m in _INFORMATION)]
    if problems:
        print("validation failed: %d mismatch(es)" % len(problems), file=stderr)
    else:
        print("validation passed: every control got the verdict the ledger predicts", file=stdout)
    return matrix, problems


# --- commands ----------------------------------------------------------------------


def _load_pack(path):
    try:
        return pack.load(path)
    except pack.PackError as error:
        raise CliError("cannot load pack: %s" % _line(error)) from None
    except OSError as error:
        raise CliError("cannot read pack: %s" % _line(error.strerror or type(error).__name__)) from None


def _cmd_demo(args, stdout, stderr) -> int:
    the_pack = _load_pack(DEMO_PACK)
    print("pack %s" % the_pack.header.id, file=stdout)
    matrix, problems = _validate(the_pack, stdout, stderr)
    if problems:
        return FAILED
    out = Path(args.out)
    for name in EXAMPLE_BOTS:
        _run_subject(the_pack, _builtin_subject(name), out, 1, matrix=matrix, stdout=stdout)
    return OK


def _cmd_run(args, stdout, stderr) -> int:
    if args.repeats < 1:
        raise CliError("--repeats must be at least 1")
    subject = _builtin_subject(args.builtin) if args.builtin else _command_subject(args.subject)
    the_pack = _load_pack(args.pack)
    results = _run_subject(the_pack, subject, Path(args.out), args.repeats, stdout=stdout)
    return FAILED if any(_failed(r) for r in results) else OK


def _cmd_validate(args, stdout, stderr) -> int:
    _, problems = _validate(_load_pack(args.pack), stdout, stderr)
    return FAILED if problems else OK


_INSPECT_COLUMNS = ("who", "fact", "key", "n", "t_ms", "event", "by", "authoritative", "allowed")


def _cmd_inspect(args, stdout, stderr) -> int:
    the_pack = _load_pack(args.pack)
    entries = engine.run(the_pack, InProcess(controls.make("null", the_pack)))
    rows = ledger.Ledger(the_pack, entries).table()
    table = [[str(row[c]) for c in _INSPECT_COLUMNS] for row in rows]
    widths = [max([len(c)] + [len(r[i]) for r in table]) for i, c in enumerate(_INSPECT_COLUMNS)]
    print("  ".join(c.ljust(w) for c, w in zip(_INSPECT_COLUMNS, widths)).rstrip(), file=stdout)
    for row in table:
        print("  ".join(v.ljust(w) for v, w in zip(row, widths)).rstrip(), file=stdout)
    return OK


def _cmd_replay(args, stdout, stderr) -> int:
    the_pack = _load_pack(args.pack)
    try:
        recorded = record.read(args.record)
        again = record.replay(args.record, the_pack)
    except record.RecordError as error:
        print("record not reproduced: %s" % _line(error), file=stderr)
        return FAILED
    except OSError as error:
        raise CliError("cannot read record: %s" % _line(error.strerror or type(error).__name__)) from None
    if again.digest == recorded.digest:
        print("reproduced %s" % again.digest, file=stdout)
        return OK
    print(
        "record not reproduced: recorded digest %s, replayed digest %s" % (recorded.digest, again.digest),
        file=stderr,
    )
    return FAILED


def _cmd_generate(args, stdout, stderr) -> int:
    try:
        made = generate.generate_file(args.population, args.out)
    except generate.PopulationError as error:
        raise CliError("cannot generate: %s" % _line(error)) from None
    except pack.PackError as error:
        raise CliError("generated pack is invalid: %s" % _line(error)) from None
    except OSError as error:
        raise CliError("cannot read or write: %s" % _line(error.strerror or type(error).__name__)) from None
    print("wrote pack %s to %s" % (made.header.id, args.out), file=stdout)
    print("hash %s" % pack.pack_hash(made), file=stdout)
    return OK


def _cmd_reduce(args, stdout, stderr) -> int:
    raise CliError("reduce is not in version 0")


# --- parsing -----------------------------------------------------------------------


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        print("%s: error: %s" % (self.prog, _line(message)), file=sys.stderr)
        raise SystemExit(USAGE)


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="python -m teamsim",
        description="Synthetic users that test software, scored against planted facts.",
    )
    sub = parser.add_subparsers(dest="command", metavar="command", parser_class=_Parser)

    demo = sub.add_parser("demo", help="validate the team-ten pack, run naive_bot and careful_bot")
    demo.add_argument("--out", default="teamsim-demo", help="output directory (default: teamsim-demo)")
    demo.set_defaults(func=_cmd_demo)

    run = sub.add_parser("run", help="run one subject against a pack and write a record and reports")
    run.add_argument("pack", help="pack directory")
    which = run.add_mutually_exclusive_group(required=True)
    which.add_argument("--subject", help="command that starts the subject (split with POSIX shell rules)")
    which.add_argument("--builtin", help="one of: " + ", ".join(BUILTINS))
    run.add_argument("--repeats", type=int, default=1, help="run the subject this many times (default: 1)")
    run.add_argument("--out", default="teamsim-run", help="output directory (default: teamsim-run)")
    run.set_defaults(func=_cmd_run)

    validate = sub.add_parser("validate", help="run the control subjects and print the control-by-check matrix")
    validate.add_argument("pack", help="pack directory")
    validate.set_defaults(func=_cmd_validate)

    inspect = sub.add_parser("inspect", help="print who was exposed to which fact, and when")
    inspect.add_argument("pack", help="pack directory")
    inspect.set_defaults(func=_cmd_inspect)

    replay = sub.add_parser("replay", help="check that a record is reproduced from its recorded observations")
    replay.add_argument("record", help="record.jsonl file")
    replay.add_argument("--pack", required=True, help="the pack directory the record was made from")
    replay.set_defaults(func=_cmd_replay)

    gen = sub.add_parser("generate", help="generate a pack from a population file")
    gen.add_argument("population", help="population .toml file")
    gen.add_argument("-o", "--out", required=True, help="pack directory to write")
    gen.set_defaults(func=_cmd_generate)

    reduce = sub.add_parser("reduce", help="not in version 0")
    reduce.add_argument("args", nargs="*")
    reduce.set_defaults(func=_cmd_reduce)
    return parser


def main(argv=None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as stop:
        return stop.code if isinstance(stop.code, int) else USAGE
    if not getattr(args, "func", None):
        parser.print_usage(sys.stderr)
        return USAGE
    try:
        return args.func(args, sys.stdout, sys.stderr)
    except CliError as error:
        print("error: %s" % _line(error), file=sys.stderr)
        return USAGE
    except (ValueError, OSError) as error:
        print("error: %s" % _line(type(error).__name__), file=sys.stderr)
        return USAGE
