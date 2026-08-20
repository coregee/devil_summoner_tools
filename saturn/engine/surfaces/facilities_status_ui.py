"""Compose EVENT's Fusion status, bar, and healing consumers.

This is the facility-complete EVENT composition base. It consumes the checked
equipment stage, owns the remaining detailed-status/facility hooks and
compatibility mirrors, and deliberately leaves Fusion's confirmation-window
patches to ``fusion.menu``. The optional FMV subtitle surface composes after it.
"""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence

from engine.core.patch_recipes import (
    ASSEMBLY_ROOT,
    PatchRecipe,
    PatchRecipeConfiguration,
    load_patch_recipe_configuration,
    resolve_recipe_expected,
)
from engine.core.patching import Patch, apply_patches
from engine.core.sh2 import Assembly, AssemblyError, assemble_file
from engine.shared.font8 import font8_tables
from engine.shared.player_names import CODENAME_BYTES
from engine.shared.status_layout import (
    derived_rows,
    direct_color_node,
    direct_color_row,
    load_font16_metrics,
    load_stock_latin_codes,
    load_status_labels,
    load_status_templates,
    node_background,
    validate_shiftable_bitmap,
)
from rom.util.catalog import load_catalog, validate_source
from rom.util.workflows import read_source_files
from text.util.assets import (
    ASSET_ROOT,
    BINDING_ROOT,
    CORPUS_ROOT,
    load_bound_translations,
    load_physical_record_files,
)
from text.util.event_repack import FontMetrics
from text.util.surfaces import load_surfaces


ENGINE_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = ENGINE_ROOT.parent
PROJECT_ROOT = SATURN_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "facilities_status_ui.json"
GENERATED_ROOT = ENGINE_ROOT / "generated" / "game"
OUTPUT_PATH = GENERATED_ROOT / "EVENT.BIN"
BUILD_PATH = GENERATED_ROOT / "facilities_status_ui_build.json"

FONT_ROOT = SATURN_ROOT / "font" / "generated" / "game"
FONT8_PATH = FONT_ROOT / "FONT8.FON"
FONT8_METRICS_PATH = FONT_ROOT / "FONT8_metrics.json"
FONT16_PATH = FONT_ROOT / "FONT16.FON"
FONT16_METRICS_PATH = FONT_ROOT / "FONT16_metrics.json"
TEXT_GENERATED_ROOT = SATURN_ROOT / "text" / "generated" / "game"
DVLNAME_PATH = TEXT_GENERATED_ROOT / "DVLNAME.DAT"
MAGNAME_PATH = TEXT_GENERATED_ROOT / "MAGNAME.DAT"
COMP_MENU_TEXT_BUILD_PATH = TEXT_GENERATED_ROOT / "comp_menu_build.json"
BATTLE_UI_TEXT_BUILD_PATH = TEXT_GENERATED_ROOT / "battle_ui_build.json"
SURFACES_PATH = SATURN_ROOT / "text" / "config" / "surfaces.json"
DISC_CONFIG_PATH = SATURN_ROOT / "rom" / "discs.json"

STATUS_ASSET_PATH = ASSET_ROOT / "ui" / "status.json"
RACE_ASSET_PATH = ASSET_ROOT / "races.json"
AFFINITY_ASSET_PATH = ASSET_ROOT / "affinities.json"
DEMON_ASSET_PATH = ASSET_ROOT / "demons.json"
CHARACTER_ASSET_PATH = ASSET_ROOT / "characters.json"
MAGIC_ASSET_PATH = ASSET_ROOT / "magic.json"
SKILL_ASSET_PATH = ASSET_ROOT / "skills.json"
BAR_ASSET_PATH = ASSET_ROOT / "facilities" / "bar.json"
HEALER_ASSET_PATH = ASSET_ROOT / "facilities" / "healer.json"
COMMON_ASSET_PATH = ASSET_ROOT / "facilities" / "common.json"
ASSET_FILES = (
    STATUS_ASSET_PATH,
    RACE_ASSET_PATH,
    AFFINITY_ASSET_PATH,
    DEMON_ASSET_PATH,
    CHARACTER_ASSET_PATH,
    MAGIC_ASSET_PATH,
    SKILL_ASSET_PATH,
    BAR_ASSET_PATH,
    HEALER_ASSET_PATH,
    COMMON_ASSET_PATH,
)
BINDING_FILES = tuple(
    BINDING_ROOT / name
    for name in (
        "affinities.json",
        "characters.json",
        "demons.json",
        "facilities_bar.json",
        "facilities_common.json",
        "facilities_healer.json",
        "magic.json",
        "races.json",
        "skills.json",
        "status.json",
    )
)
CORPUS_FILES = tuple(
    CORPUS_ROOT / relative
    for relative in (
        "compendium/addressed/race_names.json",
        "compendium/fixed/ability_names.json",
        "compendium/fixed/demon_names.json",
        "game/addressed/battle_command_labels.json",
        "game/addressed/combat_analysis_affinities.json",
        "game/addressed/da3d_analyze.json",
        "game/addressed/event_bar.json",
        "game/addressed/event_healing.json",
        "game/addressed/facility_command_labels.json",
        "game/addressed/normcom_tables.json",
        "game/addressed/normcom_status_ascii.json",
        "game/eve/shopsmp.json",
        "game/fixed/charname.json",
        "game/fixed/dvlname.json",
        "game/fixed/magname.json",
        "game/pointer/btl_mes.json",
    )
)
RUNTIME_INPUT_FILES = (
    FONT8_PATH,
    FONT8_METRICS_PATH,
    FONT16_PATH,
    FONT16_METRICS_PATH,
    DVLNAME_PATH,
    MAGNAME_PATH,
    COMP_MENU_TEXT_BUILD_PATH,
    BATTLE_UI_TEXT_BUILD_PATH,
    SURFACES_PATH,
    DISC_CONFIG_PATH,
    *BINDING_FILES,
    *CORPUS_FILES,
)

TARGET = "EVENT.BIN"
LOAD_ADDRESS = 0x06020000
RUNTIME_ADDRESS = 0x06023294
RUNTIME_LIMIT = 0x06026500
RUNTIME_CAPACITY = RUNTIME_LIMIT - RUNTIME_ADDRESS

FONT16_DRAWER = 0x060517C4
FONT12_DRAWER = 0x06051830
FONT8_GLYPH_DRAWER = 0x06051380
FONT16_BITMAP = 0x0021A000
FONT8_BITMAP = 0x00219150
CURRENT_PARTY_TYPE = 0x060BF6EC
CURRENT_NAME_PTR = 0x06076BA0
RACE_SOURCE = 0x06074828
AFFINITY_SOURCE = 0x060744EA + 32 * 34
AFFINITY_SELECTOR = 0x06076FF0
PLAYER_STATUS_NAME = 0x0023FE14
MAGNAME_BASE = 0x0022F7A0
MAGNAME_FIRST = MAGNAME_BASE + 4
MAGNAME_END = 0x00235740
MAGNAME_POINTER_OFFSET = 0x5A

CHARACTER_INSERT_STOCK = 0x0602C3A8
CHARACTER_INSERT_END = 0x0602C420
CURRENT_DEMON_IDS = 0x060BFCF0
RACE_ID_HELPER = 0x0602FC10
INSERT_STATE = 0x060BE9E8
INSERT_ACTIVE = 0x06076760
INSERT_STREAM_PUSH = 0x0602BEA8
INSERT_STREAM_POINTER = 0x060BF6E0
INSERT_STREAM_STATUS = 0x060BFD00
TEXT_FLAGS = 0x06076BC4
DEMON_INSERT_STOCK = 0x0602C84C
RACE_INSERT_STOCK = 0x0602C9F0

BAR_DVL_SOURCE = 0x0023F5D0
BAR_DVL_SOURCE_END = BAR_DVL_SOURCE + 319 * 8
BAR_CHAR_SOURCE = 0x0023FFD0
BAR_CHAR_SOURCE_END = BAR_CHAR_SOURCE + 6 * 8
BAR_PARTY_SOURCE_PTR = 0x0606254C
BAR_SURFACE_PTR = 0x06067604
HEALING_SURFACE_PTR = 0x06067360
HEALING_SURFACE_WIDTH = 0xB0
HEALING_CHAR_SOURCE_PTR = 0x0606254C
HEALING_DVL_SOURCE_PTR = 0x06062550

