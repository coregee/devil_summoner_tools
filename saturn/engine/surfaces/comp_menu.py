"""Build the Saturn COMP core on top of the shared NORMCOM runtime."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

from engine.surfaces.battle_ui import (
    NORMCOM_OUTPUT_PATH as BATTLE_NORMCOM_OUTPUT_PATH,
    build_battle_ui,
)
from engine.shared.font8 import font8_tables
from engine.shared.party_panel import build_compact_party_panel_data
from engine.core.config_io import object_value, read_json
from engine.core.patch_recipes import (
    PatchRecipe,
    PatchRecipeConfiguration,
    load_patch_recipe_configuration,
)
from engine.core.patching import Patch, apply_patches
from engine.core.sh2 import AssemblyError, assemble, assemble_file
from rom.util.catalog import load_catalog, validate_source
from rom.util.workflows import read_source_files
from text.util.event_repack import FontMetrics
from text.util.surfaces import load_surfaces


ENGINE_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = ENGINE_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "comp_menu.json"
ASSEMBLY_ROOT = ENGINE_ROOT / "asm"
GENERATED_ROOT = ENGINE_ROOT / "generated" / "game"
BUILD_PATH = GENERATED_ROOT / "comp_menu_build.json"
NORMCOM_OUTPUT_PATH = GENERATED_ROOT / "comp_menu" / "NORMCOM.BIN"
TEXT_GENERATED_ROOT = SATURN_ROOT / "text" / "generated" / "game"
TEXT_BUILD_PATH = TEXT_GENERATED_ROOT / "comp_menu_build.json"
FONT_ROOT = SATURN_ROOT / "font" / "generated" / "game"
FONT8_METRICS_PATH = FONT_ROOT / "FONT8_metrics.json"
FONT16_METRICS_PATH = FONT_ROOT / "FONT16_metrics.json"

TARGET = "NORMCOM.BIN"
LOAD_ADDRESS = 0x06020000
PANEL_MAX_PIXELS = 80
RENDERER_WIDTHS = 0x060204BC
ITEMNAME_WIDTHS = 0x060210A0
FONT8_ADDRESS = 0x00219150
FONT16_BASE = 0x0021A000
HELP_SCRATCH = 0x06020800
HELP_BLITTER = 0x06020810
HELP_CALLBACK = 0x06020930
HELP_PATTERN_LUT = 0x0603E9D4
HELP_MASK_LUT = 0x0603E9F4
PANEL_FIXED_DRAWER = 0x060205BC
MAGIC_FIXED_DRAWER = 0x06020640
MAGIC_FULL_DRAWER = 0x060206C4
PANEL_CAVE = 0x06025F34
PANEL_LIMIT = 0x06026500


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        return _sha256(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"missing generated input: {path}") from error


def _validate_surfaces() -> None:
    surfaces = load_surfaces()
    expected = {
        "comp.help": ("font16", 2, 300),
        "comp.party_demon_name": ("font8", 1, PANEL_MAX_PIXELS),
        "comp.stock_demon_name": ("font8", 1, PANEL_MAX_PIXELS),
        "comp.ability_name": ("font8", 1, 80),
        "party.character_name": ("font8", 1, PANEL_MAX_PIXELS),
    }
    for name, (font, rows, width) in expected.items():
        layout = surfaces.surface(name).en
        if (
            layout.font,
            layout.rows,
            layout.width.unit,
            layout.width.value,
        ) != (font, rows, "pixels", width):
            raise ValueError(f"{name} geometry changed")


def _validate_text_build() -> None:
    document = object_value(read_json(TEXT_BUILD_PATH), str(TEXT_BUILD_PATH))
    if (
        document.get("version") != 1
        or document.get("surface") != "comp.menu"
        or document.get("font8_metrics_sha256") != _file_sha256(FONT8_METRICS_PATH)
        or document.get("font16_metrics_sha256")
        != _file_sha256(FONT16_METRICS_PATH)
    ):
        raise ValueError("COMP text build uses different runtime inputs")
    outputs = object_value(document.get("outputs"), f"{TEXT_BUILD_PATH}.outputs")
    if set(outputs) != {"DVLNAME.DAT", "NORMHELP.DAT"}:
        raise ValueError("COMP text build has the wrong output set")
    for name, raw_row in outputs.items():
        row = object_value(raw_row, f"{TEXT_BUILD_PATH}.outputs.{name}")
        if row.get("sha256") != _file_sha256(TEXT_GENERATED_ROOT / name):
            raise ValueError(f"generated {name} does not match its text build")


def _panel_data(metrics: FontMetrics) -> dict[str, bytes]:
    return build_compact_party_panel_data(
        metrics,
        (TEXT_GENERATED_ROOT / "DVLNAME.DAT").read_bytes(),
        context="COMP",
    )


def _assembled(source: Path, address: int, symbols: dict[str, int]) -> bytes:
    try:
        result = assemble_file(source, address, symbols)
    except AssemblyError as error:
        raise ValueError(f"{source.relative_to(ENGINE_ROOT)}: {error}") from error
    if result.warnings:
        raise ValueError(
            f"{source.relative_to(ENGINE_ROOT)}: assembly warnings: {result.warnings}"
        )
    return result.data


def _source_paths(recipe: PatchRecipe, expected: tuple[str, ...]) -> tuple[Path, ...]:
    actual = tuple(
        source.relative_to(ASSEMBLY_ROOT).as_posix()
        for source in recipe.replacement.sources
    )
    if actual != expected:
        raise ValueError(f"{recipe.group}/{recipe.name}: assembly sources changed")
    return recipe.replacement.sources


def _align(payload: bytearray, address: int, alignment: int = 4) -> None:
    payload.extend(bytes((-(address + len(payload))) % alignment))


def _font16_width_layout() -> tuple[int, int]:
    document = object_value(read_json(FONT16_METRICS_PATH), str(FONT16_METRICS_PATH))
    width_table = object_value(
        document.get("width_table"), f"{FONT16_METRICS_PATH}.width_table"
    )
    if set(width_table) != {"storage_glyph", "code_limit"}:
        raise ValueError("FONT16 width-table layout is incomplete")
    storage_glyph = width_table["storage_glyph"]
    code_limit = width_table["code_limit"]
    if (
        type(storage_glyph) is not int
        or storage_glyph <= 0
        or type(code_limit) is not int
        or not 0 < code_limit <= 0xFFFF
    ):
        raise ValueError("FONT16 width-table layout is invalid")
    return FONT16_BASE + storage_glyph * 32, code_limit


def _build_item_name_cave(recipe: PatchRecipe, widths: bytes) -> bytes:
    (source,) = _source_paths(
        recipe, ("equipment_item_name.s",)
    )
    symbols = {
        "ITEM_FIRST": 0x00228C04,
        "ITEM_END": 0x0022F7A0,
        "ITEM_BASE": 0x00228C00,
        "WIDTHS": ITEMNAME_WIDTHS,
        "GLYPH": 0x06039AC4,
        "STOCK": 0x06039C0C,
    }
    code = _assembled(source, recipe.address, symbols)
    if recipe.address + len(code) != ITEMNAME_WIDTHS:
        raise ValueError("COMP item-name width-table address changed")
    payload = code + widths
    if len(payload) != len(recipe.expected):
        raise ValueError("COMP item-name assembly does not fill its cave")
    return payload


def _build_renderer_cave(recipe: PatchRecipe, widths: bytes) -> bytes:
    pixel, panel, magic, full = _source_paths(
        recipe,
        (
            "font8_pixel_blitter.s",
            "font8_fixed_name.s",
            "comp_menu/magic_grid_fixed_name.s",
            "comp_menu/magic_grid_full_name.s",
        ),
    )
    payload = bytearray(
        _assembled(pixel, recipe.address, {"FONT8": FONT8_ADDRESS})
    )
    _align(payload, recipe.address)
    if recipe.address + len(payload) != RENDERER_WIDTHS:
        raise ValueError("COMP FONT8 width-table address changed")
    payload.extend(widths)
    _align(payload, recipe.address)

    panel_address = recipe.address + len(payload)
    if panel_address != PANEL_FIXED_DRAWER:
        raise ValueError("COMP party-panel fallback address changed")
    payload.extend(
        _assembled(
            panel,
            panel_address,
            {
                "WIDTHS": RENDERER_WIDTHS,
                "PIXEL": recipe.address,
                "STOCK": 0x06027A08,
                "STRIDE": 0x0200,
            },
        )
    )
    _align(payload, recipe.address)

    magic_address = recipe.address + len(payload)
    if magic_address != MAGIC_FIXED_DRAWER:
        raise ValueError("COMP magic-grid fallback address changed")
    payload.extend(
        _assembled(
            magic,
            magic_address,
            {
                "WIDTHS": RENDERER_WIDTHS,
                "PIXEL": recipe.address,
                "ORIGINAL": 0x06027A08,
                "STRIDE": 0x0140,
            },
        )
    )
    _align(payload, recipe.address)

    full_address = recipe.address + len(payload)
    if full_address != MAGIC_FULL_DRAWER:
        raise ValueError("COMP full-name drawer address changed")
    payload.extend(
        _assembled(
            full,
            full_address,
            {
                "ITEM_FIRST": 0x00228C04,
                "ITEM_END": 0x0022F7A0,
                "ITEM_BASE": 0x00228C00,
                "MAGIC_FIRST": 0x0022F7A4,
                "MAGIC_END": 0x00235740,
                "MAGIC_BASE": 0x0022F7A0,
                "WIDTHS": RENDERER_WIDTHS,
                "PIXEL": recipe.address,
                "STRIDE": 0x0140,
                "Y_OFFSET": 0x0280,
                "FALLBACK": MAGIC_FIXED_DRAWER,
            },
        )
    )
    if len(payload) != len(recipe.expected):
        raise ValueError("COMP FONT8 assembly does not fill its cave")
    return bytes(payload)


def _build_help_blitter(recipe: PatchRecipe) -> bytes:
    (source,) = _source_paths(recipe, ("font16_subpixel_blitter.s",))
    payload = _assembled(
        source,
        recipe.address,
        {
            "FONT16_POINTER": HELP_SCRATCH,
            "RIGHT_MARGIN": HELP_SCRATCH + 4,
            "FRAMEBUFFER_POINTER": HELP_SCRATCH + 8,
            "TEXT_COLOR": HELP_SCRATCH + 12,
            "LINE_HEIGHT": HELP_SCRATCH + 14,
            "PATTERN_LUT": HELP_PATTERN_LUT,
            "MASK_LUT": HELP_MASK_LUT,
        },
    )
    if len(payload) != len(recipe.expected):
        raise ValueError("COMP help blitter does not fill its cave")
    return payload


def _build_help_callback(recipe: PatchRecipe) -> bytes:
    (source,) = _source_paths(recipe, ("comp_menu/normcom_help_word.s",))
    widths_address, width_limit = _font16_width_layout()
    payload = _assembled(
        source,
        recipe.address,
        {
            "SCRATCH_FB": HELP_SCRATCH + 8,
            "SCRATCH_STRIDE": HELP_SCRATCH + 4,
            "BLITTER": HELP_BLITTER,
            "WIDTHS": widths_address,
            "WIDTH_LIMIT": width_limit,
            "PACKED_SPACE": 267,
        },
    )
    if len(payload) != len(recipe.expected):
        raise ValueError("COMP help callback does not fill its cave")
    return payload


def _build_panel_cave(
    recipe: PatchRecipe, metrics: FontMetrics
) -> tuple[bytes, int]:
    (source,) = _source_paths(recipe, ("comp_menu/party_panel.s",))
    capacity = PANEL_LIMIT - PANEL_CAVE
    if recipe.address != PANEL_CAVE or len(recipe.expected) != capacity:
        raise ValueError("COMP panel cave contract changed")
    data = _panel_data(metrics)
    payload = bytearray()
    addresses: dict[str, int] = {}

    def append(name: str, alignment: int = 1) -> None:
        while (PANEL_CAVE + len(payload)) % alignment:
            payload.append(0)
        addresses[name] = PANEL_CAVE + len(payload)
        payload.extend(data[name])

    append("character_offsets", 2)
    append("character_pool")
    append("long_name_bits")
    append("name_pool", 2)
    append("high_name_pool", 2)
    while (PANEL_CAVE + len(payload)) & 3:
        payload.append(0)
    drawer_address = PANEL_CAVE + len(payload)
    payload.extend(
        _assembled(
            source,
            drawer_address,
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
                "PIXEL": 0x06020400,
                "STRIDE": 0x0200,
                "FALLBACK": PANEL_FIXED_DRAWER,
            },
        )
    )
    if len(payload) > capacity:
        raise ValueError(f"COMP party-panel cave uses {len(payload)}/{capacity} bytes")
    return bytes(payload).ljust(capacity, b"\0"), drawer_address


def _instruction(recipe: PatchRecipe) -> bytes:
    assert recipe.replacement.instruction is not None
    try:
        result = assemble(recipe.replacement.instruction, recipe.address)
    except AssemblyError as error:
        raise ValueError(f"{recipe.group}/{recipe.name}: {error}") from error
    if result.warnings or len(result.data) != len(recipe.expected):
        raise ValueError(f"{recipe.group}/{recipe.name}: invalid instruction")
    return result.data


def _bind_patches(
    config: PatchRecipeConfiguration, metrics: FontMetrics
) -> tuple[Patch, ...]:
    widths, _codes = font8_tables(metrics)
    recipes = config.patches[TARGET]
    panel_recipe = next(
        (recipe for recipe in recipes if recipe.name == "character_panel_cave"), None
    )
    if panel_recipe is None:
        raise ValueError("COMP config is missing the party-panel cave")
    panel, drawer_address = _build_panel_cave(panel_recipe, metrics)
    output: list[Patch] = []
    seen: set[str] = set()
    for recipe in recipes:
        replacement_recipe = recipe.replacement
        if replacement_recipe.kind == "assembly":
            seen.add(recipe.name)
            if recipe.name == "equipment_name_cave":
                replacement = _build_item_name_cave(recipe, widths)
            elif recipe.name == "subpixel_blitter":
                replacement = _build_help_blitter(recipe)
            elif recipe.name == "word_callback":
                replacement = _build_help_callback(recipe)
            elif recipe.name == "cursor_advance":
                (source,) = _source_paths(
                    recipe, ("comp_menu/help_cursor_advance.s",)
                )
                replacement = _assembled(source, recipe.address, {})
            elif recipe.name == "renderer_cave":
                replacement = _build_renderer_cave(recipe, widths)
            elif recipe.name == "character_panel_cave":
                replacement = panel
            else:
                raise ValueError(f"unsupported COMP assembly patch {recipe.name}")
        elif replacement_recipe.kind == "generated":
            if replacement_recipe.generator != "font16_scratch":
                raise ValueError(f"unsupported COMP generator {replacement_recipe.generator}")
            seen.add(recipe.name)
            replacement = struct.pack(">IHHIBBH", FONT16_BASE, 0x0200, 0, 0x25E60000, 2, 0, 16)
        elif replacement_recipe.kind == "pointer":
            assert replacement_recipe.pointer is not None
            replacement = struct.pack(">I", replacement_recipe.pointer)
        elif replacement_recipe.kind == "linked_pointer":
            if replacement_recipe.link != "party_panel_entry":
                raise ValueError(f"unsupported COMP link {replacement_recipe.link}")
            seen.add(recipe.name)
            replacement = struct.pack(">I", drawer_address)
        elif replacement_recipe.kind == "instruction":
            replacement = _instruction(recipe)
        else:
            raise ValueError(f"unsupported COMP recipe {replacement_recipe.kind}")
        output.append(
            Patch(
                recipe.group,
                recipe.name,
                recipe.address,
                recipe.expected,
                replacement,
            )
        )
    expected_built = {
        "renderer_cave",
        "equipment_name_cave",
        "character_panel_cave",
        "scratch",
        "subpixel_blitter",
        "word_callback",
        "cursor_advance",
        "panel_pointer_06029064",
        "panel_pointer_06029360",
        "panel_pointer_060295e4",
    }
    if seen != expected_built:
        raise ValueError("COMP config has an incomplete assembly/link contract")
    return tuple(output)


def build_comp_menu() -> dict[Path, bytes]:
    _validate_surfaces()
    _validate_text_build()
    config = load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="comp.menu",
        target_names={TARGET},
        input_names={"font8_metrics_sha256", "font16_metrics_sha256"},
    )
    actual_inputs = {
        "font8_metrics_sha256": _file_sha256(FONT8_METRICS_PATH),
        "font16_metrics_sha256": _file_sha256(FONT16_METRICS_PATH),
    }
    if actual_inputs != config.inputs:
        raise ValueError("COMP runtime inputs changed")
    contract = config.targets[TARGET]
    validated = validate_source(load_catalog()["game"])
    stock = read_source_files(validated, (TARGET,))[TARGET]
    if len(stock) != contract.size or _sha256(stock) != contract.stock_sha256:
        raise ValueError("stock NORMCOM.BIN does not match the COMP target")

    battle_outputs = build_battle_ui()
    base = battle_outputs[BATTLE_NORMCOM_OUTPUT_PATH]
    metrics = FontMetrics.load(FONT8_METRICS_PATH)
    patches = _bind_patches(config, metrics)
    output = apply_patches(base, contract.load_address, patches)
    assembly_files = tuple(
        sorted(
            {
                source
                for recipe in config.patches[TARGET]
                for source in recipe.replacement.sources
            }
        )
    )
    manifest = {
        "version": 1,
        "surface": "comp.menu",
        "patch_config_sha256": _file_sha256(CONFIG_PATH),
        "text_build_sha256": _file_sha256(TEXT_BUILD_PATH),
        "base_normcom_sha256": _sha256(base),
        "outputs": {TARGET: {"sha256": _sha256(output)}},
        "assembly_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): _file_sha256(path)
            for path in assembly_files
        },
        "patch_groups": list(dict.fromkeys(patch.group for patch in patches)),
        "patches": len(patches),
    }
    return {
        NORMCOM_OUTPUT_PATH: output,
        BUILD_PATH: (json.dumps(manifest, indent=2) + "\n").encode("utf-8"),
    }
