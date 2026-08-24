"""Shared proportional-name composition for PSP battle surfaces.

Only proven party-panel loops and the battle-result text wrapper are
redirected. The shared resolvers retain their other callers, while these
screen-local wrappers decode the live packed Codename and replace the fixed
Japanese result rows.
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
    S7,
    SP,
    T0,
    T1,
    T2,
    T3,
    V0,
    ZERO,
    AssembledCode,
    PatchWrite,
    _Assembler,
    _branch_word,
    _jal_word,
    _load_pc_relative_target,
    _word_bytes,
)
from ..core.layout import (
    BATTLE_NAME_CAVE_END_ADDRESS,
    BATTLE_NAME_CODE_TABLE_ADDRESS,
    BATTLE_NAME_DRAW_WRAPPER_ADDRESS,
    BATTLE_NAME_DRAW_WRAPPER_END_ADDRESS,
    BATTLE_RESULT_CAVE_END_ADDRESS,
    BATTLE_RESULT_DRAW_WRAPPER_ADDRESS,
    BATTLE_RESULT_STATIC_STORAGE_ADDRESS,
    COMPENDIUM_NAME_TABLE_ADDRESS,
    COMPENDIUM_NAME_TABLE_SIZE,
    DATA_LOAD_SEGMENT_ADDRESS,
    NAME_PROFILE_ADDRESS,
    NAME_PROFILE_FIELD_OFFSETS,
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

BATTLE_NAME_WIDTH_TABLE_ADDRESS = 0x00171760
BATTLE_NAME_STATIC_STORAGE_ADDRESS = 0x001717C0
BATTLE_NAME_STATIC_STORAGE_MAX_SIZE = 0x40

BATTLE_NAME_MODE1_DRAW_CALL_ADDRESS = 0x000868B0
BATTLE_NAME_MODE1_LOOP_SKIP_ADDRESS = 0x000868B8
BATTLE_NAME_MODE1_CONTINUE_ADDRESS = 0x000868E8
BATTLE_NAME_MODE0_DRAW_CALL_ADDRESS = 0x00086C38
BATTLE_NAME_MODE0_LOOP_SKIP_ADDRESS = 0x00086C40
BATTLE_NAME_MODE0_CONTINUE_ADDRESS = 0x00086C70
BATTLE_NAME_PARTY_DRAW_CALL_ADDRESS = 0x0008A47C
BATTLE_NAME_PARTY_LOOP_SKIP_ADDRESS = 0x0008A484
BATTLE_NAME_PARTY_CONTINUE_ADDRESS = 0x0008A4B4
BATTLE_NAME_PANEL_MODE1_DRAW_CALL_ADDRESS = 0x0002CE40
BATTLE_NAME_PANEL_MODE1_LOOP_SKIP_ADDRESS = 0x0002CE48
BATTLE_NAME_PANEL_MODE1_CONTINUE_ADDRESS = 0x0002CE78
BATTLE_NAME_PANEL_MODE0_DRAW_CALL_ADDRESS = 0x0002D3C4
BATTLE_NAME_PANEL_MODE0_LOOP_SKIP_ADDRESS = 0x0002D3CC
BATTLE_NAME_PANEL_MODE0_CONTINUE_ADDRESS = 0x0002D3FC

BATTLE_RESULT_NAME_PRIMARY_DRAW_CALL_ADDRESS = 0x00031BA4
BATTLE_RESULT_NAME_SECONDARY_DRAW_CALL_ADDRESS = 0x00031D18
BATTLE_RESULT_LIFE_STONE_DRAW_CALL_ADDRESS = 0x00031D78
BATTLE_RESULT_LIFE_STONE_CONTINUATION_DRAW_CALL_ADDRESS = 0x00031D90
BATTLE_RESULT_BEAD_DRAW_CALL_ADDRESS = 0x00031DD0
BATTLE_RESULT_BEAD_CONTINUATION_DRAW_CALL_ADDRESS = 0x00031DE8
BATTLE_RESULT_NONE_DRAW_CALL_ADDRESS = 0x00032064
BATTLE_RESULT_NONE_CONTINUATION_DRAW_CALL_ADDRESS = 0x00032080
BATTLE_RESULT_STOCK_GLYPH_DRAW_ADDRESS = 0x0000C998
BATTLE_RESULT_NAME_TABLE_POINTER_RAW_ADDRESS = 0x002F8558
BATTLE_RESULT_NAME_TABLE_POINTER_ADDRESS = (
    DATA_LOAD_SEGMENT_ADDRESS + BATTLE_RESULT_NAME_TABLE_POINTER_RAW_ADDRESS
)
BATTLE_RESULT_NONE_OFFSET = 0x00
BATTLE_RESULT_LIFE_STONES_OFFSET = 0x20
BATTLE_RESULT_BEADS_OFFSET = 0x40
BATTLE_RESULT_STATIC_RECORD_SIZE = 0x20
BATTLE_RESULT_STATIC_STORAGE_MAX_SIZE = 0x60
BATTLE_RESULT_NONE_X = 0x51
BATTLE_RESULT_LABEL_RIGHT_ANCHOR_X = 0x109

BATTLE_NAME_STOCK_RESOLVER_ADDRESS = 0x00074360
BATTLE_NAME_STOCK_GLYPH_DRAW_ADDRESS = 0x0000C998
BATTLE_NAME_PLAYER_ID_FIRST = 0x0100
BATTLE_NAME_PLAYER_ID_LIMIT = 0x0105
BATTLE_NAME_MYSTERIOUS_MAN_ID = 0x0105
BATTLE_NAME_FULL_DVL_SHADOWED_ID_FIRST = BATTLE_NAME_PLAYER_ID_FIRST
BATTLE_NAME_FULL_DVL_SHADOWED_ID_LIMIT = BATTLE_NAME_MYSTERIOUS_MAN_ID + 1
BATTLE_NAME_X = 0x32
BATTLE_NAME_Y = 8
BATTLE_NAME_LAYER = 5
BATTLE_NAME_PARTY_LAYER = 6
BATTLE_NAME_STOCK_COUNT = 8
BATTLE_NAME_STOCK_ADVANCE = 14
BATTLE_NAME_FIELD_WIDTH = BATTLE_NAME_STOCK_COUNT * BATTLE_NAME_STOCK_ADVANCE
BATTLE_NAME_FULL_DVL_RECORD_COUNT = 319
BATTLE_NAME_FULL_DVL_MAX_LENGTH = 16


@dataclass(frozen=True)
class BattleNamePatchSource:
    """PSP-local text and low-FONT16 mapping supplied by the build layer.

    Full-DVL mode reads the Compendium-owned table without writing it.  The
    stock special namespace remains authoritative, so physical DVL IDs
    256..261 stay shadowed by players and Mysterious Man.
    """

    mysterious_man: str
    result_none: str
    result_life_stones: str
    result_beads: str
    packed_glyph_codes: Iterable[int]
    packed_glyph_advances: Iterable[int]
    full_dvl_names: bool = False


@dataclass(frozen=True)
class BattleNamePatch:
    """All isolated writes for the two battle-card name states."""

    draw_wrapper: AssembledCode
    result_draw_wrapper: AssembledCode
    code_table: bytes
    width_table: bytes
    static_storage: bytes
    result_static_storage: bytes
    writes: tuple[PatchWrite, ...]

    def write(self, name: str) -> PatchWrite:
        try:
            return next(write for write in self.writes if write.name == name)
        except StopIteration as error:
            raise KeyError(f"unknown Allegrex battle-name write: {name}") from error


def _validate_table(values: Iterable[int], context: str) -> bytes:
    try:
        resolved = tuple(values)
    except TypeError as error:
        raise TypeError(f"PSP battle-name {context} must be iterable") from error
    if len(resolved) != PACKED_WIDTH_COUNT:
        raise ValueError(
            f"PSP battle-name {context} has {len(resolved)} entries; "
            f"expected {PACKED_WIDTH_COUNT}"
        )
    if any(
        not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 0xFF
        for value in resolved
    ):
        raise ValueError(f"PSP battle-name {context} must contain u8 integers")
    return bytes(resolved)


def _validate_source(
    source: BattleNamePatchSource,
) -> tuple[bytes, bytes, bytes, bytes, tuple[int, int, int]]:
    if not isinstance(source, BattleNamePatchSource):
        raise TypeError("PSP battle-name source has the wrong type")
    if not isinstance(source.full_dvl_names, bool):
        raise TypeError("PSP battle-name full-DVL mode must be boolean")
    text = source.mysterious_man
    if (
        not isinstance(text, str)
        or not text
        or len(text) > BATTLE_NAME_STATIC_STORAGE_MAX_SIZE
        or any(not 0x20 <= ord(character) <= 0x7E for character in text)
    ):
        raise ValueError("PSP Mysterious Man must be bounded printable ASCII")
    codes = _validate_table(source.packed_glyph_codes, "code table")
    widths = _validate_table(source.packed_glyph_advances, "width table")
    space_index = _packed_storage_index(" ")
    for index, (code, width) in enumerate(zip(codes, widths, strict=True)):
        if index == space_index:
            if code != 0 or width == 0:
                raise ValueError("PSP battle-name space mapping changed")
        elif (code == 0) != (width == 0):
            raise ValueError(
                "PSP battle-name unsupported glyph mappings must be all-zero"
            )

    def encode_checked(value: str, context: str) -> bytes:
        if (
            not isinstance(value, str)
            or not value
            or any(not 0x20 <= ord(character) <= 0x7E for character in value)
        ):
            raise ValueError(f"PSP {context} must be nonempty printable ASCII")
        encoded = bytes(
            PACKED_FIRST + _packed_storage_index(character) for character in value
        )
        for character, byte in zip(value, encoded, strict=True):
            index = byte - PACKED_FIRST
            if widths[index] == 0 or (character != " " and codes[index] == 0):
                raise ValueError(f"PSP {context} glyph {character!r} is not mapped")
        return encoded

    storage = encode_checked(text, "Mysterious Man")
    static_width = sum(widths[value - PACKED_FIRST] for value in storage)
    if static_width > BATTLE_NAME_FIELD_WIDTH:
        raise ValueError(
            f"PSP Mysterious Man width {static_width} exceeds "
            f"{BATTLE_NAME_FIELD_WIDTH} pixels"
        )
    if max(widths, default=0) * BATTLE_NAME_STOCK_COUNT > BATTLE_NAME_FIELD_WIDTH:
        raise ValueError("PSP battle-name mapping can exceed the 8-cell name field")
    result_storage = bytearray(BATTLE_RESULT_STATIC_STORAGE_MAX_SIZE)
    result_widths = []
    for value, offset, context in (
        (source.result_none, BATTLE_RESULT_NONE_OFFSET, "result None"),
        (
            source.result_life_stones,
            BATTLE_RESULT_LIFE_STONES_OFFSET,
            "result Life Stone",
        ),
        (source.result_beads, BATTLE_RESULT_BEADS_OFFSET, "result Bead"),
    ):
        encoded = encode_checked(value, context)
        if len(encoded) + 1 > BATTLE_RESULT_STATIC_RECORD_SIZE:
            raise ValueError(f"PSP {context} exceeds its checked result record")
        result_width = sum(widths[byte - PACKED_FIRST] for byte in encoded)
        if result_width > BATTLE_NAME_FIELD_WIDTH:
            raise ValueError(f"PSP {context} exceeds the checked result field")
        result_widths.append(result_width)
        result_storage[offset : offset + len(encoded)] = encoded
    return (
        codes,
        widths,
        storage,
        bytes(result_storage),
        (result_widths[0], result_widths[1], result_widths[2]),
    )


def validate_full_dvl_table(
    source: BattleNamePatchSource,
    dvlname_table: bytes,
) -> None:
    """Prove the shared table fits this screen's distinct Ark12 renderer."""

    codes, widths, _storage, _result_storage, _result_widths = _validate_source(source)
    if not source.full_dvl_names:
        raise ValueError("PSP battle-name source has not enabled full-DVL mode")
    if not isinstance(dvlname_table, bytes):
        raise TypeError("PSP battle-name shared DVL table must be bytes")
    if len(dvlname_table) != COMPENDIUM_NAME_TABLE_SIZE:
        raise ValueError(
            f"PSP battle-name shared DVL table is {len(dvlname_table)} bytes; "
            f"expected {COMPENDIUM_NAME_TABLE_SIZE}"
        )

    offset_table_size = BATTLE_NAME_FULL_DVL_RECORD_COUNT * 2
    space_index = _packed_storage_index(" ")
    for row_index in range(BATTLE_NAME_FULL_DVL_RECORD_COUNT):
        offset_index = row_index * 2
        offset = int.from_bytes(
            dvlname_table[offset_index : offset_index + 2],
            "little",
        )
        if not offset_table_size <= offset < len(dvlname_table):
            raise ValueError(
                f"PSP battle-name shared DVL row {row_index} has invalid offset"
            )
        try:
            terminator = dvlname_table.index(0, offset)
        except ValueError as error:
            raise ValueError(
                f"PSP battle-name shared DVL row {row_index} is unterminated"
            ) from error
        encoded = dvlname_table[offset:terminator]
        if not encoded or len(encoded) > BATTLE_NAME_FULL_DVL_MAX_LENGTH:
            raise ValueError(
                f"PSP battle-name shared DVL row {row_index} has invalid length"
            )
        width = 0
        for value in encoded:
            index = value - PACKED_FIRST
            if not 0 <= index < PACKED_WIDTH_COUNT:
                raise ValueError(
                    f"PSP battle-name shared DVL row {row_index} has invalid text"
                )
            advance = widths[index]
            if advance == 0 or (index != space_index and codes[index] == 0):
                raise ValueError(
                    f"PSP battle-name shared DVL row {row_index} uses an "
                    "unsupported Ark12 glyph"
                )
            width += advance
        if width > BATTLE_NAME_FIELD_WIDTH:
            raise ValueError(
                f"PSP battle-name shared DVL row {row_index} is {width}px; "
                f"field width is {BATTLE_NAME_FIELD_WIDTH}px"
            )


