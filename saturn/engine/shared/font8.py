"""Shared FONT8 runtime tables used by Saturn surface composers."""

from __future__ import annotations

from text.util.event_repack import FontMetrics


def font8_tables(metrics: FontMetrics) -> tuple[bytes, dict[str, int]]:
    """Return the complete byte-code width table and unambiguous text map."""
    widths = bytearray(256)
    codes: dict[str, int] = {}
    for glyph in metrics.glyphs:
        if not 0 <= glyph.code < 256:
            raise ValueError("FONT8 code exceeds one byte")
        if not 0 <= glyph.advance < 256:
            raise ValueError("FONT8 advance exceeds one byte")
        widths[glyph.code] = glyph.advance
        for text in (glyph.text, *glyph.aliases):
            codes.setdefault(text, glyph.code)
    return bytes(widths), codes