NODE_BITMAP_OFFSET = 0x48FCC
RACE_COUNT = 43
AFFINITY_COUNT = 96
RUNTIME_AFFINITY_COUNT = 66
DEMON_COUNT = 319
CHARACTER_COUNT = 6
DRINK_COUNT = 16
TALK_ROLE_COUNT = 6
AFFINITY_SURFACE_WIDTH = 128
AFFINITY_MAX_ADVANCE = AFFINITY_SURFACE_WIDTH - 1
AFFINITY_ADVANCE_OVERRIDES = {" ": 1, ",": 2, ":": 2}

FUSION_CONFIRMATION_PATCH_NAMES = frozenset(
    {
        "fusion_confirmation_pointer_lookup",
        "fusion_confirmation_main_storage",
        "fusion_confirmation_level_too_low",
        "fusion_confirmation_label_yes",
        "fusion_confirmation_label_no",
        "fusion_confirmation_vwf_drawer",
    }
)
FUSION_CONFIRMATION_SPANS = (
    ("pointer_lookup", 0x060578A2, 22),
    ("main_storage", 0x0607458E, 160),
    ("level_too_low", 0x06022FBC, 68),
    ("label_yes", 0x0607462E, 8),
    ("label_no", 0x06074636, 8),
    ("vwf_drawer", 0x06057910, 4),
)

RECIPE_CONTRACT = (
    ("fusion.status_ui", "fusion_parameter_nodes", 0x06068FCC, "generated", "facilities_status_data"),
    ("fusion.status_ui", "fusion_parameter_rows", 0x06069BCC, "generated", "facilities_status_data"),
    ("fusion.status_ui", "fusion_generic_attack_label", 0x0606BFCC, "generated", "facilities_status_data"),
    ("fusion.status_ui", "fusion_generic_accuracy_label", 0x0606C44C, "generated", "facilities_status_data"),
    ("fusion.status_ui", "fusion_personality_label_0", 0x0606C8CC, "generated", "facilities_status_data"),
    ("fusion.status_ui", "fusion_personality_label_1", 0x0606CC8C, "generated", "facilities_status_data"),
    ("fusion.status_ui", "fusion_personality_label_2", 0x0606D04C, "generated", "facilities_status_data"),
    ("fusion.status_ui", "fusion_personality_label_3", 0x0606D40C, "generated", "facilities_status_data"),
    ("fusion.status_ui", "fusion_personality_label_4", 0x0606D7CC, "generated", "facilities_status_data"),
    ("fusion.status_ui", "fusion_personality_label_5", 0x0606DB8C, "generated", "facilities_status_data"),
    ("fusion.status_ui", "fusion_personality_label_6", 0x0606DF4C, "generated", "facilities_status_data"),
    ("fusion.status_ui", "fusion_personality_label_7", 0x0606E30C, "generated", "facilities_status_data"),
    ("fusion.status_ui", "fusion_personality_label_8", 0x0606E6CC, "generated", "facilities_status_data"),
    ("fusion.status_ui", "fusion_personality_label_9", 0x0606EA8C, "generated", "facilities_status_data"),
    ("fusion.status_ui", "fusion_personality_label_10", 0x0606EE4C, "generated", "facilities_status_data"),
    (
        "fusion.status_ui",
        "fusion_status_runtime",
        0x06023294,
        "assembly",
        (
            "facilities_status_ui/font16_vwf.s",
            "facilities_status_ui/font16_from_font8.s",
            "facilities_status_ui/skill_vwf.s",
            "facilities_status_ui/affinity_font8_vwf.s",
            "facilities_status_ui/status_skill_dispatcher.s",
            "facilities_status_ui/name_race_dispatcher.s",
            "facilities_status_ui/affinity_dispatcher.s",
            "facilities_status_ui/font8_surface_blitter.s",
            "facilities_status_ui/facility_name_drawers.s",
            "facilities_status_ui/event_term_inserts.s",
        ),
    ),
    ("fusion.status_ui", "fusion_name_race_drawer", 0x06054BCC, "linked_pointer", "fusion_name_race_drawer"),
    ("fusion.status_ui", "fusion_skill_name_drawer", 0x060582A8, "linked_pointer", "fusion_skill_name_drawer"),
    ("fusion.status_ui", "fusion_status_skill_drawer", 0x06055744, "linked_pointer", "fusion_status_skill_drawer"),
    ("fusion.status_ui", "fusion_affinity_drawer", 0x06055E44, "linked_pointer", "fusion_affinity_drawer"),
    (
        "event.term_inserts",
        "event_dialogue_character_name_insert",
        0x0602C3A8,
        "assembly",
        ("facilities_status_ui/event_character_insert.s",),
    ),
    ("event.term_inserts", "event_dialogue_demon_name_insert", 0x0602C0DC, "linked_pointer", "event_dialogue_demon_name_insert"),
    ("event.term_inserts", "event_dialogue_race_insert", 0x0602C0EC, "linked_pointer", "event_dialogue_race_insert"),
    (
        "facilities.command_ui",
        "facility_revive_status_aliases",
        0x060625F8,
        "generated",
        "facilities_status_data",
    ),
    ("bar.status_ui", "bar_drink_name_drawer", 0x06039DB0, "linked_pointer", "bar_drink_name_drawer"),
    ("bar.status_ui", "bar_talk_role_drawer", 0x06039E80, "linked_pointer", "bar_talk_role_drawer"),
    ("bar.status_ui", "bar_status_name_glyph", 0x06039FCC, "linked_pointer", "bar_status_name_glyph"),
    ("bar.status_ui", "bar_party_name_glyph", 0x06039B40, "linked_pointer", "bar_party_name_glyph"),
    ("healer.status_ui", "healing_all_drawer_0", 0x06037728, "linked_pointer", "healing_all_drawer"),
    ("healer.status_ui", "healing_all_drawer_1", 0x06037940, "linked_pointer", "healing_all_drawer"),
    ("healer.status_ui", "healing_all_drawer_2", 0x06037BA8, "linked_pointer", "healing_all_drawer"),
    ("healer.status_ui", "healing_name_drawer_0", 0x0603780C, "linked_pointer", "healing_name_drawer"),
    ("healer.status_ui", "healing_name_drawer_1", 0x06037A5C, "linked_pointer", "healing_name_drawer"),
    ("healer.status_ui", "healing_name_drawer_2", 0x06037CD0, "linked_pointer", "healing_name_drawer"),
    ("healer.status_ui", "healing_name_drawer_3", 0x06037D74, "linked_pointer", "healing_name_drawer"),
    ("event.fixed_text_compatibility", "races_022", 0x060748AC, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_001", 0x0607494C, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_029", 0x06074D04, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_051", 0x06074FF0, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_052", 0x06075012, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_060", 0x06075122, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_064", 0x060751AA, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_066", 0x060751EE, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_067", 0x06075210, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_068", 0x06075232, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_069", 0x06075254, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_070", 0x06075276, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_071", 0x06075298, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_072", 0x060752BA, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_073", 0x060752DC, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_074", 0x060752FE, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_075", 0x06075320, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_076", 0x06075342, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_077", 0x06075364, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_078", 0x06075386, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_079", 0x060753A8, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_080", 0x060753CA, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_081", 0x060753EC, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_082", 0x0607540E, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_083", 0x06075430, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_084", 0x06075452, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_085", 0x06075474, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_086", 0x06075496, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_087", 0x060754B8, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_088", 0x060754DA, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_089", 0x060754FC, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_090", 0x0607551E, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_091", 0x06075540, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_092", 0x06075562, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_093", 0x06075584, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_094", 0x060755A6, "generated", "facilities_status_data"),
    ("event.fixed_text_compatibility", "affinities_095", 0x060755C8, "generated", "facilities_status_data"),
)


@dataclass(frozen=True, slots=True)
class RuntimeArena:
    name: str
    address: int
    used_size: int
    capacity: int


@dataclass(frozen=True, slots=True)
class RuntimeBuild:
    data: bytes
    character_handler: bytes
    generated: Mapping[str, bytes]
    links: Mapping[str, int]
    arena: RuntimeArena


@dataclass(frozen=True, slots=True)
class FacilitiesStatusUiBuild:
    data: bytes
    patches: tuple[Patch, ...]
    asset_files: tuple[Path, ...]
    assembly_files: tuple[Path, ...]
    runtime_input_files: tuple[Path, ...]
    source_inputs: Mapping[str, str]
    runtime_used_size: int
    runtime_capacity: int
    runtime_arenas: tuple[RuntimeArena, ...]


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        return _sha256(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"missing facilities/status input: {path}") from error


def _recipe_contract(recipe: PatchRecipe) -> tuple[object, ...]:
    replacement = recipe.replacement
    if replacement.kind == "assembly":
        detail: object = tuple(
            path.relative_to(ASSEMBLY_ROOT).as_posix()
            for path in replacement.sources
        )
    elif replacement.kind == "linked_pointer":
        detail = replacement.link
    elif replacement.kind == "generated":
        detail = replacement.generator
    elif replacement.kind == "pointer":
        detail = replacement.pointer
    elif replacement.kind == "instruction":
        detail = replacement.instruction
    else:
        raise ValueError("facilities/status replacement kind changed")
    return recipe.group, recipe.name, recipe.address, replacement.kind, detail


def _configuration() -> PatchRecipeConfiguration:
    config = load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="facilities.status_ui",
        target_names={TARGET},
        input_names={
            "font8_sha256",
            "font8_metrics_sha256",
            "font16_sha256",
            "font16_metrics_sha256",
            "stock_dvlname_sha256",
            "stock_font16_sha256",
            "stock_charname_sha256",
        },
    )
    actual = tuple(_recipe_contract(recipe) for recipe in config.patches[TARGET])
    if actual != RECIPE_CONTRACT:
        raise ValueError("facilities/status ordered recipe contract changed")
    return config