def _build_battle_name_draw_wrapper(
    static_length: int,
    *,
    full_dvl_names: bool,
) -> AssembledCode:
    code = _Assembler(BATTLE_NAME_DRAW_WRAPPER_ADDRESS)

    def save_frame() -> None:
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
        code.andi(S0, A0, 0xFFFF)

    # The two earlier battle-card paths supply only the unit ID. Normalize
    # their fixed geometry before entering the shared renderer.
    save_frame()
    code.addiu(T0, ZERO, BATTLE_NAME_X)
    code.sw(T0, 0x00, SP)
    code.addiu(T0, ZERO, BATTLE_NAME_Y)
    code.sw(T0, 0x04, SP)
    code.addiu(T0, ZERO, BATTLE_NAME_LAYER)
    code.sw(T0, 0x08, SP)
    code.addiu(T0, ZERO, -1)
    code.sw(T0, 0x0C, SP)
    code.beq(ZERO, ZERO, "dispatch")
    code.delay_nop()

    # The visible party drawer supplies x, y, and tint in a1..a3. Its stock
    # layer is six; preserve the other arguments across every C998 call.
    code.label("party_entry")
    save_frame()
    code.sw(A1, 0x00, SP)
    code.sw(A2, 0x04, SP)
    code.addiu(T0, ZERO, BATTLE_NAME_PARTY_LAYER)
    code.sw(T0, 0x08, SP)
    code.sw(A3, 0x0C, SP)

    code.label("dispatch")

    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    _load_pc_relative_target(
        code,
        S4,
        RA,
        pc_address=pc_address,
        target_address=BATTLE_NAME_CODE_TABLE_ADDRESS,
    )
    _load_pc_relative_target(
        code,
        S5,
        RA,
        pc_address=pc_address,
        target_address=BATTLE_NAME_WIDTH_TABLE_ADDRESS,
    )
    _load_pc_relative_target(
        code,
        S6,
        RA,
        pc_address=pc_address,
        target_address=BATTLE_NAME_STOCK_GLYPH_DRAW_ADDRESS,
    )
    _load_pc_relative_target(
        code,
        S7,
        RA,
        pc_address=pc_address,
        target_address=(
            COMPENDIUM_NAME_TABLE_ADDRESS
            if full_dvl_names
            else BATTLE_NAME_STOCK_RESOLVER_ADDRESS
        ),
    )

    code.addiu(T0, S0, -BATTLE_NAME_PLAYER_ID_FIRST)
    code.sltiu(T1, T0, BATTLE_NAME_PLAYER_ID_LIMIT - BATTLE_NAME_PLAYER_ID_FIRST)
    code.bne(T1, ZERO, "codename")
    code.delay_nop()
    code.ori(T0, ZERO, BATTLE_NAME_MYSTERIOUS_MAN_ID)
    code.beq(S0, T0, "mysterious_man")
    code.delay_nop()

    if full_dvl_names:
        # The stock special namespace intentionally shadows physical DVL rows
        # 256..261 (IDs 0x100..0x105).  All other one-based rows resolve through
        # the Compendium-owned offset table; this feature never writes it.
        code.addiu(T0, S0, -1)
        code.sltiu(T1, T0, BATTLE_NAME_FULL_DVL_RECORD_COUNT)
        code.beq(T1, ZERO, "return")
        code.delay_nop()
        code.sll(T0, T0, 1)
        code.addu(T0, S7, T0)
        code.lhu(T0, 0, T0)
        code.addu(S2, S7, T0)
        code.addiu(S3, ZERO, BATTLE_NAME_FULL_DVL_MAX_LENGTH)
        code.beq(ZERO, ZERO, "render_setup")
        code.delay_nop()
    else:
        # Preserve stock behavior for every unit ID outside this screen's two
        # translated owners.
        code.addu(A0, S0, ZERO)
        code.jalr(S7)
        code.delay_nop()
        code.addu(S2, V0, ZERO)
        code.addiu(S3, ZERO, BATTLE_NAME_STOCK_COUNT)
        code.lw(S1, 0x00, SP)
        code.label("stock_loop")
        code.lbu(A3, 0, S2)
        code.addu(A0, S1, ZERO)
        code.lw(A1, 0x04, SP)
        code.lw(A2, 0x08, SP)
        code.lw(T0, 0x0C, SP)
        code.addiu(S2, S2, 1)
        code.addiu(S3, S3, -1)
        code.addiu(T1, A2, 9)
        code.addu(S1, S1, T1)
        code.jalr(S6)
        code.delay_nop()
        code.bne(S3, ZERO, "stock_loop")
        code.delay_nop()
        code.beq(ZERO, ZERO, "return")
        code.delay_nop()

    code.label("codename")
    _load_pc_relative_target(
        code,
        S2,
        RA,
        pc_address=pc_address,
        target_address=(NAME_PROFILE_ADDRESS + NAME_PROFILE_FIELD_OFFSETS["codename"]),
    )
    code.addiu(S3, ZERO, BATTLE_NAME_STOCK_COUNT)
    code.beq(ZERO, ZERO, "render_setup")
    code.delay_nop()

    code.label("mysterious_man")
    _load_pc_relative_target(
        code,
        S2,
        RA,
        pc_address=pc_address,
        target_address=BATTLE_NAME_STATIC_STORAGE_ADDRESS,
    )
    code.addiu(S3, ZERO, static_length)

    code.label("render_setup")
    code.lw(S1, 0x00, SP)
    code.label("render_loop")
    code.lbu(T0, 0, S2)
    code.beq(T0, ZERO, "return")
    code.delay_nop()
    code.addiu(T1, T0, -PACKED_FIRST)
    code.sltiu(T2, T1, PACKED_WIDTH_COUNT)
    code.beq(T2, ZERO, "return")
    code.delay_nop()
    code.addu(T2, S4, T1)
    code.lbu(A3, 0, T2)
    code.addu(T2, S5, T1)
    code.lbu(T3, 0, T2)
    code.beq(T3, ZERO, "return")
    code.delay_nop()
    code.addu(A0, S1, ZERO)
    code.lw(A1, 0x04, SP)
    code.lw(A2, 0x08, SP)
    code.lw(T0, 0x0C, SP)
    code.addiu(S2, S2, 1)
    code.addiu(S3, S3, -1)
    code.addu(S1, S1, T3)
    code.beq(A3, ZERO, "glyph_done")
    code.delay_nop()
    code.jalr(S6)
    code.delay_nop()
    code.label("glyph_done")
    code.bne(S3, ZERO, "render_loop")
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


