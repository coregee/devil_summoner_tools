"""Compose MSGR.COF's portrait-scene event window from authored inputs."""

from __future__ import annotations

import hashlib
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
    resolve_recipe_expected,
)
from engine.core.patching import Patch, apply_patches
from engine.core.sh2 import AssemblyError, assemble
from engine.shared.event_window import (
    EVENT_BANK_NAMES,
    assemble_checked,
    build_absolute_jump,
    build_advance_payload,
    build_menu_payload,
    build_packed_fetch_payload,
    build_two_glyph_payload,
    file_sha256,
    font12_widths,
    font16_layout,
    font_signature,
    validate_event_text_build,
)
from engine.shared.font8 import font8_tables
from engine.shared.player_name_adapters import (
    PlayerNameAdapterSpec,
    build_player_name_assembly,
    pointer_contract,
)
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
from text.util.event_codec import load_event_dictionary
from text.util.event_repack import FontMetrics
from text.util.surfaces import load_surfaces


ENGINE_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = ENGINE_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "portrait_scene_ui.json"
GENERATED_ROOT = ENGINE_ROOT / "generated" / "game"
OUTPUT_PATH = GENERATED_ROOT / "MSGR.COF"
BUILD_PATH = GENERATED_ROOT / "portrait_scene_ui_build.json"
TARGET = "MSGR.COF"
LOAD_ADDRESS = 0x06060000

TEXT_ROOT = SATURN_ROOT / "text"
TEXT_GENERATED_ROOT = TEXT_ROOT / "generated" / "game"
TEXT_BUILD_PATH = TEXT_GENERATED_ROOT / "event_build.json"
CODEC_PATH = TEXT_ROOT / "config" / "event_codec.json"
SURFACES_PATH = TEXT_ROOT / "config" / "surfaces.json"
FONT_ROOT = SATURN_ROOT / "font" / "generated" / "game"
FONT16_PATH = FONT_ROOT / "FONT16.FON"
FONT16_METRICS_PATH = FONT_ROOT / "FONT16_metrics.json"
FONT12_PATH = FONT_ROOT / "FONT12.FON"
FONT12_METRICS_PATH = FONT_ROOT / "FONT12_metrics.json"
FONT8_PATH = FONT_ROOT / "FONT8.FON"
FONT8_METRICS_PATH = FONT_ROOT / "FONT8_metrics.json"

DEMON_ASSET_PATH = ASSET_ROOT / "demons.json"
CHARACTER_ASSET_PATH = ASSET_ROOT / "characters.json"
RACE_ASSET_PATH = ASSET_ROOT / "races.json"
DEBUG_ASSET_PATH = ASSET_ROOT / "system" / "debug.json"
ASSET_FILES = (
    DEMON_ASSET_PATH,
    CHARACTER_ASSET_PATH,
    RACE_ASSET_PATH,
    DEBUG_ASSET_PATH,
)
DEMON_BINDING_PATH = BINDING_ROOT / "demons.json"
CHARACTER_BINDING_PATH = BINDING_ROOT / "characters.json"
RACE_BINDING_PATH = BINDING_ROOT / "races.json"
DEBUG_BINDING_PATH = BINDING_ROOT / "portrait_scene_debug.json"
BINDING_FILES = (
    DEMON_BINDING_PATH,
    CHARACTER_BINDING_PATH,
    RACE_BINDING_PATH,
    DEBUG_BINDING_PATH,
)
CORPUS_FILES = tuple(
    CORPUS_ROOT / relative
    for relative in (
        "compendium/addressed/race_names.json",
        "compendium/fixed/demon_names.json",
        "game/addressed/da3d_analyze.json",
        "game/addressed/msgr_debug_ascii.json",
        "game/addressed/normcom_tables.json",
        "game/eve/shopsmp.json",
        "game/fixed/charname.json",
        "game/fixed/dvlname.json",
    )
)
EVENT_BANK_PATHS = tuple(TEXT_GENERATED_ROOT / name for name in EVENT_BANK_NAMES)
RUNTIME_INPUT_FILES = (
    FONT16_PATH,
    FONT16_METRICS_PATH,
    FONT12_PATH,
    FONT12_METRICS_PATH,
    FONT8_PATH,
    FONT8_METRICS_PATH,
    CODEC_PATH,
    TEXT_BUILD_PATH,
    *EVENT_BANK_PATHS,
    SURFACES_PATH,
    SATURN_ROOT / "rom" / "discs.json",
    *BINDING_FILES,
    *CORPUS_FILES,
    ENGINE_ROOT / "shared" / "event_window.py",
    ENGINE_ROOT / "shared" / "player_name_adapters.py",
    ENGINE_ROOT / "shared" / "player_names.py",
)

DIALOGUE_ARENA = 0x06060400
DIALOGUE_CAPACITY = 0x4C00
TERM_ARENA = 0x06065000
TERM_CAPACITY = 0x1500
RAW_MENU_ARENA = 0x0606C63C
RAW_MENU_CAPACITY = 0x60
DEMON_COUNT = 319
CHARACTER_COUNT = 6
RACE_COUNT = 43
FONT16_SPACE = 267