def _source_assets() -> tuple[bytes, bytes, bytes, bytes]:
    catalog = load_catalog()
    try:
        game = catalog["game"]
    except KeyError as error:
        raise ValueError("disc catalog has no game source") from error
    source = read_source_files(
        validate_source(game),
        (TARGET, "DVLNAME.DAT", "CHARNAME.DAT", "FONT16.FON"),
    )
    return (
        source[TARGET],
        source["DVLNAME.DAT"],
        source["CHARNAME.DAT"],
        source["FONT16.FON"],
    )


def _validate_inputs(
    config: PatchRecipeConfiguration,
    base: bytes,
    stock_event: bytes,
    stock_dvlname: bytes,
    stock_charname: bytes,
    stock_font16: bytes,
) -> tuple[bytes, bytes]:
    contract = config.targets[TARGET]
    if (
        contract.load_address != LOAD_ADDRESS
        or len(stock_event) != contract.size
        or _sha256(stock_event) != contract.stock_sha256
    ):
        raise ValueError("stock EVENT.BIN does not match the facilities/status target")
    if len(base) != contract.size:
        raise ValueError("composed EVENT.BIN has the wrong size")
    actual = {
        "font8_sha256": _file_sha256(FONT8_PATH),
        "font8_metrics_sha256": _file_sha256(FONT8_METRICS_PATH),
        "font16_sha256": _file_sha256(FONT16_PATH),
        "font16_metrics_sha256": _file_sha256(FONT16_METRICS_PATH),
        "stock_dvlname_sha256": _sha256(stock_dvlname),
        "stock_font16_sha256": _sha256(stock_font16),
        "stock_charname_sha256": _sha256(stock_charname),
    }
    for name, expected in config.inputs.items():
        if actual[name] != expected:
            raise ValueError(
                f"facilities/status {name} expected SHA-256 {expected}, "
                f"found {actual[name]}"
            )
    comp = _text_build_manifest(COMP_MENU_TEXT_BUILD_PATH, "comp.menu")
    battle = _text_build_manifest(BATTLE_UI_TEXT_BUILD_PATH, "battle.ui")
    for manifest, label in ((comp, "DVLNAME"), (battle, "MAGNAME")):
        for name in ("font8_metrics_sha256", "font16_metrics_sha256"):
            if manifest.get(name) != actual[name]:
                raise ValueError(
                    f"{label} text build uses different {name}"
                )
    dvlname = _generated_output(comp, DVLNAME_PATH, DEMON_COUNT)
    magname = _generated_output(
        battle,
        MAGNAME_PATH,
        255,
        translated_names=255,
    )
    if len(dvlname) != DEMON_COUNT * 8:
        raise ValueError("generated DVLNAME has the wrong size")
    if len(magname) != 255 * 96:
        raise ValueError("generated MAGNAME has the wrong size")
    return dvlname, magname


def _text_build_manifest(path: Path, surface: str) -> Mapping[str, object]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"missing generated text manifest: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid generated text manifest: {path}") from error
    if (
        not isinstance(document, dict)
        or document.get("version") != 1
        or document.get("surface") != surface
    ):
        raise ValueError(f"{path.name} does not describe {surface}")
    return document


def _generated_output(
    manifest: Mapping[str, object],
    path: Path,
    records: int,
    *,
    translated_names: int | None = None,
) -> bytes:
    outputs = manifest.get("outputs")
    record = outputs.get(path.name) if isinstance(outputs, dict) else None
    if not isinstance(record, dict) or record.get("records") != records:
        raise ValueError(f"generated manifest has no valid {path.name} record")
    if translated_names is not None and record.get("translated_names") != translated_names:
        raise ValueError(f"generated {path.name} translation inventory changed")
    data = path.read_bytes()
    if record.get("sha256") != _sha256(data):
        raise ValueError(f"generated {path.name} manifest SHA-256 is stale")
    return data


def _validate_surfaces() -> None:
    surfaces = load_surfaces()
    expected = {
        "status.character_name": ("font16", 1, "pixels", 126),
        "status.demon_name": ("font16", 1, "pixels", 126),
        "status.demon_race": ("font16", 1, "pixels", 46),
        "status.skill_name": ("font8", 1, "pixels", 80),
        "status.affinity": ("font8", 2, "pixels", 128),
        "status.base_stat_label": ("font8", 1, "pixels", 12),
        "status.derived_stat_label": ("font8", 1, "pixels", 46),
        "status.loyalty_label": ("font8", 1, "pixels", 38),
        "bar.drink_name": ("font8", 1, "pixels", 64),
        "bar.patron_name": ("font8", 1, "pixels", 64),
        "bar.status_name": ("font8", 1, "pixels", 104),
        "healer.all_members": ("font8", 1, "pixels", 144),
        "healer.member_name": ("font8", 1, "pixels", 104),
        "healer.status_name": ("font8", 1, "pixels", 104),
    }
    for name, geometry in expected.items():
        layout = surfaces.surface(name).en
        actual = (layout.font, layout.rows, layout.width.unit, layout.width.value)
        if actual != geometry:
            raise ValueError(f"{name} geometry changed: expected {geometry}, found {actual}")


def _bound_translations(
    prefixes: tuple[str, ...],
    required_ids: set[str],
    binding_files: tuple[Path, ...],
) -> Mapping[str, str]:
    return load_bound_translations(
        prefixes,
        required_ids=required_ids,
        binding_paths=binding_files,
        physical_records=load_physical_record_files(CORPUS_FILES),
    )


def _bound_values(
    prefix: str,
    count: int,
    record_format: str,
    binding_file: Path,
) -> list[str]:
    ids = [f"{prefix}{record_format.format(index)}" for index in range(count)]
    values = _bound_translations((prefix,), set(ids), (binding_file,))
    return [values[physical_id] for physical_id in ids]


def _status_terms() -> tuple[list[str], list[str], list[str], list[str]]:
    races = _bound_values(
        "game.normcom_tables.races.",
        RACE_COUNT,
        "r{0:04d}",
        BINDING_ROOT / "races.json",
    )
    affinities = _bound_values(
        "game.normcom_tables.affinities.",
        AFFINITY_COUNT,
        "r{0:04d}",
        BINDING_ROOT / "affinities.json",
    )
    demon_ids = [f"game.dvlname.o{index * 8:06x}.text" for index in range(DEMON_COUNT)]
    demon_values = _bound_translations(
        ("game.dvlname.",), set(demon_ids), (BINDING_ROOT / "demons.json",)
    )
    character_ids = [
        f"game.charname.o{index * 8:06x}.text" for index in range(CHARACTER_COUNT)
    ]
    character_values = _bound_translations(
        ("game.charname.",),
        set(character_ids),
        (BINDING_ROOT / "characters.json",),
    )
    return (
        races,
        affinities,
        [demon_values[physical_id] for physical_id in demon_ids],
        [character_values[physical_id] for physical_id in character_ids],
    )


