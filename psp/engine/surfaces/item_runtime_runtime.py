"""Shared packed-English runtime composition for three PSP-only items.

The native ITEMNAME m4 member remains immutable.  Two stock name helpers, the
stock description helper, the category-two branch inside ``FUN_0003d610``,
and EVENT control ``0x8018`` are the complete visible reader set patched here.
All non-owned IDs re-enter their original readers.  ID 255 additionally has
to match the complete 16-byte source name because the retail executable uses
that row as a scratch destination.

Inventory names, item-detail descriptions, and EVENT item insertion are
separate user-facing consumers of this one byte-sensitive composition.  Their
ownership metadata lives in the leaf consumer packages; this module remains
the single builder so shared caves, wrappers, and source guards cannot drift.

The packed renderer at :data:`COMPENDIUM_DRAW_WRAPPER_ADDRESS` is a deliberate
companion dependency.  This feature owns no atlas or width table and never
writes the 0x68-byte ITEMNAME rows or their four-byte metadata.
"""

from __future__ import annotations

import struct
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
    V1,
    ZERO,
    AssembledCode,
    PatchWrite,
    _Assembler,
    _branch_word,
    _i_type,
    _j_word,
    _jal_word,
    _load_pc_relative_target,
    _word_bytes,
)
from ..core.layout import (
    COMPENDIUM_DRAW_WRAPPER_ADDRESS,
    ITEM_DESCRIPTION_DRAW_WRAPPER_ADDRESS,
    ITEM_DESCRIPTION_DRAW_WRAPPER_END_ADDRESS,
    ITEM_EVENT_INSERT_WRAPPER_ADDRESS,
    ITEM_EVENT_INSERT_WRAPPER_END_ADDRESS,
    ITEM_NAME_DRAW_WRAPPER_ADDRESS,
    ITEM_NAME_DRAW_WRAPPER_END_ADDRESS,
    ITEM_NAME_RESOLVER_ADDRESS,
    ITEM_RUNTIME_DATA_ADDRESS,
    ITEM_RUNTIME_DATA_END_ADDRESS,
)
from psp.text.util.event_packed import (
    ASCII_FIRST,
    ASCII_LAST,
    GLYPH_CODE_BIAS,
    STORED_PRINTABLE_FIRST,
    encode_ascii_character,
)

PACKED_FIRST = STORED_PRINTABLE_FIRST
PACKED_RUNTIME_BIAS = GLYPH_CODE_BIAS
PACKED_WIDTH_COUNT = ASCII_LAST - ASCII_FIRST + 1


def _packed_storage_index(character: str) -> int:
    return encode_ascii_character(character) - PACKED_FIRST

ITEM_RUNTIME_GAME_IDS = (255, 280, 281)
ITEM_RUNTIME_NAME_WIDTH = 180
ITEM_RUNTIME_DESCRIPTION_WIDTH = 300

ITEM_TABLE_POINTER_ADDRESS = 0x002F854C
ITEM_255_LIVE_NAME_OFFSET = 0x6734
ITEM_CURRENT_DETAIL_ID_ADDRESS = 0x000214F0
ITEM_CURRENT_DETAIL_KIND_ADDRESS = 0x000214F2
ITEM_EVENT_CURRENT_ID_ADDRESS = 0x003F62D4

ITEM_NAME_PRIMARY_ENTRY_ADDRESS = 0x00080034
ITEM_NAME_DUPLICATE_ENTRY_ADDRESS = 0x00092DC4
ITEM_DESCRIPTION_ENTRY_ADDRESS = 0x00092E7C
ITEM_EVENT_DECODER_CALL_ADDRESS = 0x00073D14
ITEM_DETAIL_ROUTE_ADDRESS = 0x0003D834

# The first two entry points have no R_MIPS_26 relocation.  A raw far J would
# therefore lose the runtime load base.  These two relocation-free slices are
# inside the duplicate 92DC4 helper body, which becomes dead at its entry.
# Fallback replays the primary/duplicate prologue distinction in the private
# tail, then both markers enter the intact byte-identical suffix at 0x80058.
ITEM_NAME_DISPATCH_TRAMPOLINE_ADDRESS = 0x00092DDC
ITEM_NAME_DISPATCH_TRAMPOLINE_END_ADDRESS = 0x00092E00
ITEM_DESCRIPTION_DISPATCH_TRAMPOLINE_ADDRESS = 0x00092E1C
ITEM_DESCRIPTION_DISPATCH_TRAMPOLINE_END_ADDRESS = 0x00092E40

