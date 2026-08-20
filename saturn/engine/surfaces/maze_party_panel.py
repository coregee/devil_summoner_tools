"""Compose the compact-name party panel onto the translated MAZE overlay."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from engine.core.patch_recipes import (
    ASSEMBLY_ROOT,
    PatchRecipe,
    PatchRecipeConfiguration,
    load_patch_recipe_configuration,
)
from engine.core.patching import Patch, apply_patches
from engine.core.sh2 import AssemblyError, assemble_file
from engine.shared.font8 import font8_tables
from engine.shared.party_panel import build_compact_party_panel_data
from rom.util.catalog import load_catalog, validate_source
from rom.util.workflows import read_source_files
from text.util.event_repack import FontMetrics
from text.util.surfaces import load_surfaces


ENGINE_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = ENGINE_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "maze_party_panel.json"
TARGET = "MAZE.BIN"
LOAD_ADDRESS = 0x06020000
TARGET_SIZE = 169_264
OUTPUT_PATH = ENGINE_ROOT / "generated" / "game" / "MAZE.BIN"
BUILD_PATH = ENGINE_ROOT / "generated" / "game" / "maze_party_panel_build.json"

FONT_ROOT = SATURN_ROOT / "font" / "generated" / "game"
FONT8_PATH = FONT_ROOT / "FONT8.FON"
FONT8_METRICS_PATH = FONT_ROOT / "FONT8_metrics.json"
TEXT_GENERATED_ROOT = SATURN_ROOT / "text" / "generated" / "game"
DVLNAME_PATH = TEXT_GENERATED_ROOT / "DVLNAME.DAT"
COMP_TEXT_BUILD_PATH = TEXT_GENERATED_ROOT / "comp_menu_build.json"
SURFACES_PATH = SATURN_ROOT / "text" / "config" / "surfaces.json"
SOURCE_MANIFEST_PATH = (
    SATURN_ROOT / "text" / "config" / "sources" / "game" / "manifest.json"
)
DISC_CONFIG_PATH = SATURN_ROOT / "rom" / "discs.json"

ASSET_FILES = (
    SATURN_ROOT.parent / "assets" / "text" / "characters.json",
    SATURN_ROOT.parent / "assets" / "text" / "demons.json",
)
RUNTIME_INPUT_FILES = (
    FONT8_PATH,
    FONT8_METRICS_PATH,
    DVLNAME_PATH,
    COMP_TEXT_BUILD_PATH,
    SURFACES_PATH,
    SOURCE_MANIFEST_PATH,
    DISC_CONFIG_PATH,
    SATURN_ROOT / "text" / "bindings" / "characters.json",
    SATURN_ROOT / "text" / "bindings" / "demons.json",
    SATURN_ROOT / "text" / "corpus" / "game" / "fixed" / "charname.json",
    SATURN_ROOT / "text" / "corpus" / "game" / "fixed" / "dvlname.json",
)

RENDERER_CAVE = 0x06022800
RENDERER_LIMIT = 0x06022C00
RENDERER_WIDTHS = 0x060228BC
FIXED_DRAWER = 0x060229BC
RENDERER_USED = 574
PANEL_CAVE = 0x06023800
PANEL_LIMIT = 0x06024000
PANEL_POINTERS = (0x0603F364, 0x0603F660, 0x0603F8E4)


@dataclass(frozen=True, slots=True)
class RuntimeArena:
    address: int
    used_size: int
    capacity: int


@dataclass(frozen=True, slots=True)
class MazePartyPanelBuild:
    data: bytes
    patches: tuple[Patch, ...]
    asset_files: tuple[Path, ...]
    assembly_files: tuple[Path, ...]
    runtime_input_files: tuple[Path, ...]
    source_inputs: Mapping[str, str]
    runtime_used_size: int
    runtime_capacity: int
    runtime_arenas: tuple[RuntimeArena, ...]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        return _sha256(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"missing MAZE party-panel input: {path}") from error


def _configuration() -> PatchRecipeConfiguration:
    config = load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="maze.party_panel",
        target_names={TARGET},
        input_names={"font8_metrics_sha256"},
    )
    expected = (
        ("renderer_cave", RENDERER_CAVE, "assembly"),
        ("compact_name_cave", PANEL_CAVE, "assembly"),
        *(
            (f"panel_pointer_{address:08x}", address, "linked_pointer")
            for address in PANEL_POINTERS
        ),
    )
    actual = tuple(
        (recipe.name, recipe.address, recipe.replacement.kind)
        for recipe in config.patches[TARGET]
    )
    if actual != expected:
        raise ValueError("MAZE party-panel recipe inventory changed")
    if config.inputs != {"font8_metrics_sha256": _file_sha256(FONT8_METRICS_PATH)}:
        raise ValueError("MAZE party-panel font input changed")
    return config


def _validate_surfaces() -> None:
    surfaces = load_surfaces()
    for name in ("battle.party_demon_name", "party.character_name"):
        layout = surfaces.surface(name).en
        if (
            layout.font,
            layout.rows,
            layout.width.unit,
            layout.width.value,
        ) != ("font8", 1, "pixels", 80):
            raise ValueError(f"{name} geometry changed")


def _validate_text_build() -> None:
    try:
        document = json.loads(COMP_TEXT_BUILD_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError("missing or invalid COMP text build") from error
    try:
        output = document["outputs"]["DVLNAME.DAT"]
    except (KeyError, TypeError) as error:
        raise ValueError("COMP text build is missing DVLNAME") from error
    if (
        document.get("version") != 1
        or document.get("surface") != "comp.menu"
        or document.get("font8_metrics_sha256") != _file_sha256(FONT8_METRICS_PATH)
        or output.get("sha256") != _file_sha256(DVLNAME_PATH)
        or output.get("records") != 319
    ):
        raise ValueError("MAZE party panel uses stale generated demon names")


def _source_names(recipe: PatchRecipe) -> tuple[str, ...]:
    return tuple(
        path.relative_to(ASSEMBLY_ROOT).as_posix()
        for path in recipe.replacement.sources
    )


def _assembled(path: Path, address: int, symbols: dict[str, int]) -> bytes:
    try:
        result = assemble_file(path, address, symbols)
    except AssemblyError as error:
        raise ValueError(f"{path.relative_to(ENGINE_ROOT)}: {error}") from error
    if result.warnings:
        raise ValueError(f"{path.relative_to(ENGINE_ROOT)}: {result.warnings}")
    return result.data


def _renderer(recipe: PatchRecipe, metrics: FontMetrics) -> bytes:
    if (
        recipe.address != RENDERER_CAVE
        or len(recipe.expected) != RENDERER_LIMIT - RENDERER_CAVE
        or _source_names(recipe)
        != ("font8_pixel_blitter.s", "font8_fixed_name.s")
    ):
        raise ValueError("MAZE party-panel renderer contract changed")
    widths, _codes = font8_tables(metrics)
    pixel, fixed = recipe.replacement.sources
    payload = bytearray(
        _assembled(pixel, RENDERER_CAVE, {"FONT8": 0x00219150})
    )
    payload.extend(bytes((-(RENDERER_CAVE + len(payload))) % 4))
    if RENDERER_CAVE + len(payload) != RENDERER_WIDTHS:
        raise ValueError("MAZE party-panel width table moved")
    payload.extend(widths)
    payload.extend(bytes((-(RENDERER_CAVE + len(payload))) % 4))
    if RENDERER_CAVE + len(payload) != FIXED_DRAWER:
        raise ValueError("MAZE party-panel fallback moved")
    payload.extend(
        _assembled(
            fixed,
            FIXED_DRAWER,
            {
                "WIDTHS": RENDERER_WIDTHS,
                "PIXEL": RENDERER_CAVE,
                "STOCK": 0x0603E5E0,
                "STRIDE": 0x0200,
            },
        )
    )
    if len(payload) != RENDERER_USED:
        raise ValueError(f"MAZE party renderer uses {len(payload)}/{RENDERER_USED}")
    return bytes(payload).ljust(len(recipe.expected), b"\0")


def _panel_runtime(
    recipe: PatchRecipe, metrics: FontMetrics
) -> tuple[bytes, int, int]:
    if (
        recipe.address != PANEL_CAVE
        or len(recipe.expected) != PANEL_LIMIT - PANEL_CAVE
        or _source_names(recipe) != ("comp_menu/party_panel.s",)
    ):
        raise ValueError("MAZE compact-name cave contract changed")
    data = build_compact_party_panel_data(
        metrics,
        DVLNAME_PATH.read_bytes(),
        context="MAZE party panel",
    )
    payload = bytearray()
    addresses: dict[str, int] = {}

    def append(name: str, alignment: int = 1) -> None:
        payload.extend(bytes((-(PANEL_CAVE + len(payload))) % alignment))
        addresses[name] = PANEL_CAVE + len(payload)
        payload.extend(data[name])

    append("character_offsets", 2)
    append("character_pool")
    append("long_name_bits")
    append("name_pool", 2)
    append("high_name_pool", 2)
    payload.extend(bytes((-(PANEL_CAVE + len(payload))) % 4))
    drawer = PANEL_CAVE + len(payload)
    payload.extend(
        _assembled(
            recipe.replacement.sources[0],
            drawer,
            {
                "DVL_BASE": 0x0023F5D0,
                "DVL_END": 0x0023FFD0,
                "CHAR_BASE": 0x0023FFD0,
                "CHAR_FIRST": 0x0023FFD8,
                "CHAR_END": 0x00240000,
                "CHAR_OFFSETS": addresses["character_offsets"],
                "CHAR_POOL": addresses["character_pool"],
                "LONG_NAME_BITS": addresses["long_name_bits"],
                "NAME_POOL": addresses["name_pool"],
                "HIGH_NAME_POOL": addresses["high_name_pool"],
                "WIDTHS": RENDERER_WIDTHS,
                "PIXEL": RENDERER_CAVE,
                "STRIDE": 0x0200,
                "FALLBACK": FIXED_DRAWER,
            },
        )
    )
    if len(payload) > len(recipe.expected):
        raise ValueError(
            f"MAZE compact-name cave uses {len(payload)}/{len(recipe.expected)} bytes"
        )
    return bytes(payload).ljust(len(recipe.expected), b"\0"), drawer, len(payload)


def build_maze_party_panel(base: bytes) -> MazePartyPanelBuild:
    _validate_surfaces()
    _validate_text_build()
    config = _configuration()
    contract = config.targets[TARGET]
    if len(base) != TARGET_SIZE:
        raise ValueError("composed MAZE base size changed")
    validated = validate_source(load_catalog()["game"])
    stock = read_source_files(validated, (TARGET,))[TARGET]
    if len(stock) != contract.size or _sha256(stock) != contract.stock_sha256:
        raise ValueError("stock MAZE does not match the party-panel target")

    metrics = FontMetrics.load(FONT8_METRICS_PATH)
    recipes = config.patches[TARGET]
    renderer = _renderer(recipes[0], metrics)
    panel, drawer, panel_used = _panel_runtime(recipes[1], metrics)
    patches: list[Patch] = []
    for recipe in recipes:
        if recipe.name == "renderer_cave":
            replacement = renderer
        elif recipe.name == "compact_name_cave":
            replacement = panel
        else:
            if recipe.replacement.link != "party_panel_entry":
                raise ValueError(f"unsupported MAZE party-panel link {recipe.name}")
            replacement = struct.pack(">I", drawer)
        patches.append(
            Patch(
                recipe.group,
                recipe.name,
                recipe.address,
                recipe.expected,
                replacement,
            )
        )
    result = apply_patches(base, LOAD_ADDRESS, patches)
    assembly_files = tuple(
        dict.fromkeys(
            source
            for recipe in recipes
            for source in recipe.replacement.sources
        )
    )
    arenas = (
        RuntimeArena(RENDERER_CAVE, RENDERER_USED, RENDERER_LIMIT - RENDERER_CAVE),
        RuntimeArena(PANEL_CAVE, panel_used, PANEL_LIMIT - PANEL_CAVE),
    )
    return MazePartyPanelBuild(
        data=result,
        patches=tuple(patches),
        asset_files=ASSET_FILES,
        assembly_files=assembly_files,
        runtime_input_files=RUNTIME_INPUT_FILES,
        source_inputs=MappingProxyType(
            {"game:MAZE.BIN": _sha256(stock), "composed:MAZE.BIN": _sha256(base)}
        ),
        runtime_used_size=sum(arena.used_size for arena in arenas),
        runtime_capacity=sum(arena.capacity for arena in arenas),
        runtime_arenas=arenas,
    )


__all__ = [
    "BUILD_PATH",
    "CONFIG_PATH",
    "OUTPUT_PATH",
    "TARGET",
    "MazePartyPanelBuild",
    "RuntimeArena",
    "build_maze_party_panel",
]
