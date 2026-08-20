"""Compact, reversible English rows for the Akuma Zensho text renderer."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Mapping, Sequence


MARKER_BIT = 0x8000
TERMINATOR = 0
SPACE = 27
UPPERCASE = 28
EXTENDED = 29
DICTIONARY_LOW = 30
DICTIONARY_HIGH = 31
DICTIONARY_SIZE = 64
DICTIONARY_ENTRY_MAX = 6
EXTENDED_CHARACTERS = "!',-.:;?0123456789"
ASCII_FIRST = 0x20
ASCII_LIMIT = 0x80
FONT8_GLYPH_BYTES = 8
PROFILE_TAIL_BYTES = 0x1DC
PROFILE_SUMMARY_LAYOUT_OFFSET = 0x1C
PROFILE_DETAIL_LAYOUT_OFFSET = 0x8C


def _character_codes(character: str) -> tuple[int, ...]:
    if "a" <= character <= "z":
        return (ord(character) - ord("a") + 1,)
    if character == " ":
        return (SPACE,)
    if "A" <= character <= "Z":
        return (UPPERCASE, ord(character) - ord("A") + 1)
    try:
        index = EXTENDED_CHARACTERS.index(character)
    except ValueError as error:
        raise ValueError(
            f"unsupported compendium translation character {character!r}"
        ) from error
    return (EXTENDED, index)


def _base_bits(value: str) -> int:
    return sum(5 * len(_character_codes(character)) for character in value)


def build_dictionary(values: Iterable[str]) -> tuple[str, ...]:
    """Derive the fixed-size codec dictionary without authored fragments."""
    counts: Counter[str] = Counter()
    for value in values:
        for length in range(3, DICTIONARY_ENTRY_MAX + 1):
            counts.update(
                value[position : position + length]
                for position in range(len(value) - length + 1)
            )

    def order(item: tuple[str, int]) -> tuple[int, int, int, str]:
        text, count = item
        saving = _base_bits(text) - 10
        return (-saving * count, -saving, -len(text), text)

    candidates = (
        text
        for text, _count in sorted(counts.items(), key=order)
        if _base_bits(text) > 10
    )
    result = tuple(list(candidates)[:DICTIONARY_SIZE])
    if len(result) != DICTIONARY_SIZE or len(set(result)) != len(result):
        raise ValueError("compendium corpus cannot supply a 64-entry dictionary")
    return result


@dataclass(frozen=True, slots=True)
class CompactCodec:
    dictionary: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            len(self.dictionary) != DICTIONARY_SIZE
            or len(set(self.dictionary)) != DICTIONARY_SIZE
            or any(
                not entry or len(entry) > DICTIONARY_ENTRY_MAX
                for entry in self.dictionary
            )
        ):
            raise ValueError("invalid compendium dictionary")
        for entry in self.dictionary:
            for character in entry:
                _character_codes(character)

    @lru_cache(maxsize=None)
    def codes(self, value: str) -> tuple[int, ...]:
        """Return the shortest deterministic tokenization of one visible row."""
        best: list[tuple[int, tuple[int, ...]] | None] = [None] * (len(value) + 1)
        best[len(value)] = (5, (TERMINATOR,))
        for position in range(len(value) - 1, -1, -1):
            character_codes = _character_codes(value[position])
            tail = best[position + 1]
            assert tail is not None
            chosen = (
                5 * len(character_codes) + tail[0],
                (*character_codes, *tail[1]),
            )
            for index, entry in enumerate(self.dictionary):
                if not value.startswith(entry, position):
                    continue
                dictionary_tail = best[position + len(entry)]
                assert dictionary_tail is not None
                bank = DICTIONARY_LOW if index < 32 else DICTIONARY_HIGH
                candidate = (
                    10 + dictionary_tail[0],
                    (bank, index & 31, *dictionary_tail[1]),
                )
                if candidate < chosen:
                    chosen = candidate
            best[position] = chosen
        result = best[0]
        assert result is not None
        return result[1]

    def required_bits(self, value: str) -> int:
        return 1 + 5 * len(self.codes(value))

    def encode_row(self, value: str, words: int) -> bytes:
        if type(words) is not int or words <= 0:
            raise ValueError("compendium row capacity must be positive")
        bits = [1]
        for code in self.codes(value):
            bits.extend((code >> shift) & 1 for shift in range(4, -1, -1))
        capacity = words * 16
        if len(bits) > capacity:
            raise ValueError(
                f"compendium row needs {len(bits)} bits but has {capacity}"
            )
        bits.extend([0] * (capacity - len(bits)))
        output = bytearray()
        for position in range(0, capacity, 16):
            word = 0
            for bit in bits[position : position + 16]:
                word = (word << 1) | bit
            output.extend(word.to_bytes(2, "big"))
        return bytes(output)

    def decode_row(self, data: bytes) -> str:
        if not data or len(data) % 2:
            raise ValueError("compact compendium row must contain whole words")
        bits = [
            (byte >> shift) & 1
            for byte in data
            for shift in range(7, -1, -1)
        ]
        if bits[0] != 1:
            raise ValueError("compact compendium row has no marker")
        position = 1

        def read5() -> int:
            nonlocal position
            if position + 5 > len(bits):
                raise ValueError("unterminated compact compendium row")
            value = 0
            for bit in bits[position : position + 5]:
                value = (value << 1) | bit
            position += 5
            return value

        output: list[str] = []
        while True:
            code = read5()
            if code == TERMINATOR:
                return "".join(output)
            if 1 <= code <= 26:
                output.append(chr(ord("a") + code - 1))
            elif code == SPACE:
                output.append(" ")
            elif code == UPPERCASE:
                letter = read5()
                if not 1 <= letter <= 26:
                    raise ValueError("invalid uppercase compendium token")
                output.append(chr(ord("A") + letter - 1))
            elif code == EXTENDED:
                index = read5()
                if index >= len(EXTENDED_CHARACTERS):
                    raise ValueError("invalid extended compendium token")
                output.append(EXTENDED_CHARACTERS[index])
            elif code in {DICTIONARY_LOW, DICTIONARY_HIGH}:
                index = read5() + (32 if code == DICTIONARY_HIGH else 0)
                output.append(self.dictionary[index])
            else:  # pragma: no cover - every five-bit value is classified above
                raise AssertionError(code)


@dataclass(frozen=True, slots=True)
class EmbeddedFont:
    """ASCII-indexed 8x8 rasters and proportional advances for the runtime."""

    bitmaps: bytes
    advances: bytes


def build_embedded_font(
    font_data: bytes,
    codes: Mapping[str, int],
    advances: Mapping[str, int],
) -> EmbeddedFont:
    """Select the generated game font without adding a compendium font file."""
    if len(font_data) % FONT8_GLYPH_BYTES:
        raise ValueError("FONT8.FON has a partial glyph")
    count = len(font_data) // FONT8_GLYPH_BYTES
    bitmaps = bytearray((ASCII_LIMIT - ASCII_FIRST) * FONT8_GLYPH_BYTES)
    widths = bytearray(ASCII_LIMIT - ASCII_FIRST)
    required = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz ") | set(
        EXTENDED_CHARACTERS
    )
    for character in sorted(required - {";"}):
        code = codes.get(character)
        width = advances.get(character)
        if code is None or not 0 <= code < count or width is None or width <= 0:
            raise ValueError(f"FONT8.FON cannot supply {character!r}")
        index = ord(character) - ASCII_FIRST
        start = code * FONT8_GLYPH_BYTES
        bitmaps[index * FONT8_GLYPH_BYTES : (index + 1) * FONT8_GLYPH_BYTES] = (
            font_data[start : start + FONT8_GLYPH_BYTES]
        )
        widths[index] = width

    # Galmuri7's game mapping has comma and colon but no semicolon. Their union
    # is the same one-column stem plus the comma descender needed here.
    semicolon = ord(";") - ASCII_FIRST
    comma = ord(",") - ASCII_FIRST
    colon = ord(":") - ASCII_FIRST
    for row in range(FONT8_GLYPH_BYTES):
        bitmaps[semicolon * FONT8_GLYPH_BYTES + row] = (
            bitmaps[comma * FONT8_GLYPH_BYTES + row]
            | bitmaps[colon * FONT8_GLYPH_BYTES + row]
        )
    widths[semicolon] = max(widths[comma], widths[colon])
    return EmbeddedFont(bytes(bitmaps), bytes(widths))


def wrap_rows(
    value: str,
    codec: CompactCodec,
    capacities: Sequence[int],
    advances: Mapping[str, int],
    pixel_limit: int,
) -> tuple[str, ...]:
    """Wrap at authored spaces while satisfying pixels and packed storage."""
    if not value or not capacities or pixel_limit <= 0:
        raise ValueError("compendium text and layout must be nonempty")
    try:
        character_widths = tuple(advances[character] for character in value)
    except KeyError as error:
        raise ValueError(
            f"unsupported compendium raster character {error.args[0]!r}"
        ) from error
    if any(width <= 0 for width in character_widths):
        raise ValueError("compendium glyph advances must be positive")

    words = value.split(" ")
    memo: dict[tuple[int, int], tuple[str, ...] | None] = {}

    def width(text: str) -> int:
        return sum(advances[character] for character in text)

    def solve(index: int, row: int) -> tuple[str, ...] | None:
        if index == len(words):
            return ()
        if row == len(capacities):
            return None
        key = (index, row)
        if key in memo:
            return memo[key]
        line = ""
        result = None
        for end in range(index, len(words)):
            line = words[end] if end == index else f"{line} {words[end]}"
            if (
                width(line) > pixel_limit
                or codec.required_bits(line) > capacities[row] * 16
            ):
                break
            tail = solve(end + 1, row + 1)
            if tail is not None:
                result = (line, *tail)
        memo[key] = result
        return result

    wrapped = solve(0, 0)
    if wrapped is None:
        raise ValueError(
            f"compendium text does not fit {len(capacities)} row(s): {value!r}"
        )
    return wrapped


def encode_text_rows(
    value: str,
    codec: CompactCodec,
    capacities: Sequence[int],
    advances: Mapping[str, int],
    pixel_limit: int,
) -> bytes:
    rows = wrap_rows(value, codec, capacities, advances, pixel_limit)
    output = bytearray()
    for index, words in enumerate(capacities):
        output.extend(codec.encode_row(rows[index] if index < len(rows) else "", words))
    return bytes(output)


def encode_profile_tail(
    origin: str,
    summary: str,
    detail: str,
    codec: CompactCodec,
    advances: Mapping[str, int],
) -> bytes:
    """Compile the three authored fields into the retail overlapping layout."""
    output = bytearray(PROFILE_TAIL_BYTES)
    origin_data = encode_text_rows(origin, codec, (9,), advances, 144)
    summary_data = encode_text_rows(summary, codec, (14,) * 4, advances, 224)
    detail_data = encode_text_rows(detail, codec, (14,) * 12, advances, 224)
    output[: len(origin_data)] = origin_data
    output[
        PROFILE_SUMMARY_LAYOUT_OFFSET : PROFILE_SUMMARY_LAYOUT_OFFSET
        + len(summary_data)
    ] = summary_data
    output[
        PROFILE_DETAIL_LAYOUT_OFFSET : PROFILE_DETAIL_LAYOUT_OFFSET
        + len(detail_data)
    ] = detail_data
    if len(output) != PROFILE_TAIL_BYTES:
        raise AssertionError("profile tail layout changed size")
    return bytes(output)


__all__ = [
    "CompactCodec",
    "DICTIONARY_SIZE",
    "EmbeddedFont",
    "EXTENDED_CHARACTERS",
    "MARKER_BIT",
    "build_dictionary",
    "build_embedded_font",
    "encode_text_rows",
    "encode_profile_tail",
    "wrap_rows",
]
