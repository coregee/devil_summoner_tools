"""Build the Gouma-den fusion consumer directly from authored text assets."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path

from engine.core.patching import Patch, apply_patches
from engine.core.patch_recipes import (
    PatchRecipe,
    PatchRecipeConfiguration,
    load_patch_recipe_configuration,
)
from engine.core.sh2 import AssemblyError, assemble, assemble_file
from engine.shared.demon_sort import encode_sorted_pool
from engine.shared.event_window import font16_layout as shared_font16_layout
from text.util.assets import BINDING_ROOT, load_asset, load_binding
from text.util.event_repack import FontMetrics
from text.util.surfaces import load_surfaces


ENGINE_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = ENGINE_ROOT.parent
TEXT_ROOT = SATURN_ROOT / "text"
FONT_ROOT = SATURN_ROOT / "font" / "generated" / "game"
FONT16_METRICS_PATH = FONT_ROOT / "FONT16_metrics.json"
FONT12_METRICS_PATH = FONT_ROOT / "FONT12_metrics.json"
FONT8_METRICS_PATH = FONT_ROOT / "FONT8_metrics.json"
CONFIG_PATH = ENGINE_ROOT / "config" / "fusion.json"
ASSEMBLY_ROOT = ENGINE_ROOT / "asm"
FUSION_ASSEMBLY_ROOT = ASSEMBLY_ROOT / "fusion"
SURFACE_BLITTER_SOURCE = ASSEMBLY_ROOT / "font16_surface_blitter.s"
FONT8_BLITTER_SOURCE = FUSION_ASSEMBLY_ROOT / "font8_surface_blitter.s"
NAME_DRAWERS_SOURCE = FUSION_ASSEMBLY_ROOT / "name_drawers.s"
NAME_SORT_SOURCE = FUSION_ASSEMBLY_ROOT / "name_sort.s"
CONFIRMATION_DRAWER_SOURCE = FUSION_ASSEMBLY_ROOT / "confirmation_drawer.s"
CONFIRMATION_LOOKUP_SOURCE = (
    FUSION_ASSEMBLY_ROOT / "confirmation_pointer_lookup.s"
)
CONFIRMATION_LOOKUP_STOCK_SOURCE = (
    FUSION_ASSEMBLY_ROOT / "confirmation_pointer_lookup_stock.s"
)
ASSEMBLY_FILES = (
    SURFACE_BLITTER_SOURCE,
    FONT8_BLITTER_SOURCE,
    NAME_DRAWERS_SOURCE,
    NAME_SORT_SOURCE,
    CONFIRMATION_DRAWER_SOURCE,
    CONFIRMATION_LOOKUP_SOURCE,
    CONFIRMATION_LOOKUP_STOCK_SOURCE,
)
TARGET = "EVENT.BIN"

LOAD_ADDRESS = 0x06020000
CAVE_ADDRESS = 0x06021800
CAVE_END = 0x06022FBC
PACKED_FETCH_ADDRESS = 0x06023000
NAME_SORT_ADDRESS = 0x060451E0
NAME_SORT_SIZE = 0x200
NAME_SORT_STOCK_SHA256 = (
    "125d4a15c59aabee09003bba2ee91e81e5d5fde47c9c5a5d98f3133ad86b1638"
)

DEMON_COUNT = 319
CHARACTER_COUNT = 6
RACE_COUNT = 43
TERMINATOR = 0xFF
WORD_TERMINATOR = 0x8000
FONT16_SPACE = 267

LIST_NAME_WIDTH = 96
PREVIEW_NAME_WIDTH = 96
PREVIEW_RACE_WIDTH = 24
TABLE_NAME_WIDTH = 96
TABLE_RACE_WIDTH = 40
CHART_CELL_WIDTH = 26
GUIDE_WIDTH = 300
GUIDE_GLYPH_LIMIT = 100
HELP_WIDTH = 284
HELP_GLYPH_LIMIT = 94

MAIN_FILE = 0x5458E
MAIN_SIZE = 0xA0
POINTER_TABLE_OFFSET = 2
LABEL_YES_FILE = MAIN_FILE + MAIN_SIZE
LABEL_NO_FILE = LABEL_YES_FILE + 8
CONFIRMATION_WORDS = {
    "confirm_prompt": 20,
    "level_too_low": 34,
    "duplicate_demon": 30,
    "begin_fusion": 20,
    "label_yes": 4,
    "label_no": 4,
}


@dataclass(frozen=True, slots=True)
class FusionBuild:
    data: bytes
    runtime: bytes
    addresses: dict[str, int]
    patches: tuple[Patch, ...]
    asset_files: tuple[Path, ...]
    assembly_files: tuple[Path, ...]


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        return _sha256(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"missing Fusion build input: {path}") from error


def _align(payload: bytearray, alignment: int) -> None:
    payload.extend(bytes((-len(payload)) % alignment))


def _assembled(
    source: Path,
    address: int,
    symbols: dict[str, int],
    *,
    source_text: str | None = None,
) -> tuple[bytes, dict[str, int]]:
    try:
        result = (
            assemble(source_text, address, symbols)
            if source_text is not None
            else assemble_file(source, address, symbols)
        )
    except (AssemblyError, FileNotFoundError) as error:
        raise ValueError(f"{source.relative_to(ENGINE_ROOT)}: {error}") from error
    if result.warnings:
        raise ValueError(
            f"{source.relative_to(ENGINE_ROOT)}: assembly warnings: {result.warnings}"
        )
    return result.data, result.labels


def _instruction(address: int, source: str) -> bytes:
    try:
        result = assemble(source, address)
    except AssemblyError as error:
        raise ValueError(f"fusion instruction at {address:#x}: {error}") from error
    if result.warnings or len(result.data) != 2:
        raise ValueError(f"fusion instruction at {address:#x} is not one word")
    return result.data


def _name_rows(binding_name: str, prefix: str, count: int) -> tuple[str, ...]:
    binding = load_binding(BINDING_ROOT / binding_name)
    catalog = load_asset(binding.asset)
    output: list[str] = []
    for index in range(count):
        physical_id = f"{prefix}.o{index * 8:06x}.text"
        try:
            asset_ref = binding.records[physical_id]
        except KeyError as error:
            raise ValueError(f"{binding_name}: missing {physical_id}") from error
        translation = catalog.field(asset_ref).resolve(
            binding.variants.get(physical_id)
        )[1]
        if not translation:
            raise ValueError(f"{binding_name}: {asset_ref} has no translation")
        output.append(translation)
    return tuple(output)


def _race_rows() -> tuple[tuple[str, str, str], ...]:
    binding = load_binding(BINDING_ROOT / "races.json")
    catalog = load_asset(binding.asset)
    rows: list[tuple[str, str, str]] = []
    for index in range(RACE_COUNT):
        physical_id = f"game.normcom_tables.races.r{index:04d}"
        asset_ref = binding.records[physical_id]
        entry_name = asset_ref.split(".", 1)[0]
        entry = catalog.entries[entry_name]
        table_field = "fusion_name" if entry_name == "human" else "name"
        values = tuple(
            entry.fields[field].translation
            for field in (
                table_field,
                "fusion_preview_label",
                "fusion_chart_label",
            )
        )
        if not all(values):
            raise ValueError(f"races.json: {entry_name} has incomplete fusion text")
        rows.append(values)
    return tuple(rows)


def _codes(metrics: FontMetrics) -> dict[str, int]:
    return {
        text: glyph.code
        for text, glyph in metrics.by_text.items()
        if len(text) == 1
    }


def _widths(metrics: FontMetrics, size: int) -> bytes:
    output = bytearray(size)
    for glyph in metrics.glyphs:
        if not 0 <= glyph.code < size:
            raise ValueError(f"{metrics.font}: glyph code exceeds width table")
        output[glyph.code] = glyph.advance
    return bytes(output)


def _encode_pool(
    values: tuple[str, ...], codes: dict[str, int]
) -> tuple[bytes, bytes]:
    offsets: list[int] = []
    pool = bytearray()
    for value in values:
        offsets.append(len(pool))
        try:
            pool.extend(codes[character] for character in value)
        except KeyError as error:
            raise ValueError(
                f"unsupported fusion character {error.args[0]!r}"
            ) from error
        pool.append(TERMINATOR)
    if len(pool) > 0xFFFF:
        raise ValueError("fusion text pool exceeds 16-bit offsets")
    return struct.pack(f">{len(offsets)}H", *offsets), bytes(pool)


def _font8_map(
    font12_codes: dict[str, int],
    font8_codes: dict[str, int],
    requested: tuple[str, ...],
) -> bytes:
    output = bytearray([0xFF] * 256)
    for character in set(font12_codes) & set(font8_codes):
        code12 = font12_codes[character]
        code8 = font8_codes[character]
        if not 0 <= code12 < 256 or not 0 <= code8 < 256:
            continue
        existing = output[code12]
        if existing not in (0xFF, code8):
            raise ValueError(f"FONT12 code {code12:#x} has two FONT8 mappings")
        output[code12] = code8
    missing = sorted(
        character
        for character in set("".join(requested))
        if character not in font12_codes
        or output[font12_codes[character]] == 0xFF
    )
    if missing:
        raise ValueError(f"fusion FONT8 mapping is missing {''.join(missing)!r}")
    return bytes(output)


def _chart_widths(
    table_rows: tuple[str, ...],
    authored_rows: tuple[str, ...],
    font8: FontMetrics,
) -> bytes:
    glyphs = font8.by_text
    output = bytearray()
    derived: list[str] = []
    for value in table_rows:
        text: list[str] = []
        width = 0
        for character in value:
            glyph = glyphs[character]
            advance = glyph.advance + (character != " ")
            if width + advance > CHART_CELL_WIDTH:
                break
            text.append(character)
            width += advance
        if not text:
            raise ValueError(f"fusion chart label {value!r} has no fitting prefix")
        derived.append("".join(text))
        output.append(width)
    if tuple(derived) != authored_rows:
        raise ValueError(
            "fusion chart runtime prefixes disagree with fusion_chart_label assets"
        )
    return bytes(output)


def _validate_surfaces() -> None:
    surfaces = load_surfaces()
    expected = {
        "fusion.status_name": ("font12", LIST_NAME_WIDTH),
        "fusion.preview_demon_name": ("font12", PREVIEW_NAME_WIDTH),
        "fusion.preview_race": ("font12", PREVIEW_RACE_WIDTH),
        "fusion.chart_race": ("font8", CHART_CELL_WIDTH),
        "fusion.table_race": ("font8", TABLE_RACE_WIDTH),
        "fusion.table_demon_name": ("font8", TABLE_NAME_WIDTH),
        "fusion.table_character_name": ("font12", TABLE_NAME_WIDTH),
        "fusion.guide": ("font12", GUIDE_WIDTH),
        "fusion.help": ("font8", HELP_WIDTH),
    }
    for name, (font, width) in expected.items():
        layout = surfaces.surface(name).en
        if (
            layout.font != font
            or layout.rows != 1
            or layout.width.unit != "pixels"
            or layout.width.value != width
        ):
            raise ValueError(f"{name} does not match the proved fusion geometry")


def _runtime_payload() -> tuple[bytes, dict[str, int], tuple[Path, ...]]:
    font12 = FontMetrics.load(FONT12_METRICS_PATH)
    font8 = FontMetrics.load(FONT8_METRICS_PATH)
    demon_names = _name_rows("demons.json", "game.dvlname", DEMON_COUNT)
    character_names = _name_rows("characters.json", "game.charname", CHARACTER_COUNT)
    race_rows = _race_rows()
    table_races = tuple(row[0] for row in race_rows)
    preview_races = tuple(row[1] for row in race_rows)
    chart_races = tuple(row[2] for row in race_rows)
    codes12 = _codes(font12)
    codes8 = _codes(font8)

    race_offsets, race_pool = _encode_pool(preview_races, codes12)
    demon_offsets, demon_pool = encode_sorted_pool(demon_names, codes12)
    character_offsets, character_pool = _encode_pool(character_names, codes12)
    table_offsets, table_pool = _encode_pool(table_races, codes12)
    chart_widths = _chart_widths(table_races, chart_races, font8)
    widths12 = bytearray(_widths(font12, FONT16_SPACE + 1))
    widths12[FONT16_SPACE] = widths12[0]
    widths8 = _widths(font8, 256)
    code_map = _font8_map(codes12, codes8, (*table_races, *demon_names))

    payload = bytearray(widths12)
    addresses = {"font12_widths": CAVE_ADDRESS}

    def append(name: str, value: bytes, *, alignment: int = 1) -> None:
        _align(payload, alignment)
        addresses[name] = CAVE_ADDRESS + len(payload)
        payload.extend(value)

    append("race_offsets", race_offsets)
    append("demon_offsets", demon_offsets)
    append("character_offsets", character_offsets)
    append("race_pool", race_pool)
    append("demon_pool", demon_pool)
    append("character_pool", character_pool)
    append("table_race_offsets", table_offsets, alignment=2)
    append("table_race_pool", table_pool)
    append("chart_widths", chart_widths)
    append("font8_widths", widths8)
    append("font8_map", code_map)
    _align(payload, 4)
    surface_address = CAVE_ADDRESS + len(payload)
    surface, _surface_labels = _assembled(
        SURFACE_BLITTER_SOURCE,
        surface_address,
        {
            "FONT12": 0x06062598,
            "PATTERN_LUT": 0x0602B9F4,
            "MASK_LUT": 0x0602BA14,
        },
    )
    append("surface_blitter", surface)

    _align(payload, 4)
    font8_address = CAVE_ADDRESS + len(payload)
    font8_blitter, _font8_labels = _assembled(
        FONT8_BLITTER_SOURCE,
        font8_address,
        {"FONT8": 0x00219150},
    )
    append("font8_blitter", font8_blitter)

    _align(payload, 4)
    drawer_address = CAVE_ADDRESS + len(payload)
    drawer, drawer_labels = _assembled(
        NAME_DRAWERS_SOURCE,
        drawer_address,
        {
            "RACE_BASE": 219,
            "RACE_COUNT": RACE_COUNT,
            "RACE_STOCK": 0x0603C410,
            "RACE_OFFSETS": addresses["race_offsets"],
            "RACE_POOL": addresses["race_pool"],
            "RACE_MAX_WIDTH": PREVIEW_RACE_WIDTH,
            "CHART_RACE_WIDTHS": addresses["chart_widths"],
            "CHART_CELL_WIDTH": CHART_CELL_WIDTH,
            "TABLE_RACE_OFFSETS": addresses["table_race_offsets"],
            "TABLE_RACE_POOL": addresses["table_race_pool"],
            "TABLE_FONT8_MODE": 4,
            "TABLE_RACE_MAX_WIDTH": TABLE_RACE_WIDTH,
            "TABLE_RACE_STOCK": 0x0603C4C8,
            "DVL_COUNT": DEMON_COUNT,
            "DEMON_STOCK": 0x0603C50C,
            "DVL_OFFSETS": addresses["demon_offsets"],
            "DVL_POOL": addresses["demon_pool"],
            "NAME_MAX_WIDTH": TABLE_NAME_WIDTH,
            "PLAYER_ID": 0x8000,
            "CHAR_COUNT": CHARACTER_COUNT,
            "CHARACTER_STOCK": 0x0603C5C8,
            "CHAR_OFFSETS": addresses["character_offsets"],
            "CHAR_POOL": addresses["character_pool"],
            "PLAYER_CODENAME": 0x0023FE14,
            "WORD_TERMINATOR": WORD_TERMINATOR,
            "FONT16_SPACE": FONT16_SPACE,
            "FONT8_CODE_MAP": addresses["font8_map"],
            "FONT8_WIDTHS": addresses["font8_widths"],
            "WIDTHS": addresses["font12_widths"],
            "FONT8_SPACE": codes8[" "],
            "TABLE_FONT8_Y_OFFSET": 2,
            "SURFACE_GLYPH": addresses["surface_blitter"],
            "STOCK_GLYPH": 0x0603B760,
            "FONT8_GLYPH": addresses["font8_blitter"],
            "GUIDE_DESCRIPTION_Y": 150,
        },
    )
    label_names = {
        "fusion_preview_race": "fusion_race_vwf",
        "fusion_chart_race": "fusion_chart_race_font8",
        "fusion_table_race": "fusion_table_race_font8",
        "fusion_table_demon": "fusion_table_demon_font8",
        "fusion_demon_name": "fusion_demon_name_vwf",
        "fusion_preview_demon": "fusion_demon_preview_vwf",
        "fusion_character_name": "fusion_character_name_vwf",
        "fusion_word_font8_glyph": "fusion_word_font8_glyph",
        "fusion_guide_mixed_glyph": "fusion_guide_mixed_glyph",
    }
    addresses.update(
        {name: drawer_labels[label] for name, label in label_names.items()}
    )
    addresses["name_drawers"] = drawer_address
    payload.extend(drawer)

    _align(payload, 4)
    confirmation_address = CAVE_ADDRESS + len(payload)
    confirmation, confirmation_labels = _assembled(
        CONFIRMATION_DRAWER_SOURCE,
        confirmation_address,
        {
            "WORD_TERMINATOR": WORD_TERMINATOR,
            "FONT16_SPACE": FONT16_SPACE,
            "WIDTHS": 0x0021A000 + shared_font16_layout(FONT16_METRICS_PATH)[1],
            "STOCK_GLYPH": 0x06051188,
        },
    )
    addresses["confirmation_drawer"] = confirmation_labels[
        "fusion_confirmation_vwf"
    ]
    addresses["confirmation_drawer_code"] = confirmation_address
    payload.extend(confirmation)
    if CAVE_ADDRESS + len(payload) > CAVE_END:
        raise ValueError(
            "fusion runtime exceeds its cave by "
            f"{CAVE_ADDRESS + len(payload) - CAVE_END} bytes"
        )
    return bytes(payload), addresses, (
        BINDING_ROOT / "demons.json",
        BINDING_ROOT / "characters.json",
        BINDING_ROOT / "races.json",
        BINDING_ROOT / "facilities_gouma_den.json",
        TEXT_ROOT.parent.parent / "assets" / "text" / "demons.json",
        TEXT_ROOT.parent.parent / "assets" / "text" / "characters.json",
        TEXT_ROOT.parent.parent / "assets" / "text" / "races.json",
        TEXT_ROOT.parent.parent / "assets" / "text" / "facilities" / "gouma_den.json",
    )


def _only_source(recipe: PatchRecipe, expected: str) -> Path:
    sources = recipe.replacement.sources
    if (
        len(sources) != 1
        or sources[0].relative_to(ASSEMBLY_ROOT).as_posix() != expected
    ):
        raise ValueError(f"{recipe.group}/{recipe.name}: assembly source changed")
    return sources[0]


def _confirmation_payloads(font16: FontMetrics) -> dict[str, bytes]:
    binding = load_binding(BINDING_ROOT / "facilities_gouma_den.json")
    catalog = load_asset(binding.asset)

    def field(name: str) -> bytes:
        physical_id = {
            "confirm_prompt": "game.fusion_confirmation_static.o05458e",
            "level_too_low": "game.fusion_confirmation_static.o0545b6",
            "duplicate_demon": "game.fusion_confirmation_static.o0545de",
            "begin_fusion": "game.fusion_confirmation_static.o054606",
            "label_yes": "game.fusion_confirmation_static.o05462e",
            "label_no": "game.fusion_confirmation_static.o054636",
        }[name]
        text = catalog.field(binding.records[physical_id]).translation
        words = font16.encode(text, dictionary=None)
        capacity = CONFIRMATION_WORDS[name]
        if len(words) + 1 > capacity:
            raise ValueError(f"fusion confirmation {name} exceeds {capacity} words")
        words.append(WORD_TERMINATOR)
        words.extend([0] * (capacity - len(words)))
        return struct.pack(f">{capacity}H", *words)

    confirm = field("confirm_prompt")
    level = field("level_too_low")
    duplicate = field("duplicate_demon")
    begin = field("begin_fusion")
    label_yes = field("label_yes")
    label_no = field("label_no")
    table_address = LOAD_ADDRESS + MAIN_FILE + POINTER_TABLE_OFFSET
    pointers = (
        table_address + 16,
        CAVE_END,
        table_address + 16 + len(confirm),
        table_address + 16 + len(confirm) + len(duplicate),
    )
    main = bytearray(POINTER_TABLE_OFFSET)
    main.extend(struct.pack(">4I", *pointers))
    main.extend(confirm)
    main.extend(duplicate)
    main.extend(begin)
    if len(main) > MAIN_SIZE or CAVE_END + len(level) != PACKED_FETCH_ADDRESS:
        raise ValueError("fusion confirmation storage no longer fits its regions")
    main.extend(bytes(MAIN_SIZE - len(main)))
    return {
        "confirmation_main": bytes(main),
        "confirmation_level_too_low": level,
        "confirmation_label_yes": label_yes,
        "confirmation_label_no": label_no,
    }


def _instruction(recipe: PatchRecipe) -> bytes:
    instruction = recipe.replacement.instruction
    assert instruction is not None
    try:
        result = assemble(instruction, recipe.address)
    except AssemblyError as error:
        raise ValueError(f"{recipe.group}/{recipe.name}: {error}") from error
    if result.warnings or len(result.data) != len(recipe.expected):
        raise ValueError(f"{recipe.group}/{recipe.name}: invalid instruction")
    return result.data


def _assembly_patch(
    recipe: PatchRecipe,
    addresses: dict[str, int],
    runtime: bytes,
) -> bytes:
    if recipe.name == "runtime_cave":
        sources = {
            path.relative_to(ASSEMBLY_ROOT).as_posix()
            for path in recipe.replacement.sources
        }
        if sources != {
            "font16_surface_blitter.s",
            "fusion/font8_surface_blitter.s",
            "fusion/name_drawers.s",
            "fusion/confirmation_drawer.s",
        }:
            raise ValueError("Fusion runtime assembly inventory changed")
        if len(runtime) > len(recipe.expected):
            raise ValueError("fusion runtime exceeds its configured cave")
        return runtime.ljust(len(recipe.expected), b"\0")

    if recipe.name == "english_name_sort":
        source = _only_source(recipe, "fusion/name_sort.s")
        if _sha256(recipe.expected) != NAME_SORT_STOCK_SHA256:
            raise ValueError("fusion English-sort stock guard changed")
        sorter, _labels = _assembled(
            source,
            recipe.address,
            {
                "DVL_OFFSETS": addresses["demon_offsets"],
                "ROSTER_COUNT": 0x060768A8,
                "ROSTER_IDS_PTR": 0x06068E78,
                "ROSTER_AUX0_PTR": 0x06068E7C,
                "ROSTER_AUX1_PTR": 0x06068E80,
            },
        )
        if len(sorter) > len(recipe.expected):
            raise ValueError("fusion English-sort assembly exceeds its stock region")
        return sorter.ljust(len(recipe.expected), b"\0")

    if recipe.name == "pointer_lookup":
        source = _only_source(recipe, "fusion/confirmation_pointer_lookup.s")
        symbols = {
            "DESTINATION_LITERAL": 0x06057914,
            "TABLE_LITERAL": 0x06057918,
            "POINTER_TABLE_OFFSET": POINTER_TABLE_OFFSET,
        }
        replacement, _labels = _assembled(source, recipe.address, symbols)
        stock, _stock_labels = _assembled(
            CONFIRMATION_LOOKUP_STOCK_SOURCE,
            recipe.address,
            {
                "DESTINATION_LITERAL": 0x06057914,
                "TABLE_LITERAL": 0x06057918,
            },
        )
        if stock != recipe.expected:
            raise ValueError("fusion confirmation stock assembly disagrees with config")
        return replacement

    raise ValueError(f"unsupported Fusion assembly patch {recipe.name}")


def _bind_patches(
    config: PatchRecipeConfiguration,
    runtime: bytes,
    addresses: dict[str, int],
) -> tuple[Patch, ...]:
    generated = _confirmation_payloads(FontMetrics.load(FONT16_METRICS_PATH))
    patches: list[Patch] = []
    assembly_seen: set[str] = set()
    generated_seen: set[str] = set()
    for recipe in config.patches[TARGET]:
        replacement_recipe = recipe.replacement
        if replacement_recipe.kind == "assembly":
            assembly_seen.add(recipe.name)
            replacement = _assembly_patch(recipe, addresses, runtime)
        elif replacement_recipe.kind == "generated":
            generator = replacement_recipe.generator
            if generator is None or generator not in generated:
                raise ValueError(
                    f"{recipe.group}/{recipe.name}: unknown generator {generator!r}"
                )
            generated_seen.add(generator)
            replacement = generated[generator]
        elif replacement_recipe.kind == "pointer":
            assert replacement_recipe.pointer is not None
            replacement = struct.pack(">I", replacement_recipe.pointer)
        elif replacement_recipe.kind == "linked_pointer":
            link = replacement_recipe.link
            if link is None or link not in addresses:
                raise ValueError(
                    f"{recipe.group}/{recipe.name}: unresolved Fusion link {link!r}"
                )
            replacement = struct.pack(">I", addresses[link])
        elif replacement_recipe.kind == "instruction":
            replacement = _instruction(recipe)
        else:
            raise ValueError(
                f"{recipe.group}/{recipe.name}: unsupported replacement recipe"
            )
        if len(replacement) != len(recipe.expected):
            raise ValueError(
                f"{recipe.group}/{recipe.name}: replacement owns "
                f"{len(replacement)} bytes, expected {len(recipe.expected)}"
            )
        patches.append(
            Patch(
                recipe.group,
                recipe.name,
                recipe.address,
                recipe.expected,
                replacement,
            )
        )
    if assembly_seen != {"runtime_cave", "english_name_sort", "pointer_lookup"}:
        raise ValueError("Fusion assembly patch inventory changed")
    if generated_seen != set(generated):
        raise ValueError("Fusion generated-data patch inventory changed")
    return tuple(patches)


def build_fusion_menu(original: bytes, event_patched: bytes) -> FusionBuild:
    """Compose every Fusion consumer onto the already-built EVENT runtime."""
    _validate_surfaces()
    config = load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="fusion.menu",
        target_names={TARGET},
        input_names={
            "font16_metrics_sha256",
            "font12_metrics_sha256",
            "font8_metrics_sha256",
        },
    )
    actual_inputs = {
        "font16_metrics_sha256": _file_sha256(FONT16_METRICS_PATH),
        "font12_metrics_sha256": _file_sha256(FONT12_METRICS_PATH),
        "font8_metrics_sha256": _file_sha256(FONT8_METRICS_PATH),
    }
    for name, actual in actual_inputs.items():
        if config.inputs[name] != actual:
            raise ValueError(
                f"Fusion patch input {name} is {actual}, "
                f"expected {config.inputs[name]}"
            )
    contract = config.targets[TARGET]
    if (
        len(original) != contract.size
        or _sha256(original) != contract.stock_sha256
        or len(event_patched) != contract.size
    ):
        raise ValueError("Fusion EVENT inputs do not match the configured target")
    runtime, addresses, asset_files = _runtime_payload()
    patches = _bind_patches(config, runtime, addresses)
    assembly_files = set(ASSEMBLY_FILES)
    assembly_files.update(
        source
        for recipe in config.patches[TARGET]
        for source in recipe.replacement.sources
    )
    return FusionBuild(
        apply_patches(event_patched, contract.load_address, patches),
        runtime,
        addresses,
        patches,
        asset_files,
        tuple(sorted(assembly_files)),
    )
