# Golden vectors

These files pin the canonical form byte for byte, so an implementation in any language can be
checked against them. Each file is ASCII JSON and is itself a canonical value: no
floating-point numbers, no null, keys matching `[a-z0-9_.:-]+`. Integers above 2^53 - 1 are
written as decimal strings.

## `canon_vectors.json`

`{"vectors": [...]}` with one vector per line. Fields of a vector:

- `name`: a unique label.
- `value`: the value to serialise.
- `canon_hex`: the expected canonical bytes, in hexadecimal.
- `sha256`: the expected hash, the lower-case hexadecimal SHA-256 of those bytes.
- `text` (some vectors): JSON source text, with escapes or whitespace that the canonical
  form does not keep, which a strict reader must read to `value`.

### How the expected bytes were made

The expected bytes were written by hand, not produced by the implementation under test.
Output that is plain ASCII was typed as a literal. Output with other characters was worked
out by hand from the code points to UTF-8 and typed as hexadecimal.

Two vectors come from RFC 8785 (JSON Canonicalization Scheme,
<https://www.rfc-editor.org/rfc/rfc8785>, read 2026-11-15):

- `rfc8785-3.2.2-string` is the `string` member of the sample in section 3.2.2. Its bytes
  are copied from the hexadecimal listing in section 3.2.4.
- `rfc8785-3.2.2-sample-without-null-and-numbers` is the same sample with `null` and the
  `numbers` member taken out, because this form allows neither null nor floating point. Its
  bytes are the section 3.2.4 listing with the same parts taken out by hand.

The sorting sample in section 3.2.3 of the RFC is not used: its keys are outside the key
rule, so the form rejects it.

Before the file was committed, the hand-written bytes were checked two ways:

1. For every vector, Python's `json.dumps(value, ensure_ascii=False, sort_keys=True,
   separators=(",", ":"))`, encoded as UTF-8, gave the same bytes. The test suite repeats
   this comparison on every run.
2. Every `sha256` was computed with Python's `hashlib` and confirmed with GNU coreutils
   `sha256sum` over the same bytes written to files.

`tests/test_canon.py` also holds its own hand-written literals for a subset of the vectors
and compares them with this file, so the file cannot be regenerated from the implementation
without a test failing.

Not verified: the vectors have been run on Windows only, with CPython 3.12 and 3.14.

## `draw_vectors.json`

One object with a list per function: `draw`, `below`, `chance`, `choice`, `weighted`,
`order` and `quantile`. Every row carries its `seed`, `scope` and `purpose` and the `result`.
Integers above 2^53 - 1 (the 64-bit draws and large `n`) are written as decimal strings.

- `draw` rows also give `preimage_hex`, the bytes `canon(["draw-v1", seed, scope, purpose])`,
  and `sha256` of them. The result is the first eight bytes of that digest read as a
  big-endian integer.
- `below` rows give `n` and `tries`, the number of attempts used. Rows with `tries` above 1
  show the rejection branch (`n = 2^63 + 1` rejects about half of all attempts).
- `order` rows include the same items in another input order and with items removed, which
  shows the relative order is unchanged, and one row of mixed integer and string ids.

### How the expected values were made

The preimages are plain ASCII, so `json.dumps(["draw-v1", seed, scope, purpose],
ensure_ascii=False, separators=(",", ":"))` gives the same bytes. Each `sha256` was
confirmed with GNU coreutils `sha256sum` for three rows, which `tests/test_draw.py` also
spells out byte for byte. `tests/test_draw.py` recomputes every row with its own short
reference (standard-library `json` and `hashlib`, written separately from `teamsim/draw.py`)
and compares it with both the file and the implementation.

Not verified: the vectors have been run on Windows only, with CPython 3.12 and 3.14. The
frequency test checks one case (`below(7)`); it does not prove uniformity.
