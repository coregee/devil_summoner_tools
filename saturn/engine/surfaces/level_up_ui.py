"""Compose LEVEL_UP's translated panel and learned-magic window."""

from __future__ import annotations

import hashlib
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from engine.core.patch_recipes import (
    PatchRecipe,
    PatchRecipeConfiguration,
    load_patch_recipe_configuration,
    resolve_recipe_expected,
)
from engine.core.patching import Patch, apply_patches
from engine.core.sh2 import AssemblyError, assemble_file
from engine.shared.font8 import font8_tables
from engine.surfaces.status_ui import (
    NODE_BITMAP_OFFSET as STATUS_NODE_BITMAP_OFFSET,
    SIMPLE_TEMPLATE_GRAMMAR,
    StatusTemplates,
    _compile_status_templates,
    _derived_rows,
    _direct_color_node,
    _direct_color_row,
    _font16_metrics,
    _node_background,
    _status_labels,
    _stock_latin_codes,
    _validate_shiftable_bitmap,
)
from rom.util.catalog import load_catalog, validate_source
from rom.util.workflows import read_source_files
from text.util.assets import (
    ASSET_ROOT,
    BINDING_ROOT,
    CORPUS_ROOT,
    load_asset,
    load_bound_translations,
    load_physical_record_files,
)
from text.util.event_repack import FontMetrics
from text.util.glyph_sets import load_glyph_sets
from text.util.surfaces import load_surfaces


ENGINE_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = ENGINE_ROOT.parent
PROJECT_ROOT = SATURN_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "level_up_ui.json"
FONT_ROOT = SATURN_ROOT / "font" / "generated" / "game"
FONT8_PATH = FONT_ROOT / "FONT8.FON"
FONT8_METRICS_PATH = FONT_ROOT / "FONT8_metrics.json"
FONT16_PATH = FONT_ROOT / "FONT16.FON"
FONT16_METRICS_PATH = FONT_ROOT / "FONT16_metrics.json"
TEXT_GENERATED_ROOT = SATURN_ROOT / "text" / "generated" / "game"
MAGNAME_PATH = TEXT_GENERATED_ROOT / "MAGNAME.DAT"
BATTLE_UI_BUILD_PATH = TEXT_GENERATED_ROOT / "battle_ui_build.json"

LEVEL_UP_ASSET_PATH = ASSET_ROOT / "ui" / "level_up.json"
STATUS_ASSET_PATH = ASSET_ROOT / "ui" / "status.json"
CHARACTER_ASSET_PATH = ASSET_ROOT / "characters.json"
MAGIC_ASSET_PATH = ASSET_ROOT / "magic.json"
SKILL_ASSET_PATH = ASSET_ROOT / "skills.json"
ASSET_FILES = (
    LEVEL_UP_ASSET_PATH,
    STATUS_ASSET_PATH,
    CHARACTER_ASSET_PATH,
    MAGIC_ASSET_PATH,
    SKILL_ASSET_PATH,
)

LEVEL_UP_BINDING_PATH = BINDING_ROOT / "level_up.json"
LEVEL_UP_STATUS_BINDING_PATH = BINDING_ROOT / "level_up_status.json"
CHARACTER_BINDING_PATH = BINDING_ROOT / "characters.json"
MAGIC_BINDING_PATH = BINDING_ROOT / "magic.json"
SKILL_BINDING_PATH = BINDING_ROOT / "skills.json"
BINDING_FILES = (
    LEVEL_UP_BINDING_PATH,
    LEVEL_UP_STATUS_BINDING_PATH,
    CHARACTER_BINDING_PATH,
    MAGIC_BINDING_PATH,
    SKILL_BINDING_PATH,
)

LEVEL_UP_CORPUS_PATH = (
    CORPUS_ROOT / "game" / "addressed" / "level_up_system.json"
)
CHARACTER_CORPUS_PATH = CORPUS_ROOT / "game" / "fixed" / "charname.json"
MAGNAME_CORPUS_PATH = CORPUS_ROOT / "game" / "fixed" / "magname.json"
BTL_MES_CORPUS_PATH = CORPUS_ROOT / "game" / "pointer" / "btl_mes.json"
ABILITY_CORPUS_PATH = (
    CORPUS_ROOT / "compendium" / "fixed" / "ability_names.json"
)
CORPUS_FILES = (
    LEVEL_UP_CORPUS_PATH,
    CHARACTER_CORPUS_PATH,
    MAGNAME_CORPUS_PATH,
    BTL_MES_CORPUS_PATH,
    ABILITY_CORPUS_PATH,
)
RUNTIME_INPUT_FILES = (
    FONT8_PATH,
    FONT8_METRICS_PATH,
    FONT16_PATH,
    FONT16_METRICS_PATH,
    MAGNAME_PATH,
    BATTLE_UI_BUILD_PATH,
    SATURN_ROOT / "text" / "config" / "surfaces.json",
    SATURN_ROOT / "text" / "config" / "glyph_sets.json",
    SATURN_ROOT / "rom" / "discs.json",
    *BINDING_FILES,
    *CORPUS_FILES,
)

