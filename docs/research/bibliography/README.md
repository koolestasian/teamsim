# Bibliography

Every paper cited in the research notes in this folder, as data.

| File | What it is |
|---|---|
| [papers.csv](papers.csv) | One row per paper: id, title, first three authors, year, venue, the notes that cite it, how much of it was read, a link, and an open-access PDF link where one exists. GitHub shows it as a table you can search. |
| [references.bib](references.bib) | The same papers as BibTeX, for a reference manager or LaTeX. |

455 papers: 413 from arXiv and 42 from journals. Checked on 2026-11-11: every arXiv ID and DOI
resolves to a real paper, and each title and author list comes from the paper's own arXiv page
or from Crossref or OpenAlex.

## Notes

- **No PDFs are stored in this repository.** Most arXiv authors keep the copyright and the
  licences generally do not allow redistribution, and the set is about 1 GB. Use the links in
  `papers.csv`.
- **Open-access PDFs.** 431 rows have an `open_access_pdf` link. Journal papers behind a
  paywall have none; the DOI link still works.
- **`cited_in`** lists the notes that cite the paper, starting with the one where it matters
  most. A note name such as `lit-personas` means `2026-11-lit-personas.md`.
- **Most 2025-2026 entries are preprints** that may not be peer reviewed. The notes say which
  venues were checked. The `venue` column is filled only for journal papers.
- **`read_depth`** says how much of the paper was checked against the notes (2026-11-12):
  `full text` (428), `partial text` (3: the available text stops early or is a study protocol
  without results) or `abstract only` (24 paywalled journal papers). How the full-text check
  was done and how far it can be trusted is in
  [../2026-11-lit-fulltext-check.md](../2026-11-lit-fulltext-check.md).
