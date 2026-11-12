# Research illustrations

The [picture guide](../2026-11-visual-guide.md) shows five fictional examples. They illustrate
expected behaviour, not executed tests. The feedback example is a proposal to evaluate.

PNG files are embedded in the notes; matching SVGs retain editable text and vector shapes.
The coverage chart uses the bibliography: 428 full texts, 3 partial/protocol-only texts and
24 abstracts. The renderer checks these counts against [papers.csv](../bibliography/papers.csv).

## Rebuild

Optional documentation dependency: Matplotlib 3.11.2. The prototype has no new dependency.

```sh
python -m pip install matplotlib==3.11.2
python docs/research/figures/render.py
```

Six images are generated in PNG and SVG. The renderer checks source counts and text bounds.
