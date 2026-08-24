"""Checked BOOT.BIN composition for party-panel and battle-result names."""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path

from . import battle_names_runtime as runtime
from ..core.patching import Patch, apply_patches
from psp.text.util.assets import load_asset_field
from psp.text.util.event_packed import (
    ASCII_FIRST,
    ASCII_LAST,
    STORED_PRINTABLE_FIRST,
    decode_ascii_byte,
)
from psp.text.util.name_entry import load_name_entry_text

ENGINE_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ENGINE_ROOT / "config" / "battle_names.json"

RELOCATION = struct.Struct("<II")
ADDRESS_BIAS = 0x80
_RELOCATION_SECTIONS = ((0x001CD9E8, 0x00068ED8), (0x00236B28, 0x00006180), (0x0023CCA8, 0x0000C510))


def file_offset(address: int) -> int:
    return address + ADDRESS_BIAS


def iter_relocations(source: bytes):
    for offset, size in _RELOCATION_SECTIONS:
        for cursor in range(offset, offset + size, RELOCATION.size):
            yield RELOCATION.unpack_from(source, cursor)

BATTLE_NAME_DRAW_CALL_CONTRACTS = (
    (
        "battle_name_panel_mode1_draw_call",
        runtime.BATTLE_NAME_PANEL_MODE1_DRAW_CALL_ADDRESS,
        0x001E95B0,
        bytes.fromhex("d8d0010c32001024"),
    ),
    (
        "battle_name_panel_mode0_draw_call",
        runtime.BATTLE_NAME_PANEL_MODE0_DRAW_CALL_ADDRESS,
        0x001E9B18,
        bytes.fromhex("d8d0010c32001024"),
    ),
    (
        "battle_name_mode1_draw_call",
        runtime.BATTLE_NAME_MODE1_DRAW_CALL_ADDRESS,
        0x0021B138,
        bytes.fromhex("d8d0010c32001124"),
    ),
    (
        "battle_name_mode0_draw_call",
        runtime.BATTLE_NAME_MODE0_DRAW_CALL_ADDRESS,
        0x0021B350,
        bytes.fromhex("d8d0010c32001124"),
    ),
    (
        "battle_name_party_draw_call",
        runtime.BATTLE_NAME_PARTY_DRAW_CALL_ADDRESS,
        0x0021CA10,
        bytes.fromhex("d8d0010c2180a000"),
    ),
)
BATTLE_RESULT_DRAW_CALL_CONTRACTS = (
    (
        "battle_result_name_primary_draw_call",
        runtime.BATTLE_RESULT_NAME_PRIMARY_DRAW_CALL_ADDRESS,
        0x001EBAF0,
        bytes.fromhex("6632000cffff0824"),
    ),
    (
        "battle_result_name_secondary_draw_call",
        runtime.BATTLE_RESULT_NAME_SECONDARY_DRAW_CALL_ADDRESS,
        0x001EBB38,
        bytes.fromhex("6632000cffff0824"),
    ),
    (
        "battle_result_life_stone_draw_call",
        runtime.BATTLE_RESULT_LIFE_STONE_DRAW_CALL_ADDRESS,
        0x001EBB48,
        bytes.fromhex("6632000c16010724"),
    ),
    (
        "battle_result_life_stone_continuation_draw_call",
        runtime.BATTLE_RESULT_LIFE_STONE_CONTINUATION_DRAW_CALL_ADDRESS,
        0x001EBB50,
        bytes.fromhex("6632000c78010724"),
    ),
    (
        "battle_result_bead_draw_call",
        runtime.BATTLE_RESULT_BEAD_DRAW_CALL_ADDRESS,
        0x001EBB60,
        bytes.fromhex("6632000c21402002"),
    ),
    (
        "battle_result_bead_continuation_draw_call",
        runtime.BATTLE_RESULT_BEAD_CONTINUATION_DRAW_CALL_ADDRESS,
        0x001EBB68,
        bytes.fromhex("6632000c21402002"),
    ),
    (
        "battle_result_none_draw_call",
        runtime.BATTLE_RESULT_NONE_DRAW_CALL_ADDRESS,
        0x001EBC78,
        bytes.fromhex("6632000cffa00835"),
    ),
    (
        "battle_result_none_continuation_draw_call",
        runtime.BATTLE_RESULT_NONE_CONTINUATION_DRAW_CALL_ADDRESS,
        0x001EBC80,
        bytes.fromhex("6632000cffa00835"),
    ),
)
BATTLE_NAME_LOOP_SKIP_CONTRACTS = (
    (
        "battle_name_panel_mode1_loop_skip",
        runtime.BATTLE_NAME_PANEL_MODE1_LOOP_SKIP_ADDRESS,
        bytes.fromhex("2190400021105102"),
    ),
    (
        "battle_name_panel_mode0_loop_skip",
        runtime.BATTLE_NAME_PANEL_MODE0_LOOP_SKIP_ADDRESS,
        bytes.fromhex("2190400021105102"),
    ),
    (
        "battle_name_mode1_loop_skip",
        runtime.BATTLE_NAME_MODE1_LOOP_SKIP_ADDRESS,
        bytes.fromhex("2190400021105002"),
    ),
    (
        "battle_name_mode0_loop_skip",
        runtime.BATTLE_NAME_MODE0_LOOP_SKIP_ADDRESS,
        bytes.fromhex("2190400021105002"),
    ),
    (
        "battle_name_party_loop_skip",
        runtime.BATTLE_NAME_PARTY_LOOP_SKIP_ADDRESS,
        bytes.fromhex("2190400021105102"),
    ),
)
BATTLE_NAME_PARTY_CALLER_CONTRACTS = (
    (
        "battle_party_primary_caller",
        0x0008A84C,
        0x0021CB50,
        bytes.fromhex("1429020cffff0724"),
    ),
    (
        "battle_party_list_caller",
        0x0008B744,
        0x0021D2B0,
        bytes.fromhex("1429020c4a000524"),
    ),
)
BATTLE_NAME_RESOLVER_SOURCE_BYTES = bytes.fromhex(
    "ffff843000ff82243f00033c0500422cc0200400050040142c6d63243000033c"
    "5485628c21104400f8ff43240800e00321106000"
)
BATTLE_NAME_RESOLVER_RELOCATION_CONTRACTS = (
    (0x00074368, 0x00212DC8, 0x00010005),
    (0x00074378, 0x00212DD0, 0x00010006),
    (0x0007437C, 0x00212DD8, 0x00010005),
    (0x00074380, 0x00212DE0, 0x00010006),
)
BATTLE_NAME_FONT16_DRAW_ABI_SOURCE_WORDS = (
    (0x0000C9A0, 0x00A05021),
    (0x0000C9A8, 0x00804821),
    (0x0000C9AC, 0x01002821),
    (0x0000CA74, 0xAC660004),
)
BATTLE_NAME_CAVE_WRITE_ADDRESSES = {
    "battle_name_draw_wrapper": runtime.BATTLE_NAME_DRAW_WRAPPER_ADDRESS,
    "battle_name_codes": runtime.BATTLE_NAME_CODE_TABLE_ADDRESS,
    "battle_name_widths": runtime.BATTLE_NAME_WIDTH_TABLE_ADDRESS,
    "battle_name_mysterious_man": runtime.BATTLE_NAME_STATIC_STORAGE_ADDRESS,
    "battle_result_draw_wrapper": runtime.BATTLE_RESULT_DRAW_WRAPPER_ADDRESS,
    "battle_result_text": runtime.BATTLE_RESULT_STATIC_STORAGE_ADDRESS,
}


