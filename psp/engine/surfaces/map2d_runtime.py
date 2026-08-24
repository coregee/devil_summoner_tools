"""Allegrex emitters for the PSP two-dimensional city-map surface."""

from __future__ import annotations

import struct
from collections.abc import Iterable, Mapping
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
    T4,
    T5,
    T6,
    T7,
    T8,
    T9,
    ZERO,
    AssembledCode,
    PatchWrite,
    _Assembler,
    _jal_word,
    _load_pc_relative_target,
    _word_bytes,
)
from ..core.layout import (
    DATA_LOAD_SEGMENT_ADDRESS,
    ITEM_EVENT_INSERT_WRAPPER_ADDRESS,
    MAP2D_DYNAMIC_DRAW_WRAPPER_ADDRESS,
    MAP2D_FIXED_ROW_TABLE_ADDRESS,
    MAP2D_TOP_DRAW_WRAPPER_ADDRESS,
    MAP2D_TOP_ROW_TABLE_ADDRESS,
    MAP2D_WIDTH_TABLE_ADDRESS,
    NAME_FIELD_MAX,
    NAME_PROFILE_ADDRESS,
    NAME_PROFILE_FIELD_OFFSETS,
    SAVEDATA_DETAIL_WRAPPER_ADDRESS,
)
from psp.text.util.event_packed import (
    ASCII_FIRST,
    ASCII_LAST,
    STORED_PRINTABLE_FIRST,
    encode_ascii_character,
)

PACKED_FIRST = STORED_PRINTABLE_FIRST
PACKED_WIDTH_COUNT = ASCII_LAST - ASCII_FIRST + 1


def _packed_storage_index(character: str) -> int:
    return encode_ascii_character(character) - PACKED_FIRST

MAP2D_PRINTABLE_GLYPH_FIRST = 0x1DA0


MAP2D_PRINTABLE_GLYPH_LAST = 0x1DFE


MAP2D_SCRATCH_WARD_CODES = (0x1D80, 0x1D81, 0x1D82, 0x1D83)


MAP2D_SCRATCH_CITY_CODES = (0x1D84, 0x1D85, 0x1D86, 0x1D87)


MAP2D_STOCK_TEXT_DRAW_ADDRESS = 0x0009F7B0


MAP2D_STOCK_GLYPH_DRAW_ADDRESS = 0x0009EEA8


MAP2D_FONT_POINTER_RAW_ADDRESS = 0x003F6DF0


MAP2D_FONT_POINTER_ADDRESS = DATA_LOAD_SEGMENT_ADDRESS + MAP2D_FONT_POINTER_RAW_ADDRESS


MAP2D_VIEW_STATE_RAW_ADDRESS = 0x004098F0


MAP2D_VIEW_STATE_ADDRESS = DATA_LOAD_SEGMENT_ADDRESS + MAP2D_VIEW_STATE_RAW_ADDRESS


MAP2D_NAME_FIELD_WIDTH = 64


MAP2D_SCALED_NAME_Y_OFFSET = 2


MAP2D_HEADER_X = 0x54


MAP2D_MARKER_CENTER_X = 0x170


MAP2D_DYNAMIC_DRAW_CALL_SITES = (
    ("map2d_city_header_draw_call", 0x000A377C, "city_header"),
    ("map2d_ward_header_draw_call", 0x000A3804, "ward_header"),
    ("map2d_ward_marker_draw_call", 0x000A4300, "ward_marker"),
    ("map2d_city_overview_draw_call", 0x000A44B8, "city_overview"),
)


MAP2D_TOP_DRAW_CALL_SITES = (
    ("map2d_top_prompt_draw_call", 0x000A2B58, "talk_prompt"),
    ("map2d_top_yes_normal_draw_call", 0x000A2B7C, "label_yes"),
    ("map2d_top_no_draw_call", 0x000A2B98, "label_no"),
    ("map2d_top_yes_selected_draw_call", 0x000A2C00, "label_yes"),
)


@dataclass(frozen=True)
class Map2dRuntimePatch:
    """MAP2D-only dynamic-name and top prompt rendering hooks."""

    dynamic_draw_wrapper: AssembledCode
    top_draw_wrapper: AssembledCode
    width_table: bytes
    top_row_table: bytes
    fixed_row_table: bytes
    writes: tuple[PatchWrite, ...]

    def write(self, name: str) -> PatchWrite:
        try:
            return next(write for write in self.writes if write.name == name)
        except StopIteration as error:
            raise KeyError(f"unknown Allegrex MAP2D write: {name}") from error