def _built_charname(
    stock: bytes,
    character_names: list[str],
    metrics8: FontMetrics,
) -> bytes:
    if len(stock) != CHARACTER_COUNT * 8:
        raise ValueError("stock CHARNAME has the wrong size")
    glyphs = metrics8.segment(character_names[2])
    encoded = bytes(glyph.code for glyph in glyphs)
    if not encoded or len(encoded) > 8:
        raise ValueError("Kyouji's direct CHARNAME record exceeds eight bytes")
    output = bytearray(stock)
    output[16:24] = encoded.ljust(8, b"\0")
    return bytes(output)


def _add_name_hashes(
    hashes: dict[int, str],
    assets: tuple[bytes, ...],
    translated: list[str],
    context: str,
) -> None:
    for asset in assets:
        if len(asset) != len(translated) * 8:
            raise ValueError(f"{context} lookup source has the wrong size")
        for index, name in enumerate(translated):
            first, second = struct.unpack_from(">II", asset, index * 8)
            key = first ^ second
            previous = hashes.get(key)
            if previous is not None and previous != name:
                raise ValueError(
                    f"{context} XOR collision has different translations: "
                    f"{previous!r} and {name!r}"
                )
            hashes[key] = name


def _font16_glyphs(
    text: str,
    codes: Mapping[str, int],
    widths: bytes,
    context: str,
    max_width: int,
) -> list[int]:
    try:
        glyphs = [codes[character] for character in text]
    except KeyError as error:
        raise ValueError(
            f"unsupported {context} FONT16 character in {text!r}: "
            f"{error.args[0]!r}"
        ) from error
    pixel_width = sum(widths[glyph] for glyph in glyphs)
    if pixel_width > max_width:
        raise ValueError(
            f"{context} exceeds {max_width}px ({pixel_width}px): {text!r}"
        )
    return glyphs


def _affinity_advance(
    text: str,
    widths: bytes,
    codes: Mapping[str, int],
    context: str,
) -> int:
    try:
        return sum(
            AFFINITY_ADVANCE_OVERRIDES.get(character, widths[codes[character]])
            for character in text
        )
    except KeyError as error:
        raise ValueError(
            f"unsupported {context} FONT8 character {error.args[0]!r} in {text!r}"
        ) from error


def _validate_affinity_font8(
    bitmap: bytes,
    widths: bytes,
    codes: Mapping[str, int],
) -> None:
    for character, advance in AFFINITY_ADVANCE_OVERRIDES.items():
        try:
            code = codes[character]
        except KeyError as error:
            raise ValueError(f"status FONT8 is missing {character!r}") from error
        glyph = bitmap[code * 8 : (code + 1) * 8]
        if len(glyph) != 8:
            raise ValueError(f"status FONT8 glyph {code} is missing")
        ink_x = [x for row in glyph for x in range(8) if row & (0x80 >> x)]
        if character == " ":
            if ink_x:
                raise ValueError("compact affinity space is not blank")
        elif not ink_x or max(ink_x) >= advance:
            raise ValueError(
                f"compact affinity {character!r} exceeds its {advance}px advance"
            )
        if advance > widths[code]:
            raise ValueError(
                f"compact affinity {character!r} exceeds its FONT8 metrics"
            )


def _encode_affinity_font8(
    text: str,
    widths: bytes,
    codes: Mapping[str, int],
) -> bytes:
    for index, character in enumerate(text[:-1]):
        if character in ",:" and text[index + 1] != " ":
            raise ValueError(
                f"compact punctuation must be followed by a space: {text!r}"
            )
    try:
        encoded = bytes(codes[character] for character in text)
    except KeyError as error:
        raise ValueError(
            f"unsupported affinity FONT8 character {error.args[0]!r} in {text!r}"
        ) from error
    pixel_width = _affinity_advance(text, widths, codes, "affinity")
    if pixel_width > AFFINITY_MAX_ADVANCE:
        raise ValueError(
            f"affinity exceeds {AFFINITY_MAX_ADVANCE}px ({pixel_width}px): {text!r}"
        )
    return encoded + b"\0"


def _encode_font8(
    text: str,
    codes: Mapping[str, int],
    widths: bytes,
    context: str,
    max_width: int,
    max_glyphs: int | None = None,
) -> bytes:
    try:
        encoded = bytes(codes[character] for character in text)
    except KeyError as error:
        raise ValueError(
            f"unsupported {context} FONT8 character {error.args[0]!r} in {text!r}"
        ) from error
    if max_glyphs is not None and len(encoded) > max_glyphs:
        raise ValueError(
            f"{context} exceeds {max_glyphs} glyphs ({len(encoded)}): {text!r}"
        )
    pixel_width = sum(widths[code] for code in encoded) + max(0, len(encoded) - 1)
    if pixel_width > max_width:
        raise ValueError(
            f"{context} exceeds {max_width}px ({pixel_width}px): {text!r}"
        )
    return encoded + b"\0"


def _build_name_lookup(hashes: Mapping[int, str], resolve_pointer) -> bytes:
    return b"".join(
        struct.pack(">II", key, resolve_pointer(name))
        for key, name in sorted(hashes.items())
    )


def _populate_term_tables(
    data: bytearray,
    race_offset: int,
    affinity_offset: int,
    races: list[str],
    affinities: list[str],
    encode_race,
    encode_affinity,
) -> None:
    for index, text in enumerate(races):
        struct.pack_into(">I", data, race_offset + index * 4, encode_race(text))
    encode_affinity("")
    for index, text in enumerate(affinities):
        lines = text.split("{n}")
        if len(lines) > 2:
            raise ValueError(f"fusion affinity {index} exceeds two rows")
        lines += [""] * (2 - len(lines))
        struct.pack_into(
            ">II",
            data,
            affinity_offset + index * 8,
            *(encode_affinity(line) for line in lines),
        )


def _facility_terms() -> tuple[list[str], list[str], str]:
    drink_ids = [f"game.event_bar.drinks.r{index:04d}" for index in range(DRINK_COUNT)]
    talk_ids = [
        f"game.event_bar.talk_labels.r{index:04d}" for index in range(TALK_ROLE_COUNT)
    ]
    healing_id = "game.event_healing.o0168f7"
    values = _bound_translations(
        ("game.event_bar.", "game.event_healing."),
        set((*drink_ids, *talk_ids, healing_id)),
        (
            BINDING_ROOT / "facilities_bar.json",
            BINDING_ROOT / "facilities_healer.json",
        ),
    )
    return (
        [values[physical_id] for physical_id in drink_ids],
        [values[physical_id] for physical_id in talk_ids],
        values[healing_id],
    )


def _facility_alias_data(codes8: Mapping[str, int]) -> bytes:
    physical_ids = (
        "game.facility_command_labels.o0425f8",
        "game.facility_command_labels.o0425fe",
    )
    values = _bound_translations(
        ("game.facility_command_labels.",),
        set(physical_ids),
        (
            BINDING_ROOT / "facilities_healer.json",
            BINDING_ROOT / "facilities_common.json",
        ),
    )
    output = bytearray()
    for physical_id in physical_ids:
        text = values[physical_id]
        try:
            encoded = bytes(codes8[character] for character in text)
        except KeyError as error:
            raise ValueError(
                f"unsupported facility command character {error.args[0]!r} "
                f"in {text!r}"
            ) from error
        if len(encoded) != 6:
            raise ValueError(f"facility command {text!r} must occupy six cells")
        output.extend(encoded)
    if len(output) != 12:
        raise ValueError("facility command alias inventory changed")
    return bytes(output)


def _ambiguous_magname_fallbacks(built: bytes) -> tuple[bytes, ...]:
    ids = [f"game.magname.o{index * 96 + 4:06x}.name" for index in range(255)]
    values = _bound_translations(
        ("game.magname.",),
        set(ids),
        (BINDING_ROOT / "magic.json", BINDING_ROOT / "skills.json"),
    )
    if len(built) != 255 * 96:
        raise ValueError("fusion status needs 255 MAGNAME records")
    seen: dict[bytes, str] = {}
    ambiguous: set[bytes] = set()
    for index, physical_id in enumerate(ids):
        fallback = built[index * 96 + 4 : index * 96 + 12]
        name = values[physical_id]
        previous = seen.get(fallback)
        if previous is not None and previous != name:
            ambiguous.add(fallback)
        seen[fallback] = name
    result = tuple(sorted(ambiguous))
    if len(result) != 4:
        raise ValueError(
            "fusion status expected four ambiguous MAGNAME fallbacks, found "
            f"{len(result)}"
        )
    return result


