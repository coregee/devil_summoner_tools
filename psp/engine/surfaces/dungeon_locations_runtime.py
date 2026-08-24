"""Allegrex emitters for the PSP maze location and floor display."""

from __future__ import annotations

import struct
from collections.abc import Iterable
from dataclasses import dataclass

from ..core.emitter import (
    A0, A1, A2, A3, RA, S0, SP, T0, T1, T2, T3, T4, T5, T7, T8, T9,
    V0, ZERO, AssembledCode, PatchWrite, _Assembler, _jal_word,
    _load_pc_relative_target, _word_bytes,
)
from ..core.layout import (
    DUNGEON_LOCATION_CAVE_END_ADDRESS,
    DUNGEON_LOCATION_FLOOR_DRAW_WRAPPER_ADDRESS,
    DUNGEON_LOCATION_MAZE_NAME_DRAW_WRAPPER_ADDRESS,
    DUNGEON_LOCATION_MAZE_STAGE_WRAPPER_ADDRESS,
    DUNGEON_LOCATION_NAME_DESCRIPTOR_TABLE_ADDRESS,
    DUNGEON_LOCATION_NAME_SEQUENCE_CAVE_END_ADDRESS,
    DUNGEON_LOCATION_NAME_SEQUENCE_TABLE_ADDRESS,
    DUNGEON_LOCATION_STATE_ADDRESS,
    DUNGEON_LOCATION_TRANSITION_CURRENT_ID_ADDRESS,
    DUNGEON_LOCATION_TRANSITION_NAME_BRIDGE_ADDRESS,
    SAVEDATA_LOCATION_ID_TABLE_ADDRESS,
    SAVEDATA_LOCATION_NAME_COUNT,
    SAVEDATA_LOCATION_RECORD_COUNT,
    SAVEDATA_LOCATION_RECORD_SIZE,
    SAVEDATA_LOCATION_SOURCE_ADDRESS,
)


DUNGEON_LOCATION_MAZE_STAGE_CALL_ADDRESSES = (
    0x00019B08, 0x0001B31C, 0x0001B394, 0x0001B41C, 0x0001B494,
    0x0001B508, 0x0001B584, 0x0001F2C8, 0x000229F8, 0x00025E94,
)
DUNGEON_LOCATION_MAZE_STAGE_STOCK_ADDRESS = 0x00016354
DUNGEON_LOCATION_MAZE_NAME_DRAW_CALL_ADDRESS = 0x00016784
DUNGEON_LOCATION_MAZE_FLOOR_DRAW_CALL_ADDRESS = 0x0001688C
DUNGEON_LOCATION_TRANSITION_NAME_DRAW_CALL_ADDRESS = 0x00048CBC
DUNGEON_LOCATION_TRANSITION_FLOOR_DRAW_CALL_ADDRESS = 0x00048D60
DUNGEON_LOCATION_STOCK_GLYPH_DRAW_ADDRESS = 0x0000C998
DUNGEON_LOCATION_MAZE_PHYSICAL_ID_ADDRESS = DUNGEON_LOCATION_STATE_ADDRESS
DUNGEON_LOCATION_NATIVE_BASEMENT_PREFIX_CODE = 0x0138
DUNGEON_LOCATION_NATIVE_BASEMENT_SUFFIX_CODE = 0x022B
DUNGEON_LOCATION_NATIVE_FLOOR_SUFFIX_CODE = 0x022C


@dataclass(frozen=True, slots=True)
class DungeonLocationPatch:
    maze_name_draw_wrapper: AssembledCode
    floor_draw_wrapper: AssembledCode
    maze_stage_wrapper: AssembledCode
    transition_name_bridge: AssembledCode
    name_descriptors: bytes
    name_sequence: bytes
    writes: tuple[PatchWrite, ...]

    def write(self, name: str) -> PatchWrite:
        try:
            return next(write for write in self.writes if write.name == name)
        except StopIteration as error:
            raise KeyError(f"unknown PSP dungeon-location write: {name}") from error


