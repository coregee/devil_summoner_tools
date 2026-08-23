"""Shared full-name and sorting runtime for PSP Compendium surfaces.

The retail detail and list screens share a fixed eight-cell name drawer, while
the alphabetical sorter compares those same eight source bytes.  This feature
redirects only the two proven Compendium callers and replaces only the sorter's
comparison block.  Other users of the stock resolver retain their original
one-based ID and player-name behavior.
"""

from __future__ import annotations

from collections.abc import Iterable
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
    SP,
    T0,
    T1,
    T2,
    T3,
    T4,
    T5,
    T6,
    T7,
    T8,
    T9,
    V0,
    ZERO,
    AssembledCode,
    PatchWrite,
    _Assembler,
    _branch_word,
    _i_type,
    _jal_word,
    _load_pc_relative_target,
    _r_type,
    _word_bytes,
)
from ..core.layout import (
    COMPENDIUM_NAME_COMPARE_WRAPPER_ADDRESS,
    COMPENDIUM_NAME_COMPARE_WRAPPER_END_ADDRESS,
    COMPENDIUM_NAME_DRAW_WRAPPER_ADDRESS,
    COMPENDIUM_NAME_DRAW_WRAPPER_END_ADDRESS,
    COMPENDIUM_NAME_TABLE_ADDRESS,
    COMPENDIUM_NAME_TABLE_SIZE,
    WIDTH_TABLE_ADDRESS,
)
from psp.font.util.eve_ascii import PACKED_FIRST, PACKED_RUNTIME_BIAS, PACKED_WIDTH_COUNT

COMPENDIUM_NAME_DETAIL_CALL_ADDRESS = 0x0008A84C
COMPENDIUM_NAME_LIST_CALL_ADDRESS = 0x0008B744
COMPENDIUM_NAME_CALL_ADDRESSES = (
    COMPENDIUM_NAME_DETAIL_CALL_ADDRESS,
    COMPENDIUM_NAME_LIST_CALL_ADDRESS,
)

COMPENDIUM_NAME_SORT_BLOCK_ADDRESS = 0x00090D74
COMPENDIUM_NAME_SORT_BLOCK_END_ADDRESS = 0x00090D9C
COMPENDIUM_NAME_SORT_COMPARE_CALL_ADDRESS = 0x00090D84
COMPENDIUM_NAME_SORT_NO_SWAP_ADDRESS = 0x00090DF4
COMPENDIUM_NAME_SORT_SWAP_ADDRESS = 0x00090DC0

COMPENDIUM_NAME_STOCK_DRAW_ADDRESS = 0x0008A450
COMPENDIUM_NAME_STOCK_GLYPH_DRAW_ADDRESS = 0x0009EEA8
COMPENDIUM_NAME_RECORD_COUNT = 319
COMPENDIUM_NAME_OFFSET_TABLE_SIZE = COMPENDIUM_NAME_RECORD_COUNT * 2
COMPENDIUM_NAME_MAX_LENGTH = 16
COMPENDIUM_NAME_FIELD_WIDTH = 112
COMPENDIUM_NAME_PLAYER_ID_FIRST = 0x0100
COMPENDIUM_NAME_PLAYER_ID_LIMIT = 0x0106
COMPENDIUM_NAME_LAYER = 6


@dataclass(frozen=True)
class CompendiumNamePatchSource:
    """Checked packed DVLNAME table plus its live proportional advances."""

    dvlname_table: bytes
    packed_glyph_advances: Iterable[int]


@dataclass(frozen=True)
class CompendiumNamePatch:
    """Every isolated write for Compendium full names and name sorting."""

    draw_wrapper: AssembledCode
    compare_wrapper: AssembledCode
    dvlname_table: bytes
    writes: tuple[PatchWrite, ...]

    def write(self, name: str) -> PatchWrite:
        try:
            return next(write for write in self.writes if write.name == name)
        except StopIteration as error:
            raise KeyError(f"unknown Allegrex Compendium-name write: {name}") from error


