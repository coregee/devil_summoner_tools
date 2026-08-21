"""Build the proportional staff-name rows in END_ROLL.BIN."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Mapping

from engine.core.patch_recipes import (
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
CONFIG_PATH = ENGINE_ROOT / "config" / "credits_ui.json"
ASM_ROOT = ENGINE_ROOT / "asm" / "credits_ui"
OUTPUT_PATH = ENGINE_ROOT / "generated" / "game" / "END_ROLL.BIN"
BUILD_PATH = ENGINE_ROOT / "generated" / "game" / "credits_ui_build.json"
TARGET = "END_ROLL.BIN"
LOAD_ADDRESS = 0x06020000
TARGET_SIZE = 132_128

ASSET_PATH = ASSET_ROOT / "credits" / "names.json"
BINDING_PATH = BINDING_ROOT / "end_roll_credits.json"
CORPUS_PATH = CORPUS_ROOT / "game" / "addressed" / "end_roll_names.json"
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
    SOURCE_MANIFEST_PATH,
    DISC_CONFIG_PATH,
    BINDING_PATH,
    CORPUS_PATH,
)

MAIN_COUNT = 28
TEST_COUNT = 12
FIELD_COUNT = MAIN_COUNT + TEST_COUNT
MAIN_CELLS = 6
TEST_CELLS = 7
MAX_NAME_GLYPHS = 18

CAVE = 0x06025000
CAVE_LIMIT = 0x0602AD50
RENDERER = CAVE
TEST_MAIN_WRAPPER = 0x06025100
TEST_EXTRA_WRAPPER = 0x06025140
OFFSET_TABLE = 0x06025180
BITMAP_POOL = 0x060251D0
BITMAP_POOL_SIZE = MAIN_COUNT * MAIN_CELLS * 32 + TEST_COUNT * TEST_CELLS * 32
RUNTIME_USED = BITMAP_POOL + BITMAP_POOL_SIZE - CAVE
RUNTIME_CAPACITY = CAVE_LIMIT - CAVE

MAIN_HOOK = (0x0602CF5E, 0x0602CF90)
MAIN_VDP_LITERAL = 0x0602D018
MAIN_RENDERER_LITERAL = 0x0602D01C
TEST_MAIN_TRAMPOLINE = 0x0602D1B0
TEST_EXTRA_TRAMPOLINE = 0x0602D210
MAIN_CONTINUATION = MAIN_HOOK[1]
MAIN_VDP_BITMAP = 0x25E02000
TEST_VDP_BITMAP = 0x25E00000

ASSEMBLY_FILES = (
    ASM_ROOT / "renderer.s",
    ASM_ROOT / "test_wrapper.s",
    ASM_ROOT / "main_hook.s",
    ASM_ROOT / "trampoline.s",
)


@dataclass(frozen=True, slots=True)
class RuntimeArena:
    address: int
    used_size: int
    capacity: int


@dataclass(frozen=True, slots=True)
class CreditsUiBuild:
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
    assembly: Mapping[str, bytes]
    generated: Mapping[str, bytes]
    links: Mapping[str, int]
    widths: tuple[int, ...]
    compressed_fields: tuple[str, ...]


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        return _sha256(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"missing credits input: {path}") from error


def _configuration() -> PatchRecipeConfiguration:
    config = load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="credits.ui",
        target_names={TARGET},
        input_names={"font16_sha256", "font16_metrics_sha256"},
    )
    expected = (
        ("credits.runtime", "renderer", RENDERER, "assembly"),
        ("credits.runtime", "test_main_wrapper", TEST_MAIN_WRAPPER, "assembly"),
        ("credits.runtime", "test_extra_wrapper", TEST_EXTRA_WRAPPER, "assembly"),
        ("credits.runtime", "offset_table", OFFSET_TABLE, "generated"),
        ("credits.runtime", "bitmap_pool", BITMAP_POOL, "generated"),
        ("credits.main", "main_name_hook", MAIN_HOOK[0], "assembly"),
        ("credits.main", "main_vdp_literal", MAIN_VDP_LITERAL, "pointer"),
        (
            "credits.main",
            "main_renderer_literal",
            MAIN_RENDERER_LITERAL,
            "linked_pointer",
        ),
        (
            "credits.test",
            "test_main_trampoline",
            TEST_MAIN_TRAMPOLINE,
            "assembly",
        ),
        (
            "credits.test",
            "test_extra_trampoline",
            TEST_EXTRA_TRAMPOLINE,
            "assembly",
        ),
    )
    recipes = config.patches[TARGET]
    actual = tuple(
        (recipe.group, recipe.name, recipe.address, recipe.replacement.kind)
        for recipe in recipes
    )
    if actual != expected:
        raise ValueError("credits patch recipe inventory drifted")
    expected_sources = {
        "renderer": (ASSEMBLY_FILES[0].resolve(),),
        "test_main_wrapper": (ASSEMBLY_FILES[1].resolve(),),
        "test_extra_wrapper": (ASSEMBLY_FILES[1].resolve(),),
        "main_name_hook": (ASSEMBLY_FILES[2].resolve(),),
        "test_main_trampoline": (ASSEMBLY_FILES[3].resolve(),),
        "test_extra_trampoline": (ASSEMBLY_FILES[3].resolve(),),
    }
    for recipe in recipes:
        if recipe.replacement.kind == "assembly":
            if recipe.replacement.sources != expected_sources[recipe.name]:
                raise ValueError(f"credits {recipe.name} assembly source drifted")
        elif recipe.replacement.kind == "generated":
            if recipe.replacement.generator != "credits_data":
                raise ValueError("credits data generator contract drifted")
    if recipes[6].replacement.pointer != MAIN_VDP_BITMAP:
        raise ValueError("credits VDP bitmap pointer drifted")
    if recipes[7].replacement.link != "renderer":
        raise ValueError("credits renderer link drifted")
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
        raise ValueError("END_ROLL.BIN does not match the configured stock target")
    actual = {
        "font16_sha256": _file_sha256(FONT16_PATH),
        "font16_metrics_sha256": _file_sha256(FONT16_METRICS_PATH),
    }
    for name, expected in config.inputs.items():
        if actual[name] != expected:
            raise ValueError(
                f"credits {name} expected SHA-256 {expected}, found {actual[name]}"
            )
    if stock[CAVE - LOAD_ADDRESS : CAVE_LIMIT - LOAD_ADDRESS] != bytes(
        RUNTIME_CAPACITY
    ):
        raise ValueError("credits runtime cave is no longer entirely zero")


def _validate_surfaces() -> None:
    surfaces = load_surfaces()
    expected = {
        "credits.main_name": (
            ("font16", 1, "glyph_cells", 6, 6),
            ("font16", 1, "pixels", 96, 18),
        ),
        "credits.test_name": (
            ("font16", 1, "glyph_cells", 7, 7),
            ("font16", 1, "pixels", 112, 18),
        ),
    }
    for name, layouts in expected.items():
        surface = surfaces.surface(name)
        actual = tuple(
            (
                layout.font,
                layout.rows,
                layout.width.unit,
                layout.width.value,
                layout.glyphs,
            )
            for layout in (surface.ja, surface.en)
        )
        if actual != layouts:
            raise ValueError(f"{name} geometry changed: {actual!r}")


def _bound_names() -> tuple[tuple[str, str], ...]:
    physical = load_physical_record_files((CORPUS_PATH,))
    binding = load_binding(BINDING_PATH, physical_records=physical)
    ids = tuple(physical)
    if (
        len(ids) != FIELD_COUNT
        or binding.asset != PurePosixPath("credits/names.json")
        or tuple(binding.records) != ids
        or set(binding.record_surfaces) != set(ids)
        or any(
            surfaces
            != (("credits.main_name",) if index < MAIN_COUNT else ("credits.test_name",))
            for index, surfaces in enumerate(binding.record_surfaces.values())
        )
    ):
        raise ValueError("credits binding inventory drifted")
    values = load_bound_translations(
        ("game.end_roll_names.",),
        required_ids=set(ids),
        binding_paths=(BINDING_PATH,),
        physical_records=physical,
    )
    return tuple((physical_id, values[physical_id]) for physical_id in ids)


def _assemble_source(
    path: Path, address: int, symbols: Mapping[str, int]
) -> bytes:
    try:
        source = path.read_text(encoding="utf-8")
        result = assemble(source, address, dict(symbols))
    except (FileNotFoundError, AssemblyError) as error:
        raise ValueError(f"{path.name}: {error}") from error
    if result.warnings:
        raise ValueError(f"{path.name}: assembler warnings: {result.warnings}")
    return result.data


def _fit_zero(code: bytes, size: int, name: str) -> bytes:
    if len(code) > size:
        raise ValueError(f"credits {name} exceeds its {size}-byte slot")
    return code + bytes(size - len(code))


def _fit_nops(code: bytes, size: int, name: str) -> bytes:
    if len(code) > size or (size - len(code)) & 1:
        raise ValueError(f"credits {name} exceeds its {size}-byte hook")
    return code + bytes.fromhex("0009") * ((size - len(code)) // 2)


def _render_name_tiles(
    font16: bytes,
    codes: tuple[int, ...],
    advances: Mapping[int, int],
    cell_count: int,
) -> tuple[bytes, int, bool]:
    if not codes or len(codes) > MAX_NAME_GLYPHS:
        raise ValueError("credits name must contain 1 to 18 FONT16 glyphs")
    glyphs: list[tuple[int, bytes, int, int]] = []
    source_width = 0
    for code in codes:
        try:
            advance = advances[code]
        except KeyError as error:
            raise ValueError(f"credits glyph {code:#06x} has no width") from error
        start = code * 32
        glyph = font16[start : start + 32]
        if len(glyph) != 32:
            raise ValueError(f"credits glyph {code:#06x} exceeds FONT16")
        glyphs.append((code, glyph, advance, source_width))
        source_width += advance

    destination_width = cell_count * 16
    compressed = source_width > destination_width
    rows = [0] * 16
    for code, glyph, advance, glyph_x in glyphs:
        for row in range(16):
            word = struct.unpack_from(">H", glyph, row * 2)[0]
            for column in range(16):
                if not word & (1 << (15 - column)):
                    continue
                if column >= advance:
                    raise ValueError(
                        f"credits glyph {code:#06x} has ink beyond its advance"
                    )
                source_x = glyph_x + column
                destination_x = (
                    source_x * destination_width // source_width
                    if compressed
                    else source_x
                )
                if destination_x >= destination_width:
                    raise ValueError("credits name bitmap exceeds its surface")
                rows[row] |= 1 << (destination_width - destination_x - 1)

    output = bytearray()
    for cell in range(cell_count):
        left_shift = destination_width - cell * 16 - 8
        right_shift = left_shift - 8
        for row_start, shift in (
            (0, left_shift),
            (0, right_shift),
            (8, left_shift),
            (8, right_shift),
        ):
            output.extend(
                (rows[row] >> shift) & 0xFF
                for row in range(row_start, row_start + 8)
            )
    if len(output) != cell_count * 32:
        raise AssertionError("credits tile layout size changed")
    return bytes(output), source_width, compressed


def _build_runtime() -> _Runtime:
    metrics = FontMetrics.load(FONT16_METRICS_PATH)
    advances = {glyph.code: glyph.advance for glyph in metrics.glyphs}
    font16 = FONT16_PATH.read_bytes()
    offsets: list[int] = []
    bitmaps = bytearray()
    widths: list[int] = []
    compressed: list[str] = []
    for index, (physical_id, value) in enumerate(_bound_names()):
        try:
            codes = tuple(glyph.code for glyph in metrics.segment_output(value))
        except ValueError as error:
            raise ValueError(f"{physical_id}: {error}") from error
        offsets.append(len(bitmaps))
        cells = MAIN_CELLS if index < MAIN_COUNT else TEST_CELLS
        bitmap, width, was_compressed = _render_name_tiles(
            font16, codes, advances, cells
        )
        bitmaps.extend(bitmap)
        widths.append(width)
        if was_compressed:
            compressed.append(physical_id)
    if len(bitmaps) != BITMAP_POOL_SIZE or offsets[-1] > 0xFFFF:
        raise ValueError("credits bitmap pool geometry changed")

    renderer = _fit_zero(
        _assemble_source(
            ASSEMBLY_FILES[0],
            RENDERER,
            {"OFFSETS": OFFSET_TABLE, "BITMAPS": BITMAP_POOL},
        ),
        TEST_MAIN_WRAPPER - RENDERER,
        "renderer",
    )
    test_main = _fit_zero(
        _assemble_source(
            ASSEMBLY_FILES[1],
            TEST_MAIN_WRAPPER,
            {
                "INDEX_BASE": MAIN_COUNT,
                "RENDERER": RENDERER,
                "VDP_BITMAP": TEST_VDP_BITMAP,
            },
        ),
        TEST_EXTRA_WRAPPER - TEST_MAIN_WRAPPER,
        "test main wrapper",
    )
    test_extra = _fit_zero(
        _assemble_source(
            ASSEMBLY_FILES[1],
            TEST_EXTRA_WRAPPER,
            {
                "INDEX_BASE": MAIN_COUNT + 10,
                "RENDERER": RENDERER,
                "VDP_BITMAP": TEST_VDP_BITMAP,
            },
        ),
        OFFSET_TABLE - TEST_EXTRA_WRAPPER,
        "test extra wrapper",
    )
    main_hook = _fit_nops(
        _assemble_source(
            ASSEMBLY_FILES[2],
            MAIN_HOOK[0],
            {
                "CONTINUATION": MAIN_CONTINUATION,
                "RENDERER_LITERAL": MAIN_RENDERER_LITERAL,
                "VDP_LITERAL": MAIN_VDP_LITERAL,
            },
        ),
        MAIN_HOOK[1] - MAIN_HOOK[0],
        "main hook",
    )
    test_main_trampoline = _assemble_source(
        ASSEMBLY_FILES[3],
        TEST_MAIN_TRAMPOLINE,
        {"WRAPPER": TEST_MAIN_WRAPPER},
    )
    test_extra_trampoline = _assemble_source(
        ASSEMBLY_FILES[3],
        TEST_EXTRA_TRAMPOLINE,
        {"WRAPPER": TEST_EXTRA_WRAPPER},
    )
    return _Runtime(
        MappingProxyType(
            {
                "renderer": renderer,
                "test_main_wrapper": test_main,
                "test_extra_wrapper": test_extra,
                "main_name_hook": main_hook,
                "test_main_trampoline": test_main_trampoline,
                "test_extra_trampoline": test_extra_trampoline,
            }
        ),
        MappingProxyType(
            {
                "offset_table": struct.pack(f">{FIELD_COUNT}H", *offsets),
                "bitmap_pool": bytes(bitmaps),
            }
        ),
        MappingProxyType({"renderer": RENDERER}),
        tuple(widths),
        tuple(compressed),
    )


def _bind_patches(
    config: PatchRecipeConfiguration, stock: bytes
) -> tuple[tuple[Patch, ...], _Runtime]:
    runtime = _build_runtime()
    patches: list[Patch] = []
    assembly_seen: set[str] = set()
    generated_seen: set[str] = set()
    links_seen: set[str] = set()
    for recipe in config.patches[TARGET]:
        expected = resolve_recipe_expected(recipe, stock, LOAD_ADDRESS)
        replacement_recipe = recipe.replacement
        if replacement_recipe.kind == "assembly":
            try:
                replacement = runtime.assembly[recipe.name]
            except KeyError as error:
                raise ValueError(f"unknown credits assembly {recipe.name}") from error
            assembly_seen.add(recipe.name)
        elif replacement_recipe.kind == "generated":
            try:
                replacement = runtime.generated[recipe.name]
            except KeyError as error:
                raise ValueError(f"unknown credits data {recipe.name}") from error
            generated_seen.add(recipe.name)
        elif replacement_recipe.kind == "pointer":
            pointer = replacement_recipe.pointer
            assert pointer is not None
            replacement = struct.pack(">I", pointer)
        elif replacement_recipe.kind == "linked_pointer":
            link = replacement_recipe.link
            assert link is not None
            try:
                replacement = struct.pack(">I", runtime.links[link])
            except KeyError as error:
                raise ValueError(f"unknown credits link {link}") from error
            links_seen.add(link)
        else:
            raise ValueError(
                f"{recipe.group}/{recipe.name}: unsupported credits recipe"
            )
        if len(replacement) != len(expected):
            raise ValueError(
                f"{recipe.group}/{recipe.name}: generated {len(replacement)} bytes, "
                f"expected {len(expected)}"
            )
        patches.append(
            Patch(recipe.group, recipe.name, recipe.address, expected, replacement)
        )
    if assembly_seen != set(runtime.assembly):
        raise ValueError("credits assembly ownership differs from config")
    if generated_seen != set(runtime.generated):
        raise ValueError("credits generated-data ownership differs from config")
    if links_seen != set(runtime.links):
        raise ValueError("credits linked-pointer ownership differs from config")
    return tuple(patches), runtime


def build_credits_ui() -> CreditsUiBuild:
    """Build END_ROLL.BIN from verified stock and all 40 authored names."""
    config = _configuration()
    stock = _stock_source()
    _validate_sources(config, stock)
    _validate_surfaces()
    patches, _runtime = _bind_patches(config, stock)
    assembly_files = tuple(
        sorted(
            {
                source
                for recipe in config.patches[TARGET]
                for source in recipe.replacement.sources
            },
            key=lambda path: path.as_posix(),
        )
    )
    return CreditsUiBuild(
        apply_patches(stock, LOAD_ADDRESS, patches),
        patches,
        ASSET_FILES,
        assembly_files,
        RUNTIME_INPUT_FILES,
        MappingProxyType({f"game:{TARGET}": _sha256(stock)}),
        RUNTIME_USED,
        RUNTIME_CAPACITY,
        (RuntimeArena(CAVE, RUNTIME_USED, RUNTIME_CAPACITY),),
    )