RECIPE_CONTRACT = (
    (
        "msgr.dialogue_vwf",
        "dialogue_two_glyph_pacing_cave",
        0x06060BE4,
        "assembly",
    ),
    (
        "msgr.dialogue_vwf",
        "dialogue_update_pointer_0606beac",
        0x0606BEAC,
        "linked_pointer",
    ),
    (
        "msgr.dialogue_vwf",
        "dialogue_update_pointer_0606bf78",
        0x0606BF78,
        "linked_pointer",
    ),
    ("msgr.dialogue_vwf", "dialogue_two_glyph_tail", 0x0606EC8C, "assembly"),
    ("msgr.dialogue_vwf", "advance_cave", 0x06060400, "assembly"),
    ("msgr.dialogue_vwf", "packed_fetch_cave", 0x060605F8, "assembly"),
    ("msgr.dialogue_vwf", "subpixel_blitter_cave", 0x06060890, "assembly"),
    ("msgr.dialogue_vwf", "menu_glyph_cave", 0x060609B0, "assembly"),
    ("msgr.dialogue_vwf", "fetch_site_1", 0x0606EC14, "assembly"),
    ("msgr.dialogue_vwf", "fetch_site_2", 0x0606EC2C, "assembly"),
    ("msgr.dialogue_vwf", "advance_pointer", 0x0606ED48, "pointer"),
    (
        "msgr.dialogue_vwf",
        "dialogue_blitter_pointer",
        0x0606ED68,
        "linked_pointer",
    ),
    ("msgr.dialogue_vwf", "menu_blitter_pointer", 0x0606C7A8, "pointer"),
    ("msgr.dialogue_vwf", "menu_advance", 0x0606C75A, "instruction"),
    ("msgr.term_inserts", "dialogue_full_term_runtime", 0x06065000, "assembly"),
    (
        "msgr.term_inserts",
        "dialogue_character_name_insert",
        0x0606F17C,
        "linked_pointer",
    ),
    (
        "msgr.term_inserts",
        "dialogue_demon_name_insert",
        0x0606F188,
        "linked_pointer",
    ),
    (
        "msgr.term_inserts",
        "dialogue_race_insert",
        0x0606F198,
        "linked_pointer",
    ),
    (
        "msgr.player_name_adapters",
        "first_insert_pointer",
        0x0606F600,
        "pointer",
    ),
    (
        "msgr.player_name_adapters",
        "first_terminator_stamp",
        0x0606F5C8,
        "instruction",
    ),
    (
        "msgr.player_name_adapters",
        "last_insert_pointer",
        0x0606F674,
        "pointer",
    ),
    (
        "msgr.player_name_adapters",
        "last_terminator_stamp",
        0x0606F63E,
        "instruction",
    ),
    (
        "msgr.player_name_adapters",
        "city_insert_pointer",
        0x0606F6E8,
        "pointer",
    ),
    (
        "msgr.player_name_adapters",
        "city_terminator_stamp",
        0x0606F6B2,
        "instruction",
    ),
    (
        "msgr.player_name_adapters",
        "ward_insert_pointer",
        0x0606F75C,
        "pointer",
    ),
    (
        "msgr.player_name_adapters",
        "ward_terminator_stamp",
        0x0606F726,
        "instruction",
    ),
    (
        "msgr.player_name_adapters",
        "codename_skip_copy",
        0x0606F4F8,
        "assembly",
    ),
    (
        "msgr.player_name_adapters",
        "codename_insert_pointer",
        0x0606F580,
        "pointer",
    ),
    (
        "msgr.player_name_adapters",
        "raw_menu_name_renderer",
        0x0606C63C,
        "assembly",
    ),
    (
        "msgr.player_name_adapters",
        "raw_menu_first_insert_pointer",
        0x0606C79C,
        "pointer",
    ),
    (
        "msgr.player_name_adapters",
        "raw_menu_last_insert_pointer",
        0x0606C7A4,
        "pointer",
    ),
    (
        "msgr.player_name_adapters",
        "raw_menu_name_result_0606c6ee",
        0x0606C6EE,
        "assembly",
    ),
    (
        "msgr.player_name_adapters",
        "raw_menu_name_result_0606c720",
        0x0606C720,
        "assembly",
    ),
    (
        "msgr.fixed_text_compatibility",
        "race_uma_mirror",
        0x06078E40,
        "generated",
    ),
    ("msgr.debug_messages", "debug_name_id_error", 0x0606AE04, "generated"),
    ("msgr.debug_messages", "debug_load_error", 0x0606AE14, "generated"),
    (
        "msgr.debug_messages",
        "debug_menu_count_over",
        0x0606C1B4,
        "generated",
    ),
)
FIXED_POINTER_CONTRACT = MappingProxyType(
    {
        "advance_pointer": DIALOGUE_ARENA,
        "menu_blitter_pointer": 0x060609B0,
    }
)
ASSEMBLY_RECIPE_CONTRACT = MappingProxyType(
    {
        "dialogue_two_glyph_pacing_cave": (
            "shared/event_window/two_glyph_pacing.s",
        ),
        "dialogue_two_glyph_tail": ("shared/event_window/absolute_jump.s",),
        "advance_cave": ("shared/event_window/advance.s",),
        "packed_fetch_cave": ("shared/event_window/packed_fetch.s",),
        "subpixel_blitter_cave": ("font16_subpixel_blitter.s",),
        "menu_glyph_cave": ("shared/event_window/menu_glyph.s",),
        "fetch_site_1": ("shared/event_window/absolute_jump.s",),
        "fetch_site_2": ("shared/event_window/absolute_jump.s",),
        "dialogue_full_term_runtime": (
            "shared/event_window/full_term_inserts.s",
            "shared/event_window/character_term_insert.s",
        ),
        "codename_skip_copy": (
            "shared/player_name_inserts/codename_skip.s",
        ),
        "raw_menu_name_renderer": (
            "shared/player_name_inserts/raw_menu_inserts.s",
        ),
        "raw_menu_name_result_0606c6ee": (
            "shared/player_name_inserts/raw_menu_result.s",
        ),
        "raw_menu_name_result_0606c720": (
            "shared/player_name_inserts/raw_menu_result.s",
        ),
    }
)
LINKED_POINTER_RECIPE_CONTRACT = MappingProxyType(
    {
        "dialogue_update_pointer_0606beac": "two_glyph_update",
        "dialogue_update_pointer_0606bf78": "two_glyph_update",
        "dialogue_blitter_pointer": "two_glyph_blit",
        "dialogue_character_name_insert": "dialogue_character_name_insert",
        "dialogue_demon_name_insert": "dialogue_demon_name_insert",
        "dialogue_race_insert": "dialogue_race_insert",
    }
)
INSTRUCTION_RECIPE_CONTRACT = MappingProxyType(
    {
        "menu_advance": "mov r0, r1",
        "first_terminator_stamp": "nop",
        "last_terminator_stamp": "nop",
        "city_terminator_stamp": "nop",
        "ward_terminator_stamp": "nop",
    }
)
GENERATED_RECIPE_CONTRACT = MappingProxyType(
    {
        "race_uma_mirror": "portrait_scene_data",
        "debug_name_id_error": "portrait_scene_data",
        "debug_load_error": "portrait_scene_data",
        "debug_menu_count_over": "portrait_scene_data",
    }
)


