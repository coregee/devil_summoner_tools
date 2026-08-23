"""Build the checked Ark Pixel FONT16 page used by PSP title help."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from psp.archive.pack import PspPack
from psp.font.util.gim import (
    INDEX8,
    PSP_SWIZZLED,
    RGBA8888,
    decode,
    indexed_rasters,
    replace_index8_cells,
)
from psp.font.util.metrics import build_title_help_masks
from psp.text.util.assets import load_title_help_asset, strings_sha256
from psp.text.util.title_help import load_config as load_title_text_config


FONT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = FONT_ROOT / "config" / "title_help_font16.json"


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
class TitleHelpFontConfig:
    iso_path: str
    source_size: int
    source_sha256: str
    member_count: int
    member_index: int
    member_size: int
    member_sha256: str
    palette_sha256: str
    transparent_index: int
    transparent_rgba: bytes
    ink_index: int
    ink_rgba: bytes
    translation_sha256: str
    glyphs: tuple[tuple[str, int], ...]
    output_sha256: str
    output_member_sha256: str
    changed_byte_count: int
    changed_codes: tuple[int, ...]


def load_config(path: Path = CONFIG_PATH) -> TitleHelpFontConfig:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP title FONT16 config: {path}") from error
    if not isinstance(document, dict) or set(document) != {
        "version", "id", "source", "page", "text", "output"
    }:
        raise ValueError(f"{path}: invalid root fields")
    source, page, text, output = (
        document["source"], document["page"], document["text"], document["output"]
    )
    if (
        document["version"] != 1
        or document["id"] != "title_help_font16"
        or not isinstance(source, dict)
        or set(source) != {"iso_path", "size", "sha256", "member_count"}
        or not isinstance(page, dict)
        or set(page) != {
            "member_index", "size", "sha256", "format", "order", "width",
            "height", "bits_per_pixel", "palette_sha256", "transparent_index",
            "transparent_rgba", "ink_index", "ink_rgba"
        }
        or not isinstance(text, dict)
        or set(text) != {"translation_sha256", "encoding"}
        or not isinstance(output, dict)
        or set(output)
        != {"sha256", "member_sha256", "changed_byte_count", "changed_codes"}
        or source["iso_path"] != "PSP_GAME/USRDIR/datapack.bin"
        or (
            page["member_index"],
            page["format"],
            page["order"],
            page["width"],
            page["height"],
            page["bits_per_pixel"],
        )
        != (9, INDEX8, PSP_SWIZZLED, 256, 256, 8)
    ):
        raise ValueError(f"{path}: unsupported title FONT16 contract")
    digests = (
        source["sha256"], page["sha256"], page["palette_sha256"],
        text["translation_sha256"], output["sha256"], output["member_sha256"],
    )
    if any(
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
        for value in digests
    ):
        raise ValueError(f"{path}: invalid digest")
    try:
        transparent_rgba = bytes.fromhex(page["transparent_rgba"])
        ink_rgba = bytes.fromhex(page["ink_rgba"])
    except (TypeError, ValueError) as error:
        raise ValueError(f"{path}: invalid palette color") from error
    if len(transparent_rgba) != 4 or len(ink_rgba) != 4:
        raise ValueError(f"{path}: palette colors must be RGBA records")
    required = set("".join(row[2] for row in load_title_help_asset()))
    encoding_path = (path.parent / text["encoding"]).resolve()
    text_plan = load_title_text_config(encoding_path)
    glyphs = tuple(
        (character, code)
        for character, code in text_plan.encoding
        if character in required
    )
    if (
        text["encoding"] != "../../text/config/title_help.json"
        or text_plan.translation_sha256 != text["translation_sha256"]
        or {character for character, _code_value in glyphs} != required
    ):
        raise ValueError(f"{path}: title FONT16 glyph ownership changed")
    return TitleHelpFontConfig(
        source["iso_path"], source["size"], source["sha256"], source["member_count"],
        page["member_index"], page["size"], page["sha256"], page["palette_sha256"],
        page["transparent_index"], transparent_rgba, page["ink_index"], ink_rgba,
        text["translation_sha256"], glyphs, output["sha256"],
        output["member_sha256"], output["changed_byte_count"],
        tuple(_code(value, "changed code") for value in output["changed_codes"]),
    )


@dataclass(frozen=True, slots=True)
class TitleHelpFontBuild:
    data: bytes
    member: bytes
    changed_codes: tuple[int, ...]
    changed_byte_count: int
    advances: tuple[tuple[str, int], ...]


def _cell(image, code: int) -> bytes:
    row, column = divmod(code & 0xFF, 16)
    return image.crop(
        (column * 16, row * 16, column * 16 + 16, row * 16 + 16)
    ).tobytes()


def build_title_help_font16(
    source: bytes, config: TitleHelpFontConfig | None = None
) -> TitleHelpFontBuild:
    plan = config or load_config()
    if len(source) != plan.source_size or _sha(source) != plan.source_sha256:
        raise ValueError("PSP datapack.bin source contract changed")
    translations = tuple(row[2] for row in load_title_help_asset())
    if strings_sha256(translations) != plan.translation_sha256:
        raise ValueError("PSP title-help FONT16 text contract changed")
    archive = PspPack.parse(source)
    if len(archive.members) != plan.member_count or archive.rebuild() != source:
        raise ValueError("PSP datapack.bin pack layout changed")
    member = archive.members[plan.member_index]
    if member.size != plan.member_size or _sha(member.data) != plan.member_sha256:
        raise ValueError("PSP title FONT16 source member contract changed")
    image, palette = indexed_rasters(member.data)
    if (
        image.format != INDEX8
        or image.order != PSP_SWIZZLED
        or (image.width, image.height, image.bits_per_pixel) != (256, 256, 8)
        or palette.format != RGBA8888
        or _sha(palette.payload) != plan.palette_sha256
    ):
        raise ValueError("PSP title FONT16 GIM geometry changed")
    for index, color, label in (
        (plan.transparent_index, plan.transparent_rgba, "transparent"),
        (plan.ink_index, plan.ink_rgba, "ink"),
    ):
        if palette.payload[index * 4 : index * 4 + 4] != color:
            raise ValueError(f"PSP title FONT16 {label} palette record changed")

    characters = "".join(character for character, _code_value in plan.glyphs)
    rasters = build_title_help_masks(characters)
    replacements = {
        code & 0xFF: rasters[character]["coverage"]
        for character, code in plan.glyphs
    }
    replacement_member = replace_index8_cells(
        member.data,
        replacements,
        transparent_index=plan.transparent_index,
        ink_index=plan.ink_index,
    )
    if (
        len(replacement_member) != member.size
        or _sha(replacement_member) != plan.output_member_sha256
    ):
        raise ValueError("PSP title FONT16 replacement member contract changed")
    before_image = decode(member.data)
    after_image = decode(replacement_member)
    changed_codes = tuple(
        code
        for _character, code in plan.glyphs
        if _cell(before_image, code) != _cell(after_image, code)
    )
    if changed_codes != plan.changed_codes:
        raise ValueError("PSP title FONT16 changed glyph inventory differs")
    rebuilt = archive.rebuild({member.index: replacement_member})
    changed_byte_count = sum(
        left != right for left, right in zip(source, rebuilt, strict=True)
    )
    if (
        len(rebuilt) != len(source)
        or _sha(rebuilt) != plan.output_sha256
        or changed_byte_count != plan.changed_byte_count
    ):
        raise ValueError("PSP title FONT16 datapack output contract changed")
    return TitleHelpFontBuild(
        rebuilt,
        replacement_member,
        changed_codes,
        changed_byte_count,
        tuple(
            (character, int(rasters[character]["advance"]))
            for character, _code_value in plan.glyphs
        ),
    )
