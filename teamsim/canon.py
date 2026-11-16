"""Canonical form and hash for every value in a pack or a run record.

A value is one of: a string, an integer, a boolean, an array or an object. There
are no floating-point numbers and there is no null.

- An integer lies in -(2**53 - 1) .. 2**53 - 1, so every JSON implementation
  reads it exactly.
- A string is in Unicode Normalization Form C and holds no surrogate code point.
  Nothing is normalised silently: a string that is not NFC is an error.
- An object key matches ``[a-z0-9_.:-]+`` (ASCII), so byte order, code point
  order and UTF-16 order all agree.
- Containers nest at most ``MAX_DEPTH`` deep.

``canon(value)`` is the UTF-8 encoding of JSON text with object keys sorted
ascending, no whitespace, integers in shortest decimal form, and strings escaped
only where JSON requires it: ``\\"``, ``\\\\``, ``\\b``, ``\\f``, ``\\n``,
``\\r``, ``\\t``, and ``\\u00xx`` in lower-case hexadecimal for the other
characters below U+0020. Every other character is written as it is. For these
values the output equals that of RFC 8785 (JSON Canonicalization Scheme,
https://www.rfc-editor.org/rfc/rfc8785, read 2026-11-15), whose number rules
reduce to plain decimal digits for integers in this range.

In Python the allowed types are exactly ``str``, ``int``, ``bool``, ``list`` and
``dict``. A ``bool`` is never an integer. Tuples, ``None``, ``float`` and
subclasses of the allowed types are rejected.

Known limit: whether a string is NFC is decided by the Unicode tables of the
running interpreter (``unicodedata.unidata_version``). Two interpreters can
disagree about a character that only the newer one has assigned. Not verified
beyond the characters in the golden vectors.
"""

import hashlib
import re
import unicodedata

__all__ = [
    "MAX_DEPTH",
    "MAX_INT",
    "MIN_INT",
    "CanonError",
    "canon",
    "check",
    "hash_of",
    "parse",
]

MAX_INT = 2**53 - 1
MIN_INT = -MAX_INT
MAX_DEPTH = 64

_KEY_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_.:-")
_KEY_RULE = "[a-z0-9_.:-]+"
_DIGITS = frozenset("0123456789")
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_MAX_INT_DIGITS = len(str(MAX_INT))
_WHITESPACE = " \t\n\r"

_SHORT_ESCAPES = {
    0x08: "\\b",
    0x09: "\\t",
    0x0A: "\\n",
    0x0C: "\\f",
    0x0D: "\\r",
    0x22: '\\"',
    0x5C: "\\\\",
}
_ESCAPES = {
    code: _SHORT_ESCAPES.get(code, f"\\u{code:04x}")
    for code in [*range(0x20), 0x22, 0x5C]
}
_UNESCAPES = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}
_PLAIN_RUN = re.compile(r'[^"\\\x00-\x1f]+')


class CanonError(ValueError):
    """A value, or JSON text, outside the canonical form.

    ``path`` locates the offending element from the root ``$``, for example
    ``$["actors"][2]["id"]``. ``reason`` says what is wrong with it.
    """

    def __init__(self, path: str, reason: str) -> None:
        super().__init__(path, reason)
        self.path = path
        self.reason = reason

    def __str__(self) -> str:
        return f"{self.path}: {self.reason}"


def canon(value: object) -> bytes:
    """Return the canonical bytes of ``value``, or raise ``CanonError``."""
    parts: list[str] = []
    _walk(value, [], 0, parts)
    return "".join(parts).encode("utf-8")


def hash_of(value: object) -> str:
    """Return the lower-case hexadecimal SHA-256 of ``canon(value)``."""
    return hashlib.sha256(canon(value)).hexdigest()


def check(value: object) -> None:
    """Raise ``CanonError`` unless ``value`` is allowed; build no output."""
    _walk(value, [], 0, None)


def parse(data: str | bytes) -> object:
    """Read JSON text strictly and return an allowed value.

    The text may use any JSON whitespace, key order and string escape. It is
    rejected, with ``CanonError``, if it holds a fraction or an exponent, null, a
    duplicate key, a string that is not NFC, a lone surrogate, a key outside the
    key rule, an integer out of range, a byte order mark, anything after the
    value, or anything that is not JSON. ``bytes`` must be UTF-8. ``-0`` reads as
    ``0``. Offsets in messages count characters, not bytes.

    ``parse(canon(v)) == v`` for every allowed ``v``.
    """
    if isinstance(data, bytes):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise CanonError("$", f"input is not UTF-8 (byte {error.start})") from None
    elif isinstance(data, str):
        text = data
    else:
        raise TypeError(f"parse() needs str or bytes, not {type(data).__name__}")
    if text.startswith("\ufeff"):
        raise CanonError("$", "a byte order mark is not allowed")
    start = _skip(text, 0)
    value, pos = _read_value(text, start, [], 0)
    pos = _skip(text, pos)
    if pos != len(text):
        raise _syntax([], pos, "trailing data after the value")
    return value