def _build_battle_result_draw_wrapper(
    result_widths: tuple[int, int, int],
) -> AssembledCode:
    """Render the private result owner's Codename and fixed item labels."""

    mode_name = 0
    mode_none = 1
    mode_life_stone = 2
    mode_bead = 3

    code = _Assembler(BATTLE_RESULT_DRAW_WRAPPER_ADDRESS)

    # Both name loops enter here. The live table also contains native rows, so
    # only row zero is decoded as packed English; every other row delegates one
    # glyph to the original C998 call.
    code.label("name_entry")
    code.addiu(T3, ZERO, mode_name)
    code.beq(ZERO, ZERO, "save")
    code.delay_nop()

    for label, mode in (
        ("none_entry", mode_none),
        ("life_stone_entry", mode_life_stone),
        ("bead_entry", mode_bead),
    ):
        code.label(label)
        code.addiu(T3, ZERO, mode)
        code.beq(ZERO, ZERO, "save")
        code.delay_nop()

    # The second stock cell for each fixed label must consume its relocated JAL
    # without drawing a ghost glyph.
    code.label("noop_entry")
    code.jr(RA)
    code.delay_nop()

    code.label("save")
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
    code.sw(A0, 0x00, SP)
    code.sw(A1, 0x04, SP)
    code.sw(A2, 0x08, SP)
    code.sw(T0, 0x0C, SP)
    code.sw(T3, 0x10, SP)
    code.sw(A3, 0x14, SP)

    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    _load_pc_relative_target(
        code,
        S4,
        RA,
        pc_address=pc_address,
        target_address=BATTLE_NAME_CODE_TABLE_ADDRESS,
    )
    _load_pc_relative_target(
        code,
        S5,
        RA,
        pc_address=pc_address,
        target_address=BATTLE_NAME_WIDTH_TABLE_ADDRESS,
    )
    _load_pc_relative_target(
        code,
        S6,
        RA,
        pc_address=pc_address,
        target_address=BATTLE_RESULT_STOCK_GLYPH_DRAW_ADDRESS,
    )

    code.lw(T3, 0x10, SP)
    code.beq(T3, ZERO, "select_name")
    code.delay_nop()
    code.addiu(T2, T3, -mode_none)
    code.beq(T2, ZERO, "select_none")
    code.delay_nop()
    code.addiu(T2, T3, -mode_life_stone)
    code.beq(T2, ZERO, "select_life_stone")
    code.delay_nop()
    code.beq(ZERO, ZERO, "select_bead")
    code.delay_nop()

    code.label("select_name")
    _load_pc_relative_target(
        code,
        T2,
        RA,
        pc_address=pc_address,
        target_address=BATTLE_RESULT_NAME_TABLE_POINTER_ADDRESS,
    )
    code.lw(T2, 0, T2)
    code.bne(S0, T2, "stock_glyph")
    code.delay_nop()
    code.bne(S1, ZERO, "return")
    code.delay_nop()
    code.addu(S2, S0, ZERO)
    code.addiu(S3, ZERO, BATTLE_NAME_STOCK_COUNT)
    code.lw(S1, 0x00, SP)
    code.beq(ZERO, ZERO, "render_loop")
    code.delay_nop()

    for label, offset, x in (
        ("select_none", BATTLE_RESULT_NONE_OFFSET, BATTLE_RESULT_NONE_X),
        (
            "select_life_stone",
            BATTLE_RESULT_LIFE_STONES_OFFSET,
            BATTLE_RESULT_LABEL_RIGHT_ANCHOR_X - result_widths[1],
        ),
        (
            "select_bead",
            BATTLE_RESULT_BEADS_OFFSET,
            BATTLE_RESULT_LABEL_RIGHT_ANCHOR_X - result_widths[2],
        ),
    ):
        code.label(label)
        _load_pc_relative_target(
            code,
            S2,
            RA,
            pc_address=pc_address,
            target_address=BATTLE_RESULT_STATIC_STORAGE_ADDRESS + offset,
        )
        code.addiu(S3, ZERO, BATTLE_RESULT_STATIC_RECORD_SIZE)
        code.addiu(S1, ZERO, x)
        code.beq(ZERO, ZERO, "render_loop")
        code.delay_nop()

    code.label("render_loop")
    code.beq(S3, ZERO, "return")
    code.delay_nop()
    code.lbu(T0, 0, S2)
    code.beq(T0, ZERO, "return")
    code.delay_nop()
    code.addiu(T1, T0, -PACKED_FIRST)
    code.sltiu(T2, T1, PACKED_WIDTH_COUNT)
    code.beq(T2, ZERO, "return")
    code.delay_nop()
    code.addu(T2, S4, T1)
    code.lbu(A3, 0, T2)
    code.addu(T2, S5, T1)
    code.lbu(T3, 0, T2)
    code.beq(T3, ZERO, "return")
    code.delay_nop()
    code.addiu(S2, S2, 1)
    code.addiu(S3, S3, -1)
    code.addu(A0, S1, ZERO)
    code.lw(A1, 0x04, SP)
    code.lw(A2, 0x08, SP)
    code.lw(T0, 0x0C, SP)
    code.addu(S1, S1, T3)
    code.beq(A3, ZERO, "render_loop")
    code.delay_nop()
    code.jalr(S6)
    code.delay_nop()
    code.beq(ZERO, ZERO, "render_loop")
    code.delay_nop()

    code.label("stock_glyph")
    code.lw(A0, 0x00, SP)
    code.lw(A1, 0x04, SP)
    code.lw(A2, 0x08, SP)
    code.lw(A3, 0x14, SP)
    code.lw(T0, 0x0C, SP)
    code.jalr(S6)
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