def _event_english_data(
    widths8: bytes,
    codes8: Mapping[str, int],
    widths16: bytes,
    codes16: Mapping[str, int],
    font8: bytes,
    font16: bytes,
    races: list[str],
    affinities: list[str],
    demon_names: list[str],
    character_names: list[str],
    english_dvlname: bytes,
    stock_charname: bytes,
    english_charname: bytes,
) -> tuple[bytes, dict[str, int]]:
    validate_shiftable_bitmap(font16, widths16, 32, 2, "EVENT status FONT16")
    validate_shiftable_bitmap(font8, widths8, 8, 1, "EVENT status FONT8")
    _validate_affinity_font8(font8, widths8, codes8)
    if (
        len(races) != RACE_COUNT
        or len(affinities) != AFFINITY_COUNT
        or len(demon_names) != DEMON_COUNT
        or len(character_names) != CHARACTER_COUNT
        or len(english_dvlname) != DEMON_COUNT * 8
        or any(len(value) != CHARACTER_COUNT * 8 for value in (stock_charname, english_charname))
    ):
        raise ValueError("EVENT status terminology inventory changed")

    all_names = (*demon_names, *character_names)
    _validate_status_name_mapper(codes8, codes16, all_names)

    hashes: dict[int, str] = {}
    _add_name_hashes(hashes, (english_dvlname,), demon_names, "EVENT demon name")
    _add_name_hashes(
        hashes,
        (stock_charname, english_charname),
        character_names,
        "EVENT character name",
    )

    data = bytearray()

    def align(alignment: int = 4) -> None:
        data.extend(bytes((-(RUNTIME_ADDRESS + len(data))) % alignment))

    def reserve(size: int, alignment: int = 4) -> tuple[int, int]:
        align(alignment)
        offset = len(data)
        data.extend(bytes(size))
        return offset, RUNTIME_ADDRESS + offset

    widths16_offset, widths16_address = reserve(len(widths16))
    data[widths16_offset : widths16_offset + len(widths16)] = widths16
    widths8_offset, widths8_address = reserve(len(widths8))
    data[widths8_offset : widths8_offset + len(widths8)] = widths8

    for index, name in enumerate(all_names):
        _font16_glyphs(
            name,
            codes16,
            widths16,
            f"EVENT status name {index}",
            126,
        )

    font16_advances = bytearray(229 - 63 + 1)
    for character in set("".join(all_names)):
        try:
            source_code = codes8[character]
            target_code = codes16[character]
        except KeyError as error:
            raise ValueError(
                f"EVENT FONT16 name mapping is missing {error.args[0]!r}"
            ) from error
        if not 63 <= source_code <= 229:
            raise ValueError(f"EVENT FONT8 name code {source_code} is out of range")
        font16_advances[source_code - 63] = widths16[target_code]
    compact_font16_advances = (
        font16_advances[: 118 - 63] + font16_advances[205 - 63 :]
    )
    if len(compact_font16_advances) != 80:
        raise ValueError("EVENT compact FONT16 table must be 80 bytes")
    compact16_offset, compact16_address = reserve(len(compact_font16_advances))
    data[compact16_offset : compact16_offset + len(compact_font16_advances)] = (
        compact_font16_advances
    )

    race_offset, race_address = reserve(RACE_COUNT * 4)
    runtime_affinities = affinities[:RUNTIME_AFFINITY_COUNT]
    affinity_offset, affinity_address = reserve(RUNTIME_AFFINITY_COUNT * 8)
    lookup_offset, lookup_address = reserve(len(hashes) * 8)

    font16_pool: dict[str, int] = {}
    affinity_pool: dict[str, int] = {}

    def encode_font16(text: str) -> int:
        cached = font16_pool.get(text)
        if cached is not None:
            return cached
        align(2)
        pointer = RUNTIME_ADDRESS + len(data)
        glyphs = _font16_glyphs(
            text,
            codes16,
            widths16,
            "EVENT status race",
            46,
        )
        data.extend(struct.pack(f">{len(glyphs) + 1}H", *glyphs, 0x8000))
        font16_pool[text] = pointer
        return pointer

    def encode_affinity(text: str) -> int:
        cached = affinity_pool.get(text)
        if cached is not None:
            return cached
        pointer = RUNTIME_ADDRESS + len(data)
        data.extend(_encode_affinity_font8(text, widths8, codes8))
        affinity_pool[text] = pointer
        return pointer

    _populate_term_tables(
        data,
        race_offset,
        affinity_offset,
        races,
        runtime_affinities,
        encode_font16,
        encode_affinity,
    )

    name_pool = bytearray()
    name_offsets: dict[str, int] = {}
    for name in hashes.values():
        if name in name_offsets:
            continue
        name_offsets[name] = len(name_pool)
        name_pool.extend(
            _encode_font8(name, codes8, widths8, "EVENT facility name", 104)
        )
    record_offsets = bytearray()
    for name in (*demon_names, *character_names):
        offset = name_offsets[name]
        if offset > 0xFFFF:
            raise ValueError("EVENT name pool exceeds 16-bit offsets")
        record_offsets.extend(struct.pack(">H", offset))
    align(2)
    record_offsets_address = RUNTIME_ADDRESS + len(data)
    data.extend(record_offsets)
    name_pool_address = RUNTIME_ADDRESS + len(data)
    data.extend(name_pool)
    lookup = _build_name_lookup(
        hashes, lambda name: name_pool_address + name_offsets[name]
    )
    data[lookup_offset : lookup_offset + len(lookup)] = lookup

    drinks, talk_labels, healing_all = _facility_terms()
    drink_pool = bytearray()
    drink_offsets = bytearray()
    for index, translation in enumerate(drinks):
        if len(drink_pool) > 0xFFFF:
            raise ValueError("bar drink string pool exceeds 16-bit offsets")
        drink_offsets.extend(struct.pack(">H", len(drink_pool)))
        drink_pool.extend(
            _encode_font8(
                translation,
                codes8,
                widths8,
                f"bar drink {index}",
                64,
            )
        )
    align(2)
    drink_offsets_address = RUNTIME_ADDRESS + len(data)
    data.extend(drink_offsets)
    drink_pool_address = RUNTIME_ADDRESS + len(data)
    data.extend(drink_pool)

    talk_pool = bytearray(b"\0")
    talk_offsets = bytearray(b"\0\0")
    for index, translation in enumerate(talk_labels, 1):
        if len(talk_pool) > 0xFFFF:
            raise ValueError("bar patron string pool exceeds 16-bit offsets")
        talk_offsets.extend(struct.pack(">H", len(talk_pool)))
        talk_pool.extend(
            _encode_font8(
                translation,
                codes8,
                widths8,
                f"bar patron {index}",
                64,
            )
        )
    align(2)
    talk_offsets_address = RUNTIME_ADDRESS + len(data)
    data.extend(talk_offsets)
    talk_pool_address = RUNTIME_ADDRESS + len(data)
    data.extend(talk_pool)

    healing_all_address = RUNTIME_ADDRESS + len(data)
    data.extend(
        _encode_font8(
            healing_all,
            codes8,
            widths8,
            "healer all-members",
            144,
            32,
        )
    )
    return bytes(data), {
        "widths16": widths16_address,
        "widths8": widths8_address,
        "compact_widths16": compact16_address,
        "race_table": race_address,
        "affinity_table": affinity_address,
        "name_lookup": lookup_address,
        "name_count": len(hashes),
        "name_offsets": record_offsets_address,
        "name_pool": name_pool_address,
        "drink_offsets": drink_offsets_address,
        "drink_pool": drink_pool_address,
        "talk_offsets": talk_offsets_address,
        "talk_pool": talk_pool_address,
        "healing_all": healing_all_address,
    }


