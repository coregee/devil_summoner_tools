"""Build the FONT16 cells and draw records for the PSP maze location HUD."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from psp.archive.pack import PspPack
from psp.font.util.config_menu import ConfigFontBuild
from psp.font.util.gim import Gim, replace_index8_coverage_cells
from psp.text.util.savedata import load_savedata_text


FONT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = FONT_ROOT / "config" / "dungeon_locations_font16.json"
MAX_VISIBLE_ADVANCE = 14


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _code(value: object, context: str) -> int:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise ValueError(f"{context} must be hexadecimal text")
    try:
        return int(value, 16)
    except ValueError as error:
        raise ValueError(f"{context} is not hexadecimal") from error


@dataclass(frozen=True, slots=True)
class DungeonLocationGlyph:
    character: str
    code: int
    x_offset: int
    row: int
    advance: int


@dataclass(frozen=True, slots=True)
class DungeonLocationLine:
    text: str
    measured_width: int
    rendered_width: int
    tracking_reduction: int


@dataclass(frozen=True, slots=True)
class DungeonLocationRecord:
    location_id: int
    text: str
    lines: tuple[DungeonLocationLine, ...]
    glyphs: tuple[DungeonLocationGlyph, ...]


@dataclass(frozen=True, slots=True)
class DungeonLocationFontBuild:
    data: bytes
    member: bytes
    records: tuple[DungeonLocationRecord, ...]
    digit_codes: tuple[int, ...]
    basement_code: int
    floor_code: int
    owned_codes: tuple[int, ...]
    changed_codes: tuple[int, ...]
    required_limit: int
    added_changed_byte_count: int
    changed_byte_count: int


def _load() -> dict[str, object]:
    try:
        document = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP dungeon-location font contract: {CONFIG_PATH}") from error
    if (
        not isinstance(document, dict)
        or set(document)
        != {"version", "id", "asset", "dependency", "provider", "layout", "output"}
        or document.get("version") != 1
        or document.get("id") != "dungeon_locations_font16"
        or document.get("dependency") != "config_menu.font16"
    ):
        raise ValueError("invalid PSP dungeon-location font contract")
    return document


def _render_mask(
    character: str,
    font: ImageFont.FreeTypeFont,
    *,
    baseline: int,
) -> bytes:
    canvas = Image.new("L", (64, 64), 0)
    draw = ImageDraw.Draw(canvas)
    draw.fontmode = "L"
    draw.text((24, 24 + baseline), character, font=font, fill=255, anchor="ls")
    bounds = canvas.getbbox()
    if bounds is None or bounds[1] < 24 or bounds[3] > 40:
        raise ValueError(f"PSP dungeon-location glyph {character!r} clips")
    strip = canvas.crop((bounds[0], 24, bounds[2], 40))
    cell = Image.new("L", (16, 16), 0)
    cell.paste(strip, (0, 0))
    return bytes(cell.tobytes())


def _advance(mask: bytes) -> int:
    bounds = Image.frombytes("L", (16, 16), mask).getbbox()
    if bounds is None:
        raise ValueError("PSP dungeon-location glyph rendered blank")
    return min(bounds[2] - bounds[0] + 1, MAX_VISIBLE_ADVANCE)


def _measure(text: str, advances: dict[str, int]) -> int:
    return sum(advances[character] for character in text)


def _lines(text: str, advances: dict[str, int], width: int) -> tuple[str, ...]:
    if _measure(text, advances) <= width or " " not in text:
        return (text,)
    candidates: list[tuple[float, int, int, str, str]] = []
    for index, character in enumerate(text):
        if character != " ":
            continue
        upper = text[:index]
        lower = text[index + 1 :]
        upper_width = _measure(upper, advances)
        lower_width = _measure(lower, advances)
        candidates.append(
            (
                max(upper_width / width, lower_width / width),
                abs(upper_width - lower_width),
                index,
                upper,
                lower,
            )
        )
    _pressure, _balance, _index, upper, lower = min(candidates)
    return upper, lower


def _tracked_offsets(text: str, advances: dict[str, int], width: int) -> tuple[int, ...]:
    positions = []
    pen = 0
    for character in text:
        positions.append(pen)
        pen += advances[character]
    reduction = max(0, pen - width)
    gaps = len(text) - 1
    if not reduction:
        return tuple(positions)
    if not gaps or reduction > gaps:
        raise ValueError(f"PSP dungeon-location row {text!r} cannot fit")
    tracked = tuple(
        position - index * reduction // gaps
        for index, position in enumerate(positions)
    )
    if any(right <= left for left, right in zip(tracked, tracked[1:])):
        raise ValueError(f"PSP dungeon-location row {text!r} collapsed")
    if tracked[-1] + advances[text[-1]] != width:
        raise AssertionError("PSP dungeon-location tracking missed its limit")
    return tracked


def _cell_alpha_blank(member: bytes, code: int) -> bool:
    image = Gim.parse(member).decode()
    cell = code & 0xFF
    left = cell % 16 * 16
    top = cell // 16 * 16
    return image.crop((left, top, left + 16, top + 16)).getchannel("A").getbbox() is None


def build_dungeon_location_font16(
    source: bytes,
    dependency: ConfigFontBuild,
) -> DungeonLocationFontBuild:
    """Extend CONFIG's output while reserving MAP2D's original code range."""

    if not isinstance(source, bytes) or not isinstance(dependency, ConfigFontBuild):
        raise TypeError("PSP dungeon locations require source and CONFIG FONT16")
    plan = _load()
    provider = plan["provider"]
    layout = plan["layout"]
    asset = plan["asset"]
    output_plan = plan["output"]
    if (
        not isinstance(provider, dict)
        or not isinstance(layout, dict)
        or not isinstance(asset, dict)
        or set(asset) != {"path", "sha256"}
        or not isinstance(output_plan, dict)
        or set(output_plan)
        != {
            "input_sha256",
            "input_member_sha256",
            "sha256",
            "member_sha256",
            "added_changed_byte_count",
            "changed_byte_count",
        }
    ):
        raise ValueError("invalid PSP dungeon-location font contract")
    member_index = layout.get("member_index")
    first_code = _code(layout.get("first_code"), "dungeon first code")
    reserved_first = _code(layout.get("reserved_first_code"), "reserved first code")
    required_limit = _code(layout.get("required_limit"), "dungeon draw limit")
    width = layout.get("line_width")
    if (
        member_index != 15
        or reserved_first != dependency.required_limit
        or first_code != 0x06B0
        or required_limit != 0x06E4
        or width != 64
        or layout.get("cell_size") != 16
        or layout.get("location_count") != 24
    ):
        raise ValueError("PSP dungeon-location FONT16 layout changed")

    source_pack = PspPack.parse(source)
    input_pack = PspPack.parse(dependency.data)
    source_member = source_pack.members[member_index].data
    input_member = input_pack.members[member_index].data
    asset_path = (CONFIG_PATH.parent / str(asset["path"])).resolve()
    if _sha(asset_path.read_bytes()) != asset["sha256"]:
        raise ValueError("PSP dungeon-location authored asset changed")
    if (
        _sha(dependency.data) != output_plan["input_sha256"]
        or _sha(input_member) != output_plan["input_member_sha256"]
    ):
        raise ValueError("PSP dungeon-location CONFIG dependency changed")
    for code in range(reserved_first, first_code):
        if not _cell_alpha_blank(source_member, code) or not _cell_alpha_blank(input_member, code):
            raise ValueError(f"PSP MAP2D-reserved FONT16 cell {code:#x} is not blank")

    provider_path = (CONFIG_PATH.parent / str(provider.get("path"))).resolve()
    provider_data = provider_path.read_bytes()
    if (
        _sha(provider_data) != provider.get("sha256")
        or provider.get("size") != 12
        or provider.get("baseline") != 13
        or provider.get("antialias") is not True
    ):
        raise ValueError("PSP dungeon-location typeface contract changed")
    font = ImageFont.truetype(
        str(provider_path), 12, layout_engine=ImageFont.Layout.BASIC
    )
    locations = load_savedata_text().locations
    characters = tuple(dict.fromkeys("".join(locations) + "0123456789BF"))
    visible = tuple(character for character in characters if character != " ")
    masks = {
        character: _render_mask(character, font, baseline=13)
        for character in visible
    }
    advances = {" ": 4}
    advances.update((character, _advance(masks[character])) for character in visible)
    line_texts = tuple(_lines(text, advances, width) for text in locations)
    tracked = tuple(
        dict.fromkeys(
            (line, width)
            for lines in line_texts
            for line in lines
            if _measure(line, advances) > width
        )
    )
    if tracked != (("Construction", 64), ("Underground", 64)):
        raise ValueError("PSP dungeon-location tracked-row inventory changed")

    codes = {character: first_code + index for index, character in enumerate(visible)}
    if first_code + len(codes) != required_limit:
        raise ValueError("PSP dungeon-location character inventory changed")
    digit_codes = tuple(codes[character] for character in "0123456789")
    basement_code = codes["B"]
    floor_code = codes["F"]
    owned_codes = tuple(range(first_code, required_limit))
    for code in owned_codes:
        if not _cell_alpha_blank(source_member, code) or not _cell_alpha_blank(input_member, code):
            raise ValueError(f"PSP dungeon-location FONT16 cell {code:#x} is not blank")

    replacement_member = replace_index8_coverage_cells(
        input_member,
        {codes[character] & 0xFF: masks[character] for character in visible},
        maximum_source_index=10,
    )
    records = []
    for location_id, (text, rows) in enumerate(zip(locations, line_texts, strict=True)):
        built_lines = []
        glyphs = []
        for row, line in enumerate(rows):
            measured = _measure(line, advances)
            offsets = _tracked_offsets(line, advances, width)
            for character, x_offset in zip(line, offsets, strict=True):
                if character != " ":
                    glyphs.append(
                        DungeonLocationGlyph(
                            character, codes[character], x_offset, row, advances[character]
                        )
                    )
            built_lines.append(
                DungeonLocationLine(line, measured, min(measured, width), max(0, measured - width))
            )
        records.append(DungeonLocationRecord(location_id, text, tuple(built_lines), tuple(glyphs)))

    output = input_pack.rebuild({member_index: replacement_member})
    changed_codes = tuple(code for code in owned_codes if not _cell_alpha_blank(replacement_member, code))
    if changed_codes != owned_codes:
        raise ValueError("PSP dungeon-location FONT16 emitted a blank owned cell")
    added_changed = sum(
        left != right for left, right in zip(dependency.data, output, strict=True)
    )
    changed = sum(left != right for left, right in zip(source, output, strict=True))
    if (
        _sha(output) != output_plan["sha256"]
        or _sha(replacement_member) != output_plan["member_sha256"]
        or added_changed != output_plan["added_changed_byte_count"]
        or changed != output_plan["changed_byte_count"]
    ):
        raise ValueError(
            "PSP dungeon-location FONT16 output contract changed: "
            f"{_sha(output)}, {_sha(replacement_member)}, {added_changed}, {changed}"
        )
    return DungeonLocationFontBuild(
        output,
        replacement_member,
        tuple(records),
        digit_codes,
        basement_code,
        floor_code,
        owned_codes,
        changed_codes,
        required_limit,
        added_changed,
        changed,
    )


__all__ = [
    "CONFIG_PATH",
    "DungeonLocationFontBuild",
    "DungeonLocationGlyph",
    "DungeonLocationLine",
    "DungeonLocationRecord",
    "build_dungeon_location_font16",
]
