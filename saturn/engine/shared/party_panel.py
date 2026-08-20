"""Shared compact-name data used by NORMCOM and MAZE party panels."""

from __future__ import annotations

import struct

from text.util.assets import load_bound_translations
from text.util.event_repack import FontMetrics


DEMON_COUNT = 319
CHARACTER_COUNT = 6
PANEL_MAX_PIXELS = 80
DIRECT_DEMON_BYTES = 8
DIRECT_DEMON_PIXELS = 64


def _encode_name(
    value: str,
    metrics: FontMetrics,
    context: str,
) -> tuple[bytes, int]:
    glyphs = metrics.segment(value)
    encoded = bytes(glyph.code for glyph in glyphs)
    pixels = sum(glyph.advance for glyph in glyphs)
    if pixels > PANEL_MAX_PIXELS:
        raise ValueError(
            f"{context} exceeds {PANEL_MAX_PIXELS}px ({pixels}px): {value!r}"
        )
    return encoded, pixels


def _pack_title_case_names(
    names: list[tuple[int, str]], *, record_count: int
) -> tuple[bytes, bytes]:
    bits = bytearray((record_count + 7) // 8)
    pool = bytearray()
    previous = -1
    for index, name in names:
        if not 0 <= index < record_count or index <= previous:
            raise ValueError("compact name indices must be ordered and unique")
        previous = index
        bits[index // 8] |= 1 << (index & 7)
        tokens: list[int] = []
        uppercase = True
        for character in name:
            if character.isalpha() and character.isascii():
                wanted_uppercase = character.isupper()
                if wanted_uppercase != uppercase:
                    tokens.append(30)
                tokens.append(ord(character.lower()) - ord("a") + 1)
                uppercase = False
            elif character == " ":
                tokens.append(27)
                uppercase = True
            elif character == "-":
                tokens.append(28)
                uppercase = True
            elif character == "'":
                tokens.append(29)
                uppercase = True
            elif character == "8":
                tokens.append(31)
                uppercase = False
            else:
                raise ValueError(
                    f"unsupported compact-name character {character!r} in {name!r}"
                )
        while len(tokens) % 3:
            tokens.append(0)
        for offset in range(0, len(tokens), 3):
            first, second, third = tokens[offset:offset + 3]
            pool.extend(
                struct.pack(
                    ">H",
                    (0x8000 if offset + 3 == len(tokens) else 0)
                    | (first << 10)
                    | (second << 5)
                    | third,
                )
            )
    return bytes(bits), bytes(pool)


def build_compact_party_panel_data(
    metrics: FontMetrics,
    built_names: bytes,
    *,
    context: str,
) -> dict[str, bytes]:
    """Build character rows and overflow-only compact demon-name pools."""
    character_ids = [
        f"game.charname.o{index * 8:06x}.text" for index in range(CHARACTER_COUNT)
    ]
    character_values = load_bound_translations(
        ("game.charname.",), required_ids=set(character_ids)
    )
    character_offsets = bytearray()
    character_pool = bytearray()
    for index, physical_id in enumerate(character_ids):
        encoded, _pixels = _encode_name(
            character_values[physical_id],
            metrics,
            f"{context} character name {index}",
        )
        character_offsets.extend(struct.pack(">H", len(character_pool)))
        character_pool.extend(encoded)
        character_pool.append(0)

    demon_ids = [
        f"game.dvlname.o{index * DIRECT_DEMON_BYTES:06x}.text"
        for index in range(DEMON_COUNT)
    ]
    demon_values = load_bound_translations(
        ("game.dvlname.",), required_ids=set(demon_ids)
    )
    if len(built_names) != DEMON_COUNT * DIRECT_DEMON_BYTES:
        raise ValueError("generated DVLNAME has the wrong size")
    overflow: list[tuple[int, str]] = []
    for index, physical_id in enumerate(demon_ids):
        text = demon_values[physical_id]
        encoded, pixels = _encode_name(
            text, metrics, f"{context} demon name {index}"
        )
        if len(encoded) <= DIRECT_DEMON_BYTES and pixels <= DIRECT_DEMON_PIXELS:
            start = index * DIRECT_DEMON_BYTES
            if built_names[start:start + DIRECT_DEMON_BYTES] != encoded.ljust(
                DIRECT_DEMON_BYTES, b"\0"
            ):
                raise ValueError(f"generated direct demon name {index} is stale")
        else:
            overflow.append((index, text))
    low_bits, low_pool = _pack_title_case_names(
        [(index, text) for index, text in overflow if index < 0x100],
        record_count=0x100,
    )
    high_bits, high_pool = _pack_title_case_names(
        [(index - 0x100, text) for index, text in overflow if index >= 0x100],
        record_count=DEMON_COUNT - 0x100,
    )
    return {
        "character_offsets": bytes(character_offsets),
        "character_pool": bytes(character_pool),
        "long_name_bits": low_bits + high_bits,
        "name_pool": low_pool,
        "high_name_pool": high_pool,
    }


__all__ = ["build_compact_party_panel_data"]
