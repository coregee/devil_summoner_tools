"""Shared packed-ASCII prose runtime for PSP Compendium surfaces.

The retail viewer stores three little-endian u16 strings per live profile in
BOOT.BIN and dispatches all three through the stock fixed-advance template
reader.  This feature keeps the original 319-row pointer/flag table and lore
arena, but redirects only the three proven viewer call sites to a byte reader
using the project's existing EVE ASCII atlas and width table.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from ..core.emitter import (
    A0,
    A1,
    A2,
    A3,
    RA,
    S0,
    S1,
    S2,
    S3,
    S4,
    S5,
    S6,
    S7,
    SP,
    T0,
    T1,
    T2,
    T3,
    ZERO,
    AssembledCode,
    PatchWrite,
    _Assembler,
    _jal_word,
    _load_pc_relative_target,
    _word_bytes,
)
from ..core.layout import (
    COMPENDIUM_DRAW_WRAPPER_ADDRESS,
    COMPENDIUM_DRAW_WRAPPER_END_ADDRESS,
    COMPENDIUM_NAME_TABLE_ADDRESS,
    DATA_LOAD_SEGMENT_ADDRESS,
    WIDTH_TABLE_ADDRESS,
)
from psp.text.util.event_packed import (
    ASCII_FIRST,
    ASCII_LAST,
    GLYPH_CODE_BIAS,
    STORED_PRINTABLE_FIRST,
)

PACKED_FIRST = STORED_PRINTABLE_FIRST
PACKED_RUNTIME_BIAS = GLYPH_CODE_BIAS
PACKED_WIDTH_COUNT = ASCII_LAST - ASCII_FIRST + 1

COMPENDIUM_ORIGIN_DRAW_CALL_ADDRESS = 0x0008A88C
COMPENDIUM_SUMMARY_DRAW_CALL_ADDRESS = 0x0008A8A4
COMPENDIUM_DETAIL_DRAW_CALL_ADDRESS = 0x0008A974
COMPENDIUM_DRAW_CALL_ADDRESSES = (
    COMPENDIUM_ORIGIN_DRAW_CALL_ADDRESS,
    COMPENDIUM_SUMMARY_DRAW_CALL_ADDRESS,
    COMPENDIUM_DETAIL_DRAW_CALL_ADDRESS,
)

COMPENDIUM_STOCK_GLYPH_DRAW_ADDRESS = 0x0009EEA8
COMPENDIUM_TEXT_ARENA_ADDRESS = 0x001A0AD8
# Translated prose stops where the separately checked full-name table begins.
# Source validation still hashes the complete retail arena through 0x1BEB36.
COMPENDIUM_TEXT_ARENA_END_ADDRESS = COMPENDIUM_NAME_TABLE_ADDRESS
COMPENDIUM_TEXT_ARENA_SIZE = (
    COMPENDIUM_TEXT_ARENA_END_ADDRESS - COMPENDIUM_TEXT_ARENA_ADDRESS
)
COMPENDIUM_SOURCE_TEXT_ARENA_END_ADDRESS = 0x001BEB36
COMPENDIUM_SOURCE_TEXT_ARENA_SIZE = (
    COMPENDIUM_SOURCE_TEXT_ARENA_END_ADDRESS - COMPENDIUM_TEXT_ARENA_ADDRESS
)
COMPENDIUM_TEXT_ARENA_RAW_ADDRESS = (
    COMPENDIUM_TEXT_ARENA_ADDRESS - DATA_LOAD_SEGMENT_ADDRESS
)

COMPENDIUM_POINTER_TABLE_ADDRESS = 0x001BEB4C
COMPENDIUM_POINTER_RECORD_COUNT = 319
COMPENDIUM_POINTER_RECORD_SIZE = 0x10
COMPENDIUM_POINTER_TABLE_SIZE = (
    COMPENDIUM_POINTER_RECORD_COUNT * COMPENDIUM_POINTER_RECORD_SIZE
)
COMPENDIUM_POINTER_TABLE_END_ADDRESS = (
    COMPENDIUM_POINTER_TABLE_ADDRESS + COMPENDIUM_POINTER_TABLE_SIZE
)
COMPENDIUM_LIVE_PROFILE_COUNT = 292

COMPENDIUM_TERMINATOR = 0x00
COMPENDIUM_NEWLINE = 0x01
COMPENDIUM_LINE_ADVANCE = 15


@dataclass(frozen=True)
class CompendiumPatchSource:
    """Fully materialized same-size lore arena and 319-row pointer table."""

    text_arena: bytes
    pointer_table: bytes


@dataclass(frozen=True)
class CompendiumPatch:
    """All isolated BOOT.BIN writes for translated Compendium prose."""

    draw_wrapper: AssembledCode
    text_arena: bytes
    pointer_table: bytes
    writes: tuple[PatchWrite, ...]

    def write(self, name: str) -> PatchWrite:
        try:
            return next(write for write in self.writes if write.name == name)
        except StopIteration as error:
            raise KeyError(f"unknown Allegrex Compendium write: {name}") from error


def _validate_source(source: CompendiumPatchSource) -> tuple[bytes, bytes]:
    if not isinstance(source, CompendiumPatchSource):
        raise TypeError("PSP Compendium source has the wrong type")
    if not isinstance(source.text_arena, bytes):
        raise TypeError("PSP Compendium text arena must be bytes")
    if len(source.text_arena) != COMPENDIUM_TEXT_ARENA_SIZE:
        raise ValueError(
            f"PSP Compendium text arena is {len(source.text_arena)} bytes; "
            f"expected {COMPENDIUM_TEXT_ARENA_SIZE}"
        )
    if not isinstance(source.pointer_table, bytes):
        raise TypeError("PSP Compendium pointer table must be bytes")
    if len(source.pointer_table) != COMPENDIUM_POINTER_TABLE_SIZE:
        raise ValueError(
            f"PSP Compendium pointer table is {len(source.pointer_table)} bytes; "
            f"expected {COMPENDIUM_POINTER_TABLE_SIZE}"
        )

    allowed = frozenset((COMPENDIUM_TERMINATOR, COMPENDIUM_NEWLINE)) | frozenset(
        range(PACKED_FIRST, PACKED_FIRST + PACKED_WIDTH_COUNT)
    )
    if any(value not in allowed for value in source.text_arena):
        raise ValueError("PSP Compendium text arena contains an unsupported byte")

    live_count = 0
    raw_limit = COMPENDIUM_TEXT_ARENA_RAW_ADDRESS + COMPENDIUM_TEXT_ARENA_SIZE
    for row_index in range(COMPENDIUM_POINTER_RECORD_COUNT):
        row_offset = row_index * COMPENDIUM_POINTER_RECORD_SIZE
        origin, summary, detail, _flags = struct.unpack_from(
            "<IIII", source.pointer_table, row_offset
        )
        pointers = (origin, summary, detail)
        if not any(pointers):
            continue
        if not all(pointers):
            raise ValueError(
                f"PSP Compendium row {row_index} has a partial pointer triple"
            )
        live_count += 1
        for field_index, pointer in enumerate(pointers):
            if not COMPENDIUM_TEXT_ARENA_RAW_ADDRESS <= pointer < raw_limit:
                raise ValueError(
                    f"PSP Compendium row {row_index} field {field_index} pointer "
                    f"{pointer:#x} is outside the lore arena"
                )
            arena_offset = pointer - COMPENDIUM_TEXT_ARENA_RAW_ADDRESS
            try:
                source.text_arena.index(COMPENDIUM_TERMINATOR, arena_offset)
            except ValueError as error:
                raise ValueError(
                    f"PSP Compendium row {row_index} field {field_index} "
                    "is not terminated"
                ) from error
    if live_count != COMPENDIUM_LIVE_PROFILE_COUNT:
        raise ValueError(
            f"PSP Compendium pointer table has {live_count} live profiles; "
            f"expected {COMPENDIUM_LIVE_PROFILE_COUNT}"
        )
    return source.text_arena, source.pointer_table


def _build_compendium_draw_wrapper() -> AssembledCode:
    code = _Assembler(COMPENDIUM_DRAW_WRAPPER_ADDRESS)
    code.addiu(SP, SP, -0x40)
    code.sw(RA, 0x3C, SP)
    code.sw(S0, 0x38, SP)
    code.sw(S1, 0x34, SP)
    code.sw(S2, 0x30, SP)
    code.sw(S3, 0x2C, SP)
    code.sw(S4, 0x28, SP)
    code.sw(S5, 0x24, SP)
    code.sw(S6, 0x20, SP)
    code.sw(S7, 0x1C, SP)

    code.addu(S0, A0, ZERO)
    code.addu(S1, A1, ZERO)
    code.addu(S2, A1, ZERO)
    code.addu(S3, A2, ZERO)
    code.addu(S4, A3, ZERO)
    code.addu(S5, T0, ZERO)

    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    _load_pc_relative_target(
        code,
        S6,
        RA,
        pc_address=pc_address,
        target_address=WIDTH_TABLE_ADDRESS,
    )
    _load_pc_relative_target(
        code,
        S7,
        RA,
        pc_address=pc_address,
        target_address=COMPENDIUM_STOCK_GLYPH_DRAW_ADDRESS,
    )

    code.label("loop")
    code.lbu(T0, 0, S0)
    code.beq(T0, ZERO, "return")
    code.delay_nop()
    code.addiu(S0, S0, 1)
    code.addiu(T1, ZERO, COMPENDIUM_NEWLINE)
    code.beq(T0, T1, "newline")
    code.delay_nop()

    code.addiu(T1, T0, -PACKED_FIRST)
    code.sltiu(T2, T1, PACKED_WIDTH_COUNT)
    code.beq(T2, ZERO, "return")
    code.delay_nop()
    code.addu(T2, S6, T1)
    code.lbu(T3, 0, T2)
    code.beq(T3, ZERO, "return")
    code.delay_nop()

    code.addu(A0, S1, ZERO)
    code.addu(A1, S3, ZERO)
    code.addiu(A2, T0, PACKED_RUNTIME_BIAS)
    code.addu(A3, S4, ZERO)
    code.addu(S1, S1, T3)
    code.addu(T0, S5, ZERO)
    code.addiu(T1, ZERO, 1)
    code.addu(T2, ZERO, ZERO)
    code.jalr(S7)
    code.delay_nop()
    code.beq(ZERO, ZERO, "loop")
    code.delay_nop()

    code.label("newline")
    code.addu(S1, S2, ZERO)
    code.addiu(S3, S3, COMPENDIUM_LINE_ADVANCE)
    code.beq(ZERO, ZERO, "loop")
    code.delay_nop()

    code.label("return")
    code.lw(S7, 0x1C, SP)
    code.lw(S6, 0x20, SP)
    code.lw(S5, 0x24, SP)
    code.lw(S4, 0x28, SP)
    code.lw(S3, 0x2C, SP)
    code.lw(S2, 0x30, SP)
    code.lw(S1, 0x34, SP)
    code.lw(S0, 0x38, SP)
    code.lw(RA, 0x3C, SP)
    code.addiu(SP, SP, 0x40)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def build_compendium_patch(source: CompendiumPatchSource) -> CompendiumPatch:
    """Build the viewer-local renderer plus same-size lore/table writes."""

    text_arena, pointer_table = _validate_source(source)
    draw_wrapper = _build_compendium_draw_wrapper()
    if draw_wrapper.end_address > COMPENDIUM_DRAW_WRAPPER_END_ADDRESS:
        raise ValueError("PSP Compendium draw wrapper exceeds its checked cave")

    writes = (
        PatchWrite(
            "compendium_draw_wrapper",
            COMPENDIUM_DRAW_WRAPPER_ADDRESS,
            draw_wrapper.data,
        ),
        *(
            PatchWrite(
                name,
                address,
                _word_bytes(_jal_word(address, COMPENDIUM_DRAW_WRAPPER_ADDRESS)),
            )
            for name, address in (
                ("compendium_origin_draw_call", COMPENDIUM_ORIGIN_DRAW_CALL_ADDRESS),
                (
                    "compendium_summary_draw_call",
                    COMPENDIUM_SUMMARY_DRAW_CALL_ADDRESS,
                ),
                ("compendium_detail_draw_call", COMPENDIUM_DETAIL_DRAW_CALL_ADDRESS),
            )
        ),
        PatchWrite(
            "compendium_text_arena",
            COMPENDIUM_TEXT_ARENA_ADDRESS,
            text_arena,
        ),
        PatchWrite(
            "compendium_pointer_table",
            COMPENDIUM_POINTER_TABLE_ADDRESS,
            pointer_table,
        ),
    )
    return CompendiumPatch(
        draw_wrapper=draw_wrapper,
        text_arena=text_arena,
        pointer_table=pointer_table,
        writes=writes,
    )


__all__ = (
    "COMPENDIUM_DETAIL_DRAW_CALL_ADDRESS",
    "COMPENDIUM_DRAW_CALL_ADDRESSES",
    "COMPENDIUM_DRAW_WRAPPER_ADDRESS",
    "COMPENDIUM_DRAW_WRAPPER_END_ADDRESS",
    "COMPENDIUM_LIVE_PROFILE_COUNT",
    "COMPENDIUM_NEWLINE",
    "COMPENDIUM_ORIGIN_DRAW_CALL_ADDRESS",
    "COMPENDIUM_POINTER_RECORD_COUNT",
    "COMPENDIUM_POINTER_RECORD_SIZE",
    "COMPENDIUM_POINTER_TABLE_ADDRESS",
    "COMPENDIUM_POINTER_TABLE_END_ADDRESS",
    "COMPENDIUM_POINTER_TABLE_SIZE",
    "COMPENDIUM_SOURCE_TEXT_ARENA_END_ADDRESS",
    "COMPENDIUM_SOURCE_TEXT_ARENA_SIZE",
    "COMPENDIUM_STOCK_GLYPH_DRAW_ADDRESS",
    "COMPENDIUM_SUMMARY_DRAW_CALL_ADDRESS",
    "COMPENDIUM_TERMINATOR",
    "COMPENDIUM_TEXT_ARENA_ADDRESS",
    "COMPENDIUM_TEXT_ARENA_END_ADDRESS",
    "COMPENDIUM_TEXT_ARENA_RAW_ADDRESS",
    "COMPENDIUM_TEXT_ARENA_SIZE",
    "CompendiumPatch",
    "CompendiumPatchSource",
    "build_compendium_patch",
)
