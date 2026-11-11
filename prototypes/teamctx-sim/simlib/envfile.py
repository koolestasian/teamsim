"""Secrets: env-file loader, the Secret wrapper and the redaction code path.

Everything the harness prints, logs or writes to a report goes through `redact`.
Known secret values are registered with `REDACTOR.add`; shape-based patterns catch
values that were never registered (OpenRouter keys, teamctx API tokens, Authorization
headers, Discord-style bot tokens, control-token query strings).
"""

from __future__ import annotations

import re
from pathlib import Path

MASK = "***"


class Secret:
    """Holds a secret string. str/repr/format/pickle never show the value."""

    __slots__ = ("_value", "label")

    def __init__(self, value: str, label: str = "secret") -> None:
        object.__setattr__(self, "_value", value)
        object.__setattr__(self, "label", label)

    def reveal(self) -> str:
        return self._value

    def __setattr__(self, name, value):  # immutable
        raise AttributeError("Secret is immutable")

    def __repr__(self) -> str:
        return f"Secret({self.label}={MASK})"

    def __str__(self) -> str:
        return MASK

    def __format__(self, spec: str) -> str:
        return MASK

    def __bool__(self) -> bool:
        return bool(self._value)

    def __len__(self) -> int:
        return len(self._value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Secret) and other._value == self._value

    def __hash__(self) -> int:
        return hash(("Secret", self._value))

    def __reduce__(self):
        raise TypeError("Secret cannot be pickled")

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self


# Shape-based patterns. Order matters: Authorization headers first.
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Case-sensitive and single-space, so prose like "bot\nMessage Content" is left alone.
    (re.compile(r"\b(Bot|Bearer) [A-Za-z0-9._~+/=\-]{12,}"), r"\1 " + MASK),
    (re.compile(r"(?i)(x-baseline-control-token\W{0,4})[A-Za-z0-9_\-]{6,}"), r"\1" + MASK),
    (re.compile(r"(?i)([?&]token=)[^&\s\"']+"), r"\1" + MASK),
    (re.compile(r"(?m)^(\s*Token:\s+)\S+(\s+\(header X-Baseline-Control-Token\))"), r"\1" + MASK + r"\2"),
    (re.compile(r"sk-or-[A-Za-z0-9_\-]{6,}"), MASK),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"), MASK),
    (re.compile(r"\btctx_[A-Za-z0-9_\-]{6,}"), MASK),
    # Discord-style token: three dot-separated base64url-ish segments, the first
    # starting like a base64 snowflake.
    (re.compile(r"\b[MNO][A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{4,}\.[A-Za-z0-9_\-]{6,}\b"), MASK),
]


class Redactor:
    def __init__(self) -> None:
        self._literals: set[str] = set()

    def add(self, value: "Secret | str | None") -> None:
        text = value.reveal() if isinstance(value, Secret) else value
        if text and len(text) >= 6:
            self._literals.add(text)

    def clear(self) -> None:
        self._literals.clear()

    def __call__(self, text: str) -> str:
        if not isinstance(text, str):
            text = str(text)
        # Longest literals first so a literal that contains another is masked whole.
        for lit in sorted(self._literals, key=len, reverse=True):
            if lit in text:
                text = text.replace(lit, MASK)
        for pattern, repl in _PATTERNS:
            text = pattern.sub(repl, text)
        return text


REDACTOR = Redactor()


def redact(text: str) -> str:
    return REDACTOR(text)


def parse_env(text: str) -> dict[str, str]:
    """A tiny KEY=VALUE parser: comments, `export `, single or double quotes."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        if key:
            out[key] = value
    return out


def load_secret(path: Path, key: str) -> Secret | None:
    """Reads one key from an env file as a Secret (registered for redaction).

    Returns None when the file or key is missing or empty. The value is never printed.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return None
    value = parse_env(text).get(key, "")
    if not value:
        return None
    secret = Secret(value, key)
    REDACTOR.add(secret)
    return secret
