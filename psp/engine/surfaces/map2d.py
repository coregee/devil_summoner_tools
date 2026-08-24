"""Checked BOOT.BIN binding for the two-dimensional city map."""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from ..core.patching import Patch, apply_patches
from . import map2d_runtime as runtime
from .savedata import file_offset
from psp.text.util.map2d import load_map2d_text

RELOCATION = struct.Struct("<II")
ENGINE_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ENGINE_ROOT / "config" / "map2d.json"
BOOT_SIZE = 2_404_599
BOOT_STOCK_SHA256 = "37b5b7a49fe1a5af60ab042d2822befb00580e02a7d7d2ed77dd279ebe6f55fa"

# MAP2D owns fixed native FONT16 rows in the second data region. The prompt
# has no trailing word in its 14-cell field; the two choice rows retain their
# stock 3-word stride, with NO's third zero word deliberately left untouched.
MAP2D_YES_ADDRESS = 0x00190810
MAP2D_NO_ADDRESS = 0x00190816
MAP2D_PROMPT_ADDRESS = 0x00190824
MAP2D_SOURCE_CONTRACTS = (
    ("map2d_yes", MAP2D_YES_ADDRESS, bytes.fromhex("23000f001d00")),
    ("map2d_no", MAP2D_NO_ADDRESS, bytes.fromhex("180019000000")),
    (
        "map2d_prompt",
        MAP2D_PROMPT_ADDRESS,
        bytes.fromhex("c500c702440040006700b500aa014a00440047005d004b004400b400"),
    ),
)
MAP2D_TOP_SOURCE_CONTRACTS = (
    (
        "map2d_top_prompt_source",
        0x001785F4,
        bytes.fromhex("43008a0c24011d01640102000611300124012a015701320124010800f2ff"),
    ),
    (
        "map2d_top_yes_source",
        0x00178614,
        bytes.fromhex("f400e000ee00f2ff"),
    ),
    (
        "map2d_top_no_source",
        0x0017861C,
        bytes.fromhex("e900ea00f2ff"),
    ),
)

# The visible top prompt and all four city/ward render states are independent
# call paths. Pin each JAL together with its live delay slot and its R_MIPS_26
# relocation; several delay slots update map state and must remain untouched.
MAP2D_DRAW_CALL_CONTRACTS = (
    (
        "map2d_top_prompt_draw_call",
        0x000A2B58,
        0x00226FD0,
        bytes.fromhex("ec7d020cffff0824"),
    ),
    (
        "map2d_top_yes_normal_draw_call",
        0x000A2B7C,
        0x00226FD8,
        bytes.fromhex("ec7d020ce3ef0835"),
    ),
    (
        "map2d_top_no_draw_call",
        0x000A2B98,
        0x00226FE0,
        bytes.fromhex("ec7d020c00000000"),
    ),
    (
        "map2d_top_yes_selected_draw_call",
        0x000A2C00,
        0x00227038,
        bytes.fromhex("ec7d020cffff0824"),
    ),
    (
        "map2d_city_header_draw_call",
        0x000A377C,
        0x00227608,
        bytes.fromhex("ec7d020c4100153c"),
    ),
    (
        "map2d_ward_header_draw_call",
        0x000A3804,
        0x00227638,
        bytes.fromhex("ec7d020c4100103c"),
    ),
    (
        "map2d_ward_marker_draw_call",
        0x000A4300,
        0x00227BC8,
        bytes.fromhex("ec7d020c01007326"),
    ),
    (
        "map2d_city_overview_draw_call",
        0x000A44B8,
        0x00227C80,
        bytes.fromhex("ec7d020c9c00a2a7"),
    ),
)

_LOWER_SOURCE_BY_WRITE = {
    "map2d_label_yes": (MAP2D_YES_ADDRESS, MAP2D_SOURCE_CONTRACTS[0][2]),
    "map2d_label_no": (MAP2D_NO_ADDRESS, MAP2D_SOURCE_CONTRACTS[1][2][:4]),
    "map2d_talk_prompt": (MAP2D_PROMPT_ADDRESS, MAP2D_SOURCE_CONTRACTS[2][2]),
}
_CALL_SOURCE_BY_WRITE = {
    name: (address, source_sequence[:4])
    for name, address, _relocation_offset, source_sequence in (
        MAP2D_DRAW_CALL_CONTRACTS
    )
}
MAP2D_CAVE_WRITE_ADDRESSES = {
    "map2d_dynamic_draw_wrapper": runtime.MAP2D_DYNAMIC_DRAW_WRAPPER_ADDRESS,
    "map2d_top_draw_wrapper": runtime.MAP2D_TOP_DRAW_WRAPPER_ADDRESS,
    "map2d_widths": runtime.MAP2D_WIDTH_TABLE_ADDRESS,
    "map2d_top_rows": runtime.MAP2D_TOP_ROW_TABLE_ADDRESS,
    "map2d_fixed_rows": runtime.MAP2D_FIXED_ROW_TABLE_ADDRESS,
}