def _validate_source(source: CompendiumNamePatchSource) -> tuple[bytes, bytes]:
    if not isinstance(source, CompendiumNamePatchSource):
        raise TypeError("PSP Compendium-name source has the wrong type")
    table = source.dvlname_table
    if not isinstance(table, bytes):
        raise TypeError("PSP Compendium DVLNAME table must be bytes")
    if len(table) != COMPENDIUM_NAME_TABLE_SIZE:
        raise ValueError(
            f"PSP Compendium DVLNAME table is {len(table)} bytes; "
            f"expected {COMPENDIUM_NAME_TABLE_SIZE}"
        )
    try:
        width_values = tuple(source.packed_glyph_advances)
    except TypeError as error:
        raise TypeError("PSP Compendium name widths must be iterable") from error
    if len(width_values) != PACKED_WIDTH_COUNT or any(
        not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 0xFF
        for value in width_values
    ):
        raise ValueError(
            f"PSP Compendium name widths must contain {PACKED_WIDTH_COUNT} u8 advances"
        )
    widths = bytes(width_values)

    pool = table[COMPENDIUM_NAME_OFFSET_TABLE_SIZE:]
    if not pool or pool[-1] != 0:
        raise ValueError("PSP Compendium DVLNAME pool is not terminated")
    if any(
        value != 0 and not PACKED_FIRST <= value < PACKED_FIRST + PACKED_WIDTH_COUNT
        for value in pool
    ):
        raise ValueError("PSP Compendium DVLNAME pool contains an unsupported byte")

    pool_starts: set[int] = set()
    cursor = COMPENDIUM_NAME_OFFSET_TABLE_SIZE
    while cursor < len(table):
        pool_starts.add(cursor)
        terminator = table.find(b"\0", cursor)
        if terminator < 0:
            raise ValueError("PSP Compendium DVLNAME pool has an unterminated row")
        cursor = terminator + 1

    offsets = tuple(
        int.from_bytes(table[index : index + 2], "little")
        for index in range(0, COMPENDIUM_NAME_OFFSET_TABLE_SIZE, 2)
    )
    if set(offsets) != pool_starts:
        raise ValueError("PSP Compendium DVLNAME offsets do not own the complete pool")
    for row_index, offset in enumerate(offsets):
        terminator = table.index(0, offset)
        encoded = table[offset:terminator]
        if not encoded or len(encoded) > COMPENDIUM_NAME_MAX_LENGTH:
            raise ValueError(
                f"PSP Compendium DVLNAME row {row_index} has invalid length"
            )
        width = sum(widths[value - PACKED_FIRST] for value in encoded)
        if width > COMPENDIUM_NAME_FIELD_WIDTH:
            raise ValueError(
                f"PSP Compendium DVLNAME row {row_index} is {width}px; "
                f"field width is {COMPENDIUM_NAME_FIELD_WIDTH}px"
            )
    return table, widths


