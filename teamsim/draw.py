"""Keyed draws: every random choice is a function of its own identity.

There is no random stream and no module state. ::

    draw(seed, scope, purpose) = big-endian integer of the first 8 bytes of
                                 SHA-256(canon(["draw-v1", seed, scope, purpose]))

``seed`` is a string. ``scope`` is an array of strings and integers naming who is
choosing (an actor id, an event id). ``purpose`` is an array of strings and
integers naming the choice. Because a draw depends on nothing else, adding,
removing or reordering other draws cannot change it.

Every helper is defined through ``draw`` alone and takes ``seed, scope,
purpose`` first. ``below`` appends ``"try", i`` to the purpose and ``order``
appends ``"order", item_id``; a caller's own purpose should not end that way.
``chance``, ``choice``, ``weighted`` and ``quantile`` are thin layers over
``below``, so two of them called with the same seed, scope and purpose share one
underlying draw. Give each choice its own purpose.

Arrays may be passed as a ``list`` or a ``tuple``. Every invalid argument raises
``ValueError``. The output is assumed, not proved, to be uniform: SHA-256 over
an injective encoding is treated as a random oracle, and a frequency test in the
test suite checks one case.

The bounded integer is plain rejection sampling on a 64-bit word (the rejection
method in D. Lemire, "Fast Random Integer Generation in an Interval", ACM
TOMACS 29(1), 2019, doi:10.1145/3230636), with the modulus form so that any
language with 64-bit unsigned integers reproduces it.
"""

from hashlib import sha256

from .canon import canon

__all__ = ["below", "chance", "choice", "draw", "order", "quantile", "weighted"]

_TAG = "draw-v1"
_WORD = 2**64


def _names(label: str, value: object) -> list:
    """Return ``value`` as a list after checking it holds only str and int."""
    if type(value) is not list and type(value) is not tuple:
        raise ValueError(
            f"{label} must be a list of strings and integers, "
            f"not {type(value).__name__}"
        )
    for index, element in enumerate(value):
        if type(element) is not str and type(element) is not int:
            raise ValueError(
                f"{label}[{index}] must be a string or an integer, "
                f"not {type(element).__name__}"
            )
    return list(value)


def _integer(label: str, value: object) -> int:
    if type(value) is not int:
        raise ValueError(f"{label} must be an integer, not {type(value).__name__}")
    return value


def _sequence(label: str, value: object) -> list | tuple:
    if type(value) is not list and type(value) is not tuple:
        raise ValueError(f"{label} must be a list, not {type(value).__name__}")
    if not value:
        raise ValueError(f"{label} must not be empty")
    return value


def draw(seed: str, scope: list | tuple, purpose: list | tuple) -> int:
    """Return the 64-bit unsigned integer keyed by ``(seed, scope, purpose)``."""
    if type(seed) is not str:
        raise ValueError(f"seed must be a string, not {type(seed).__name__}")
    preimage = canon([_TAG, seed, _names("scope", scope), _names("purpose", purpose)])
    return int.from_bytes(sha256(preimage).digest()[:8], "big")


def below(seed: str, scope: list | tuple, purpose: list | tuple, n: int) -> int:
    """Return an integer in ``[0, n)`` without bias, for ``1 <= n <= 2**64``.

    For attempt ``i = 0, 1, ...``: ``x = draw(seed, scope, purpose + ["try", i])``;
    the first ``x`` below ``2**64 - (2**64 mod n)`` is accepted and ``x mod n``
    returned. An attempt is rejected with probability below one half.
    """
    if _integer("n", n) < 1 or n > _WORD:
        raise ValueError(f"n must be in 1..2**64, got {n}")
    base = _names("purpose", purpose)
    limit = _WORD - _WORD % n
    attempt = 0
    while True:
        x = draw(seed, scope, [*base, "try", attempt])
        if x < limit:
            return x % n
        attempt += 1


def chance(
    seed: str, scope: list | tuple, purpose: list | tuple, num: int, den: int
) -> bool:
    """Return True with probability ``num / den``: ``below(den) < num``."""
    if _integer("den", den) < 1:
        raise ValueError(f"den must be at least 1, got {den}")
    if not 0 <= _integer("num", num) <= den:
        raise ValueError(f"num must be in 0..den, got {num} with den {den}")
    return below(seed, scope, purpose, den) < num


def choice(seed: str, scope: list | tuple, purpose: list | tuple, items: list | tuple):
    """Return ``items[below(len(items))]``."""
    items = _sequence("items", items)
    return items[below(seed, scope, purpose, len(items))]


def weighted(
    seed: str, scope: list | tuple, purpose: list | tuple, weights: list | tuple
) -> int:
    """Return an index chosen in proportion to the integer ``weights``.

    ``r = below(sum(weights))``; the result is the first index whose cumulative
    weight exceeds ``r``. An index of weight zero is never returned.
    """
    weights = _sequence("weights", weights)
    total = 0
    for index, weight in enumerate(weights):
        if _integer(f"weights[{index}]", weight) < 0:
            raise ValueError(f"weights[{index}] is negative: {weight}")
        total += weight
    if total == 0:
        raise ValueError("weights must not all be zero")
    remaining = below(seed, scope, purpose, total)
    for index, weight in enumerate(weights):
        if remaining < weight:
            return index
        remaining -= weight
    raise AssertionError("unreachable: below(total) is less than total")


def _tie_break(item_id: str | int) -> tuple[int, int, str]:
    """Total order on item ids: integers by value, then strings by code point."""
    if type(item_id) is int:
        return (0, item_id, "")
    return (1, 0, item_id)


def order(
    seed: str, scope: list | tuple, purpose: list | tuple, items: list | tuple
) -> list:
    """Return the item ids sorted by ``(draw(purpose + ["order", id]), id)``.

    ``items`` holds distinct ids, each a string or an integer. An item's sort key
    depends on no other item, so removing one leaves the relative order of the
    rest unchanged. Equal draws are broken by id: integers first, by value, then
    strings by Unicode code point.
    """
    ids = _names("items", items)
    seen = set()
    for index, item_id in enumerate(ids):
        if item_id in seen:
            raise ValueError(f"items[{index}] repeats the id {item_id!r}")
        seen.add(item_id)
    base = _names("purpose", purpose)
    return sorted(
        ids,
        key=lambda item_id: (
            draw(seed, scope, [*base, "order", item_id]),
            _tie_break(item_id),
        ),
    )


def quantile(
    seed: str, scope: list | tuple, purpose: list | tuple, table: list | tuple
) -> int:
    """Return ``table[below(len(table))]`` from an integer quantile table.

    A delay or a size is given as a table of equally likely integers, which is
    how a distribution is expressed without floating point.
    """
    table = _sequence("table", table)
    for index, entry in enumerate(table):
        _integer(f"table[{index}]", entry)
    return table[below(seed, scope, purpose, len(table))]
