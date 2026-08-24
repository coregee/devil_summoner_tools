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
from psp.text.util.assets import load_asset_field, load_config_asset
from psp.text.util.event_dvlname import load_psp_dvlname_text
from psp.text.util.name_entry import load_name_entry_text


FONT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = FONT_ROOT / "config" / "config_menu_font16.json"
ARK16_NEW_CHARACTERS = "123BDFLMNSUz"


def _ark12_code(character: str) -> int:
    """Return the established low-code FONT16 mapping shared by Ark12 users."""

    if character == " ":
        return 0
    if "0" <= character <= "9":
        return 1 + ord(character) - ord("0")
    if "A" <= character <= "Z":
        return 11 + ord(character) - ord("A")
    if "a" <= character <= "z":
        return 37 + ord(character) - ord("a")
    punctuation = {
        "-": 0xAD,
        ":": 0xAF,
        ".": 0xB0,
        ",": 0xB1,
        "'": 0xB2,
        "!": 0xB3,
        "?": 0xB4,
        "&": 0xB7,
        "/": 0xC6,
        "(": 0xCA,
        ")": 0xCB,
    }
    try:
        return punctuation[character]
    except KeyError as error:
        raise ValueError(
            f"shared PSP Ark12 character {character!r} has no conventional code"
        ) from error


def _battle_ark12_characters() -> frozenset[str]:
    name_entry = load_name_entry_text()
    text = "".join(record.translation for record in load_psp_dvlname_text())
    text += "".join(grid.characters for grid in name_entry.grids)
    text += load_asset_field("demons.json#mysterious_man.name")[1]
    text += "(None)"
    text += load_asset_field("items.json#life_stone.name")[1]
    text += load_asset_field("items.json#bead.name")[1]
    characters = frozenset(text)
    for character in characters:
        _ark12_code(character)
    return characters


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
    title_characters = {
        character for character, _code in load_title_font_config().glyphs
    }
    required_ark12 = _battle_ark12_characters()
    new_ark12_characters = tuple(
        sorted(required_ark12 - title_characters - {" "}, key=_ark12_code)
    )
    masks12 = render_title_help_masks("".join(new_ark12_characters))
    ark12_new = tuple(
        (
            character,
            _ark12_code(character),
            int(masks12[character]["advance"]),
        )
        for character in new_ark12_characters
    )
    if ark12_plan.get("new_codes") != [
        f"0x{code:04x}" for _character, code, _advance in ark12_new
    ]:
        raise ValueError("PSP shared Ark12 code inventory changed")
    member9 = replace_index8_cells(
        title_member,
        {
            code: masks12[character]["coverage"]
            for character, code, _advance in ark12_new
        },
        transparent_index=0,
        ink_index=10,
    )
    if _sha(member9) != ark12_plan["output_member_sha256"]:
        raise ValueError(
            "PSP CONFIG Ark12 output contract changed: " + _sha(member9)
        )

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
        raise ValueError(
            f"PSP CONFIG FONT16 output contract changed: {_sha(rebuilt)}, {changed}"
        )
    # Export one shared Ark12 mapping for title, CONFIG, NAME, and battle names.
    title_mappings = tuple(
        (character, code, int(dict(title.advances)[character]))
        for character, code in load_title_font_config().glyphs
    )
    ark12 = tuple(sorted((*title_mappings, *ark12_new), key=lambda row: row[1]))
    ark16 = ((" ", 0, 7), ("△", 0x0671, 16), *mappings)
    table = bytes(
        advance
        for _character, code, advance in ark16
        if 0x0672 <= code < 0x069D
    )
    return ConfigFontBuild(rebuilt, ark12, ark16, table, 0x069D, changed)
