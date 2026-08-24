"""Validate and compose the English PSP maze location-display patch."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path

from ..core.layout import (
    DUNGEON_LOCATION_CAVE_END_ADDRESS,
    DUNGEON_LOCATION_CAVE_SOURCE_START_ADDRESS,
    DUNGEON_LOCATION_FLOOR_DRAW_WRAPPER_ADDRESS,
    DUNGEON_LOCATION_MAZE_NAME_DRAW_WRAPPER_ADDRESS,
    DUNGEON_LOCATION_MAZE_STAGE_WRAPPER_ADDRESS,
    DUNGEON_LOCATION_NAME_DESCRIPTOR_TABLE_ADDRESS,
    DUNGEON_LOCATION_NAME_SEQUENCE_CAVE_END_ADDRESS,
    DUNGEON_LOCATION_NAME_SEQUENCE_CAVE_SOURCE_START_ADDRESS,
    DUNGEON_LOCATION_NAME_SEQUENCE_TABLE_ADDRESS,
    DUNGEON_LOCATION_STATE_ADDRESS,
    DUNGEON_LOCATION_STATE_END_ADDRESS,
    DUNGEON_LOCATION_TRANSITION_NAME_BRIDGE_ADDRESS,
    SAVEDATA_LOCATION_ID_TABLE_ADDRESS,
    SAVEDATA_LOCATION_RECORD_COUNT,
)
from ..core.patching import Patch, apply_patches
from .dungeon_locations_runtime import (
    DUNGEON_LOCATION_MAZE_FLOOR_DRAW_CALL_ADDRESS,
    DUNGEON_LOCATION_MAZE_NAME_DRAW_CALL_ADDRESS,
    DUNGEON_LOCATION_MAZE_STAGE_CALL_ADDRESSES,
    DUNGEON_LOCATION_TRANSITION_FLOOR_DRAW_CALL_ADDRESS,
    DUNGEON_LOCATION_TRANSITION_NAME_DRAW_CALL_ADDRESS,
    DungeonLocationPatch,
    build_dungeon_location_patch,
)
from .savedata import file_offset, iter_relocations
from psp.text.util.savedata import load_savedata_text


ENGINE_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ENGINE_ROOT / "config" / "dungeon_locations.json"
BOOT_SIZE = 2_404_599
BOOT_STOCK_SHA256 = "37b5b7a49fe1a5af60ab042d2822befb00580e02a7d7d2ed77dd279ebe6f55fa"
ADDRESS_BIAS = 0x80
RELOCATION = struct.Struct("<II")

DUNGEON_LOCATION_DRAW_CALL_CONTRACTS = (
    (
        "dungeon_location_maze_name_draw_call",
        DUNGEON_LOCATION_MAZE_NAME_DRAW_CALL_ADDRESS,
        0x001DA078,
        bytes.fromhex("66 32 00 0c ff ff 08 24"),
    ),
    (
        "dungeon_location_maze_floor_draw_call",
        DUNGEON_LOCATION_MAZE_FLOOR_DRAW_CALL_ADDRESS,
        0x001DA0A0,
        bytes.fromhex("66 32 00 0c ff ff 08 24"),
    ),
    (
        "dungeon_location_transition_name_draw_call",
        DUNGEON_LOCATION_TRANSITION_NAME_DRAW_CALL_ADDRESS,
        0x001F9D70,
        bytes.fromhex("66 32 00 0c 01 00 10 26"),
    ),
    (
        "dungeon_location_transition_floor_draw_call",
        DUNGEON_LOCATION_TRANSITION_FLOOR_DRAW_CALL_ADDRESS,
        0x001F9D88,
        bytes.fromhex("66 32 00 0c ff ff 10 26"),
    ),
)
DUNGEON_LOCATION_STAGE_CALL_CONTRACTS = tuple(
    (name, address, relocation_offset, bytes.fromhex(source))
    for name, address, relocation_offset, source in zip(
        tuple(
            f"dungeon_location_maze_stage_call_{index}"
            for index in range(len(DUNGEON_LOCATION_MAZE_STAGE_CALL_ADDRESSES))
        ),
        DUNGEON_LOCATION_MAZE_STAGE_CALL_ADDRESSES,
        (
            0x001DB788, 0x001DD528, 0x001DD5C8, 0x001DD670, 0x001DD6F8,
            0x001DD790, 0x001DD810, 0x001DF798, 0x001E1E48, 0x001E4B78,
        ),
        (
            "d5 58 00 0c f4 6a c0 af",
            "d5 58 00 0c 21 28 a3 00",
            "d5 58 00 0c 21 28 a3 00",
            "d5 58 00 0c 21 28 a3 00",
            "d5 58 00 0c 21 28 a3 00",
            "d5 58 00 0c 21 28 a3 00",
            "d5 58 00 0c 21 28 a3 00",
            "d5 58 00 0c 00 6b 40 ac",
            "d5 58 00 0c 12 00 a5 24",
            "d5 58 00 0c 5e 00 a5 24",
        ),
        strict=True,
    )
)
DUNGEON_LOCATION_OWNER_CONTRACTS = (
    (
        "maze_stage_function",
        0x00016354,
        bytes.fromhex(
            "ff 00 84 30 0c 00 87 2c 0b 00 02 24 0a 20 47 00 "
            "3e 00 03 3c 30 7d 64 a0 38 00 02 3c 04 87 42 24 "
            "03 00 a3 88 00 00 a3 98 07 00 a4 88 04 00 a4 98 "
            "03 00 43 a8 00 00 43 b8 07 00 44 a8 04 00 44 b8 "
            "36 00 03 3c 01 00 04 24 07 00 02 3c 36 7c 66 a0 "
            "08 00 e0 03 a0 6a 44 ac"
        ),
    ),
    (
        "transition_location_selector_store",
        0x00048AD0,
        bytes.fromhex(
            "07 00 02 3c 3f 00 03 3c 6c 6d 50 a4 07 00 02 3c "
            "0f bd 70 a0 07 00 03 3c 6a 6d 50 a4 3f 00 02 3c"
        ),
    ),
    (
        "transition_location_draw_selector",
        0x00048C88,
        bytes.fromhex(
            "00 00 02 3c c0 32 52 24 60 00 11 24 6a 6d a2 96 "
            "21 20 20 02 13 00 05 24 00 11 02 00 21 10 50 00 "
            "40 10 02 00 21 10 52 00 02 00 47 94 05 00 06 24 "
            "ff ff 08 24"
        ),
    ),
    (
        "maze_hud_draw_dispatch",
        0x00016430,
        bytes.fromhex(
            "38 00 04 3c c3 59 00 0c 04 87 84 24 36 00 02 3c "
            "ef 59 00 0c 36 7c 44 80"
        ),
    ),
    (
        "maze_name_draw_loop",
        0x00016764,
        bytes.fromhex(
            "40 20 10 00 21 10 93 00 00 00 47 94 21 20 92 00 "
            "c0 20 04 00 06 00 84 24 f8 ff 25 26 04 00 06 24 "
            "66 32 00 0c ff ff 08 24 01 00 02 26"
        ),
    ),
    (
        "maze_floor_draw_loop",
        0x0001686C,
        bytes.fromhex(
            "40 20 10 00 21 10 9d 00 00 00 47 94 21 20 92 00 "
            "c0 20 04 00 06 00 84 24 f8 ff 25 26 04 00 06 24 "
            "66 32 00 0c ff ff 08 24 01 00 02 26"
        ),
    ),
)
DUNGEON_LOCATION_CAVE_WRITE_ADDRESSES = {
    "dungeon_location_maze_name_draw_wrapper": DUNGEON_LOCATION_MAZE_NAME_DRAW_WRAPPER_ADDRESS,
    "dungeon_location_floor_draw_wrapper": DUNGEON_LOCATION_FLOOR_DRAW_WRAPPER_ADDRESS,
    "dungeon_location_maze_stage_wrapper": DUNGEON_LOCATION_MAZE_STAGE_WRAPPER_ADDRESS,
    "dungeon_location_name_descriptors": DUNGEON_LOCATION_NAME_DESCRIPTOR_TABLE_ADDRESS,
    "dungeon_location_transition_name_bridge": DUNGEON_LOCATION_TRANSITION_NAME_BRIDGE_ADDRESS,
    "dungeon_location_name_sequence": DUNGEON_LOCATION_NAME_SEQUENCE_TABLE_ADDRESS,
    "dungeon_location_state": DUNGEON_LOCATION_STATE_ADDRESS,
}


@dataclass(frozen=True, slots=True)
class DungeonLocationBuild:
    data: bytes
    patches: tuple[Patch, ...]
    runtime: DungeonLocationPatch
    runtime_used_size: int
    runtime_capacity: int


def _configuration() -> dict[str, object]:
    try:
        value = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP dungeon-location contract: {CONFIG_PATH}") from error
    if (
        value.get("version") != 1
        or value.get("surface") != "maze.location_display"
        or value.get("dependency") != "savedata.runtime"
        or value.get("font_dependency") != "dungeon_locations.font16"
        or value.get("write_count") != 21
        or value.get("write_fingerprint")
        != "bd7b360d9532bfeba5724d8c174a3b81c7e6e6999eee96f0df09bd656f0b884b"
    ):
        raise ValueError("invalid PSP dungeon-location contract")
    return value


def _font_plan(contract: dict[str, object]) -> tuple[tuple[tuple[int, int, int], ...], tuple[int, ...], int, int]:
    records = contract.get("records")
    digit_codes = contract.get("digit_codes")
    basement_code = contract.get("basement_code")
    floor_code = contract.get("floor_code")
    if (
        contract.get("required_draw_code_limit") != 0x06E4
        or not isinstance(records, list)
        or len(records) != 24
        or not isinstance(digit_codes, list)
        or any(type(code) is not int for code in digit_codes)
        or type(basement_code) is not int
        or type(floor_code) is not int
    ):
        raise ValueError("PSP font manifest has no dungeon-location contract")
    locations = load_savedata_text().locations
    built_records = []
    for location_id, (record, location) in enumerate(zip(records, locations, strict=True)):
        glyphs = record.get("glyphs") if isinstance(record, dict) else None
        if (
            not isinstance(record, dict)
            or set(record) != {"location_id", "text", "lines", "glyphs"}
            or record.get("location_id") != location_id
            or record.get("text") != location
            or not isinstance(glyphs, list)
        ):
            raise ValueError("PSP dungeon-location font records are invalid")
        built = []
        for glyph in glyphs:
            if (
                not isinstance(glyph, dict)
                or set(glyph) != {"character", "code", "x", "row", "advance"}
                or not isinstance(glyph["character"], str)
                or len(glyph["character"]) != 1
                or any(type(glyph[key]) is not int for key in ("code", "x", "row", "advance"))
            ):
                raise ValueError("PSP dungeon-location font glyph is invalid")
            built.append((glyph["code"], glyph["x"], glyph["row"]))
        built_records.append(tuple(built))
    return tuple(built_records), tuple(digit_codes), basement_code, floor_code


def validate_source_elf(source: bytes) -> None:
    for name, address, expected in DUNGEON_LOCATION_OWNER_CONTRACTS:
        if source[file_offset(address) : file_offset(address) + len(expected)] != expected:
            raise ValueError(f"PSP dungeon-location owner changed at {name}")
    calls = DUNGEON_LOCATION_DRAW_CALL_CONTRACTS + DUNGEON_LOCATION_STAGE_CALL_CONTRACTS
    for name, address, relocation_offset, expected in calls:
        if source[file_offset(address) : file_offset(address) + len(expected)] != expected:
            raise ValueError(f"PSP dungeon-location call changed at {name}")
        if source[relocation_offset : relocation_offset + 8] != RELOCATION.pack(address, 4):
            raise ValueError(f"PSP dungeon-location relocation changed at {address:#x}")
    relocations = tuple(iter_relocations(source))
    if any(
        DUNGEON_LOCATION_CAVE_SOURCE_START_ADDRESS <= address < DUNGEON_LOCATION_CAVE_END_ADDRESS
        or DUNGEON_LOCATION_NAME_SEQUENCE_CAVE_SOURCE_START_ADDRESS <= address < DUNGEON_LOCATION_NAME_SEQUENCE_CAVE_END_ADDRESS
        or DUNGEON_LOCATION_STATE_ADDRESS <= address < DUNGEON_LOCATION_STATE_END_ADDRESS
        for address, _info in relocations
    ):
        raise ValueError("PSP BOOT.BIN has a relocation inside the dungeon cave")
    for description, start, end in (
        ("code", DUNGEON_LOCATION_CAVE_SOURCE_START_ADDRESS, DUNGEON_LOCATION_CAVE_END_ADDRESS),
        ("sequence", DUNGEON_LOCATION_NAME_SEQUENCE_CAVE_SOURCE_START_ADDRESS, DUNGEON_LOCATION_NAME_SEQUENCE_CAVE_END_ADDRESS),
        ("state", DUNGEON_LOCATION_STATE_ADDRESS, DUNGEON_LOCATION_STATE_END_ADDRESS),
    ):
        if any(source[file_offset(start) : file_offset(end)]):
            raise ValueError(f"PSP dungeon-location {description} cave is no longer source-blank")


def build_dungeon_locations(
    stock: bytes,
    intermediate: bytes,
    font_contract: dict[str, object],
) -> DungeonLocationBuild:
    configuration = _configuration()
    if len(stock) != BOOT_SIZE or hashlib.sha256(stock).hexdigest() != BOOT_STOCK_SHA256:
        raise ValueError("PSP dungeon-location BOOT source contract changed")
    if not isinstance(intermediate, bytes) or len(intermediate) != len(stock):
        raise ValueError("PSP dungeon-location intermediate BOOT size changed")
    location_ids = intermediate[
        file_offset(SAVEDATA_LOCATION_ID_TABLE_ADDRESS) :
        file_offset(SAVEDATA_LOCATION_ID_TABLE_ADDRESS + SAVEDATA_LOCATION_RECORD_COUNT)
    ]
    if len(location_ids) != SAVEDATA_LOCATION_RECORD_COUNT or set(location_ids) != set(range(24)):
        raise ValueError("PSP dungeon-location runtime requires the savedata selector")
    validate_source_elf(stock)
    records, digit_codes, basement_code, floor_code = _font_plan(font_contract)
    runtime = build_dungeon_location_patch(
        records,
        digit_codes,
        basement_code=basement_code,
        floor_code=floor_code,
    )
    fingerprint = hashlib.sha256(b"".join(write.data for write in runtime.writes)).hexdigest()
    if fingerprint != configuration["write_fingerprint"]:
        raise ValueError("PSP dungeon-location runtime emitter contract changed")
    source_calls = {
        name: (address, expected[:4])
        for name, address, _relocation, expected in (
            DUNGEON_LOCATION_DRAW_CALL_CONTRACTS + DUNGEON_LOCATION_STAGE_CALL_CONTRACTS
        )
    }
    expected_names = frozenset(source_calls) | frozenset(
        DUNGEON_LOCATION_CAVE_WRITE_ADDRESSES
    )
    if frozenset(write.name for write in runtime.writes) != expected_names:
        raise ValueError("PSP dungeon-location write inventory changed")
    patches = []
    for write in runtime.writes:
        before = stock[write.file_offset : write.file_offset + len(write.data)]
        if write.name in source_calls:
            expected_address, expected = source_calls[write.name]
            if write.address != expected_address or before != expected:
                raise ValueError(f"PSP dungeon-location hook changed at {write.name}")
        else:
            expected_address = DUNGEON_LOCATION_CAVE_WRITE_ADDRESSES[write.name]
            if write.address != expected_address or not write.data or any(before):
                raise ValueError(f"PSP dungeon-location cave changed at {write.name}")
        patches.append(Patch("maze.location_display", write.name, write.address, before, write.data))
    output = apply_patches(intermediate, ADDRESS_BIAS, tuple(patches))
    used = sum(len(write.data) for write in runtime.writes if write.name not in source_calls)
    capacity = (
        DUNGEON_LOCATION_CAVE_END_ADDRESS - DUNGEON_LOCATION_CAVE_SOURCE_START_ADDRESS
        + DUNGEON_LOCATION_NAME_SEQUENCE_CAVE_END_ADDRESS - DUNGEON_LOCATION_NAME_SEQUENCE_CAVE_SOURCE_START_ADDRESS
        + DUNGEON_LOCATION_STATE_END_ADDRESS - DUNGEON_LOCATION_STATE_ADDRESS
    )
    return DungeonLocationBuild(output, tuple(patches), runtime, used, capacity)


__all__ = [
    "CONFIG_PATH",
    "DUNGEON_LOCATION_DRAW_CALL_CONTRACTS",
    "DUNGEON_LOCATION_OWNER_CONTRACTS",
    "DUNGEON_LOCATION_STAGE_CALL_CONTRACTS",
    "DungeonLocationBuild",
    "build_dungeon_locations",
    "validate_source_elf",
]