@dataclass(frozen=True)
class Map2dExecutablePlan:
    """Complete native/EVE MAP2D rows and their shared glyph contract."""

    records: Mapping[str, Iterable[int]]
    eve_records: Mapping[str, Iterable[int]]
    fixed_eve_records: Iterable[Iterable[int]]
    glyph_codes: Mapping[str, int]
    glyph_advances: Mapping[str, int]
    scratch_ward_codes: Iterable[int]
    scratch_city_codes: Iterable[int]


@dataclass(frozen=True)
class Map2dExecutablePatch:
    """Checked lower-grid rows plus MAP2D-owned EVE/runtime hooks."""

    runtime_patch: runtime.Map2dRuntimePatch
    writes: tuple[runtime.PatchWrite, ...]

    def write(self, name: str) -> runtime.PatchWrite:
        try:
            return next(write for write in self.writes if write.name == name)
        except StopIteration as error:
            raise KeyError(f"unknown MAP2D executable write: {name}") from error


def build_patch(plan: Map2dExecutablePlan) -> Map2dExecutablePatch:
    """Compile one complete MAP2D plan into its checked write inventory."""

    records = plan.records
    if not isinstance(records, Mapping):
        raise TypeError("PSP MAP2D records must be a mapping")
    expected_lengths = {"talk_prompt": 14, "label_yes": 3, "label_no": 2}
    if set(records) != set(expected_lengths):
        raise ValueError("PSP MAP2D record names changed")
    addresses = {
        "talk_prompt": MAP2D_PROMPT_ADDRESS,
        "label_yes": MAP2D_YES_ADDRESS,
        "label_no": MAP2D_NO_ADDRESS,
    }
    lower_writes = []
    for name in ("label_yes", "label_no", "talk_prompt"):
        try:
            words = tuple(records[name])
        except TypeError as error:
            raise TypeError(f"PSP MAP2D {name} words must be iterable") from error
        if len(words) != expected_lengths[name]:
            raise ValueError(
                f"PSP MAP2D {name} has {len(words)} words; "
                f"expected {expected_lengths[name]}"
            )
        if any(
            not isinstance(word, int)
            or isinstance(word, bool)
            or not 0 <= word <= 0xFFFF
            for word in words
        ):
            raise ValueError(f"PSP MAP2D {name} words must be u16 integers")
        lower_writes.append(
            runtime.PatchWrite(
                f"map2d_{name}",
                addresses[name],
                struct.pack(f"<{len(words)}H", *words),
            )
        )
    runtime_patch = runtime.build_map2d_runtime_patch(
        plan.eve_records,
        plan.fixed_eve_records,
        plan.glyph_codes,
        plan.glyph_advances,
        scratch_ward_codes=plan.scratch_ward_codes,
        scratch_city_codes=plan.scratch_city_codes,
    )
    writes = tuple(lower_writes) + runtime_patch.writes
    if len({write.name for write in writes}) != len(writes):
        raise ValueError("PSP MAP2D executable patch has duplicate writes")
    ordered = tuple(sorted(writes, key=lambda write: write.address))
    for left, right in zip(ordered, ordered[1:]):
        if left.end_address > right.address:
            raise ValueError(
                f"PSP MAP2D executable writes overlap: {left.name} and {right.name}"
            )
    return Map2dExecutablePatch(runtime_patch, writes)


def validate_source_elf(source: bytes) -> None:
    """Validate MAP2D's native rows, call sites, delay slots, and relocations."""

    for name, address, expected in MAP2D_SOURCE_CONTRACTS + MAP2D_TOP_SOURCE_CONTRACTS:
        offset = file_offset(address)
        actual = source[offset : offset + len(expected)]
        if actual != expected:
            raise ValueError(
                f"PSP MAP2D source changed at {name}: "
                f"expected {expected.hex()}, found {actual.hex()}"
            )
    expected_calls = {
        (name, address)
        for name, address, _context in (
            runtime.MAP2D_DYNAMIC_DRAW_CALL_SITES + runtime.MAP2D_TOP_DRAW_CALL_SITES
        )
    }
    actual_calls = {
        (name, address)
        for name, address, _relocation_offset, _source_sequence in (
            MAP2D_DRAW_CALL_CONTRACTS
        )
    }
    if actual_calls != expected_calls:
        raise RuntimeError("PSP MAP2D Allegrex and executable call contracts disagree")
    for (
        name,
        address,
        relocation_offset,
        expected_sequence,
    ) in MAP2D_DRAW_CALL_CONTRACTS:
        call_offset = file_offset(address)
        actual_sequence = source[call_offset : call_offset + len(expected_sequence)]
        if actual_sequence != expected_sequence:
            raise ValueError(
                f"PSP MAP2D call or delay slot changed at {name}: "
                f"expected {expected_sequence.hex()}, found {actual_sequence.hex()}"
            )
        expected_relocation = RELOCATION.pack(address, 4)
        actual_relocation = source[
            relocation_offset : relocation_offset + len(expected_relocation)
        ]
        if actual_relocation != expected_relocation:
            raise ValueError(f"PSP MAP2D JAL relocation changed at {address:#x}")


