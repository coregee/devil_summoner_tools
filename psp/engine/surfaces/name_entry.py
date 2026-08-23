"""Build the five-field English PSP NAME/profile-entry surface."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterable

from .name_entry_runtime import (
    NAME_ADDRESS_DEFAULT_STORE_CONTRACTS,
    NAME_BUTTON_HELPER_ADDRESS,
    NAME_CACHE_REBUILD_ADDRESS,
    NAME_COMMIT_WRAPPER_ADDRESS,
    NAME_CONFIRM_WRAPPER_ADDRESS,
    NAME_DONE_HANDLER_ADDRESS,
    NAME_DONE_SOUND_WRAPPER_ADDRESS,
    NAME_ECHO_WRAPPER_ADDRESS,
    NAME_HOOK_CONTRACTS,
    NAME_INIT_WRAPPER_ADDRESS,
    NAME_INSTRUCTION_PATCH_CONTRACTS,
    NAME_LOAD_WRAPPER_ADDRESS,
    NAME_NEW_PROFILE_WRAPPER_ADDRESS,
    NAME_PROMPT_WRAPPER_ADDRESS,
    NAME_RENAME_SYNC_ADDRESS,
    NAME_RESET_WRAPPER_ADDRESS,
    NAME_SELECT_WRAPPER_ADDRESS,
    NameEntryPatch,
    NameEntryPatchSource,
    build_name_entry_patch,
)
from psp.text.util.name_entry import NameEntryText, load_name_entry_text

from ..core.layout import EVENT_CAPACITY_HELPER_ADDRESS
from ..core.patching import Patch, apply_patches
from .command_menu_help import load_eve_widths

RELOCATION = struct.Struct("<II")
ADDRESS_BIAS = 0x80
BOOT_SIZE = 2_404_599
BOOT_STOCK_SHA256 = "37b5b7a49fe1a5af60ab042d2822befb00580e02a7d7d2ed77dd279ebe6f55fa"
ENGINE_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ENGINE_ROOT / "config" / "name_entry.json"


def file_offset(address: int) -> int:
    return address + ADDRESS_BIAS


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True, slots=True)
class NameEntryBuild:
    data: bytes
    patches: tuple[Patch, ...]
    text: NameEntryText
    runtime: NameEntryPatch
    runtime_used_size: int
    runtime_capacity: int


def _configuration() -> dict[str, object]:
    try:
        value = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP name-entry contract: {CONFIG_PATH}") from error
    if (
        value.get("version") != 1
        or value.get("surface") != "name_entry.runtime"
        or value.get("dependency") != "event_window.runtime_foundation"
        or value.get("field_keys") != ["first", "last", "codename", "city", "ward"]
        or value.get("field_size") != 8
        or value.get("write_count") != 138
    ):
        raise ValueError("invalid PSP name-entry contract")
    return value


def _patch_source(text: NameEntryText) -> NameEntryPatchSource:
    upper, lower, symbol = text.grids
    labels = (
        None,
        text.field("first").prompt,
        upper.label,
        lower.label,
        symbol.label,
        upper.label,
        text.field("last").prompt,
        text.field("codename").prompt,
        text.field("city").prompt,
        text.field("ward").prompt,
        text.prompt_occupation,
        *text.occupations,
        text.prompt_confirm,
        text.label_yes,
        text.label_no,
        *text.occupations,
        text.field("codename").prompt,
    )
    if len(labels) != 27:
        raise ValueError("PSP name-entry descriptor inventory changed")
    return NameEntryPatchSource(
        tuple(grid.rows for grid in text.grids),
        labels,
        text.default_city,
        text.default_ward,
    )

# NAME.BIN's live screen is executable-owned.  These checks pin both the
# instructions being redirected and the otherwise unrelated data ranges that
# become the translated three-page grid and static-label pool.
NAME_ENTRY_HOOK_SOURCE_CONTRACTS = {
    **{
        name: (address, struct.pack(f"<{len(source_words)}I", *source_words))
        for name, address, source_words, replacement_words in (
            NAME_INSTRUCTION_PATCH_CONTRACTS
        )
        if source_words != replacement_words
    },
    **{
        name: (address, struct.pack("<I", source_word))
        for name, address, source_word, _replacement_word in NAME_HOOK_CONTRACTS
    },
    **{
        name: (address, struct.pack("<I", source_word))
        for name, address, source_word, _replacement_word in (
            NAME_ADDRESS_DEFAULT_STORE_CONTRACTS
        )
    },
}
NAME_ENTRY_CAVE_WRITE_ADDRESSES = {
    "name_label_draw_wrapper": 0x0013FC10,
    "name_glyph_to_byte": 0x0013FD40,
    "name_byte_to_glyph": 0x0013FDC0,
    "name_widths": 0x0013FE40,
    "name_x_starts": 0x0013FEA0,
    "name_init_wrapper": NAME_INIT_WRAPPER_ADDRESS,
    "name_prompt_wrapper": NAME_PROMPT_WRAPPER_ADDRESS,
    "name_echo_wrapper": NAME_ECHO_WRAPPER_ADDRESS,
    "name_done_handler": NAME_DONE_HANDLER_ADDRESS,
    "name_select_wrapper": NAME_SELECT_WRAPPER_ADDRESS,
    "name_button_wrapper": NAME_BUTTON_HELPER_ADDRESS,
    "name_done_sound_wrapper": NAME_DONE_SOUND_WRAPPER_ADDRESS,
    "name_confirm_wrapper": NAME_CONFIRM_WRAPPER_ADDRESS,
    "name_commit_wrapper": NAME_COMMIT_WRAPPER_ADDRESS,
    "name_cache_rebuild": NAME_CACHE_REBUILD_ADDRESS,
    "name_load_wrapper": NAME_LOAD_WRAPPER_ADDRESS,
    "name_new_profile_wrapper": NAME_NEW_PROFILE_WRAPPER_ADDRESS,
    "name_reset_wrapper": NAME_RESET_WRAPPER_ADDRESS,
    "name_rename_sync": NAME_RENAME_SYNC_ADDRESS,
}
NAME_ENTRY_DATA_SOURCE_CONTRACTS = (
    (
        "static descriptors",
        0x001C6BD4,
        216,
        "18e8f1982efbccf366c8a0f6081de08e7e8dac2e5d30c97b37e66c97c18a1008",
    ),
    (
        "primary upper grid",
        0x001C6CAC,
        304,
        "5ee9bbd48a8875db598ef7fa926e09217d350fb2c1cdc7ad3a851594991bf8d9",
    ),
    (
        "lower grid",
        0x001C8764,
        304,
        "3d3f108a9722c47e63f9105b0299a24dc68d112f300153f8e89729a24436334a",
    ),
    (
        "symbol grid",
        0x001C8894,
        304,
        "1ace43bb7efb40a3a9b941ddcaf69ad35c933a683368bab814812370c909e3f9",
    ),
    (
        "secondary upper grid",
        0x001C89C4,
        304,
        "df3211a632b482ace250d6dbc09a330b612b78404461c42888228bb8a837b927",
    ),
    (
        "primary-grid count",
        0x001C8AF8,
        4,
        "a5d962486507895f5e6395f061675d83acbb1b2adef60de0d6fc3c1485b5cdeb",
    ),
    (
        "echo coordinate pointers",
        0x001C8B84,
        28,
        "166140468a28083713fc09d00efb739c8095de49eb6f2dff8b5543b5094b3835",
    ),
    (
        "retired Kanji label reserve",
        0x001C6DDC,
        0x400,
        "38c34be6cc09e1af9c8d48852e3d383b8c73625e438f61da0bc134050d71278f",
    ),
)
NAME_ENTRY_DATA_WRITE_LAYOUT = {
    "name_echo_eight_x_pointers": (0x001C8B84, 12),
    "name_grid0_count": (0x001C8AF8, 4),
    "name_grid_upper_primary": (0x001C6CAC, 304),
    "name_grid_lower": (0x001C8764, 304),
    "name_grid_symbol": (0x001C8894, 304),
    "name_grid_upper_secondary": (0x001C89C4, 304),
    "name_label_blob": (0x001C6DDC, 0x400),
    **{
        f"name_label_descriptor_{index:02d}": (0x001C6BD4 + index * 8, 8)
        for index in range(1, 27)
    },
}
NAME_ENTRY_CONTROL_RELOCATION_CONTRACTS = (
    (0x000114A0, 0x001D6F98, RELOCATION.pack(0x000114A0, 4)),
    (0x00074A3C, 0x00213290, RELOCATION.pack(0x00074A3C, 4)),
    (0x0009CD34, 0x00224238, RELOCATION.pack(0x0009CD34, 4)),
    (0x0009CE58, 0x00224290, RELOCATION.pack(0x0009CE58, 4)),
    (0x0009D074, 0x00224398, RELOCATION.pack(0x0009D074, 4)),
    (0x0009D4A8, 0x002245D8, RELOCATION.pack(0x0009D4A8, 4)),
    (0x0009D620, 0x002246D0, RELOCATION.pack(0x0009D620, 4)),
    (0x0009D9F0, 0x00224920, RELOCATION.pack(0x0009D9F0, 4)),
    (0x0009D9FC, 0x00224928, RELOCATION.pack(0x0009D9FC, 4)),
    (0x0009DA70, 0x00224960, RELOCATION.pack(0x0009DA70, 4)),
    (0x0009DB7C, 0x00224A08, RELOCATION.pack(0x0009DB7C, 4)),
    (0x0009DEB8, 0x00224C10, RELOCATION.pack(0x0009DEB8, 4)),
    (0x0009DED4, 0x00224C20, RELOCATION.pack(0x0009DED4, 4)),
    (0x0009DF6C, 0x00224C58, RELOCATION.pack(0x0009DF6C, 4)),
    (0x0009DFD4, 0x00224CA0, RELOCATION.pack(0x0009DFD4, 4)),
    (0x0009DFEC, 0x00224CC0, RELOCATION.pack(0x0009DFEC, 4)),
    (0x0009E260, 0x00224DD0, RELOCATION.pack(0x0009E260, 4)),
    (0x0009ECAC, 0x00225100, RELOCATION.pack(0x0009ECAC, 4)),
)
NAME_ENTRY_CACHE_RELOCATION_CONTRACTS = tuple(
    (address, offset, RELOCATION.pack(address, info))
    for address, offset, info in (
        (0x73C7C, 0x212990, 0x00010005),
        (0x73C80, 0x212998, 0x00010006),
        (0x73CD0, 0x2129A8, 0x00010005),
        (0x73CD4, 0x2129B0, 0x00010006),
        (0x73D4C, 0x212A10, 0x00010005),
        (0x73D50, 0x212A18, 0x00010006),
        (0x73D68, 0x212A28, 0x00010005),
        (0x73D6C, 0x212A30, 0x00010006),
        (0x73DB8, 0x212A70, 0x00010005),
        (0x73DBC, 0x212A78, 0x00010006),
        (0x73E4C, 0x212AB0, 0x00010005),
        (0x73E54, 0x212AB8, 0x00010006),
        (0x73E70, 0x212AD0, 0x00010005),
        (0x73E78, 0x212AD8, 0x00010006),
        (0x73EE0, 0x212B38, 0x00010005),
        (0x73EE8, 0x212B40, 0x00010006),
        (0x73EF4, 0x212B50, 0x00010005),
        (0x73EFC, 0x212B58, 0x00010006),
        (0x73F38, 0x212B98, 0x00010005),
        (0x73F40, 0x212BA0, 0x00010006),
        (0x7413C, 0x212C60, 0x00010005),
        (0x74140, 0x212C68, 0x00010006),
        (0x742B8, 0x212D48, 0x00010005),
        (0x742C0, 0x212D50, 0x00010006),
        (0x761CC, 0x212E98, 0x00010005),
        (0x761E8, 0x213E68, 0x00010005),
        (0x761FC, 0x213E70, 0x00010006),
        (0x76308, 0x213E98, 0x00010006),
        (0x7631C, 0x213EB0, 0x00010005),
        (0x76320, 0x213EB8, 0x00010006),
        (0xA3708, 0x2275F0, 0x00010005),
        (0xA370C, 0x2275F8, 0x00010006),
        (0xA3794, 0x227620, 0x00010005),
        (0xA3798, 0x227628, 0x00010006),
        (0xA4254, 0x227BA0, 0x00010005),
        (0xA4258, 0x227BA8, 0x00010006),
        (0xA4288, 0x227BB8, 0x00010005),
        (0xA428C, 0x227BC0, 0x00010006),
        (0xA4420, 0x227C68, 0x00010005),
        (0xA4424, 0x227C70, 0x00010006),
        (0xAB914, 0x22B8D0, 0x00010005),
        (0xAB918, 0x22B8D8, 0x00010006),
    )
)
NAME_ENTRY_RELOCATION_CONTRACTS = (
    NAME_ENTRY_CONTROL_RELOCATION_CONTRACTS + NAME_ENTRY_CACHE_RELOCATION_CONTRACTS
)
NAME_ENTRY_STATIC_POINTER_RELOCATION_OFFSET = 0x00248350
NAME_ENTRY_STATIC_POINTER_RELOCATIONS = b"".join(
    RELOCATION.pack(0x0004C614 + index * 8, 0x00010102) for index in range(27)
)
NAME_ENTRY_GRID_POINTER_RELOCATION_OFFSET = 0x00248428
NAME_ENTRY_GRID_POINTER_RELOCATIONS = b"".join(
    RELOCATION.pack(0x0004E534 + index * 8, 0x00010102) for index in range(4)
)
NAME_ENTRY_ECHO_POINTER_RELOCATION_OFFSET = 0x00248448
NAME_ENTRY_ECHO_POINTER_RELOCATIONS = b"".join(
    RELOCATION.pack(0x0004E5C4 + index * 4, 0x00010102) for index in range(7)
)


def build_patch(
    eve_widths: Iterable[int],
    source: NameEntryPatchSource,
) -> NameEntryPatch:
    """Build the Allegrex patch for checked NAME text and EVE widths."""

    return build_name_entry_patch(eve_widths, source)


def validate_source_elf(source: bytes) -> None:
    """Verify NAME hooks, writable data ranges, and relocations."""

    for name, (address, expected) in NAME_ENTRY_HOOK_SOURCE_CONTRACTS.items():
        offset = file_offset(address)
        if source[offset : offset + len(expected)] != expected:
            raise ValueError(f"PSP name-entry hook source changed at {name}")

    for description, address, size, expected_digest in NAME_ENTRY_DATA_SOURCE_CONTRACTS:
        offset = file_offset(address)
        data = source[offset : offset + size]
        if len(data) != size or sha256(data) != expected_digest:
            raise ValueError(f"PSP name-entry {description} source changed")

    for address, offset, expected in NAME_ENTRY_RELOCATION_CONTRACTS:
        if source[offset : offset + len(expected)] != expected:
            raise ValueError(f"PSP name-entry JAL relocation changed at {address:#x}")
    pointer_contracts = (
        (
            NAME_ENTRY_STATIC_POINTER_RELOCATION_OFFSET,
            NAME_ENTRY_STATIC_POINTER_RELOCATIONS,
            "static-label pointer",
        ),
        (
            NAME_ENTRY_GRID_POINTER_RELOCATION_OFFSET,
            NAME_ENTRY_GRID_POINTER_RELOCATIONS,
            "grid pointer",
        ),
        (
            NAME_ENTRY_ECHO_POINTER_RELOCATION_OFFSET,
            NAME_ENTRY_ECHO_POINTER_RELOCATIONS,
            "echo-coordinate pointer",
        ),
    )
    for offset, expected, description in pointer_contracts:
        if source[offset : offset + len(expected)] != expected:
            raise ValueError(f"PSP name-entry {description} relocations changed")


def validate_patch_sources(source: bytes, patch: NameEntryPatch) -> None:
    """Verify the name-entry write inventory against the stock ELF."""

    expected_names = (
        frozenset(NAME_ENTRY_HOOK_SOURCE_CONTRACTS)
        | frozenset(NAME_ENTRY_CAVE_WRITE_ADDRESSES)
        | frozenset(NAME_ENTRY_DATA_WRITE_LAYOUT)
    )
    actual_names = frozenset(write.name for write in patch.writes)
    if actual_names != expected_names:
        raise ValueError("PSP name-entry write inventory changed")

    for write in patch.writes:
        before = source[write.file_offset : write.file_offset + len(write.data)]
        if len(before) != len(write.data):
            raise ValueError(f"PSP name-entry write {write.name} exceeds BOOT.BIN")
        if write.name in NAME_ENTRY_HOOK_SOURCE_CONTRACTS:
            expected_address, expected = NAME_ENTRY_HOOK_SOURCE_CONTRACTS[write.name]
            if write.address != expected_address or before != expected:
                raise ValueError(f"PSP name-entry hook source changed at {write.name}")
        elif write.name in NAME_ENTRY_CAVE_WRITE_ADDRESSES:
            expected_address = NAME_ENTRY_CAVE_WRITE_ADDRESSES[write.name]
            if write.address != expected_address:
                raise ValueError(f"PSP name-entry cave address changed at {write.name}")
            if not write.data or any(before):
                raise ValueError(f"PSP name-entry cave source changed at {write.name}")
        elif write.name in NAME_ENTRY_DATA_WRITE_LAYOUT:
            expected_address, expected_size = NAME_ENTRY_DATA_WRITE_LAYOUT[write.name]
            if write.address != expected_address or len(write.data) != expected_size:
                raise ValueError(f"PSP name-entry data layout changed at {write.name}")
        else:  # The exact inventory check above makes this defensive only.
            raise ValueError(f"unknown PSP name-entry write: {write.name}")


def build_name_entry(stock: bytes, intermediate: bytes) -> NameEntryBuild:
    """Apply NAME after the packed EVENT renderer that consumes its cache."""

    _configuration()
    if len(stock) != BOOT_SIZE or sha256(stock) != BOOT_STOCK_SHA256:
        raise ValueError("PSP name-entry BOOT source contract changed")
    if not isinstance(intermediate, bytes) or len(intermediate) != len(stock):
        raise ValueError("PSP name-entry intermediate BOOT size changed")
    dependency = intermediate[
        file_offset(EVENT_CAPACITY_HELPER_ADDRESS) : file_offset(EVENT_CAPACITY_HELPER_ADDRESS + 4)
    ]
    if not any(dependency):
        raise ValueError("PSP name entry requires the EVENT runtime foundation")

    text = load_name_entry_text()
    runtime = build_patch(load_eve_widths(), _patch_source(text))
    validate_source_elf(stock)
    validate_patch_sources(stock, runtime)
    patches = tuple(
        Patch(
            "name_entry.runtime",
            write.name,
            write.address,
            stock[write.file_offset : write.file_offset + len(write.data)],
            write.data,
        )
        for write in runtime.writes
    )
    output = apply_patches(intermediate, ADDRESS_BIAS, patches)
    used = sum(
        len(write.data)
        for write in runtime.writes
        if write.name in NAME_ENTRY_CAVE_WRITE_ADDRESSES
    )
    capacity = 0x00140B70 - 0x0013FC10
    return NameEntryBuild(output, patches, text, runtime, used, capacity)


__all__ = [
    "CONFIG_PATH",
    "NAME_ENTRY_CACHE_RELOCATION_CONTRACTS",
    "NAME_ENTRY_CAVE_WRITE_ADDRESSES",
    "NAME_ENTRY_CONTROL_RELOCATION_CONTRACTS",
    "NAME_ENTRY_DATA_SOURCE_CONTRACTS",
    "NAME_ENTRY_DATA_WRITE_LAYOUT",
    "NAME_ENTRY_ECHO_POINTER_RELOCATIONS",
    "NAME_ENTRY_ECHO_POINTER_RELOCATION_OFFSET",
    "NAME_ENTRY_GRID_POINTER_RELOCATIONS",
    "NAME_ENTRY_GRID_POINTER_RELOCATION_OFFSET",
    "NAME_ENTRY_HOOK_SOURCE_CONTRACTS",
    "NAME_ENTRY_RELOCATION_CONTRACTS",
    "NAME_ENTRY_STATIC_POINTER_RELOCATIONS",
    "NAME_ENTRY_STATIC_POINTER_RELOCATION_OFFSET",
    "NameEntryBuild",
    "build_name_entry",
    "build_patch",
    "validate_patch_sources",
    "validate_source_elf",
]
