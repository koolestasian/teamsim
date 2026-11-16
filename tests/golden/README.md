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