@dataclass(frozen=True, slots=True)
class RuntimeArena:
    name: str
    address: int
    used_size: int
    capacity: int


@dataclass(frozen=True, slots=True)
class RuntimeBuild:
    assembly: Mapping[str, bytes]
    generated: Mapping[str, bytes]
    links: Mapping[str, int]
    arenas: tuple[RuntimeArena, ...]


@dataclass(frozen=True, slots=True)
class PortraitSceneUiBuild:
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


def _configuration() -> PatchRecipeConfiguration:
    return load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="portrait_scene.ui",
        target_names={TARGET},
        input_names={
            "font16_metrics_sha256",
            "font12_metrics_sha256",
            "font8_metrics_sha256",
            "font16_font_sha256",
            "font12_font_sha256",
            "font8_font_sha256",
            "event_runtime_table_sha256",
        },
    )


def _stock_source() -> bytes:
    catalog = load_catalog()
    try:
        game = catalog["game"]
    except KeyError as error:
        raise ValueError("disc catalog has no game source") from error
    validated = validate_source(game)
    return read_source_files(validated, (TARGET,))[TARGET]


def _validate_surfaces() -> None:
    surfaces = load_surfaces()
    dialogue = surfaces.surface("event.dialogue").en
    if (
        dialogue.font != "font16"
        or dialogue.rows != 3
        or dialogue.width.unit != "pixels"
        or dialogue.width.value != 300
    ):
        raise ValueError("portrait dialogue requires font16, three rows, and 300px")
    debug = surfaces.surface("portrait_scene.debug_message").en
    if (
        debug.font is not None
        or debug.rows != 1
        or debug.width.unit != "glyph_cells"
        or debug.width.value != 64
    ):
        raise ValueError("portrait debug text requires one 64-cell embedded-glyph row")


def _validate_inputs(
    config: PatchRecipeConfiguration,
    stock: bytes,
    dictionary: bytes,
) -> None:
    target = config.targets[TARGET]
    if target.load_address != LOAD_ADDRESS or len(stock) != target.size:
        raise ValueError("MSGR.COF portrait-scene composition target changed")
    if _sha256(stock) != target.stock_sha256:
        raise ValueError("stock MSGR.COF does not match the patch target")
    actual = {
        "font16_metrics_sha256": file_sha256(FONT16_METRICS_PATH),
        "font12_metrics_sha256": file_sha256(FONT12_METRICS_PATH),
        "font8_metrics_sha256": file_sha256(FONT8_METRICS_PATH),
        "font16_font_sha256": file_sha256(FONT16_PATH),
        "font12_font_sha256": file_sha256(FONT12_PATH),
        "font8_font_sha256": file_sha256(FONT8_PATH),
        "event_runtime_table_sha256": _sha256(dictionary),
    }
    for name, expected in config.inputs.items():
        if actual[name] != expected:
            raise ValueError(
                f"portrait-scene {name} expected SHA-256 {expected}, "
                f"found {actual[name]}"
            )
    validate_event_text_build(
        TEXT_BUILD_PATH,
        TEXT_GENERATED_ROOT,
        file_sha256(CODEC_PATH),
        actual["event_runtime_table_sha256"],
        actual["font16_metrics_sha256"],
    )