TARGET = "LEVEL_UP.BIN"
LOAD_ADDRESS = 0x06020000
TARGET_SIZE = 235_304
RUNTIME_CAVE = 0x06022000
RUNTIME_DATA = 0x06022200
RUNTIME_LIMIT = 0x06022500
RUNTIME_CAPACITY = RUNTIME_LIMIT - RUNTIME_CAVE

FONT16_BITMAP = 0x0021A000
FONT16_DRAWER = 0x06029C8C
NAME_PREPARE = 0x0602A05C
NAME_SURFACE = 0x06059580
CHARACTER_SELECTOR = 0x06059878
PLAYER_NAME = 0x0023FE14
LEARNED_LIST_POINTER = 0x060598AC
MAGNAME_BASE = 0x0022F7A0
MAGNAME_POINTER_OFFSET = 0x5E
MAGNAME_POINTER_FROM_NAME = 0x5A

CHARACTER_COUNT = 5
MAGNAME_COUNT = 255
MAGNAME_RECORD_SIZE = 0x60
MAGNAME_SIZE = MAGNAME_COUNT * MAGNAME_RECORD_SIZE
MAX_ABILITY_NAME_BYTES = 32
MAX_ABILITY_FONT8_PIXELS = 80
MAX_ABILITY_FONT16_PIXELS = 128
SCRATCH_BYTES = (MAX_ABILITY_NAME_BYTES + 1) * 2
LEARNED_HEADING_MAX_WORDS = 18

NODE_BITMAP_OFFSET = 0xC750
NODE_BITMAP_SIZE = 16 * 16 * 2

STATUS_IDS = MappingProxyType(
    {
        "level": "game.level_up_system.o0079a4",
        "hit_points": "game.level_up_system.o0079a8",
        "magic_points": "game.level_up_system.o0079ac",
        "experience": "game.level_up_system.o0079b0",
        "next_experience": "game.level_up_system.o0079b4",
    }
)
DIRECT_IDS = MappingProxyType(
    {
        "title": "game.level_up_system.o008478",
        "remaining_points": "game.level_up_system.o008488",
        "confirm_yes": "game.level_up_system.o008e1c",
        "confirm_no": "game.level_up_system.o008e21",
        "accept": "game.level_up_system.o008e24",
        "learned_magic_heading": "game.level_up_system.o008f2c",
    }
)
REQUIRED_LEVEL_UP_IDS = frozenset((*STATUS_IDS.values(), *DIRECT_IDS.values()))
_REMAINING_TEMPLATE = re.compile(r"^\{remaining_points\} ([^{}]+)$")


@dataclass(frozen=True, slots=True)
class LevelUpTerms:
    templates: StatusTemplates
    title: str
    remaining_points_suffix: str
    confirm_yes: str
    confirm_no: str
    accept: str
    learned_magic_heading: str
    max_level_next_reference: str
    max_level_next: str
    no_magic_points_reference: str
    no_magic_points: str


@dataclass(frozen=True, slots=True)
class RuntimeBuild:
    data: bytes
    links: Mapping[str, int]
    used_size: int


@dataclass(frozen=True, slots=True)
class LevelUpUiBuild:
    data: bytes
    patches: tuple[Patch, ...]
    asset_files: tuple[Path, ...]
    assembly_files: tuple[Path, ...]
    runtime_input_files: tuple[Path, ...]
    source_inputs: Mapping[str, str]
    runtime_used_size: int


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        return _sha256(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"missing Level Up UI input: {path}") from error


def _source_assets() -> tuple[bytes, bytes]:
    catalog = load_catalog()
    try:
        game = catalog["game"]
    except KeyError as error:
        raise ValueError("disc catalog has no game source") from error
    source = read_source_files(
        validate_source(game, verify_hashes=False),
        (TARGET, "FONT16.FON"),
    )
    return source[TARGET], source["FONT16.FON"]


def _configuration() -> PatchRecipeConfiguration:
    return load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="level_up.ui",
        target_names={TARGET},
        input_names={
            "font8_sha256",
            "font8_metrics_sha256",
            "font16_sha256",
            "font16_metrics_sha256",
            "stock_font16_sha256",
        },
    )


