"""Reports built from a run record (``docs/spec/engine-modules.md`` section 8).

``markdown`` and ``json_obj`` read only a ``RunResult`` (and, when given, the control
matrix of ``teamsim.controls.matrix``). They state the pack id and hash, the seed, the
subject descriptor, the mode, the record digest, one row per check, counts per check kind,
the matrix and the limits the pack states about itself. No interval is computed over raw
check counts: checks that share a scenario are not independent.

Every string that comes from a pack or a subject is escaped before it enters the Markdown:
ASCII punctuation is backslash-escaped, ``&``, ``<`` and ``>`` become entities and line
breaks and other control characters become spaces, so links, images, tags, autolinks and
table breaks render as plain text.

The optional ``repeats`` argument is a list of results of the same pack and subject run
several times; the report then adds, for each check, how many repeats passed it.
"""

from teamsim.model import (
    VERDICT_FAIL,
    VERDICT_HARNESS_ERROR,
    VERDICT_NOT_APPLICABLE,
    VERDICT_PASS,
    RunResult,
)

__all__ = ["escape", "json_obj", "markdown"]

_VERDICT_ORDER = (VERDICT_PASS, VERDICT_FAIL, VERDICT_NOT_APPLICABLE, VERDICT_HARNESS_ERROR)
_ENTITIES = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}
_PUNCTUATION = frozenset("!\"#$%'()*+,-./:;=?@[\\]^_`{|}~")


def escape(text: object) -> str:
    """``text`` made inert for Markdown and HTML, on one line."""
    out = []
    for char in str(text):
        if char in _ENTITIES:
            out.append(_ENTITIES[char])
        elif char in _PUNCTUATION:
            out.append("\\" + char)
        elif ord(char) < 32 or ord(char) == 127 or char in "  \u0085":
            out.append(" ")
        else:
            out.append(char)
    return "".join(out)


def _subject_text(subject: dict) -> str:
    return ", ".join("%s %s" % (key, subject[key]) for key in sorted(subject))


def _pair(pair) -> dict:
    verdict, reason = pair
    obj = {"verdict": verdict}
    if reason is not None:
        obj["reason"] = reason
    return obj


def _short(pair) -> str:
    verdict, reason = pair
    if verdict == VERDICT_PASS:
        return "pass"
    if verdict == VERDICT_FAIL:
        return "fail: %s" % reason
    return verdict.replace("_", " ")


def _counts(result: RunResult) -> dict:
    counts: dict = {}
    for v in result.verdicts:
        row = counts.setdefault(v.kind, {name: 0 for name in _VERDICT_ORDER})
        row[v.verdict] += 1
    return {kind: counts[kind] for kind in sorted(counts)}


def _repeat_rows(result: RunResult, repeats) -> list:
    """Per check: repeats run and repeats that did not fail it (a pass or a check that does
    not apply), the same rule the command line uses for a repeat that passed."""
    if not repeats:
        return []
    rows = []
    for v in result.verdicts:
        passed = 0
        for other in repeats:
            for w in other.verdicts:
                if w.check == v.check and w.verdict in (VERDICT_PASS, VERDICT_NOT_APPLICABLE):
                    passed += 1
        rows.append({"check": v.check, "not_failed": passed, "repeats": len(repeats)})
    return rows


def json_obj(result: RunResult, *, matrix=None, repeats=None) -> dict:
    """The report as a plain object that ``json.dumps`` writes without loss."""
    h = result.header
    obj: dict = {
        "pack": {"id": h.pack_id, "hash": h.pack_hash},
        "seed": h.seed,
        "subject": dict(h.subject),
        "mode": h.mode,
        "engine": h.engine,
        "digest": result.digest,
        "counts": _counts(result),
        "checks": [
            {
                "check": v.check,
                "kind": v.kind,
                "verdict": v.verdict,
                "reason": v.reason,
                "policy": v.policy,
                "events": list(v.events),
                "entries": list(v.entries),
                "detail": list(v.detail),
            }
            for v in result.verdicts
        ],
        "limits": list(h.limits),
    }
    if matrix is not None:
        obj["matrix"] = {
            control: {check: _pair(pair) for check, pair in row.items()}
            for control, row in matrix.items()
        }
    rows = _repeat_rows(result, repeats)
    if rows:
        obj["repeats"] = rows
    return obj


def _table(head: list, rows: list) -> list:
    lines = ["| " + " | ".join(head) + " |", "|" + "|".join(" --- " for _ in head) + "|"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def markdown(result: RunResult, *, matrix=None, repeats=None) -> str:
    """The report as Markdown."""
    h = result.header
    e = escape
    out = ["# Run report", ""]
    out.append("- Pack: %s (hash %s)" % (e(h.pack_id), e(h.pack_hash)))
    out.append("- Seed: %s" % e(h.seed))
    out.append("- Subject: %s" % e(_subject_text(h.subject)))
    out.append("- Mode: %s" % e(h.mode))
    out.append("- Engine: %s" % e(h.engine))
    out.append("- Record digest: %s" % e(result.digest))
    out.append("")
    out.append("## Counts per check kind")
    out.append("")
    counts = _counts(result)
    out.extend(
        _table(
            ["Kind"] + [name.replace("_", " ") for name in _VERDICT_ORDER],
            [[e(kind)] + [str(row[name]) for name in _VERDICT_ORDER] for kind, row in counts.items()],
        )
    )
    out.append("")
    out.append(
        "Checks that share a scenario are not independent, so these are counts, "
        "not rates, and carry no interval."
    )
    out.append("")
    out.append("## Checks")
    out.append("")
    rows = []
    for v in result.verdicts:
        evidence = []
        if v.events:
            evidence.append("events " + ", ".join(e(x) for x in v.events))
        if v.entries:
            evidence.append("entries " + ", ".join(str(n) for n in v.entries))
        if v.detail:
            evidence.append("detail " + ", ".join(e(x) for x in v.detail))
        rows.append(
            [
                e(v.check),
                e(v.kind),
                "policy" if v.policy else "",
                e(v.verdict),
                e(v.reason) if v.reason else "",
                "; ".join(evidence),
            ]
        )
    out.extend(_table(["Check", "Kind", "Tag", "Verdict", "Reason", "Evidence"], rows))
    out.append("")
    repeat_rows = _repeat_rows(result, repeats)
    if repeat_rows:
        out.append("## Repeats")
        out.append("")
        out.extend(
            _table(
                ["Check", "Not failed in", "Repeats"],
                [[e(r["check"]), str(r["not_failed"]), str(r["repeats"])] for r in repeat_rows],
            )
        )
        out.append("")
        total = sum(r["not_failed"] for r in repeat_rows)
        every = sum(1 for r in repeat_rows if r["not_failed"] == r["repeats"])
        out.append(
            "Checks not failed in every repeat: %d of %d. Check runs not failed: %d of %d."
            % (every, len(repeat_rows), total, len(repeat_rows) * len(repeats))
        )
        out.append("")
    if matrix is not None:
        out.append("## Control matrix")
        out.append("")
        controls = list(matrix)
        check_ids = [v.check for v in result.verdicts] or sorted(
            {c for row in matrix.values() for c in row}
        )
        out.extend(
            _table(
                ["Check"] + [e(name) for name in controls],
                [
                    [e(cid)] + [e(_short(matrix[name][cid])) if cid in matrix[name] else "" for name in controls]
                    for cid in check_ids
                ],
            )
        )
        out.append("")
    out.append("## Limits")
    out.append("")
    if h.limits:
        out.extend("- %s" % e(text) for text in h.limits)
    else:
        out.append("The pack states no limits.")
    out.append("")
    return "\n".join(out)
