"""Populate the checked blank printable-ASCII bank in EVE KANJI member 5."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from psp.archive.pack import PspPack
from psp.text.util.event_packed import (
    ASCII_FIRST,
    ASCII_LAST,
    GLYPH_CODE_BIAS,
    GLYPH_CODE_FIRST,
    STORED_PRINTABLE_FIRST,
    glyph_code_for_character,
)


FONT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = FONT_ROOT / "config" / "eve_ascii.json"
TILE_WIDTH = 16
TILE_HEIGHT = 16
TILE_STRIDE = 128
PIXEL_COUNT = TILE_WIDTH * TILE_HEIGHT
ASCII_CHARACTERS = tuple(
    chr(value) for value in range(ASCII_FIRST, ASCII_LAST + 1)
)
SPACE_ADVANCE = 3
MAX_ADVANCE = 14
PACKED_FIRST = STORED_PRINTABLE_FIRST
PACKED_RUNTIME_BIAS = GLYPH_CODE_BIAS
PACKED_RUNTIME_FIRST = GLYPH_CODE_FIRST
PACKED_WIDTH_COUNT = ASCII_LAST - ASCII_FIRST + 1


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def glyph_code(character: str) -> int:
    """Return the retail packed EVE tile code for one printable ASCII glyph."""

    return glyph_code_for_character(character)


def _validate_widths(widths) -> bytes:
    try:
        table = bytes(widths)
    except (TypeError, ValueError) as error:
        raise ValueError("EVE advances must be byte values") from error
    if len(table) != PACKED_WIDTH_COUNT or any(value == 0 for value in table):
        raise ValueError("EVE advances must contain 95 positive bytes")
    return table


def _decode_tile(data: bytes) -> tuple[int, ...]:
    if len(data) != TILE_STRIDE:
        raise ValueError("EVE glyph tile has the wrong size")
    return tuple(nibble for value in data for nibble in (value >> 4, value & 0xF))


def _encode_tile(pixels: tuple[int, ...]) -> bytes:
    if len(pixels) != PIXEL_COUNT or any(not 0 <= value <= 0xF for value in pixels):
        raise ValueError("EVE glyph pixels do not fit one 4-bpp tile")
    return bytes(
        (pixels[index] << 4) | pixels[index + 1]
        for index in range(0, PIXEL_COUNT, 2)
    )


def _bounds(pixels: tuple[int, ...]) -> tuple[int, int, int, int] | None:
    points = [
        (index % TILE_WIDTH, index // TILE_WIDTH)
        for index, value in enumerate(pixels)
        if value
    ]
    if not points:
        return None
    return (
        min(point[0] for point in points),
        min(point[1] for point in points),
        max(point[0] for point in points) + 1,
        max(point[1] for point in points) + 1,
    )


def _runtime_palette(palette: bytes, index: int) -> tuple[int, int, int, int]:
    start = index * 4
    red, green, blue, _ignored = palette[start : start + 4]
    return red, green, blue, 0 if index == 0 else 0xFF


def _palette_ramp(palette: bytes, maximum: int) -> tuple[tuple[int, int], ...]:
    if len(palette) != 64:
        raise ValueError("EVE palette member has the wrong size")
    ramp = []
    for index in range(1, maximum + 1):
        red, green, blue, alpha = _runtime_palette(palette, index)
        if alpha != 0xFF or max(red, green, blue) - min(red, green, blue) > 4:
            raise ValueError("EVE font palette is not an opaque grayscale ramp")
        ramp.append((index, round((red + green + blue) / 3)))
    return tuple(ramp)


def _quantize(coverage: bytes, ramp: tuple[tuple[int, int], ...]) -> tuple[int, ...]:
    darkest = min(value for _index, value in ramp)
    brightest = max(value for _index, value in ramp)
    pixels = []
    for value in coverage:
        if value == 0:
            pixels.append(0)
            continue
        target = darkest + value * (brightest - darkest) / 255
        index, _value = min(
            ramp, key=lambda item: (abs(item[1] - target), -item[1])
        )
        pixels.append(index)
    return tuple(pixels)


def _render(character: str, font: ImageFont.FreeTypeFont, baseline: int) -> bytes:
    canvas = Image.new("L", (64, 64), 0)
    draw = ImageDraw.Draw(canvas)
    draw.fontmode = "L"
    draw.text((24, 24 + baseline), character, font=font, fill=255, anchor="ls")
    bounds = canvas.getbbox()
    if bounds is None:
        raise ValueError(f"EVE provider rendered {character!r} blank")
    left, top, right, bottom = bounds
    if top < 24 or bottom > 40 or right - left > MAX_ADVANCE:
        raise ValueError(f"EVE provider glyph {character!r} exceeds its cell")
    strip = canvas.crop((left, 24, right, 40))
    cell = Image.new("L", (16, 16), 0)
    cell.paste(strip, (0, 0))
    return cell.tobytes()


def _storage_characters() -> tuple[str, ...]:
    result = [None] * 95
    for character in ASCII_CHARACTERS:
        result[glyph_code(character) - 0x1E20] = character
    if any(character is None for character in result):
        raise AssertionError("EVE ASCII storage map is incomplete")
    return tuple(result)  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class EveAsciiBuild:
    data: bytes
    atlas: bytes
    mappings: tuple[tuple[str, int, int], ...]
    advance_table: bytes
    changed_codes: tuple[int, ...]
    changed_byte_count: int


def build_eve_ascii(source: bytes) -> EveAsciiBuild:
    plan = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if plan.get("version") != 1:
        raise ValueError("invalid EVE ASCII font contract")
    if plan.get("format") != {
        "width": 16,
        "height": 16,
        "bpp": 4,
        "row_stride": 8,
        "glyph_stride": 128,
        "nibble_order": "high_then_low",
    }:
        raise ValueError("PSP EVE ASCII tile format changed")
    if len(source) != plan["source_size"] or _sha(source) != plan["source_sha256"]:
        raise ValueError("PSP eve_files source changed")
    archive = PspPack.parse(source)
    if len(archive.members) != plan["member_count"]:
        raise ValueError("PSP eve_files member count changed")
    atlas_plan, palette_plan = plan["atlas"], plan["palette"]
    atlas_member = archive.members[atlas_plan["member_index"]]
    palette_member = archive.members[palette_plan["member_index"]]
    for member, contract, name in (
        (atlas_member, atlas_plan, "atlas"),
        (palette_member, palette_plan, "palette"),
    ):
        if (
            member.offset != contract["offset"]
            or member.size != contract["size"]
            or _sha(member.data) != contract["sha256"]
        ):
            raise ValueError(f"PSP EVE {name} member changed")
    for character in ASCII_CHARACTERS:
        code = glyph_code(character)
        if _bounds(_decode_tile(atlas_member.data[code * 128 : (code + 1) * 128])):
            raise ValueError("PSP EVE ASCII bank is no longer source-blank")

    provider = plan["provider"]
    provider_path = (CONFIG_PATH.parent / provider["path"]).resolve()
    if _sha(provider_path.read_bytes()) != provider["sha256"]:
        raise ValueError("PSP EVE typeface source changed")
    font = ImageFont.truetype(
        str(provider_path), provider["size"], layout_engine=ImageFont.Layout.BASIC
    )
    ramp = _palette_ramp(palette_member.data, palette_plan["maximum_source_index"])
    rebuilt_atlas = bytearray(atlas_member.data)
    advances = {}
    for character in ASCII_CHARACTERS:
        code = glyph_code(character)
        if character == " ":
            pixels = (0,) * PIXEL_COUNT
            advance = SPACE_ADVANCE
        else:
            pixels = _quantize(_render(character, font, provider["baseline"]), ramp)
            bounds = _bounds(pixels)
            assert bounds is not None
            advance = min(bounds[2] - bounds[0] + 1, MAX_ADVANCE)
        rebuilt_atlas[code * 128 : (code + 1) * 128] = _encode_tile(pixels)
        advances[character] = advance
    atlas_data = bytes(rebuilt_atlas)
    rebuilt = archive.rebuild({atlas_member.index: atlas_data})
    changed_codes = tuple(
        code
        for code in range(0x1E20, 0x1E7F)
        if atlas_member.data[code * 128 : (code + 1) * 128]
        != atlas_data[code * 128 : (code + 1) * 128]
    )
    changed = sum(left != right for left, right in zip(source, rebuilt, strict=True))
    output = plan["output"]
    if (
        _sha(atlas_data) != output["atlas_sha256"]
        or _sha(rebuilt) != output["archive_sha256"]
        or changed != output["changed_byte_count"]
    ):
        raise ValueError("PSP EVE ASCII output contract changed")
    storage = _storage_characters()
    table = bytes(advances[character] for character in storage)
    mappings = tuple(
        (character, glyph_code(character), advances[character])
        for character in ASCII_CHARACTERS
    )
    return EveAsciiBuild(rebuilt, atlas_data, mappings, table, changed_codes, changed)


__all__ = (
    "CONFIG_PATH",
    "PACKED_FIRST",
    "PACKED_RUNTIME_BIAS",
    "PACKED_RUNTIME_FIRST",
    "PACKED_WIDTH_COUNT",
    "EveAsciiBuild",
    "build_eve_ascii",
    "glyph_code",
)