def _build_stage_wrapper() -> AssembledCode:
    code = _Assembler(DUNGEON_LOCATION_MAZE_STAGE_WRAPPER_ADDRESS)
    code.addu(T8, RA, ZERO)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    code.addu(T7, RA, ZERO)
    _load_pc_relative_target(
        code, T0, T7, pc_address=pc_address,
        target_address=SAVEDATA_LOCATION_SOURCE_ADDRESS + 2,
    )
    code.subu(T1, A1, T0)
    code.sltiu(T2, T1, SAVEDATA_LOCATION_RECORD_COUNT * SAVEDATA_LOCATION_RECORD_SIZE)
    code.beq(T2, ZERO, "invalid")
    code.delay_nop()
    code.andi(T2, T1, SAVEDATA_LOCATION_RECORD_SIZE - 1)
    code.bne(T2, ZERO, "invalid")
    code.delay_nop()
    code.srl(T1, T1, 5)
    code.beq(ZERO, ZERO, "store")
    code.delay_nop()
    code.label("invalid")
    code.addiu(T1, ZERO, 0xFF)
    code.label("store")
    code.addiu(T0, T7, DUNGEON_LOCATION_MAZE_PHYSICAL_ID_ADDRESS - pc_address)
    code.sb(T1, 0, T0)
    _load_pc_relative_target(
        code, T9, T7, pc_address=pc_address,
        target_address=DUNGEON_LOCATION_MAZE_STAGE_STOCK_ADDRESS,
    )
    code.addu(RA, T8, ZERO)
    code.jr(T9)
    code.delay_nop()
    return code.finish()


