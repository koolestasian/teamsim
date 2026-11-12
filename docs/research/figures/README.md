# Research figures

Twelve figures accompany the [visual guide](../2026-11-visual-guide.md), synthesis and
supporting notes. PNGs are embedded in Markdown for GitHub and mobile reading. Matching SVGs
retain editable text and vector marks. Captions and alternative text stay with each figure.

## Sources and meaning

- [data.json](data.json) holds the reviewed counts, benchmark numerators, denominators and
  costs, with relative source links. Coverage is checked against
  [papers.csv](../bibliography/papers.csv) on every render.
- Main and supplementary editorial decisions are separate populations. They count decisions
  about candidate fixes, not distinct edits or established source errors.
- Benchmark agreement uses real note passages and Opus as the reference. The Opus repeat
  covers 8 papers and 23 passages; other shown configurations cover 16 papers and 41 passages.
  Wilson 95% item intervals do not account for within-paper dependence. Pass includes
  `partly_supported`. Haiku means the v2 reader throughout.
- Costs are CLI-reported API-equivalent USD per benchmark paper, rounded to three decimals
  for display. They are not invoices or measurements of quality. Every benchmark paper has
  planted errors, so every paper reaches the judge stage in judged configurations.
- Evidence grades are the synthesis author's editorial judgments, not quantitative scores.
- The testing loop and feedback gate are conceptual proposals. The hidden-profile launch
  example is fictional; it is not a measured study result or a new fixture.
- Quote presence, factual support and transfer to a team setting remain separate questions.

## Regenerate

The prototype has no new dependency. Optional figure generation uses Matplotlib; generation
was checked with version 3.11.2. In a separate documentation environment:

```sh
python -m pip install matplotlib==3.11.2
python docs/research/figures/render.py
```

The renderer checks source totals and rejects text outside the image or overlapping text
labels before saving PNG and SVG. Normal and 390-pixel-wide raster previews were inspected;
the charts use direct labels as well as colour. These checks do not validate every source
claim or guarantee identical font metrics in every SVG viewer.

## Figure index

| Figure | Question | Vector version |
|---|---|---|
| [Testing loop](testing-loop.png) | What observes the product, and where does the answer key belong? | [SVG](testing-loop.svg) |
| [Evidence map](evidence-map.png) | Which findings are better supported, within which settings? | [SVG](evidence-map.svg) |
| [Source depth](source-depth.png) | How much of the 455-paper set had text available? | [SVG](source-depth.svg) |
| [Review flow](review-flow.png) | Where do reader, selective judge and editor enter? | [SVG](review-flow.svg) |
| [Benchmark agreement](benchmark-agreement.png) | What does reader-reference agreement show, with uncertainty? | [SVG](benchmark-agreement.svg) |
| [Benchmark cost](benchmark-cost.png) | What did the benchmark configurations cost? | [SVG](benchmark-cost.svg) |
| [Editorial decisions](review-decisions.png) | How were candidate fixes handled in each review set? | [SVG](review-decisions.svg) |
| [Verdict counts](verdicts.png) | Which labels made up the 1,555 main verdicts? | [SVG](verdicts.svg) |
| [Hidden profile](hidden-profile.png) | How can one member's fact determine an answer? | [SVG](hidden-profile.svg) |
| [Feedback pilot](feedback-gate.png) | How could good and bad variants test feedback usefulness? | [SVG](feedback-gate.svg) |
| [Validation layers](validation-layers.png) | Why does one successful check not establish the next? | [SVG](validation-layers.svg) |
| [Injection check](injection-check.png) | How do delivery, actions and benign controls change scoring? | [SVG](injection-check.svg) |
