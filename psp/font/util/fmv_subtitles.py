"""Build the dedicated Ark Pixel FONT16 bank for START2 subtitles."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from psp.archive.pack import PspPack
from psp.font.util.gim import indexed_rasters, replace_index8_coverage_cells


FONT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = FONT_ROOT / "config" / "fmv_subtitles_font16.json"


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
class FmvSubtitleFontConfig:
    asset_path: Path
    asset_sha256: str
    source_sha256: str
    member_index: int
    source_member_sha256: str
    palette_sha256: str
    provider_path: Path
    provider_sha256: str
    size: int
    baseline: int
    first_code: int
    required_limit: int
    canvas_width: int
    horizontal_margin: int
    characters: tuple[tuple[str, int, int], ...]
    output_sha256: str
    output_member_sha256: str
    changed_byte_count: int


def load_config(path: Path = CONFIG_PATH) -> FmvSubtitleFontConfig:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP FMV FONT16 config: {path}") from error
    if (
        not isinstance(document, dict)
        or set(document)
        != {
            "version",
            "id",
            "asset",
            "source",
            "provider",
            "layout",
            "characters",
            "output",
        }
        or document["version"] != 1
        or document["id"] != "fmv_subtitles_font16"
    ):
        raise ValueError(f"{path}: unsupported PSP FMV FONT16 contract")
    asset = document["asset"]
    source = document["source"]
    provider = document["provider"]
    layout = document["layout"]
    output = document["output"]
    if (
        not isinstance(asset, dict)
        or set(asset) != {"path", "sha256"}
        or not isinstance(source, dict)
        or set(source)
        != {"sha256", "member_index", "member_sha256", "palette_sha256"}
        or not isinstance(provider, dict)
        or set(provider) != {"path", "sha256", "size", "baseline"}
        or not isinstance(layout, dict)
        or set(layout)
        != {"first_code", "required_limit", "canvas_width", "horizontal_margin"}
        or not isinstance(output, dict)
        or set(output) != {"sha256", "member_sha256", "changed_byte_count"}
    ):
        raise ValueError(f"{path}: malformed PSP FMV FONT16 contract")
    digests = (
        asset["sha256"],
        source["sha256"],
        source["member_sha256"],
        source["palette_sha256"],
        provider["sha256"],
        output["sha256"],
        output["member_sha256"],
    )
    if any(
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
        for value in digests
    ):
        raise ValueError(f"{path}: invalid PSP FMV FONT16 digest")
    rows = document["characters"]
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{path}: FMV FONT16 characters must be nonempty")
    characters = []
    for index, row in enumerate(rows):
        if (
            not isinstance(row, dict)
            or set(row) != {"character", "code", "advance"}
            or not isinstance(row["character"], str)
            or len(row["character"]) != 1
            or type(row["advance"]) is not int
            or not 1 <= row["advance"] <= 16
        ):
            raise ValueError(f"{path}: invalid FMV character row {index}")
        characters.append(
            (row["character"], _code(row["code"], "FMV glyph code"), row["advance"])
        )
    first_code = _code(layout["first_code"], "FMV first code")
    required_limit = _code(layout["required_limit"], "FMV draw limit")
    if (
        len({row[0] for row in characters}) != len(characters)
        or characters[0][0:2] != (" ", 0)
        or tuple(code for _character, code, _advance in characters[1:])
        != tuple(range(first_code, required_limit))
    ):
        raise ValueError(f"{path}: FMV FONT16 mapping is not contiguous")
    asset_path = (path.parent / asset["path"]).resolve()
    provider_path = (path.parent / provider["path"]).resolve()
    integer_values = (
        source["member_index"],
        provider["size"],
        provider["baseline"],
        layout["canvas_width"],
        layout["horizontal_margin"],
        output["changed_byte_count"],
    )
    if any(type(value) is not int or value < 0 for value in integer_values):
        raise ValueError(f"{path}: invalid FMV FONT16 integer")
    return FmvSubtitleFontConfig(
        asset_path,
        asset["sha256"],
        source["sha256"],
        source["member_index"],
        source["member_sha256"],
        source["palette_sha256"],
        provider_path,
        provider["sha256"],
        provider["size"],
        provider["baseline"],
        first_code,
        required_limit,
        layout["canvas_width"],
        layout["horizontal_margin"],
        tuple(characters),
        output["sha256"],
        output["member_sha256"],
        output["changed_byte_count"],
    )


def load_dialogues(config: FmvSubtitleFontConfig) -> tuple[tuple[str, ...], ...]:
    data = config.asset_path.read_bytes()
    if _sha(data) != config.asset_sha256:
        raise ValueError("PSP FMV subtitle authored asset changed")
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid PSP FMV subtitle authored asset") from error
    movies = document.get("movies") if isinstance(document, dict) else None
    movie = movies.get("start2_news") if isinstance(movies, dict) else None
    cues = movie.get("cues") if isinstance(movie, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("version") != 1
        or document.get("kind") != "timed_text_surface"
        or document.get("surface") != "fmv.subtitles"
        or document.get("timeline") != "presentation_relative_centiseconds"
        or not isinstance(cues, list)
        or len(cues) != 9
    ):
        raise ValueError("invalid PSP START2 subtitle catalogue")
    dialogues = []
    previous_end = 0
    for index, cue in enumerate(cues):
        if (
            not isinstance(cue, dict)
            or set(cue) != {"start", "end", "reference", "translation"}
            or type(cue["start"]) is not int
            or type(cue["end"]) is not int
            or not previous_end <= cue["start"] < cue["end"]
            or not isinstance(cue["reference"], list)
            or not cue["reference"]
            or any(not isinstance(line, str) or not line for line in cue["reference"])
            or not isinstance(cue["translation"], list)
            or not 1 <= len(cue["translation"]) <= 2
            or any(
                not isinstance(line, str)
                or not line
                or not line.isascii()
                or "\n" in line
                for line in cue["translation"]
            )
        ):
            raise ValueError(f"invalid PSP START2 subtitle cue {index}")
        previous_end = cue["end"]
        dialogues.append(tuple(cue["translation"]))
    return tuple(dialogues)


def render_mask(
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
        raise ValueError(f"PSP FMV Ark16 glyph {character!r} clips")
    strip = canvas.crop((bounds[0], 24, bounds[2], 40))
    cell = Image.new("L", (16, 16), 0)
    cell.paste(strip, (0, 0))
    return bytes(cell.tobytes())


@dataclass(frozen=True, slots=True)
class FmvSubtitleFontBuild:
    data: bytes
    member: bytes
    mappings: tuple[tuple[str, int, int], ...]
    changed_codes: tuple[int, ...]
    changed_byte_count: int


def build_fmv_subtitle_font16(
    source: bytes,
    config: FmvSubtitleFontConfig | None = None,
) -> FmvSubtitleFontBuild:
    plan = config or load_config()
    if not isinstance(source, bytes) or _sha(source) != plan.source_sha256:
        raise ValueError("PSP FMV datapack source changed")
    dialogues = load_dialogues(plan)
    used = set("".join(line for dialogue in dialogues for line in dialogue))
    if used != {row[0] for row in plan.characters}:
        raise ValueError("PSP FMV FONT16 mapping differs from authored subtitles")
    widths = {
        character: advance for character, _code_value, advance in plan.characters
    }
    if any(
        sum(widths[character] for character in line)
        > plan.canvas_width - plan.horizontal_margin * 2
        for dialogue in dialogues
        for line in dialogue
    ):
        raise ValueError("PSP FMV subtitle line exceeds the authored canvas")
    provider_data = plan.provider_path.read_bytes()
    if _sha(provider_data) != plan.provider_sha256:
        raise ValueError("PSP FMV typeface source changed")
    font = ImageFont.truetype(
        str(plan.provider_path),
        plan.size,
        layout_engine=ImageFont.Layout.BASIC,
    )
    for character, _code_value, advance in plan.characters:
        if round(font.getlength(character)) != advance:
            raise ValueError(f"PSP FMV advance changed for {character!r}")
    archive = PspPack.parse(source)
    member = archive.members[plan.member_index].data
    _image, palette = indexed_rasters(member)
    if (
        _sha(member) != plan.source_member_sha256
        or _sha(palette.payload) != plan.palette_sha256
    ):
        raise ValueError("PSP FMV FONT16 source member changed")
    replacements = {
        code & 0xFF: render_mask(character, font, baseline=plan.baseline)
        for character, code, _advance in plan.characters
        if code
    }
    replacement_member = replace_index8_coverage_cells(
        member,
        replacements,
        maximum_source_index=10,
    )
    if _sha(replacement_member) != plan.output_member_sha256:
        raise ValueError("PSP FMV FONT16 output member contract changed")
    rebuilt = archive.rebuild({plan.member_index: replacement_member})
    changed = sum(left != right for left, right in zip(source, rebuilt, strict=True))
    if _sha(rebuilt) != plan.output_sha256 or changed != plan.changed_byte_count:
        raise ValueError("PSP FMV FONT16 datapack output contract changed")
    return FmvSubtitleFontBuild(
        rebuilt,
        replacement_member,
        plan.characters,
        tuple(range(plan.first_code, plan.required_limit)),
        changed,
    )


__all__ = [
    "CONFIG_PATH",
    "FmvSubtitleFontBuild",
    "FmvSubtitleFontConfig",
    "build_fmv_subtitle_font16",
    "load_config",
    "load_dialogues",
    "render_mask",
]
