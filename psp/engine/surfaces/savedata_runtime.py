"""Allegrex emitter for the PSP save/load metadata surface."""

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
    V1,
    ZERO,
    AssembledCode,
    PatchWrite,
    _Assembler,
    _branch_word,
    _i_type,
    _load_pc_relative_target,
    _word_bytes,
)
from ..core.layout import (
    DATA_LOAD_SEGMENT_ADDRESS,
    ITEM_DESCRIPTION_DRAW_WRAPPER_ADDRESS,
    ITEM_RUNTIME_DATA_ADDRESS,
    NAME_FIELD_MAX,
    NAME_PROFILE_ADDRESS,
    NAME_PROFILE_FIELD_OFFSETS,
    SAVEDATA_DETAIL_WRAPPER_ADDRESS,
    SAVEDATA_LOCATION_ID_TABLE_ADDRESS,
    SAVEDATA_LOCATION_NAME_COUNT,
    SAVEDATA_LOCATION_RECORD_COUNT,
)
from psp.text.util.event_packed import (
    STORED_SPACE as PACKED_LAST,
    validate_printable_ascii,
)

SAVEDATA_LANGUAGE_LOAD_ADDRESS = 0x0000EE98


SAVEDATA_LANGUAGE_STORE_ADDRESS = 0x0000EEA0


SAVEDATA_GAME_TITLE_ADDRESS = 0x000EC334


SAVEDATA_GAME_TITLE_SIZE = 0x10


SAVEDATA_SLOT_TITLE_ADDRESS = 0x000EC344


SAVEDATA_SLOT_TITLE_SIZE = 0x1C


SAVEDATA_CANCEL_LOAD_ADDRESS = 0x000EC434


SAVEDATA_CANCEL_SAVE_ADDRESS = 0x000EC45C


SAVEDATA_CANCEL_PROMPT_SIZE = 0x28


SAVEDATA_DETAIL_FUNCTION_ADDRESS = 0x0001163C


SAVEDATA_DETAIL_TRAMPOLINE_ADDRESS = 0x0001164C


SAVEDATA_DETAIL_BUFFER_RAW_ADDRESS = 0x00076244


SAVEDATA_DETAIL_BUFFER_ADDRESS = (
    DATA_LOAD_SEGMENT_ADDRESS + SAVEDATA_DETAIL_BUFFER_RAW_ADDRESS
)


SAVEDATA_ELAPSED_TIME_ADDRESS = 0x0000C480


SAVEDATA_PLAYTIME_RAW_ADDRESS = 0x000543E4


SAVEDATA_PLAYTIME_ADDRESS = DATA_LOAD_SEGMENT_ADDRESS + SAVEDATA_PLAYTIME_RAW_ADDRESS


SAVEDATA_LEVEL_RAW_ADDRESS = 0x003DF646


SAVEDATA_LEVEL_ADDRESS = DATA_LOAD_SEGMENT_ADDRESS + SAVEDATA_LEVEL_RAW_ADDRESS


SAVEDATA_DIFFICULTY_RAW_ADDRESS = 0x003F6DB0


SAVEDATA_DIFFICULTY_ADDRESS = (
    DATA_LOAD_SEGMENT_ADDRESS + SAVEDATA_DIFFICULTY_RAW_ADDRESS
)


SAVEDATA_TABLE_CAVE_SOURCE_START_ADDRESS = 0x0010872E


SAVEDATA_LOCATION_OFFSET_TABLE_ADDRESS = 0x001087C0


SAVEDATA_TEXT_BLOB_ADDRESS = 0x001087F0


SAVEDATA_TABLE_CAVE_END_ADDRESS = ITEM_RUNTIME_DATA_ADDRESS


SAVEDATA_LOCATION_TEXT_BLOB_ADDRESS = 0x00175488


SAVEDATA_LOCATION_TEXT_CAVE_END_ADDRESS = 0x001755CC


@dataclass(frozen=True)
class SavedataPatchSource:
    """English SFO prose before PSP selector/table compilation."""

    game_title: str
    slot_title: str
    detail_title: str
    difficulties: tuple[str, str]
    cancel_load: str
    cancel_save: str
    home: str
    office: str
    unknown: str
    locations: tuple[str, ...]