def _recipe_map(config: PatchRecipeConfiguration) -> Mapping[str, PatchRecipe]:
    recipes = config.patches[TARGET]
    result = {recipe.name: recipe for recipe in recipes}
    actual = tuple(
        (recipe.group, recipe.name, recipe.address, recipe.replacement.kind)
        for recipe in recipes
    )
    if len(result) != len(recipes) or actual != RECIPE_CONTRACT:
        raise ValueError("portrait-scene ordered patch inventory changed")
    pointer_recipes = {**pointer_contract(), **FIXED_POINTER_CONTRACT}
    contracts: Mapping[str, Mapping[str, object]] = {
        "assembly": ASSEMBLY_RECIPE_CONTRACT,
        "linked_pointer": LINKED_POINTER_RECIPE_CONTRACT,
        "pointer": pointer_recipes,
        "instruction": INSTRUCTION_RECIPE_CONTRACT,
        "generated": GENERATED_RECIPE_CONTRACT,
    }
    for recipe in recipes:
        replacement = recipe.replacement
        if replacement.kind == "assembly":
            semantic: object = tuple(
                path.relative_to(ASSEMBLY_ROOT).as_posix()
                for path in replacement.sources
            )
        elif replacement.kind == "linked_pointer":
            semantic = replacement.link
        elif replacement.kind == "pointer":
            semantic = replacement.pointer
        elif replacement.kind == "instruction":
            semantic = replacement.instruction
        elif replacement.kind == "generated":
            semantic = replacement.generator
        else:
            raise ValueError("portrait-scene replacement kind changed")
        try:
            expected = contracts[replacement.kind][recipe.name]
        except KeyError as error:
            raise ValueError("portrait-scene replacement inventory changed") from error
        if semantic != expected:
            raise ValueError(
                f"portrait-scene replacement contract changed for {recipe.name}"
            )
    return MappingProxyType(result)


def _only_source(recipe: PatchRecipe, expected: str) -> Path:
    sources = recipe.replacement.sources
    if (
        len(sources) != 1
        or sources[0].relative_to(ASSEMBLY_ROOT).as_posix() != expected
    ):
        raise ValueError(f"{recipe.group}/{recipe.name}: assembly source changed")
    return sources[0]


def _font_codes(metrics: FontMetrics) -> dict[str, int]:
    output: dict[str, int] = {}
    for glyph in metrics.glyphs:
        for text in (glyph.text, *glyph.aliases):
            if len(text) == 1:
                output.setdefault(text, glyph.code)
    return output


def _bound_terms() -> tuple[
    tuple[str, ...], tuple[str, ...], tuple[str, ...], Mapping[str, str]
]:
    physical = load_physical_record_files(CORPUS_FILES)
    binding_specs = (
        (DEMON_BINDING_PATH, "demons.json"),
        (CHARACTER_BINDING_PATH, "characters.json"),
        (RACE_BINDING_PATH, "races.json"),
        (DEBUG_BINDING_PATH, "system/debug.json"),
    )
    bindings = {}
    for path, asset in binding_specs:
        binding = load_binding(path, physical_records=physical)
        if binding.asset.as_posix() != asset:
            raise ValueError(f"portrait-scene binding owner changed: {path}")
        bindings[path] = binding

    demon_ids = tuple(
        f"game.dvlname.o{index * 8:06x}.text" for index in range(DEMON_COUNT)
    )
    character_ids = tuple(
        f"game.charname.o{index * 8:06x}.text" for index in range(CHARACTER_COUNT)
    )
    race_ids = tuple(
        f"game.normcom_tables.races.r{index:04d}" for index in range(RACE_COUNT)
    )
    debug_ids = (
        "game.msgr_debug_ascii.o00ae04",
        "game.msgr_debug_ascii.o00ae14",
        "game.msgr_debug_ascii.o00c1b4",
    )
    inventories = (
        (DEMON_BINDING_PATH, "game.dvlname.", set(demon_ids)),
        (CHARACTER_BINDING_PATH, "game.charname.", set(character_ids)),
        (RACE_BINDING_PATH, "game.normcom_tables.races.", set(race_ids)),
        (DEBUG_BINDING_PATH, "game.msgr_debug_ascii.", set(debug_ids)),
    )
    for path, prefix, expected in inventories:
        actual = {
            record for record in bindings[path].records if record.startswith(prefix)
        }
        if actual != expected:
            raise ValueError(
                f"portrait-scene physical inventory changed for {path.name}"
            )

    def resolve(ids: tuple[str, ...], prefix: str, binding: Path) -> tuple[str, ...]:
        values = load_bound_translations(
            (prefix,),
            required_ids=set(ids),
            binding_paths=(binding,),
            physical_records=physical,
        )
        if set(values) != set(ids):
            raise ValueError(
                f"portrait-scene binding coverage changed for {binding.name}"
            )
        return tuple(values[physical_id] for physical_id in ids)

    demons = resolve(demon_ids, "game.dvlname.", DEMON_BINDING_PATH)
    characters = resolve(character_ids, "game.charname.", CHARACTER_BINDING_PATH)
    races = resolve(race_ids, "game.normcom_tables.races.", RACE_BINDING_PATH)
    debug_values = load_bound_translations(
        ("game.msgr_debug_ascii.",),
        required_ids=set(debug_ids),
        binding_paths=(DEBUG_BINDING_PATH,),
        physical_records=physical,
    )
    return demons, characters, races, debug_values


