"""Rebuild the research figures: python render.py. Requires matplotlib, only for docs.

Measured inputs and provenance are in data.json. Diagram examples are fictional;
architecture and feedback gates are proposals, not descriptions of shipped features.
"""
import csv
import json
import math
import re
from collections import Counter
from html import escape
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from matplotlib.text import Text

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
INK, MUTED, LINE = "#223247", "#536277", "#dbe2e9"
BLUE, ORANGE, GRAY = "#2864a7", "#b16b27", "#737d8a"
PALE, WARM, WHITE = "#edf3fa", "#fbf2e6", "#ffffff"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 17,
    "text.color": INK, "axes.labelcolor": INK, "xtick.color": MUTED,
    "ytick.color": INK, "axes.edgecolor": LINE, "axes.linewidth": 1.2,
    "svg.fonttype": "none", "svg.hashsalt": "teamsim-research",
    "figure.facecolor": WHITE, "axes.facecolor": WHITE,
})


def canvas(title, subtitle, height=6.4):
    fig = plt.figure(figsize=(8, height))
    fig.text(.055, .955, title, fontsize=24, weight="bold", va="top")
    fig.text(.055, .955 - .42 / height, subtitle, fontsize=16, color=MUTED, va="top")
    ax = fig.add_axes([.045, .05, .91, 1 - 1.35 / height])
    ax.set(xlim=(0, 10), ylim=(0, 10))
    ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, title, detail="", fill=PALE):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.03,rounding_size=.08",
                               linewidth=0, facecolor=fill))
    cy = y + h / 2
    two_lines = "\n" in detail
    ax.text(x + w / 2, cy + (.45 if two_lines else .28 if detail else 0), title, ha="center", va="center",
            fontsize=18, weight="bold", linespacing=1.3)
    if detail:
        ax.text(x + w / 2, cy - (.4 if two_lines else .36), detail, ha="center", va="center", fontsize=16,
                color=MUTED, linespacing=1.3)


def arrow(ax, start, end, color=GRAY, style="-"):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=16,
                               linewidth=1.5, color=color, linestyle=style))


def save(fig, name, description):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    labels = []
    for text in fig.findobj(Text):
        if not text.get_visible() or not text.get_text().strip():
            continue
        bounds = text.get_window_extent(renderer)
        assert (bounds.x0 >= -1 and bounds.y0 >= -1 and
                bounds.x1 <= fig.bbox.width + 1 and bounds.y1 <= fig.bbox.height + 1), (
                    name, "text outside figure", text.get_text())
        for other, prior in labels:
            assert not (min(bounds.x1, prior.x1) - max(bounds.x0, prior.x0) > 2 and
                        min(bounds.y1, prior.y1) - max(bounds.y0, prior.y0) > 2), (
                            name, "overlapping labels", other, text.get_text())
        labels.append((text.get_text(), bounds))
    fig.savefig(ROOT / f"{name}.png", dpi=180, facecolor=WHITE)
    vector = ROOT / f"{name}.svg"
    fig.savefig(vector, metadata={"Date": None, "Title": description})
    svg = vector.read_text(encoding="utf-8")
    tag = re.search(r"<svg\b[^>]*>", svg)
    assert tag is not None
    opening = tag.group()[:-1] + ' role="img" aria-labelledby="figure-title">'
    title = '<title id="figure-title">' + escape(description) + '</title>'
    svg = svg[:tag.start()] + opening + title + svg[tag.end():]
    vector.write_text("\n".join(line.rstrip() for line in svg.splitlines()) + "\n",
                      encoding="utf-8", newline="\n")
    plt.close(fig)


def clean_axes(ax):
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="both", length=0, pad=10)
    ax.xaxis.grid(True, color=LINE, linewidth=.8)
    ax.set_axisbelow(True)