ITEM_NAME_SHARED_SUFFIX_ADDRESS = 0x00080058
ITEM_DESCRIPTION_STOCK_CONTINUATION_ADDRESS = 0x00092E84
ITEM_DETAIL_STOCK_CONTINUATION_ADDRESS = 0x0003D81C
ITEM_DETAIL_STOCK_CLEANUP_ADDRESS = 0x0003D704
ITEM_EVENT_STOCK_DECODER_ADDRESS = 0x000791C0
ITEM_NAME_STOCK_TAIL_ADDRESS = 0x00171DA0

ITEM_DATA_PADDING_SIZE = 1
ITEM_255_SOURCE_GUARD_OFFSET = ITEM_DATA_PADDING_SIZE
ITEM_255_SOURCE_GUARD_SIZE = 16
ITEM_DESCRIPTOR_TABLE_OFFSET = ITEM_255_SOURCE_GUARD_OFFSET + ITEM_255_SOURCE_GUARD_SIZE
ITEM_DESCRIPTOR_SIZE = 6
ITEM_STRING_TABLE_OFFSET = ITEM_DESCRIPTOR_TABLE_OFFSET + ITEM_DESCRIPTOR_SIZE * len(
    ITEM_RUNTIME_GAME_IDS
)
ITEM_TERMINATOR = 0
ITEM_DESCRIPTION_LINE_ADVANCE = 15
ITEM_DETAIL_LINE_ADVANCE = 16

# Exhaustive direct xrefs to the m4 pointer in the supported BOOT.BIN.  Keeping
# the inventory next to the feature makes it impossible to confuse aggregate
# corpus coverage with runtime reader coverage.
ITEM_M4_DIRECT_READER_SITES = (
    0x0002EC88,
    0x00073D00,
    0x0009ECF0,
    0x00073E98,
    0x00092E00,
    0x00092E8C,
    0x00080070,
    0x000A9560,
    0x0003D654,
    0x0003D838,
    0x000A96D0,
)
ITEM_NAME_PRIMARY_CALLERS = (
    0x00080300,
    0x00080650,
    0x000806C8,
    0x00080768,
    0x00080B28,
    0x00080E84,
    0x00080FBC,
    0x00081370,
    0x00081608,
    0x00081A2C,
    0x00081B90,
    0x00083354,
    0x000874C4,
)
ITEM_NAME_DUPLICATE_CALLERS = (0x00095088, 0x00095C9C, 0x000AE490)
ITEM_DESCRIPTION_CALLERS = (0x00094F68, 0x00095BB0, 0x000AE56C)
ITEM_DETAIL_CALLERS = (
    0x00014380,
    0x0001483C,
    0x00019BAC,
    0x00019FE8,
    0x00078B2C,
    0x000A2F24,
)

# These readers are intentionally stock.  The equipment owner cannot receive
# metadata kinds 0x0d/0x0f; the two combat-control formatters reject IDs above
# 0x10b and these three records are field/passive items; 9EC70 is the reason
# the ID-255 live-row guard exists and must retain its scratch-copy behavior.
ITEM_RUNTIME_EXCLUDED_READERS = (
    (0x0002EA70, "demon equipment slots exclude item kinds 0x0d and 0x0f"),
    (0x0009EC70, "retail ID-255 scratch-row copier remains authoritative"),
    (0x000A94BC, "combat-use formatter rejects these field/passive IDs"),
    (0x000A962C, "combat-use formatter rejects these field/passive IDs"),
)


@dataclass(frozen=True)
class ItemRuntimeRecordSource:
    """One source-pinned active item supplied by the text build layer."""

    game_id: int
    name: str
    description: str
    source_name: bytes


@dataclass(frozen=True)
class ItemRuntimePatchSource:
    """The exact three records plus the production packed-width table."""

    records: tuple[ItemRuntimeRecordSource, ...]
    packed_glyph_advances: Iterable[int]


@dataclass(frozen=True)
class PackedItemRuntimeRecord:
    """Readback geometry for one row inside the private packed data blob."""

    game_id: int
    name: str
    description_lines: tuple[str, ...]
    name_offset: int
    description_offset: int
    name_length: int


@dataclass(frozen=True)
class ItemRuntimePatch:
    """All isolated BOOT.BIN writes for the three active PSP item rows."""

    resolver: AssembledCode
    name_wrapper: AssembledCode
    description_wrapper: AssembledCode
    event_wrapper: AssembledCode
    name_stock_tail: AssembledCode
    name_trampoline: AssembledCode
    description_trampoline: AssembledCode
    data_blob: bytes
    source_guard: bytes
    records: tuple[PackedItemRuntimeRecord, ...]
    writes: tuple[PatchWrite, ...]

    def write(self, name: str) -> PatchWrite:
        try:
            return next(write for write in self.writes if write.name == name)
        except StopIteration as error:
            raise KeyError(f"unknown Allegrex item-runtime write: {name}") from error

    def resolve_record(
        self,
        game_id: int,
        *,
        live_source_name: bytes | None = None,
    ) -> PackedItemRuntimeRecord | None:
        """Model the assembly resolver, including ID 255's fail-closed guard."""

        if game_id == 255 and live_source_name != self.source_guard:
            return None
        return next(
            (record for record in self.records if record.game_id == game_id),
            None,
        )