def _dialogue_runtime(
    recipes: Mapping[str, PatchRecipe],
    metrics16: FontMetrics,
    metrics12: FontMetrics,
    dictionary: bytes,
) -> tuple[Mapping[str, bytes], Mapping[str, int], int]:
    widths12 = font12_widths(metrics12, space_code=FONT16_SPACE)
    code_limit, width_offset = font16_layout(FONT16_METRICS_PATH)
    signature_offset, signature_value = font_signature(FONT12_PATH, FONT16_PATH)

    pacing_recipe = recipes["dialogue_two_glyph_pacing_cave"]
    pacing = build_two_glyph_payload(
        _only_source(pacing_recipe, "shared/event_window/two_glyph_pacing.s"),
        pacing_recipe.address,
        original_update=0x0606EBE4,
        visible_blitter=0x06060890,
        tail_continue=0x0606EC9C,
        context="MSGR two-glyph pacing",
    )
    links = {
        "two_glyph_update": pacing.labels["two_glyph_update"],
        "two_glyph_blit": pacing.labels["two_glyph_blit"],
    }

    advance_recipe = recipes["advance_cave"]
    advance = build_advance_payload(
        _only_source(advance_recipe, "shared/event_window/advance.s"),
        advance_recipe.address,
        {
            "TEXT_ADVANCE": 0x06079594,
            "RIGHT_MARGIN": 0x06079AA4,
            "FONT16_CODE_LIMIT": code_limit,
            "FONT_MODE": 0x060217FC,
            "FONT16_POINTER": 0x06075E88,
            "FONT12_SIGNATURE_OFFSET": signature_offset,
            "FONT12_SIGNATURE_VALUE": signature_value,
            "FONT16_WIDTH_OFFSET": width_offset,
            "FONT12_CODE_LIMIT": len(widths12),
            "TEXT_RIGHT_EDGE": 310,
            "CURSOR_X": 0x06079AA8,
            "STOCK_ADVANCE": 0x0606EEB0,
            "TEXT_LEFT_MARGIN": 10,
        },
        widths12,
        "MSGR dialogue advance",
    )
    fetch_recipe = recipes["packed_fetch_cave"]
    fetch = build_packed_fetch_payload(
        _only_source(fetch_recipe, "shared/event_window/packed_fetch.s"),
        fetch_recipe.address,
        dictionary,
        return_code=0x0606EC38,
        return_zero=0x0606EC20,
        context="MSGR packed fetch",
    )
    blitter_recipe = recipes["subpixel_blitter_cave"]
    blitter = assemble_checked(
        _only_source(blitter_recipe, "font16_subpixel_blitter.s"),
        blitter_recipe.address,
        {
            "FONT16_POINTER": 0x06075E88,
            "RIGHT_MARGIN": 0x06079AA4,
            "FRAMEBUFFER_POINTER": 0x06079568,
            "TEXT_COLOR": 0x0607A8C4,
            "LINE_HEIGHT": 0x06079598,
            "PATTERN_LUT": 0x0606EAA0,
            "MASK_LUT": 0x0606EAC0,
        },
        "MSGR subpixel blitter",
    ).data
    menu_recipe = recipes["menu_glyph_cave"]
    menu = build_menu_payload(
        _only_source(menu_recipe, "shared/event_window/menu_glyph.s"),
        menu_recipe.address,
        metrics16,
        widths12,
        {
            "BLITTER": blitter_recipe.address,
            "FONT16_POINTER": 0x06075E88,
            "FONT12_SIGNATURE_OFFSET": signature_offset,
            "FONT12_SIGNATURE_VALUE": signature_value,
        },
        "MSGR raw-menu glyph",
    )
    tail_recipe = recipes["dialogue_two_glyph_tail"]
    tail = build_absolute_jump(
        _only_source(tail_recipe, "shared/event_window/absolute_jump.s"),
        tail_recipe.address,
        pacing.labels["two_glyph_tail"],
        "MSGR dialogue pacing tail",
    )
    fetch_sites = {}
    for name in ("fetch_site_1", "fetch_site_2"):
        recipe = recipes[name]
        fetch_sites[name] = build_absolute_jump(
            _only_source(recipe, "shared/event_window/absolute_jump.s"),
            recipe.address,
            fetch_recipe.address,
            f"MSGR {name}",
        )

    assembly = {
        "dialogue_two_glyph_pacing_cave": pacing.data,
        "dialogue_two_glyph_tail": tail,
        "advance_cave": advance,
        "packed_fetch_cave": fetch,
        "subpixel_blitter_cave": blitter,
        "menu_glyph_cave": menu,
        **fetch_sites,
    }
    # The arena owns only its five resident components; site stubs live elsewhere.
    used = len(pacing.data) + len(advance) + len(fetch) + len(blitter) + len(menu)
    if used != 2113:
        raise ValueError(f"MSGR dialogue arena uses {used} bytes; expected 2113")
    return MappingProxyType(assembly), MappingProxyType(links), used