def _layout_data(
    base: bytes,
    font8: bytes,
    stock_font16: bytes,
    widths8: bytes,
    codes8: Mapping[str, int],
) -> dict[str, bytes]:
    templates = load_status_templates()
    labels = load_status_labels(templates)
    rows = derived_rows(labels)
    background = node_background(
        base[NODE_BITMAP_OFFSET : NODE_BITMAP_OFFSET + 16 * 16 * 2],
        stock_font16,
    )
    output = {
        "fusion_parameter_nodes": b"".join(
            direct_color_node(label, font8, widths8, codes8, background)
            for label in labels.base
        ),
        "fusion_parameter_rows": b"".join(
            direct_color_row(" ".join(row), font8, widths8, codes8)
            for row in rows
        ),
        "fusion_generic_attack_label": direct_color_row(
            labels.attack, font8, widths8, codes8
        ),
        "fusion_generic_accuracy_label": direct_color_row(
            labels.accuracy, font8, widths8, codes8
        ),
    }
    output.update(
        {
            f"fusion_personality_label_{index}": direct_color_row(
                label, font8, widths8, codes8, 40
            )
            for index, label in enumerate(labels.personality)
        }
    )
    if len(output) != 15:
        raise ValueError("EVENT status bitmap inventory changed")
    return output


def _encode_mirror_record(
    text: str,
    codes16: Mapping[str, int],
    units: int,
    *,
    separator_newline: bool,
    optional_terminator: bool,
) -> bytes | None:
    lines = text.split("{n}")
    if not separator_newline and len(lines) != 1:
        raise ValueError(f"race mirror cannot contain a newline: {text!r}")
    words: list[int] = []
    for index, line in enumerate(lines):
        if index:
            words.append(0)
        try:
            words.extend(codes16[character] for character in line)
        except KeyError as error:
            raise ValueError(
                f"unsupported mirror FONT16 character {error.args[0]!r} in {text!r}"
            ) from error
    if len(words) < units or not optional_terminator:
        words.append(0x8000)
    if len(words) > units:
        return None
    words.extend([0] * (units - len(words)))
    return struct.pack(f">{units}H", *words)


def _mirror_data(
    races: list[str],
    affinities: list[str],
    codes16: Mapping[str, int],
) -> dict[str, bytes]:
    output: dict[str, bytes] = {}
    encoded = _encode_mirror_record(
        races[22],
        codes16,
        3,
        separator_newline=False,
        optional_terminator=True,
    )
    if encoded is None:
        raise ValueError("authored race mirror 22 exceeds three words")
    output["races_022"] = encoded

    affinity_indices = (1, 29, 51, 52, 60, 64, *range(66, 96))
    for index in affinity_indices:
        encoded = _encode_mirror_record(
            affinities[index],
            codes16,
            17,
            separator_newline=True,
            optional_terminator=False,
        )
        if encoded is None:
            raise ValueError(f"authored affinity mirror {index} exceeds 17 words")
        output[f"affinities_{index:03d}"] = encoded
    if len(output) != 37:
        raise ValueError("mature EVENT mirror inventory changed")
    return output


def _assembly(source: Path, address: int, symbols: Mapping[str, int]) -> Assembly:
    try:
        result = assemble_file(source, address, dict(symbols))
    except AssemblyError as error:
        raise ValueError(f"{source.relative_to(ENGINE_ROOT)}: {error}") from error
    if result.warnings:
        raise ValueError(
            f"{source.relative_to(ENGINE_ROOT)}: assembly warnings: {result.warnings}"
        )
    return result


def _source_paths(
    recipe: PatchRecipe,
    expected: tuple[str, ...],
) -> tuple[Path, ...]:
    actual = tuple(
        source.relative_to(ASSEMBLY_ROOT).as_posix()
        for source in recipe.replacement.sources
    )
    if actual != expected:
        raise ValueError(f"{recipe.group}/{recipe.name}: assembly sources changed")
    return recipe.replacement.sources


def _validate_name_mapper(
    codes8: Mapping[str, int],
    codes16: Mapping[str, int],
    names: Sequence[str],
) -> None:
    def expected_code(code: int) -> int | None:
        if code == codes8[" "]:
            return codes16[" "]
        if codes8["0"] <= code < codes8["s"]:
            return code - 63
        if codes8["s"] <= code <= codes8["z"]:
            return code - 150
        if code == codes8["-"]:
            return codes16["-"]
        if code == codes8["'"]:
            return codes16["'"]
        return None

    if any(not name or len(name) > 20 for name in names):
        raise ValueError("EVENT insert name is empty or exceeds 20 glyphs")
    for character in set("".join(names)):
        source = codes8.get(character)
        target = codes16.get(character)
        if source is None or target is None or expected_code(source) != target:
            raise ValueError(f"EVENT term mapper cannot convert {character!r}")


def _validate_status_name_mapper(
    codes8: Mapping[str, int],
    codes16: Mapping[str, int],
    names: Sequence[str],
) -> None:
    """Validate the exact FONT8-to-FONT16 map used by font16_from_font8.s."""

    punctuation = {
        213: 173,  # hyphen
        214: 175,  # colon
        217: 177,  # apostrophe
        229: 204,  # comma
    }

    def expected_code(code: int) -> int | None:
        if code == 63:
            return 267
        if 63 <= code < 118:
            return code - 63
        if 205 <= code < 213:
            return code - 150
        return punctuation.get(code)

    for character in set("".join(names)):
        source = codes8.get(character)
        target = codes16.get(character)
        if source is None or target is None or expected_code(source) != target:
            raise ValueError(f"EVENT status name mapper cannot convert {character!r}")


def _term_insert_payload(
    source: Path,
    address: int,
    data_links: Mapping[str, int],
    codes8: Mapping[str, int],
    codes16: Mapping[str, int],
    demon_names: list[str],
    character_names: list[str],
) -> tuple[bytes, Mapping[str, int]]:
    if len(demon_names) != DEMON_COUNT or len(character_names) < 3:
        raise ValueError("EVENT term inserts need 319 demons and three characters")
    _validate_name_mapper(codes8, codes16, (*demon_names, *character_names[:3]))

    def assemble_at(buffer: int) -> Assembly:
        return _assembly(
            source,
            address,
            {
                "CURRENT_DEMON_IDS": CURRENT_DEMON_IDS,
                "DEMON_COUNT": DEMON_COUNT,
                "NAME_OFFSETS": data_links["name_offsets"],
                "NAME_POOL": data_links["name_pool"],
                "RACE_COUNT": RACE_COUNT,
                "RACE_TABLE": data_links["race_table"],
                "RACE_ID_HELPER": RACE_ID_HELPER,
                "INSERT_STATE": INSERT_STATE,
                "INSERT_ACTIVE": INSERT_ACTIVE,
                "STREAM_PUSH": INSERT_STREAM_PUSH,
                "STREAM_POINTER": INSERT_STREAM_POINTER,
                "STREAM_STATUS": INSERT_STREAM_STATUS,
                "TEXT_FLAGS": TEXT_FLAGS,
                "STOCK_DEMON_INSERT": DEMON_INSERT_STOCK,
                "STOCK_RACE_INSERT": RACE_INSERT_STOCK,
                "INSERT_BUFFER": buffer,
                "NAME_LIMIT": 20,
                "FONT8_TAIL_FIRST": codes8["s"],
                "FONT8_TAIL_END": codes8["z"] + 1,
                "FONT8_TAIL_DELTA": 150,
                "FONT8_HYPHEN": codes8["-"],
                "FONT8_APOSTROPHE": codes8["'"],
                "FONT16_SPACE": codes16[" "],
                "FONT16_HYPHEN": codes16["-"],
                "FONT16_APOSTROPHE": codes16["'"],
                "TERMINATOR": 0x8000,
                "ACTIVE_STATUS": 0x7FFF,
            },
        )

    probe = assemble_at(address)
    buffer_address = (address + len(probe.data) + 3) & ~3
    code = assemble_at(buffer_address)
    if len(code.data) != len(probe.data):
        raise ValueError("EVENT term buffer address changed code size")
    payload = bytearray(code.data)
    payload.extend(bytes(buffer_address - address - len(payload)))
    payload.extend(bytes((20 + 1) * 2))
    labels = dict(code.labels)
    labels["insert_buffer"] = buffer_address
    return bytes(payload), MappingProxyType(labels)


