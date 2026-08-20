"""Build lossless, timed FONT16 subtitles over Saturn Cinepak playback."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from engine.core.patch_recipes import (
    PatchRecipeConfiguration,
    load_patch_recipe_configuration,
    resolve_recipe_expected,
)
from engine.core.patching import Patch, apply_patches
from engine.core.sh2 import AssemblyError, assemble_file
from rom.util.catalog import load_catalog, validate_source
from rom.util.workflows import read_source_files
from text.util.event_repack import FontMetrics


ENGINE_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = ENGINE_ROOT.parent
PROJECT_ROOT = SATURN_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "fmv_subtitles.json"
ASSEMBLY_PATH = ENGINE_ROOT / "asm" / "fmv_subtitles" / "runtime.s"
ASSET_PATH = PROJECT_ROOT / "assets" / "text" / "fmv" / "subtitles.json"
FONT16_PATH = SATURN_ROOT / "font" / "generated" / "game" / "FONT16.FON"
FONT16_METRICS_PATH = (
    SATURN_ROOT / "font" / "generated" / "game" / "FONT16_metrics.json"
)
DISC_CONFIG_PATH = SATURN_ROOT / "rom" / "discs.json"

TARGET = "EVENT.BIN"
MOVIE_TARGET = "BGDATA/START2.CPK"
LOAD_ADDRESS = 0x06020000
TARGET_SIZE = 354_072
MOVIE_SIZE = 9_134_032
MOVIE_SHA256 = "f84a02d629049212b9307c40b228dcbb6565ac7278795bc05cd05bc24fc8ea2a"
MOVIE_INDEX = 18
MOVIE_WIDTH = 320
MOVIE_HEIGHT = 224
MOVIE_FRAME_COUNT = 401
FRAME_RATE_NUMERATOR = 12
FRAME_RATE_DENOMINATOR = 1

PRIMARY_DATA_ADDRESS = 0x06020000
PRIMARY_DATA_CAPACITY = 1024
ACTIVE_ADDRESS = PRIMARY_DATA_ADDRESS
FRAME_ADDRESS = PRIMARY_DATA_ADDRESS + 4
CUE_TABLE_ADDRESS = PRIMARY_DATA_ADDRESS + 8
RUNTIME_ADDRESS = 0x060260A8
RUNTIME_CAPACITY = 512
SECONDARY_DATA_ADDRESS = 0x060262A8
SECONDARY_DATA_CAPACITY = 600

FONT16_BITMAP = 0x0021A000
MOVIE_FRAMEBUFFER = 0x25E08000
MOVIE_FRAMEBUFFER_STRIDE = 512
MOVIE_BYTES_PER_PIXEL = 4
SHADOW_OFFSET = MOVIE_FRAMEBUFFER_STRIDE * MOVIE_BYTES_PER_PIXEL + 4
ROW_ADVANCE = MOVIE_FRAMEBUFFER_STRIDE * MOVIE_BYTES_PER_PIXEL - 16 * 4
WHITE_PIXEL = 0x00FFFFFF
SHADOW_PIXEL = 0x00010101

STOCK_BLOCKING_PLAYER = 0x060393D0
STOCK_ASYNC_INIT = 0x060390E0
ASYNC_MOVIE_INDEX = 0x0607693C
STOCK_PRESENTER = 0x06039294

SINGLE_LINE_TOP = 196
DOUBLE_LINE_TOPS = (180, 196)
MAX_LINES = 2
CENTISECONDS_PER_SECOND = 100

ASSET_FILES = (ASSET_PATH,)
ASSEMBLY_FILES = (ASSEMBLY_PATH,)
RUNTIME_INPUT_FILES = (FONT16_PATH, FONT16_METRICS_PATH, DISC_CONFIG_PATH)


@dataclass(frozen=True, slots=True)
class SubtitleCue:
    start_centiseconds: int
    end_centiseconds: int
    start_frame: int
    end_frame: int
    reference: tuple[str, ...]
    translation: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SubtitleLine:
    text: str
    x: int
    y: int
    width: int
    packed_glyphs: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class CompiledCue:
    start_frame: int
    end_frame: int
    lines: tuple[SubtitleLine, ...]


@dataclass(frozen=True, slots=True)
class RuntimeArena:
    name: str
    address: int
    used_size: int
    capacity: int


@dataclass(frozen=True, slots=True)
class FmvSubtitleBuild:
    data: bytes
    patches: tuple[Patch, ...]
    cues: tuple[CompiledCue, ...]
    asset_files: tuple[Path, ...]
    assembly_files: tuple[Path, ...]
    runtime_input_files: tuple[Path, ...]
    source_inputs: Mapping[str, str]
    runtime_used_size: int
    runtime_capacity: int
    runtime_arenas: tuple[RuntimeArena, ...]


@dataclass(frozen=True, slots=True)
class _Runtime:
    primary: bytes
    secondary: bytes
    code: bytes
    labels: Mapping[str, int]
    cues: tuple[CompiledCue, ...]
    primary_used: int
    secondary_used: int
    code_used: int


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        return _sha256(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"missing FMV subtitle input: {path}") from error


def _object(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return value


def _exact_fields(value: Mapping[str, Any], fields: set[str], context: str) -> None:
    if set(value) != fields:
        raise ValueError(
            f"{context} fields are {sorted(value)}, expected {sorted(fields)}"
        )


def _positive_integer(value: Any, context: str, *, allow_zero: bool = False) -> int:
    if type(value) is not int or value < (0 if allow_zero else 1):
        qualifier = "nonnegative" if allow_zero else "positive"
        raise ValueError(f"{context} must be a {qualifier} integer")
    return value


def _text_lines(value: Any, context: str) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not 1 <= len(value) <= MAX_LINES
        or any(
            not isinstance(line, str) or not line or line != line.strip()
            for line in value
        )
    ):
        raise ValueError(f"{context} must contain one or two nonempty lines")
    return tuple(value)


def centiseconds_to_frame(centiseconds: int) -> int:
    """Return the first 12 fps movie frame at or after a cue time."""
    centiseconds = _positive_integer(
        centiseconds, "subtitle time", allow_zero=True
    )
    numerator = centiseconds * FRAME_RATE_NUMERATOR
    denominator = CENTISECONDS_PER_SECOND * FRAME_RATE_DENOMINATOR
    return (numerator + denominator - 1) // denominator


def load_subtitle_cues(path: Path = ASSET_PATH) -> tuple[SubtitleCue, ...]:
    """Load the strict human-authored START2 timed-text specification."""
    try:
        document = _object(json.loads(path.read_text(encoding="utf-8")), str(path))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"could not load FMV subtitle spec: {path}") from error
    _exact_fields(
        document,
        {"version", "kind", "surface", "timeline", "movies"},
        "FMV subtitle spec",
    )
    if (
        document["version"] != 1
        or document["kind"] != "timed_text_surface"
        or document["surface"] != "fmv.subtitles"
        or document["timeline"] != "presentation_relative_centiseconds"
    ):
        raise ValueError("FMV subtitle spec header changed")
    movies = _object(document["movies"], "FMV subtitle movies")
    if set(movies) != {"start2_news"}:
        raise ValueError("FMV subtitle spec must own only start2_news")
    movie = _object(movies["start2_news"], "START2 subtitle movie")
    _exact_fields(movie, {"role", "canvas", "cues"}, "START2 subtitle movie")
    if movie["role"] != "opening_story_news_report":
        raise ValueError("START2 subtitle role changed")
    canvas = _object(movie["canvas"], "START2 subtitle canvas")
    _exact_fields(canvas, {"width", "height"}, "START2 subtitle canvas")
    if canvas != {"width": MOVIE_WIDTH, "height": MOVIE_HEIGHT}:
        raise ValueError("START2 subtitle canvas changed")
    rows = movie["cues"]
    if not isinstance(rows, list) or len(rows) != 9:
        raise ValueError("START2 subtitle spec must contain nine cues")

    cues: list[SubtitleCue] = []
    for index, raw_row in enumerate(rows):
        context = f"START2 cue {index + 1}"
        row = _object(raw_row, context)
        _exact_fields(
            row, {"start", "end", "reference", "translation"}, context
        )
        start = _positive_integer(row["start"], f"{context} start", allow_zero=True)
        end = _positive_integer(row["end"], f"{context} end")
        reference = _text_lines(row["reference"], f"{context} reference")
        translation = _text_lines(row["translation"], f"{context} translation")
        if end <= start:
            raise ValueError(f"{context} must have a positive duration")
        if cues and start < cues[-1].end_centiseconds:
            raise ValueError(f"{context} overlaps its predecessor")
        start_frame = centiseconds_to_frame(start)
        end_frame = centiseconds_to_frame(end)
        if start_frame >= end_frame or end_frame > MOVIE_FRAME_COUNT:
            raise ValueError(f"{context} lies outside the START2 frame timeline")
        cues.append(
            SubtitleCue(
                start,
                end,
                start_frame,
                end_frame,
                reference,
                translation,
            )
        )
    return tuple(cues)


def _configuration() -> PatchRecipeConfiguration:
    config = load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="fmv.subtitles",
        target_names={TARGET},
        input_names={"font16_sha256", "font16_metrics_sha256"},
    )
    expected = (
        ("subtitle_data_primary", PRIMARY_DATA_ADDRESS, "generated"),
        ("subtitle_runtime", RUNTIME_ADDRESS, "assembly"),
        ("subtitle_data_secondary", SECONDARY_DATA_ADDRESS, "generated"),
        ("blocking_player_pointer", 0x0602EE70, "linked_pointer"),
        ("async_init_pointer", 0x060390AC, "linked_pointer"),
        ("presenter_pointer", 0x0603907C, "linked_pointer"),
    )
    recipes = config.patches[TARGET]
    actual = tuple((row.name, row.address, row.replacement.kind) for row in recipes)
    if actual != expected:
        raise ValueError("FMV subtitle patch recipe inventory drifted")
    if any(
        row.replacement.generator != "fmv_subtitle_data"
        for row in (recipes[0], recipes[2])
    ):
        raise ValueError("FMV subtitle data generator contract drifted")
    return config


def _source_files() -> tuple[bytes, bytes]:
    catalog = load_catalog()
    try:
        game = catalog["game"]
    except KeyError as error:
        raise ValueError("disc catalog has no game source") from error
    files = read_source_files(
        validate_source(game, verify_hashes=False), (TARGET, MOVIE_TARGET)
    )
    return files[TARGET], files[MOVIE_TARGET]


def _validate_sources(
    config: PatchRecipeConfiguration, stock: bytes, movie: bytes, base: bytes
) -> None:
    target = config.targets[TARGET]
    if (
        target.load_address != LOAD_ADDRESS
        or target.size != TARGET_SIZE
        or len(stock) != TARGET_SIZE
        or _sha256(stock) != target.stock_sha256
    ):
        raise ValueError("EVENT.BIN does not match the FMV subtitle stock target")
    if len(base) != TARGET_SIZE:
        raise ValueError("FMV subtitle composition base has the wrong size")
    if len(movie) != MOVIE_SIZE or _sha256(movie) != MOVIE_SHA256:
        raise ValueError("START2.CPK does not match the checked subtitle target")
    actual = {
        "font16_sha256": _file_sha256(FONT16_PATH),
        "font16_metrics_sha256": _file_sha256(FONT16_METRICS_PATH),
    }
    for name, expected in config.inputs.items():
        if actual[name] != expected:
            raise ValueError(
                f"FMV subtitle {name} expected SHA-256 {expected}, found {actual[name]}"
            )


def _compile_cues() -> tuple[CompiledCue, ...]:
    metrics = FontMetrics.load(FONT16_METRICS_PATH)
    output: list[CompiledCue] = []
    for cue_index, cue in enumerate(load_subtitle_cues(), 1):
        tops = (SINGLE_LINE_TOP,) if len(cue.translation) == 1 else DOUBLE_LINE_TOPS
        lines: list[SubtitleLine] = []
        for line_index, (text, y) in enumerate(zip(cue.translation, tops), 1):
            try:
                glyphs = tuple(metrics.segment(text))
            except ValueError as error:
                raise ValueError(
                    f"START2 cue {cue_index} line {line_index}: {error}"
                ) from error
            if not glyphs:
                raise ValueError(f"START2 cue {cue_index} line {line_index} is empty")
            width = sum(glyph.advance for glyph in glyphs)
            if width > MOVIE_WIDTH:
                raise ValueError(
                    f"START2 cue {cue_index} line {line_index} is {width}px wide"
                )
            x = (MOVIE_WIDTH - width) // 2
            packed = []
            for glyph in glyphs:
                if not 0 < glyph.advance <= 15 or not 0 < glyph.code <= 0x0FFF:
                    raise ValueError("START2 subtitle glyph cannot use packed FONT16")
                packed.append(glyph.advance << 12 | glyph.code)
            lines.append(SubtitleLine(text, x, y, width, tuple(packed)))
        output.append(CompiledCue(cue.start_frame, cue.end_frame, tuple(lines)))
    return tuple(output)


def _build_runtime() -> _Runtime:
    cues = _compile_cues()
    header_size = 8 + 4 + len(cues) * 12
    if header_size > PRIMARY_DATA_CAPACITY:
        raise ValueError("FMV subtitle cue table exceeds its primary arena")
    primary = bytearray(PRIMARY_DATA_CAPACITY)
    secondary = bytearray(SECONDARY_DATA_CAPACITY)
    struct.pack_into(">HH", primary, 8, len(cues), 0)
    primary_cursor = header_size
    secondary_cursor = 0
    line_addresses: list[tuple[int, ...]] = []

    for cue in cues:
        pointers: list[int] = []
        for line in cue.lines:
            payload = struct.pack(
                f">HH{len(line.packed_glyphs) + 1}H",
                line.x,
                line.y,
                *line.packed_glyphs,
                0,
            )
            if primary_cursor + len(payload) <= PRIMARY_DATA_CAPACITY:
                pointer = PRIMARY_DATA_ADDRESS + primary_cursor
                primary[primary_cursor : primary_cursor + len(payload)] = payload
                primary_cursor += len(payload)
            else:
                if secondary_cursor + len(payload) > SECONDARY_DATA_CAPACITY:
                    raise ValueError(
                        "FMV subtitle text exceeds its checked data arenas"
                    )
                pointer = SECONDARY_DATA_ADDRESS + secondary_cursor
                secondary[secondary_cursor : secondary_cursor + len(payload)] = payload
                secondary_cursor += len(payload)
            pointers.append(pointer)
        line_addresses.append(tuple(pointers))

    for index, (cue, pointers) in enumerate(zip(cues, line_addresses)):
        first = pointers[0]
        second = pointers[1] if len(pointers) == 2 else 0
        struct.pack_into(
            ">HHII",
            primary,
            12 + index * 12,
            cue.start_frame,
            cue.end_frame,
            first,
            second,
        )

    symbols = {
        "FMV_ACTIVE": ACTIVE_ADDRESS,
        "FMV_FRAME": FRAME_ADDRESS,
        "FMV_CUE_TABLE": CUE_TABLE_ADDRESS,
        "START2_INDEX": MOVIE_INDEX,
        "STOCK_BLOCKING_PLAYER": STOCK_BLOCKING_PLAYER,
        "STOCK_ASYNC_INIT": STOCK_ASYNC_INIT,
        "ASYNC_MOVIE_INDEX": ASYNC_MOVIE_INDEX,
        "STOCK_PRESENTER": STOCK_PRESENTER,
        "FONT16_BITMAP": FONT16_BITMAP,
        "MOVIE_FRAMEBUFFER": MOVIE_FRAMEBUFFER,
        "SHADOW_OFFSET": SHADOW_OFFSET,
        "ROW_ADVANCE": ROW_ADVANCE,
        "WHITE_PIXEL": WHITE_PIXEL,
        "SHADOW_PIXEL": SHADOW_PIXEL,
    }
    try:
        assembly = assemble_file(ASSEMBLY_PATH, RUNTIME_ADDRESS, symbols)
    except AssemblyError as error:
        raise ValueError(f"FMV subtitle runtime: {error}") from error
    if assembly.warnings:
        raise ValueError(f"FMV subtitle runtime warnings: {assembly.warnings}")
    required_labels = {
        "fmv_blocking_player_wrapper",
        "fmv_async_init_wrapper",
        "fmv_present_wrapper",
    }
    if not required_labels <= assembly.labels.keys():
        raise ValueError("FMV subtitle runtime is missing public entry points")
    if len(assembly.data) > RUNTIME_CAPACITY:
        raise ValueError("FMV subtitle runtime exceeds its checked code cave")
    code = assembly.data + bytes(RUNTIME_CAPACITY - len(assembly.data))
    return _Runtime(
        bytes(primary),
        bytes(secondary),
        code,
        MappingProxyType(dict(assembly.labels)),
        cues,
        primary_cursor,
        secondary_cursor,
        len(assembly.data),
    )


def _bind_patches(
    config: PatchRecipeConfiguration, base: bytes
) -> tuple[tuple[Patch, ...], _Runtime]:
    runtime = _build_runtime()
    generated = {
        "subtitle_data_primary": runtime.primary,
        "subtitle_data_secondary": runtime.secondary,
    }
    links_seen: set[str] = set()
    patches: list[Patch] = []
    for recipe in config.patches[TARGET]:
        expected = resolve_recipe_expected(recipe, base, LOAD_ADDRESS)
        replacement_recipe = recipe.replacement
        if replacement_recipe.kind == "generated":
            try:
                replacement = generated[recipe.name]
            except KeyError as error:
                raise ValueError(
                    f"unknown FMV subtitle data patch {recipe.name}"
                ) from error
        elif replacement_recipe.kind == "assembly":
            if recipe.name != "subtitle_runtime":
                raise ValueError(f"unknown FMV subtitle assembly {recipe.name}")
            replacement = runtime.code
        elif replacement_recipe.kind == "linked_pointer":
            link = replacement_recipe.link
            assert link is not None
            try:
                replacement = struct.pack(">I", runtime.labels[link])
            except KeyError as error:
                raise ValueError(f"unknown FMV subtitle link {link}") from error
            links_seen.add(link)
        else:
            raise ValueError(
                f"{recipe.group}/{recipe.name}: unsupported FMV subtitle recipe"
            )
        if len(replacement) != len(expected):
            raise ValueError(
                f"{recipe.group}/{recipe.name}: generated {len(replacement)} bytes, "
                f"expected {len(expected)}"
            )
        patches.append(
            Patch(recipe.group, recipe.name, recipe.address, expected, replacement)
        )
    if links_seen != {
        "fmv_blocking_player_wrapper",
        "fmv_async_init_wrapper",
        "fmv_present_wrapper",
    }:
        raise ValueError("FMV subtitle linked-pointer ownership drifted")
    return tuple(patches), runtime


def build_fmv_subtitles(base: bytes) -> FmvSubtitleBuild:
    """Patch one fully composed EVENT.BIN without changing the bound CPK."""
    config = _configuration()
    stock, movie = _source_files()
    _validate_sources(config, stock, movie, base)
    patches, runtime = _bind_patches(config, base)
    arenas = (
        RuntimeArena(
            "data_primary",
            PRIMARY_DATA_ADDRESS,
            runtime.primary_used,
            PRIMARY_DATA_CAPACITY,
        ),
        RuntimeArena("code", RUNTIME_ADDRESS, runtime.code_used, RUNTIME_CAPACITY),
        RuntimeArena(
            "data_secondary",
            SECONDARY_DATA_ADDRESS,
            runtime.secondary_used,
            SECONDARY_DATA_CAPACITY,
        ),
    )
    return FmvSubtitleBuild(
        apply_patches(base, LOAD_ADDRESS, patches),
        patches,
        runtime.cues,
        ASSET_FILES,
        ASSEMBLY_FILES,
        RUNTIME_INPUT_FILES,
        MappingProxyType(
            {
                f"game:{TARGET}": _sha256(stock),
                f"game:{MOVIE_TARGET}": _sha256(movie),
            }
        ),
        sum(arena.used_size for arena in arenas),
        sum(arena.capacity for arena in arenas),
        arenas,
    )


__all__ = [
    "ASSET_PATH",
    "CONFIG_PATH",
    "FmvSubtitleBuild",
    "MOVIE_TARGET",
    "RUNTIME_ADDRESS",
    "SubtitleCue",
    "build_fmv_subtitles",
    "centiseconds_to_frame",
    "load_subtitle_cues",
]