def _term_runtime(
    recipes: Mapping[str, PatchRecipe],
    demons: tuple[str, ...],
    characters: tuple[str, ...],
    races: tuple[str, ...],
    metrics8: FontMetrics,
    metrics16: FontMetrics,
) -> tuple[bytes, Mapping[str, int], int]:
    if (len(demons), len(characters), len(races)) != (
        DEMON_COUNT,
        CHARACTER_COUNT,
        RACE_COUNT,
    ):
        raise ValueError("MSGR term inventory changed")
    _widths8, codes8 = font8_tables(metrics8)
    codes16 = _font_codes(metrics16)
    if any(not name or len(name) > 20 for name in (*demons, *characters)):
        raise ValueError("MSGR demon/character name is empty or exceeds 20 glyphs")

    def mapped_code(code: int) -> int | None:
        if code == codes8.get(" "):
            return codes16.get(" ")
        if 64 <= code < 118:
            return code - 63
        if codes8.get("s") is not None and codes8["s"] <= code <= codes8["z"]:
            return code - 150
        if code == codes8.get("-"):
            return codes16.get("-")
        if code == codes8.get("'"):
            return codes16.get("'")
        return None

    if codes8.get(" ") != 63 or codes8.get("0") != 64 or codes8.get("s") != 205:
        raise ValueError("MSGR FONT8-to-FONT16 mapper ABI changed")
    for character in set("".join((*demons, *characters[:3]))):
        source = codes8.get(character)
        target = codes16.get(character)
        if source is None or target is None or mapped_code(source) != target:
            raise ValueError(f"MSGR term mapper cannot convert {character!r}")

    names = (*demons, *characters)
    data = bytearray(2 * len(names))
    name_pool_address = TERM_ARENA + len(data)
    pool = bytearray()
    offsets: dict[str, int] = {}
    for index, name in enumerate(names):
        offset = offsets.get(name)
        if offset is None:
            offset = len(pool)
            offsets[name] = offset
            try:
                pool.extend(codes8[character] for character in name)
            except KeyError as error:
                raise ValueError(
                    f"MSGR term {name!r} uses unsupported FONT8 character "
                    f"{error.args[0]!r}"
                ) from error
            pool.append(0)
        if offset > 0xFFFF:
            raise ValueError("MSGR term pool exceeds 16-bit offsets")
        struct.pack_into(">H", data, index * 2, offset)
    data.extend(pool)
    data.extend(bytes((-(TERM_ARENA + len(data))) % 4))

    race_table_address = TERM_ARENA + len(data)
    table_offset = len(data)
    data.extend(bytes(4 * RACE_COUNT))
    for index, race in enumerate(races):
        pointer = TERM_ARENA + len(data)
        struct.pack_into(">I", data, table_offset + index * 4, pointer)
        try:
            glyphs = tuple(codes16[character] for character in race)
        except KeyError as error:
            raise ValueError(
                f"MSGR race {race!r} uses unsupported FONT16 character "
                f"{error.args[0]!r}"
            ) from error
        data.extend(struct.pack(f">{len(glyphs) + 1}H", *glyphs, 0x8000))
    data.extend(bytes((-(TERM_ARENA + len(data))) % 4))

    recipe = recipes["dialogue_full_term_runtime"]
    sources = tuple(
        path.relative_to(ASSEMBLY_ROOT).as_posix()
        for path in recipe.replacement.sources
    )
    if sources != (
        "shared/event_window/full_term_inserts.s",
        "shared/event_window/character_term_insert.s",
    ):
        raise ValueError("MSGR term runtime source inventory changed")
    code_address = TERM_ARENA + len(data)
    base_symbols = {
        "CURRENT_DEMON_IDS": 0x0607A8C8,
        "DEMON_COUNT": DEMON_COUNT,
        "NAME_OFFSETS": TERM_ARENA,
        "NAME_POOL": name_pool_address,
        "RACE_COUNT": RACE_COUNT,
        "RACE_TABLE": race_table_address,
        "RACE_ID_HELPER": 0x0606B680,
        "INSERT_STATE": 0x0607A434,
        "INSERT_ACTIVE": 0x0607959C,
        "STREAM_PUSH": 0x0606EF54,
        "STREAM_POINTER": 0x0607A450,
        "STREAM_STATUS": 0x0607A8D0,
        "TEXT_FLAGS": 0x06079894,
        "STOCK_DEMON_INSERT": 0x0606F8F8,
        "STOCK_RACE_INSERT": 0x0606FA9C,
        "INSERT_BUFFER": code_address,
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
    }
    probe = assemble_checked(
        recipe.replacement.sources[0],
        code_address,
        base_symbols,
        "MSGR full-term adapters",
    )
    buffer_address = (code_address + len(probe.data) + 3) & ~3
    code = assemble_checked(
        recipe.replacement.sources[0],
        code_address,
        {**base_symbols, "INSERT_BUFFER": buffer_address},
        "MSGR full-term adapters",
    )
    if len(code.data) != len(probe.data):
        raise ValueError("MSGR term buffer placement changed assembly size")
    data.extend(code.data)
    data.extend(bytes(buffer_address - (TERM_ARENA + len(data))))
    data.extend(bytes(42))
    data.extend(bytes((-(TERM_ARENA + len(data))) % 4))

    character_address = TERM_ARENA + len(data)
    character = assemble_checked(
        recipe.replacement.sources[1],
        character_address,
        {
            "INSERT_STATE": 0x0607A434,
            "CHARACTER_COUNT": 3,
            "CHARACTER_OFFSETS": TERM_ARENA + DEMON_COUNT * 2,
            "NAME_POOL": name_pool_address,
            "INSERT_BUFFER": buffer_address,
            "NAME_LIMIT": 20,
            "NAME_COPY": code.labels["name_copy"],
            "NAME_CLEANUP": code.labels["name_cleanup"],
        },
        "MSGR character-term adapter",
    )
    data.extend(character.data)
    used = len(data)
    if used > TERM_CAPACITY:
        raise ValueError("MSGR term runtime exceeds its verified zero arena")
    links = MappingProxyType(
        {
            "dialogue_demon_name_insert": code.labels["dialogue_demon_name_insert"],
            "dialogue_race_insert": code.labels["dialogue_race_insert"],
            "dialogue_character_name_insert": character.labels[
                "dialogue_character_name_insert"
            ],
        }
    )
    return bytes(data).ljust(TERM_CAPACITY, b"\0"), links, used