def build_patch(
    source: runtime.BattleNamePatchSource,
) -> runtime.BattleNamePatch:
    """Compile one semantic name source into its checked runtime patch."""

    return runtime.build_battle_name_patch(source)


def validate_source_elf(source: bytes) -> None:
    """Validate the two live loops, shared ABI, relocations, and cave holes."""

    for (
        name,
        address,
        relocation_offset,
        expected_bytes,
    ) in BATTLE_NAME_DRAW_CALL_CONTRACTS + BATTLE_RESULT_DRAW_CALL_CONTRACTS:
        offset = file_offset(address)
        actual = source[offset : offset + len(expected_bytes)]
        if actual != expected_bytes:
            raise ValueError(
                f"PSP battle-name call changed at {name}: "
                f"expected {expected_bytes.hex()}, found {actual.hex()}"
            )
        relocation = RELOCATION.pack(address, 4)
        if (
            source[relocation_offset : relocation_offset + len(relocation)]
            != relocation
        ):
            raise ValueError(f"PSP battle-name JAL relocation changed at {address:#x}")

    for name, address, expected_bytes in BATTLE_NAME_LOOP_SKIP_CONTRACTS:
        offset = file_offset(address)
        if source[offset : offset + len(expected_bytes)] != expected_bytes:
            raise ValueError(f"PSP battle-name loop changed at {name}")

    for (
        name,
        address,
        relocation_offset,
        expected_bytes,
    ) in BATTLE_NAME_PARTY_CALLER_CONTRACTS:
        offset = file_offset(address)
        if source[offset : offset + len(expected_bytes)] != expected_bytes:
            raise ValueError(f"PSP battle-name party caller changed at {name}")
        relocation = RELOCATION.pack(address, 4)
        if (
            source[relocation_offset : relocation_offset + len(relocation)]
            != relocation
        ):
            raise ValueError(
                f"PSP battle-name party-caller relocation changed at {address:#x}"
            )

    resolver_offset = file_offset(runtime.BATTLE_NAME_STOCK_RESOLVER_ADDRESS)
    if (
        source[
            resolver_offset : resolver_offset + len(BATTLE_NAME_RESOLVER_SOURCE_BYTES)
        ]
        != BATTLE_NAME_RESOLVER_SOURCE_BYTES
    ):
        raise ValueError("PSP battle-name stock resolver changed")
    for address, relocation_offset, info in BATTLE_NAME_RESOLVER_RELOCATION_CONTRACTS:
        expected_relocation = RELOCATION.pack(address, info)
        if (
            source[relocation_offset : relocation_offset + len(expected_relocation)]
            != expected_relocation
        ):
            raise ValueError(
                f"PSP battle-name resolver relocation changed at {address:#x}"
            )
    for address, expected_word in BATTLE_NAME_FONT16_DRAW_ABI_SOURCE_WORDS:
        offset = file_offset(address)
        if int.from_bytes(source[offset : offset + 4], "little") != expected_word:
            raise ValueError(f"PSP battle-name FONT16 ABI changed at {address:#x}")

    cave_ranges = (
        (
            runtime.BATTLE_NAME_DRAW_WRAPPER_ADDRESS,
            runtime.BATTLE_NAME_DRAW_WRAPPER_END_ADDRESS,
        ),
        (
            runtime.BATTLE_NAME_CODE_TABLE_ADDRESS,
            runtime.BATTLE_NAME_CAVE_END_ADDRESS,
        ),
        (
            runtime.BATTLE_RESULT_DRAW_WRAPPER_ADDRESS,
            runtime.BATTLE_RESULT_CAVE_END_ADDRESS,
        ),
    )
    if any(
        any(start <= address < end for start, end in cave_ranges)
        for address, _info in iter_relocations(source)
    ):
        raise ValueError("PSP BOOT.BIN has a relocation inside a battle-name cave")
    for start, end in cave_ranges:
        if any(source[file_offset(start) : file_offset(end)]):
            raise ValueError("PSP battle-name code cave is no longer source-blank")