def _character_handler(
    source: Path,
    data_links: Mapping[str, int],
    term_labels: Mapping[str, int],
) -> bytes:
    code = _assembly(
        source,
        CHARACTER_INSERT_STOCK,
        {
            "INSERT_STATE": INSERT_STATE,
            "CHARACTER_COUNT": 3,
            "CHARACTER_OFFSETS": data_links["name_offsets"] + DEMON_COUNT * 2,
            "NAME_POOL": data_links["name_pool"],
            "INSERT_BUFFER": term_labels["insert_buffer"],
            "NAME_LIMIT": 20,
            "NAME_COPY": term_labels["name_copy"],
            "NAME_CLEANUP": term_labels["name_cleanup"],
        },
    ).data
    capacity = CHARACTER_INSERT_END - CHARACTER_INSERT_STOCK
    if len(code) > capacity or (capacity - len(code)) % 2:
        raise ValueError("EVENT character insert exceeds its stock window")
    return code + bytes.fromhex("0009") * ((capacity - len(code)) // 2)


def _runtime_payload(
    runtime_recipe: PatchRecipe,
    character_recipe: PatchRecipe,
    widths8: bytes,
    codes8: Mapping[str, int],
    widths16: bytes,
    codes16: Mapping[str, int],
    font8: bytes,
    font16: bytes,
    races: list[str],
    affinities: list[str],
    demon_names: list[str],
    character_names: list[str],
    english_dvlname: bytes,
    english_magname: bytes,
    stock_charname: bytes,
    english_charname: bytes,
) -> RuntimeBuild:
    sources = _source_paths(
        runtime_recipe,
        (
            "facilities_status_ui/font16_vwf.s",
            "facilities_status_ui/font16_from_font8.s",
            "facilities_status_ui/skill_vwf.s",
            "facilities_status_ui/affinity_font8_vwf.s",
            "facilities_status_ui/status_skill_dispatcher.s",
            "facilities_status_ui/name_race_dispatcher.s",
            "facilities_status_ui/affinity_dispatcher.s",
            "facilities_status_ui/font8_surface_blitter.s",
            "facilities_status_ui/facility_name_drawers.s",
            "facilities_status_ui/event_term_inserts.s",
        ),
    )
    (character_source,) = _source_paths(
        character_recipe,
        ("facilities_status_ui/event_character_insert.s",),
    )
    english, data_links = _event_english_data(
        widths8,
        codes8,
        widths16,
        codes16,
        font8,
        font16,
        races,
        affinities,
        demon_names,
        character_names,
        english_dvlname,
        stock_charname,
        english_charname,
    )
    payload = bytearray(english)

    def append(source: Path, symbols: Mapping[str, int]) -> tuple[int, Assembly]:
        payload.extend(bytes((-(RUNTIME_ADDRESS + len(payload))) % 4))
        address = RUNTIME_ADDRESS + len(payload)
        code = _assembly(source, address, symbols)
        payload.extend(code.data)
        return address, code

    font16_vwf, _font16_code = append(
        sources[0],
        {
            "WIDTHS": data_links["widths16"],
            "END_MASK": 0x8000,
            "FONT_BITMAP": FONT16_BITMAP,
            "STOCK": FONT16_DRAWER,
        },
    )
    name_font16_vwf, _name_font16_code = append(
        sources[1],
        {
            "WIDTHS": data_links["compact_widths16"],
            "FONT_BITMAP": FONT16_BITMAP,
            "STOCK": FONT16_DRAWER,
        },
    )
    skill_vwf, _skill_code = append(
        sources[2],
        {
            "MAGIC_FIRST": MAGNAME_FIRST,
            "MAGIC_END": MAGNAME_END,
            "MAGIC_BASE": MAGNAME_BASE,
            "NAME_POINTER": MAGNAME_POINTER_OFFSET,
            "WIDTHS": data_links["widths8"],
            "FONT_BITMAP": FONT8_BITMAP,
            "STOCK": FONT12_DRAWER,
            "GLYPH": FONT8_GLYPH_DRAWER,
        },
    )
    affinity_vwf, _affinity_code = append(
        sources[3],
        {
            "WIDTHS": data_links["widths8"],
            "FONT_BITMAP": FONT8_BITMAP,
            "GLYPH": FONT8_GLYPH_DRAWER,
            "MAX_WIDTH": AFFINITY_SURFACE_WIDTH,
            "SPACE_CODE": codes8[" "],
            "COLON_CODE": codes8[":"],
            "COMMA_CODE": codes8[","],
        },
    )
    ambiguous = _ambiguous_magname_fallbacks(english_magname)
    status_symbols = {
        "MAGIC_FIRST": MAGNAME_FIRST,
        "SKILL_VWF": skill_vwf,
        "STOCK": FONT12_DRAWER,
    }
    for index, key in enumerate(ambiguous):
        status_symbols[f"AMBIG{index}_HI"] = int.from_bytes(key[:4], "big")
        status_symbols[f"AMBIG{index}_LO"] = int.from_bytes(key[4:], "big")
    status_skill, _status_skill_code = append(sources[4], status_symbols)
    name_race, _name_race_code = append(
        sources[5],
        {
            "RACE_SOURCE": RACE_SOURCE,
            "RACE_TABLE": data_links["race_table"],
            "PARTY_TYPE": CURRENT_PARTY_TYPE,
            "CURRENT_NAME_PTR": CURRENT_NAME_PTR,
            "PLAYER_NAME": PLAYER_STATUS_NAME,
            "NAME_LOOKUP": data_links["name_lookup"],
            "NAME_COUNT": data_links["name_count"],
            "FONT16_VWF": font16_vwf,
            "NAME_VWF": name_font16_vwf,
            "STOCK": FONT16_DRAWER,
        },
    )
    affinity, _affinity_dispatch_code = append(
        sources[6],
        {
            "SELECTOR": AFFINITY_SELECTOR,
            "SOURCE": AFFINITY_SOURCE,
            "TABLE": data_links["affinity_table"],
            "FONT8_VWF": affinity_vwf,
            "STOCK": FONT16_DRAWER,
        },
    )
    bar_glyph, _bar_glyph_code = append(
        sources[7],
        {"FONT8": FONT8_BITMAP},
    )

    facility_address = RUNTIME_ADDRESS + len(payload)
    facility = _assembly(
        sources[8],
        facility_address,
        {
            "WIDTHS": data_links["widths8"],
            "NAME_LOOKUP": data_links["name_lookup"],
            "NAME_COUNT": data_links["name_count"],
            "DVL_SOURCE": BAR_DVL_SOURCE,
            "DVL_SOURCE_END": BAR_DVL_SOURCE_END,
            "CHAR_SOURCE": BAR_CHAR_SOURCE,
            "CHAR_SOURCE_END": BAR_CHAR_SOURCE_END,
            "PARTY_SOURCE_PTR": BAR_PARTY_SOURCE_PTR,
            "PLAYER_CODENAME": CODENAME_BYTES,
            "DVL_OFFSETS": data_links["name_offsets"],
            "CHAR_OFFSETS": data_links["name_offsets"] + DEMON_COUNT * 2,
            "NAME_POOL": data_links["name_pool"],
            "DRINK_OFFSETS": data_links["drink_offsets"],
            "DRINK_POOL": data_links["drink_pool"],
            "TALK_OFFSETS": data_links["talk_offsets"],
            "TALK_POOL": data_links["talk_pool"],
            "HEALING_ALL": data_links["healing_all"],
            "HEALING_SURFACE_PTR": HEALING_SURFACE_PTR,
            "HEALING_SURFACE_WIDTH": HEALING_SURFACE_WIDTH,
            "HEALING_CHAR_SOURCE_PTR": HEALING_CHAR_SOURCE_PTR,
            "HEALING_DVL_SOURCE_PTR": HEALING_DVL_SOURCE_PTR,
            "SURFACE_PTR": BAR_SURFACE_PTR,
            "GLYPH": bar_glyph,
        },
    )
    payload.extend(facility.data)

    payload.extend(bytes((-(RUNTIME_ADDRESS + len(payload))) % 4))
    term_address = RUNTIME_ADDRESS + len(payload)
    term_payload, term_labels = _term_insert_payload(
        sources[9],
        term_address,
        data_links,
        codes8,
        codes16,
        demon_names,
        character_names,
    )
    payload.extend(term_payload)
    character_handler = _character_handler(
        character_source,
        data_links,
        term_labels,
    )

    used_size = len(payload)
    if RUNTIME_ADDRESS + used_size > RUNTIME_LIMIT:
        raise ValueError(
            "EVENT facilities/status runtime exceeds its verified cave by "
            f"{RUNTIME_ADDRESS + used_size - RUNTIME_LIMIT:#x} bytes"
        )
    if len(runtime_recipe.expected) != RUNTIME_CAPACITY:
        raise ValueError("EVENT facilities/status runtime recipe changed capacity")
    if used_size > len(runtime_recipe.expected):
        raise ValueError(
            f"EVENT facilities/status runtime uses {used_size}/"
            f"{len(runtime_recipe.expected)} configured bytes"
        )

    links = {
        "fusion_name_race_drawer": name_race,
        "fusion_skill_name_drawer": skill_vwf,
        "fusion_status_skill_drawer": status_skill,
        "fusion_affinity_drawer": affinity,
        "event_dialogue_demon_name_insert": term_labels[
            "dialogue_demon_name_insert"
        ],
        "event_dialogue_race_insert": term_labels["dialogue_race_insert"],
        "bar_drink_name_drawer": facility.labels["bar_drink_name_drawer"],
        "bar_talk_role_drawer": facility.labels["bar_talk_role_drawer"],
        "bar_status_name_glyph": facility.labels["bar_status_name_glyph"],
        "bar_party_name_glyph": facility.labels["bar_party_name_glyph"],
        "healing_all_drawer": facility.labels["healing_all_drawer"],
        "healing_name_drawer": facility.labels["healing_name_drawer"],
    }
    arena = RuntimeArena(
        "event_facilities_status",
        RUNTIME_ADDRESS,
        used_size,
        RUNTIME_CAPACITY,
    )
    return RuntimeBuild(
        bytes(payload).ljust(RUNTIME_CAPACITY, b"\0"),
        character_handler,
        MappingProxyType({}),
        MappingProxyType(links),
        arena,
    )


def _build_components(
    config: PatchRecipeConfiguration,
    base: bytes,
    stock_charname: bytes,
    stock_font16: bytes,
    english_dvlname: bytes,
    english_magname: bytes,
) -> tuple[dict[str, bytes], RuntimeBuild]:
    metrics8 = FontMetrics.load(FONT8_METRICS_PATH)
    widths8, codes8 = font8_tables(metrics8)
    widths16, codes16 = load_font16_metrics(FONT16_METRICS_PATH)
    font8 = FONT8_PATH.read_bytes()
    font16 = FONT16_PATH.read_bytes()
    if len(font8) != 256 * 8 or len(font16) != 1872 * 32:
        raise ValueError("EVENT facilities/status font geometry changed")

    races, affinities, demon_names, character_names = _status_terms()
    english_charname = _built_charname(stock_charname, character_names, metrics8)
    generated = _layout_data(
        base,
        font8,
        stock_font16,
        widths8,
        codes8,
    )
    generated.update(_mirror_data(races, affinities, codes16))
    generated["facility_revive_status_aliases"] = _facility_alias_data(
        load_stock_latin_codes(FONT8_METRICS_PATH)
    )

    recipes = {recipe.name: recipe for recipe in config.patches[TARGET]}
    if len(recipes) != len(config.patches[TARGET]):
        raise ValueError("facilities/status patch names must be unique")
    try:
        runtime_recipe = recipes["fusion_status_runtime"]
        character_recipe = recipes["event_dialogue_character_name_insert"]
    except KeyError as error:
        raise ValueError("facilities/status config is missing an assembly owner") from error
    runtime = _runtime_payload(
        runtime_recipe,
        character_recipe,
        widths8,
        codes8,
        widths16,
        codes16,
        font8,
        font16,
        races,
        affinities,
        demon_names,
        character_names,
        english_dvlname,
        english_magname,
        stock_charname,
        english_charname,
    )
    return generated, runtime


def _bind_patches(
    config: PatchRecipeConfiguration,
    base: bytes,
    stock_charname: bytes,
    stock_font16: bytes,
    english_dvlname: bytes,
    english_magname: bytes,
) -> tuple[tuple[Patch, ...], RuntimeBuild]:
    generated, runtime = _build_components(
        config,
        base,
        stock_charname,
        stock_font16,
        english_dvlname,
        english_magname,
    )
    output: list[Patch] = []
    generated_seen: set[str] = set()
    assembly_seen: set[str] = set()
    for recipe in config.patches[TARGET]:
        expected = resolve_recipe_expected(recipe, base, LOAD_ADDRESS)
        replacement_recipe = recipe.replacement
        if replacement_recipe.kind == "assembly":
            if recipe.name == "fusion_status_runtime":
                replacement = runtime.data
            elif recipe.name == "event_dialogue_character_name_insert":
                replacement = runtime.character_handler
            else:
                raise ValueError(
                    f"{recipe.group}/{recipe.name}: unknown assembly owner"
                )
            assembly_seen.add(recipe.name)
        elif replacement_recipe.kind == "generated":
            if replacement_recipe.generator != "facilities_status_data":
                raise ValueError(
                    f"{recipe.name}: unknown facilities/status data generator"
                )
            try:
                replacement = generated[recipe.name]
            except KeyError as error:
                raise ValueError(
                    f"facilities/status data generator did not own {recipe.name}"
                ) from error
            generated_seen.add(recipe.name)
        elif replacement_recipe.kind == "linked_pointer":
            link = replacement_recipe.link
            assert link is not None
            try:
                replacement = struct.pack(">I", runtime.links[link])
            except KeyError as error:
                raise ValueError(
                    f"{recipe.group}/{recipe.name}: unknown runtime link {link}"
                ) from error
        else:
            raise ValueError(
                f"{recipe.group}/{recipe.name}: unsupported replacement kind "
                f"{replacement_recipe.kind}"
            )
        if len(replacement) != len(expected):
            raise ValueError(
                f"{recipe.group}/{recipe.name}: generated {len(replacement)} bytes, "
                f"expected {len(expected)}"
            )
        output.append(
            Patch(
                recipe.group,
                recipe.name,
                recipe.address,
                expected,
                replacement,
            )
        )

    if assembly_seen != {
        "fusion_status_runtime",
        "event_dialogue_character_name_insert",
    }:
        raise ValueError("facilities/status assembly ownership differs from config")
    unused_generated = set(generated) - generated_seen
    if unused_generated:
        raise ValueError(
            "facilities/status data generator has no configured owner: "
            + ", ".join(sorted(unused_generated))
        )
    if len(output) != 72:
        raise ValueError(f"facilities/status patch inventory changed: {len(output)}/72")
    if FUSION_CONFIRMATION_PATCH_NAMES & {patch.name for patch in output}:
        raise ValueError("facilities/status duplicates Fusion confirmation ownership")
    for patch in output:
        patch_end = patch.address + len(patch.replacement)
        for owner, address, size in FUSION_CONFIRMATION_SPANS:
            if patch.address < address + size and address < patch_end:
                raise ValueError(
                    f"facilities/status {patch.name} overlaps Fusion confirmation "
                    f"{owner}"
                )
    capability_counts: dict[str, int] = {}
    for patch in output:
        capability_counts[patch.group] = capability_counts.get(patch.group, 0) + 1
    if capability_counts != {
        "fusion.status_ui": 20,
        "event.term_inserts": 3,
        "facilities.command_ui": 1,
        "bar.status_ui": 4,
        "healer.status_ui": 7,
        "event.fixed_text_compatibility": 37,
    }:
        raise ValueError(
            f"facilities/status capability inventory changed: {capability_counts}"
        )
    return tuple(output), runtime


def build_facilities_status_ui(base: bytes) -> FacilitiesStatusUiBuild:
    """Apply the EVENT facility/status stage to equipment output."""
    _validate_surfaces()
    config = _configuration()
    stock_event, stock_dvlname, stock_charname, stock_font16 = _source_assets()
    english_dvlname, english_magname = _validate_inputs(
        config,
        base,
        stock_event,
        stock_dvlname,
        stock_charname,
        stock_font16,
    )
    patches, runtime = _bind_patches(
        config,
        base,
        stock_charname,
        stock_font16,
        english_dvlname,
        english_magname,
    )
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
    return FacilitiesStatusUiBuild(
        apply_patches(base, LOAD_ADDRESS, patches),
        patches,
        ASSET_FILES,
        assembly_files,
        RUNTIME_INPUT_FILES,
        MappingProxyType(
            {
                f"game:{TARGET}": _sha256(stock_event),
                "game:DVLNAME.DAT": _sha256(stock_dvlname),
                "game:CHARNAME.DAT": _sha256(stock_charname),
                "game:FONT16.FON": _sha256(stock_font16),
            }
        ),
        runtime.arena.used_size,
        runtime.arena.capacity,
        (runtime.arena,),
    )


__all__ = (
    "BUILD_PATH",
    "CONFIG_PATH",
    "OUTPUT_PATH",
    "TARGET",
    "FacilitiesStatusUiBuild",
    "RuntimeArena",
    "build_facilities_status_ui",
)
