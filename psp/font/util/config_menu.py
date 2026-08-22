"""Compose the checked title, START2, and CONFIG FONT16 allocations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from psp.archive.pack import PspPack
from psp.font.util.gim import (
    indexed_rasters,
    replace_index8_cells,
    replace_index8_coverage_cells,
)
from psp.font.util.metrics import render_title_help_masks
from psp.font.util.title_help import TitleHelpFontBuild
from psp.text.util.assets import load_config_asset


FONT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = FONT_ROOT / "config" / "config_menu_font16.json"
ARK16_BASE = (
    ("'", 0x0672, 4),
    (",", 0x0673, 5),
    (".", 0x0674, 5),
    ("A", 0x0675, 8),
    ("H", 0x0676, 8),
    ("I", 0x0677, 4),
    ("R", 0x0678, 8),
    ("T", 0x0679, 8),
    ("W", 0x067A, 12),
    ("a", 0x067B, 7),
    ("b", 0x067C, 7),
    ("c", 0x067D, 7),
    ("d", 0x067E, 7),
    ("e", 0x067F, 7),
    ("f", 0x0680, 7),
    ("g", 0x0681, 7),
    ("h", 0x0682, 7),
    ("i", 0x0683, 4),
    ("l", 0x0684, 4),
    ("m", 0x0685, 10),
    ("n", 0x0686, 7),
    ("o", 0x0687, 7),
    ("p", 0x0688, 7),
    ("r", 0x0689, 6),
    ("s", 0x068A, 7),
    ("t", 0x068B, 7),
    ("u", 0x068C, 7),
    ("v", 0x068D, 8),
    ("w", 0x068E, 10),
    ("x", 0x068F, 8),
    ("y", 0x0690, 8),
)
ARK16_NEW_CHARACTERS = "123BDFLMNSUz"
ARK12_NEW = (("H", 0x12, 7), ("M", 0x17, 8), ("N", 0x18, 7))


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load() -> dict[str, object]:
    document = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("version") != 1:
        raise ValueError("invalid PSP CONFIG font contract")
    return document


def _provider(path_text: str, digest: str, size: int) -> ImageFont.FreeTypeFont:
    path = (CONFIG_PATH.parent / path_text).resolve()
    data = path.read_bytes()
    if _sha(data) != digest:
        raise ValueError(f"PSP CONFIG typeface source changed: {path}")
    return ImageFont.truetype(str(path), size, layout_engine=ImageFont.Layout.BASIC)


def _mask(character: str, font: ImageFont.FreeTypeFont) -> bytes:
    canvas = Image.new("L", (64, 64), 0)
    draw = ImageDraw.Draw(canvas)
    draw.fontmode = "L"
    draw.text((24, 37), character, font=font, fill=255, anchor="ls")
    bounds = canvas.getbbox()
    if bounds is None or bounds[1] < 24 or bounds[3] > 40:
        raise ValueError(f"PSP CONFIG Ark16 glyph {character!r} clips")
    strip = canvas.crop((bounds[0], 24, bounds[2], 40))
    cell = Image.new("L", (16, 16), 0)
    cell.paste(strip, (0, 0))
    return bytes(cell.tobytes())


@dataclass(frozen=True, slots=True)
class ConfigFontBuild:
    data: bytes
    ark12: tuple[tuple[str, int, int], ...]
    ark16: tuple[tuple[str, int, int], ...]
    advance_table: bytes
    required_limit: int
    changed_byte_count: int


def build_config_font16(source: bytes, title: TitleHelpFontBuild) -> ConfigFontBuild:
    plan = _load()
    ark12_plan = plan["ark12"]
    ark16_plan = plan["ark16"]
    output_plan = plan["output"]
    if _sha(source) != plan["source_sha256"]:
        raise ValueError("PSP CONFIG datapack source changed")
    archive = PspPack.parse(source)
    title_member = title.member
    masks12 = render_title_help_masks("HMN")
    member9 = replace_index8_cells(
        title_member,
        {
            code: masks12[character]["coverage"]
            for character, code, _advance in ARK12_NEW
        },
        transparent_index=0,
        ink_index=10,
    )
    if _sha(member9) != ark12_plan["output_member_sha256"]:
        raise ValueError("PSP CONFIG Ark12 output contract changed")

    member15 = archive.members[15].data
    image, palette = indexed_rasters(member15)
    if (
        _sha(member15) != ark16_plan["source_member_sha256"]
        or _sha(palette.payload) != ark16_plan["palette_sha256"]
    ):
        raise ValueError("PSP CONFIG Ark16 source contract changed")
    font16 = _provider(
        ark16_plan["provider"], ark16_plan["provider_sha256"], ark16_plan["size"]
    )
    new = tuple(
        (character, 0x0691 + index, round(font16.getlength(character)))
        for index, character in enumerate(ARK16_NEW_CHARACTERS)
    )
    runtime_strings = tuple(
        row[3]
        for row in load_config_asset()
        if row[0] not in {"mode", "context_help"}
    )
    required = set("".join(runtime_strings)) - {" ", "△"}
    mappings = (*ARK16_BASE, *new)
    mapped = {character for character, _code, _advance in mappings}
    if not required <= mapped or required - {
        row[0] for row in ARK16_BASE
    } != set(ARK16_NEW_CHARACTERS):
        raise ValueError("PSP CONFIG Ark16 mapping differs from authored text")
    masks16 = {
        code & 0xFF: _mask(character, font16)
        for character, code, _advance in mappings
    }
    member15 = replace_index8_coverage_cells(
        member15, masks16, maximum_source_index=10
    )
    if _sha(member15) != ark16_plan["output_member_sha256"]:
        raise ValueError("PSP CONFIG Ark16 output contract changed")
    rebuilt = archive.rebuild({9: member9, 15: member15})
    changed = sum(left != right for left, right in zip(source, rebuilt, strict=True))
    if (
        _sha(rebuilt) != output_plan["sha256"]
        or changed != output_plan["changed_byte_count"]
    ):
        raise ValueError("PSP CONFIG FONT16 output contract changed")
    # Ark12 mappings needed by the runtime are the title allocation plus H/M/N.
    title_mappings = tuple(
        (character, code, int(dict(title.advances)[character]))
        for character, code in (
            (" ", 0),
            ("C", 13),
            ("D", 14),
            ("F", 16),
            ("R", 28),
            ("S", 29),
            ("V", 32),
            ("a", 37),
            ("c", 39),
            ("d", 40),
            ("e", 41),
            ("f", 42),
            ("g", 43),
            ("h", 44),
            ("i", 45),
            ("l", 48),
            ("m", 49),
            ("n", 50),
            ("o", 51),
            ("r", 54),
            ("s", 55),
            ("t", 56),
            ("u", 57),
            ("v", 58),
            ("w", 59),
            ("y", 61),
            (".", 176),
        )
    )
    ark12 = tuple(sorted((*title_mappings, *ARK12_NEW), key=lambda row: row[1]))
    ark16 = ((" ", 0, 7), ("△", 0x0671, 16), *mappings)
    table = bytes(
        advance
        for _character, code, advance in ark16
        if 0x0672 <= code < 0x069D
    )
    return ConfigFontBuild(rebuilt, ark12, ark16, table, 0x069D, changed)
