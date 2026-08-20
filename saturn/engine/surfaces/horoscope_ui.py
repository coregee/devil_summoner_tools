"""Build the eight authored horoscope messages in HOSI.BIN."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Mapping

from engine.core.patch_recipes import (
    PatchRecipe,
    PatchRecipeConfiguration,
    load_patch_recipe_configuration,
    resolve_recipe_expected,
)
from engine.core.patching import Patch, apply_patches
from engine.core.sh2 import AssemblyError, assemble
from rom.util.catalog import load_catalog, validate_source
from rom.util.workflows import read_source_files
from text.util.assets import (
    ASSET_ROOT,
    BINDING_ROOT,
    CORPUS_ROOT,
    load_binding,
    load_bound_translations,
    load_physical_record_files,
)
from text.util.event_repack import FontMetrics
from text.util.surfaces import load_surfaces


ENGINE_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = ENGINE_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "horoscope_ui.json"
OUTPUT_PATH = ENGINE_ROOT / "generated" / "game" / "HOSI.BIN"
BUILD_PATH = ENGINE_ROOT / "generated" / "game" / "horoscope_ui_build.json"
TARGET = "HOSI.BIN"
LOAD_ADDRESS = 0x06020000
TARGET_SIZE = 213_192

ASSET_PATH = ASSET_ROOT / "ui" / "horoscope.json"
BINDING_PATH = BINDING_ROOT / "horoscope.json"
CORPUS_PATH = CORPUS_ROOT / "game" / "fixed" / "hosi_messages.json"
SURFACES_PATH = SATURN_ROOT / "text" / "config" / "surfaces.json"
SOURCE_MANIFEST_PATH = (
    SATURN_ROOT / "text" / "config" / "sources" / "game" / "manifest.json"
)
DISC_CONFIG_PATH = SATURN_ROOT / "rom" / "discs.json"
FONT16_PATH = SATURN_ROOT / "font" / "generated" / "game" / "FONT16.FON"
FONT16_METRICS_PATH = (
    SATURN_ROOT / "font" / "generated" / "game" / "FONT16_metrics.json"
)

ASSET_FILES = (ASSET_PATH,)
RUNTIME_INPUT_FILES = (
    FONT16_PATH,
    FONT16_METRICS_PATH,
    SURFACES_PATH,
    DISC_CONFIG_PATH,
    SOURCE_MANIFEST_PATH,
    BINDING_PATH,
    CORPUS_PATH,
)

POOL_ADDRESS = 0x06020400
POOL_CAPACITY = 0x400
TERMINATOR = 0x8000
NEWLINE = 0x8001
LINE_CELLS = 20
MAX_LINES = 3
MAX_WORDS = 64

MESSAGE_ROWS = (
    ("message_01", "game.hosi_messages.o010f62.text", 0x0602D7F8),
    ("message_02", "game.hosi_messages.o010f8c.text", 0x0602D7FC),
    ("message_03", "game.hosi_messages.o010fb6.text", 0x0602D800),
    ("message_04", "game.hosi_messages.o010fe0.text", 0x0602D804),
    ("message_05", "game.hosi_messages.o01100a.text", 0x0602D808),
    ("message_06", "game.hosi_messages.o011034.text", 0x0602D80C),
    ("message_07", "game.hosi_messages.o01105e.text", 0x0602D8AC),
    ("message_08", "game.hosi_messages.o011088.text", 0x0602D8B0),
)


@dataclass(frozen=True, slots=True)
class RuntimeArena:
    address: int
    used_size: int
    capacity: int


@dataclass(frozen=True, slots=True)
class HoroscopeUiBuild:
    data: bytes
    patches: tuple[Patch, ...]
    asset_files: tuple[Path, ...]
    assembly_files: tuple[Path, ...]
    runtime_input_files: tuple[Path, ...]
    source_inputs: Mapping[str, str]
    runtime_used_size: int
    runtime_capacity: int
    runtime_arenas: tuple[RuntimeArena, ...]


@dataclass(frozen=True, slots=True)
class _Runtime:
    pool: bytes
    used_size: int
    links: Mapping[str, int]
    layouts: Mapping[str, tuple[int, ...]]


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        return _sha256(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"missing horoscope input: {path}") from error


def _configuration() -> PatchRecipeConfiguration:
    config = load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="horoscope.ui",
        target_names={TARGET},
        input_names={"font16_sha256", "font16_metrics_sha256"},
    )
    expected = (
        ("horoscope.messages", "message_pool", POOL_ADDRESS, "generated"),
        *(
            (
                "horoscope.messages",
                f"message_{index:02d}_pointer",
                literal,
                "linked_pointer",
            )
            for index, (_link, _physical_id, literal) in enumerate(
                MESSAGE_ROWS, start=1
            )
        ),
        ("horoscope.messages", "reveal_scale", 0x0602D880, "instruction"),
    )
    recipes = config.patches[TARGET]
    actual = tuple(
        (recipe.group, recipe.name, recipe.address, recipe.replacement.kind)
        for recipe in recipes
    )
    if actual != expected:
        raise ValueError("horoscope patch recipe inventory drifted")
    if recipes[0].replacement.generator != "horoscope_data":
        raise ValueError("horoscope data generator contract drifted")
    for recipe, (link, _physical_id, _literal) in zip(
        recipes[1:9], MESSAGE_ROWS
    ):
        if recipe.replacement.link != link:
            raise ValueError("horoscope message link contract drifted")
    if recipes[-1].replacement.instruction != "shll2 r5":
        raise ValueError("horoscope reveal instruction drifted")
    return config


def _stock_source() -> bytes:
    catalog = load_catalog()
    try:
        game = catalog["game"]
    except KeyError as error:
        raise ValueError("disc catalog has no game source") from error
    return read_source_files(validate_source(game, verify_hashes=False), (TARGET,))[
        TARGET
    ]


def _validate_sources(config: PatchRecipeConfiguration, stock: bytes) -> None:
    target = config.targets[TARGET]
    if (
        target.load_address != LOAD_ADDRESS
        or target.size != TARGET_SIZE
        or len(stock) != TARGET_SIZE
        or _sha256(stock) != target.stock_sha256
    ):
        raise ValueError("HOSI.BIN does not match the configured stock target")
    actual = {
        "font16_sha256": _file_sha256(FONT16_PATH),
        "font16_metrics_sha256": _file_sha256(FONT16_METRICS_PATH),
    }
    for name, expected in config.inputs.items():
        if actual[name] != expected:
            raise ValueError(
                f"horoscope {name} expected SHA-256 {expected}, "
                f"found {actual[name]}"
            )


def _validate_surface() -> None:
    surface = load_surfaces().surface("horoscope.message")
    actual = (
        (
            surface.ja.font,
            surface.ja.rows,
            surface.ja.width.unit,
            surface.ja.width.value,
            surface.ja.glyphs,
        ),
        (
            surface.en.font,
            surface.en.rows,
            surface.en.width.unit,
            surface.en.width.value,
            surface.en.glyphs,
        ),
    )
    expected = (
        ("font16", 3, "glyph_cells", 20, 60),
        ("font16", 3, "pixels", 320, 60),
    )
    if actual != expected:
        raise ValueError(f"horoscope.message geometry changed: {actual!r}")


def _bound_messages() -> Mapping[str, str]:
    physical = load_physical_record_files((CORPUS_PATH,))
    binding = load_binding(BINDING_PATH, physical_records=physical)
    expected_ids = {physical_id for _link, physical_id, _literal in MESSAGE_ROWS}
    if (
        binding.asset != PurePosixPath("ui/horoscope.json")
        or set(binding.records) != expected_ids
        or set(binding.record_surfaces) != expected_ids
        or any(
            surfaces != ("horoscope.message",)
            for surfaces in binding.record_surfaces.values()
        )
    ):
        raise ValueError("horoscope binding inventory drifted")
    return load_bound_translations(
        ("game.hosi_messages.",),
        required_ids=expected_ids,
        binding_paths=(BINDING_PATH,),
        physical_records=physical,
    )


def _layout_words(codes: tuple[int, ...], space_code: int) -> tuple[int, ...]:
    if not codes:
        raise ValueError("horoscope message cannot be empty")
    remaining = list(codes)
    lines: list[tuple[int, ...]] = []
    while len(remaining) > LINE_CELLS:
        boundaries = [
            index
            for index, code in enumerate(remaining[: LINE_CELLS + 1])
            if code == space_code and index > 0
        ]
        if not boundaries:
            raise ValueError("horoscope message has a word wider than 20 cells")
        boundary = boundaries[-1]
        lines.append(tuple(remaining[:boundary]))
        remaining = remaining[boundary + 1 :]
    if not remaining:
        raise ValueError("horoscope message cannot end with a space")
    lines.append(tuple(remaining))
    if len(lines) > MAX_LINES or any(
        not line or len(line) > LINE_CELLS for line in lines
    ):
        raise ValueError("horoscope message exceeds its three 20-cell rows")

    reconstructed: list[int] = []
    laid_out: list[int] = []
    for index, line in enumerate(lines):
        if index:
            reconstructed.append(space_code)
            laid_out.append(NEWLINE)
        reconstructed.extend(line)
        laid_out.extend(line)
    if tuple(reconstructed) != codes:
        raise ValueError("horoscope line layout changed the authored message")
    laid_out.append(TERMINATOR)
    if len(laid_out) > MAX_WORDS:
        raise ValueError("horoscope message exceeds its reveal limit")
    return tuple(laid_out)


def _build_runtime() -> _Runtime:
    values = _bound_messages()
    metrics = FontMetrics.load(FONT16_METRICS_PATH)
    try:
        space_code = metrics.by_text[" "].code
    except KeyError as error:
        raise ValueError("FONT16 metrics do not define the horoscope space") from error
    if space_code != 0x010B:
        raise ValueError("horoscope renderer space code changed")

    payload = bytearray()
    links: dict[str, int] = {}
    layouts: dict[str, tuple[int, ...]] = {}
    for link, physical_id, _literal in MESSAGE_ROWS:
        value = values[physical_id]
        try:
            codes = tuple(glyph.code for glyph in metrics.segment(value))
        except ValueError as error:
            raise ValueError(f"{physical_id}: {error}") from error
        layout = _layout_words(codes, space_code)
        links[link] = POOL_ADDRESS + len(payload)
        layouts[link] = layout
        payload.extend(struct.pack(f">{len(layout)}H", *layout))
    used_size = len(payload)
    if used_size > POOL_CAPACITY:
        raise ValueError("horoscope message pool exceeds its verified zero window")
    payload.extend(bytes(POOL_CAPACITY - used_size))
    return _Runtime(
        bytes(payload),
        used_size,
        MappingProxyType(links),
        MappingProxyType(layouts),
    )


def _instruction(recipe: PatchRecipe) -> bytes:
    source = recipe.replacement.instruction
    assert source is not None
    try:
        result = assemble(source, recipe.address)
    except AssemblyError as error:
        raise ValueError(f"{recipe.group}/{recipe.name}: {error}") from error
    if result.warnings or len(result.data) != len(recipe.expected):
        raise ValueError(f"{recipe.group}/{recipe.name}: invalid instruction")
    return result.data


def _bind_patches(
    config: PatchRecipeConfiguration,
    stock: bytes,
) -> tuple[tuple[Patch, ...], _Runtime]:
    runtime = _build_runtime()
    patches: list[Patch] = []
    links_seen: set[str] = set()
    for recipe in config.patches[TARGET]:
        expected = resolve_recipe_expected(recipe, stock, LOAD_ADDRESS)
        replacement_recipe = recipe.replacement
        if replacement_recipe.kind == "generated":
            if (
                recipe.name != "message_pool"
                or replacement_recipe.generator != "horoscope_data"
            ):
                raise ValueError("unknown horoscope generated-data recipe")
            replacement = runtime.pool
        elif replacement_recipe.kind == "linked_pointer":
            link = replacement_recipe.link
            assert link is not None
            try:
                replacement = struct.pack(">I", runtime.links[link])
            except KeyError as error:
                raise ValueError(f"unknown horoscope message link {link}") from error
            links_seen.add(link)
        elif replacement_recipe.kind == "instruction":
            replacement = _instruction(recipe)
        else:
            raise ValueError(
                f"{recipe.group}/{recipe.name}: unsupported horoscope recipe"
            )
        if len(replacement) != len(expected):
            raise ValueError(
                f"{recipe.group}/{recipe.name}: generated {len(replacement)} bytes, "
                f"expected {len(expected)}"
            )
        patches.append(
            Patch(recipe.group, recipe.name, recipe.address, expected, replacement)
        )
    if links_seen != set(runtime.links):
        raise ValueError("horoscope linked-pointer ownership differs from config")
    return tuple(patches), runtime


def build_horoscope_ui() -> HoroscopeUiBuild:
    """Build HOSI.BIN from its verified retail source and authored messages."""
    config = _configuration()
    stock = _stock_source()
    _validate_sources(config, stock)
    _validate_surface()
    patches, runtime = _bind_patches(config, stock)
    return HoroscopeUiBuild(
        apply_patches(stock, LOAD_ADDRESS, patches),
        patches,
        ASSET_FILES,
        (),
        RUNTIME_INPUT_FILES,
        MappingProxyType({f"game:{TARGET}": _sha256(stock)}),
        runtime.used_size,
        POOL_CAPACITY,
        (RuntimeArena(POOL_ADDRESS, runtime.used_size, POOL_CAPACITY),),
    )