def testing_loop():
    fig, ax = canvas("What teamsim is testing", "Conceptual loop; future boundaries are proposals", 7.2)
    box(ax, .3, 7.4, 4.1, 1.8, "Fictional scenario", "People, timeline,\nknown facts")
    box(ax, 5.6, 7.4, 4.1, 1.8, "Private answer key", "Expected facts\nand outcomes", WARM)
    box(ax, .3, 4.6, 4.1, 1.8, "Fake workspace", "Messages and events")
    box(ax, .3, 1.8, 4.1, 1.8, "Product under test", "Observed answers\nand actions")
    box(ax, 5.6, 1.8, 4.1, 1.8, "Independent checks", "Compare with\nthe answer key")
    arrow(ax, (2.35, 7.3), (2.35, 6.5))
    arrow(ax, (2.35, 4.5), (2.35, 3.7))
    arrow(ax, (4.5, 2.7), (5.5, 2.7))
    arrow(ax, (4.5, 8.3), (5.5, 8.3))
    arrow(ax, (9.2, 7.3), (9.2, 3.7), ORANGE)
    ax.text(7.2, 5.45, "Key stays outside\nthe product's reach", ha="center", fontsize=16,
            color=ORANGE, linespacing=1.4)
    ax.text(5, .55, "A score describes this scenario and these checks.", ha="center", fontsize=16)
    save(fig, "testing-loop", "Scenario and private answer key feed independent checks of a product in a fake workspace.")


def evidence_map():
    fig, ax = canvas("Where the evidence is stronger", "Editorial judgments, not numerical scores", 7.7)
    rows = [
        ("Hidden-profile failures", "Strong*", "Studied group tasks"),
        ("Repeats and intervals", "Strong*", "Studied settings"),
        ("Simulated-user difficulty", "Moderate", "Service and sales"),
        ("Persona behaviour", "Moderate", "Mostly model experiments"),
        ("Outcome and grader checks", "Moderate", "Benchmarks and audits"),
        ("Feedback prediction", "Weak", "No team validation found"),
        ("Exact chat-rate transfer", "Weak", "Community-specific rates"),
    ]
    ax.text(.2, 9.5, "Finding", fontsize=16, color=MUTED)
    ax.text(5.2, 9.5, "Evidence", fontsize=16, color=MUTED)
    for i, (label, grade, limit) in enumerate(rows):
        y = 8.55 - i * 1.18
        ax.text(.2, y + .1, label, va="center", fontsize=17)
        ax.text(.2, y - .33, limit, va="center", fontsize=16, color=MUTED)
        box(ax, 5.2, y - .34, 4.55, .75, grade, fill=WARM if grade == "Weak" else PALE)
    ax.text(.2, -.05, "* Strong within those settings; transfer still needs testing.", fontsize=16, color=MUTED)
    save(fig, "evidence-map", "Evidence grades and the limits of transfer to simulated teammates.")


def source_depth():
    fig, ax = canvas("How much source text was available", "455 papers in the bibliography", 5.6)
    colors = [BLUE, ORANGE, GRAY]
    left = 0
    for (label, count), color in zip(DATA["coverage"].items(), colors):
        width = count / 455 * 9.4
        ax.add_patch(plt.Rectangle((.3 + left, 7.5), width, 1.05, color=color, linewidth=0))
        left += width
    labels = [("428", "Full text", BLUE), ("3", "Partial / protocol", ORANGE),
              ("24", "Abstract only", GRAY)]
    for i, (count, label, color) in enumerate(labels):
        y = 5.7 - i * 1.8
        ax.add_patch(plt.Rectangle((.35, y - .17), .25, .45, color=color, linewidth=0))
        ax.text(.9, y, count, weight="bold", fontsize=23, va="center")
        ax.text(2.1, y, label, fontsize=18, va="center")
    ax.text(.3, .2, "Reader classifications; source access is not correctness.", fontsize=16, color=MUTED)
    save(fig, "source-depth", "Of 455 papers, 428 have full text, 3 partial or protocol text and 24 abstracts only.")