def _build_map2d_dynamic_draw_wrapper() -> AssembledCode:
    """Draw chosen city/ward tags without the stock suffix/stack builders.

    Compact NAME profile bytes are the durable source.  Natural names use the
    dedicated Ark16 EVE cells and proportional advances directly.  Names over
    the native 64-pixel tag width are resampled into four writable atlas cells,
    matching Saturn's bounded four-cell output contract.
    """

    code = _Assembler(MAP2D_DYNAMIC_DRAW_WRAPPER_ADDRESS)
    code.addiu(SP, SP, -0x60)
    code.sw(RA, 0x5C, SP)
    code.sw(S0, 0x58, SP)
    code.sw(S1, 0x54, SP)
    code.sw(S2, 0x50, SP)
    code.sw(S3, 0x4C, SP)
    code.sw(S4, 0x48, SP)
    code.sw(S5, 0x44, SP)
    code.sw(S6, 0x40, SP)
    code.sw(S7, 0x3C, SP)
    code.sw(A0, 0x38, SP)
    code.sw(A3, 0x34, SP)
    code.addu(S0, RA, ZERO)
    code.addu(S4, A1, ZERO)
    code.addu(S5, A2, ZERO)
    code.addu(S6, T0, ZERO)

    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    code.addu(T8, RA, ZERO)
    _load_pc_relative_target(
        code,
        S1,
        T8,
        pc_address=pc_address,
        target_address=NAME_PROFILE_ADDRESS,
    )
    _load_pc_relative_target(
        code,
        S2,
        T8,
        pc_address=pc_address,
        target_address=MAP2D_WIDTH_TABLE_ADDRESS,
    )
    _load_pc_relative_target(
        code,
        T0,
        T8,
        pc_address=pc_address,
        target_address=MAP2D_FONT_POINTER_ADDRESS,
    )
    code.lw(S3, 0, T0)
    _load_pc_relative_target(
        code,
        S7,
        T8,
        pc_address=pc_address,
        target_address=MAP2D_STOCK_GLYPH_DRAW_ADDRESS,
    )

    # Match Saturn's contextual tags: the district header suppresses its first
    # city draw and moves the ward into that slot; the separate moving overview
    # footer keeps only the chosen city.  A4300 shares one return address for
    # dynamic and fixed markers, so it must resolve the current entry ID from
    # the caller's preserved s2/s3 rather than dispatching by RA alone.
    _load_pc_relative_target(
        code,
        T0,
        T8,
        pc_address=pc_address,
        target_address=0x000A377C + 8,
    )
    code.bne(S0, T0, "ward_header_context")
    code.delay_nop()
    code.beq(ZERO, ZERO, "return")
    code.delay_nop()

    code.label("ward_header_context")
    _load_pc_relative_target(
        code,
        T0,
        T8,
        pc_address=pc_address,
        target_address=0x000A3804 + 8,
    )
    code.bne(S0, T0, "ward_marker_context")
    code.delay_nop()
    _load_pc_relative_target(
        code,
        T0,
        T8,
        pc_address=pc_address,
        target_address=MAP2D_VIEW_STATE_ADDRESS,
    )
    code.lw(T0, 0, T0)
    code.bne(T0, ZERO, "fixed_header")
    code.delay_nop()
    code.addiu(S1, S1, NAME_PROFILE_FIELD_OFFSETS["ward"])
    code.addiu(S4, ZERO, MAP2D_HEADER_X)
    code.addiu(T0, ZERO, MAP2D_SCRATCH_WARD_CODES[0])
    code.sw(T0, 0x30, SP)
    code.sw(ZERO, 0x2C, SP)
    code.beq(ZERO, ZERO, "measure")
    code.delay_nop()

    code.label("fixed_header")
    code.sw(T0, 0x10, SP)
    code.addiu(S4, ZERO, MAP2D_HEADER_X)
    code.beq(ZERO, ZERO, "fixed_row")
    code.delay_nop()

    code.label("ward_marker_context")
    _load_pc_relative_target(
        code,
        T0,
        T8,
        pc_address=pc_address,
        target_address=0x000A4300 + 8,
    )
    code.bne(S0, T0, "city_overview_context")
    code.delay_nop()
    code.lw(T0, 0x4C, SP)  # caller s3, incremented by A4304's delay slot
    code.addiu(T0, T0, -1)
    code.sll(T0, T0, 2)
    code.lw(T1, 0x50, SP)  # caller s2, MAP2D state base
    code.addu(T0, T0, T1)
    code.lw(T0, 0x4B0, T0)
    code.bne(T0, ZERO, "fixed_marker")
    code.delay_nop()
    code.addiu(S1, S1, NAME_PROFILE_FIELD_OFFSETS["ward"])
    code.addiu(T0, ZERO, MAP2D_SCRATCH_WARD_CODES[0])
    code.sw(T0, 0x30, SP)
    code.addiu(T0, ZERO, 1)
    code.sw(T0, 0x2C, SP)
    code.beq(ZERO, ZERO, "measure")
    code.delay_nop()

    code.label("fixed_marker")
    code.sw(T0, 0x10, SP)
    code.addiu(S4, ZERO, MAP2D_MARKER_CENTER_X - MAP2D_NAME_FIELD_WIDTH // 2)
    code.beq(ZERO, ZERO, "fixed_row")
    code.delay_nop()

    code.label("city_overview_context")
    _load_pc_relative_target(
        code,
        T0,
        T8,
        pc_address=pc_address,
        target_address=0x000A44B8 + 8,
    )
    code.bne(S0, T0, "fallback")
    code.delay_nop()
    code.addiu(S1, S1, NAME_PROFILE_FIELD_OFFSETS["city"])
    code.addiu(S4, ZERO, MAP2D_HEADER_X)
    code.addiu(T0, ZERO, MAP2D_SCRATCH_CITY_CODES[0])
    code.sw(T0, 0x30, SP)
    code.sw(ZERO, 0x2C, SP)
    code.beq(ZERO, ZERO, "measure")
    code.delay_nop()

    code.label("fixed_row")
    code.lw(T0, 0x10, SP)
    code.addiu(T0, T0, -1)
    code.sltiu(T1, T0, 5)
    code.beq(T1, ZERO, "return")
    code.delay_nop()
    code.sll(T0, T0, 3)
    _load_pc_relative_target(
        code,
        S1,
        T8,
        pc_address=pc_address,
        target_address=MAP2D_FIXED_ROW_TABLE_ADDRESS,
    )
    code.addu(S1, S1, T0)
    code.sw(ZERO, 0x20, SP)

    code.label("draw_fixed_cell")
    code.lw(T0, 0x20, SP)
    code.sltiu(T1, T0, 4)
    code.beq(T1, ZERO, "return")
    code.delay_nop()
    code.sll(T1, T0, 1)
    code.addu(T1, S1, T1)
    code.lhu(A2, 0, T1)
    code.addu(A0, S4, ZERO)
    code.addu(A1, S5, ZERO)
    code.addiu(A3, ZERO, 9)
    code.addu(T0, S6, ZERO)
    code.addiu(T1, ZERO, 1)
    code.addu(T2, ZERO, ZERO)
    code.jalr(S7)
    code.delay_nop()
    code.addiu(S4, S4, 16)
    code.lw(T0, 0x20, SP)
    code.addiu(T0, T0, 1)
    code.sw(T0, 0x20, SP)
    code.beq(ZERO, ZERO, "draw_fixed_cell")
    code.delay_nop()

    code.label("measure")
    code.addu(T0, ZERO, ZERO)  # measured width
    code.addu(T1, ZERO, ZERO)  # byte count
    code.label("measure_byte")
    code.sltiu(T2, T1, NAME_FIELD_MAX)
    code.beq(T2, ZERO, "measure_done")
    code.delay_nop()
    code.addu(T2, S1, T1)
    code.lbu(T2, 0, T2)
    code.addiu(T3, T2, -PACKED_FIRST)
    code.sltiu(T4, T3, PACKED_WIDTH_COUNT)
    code.beq(T4, ZERO, "measure_done")
    code.delay_nop()
    code.addu(T4, S2, T3)
    code.lbu(T4, 0, T4)
    code.addu(T0, T0, T4)
    code.addiu(T1, T1, 1)
    code.beq(ZERO, ZERO, "measure_byte")
    code.delay_nop()

    code.label("measure_done")
    code.sw(T0, 0x28, SP)
    code.sw(T1, 0x24, SP)
    code.beq(T0, ZERO, "return")
    code.delay_nop()
    code.lw(T2, 0x2C, SP)
    code.beq(T2, ZERO, "choose_path")
    code.delay_nop()
    code.sltiu(T2, T0, MAP2D_NAME_FIELD_WIDTH + 1)
    code.beq(T2, ZERO, "center_scaled")
    code.delay_nop()
    code.srl(T0, T0, 1)
    code.addiu(S4, ZERO, MAP2D_MARKER_CENTER_X)
    code.subu(S4, S4, T0)
    code.beq(ZERO, ZERO, "choose_path")
    code.delay_nop()

    code.label("center_scaled")
    code.addiu(S4, ZERO, MAP2D_MARKER_CENTER_X - MAP2D_NAME_FIELD_WIDTH // 2)

    code.label("choose_path")
    code.lw(T0, 0x28, SP)
    code.sltiu(T0, T0, MAP2D_NAME_FIELD_WIDTH + 1)
    code.beq(T0, ZERO, "scale_clear")
    code.delay_nop()
    code.sw(ZERO, 0x20, SP)

    code.label("direct_glyph")
    code.lw(T0, 0x20, SP)
    code.lw(T1, 0x24, SP)
    code.sltu(T2, T0, T1)
    code.beq(T2, ZERO, "return")
    code.delay_nop()
    code.addu(T1, S1, T0)
    code.lbu(T1, 0, T1)
    code.addiu(T1, T1, -PACKED_FIRST)
    code.addiu(A2, T1, MAP2D_PRINTABLE_GLYPH_FIRST)
    code.addu(A0, S4, ZERO)
    code.addu(A1, S5, ZERO)
    code.addiu(A3, ZERO, 9)
    code.addu(T0, S6, ZERO)
    code.addiu(T1, ZERO, 1)
    code.addu(T2, ZERO, ZERO)
    code.jalr(S7)
    code.delay_nop()
    code.lw(T0, 0x20, SP)
    code.addu(T1, S1, T0)
    code.lbu(T1, 0, T1)
    code.addiu(T1, T1, -PACKED_FIRST)
    code.addu(T1, S2, T1)
    code.lbu(T1, 0, T1)
    code.addu(S4, S4, T1)
    code.addiu(T0, T0, 1)
    code.sw(T0, 0x20, SP)
    code.beq(ZERO, ZERO, "direct_glyph")
    code.delay_nop()

    # Clear four 16x16/4-bpp scratch cells before nearest-neighbour horizontal
    # resampling.  Source and destination use high-nibble-first pixels.
    code.label("scale_clear")
    code.lw(T0, 0x30, SP)
    code.sll(T0, T0, 7)
    code.addu(T0, T0, S3)
    code.addiu(T1, ZERO, 0x80)
    code.label("clear_word")
    code.sw(ZERO, 0, T0)
    code.addiu(T0, T0, 4)
    code.addiu(T1, T1, -1)
    code.bne(T1, ZERO, "clear_word")
    code.delay_nop()
    code.sw(ZERO, 0x1C, SP)

    code.label("scale_row")
    code.sw(ZERO, 0x18, SP)
    code.label("scale_pixel")
    code.lw(T6, 0x28, SP)
    code.lw(T7, 0x18, SP)
    code.mult(T7, T6)
    code.mflo(T0)
    code.srl(T0, T0, 6)
    code.addu(T1, ZERO, ZERO)

    code.label("find_source_glyph")
    code.addu(T2, S1, T1)
    code.lbu(T2, 0, T2)
    code.addiu(T2, T2, -PACKED_FIRST)
    code.addu(T3, S2, T2)
    code.lbu(T3, 0, T3)
    code.sltu(T4, T0, T3)
    code.bne(T4, ZERO, "source_glyph_found")
    code.delay_nop()
    code.subu(T0, T0, T3)
    code.addiu(T1, T1, 1)
    code.beq(ZERO, ZERO, "find_source_glyph")
    code.delay_nop()

    code.label("source_glyph_found")
    code.addiu(T3, T2, MAP2D_PRINTABLE_GLYPH_FIRST)
    code.sll(T3, T3, 7)
    code.addu(T3, T3, S3)
    code.lw(T4, 0x1C, SP)
    code.sll(T4, T4, 3)
    code.addu(T3, T3, T4)
    code.srl(T4, T0, 1)
    code.addu(T3, T3, T4)
    code.lbu(T3, 0, T3)
    code.andi(T4, T0, 1)
    code.bne(T4, ZERO, "source_low_nibble")
    code.delay_nop()
    code.srl(T3, T3, 4)
    code.beq(ZERO, ZERO, "source_pixel_ready")
    code.delay_nop()
    code.label("source_low_nibble")
    code.andi(T3, T3, 0x0F)

    code.label("source_pixel_ready")
    code.lw(T4, 0x30, SP)
    code.sll(T4, T4, 7)
    code.addu(T4, T4, S3)
    code.lw(T6, 0x18, SP)
    code.srl(T5, T6, 4)
    code.sll(T5, T5, 7)
    code.addu(T4, T4, T5)
    code.lw(T5, 0x1C, SP)
    code.sll(T5, T5, 3)
    code.addu(T4, T4, T5)
    code.andi(T5, T6, 0x0F)
    code.srl(T5, T5, 1)
    code.addu(T4, T4, T5)
    code.lbu(T5, 0, T4)
    code.andi(T7, T6, 1)
    code.bne(T7, ZERO, "destination_low_nibble")
    code.delay_nop()
    code.andi(T5, T5, 0x0F)
    code.sll(T3, T3, 4)
    code.or_(T5, T5, T3)
    code.beq(ZERO, ZERO, "store_scaled_pixel")
    code.delay_nop()
    code.label("destination_low_nibble")
    code.andi(T5, T5, 0xF0)
    code.or_(T5, T5, T3)
    code.label("store_scaled_pixel")
    code.sb(T5, 0, T4)
    code.addiu(T6, T6, 1)
    code.sw(T6, 0x18, SP)
    code.sltiu(T7, T6, MAP2D_NAME_FIELD_WIDTH)
    code.bne(T7, ZERO, "scale_pixel")
    code.delay_nop()
    code.lw(T6, 0x1C, SP)
    code.addiu(T6, T6, 1)
    code.sw(T6, 0x1C, SP)
    code.sltiu(T7, T6, 16)
    code.bne(T7, ZERO, "scale_row")
    code.delay_nop()
    code.sw(ZERO, 0x20, SP)

    code.label("draw_scratch")
    code.lw(T3, 0x20, SP)
    code.sltiu(T4, T3, 4)
    code.beq(T4, ZERO, "return")
    code.delay_nop()
    code.lw(A2, 0x30, SP)
    code.addu(A2, A2, T3)
    code.addu(A0, S4, ZERO)
    # Overflow names retain the 16px glyph height after horizontal resampling;
    # lower only this scratch strip to center its ink in the map-tag background.
    code.addiu(A1, S5, MAP2D_SCALED_NAME_Y_OFFSET)
    code.addiu(A3, ZERO, 9)
    code.addu(T0, S6, ZERO)
    code.addiu(T1, ZERO, 1)
    code.addu(T2, ZERO, ZERO)
    code.jalr(S7)
    code.delay_nop()
    code.addiu(S4, S4, 16)
    code.lw(T3, 0x20, SP)
    code.addiu(T3, T3, 1)
    code.sw(T3, 0x20, SP)
    code.beq(ZERO, ZERO, "draw_scratch")
    code.delay_nop()

    code.label("fallback")
    _load_pc_relative_target(
        code,
        T9,
        T8,
        pc_address=pc_address,
        target_address=MAP2D_STOCK_TEXT_DRAW_ADDRESS,
    )
    code.lw(A0, 0x38, SP)
    code.addu(A1, S4, ZERO)
    code.addu(A2, S5, ZERO)
    code.lw(A3, 0x34, SP)
    code.addu(T0, S6, ZERO)
    code.lw(RA, 0x5C, SP)
    code.lw(S0, 0x58, SP)
    code.lw(S1, 0x54, SP)
    code.lw(S2, 0x50, SP)
    code.lw(S3, 0x4C, SP)
    code.lw(S4, 0x48, SP)
    code.lw(S5, 0x44, SP)
    code.lw(S6, 0x40, SP)
    code.lw(S7, 0x3C, SP)
    code.addiu(SP, SP, 0x60)
    code.jr(T9)
    code.delay_nop()

    code.label("return")
    code.lw(RA, 0x5C, SP)
    code.lw(S0, 0x58, SP)
    code.lw(S1, 0x54, SP)
    code.lw(S2, 0x50, SP)
    code.lw(S3, 0x4C, SP)
    code.lw(S4, 0x48, SP)
    code.lw(S5, 0x44, SP)
    code.lw(S6, 0x40, SP)
    code.lw(S7, 0x3C, SP)
    code.addiu(SP, SP, 0x60)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def _build_map2d_top_draw_wrapper(
    row_offsets: Mapping[str, int],
) -> AssembledCode:
    """Draw EVE prompt/choice strips at their authored 16-pixel cell pitch."""

    code = _Assembler(MAP2D_TOP_DRAW_WRAPPER_ADDRESS)
    code.addiu(SP, SP, -0x40)
    code.sw(RA, 0x3C, SP)
    code.sw(S0, 0x38, SP)
    code.sw(S1, 0x34, SP)
    code.sw(S2, 0x30, SP)
    code.sw(S3, 0x2C, SP)
    code.sw(S4, 0x28, SP)
    code.sw(S5, 0x24, SP)
    code.sw(A0, 0x20, SP)
    code.sw(A3, 0x1C, SP)
    code.addu(S0, RA, ZERO)
    code.addu(S1, A1, ZERO)
    code.addu(S2, A2, ZERO)
    code.addu(S3, T0, ZERO)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    code.addu(T8, RA, ZERO)
    _load_pc_relative_target(
        code,
        S5,
        T8,
        pc_address=pc_address,
        target_address=MAP2D_STOCK_GLYPH_DRAW_ADDRESS,
    )
    cell_counts = {"talk_prompt": 14, "label_yes": 3, "label_no": 2}
    for index, (_name, site, record_name) in enumerate(MAP2D_TOP_DRAW_CALL_SITES):
        next_label = f"top_context_{index + 1}"
        _load_pc_relative_target(
            code,
            T1,
            T8,
            pc_address=pc_address,
            target_address=site + 8,
        )
        code.bne(S0, T1, next_label)
        code.delay_nop()
        _load_pc_relative_target(
            code,
            S4,
            T8,
            pc_address=pc_address,
            target_address=MAP2D_TOP_ROW_TABLE_ADDRESS + row_offsets[record_name],
        )
        code.addiu(T0, ZERO, cell_counts[record_name])
        code.sw(T0, 0x18, SP)
        code.beq(ZERO, ZERO, "draw")
        code.delay_nop()
        code.label(next_label)

    code.beq(ZERO, ZERO, "fallback")
    code.delay_nop()

    code.label("draw")
    code.sw(ZERO, 0x14, SP)
    code.label("draw_cell")
    code.lw(T0, 0x14, SP)
    code.lw(T1, 0x18, SP)
    code.sltu(T2, T0, T1)
    code.beq(T2, ZERO, "return")
    code.delay_nop()
    code.sll(T1, T0, 1)
    code.addu(T1, S4, T1)
    code.lhu(A2, 0, T1)
    code.addu(A0, S1, ZERO)
    code.addu(A1, S2, ZERO)
    code.addiu(A3, ZERO, 9)
    code.addu(T0, S3, ZERO)
    code.addiu(T1, ZERO, 1)
    code.addu(T2, ZERO, ZERO)
    code.jalr(S5)
    code.delay_nop()
    code.addiu(S1, S1, 16)
    code.lw(T0, 0x14, SP)
    code.addiu(T0, T0, 1)
    code.sw(T0, 0x14, SP)
    code.beq(ZERO, ZERO, "draw_cell")
    code.delay_nop()

    code.label("fallback")
    _load_pc_relative_target(
        code,
        T9,
        T8,
        pc_address=pc_address,
        target_address=MAP2D_STOCK_TEXT_DRAW_ADDRESS,
    )
    code.lw(A0, 0x20, SP)
    code.addu(A1, S1, ZERO)
    code.addu(A2, S2, ZERO)
    code.lw(A3, 0x1C, SP)
    code.addu(T0, S3, ZERO)
    code.lw(RA, 0x3C, SP)
    code.lw(S0, 0x38, SP)
    code.lw(S1, 0x34, SP)
    code.lw(S2, 0x30, SP)
    code.lw(S3, 0x2C, SP)
    code.lw(S4, 0x28, SP)
    code.lw(S5, 0x24, SP)
    code.addiu(SP, SP, 0x40)
    code.jr(T9)
    code.delay_nop()

    code.label("return")
    code.lw(RA, 0x3C, SP)
    code.lw(S0, 0x38, SP)
    code.lw(S1, 0x34, SP)
    code.lw(S2, 0x30, SP)
    code.lw(S3, 0x2C, SP)
    code.lw(S4, 0x28, SP)
    code.lw(S5, 0x24, SP)
    code.addiu(SP, SP, 0x40)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def build_map2d_runtime_patch(
    eve_records: Mapping[str, Iterable[int]],
    fixed_records: Iterable[Iterable[int]],
    glyph_codes: Mapping[str, int],
    glyph_advances: Mapping[str, int],
    *,
    scratch_ward_codes: Iterable[int],
    scratch_city_codes: Iterable[int],
) -> Map2dRuntimePatch:
    """Build MAP2D's EVE-atlas prompt and chosen-name runtime contract."""

    expected_record_lengths = {"talk_prompt": 14, "label_yes": 3, "label_no": 2}
    if not isinstance(eve_records, Mapping) or set(eve_records) != set(
        expected_record_lengths
    ):
        raise ValueError("PSP MAP2D EVE record inventory changed")
    rows: dict[str, tuple[int, ...]] = {}
    occupied_codes: set[int] = set()
    for name in ("talk_prompt", "label_yes", "label_no"):
        try:
            words = tuple(eve_records[name])
        except TypeError as error:
            raise TypeError(f"PSP MAP2D EVE {name} words must be iterable") from error
        if len(words) != expected_record_lengths[name]:
            raise ValueError(
                f"PSP MAP2D EVE {name} has {len(words)} words; "
                f"expected {expected_record_lengths[name]}"
            )
        if any(
            not isinstance(word, int)
            or isinstance(word, bool)
            or not 0 <= word <= 0x1E7F
            for word in words
        ):
            raise ValueError(f"PSP MAP2D EVE {name} words must be atlas u16 codes")
        if occupied_codes.intersection(words):
            raise ValueError("PSP MAP2D EVE prompt rows overlap")
        occupied_codes.update(words)
        rows[name] = words

    try:
        fixed_rows = tuple(tuple(row) for row in fixed_records)
    except TypeError as error:
        raise TypeError("PSP MAP2D fixed EVE rows must be iterable") from error
    if len(fixed_rows) != 5 or any(len(row) != 4 for row in fixed_rows):
        raise ValueError("PSP MAP2D requires five four-cell fixed EVE rows")
    for row_index, row in enumerate(fixed_rows, 1):
        if any(
            not isinstance(word, int)
            or isinstance(word, bool)
            or not 0 <= word <= 0x1E7F
            for word in row
        ):
            raise ValueError(
                f"PSP MAP2D fixed EVE row {row_index} must use atlas u16 codes"
            )
        if occupied_codes.intersection(row):
            raise ValueError("PSP MAP2D fixed EVE rows overlap another allocation")
        occupied_codes.update(row)

    printable = tuple(chr(code) for code in range(0x20, 0x7F))
    if not isinstance(glyph_codes, Mapping) or set(glyph_codes) != set(printable):
        raise ValueError("PSP MAP2D printable glyph-code inventory changed")
    if not isinstance(glyph_advances, Mapping) or set(glyph_advances) != set(printable):
        raise ValueError("PSP MAP2D printable advance inventory changed")
    width_values = [0] * PACKED_WIDTH_COUNT
    for character in printable:
        storage_index = _packed_storage_index(character)
        expected_code = MAP2D_PRINTABLE_GLYPH_FIRST + storage_index
        code_value = glyph_codes[character]
        advance = glyph_advances[character]
        if code_value != expected_code:
            raise ValueError(
                f"PSP MAP2D glyph {character!r} is {code_value:#x}; "
                f"expected {expected_code:#x}"
            )
        if (
            not isinstance(advance, int)
            or isinstance(advance, bool)
            or not 1 <= advance <= 16
        ):
            raise ValueError(f"PSP MAP2D advance for {character!r} is invalid")
        width_values[storage_index] = advance
    if any(value == 0 for value in width_values):
        raise ValueError("PSP MAP2D width table has an unowned storage slot")
    width_table = bytes(width_values)

    ward_codes = tuple(scratch_ward_codes)
    city_codes = tuple(scratch_city_codes)
    if ward_codes != MAP2D_SCRATCH_WARD_CODES:
        raise ValueError("PSP MAP2D ward scratch allocation changed")
    if city_codes != MAP2D_SCRATCH_CITY_CODES:
        raise ValueError("PSP MAP2D city scratch allocation changed")
    reserved = set(ward_codes) | set(city_codes)
    if occupied_codes & reserved or occupied_codes & set(glyph_codes.values()):
        raise ValueError("PSP MAP2D EVE atlas allocations overlap")

    row_offsets: dict[str, int] = {}
    top_row_table = bytearray()
    for name in ("talk_prompt", "label_yes", "label_no"):
        row_offsets[name] = len(top_row_table)
        words = (*rows[name], 0xFFF2)
        top_row_table.extend(struct.pack(f"<{len(words)}H", *words))
    fixed_row_table = b"".join(struct.pack("<4H", *row) for row in fixed_rows)

    dynamic_draw_wrapper = _build_map2d_dynamic_draw_wrapper()
    top_draw_wrapper = _build_map2d_top_draw_wrapper(row_offsets)
    if dynamic_draw_wrapper.end_address > ITEM_EVENT_INSERT_WRAPPER_ADDRESS:
        raise ValueError("PSP MAP2D dynamic wrapper exceeds its cave partition")
    if top_draw_wrapper.end_address > MAP2D_WIDTH_TABLE_ADDRESS:
        raise ValueError("PSP MAP2D top wrapper exceeds its cave partition")
    if MAP2D_WIDTH_TABLE_ADDRESS + len(width_table) > MAP2D_TOP_ROW_TABLE_ADDRESS:
        raise ValueError("PSP MAP2D widths exceed their cave partition")
    if MAP2D_TOP_ROW_TABLE_ADDRESS + len(top_row_table) > (
        MAP2D_FIXED_ROW_TABLE_ADDRESS
    ):
        raise ValueError("PSP MAP2D rows exceed the checked source-zero run")
    if MAP2D_FIXED_ROW_TABLE_ADDRESS + len(fixed_row_table) > (
        SAVEDATA_DETAIL_WRAPPER_ADDRESS
    ):
        raise ValueError("PSP MAP2D fixed rows exceed the checked source-zero run")

    writes = (
        tuple(
            PatchWrite(
                name,
                address,
                _word_bytes(_jal_word(address, MAP2D_DYNAMIC_DRAW_WRAPPER_ADDRESS)),
            )
            for name, address, _context in MAP2D_DYNAMIC_DRAW_CALL_SITES
        )
        + tuple(
            PatchWrite(
                name,
                address,
                _word_bytes(_jal_word(address, MAP2D_TOP_DRAW_WRAPPER_ADDRESS)),
            )
            for name, address, _record_name in MAP2D_TOP_DRAW_CALL_SITES
        )
        + (
            PatchWrite(
                "map2d_dynamic_draw_wrapper",
                dynamic_draw_wrapper.address,
                dynamic_draw_wrapper.data,
            ),
            PatchWrite(
                "map2d_top_draw_wrapper",
                top_draw_wrapper.address,
                top_draw_wrapper.data,
            ),
            PatchWrite("map2d_widths", MAP2D_WIDTH_TABLE_ADDRESS, width_table),
            PatchWrite(
                "map2d_top_rows",
                MAP2D_TOP_ROW_TABLE_ADDRESS,
                bytes(top_row_table),
            ),
            PatchWrite(
                "map2d_fixed_rows",
                MAP2D_FIXED_ROW_TABLE_ADDRESS,
                fixed_row_table,
            ),
        )
    )
    if len({write.name for write in writes}) != len(writes):
        raise ValueError("PSP MAP2D runtime patch contains duplicate write names")
    ordered = tuple(sorted(writes, key=lambda write: write.address))
    for left, right in zip(ordered, ordered[1:]):
        if left.end_address > right.address:
            raise ValueError(f"PSP MAP2D writes overlap: {left.name} and {right.name}")
    return Map2dRuntimePatch(
        dynamic_draw_wrapper,
        top_draw_wrapper,
        width_table,
        bytes(top_row_table),
        fixed_row_table,
        writes,
    )


__all__ = [
    "MAP2D_DYNAMIC_DRAW_CALL_SITES",
    "MAP2D_DYNAMIC_DRAW_WRAPPER_ADDRESS",
    "MAP2D_FIXED_ROW_TABLE_ADDRESS",
    "MAP2D_FONT_POINTER_ADDRESS",
    "MAP2D_FONT_POINTER_RAW_ADDRESS",
    "MAP2D_MARKER_CENTER_X",
    "MAP2D_NAME_FIELD_WIDTH",
    "MAP2D_PRINTABLE_GLYPH_FIRST",
    "MAP2D_PRINTABLE_GLYPH_LAST",
    "MAP2D_SCALED_NAME_Y_OFFSET",
    "MAP2D_SCRATCH_CITY_CODES",
    "MAP2D_SCRATCH_WARD_CODES",
    "MAP2D_STOCK_GLYPH_DRAW_ADDRESS",
    "MAP2D_STOCK_TEXT_DRAW_ADDRESS",
    "MAP2D_TOP_DRAW_CALL_SITES",
    "MAP2D_TOP_DRAW_WRAPPER_ADDRESS",
    "MAP2D_TOP_ROW_TABLE_ADDRESS",
    "MAP2D_VIEW_STATE_ADDRESS",
    "MAP2D_VIEW_STATE_RAW_ADDRESS",
    "MAP2D_WIDTH_TABLE_ADDRESS",
    "Map2dRuntimePatch",
    "build_map2d_runtime_patch",
]
