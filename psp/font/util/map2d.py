"""Compose MAP2D's reserved FONT16 rows and private EVE glyph projection."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from PIL import ImageFont

from psp.archive.pack import PspPack
from psp.font.util.gim import Gim, indexed_rasters, replace_index8_coverage_cells
from psp.text.util.event_packed import (
    ASCII_FIRST,
    ASCII_LAST,
    STORED_PRINTABLE_FIRST,
    decode_ascii_byte,
)
from psp.text.util.map2d import Map2dText, load_map2d_text

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
CONFIG_PATH = FONT_ROOT / "config" / "map2d.json"
CELL_SIZE = 16
ROW_CELL_COUNTS = (14, 3, 2)
FIXED_CELL_COUNT = 4


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _code(value: object, context: str) -> int:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise ValueError(f"{context} must be hexadecimal text")
    return int(value, 16)


def _advance(character: str, font: ImageFont.FreeTypeFont) -> int:
    measured = font.getlength(character)
    advance = round(measured)
    if measured != advance or not 1 <= advance <= CELL_SIZE:
        raise ValueError(f"PSP MAP2D glyph {character!r} has invalid advance")
    return advance


def _precompose(
    text: str,
    cell_count: int,
    font: ImageFont.FreeTypeFont,
    baseline: int,
) -> tuple[bytes, int]:
    width = cell_count * CELL_SIZE
    advances = tuple(_advance(character, font) for character in text)
    measured = sum(advances)
    if measured > width:
        raise ValueError(f"PSP MAP2D row {text!r} exceeds its {width}px field")
    canvas = bytearray(width * CELL_SIZE)
    pen = 0
    for character, advance in zip(text, advances, strict=True):
        if character != " ":
            mask = _render(character, font, baseline)
            for y in range(CELL_SIZE):
                for x in range(min(CELL_SIZE, width - pen)):
                    target = y * width + pen + x
                    canvas[target] = max(canvas[target], mask[y * CELL_SIZE + x])
        pen += advance
    return bytes(canvas), measured


def _coverage_cell(coverage: bytes, width: int, index: int) -> bytes:
    return b"".join(
        coverage[y * width + index * CELL_SIZE : y * width + (index + 1) * CELL_SIZE]
        for y in range(CELL_SIZE)
    )


def _cell_box(code: int) -> tuple[int, int, int, int]:
    cell = code & 0xFF
    left = (cell & 0x0F) * CELL_SIZE
    top = (cell >> 4) * CELL_SIZE
    return left, top, left + CELL_SIZE, top + CELL_SIZE


def _tile(data: bytes, code: int) -> bytes:
    return data[code * TILE_STRIDE : (code + 1) * TILE_STRIDE]


@dataclass(frozen=True, slots=True)
class Map2dGlyph:
    character: str
    code: int
    advance: int


@dataclass(frozen=True, slots=True)
class Map2dRow:
    name: str
    text: str
    first_code: int
    eve_first_code: int
    cell_count: int
    measured_width: int

    @property
    def words(self) -> tuple[int, ...]:
        return tuple(range(self.first_code, self.first_code + self.cell_count))

    @property
    def eve_words(self) -> tuple[int, ...]:
        return tuple(range(self.eve_first_code, self.eve_first_code + self.cell_count))


@dataclass(frozen=True, slots=True)
class Map2dFixedLocation:
    location_id: int
    text: str
    first_code: int
    measured_width: int

    @property
    def words(self) -> tuple[int, ...]:
        return tuple(range(self.first_code, self.first_code + FIXED_CELL_COUNT))


@dataclass(frozen=True, slots=True)
class Map2dFontBuild:
    datapack: bytes
    eve_files: bytes
    member: bytes
    atlas: bytes
    text: Map2dText
    records: tuple[Map2dRow, Map2dRow, Map2dRow]
    fixed_locations: tuple[Map2dFixedLocation, ...]
    printable: tuple[Map2dGlyph, ...]
    scratch_ward_codes: tuple[int, ...]
    scratch_city_codes: tuple[int, ...]
    owned_codes: tuple[int, ...]
    eve_owned_codes: tuple[int, ...]
    changed_codes: tuple[int, ...]
    eve_changed_codes: tuple[int, ...]
    required_limit: int
    datapack_added_changed_byte_count: int
    datapack_changed_byte_count: int
    eve_added_changed_byte_count: int
    eve_changed_byte_count: int

    @property
    def printable_codes(self) -> dict[str, int]:
        return {glyph.character: glyph.code for glyph in self.printable}

    @property
    def printable_advances(self) -> dict[str, int]:
        return {glyph.character: glyph.advance for glyph in self.printable}


def build_map2d_fonts(
    datapack_source: bytes,
    datapack_dependency: bytes,
    eve_source: bytes,
    eve_dependency: bytes,
) -> Map2dFontBuild:
    """Fill MAP2D's disjoint banks on top of the shared font dependencies."""

    plan = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if plan.get("version") != 1 or plan.get("id") != "map2d":
        raise ValueError("invalid PSP MAP2D font contract")
    providers = plan["providers"]
    data_plan = plan["datapack"]
    eve_plan = plan["eve"]
    output_plan = plan["output"]
    for provider in providers.values():
        path = (CONFIG_PATH.parent / provider["path"]).resolve()
        if _sha(path.read_bytes()) != provider["sha256"]:
            raise ValueError("PSP MAP2D typeface source changed")
    if _sha(datapack_dependency) != data_plan["input_sha256"]:
        raise ValueError("PSP MAP2D DATAPACK dependency changed")
    if _sha(eve_dependency) != eve_plan["input_sha256"]:
        raise ValueError("PSP MAP2D EVE dependency changed")

    text = load_map2d_text()
    ark12_plan = providers["ark12"]
    ark16_plan = providers["ark16"]
    ark12 = ImageFont.truetype(
        str((CONFIG_PATH.parent / ark12_plan["path"]).resolve()),
        ark12_plan["size"],
        layout_engine=ImageFont.Layout.BASIC,
    )
    ark16 = ImageFont.truetype(
        str((CONFIG_PATH.parent / ark16_plan["path"]).resolve()),
        ark16_plan["size"],
        layout_engine=ImageFont.Layout.BASIC,
    )

    source_pack = PspPack.parse(datapack_source)
    data_pack = PspPack.parse(datapack_dependency)
    member_index = data_plan["member_index"]
    source_member = source_pack.members[member_index].data
    input_member = data_pack.members[member_index].data
    if _sha(input_member) != data_plan["input_member_sha256"]:
        raise ValueError("PSP MAP2D FONT16 dependency member changed")
    indexed_rasters(source_member)
    source_image = Gim.parse(source_member).decode()
    input_image = Gim.parse(input_member).decode()
    first_code = _code(data_plan["first_code"], "MAP2D FONT16 first code")
    code_limit = _code(data_plan["code_limit"], "MAP2D FONT16 code limit")
    owned_codes = tuple(range(first_code, code_limit))
    for code in owned_codes:
        box = _cell_box(code)
        if source_image.crop(box).getchannel("A").getbbox():
            raise ValueError(f"PSP MAP2D source FONT16 cell {code:#x} is not blank")
        if input_image.crop(box).getchannel("A").getbbox():
            raise ValueError(f"PSP MAP2D dependency owns FONT16 cell {code:#x}")

    data_replacements: dict[int, bytes] = {}
    compositions: list[bytes] = []
    records = []
    cursor = first_code
    eve_cursor = _code(eve_plan["precomposed_first_code"], "MAP2D EVE row code")
    for name, value, cells in zip(
        ("talk_prompt", "label_yes", "label_no"),
        text.runtime_records,
        ROW_CELL_COUNTS,
        strict=True,
    ):
        coverage, measured = _precompose(value, cells, ark12, ark12_plan["baseline"])
        for index in range(cells):
            data_replacements[(cursor + index) & 0xFF] = _coverage_cell(
                coverage, cells * CELL_SIZE, index
            )
        records.append(Map2dRow(name, value, cursor, eve_cursor, cells, measured))
        compositions.append(coverage)
        cursor += cells
        eve_cursor += cells
    printable_first = _code(
        eve_plan["printable_first_code"], "MAP2D printable code"
    )
    if cursor != code_limit or eve_cursor != printable_first - 5:
        raise ValueError("PSP MAP2D fixed-row allocation changed")
    replacement_member = replace_index8_coverage_cells(
        input_member, data_replacements, maximum_source_index=10
    )
    datapack = data_pack.rebuild({member_index: replacement_member})

    eve_source_pack = PspPack.parse(eve_source)
    eve_pack = PspPack.parse(eve_dependency)
    atlas_index = eve_plan["atlas_member_index"]
    palette_index = eve_plan["palette_member_index"]
    source_atlas = eve_source_pack.members[atlas_index].data
    input_atlas = eve_pack.members[atlas_index].data
    palette = eve_pack.members[palette_index].data
    if (
        _sha(input_atlas) != eve_plan["input_atlas_sha256"]
        or _sha(palette) != eve_plan["palette_sha256"]
    ):
        raise ValueError("PSP MAP2D EVE atlas dependency changed")
    fixed_first = _code(eve_plan["fixed_first_code"], "MAP2D fixed EVE code")
    reserved_limit = _code(eve_plan["code_limit"], "MAP2D EVE limit")
    eve_owned_codes = tuple(range(fixed_first, reserved_limit))
    if any(_bounds(_decode_tile(_tile(source_atlas, code))) for code in eve_owned_codes):
        raise ValueError("PSP MAP2D EVE bank is no longer source-blank")
    if any(
        _tile(input_atlas, code) != _tile(source_atlas, code)
        for code in eve_owned_codes
    ):
        raise ValueError("PSP MAP2D EVE dependency overlaps its reserved bank")
    ramp = _palette_ramp(palette, eve_plan["maximum_source_index"])
    replacements: dict[int, tuple[int, ...]] = {}
    fixed_locations = []
    for location_id, value in enumerate(text.locations, 1):
        coverage, measured = _precompose(
            value, FIXED_CELL_COUNT, ark12, ark12_plan["baseline"]
        )
        first = fixed_first + (location_id - 1) * FIXED_CELL_COUNT
        record = Map2dFixedLocation(location_id, value, first, measured)
        fixed_locations.append(record)
        for index, code in enumerate(record.words):
            replacements[code] = _quantize(
                _coverage_cell(coverage, FIXED_CELL_COUNT * CELL_SIZE, index), ramp
            )
    for record, coverage in zip(records, compositions, strict=True):
        for index, code in enumerate(record.eve_words):
            replacements[code] = _quantize(
                _coverage_cell(coverage, record.cell_count * CELL_SIZE, index), ramp
            )

    printable = []
    storage_bytes = range(
        STORED_PRINTABLE_FIRST,
        STORED_PRINTABLE_FIRST + ASCII_LAST - ASCII_FIRST + 1,
    )
    for index, storage in enumerate(storage_bytes):
        character = decode_ascii_byte(storage)
        code = printable_first + index
        advance = _advance(character, ark16)
        pixels = (0,) * PIXEL_COUNT if character == " " else _quantize(
            _render(character, ark16, ark16_plan["baseline"]), ramp
        )
        bounds = _bounds(pixels)
        if character != " " and (bounds is None or bounds[2] > advance):
            raise ValueError(f"PSP MAP2D printable glyph {character!r} exceeds its advance")
        replacements[code] = pixels
        printable.append(Map2dGlyph(character, code, advance))
    rebuilt_atlas = bytearray(input_atlas)
    for code, pixels in replacements.items():
        rebuilt_atlas[code * TILE_STRIDE : (code + 1) * TILE_STRIDE] = (
            _encode_tile(pixels)
        )
    atlas = bytes(rebuilt_atlas)
    eve_files = eve_pack.rebuild({atlas_index: atlas})

    final_image = Gim.parse(replacement_member).decode()
    changed_codes = tuple(
        code
        for code in owned_codes
        if input_image.crop(_cell_box(code)).tobytes()
        != final_image.crop(_cell_box(code)).tobytes()
    )
    eve_changed_codes = tuple(
        code
        for code in eve_owned_codes
        if _tile(atlas, code) != _tile(input_atlas, code)
    )
    data_added = sum(
        a != b for a, b in zip(datapack_dependency, datapack, strict=True)
    )
    data_changed = sum(
        a != b for a, b in zip(datapack_source, datapack, strict=True)
    )
    eve_added = sum(
        a != b for a, b in zip(eve_dependency, eve_files, strict=True)
    )
    eve_changed = sum(
        a != b for a, b in zip(eve_source, eve_files, strict=True)
    )
    actual = {
        "datapack_sha256": _sha(datapack),
        "datapack_member_sha256": _sha(replacement_member),
        "datapack_added_changed_byte_count": data_added,
        "datapack_changed_byte_count": data_changed,
        "eve_sha256": _sha(eve_files),
        "atlas_sha256": _sha(atlas),
        "eve_added_changed_byte_count": eve_added,
        "eve_changed_byte_count": eve_changed,
    }
    if actual != output_plan:
        raise ValueError(f"PSP MAP2D font output contract changed: {actual}")
    return Map2dFontBuild(
        datapack,
        eve_files,
        replacement_member,
        atlas,
        text,
        tuple(records),
        tuple(fixed_locations),
        tuple(printable),
        tuple(
            range(
                _code(eve_plan["scratch_ward_first_code"], "ward scratch"),
                _code(eve_plan["scratch_ward_first_code"], "ward scratch") + 4,
            )
        ),
        tuple(
            range(
                _code(eve_plan["scratch_city_first_code"], "city scratch"),
                _code(eve_plan["scratch_city_first_code"], "city scratch") + 4,
            )
        ),
        owned_codes,
        eve_owned_codes,
        changed_codes,
        eve_changed_codes,
        code_limit,
        data_added,
        data_changed,
        eve_added,
        eve_changed,
    )


__all__ = ["CONFIG_PATH", "Map2dFontBuild", "build_map2d_fonts"]
