"""Build the packed PSP-only item name, description, and EVENT runtime."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path

from psp.archive.pack import PspPack
from psp.text.util.item_runtime import ItemRuntimeTextSource, load_item_runtime_text
from psp.text.util.event_packed import ASCII_FIRST, ASCII_LAST

PACKED_WIDTH_COUNT = ASCII_LAST - ASCII_FIRST + 1

from ..core.layout import (
    COMPENDIUM_DRAW_WRAPPER_ADDRESS,
    COMPENDIUM_DRAW_WRAPPER_END_ADDRESS,
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
from ..core.patching import Patch, apply_patches
from .item_runtime_runtime import (
    ITEM_DESCRIPTION_DISPATCH_TRAMPOLINE_ADDRESS,
    ITEM_DESCRIPTION_ENTRY_ADDRESS,
    ITEM_EVENT_DECODER_CALL_ADDRESS,
    ITEM_DETAIL_ROUTE_ADDRESS,
    ITEM_NAME_DISPATCH_TRAMPOLINE_ADDRESS,
    ITEM_NAME_DUPLICATE_ENTRY_ADDRESS,
    ITEM_NAME_PRIMARY_ENTRY_ADDRESS,
    ITEM_NAME_STOCK_TAIL_ADDRESS,
    ItemRuntimePatch,
    ItemRuntimePatchSource,
    ItemRuntimeRecordSource,
    build_item_runtime_patch,
)


ENGINE_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ENGINE_ROOT / "config" / "item_runtime.json"
ADDRESS_BIAS = 0x80
BOOT_SIZE = 2_404_599
BOOT_STOCK_SHA256 = "37b5b7a49fe1a5af60ab042d2822befb00580e02a7d7d2ed77dd279ebe6f55fa"
_RELOCATION = struct.Struct("<II")
_RELOCATION_SECTIONS = ((0x001CD9E8, 0x00068ED8), (0x00236B28, 0x00006180), (0x0023CCA8, 0x0000C510))

_HOOKS = {
    "item_name_primary_dispatch": (ITEM_NAME_PRIMARY_ENTRY_ADDRESS, bytes.fromhex("c0ffbd27ffff8430")),
    "item_name_duplicate_dispatch": (ITEM_NAME_DUPLICATE_ENTRY_ADDRESS, bytes.fromhex("c0ffbd27ffff8430")),
    "item_description_dispatch": (ITEM_DESCRIPTION_ENTRY_ADDRESS, bytes.fromhex("ffff893068000224")),
    "item_event_decoder_call": (ITEM_EVENT_DECODER_CALL_ADDRESS, bytes.fromhex("70e4010c")),
    "item_detail_route": (ITEM_DETAIL_ROUTE_ADDRESS, bytes.fromhex("07f60008")),
}
_TRAMPOLINES = {
    "item_name_dispatch_trampoline": (ITEM_NAME_DISPATCH_TRAMPOLINE_ADDRESS, bytes.fromhex("2c00b3af21a0c0002198a0002800b2af122000002400b1af218800003400bfaf2000b0af")),
    "item_description_dispatch_trampoline": (ITEM_DESCRIPTION_DISPATCH_TRAMPOLINE_ADDRESS, bytes.fromhex("21801d0201002326ffff71300800242ef7ff8014000002a64018110021187d00f2ff0224")),
}
_CAVE_WRITES = {
    "item_runtime_data": ITEM_RUNTIME_DATA_ADDRESS,
    "item_event_wrapper": ITEM_EVENT_INSERT_WRAPPER_ADDRESS,
    "item_name_stock_tail": ITEM_NAME_STOCK_TAIL_ADDRESS,
    "item_name_resolver": ITEM_NAME_RESOLVER_ADDRESS,
    "item_name_wrapper": ITEM_NAME_DRAW_WRAPPER_ADDRESS,
    "item_description_wrapper": ITEM_DESCRIPTION_DRAW_WRAPPER_ADDRESS,
}
_CAVES = (
    (ITEM_RUNTIME_DATA_ADDRESS, ITEM_RUNTIME_DATA_END_ADDRESS),
    (ITEM_EVENT_INSERT_WRAPPER_ADDRESS, ITEM_EVENT_INSERT_WRAPPER_END_ADDRESS),
    (ITEM_NAME_RESOLVER_ADDRESS, ITEM_NAME_DRAW_WRAPPER_END_ADDRESS),
    (ITEM_DESCRIPTION_DRAW_WRAPPER_ADDRESS, ITEM_DESCRIPTION_DRAW_WRAPPER_END_ADDRESS),
)
_RELOCATIONS = ((ITEM_EVENT_DECODER_CALL_ADDRESS, 0x002129E0), (ITEM_DETAIL_ROUTE_ADDRESS, 0x001F2780))
_REACHABILITY = (
    ("primary shared name helper", 0x00080034, 0x000800EC, "414bceee26eb9ee6c130c4878ee8634c8b37d6234c274b4940dfb4a77991a55c"),
    ("duplicate shared name helper", 0x00092DC4, 0x00092E7C, "32b29dada5520025ed7565862c3f92467178c7a07210afe131f0cace4018a7c9"),
    ("3D610 detail renderer", 0x0003D610, 0x0003D83C, "7255335ee4e82be120c170efb0b35de1a7265b5297fc93d80d92085913c75092"),
    ("demon equipment owner", 0x0002EA70, 0x0002F714, "efba4a84a129c507f255554e9da8cef3908349659f6006783771e8a711062f7a"),
    ("ID-255 scratch copier", 0x0009EC70, 0x0009ED74, "b1e8a20688d345928fc29a6ba95cde90648bc0795f55d09b5ce905d55d4a3396"),
    ("first combat-use formatter", 0x000A94BC, 0x000A962C, "fc0bf1e6d0337ae408af4be6a7328c4ead8230f01ea8cb464352a083406bcfeb"),
    ("second combat-use formatter", 0x000A962C, 0x000A9780, "115e43aebe63e347f236f169ab9f22986ad7540ad4c132db499911a58adf9175"),
)


@dataclass(frozen=True, slots=True)
class ItemRuntimeBuild:
    data: bytes
    patches: tuple[Patch, ...]
    text: ItemRuntimeTextSource
    runtime: ItemRuntimePatch
    runtime_used_size: int
    runtime_capacity: int


def _configuration() -> dict[str, object]:
    try:
        value = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP item-runtime contract: {CONFIG_PATH}") from error
    if value.get("version") != 1 or value.get("surface") != "psp_active_items.runtime" or value.get("owned_game_ids") != [255, 280, 281] or value.get("write_count") != 13:
        raise ValueError("invalid PSP item-runtime contract")
    return value


def _relocations(stock: bytes):
    for offset, size in _RELOCATION_SECTIONS:
        for cursor in range(offset, offset + size, _RELOCATION.size):
            yield _RELOCATION.unpack_from(stock, cursor)


def _validate_source(stock: bytes, runtime: ItemRuntimePatch) -> None:
    _configuration()
    if len(stock) != BOOT_SIZE or hashlib.sha256(stock).hexdigest() != BOOT_STOCK_SHA256:
        raise ValueError("PSP item-runtime BOOT source contract changed")
    contracts = _HOOKS | _TRAMPOLINES
    for name, (address, expected) in contracts.items():
        if stock[address + ADDRESS_BIAS : address + ADDRESS_BIAS + len(expected)] != expected:
            raise ValueError(f"PSP item-runtime source changed at {name}")
    for description, start, end, digest in _REACHABILITY:
        if hashlib.sha256(stock[start + ADDRESS_BIAS : end + ADDRESS_BIAS]).hexdigest() != digest:
            raise ValueError(f"PSP item-runtime {description} changed")
    for address, relocation_offset in _RELOCATIONS:
        if stock[relocation_offset : relocation_offset + 8] != _RELOCATION.pack(address, 4):
            raise ValueError(f"PSP item-runtime relocation changed at {address:#x}")
    for start, end in _CAVES:
        cave = stock[start + ADDRESS_BIAS : end + ADDRESS_BIAS]
        if len(cave) != end - start or any(cave):
            raise ValueError(f"PSP item-runtime cave {start:#x}..{end:#x} is not blank")
    if any(start <= address < end for address, _ in _relocations(stock) for start, end in _CAVES):
        raise ValueError("PSP item-runtime cave gained a relocation")
    expected_names = frozenset(contracts) | frozenset(_CAVE_WRITES)
    if frozenset(write.name for write in runtime.writes) != expected_names:
        raise ValueError("PSP item-runtime write inventory changed")
    for write in runtime.writes:
        before = stock[write.address + ADDRESS_BIAS : write.address + ADDRESS_BIAS + len(write.data)]
        if write.name in contracts:
            address, expected = contracts[write.name]
            if write.address != address or before != expected:
                raise ValueError(f"PSP item-runtime source changed at {write.name}")
        elif write.address != _CAVE_WRITES[write.name] or any(before):
            raise ValueError(f"PSP item-runtime cave changed at {write.name}")


def build_item_runtime(stock: bytes, intermediate: bytes, regdata: bytes, packed_widths: bytes) -> ItemRuntimeBuild:
    """Apply the three active-item consumers after the Compendium renderer."""
    if not isinstance(intermediate, bytes) or len(intermediate) != len(stock):
        raise ValueError("PSP item-runtime intermediate BOOT size changed")
    if not isinstance(packed_widths, bytes) or len(packed_widths) != PACKED_WIDTH_COUNT:
        raise ValueError("PSP item-runtime EVE widths are invalid")
    dependency = intermediate[COMPENDIUM_DRAW_WRAPPER_ADDRESS + ADDRESS_BIAS : COMPENDIUM_DRAW_WRAPPER_END_ADDRESS + ADDRESS_BIAS]
    if not any(dependency):
        raise ValueError("PSP item runtime requires the Compendium draw wrapper")
    pack = PspPack.parse(regdata)
    if len(pack.members) != 32 or pack.members[4].offset != 0xF9D0:
        raise ValueError("PSP item-runtime regdata layout changed")
    text = load_item_runtime_text(pack.members[4].data)
    runtime = build_item_runtime_patch(ItemRuntimePatchSource(tuple(ItemRuntimeRecordSource(record.game_id, record.name, record.description, record.source_name) for record in text.records), packed_widths))
    _validate_source(stock, runtime)
    patches = tuple(Patch("psp_active_items.runtime", write.name, write.address, stock[write.address + ADDRESS_BIAS : write.address + ADDRESS_BIAS + len(write.data)], write.data) for write in runtime.writes)
    output = apply_patches(intermediate, ADDRESS_BIAS, patches)
    used = len(runtime.data_blob) + sum(len(code.data) for code in (runtime.event_wrapper, runtime.name_stock_tail, runtime.resolver, runtime.name_wrapper, runtime.description_wrapper))
    capacity = sum(end - start for start, end in _CAVES)
    return ItemRuntimeBuild(output, patches, text, runtime, used, capacity)


__all__ = ["CONFIG_PATH", "ItemRuntimeBuild", "build_item_runtime"]