def _validate_widths(values: Iterable[int]) -> bytes:
    try:
        resolved = tuple(values)
    except TypeError as error:
        raise TypeError("PSP item-runtime widths must be iterable") from error
    if len(resolved) != PACKED_WIDTH_COUNT:
        raise ValueError(
            f"PSP item-runtime widths have {len(resolved)} entries; "
            f"expected {PACKED_WIDTH_COUNT}"
        )
    if any(
        not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 0xFF
        for value in resolved
    ):
        raise ValueError("PSP item-runtime widths must contain nonzero u8 values")
    return bytes(resolved)


def _encode_checked(value: str, widths: bytes, context: str) -> bytes:
    if (
        not isinstance(value, str)
        or not value
        or any(
            character == "\n" or not 0x20 <= ord(character) <= 0x7E
            for character in value
        )
    ):
        raise ValueError(f"PSP item-runtime {context} must be printable ASCII")
    encoded = bytes(
        PACKED_FIRST + _packed_storage_index(character) for character in value
    )
    if any(widths[value - PACKED_FIRST] == 0 for value in encoded):
        raise ValueError(f"PSP item-runtime {context} uses an unmapped glyph")
    return encoded


def _measure(value: str, widths: bytes) -> int:
    return sum(widths[_packed_storage_index(character)] for character in value)


def _wrap_description(value: str, widths: bytes) -> tuple[str, ...]:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("PSP item-runtime description is empty")
    lines: list[str] = []
    for paragraph in value.split("\n"):
        words = paragraph.split()
        if not words:
            raise ValueError("PSP item-runtime description has an empty line")
        current = words[0]
        if _measure(current, widths) > ITEM_RUNTIME_DESCRIPTION_WIDTH:
            raise ValueError("PSP item-runtime description contains an overwide word")
        for word in words[1:]:
            if _measure(word, widths) > ITEM_RUNTIME_DESCRIPTION_WIDTH:
                raise ValueError(
                    "PSP item-runtime description contains an overwide word"
                )
            candidate = f"{current} {word}"
            if _measure(candidate, widths) <= ITEM_RUNTIME_DESCRIPTION_WIDTH:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return tuple(lines)


def _validate_source(
    source: ItemRuntimePatchSource,
) -> tuple[bytes, bytes, tuple[PackedItemRuntimeRecord, ...]]:
    if not isinstance(source, ItemRuntimePatchSource):
        raise TypeError("PSP item-runtime source has the wrong type")
    widths = _validate_widths(source.packed_glyph_advances)
    if not isinstance(source.records, tuple):
        raise TypeError("PSP item-runtime records must be a tuple")
    if tuple(record.game_id for record in source.records) != ITEM_RUNTIME_GAME_IDS:
        raise ValueError("PSP item-runtime record ownership changed")

    storage = bytearray(ITEM_STRING_TABLE_OFFSET)
    packed_records: list[PackedItemRuntimeRecord] = []
    descriptors: list[tuple[int, int, int, int]] = []
    for record in source.records:
        if not isinstance(record, ItemRuntimeRecordSource):
            raise TypeError("PSP item-runtime record has the wrong type")
        if not isinstance(record.source_name, bytes) or len(record.source_name) != 16:
            raise ValueError(
                f"PSP item-runtime ID {record.game_id} source name must be 16 bytes"
            )
        name = _encode_checked(record.name, widths, f"ID {record.game_id} name")
        name_width = _measure(record.name, widths)
        if name_width > ITEM_RUNTIME_NAME_WIDTH:
            raise ValueError(
                f"PSP item-runtime ID {record.game_id} name is {name_width}px; "
                f"limit is {ITEM_RUNTIME_NAME_WIDTH}px"
            )
        lines = _wrap_description(record.description, widths)
        encoded_lines = tuple(
            _encode_checked(line, widths, f"ID {record.game_id} description")
            for line in lines
        )

        name_offset = len(storage)
        storage.extend(name)
        storage.append(ITEM_TERMINATOR)
        description_offset = len(storage)
        for line in encoded_lines:
            storage.extend(line)
            storage.append(ITEM_TERMINATOR)
        if max(name_offset, description_offset) > 0xFFFF:
            raise ValueError("PSP item-runtime string offset exceeds u16")
        if len(lines) > 0xFF or len(name) > 0xFF:
            raise ValueError("PSP item-runtime descriptor exceeds u8")
        descriptors.append((name_offset, description_offset, len(lines), len(name)))
        packed_records.append(
            PackedItemRuntimeRecord(
                game_id=record.game_id,
                name=record.name,
                description_lines=lines,
                name_offset=name_offset,
                description_offset=description_offset,
                name_length=len(name),
            )
        )

    guard = source.records[0].source_name
    storage[ITEM_255_SOURCE_GUARD_OFFSET:ITEM_DESCRIPTOR_TABLE_OFFSET] = guard
    for index, descriptor in enumerate(descriptors):
        struct.pack_into(
            "<HHBB",
            storage,
            ITEM_DESCRIPTOR_TABLE_OFFSET + index * ITEM_DESCRIPTOR_SIZE,
            *descriptor,
        )
    data = bytes(storage)
    if ITEM_RUNTIME_DATA_ADDRESS + len(data) > ITEM_RUNTIME_DATA_END_ADDRESS:
        raise ValueError(
            f"PSP item-runtime data uses {len(data)} bytes; "
            f"capacity is {ITEM_RUNTIME_DATA_END_ADDRESS - ITEM_RUNTIME_DATA_ADDRESS}"
        )
    return widths, data, tuple(packed_records)


