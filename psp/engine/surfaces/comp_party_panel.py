"""Pinned BOOT.BIN binding for the common six-card party-card name path."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path

from ..core.layout import (
    COMP_PARTY_NAME_CAVE_END_ADDRESS,
    COMP_PARTY_NAME_CHARACTER_TABLE_ADDRESS,
    COMP_PARTY_NAME_DRAW_WRAPPER_ADDRESS,
    COMP_PARTY_NAME_WIDTH_TABLE_ADDRESS,
)
from ..core.patching import Patch, apply_patches
from psp.text.util.assets import load_asset_field
from psp.text.util.event_packed import encode_ascii
from psp.text.util.name_entry import load_name_entry_text

SECTION_HEADER = struct.Struct("<IIIIIIIIII")
RELOCATION = struct.Struct("<II")
ELF_HEADER_CONTRACT = (
    b"\x7fELF\x01\x01\x01" + bytes(9), 0xFFA0, 8, 1, 0x128, 0x34,
    0x1CD488, 0x10A23001, 0x34, 0x20, 2, 0x28, 34, 32,
)
FIRST_LOAD_CONTRACT = (1, 0x80, 0, 0xD2164, 0x17A5C0, 0x17A5C0, 7, 0x40)
SECOND_LOAD_CONTRACT = (1, 0x17A640, 0x0017A5C0, 0, 0x52CCC, 0x409F20, 6, 0x40)
ADDRESS_BIAS = 0x80
ENGINE_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ENGINE_ROOT / "config" / "comp_party_panel.json"


def file_offset(address: int) -> int:
    return address + ADDRESS_BIAS


from . import comp_party_panel_runtime as runtime

COMP_PARTY_NAME_DRAW_CALL_RELOCATION_OFFSET = 0x001E88C0
COMP_PARTY_NAME_DRAW_CALL_SOURCE_BYTES = bytes.fromhex("b8aa000c21306002")

# FUN_2B050 asks the coordinate/unit helper to fill sp+0x30, then retains the
# u16 unit ID at sp+0x32 through the name call.  The wrapper's 0x40-byte frame
# therefore owns the rebuilt read at sp+0x72.
COMP_PARTY_NAME_CALLER_ID_TRACE_ADDRESS = 0x0002B150
COMP_PARTY_NAME_CALLER_ID_TRACE_BYTES = bytes.fromhex(
    "3000a52755ad000c212020023200a39702006224ffff42300200422c1a004014ffff6430"
)
COMP_PARTY_NAME_CALLER_DISPATCH_ADDRESS = 0x0002B1D0
COMP_PARTY_NAME_CALLER_DISPATCH_BYTES = bytes.fromhex(
    "3200a397ffff6430ffff0234570082102016037c4f0040043000023cd8d0010c"
    "0000000021805d0221204000100011262128b202b8aa000c21306002"
)
COMP_PARTY_NAME_CHARNAME_REJOIN_ADDRESS = 0x0002B324
COMP_PARTY_NAME_CHARNAME_REJOIN_BYTES = bytes.fromhex(
    "5885438cc0200400fcff023c211864007dac000821106200"
)

# State 1 is the focused acceptance canary: six iterations call FUN_2B554 for
# a card record and the common FUN_2B050 party-panel renderer.
COMP_PARTY_STATE1_LOOP_ADDRESS = 0x0003B784
COMP_PARTY_STATE1_LOOP_BYTES = bytes.fromhex(
    "ff0011322120200255ad000c2128a0030200a29713005310212020020000459214"
    "ac000c010010260600022af4ff401401005226"
)

# The focused COMP owner is traversed once per visible UI frame.  Its state
# gate at 0x3B764 reaches the pinned six-card loop while 0x003F6B78 is active;
# closing the surface skips the loop.  Managed EVE handles can therefore be
# released at the next global frame setup and rebuilt only while COMP remains
# visible, instead of leaking persistent registry objects across frames.
COMP_PARTY_STATE1_FRAME_OWNER_ADDRESS = 0x0003B4D8
COMP_PARTY_STATE1_FRAME_OWNER_BYTES = bytes.fromhex(
    "b0ffbd274000bfaf3c00b7af3800b6af3400b5af3000b4af2c00b3af2800b2af"
    "2400b1afd5d0010c2000b0af830440100200163c010002241414c2a23100023c"
    "7872442421a0000021800000ff000524211004020000429040004330050060500"
    "10010260200451001008226ff005430010010260600022af6ff4014211004023e"
    "00023cc8f24424219000000b0010242800829006004010ffff102610008294030"
    "040100000000001004226ff005230f7ff0106440084243a00023c148744242188"
    "0000218000002110040200004390010010260001022a2b180300faff401421882"
    "3020700133c7c6b638e2900622c660040500700033c801003000f00033cf00363"
    "24211043000000448c08008000000000003e00023cc8f251240b0010242800229"
    "205004054ffff1026100022961101401421202002ffff1026f8ff0106440031263"
    "2a9000c010010240700023c846b40ac0700023c0700033c0700113c886b40ac07"
    "00023c746b60ac8c6b40ac7c6b70aeeb58000c806b20ae285d000c00000000d1"
    "ad000c000000000700023c0700043cb66a4390b76a8290806b258e25186200ff"
    "0063300700023c0b280302006b50ac0700023c786b50ac806b25ae3f00043c30"
    "af8424120006249527030c02000524d683000c0700103c806b248e5ff2000c010"
    "005240100023c2e03000ce05f448c4b0040100100023cb631000c21200000806b"
    "258e0500a0140700023c07000224806b22ae070005240700023cb86a4390ffffa"
    "42405006010806b04ae01008238211800000b188200806b03ae0700033c070004"
    "3cb66a6290b76a839025104300ff00423007004050806b2496806b228e0400405"
    "4806b249606000224806b22ae806b249621280000180084246ef5000cffff8430"
    "0700033c786b628c14004010211000003f00043c30af922421800000ffff133404"
    "001424ff0011322120200255ad000c2128a0030200a29713005310212020020000"
    "459214ac000c010010260600022af4ff40140100522621100000"
)

# FUN_2B050 is the common six-card party-panel owner reached by six menu
# controllers.  Pin the complete executable JAL inventory so this screen-local
# hook is not described as State-1-only and cannot silently absorb a new caller.
COMP_PARTY_COMMON_CALLER_ADDRESSES = (
    runtime.COMP_PARTY_NAME_COMMON_CALLER_ADDRESSES
)

# The sibling 0x2AD48 name call belongs to FUN_2AB5C's general 18-slot grid,
# not the common six-card path.  Keep this classification pinned so a
# future broad hook cannot silently absorb unrelated list/card surfaces.
COMP_PARTY_UNRELATED_GRID_LOOP_ADDRESS = 0x0002A888
COMP_PARTY_UNRELATED_GRID_LOOP_BYTES = bytes.fromhex(
    "f0ffbd270400bfaf0000b0af21800000ff00043221280000d7aa000c01001026"
    "1200022afbff4014ff000432"
)
COMP_PARTY_UNRELATED_GRID_DISPATCH_ADDRESS = 0x0002AD28
COMP_PARTY_UNRELATED_GRID_DISPATCH_BYTES = bytes.fromhex(
    "4f0040043000023cd8d0010c0000000021803d02212040002128b10221306002b8aa000c20151126"
)
COMP_PARTY_UNRELATED_GRID_NAME_CALL_ADDRESS = 0x0002AD48

COMP_PARTY_NAME_CAVE_SIZE = (
    COMP_PARTY_NAME_CAVE_END_ADDRESS - COMP_PARTY_NAME_DRAW_WRAPPER_ADDRESS
)
COMP_PARTY_NAME_CAVE_SOURCE_SHA256 = (
    "c38ddce4c7d430b93408979c091f901ac3e5cbb112fdef114e87b683b09ef8ff"
)

COMP_PARTY_DATA_SECTION_INDEX = 28
COMP_PARTY_DATA_SECTION_CONTRACT = (
    SECOND_LOAD_CONTRACT[2],
    SECOND_LOAD_CONTRACT[1],
    SECOND_LOAD_CONTRACT[4],
)
PSP_RELOCATION_SECTION_TYPE = 0x700000A0

COMP_PARTY_NAME_CAVE_WRITE_ADDRESSES = {
    "comp_party_name_draw_wrapper": COMP_PARTY_NAME_DRAW_WRAPPER_ADDRESS,
    "comp_party_name_widths": COMP_PARTY_NAME_WIDTH_TABLE_ADDRESS,
    "comp_party_character_names": COMP_PARTY_NAME_CHARACTER_TABLE_ADDRESS,
}


def _iter_all_relocations(source: bytes):
    section_offset = ELF_HEADER_CONTRACT[6]
    section_size = ELF_HEADER_CONTRACT[11]
    section_count = ELF_HEADER_CONTRACT[12]
    for index in range(section_count):
        section = SECTION_HEADER.unpack_from(
            source,
            section_offset + index * section_size,
        )
        if section[1] != PSP_RELOCATION_SECTION_TYPE:
            continue
        relocation_offset = section[4]
        relocation_size = section[5]
        if relocation_size % RELOCATION.size:
            raise ValueError("PSP relocation section is not record-aligned")
        for cursor in range(
            relocation_offset,
            relocation_offset + relocation_size,
            RELOCATION.size,
        ):
            yield RELOCATION.unpack_from(source, cursor)


def build_patch(
    source: runtime.CompPartyPanelPatchSource,
) -> runtime.CompPartyPanelPatch:
    """Compile the isolated COMP party-card patch."""

    return runtime.build_comp_party_panel_patch(source)


def validate_source_elf(source: bytes) -> None:
    """Pin the live six-card ABI, excluded grid, cave mapping, and relocation."""

    exact_regions = (
        (
            "COMP party-name call",
            runtime.COMP_PARTY_NAME_DRAW_CALL_ADDRESS,
            COMP_PARTY_NAME_DRAW_CALL_SOURCE_BYTES,
        ),
        (
            "COMP party-name ID trace",
            COMP_PARTY_NAME_CALLER_ID_TRACE_ADDRESS,
            COMP_PARTY_NAME_CALLER_ID_TRACE_BYTES,
        ),
        (
            "COMP party-name dispatch",
            COMP_PARTY_NAME_CALLER_DISPATCH_ADDRESS,
            COMP_PARTY_NAME_CALLER_DISPATCH_BYTES,
        ),
        (
            "COMP CHARNAME rejoin",
            COMP_PARTY_NAME_CHARNAME_REJOIN_ADDRESS,
            COMP_PARTY_NAME_CHARNAME_REJOIN_BYTES,
        ),
        (
            "COMP State-1 six-card loop",
            COMP_PARTY_STATE1_LOOP_ADDRESS,
            COMP_PARTY_STATE1_LOOP_BYTES,
        ),
        (
            "COMP State-1 per-frame owner",
            COMP_PARTY_STATE1_FRAME_OWNER_ADDRESS,
            COMP_PARTY_STATE1_FRAME_OWNER_BYTES,
        ),
        (
            "unrelated 18-slot grid loop",
            COMP_PARTY_UNRELATED_GRID_LOOP_ADDRESS,
            COMP_PARTY_UNRELATED_GRID_LOOP_BYTES,
        ),
        (
            "unrelated 18-slot name dispatch",
            COMP_PARTY_UNRELATED_GRID_DISPATCH_ADDRESS,
            COMP_PARTY_UNRELATED_GRID_DISPATCH_BYTES,
        ),
    )
    for context, address, expected in exact_regions:
        offset = file_offset(address)
        actual = source[offset : offset + len(expected)]
        if actual != expected:
            raise ValueError(
                f"PSP {context} changed: expected {expected.hex()}, "
                f"found {actual.hex()}"
            )

    caller_word = COMP_PARTY_STATE1_LOOP_BYTES[32:36]
    actual_callers = tuple(
        address
        for address in range(0, FIRST_LOAD_CONTRACT[3] - 3, 4)
        if source[file_offset(address) : file_offset(address) + 4] == caller_word
    )
    if actual_callers != COMP_PARTY_COMMON_CALLER_ADDRESSES:
        raise ValueError(
            "PSP common six-card caller inventory changed: "
            f"expected {COMP_PARTY_COMMON_CALLER_ADDRESSES}, found {actual_callers}"
        )

    relocation = RELOCATION.pack(runtime.COMP_PARTY_NAME_DRAW_CALL_ADDRESS, 4)
    if (
        source[
            COMP_PARTY_NAME_DRAW_CALL_RELOCATION_OFFSET : COMP_PARTY_NAME_DRAW_CALL_RELOCATION_OFFSET
            + len(relocation)
        ]
        != relocation
    ):
        raise ValueError("PSP COMP party-name JAL relocation changed")

    # Pin why address+0x80 remains correct here: this interval is inside the
    # source-backed .data range of the second PT_LOAD, not unbacked BSS or the
    # later .rel.text file storage.
    section_offset = ELF_HEADER_CONTRACT[6]
    section_size = ELF_HEADER_CONTRACT[11]
    data_section = SECTION_HEADER.unpack_from(
        source,
        section_offset + COMP_PARTY_DATA_SECTION_INDEX * section_size,
    )
    if data_section[3:6] != COMP_PARTY_DATA_SECTION_CONTRACT:
        raise ValueError("PSP COMP party-name .data source mapping changed")
    segment_start = SECOND_LOAD_CONTRACT[2]
    segment_file_end = segment_start + SECOND_LOAD_CONTRACT[4]
    if not (
        segment_start
        <= COMP_PARTY_NAME_DRAW_WRAPPER_ADDRESS
        < COMP_PARTY_NAME_CAVE_END_ADDRESS
        <= segment_file_end
    ):
        raise ValueError("PSP COMP party-name cave left the file-backed PT_LOAD")
    mapped_offset = SECOND_LOAD_CONTRACT[1] + (
        COMP_PARTY_NAME_DRAW_WRAPPER_ADDRESS - segment_start
    )
    if mapped_offset != file_offset(COMP_PARTY_NAME_DRAW_WRAPPER_ADDRESS):
        raise ValueError("PSP COMP party-name cave file mapping changed")

    cave = source[
        file_offset(COMP_PARTY_NAME_DRAW_WRAPPER_ADDRESS) : file_offset(
            COMP_PARTY_NAME_CAVE_END_ADDRESS
        )
    ]
    if len(cave) != COMP_PARTY_NAME_CAVE_SIZE:
        raise ValueError("PSP COMP party-name cave is truncated")
    if hashlib.sha256(cave).hexdigest() != COMP_PARTY_NAME_CAVE_SOURCE_SHA256:
        raise ValueError("PSP COMP party-name cave preimage changed")
    if any(cave):
        raise ValueError("PSP COMP party-name cave is not blank")
    if any(
        COMP_PARTY_NAME_DRAW_WRAPPER_ADDRESS
        <= address
        < COMP_PARTY_NAME_CAVE_END_ADDRESS
        for address, _info in _iter_all_relocations(source)
    ):
        raise ValueError("PSP COMP party-name cave has a relocation")


def validate_patch_sources(
    source: bytes,
    patch: runtime.CompPartyPanelPatch,
) -> None:
    """Validate every emitted write against its exact retail preimage."""

    if not isinstance(patch, runtime.CompPartyPanelPatch):
        raise TypeError("PSP COMP party-panel patch has the wrong type")
    source_by_write = {
        "comp_party_name_draw_call": (
            runtime.COMP_PARTY_NAME_DRAW_CALL_ADDRESS,
            COMP_PARTY_NAME_DRAW_CALL_SOURCE_BYTES[:4],
        ),
        "comp_party_name_draw_wrapper": (
            COMP_PARTY_NAME_DRAW_WRAPPER_ADDRESS,
            bytes(len(patch.draw_wrapper.data)),
        ),
        "comp_party_name_widths": (
            COMP_PARTY_NAME_WIDTH_TABLE_ADDRESS,
            bytes(len(patch.width_table)),
        ),
        "comp_party_character_names": (
            COMP_PARTY_NAME_CHARACTER_TABLE_ADDRESS,
            bytes(len(patch.character_table)),
        ),
    }
    if frozenset(write.name for write in patch.writes) != frozenset(source_by_write):
        raise ValueError("PSP COMP party-name write inventory changed")
    for write in patch.writes:
        address, expected = source_by_write[write.name]
        before = source[write.file_offset : write.file_offset + len(write.data)]
        if write.address != address or before != expected:
            raise ValueError(f"PSP COMP party-name source changed at {write.name}")


@dataclass(frozen=True, slots=True)
class CompPartyPanelBuild:
    data: bytes
    patches: tuple[Patch, ...]
    runtime: runtime.CompPartyPanelPatch
    character_names: tuple[str, ...]
    runtime_used_size: int
    runtime_capacity: int


def _configuration() -> dict[str, object]:
    try:
        value = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP COMP party-panel contract: {CONFIG_PATH}") from error
    identities = value.get("character_names") if isinstance(value, dict) else None
    if (
        not isinstance(value, dict)
        or set(value) != {"version", "surface", "character_names", "write_count"}
        or value.get("version") != 1
        or value.get("surface") != "comp_party_panel.runtime"
        or value.get("write_count") != 4
        or not isinstance(identities, list)
        or len(identities) != 5
        or any(not isinstance(identity, str) for identity in identities)
    ):
        raise ValueError("invalid PSP COMP party-panel contract")
    return value


def _ark10_widths(contract: dict[str, object]) -> bytes:
    table = contract.get("advance_table") if isinstance(contract, dict) else None
    characters = contract.get("characters") if isinstance(contract, dict) else None
    if (
        not isinstance(table, list)
        or len(table) != 95
        or any(type(value) is not int or not 1 <= value <= 14 for value in table)
        or not isinstance(characters, list)
        or len(characters) != 95
    ):
        raise ValueError("PSP font manifest has no valid COMP Ark10 contract")
    storage_codes = tuple(runtime.COMP_PARTY_NAME_ARK10_FIRST_CODE + index for index in range(95))
    if tuple(row.get("code") if isinstance(row, dict) else None for row in characters) != storage_codes:
        raise ValueError("PSP COMP Ark10 packed mapping changed")
    return bytes(table)


def build_comp_party_panel(
    stock: bytes,
    intermediate: bytes,
    font_contract: dict[str, object],
    dvlname_table: bytes,
    mysterious_man: str,
) -> CompPartyPanelBuild:
    """Apply the common six-card COMP party-name consumer."""

    if not isinstance(intermediate, bytes) or len(intermediate) != len(stock):
        raise ValueError("PSP COMP party-panel intermediate BOOT size changed")
    config = _configuration()
    identities = config["character_names"]
    rows = tuple(load_asset_field(identity) for identity in identities)
    expected_references = (
        "レイ・レイホゥ",
        "キョウジ",
        "たにがわたろう",
        "たにがわじろう",
        "たにがわさぶろう",
    )
    if tuple(reference for reference, _translation in rows) != expected_references:
        raise ValueError("PSP COMP CHARNAME authored identities changed")
    character_names = tuple(translation for _reference, translation in rows)
    name_entry = load_name_entry_text()
    codename_characters = "".join(grid.characters for grid in name_entry.grids)
    widths = _ark10_widths(font_contract)

    table_start = runtime.COMPENDIUM_NAME_TABLE_ADDRESS + ADDRESS_BIAS
    if intermediate[table_start : table_start + len(dvlname_table)] != dvlname_table:
        raise ValueError("PSP COMP party panel requires the Compendium name-table owner")
    mysterious = encode_ascii(mysterious_man)
    mysterious_start = runtime.BATTLE_NAME_STATIC_STORAGE_ADDRESS + ADDRESS_BIAS
    if intermediate[mysterious_start : mysterious_start + len(mysterious)] != mysterious:
        raise ValueError("PSP COMP party panel requires the battle-name owner")
    handle_start = runtime.EVE_UI_HANDLE_APPEND_ADDRESS + ADDRESS_BIAS
    if not any(intermediate[handle_start : handle_start + 16]):
        raise ValueError("PSP COMP party panel requires the shared EVE handle owner")

    source = runtime.CompPartyPanelPatchSource(
        character_names=character_names,
        codename_characters=codename_characters,
        mysterious_man=mysterious_man,
        dvlname_table=dvlname_table,
        packed_glyph_advances=widths,
    )
    compiled = build_patch(source)
    validate_source_elf(stock)
    validate_patch_sources(stock, compiled)
    patches = tuple(
        Patch(
            "comp_party_panel.runtime",
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
        + len(compiled.width_table)
        + len(compiled.character_table)
    )
    return CompPartyPanelBuild(
        output,
        patches,
        compiled,
        character_names,
        used,
        COMP_PARTY_NAME_CAVE_SIZE,
    )


__all__ = (
    "CONFIG_PATH",
    "COMP_PARTY_COMMON_CALLER_ADDRESSES",
    "COMP_PARTY_DATA_SECTION_CONTRACT",
    "COMP_PARTY_DATA_SECTION_INDEX",
    "COMP_PARTY_NAME_CALLER_DISPATCH_ADDRESS",
    "COMP_PARTY_NAME_CALLER_DISPATCH_BYTES",
    "COMP_PARTY_NAME_CALLER_ID_TRACE_ADDRESS",
    "COMP_PARTY_NAME_CALLER_ID_TRACE_BYTES",
    "COMP_PARTY_NAME_CAVE_SIZE",
    "COMP_PARTY_NAME_CAVE_SOURCE_SHA256",
    "COMP_PARTY_NAME_CAVE_WRITE_ADDRESSES",
    "COMP_PARTY_NAME_CHARNAME_REJOIN_ADDRESS",
    "COMP_PARTY_NAME_CHARNAME_REJOIN_BYTES",
    "COMP_PARTY_NAME_DRAW_CALL_RELOCATION_OFFSET",
    "COMP_PARTY_NAME_DRAW_CALL_SOURCE_BYTES",
    "COMP_PARTY_STATE1_FRAME_OWNER_ADDRESS",
    "COMP_PARTY_STATE1_FRAME_OWNER_BYTES",
    "COMP_PARTY_STATE1_LOOP_ADDRESS",
    "COMP_PARTY_STATE1_LOOP_BYTES",
    "COMP_PARTY_UNRELATED_GRID_DISPATCH_ADDRESS",
    "COMP_PARTY_UNRELATED_GRID_DISPATCH_BYTES",
    "COMP_PARTY_UNRELATED_GRID_LOOP_ADDRESS",
    "COMP_PARTY_UNRELATED_GRID_LOOP_BYTES",
    "COMP_PARTY_UNRELATED_GRID_NAME_CALL_ADDRESS",
    "CompPartyPanelBuild",
    "build_comp_party_panel",
    "build_patch",
    "validate_patch_sources",
    "validate_source_elf",
)