def _build_name_draw_wrapper() -> AssembledCode:
    code = _Assembler(COMPENDIUM_NAME_DRAW_WRAPPER_ADDRESS)
    code.addiu(SP, SP, -0x30)
    code.sw(RA, 0x2C, SP)
    code.sw(S0, 0x28, SP)
    code.sw(S1, 0x24, SP)
    code.sw(S2, 0x20, SP)
    code.sw(S3, 0x1C, SP)
    code.sw(S4, 0x18, SP)
    code.sw(S5, 0x14, SP)
    code.sw(S6, 0x10, SP)
    code.andi(S0, A0, 0xFFFF)
    code.addu(S1, A1, ZERO)
    code.addu(S2, A2, ZERO)
    code.addu(S3, A3, ZERO)

    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    _load_pc_relative_target(
        code,
        S4,
        RA,
        pc_address=pc_address,
        target_address=COMPENDIUM_NAME_TABLE_ADDRESS,
    )
    _load_pc_relative_target(
        code,
        S5,
        RA,
        pc_address=pc_address,
        target_address=WIDTH_TABLE_ADDRESS,
    )
    _load_pc_relative_target(
        code,
        S6,
        RA,
        pc_address=pc_address,
        target_address=COMPENDIUM_NAME_STOCK_GLYPH_DRAW_ADDRESS,
    )

    # IDs 0x100..0x105 are the stock player/Mysterious Man namespace, not
    # physical DVLNAME rows 255..260.  Preserve that resolver path exactly.
    code.addiu(T0, S0, -COMPENDIUM_NAME_PLAYER_ID_FIRST)
    code.sltiu(
        T1,
        T0,
        COMPENDIUM_NAME_PLAYER_ID_LIMIT - COMPENDIUM_NAME_PLAYER_ID_FIRST,
    )
    code.bne(T1, ZERO, "fallback")
    code.delay_nop()
    code.addiu(T0, S0, -1)
    code.sltiu(T1, T0, COMPENDIUM_NAME_RECORD_COUNT)
    code.beq(T1, ZERO, "fallback")
    code.delay_nop()

    code.sll(T0, T0, 1)
    code.addu(T0, S4, T0)
    code.lhu(T0, 0, T0)
    code.addu(S4, S4, T0)

    code.label("render_loop")
    code.lbu(T0, 0, S4)
    code.beq(T0, ZERO, "return")
    code.delay_nop()
    code.addiu(T1, T0, -PACKED_FIRST)
    code.sltiu(T2, T1, PACKED_WIDTH_COUNT)
    code.beq(T2, ZERO, "return")
    code.delay_nop()
    code.addu(T2, S5, T1)
    code.lbu(T3, 0, T2)
    code.beq(T3, ZERO, "return")
    code.delay_nop()
    code.addu(A0, S1, ZERO)
    code.addu(A1, S2, ZERO)
    code.addiu(A2, T0, PACKED_RUNTIME_BIAS)
    code.addiu(A3, ZERO, COMPENDIUM_NAME_LAYER)
    code.addiu(S4, S4, 1)
    code.addu(S1, S1, T3)
    code.addu(T0, S3, ZERO)
    code.addiu(T1, ZERO, 1)
    code.addu(T2, ZERO, ZERO)
    code.jalr(S6)
    code.delay_nop()
    code.beq(ZERO, ZERO, "render_loop")
    code.delay_nop()

    code.label("fallback")
    _load_pc_relative_target(
        code,
        S4,
        RA,
        pc_address=pc_address,
        target_address=COMPENDIUM_NAME_STOCK_DRAW_ADDRESS,
    )
    code.addu(A0, S0, ZERO)
    code.addu(A1, S1, ZERO)
    code.addu(A2, S2, ZERO)
    code.addu(A3, S3, ZERO)
    code.jalr(S4)
    code.delay_nop()

    code.label("return")
    code.lw(S6, 0x10, SP)
    code.lw(S5, 0x14, SP)
    code.lw(S4, 0x18, SP)
    code.lw(S3, 0x1C, SP)
    code.lw(S2, 0x20, SP)
    code.lw(S1, 0x24, SP)
    code.lw(S0, 0x28, SP)
    code.lw(RA, 0x2C, SP)
    code.addiu(SP, SP, 0x30)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def _build_name_compare_wrapper() -> AssembledCode:
    """Return one when ``a1`` sorts before ``a0`` in case-folded ASCII."""

    code = _Assembler(COMPENDIUM_NAME_COMPARE_WRAPPER_ADDRESS)
    code.addu(T9, RA, ZERO)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    _load_pc_relative_target(
        code,
        T4,
        RA,
        pc_address=pc_address,
        target_address=COMPENDIUM_NAME_TABLE_ADDRESS,
    )

    for identifier in (A0, A1):
        code.addiu(T0, identifier, -1)
        code.sltiu(T1, T0, COMPENDIUM_NAME_RECORD_COUNT)
        code.beq(T1, ZERO, "return_zero")
        code.delay_nop()

    code.addiu(T0, A0, -1)
    code.sll(T0, T0, 1)
    code.addu(T0, T4, T0)
    code.lhu(T0, 0, T0)
    code.addu(A0, T4, T0)
    code.addiu(T0, A1, -1)
    code.sll(T0, T0, 1)
    code.addu(T0, T4, T0)
    code.lhu(T0, 0, T0)
    code.addu(A1, T4, T0)

    code.label("compare")
    code.lbu(T0, 0, A0)
    code.lbu(T1, 0, A1)
    code.bne(T0, T1, "different")
    code.delay_nop()
    code.beq(T0, ZERO, "return_zero")
    code.delay_nop()
    code.addiu(A0, A0, 1)
    code.addiu(A1, A1, 1)
    code.beq(ZERO, ZERO, "compare")
    code.delay_nop()

    code.label("different")
    code.beq(T0, ZERO, "return_zero")
    code.delay_nop()
    code.beq(T1, ZERO, "return_one")
    code.delay_nop()

    def normalize(
        source: int, output: int, work: int, condition: int, tag: str
    ) -> None:
        code.sltiu(condition, source, 0x6E)
        code.bne(condition, ZERO, f"{tag}_core")
        code.delay_nop()
        code.addiu(work, source, -0x7D)
        code.beq(work, ZERO, f"{tag}_space")
        code.delay_nop()
        code.addiu(output, source, -0x4D)
        code.beq(ZERO, ZERO, f"{tag}_fold")
        code.delay_nop()
        code.label(f"{tag}_core")
        code.addiu(output, source, 0x11)
        code.beq(ZERO, ZERO, f"{tag}_fold")
        code.delay_nop()
        code.label(f"{tag}_space")
        code.addiu(output, ZERO, 0x20)
        code.label(f"{tag}_fold")
        code.addiu(work, output, -0x41)
        code.sltiu(condition, work, 26)
        code.beq(condition, ZERO, f"{tag}_done")
        code.delay_nop()
        code.addiu(output, output, 0x20)
        code.label(f"{tag}_done")

    normalize(T0, T2, T5, T6, "left")
    normalize(T1, T3, T7, T8, "right")
    code.sltu(T0, T2, T3)
    code.sltu(V0, T3, T2)
    code.or_(T0, T0, V0)
    code.bne(T0, ZERO, "return")
    code.delay_nop()
    code.addiu(A0, A0, 1)
    code.addiu(A1, A1, 1)
    code.beq(ZERO, ZERO, "compare")
    code.delay_nop()

    code.label("return_one")
    code.addiu(V0, ZERO, 1)
    code.beq(ZERO, ZERO, "return")
    code.delay_nop()
    code.label("return_zero")
    code.addu(V0, ZERO, ZERO)
    code.label("return")
    code.jr(T9)
    code.delay_nop()
    return code.finish()