def review_flow():
    fig, ax = canvas("How the full-text check worked", "Main run; supplementary source checks reported separately", 8.5)
    rows = [
        ("431 texts + citing passages", "Paper text supplied as untrusted data"),
        ("Haiku reader + quote matching", "Structured claims, fixes and quotations"),
        ("Sonnet on flagged cards only", "167 flags in 110 paper cards"),
        ("1,555 final claim verdicts", "710 candidate corrections for editorial review"),
        ("Editor checks source and context", "Apply, skip or reject; then revise the synthesis"),
    ]
    for i, (title, detail) in enumerate(rows):
        y = 8.15 - i * 1.8
        box(ax, .35, y, 9.3, 1.4, title, detail, WARM if i == 2 else PALE)
        if i < len(rows) - 1:
            arrow(ax, (5, y - .05), (5, y - .36))
    ax.text(5, .05, "Partly supported claims bypass the Sonnet stage.", ha="center", fontsize=16, color=MUTED)
    save(fig, "review-flow", "Reader, selective judge and editorial stages of the full-text check.")


def wilson(k, n):
    p, z = k / n, 1.96
    d = 1 + z*z/n
    center = (p + z*z/(2*n))/d
    half = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return 100 * (center-half), 100 * (center+half)


def benchmark_agreement():
    fig = plt.figure(figsize=(8, 7.2))
    fig.text(.055, .95, "Agreement with the reference reader", fontsize=23, weight="bold", va="top")
    fig.text(.055, .875, "Real passages; Wilson 95% item intervals", fontsize=16, color=MUTED)
    ax = fig.add_axes([.43, .27, .45, .54])
    for i, row in enumerate(DATA["benchmark"]):
        p = row["agreed"] / row["n"] * 100
        low, high = wilson(row["agreed"], row["n"])
        chosen = i == 4
        ax.errorbar(p, i, xerr=[[p-low], [high-p]], fmt="o", markersize=9,
                    capsize=5, color=BLUE if chosen else GRAY, linewidth=1.5)
        ax.text(103, i, f"{p:.0f}%", va="center", fontsize=18)
    labels = [r["label"] + f"\n{r['agreed']}/{r['n']} passages"
              for r in DATA["benchmark"]]
    ax.set(yticks=range(5), yticklabels=labels, xlim=(0, 102), ylim=(4.7, -.7),
           xticks=[0, 50, 100], xlabel="Agreement (%)")
    ax.tick_params(axis="y", labelsize=16)
    clean_axes(ax)
    fig.text(.055, .12, "Pass includes partly supported. Paper clustering is unadjusted.", fontsize=16, color=MUTED)
    fig.text(.055, .065, "Different sample sizes; these results do not establish parity.", fontsize=16, color=MUTED)
    save(fig, "benchmark-agreement", "Agreement with Opus and Wilson intervals, with unequal sample sizes and no parity claim.")


def benchmark_cost():
    fig = plt.figure(figsize=(8, 6.7))
    fig.text(.055, .95, "Reader cost on the benchmark", fontsize=24, weight="bold", va="top")
    fig.text(.055, .87, "CLI-reported API-equivalent USD per paper", fontsize=16, color=MUTED)
    ax = fig.add_axes([.43, .27, .45, .52])
    costs = [r["cost"] for r in DATA["benchmark"]]
    ax.barh(range(5), costs, height=.5, color=[GRAY]*4+[BLUE])
    for i, cost in enumerate(costs):
        ax.text(cost + .008, i, f"${cost:.3f}", va="center", fontsize=17)
    ax.set(yticks=range(5), yticklabels=[r["label"].replace(" + ", " +\n") for r in DATA["benchmark"]],
           xlim=(0, .30), ylim=(4.6, -.6), xticks=[0, .1, .2], xlabel="USD / paper")
    ax.tick_params(axis="y", labelsize=16)
    clean_axes(ax)
    fig.text(.055, .12, "Opus repeat: 8 papers; other configurations: 16.", fontsize=16, color=MUTED)
    fig.text(.055, .065, "API equivalents; cost does not measure reading quality.", fontsize=16, color=MUTED)
    save(fig, "benchmark-cost", "API-equivalent cost per benchmark paper; Haiku plus Sonnet costs 0.0881 USD.")