@dataclass(frozen=True)
class SavedataPatch:
    """English savedata utility language and SFO detail formatter."""

    detail_trampoline: AssembledCode
    detail_wrapper: AssembledCode
    location_ids: bytes
    location_offsets: bytes
    text_blob: bytes
    location_text_blob: bytes
    writes: tuple[PatchWrite, ...]

    def write(self, name: str) -> PatchWrite:
        try:
            return next(write for write in self.writes if write.name == name)
        except StopIteration as error:
            raise KeyError(f"unknown Allegrex savedata write: {name}") from error


def _savedata_ascii(value: object, context: str) -> str:
    return validate_printable_ascii(value, f"PSP savedata {context}")


def _savedata_fixed_ascii(value: object, size: int, context: str) -> bytes:
    text = _savedata_ascii(value, context)
    encoded = text.encode("ascii") + b"\0"
    if len(encoded) > size:
        raise ValueError(f"PSP savedata {context} exceeds its {size}-byte field")
    return encoded.ljust(size, b"\0")


def _build_savedata_detail_trampoline() -> AssembledCode:
    """Reach the far formatter without an ELF R_MIPS_26 relocation.

    The stock entry's first eight bytes can hold only a nearby branch.  The
    trampoline occupies an unreachable relocation-free slice of the replaced
    function body, derives the module load base from BAL, restores the caller's
    return address, and tail-jumps to the second-cave wrapper.
    """

    code = _Assembler(SAVEDATA_DETAIL_TRAMPOLINE_ADDRESS)
    code.addu(T9, RA, ZERO)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    _load_pc_relative_target(
        code,
        T8,
        RA,
        pc_address=pc_address,
        target_address=SAVEDATA_DETAIL_WRAPPER_ADDRESS,
    )
    code.addu(RA, T9, ZERO)
    code.jr(T8)
    code.delay_nop()
    return code.finish()


