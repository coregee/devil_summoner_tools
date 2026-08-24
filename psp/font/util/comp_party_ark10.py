"""Compose the common six-card COMP panel's Ark Pixel 10 EVE projection."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from PIL import ImageFont

from psp.archive.pack import PspPack
from psp.text.util.event_packed import (
    ASCII_FIRST,
    ASCII_LAST,
    STORED_PRINTABLE_FIRST,
    decode_ascii_byte,
)

from .eve_ascii import (
    PIXEL_COUNT,
    TILE_STRIDE,
    _bounds,
    _decode_tile,
    _encode_tile,
    _palette_ramp,
    _quantize,
    _render,
)


FONT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = FONT_ROOT / "config" / "comp_party_ark10.json"
PACKED_FIRST = STORED_PRINTABLE_FIRST
PACKED_WIDTH_COUNT = ASCII_LAST - ASCII_FIRST + 1


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True, slots=True)
class CompPartyArk10Build:
    data: bytes
    atlas: bytes
    mappings: tuple[tuple[str, int, int], ...]
    advance_table: bytes
    owned_codes: tuple[int, ...]
    changed_codes: tuple[int, ...]
    added_changed_byte_count: int
    changed_byte_count: int


def build_comp_party_ark10(source: bytes, dependency: bytes) -> CompPartyArk10Build:
    """Add the private Ark10 raster while retaining the shared packed codec."""

    try:
        plan = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP COMP Ark10 contract: {CONFIG_PATH}") from error
    if not isinstance(plan, dict):
        raise ValueError("invalid PSP COMP Ark10 contract")
    atlas_plan = plan.get("atlas")
    palette_plan = plan.get("palette")
    provider = plan.get("provider")
    output_plan = plan.get("output")
    if (
        plan.get("version") != 1
        or plan.get("id") != "comp_party_ark10"
        or not all(
            isinstance(value, dict)
            for value in (atlas_plan, palette_plan, provider, output_plan)
        )
        or not isinstance(source, bytes)
        or not isinstance(dependency, bytes)
        or len(source) != len(dependency)
    ):
        raise ValueError("invalid PSP COMP Ark10 contract")

    source_pack = PspPack.parse(source)
    input_pack = PspPack.parse(dependency)
    if len(source_pack.members) != 30 or len(input_pack.members) != 30:
        raise ValueError("PSP COMP Ark10 EVE member inventory changed")
    member_index = atlas_plan["member_index"]
    palette_index = palette_plan["member_index"]
    source_atlas = source_pack.members[member_index].data
    atlas = input_pack.members[member_index].data
    palette = input_pack.members[palette_index].data
    if (
        len(atlas) != 999_424
        or _sha(atlas) != atlas_plan["input_sha256"]
        or len(palette) != 64
        or _sha(palette) != palette_plan["sha256"]
    ):
        raise ValueError("PSP COMP Ark10 atlas dependency changed")

    first_code = int(atlas_plan["first_code"], 16)
    code_limit = int(atlas_plan["code_limit"], 16)
    owned_codes = tuple(range(first_code, code_limit))
    if len(owned_codes) != PACKED_WIDTH_COUNT:
        raise ValueError("PSP COMP Ark10 allocation size changed")
    start = first_code * TILE_STRIDE
    end = code_limit * TILE_STRIDE
    source_run = source_atlas[start:end]
    input_run = atlas[start:end]
    if (
        _sha(source_run) != atlas_plan["source_run_sha256"]
        or any(source_run)
        or input_run != source_run
    ):
        raise ValueError("PSP COMP Ark10 target run is no longer blank")

    provider_path = (CONFIG_PATH.parent / provider["path"]).resolve()
    if _sha(provider_path.read_bytes()) != provider["sha256"]:
        raise ValueError("PSP COMP Ark10 typeface source changed")
    font = ImageFont.truetype(
        str(provider_path), provider["size"], layout_engine=ImageFont.Layout.BASIC
    )
    ramp = _palette_ramp(palette, palette_plan["maximum_source_index"])
    replacement = bytearray(atlas)
    mappings = []
    advances = bytearray()
    for index, storage_byte in enumerate(
        range(PACKED_FIRST, PACKED_FIRST + PACKED_WIDTH_COUNT)
    ):
        character = decode_ascii_byte(storage_byte)
        code = first_code + index
        if character == " ":
            pixels = (0,) * PIXEL_COUNT
            measured = font.getlength(character)
            advance = round(measured)
            if measured != advance:
                raise ValueError("PSP COMP Ark10 space advance is fractional")
        else:
            coverage = _render(character, font, provider["baseline"])
            if not set(coverage) - {0, 255}:
                raise ValueError(f"PSP COMP Ark10 glyph {character!r} lost antialiasing")
            pixels = _quantize(coverage, ramp)
            bounds = _bounds(pixels)
            if bounds is None or bounds[2] > 12 or bounds[3] > 12:
                raise ValueError(f"PSP COMP Ark10 glyph {character!r} exceeds its box")
            advance = min(bounds[2] - bounds[0] + 1, 14)
        if not 1 <= advance <= 14:
            raise ValueError(f"PSP COMP Ark10 glyph {character!r} has invalid advance")
        replacement[code * TILE_STRIDE : (code + 1) * TILE_STRIDE] = _encode_tile(pixels)
        mappings.append((character, code, advance))
        advances.append(advance)

    atlas_data = bytes(replacement)
    changed_codes = tuple(
        code
        for code in owned_codes
        if _decode_tile(atlas[code * TILE_STRIDE : (code + 1) * TILE_STRIDE])
        != _decode_tile(atlas_data[code * TILE_STRIDE : (code + 1) * TILE_STRIDE])
    )
    space_code = owned_codes[-1]
    if changed_codes != tuple(code for code in owned_codes if code != space_code):
        raise ValueError("PSP COMP Ark10 changed an unowned atlas cell")
    rebuilt = input_pack.rebuild({member_index: atlas_data})
    reparsed = PspPack.parse(rebuilt)
    changed_members = tuple(
        left.index
        for left, right in zip(input_pack.members, reparsed.members, strict=True)
        if left != right
    )
    if changed_members != (member_index,):
        raise ValueError("PSP COMP Ark10 changed an unrelated EVE member")
    added = sum(left != right for left, right in zip(dependency, rebuilt, strict=True))
    changed = sum(left != right for left, right in zip(source, rebuilt, strict=True))
    if (
        _sha(atlas_data) != output_plan["atlas_sha256"]
        or _sha(rebuilt) != output_plan["archive_sha256"]
        or added != output_plan["added_changed_byte_count"]
        or changed != output_plan["total_changed_byte_count"]
    ):
        raise ValueError(
            "PSP COMP Ark10 output contract changed: "
            f"{_sha(rebuilt)}, {_sha(atlas_data)}, {added}, {changed}"
        )
    return CompPartyArk10Build(
        rebuilt,
        atlas_data,
        tuple(mappings),
        bytes(advances),
        owned_codes,
        changed_codes,
        added,
        changed,
    )


__all__ = ["CONFIG_PATH", "CompPartyArk10Build", "build_comp_party_ark10"]