# --- validation and output -------------------------------------------------


def _show(path: list) -> str:
    return "$" + "".join(
        f"[{part}]" if type(part) is int else f'["{part}"]' for part in path
    )


def _check_string(value: str, path: list) -> None:
    if value.isascii():
        return
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        code = ord(value[error.start])
        raise CanonError(
            _show(path), f"lone surrogate U+{code:04X} at index {error.start}"
        ) from None
    if unicodedata.normalize("NFC", value) != value:
        raise CanonError(_show(path), "string is not in Unicode NFC")


def _check_key(key: object, path: list) -> None:
    if type(key) is not str:
        raise CanonError(
            _show(path), f"object key {key!r} is not a string ({type(key).__name__})"
        )
    if not key or not _KEY_CHARS.issuperset(key):
        raise CanonError(_show(path), f"object key {key!r} does not match {_KEY_RULE}")


def _check_integer(value: int, path: list) -> None:
    if not MIN_INT <= value <= MAX_INT:
        raise CanonError(
            _show(path), f"integer {value} is outside {MIN_INT}..{MAX_INT}"
        )


def _check_depth(depth: int, path: list) -> None:
    if depth >= MAX_DEPTH:
        raise CanonError(_show(path), f"nested deeper than {MAX_DEPTH} containers")


def _walk(value: object, path: list, depth: int, out: list[str] | None) -> None:
    """Validate ``value``; append its canonical text to ``out`` when given."""
    kind = type(value)
    if kind is str:
        _check_string(value, path)
        if out is not None:
            out.append('"' + value.translate(_ESCAPES) + '"')
    elif kind is bool:
        if out is not None:
            out.append("true" if value else "false")
    elif kind is int:
        _check_integer(value, path)
        if out is not None:
            out.append(str(value))
    elif kind is list:
        _check_depth(depth, path)
        if out is not None:
            out.append("[")
        for index, item in enumerate(value):
            if index and out is not None:
                out.append(",")
            path.append(index)
            _walk(item, path, depth + 1, out)
            path.pop()
        if out is not None:
            out.append("]")
    elif kind is dict:
        _check_depth(depth, path)
        for key in value:
            _check_key(key, path)
        if out is not None:
            out.append("{")
        for index, key in enumerate(sorted(value)):
            if out is not None:
                out.append(("," if index else "") + '"' + key + '":')
            path.append(key)
            _walk(value[key], path, depth + 1, out)
            path.pop()
        if out is not None:
            out.append("}")
    elif value is None:
        raise CanonError(_show(path), "null (None) is not allowed")
    elif kind is float:
        raise CanonError(_show(path), "floating-point numbers are not allowed")
    else:
        raise CanonError(_show(path), f"unsupported type {kind.__name__}")


# --- strict reader ---------------------------------------------------------


def _syntax(path: list, pos: int, reason: str) -> CanonError:
    return CanonError(_show(path), f"{reason} (at character {pos})")


def _skip(text: str, pos: int) -> int:
    end = len(text)
    while pos < end and text[pos] in _WHITESPACE:
        pos += 1
    return pos


def _read_value(text: str, pos: int, path: list, depth: int) -> tuple[object, int]:
    if pos >= len(text):
        raise _syntax(path, pos, "unexpected end of input")
    char = text[pos]
    if char == '"':
        value, pos = _read_string(text, pos, path)
        _check_string(value, path)
        return value, pos
    if char == "{":
        return _read_object(text, pos, path, depth)
    if char == "[":
        return _read_array(text, pos, path, depth)
    if char == "-" or char in _DIGITS:
        return _read_integer(text, pos, path)
    if text.startswith("true", pos):
        return True, pos + 4
    if text.startswith("false", pos):
        return False, pos + 5
    if text.startswith("null", pos):
        raise _syntax(path, pos, "null is not allowed")
    raise _syntax(path, pos, f"unexpected character {char!r}")


