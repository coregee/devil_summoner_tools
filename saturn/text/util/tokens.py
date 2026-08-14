"""Readable tokens that preserve unresolved Saturn text values."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, TypeAlias

_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_RAW_RE = re.compile(r"(GLYPH|OP):([0-9a-fA-F]{2}|[0-9a-fA-F]{4})\Z")
_RESERVED_NAMES = frozenset({"GLYPH", "OP"})


def valid_name(value: str) -> bool:
    return bool(_NAME_RE.fullmatch(value)) and value not in _RESERVED_NAMES


@dataclass(frozen=True, slots=True)
class Text:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value:
            raise ValueError("text tokens must contain nonempty text")


@dataclass(frozen=True, slots=True)
class Named:
    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not valid_name(self.name):
            raise ValueError(f"invalid named token {self.name!r}")


@dataclass(frozen=True, slots=True)
class Raw:
    kind: Literal["GLYPH", "OP"]
    value: int
    width: int

    def __post_init__(self) -> None:
        if self.kind not in {"GLYPH", "OP"}:
            raise ValueError(f"invalid raw token kind {self.kind!r}")
        if (
            not isinstance(self.width, int)
            or isinstance(self.width, bool)
            or self.width not in {1, 2}
        ):
            raise ValueError("raw token width must be one or two bytes")
        limit = 1 << (self.width * 8)
        if (
            not isinstance(self.value, int)
            or isinstance(self.value, bool)
            or not 0 <= self.value < limit
        ):
            raise ValueError(f"raw token values must fit in {self.width} byte(s)")


Token: TypeAlias = Text | Named | Raw


def _append_text(tokens: list[Token], value: str) -> None:
    if not value:
        return
    if tokens and isinstance(tokens[-1], Text):
        tokens[-1] = Text(tokens[-1].value + value)
    else:
        tokens.append(Text(value))


def _parse_token(body: str) -> Token:
    if valid_name(body):
        return Named(body)

    match = _RAW_RE.fullmatch(body)
    if match is None:
        raise ValueError(f"invalid text token {{{body}}}")
    kind, rendered_value = match.groups()
    width = len(rendered_value) // 2
    return Raw(kind, int(rendered_value, 16), width)


def parse_tokens(value: str) -> tuple[Token, ...]:
    """Parse canonical tokens while treating doubled braces as literal text."""
    if not isinstance(value, str):
        raise TypeError("token input must be text")

    output: list[Token] = []
    literal: list[str] = []

    def flush_literal() -> None:
        _append_text(output, "".join(literal))
        literal.clear()

    position = 0
    while position < len(value):
        if value.startswith("{{", position):
            literal.append("{")
            position += 2
            continue
        if value.startswith("}}", position):
            literal.append("}")
            position += 2
            continue

        character = value[position]
        if character == "}":
            raise ValueError(f"unescaped closing brace at character {position}")
        if character != "{":
            literal.append(character)
            position += 1
            continue

        flush_literal()
        end = value.find("}", position + 1)
        if end < 0:
            raise ValueError(f"unclosed text token at character {position}")
        output.append(_parse_token(value[position + 1 : end]))
        position = end + 1

    flush_literal()
    return tuple(output)


def format_tokens(tokens: Iterable[Token]) -> str:
    """Render tokens using one canonical, JSON-friendly text representation."""
    output: list[str] = []
    for token in tokens:
        if isinstance(token, Text):
            output.append(token.value.replace("{", "{{").replace("}", "}}"))
        elif isinstance(token, Named):
            output.append(f"{{{token.name}}}")
        elif isinstance(token, Raw):
            digits = token.width * 2
            rendered = f"{token.kind}:{token.value:0{digits}x}"
            output.append(f"{{{rendered}}}")
        else:
            raise TypeError(f"unknown token type {type(token).__name__}")
    return "".join(output)