def validate_patch_sources(
    source: bytes,
    patch: runtime.BattleNamePatch,
) -> None:
    """Validate every battle-name write against its exact stock preimage."""

    source_by_write = {
        name: (address, expected[:4])
        for name, address, _relocation_offset, expected in (
            BATTLE_NAME_DRAW_CALL_CONTRACTS + BATTLE_RESULT_DRAW_CALL_CONTRACTS
        )
    } | {
        name: (address, expected)
        for name, address, expected in BATTLE_NAME_LOOP_SKIP_CONTRACTS
    }
    expected_names = frozenset(source_by_write) | frozenset(
        BATTLE_NAME_CAVE_WRITE_ADDRESSES
    )
    actual_names = frozenset(write.name for write in patch.writes)
    if actual_names != expected_names:
        raise ValueError("PSP battle-name write inventory changed")

    for write in patch.writes:
        before = source[write.file_offset : write.file_offset + len(write.data)]
        if len(before) != len(write.data):
            raise ValueError(f"PSP battle-name write {write.name} exceeds BOOT.BIN")
        if write.name in source_by_write:
            expected_address, expected = source_by_write[write.name]
            if write.address != expected_address or before != expected:
                raise ValueError(f"PSP battle-name source changed at {write.name}")
        elif write.name in BATTLE_NAME_CAVE_WRITE_ADDRESSES:
            expected_address = BATTLE_NAME_CAVE_WRITE_ADDRESSES[write.name]
            if write.address != expected_address or not write.data or any(before):
                raise ValueError(f"PSP battle-name cave source changed at {write.name}")
        else:
            raise ValueError(f"unknown PSP battle-name write: {write.name}")