def _build_name_wrapper() -> AssembledCode:
    code = _Assembler(DUNGEON_LOCATION_MAZE_NAME_DRAW_WRAPPER_ADDRESS)
    code.addiu(SP, SP, -0x20)
    code.sw(A0, 0x00, SP)
    code.sw(A1, 0x04, SP)
    code.sw(A2, 0x08, SP)
    code.sw(RA, 0x1C, SP)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    code.addu(T7, RA, ZERO)
    code.sw(T7, 0x14, SP)
    _load_pc_relative_target(
        code, T9, T7, pc_address=pc_address,
        target_address=DUNGEON_LOCATION_MAZE_PHYSICAL_ID_ADDRESS,
    )
    code.lbu(T0, 0, T9)
    code.sltiu(T2, T0, SAVEDATA_LOCATION_RECORD_COUNT)
    code.beq(T2, ZERO, "fallback")
    code.delay_nop()
    _load_pc_relative_target(
        code, T9, T7, pc_address=pc_address,
        target_address=SAVEDATA_LOCATION_ID_TABLE_ADDRESS,
    )
    code.addu(T9, T9, T0)
    code.lbu(T0, 0, T9)
    code.sltiu(T2, T0, SAVEDATA_LOCATION_NAME_COUNT)
    code.beq(T2, ZERO, "fallback")
    code.delay_nop()
    code.bne(S0, ZERO, "suppress")
    code.delay_nop()
    _load_pc_relative_target(
        code, T9, T7, pc_address=pc_address,
        target_address=DUNGEON_LOCATION_NAME_DESCRIPTOR_TABLE_ADDRESS,
    )
    code.sll(T0, T0, 1)
    code.addu(T9, T9, T0)
    code.lhu(T0, 0, T9)
    _load_pc_relative_target(
        code, T9, T7, pc_address=pc_address,
        target_address=DUNGEON_LOCATION_NAME_SEQUENCE_TABLE_ADDRESS,
    )
    code.addu(T9, T9, T0)
    code.sw(T9, 0x10, SP)
    code.label("loop")
    code.lw(T9, 0x10, SP)
    code.lbu(T3, 0, T9)
    code.lbu(T4, 1, T9)
    code.addiu(T9, T9, 2)
    code.sw(T9, 0x10, SP)
    code.addiu(T1, ZERO, 0xFF)
    code.beq(T3, T1, "done")
    code.delay_nop()
    code.lw(A0, 0x00, SP)
    code.andi(T5, T4, 0x3F)
    code.addu(A0, A0, T5)
    code.lw(A1, 0x04, SP)
    code.andi(T5, T4, 0x80)
    code.srl(T5, T5, 3)
    code.addu(A1, A1, T5)
    code.lw(A2, 0x08, SP)
    code.ori(A3, T3, 0x0600)
    code.addiu(T0, ZERO, -1)
    code.lw(T7, 0x14, SP)
    _load_pc_relative_target(
        code, T9, T7, pc_address=pc_address,
        target_address=DUNGEON_LOCATION_STOCK_GLYPH_DRAW_ADDRESS,
    )
    code.jalr(T9)
    code.delay_nop()
    code.beq(ZERO, ZERO, "loop")
    code.delay_nop()
    code.label("done")
    code.lw(RA, 0x1C, SP)
    code.addiu(SP, SP, 0x20)
    code.jr(RA)
    code.delay_nop()
    code.label("fallback")
    code.addiu(T0, ZERO, -1)
    _load_pc_relative_target(
        code, T9, T7, pc_address=pc_address,
        target_address=DUNGEON_LOCATION_STOCK_GLYPH_DRAW_ADDRESS,
    )
    code.lw(RA, 0x1C, SP)
    code.addiu(SP, SP, 0x20)
    code.jr(T9)
    code.delay_nop()
    code.label("suppress")
    code.addu(V0, ZERO, ZERO)
    code.lw(RA, 0x1C, SP)
    code.addiu(SP, SP, 0x20)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def _build_floor_wrapper(digit_first: int, basement: int, floor: int) -> AssembledCode:
    code = _Assembler(DUNGEON_LOCATION_FLOOR_DRAW_WRAPPER_ADDRESS)
    code.addu(T7, RA, ZERO)
    code.beq(A3, ZERO, "suppress")
    code.delay_nop()
    code.addiu(T1, ZERO, DUNGEON_LOCATION_NATIVE_BASEMENT_PREFIX_CODE)
    code.beq(A3, T1, "suppress")
    code.delay_nop()
    code.sltiu(T1, A3, 11)
    code.bne(T1, ZERO, "digit")
    code.delay_nop()
    code.addiu(T1, ZERO, DUNGEON_LOCATION_NATIVE_BASEMENT_SUFFIX_CODE)
    code.beq(A3, T1, "basement")
    code.delay_nop()
    code.addiu(T1, ZERO, DUNGEON_LOCATION_NATIVE_FLOOR_SUFFIX_CODE)
    code.beq(A3, T1, "floor")
    code.delay_nop()
    code.beq(ZERO, ZERO, "draw")
    code.delay_nop()
    code.label("digit")
    code.addiu(A3, A3, digit_first - 1)
    code.sltiu(T1, S0, 2)
    code.bne(T1, ZERO, "tens")
    code.delay_nop()
    code.addiu(A0, A0, 17)
    code.beq(ZERO, ZERO, "draw")
    code.delay_nop()
    code.label("tens")
    code.addiu(A0, A0, 26)
    code.beq(ZERO, ZERO, "draw")
    code.delay_nop()
    code.label("basement")
    code.addiu(A3, ZERO, basement)
    code.addiu(A0, A0, 25)
    code.beq(ZERO, ZERO, "draw")
    code.delay_nop()
    code.label("floor")
    code.addiu(A3, ZERO, floor)
    code.addiu(A0, A0, 8)
    code.label("draw")
    code.addiu(T0, ZERO, -1)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    _load_pc_relative_target(
        code, T9, RA, pc_address=pc_address,
        target_address=DUNGEON_LOCATION_STOCK_GLYPH_DRAW_ADDRESS,
    )
    code.addu(RA, T7, ZERO)
    code.jr(T9)
    code.delay_nop()
    code.label("suppress")
    code.addu(V0, ZERO, ZERO)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def _build_transition_name_bridge() -> AssembledCode:
    """Stage surface A's physical ID, then enter the shared name drawer."""

    code = _Assembler(DUNGEON_LOCATION_TRANSITION_NAME_BRIDGE_ADDRESS)
    code.addu(T8, RA, ZERO)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    code.addu(T7, RA, ZERO)
    _load_pc_relative_target(
        code, T9, T7, pc_address=pc_address,
        target_address=DUNGEON_LOCATION_TRANSITION_CURRENT_ID_ADDRESS,
    )
    code.lhu(T0, 0, T9)
    _load_pc_relative_target(
        code, T9, T7, pc_address=pc_address,
        target_address=DUNGEON_LOCATION_MAZE_PHYSICAL_ID_ADDRESS,
    )
    code.sb(T0, 0, T9)
    _load_pc_relative_target(
        code, T9, T7, pc_address=pc_address,
        target_address=DUNGEON_LOCATION_MAZE_NAME_DRAW_WRAPPER_ADDRESS,
    )
    code.addu(RA, T8, ZERO)
    code.jr(T9)
    code.delay_nop()
    return code.finish()


