"""Proportional names for the common six-card party-card path.

The stock common owner resolves an eight-byte DVLNAME/CHARNAME pointer
and sends it through a fixed FONT8 loop.  This screen-local wrapper instead
classifies the original unit ID retained in the caller's frame, selects packed
English storage, and draws Ark Pixel 10 through the existing EVE glyph ABI.
Successful handles join the shared bounded UI-frame owner and are released
before the next visible-frame traversal.  The wrapper never changes the shared
stock resolver or its source tables.
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
    _jal_word,
    _load_pc_relative_target,
    _word_bytes,
)
from ..core.layout import (
    COMP_PARTY_NAME_CAVE_END_ADDRESS,
    COMP_PARTY_NAME_CHARACTER_TABLE_ADDRESS,
    COMP_PARTY_NAME_DRAW_WRAPPER_ADDRESS,
    COMP_PARTY_NAME_WIDTH_TABLE_ADDRESS,
    COMPENDIUM_NAME_TABLE_ADDRESS,
    COMPENDIUM_NAME_TABLE_SIZE,
    EVE_UI_HANDLE_APPEND_ADDRESS,
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
from .battle_names_runtime import BATTLE_NAME_STATIC_STORAGE_ADDRESS

COMP_PARTY_NAME_DRAW_CALL_ADDRESS = 0x0002B204
COMP_PARTY_NAME_STOCK_DRAW_ADDRESS = 0x0002AAE0
COMP_PARTY_NAME_EVE_GLYPH_DRAW_ADDRESS = 0x0009EEA8
COMP_PARTY_NAME_ARK10_FIRST_CODE = 0x1155
COMP_PARTY_NAME_ARK10_RUNTIME_BIAS = COMP_PARTY_NAME_ARK10_FIRST_CODE - PACKED_FIRST

# At 0x2B204 the active FUN_2B050 frame still owns the unit ID at sp+0x32.
# The replacement frame is 0x40 bytes, so the wrapper reads it at sp+0x72.
COMP_PARTY_NAME_CALLER_ID_OFFSET = 0x32
COMP_PARTY_NAME_WRAPPER_FRAME_SIZE = 0x40

COMP_PARTY_NAME_PRIMARY_PLAYER_ID = 0x8000
COMP_PARTY_NAME_CHARACTER_ID_FIRST = 0x8001
COMP_PARTY_NAME_CHARACTER_COUNT = 5
COMP_PARTY_NAME_CHARACTER_MAX_LENGTH = 16
COMP_PARTY_NAME_CHARACTER_TABLE_MAX_SIZE = (
    COMP_PARTY_NAME_CAVE_END_ADDRESS - COMP_PARTY_NAME_CHARACTER_TABLE_ADDRESS
)
COMP_PARTY_NAME_DVL_RECORD_COUNT = 319
COMP_PARTY_NAME_DVL_MAX_LENGTH = 16
COMP_PARTY_NAME_PLAYER_ID_FIRST = 0x0100
COMP_PARTY_NAME_PLAYER_ID_LIMIT = 0x0105
COMP_PARTY_NAME_MYSTERIOUS_MAN_ID = 0x0105
COMP_PARTY_NAME_CODENAME_MAX_LENGTH = 8
COMP_PARTY_NAME_COMMON_CALLER_ADDRESSES = (
    0x00029BA8,
    0x0003B7A4,
    0x000446C0,
    0x00044CDC,
    0x0004CF98,
    0x00051D1C,
)

# The retail cards are 128px wide.  Names begin six pixels inside the card;
# 112px leaves ten pixels at the right edge and is stricter than the actual
# production maxima with the dedicated Ark Pixel 10 face.
COMP_PARTY_NAME_CARD_WIDTH = 128
COMP_PARTY_NAME_X_INSET = 6
COMP_PARTY_NAME_FIELD_WIDTH = 112
COMP_PARTY_NAME_RIGHT_INSET = (
    COMP_PARTY_NAME_CARD_WIDTH - COMP_PARTY_NAME_X_INSET - COMP_PARTY_NAME_FIELD_WIDTH
)

# Ark10 descenders occupy through cell row 11, while the HP sprite has opaque
# ink from its first row at card y+14.  A card-relative y inset of two leaves
# the final name pixel at y+13 while preserving the HP row.
COMP_PARTY_NAME_STOCK_Y_INSET = 5
COMP_PARTY_NAME_Y_INSET = 2
COMP_PARTY_NAME_HP_Y_INSET = 14
COMP_PARTY_NAME_EVE_ORIGIN_X = 72
COMP_PARTY_NAME_EVE_ORIGIN_Y = 24
COMP_PARTY_NAME_LAYER = 7
COMP_PARTY_NAME_NORMAL_TINT = 0xFFFFFFFF
COMP_PARTY_NAME_SELECTED_TINT = 0xFF0000FF

COMP_PARTY_NAME_OFFSET_TABLE_SIZE = COMP_PARTY_NAME_CHARACTER_COUNT * 2


@dataclass(frozen=True)
class CompPartyPanelPatchSource:
    """Packed name owners and the private Ark10 advance projection."""

    character_names: tuple[str, ...]
    codename_characters: str
    mysterious_man: str
    dvlname_table: bytes
    packed_glyph_advances: Iterable[int]


@dataclass(frozen=True)
class CompPartyPanelPatch:
    """Every isolated write owned by the COMP party-card name consumer."""

    draw_wrapper: AssembledCode
    character_table: bytes
    width_table: bytes
    writes: tuple[PatchWrite, ...]

    def write(self, name: str) -> PatchWrite:
        try:
            return next(write for write in self.writes if write.name == name)
        except StopIteration as error:
            raise KeyError(f"unknown PSP COMP party-panel write: {name}") from error


def _validate_table(values: Iterable[int], context: str) -> bytes:
    try:
        resolved = tuple(values)
    except TypeError as error:
        raise TypeError(f"PSP COMP party-name {context} must be iterable") from error
    if len(resolved) != PACKED_WIDTH_COUNT:
        raise ValueError(
            f"PSP COMP party-name {context} has {len(resolved)} entries; "
            f"expected {PACKED_WIDTH_COUNT}"
        )
    if any(
        not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 0xFF
        for value in resolved
    ):
        raise ValueError(f"PSP COMP party-name {context} must contain u8 integers")
    return bytes(resolved)


def _encode_checked(
    value: str,
    *,
    context: str,
    maximum: int,
    widths: bytes,
) -> bytes:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or any(not 0x20 <= ord(character) <= 0x7E for character in value)
    ):
        raise ValueError(
            f"PSP {context} must contain 1..{maximum} printable ASCII characters"
        )
    encoded = bytes(
        PACKED_FIRST + _packed_storage_index(character) for character in value
    )
    for byte in encoded:
        index = byte - PACKED_FIRST
        if widths[index] == 0:
            raise ValueError(f"PSP {context} contains an unmapped Ark10 glyph")
    width = sum(widths[value - PACKED_FIRST] for value in encoded)
    if width > COMP_PARTY_NAME_FIELD_WIDTH:
        raise ValueError(
            f"PSP {context} is {width}px; field width is "
            f"{COMP_PARTY_NAME_FIELD_WIDTH}px"
        )
    return encoded


def _validate_dvlname_table(table: bytes, widths: bytes) -> None:
    if not isinstance(table, bytes):
        raise TypeError("PSP COMP DVLNAME table must be bytes")
    if len(table) != COMPENDIUM_NAME_TABLE_SIZE:
        raise ValueError(
            f"PSP COMP DVLNAME table is {len(table)} bytes; "
            f"expected {COMPENDIUM_NAME_TABLE_SIZE}"
        )
    offset_table_size = COMP_PARTY_NAME_DVL_RECORD_COUNT * 2
    pool_starts: set[int] = set()
    cursor = offset_table_size
    while cursor < len(table):
        pool_starts.add(cursor)
        terminator = table.find(b"\0", cursor)
        if terminator < 0:
            raise ValueError("PSP COMP DVLNAME pool has an unterminated row")
        cursor = terminator + 1
    offsets = tuple(
        int.from_bytes(table[index : index + 2], "little")
        for index in range(0, offset_table_size, 2)
    )
    if set(offsets) != pool_starts:
        raise ValueError("PSP COMP DVLNAME offsets do not own the complete pool")
    for row_index, offset in enumerate(offsets):
        terminator = table.index(0, offset)
        encoded = table[offset:terminator]
        if not encoded or len(encoded) > COMP_PARTY_NAME_DVL_MAX_LENGTH:
            raise ValueError(f"PSP COMP DVLNAME row {row_index} has invalid length")
        width = 0
        for byte in encoded:
            if not PACKED_FIRST <= byte < PACKED_FIRST + PACKED_WIDTH_COUNT:
                raise ValueError(
                    f"PSP COMP DVLNAME row {row_index} has an unsupported byte"
                )
            index = byte - PACKED_FIRST
            if widths[index] == 0:
                raise ValueError(
                    f"PSP COMP DVLNAME row {row_index} uses an unsupported Ark10 glyph"
                )
            width += widths[index]
        if width > COMP_PARTY_NAME_FIELD_WIDTH:
            raise ValueError(
                f"PSP COMP DVLNAME row {row_index} is {width}px; "
                f"field width is {COMP_PARTY_NAME_FIELD_WIDTH}px"
            )


def _validate_source(
    source: CompPartyPanelPatchSource,
) -> tuple[bytes, bytes]:
    if not isinstance(source, CompPartyPanelPatchSource):
        raise TypeError("PSP COMP party-panel source has the wrong type")
    widths = _validate_table(source.packed_glyph_advances, "width table")
    space_index = _packed_storage_index(" ")
    if widths[space_index] == 0:
        raise ValueError("PSP COMP party-name space mapping changed")
    if any(width == 0 for width in widths):
        raise ValueError("PSP COMP Ark10 advances must map every packed glyph")

    if (
        not isinstance(source.character_names, tuple)
        or len(source.character_names) != COMP_PARTY_NAME_CHARACTER_COUNT
    ):
        raise ValueError(
            f"PSP COMP CHARNAME source must contain "
            f"{COMP_PARTY_NAME_CHARACTER_COUNT} rows"
        )
    encoded_names = tuple(
        _encode_checked(
            value,
            context=f"COMP CHARNAME row {index}",
            maximum=COMP_PARTY_NAME_CHARACTER_MAX_LENGTH,
            widths=widths,
        )
        for index, value in enumerate(source.character_names)
    )

    codename_characters = source.codename_characters
    if (
        not isinstance(codename_characters, str)
        or not codename_characters
        or len(set(codename_characters)) != len(codename_characters)
    ):
        raise ValueError("PSP COMP Codename alphabet must contain unique characters")
    for character in codename_characters:
        _encode_checked(
            character,
            context="COMP Codename alphabet",
            maximum=1,
            widths=widths,
        )
    _encode_checked(
        source.mysterious_man,
        context="COMP Mysterious Man",
        maximum=COMP_PARTY_NAME_CHARACTER_MAX_LENGTH,
        widths=widths,
    )
    widest_codename = (
        max(
            widths[_packed_storage_index(character)]
            for character in codename_characters
        )
        * COMP_PARTY_NAME_CODENAME_MAX_LENGTH
    )
    if widest_codename > COMP_PARTY_NAME_FIELD_WIDTH:
        raise ValueError(
            f"PSP COMP reachable Codename is {widest_codename}px; field width is "
            f"{COMP_PARTY_NAME_FIELD_WIDTH}px"
        )

    _validate_dvlname_table(source.dvlname_table, widths)

    pool = bytearray()
    offsets: list[int] = []
    for encoded in encoded_names:
        offsets.append(COMP_PARTY_NAME_OFFSET_TABLE_SIZE + len(pool))
        pool.extend(encoded)
        pool.append(0)
    table = b"".join(offset.to_bytes(2, "little") for offset in offsets) + bytes(pool)
    if len(table) > COMP_PARTY_NAME_CHARACTER_TABLE_MAX_SIZE:
        raise ValueError("PSP COMP CHARNAME table exceeds its checked partition")
    return widths, table


def _build_draw_wrapper() -> AssembledCode:
    code = _Assembler(COMP_PARTY_NAME_DRAW_WRAPPER_ADDRESS)
    code.addiu(SP, SP, -COMP_PARTY_NAME_WRAPPER_FRAME_SIZE)
    code.sw(A0, 0x00, SP)
    code.sw(A1, 0x04, SP)
    code.sw(A2, 0x08, SP)
    code.sw(RA, 0x3C, SP)
    code.sw(S0, 0x38, SP)
    code.sw(S1, 0x34, SP)
    code.sw(S2, 0x30, SP)
    code.sw(S3, 0x2C, SP)
    code.sw(S4, 0x28, SP)
    code.sw(S5, 0x24, SP)
    code.sw(S6, 0x20, SP)
    code.sw(S7, 0x1C, SP)
    code.lhu(
        S0,
        COMP_PARTY_NAME_WRAPPER_FRAME_SIZE + COMP_PARTY_NAME_CALLER_ID_OFFSET,
        SP,
    )

    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    _load_pc_relative_target(
        code,
        S4,
        RA,
        pc_address=pc_address,
        target_address=COMP_PARTY_NAME_WIDTH_TABLE_ADDRESS,
    )
    _load_pc_relative_target(
        code,
        S5,
        RA,
        pc_address=pc_address,
        target_address=COMP_PARTY_NAME_EVE_GLYPH_DRAW_ADDRESS,
    )
    _load_pc_relative_target(
        code,
        S6,
        RA,
        pc_address=pc_address,
        target_address=EVE_UI_HANDLE_APPEND_ADDRESS,
    )

    # The stock negative resolver maps 0x8000 to runtime CHARNAME row zero,
    # which PPST confirms is a mutable WWWWWWWW mirror rather than static
    # Hajime text.  The original English bug replaced that row with private
    # static CHARNAME row zero.  This consumer instead reads canonical profile
    # +0x10 directly, avoiding dependence on the mutable +0x34 mirror. Positive
    # profile IDs arrive with their resolved mirror pointer in a0.
    code.ori(T0, ZERO, COMP_PARTY_NAME_PRIMARY_PLAYER_ID)
    code.beq(S0, T0, "primary_codename")
    code.delay_nop()
    code.addiu(T0, S0, -COMP_PARTY_NAME_PLAYER_ID_FIRST)
    code.sltiu(
        T1,
        T0,
        COMP_PARTY_NAME_PLAYER_ID_LIMIT - COMP_PARTY_NAME_PLAYER_ID_FIRST,
    )
    code.bne(T1, ZERO, "codename")
    code.delay_nop()
    code.ori(T0, ZERO, COMP_PARTY_NAME_MYSTERIOUS_MAN_ID)
    code.beq(S0, T0, "mysterious_man")
    code.delay_nop()

    code.addiu(T0, S0, -COMP_PARTY_NAME_PRIMARY_PLAYER_ID)
    code.addiu(T0, T0, -1)
    code.sltiu(T1, T0, COMP_PARTY_NAME_CHARACTER_COUNT)
    code.bne(T1, ZERO, "character_name")
    code.delay_nop()

    code.addiu(T0, S0, -1)
    code.sltiu(T1, T0, COMP_PARTY_NAME_DVL_RECORD_COUNT)
    code.beq(T1, ZERO, "fallback")
    code.delay_nop()
    code.sll(T0, T0, 1)
    _load_pc_relative_target(
        code,
        T2,
        RA,
        pc_address=pc_address,
        target_address=COMPENDIUM_NAME_TABLE_ADDRESS,
    )
    code.addu(T0, T2, T0)
    code.lhu(T0, 0, T0)
    code.addu(S3, T2, T0)
    code.addiu(S7, ZERO, COMP_PARTY_NAME_DVL_MAX_LENGTH)
    code.beq(ZERO, ZERO, "render_setup")
    code.delay_nop()

    code.label("character_name")
    code.sll(T0, T0, 1)
    _load_pc_relative_target(
        code,
        T2,
        RA,
        pc_address=pc_address,
        target_address=COMP_PARTY_NAME_CHARACTER_TABLE_ADDRESS,
    )
    code.addu(T0, T2, T0)
    code.lhu(T0, 0, T0)
    code.addu(S3, T2, T0)
    code.addiu(S7, ZERO, COMP_PARTY_NAME_CHARACTER_MAX_LENGTH)
    code.beq(ZERO, ZERO, "render_setup")
    code.delay_nop()

    code.label("codename")
    code.lw(S3, 0x00, SP)
    code.addiu(S7, ZERO, COMP_PARTY_NAME_CODENAME_MAX_LENGTH)
    code.beq(ZERO, ZERO, "render_setup")
    code.delay_nop()

    code.label("primary_codename")
    _load_pc_relative_target(
        code,
        S3,
        RA,
        pc_address=pc_address,
        target_address=(NAME_PROFILE_ADDRESS + NAME_PROFILE_FIELD_OFFSETS["codename"]),
    )
    code.addiu(S7, ZERO, COMP_PARTY_NAME_CODENAME_MAX_LENGTH)
    code.beq(ZERO, ZERO, "render_setup")
    code.delay_nop()

    code.label("mysterious_man")
    _load_pc_relative_target(
        code,
        S3,
        RA,
        pc_address=pc_address,
        target_address=BATTLE_NAME_STATIC_STORAGE_ADDRESS,
    )
    code.addiu(S7, ZERO, COMP_PARTY_NAME_CHARACTER_MAX_LENGTH)

    code.label("render_setup")
    code.lw(T2, 0x04, SP)
    code.lhu(S1, 0, T2)
    code.lhu(S2, 2, T2)
    code.addiu(
        S1,
        S1,
        COMP_PARTY_NAME_EVE_ORIGIN_X + COMP_PARTY_NAME_X_INSET,
    )
    code.addiu(
        S2,
        S2,
        COMP_PARTY_NAME_EVE_ORIGIN_Y + COMP_PARTY_NAME_Y_INSET,
    )
    code.addiu(T0, ZERO, -1)
    code.lw(T2, 0x08, SP)
    code.andi(T2, T2, 0xFF)
    code.addiu(T1, ZERO, 5)
    code.bne(T2, T1, "tint_ready")
    code.delay_nop()
    code.lui(T0, COMP_PARTY_NAME_SELECTED_TINT >> 16)
    code.ori(T0, T0, COMP_PARTY_NAME_SELECTED_TINT & 0xFFFF)
    code.label("tint_ready")
    code.sw(T0, 0x0C, SP)

    code.label("render_loop")
    code.beq(S7, ZERO, "return")
    code.delay_nop()
    code.lbu(T0, 0, S3)
    code.beq(T0, ZERO, "return")
    code.delay_nop()
    code.addiu(T1, T0, -PACKED_FIRST)
    code.sltiu(T2, T1, PACKED_WIDTH_COUNT)
    code.beq(T2, ZERO, "return")
    code.delay_nop()
    code.addu(T2, S4, T1)
    code.lbu(T3, 0, T2)
    code.beq(T3, ZERO, "return")
    code.delay_nop()
    code.addu(A0, S1, ZERO)
    code.addu(A1, S2, ZERO)
    code.addiu(A2, T0, COMP_PARTY_NAME_ARK10_RUNTIME_BIAS)
    code.addiu(A3, ZERO, COMP_PARTY_NAME_LAYER)
    code.lw(T0, 0x0C, SP)
    code.addiu(T1, ZERO, 1)
    code.addu(T2, ZERO, ZERO)
    code.addiu(S3, S3, 1)
    code.addiu(S7, S7, -1)
    code.addu(S1, S1, T3)
    code.jalr(S5)
    code.delay_nop()
    code.addu(A0, V0, ZERO)
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
        target_address=COMP_PARTY_NAME_STOCK_DRAW_ADDRESS,
    )
    code.lw(A0, 0x00, SP)
    code.lw(A1, 0x04, SP)
    code.lw(A2, 0x08, SP)
    code.jalr(S4)
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
    code.addiu(SP, SP, COMP_PARTY_NAME_WRAPPER_FRAME_SIZE)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def build_comp_party_panel_patch(
    source: CompPartyPanelPatchSource,
) -> CompPartyPanelPatch:
    """Compile the shared six-card callsite and its private Ark10 data."""

    widths, character_table = _validate_source(source)
    wrapper = _build_draw_wrapper()
    if wrapper.end_address > COMP_PARTY_NAME_WIDTH_TABLE_ADDRESS:
        raise ValueError("PSP COMP party-name wrapper exceeds its checked partition")
    if (
        COMP_PARTY_NAME_WIDTH_TABLE_ADDRESS + len(widths)
        > COMP_PARTY_NAME_CHARACTER_TABLE_ADDRESS
    ):
        raise ValueError("PSP COMP Ark10 widths exceed their checked partition")
    if (
        COMP_PARTY_NAME_CHARACTER_TABLE_ADDRESS + len(character_table)
        > COMP_PARTY_NAME_CAVE_END_ADDRESS
    ):
        raise ValueError("PSP COMP CHARNAME table exceeds its checked partition")
    writes = (
        PatchWrite(
            "comp_party_name_draw_call",
            COMP_PARTY_NAME_DRAW_CALL_ADDRESS,
            _word_bytes(
                _jal_word(
                    COMP_PARTY_NAME_DRAW_CALL_ADDRESS,
                    COMP_PARTY_NAME_DRAW_WRAPPER_ADDRESS,
                )
            ),
        ),
        PatchWrite(
            "comp_party_name_draw_wrapper",
            wrapper.address,
            wrapper.data,
        ),
        PatchWrite(
            "comp_party_name_widths",
            COMP_PARTY_NAME_WIDTH_TABLE_ADDRESS,
            widths,
        ),
        PatchWrite(
            "comp_party_character_names",
            COMP_PARTY_NAME_CHARACTER_TABLE_ADDRESS,
            character_table,
        ),
    )
    ordered = tuple(sorted(writes, key=lambda write: write.address))
    for left, right in zip(ordered, ordered[1:]):
        if left.end_address > right.address:
            raise ValueError(
                f"PSP COMP party-name writes overlap: {left.name} and {right.name}"
            )
    return CompPartyPanelPatch(wrapper, character_table, widths, writes)


__all__ = (
    "COMP_PARTY_NAME_ARK10_FIRST_CODE",
    "COMP_PARTY_NAME_ARK10_RUNTIME_BIAS",
    "COMP_PARTY_NAME_CALLER_ID_OFFSET",
    "COMP_PARTY_NAME_CARD_WIDTH",
    "COMP_PARTY_NAME_CHARACTER_COUNT",
    "COMP_PARTY_NAME_CHARACTER_ID_FIRST",
    "COMP_PARTY_NAME_CHARACTER_MAX_LENGTH",
    "COMP_PARTY_NAME_CHARACTER_TABLE_MAX_SIZE",
    "COMP_PARTY_NAME_CODENAME_MAX_LENGTH",
    "COMP_PARTY_NAME_COMMON_CALLER_ADDRESSES",
    "COMP_PARTY_NAME_DRAW_CALL_ADDRESS",
    "COMP_PARTY_NAME_DVL_MAX_LENGTH",
    "COMP_PARTY_NAME_DVL_RECORD_COUNT",
    "COMP_PARTY_NAME_EVE_GLYPH_DRAW_ADDRESS",
    "COMP_PARTY_NAME_EVE_ORIGIN_X",
    "COMP_PARTY_NAME_EVE_ORIGIN_Y",
    "COMP_PARTY_NAME_FIELD_WIDTH",
    "COMP_PARTY_NAME_HP_Y_INSET",
    "COMP_PARTY_NAME_LAYER",
    "COMP_PARTY_NAME_MYSTERIOUS_MAN_ID",
    "COMP_PARTY_NAME_NORMAL_TINT",
    "COMP_PARTY_NAME_OFFSET_TABLE_SIZE",
    "COMP_PARTY_NAME_PLAYER_ID_FIRST",
    "COMP_PARTY_NAME_PLAYER_ID_LIMIT",
    "COMP_PARTY_NAME_PRIMARY_PLAYER_ID",
    "COMP_PARTY_NAME_RIGHT_INSET",
    "COMP_PARTY_NAME_SELECTED_TINT",
    "COMP_PARTY_NAME_STOCK_DRAW_ADDRESS",
    "COMP_PARTY_NAME_STOCK_Y_INSET",
    "COMP_PARTY_NAME_WRAPPER_FRAME_SIZE",
    "COMP_PARTY_NAME_X_INSET",
    "COMP_PARTY_NAME_Y_INSET",
    "CompPartyPanelPatch",
    "CompPartyPanelPatchSource",
    "build_comp_party_panel_patch",
)