@dataclass(frozen=True, slots=True)
class BattleNamesBuild:
    data: bytes
    patches: tuple[Patch, ...]
    runtime: runtime.BattleNamePatch
    mysterious_man: str
    result_labels: tuple[str, str, str]
    runtime_used_size: int
    runtime_capacity: int


def _configuration() -> dict[str, object]:
    try:
        value = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP battle-name contract: {CONFIG_PATH}") from error
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "version",
            "surface",
            "mysterious_man",
            "result_none",
            "result_life_stone",
            "result_bead",
            "full_dvl_names",
            "write_count",
        }
        or value.get("version") != 1
        or value.get("surface") != "battle_names.runtime"
        or value.get("full_dvl_names") is not True
        or value.get("write_count") != 24
        or any(
            not isinstance(value.get(key), str)
            for key in (
                "mysterious_man",
                "result_none",
                "result_life_stone",
                "result_bead",
            )
        )
    ):
        raise ValueError("invalid PSP battle-name contract")
    return value


def _font_mapping(contract: dict[str, object]) -> tuple[dict[str, int], dict[str, int]]:
    rows = contract.get("ark12") if isinstance(contract, dict) else None
    if not isinstance(rows, list):
        raise ValueError("PSP font manifest has no shared Ark12 mapping")
    codes: dict[str, int] = {}
    advances: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("PSP shared Ark12 mapping is malformed")
        character = row.get("character")
        code = row.get("code")
        advance = row.get("advance")
        if (
            not isinstance(character, str)
            or len(character) != 1
            or type(code) is not int
            or type(advance) is not int
            or not 0 <= code <= 0xFF
            or not 1 <= advance <= 16
            or character in codes
            or code in codes.values()
        ):
            raise ValueError("PSP shared Ark12 mapping is malformed")
        codes[character] = code
        advances[character] = advance
    if codes.get(" ") != 0:
        raise ValueError("PSP shared Ark12 space mapping changed")
    return codes, advances


