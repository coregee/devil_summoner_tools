"""Build the English PSP savedata utility and SFO-detail surface."""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .savedata_runtime import (
    SAVEDATA_CANCEL_LOAD_ADDRESS,
    SAVEDATA_CANCEL_SAVE_ADDRESS,
    SAVEDATA_DETAIL_FUNCTION_ADDRESS,
    SAVEDATA_DETAIL_TRAMPOLINE_ADDRESS,
    SAVEDATA_DETAIL_WRAPPER_ADDRESS,
    SAVEDATA_GAME_TITLE_ADDRESS,
    SAVEDATA_LANGUAGE_LOAD_ADDRESS,
    SAVEDATA_LANGUAGE_STORE_ADDRESS,
    SAVEDATA_LOCATION_ID_TABLE_ADDRESS,
    SAVEDATA_LOCATION_NAME_COUNT,
    SAVEDATA_LOCATION_OFFSET_TABLE_ADDRESS,
    SAVEDATA_LOCATION_RECORD_COUNT,
    SAVEDATA_LOCATION_TEXT_BLOB_ADDRESS,
    SAVEDATA_LOCATION_TEXT_CAVE_END_ADDRESS,
    SAVEDATA_SLOT_TITLE_ADDRESS,
    SAVEDATA_TABLE_CAVE_END_ADDRESS,
    SAVEDATA_TABLE_CAVE_SOURCE_START_ADDRESS,
    SAVEDATA_TEXT_BLOB_ADDRESS,
    SavedataPatch,
    SavedataPatchSource,
    build_savedata_patch,
)
from psp.text.util.savedata import SavedataText, load_savedata_text

from ..core.layout import (
    CONFIG_CAVE_END_ADDRESS,
    ITEM_DESCRIPTION_DRAW_WRAPPER_ADDRESS,
    SAVEDATA_LOCATION_RECORD_SIZE,
    SAVEDATA_LOCATION_SOURCE_ADDRESS,
)
from ..core.patching import Patch, apply_patches
from .name_entry_runtime import NAME_INIT_WRAPPER_ADDRESS

ADDRESS_BIAS = 0x80
BOOT_SIZE = 2_404_599
BOOT_STOCK_SHA256 = "37b5b7a49fe1a5af60ab042d2822befb00580e02a7d7d2ed77dd279ebe6f55fa"
ENGINE_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ENGINE_ROOT / "config" / "savedata.json"
_RELOCATION = struct.Struct("<II")
_RELOCATION_SECTIONS = (
    (0x001CD9E8, 0x00068ED8),
    (0x00236B28, 0x00006180),
    (0x0023CCA8, 0x0000C510),
)


def file_offset(address: int) -> int:
    return address + ADDRESS_BIAS


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def iter_relocations(source: bytes):
    for offset, size in _RELOCATION_SECTIONS:
        for cursor in range(offset, offset + size, _RELOCATION.size):
            yield _RELOCATION.unpack_from(source, cursor)


@dataclass(frozen=True, slots=True)
class SavedataBuild:
    data: bytes
    patches: tuple[Patch, ...]
    text: SavedataText
    runtime: SavedataPatch
    runtime_used_size: int
    runtime_capacity: int


def _configuration() -> dict[str, object]:
    try:
        value = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP savedata contract: {CONFIG_PATH}") from error
    if (
        value.get("version") != 1
        or value.get("surface") != "savedata.runtime"
        or value.get("dependency") != "name_entry.runtime"
        or value.get("location_record_count") != SAVEDATA_LOCATION_RECORD_COUNT
        or value.get("location_name_count") != SAVEDATA_LOCATION_NAME_COUNT
        or value.get("write_count") != 13
    ):
        raise ValueError("invalid PSP savedata contract")
    return value


def _patch_source(text: SavedataText) -> SavedataPatchSource:
    return SavedataPatchSource(
        text.game_title,
        text.slot_title,
        text.detail_title,
        text.difficulties,
        text.cancel_load,
        text.cancel_save,
        text.home,
        text.office,
        text.unknown,
        text.locations,
    )

