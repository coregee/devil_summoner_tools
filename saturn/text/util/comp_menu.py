"""Compile the file-backed text used by the Saturn COMP core."""

from __future__ import annotations

from dataclasses import dataclass

from .assets import load_bound_translations
from .battle_ui import PointerBuild, compile_fixed_help
from .event_repack import FontMetrics, NORMALIZE_CHARACTERS
from .tokens import Text, parse_tokens


DEMON_COUNT = 319
DEMON_RECORD_BYTES = 8
DIRECT_DEMON_MAX_PIXELS = 64
COMP_DEMON_MAX_PIXELS = 80
NORMHELP_COUNT = 24
NORMHELP_WORDS = 42
NORMHELP_WIDTH = 300
NORMHELP_LINES = 2


@dataclass(frozen=True, slots=True)
class DemonNameBuild:
    data: bytes
    records: int
    direct_names: int
    overflow_names: int
    longest_name_bytes: int
    longest_name_pixels: int


def _normalize(value: str) -> str:
    for source, replacement in NORMALIZE_CHARACTERS.items():
        value = value.replace(source, replacement)
    return value


def compile_demon_names(stock: bytes, metrics: FontMetrics) -> DemonNameBuild:
    """Translate direct DVLNAME rows and retain overflow rows for the runtime."""
    expected_size = DEMON_COUNT * DEMON_RECORD_BYTES
    if len(stock) != expected_size:
        raise ValueError("DVLNAME inventory changed")
    ids = [f"game.dvlname.o{index * DEMON_RECORD_BYTES:06x}.text" for index in range(DEMON_COUNT)]
    translations = load_bound_translations(
        ("game.dvlname.",), required_ids=set(ids)
    )
    output = bytearray(stock)
    direct = 0
    overflow = 0
    longest_bytes = 0
    longest_pixels = 0
    for index, physical_id in enumerate(ids):
        text = _normalize(translations[physical_id])
        if not text or any(not isinstance(token, Text) for token in parse_tokens(text)):
            raise ValueError(f"{physical_id}: demon name must be nonempty literal text")
        glyphs = metrics.segment_output(text)
        encoded = bytes(glyph.code for glyph in glyphs)
        pixels = sum(glyph.advance for glyph in glyphs)
        if pixels > COMP_DEMON_MAX_PIXELS:
            raise ValueError(
                f"{physical_id}: demon name exceeds {COMP_DEMON_MAX_PIXELS}px "
                f"({pixels}px): {text!r}"
            )
        longest_bytes = max(longest_bytes, len(encoded))
        longest_pixels = max(longest_pixels, pixels)
        if len(encoded) <= DEMON_RECORD_BYTES and pixels <= DIRECT_DEMON_MAX_PIXELS:
            start = index * DEMON_RECORD_BYTES
            output[start:start + DEMON_RECORD_BYTES] = encoded.ljust(
                DEMON_RECORD_BYTES, b"\0"
            )
            direct += 1
        else:
            overflow += 1
    return DemonNameBuild(
        bytes(output),
        DEMON_COUNT,
        direct,
        overflow,
        longest_bytes,
        longest_pixels,
    )


def compile_normhelp(stock: bytes, metrics: FontMetrics) -> PointerBuild:
    return compile_fixed_help(
        stock,
        prefix="game.normhelp.",
        count=NORMHELP_COUNT,
        record_words=NORMHELP_WORDS,
        metrics=metrics,
        width=NORMHELP_WIDTH,
        max_lines=NORMHELP_LINES,
    )
