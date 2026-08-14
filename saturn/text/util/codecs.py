"""Decode framed Saturn text records without knowing their source files."""

from __future__ import annotations

from collections.abc import Iterable

from .config import SourceEncoding
from .tokens import Named, Raw, Text, Token, format_tokens


def read_units(
    data: bytes | bytearray | memoryview,
    encoding: SourceEncoding,
) -> tuple[int, ...]:
    raw = bytes(data)
    if encoding.unit_width == 1:
        return tuple(raw)
    if len(raw) % 2:
        raise ValueError(
            f"{encoding.name}: big-endian 16-bit text has an odd byte length"
        )
    return tuple(
        int.from_bytes(raw[offset : offset + 2], "big")
        for offset in range(0, len(raw), 2)
    )


def _append(tokens: list[Token], token: Token) -> None:
    if isinstance(token, Text) and tokens and isinstance(tokens[-1], Text):
        tokens[-1] = Text(tokens[-1].value + token.value)
    else:
        tokens.append(token)


def _glyph_token(code: int, encoding: SourceEncoding) -> Token:
    value = encoding.glyphs.get(code)
    if value is None or value in encoding.ambiguous_glyphs:
        return Raw("GLYPH", code, encoding.unit_width)
    if len(value) == 1:
        return Text(value)
    if value.startswith("{") and value.endswith("}"):
        name = value[1:-1]
        if encoding.named_glyph_codes.get(name) == code:
            return Named(name)
    return Raw("GLYPH", code, encoding.unit_width)


def decode_units(
    units: Iterable[int], encoding: SourceEncoding
) -> tuple[Token, ...]:
    """Decode already-framed code units, preserving unknown values as raw tokens."""
    limit = 1 << (encoding.unit_width * 8)
    values = tuple(units)
    if any(
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 0 <= value < limit
        for value in values
    ):
        raise ValueError(f"{encoding.name}: code unit exceeds its codec width")

    output: list[Token] = []
    pending_separator = False
    for code in values:
        if code == 0 and encoding.zero != "glyph":
            if encoding.zero == "space":
                _append(output, Text(" "))
            elif encoding.zero.startswith("separator_"):
                pending_separator = bool(output)
            continue
        if pending_separator:
            separator = encoding.zero.removeprefix("separator_")
            _append(output, Text(" ") if separator == "space" else Named("n"))
            pending_separator = False
        if token := encoding.controls.get(code):
            _append(output, Named(token))
        elif encoding.is_control(code):
            _append(output, Raw("OP", code, encoding.unit_width))
        else:
            _append(output, _glyph_token(code, encoding))
    return tuple(output)


def decode(
    data: bytes | bytearray | memoryview, encoding: SourceEncoding
) -> tuple[Token, ...]:
    return decode_units(read_units(data, encoding), encoding)


def decode_text(data: bytes | bytearray | memoryview, encoding: SourceEncoding) -> str:
    return format_tokens(decode(data, encoding))