def _build_sort_comparison_block() -> bytes:
    """Replace one comparator block while preserving both sort swap payloads."""

    return _word_bytes(
        _i_type(0x25, S5, S3, 8),
        _i_type(0x25, S4, S2, 8),
        _r_type(S3, ZERO, A0, 0, 0x21),
        _r_type(S2, ZERO, A1, 0, 0x21),
        _jal_word(
            COMPENDIUM_NAME_SORT_COMPARE_CALL_ADDRESS,
            COMPENDIUM_NAME_COMPARE_WRAPPER_ADDRESS,
        ),
        0,
        _i_type(
            0x04,
            V0,
            ZERO,
            (
                COMPENDIUM_NAME_SORT_NO_SWAP_ADDRESS
                - (COMPENDIUM_NAME_SORT_COMPARE_CALL_ADDRESS + 0x0C)
            )
            // 4,
        ),
        0,
        _branch_word(
            COMPENDIUM_NAME_SORT_BLOCK_ADDRESS + 0x20,
            COMPENDIUM_NAME_SORT_SWAP_ADDRESS,
        ),
        0,
    )


def build_compendium_name_patch(
    source: CompendiumNamePatchSource,
) -> CompendiumNamePatch:
    """Build the two local readers, comparator, hooks, and exact name table."""

    table, _widths = _validate_source(source)
    draw_wrapper = _build_name_draw_wrapper()
    compare_wrapper = _build_name_compare_wrapper()
    if draw_wrapper.end_address > COMPENDIUM_NAME_DRAW_WRAPPER_END_ADDRESS:
        raise ValueError("PSP Compendium name drawer exceeds its checked cave")
    if compare_wrapper.end_address > COMPENDIUM_NAME_COMPARE_WRAPPER_END_ADDRESS:
        raise ValueError("PSP Compendium name comparator exceeds its checked cave")
    sort_block = _build_sort_comparison_block()
    if len(sort_block) != (
        COMPENDIUM_NAME_SORT_BLOCK_END_ADDRESS - COMPENDIUM_NAME_SORT_BLOCK_ADDRESS
    ):
        raise ValueError("PSP Compendium name-sort block size changed")

    writes = (
        PatchWrite(
            "compendium_name_draw_wrapper",
            COMPENDIUM_NAME_DRAW_WRAPPER_ADDRESS,
            draw_wrapper.data,
        ),
        PatchWrite(
            "compendium_name_compare_wrapper",
            COMPENDIUM_NAME_COMPARE_WRAPPER_ADDRESS,
            compare_wrapper.data,
        ),
        *(
            PatchWrite(
                name, address, _word_bytes(_jal_word(address, draw_wrapper.address))
            )
            for name, address in (
                ("compendium_name_detail_call", COMPENDIUM_NAME_DETAIL_CALL_ADDRESS),
                ("compendium_name_list_call", COMPENDIUM_NAME_LIST_CALL_ADDRESS),
            )
        ),
        PatchWrite(
            "compendium_name_sort_block",
            COMPENDIUM_NAME_SORT_BLOCK_ADDRESS,
            sort_block,
        ),
        PatchWrite("compendium_name_table", COMPENDIUM_NAME_TABLE_ADDRESS, table),
    )
    return CompendiumNamePatch(
        draw_wrapper=draw_wrapper,
        compare_wrapper=compare_wrapper,
        dvlname_table=table,
        writes=writes,
    )


