"""Build the canonical PSP Demon Compendium prose, names, and sort runtime."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path

from psp.text.util.compendium import (
    COMPENDIUM_LIVE_PROFILE_COUNT,
    COMPENDIUM_TEXT_ARENA_SIZE,
    CompendiumTextBuild,
    build_compendium_text,
    load_compendium_profiles,
)
from psp.text.util.event_dvlname import build_psp_dvlname_runtime_table
from psp.text.util.event_packed import (
    ASCII_FIRST,
    ASCII_LAST,
    STORED_PRINTABLE_FIRST,
    encode_ascii,
)

PACKED_FIRST = STORED_PRINTABLE_FIRST
PACKED_WIDTH_COUNT = ASCII_LAST - ASCII_FIRST + 1

from ..core.layout import DATA_LOAD_SEGMENT_ADDRESS
from ..core.patching import Patch, apply_patches
from .compendium_name_runtime import (
    COMPENDIUM_NAME_COMPARE_WRAPPER_ADDRESS,
    COMPENDIUM_NAME_COMPARE_WRAPPER_END_ADDRESS,
    COMPENDIUM_NAME_DRAW_WRAPPER_ADDRESS,
    COMPENDIUM_NAME_DRAW_WRAPPER_END_ADDRESS,
    COMPENDIUM_NAME_SORT_BLOCK_ADDRESS,
    COMPENDIUM_NAME_SORT_COMPARE_CALL_ADDRESS,
    COMPENDIUM_NAME_TABLE_ADDRESS,
    COMPENDIUM_NAME_TABLE_SIZE,
    CompendiumNamePatch,
    CompendiumNamePatchSource,
    build_compendium_name_patch,
)
from .compendium_prose_runtime import (
    COMPENDIUM_DRAW_WRAPPER_ADDRESS,
    COMPENDIUM_DRAW_WRAPPER_END_ADDRESS,
    COMPENDIUM_POINTER_RECORD_COUNT,
    COMPENDIUM_POINTER_RECORD_SIZE,
    COMPENDIUM_POINTER_TABLE_ADDRESS,
    COMPENDIUM_POINTER_TABLE_SIZE,
    COMPENDIUM_SOURCE_TEXT_ARENA_SIZE,
    COMPENDIUM_TEXT_ARENA_ADDRESS,
    COMPENDIUM_TEXT_ARENA_RAW_ADDRESS,
    CompendiumPatch,
    CompendiumPatchSource,
    build_compendium_patch,
)


ENGINE_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ENGINE_ROOT / "config" / "compendium.json"
ADDRESS_BIAS = 0x80
BOOT_SIZE = 2_404_599
BOOT_STOCK_SHA256 = "37b5b7a49fe1a5af60ab042d2822befb00580e02a7d7d2ed77dd279ebe6f55fa"

_DRAW_CALLS = (
    ("compendium_origin_draw_call", 0x0008A88C, 0x0021CB70, bytes.fromhex("ec7d020cffff0824")),
    ("compendium_summary_draw_call", 0x0008A8A4, 0x0021CB78, bytes.fromhex("ec7d020cffff0824")),
    ("compendium_detail_draw_call", 0x0008A974, 0x0021CBF8, bytes.fromhex("ec7d020c3f00113c")),
)
_NAME_CALLS = (
    ("compendium_name_detail_call", 0x0008A84C, 0x0021CB50, bytes.fromhex("1429020cffff0724")),
    ("compendium_name_list_call", 0x0008B744, 0x0021D2B0, bytes.fromhex("1429020c4a000524")),
)
_SORT_SOURCE = bytes.fromhex(
    "0800b396c0101300211051002110c203e442020cf8ff44900800929621804000ffff4232c0100200"
)
_SORT_RELOCATION_OFFSET = 0x0021F3B8
_SORT_PRESERVED_ADDRESS = 0x00090DA4
_SORT_PRESERVED_RELOCATION_OFFSET = 0x0021F3C0
_SORT_PRESERVED_SOURCE = bytes.fromhex("e442020cf8ff4490")
_ATLAS_CONTRACTS = (
    (0x00074ACC, bytes.fromhex("3f00063c2138a003f06dc6248808000c05000524")),
    (0x0009EEE0, bytes.fromhex("f06d4c8c")),
    (0x0010CA2C, b"flwdat/eve_files.bin\0"),
)
_REL_TEXT_FILE_OFFSET = 0x001CD9E8
_REL_TEXT_SIZE = 0x00068ED8
_REL_RODATA_FILE_OFFSET = 0x00236B28
_REL_RODATA_SIZE = 0x00006180
_REL_DATA_FILE_OFFSET = 0x0023CCA8
_REL_DATA_SIZE = 0x0000C510
_POINTER_RELOCATION_INFO = 0x00010102
_RELOCATION = struct.Struct("<II")


@dataclass(frozen=True, slots=True)
class CompendiumBuild:
    data: bytes
    patches: tuple[Patch, ...]
    text: CompendiumTextBuild
    prose: CompendiumPatch
    names: CompendiumNamePatch
    runtime_used_size: int
    runtime_capacity: int


def _configuration() -> dict[str, object]:
    try:
        document = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP Compendium runtime contract: {CONFIG_PATH}") from error
    if (
        document.get("version") != 1
        or document.get("surface") != "demon_compendium.runtime"
        or document.get("target")
        != {
            "name": "BOOT.BIN",
            "address_bias": ADDRESS_BIAS,
            "size": BOOT_SIZE,
            "stock_sha256": BOOT_STOCK_SHA256,
        }
        or document.get("prose")
        != {
            "source_arena_address": "0x001a0ad8",
            "source_arena_size": 122974,
            "source_arena_sha256": "fbb3627b44d8dfb30f7f65859e76619deee619f5fb3b2db93b90b35aa36d6cb5",
            "output_arena_size": 118824,
            "pointer_table_address": "0x001beb4c",
            "pointer_table_size": 5104,
            "pointer_table_sha256": "01c55fa4a613d2918cc31aa1fb3219d11dc30190176aab2d328b09b11bbf66ed",
        }
        or document.get("names")
        != {
            "source_table_address": "0x001bdb00",
            "table_size": 3205,
            "source_table_sha256": "459405b2a66a726669da6dc9a0ec89bb56a0df6588892e337e983478d151561f",
        }
    ):
        raise ValueError("invalid PSP Compendium runtime contract")
    return document


def _relocations(source: bytes, offset: int, size: int):
    for cursor in range(offset, offset + size, _RELOCATION.size):
        yield _RELOCATION.unpack_from(source, cursor)


def _validate_source(stock: bytes, pointer_table: bytes) -> None:
    config = _configuration()
    if len(stock) != BOOT_SIZE or hashlib.sha256(stock).hexdigest() != BOOT_STOCK_SHA256:
        raise ValueError("PSP Compendium BOOT source contract changed")

    for address, expected in _ATLAS_CONTRACTS:
        start = address + ADDRESS_BIAS
        if stock[start : start + len(expected)] != expected:
            raise ValueError(f"PSP Compendium EVE atlas contract changed at {address:#x}")
    for name, address, relocation_offset, expected in (*_DRAW_CALLS, *_NAME_CALLS):
        start = address + ADDRESS_BIAS
        if stock[start : start + len(expected)] != expected:
            raise ValueError(f"PSP Compendium call preimage changed at {name}")
        if stock[relocation_offset : relocation_offset + 8] != _RELOCATION.pack(address, 4):
            raise ValueError(f"PSP Compendium relocation changed at {name}")

    sort_start = COMPENDIUM_NAME_SORT_BLOCK_ADDRESS + ADDRESS_BIAS
    if stock[sort_start : sort_start + len(_SORT_SOURCE)] != _SORT_SOURCE:
        raise ValueError("PSP Compendium alphabetical comparison block changed")
    if stock[_SORT_RELOCATION_OFFSET : _SORT_RELOCATION_OFFSET + 8] != _RELOCATION.pack(
        COMPENDIUM_NAME_SORT_COMPARE_CALL_ADDRESS, 4
    ):
        raise ValueError("PSP Compendium sort relocation changed")
    preserved = _SORT_PRESERVED_ADDRESS + ADDRESS_BIAS
    if stock[preserved : preserved + len(_SORT_PRESERVED_SOURCE)] != _SORT_PRESERVED_SOURCE:
        raise ValueError("PSP Compendium preserved sort call changed")
    if stock[
        _SORT_PRESERVED_RELOCATION_OFFSET : _SORT_PRESERVED_RELOCATION_OFFSET + 8
    ] != _RELOCATION.pack(_SORT_PRESERVED_ADDRESS, 4):
        raise ValueError("PSP Compendium preserved sort relocation changed")

    prose_contract = config["prose"]
    source_arena = stock[
        COMPENDIUM_TEXT_ARENA_ADDRESS + ADDRESS_BIAS :
        COMPENDIUM_TEXT_ARENA_ADDRESS + ADDRESS_BIAS + COMPENDIUM_SOURCE_TEXT_ARENA_SIZE
    ]
    if hashlib.sha256(source_arena).hexdigest() != prose_contract["source_arena_sha256"]:
        raise ValueError("PSP Compendium source lore arena changed")
    source_table = stock[
        COMPENDIUM_POINTER_TABLE_ADDRESS + ADDRESS_BIAS :
        COMPENDIUM_POINTER_TABLE_ADDRESS + ADDRESS_BIAS + COMPENDIUM_POINTER_TABLE_SIZE
    ]
    if hashlib.sha256(source_table).hexdigest() != prose_contract["pointer_table_sha256"]:
        raise ValueError("PSP Compendium source pointer table changed")
    source_names = stock[
        COMPENDIUM_NAME_TABLE_ADDRESS + ADDRESS_BIAS :
        COMPENDIUM_NAME_TABLE_ADDRESS + ADDRESS_BIAS + COMPENDIUM_NAME_TABLE_SIZE
    ]
    if hashlib.sha256(source_names).hexdigest() != config["names"]["source_table_sha256"]:
        raise ValueError("PSP Compendium source name-table region changed")

    live_count = 0
    expected_relocations: list[tuple[int, int]] = []
    table_raw = COMPENDIUM_POINTER_TABLE_ADDRESS - DATA_LOAD_SEGMENT_ADDRESS
    for row_index in range(COMPENDIUM_POINTER_RECORD_COUNT):
        offset = row_index * COMPENDIUM_POINTER_RECORD_SIZE
        source_values = struct.unpack_from("<IIII", source_table, offset)
        output_values = struct.unpack_from("<IIII", pointer_table, offset)
        source_live = all(source_values[:3])
        if source_live:
            live_count += 1
            expected_relocations.extend(
                (table_raw + offset + field_offset, _POINTER_RELOCATION_INFO)
                for field_offset in (0, 4, 8)
            )
        if source_live != all(output_values[:3]):
            raise ValueError(f"PSP Compendium row {row_index} changed pointer ownership")
        if source_values[3] != output_values[3]:
            raise ValueError(f"PSP Compendium row {row_index} changed flags")
    if live_count != COMPENDIUM_LIVE_PROFILE_COUNT:
        raise ValueError("PSP Compendium source live-row inventory changed")
    actual_pointer_relocations = tuple(
        (address, info)
        for address, info in _relocations(stock, _REL_DATA_FILE_OFFSET, _REL_DATA_SIZE)
        if table_raw <= address < table_raw + COMPENDIUM_POINTER_TABLE_SIZE
    )
    if actual_pointer_relocations != tuple(expected_relocations):
        raise ValueError("PSP Compendium pointer relocation inventory changed")

    caves = (
        (COMPENDIUM_DRAW_WRAPPER_ADDRESS, COMPENDIUM_DRAW_WRAPPER_END_ADDRESS),
        (COMPENDIUM_NAME_DRAW_WRAPPER_ADDRESS, COMPENDIUM_NAME_DRAW_WRAPPER_END_ADDRESS),
        (COMPENDIUM_NAME_COMPARE_WRAPPER_ADDRESS, COMPENDIUM_NAME_COMPARE_WRAPPER_END_ADDRESS),
    )
    for start, end in caves:
        source = stock[start + ADDRESS_BIAS : end + ADDRESS_BIAS]
        if len(source) != end - start or any(source):
            raise ValueError(f"PSP Compendium cave {start:#x}..{end:#x} is not blank")
    relocation_rows = (
        *_relocations(stock, _REL_TEXT_FILE_OFFSET, _REL_TEXT_SIZE),
        *_relocations(stock, _REL_RODATA_FILE_OFFSET, _REL_RODATA_SIZE),
    )
    if any(
        start <= address < end
        for address, _info in relocation_rows
        for start, end in caves
    ):
        raise ValueError("PSP Compendium code cave has a relocation")
    name_raw = COMPENDIUM_NAME_TABLE_ADDRESS - DATA_LOAD_SEGMENT_ADDRESS
    if any(
        name_raw <= address < name_raw + COMPENDIUM_NAME_TABLE_SIZE
        for address, _info in _relocations(stock, _REL_DATA_FILE_OFFSET, _REL_DATA_SIZE)
    ):
        raise ValueError("PSP Compendium name-table region has a relocation")


def build_compendium(
    stock: bytes,
    intermediate: bytes,
    packed_widths: bytes,
) -> CompendiumBuild:
    """Apply the complete Compendium surface after earlier disjoint patches."""

    if (
        not isinstance(packed_widths, bytes)
        or len(packed_widths) != PACKED_WIDTH_COUNT
        or any(not 1 <= value <= 14 for value in packed_widths)
    ):
        raise ValueError("PSP Compendium EVE width table is invalid")
    if not isinstance(intermediate, bytes) or len(intermediate) != len(stock):
        raise ValueError("PSP Compendium intermediate BOOT size changed")

    def measure(value: str) -> int:
        return sum(packed_widths[code - PACKED_FIRST] for code in encode_ascii(value))

    text = build_compendium_text(
        load_compendium_profiles(),
        measure,
        arena_size=COMPENDIUM_TEXT_ARENA_SIZE,
        arena_raw_address=COMPENDIUM_TEXT_ARENA_RAW_ADDRESS,
    )
    prose = build_compendium_patch(
        CompendiumPatchSource(text.text_arena, text.pointer_table)
    )
    names = build_compendium_name_patch(
        CompendiumNamePatchSource(
            build_psp_dvlname_runtime_table(),
            packed_widths,
        )
    )
    if prose.write("compendium_text_arena").end_address != names.write(
        "compendium_name_table"
    ).address:
        raise ValueError("PSP Compendium prose/name arena boundary changed")
    _validate_source(stock, text.pointer_table)

    writes = (*prose.writes, *names.writes)
    ordered = tuple(sorted(writes, key=lambda write: write.address))
    for left, right in zip(ordered, ordered[1:]):
        if left.end_address > right.address:
            raise ValueError(f"PSP Compendium writes overlap: {left.name}, {right.name}")
    patches = tuple(
        Patch(
            "demon_compendium.runtime",
            write.name,
            write.address,
            stock[
                write.address + ADDRESS_BIAS :
                write.address + ADDRESS_BIAS + len(write.data)
            ],
            write.data,
        )
        for write in writes
    )
    output = apply_patches(intermediate, ADDRESS_BIAS, patches)
    code_used = (
        len(prose.draw_wrapper.data)
        + len(names.draw_wrapper.data)
        + len(names.compare_wrapper.data)
    )
    code_capacity = (
        COMPENDIUM_DRAW_WRAPPER_END_ADDRESS - COMPENDIUM_DRAW_WRAPPER_ADDRESS
        + COMPENDIUM_NAME_DRAW_WRAPPER_END_ADDRESS - COMPENDIUM_NAME_DRAW_WRAPPER_ADDRESS
        + COMPENDIUM_NAME_COMPARE_WRAPPER_END_ADDRESS - COMPENDIUM_NAME_COMPARE_WRAPPER_ADDRESS
    )
    fixed_tables = COMPENDIUM_POINTER_TABLE_SIZE + COMPENDIUM_NAME_TABLE_SIZE
    return CompendiumBuild(
        output,
        patches,
        text,
        prose,
        names,
        text.used_size + fixed_tables + code_used,
        COMPENDIUM_TEXT_ARENA_SIZE + fixed_tables + code_capacity,
    )


__all__ = [
    "CONFIG_PATH",
    "CompendiumBuild",
    "build_compendium",
]