def validate_patch_sources(source: bytes, patch: Map2dExecutablePatch) -> None:
    """Validate MAP2D's exact write inventory and every overwritten preimage."""

    source_by_write = _LOWER_SOURCE_BY_WRITE | _CALL_SOURCE_BY_WRITE
    expected_names = frozenset(source_by_write) | frozenset(MAP2D_CAVE_WRITE_ADDRESSES)
    actual_names = frozenset(write.name for write in patch.writes)
    if actual_names != expected_names:
        raise ValueError("PSP MAP2D write inventory changed")

    for write in patch.writes:
        before = source[write.file_offset : write.file_offset + len(write.data)]
        if len(before) != len(write.data):
            raise ValueError(f"PSP MAP2D write {write.name} exceeds BOOT.BIN")
        if write.name in source_by_write:
            expected_address, expected = source_by_write[write.name]
            if write.address != expected_address or before != expected:
                raise ValueError(f"PSP MAP2D source changed at {write.name}")
        elif write.name in MAP2D_CAVE_WRITE_ADDRESSES:
            expected_address = MAP2D_CAVE_WRITE_ADDRESSES[write.name]
            if write.address != expected_address or not write.data or any(before):
                raise ValueError(f"PSP MAP2D cave source changed at {write.name}")
        else:  # The exact inventory check above makes this defensive only.
            raise ValueError(f"unknown PSP MAP2D write: {write.name}")


@dataclass(frozen=True, slots=True)
class Map2dBuild:
    data: bytes
    patches: tuple[Patch, ...]
    runtime: Map2dExecutablePatch
    locations: tuple[str, ...]
    runtime_used_size: int
    runtime_capacity: int


def _configuration() -> dict[str, object]:
    try:
        value = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP MAP2D engine contract: {CONFIG_PATH}") from error
    if (
        not isinstance(value, dict)
        or value.get("version") != 1
        or value.get("surface") != "map_2d.runtime"
        or value.get("dependency") != "name_entry.runtime"
        or value.get("font_dependency") != "map_2d.font16+eve"
        or value.get("write_count") != 16
        or value.get("write_fingerprint")
        != "a08359da6376d8079910b960a3edcd12b0c9c59fbf2e63d3fc5dc2c169f0b4b5"
    ):
        raise ValueError("invalid PSP MAP2D engine contract")
    return value


def _font_plan(contract: dict[str, object]) -> Map2dExecutablePlan:
    records = contract.get("records") if isinstance(contract, dict) else None
    fixed = contract.get("fixed_locations") if isinstance(contract, dict) else None
    printable = contract.get("printable") if isinstance(contract, dict) else None
    ward = contract.get("scratch_ward_codes") if isinstance(contract, dict) else None
    city = contract.get("scratch_city_codes") if isinstance(contract, dict) else None
    if (
        contract.get("required_draw_code_limit") != 0x06B0
        or not isinstance(records, list)
        or len(records) != 3
        or not isinstance(fixed, list)
        or len(fixed) != 5
        or not isinstance(printable, list)
        or len(printable) != 95
        or ward != list(runtime.MAP2D_SCRATCH_WARD_CODES)
        or city != list(runtime.MAP2D_SCRATCH_CITY_CODES)
    ):
        raise ValueError("PSP font manifest has no valid MAP2D contract")
    text = load_map2d_text()
    record_map: dict[str, tuple[int, ...]] = {}
    eve_map: dict[str, tuple[int, ...]] = {}
    for row, expected_name, expected_text in zip(
        records,
        ("talk_prompt", "label_yes", "label_no"),
        text.runtime_records,
        strict=True,
    ):
        if (
            not isinstance(row, dict)
            or row.get("name") != expected_name
            or row.get("text") != expected_text
            or not isinstance(row.get("words"), list)
            or not isinstance(row.get("eve_words"), list)
        ):
            raise ValueError("PSP MAP2D font row contract changed")
        record_map[expected_name] = tuple(row["words"])
        eve_map[expected_name] = tuple(row["eve_words"])
    fixed_rows = []
    for location_id, (row, expected_text) in enumerate(
        zip(fixed, text.locations, strict=True), 1
    ):
        if (
            not isinstance(row, dict)
            or row.get("location_id") != location_id
            or row.get("text") != expected_text
            or not isinstance(row.get("words"), list)
        ):
            raise ValueError("PSP MAP2D fixed-location contract changed")
        fixed_rows.append(tuple(row["words"]))
    glyph_codes = {}
    glyph_advances = {}
    for row in printable:
        if (
            not isinstance(row, dict)
            or set(row) != {"character", "code", "advance"}
            or not isinstance(row["character"], str)
            or len(row["character"]) != 1
            or type(row["code"]) is not int
            or type(row["advance"]) is not int
        ):
            raise ValueError("PSP MAP2D printable contract changed")
        glyph_codes[row["character"]] = row["code"]
        glyph_advances[row["character"]] = row["advance"]
    return Map2dExecutablePlan(
        record_map,
        eve_map,
        tuple(fixed_rows),
        glyph_codes,
        glyph_advances,
        tuple(ward),
        tuple(city),
    )