__all__ = (
    "COMPENDIUM_NAME_CALL_ADDRESSES",
    "COMPENDIUM_NAME_COMPARE_WRAPPER_ADDRESS",
    "COMPENDIUM_NAME_COMPARE_WRAPPER_END_ADDRESS",
    "COMPENDIUM_NAME_DETAIL_CALL_ADDRESS",
    "COMPENDIUM_NAME_DRAW_WRAPPER_ADDRESS",
    "COMPENDIUM_NAME_DRAW_WRAPPER_END_ADDRESS",
    "COMPENDIUM_NAME_FIELD_WIDTH",
    "COMPENDIUM_NAME_LAYER",
    "COMPENDIUM_NAME_LIST_CALL_ADDRESS",
    "COMPENDIUM_NAME_MAX_LENGTH",
    "COMPENDIUM_NAME_OFFSET_TABLE_SIZE",
    "COMPENDIUM_NAME_PLAYER_ID_FIRST",
    "COMPENDIUM_NAME_PLAYER_ID_LIMIT",
    "COMPENDIUM_NAME_RECORD_COUNT",
    "COMPENDIUM_NAME_SORT_BLOCK_ADDRESS",
    "COMPENDIUM_NAME_SORT_BLOCK_END_ADDRESS",
    "COMPENDIUM_NAME_SORT_COMPARE_CALL_ADDRESS",
    "COMPENDIUM_NAME_SORT_NO_SWAP_ADDRESS",
    "COMPENDIUM_NAME_SORT_SWAP_ADDRESS",
    "COMPENDIUM_NAME_STOCK_DRAW_ADDRESS",
    "COMPENDIUM_NAME_STOCK_GLYPH_DRAW_ADDRESS",
    "COMPENDIUM_NAME_TABLE_ADDRESS",
    "COMPENDIUM_NAME_TABLE_SIZE",
    "CompendiumNamePatch",
    "CompendiumNamePatchSource",
    "build_compendium_name_patch",
)