def build_dungeon_location_patch(
    name_records: Iterable[Iterable[tuple[int, int, int]]],
    digit_codes: Iterable[int],
    *,
    basement_code: int,
    floor_code: int,
) -> DungeonLocationPatch:
    try:
        records = tuple(tuple(tuple(glyph) for glyph in record) for record in name_records)
        digits = tuple(digit_codes)
    except TypeError as error:
        raise TypeError("PSP dungeon-location records must be iterable") from error
    if len(records) != SAVEDATA_LOCATION_NAME_COUNT:
        raise ValueError("PSP dungeon locations require 24 aligned name records")
    if (
        len(digits) != 10
        or digits != tuple(range(digits[0], digits[0] + 10))
        or any(code >> 8 != 0x06 for code in digits)
    ):
        raise ValueError("PSP dungeon-location digit allocation is invalid")
    if not all(isinstance(code, int) and 0 < code < 0x8000 for code in (basement_code, floor_code)):
        raise ValueError("PSP dungeon-location floor codes are invalid")

    descriptor_offsets = []
    sequence = bytearray()
    for location_id, record in enumerate(records):
        if not record:
            raise ValueError(f"PSP dungeon-location record {location_id} is empty")
        descriptor_offsets.append(len(sequence))
        prior_row = -1
        prior_x = -1
        for glyph in record:
            if len(glyph) != 3 or not all(isinstance(value, int) for value in glyph):
                raise ValueError("PSP dungeon-location glyphs require integer code/x/row")
            glyph_code, x_offset, row = glyph
            if glyph_code >> 8 != 0x06 or glyph_code & 0xFF == 0xFF:
                raise ValueError("PSP dungeon-location glyph escaped page 6")
            if not 0 <= x_offset < 64 or row not in (0, 1):
                raise ValueError("PSP dungeon-location glyph escaped its two-row field")
            if row < prior_row or (row == prior_row and x_offset <= prior_x):
                raise ValueError("PSP dungeon-location glyph order is not increasing")
            if row != prior_row:
                prior_x = -1
            sequence.extend((glyph_code & 0xFF, x_offset | row << 7))
            prior_row, prior_x = row, x_offset
        sequence.extend((0xFF, 0))
    descriptors = struct.pack(f"<{SAVEDATA_LOCATION_NAME_COUNT}H", *descriptor_offsets)

    name_wrapper = _build_name_wrapper()
    floor_wrapper = _build_floor_wrapper(digits[0], basement_code, floor_code)
    stage_wrapper = _build_stage_wrapper()
    transition_name_bridge = _build_transition_name_bridge()
    if name_wrapper.end_address > DUNGEON_LOCATION_FLOOR_DRAW_WRAPPER_ADDRESS:
        raise ValueError("PSP dungeon-location name wrapper exceeds its partition")
    if floor_wrapper.end_address > DUNGEON_LOCATION_MAZE_STAGE_WRAPPER_ADDRESS:
        raise ValueError("PSP dungeon-location floor wrapper exceeds its partition")
    if stage_wrapper.end_address > DUNGEON_LOCATION_NAME_DESCRIPTOR_TABLE_ADDRESS:
        raise ValueError("PSP dungeon-location staging exceeds its partition")
    if transition_name_bridge.end_address > DUNGEON_LOCATION_CAVE_END_ADDRESS:
        raise ValueError("PSP dungeon-location transition bridge exceeds its cave")
    if DUNGEON_LOCATION_NAME_DESCRIPTOR_TABLE_ADDRESS + len(descriptors) > DUNGEON_LOCATION_CAVE_END_ADDRESS:
        raise ValueError("PSP dungeon-location descriptors exceed their cave")
    if DUNGEON_LOCATION_NAME_SEQUENCE_TABLE_ADDRESS + len(sequence) > DUNGEON_LOCATION_NAME_SEQUENCE_CAVE_END_ADDRESS:
        raise ValueError("PSP dungeon-location sequence exceeds its cave")

    writes = (
        *tuple(
            PatchWrite(
                f"dungeon_location_maze_stage_call_{index}", address,
                _word_bytes(_jal_word(address, DUNGEON_LOCATION_MAZE_STAGE_WRAPPER_ADDRESS)),
            )
            for index, address in enumerate(DUNGEON_LOCATION_MAZE_STAGE_CALL_ADDRESSES)
        ),
        PatchWrite(
            "dungeon_location_maze_name_draw_call",
            DUNGEON_LOCATION_MAZE_NAME_DRAW_CALL_ADDRESS,
            _word_bytes(_jal_word(DUNGEON_LOCATION_MAZE_NAME_DRAW_CALL_ADDRESS, DUNGEON_LOCATION_MAZE_NAME_DRAW_WRAPPER_ADDRESS)),
        ),
        PatchWrite(
            "dungeon_location_maze_floor_draw_call",
            DUNGEON_LOCATION_MAZE_FLOOR_DRAW_CALL_ADDRESS,
            _word_bytes(_jal_word(DUNGEON_LOCATION_MAZE_FLOOR_DRAW_CALL_ADDRESS, DUNGEON_LOCATION_FLOOR_DRAW_WRAPPER_ADDRESS)),
        ),
        PatchWrite(
            "dungeon_location_transition_name_draw_call",
            DUNGEON_LOCATION_TRANSITION_NAME_DRAW_CALL_ADDRESS,
            _word_bytes(
                _jal_word(
                    DUNGEON_LOCATION_TRANSITION_NAME_DRAW_CALL_ADDRESS,
                    DUNGEON_LOCATION_TRANSITION_NAME_BRIDGE_ADDRESS,
                )
            ),
        ),
        PatchWrite(
            "dungeon_location_transition_floor_draw_call",
            DUNGEON_LOCATION_TRANSITION_FLOOR_DRAW_CALL_ADDRESS,
            _word_bytes(
                _jal_word(
                    DUNGEON_LOCATION_TRANSITION_FLOOR_DRAW_CALL_ADDRESS,
                    DUNGEON_LOCATION_FLOOR_DRAW_WRAPPER_ADDRESS,
                )
            ),
        ),
        PatchWrite("dungeon_location_maze_name_draw_wrapper", name_wrapper.address, name_wrapper.data),
        PatchWrite("dungeon_location_floor_draw_wrapper", floor_wrapper.address, floor_wrapper.data),
        PatchWrite("dungeon_location_maze_stage_wrapper", stage_wrapper.address, stage_wrapper.data),
        PatchWrite("dungeon_location_name_descriptors", DUNGEON_LOCATION_NAME_DESCRIPTOR_TABLE_ADDRESS, descriptors),
        PatchWrite(
            "dungeon_location_transition_name_bridge",
            DUNGEON_LOCATION_TRANSITION_NAME_BRIDGE_ADDRESS,
            transition_name_bridge.data,
        ),
        PatchWrite("dungeon_location_name_sequence", DUNGEON_LOCATION_NAME_SEQUENCE_TABLE_ADDRESS, bytes(sequence)),
        PatchWrite("dungeon_location_state", DUNGEON_LOCATION_STATE_ADDRESS, b"\xff"),
    )
    ordered = tuple(sorted(writes, key=lambda write: write.address))
    for left, right in zip(ordered, ordered[1:]):
        if left.end_address > right.address:
            raise ValueError(f"PSP dungeon-location writes overlap: {left.name} and {right.name}")
    return DungeonLocationPatch(
        name_wrapper,
        floor_wrapper,
        stage_wrapper,
        transition_name_bridge,
        descriptors,
        bytes(sequence),
        writes,
    )


__all__ = [
    "DUNGEON_LOCATION_MAZE_FLOOR_DRAW_CALL_ADDRESS",
    "DUNGEON_LOCATION_MAZE_NAME_DRAW_CALL_ADDRESS",
    "DUNGEON_LOCATION_MAZE_PHYSICAL_ID_ADDRESS",
    "DUNGEON_LOCATION_MAZE_STAGE_CALL_ADDRESSES",
    "DUNGEON_LOCATION_MAZE_STAGE_STOCK_ADDRESS",
    "DUNGEON_LOCATION_NATIVE_BASEMENT_PREFIX_CODE",
    "DUNGEON_LOCATION_NATIVE_BASEMENT_SUFFIX_CODE",
    "DUNGEON_LOCATION_NATIVE_FLOOR_SUFFIX_CODE",
    "DUNGEON_LOCATION_STOCK_GLYPH_DRAW_ADDRESS",
    "DUNGEON_LOCATION_TRANSITION_FLOOR_DRAW_CALL_ADDRESS",
    "DUNGEON_LOCATION_TRANSITION_NAME_DRAW_CALL_ADDRESS",
    "DungeonLocationPatch",
    "build_dungeon_location_patch",
]