def _build_far_trampoline(address: int, target: int) -> AssembledCode:
    code = _Assembler(address)
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
        target_address=target,
    )
    code.addu(RA, T9, ZERO)
    code.jr(T8)
    code.delay_nop()
    return code.finish()


def _build_resolver() -> AssembledCode:
    code = _Assembler(ITEM_NAME_RESOLVER_ADDRESS)
    code.addu(T9, RA, ZERO)

    # IDs 280/281 are consecutive; every other value is rejected except 255.
    code.andi(T0, A0, 0xFFFF)
    code.addiu(T1, T0, -280)
    code.sltiu(T2, T1, 2)
    code.bne(T2, ZERO, "late_ids")
    code.delay_nop()
    code.addiu(T2, T0, -255)
    code.bne(T2, ZERO, "fail")
    code.delay_nop()
    code.addu(T1, ZERO, ZERO)
    code.beq(ZERO, ZERO, "selected")
    code.delay_nop()
    code.label("late_ids")
    code.addiu(T1, T1, 1)

    code.label("selected")
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    _load_pc_relative_target(
        code,
        T8,
        RA,
        pc_address=pc_address,
        target_address=ITEM_RUNTIME_DATA_ADDRESS,
    )

    # Only ID 255 is mutable in retail.  Compare all eight source u16s before
    # publishing its override; a copied scratch row always falls back stock.
    code.bne(T1, ZERO, "descriptor")
    code.delay_nop()
    _load_pc_relative_target(
        code,
        T2,
        RA,
        pc_address=pc_address,
        target_address=ITEM_TABLE_POINTER_ADDRESS,
    )
    code.lw(T2, 0, T2)
    code.addiu(T2, T2, ITEM_255_LIVE_NAME_OFFSET)
    code.addiu(T3, T8, ITEM_255_SOURCE_GUARD_OFFSET)
    code.addiu(T4, ZERO, ITEM_255_SOURCE_GUARD_SIZE // 2)
    code.label("guard_loop")
    code.lhu(T5, 0, T2)
    code.lhu(T6, 0, T3)
    code.bne(T5, T6, "fail")
    code.delay_nop()
    code.addiu(T2, T2, 2)
    code.addiu(T3, T3, 2)
    code.addiu(T4, T4, -1)
    code.bne(T4, ZERO, "guard_loop")
    code.delay_nop()

    code.label("descriptor")
    code.sll(T2, T1, 1)
    code.sll(T3, T1, 2)
    code.addu(T2, T2, T3)
    code.addiu(T2, T2, ITEM_DESCRIPTOR_TABLE_OFFSET)
    code.addu(T2, T8, T2)
    code.lhu(T3, 0, T2)
    code.lhu(T4, 2, T2)
    code.lbu(T5, 4, T2)
    code.lbu(T6, 5, T2)
    code.beq(A1, ZERO, "name")
    code.delay_nop()
    code.addu(V0, T8, T4)
    code.addu(V1, T5, ZERO)
    code.jr(T9)
    code.delay_nop()

    code.label("name")
    code.addu(V0, T8, T3)
    code.addu(V1, T6, ZERO)
    code.jr(T9)
    code.delay_nop()

    code.label("fail")
    code.addu(V0, ZERO, ZERO)
    code.addu(V1, ZERO, ZERO)
    code.jr(T9)
    code.delay_nop()
    return code.finish()


def _build_name_wrapper() -> AssembledCode:
    code = _Assembler(ITEM_NAME_DRAW_WRAPPER_ADDRESS)
    code.addiu(SP, SP, -0x20)
    code.sw(RA, 0x1C, SP)
    code.sw(A0, 0x18, SP)
    code.sw(A1, 0x14, SP)
    code.sw(A2, 0x10, SP)
    code.sw(T0, 0x0C, SP)
    code.andi(A0, A0, 0xFFFF)
    code.addu(A1, ZERO, ZERO)
    code.bal_address(ITEM_NAME_RESOLVER_ADDRESS)
    code.delay_nop()
    code.beq(V0, ZERO, "stock")
    code.delay_nop()

    code.addu(A0, V0, ZERO)
    code.lw(A1, 0x14, SP)
    code.lw(A2, 0x10, SP)
    code.addiu(A3, ZERO, 6)
    code.addiu(T0, ZERO, -1)
    code.bal_address(COMPENDIUM_DRAW_WRAPPER_ADDRESS)
    code.delay_nop()
    code.lw(RA, 0x1C, SP)
    code.addiu(SP, SP, 0x20)
    code.jr(RA)
    code.delay_nop()

    code.label("stock")
    code.lw(A0, 0x18, SP)
    code.lw(A1, 0x14, SP)
    code.lw(A2, 0x10, SP)
    code.lw(T0, 0x0C, SP)
    code.lw(RA, 0x1C, SP)
    code.addiu(SP, SP, 0x20)
    code.addiu(SP, SP, -0x40)
    code.andi(A0, A0, 0xFFFF)
    code.addu(T6, RA, ZERO)
    code.bal_address(ITEM_NAME_STOCK_TAIL_ADDRESS)
    code.delay_nop()
    return code.finish()


def _load_module_target(code: _Assembler, target: int) -> None:
    code.lui(T9, (target >> 16) & 0xFFFF)
    code.ori(T9, T9, target & 0xFFFF)


def _build_name_stock_tail() -> AssembledCode:
    """Replay both stock prologues, then enter their shared intact suffix.

    The duplicate body owns both near trampoline slices and is intentionally
    unreachable after its entry dispatch.  The common primary prefix is
    replayed first; duplicate dispatch then overwrites the two masked
    coordinates with its original raw a1/a2 values.  Both paths enter the
    byte-identical primary suffix at 0x80058.  The PC-derived module base
    substitutes for the original LUI relocation.
    """

    code = _Assembler(ITEM_NAME_STOCK_TAIL_ADDRESS)
    code.addiu(V0, ZERO, 0x68)
    code.sw(S4, 0x30, SP)
    code.mult(A0, V0)
    code.lui(V1, 0x30)
    code.sw(S3, 0x2C, SP)
    code.andi(S4, A2, 0xFFFF)
    code.andi(S3, A1, 0xFFFF)
    code.beq(T0, ZERO, "selected")
    code.delay_nop()
    code.addu(S4, A2, ZERO)
    code.addu(S3, A1, ZERO)

    code.label("selected")
    _load_module_target(code, ITEM_NAME_SHARED_SUFFIX_ADDRESS)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    _load_pc_relative_target(
        code,
        T8,
        RA,
        pc_address=pc_address,
        target_address=0,
    )
    code.addu(V1, V1, T8)
    code.addu(T8, T8, T9)
    code.addu(RA, T6, ZERO)
    code.jr(T8)
    code.delay_nop()
    return code.finish()


def _build_description_wrapper() -> AssembledCode:
    code = _Assembler(ITEM_DESCRIPTION_DRAW_WRAPPER_ADDRESS)
    code.addu(T0, ZERO, ZERO)
    code.beq(ZERO, ZERO, "setup")
    code.delay_nop()

    # Reached only through the relocated J at the category-two ITEMNAME branch
    # inside FUN_0003d610.  Its setup, FFFF guard, and visibility gate have all
    # already run; the J delay slot supplies the stock m4 pointer in v1.
    code.label("detail_entry")
    code.addiu(T0, ZERO, 1)
    code.addu(A0, S1, ZERO)
    code.addiu(A1, ZERO, 8)
    code.addiu(A2, ZERO, 8)

    code.label("setup")
    code.addiu(SP, SP, -0x30)
    code.sw(RA, 0x2C, SP)
    code.sw(V1, 0x28, SP)
    code.sw(S0, 0x24, SP)
    code.sw(S1, 0x20, SP)
    code.sw(S2, 0x1C, SP)
    code.sw(S3, 0x18, SP)
    code.sw(S4, 0x14, SP)
    code.sw(S5, 0x10, SP)
    code.sw(S6, 0x0C, SP)
    code.addu(S0, A0, ZERO)
    code.addu(S1, T0, ZERO)
    code.addu(S2, A1, ZERO)
    code.addu(S3, A2, ZERO)
    code.addiu(S4, ZERO, 6)
    code.beq(S1, ZERO, "resolve")
    code.delay_nop()
    code.addiu(S4, ZERO, 5)

    code.label("resolve")
    code.andi(A0, S0, 0xFFFF)
    code.addiu(A1, ZERO, 1)
    code.bal_address(ITEM_NAME_RESOLVER_ADDRESS)
    code.delay_nop()
    code.beq(V0, ZERO, "stock")
    code.delay_nop()
    code.addu(S5, V0, ZERO)
    code.addu(S6, V1, ZERO)

    code.label("line")
    code.addu(A0, S5, ZERO)
    code.addu(A1, S2, ZERO)
    code.addu(A2, S3, ZERO)
    code.addu(A3, S4, ZERO)
    code.addiu(T0, ZERO, -1)
    code.bal_address(COMPENDIUM_DRAW_WRAPPER_ADDRESS)
    code.delay_nop()
    code.label("scan")
    code.lbu(T0, 0, S5)
    code.addiu(S5, S5, 1)
    code.bne(T0, ZERO, "scan")
    code.delay_nop()
    code.addiu(S3, S3, ITEM_DESCRIPTION_LINE_ADVANCE)
    code.addu(S3, S3, S1)
    code.addiu(S6, S6, -1)
    code.bne(S6, ZERO, "line")
    code.delay_nop()

    code.beq(S1, ZERO, "return_selector")
    code.delay_nop()
    _load_module_target(code, ITEM_DETAIL_STOCK_CLEANUP_ADDRESS)
    code.beq(ZERO, ZERO, "restore")
    code.delay_nop()
    code.label("return_selector")
    code.addu(T9, ZERO, ZERO)
    code.beq(ZERO, ZERO, "restore")
    code.delay_nop()

    code.label("stock")
    code.bne(S1, ZERO, "detail_stock")
    code.delay_nop()
    code.andi(T1, S0, 0xFFFF)
    code.addiu(V0, ZERO, 0x68)
    code.addu(A1, S2, ZERO)
    code.addu(A2, S3, ZERO)
    _load_module_target(code, ITEM_DESCRIPTION_STOCK_CONTINUATION_ADDRESS)
    code.beq(ZERO, ZERO, "restore")
    code.delay_nop()
    code.label("detail_stock")
    code.lw(V1, 0x28, SP)
    _load_module_target(code, ITEM_DETAIL_STOCK_CONTINUATION_ADDRESS)

    code.label("restore")
    code.lw(S6, 0x0C, SP)
    code.lw(S5, 0x10, SP)
    code.lw(S4, 0x14, SP)
    code.lw(S3, 0x18, SP)
    code.lw(S2, 0x1C, SP)
    code.lw(S1, 0x20, SP)
    code.lw(S0, 0x24, SP)
    code.lw(RA, 0x2C, SP)
    code.addiu(SP, SP, 0x30)
    code.beq(T9, ZERO, "return")
    code.delay_nop()
    code.addu(T7, RA, ZERO)
    code.bal("tail_pc")
    code.delay_nop()
    code.label("tail_pc")
    pc_address = code.cursor
    _load_pc_relative_target(
        code,
        T8,
        RA,
        pc_address=pc_address,
        target_address=0,
    )
    code.addu(T8, T8, T9)
    code.addu(RA, T7, ZERO)
    code.jr(T8)
    code.delay_nop()
    code.label("return")
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def _build_event_wrapper() -> AssembledCode:
    code = _Assembler(ITEM_EVENT_INSERT_WRAPPER_ADDRESS)
    code.addiu(SP, SP, -0x10)
    code.sw(RA, 0x0C, SP)
    code.sw(A0, 0x08, SP)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    _load_pc_relative_target(
        code,
        T8,
        RA,
        pc_address=pc_address,
        target_address=ITEM_EVENT_CURRENT_ID_ADDRESS,
    )
    # The stock byte-swap decoder reads only a0.  Keep its module-relative
    # target in otherwise-unused a2 across the private resolver call.
    _load_pc_relative_target(
        code,
        A2,
        RA,
        pc_address=pc_address,
        target_address=ITEM_EVENT_STOCK_DECODER_ADDRESS,
    )
    code.lhu(A0, 0, T8)
    code.addu(A1, ZERO, ZERO)
    code.bal_address(ITEM_NAME_RESOLVER_ADDRESS)
    code.delay_nop()
    code.beq(V0, ZERO, "stock")
    code.delay_nop()
    code.lw(T0, 0x8C, S0)
    code.addu(V0, V0, T0)
    code.lbu(V0, 0, V0)
    code.addiu(V0, V0, PACKED_RUNTIME_BIAS)
    code.sw(V1, 0x90, S0)
    code.beq(ZERO, ZERO, "return")
    code.delay_nop()

    code.label("stock")
    code.lw(A0, 0x08, SP)
    code.jalr(A2)
    code.delay_nop()

    code.label("return")
    code.lw(RA, 0x0C, SP)
    code.addiu(SP, SP, 0x10)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def build_item_runtime_patch(source: ItemRuntimePatchSource) -> ItemRuntimePatch:
    """Compile the three guarded runtime rows without changing ITEMNAME m4."""

    _widths, data, records = _validate_source(source)
    resolver = _build_resolver()
    name_wrapper = _build_name_wrapper()
    description_wrapper = _build_description_wrapper()
    event_wrapper = _build_event_wrapper()
    name_stock_tail = _build_name_stock_tail()
    name_trampoline = _build_far_trampoline(
        ITEM_NAME_DISPATCH_TRAMPOLINE_ADDRESS,
        ITEM_NAME_DRAW_WRAPPER_ADDRESS,
    )
    description_trampoline = _build_far_trampoline(
        ITEM_DESCRIPTION_DISPATCH_TRAMPOLINE_ADDRESS,
        ITEM_DESCRIPTION_DRAW_WRAPPER_ADDRESS,
    )

    if resolver.end_address > ITEM_NAME_DRAW_WRAPPER_ADDRESS:
        raise ValueError("PSP item-runtime resolver exceeds its checked partition")
    if name_wrapper.end_address > ITEM_NAME_DRAW_WRAPPER_END_ADDRESS:
        raise ValueError("PSP item-runtime name wrapper exceeds its checked partition")
    if description_wrapper.end_address > ITEM_DESCRIPTION_DRAW_WRAPPER_END_ADDRESS:
        raise ValueError(
            "PSP item-runtime description wrapper exceeds its checked partition"
        )
    if event_wrapper.end_address != ITEM_NAME_STOCK_TAIL_ADDRESS:
        raise ValueError("PSP item-runtime EVENT/name-tail partition changed")
    if name_stock_tail.end_address > ITEM_EVENT_INSERT_WRAPPER_END_ADDRESS:
        raise ValueError("PSP item-runtime EVENT wrapper exceeds its checked partition")
    if name_trampoline.end_address != ITEM_NAME_DISPATCH_TRAMPOLINE_END_ADDRESS:
        raise ValueError("PSP item-runtime name trampoline size changed")
    if (
        description_trampoline.end_address
        != ITEM_DESCRIPTION_DISPATCH_TRAMPOLINE_END_ADDRESS
    ):
        raise ValueError("PSP item-runtime description trampoline size changed")

    writes = (
        PatchWrite(
            "item_name_primary_dispatch",
            ITEM_NAME_PRIMARY_ENTRY_ADDRESS,
            _word_bytes(
                _branch_word(
                    ITEM_NAME_PRIMARY_ENTRY_ADDRESS,
                    ITEM_NAME_DISPATCH_TRAMPOLINE_ADDRESS,
                ),
                _i_type(0x09, ZERO, T0, 0),
            ),
        ),
        PatchWrite(
            "item_name_duplicate_dispatch",
            ITEM_NAME_DUPLICATE_ENTRY_ADDRESS,
            _word_bytes(
                _branch_word(
                    ITEM_NAME_DUPLICATE_ENTRY_ADDRESS,
                    ITEM_NAME_DISPATCH_TRAMPOLINE_ADDRESS,
                ),
                _i_type(0x09, ZERO, T0, 1),
            ),
        ),
        PatchWrite(
            "item_description_dispatch",
            ITEM_DESCRIPTION_ENTRY_ADDRESS,
            _word_bytes(
                _branch_word(
                    ITEM_DESCRIPTION_ENTRY_ADDRESS,
                    ITEM_DESCRIPTION_DISPATCH_TRAMPOLINE_ADDRESS,
                ),
                0,
            ),
        ),
        PatchWrite(
            "item_event_decoder_call",
            ITEM_EVENT_DECODER_CALL_ADDRESS,
            _word_bytes(
                _jal_word(
                    ITEM_EVENT_DECODER_CALL_ADDRESS,
                    ITEM_EVENT_INSERT_WRAPPER_ADDRESS,
                )
            ),
        ),
        PatchWrite(
            "item_detail_route",
            ITEM_DETAIL_ROUTE_ADDRESS,
            _word_bytes(
                _j_word(
                    ITEM_DETAIL_ROUTE_ADDRESS,
                    description_wrapper.label_address("detail_entry"),
                )
            ),
        ),
        PatchWrite(
            "item_name_dispatch_trampoline",
            name_trampoline.address,
            name_trampoline.data,
        ),
        PatchWrite(
            "item_description_dispatch_trampoline",
            description_trampoline.address,
            description_trampoline.data,
        ),
        PatchWrite(
            "item_runtime_data",
            ITEM_RUNTIME_DATA_ADDRESS,
            data,
        ),
        PatchWrite(
            "item_event_wrapper",
            event_wrapper.address,
            event_wrapper.data,
        ),
        PatchWrite(
            "item_name_stock_tail",
            name_stock_tail.address,
            name_stock_tail.data,
        ),
        PatchWrite("item_name_resolver", resolver.address, resolver.data),
        PatchWrite("item_name_wrapper", name_wrapper.address, name_wrapper.data),
        PatchWrite(
            "item_description_wrapper",
            description_wrapper.address,
            description_wrapper.data,
        ),
    )
    ordered = tuple(sorted(writes, key=lambda write: write.address))
    for left, right in zip(ordered, ordered[1:]):
        if left.end_address > right.address:
            raise ValueError(
                f"PSP item-runtime writes overlap: {left.name} and {right.name}"
            )
    return ItemRuntimePatch(
        resolver=resolver,
        name_wrapper=name_wrapper,
        description_wrapper=description_wrapper,
        event_wrapper=event_wrapper,
        name_stock_tail=name_stock_tail,
        name_trampoline=name_trampoline,
        description_trampoline=description_trampoline,
        data_blob=data,
        source_guard=source.records[0].source_name,
        records=records,
        writes=writes,
    )


__all__ = (
    "ITEM_255_LIVE_NAME_OFFSET",
    "ITEM_255_SOURCE_GUARD_OFFSET",
    "ITEM_255_SOURCE_GUARD_SIZE",
    "ITEM_DATA_PADDING_SIZE",
    "ITEM_DESCRIPTION_CALLERS",
    "ITEM_DESCRIPTION_DISPATCH_TRAMPOLINE_ADDRESS",
    "ITEM_DESCRIPTION_DISPATCH_TRAMPOLINE_END_ADDRESS",
    "ITEM_DESCRIPTION_ENTRY_ADDRESS",
    "ITEM_DESCRIPTION_LINE_ADVANCE",
    "ITEM_DESCRIPTION_STOCK_CONTINUATION_ADDRESS",
    "ITEM_DESCRIPTOR_SIZE",
    "ITEM_DESCRIPTOR_TABLE_OFFSET",
    "ITEM_DETAIL_CALLERS",
    "ITEM_DETAIL_LINE_ADVANCE",
    "ITEM_DETAIL_ROUTE_ADDRESS",
    "ITEM_DETAIL_STOCK_CLEANUP_ADDRESS",
    "ITEM_DETAIL_STOCK_CONTINUATION_ADDRESS",
    "ITEM_EVENT_CURRENT_ID_ADDRESS",
    "ITEM_EVENT_DECODER_CALL_ADDRESS",
    "ITEM_EVENT_STOCK_DECODER_ADDRESS",
    "ITEM_M4_DIRECT_READER_SITES",
    "ITEM_NAME_DISPATCH_TRAMPOLINE_ADDRESS",
    "ITEM_NAME_DISPATCH_TRAMPOLINE_END_ADDRESS",
    "ITEM_NAME_DUPLICATE_CALLERS",
    "ITEM_NAME_DUPLICATE_ENTRY_ADDRESS",
    "ITEM_NAME_PRIMARY_CALLERS",
    "ITEM_NAME_PRIMARY_ENTRY_ADDRESS",
    "ITEM_NAME_SHARED_SUFFIX_ADDRESS",
    "ITEM_NAME_STOCK_TAIL_ADDRESS",
    "ITEM_RUNTIME_DESCRIPTION_WIDTH",
    "ITEM_RUNTIME_EXCLUDED_READERS",
    "ITEM_RUNTIME_GAME_IDS",
    "ITEM_RUNTIME_NAME_WIDTH",
    "ITEM_STRING_TABLE_OFFSET",
    "ITEM_TABLE_POINTER_ADDRESS",
    "ItemRuntimePatch",
    "ItemRuntimePatchSource",
    "ItemRuntimeRecordSource",
    "PackedItemRuntimeRecord",
    "build_item_runtime_patch",
)