def build_battle_name_patch(source: BattleNamePatchSource) -> BattleNamePatch:
    """Compile the checked name source into two local battle-screen hooks."""

    codes, widths, static_storage, result_static_storage, result_widths = (
        _validate_source(source)
    )
    wrapper = _build_battle_name_draw_wrapper(
        len(static_storage),
        full_dvl_names=source.full_dvl_names,
    )
    result_wrapper = _build_battle_result_draw_wrapper(
        result_widths,
    )
    if wrapper.end_address > BATTLE_NAME_DRAW_WRAPPER_END_ADDRESS:
        raise ValueError("PSP battle-name wrapper exceeds its checked partition")
    if BATTLE_NAME_STATIC_STORAGE_ADDRESS + len(static_storage) > (
        BATTLE_NAME_CAVE_END_ADDRESS
    ):
        raise ValueError("PSP battle-name static row exceeds its checked partition")
    if result_wrapper.end_address > BATTLE_RESULT_STATIC_STORAGE_ADDRESS:
        raise ValueError("PSP battle-result wrapper exceeds its checked partition")
    if BATTLE_RESULT_STATIC_STORAGE_ADDRESS + len(result_static_storage) > (
        BATTLE_RESULT_CAVE_END_ADDRESS
    ):
        raise ValueError("PSP battle-result rows exceed their checked partition")

    writes = (
        PatchWrite(
            "battle_name_mode1_draw_call",
            BATTLE_NAME_MODE1_DRAW_CALL_ADDRESS,
            _word_bytes(
                _jal_word(
                    BATTLE_NAME_MODE1_DRAW_CALL_ADDRESS,
                    BATTLE_NAME_DRAW_WRAPPER_ADDRESS,
                )
            ),
        ),
        PatchWrite(
            "battle_name_mode1_loop_skip",
            BATTLE_NAME_MODE1_LOOP_SKIP_ADDRESS,
            _word_bytes(
                _branch_word(
                    BATTLE_NAME_MODE1_LOOP_SKIP_ADDRESS,
                    BATTLE_NAME_MODE1_CONTINUE_ADDRESS,
                ),
                0,
            ),
        ),
        PatchWrite(
            "battle_name_mode0_draw_call",
            BATTLE_NAME_MODE0_DRAW_CALL_ADDRESS,
            _word_bytes(
                _jal_word(
                    BATTLE_NAME_MODE0_DRAW_CALL_ADDRESS,
                    BATTLE_NAME_DRAW_WRAPPER_ADDRESS,
                )
            ),
        ),
        PatchWrite(
            "battle_name_mode0_loop_skip",
            BATTLE_NAME_MODE0_LOOP_SKIP_ADDRESS,
            _word_bytes(
                _branch_word(
                    BATTLE_NAME_MODE0_LOOP_SKIP_ADDRESS,
                    BATTLE_NAME_MODE0_CONTINUE_ADDRESS,
                ),
                0,
            ),
        ),
        PatchWrite(
            "battle_name_party_draw_call",
            BATTLE_NAME_PARTY_DRAW_CALL_ADDRESS,
            _word_bytes(
                _jal_word(
                    BATTLE_NAME_PARTY_DRAW_CALL_ADDRESS,
                    wrapper.label_address("party_entry"),
                )
            ),
        ),
        PatchWrite(
            "battle_name_party_loop_skip",
            BATTLE_NAME_PARTY_LOOP_SKIP_ADDRESS,
            _word_bytes(
                _branch_word(
                    BATTLE_NAME_PARTY_LOOP_SKIP_ADDRESS,
                    BATTLE_NAME_PARTY_CONTINUE_ADDRESS,
                ),
                0,
            ),
        ),
        PatchWrite(
            "battle_name_panel_mode1_draw_call",
            BATTLE_NAME_PANEL_MODE1_DRAW_CALL_ADDRESS,
            _word_bytes(
                _jal_word(
                    BATTLE_NAME_PANEL_MODE1_DRAW_CALL_ADDRESS,
                    BATTLE_NAME_DRAW_WRAPPER_ADDRESS,
                )
            ),
        ),
        PatchWrite(
            "battle_name_panel_mode1_loop_skip",
            BATTLE_NAME_PANEL_MODE1_LOOP_SKIP_ADDRESS,
            _word_bytes(
                _branch_word(
                    BATTLE_NAME_PANEL_MODE1_LOOP_SKIP_ADDRESS,
                    BATTLE_NAME_PANEL_MODE1_CONTINUE_ADDRESS,
                ),
                0,
            ),
        ),
        PatchWrite(
            "battle_name_panel_mode0_draw_call",
            BATTLE_NAME_PANEL_MODE0_DRAW_CALL_ADDRESS,
            _word_bytes(
                _jal_word(
                    BATTLE_NAME_PANEL_MODE0_DRAW_CALL_ADDRESS,
                    BATTLE_NAME_DRAW_WRAPPER_ADDRESS,
                )
            ),
        ),
        PatchWrite(
            "battle_name_panel_mode0_loop_skip",
            BATTLE_NAME_PANEL_MODE0_LOOP_SKIP_ADDRESS,
            _word_bytes(
                _branch_word(
                    BATTLE_NAME_PANEL_MODE0_LOOP_SKIP_ADDRESS,
                    BATTLE_NAME_PANEL_MODE0_CONTINUE_ADDRESS,
                ),
                0,
            ),
        ),
        PatchWrite(
            "battle_result_name_primary_draw_call",
            BATTLE_RESULT_NAME_PRIMARY_DRAW_CALL_ADDRESS,
            _word_bytes(
                _jal_word(
                    BATTLE_RESULT_NAME_PRIMARY_DRAW_CALL_ADDRESS,
                    result_wrapper.label_address("name_entry"),
                )
            ),
        ),
        PatchWrite(
            "battle_result_name_secondary_draw_call",
            BATTLE_RESULT_NAME_SECONDARY_DRAW_CALL_ADDRESS,
            _word_bytes(
                _jal_word(
                    BATTLE_RESULT_NAME_SECONDARY_DRAW_CALL_ADDRESS,
                    result_wrapper.label_address("name_entry"),
                )
            ),
        ),
        PatchWrite(
            "battle_result_life_stone_draw_call",
            BATTLE_RESULT_LIFE_STONE_DRAW_CALL_ADDRESS,
            _word_bytes(
                _jal_word(
                    BATTLE_RESULT_LIFE_STONE_DRAW_CALL_ADDRESS,
                    result_wrapper.label_address("life_stone_entry"),
                )
            ),
        ),
        PatchWrite(
            "battle_result_life_stone_continuation_draw_call",
            BATTLE_RESULT_LIFE_STONE_CONTINUATION_DRAW_CALL_ADDRESS,
            _word_bytes(
                _jal_word(
                    BATTLE_RESULT_LIFE_STONE_CONTINUATION_DRAW_CALL_ADDRESS,
                    result_wrapper.label_address("noop_entry"),
                )
            ),
        ),
        PatchWrite(
            "battle_result_bead_draw_call",
            BATTLE_RESULT_BEAD_DRAW_CALL_ADDRESS,
            _word_bytes(
                _jal_word(
                    BATTLE_RESULT_BEAD_DRAW_CALL_ADDRESS,
                    result_wrapper.label_address("bead_entry"),
                )
            ),
        ),
        PatchWrite(
            "battle_result_bead_continuation_draw_call",
            BATTLE_RESULT_BEAD_CONTINUATION_DRAW_CALL_ADDRESS,
            _word_bytes(
                _jal_word(
                    BATTLE_RESULT_BEAD_CONTINUATION_DRAW_CALL_ADDRESS,
                    result_wrapper.label_address("noop_entry"),
                )
            ),
        ),
        PatchWrite(
            "battle_result_none_draw_call",
            BATTLE_RESULT_NONE_DRAW_CALL_ADDRESS,
            _word_bytes(
                _jal_word(
                    BATTLE_RESULT_NONE_DRAW_CALL_ADDRESS,
                    result_wrapper.label_address("none_entry"),
                )
            ),
        ),
        PatchWrite(
            "battle_result_none_continuation_draw_call",
            BATTLE_RESULT_NONE_CONTINUATION_DRAW_CALL_ADDRESS,
            _word_bytes(
                _jal_word(
                    BATTLE_RESULT_NONE_CONTINUATION_DRAW_CALL_ADDRESS,
                    result_wrapper.label_address("noop_entry"),
                )
            ),
        ),
        PatchWrite("battle_name_draw_wrapper", wrapper.address, wrapper.data),
        PatchWrite(
            "battle_result_draw_wrapper",
            result_wrapper.address,
            result_wrapper.data,
        ),
        PatchWrite("battle_name_codes", BATTLE_NAME_CODE_TABLE_ADDRESS, codes),
        PatchWrite("battle_name_widths", BATTLE_NAME_WIDTH_TABLE_ADDRESS, widths),
        PatchWrite(
            "battle_name_mysterious_man",
            BATTLE_NAME_STATIC_STORAGE_ADDRESS,
            static_storage,
        ),
        PatchWrite(
            "battle_result_text",
            BATTLE_RESULT_STATIC_STORAGE_ADDRESS,
            result_static_storage,
        ),
    )
    ordered = tuple(sorted(writes, key=lambda write: write.address))
    for left, right in zip(ordered, ordered[1:]):
        if left.end_address > right.address:
            raise ValueError(
                f"PSP battle-name writes overlap: {left.name} and {right.name}"
            )
    return BattleNamePatch(
        wrapper,
        result_wrapper,
        codes,
        widths,
        static_storage,
        result_static_storage,
        writes,
    )


