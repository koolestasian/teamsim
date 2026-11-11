"""Report writer: a timeline report a human can read, plus the same data as JSON.

The whole text is passed through the redactor before it is written, so a secret that slipped
into a detail string still cannot reach the file.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import envfile, script as S
from .state import atomic_write_text

ICON = {"pass": "PASS", "fail": "FAIL", "n.a.": "n.a.", "blocked": "BLOCKED"}


def _cell(text: object, limit: int = 220) -> str:
    s = " ".join(str(text if text is not None else "").split()).replace("|", "\\|")
    return s if len(s) <= limit else s[: limit - 1] + "…"


def counts(checks: list[dict]) -> dict[str, int]:
    out = {"pass": 0, "fail": 0, "n.a.": 0, "blocked": 0}
    for c in checks:
        out[c["status"]] = out.get(c["status"], 0) + 1
    return out


def timeline_lines(events: list[dict]) -> list[str]:
    """Message posts are folded into one line per run of consecutive posts."""
    lines: list[str] = []
    run: list[dict] = []

    def flush() -> None:
        if run:
            lines.append(f"- {run[0]['t']} .. {run[-1]['t']}: {len(run)} messages posted (act {run[0].get('act')})")
            run.clear()

    for e in events:
        if e["kind"] == "message":
            if run and run[-1].get("act") != e.get("act"):
                flush()
            run.append(e)
            continue
        flush()
        lines.append(f"- {e['t']} [{e['kind']}] {e['summary']}")
    flush()
    return lines


def render(meta: dict, checks: list[dict], events: list[dict], results: dict, extra: dict) -> str:
    c = counts(checks)
    out: list[str] = []
    out.append(f"# teamctx end-to-end simulation report ({meta['run_id']})")
    out.append("")
    out.append(f"Generated {meta['generated']}. Scope: {meta['scope']}.")
    out.append("")
    out.append("All names, ids and messages are fictional (the Lantern Shelf demo dataset). Secrets are redacted.")
    out.append("")
    out.append("## Summary")
    out.append("")
    out.append(f"**{c['pass']} pass, {c['fail']} fail, {c['n.a.']} n.a., {c['blocked']} blocked.**")
    out.append("")
    out.append("| # | Check | Status | Evidence |")
    out.append("|---|---|---|---|")
    for ck in checks:
        out.append(f"| {ck['id']} | {_cell(ck['name'])} | {ICON.get(ck['status'], ck['status'])} | {_cell(ck['evidence'], 320)} |")
    out.append("")
    out.append("## Run facts")
    out.append("")
    for key, value in meta.get("facts", {}).items():
        out.append(f"- **{key}:** {value}")
    out.append("")
    if extra.get("act_counts"):
        out.append("## Acts")
        out.append("")
        out.append("| Act | Dates (UTC, original) | Dataset messages | Extras | Edits | Folded from threads | Bot posts | "
                   "Realism messages | Fragments | Reactions |")
        out.append("|---|---|---|---|---|---|---|---|---|---|")
        for act, row in sorted(extra["act_counts"].items()):
            out.append(f"| {act} | {S.ACT_NAMES[int(act)]} | {row['dataset']} | {row['extras']} | {row['edits']} | {row['folded']} | "
                       f"{row['bot']} | {row.get('realism', 0)} | {row.get('fragments', 0)} | {row.get('reactions', 0)} |")
        out.append("")
    if extra.get("history"):
        h = extra["history"]
        out.append("## History-seeding experiment")
        out.append("")
        out.append(f"- Seed messages with explicit dataset ids: **ids kept: {h.get('ids_kept')}**.")
        for line in h.get("details", []):
            out.append(f"- {line}")
        out.append(f"- Decision: {h.get('decision')}")
        out.append("")
    out.append("## Timeline")
    out.append("")
    out.extend(timeline_lines(events))
    out.append("")
    out.append("## Checks in detail")
    for ck in checks:
        out.append("")
        out.append(f"### {ck['id']}. {ck['name']}: {ICON.get(ck['status'], ck['status'])}")
        out.append("")
        out.append(ck["evidence"])
        for d in ck.get("details", []):
            out.append(f"- {_cell(d, 400)}")
    if results:
        out.append("")
        out.append("## Interactions")
        out.append("")
        out.append("| Key | Command | As | Callback | Ephemeral | Answer ms | Deferred+edited | Entry | Result |")
        out.append("|---|---|---|---|---|---|---|---|---|")
        for key, r in sorted(results.items()):
            note = r.get("error") or r.get("text", "")
            if r.get("note"):
                note = f"[{r['note']}] {note}"
            out.append(
                f"| {key} | {_cell(r.get('label'), 60)} | {r.get('actor')} | {r.get('first_type')} | {r.get('ephemeral')} | "
                f"{_cell(None if r.get('answer_ms') is None else round(r['answer_ms']))} | "
                f"{'edited ' + str(round(r['edit_ms'])) + ' ms' if r.get('edited') else ('deferred, not edited' if r.get('deferred') else '-')} | "
                f"{_cell(', '.join(r.get('refs') or []))} | {_cell(note, 260)} |")
    if extra.get("retrieval"):
        out.append("")
        out.append("## Retrieval (messages, k=10)")
        out.append("")
        out.append("| Tool | Group | Cases | Live R@10 | Live MRR | Offline R@10 | Offline MRR | Delta R@10 | Delta MRR |")
        out.append("|---|---|---|---|---|---|---|---|---|")
        for row in extra["retrieval"]:
            out.append("| " + " | ".join(_cell(x) for x in row) + " |")
    if extra.get("observations"):
        out.append("")
        out.append("## Observations")
        out.append("")
        for o in extra["observations"]:
            out.append(f"- {o}")
    if extra.get("assumptions"):
        out.append("")
        out.append("## Assumptions about API shapes (not confirmed from source or docs)")
        out.append("")
        for a in extra["assumptions"]:
            out.append(f"- {a}")
    out.append("")
    return "\n".join(out)


def write_report(reports_dir: Path, meta: dict, checks: list[dict], events: list[dict], results: dict, extra: dict) -> Path:
    text = envfile.redact(render(meta, checks, events, results, extra))
    folder = reports_dir / meta["run_id"]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "report.md"
    atomic_write_text(path, text)
    payload = envfile.redact(json.dumps({"meta": meta, "checks": checks, "events": events, "results": results,
                                         "extra": extra}, indent=2, default=str))
    atomic_write_text(folder / "report.json", payload)
    atomic_write_text(reports_dir / "LATEST.txt", str(path) + "\n")
    return path