def build_battle_names(
    stock: bytes,
    intermediate: bytes,
    font_contract: dict[str, object],
    dvlname_table: bytes,
) -> BattleNamesBuild:
    """Apply the shared battle-panel and battle-result name renderer."""

    if not isinstance(intermediate, bytes) or len(intermediate) != len(stock):
        raise ValueError("PSP battle-name intermediate BOOT size changed")
    config = _configuration()
    mysterious_reference, mysterious_man = load_asset_field(config["mysterious_man"])
    life_reference, life_stone = load_asset_field(config["result_life_stone"])
    bead_reference, bead = load_asset_field(config["result_bead"])
    if (
        mysterious_reference != "ナゾのおとこ"
        or life_reference != "ませき"
        or bead_reference != "ほうぎょく"
    ):
        raise ValueError("PSP battle-name authored source identities changed")
    result_none = config["result_none"]
    if result_none != "(None)":
        raise ValueError("PSP battle-result empty label changed")

    codes_by_character, advances_by_character = _font_mapping(font_contract)
    name_entry = load_name_entry_text()
    allowed = frozenset(
        character
        for grid in name_entry.grids
        for character in grid.characters
    ) | frozenset(mysterious_man + result_none + life_stone + bead)
    codes = [0] * (ASCII_LAST - ASCII_FIRST + 1)
    advances = [0] * len(codes)
    for value in range(STORED_PRINTABLE_FIRST, STORED_PRINTABLE_FIRST + len(codes)):
        character = decode_ascii_byte(value)
        if character not in allowed:
            continue
        try:
            code = codes_by_character[character]
            advance = advances_by_character[character]
        except KeyError as error:
            raise ValueError(
                f"PSP shared Ark12 mapping lacks battle-name glyph {character!r}"
            ) from error
        index = value - STORED_PRINTABLE_FIRST
        codes[index] = code
        advances[index] = advance

    source = runtime.BattleNamePatchSource(
        mysterious_man=mysterious_man,
        result_none=result_none,
        result_life_stones=life_stone,
        result_beads=bead,
        packed_glyph_codes=tuple(codes),
        packed_glyph_advances=tuple(advances),
        full_dvl_names=True,
    )
    table_start = runtime.COMPENDIUM_NAME_TABLE_ADDRESS + ADDRESS_BIAS
    if intermediate[table_start : table_start + len(dvlname_table)] != dvlname_table:
        raise ValueError("PSP battle names require the Compendium name-table owner")
    runtime.validate_full_dvl_table(source, dvlname_table)
    compiled = build_patch(source)
    validate_source_elf(stock)
    validate_patch_sources(stock, compiled)
    patches = tuple(
        Patch(
            "battle_names.runtime",
            write.name,
            write.address,
            stock[write.file_offset : write.file_offset + len(write.data)],
            write.data,
        )
        for write in compiled.writes
    )
    output = apply_patches(intermediate, ADDRESS_BIAS, patches)
    used = (
        len(compiled.draw_wrapper.data)
        + len(compiled.result_draw_wrapper.data)
        + len(compiled.code_table)
        + len(compiled.width_table)
        + len(compiled.static_storage)
        + len(compiled.result_static_storage)
    )
    capacity = (
        runtime.BATTLE_NAME_DRAW_WRAPPER_END_ADDRESS
        - runtime.BATTLE_NAME_DRAW_WRAPPER_ADDRESS
        + runtime.BATTLE_NAME_CAVE_END_ADDRESS
        - runtime.BATTLE_NAME_CODE_TABLE_ADDRESS
        + runtime.BATTLE_RESULT_CAVE_END_ADDRESS
        - runtime.BATTLE_RESULT_DRAW_WRAPPER_ADDRESS
    )
    return BattleNamesBuild(
        output,
        patches,
        compiled,
        mysterious_man,
        (result_none, life_stone, bead),
        used,
        capacity,
    )


__all__ = (
    "CONFIG_PATH",
    "BATTLE_NAME_CAVE_WRITE_ADDRESSES",
    "BATTLE_NAME_DRAW_CALL_CONTRACTS",
    "BATTLE_NAME_FONT16_DRAW_ABI_SOURCE_WORDS",
    "BATTLE_NAME_LOOP_SKIP_CONTRACTS",
    "BATTLE_NAME_PARTY_CALLER_CONTRACTS",
    "BATTLE_NAME_RESOLVER_RELOCATION_CONTRACTS",
    "BATTLE_NAME_RESOLVER_SOURCE_BYTES",
    "BATTLE_RESULT_DRAW_CALL_CONTRACTS",
    "BattleNamesBuild",
    "build_battle_names",
    "build_patch",
    "validate_patch_sources",
    "validate_source_elf",
)