def build_map2d(
    stock: bytes,
    intermediate: bytes,
    font_contract: dict[str, object],
) -> Map2dBuild:
    """Apply the complete lower-grid, top-row, and dynamic MAP2D surface."""

    configuration = _configuration()
    if (
        len(stock) != BOOT_SIZE
        or hashlib.sha256(stock).hexdigest() != BOOT_STOCK_SHA256
    ):
        raise ValueError("PSP MAP2D BOOT source contract changed")
    if not isinstance(intermediate, bytes) or len(intermediate) != len(stock):
        raise ValueError("PSP MAP2D intermediate BOOT size changed")
    name_dependency = file_offset(0x0009DEB8)
    if intermediate[name_dependency : name_dependency + 4] == stock[
        name_dependency : name_dependency + 4
    ]:
        raise ValueError("PSP MAP2D requires the NAME packed-profile owner")
    compiled = build_patch(_font_plan(font_contract))
    validate_source_elf(stock)
    validate_patch_sources(stock, compiled)
    fingerprint = hashlib.sha256(
        b"".join(write.data for write in compiled.writes)
    ).hexdigest()
    if fingerprint != configuration["write_fingerprint"]:
        raise ValueError(f"PSP MAP2D emitter contract changed: {fingerprint}")
    patches = tuple(
        Patch(
            "map_2d.runtime",
            write.name,
            write.address,
            stock[write.file_offset : write.file_offset + len(write.data)],
            write.data,
        )
        for write in compiled.writes
    )
    output = apply_patches(intermediate, 0x80, patches)
    used = sum(
        len(write.data)
        for write in compiled.writes
        if write.name in MAP2D_CAVE_WRITE_ADDRESSES
    )
    capacity = (
        runtime.ITEM_EVENT_INSERT_WRAPPER_ADDRESS
        - runtime.MAP2D_DYNAMIC_DRAW_WRAPPER_ADDRESS
        + runtime.MAP2D_WIDTH_TABLE_ADDRESS - runtime.MAP2D_TOP_DRAW_WRAPPER_ADDRESS
        + runtime.MAP2D_TOP_ROW_TABLE_ADDRESS - runtime.MAP2D_WIDTH_TABLE_ADDRESS
        + runtime.MAP2D_FIXED_ROW_TABLE_ADDRESS - runtime.MAP2D_TOP_ROW_TABLE_ADDRESS
        + runtime.SAVEDATA_DETAIL_WRAPPER_ADDRESS - runtime.MAP2D_FIXED_ROW_TABLE_ADDRESS
    )
    return Map2dBuild(
        output,
        patches,
        compiled,
        tuple(load_map2d_text().locations),
        used,
        capacity,
    )


__all__ = [
    "MAP2D_CAVE_WRITE_ADDRESSES",
    "MAP2D_DRAW_CALL_CONTRACTS",
    "MAP2D_NO_ADDRESS",
    "MAP2D_PROMPT_ADDRESS",
    "MAP2D_SOURCE_CONTRACTS",
    "MAP2D_TOP_SOURCE_CONTRACTS",
    "MAP2D_YES_ADDRESS",
    "Map2dExecutablePatch",
    "Map2dExecutablePlan",
    "Map2dBuild",
    "CONFIG_PATH",
    "build_map2d",
    "build_patch",
    "validate_patch_sources",
    "validate_source_elf",
]
