"""Compile canonical START2 timed text into checked PSP runtime placements."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


PSP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PSP_ROOT / "fmv" / "config" / "start2_news.json"
FONT_MANIFEST_PATH = PSP_ROOT / "font" / "generated" / "game" / "psp.fonts.json"
PSMF_MAGIC_VERSION = b"PSMF0014"
PSMF_PRESENTATION_START_OFFSET = 0x54
PSMF_PRESENTATION_END_OFFSET = 0x5A
PSMF_WIDTH_BLOCKS_OFFSET = 0x8E
PSMF_HEIGHT_BLOCKS_OFFSET = 0x8F


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True, slots=True)
class SubtitleConfig:
    asset_path: Path
    disc_entry: str
    extent_offset: int
    width: int
    height: int
    frame_rate_numerator: int
    frame_rate_denominator: int
    sample_count: int
    header_size: int
    stream_size: int
    clock_hz: int
    presentation_start_ticks: int
    presentation_end_ticks: int
    single_line_tops: tuple[int, ...]
    double_line_tops: tuple[int, ...]
    x_compensation: int
    outline_pixels: int
    stock_movie_sprites: int
    sprite_limit: int


@dataclass(frozen=True, slots=True)
class AuthoredCue:
    start_centiseconds: int
    end_centiseconds: int
    lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuntimeGlyph:
    x: int
    y: int
    code: int


@dataclass(frozen=True, slots=True)
class RuntimeCue:
    start_frame: int
    end_frame_exclusive: int
    glyphs: tuple[RuntimeGlyph, ...]


def _positive_integer(value: object, context: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{context} must be a positive integer")
    return value


def load_config(path: Path = CONFIG_PATH) -> SubtitleConfig:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP FMV subtitle config: {path}") from error
    if (
        not isinstance(document, dict)
        or set(document)
        != {
            "version",
            "id",
            "surface",
            "asset",
            "disc_entry",
            "extent_offset",
            "video",
            "render",
        }
        or document["version"] != 1
        or document["id"] != "start2_news"
        or document["surface"] != "fmv.subtitles"
        or not isinstance(document["asset"], str)
        or not document["asset"]
        or document["disc_entry"] != "start2_pmf"
        or type(document["extent_offset"]) is not int
        or document["extent_offset"] < 0
    ):
        raise ValueError(f"{path}: unsupported PSP FMV subtitle contract")
    video = document["video"]
    render = document["render"]
    if (
        not isinstance(video, dict)
        or set(video)
        != {
            "container",
            "codec",
            "width",
            "height",
            "frame_rate_numerator",
            "frame_rate_denominator",
            "sample_count",
            "header_size",
            "stream_size",
            "clock_hz",
            "presentation_start_ticks",
            "presentation_end_ticks",
        }
        or video["container"] != "psmf"
        or video["codec"] != "h264"
        or not isinstance(render, dict)
        or set(render)
        != {
            "single_line_tops",
            "double_line_tops",
            "x_compensation",
            "outline_pixels",
            "stock_movie_sprites",
            "sprite_limit",
        }
    ):
        raise ValueError(f"{path}: malformed PSP FMV subtitle contract")
    single = render["single_line_tops"]
    double = render["double_line_tops"]
    if (
        not isinstance(single, list)
        or len(single) != 1
        or not isinstance(double, list)
        or len(double) != 2
        or any(type(value) is not int or value < 0 for value in (*single, *double))
        or type(render["x_compensation"]) is not int
    ):
        raise ValueError(f"{path}: invalid PSP FMV subtitle placement")
    values = {
        key: _positive_integer(video[key], f"video.{key}")
        for key in (
            "width",
            "height",
            "frame_rate_numerator",
            "frame_rate_denominator",
            "sample_count",
            "header_size",
            "stream_size",
            "clock_hz",
            "presentation_start_ticks",
            "presentation_end_ticks",
        )
    }
    render_values = {
        key: _positive_integer(render[key], f"render.{key}")
        for key in ("outline_pixels", "stock_movie_sprites", "sprite_limit")
    }
    duration_numerator = (
        values["presentation_end_ticks"] - values["presentation_start_ticks"]
    ) * values["frame_rate_numerator"]
    duration_denominator = values["clock_hz"] * values["frame_rate_denominator"]
    frames, remainder = divmod(duration_numerator, duration_denominator)
    if remainder or frames != values["sample_count"]:
        raise ValueError("PSP START2 sample count differs from its PSMF timeline")
    return SubtitleConfig(
        (path.parent / document["asset"]).resolve(),
        document["disc_entry"],
        document["extent_offset"],
        values["width"],
        values["height"],
        values["frame_rate_numerator"],
        values["frame_rate_denominator"],
        values["sample_count"],
        values["header_size"],
        values["stream_size"],
        values["clock_hz"],
        values["presentation_start_ticks"],
        values["presentation_end_ticks"],
        tuple(single),
        tuple(double),
        render["x_compensation"],
        render_values["outline_pixels"],
        render_values["stock_movie_sprites"],
        render_values["sprite_limit"],
    )


def load_authored_cues(config: SubtitleConfig) -> tuple[AuthoredCue, ...]:
    try:
        document = json.loads(config.asset_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError("invalid PSP START2 authored subtitle asset") from error
    movies = document.get("movies") if isinstance(document, dict) else None
    movie = movies.get("start2_news") if isinstance(movies, dict) else None
    canvas = movie.get("canvas") if isinstance(movie, dict) else None
    raw_cues = movie.get("cues") if isinstance(movie, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("version") != 1
        or document.get("kind") != "timed_text_surface"
        or document.get("surface") != "fmv.subtitles"
        or document.get("timeline") != "presentation_relative_centiseconds"
        or not isinstance(movie, dict)
        or set(movie) != {"role", "canvas", "cues"}
        or movie["role"] != "opening_story_news_report"
        or canvas != {"width": config.width, "height": config.height}
        or not isinstance(raw_cues, list)
        or len(raw_cues) != 9
    ):
        raise ValueError("PSP START2 authored subtitle contract changed")
    cues = []
    previous_end = 0
    for index, row in enumerate(raw_cues):
        if (
            not isinstance(row, dict)
            or set(row) != {"start", "end", "reference", "translation"}
            or type(row["start"]) is not int
            or type(row["end"]) is not int
            or not previous_end <= row["start"] < row["end"]
            or not isinstance(row["reference"], list)
            or not row["reference"]
            or any(not isinstance(line, str) or not line for line in row["reference"])
            or not isinstance(row["translation"], list)
            or not 1 <= len(row["translation"]) <= 2
            or any(
                not isinstance(line, str)
                or not line
                or not line.isascii()
                or "\n" in line
                for line in row["translation"]
            )
        ):
            raise ValueError(f"invalid PSP START2 authored cue {index}")
        previous_end = row["end"]
        cues.append(AuthoredCue(row["start"], row["end"], tuple(row["translation"])))
    return tuple(cues)


def validate_pmf(
    data: bytes,
    *,
    extent_offset: int,
    size: int,
    sha256: str,
    config: SubtitleConfig,
) -> None:
    if not isinstance(data, bytes):
        raise TypeError("PSP START2 PMF must be immutable bytes")
    if extent_offset != config.extent_offset:
        raise ValueError("PSP START2 PMF extent offset changed")
    if len(data) != size or _sha(data) != sha256:
        raise ValueError("PSP START2 PMF size or SHA-256 changed")
    if len(data) < config.header_size or data[:8] != PSMF_MAGIC_VERSION:
        raise ValueError("PSP START2 PSMF magic/version changed")
    header_size = int.from_bytes(data[0x08:0x0C], "big")
    stream_size = int.from_bytes(data[0x0C:0x10], "big")
    if (
        header_size != config.header_size
        or stream_size != config.stream_size
        or header_size + stream_size != len(data)
    ):
        raise ValueError("PSP START2 PSMF stream geometry changed")
    start = int.from_bytes(
        data[PSMF_PRESENTATION_START_OFFSET:PSMF_PRESENTATION_END_OFFSET],
        "big",
    )
    end = int.from_bytes(
        data[PSMF_PRESENTATION_END_OFFSET:PSMF_PRESENTATION_END_OFFSET + 6],
        "big",
    )
    width = data[PSMF_WIDTH_BLOCKS_OFFSET] * 16
    height = data[PSMF_HEIGHT_BLOCKS_OFFSET] * 16
    if (
        start != config.presentation_start_ticks
        or end != config.presentation_end_ticks
        or width != config.width
        or height != config.height
        or data[header_size:header_size + 4] != b"\x00\x00\x01\xba"
    ):
        raise ValueError("PSP START2 PSMF presentation contract changed")


def ceil_centiseconds_to_frame(
    centiseconds: int,
    *,
    numerator: int = 30_000,
    denominator: int = 1_001,
) -> int:
    if type(centiseconds) is not int:
        raise TypeError("PSP subtitle time must be integer centiseconds")
    if centiseconds < 0 or numerator <= 0 or denominator <= 0:
        raise ValueError("PSP subtitle time and frame rate must be positive")
    scaled_denominator = 100 * denominator
    return (centiseconds * numerator + scaled_denominator - 1) // scaled_denominator


def compile_runtime_cues(
    authored: tuple[AuthoredCue, ...],
    font_rows: tuple[tuple[str, int, int], ...],
    config: SubtitleConfig,
) -> tuple[RuntimeCue, ...]:
    if not authored:
        raise ValueError("PSP START2 needs authored subtitle cues")
    if len({row[0] for row in font_rows}) != len(font_rows):
        raise ValueError("PSP START2 FONT16 mapping is not unique")
    mapping = {character: (code, advance) for character, code, advance in font_rows}
    used = set("".join(line for cue in authored for line in cue.lines))
    if used != set(mapping):
        raise ValueError("PSP START2 authored text and FONT16 mapping diverged")
    if mapping.get(" ", (None, None))[0] != 0:
        raise ValueError("PSP START2 space must remain a no-draw code")
    cues = []
    previous_end = 0
    for index, cue in enumerate(authored):
        start = ceil_centiseconds_to_frame(
            cue.start_centiseconds,
            numerator=config.frame_rate_numerator,
            denominator=config.frame_rate_denominator,
        )
        end = ceil_centiseconds_to_frame(
            cue.end_centiseconds,
            numerator=config.frame_rate_numerator,
            denominator=config.frame_rate_denominator,
        )
        if not previous_end <= start < end <= config.sample_count:
            raise ValueError(f"PSP START2 cue {index} has invalid frame bounds")
        previous_end = end
        tops = (
            config.single_line_tops
            if len(cue.lines) == 1
            else config.double_line_tops
        )
        glyphs = []
        for line, top in zip(cue.lines, tops, strict=True):
            width = sum(mapping[character][1] for character in line)
            x = (config.width - width) // 2
            if (
                x - config.outline_pixels < 0
                or x + width + config.outline_pixels > config.width
                or top - config.outline_pixels < 0
                or top + 16 + config.outline_pixels > config.height
            ):
                raise ValueError(f"PSP START2 cue {index} lies outside the movie")
            pen = x
            for character in line:
                code, advance = mapping[character]
                if character != " ":
                    if not 0x0672 <= code < 0x0691:
                        raise ValueError("PSP START2 visible glyph is outside its bank")
                    glyphs.append(RuntimeGlyph(pen + config.x_compensation, top, code))
                pen += advance
            if pen != x + width:
                raise ValueError(f"PSP START2 cue {index} placement drifted")
        if len(glyphs) * 2 + config.stock_movie_sprites >= config.sprite_limit:
            raise ValueError(f"PSP START2 cue {index} exceeds the sprite queue")
        cues.append(RuntimeCue(start, end, tuple(glyphs)))
    return tuple(cues)


def load_font_rows(path: Path = FONT_MANIFEST_PATH) -> tuple[tuple[str, int, int], ...]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP font manifest: {path}") from error
    contract = document.get("fmv_subtitles") if isinstance(document, dict) else None
    rows = contract.get("characters") if isinstance(contract, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("version") != 1
        or document.get("surface") != "psp.fonts"
        or not isinstance(contract, dict)
        or set(contract)
        != {"first_code", "required_draw_code_limit", "changed_codes", "characters"}
        or contract["first_code"] != 0x0672
        or contract["required_draw_code_limit"] != 0x0691
        or contract["changed_codes"] != list(range(0x0672, 0x0691))
        or not isinstance(rows, list)
    ):
        raise ValueError("PSP font manifest has no valid FMV subtitle contract")
    result = []
    for row in rows:
        if (
            not isinstance(row, dict)
            or set(row) != {"character", "code", "advance"}
            or not isinstance(row["character"], str)
            or len(row["character"]) != 1
            or type(row["code"]) is not int
            or type(row["advance"]) is not int
        ):
            raise ValueError("PSP FMV subtitle font mapping is malformed")
        result.append((row["character"], row["code"], row["advance"]))
    return tuple(result)


__all__ = [
    "CONFIG_PATH",
    "FONT_MANIFEST_PATH",
    "AuthoredCue",
    "RuntimeCue",
    "RuntimeGlyph",
    "SubtitleConfig",
    "ceil_centiseconds_to_frame",
    "compile_runtime_cues",
    "load_authored_cues",
    "load_config",
    "load_font_rows",
    "validate_pmf",
]