__all__ = (
    "BATTLE_NAME_CAVE_END_ADDRESS",
    "BATTLE_NAME_CODE_TABLE_ADDRESS",
    "BATTLE_NAME_DRAW_WRAPPER_ADDRESS",
    "BATTLE_NAME_DRAW_WRAPPER_END_ADDRESS",
    "BATTLE_NAME_FIELD_WIDTH",
    "BATTLE_NAME_FULL_DVL_MAX_LENGTH",
    "BATTLE_NAME_FULL_DVL_RECORD_COUNT",
    "BATTLE_NAME_FULL_DVL_SHADOWED_ID_FIRST",
    "BATTLE_NAME_FULL_DVL_SHADOWED_ID_LIMIT",
    "BATTLE_NAME_LAYER",
    "BATTLE_NAME_MODE0_CONTINUE_ADDRESS",
    "BATTLE_NAME_MODE0_DRAW_CALL_ADDRESS",
    "BATTLE_NAME_MODE0_LOOP_SKIP_ADDRESS",
    "BATTLE_NAME_MODE1_CONTINUE_ADDRESS",
    "BATTLE_NAME_MODE1_DRAW_CALL_ADDRESS",
    "BATTLE_NAME_MODE1_LOOP_SKIP_ADDRESS",
    "BATTLE_NAME_MYSTERIOUS_MAN_ID",
    "BATTLE_NAME_PANEL_MODE0_CONTINUE_ADDRESS",
    "BATTLE_NAME_PANEL_MODE0_DRAW_CALL_ADDRESS",
    "BATTLE_NAME_PANEL_MODE0_LOOP_SKIP_ADDRESS",
    "BATTLE_NAME_PANEL_MODE1_CONTINUE_ADDRESS",
    "BATTLE_NAME_PANEL_MODE1_DRAW_CALL_ADDRESS",
    "BATTLE_NAME_PANEL_MODE1_LOOP_SKIP_ADDRESS",
    "BATTLE_NAME_PARTY_CONTINUE_ADDRESS",
    "BATTLE_NAME_PARTY_DRAW_CALL_ADDRESS",
    "BATTLE_NAME_PARTY_LAYER",
    "BATTLE_NAME_PARTY_LOOP_SKIP_ADDRESS",
    "BATTLE_NAME_PLAYER_ID_FIRST",
    "BATTLE_NAME_PLAYER_ID_LIMIT",
    "BATTLE_NAME_STATIC_STORAGE_ADDRESS",
    "BATTLE_NAME_STATIC_STORAGE_MAX_SIZE",
    "BATTLE_NAME_STOCK_ADVANCE",
    "BATTLE_NAME_STOCK_COUNT",
    "BATTLE_NAME_STOCK_GLYPH_DRAW_ADDRESS",
    "BATTLE_NAME_STOCK_RESOLVER_ADDRESS",
    "BATTLE_NAME_WIDTH_TABLE_ADDRESS",
    "BATTLE_NAME_X",
    "BATTLE_NAME_Y",
    "BATTLE_RESULT_BEAD_CONTINUATION_DRAW_CALL_ADDRESS",
    "BATTLE_RESULT_BEAD_DRAW_CALL_ADDRESS",
    "BATTLE_RESULT_CAVE_END_ADDRESS",
    "BATTLE_RESULT_DRAW_WRAPPER_ADDRESS",
    "BATTLE_RESULT_LABEL_RIGHT_ANCHOR_X",
    "BATTLE_RESULT_LIFE_STONE_CONTINUATION_DRAW_CALL_ADDRESS",
    "BATTLE_RESULT_LIFE_STONE_DRAW_CALL_ADDRESS",
    "BATTLE_RESULT_NAME_PRIMARY_DRAW_CALL_ADDRESS",
    "BATTLE_RESULT_NAME_SECONDARY_DRAW_CALL_ADDRESS",
    "BATTLE_RESULT_NAME_TABLE_POINTER_ADDRESS",
    "BATTLE_RESULT_NONE_CONTINUATION_DRAW_CALL_ADDRESS",
    "BATTLE_RESULT_NONE_DRAW_CALL_ADDRESS",
    "BATTLE_RESULT_STATIC_STORAGE_ADDRESS",
    "BATTLE_RESULT_STOCK_GLYPH_DRAW_ADDRESS",
    "BattleNamePatch",
    "BattleNamePatchSource",
    "build_battle_name_patch",
    "validate_full_dvl_table",
)