# The savedata utility initializer clears its whole 0x600-byte parameter block,
# then explicitly reuses two redundant zero writes.  Those exact words become
# ``language = English`` without altering the Japanese confirm-button setting.
# The stock detail formatter is replaced at function entry, so its callers and
# their JAL relocations remain intact.  Its first eight bytes branch to a
# relocation-free slice of the now-dead function body; that trampoline derives
# the runtime load base before tail-jumping to the distant second-cave wrapper.
SAVEDATA_HOOK_SOURCE_CONTRACTS = {
    "savedata_language_one": (
        SAVEDATA_LANGUAGE_LOAD_ADDRESS,
        bytes.fromhex("08 00 00 ae"),
    ),
    "savedata_language_store": (
        SAVEDATA_LANGUAGE_STORE_ADDRESS,
        bytes.fromhex("ec 05 00 ae"),
    ),
    "savedata_game_title": (
        SAVEDATA_GAME_TITLE_ADDRESS,
        b"DEVIL SUMMONER\0\0",
    ),
    "savedata_slot_title": (
        SAVEDATA_SLOT_TITLE_ADDRESS,
        b"DEVIL SUMMONER SAVE DATA\0\0\0\0",
    ),
    "savedata_cancel_load": (
        SAVEDATA_CANCEL_LOAD_ADDRESS,
        bytes.fromhex(
            "e3 83 ad e3 83 bc e3 83 89 e5 87 a6 e7 90 86 e3 82 92 "
            "e4 b8 ad e6 96 ad e3 81 97 e3 81 be e3 81 99 e3 81 8b "
            "ef bc 9f 00"
        ),
    ),
    "savedata_cancel_save": (
        SAVEDATA_CANCEL_SAVE_ADDRESS,
        bytes.fromhex(
            "e3 82 bb e3 83 bc e3 83 96 e5 87 a6 e7 90 86 e3 82 92 "
            "e4 b8 ad e6 96 ad e3 81 97 e3 81 be e3 81 99 e3 81 8b "
            "ef bc 9f 00"
        ),
    ),
    "savedata_detail_dispatch": (
        SAVEDATA_DETAIL_FUNCTION_ADDRESS,
        bytes.fromhex("00 ff bd 27 ec 00 b3 af"),
    ),
    "savedata_detail_trampoline": (
        SAVEDATA_DETAIL_TRAMPOLINE_ADDRESS,
        bytes.fromhex(
            "e8 00 b2 af 21 18 80 00 ff ff 73 30 e0 00 b0 af "
            "21 20 a0 03 21 28 00 00 f4 00 bf af 60 00 06 24 "
            "21 90 00 00"
        ),
    ),
}
SAVEDATA_CAVE_WRITE_ADDRESSES = {
    "savedata_detail_wrapper": SAVEDATA_DETAIL_WRAPPER_ADDRESS,
    "savedata_location_ids": SAVEDATA_LOCATION_ID_TABLE_ADDRESS,
    "savedata_location_offsets": SAVEDATA_LOCATION_OFFSET_TABLE_ADDRESS,
    "savedata_text_blob": SAVEDATA_TEXT_BLOB_ADDRESS,
    "savedata_location_text_blob": SAVEDATA_LOCATION_TEXT_BLOB_ADDRESS,
}
SAVEDATA_RUNTIME_SOURCE_CONTRACTS = {
    "elapsed_time_call": (0x000119E8, bytes.fromhex("20 31 00 0c")),
    "playtime_pointer_hi": (0x000119F0, bytes.fromhex("05 00 04 3c")),
    "playtime_pointer_lo": (0x000119F4, bytes.fromhex("e4 43 83 8c")),
    "level_pointer_hi": (0x00011840, bytes.fromhex("3e 00 02 3c")),
    "level_pointer_lo": (0x00011844, bytes.fromhex("46 f6 51 94")),
    "difficulty_pointer_hi": (0x00011914, bytes.fromhex("3f 00 02 3c")),
    "difficulty_pointer_lo": (0x00011924, bytes.fromhex("b0 6d 45 8c")),
    "detail_buffer_pointer_hi": (0x00011CD4, bytes.fromhex("07 00 04 3c")),
    "detail_buffer_pointer_lo": (0x00011CE4, bytes.fromhex("44 62 84 24")),
}
SAVEDATA_RUNTIME_RELOCATION_CONTRACTS = frozenset(
    {
        (0x000119E8, 0x00000004),
        (0x000119F0, 0x00010005),
        (0x000119F4, 0x00010006),
        (0x00011840, 0x00010005),
        (0x00011844, 0x00010006),
        (0x00011914, 0x00010005),
        (0x00011924, 0x00010006),
        (0x00011CD4, 0x00010005),
        (0x00011CE4, 0x00010006),
    }
)
SAVEDATA_LOCATION_SOURCE_SHA256 = (
    "54371483ee91ca5d913d675a8ae6aeaf2cd8af0bf5a59dded2d69c1fdde9e9f4"
)