def _ascii_field(value: str, capacity: int, context: str) -> bytes:
    if (
        not value
        or not value.isascii()
        or any(not 0x20 <= ord(char) <= 0x7E for char in value)
    ):
        raise ValueError(f"{context} must be nonempty printable ASCII")
    encoded = value.encode("ascii")
    if len(encoded) >= capacity:
        raise ValueError(f"{context} exceeds its {capacity - 1}-byte field")
    return (encoded + b"\0").ljust(capacity, b"\0")


def _generated_data(
    races: tuple[str, ...],
    debug: Mapping[str, str],
    metrics16: FontMetrics,
    uma_fallback: bytes,
) -> Mapping[str, bytes]:
    if len(uma_fallback) != 8:
        raise ValueError("MSGR Uma compatibility guard must own four glyph cells")
    codes16 = _font_codes(metrics16)
    try:
        uma = tuple(codes16[character] for character in races[22])
    except (IndexError, KeyError) as error:
        raise ValueError("MSGR Uma compatibility row cannot be encoded") from error
    uma_mirror = uma_fallback
    if 1 <= len(uma) <= 3:
        encoded = struct.pack(f">{len(uma) + 1}H", *uma, 0x8000)
        uma_mirror = encoded.ljust(8, b"\0")
    elif len(uma) == 4:
        # The retail table's framing is optional-full: a row that occupies all
        # four words has no terminator. The live portrait consumer is redirected
        # to the dynamic table, but keep this compatibility mirror truthful when
        # the authored value still fits its physical record.
        uma_mirror = struct.pack(">4H", *uma)
    generated = {
        "race_uma_mirror": uma_mirror,
        "debug_name_id_error": _ascii_field(
            debug["game.msgr_debug_ascii.o00ae04"], 16, "portrait name-ID error"
        ),
        "debug_load_error": _ascii_field(
            debug["game.msgr_debug_ascii.o00ae14"], 10, "portrait load error"
        ),
        "debug_menu_count_over": _ascii_field(
            debug["game.msgr_debug_ascii.o00c1b4"],
            24,
            "portrait menu-count error",
        ),
    }
    return MappingProxyType(generated)


def _build_runtime(
    config: PatchRecipeConfiguration,
    dictionary: bytes,
) -> RuntimeBuild:
    recipes = _recipe_map(config)
    metrics16 = FontMetrics.load(FONT16_METRICS_PATH)
    metrics12 = FontMetrics.load(FONT12_METRICS_PATH)
    metrics8 = FontMetrics.load(FONT8_METRICS_PATH)
    demons, characters, races, debug = _bound_terms()

    dialogue, dialogue_links, dialogue_used = _dialogue_runtime(
        recipes, metrics16, metrics12, dictionary
    )
    term, term_links, term_used = _term_runtime(
        recipes, demons, characters, races, metrics8, metrics16
    )
    player = build_player_name_assembly(
        PlayerNameAdapterSpec(
            "MSGR",
            0x0606F4F8,
            0x0606F54A,
            RAW_MENU_ARENA,
            RAW_MENU_CAPACITY,
            0x0606C7A8,
            0x0606ED6C,
            0x06079594,
            (0x0606C6EE, 0x0606C720),
            0x0606C762,
        ),
        codename_source=_only_source(
            recipes["codename_skip_copy"],
            "shared/player_name_inserts/codename_skip.s",
        ),
        raw_menu_source=_only_source(
            recipes["raw_menu_name_renderer"],
            "shared/player_name_inserts/raw_menu_inserts.s",
        ),
        result_source=_only_source(
            recipes["raw_menu_name_result_0606c6ee"],
            "shared/player_name_inserts/raw_menu_result.s",
        ),
    )
    _only_source(
        recipes["raw_menu_name_result_0606c720"],
        "shared/player_name_inserts/raw_menu_result.s",
    )
    assembly = {**dialogue, "dialogue_full_term_runtime": term, **player.replacements}
    links = {**dialogue_links, **term_links}
    arenas = (
        RuntimeArena(
            "dialogue_window", DIALOGUE_ARENA, dialogue_used, DIALOGUE_CAPACITY
        ),
        RuntimeArena("full_term_inserts", TERM_ARENA, term_used, TERM_CAPACITY),
        RuntimeArena(
            "player_name_raw_menu",
            RAW_MENU_ARENA,
            player.raw_menu_used_size,
            player.raw_menu_capacity,
        ),
    )
    if any(not 0 < arena.used_size <= arena.capacity for arena in arenas):
        raise ValueError("MSGR runtime-arena used size exceeds its capacity")
    if sum(arena.capacity for arena in arenas) != 24928:
        raise ValueError("MSGR runtime-arena capacity accounting changed")
    return RuntimeBuild(
        MappingProxyType(assembly),
        _generated_data(
            races,
            debug,
            metrics16,
            recipes["race_uma_mirror"].expected,
        ),
        MappingProxyType(links),
        arenas,
    )