def _build_savedata_detail_wrapper(
    text_offsets: Mapping[str, int],
) -> AssembledCode:
    """Build the live PSP SFO detail from translated profile/game state."""

    code = _Assembler(SAVEDATA_DETAIL_WRAPPER_ADDRESS)
    code.addiu(SP, SP, -0x10)
    code.sw(RA, 0x0C, SP)
    code.sw(A0, 0x08, SP)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    code.addu(T8, RA, ZERO)

    # Match the stock formatter's playtime source: accumulated seconds plus
    # the live elapsed-time helper's current-session contribution.
    _load_pc_relative_target(
        code,
        T6,
        T8,
        pc_address=pc_address,
        target_address=SAVEDATA_ELAPSED_TIME_ADDRESS,
    )
    code.sw(T8, 0x04, SP)
    code.jalr(T6)
    code.delay_nop()
    code.lw(T8, 0x04, SP)
    _load_pc_relative_target(
        code,
        T6,
        T8,
        pc_address=pc_address,
        target_address=SAVEDATA_PLAYTIME_ADDRESS,
    )
    code.lw(T7, 0, T6)
    code.addu(V0, V0, T7)
    code.sw(V0, 0, SP)

    _load_pc_relative_target(
        code,
        T0,
        T8,
        pc_address=pc_address,
        target_address=SAVEDATA_DETAIL_BUFFER_ADDRESS,
    )
    _load_pc_relative_target(
        code,
        T1,
        T8,
        pc_address=pc_address,
        target_address=NAME_PROFILE_ADDRESS,
    )
    _load_pc_relative_target(
        code,
        T2,
        T8,
        pc_address=pc_address,
        target_address=SAVEDATA_LOCATION_ID_TABLE_ADDRESS,
    )
    _load_pc_relative_target(
        code,
        T3,
        T8,
        pc_address=pc_address,
        target_address=SAVEDATA_LOCATION_OFFSET_TABLE_ADDRESS,
    )
    _load_pc_relative_target(
        code,
        T4,
        T8,
        pc_address=pc_address,
        target_address=SAVEDATA_TEXT_BLOB_ADDRESS,
    )
    _load_pc_relative_target(
        code,
        T5,
        T8,
        pc_address=pc_address,
        target_address=SAVEDATA_LOCATION_TEXT_BLOB_ADDRESS,
    )
    code.lw(A3, 0x08, SP)

    code.addiu(T6, T4, text_offsets["detail_title"])
    code.label("copy_title")
    code.lbu(V0, 0, T6)
    code.beq(V0, ZERO, "title_done")
    code.delay_nop()
    code.sb(V0, 0, T0)
    code.addiu(T6, T6, 1)
    code.addiu(T0, T0, 1)
    code.beq(ZERO, ZERO, "copy_title")
    code.delay_nop()

    code.label("title_done")
    code.addiu(V0, ZERO, 0x0A)
    code.sb(V0, 0, T0)
    code.addiu(T0, T0, 1)
    code.addiu(T6, T1, NAME_PROFILE_FIELD_OFFSETS["codename"])
    code.addu(T7, ZERO, ZERO)

    code.label("copy_codename")
    code.sltiu(V1, T7, NAME_FIELD_MAX)
    code.beq(V1, ZERO, "codename_done")
    code.delay_nop()
    code.lbu(V0, 0, T6)
    code.beq(V0, ZERO, "codename_done")
    code.delay_nop()
    code.sltiu(V1, V0, 0x6E)
    code.bne(V1, ZERO, "codename_core")
    code.delay_nop()
    code.addiu(V1, ZERO, PACKED_LAST)
    code.beq(V0, V1, "codename_space")
    code.delay_nop()
    code.addiu(V0, V0, -0x4D)
    code.beq(ZERO, ZERO, "codename_store")
    code.delay_nop()
    code.label("codename_core")
    code.addiu(V0, V0, 0x11)
    code.beq(ZERO, ZERO, "codename_store")
    code.delay_nop()
    code.label("codename_space")
    code.addiu(V0, ZERO, 0x20)
    code.label("codename_store")
    code.sb(V0, 0, T0)
    code.addiu(T0, T0, 1)
    code.addiu(T6, T6, 1)
    code.addiu(T7, T7, 1)
    code.beq(ZERO, ZERO, "copy_codename")
    code.delay_nop()

    code.label("codename_done")
    code.addiu(T6, T4, text_offsets["level_prefix"])
    code.label("copy_level_prefix")
    code.lbu(V0, 0, T6)
    code.beq(V0, ZERO, "level_prefix_done")
    code.delay_nop()
    code.sb(V0, 0, T0)
    code.addiu(T6, T6, 1)
    code.addiu(T0, T0, 1)
    code.beq(ZERO, ZERO, "copy_level_prefix")
    code.delay_nop()

    code.label("level_prefix_done")
    _load_pc_relative_target(
        code,
        T6,
        T8,
        pc_address=pc_address,
        target_address=SAVEDATA_LEVEL_ADDRESS,
    )
    code.lhu(V1, 0, T6)
    code.addiu(A0, ZERO, 10)
    code.divu(V1, A0)
    code.mflo(T7)
    code.mfhi(V1)
    code.beq(T7, ZERO, "level_ones")
    code.delay_nop()
    code.addiu(T7, T7, 0x30)
    code.sb(T7, 0, T0)
    code.addiu(T0, T0, 1)
    code.label("level_ones")
    code.addiu(V1, V1, 0x30)
    code.sb(V1, 0, T0)
    code.addiu(T0, T0, 1)

    code.addiu(V0, ZERO, 0x20)
    code.sb(V0, 0, T0)
    code.addiu(T0, T0, 1)
    code.addiu(V0, ZERO, 0x28)
    code.sb(V0, 0, T0)
    code.addiu(T0, T0, 1)
    _load_pc_relative_target(
        code,
        T6,
        T8,
        pc_address=pc_address,
        target_address=SAVEDATA_DIFFICULTY_ADDRESS,
    )
    code.lw(V0, 0, T6)
    code.beq(V0, ZERO, "difficulty_normal")
    code.delay_nop()
    code.addiu(T6, T4, text_offsets["difficulty_hard"])
    code.beq(ZERO, ZERO, "copy_difficulty")
    code.delay_nop()
    code.label("difficulty_normal")
    code.addiu(T6, T4, text_offsets["difficulty_normal"])

    code.label("copy_difficulty")
    code.lbu(V0, 0, T6)
    code.beq(V0, ZERO, "difficulty_done")
    code.delay_nop()
    code.sb(V0, 0, T0)
    code.addiu(T6, T6, 1)
    code.addiu(T0, T0, 1)
    code.beq(ZERO, ZERO, "copy_difficulty")
    code.delay_nop()

    code.label("difficulty_done")
    code.addiu(V0, ZERO, 0x29)
    code.sb(V0, 0, T0)
    code.addiu(T0, T0, 1)
    code.addiu(V0, ZERO, 0x0A)
    code.sb(V0, 0, T0)
    code.addiu(T0, T0, 1)

    code.andi(A0, A3, 0x200)
    code.bne(A0, ZERO, "location_home")
    code.delay_nop()
    code.andi(A0, A3, 0x100)
    code.bne(A0, ZERO, "location_office")
    code.delay_nop()
    code.andi(A0, A3, 0xFF)
    code.sltiu(V0, A0, SAVEDATA_LOCATION_RECORD_COUNT)
    code.beq(V0, ZERO, "location_unknown")
    code.delay_nop()
    code.addu(T6, T2, A0)
    code.lbu(V0, 0, T6)
    code.sll(V0, V0, 1)
    code.addu(T6, T3, V0)
    code.lhu(V0, 0, T6)
    code.addu(T6, T5, V0)
    code.beq(ZERO, ZERO, "copy_location")
    code.delay_nop()

    code.label("location_home")
    code.addiu(T6, T4, text_offsets["home"])
    code.beq(ZERO, ZERO, "copy_location")
    code.delay_nop()
    code.label("location_office")
    code.addiu(T6, T4, text_offsets["office"])
    code.beq(ZERO, ZERO, "copy_location")
    code.delay_nop()
    code.label("location_unknown")
    code.addiu(T6, T4, text_offsets["unknown"])

    code.label("copy_location")
    code.lbu(V0, 0, T6)
    code.beq(V0, ZERO, "location_done")
    code.delay_nop()
    code.sb(V0, 0, T0)
    code.addiu(T6, T6, 1)
    code.addiu(T0, T0, 1)
    code.beq(ZERO, ZERO, "copy_location")
    code.delay_nop()

    code.label("location_done")
    code.addiu(V0, ZERO, 0x20)
    code.sb(V0, 0, T0)
    code.addiu(T0, T0, 1)
    code.addiu(V0, ZERO, 0x28)
    code.sb(V0, 0, T0)
    code.addiu(T0, T0, 1)

    code.lw(A1, 0, SP)
    code.addiu(V0, ZERO, 3600)
    code.divu(A1, V0)
    code.mflo(A1)
    code.mfhi(A2)
    code.sltiu(V1, A1, 1000)
    code.bne(V1, ZERO, "hours_ready")
    code.delay_nop()
    code.addiu(A1, ZERO, 999)
    code.label("hours_ready")
    code.addiu(V0, ZERO, 60)
    code.divu(A2, V0)
    code.mflo(A2)

    code.addiu(V0, ZERO, 100)
    code.divu(A1, V0)
    code.mflo(T7)
    code.mfhi(A1)
    code.beq(T7, ZERO, "hour_tens")
    code.delay_nop()
    code.addiu(T7, T7, 0x30)
    code.sb(T7, 0, T0)
    code.addiu(T0, T0, 1)
    code.label("hour_tens")
    code.addiu(V0, ZERO, 10)
    code.divu(A1, V0)
    code.mflo(T7)
    code.mfhi(A1)
    code.addiu(T7, T7, 0x30)
    code.sb(T7, 0, T0)
    code.addiu(T0, T0, 1)
    code.addiu(A1, A1, 0x30)
    code.sb(A1, 0, T0)
    code.addiu(T0, T0, 1)
    code.addiu(V0, ZERO, 0x3A)
    code.sb(V0, 0, T0)
    code.addiu(T0, T0, 1)

    code.addiu(V0, ZERO, 10)
    code.divu(A2, V0)
    code.mflo(T7)
    code.mfhi(A2)
    code.addiu(T7, T7, 0x30)
    code.sb(T7, 0, T0)
    code.addiu(T0, T0, 1)
    code.addiu(A2, A2, 0x30)
    code.sb(A2, 0, T0)
    code.addiu(T0, T0, 1)
    code.addiu(V0, ZERO, 0x29)
    code.sb(V0, 0, T0)
    code.addiu(T0, T0, 1)

    code.sb(ZERO, 0, T0)
    code.lw(RA, 0x0C, SP)
    code.addiu(SP, SP, 0x10)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def build_savedata_patch(
    source: SavedataPatchSource,
    location_record_ids: Iterable[int],
) -> SavedataPatch:
    """Build English utility-language and SFO metadata writes."""

    if not isinstance(source, SavedataPatchSource):
        raise TypeError("PSP savedata source must be SavedataPatchSource")
    game_title = _savedata_fixed_ascii(
        source.game_title,
        SAVEDATA_GAME_TITLE_SIZE,
        "game title",
    )
    slot_title = _savedata_fixed_ascii(
        source.slot_title,
        SAVEDATA_SLOT_TITLE_SIZE,
        "slot title",
    )
    detail_title = _savedata_ascii(source.detail_title, "detail title")
    cancel_load = _savedata_fixed_ascii(
        source.cancel_load,
        SAVEDATA_CANCEL_PROMPT_SIZE,
        "load-cancel prompt",
    )
    cancel_save = _savedata_fixed_ascii(
        source.cancel_save,
        SAVEDATA_CANCEL_PROMPT_SIZE,
        "save-cancel prompt",
    )
    if not isinstance(source.difficulties, tuple) or len(source.difficulties) != 2:
        raise ValueError("PSP savedata requires Normal and Hard difficulty labels")
    difficulties = tuple(
        _savedata_ascii(value, f"difficulty {index}")
        for index, value in enumerate(source.difficulties)
    )
    home = _savedata_ascii(source.home, "home label")
    office = _savedata_ascii(source.office, "office label")
    unknown = _savedata_ascii(source.unknown, "unknown-location label")
    if not isinstance(source.locations, tuple) or len(source.locations) != (
        SAVEDATA_LOCATION_NAME_COUNT
    ):
        raise ValueError(
            f"PSP savedata requires {SAVEDATA_LOCATION_NAME_COUNT} location names"
        )
    locations = tuple(
        _savedata_ascii(value, f"location {index}")
        for index, value in enumerate(source.locations)
    )

    record_ids = tuple(location_record_ids)
    if len(record_ids) != SAVEDATA_LOCATION_RECORD_COUNT or any(
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 0 <= value < SAVEDATA_LOCATION_NAME_COUNT
        for value in record_ids
    ):
        raise ValueError("PSP savedata location-record IDs are invalid")
    if set(record_ids) != set(range(SAVEDATA_LOCATION_NAME_COUNT)):
        raise ValueError("PSP savedata location-record IDs are incomplete")

    values = (
        ("detail_title", detail_title),
        ("level_prefix", " Lv. "),
        ("difficulty_normal", difficulties[0]),
        ("difficulty_hard", difficulties[1]),
        ("home", home),
        ("office", office),
        ("unknown", unknown),
    )
    text_offsets: dict[str, int] = {}
    text_blob = bytearray()
    for key, value in values:
        text_offsets[key] = len(text_blob)
        text_blob.extend(value.encode("ascii") + b"\0")
    location_text_blob = bytearray()
    location_text_offsets = []
    for value in locations:
        location_text_offsets.append(len(location_text_blob))
        location_text_blob.extend(value.encode("ascii") + b"\0")
    location_offsets = struct.pack(
        f"<{SAVEDATA_LOCATION_NAME_COUNT}H",
        *location_text_offsets,
    )
    detail_trampoline = _build_savedata_detail_trampoline()
    detail_wrapper = _build_savedata_detail_wrapper(text_offsets)
    if detail_wrapper.end_address > ITEM_DESCRIPTION_DRAW_WRAPPER_ADDRESS:
        raise ValueError("PSP savedata wrapper exceeds its cave partition")
    if (
        SAVEDATA_LOCATION_ID_TABLE_ADDRESS + len(record_ids)
        > SAVEDATA_LOCATION_OFFSET_TABLE_ADDRESS
    ):
        raise ValueError("PSP savedata record IDs exceed their cave partition")
    if (
        SAVEDATA_LOCATION_OFFSET_TABLE_ADDRESS + len(location_offsets)
        > SAVEDATA_TABLE_CAVE_END_ADDRESS
    ):
        raise ValueError("PSP savedata offsets exceed their cave partition")
    if SAVEDATA_TEXT_BLOB_ADDRESS + len(text_blob) > SAVEDATA_TABLE_CAVE_END_ADDRESS:
        raise ValueError("PSP savedata static text exceeds its source-zero run")
    if (
        SAVEDATA_LOCATION_TEXT_BLOB_ADDRESS + len(location_text_blob)
        > SAVEDATA_LOCATION_TEXT_CAVE_END_ADDRESS
    ):
        raise ValueError("PSP savedata location text exceeds its source-zero run")

    writes = (
        PatchWrite(
            "savedata_language_one",
            SAVEDATA_LANGUAGE_LOAD_ADDRESS,
            _word_bytes(_i_type(0x09, ZERO, V1, 1)),
        ),
        PatchWrite(
            "savedata_language_store",
            SAVEDATA_LANGUAGE_STORE_ADDRESS,
            _word_bytes(_i_type(0x2B, S0, V1, 4)),
        ),
        PatchWrite(
            "savedata_game_title",
            SAVEDATA_GAME_TITLE_ADDRESS,
            game_title,
        ),
        PatchWrite(
            "savedata_slot_title",
            SAVEDATA_SLOT_TITLE_ADDRESS,
            slot_title,
        ),
        PatchWrite(
            "savedata_cancel_load",
            SAVEDATA_CANCEL_LOAD_ADDRESS,
            cancel_load,
        ),
        PatchWrite(
            "savedata_cancel_save",
            SAVEDATA_CANCEL_SAVE_ADDRESS,
            cancel_save,
        ),
        PatchWrite(
            "savedata_detail_dispatch",
            SAVEDATA_DETAIL_FUNCTION_ADDRESS,
            _word_bytes(
                _branch_word(
                    SAVEDATA_DETAIL_FUNCTION_ADDRESS,
                    SAVEDATA_DETAIL_TRAMPOLINE_ADDRESS,
                ),
                0,
            ),
        ),
        PatchWrite(
            "savedata_detail_trampoline",
            detail_trampoline.address,
            detail_trampoline.data,
        ),
        PatchWrite(
            "savedata_detail_wrapper",
            detail_wrapper.address,
            detail_wrapper.data,
        ),
        PatchWrite(
            "savedata_location_ids",
            SAVEDATA_LOCATION_ID_TABLE_ADDRESS,
            bytes(record_ids),
        ),
        PatchWrite(
            "savedata_location_offsets",
            SAVEDATA_LOCATION_OFFSET_TABLE_ADDRESS,
            location_offsets,
        ),
        PatchWrite(
            "savedata_text_blob",
            SAVEDATA_TEXT_BLOB_ADDRESS,
            bytes(text_blob),
        ),
        PatchWrite(
            "savedata_location_text_blob",
            SAVEDATA_LOCATION_TEXT_BLOB_ADDRESS,
            bytes(location_text_blob),
        ),
    )
    ordered = tuple(sorted(writes, key=lambda write: write.address))
    for left, right in zip(ordered, ordered[1:]):
        if left.end_address > right.address:
            raise ValueError(f"PSP savedata writes overlap: {left.name}, {right.name}")
    return SavedataPatch(
        detail_trampoline,
        detail_wrapper,
        bytes(record_ids),
        location_offsets,
        bytes(text_blob),
        bytes(location_text_blob),
        writes,
    )