def _location_record_ids(source: bytes) -> tuple[int, ...]:
    """Map 144 PSP records to the shared first-occurrence location order."""

    offset = file_offset(SAVEDATA_LOCATION_SOURCE_ADDRESS)
    size = SAVEDATA_LOCATION_RECORD_COUNT * SAVEDATA_LOCATION_RECORD_SIZE
    table = source[offset : offset + size]
    if len(table) != size or sha256(table) != SAVEDATA_LOCATION_SOURCE_SHA256:
        raise ValueError("PSP savedata location table source changed")
    identities: dict[bytes, int] = {}
    record_ids: list[int] = []
    for index in range(SAVEDATA_LOCATION_RECORD_COUNT):
        record = table[
            index * SAVEDATA_LOCATION_RECORD_SIZE : (index + 1)
            * SAVEDATA_LOCATION_RECORD_SIZE
        ]
        identity = record[2:10]
        record_ids.append(identities.setdefault(identity, len(identities)))
    if len(identities) != SAVEDATA_LOCATION_NAME_COUNT:
        raise ValueError(
            f"PSP savedata location table has {len(identities)} names; "
            f"expected {SAVEDATA_LOCATION_NAME_COUNT}"
        )
    return tuple(record_ids)


def build_patch(
    source: SavedataPatchSource,
    record_ids: Iterable[int],
) -> SavedataPatch:
    """Build the Allegrex patch for checked savedata text and record IDs."""

    return build_savedata_patch(source, record_ids)


def validate_source_elf(source: bytes) -> tuple[int, ...]:
    """Validate savedata source contracts and return physical record IDs."""

    for name, (address, expected) in SAVEDATA_HOOK_SOURCE_CONTRACTS.items():
        offset = file_offset(address)
        if source[offset : offset + len(expected)] != expected:
            raise ValueError(f"PSP savedata hook source changed at {name}")
    for name, (address, expected) in SAVEDATA_RUNTIME_SOURCE_CONTRACTS.items():
        offset = file_offset(address)
        if source[offset : offset + len(expected)] != expected:
            raise ValueError(f"PSP savedata runtime source changed at {name}")

    relocations = tuple(iter_relocations(source))
    if not SAVEDATA_RUNTIME_RELOCATION_CONTRACTS.issubset(relocations):
        raise ValueError("PSP savedata runtime relocations changed")
    trampoline_end = SAVEDATA_DETAIL_TRAMPOLINE_ADDRESS + len(
        SAVEDATA_HOOK_SOURCE_CONTRACTS["savedata_detail_trampoline"][1]
    )
    if any(
        SAVEDATA_DETAIL_TRAMPOLINE_ADDRESS <= address < trampoline_end
        for address, _info in relocations
    ):
        raise ValueError("PSP BOOT.BIN has a relocation inside the savedata trampoline")
    if any(
        (
            SAVEDATA_DETAIL_WRAPPER_ADDRESS <= address < CONFIG_CAVE_END_ADDRESS
            or SAVEDATA_TABLE_CAVE_SOURCE_START_ADDRESS
            <= address
            < SAVEDATA_TABLE_CAVE_END_ADDRESS
            or SAVEDATA_LOCATION_TEXT_BLOB_ADDRESS
            <= address
            < SAVEDATA_LOCATION_TEXT_CAVE_END_ADDRESS
        )
        for address, _info in relocations
    ):
        raise ValueError("PSP BOOT.BIN has a relocation inside the savedata cave")
    for description, start, end in (
        ("code", SAVEDATA_DETAIL_WRAPPER_ADDRESS, CONFIG_CAVE_END_ADDRESS),
        (
            "table",
            SAVEDATA_TABLE_CAVE_SOURCE_START_ADDRESS,
            SAVEDATA_TABLE_CAVE_END_ADDRESS,
        ),
        (
            "location text",
            SAVEDATA_LOCATION_TEXT_BLOB_ADDRESS,
            SAVEDATA_LOCATION_TEXT_CAVE_END_ADDRESS,
        ),
    ):
        cave_start = file_offset(start)
        cave_end = file_offset(end)
        if any(source[cave_start:cave_end]):
            raise ValueError(
                f"PSP savedata {description} cave is no longer source-blank"
            )
    return _location_record_ids(source)