def _instruction(recipe: PatchRecipe) -> bytes:
    source = recipe.replacement.instruction
    assert source is not None
    try:
        result = assemble(source, recipe.address)
    except AssemblyError as error:
        raise ValueError(f"{recipe.group}/{recipe.name}: {error}") from error
    if result.warnings:
        raise ValueError(f"{recipe.group}/{recipe.name}: instruction warnings")
    return result.data


def _bind_patches(
    config: PatchRecipeConfiguration,
    stock: bytes,
    runtime: RuntimeBuild,
) -> tuple[Patch, ...]:
    output: list[Patch] = []
    assembly_seen: set[str] = set()
    generated_seen: set[str] = set()
    links_seen: set[str] = set()
    pointer_values = {**pointer_contract(), **FIXED_POINTER_CONTRACT}
    pointers_seen: set[str] = set()
    for recipe in config.patches[TARGET]:
        expected = resolve_recipe_expected(recipe, stock, LOAD_ADDRESS)
        replacement_recipe = recipe.replacement
        if replacement_recipe.kind == "assembly":
            try:
                replacement = runtime.assembly[recipe.name]
            except KeyError as error:
                raise ValueError(f"unknown MSGR assembly {recipe.name}") from error
            assembly_seen.add(recipe.name)
        elif replacement_recipe.kind == "generated":
            if replacement_recipe.generator != "portrait_scene_data":
                raise ValueError(f"unknown MSGR generator for {recipe.name}")
            try:
                replacement = runtime.generated[recipe.name]
            except KeyError as error:
                raise ValueError(
                    f"unknown MSGR generated data {recipe.name}"
                ) from error
            generated_seen.add(recipe.name)
        elif replacement_recipe.kind == "linked_pointer":
            link = replacement_recipe.link
            assert link is not None
            try:
                replacement = struct.pack(">I", runtime.links[link])
            except KeyError as error:
                raise ValueError(f"unknown MSGR assembly link {link}") from error
            links_seen.add(link)
        elif replacement_recipe.kind == "pointer":
            pointer = replacement_recipe.pointer
            assert pointer is not None
            try:
                expected_pointer = pointer_values[recipe.name]
            except KeyError as error:
                raise ValueError(f"unknown MSGR pointer {recipe.name}") from error
            if expected_pointer != pointer:
                raise ValueError(f"MSGR pointer contract changed for {recipe.name}")
            pointers_seen.add(recipe.name)
            replacement = struct.pack(">I", pointer)
        elif replacement_recipe.kind == "instruction":
            replacement = _instruction(recipe)
        else:
            raise ValueError(
                f"{recipe.group}/{recipe.name}: unsupported MSGR replacement kind"
            )
        if len(replacement) != len(expected):
            raise ValueError(
                f"{recipe.group}/{recipe.name}: generated {len(replacement)} bytes, "
                f"expected {len(expected)}"
            )
        output.append(
            Patch(recipe.group, recipe.name, recipe.address, expected, replacement)
        )

    if assembly_seen != set(runtime.assembly):
        raise ValueError("MSGR assembly ownership differs from config")
    if generated_seen != set(runtime.generated):
        raise ValueError("MSGR generated-data ownership differs from config")
    if pointers_seen != set(pointer_values):
        raise ValueError("MSGR pointer ownership differs from config")
    expected_links = {
        recipe.replacement.link
        for recipe in config.patches[TARGET]
        if recipe.replacement.kind == "linked_pointer"
    }
    if links_seen != expected_links or set(runtime.links) != expected_links:
        raise ValueError("MSGR linked-pointer ownership differs from config")
    return tuple(output)


def build_portrait_scene_ui() -> PortraitSceneUiBuild:
    """Build the complete portrait-scene surface from the verified game disc."""
    config = _configuration()
    stock = _stock_source()
    dictionary = load_event_dictionary(CODEC_PATH).runtime_table()
    _validate_inputs(config, stock, dictionary)
    _validate_surfaces()
    runtime = _build_runtime(config, dictionary)
    patches = _bind_patches(config, stock, runtime)
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
    used = sum(arena.used_size for arena in runtime.arenas)
    capacity = sum(arena.capacity for arena in runtime.arenas)
    return PortraitSceneUiBuild(
        apply_patches(stock, LOAD_ADDRESS, patches),
        patches,
        ASSET_FILES,
        assembly_files,
        RUNTIME_INPUT_FILES,
        MappingProxyType({f"game:{TARGET}": _sha256(stock)}),
        used,
        capacity,
        runtime.arenas,
    )
