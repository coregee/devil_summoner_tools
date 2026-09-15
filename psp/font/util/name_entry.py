"""Publish native PSP NAME-grid ink geometry for runtime centering."""

from __future__ import annotations

from collections.abc import Iterable

TILE_STRIDE = 128
NAME_GRID_LOW_PUNCTUATION = {
    ":": 0x0006,
    "?": 0x0008,
    "!": 0x0009,
    " ": 0x0011,
    "-": 0x001D,
    "/": 0x001E,
    "'": 0x0026,
    "&": 0x0054,
    ",": 0x0003,
    ".": 0x0004,
}


def name_grid_glyph(character: str) -> int:
    """Return the native low KANJI glyph used by the NAME character grid."""

    code = ord(character)
    if character in NAME_GRID_LOW_PUNCTUATION:
        return NAME_GRID_LOW_PUNCTUATION[character]
    if 0x30 <= code <= 0x39 or 0x41 <= code <= 0x5A or 0x61 <= code <= 0x7A:
        return code + 0x9B
    raise ValueError(f"character has no PSP NAME grid glyph: {character!r}")


def build_name_grid_metrics(
    atlas: bytes,
    characters: Iterable[str],
) -> tuple[dict[str, int | str | list[int]], ...]:
    """Measure preserved native glyphs and derive centered draw offsets."""

    from .eve_ascii import _bounds, _decode_tile

    ordered = tuple(dict.fromkeys(characters))
    if any(
        not isinstance(character, str) or len(character) != 1 for character in ordered
    ):
        raise ValueError("PSP NAME grid metrics require single-character strings")
    rows = []
    for character in ordered:
        code = name_grid_glyph(character)
        start = code * TILE_STRIDE
        tile = atlas[start : start + TILE_STRIDE]
        if len(tile) != TILE_STRIDE:
            raise ValueError(f"PSP NAME grid glyph {code:#x} exceeds the EVE atlas")
        bounds = _bounds(_decode_tile(tile))
        if bounds is None:
            offset = 0
            serialized_bounds = [0, 0, 0, 0]
        else:
            left, top, right, bottom = bounds
            ink_width = right - left
            offset = (16 - ink_width) // 2 - left
            serialized_bounds = [left, top, right, bottom]
        if not 0 <= offset <= 15:
            raise ValueError(
                f"PSP NAME grid glyph {character!r} has invalid x offset {offset}"
            )
        rows.append(
            {
                "character": character,
                "code": code,
                "bounds": serialized_bounds,
                "x_offset": offset,
            }
        )
    return tuple(rows)


__all__ = (
    "NAME_GRID_LOW_PUNCTUATION",
    "build_name_grid_metrics",
    "name_grid_glyph",
)
