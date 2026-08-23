"""Compose the checked title, START2, and CONFIG FONT16 allocations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from PIL import ImageFont

from psp.archive.pack import PspPack
from psp.font.util.gim import (
    replace_index8_cells,
    replace_index8_coverage_cells,
)
from psp.font.util.fmv_subtitles import (
    FmvSubtitleFontBuild,
    build_fmv_subtitle_font16,
    load_config as load_fmv_config,
    render_mask,
)
from psp.font.util.metrics import render_title_help_masks
from psp.font.util.title_help import (
    TitleHelpFontBuild,
    load_config as load_title_font_config,
)
from psp.text.util.assets import load_config_asset


FONT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = FONT_ROOT / "config" / "config_menu_font16.json"
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


@dataclass(frozen=True, slots=True)
class ConfigFontBuild:
    data: bytes
    ark12: tuple[tuple[str, int, int], ...]
    ark16: tuple[tuple[str, int, int], ...]
    advance_table: bytes
    required_limit: int
    changed_byte_count: int


def build_config_font16(
    source: bytes,
    title: TitleHelpFontBuild,
    fmv: FmvSubtitleFontBuild | None = None,
) -> ConfigFontBuild:
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

    fmv_result = fmv or build_fmv_subtitle_font16(source)
    fmv_plan = load_fmv_config()
    if (
        fmv_result.mappings != fmv_plan.characters
        or _sha(fmv_result.member) != fmv_plan.output_member_sha256
    ):
        raise ValueError("PSP CONFIG FMV FONT16 input contract changed")
    member15 = fmv_result.member
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
    mappings = (*fmv_result.mappings[1:], *new)
    mapped = {character for character, _code, _advance in mappings}
    if not required <= mapped or required - {
        row[0] for row in fmv_result.mappings[1:]
    } != set(ARK16_NEW_CHARACTERS):
        raise ValueError("PSP CONFIG Ark16 mapping differs from authored text")
    masks16 = {
        code & 0xFF: render_mask(
            character,
            font16,
            baseline=fmv_plan.baseline,
        )
        for character, code, _advance in new
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
        for character, code in load_title_font_config().glyphs
    )
    ark12 = tuple(sorted((*title_mappings, *ARK12_NEW), key=lambda row: row[1]))
    ark16 = ((" ", 0, 7), ("△", 0x0671, 16), *mappings)
    table = bytes(
        advance
        for _character, code, advance in ark16
        if 0x0672 <= code < 0x069D
    )
    return ConfigFontBuild(rebuilt, ark12, ark16, table, 0x069D, changed)