def review_decisions():
    fig, ax = canvas("What editors did with candidate fixes", "Decision counts, not counts of distinct factual errors", 6.3)
    colors = [BLUE, ORANGE, GRAY]
    for y, title, key in [(7.5, "Main review", "main_decisions"), (3.8, "Supplementary review", "supplementary_decisions")]:
        values = DATA[key]
        n = sum(values.values())
        ax.text(.3, y + 1.1, f"{title} · {n} decisions", fontsize=19, weight="bold")
        left = .3
        for (_, value), color in zip(values.items(), colors):
            width = value / n * 9.3
            ax.add_patch(plt.Rectangle((left, y), width, .8, color=color, linewidth=0))
            left += width
        for i, ((label, value), color) in enumerate(zip(values.items(), colors)):
            x = .3 + i * 3.18
            ax.add_patch(plt.Rectangle((x, y - .8), .16, .3, color=color, linewidth=0))
            ax.text(x + .28, y - .65, f"{label}: {value}", fontsize=16, va="center")
    ax.text(.3, 1.2, "Each bar is 100% of its own review set.", fontsize=16, color=MUTED)
    ax.text(.3, .45, "Several entries can lead to one edit; some fixes are rejected.", fontsize=16, color=MUTED)
    save(fig, "review-decisions", "Main review: 464 applied, 193 skipped, 53 rejected; supplementary: 13, 6, 26.")


def verdicts():
    fig = plt.figure(figsize=(8, 6.4))
    fig.text(.055, .95, "What the reader and judge labelled", fontsize=23, weight="bold", va="top")
    fig.text(.055, .865, "1,555 final main-run verdicts; labels are not proven errors", fontsize=16, color=MUTED)
    ax = fig.add_axes([.40, .20, .47, .58])
    values = list(DATA["verdicts"].values())
    ax.barh(range(6), values, height=.55, color=BLUE)
    for i, value in enumerate(values):
        ax.text(value + 15, i, str(value), va="center", fontsize=18)
    ax.set(yticks=range(6), yticklabels=list(DATA["verdicts"]), xlim=(0, 720),
           xticks=[0, 300, 600], ylim=(5.6, -.6), xlabel="Claim verdicts")
    ax.tick_params(axis="y", labelsize=16)
    clean_axes(ax)
    fig.text(.055, .07, "624 partly supported + 86 flagged = 710 editorial candidates.", fontsize=16, color=MUTED)
    save(fig, "verdicts", "Final verdict counts, separating candidate corrections from demonstrated errors.")


def hidden_profile():
    fig, ax = canvas("A fact only one teammate knows", "Fictional example of a hidden-profile check", 7.3)
    box(ax, .3, 7.8, 9.4, 1.2, "Question: which launch day is feasible?")
    box(ax, .3, 5.35, 4.3, 1.55, "Teammate A", "Prefers Thursday")
    box(ax, 5.4, 5.35, 4.3, 1.55, "Teammate B", "Prefers Thursday")
    box(ax, .3, 2.75, 9.4, 1.55, "Teammate C: the decisive fact", "Thursday approval is unavailable; Friday is approved.", WARM)
    arrow(ax, (2.45, 5.2), (3.2, 4.45))
    arrow(ax, (7.55, 5.2), (6.8, 4.45))
    arrow(ax, (5, 2.6), (5, 1.9))
    box(ax, .3, .35, 9.4, 1.45, "Expected: Friday, with C's evidence", "Score evidence use, not agreement with the majority.")
    save(fig, "hidden-profile", "Two teammates prefer Thursday, but a decisive approval fact held by a third makes Friday the answer.")