def validate_patch_sources(source: bytes, patch: SavedataPatch) -> None:
    """Verify the savedata write inventory against the stock ELF."""

    expected_names = frozenset(SAVEDATA_HOOK_SOURCE_CONTRACTS) | frozenset(
        SAVEDATA_CAVE_WRITE_ADDRESSES
    )
    actual_names = frozenset(write.name for write in patch.writes)
    if actual_names != expected_names:
        raise ValueError("PSP savedata write inventory changed")

    for write in patch.writes:
        before = source[write.file_offset : write.file_offset + len(write.data)]
        if len(before) != len(write.data):
            raise ValueError(f"PSP savedata write {write.name} exceeds BOOT.BIN")
        if write.name in SAVEDATA_HOOK_SOURCE_CONTRACTS:
            expected_address, expected = SAVEDATA_HOOK_SOURCE_CONTRACTS[write.name]
            if write.address != expected_address or before != expected:
                raise ValueError(f"PSP savedata hook source changed at {write.name}")
        elif write.name in SAVEDATA_CAVE_WRITE_ADDRESSES:
            expected_address = SAVEDATA_CAVE_WRITE_ADDRESSES[write.name]
            if write.address != expected_address or not write.data or any(before):
                raise ValueError(f"PSP savedata cave source changed at {write.name}")
        else:  # The exact inventory check above makes this defensive only.
            raise ValueError(f"unknown PSP savedata write: {write.name}")


def build_savedata(stock: bytes, intermediate: bytes) -> SavedataBuild:
    """Apply English utility metadata after NAME establishes profile bytes."""

    _configuration()
    if len(stock) != BOOT_SIZE or sha256(stock) != BOOT_STOCK_SHA256:
        raise ValueError("PSP savedata BOOT source contract changed")
    if not isinstance(intermediate, bytes) or len(intermediate) != len(stock):
        raise ValueError("PSP savedata intermediate BOOT size changed")
    dependency = intermediate[
        file_offset(NAME_INIT_WRAPPER_ADDRESS) : file_offset(NAME_INIT_WRAPPER_ADDRESS + 4)
    ]
    if not any(dependency):
        raise ValueError("PSP savedata requires the English NAME runtime")

    text = load_savedata_text()
    record_ids = validate_source_elf(stock)
    runtime = build_patch(_patch_source(text), record_ids)
    validate_patch_sources(stock, runtime)
    patches = tuple(
        Patch(
            "savedata.runtime",
            write.name,
            write.address,
            stock[write.file_offset : write.file_offset + len(write.data)],
            write.data,
        )
        for write in runtime.writes
    )
    output = apply_patches(intermediate, ADDRESS_BIAS, patches)
    used = (
        len(runtime.detail_wrapper.data)
        + len(runtime.location_ids)
        + len(runtime.location_offsets)
        + len(runtime.text_blob)
        + len(runtime.location_text_blob)
    )
    capacity = (
        ITEM_DESCRIPTION_DRAW_WRAPPER_ADDRESS - SAVEDATA_DETAIL_WRAPPER_ADDRESS
        + SAVEDATA_TABLE_CAVE_END_ADDRESS - SAVEDATA_TABLE_CAVE_SOURCE_START_ADDRESS
        + SAVEDATA_LOCATION_TEXT_CAVE_END_ADDRESS - SAVEDATA_LOCATION_TEXT_BLOB_ADDRESS
    )
    return SavedataBuild(output, patches, text, runtime, used, capacity)


__all__ = [
    "CONFIG_PATH",
    "SAVEDATA_CAVE_WRITE_ADDRESSES",
    "SAVEDATA_HOOK_SOURCE_CONTRACTS",
    "SAVEDATA_LOCATION_SOURCE_SHA256",
    "SAVEDATA_RUNTIME_RELOCATION_CONTRACTS",
    "SAVEDATA_RUNTIME_SOURCE_CONTRACTS",
    "SavedataBuild",
    "build_savedata",
    "build_patch",
    "validate_patch_sources",
    "validate_source_elf",
]