def _read_integer(text: str, pos: int, path: list) -> tuple[int, int]:
    start = pos
    end = len(text)
    if text[pos] == "-":
        pos += 1
    first = pos
    if pos >= end or text[pos] not in _DIGITS:
        raise _syntax(path, pos, "a digit must follow the minus sign")
    if text[pos] == "0":
        pos += 1
        if pos < end and text[pos] in _DIGITS:
            raise _syntax(path, pos, "leading zeros are not allowed")
    else:
        while pos < end and text[pos] in _DIGITS:
            pos += 1
    if pos < end and text[pos] == ".":
        raise _syntax(
            path, pos, "fraction part: floating-point numbers are not allowed"
        )
    if pos < end and text[pos] in "eE":
        raise _syntax(path, pos, "exponent: floating-point numbers are not allowed")
    if pos - first > _MAX_INT_DIGITS:
        raise _syntax(path, start, f"integer is outside {MIN_INT}..{MAX_INT}")
    value = int(text[start:pos])
    if not MIN_INT <= value <= MAX_INT:
        raise _syntax(path, start, f"integer {value} is outside {MIN_INT}..{MAX_INT}")
    return value, pos


def _read_hex4(text: str, pos: int, path: list) -> int:
    digits = text[pos : pos + 4]
    if len(digits) != 4 or not _HEX_DIGITS.issuperset(digits):
        raise _syntax(path, pos, "\\u must be followed by four hexadecimal digits")
    return int(digits, 16)


def _read_string(text: str, pos: int, path: list) -> tuple[str, int]:
    """Read the string whose opening quote is at ``pos``; decode its escapes."""
    start = pos
    pos += 1
    end = len(text)
    parts: list[str] = []
    while True:
        run = _PLAIN_RUN.match(text, pos)
        if run is not None:
            parts.append(run.group())
            pos = run.end()
        if pos >= end:
            raise _syntax(path, start, "string is not closed")
        char = text[pos]
        if char == '"':
            return "".join(parts), pos + 1
        if char != "\\":
            raise _syntax(
                path, pos, f"control character U+{ord(char):04X} must be escaped"
            )
        escape = text[pos + 1 : pos + 2]
        if escape in _UNESCAPES:
            parts.append(_UNESCAPES[escape])
            pos += 2
        elif escape == "u":
            code = _read_hex4(text, pos + 2, path)
            if 0xD800 <= code <= 0xDBFF and text.startswith("\\u", pos + 6):
                low = _read_hex4(text, pos + 8, path)
                if 0xDC00 <= low <= 0xDFFF:
                    code = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)
                    pos += 6
            if 0xD800 <= code <= 0xDFFF:
                raise _syntax(path, pos, f"lone surrogate \\u{code:04x}")
            parts.append(chr(code))
            pos += 6
        else:
            raise _syntax(path, pos, f"invalid escape \\{escape}")


def _read_array(text: str, pos: int, path: list, depth: int) -> tuple[list, int]:
    _check_depth(depth, path)
    items: list = []
    pos = _skip(text, pos + 1)
    if text.startswith("]", pos):
        return items, pos + 1
    while True:
        path.append(len(items))
        item, pos = _read_value(text, _skip(text, pos), path, depth + 1)
        path.pop()
        items.append(item)
        pos = _skip(text, pos)
        if text.startswith(",", pos):
            pos += 1
        elif text.startswith("]", pos):
            return items, pos + 1
        else:
            raise _syntax(path, pos, "expected ',' or ']' in array")


def _read_object(text: str, pos: int, path: list, depth: int) -> tuple[dict, int]:
    _check_depth(depth, path)
    members: dict = {}
    pos = _skip(text, pos + 1)
    if text.startswith("}", pos):
        return members, pos + 1
    while True:
        pos = _skip(text, pos)
        if not text.startswith('"', pos):
            raise _syntax(path, pos, "expected a string key")
        key_pos = pos
        key, pos = _read_string(text, pos, path)
        if not key or not _KEY_CHARS.issuperset(key):
            raise _syntax(
                path, key_pos, f"object key {key!r} does not match {_KEY_RULE}"
            )
        path.append(key)
        if key in members:
            raise _syntax(path, key_pos, "duplicate key")
        pos = _skip(text, pos)
        if not text.startswith(":", pos):
            raise _syntax(path, pos, "expected ':' after the key")
        value, pos = _read_value(text, _skip(text, pos + 1), path, depth + 1)
        path.pop()
        members[key] = value
        pos = _skip(text, pos)
        if text.startswith(",", pos):
            pos += 1
        elif text.startswith("}", pos):
            return members, pos + 1
        else:
            raise _syntax(path, pos, "expected ',' or '}' in object")