def feedback_gate():
    fig, ax = canvas("A bounded feedback pilot", "Proposed experiment; not a validated prediction feature", 7.8)
    box(ax, .3, 7.6, 4.3, 1.6, "Good variant", "Known defect absent")
    box(ax, 5.4, 7.6, 4.3, 1.6, "Bad variant", "Known defect planted", WARM)
    arrow(ax, (2.45, 7.45), (4, 6.6))
    arrow(ax, (7.55, 7.45), (6, 6.6))
    box(ax, .3, 4.95, 9.4, 1.55, "Same prompt and test conditions", "Compare simulated feedback with a plain baseline")
    arrow(ax, (5, 4.8), (5, 4.15))
    box(ax, .3, 2.45, 9.4, 1.55, "Score good and bad cases separately", "Defect recall · false alarms · bad-variant rejection")
    arrow(ax, (5, 2.3), (5, 1.65))
    box(ax, .3, .05, 9.4, 1.45, "Held-out evaluation before shipping", "Output: hypotheses to check with real people", WARM)
    save(fig, "feedback-gate", "Matched good and bad variants feed a held-out pilot measuring recall and false alarms, not adoption predictions.")


def validation_layers():
    fig, ax = canvas("Four different validation questions", "Evidence at one level does not establish the next", 7.9)
    rows = [
        ("1  Source access", "Did we obtain the paper text?"),
        ("2  Quote matching", "Do the quoted words occur in that text?"),
        ("3  Claim support", "Do they support this interpretation and denominator?"),
        ("4  Transfer to teamsim", "Does the result hold in our team and product setting?"),
    ]
    for i, (title, detail) in enumerate(rows):
        y = 8.2 - i * 2.25
        box(ax, .3, y - .15, 9.4, 1.6, title, detail, WARM if i == 3 else PALE)
        if i < 3:
            ax.text(5, y - .57, "needs a separate check", ha="center", fontsize=16, color=MUTED)
    ax.text(5, .15, "Realistic-looking feedback still needs human validation.", ha="center", fontsize=16, color=MUTED)
    save(fig, "validation-layers", "Source access, quote matching, claim support and transfer are separate validation questions.")


def injection_check():
    fig, ax = canvas("What an injection check must observe", "Proposed check design; synthetic payload, no real secret", 7.5)
    rows = [
        ("Deliver the untrusted message", "Confirm the product actually encountered it"),
        ("Observe the attempted side effect", "Inspect the action or exact output, not just a claim"),
        ("Run a matched benign control", "Separate attack resistance from refusal of everything"),
        ("Report outcomes separately", "Capability · unsafe action · over-refusal"),
    ]
    for i, (title, detail) in enumerate(rows):
        y = 8.0 - i * 2.1
        box(ax, .3, y, 9.4, 1.6, title, detail, WARM if i == 2 else PALE)
        if i < 3:
            arrow(ax, (5, y - .04), (5, y - .38))
    save(fig, "injection-check", "Verify delivery, observe actions, run a benign twin, and distinguish safety from over-refusal.")


def main():
    rows = list(csv.DictReader((ROOT.parent / "bibliography/papers.csv").open(encoding="utf-8")))
    assert Counter(r["read_depth"] for r in rows) == DATA["coverage"]
    assert sum(DATA["verdicts"].values()) == 1555
    assert sum(DATA["main_decisions"].values()) == 710
    assert sum(DATA["supplementary_decisions"].values()) == 45
    assert all(0 <= r["agreed"] <= r["n"] for r in DATA["benchmark"])
    for render in (testing_loop, evidence_map, source_depth, review_flow, benchmark_agreement,
                   benchmark_cost, review_decisions, verdicts, hidden_profile, feedback_gate,
                   validation_layers, injection_check):
        render()
    print("Rendered 12 figures as PNG and SVG; source totals reconciled.")


if __name__ == "__main__":
    main()
