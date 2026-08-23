"""Source-owned packed-English authoring codec for PSP EVE dialogue.

This deliberately exposes only the printable-ASCII subset assigned by this
project, plus preserved raw logical words.  The traced runtime accepts a wider
range of otherwise unassigned one-byte glyph values; source authoring rejects
those values.  This module also does not rebuild pointer banks: packed messages
use byte cursors while their bank pointers remain measured in two-byte units,
so a separate packed-bank model must own padding and final-message discovery.
"""

from __future__ import annotations

from dataclasses import dataclass

ASCII_FIRST = 0x20
ASCII_LAST = 0x7E

STORED_CORE_FIRST = 0x1F
STORED_CORE_LAST = 0x6D
STORED_PUNCT_FIRST = 0x6E
STORED_PUNCT_LAST = 0x7C
STORED_SPACE = 0x7D
STORED_PRINTABLE_FIRST = STORED_CORE_FIRST
STORED_PRINTABLE_LAST = STORED_SPACE

GLYPH_CODE_BIAS = 0x1E01
GLYPH_CODE_FIRST = STORED_PRINTABLE_FIRST + GLYPH_CODE_BIAS
GLYPH_CODE_LAST = STORED_PRINTABLE_LAST + GLYPH_CODE_BIAS
MESSAGE_TERMINATOR = 0x8000

ASCII_NORMALIZATION = {
    "\u2019": "'",
    "\u2018": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2014": "-",
    "\u2013": "-",
    "\u2026": "...",
    "\u00e9": "e",
    "\u3000": " ",
    "\u00a0": " ",
}


def normalize_ascii(text: str) -> str:
    """Normalize prose shared by consumers of the packed-ASCII codec."""

    if not isinstance(text, str):
        raise TypeError("packed PSP text must be a string")
    for source, replacement in ASCII_NORMALIZATION.items():
        text = text.replace(source, replacement)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def validate_printable_ascii(
    value: object,
    context: str,
    *,
    maximum: int | None = None,
) -> str:
    """Validate prose that must remain in the shared printable-ASCII domain.

    This does not encode the value.  System ASCII fields and packed-EVE
    consumers can therefore share one authoring boundary without pretending
    that their binary representations are identical.
    """

    if not isinstance(value, str) or not value:
        raise ValueError(f"{context} must be nonempty text")
    if maximum is not None and len(value) > maximum:
        raise ValueError(f"{context} exceeds {maximum} characters")
    if any(not ASCII_FIRST <= ord(character) <= ASCII_LAST for character in value):
        raise ValueError(f"{context} must use printable ASCII")
    return value


def _validate_character(character: str) -> int:
    if not isinstance(character, str) or len(character) != 1:
        raise TypeError("packed PSP text expects one character")
    codepoint = ord(character)
    if not ASCII_FIRST <= codepoint <= ASCII_LAST:
        raise ValueError(
            f"packed PSP text only supports printable ASCII, got {character!r}"
        )
    return codepoint


def encode_ascii_character(character: str) -> int:
    """Return the one-byte PSP storage code for one printable ASCII glyph."""

    codepoint = _validate_character(character)
    if 0x30 <= codepoint <= ASCII_LAST:
        return codepoint - 0x11
    if 0x21 <= codepoint <= 0x2F:
        return codepoint + 0x4D
    return STORED_SPACE


def decode_ascii_byte(value: int) -> str:
    """Decode one valid packed glyph byte back to printable ASCII."""

    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("packed PSP glyph code must be an integer byte")
    if STORED_CORE_FIRST <= value <= STORED_CORE_LAST:
        return chr(value + 0x11)
    if STORED_PUNCT_FIRST <= value <= STORED_PUNCT_LAST:
        return chr(value - 0x4D)
    if value == STORED_SPACE:
        return " "
    raise ValueError(f"reserved packed PSP glyph byte: {value:#04x}")


def encode_ascii(text: str) -> bytes:
    """Encode printable ASCII without adding controls or padding."""

    if not isinstance(text, str):
        raise TypeError("packed PSP text must be a string")
    return bytes(encode_ascii_character(character) for character in text)


def decode_ascii(data: bytes) -> str:
    """Decode a glyph-only byte string; raw logical words are rejected."""

    if not isinstance(data, bytes):
        raise TypeError("packed PSP glyph data must be bytes")
    return "".join(decode_ascii_byte(value) for value in data)


def glyph_code_for_byte(value: int) -> int:
    """Return the member-5 tile index selected by one packed glyph byte."""

    decode_ascii_byte(value)
    return value + GLYPH_CODE_BIAS


def glyph_code_for_character(character: str) -> int:
    return glyph_code_for_byte(encode_ascii_character(character))


def encode_logical_word(value: int) -> bytes:
    """Encode a two-byte token that cannot collide with a packed glyph.

    The traced decoder treats a high byte below ``0x1f`` or exactly ``0x80``
    as a raw big-endian word prefix.  Other high bytes would be interpreted as
    single-byte glyphs and are rejected here.
    """

    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("packed PSP logical word must be an integer")
    if not 0 <= value <= 0xFFFF:
        raise ValueError("packed PSP logical words must be u16 integers")
    high = value >> 8
    if high >= STORED_PRINTABLE_FIRST and high != 0x80:
        raise ValueError(
            f"logical word {value:#06x} collides with the packed glyph grammar"
        )
    return value.to_bytes(2, "big")


@dataclass(frozen=True)
class PackedToken:
    runtime_code: int
    size: int
    character: str | None

    @property
    def is_glyph(self) -> bool:
        return self.character is not None


def decode_token(data: bytes, offset: int = 0) -> PackedToken:
    """Decode one token from the source-authorable subset of the grammar."""

    if not isinstance(data, bytes):
        raise TypeError("packed PSP token data must be bytes")
    if not isinstance(offset, int) or isinstance(offset, bool):
        raise TypeError("packed PSP token offset must be an integer")
    if not 0 <= offset < len(data):
        raise ValueError("packed PSP token offset is outside the data")
    first = data[offset]
    if first < STORED_PRINTABLE_FIRST or first == 0x80:
        if offset + 1 >= len(data):
            raise ValueError("packed PSP logical word is truncated")
        return PackedToken((first << 8) | data[offset + 1], 2, None)
    character = decode_ascii_byte(first)
    return PackedToken(first + GLYPH_CODE_BIAS, 1, character)