__all__ = [
    "SAVEDATA_CANCEL_LOAD_ADDRESS",
    "SAVEDATA_CANCEL_PROMPT_SIZE",
    "SAVEDATA_CANCEL_SAVE_ADDRESS",
    "SAVEDATA_DETAIL_BUFFER_ADDRESS",
    "SAVEDATA_DETAIL_BUFFER_RAW_ADDRESS",
    "SAVEDATA_DETAIL_FUNCTION_ADDRESS",
    "SAVEDATA_DETAIL_TRAMPOLINE_ADDRESS",
    "SAVEDATA_DIFFICULTY_ADDRESS",
    "SAVEDATA_DIFFICULTY_RAW_ADDRESS",
    "SAVEDATA_ELAPSED_TIME_ADDRESS",
    "SAVEDATA_GAME_TITLE_ADDRESS",
    "SAVEDATA_GAME_TITLE_SIZE",
    "SAVEDATA_LANGUAGE_LOAD_ADDRESS",
    "SAVEDATA_LANGUAGE_STORE_ADDRESS",
    "SAVEDATA_LEVEL_ADDRESS",
    "SAVEDATA_LEVEL_RAW_ADDRESS",
    "SAVEDATA_LOCATION_OFFSET_TABLE_ADDRESS",
    "SAVEDATA_LOCATION_TEXT_BLOB_ADDRESS",
    "SAVEDATA_LOCATION_TEXT_CAVE_END_ADDRESS",
    "SAVEDATA_PLAYTIME_ADDRESS",
    "SAVEDATA_PLAYTIME_RAW_ADDRESS",
    "SAVEDATA_SLOT_TITLE_ADDRESS",
    "SAVEDATA_SLOT_TITLE_SIZE",
    "SAVEDATA_TABLE_CAVE_END_ADDRESS",
    "SAVEDATA_TABLE_CAVE_SOURCE_START_ADDRESS",
    "SAVEDATA_TEXT_BLOB_ADDRESS",
    "SavedataPatch",
    "SavedataPatchSource",
    "build_savedata_patch",
]

