"""Matching a fact's form against text (engine spec section 6.2).

Both sides are normalised the same way: Unicode NFKC, then case-folded, then
every run of whitespace collapsed to one space and the ends stripped. A form
matches only on word boundaries: the character before a match and the
character after it must not be a word character when the form's own edge is
one. A word character is a letter, a digit or ``_`` (``str.isalnum``).

Stated limit: a correct answer worded outside the declared forms is not
matched. Nothing here reads a clock, a file or a random source.
"""

import unicodedata

__all__ = ["contains", "find", "normalise"]


def normalise(text: str) -> str:
    """NFKC, case-fold, collapse whitespace to single spaces, strip the ends."""
    if type(text) is not str:
        raise TypeError("text must be a string")
    folded = unicodedata.normalize("NFKC", text).casefold()
    # casefold can produce characters whose NFKC form differs (rare); settle it.
    folded = unicodedata.normalize("NFKC", folded)
    return " ".join(folded.split())


def _word(char: str) -> bool:
    return char.isalnum() or char == "_"


def find(text: str, form: str) -> int:
    """Return the index in ``normalise(text)`` of the first boundary match of
    ``form``, or -1. An empty form (after normalising) is an error."""
    hay = normalise(text)
    needle = normalise(form)
    if not needle:
        raise ValueError("a form must not be empty")
    check_left = _word(needle[0])
    check_right = _word(needle[-1])
    start = hay.find(needle)
    while start != -1:
        end = start + len(needle)
        left_ok = not check_left or start == 0 or not _word(hay[start - 1])
        right_ok = not check_right or end == len(hay) or not _word(hay[end])
        if left_ok and right_ok:
            return start
        start = hay.find(needle, start + 1)
    return -1


def contains(text: str, form: str) -> bool:
    """True when ``form`` appears in ``text`` on word boundaries, after both
    are normalised."""
    return find(text, form) != -1