def _manifest() -> Mapping[str, object]:
    try:
        document = json.loads(BATTLE_UI_BUILD_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(
            f"missing generated battle UI manifest: {BATTLE_UI_BUILD_PATH}"
        ) from error
    except json.JSONDecodeError as error:
        raise ValueError("generated battle UI manifest is invalid JSON") from error
    if not isinstance(document, dict):
        raise ValueError("generated battle UI manifest must be an object")
    return document


def _validate_generated_magname(manifest: Mapping[str, object]) -> bytes:
    if manifest.get("version") != 1 or manifest.get("surface") != "battle.ui":
        raise ValueError("MAGNAME needs the version-1 battle.ui text build")
    metrics = {
        "font8_metrics_sha256": _file_sha256(FONT8_METRICS_PATH),
        "font16_metrics_sha256": _file_sha256(FONT16_METRICS_PATH),
    }
    for name, actual in metrics.items():
        if manifest.get(name) != actual:
            raise ValueError(
                f"MAGNAME manifest {name} does not match the current generated font"
            )
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        raise ValueError("MAGNAME manifest has no output inventory")
    record = outputs.get("MAGNAME.DAT")
    if not isinstance(record, dict):
        raise ValueError("MAGNAME manifest has no MAGNAME.DAT record")
    if record.get("records") != MAGNAME_COUNT or record.get(
        "translated_names"
    ) != MAGNAME_COUNT:
        raise ValueError("MAGNAME manifest does not contain 255 translated names")
    packed = MAGNAME_PATH.read_bytes()
    if len(packed) != MAGNAME_SIZE:
        raise ValueError(
            f"generated MAGNAME has {len(packed):#x} bytes; expected {MAGNAME_SIZE:#x}"
        )
    if record.get("sha256") != _sha256(packed):
        raise ValueError("MAGNAME manifest output SHA-256 is stale")
    return packed


def _validate_inputs(
    config: PatchRecipeConfiguration,
    base: bytes,
    stock_font16: bytes,
) -> bytes:
    target = config.targets[TARGET]
    if (
        target.load_address != LOAD_ADDRESS
        or target.size != TARGET_SIZE
        or len(base) != TARGET_SIZE
    ):
        raise ValueError("Level Up UI target geometry changed")
    if _sha256(base) != target.stock_sha256:
        raise ValueError("Level Up UI requires the configured stock LEVEL_UP.BIN")
    actual = {
        "font8_sha256": _file_sha256(FONT8_PATH),
        "font8_metrics_sha256": _file_sha256(FONT8_METRICS_PATH),
        "font16_sha256": _file_sha256(FONT16_PATH),
        "font16_metrics_sha256": _file_sha256(FONT16_METRICS_PATH),
        "stock_font16_sha256": _sha256(stock_font16),
    }
    for name, expected in config.inputs.items():
        if actual[name] != expected:
            raise ValueError(
                f"Level Up UI {name} expected SHA-256 {expected}, "
                f"found {actual[name]}"
            )
    if base[RUNTIME_CAVE - LOAD_ADDRESS : RUNTIME_LIMIT - LOAD_ADDRESS] != bytes(
        RUNTIME_CAPACITY
    ):
        raise ValueError("Level Up runtime cave is not exactly 0x500 stock-zero bytes")
    return _validate_generated_magname(_manifest())


def _physical_records() -> Mapping[str, str]:
    return load_physical_record_files(CORPUS_FILES)


def _level_up_terms(physical: Mapping[str, str]) -> LevelUpTerms:
    bound = load_bound_translations(
        ("game.level_up_system.",),
        required_ids=set(REQUIRED_LEVEL_UP_IDS),
        binding_paths=(LEVEL_UP_BINDING_PATH, LEVEL_UP_STATUS_BINDING_PATH),
        physical_records=physical,
    )
    status = load_asset("ui/status.json")
    status_names = set(SIMPLE_TEMPLATE_GRAMMAR) | {"hit_points", "magic_points"}
    status_values = {
        name: status.field(f"{name}.text").resolve()[1]
        for name in status_names
    }
    for name, physical_id in STATUS_IDS.items():
        status_values[name] = bound[physical_id]
    templates = _compile_status_templates(status_values)

    remaining = bound[DIRECT_IDS["remaining_points"]]
    match = _REMAINING_TEMPLATE.fullmatch(remaining)
    if match is None or match.group(1) != match.group(1).strip():
        raise ValueError(
            "level_up.remaining_points must use "
            "'{remaining_points} SUFFIX' with one layout space"
        )
    level_up = load_asset("ui/level_up.json")
    max_reference, max_translation, _reviewed = level_up.field(
        "max_level_next.text"
    ).resolve()
    no_mp_reference, no_mp_translation, _reviewed = level_up.field(
        "no_magic_points.text"
    ).resolve()
    return LevelUpTerms(
        templates,
        bound[DIRECT_IDS["title"]],
        match.group(1),
        bound[DIRECT_IDS["confirm_yes"]],
        bound[DIRECT_IDS["confirm_no"]],
        bound[DIRECT_IDS["accept"]],
        bound[DIRECT_IDS["learned_magic_heading"]],
        max_reference,
        max_translation,
        no_mp_reference,
        no_mp_translation,
    )


def _character_names(physical: Mapping[str, str]) -> tuple[str, ...]:
    # Selector zero and selectors above five use the live codename. Only the
    # five fixed selector rows belong in this runtime table.
    ids = tuple(
        f"game.charname.o{index * 8:06x}.text"
        for index in range(1, CHARACTER_COUNT + 1)
    )
    bound = load_bound_translations(
        ("game.charname.",),
        required_ids=set(ids),
        binding_paths=(CHARACTER_BINDING_PATH,),
        physical_records=physical,
    )
    return tuple(bound[physical_id] for physical_id in ids)


def _ability_names(physical: Mapping[str, str]) -> tuple[str, ...]:
    ids = tuple(
        f"game.magname.o{index * MAGNAME_RECORD_SIZE + 4:06x}.name"
        for index in range(MAGNAME_COUNT)
    )
    bound = load_bound_translations(
        ("game.magname.",),
        required_ids=set(ids),
        binding_paths=(MAGIC_BINDING_PATH, SKILL_BINDING_PATH),
        physical_records=physical,
    )
    return tuple(bound[physical_id] for physical_id in ids)


def _font8_to_font16(code: int) -> int | None:
    if code == 63:
        return 267
    if 63 < code < 118:
        return code - 63
    if 205 <= code < 213:
        return code - 150
    return {213: 173, 214: 175, 217: 177, 229: 204}.get(code)


def _validate_ability_names(
    packed: bytes,
    names: tuple[str, ...],
    metrics8: FontMetrics,
    metrics16: FontMetrics,
) -> None:
    if len(names) != MAGNAME_COUNT:
        raise ValueError("Level Up learned-magic table needs exactly 255 names")
    if len(packed) != MAGNAME_SIZE:
        raise ValueError("Level Up learned-magic MAGNAME geometry changed")
    for index, name in enumerate(names):
        if not name or name != name.strip():
            raise ValueError(f"Level Up MAGNAME row {index} is empty or padded")
        try:
            glyphs8 = metrics8.segment(name)
            glyphs16 = metrics16.segment(name)
        except ValueError as error:
            raise ValueError(
                f"Level Up MAGNAME row {index} uses unsupported text: {name!r}"
            ) from error
        codes8 = tuple(glyph.code for glyph in glyphs8)
        codes16 = tuple(glyph.code for glyph in glyphs16)
        if len(codes8) > MAX_ABILITY_NAME_BYTES:
            raise ValueError(
                f"Level Up MAGNAME row {index} exceeds "
                f"{MAX_ABILITY_NAME_BYTES} bytes"
            )
        if sum(glyph.advance for glyph in glyphs8) > MAX_ABILITY_FONT8_PIXELS:
            raise ValueError(
                f"Level Up MAGNAME row {index} exceeds "
                f"{MAX_ABILITY_FONT8_PIXELS} FONT8 pixels"
            )
        if sum(glyph.advance for glyph in glyphs16) > MAX_ABILITY_FONT16_PIXELS:
            raise ValueError(
                f"Level Up MAGNAME row {index} exceeds "
                f"{MAX_ABILITY_FONT16_PIXELS} FONT16 pixels"
            )
        mapped = tuple(_font8_to_font16(code) for code in codes8)
        if None in mapped or mapped != codes16:
            raise ValueError(f"Level Up MAGNAME row {index} cannot map FONT8 to FONT16")
        pointer = struct.unpack_from(
            ">H", packed, index * MAGNAME_RECORD_SIZE + MAGNAME_POINTER_OFFSET
        )[0]
        expected = bytes(codes8) + b"\xff"
        if packed[pointer : pointer + len(expected)] != expected:
            raise ValueError(f"Level Up MAGNAME row {index} full-name payload is stale")


def _validate_surfaces() -> None:
    surfaces = load_surfaces()
    expected = {
        "level_up.character_name": ("font16", 1, "pixels", 96),
        "level_up.live_codename": ("font16", 1, "pixels", 128),
        "level_up.title": ("font8", 1, "glyph_cells", 8),
        "level_up.numeric_readout": ("font8", 1, None, None),
        "level_up.max_level_next": ("font8", 1, "glyph_cells", 7),
        "level_up.no_magic_points": ("font8", 1, "glyph_cells", 8),
        "level_up.remaining_points": ("font8", 1, "glyph_cells", 17),
        "level_up.accept_action": ("font8", 1, "glyph_cells", 2),
        "level_up.confirm_choice": ("font8", 1, "glyph_cells", 3),
        "level_up.ability_name": ("font16", 1, "pixels", 128),
        "level_up.learned_heading": ("font16", 1, "pixels", 128),
        "level_up.base_stat_label": ("font8", 1, "pixels", 12),
        "level_up.derived_stat_label": ("font8", 1, "pixels", 46),
        "level_up.generic_combat_stat_label": ("font8", 1, "pixels", 46),
    }
    for name, geometry in expected.items():
        layout = surfaces.surface(name).en
        actual = (layout.font, layout.rows, layout.width.unit, layout.width.value)
        if actual != geometry:
            raise ValueError(f"{name} geometry changed")

    glyph_sets = load_glyph_sets()
    for name in (
        "level_up.numeric_readout",
        "level_up.max_level_next",
        "level_up.no_magic_points",
        "level_up.title",
        "level_up.remaining_points",
        "level_up.accept_action",
        "level_up.confirm_choice",
    ):
        handler = glyph_sets.for_surface(name)
        if (
            handler is None
            or handler.name != "font8_stock_latin"
            or handler.font != "font8"
            or handler.reference_set != "stock_latin"
        ):
            raise ValueError(f"{name} lost its preserved stock-Latin handler")


def _ascii_record(
    text: str,
    capacity: int,
    maximum: int,
    context: str,
    stock_codes: Mapping[str, int],
) -> bytes:
    if not text or len(text) > maximum:
        raise ValueError(f"{context} must contain one to {maximum} cells")
    unsupported = next((character for character in text if character not in stock_codes), None)
    if unsupported is not None:
        raise ValueError(f"{context} uses unsupported stock-Latin cell {unsupported!r}")
    try:
        encoded = text.encode("ascii")
    except UnicodeEncodeError as error:
        raise ValueError(f"{context} must use ASCII-backed stock-Latin cells") from error
    if len(encoded) + 1 > capacity:
        raise ValueError(f"{context} exceeds its {capacity}-byte record")
    return (encoded + b"\0").ljust(capacity, b"\0")


def _fixed_data(terms: LevelUpTerms) -> dict[str, bytes]:
    stock_codes = _stock_latin_codes()
    prefixes = terms.templates.prefixes
    generated = {
        "level_prefix": _ascii_record(prefixes["level"], 4, 3, "status.level", stock_codes),
        "hit_points_prefix": _ascii_record(
            prefixes["hit_points"], 4, 3, "status.hit_points", stock_codes
        ),
        "magic_points_prefix": _ascii_record(
            prefixes["magic_points"], 4, 3, "status.magic_points", stock_codes
        ),
        "experience_prefix": _ascii_record(
            prefixes["experience"], 4, 3, "status.experience", stock_codes
        ),
        "next_experience_prefix": _ascii_record(
            prefixes["next_experience"],
            6,
            4,
            "status.next_experience",
            stock_codes,
        ),
        "title": _ascii_record(terms.title, 12, 8, "level_up.title", stock_codes),
        "remaining_points_suffix": _ascii_record(
            terms.remaining_points_suffix,
            6,
            4,
            "level_up.remaining_points suffix",
            stock_codes,
        ),
        "confirm_yes": _ascii_record(
            terms.confirm_yes, 4, 3, "level_up.confirm_yes", stock_codes
        ),
        "accept": _ascii_record(terms.accept, 4, 2, "level_up.accept", stock_codes),
    }
    no_record = _ascii_record(
        terms.confirm_no, 4, 3, "level_up.confirm_no", stock_codes
    )
    no = no_record[: len(terms.confirm_no)]
    remaining = 3 - len(no)
    left = (remaining + 1) // 2
    generated["confirm_no"] = (
        b" " * left + no + b" " * (remaining - left) + b"\0"
    )
    try:
        separator = stock_codes[terms.templates.hp_mp_separator]
    except KeyError as error:
        raise ValueError(
            "status HP/MP separator must use a preserved stock-Latin cell"
        ) from error
    generated["hp_mp_separator"] = struct.pack(">H", separator)
    return generated


def _layout_data(
    base: bytes,
    stock_font16: bytes,
    metrics8: FontMetrics,
    terms: LevelUpTerms,
) -> dict[str, bytes]:
    font8 = FONT8_PATH.read_bytes()
    widths8, codes8 = font8_tables(metrics8)
    if len(font8) != 256 * 8:
        raise ValueError("Level Up FONT8 bitmap geometry changed")
    labels = _status_labels(terms.templates)
    cell = base[NODE_BITMAP_OFFSET : NODE_BITMAP_OFFSET + NODE_BITMAP_SIZE]
    if len(cell) != NODE_BITMAP_SIZE:
        raise ValueError("LEVEL_UP status-node bitmap is truncated")
    # Reuse the status package's pure reconstruction routine without pretending
    # LEVEL_UP has NORMCOM's file layout.
    proxy = bytearray(STATUS_NODE_BITMAP_OFFSET + NODE_BITMAP_SIZE)
    proxy[STATUS_NODE_BITMAP_OFFSET:] = cell
    background = _node_background(bytes(proxy), stock_font16)
    return {
        "parameter_nodes": b"".join(
            _direct_color_node(label, font8, widths8, codes8, background)
            for label in labels.base
        ),
        "parameter_rows": b"".join(
            _direct_color_row(" ".join(row), font8, widths8, codes8)
            for row in _derived_rows(labels)
        ),
        "generic_attack_label": _direct_color_row(
            labels.attack, font8, widths8, codes8
        ),
        "generic_accuracy_label": _direct_color_row(
            labels.accuracy, font8, widths8, codes8
        ),
    }


def _assembled(source: Path, address: int, symbols: Mapping[str, int]) -> bytes:
    try:
        assembly = assemble_file(source, address, dict(symbols))
    except AssemblyError as error:
        raise ValueError(f"Level Up assembly failed for {source.name}: {error}") from error
    if assembly.warnings:
        raise ValueError(
            f"Level Up assembly warnings for {source.name}: "
            + "; ".join(assembly.warnings)
        )
    return assembly.data


def _recipe_sources(
    recipe: PatchRecipe,
    expected: tuple[str, ...],
) -> tuple[Path, ...]:
    actual = tuple(
        path.relative_to(ENGINE_ROOT / "asm").as_posix()
        for path in recipe.replacement.sources
    )
    if actual != expected:
        raise ValueError(
            f"{recipe.name} assembly sources changed: {actual!r}, expected {expected!r}"
        )
    return recipe.replacement.sources


def _runtime_payload(
    recipe: PatchRecipe,
    terms: LevelUpTerms,
    character_names: tuple[str, ...],
    ability_names: tuple[str, ...],
    packed_magname: bytes,
) -> RuntimeBuild:
    if recipe.address != RUNTIME_CAVE or len(recipe.expected) != RUNTIME_CAPACITY:
        raise ValueError("Level Up runtime recipe no longer owns the exact 0x500 cave")
    sources = _recipe_sources(
        recipe,
        (
            "level_up_ui/font16_vwf.s",
            "level_up_ui/name_drawer.s",
            "level_up_ui/learned_dispatcher.s",
            "level_up_ui/learned_prepare.s",
        ),
    )
    metrics8 = FontMetrics.load(FONT8_METRICS_PATH)
    metrics16 = FontMetrics.load(FONT16_METRICS_PATH)
    widths16, _codes16 = _font16_metrics()
    font16 = FONT16_PATH.read_bytes()
    if len(font16) != 1872 * 32 or len(widths16) != 268:
        raise ValueError("Level Up FONT16 geometry changed")
    _validate_shiftable_bitmap(
        font16, widths16, 32, 2, "Level Up status FONT16"
    )
    _validate_ability_names(packed_magname, ability_names, metrics8, metrics16)

    font16_vwf = _assembled(
        sources[0],
        RUNTIME_CAVE,
        {
            "WIDTHS": RUNTIME_DATA,
            "END_MASK": 0x8000,
            "FONT_BITMAP": FONT16_BITMAP,
            "STOCK": FONT16_DRAWER,
        },
    )
    wrapper_address = RUNTIME_CAVE + len(font16_vwf)
    wrapper_symbols = {
        "PLAYER_NAME": PLAYER_NAME,
        "CHARACTER_SELECTOR": CHARACTER_SELECTOR,
        "CHARACTER_COUNT": CHARACTER_COUNT,
        "CHARACTER_TABLE": RUNTIME_CAVE,
        "PREPARE": NAME_PREPARE,
        "SURFACE": NAME_SURFACE,
        "FONT16_VWF": RUNTIME_CAVE,
    }
    wrapper_probe = _assembled(sources[1], wrapper_address, wrapper_symbols)
    if wrapper_address + len(wrapper_probe) > RUNTIME_DATA:
        raise ValueError("Level Up code overlaps its fixed width table")

    try:
        heading_glyphs = metrics16.segment(terms.learned_magic_heading)
    except ValueError as error:
        raise ValueError("Level Up learned heading uses unsupported FONT16 text") from error
    heading_words = tuple(glyph.code for glyph in heading_glyphs) + (0x8000,)
    if (
        len(heading_words) > LEARNED_HEADING_MAX_WORDS
        or sum(glyph.advance for glyph in heading_glyphs) > 128
    ):
        raise ValueError("Level Up learned heading exceeds its 128px surface")
    heading_address = RUNTIME_DATA + len(widths16)
    character_table_address = (
        heading_address + len(heading_words) * 2 + 3
    ) & ~3
    wrapper_symbols["CHARACTER_TABLE"] = character_table_address
    wrapper = _assembled(sources[1], wrapper_address, wrapper_symbols)
    if len(wrapper) != len(wrapper_probe):
        raise ValueError("Level Up character table changed wrapper code size")

    payload = bytearray(font16_vwf)
    payload.extend(wrapper)
    payload.extend(bytes(RUNTIME_DATA - (RUNTIME_CAVE + len(payload))))
    payload.extend(widths16)
    if RUNTIME_CAVE + len(payload) != heading_address:
        raise ValueError("Level Up learned heading address drifted")
    payload.extend(struct.pack(f">{len(heading_words)}H", *heading_words))
    payload.extend(
        bytes(character_table_address - (RUNTIME_CAVE + len(payload)))
    )
    table_offset = len(payload)
    payload.extend(bytes(CHARACTER_COUNT * 4))
    if len(character_names) != CHARACTER_COUNT:
        raise ValueError("Level Up needs five fixed character-name rows")
    for index, name in enumerate(character_names):
        if not name or name != name.strip():
            raise ValueError(f"Level Up character-name row {index + 1} is invalid")
        try:
            glyphs = metrics16.segment(name)
        except ValueError as error:
            raise ValueError(
                f"Level Up character name {name!r} uses unsupported FONT16 text"
            ) from error
        if sum(glyph.advance for glyph in glyphs) > 96:
            raise ValueError(f"Level Up character name exceeds 96px: {name!r}")
        pointer = RUNTIME_CAVE + len(payload)
        struct.pack_into(">I", payload, table_offset + index * 4, pointer)
        words = tuple(glyph.code for glyph in glyphs) + (0x8000,)
        payload.extend(struct.pack(f">{len(words)}H", *words))

    payload.extend(bytes((-(RUNTIME_CAVE + len(payload))) % 4))
    dispatcher_address = RUNTIME_CAVE + len(payload)
    dispatcher_symbols = {
        "LEARNED_LIST_POINTER": LEARNED_LIST_POINTER,
        "MAGIC_BASE": MAGNAME_BASE,
        "NAME_POINTER": MAGNAME_POINTER_FROM_NAME,
        "MAX_NAME_BYTES": MAX_ABILITY_NAME_BYTES,
        "SCRATCH": dispatcher_address,
        "LEARNED_LABEL": heading_address,
        "FONT16_VWF": RUNTIME_CAVE,
    }
    dispatcher_probe = _assembled(
        sources[2], dispatcher_address, dispatcher_symbols
    )
    scratch_address = (dispatcher_address + len(dispatcher_probe) + 1) & ~1
    dispatcher_symbols["SCRATCH"] = scratch_address
    dispatcher = _assembled(sources[2], dispatcher_address, dispatcher_symbols)
    if len(dispatcher) != len(dispatcher_probe):
        raise ValueError("Level Up scratch address changed dispatcher code size")
    payload.extend(dispatcher)
    payload.extend(bytes(scratch_address - (RUNTIME_CAVE + len(payload))))
    payload.extend(bytes(SCRATCH_BYTES))

    prepare_address = RUNTIME_CAVE + len(payload)
    prepare_symbols = {
        "LEARNED_LIST_POINTER": LEARNED_LIST_POINTER,
        "LAST_SKILL": prepare_address,
        "PREPARE": NAME_PREPARE,
    }
    prepare_probe = _assembled(sources[3], prepare_address, prepare_symbols)
    last_skill_address = prepare_address + len(prepare_probe)
    prepare_symbols["LAST_SKILL"] = last_skill_address
    prepare = _assembled(sources[3], prepare_address, prepare_symbols)
    if len(prepare) != len(prepare_probe):
        raise ValueError("Level Up state address changed prepare code size")
    payload.extend(prepare)
    if RUNTIME_CAVE + len(payload) != last_skill_address:
        raise ValueError("Level Up learned-row state address drifted")
    payload.append(0)

    used_size = len(payload)
    if used_size > RUNTIME_CAPACITY:
        raise ValueError(
            "Level Up runtime exceeds its exact 0x500 cave by "
            f"{used_size - RUNTIME_CAPACITY:#x} bytes"
        )
    payload.extend(bytes(RUNTIME_CAPACITY - used_size))
    return RuntimeBuild(
        bytes(payload),
        MappingProxyType(
            {
                "name_drawer": wrapper_address,
                "learned_drawer": dispatcher_address,
                "learned_prepare": prepare_address,
            }
        ),
        used_size,
    )


def _fallback_codes(
    terms: LevelUpTerms,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    stock_codes = _stock_latin_codes()
    max_text = terms.max_level_next
    if not max_text or len(max_text) > 7:
        raise ValueError("level_up.max_level_next must contain one to seven cells")
    no_mp = terms.no_magic_points
    if len(no_mp) != 7:
        raise ValueError(
            "level_up.no_magic_points must be three cells, one authored "
            "separator, then three cells"
        )
    try:
        max_codes = tuple(stock_codes[character] for character in max_text)
        no_mp_codes = tuple(stock_codes[character] for character in no_mp)
        blank = stock_codes[" "]
    except KeyError as error:
        raise ValueError(
            f"Level Up fallback uses unsupported stock-Latin cell {error.args[0]!r}"
        ) from error
    max_codes += (blank,) * (7 - len(max_codes))
    # Retail reserves one alignment cell after the separator; it is layout,
    # not part of the authored no-MP string.
    no_mp_codes = (*no_mp_codes[:4], blank, *no_mp_codes[4:])
    return max_codes, no_mp_codes


def _fallback_assembly(
    recipe: PatchRecipe,
    expected: bytes,
    terms: LevelUpTerms,
) -> bytes:
    max_codes, no_mp_codes = _fallback_codes(terms)
    if recipe.name == "no_magic_points_runtime":
        (source,) = _recipe_sources(
            recipe, ("level_up_ui/no_magic_points.s",)
        )
        if (
            terms.no_magic_points == terms.no_magic_points_reference
            and terms.templates.hp_mp_separator == "/"
        ):
            return expected
        replacement = _assembled(
            source,
            recipe.address,
            {
                "TEXT_FIRST": int.from_bytes(bytes(no_mp_codes[:4]), "big"),
                "TEXT_SECOND": int.from_bytes(bytes(no_mp_codes[4:]), "big"),
                "CONTINUE": recipe.address + len(expected),
            },
        )
    elif recipe.name == "max_level_next_runtime":
        (source,) = _recipe_sources(recipe, ("level_up_ui/max_level_next.s",))
        if terms.max_level_next == terms.max_level_next_reference:
            return expected
        replacement = _assembled(
            source,
            recipe.address,
            {
                **{f"MAX_LEVEL_{index}": code for index, code in enumerate(max_codes)},
                "STRING_DRAWER": 0x06026D4C,
                "NEXT_TABLE": 0x0602C5B4,
                "CONTINUE": recipe.address + len(expected),
            },
        )
    else:
        raise ValueError(f"unknown Level Up fallback assembly {recipe.name}")
    if len(replacement) != len(expected):
        raise ValueError(f"{recipe.name} assembly changed size")
    return replacement


def _build_components(
    config: PatchRecipeConfiguration,
    base: bytes,
    stock_font16: bytes,
    packed_magname: bytes,
) -> tuple[dict[str, bytes], RuntimeBuild, LevelUpTerms]:
    physical = _physical_records()
    terms = _level_up_terms(physical)
    characters = _character_names(physical)
    abilities = _ability_names(physical)
    metrics8 = FontMetrics.load(FONT8_METRICS_PATH)
    generated = _fixed_data(terms)
    generated.update(_layout_data(base, stock_font16, metrics8, terms))
    recipes = {recipe.name: recipe for recipe in config.patches[TARGET]}
    if len(recipes) != len(config.patches[TARGET]):
        raise ValueError("Level Up patch names must be unique")
    try:
        runtime_recipe = recipes["level_up_runtime"]
    except KeyError as error:
        raise ValueError("Level Up config is missing its runtime cave") from error
    runtime = _runtime_payload(
        runtime_recipe, terms, characters, abilities, packed_magname
    )
    return generated, runtime, terms


def _bind_patches(
    config: PatchRecipeConfiguration,
    base: bytes,
    stock_font16: bytes,
    packed_magname: bytes,
) -> tuple[tuple[Patch, ...], RuntimeBuild]:
    # All guards resolve against one untouched stock composition base.
    expected = {
        recipe.name: resolve_recipe_expected(recipe, base, LOAD_ADDRESS)
        for recipe in config.patches[TARGET]
    }
    generated, runtime, terms = _build_components(
        config, base, stock_font16, packed_magname
    )
    output: list[Patch] = []
    generated_seen: set[str] = set()
    for recipe in config.patches[TARGET]:
        replacement_recipe = recipe.replacement
        if replacement_recipe.kind == "assembly":
            if recipe.name == "level_up_runtime":
                replacement = runtime.data
            else:
                replacement = _fallback_assembly(
                    recipe, expected[recipe.name], terms
                )
        elif replacement_recipe.kind == "generated":
            if replacement_recipe.generator != "level_up_data":
                raise ValueError(f"{recipe.name}: unknown Level Up data generator")
            try:
                replacement = generated[recipe.name]
            except KeyError as error:
                raise ValueError(
                    f"Level Up data generator did not own {recipe.name}"
                ) from error
            generated_seen.add(recipe.name)
        elif replacement_recipe.kind == "linked_pointer":
            link = replacement_recipe.link
            assert link is not None
            try:
                replacement = struct.pack(">I", runtime.links[link])
            except KeyError as error:
                raise ValueError(f"unknown Level Up runtime link {link}") from error
        else:
            raise ValueError(
                f"{recipe.group}/{recipe.name}: unsupported Level Up replacement "
                f"kind {replacement_recipe.kind}"
            )
        if len(replacement) != len(expected[recipe.name]):
            raise ValueError(
                f"{recipe.group}/{recipe.name}: generated {len(replacement)} bytes, "
                f"expected {len(expected[recipe.name])}"
            )
        output.append(
            Patch(
                recipe.group,
                recipe.name,
                recipe.address,
                expected[recipe.name],
                replacement,
            )
        )
    unused = set(generated) - generated_seen
    if unused:
        raise ValueError(
            "Level Up data generator has no configured owner: "
            + ", ".join(sorted(unused))
        )
    return tuple(output), runtime


def build_level_up_ui(base: bytes | None = None) -> LevelUpUiBuild:
    """Build the complete standalone Level Up interface patch."""
    _validate_surfaces()
    config = _configuration()
    stock_level_up, stock_font16 = _source_assets()
    source = stock_level_up if base is None else base
    packed_magname = _validate_inputs(config, source, stock_font16)
    patches, runtime = _bind_patches(
        config, source, stock_font16, packed_magname
    )
    assembly_files = tuple(
        sorted(
            {
                path
                for recipe in config.patches[TARGET]
                for path in recipe.replacement.sources
            },
            key=lambda path: path.as_posix(),
        )
    )
    return LevelUpUiBuild(
        apply_patches(source, LOAD_ADDRESS, patches),
        patches,
        ASSET_FILES,
        assembly_files,
        RUNTIME_INPUT_FILES,
        MappingProxyType(
            {
                "game:LEVEL_UP.BIN": _sha256(source),
                "game:FONT16.FON": _sha256(stock_font16),
            }
        ),
        runtime.used_size,
    )
