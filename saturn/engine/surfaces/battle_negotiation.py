"""Build the Saturn runtime used by the battle-negotiation surfaces."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path, PurePosixPath

from engine.core.patching import Patch, apply_patches
from engine.core.patch_recipes import (
    PatchRecipe,
    PatchRecipeConfiguration,
    load_patch_recipe_configuration,
)
from engine.core.sh2 import Assembly, AssemblyError, assemble, assemble_file
from rom.util.catalog import load_catalog, validate_source
from rom.util.workflows import read_source_files
from text.util.assets import load_asset, load_bound_translations
from text.util.event_codec import load_event_dictionary
from text.util.event_repack import FontMetrics
from text.util.surfaces import load_surfaces


ENGINE_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = ENGINE_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "battle_negotiation.json"
ASSEMBLY_ROOT = ENGINE_ROOT / "asm"
GENERATED_ROOT = ENGINE_ROOT / "generated" / "game"
OUTPUT_PATH = GENERATED_ROOT / "COMBAT.BIN"
BUILD_PATH = GENERATED_ROOT / "battle_negotiation_build.json"
TEXT_ROOT = SATURN_ROOT / "text"
TEXT_GENERATED_ROOT = TEXT_ROOT / "generated" / "game"
TEXT_BUILD_PATH = TEXT_GENERATED_ROOT / "battle_negotiation_build.json"
TEXT_COMBAT_PATH = TEXT_GENERATED_ROOT / "COMBAT.BIN"
CODEC_PATH = TEXT_ROOT / "config" / "event_codec.json"
FONT_ROOT = SATURN_ROOT / "font" / "generated" / "game"
FONT16_METRICS_PATH = FONT_ROOT / "FONT16_metrics.json"
FONT8_METRICS_PATH = FONT_ROOT / "FONT8_metrics.json"

TARGET = "COMBAT.BIN"
LOAD_ADDRESS = 0x06020000

NAME_COUNT = 319
RACE_COUNT = 43
DISPATCH_CAVE_ADDRESS = 0x06021000
DICTIONARY_ADDRESS = 0x06021200
DIALOGUE_DISPATCH_MODE = 0x060213FC
DIALOGUE_CAVE_ADDRESS = 0x06021400
KYOUJI_NAME_ADDRESS = 0x060219C6
KYOUJI_NAME_BYTES = 58
NAME_OFFSETS_ADDRESS = 0x06024000
RACE_OFFSETS_ADDRESS = 0x0602427E
FONT8_MAP_ADDRESS = 0x060242D4
STRING_POOL_ADDRESS = 0x060244D4
INSERT_DATA_ADDRESS = NAME_OFFSETS_ADDRESS
INSERT_CODE_ADDRESS = 0x06025D00
INSERT_DATA_BYTES = INSERT_CODE_ADDRESS - INSERT_DATA_ADDRESS
FULLWORD_GLYPH_LIMIT = 20

GRID_ADDRESS = 0x06026000
CURSOR_X = 0x06074099
CURSOR_Y = 0x0607409A
CURRENT_COLOR = 0x0607409B
PENDING_BUFFER = 0x06073FA8
PENDING_FLAG = 0x06073FD2
PENDING_WORD_CAPACITY = (PENDING_FLAG - PENDING_BUFFER) // 2


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        return _sha256(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"missing generated input: {path}") from error


def _read_json(path: Path) -> dict[str, object]:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        output: dict[str, object] = {}
        for key, value in pairs:
            if key in output:
                raise ValueError(f"{path}: duplicate JSON field {key!r}")
            output[key] = value
        return output

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates
        )
    except FileNotFoundError as error:
        raise ValueError(f"missing build input: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: invalid JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path}: root must be an object")
    return value


def _object(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return value


def _validate_surfaces() -> None:
    surfaces = load_surfaces()
    dialogue = surfaces.surface("battle.negotiation_dialogue")
    choice = surfaces.surface("battle.negotiation_choice")
    if (
        dialogue.en.font,
        dialogue.en.rows,
        dialogue.en.width.unit,
        dialogue.en.width.value,
    ) != ("font16", 3, "pixels", 300):
        raise ValueError("battle negotiation dialogue geometry changed")
    if (
        choice.en.font,
        choice.en.rows,
        choice.en.width.unit,
        choice.en.width.value,
    ) != ("font16", 1, "pixels", 150):
        raise ValueError("battle negotiation choice geometry changed")


def _validate_text_build() -> bytes:
    document = _read_json(TEXT_BUILD_PATH)
    if document.get("version") != 1 or document.get("surface") != "battle.negotiation":
        raise ValueError("battle-negotiation text build has the wrong surface")
    if document.get("codec_sha256") != _file_sha256(CODEC_PATH):
        raise ValueError("battle-negotiation text build uses a different codec")
    outputs = _object(document.get("outputs"), f"{TEXT_BUILD_PATH}.outputs")
    expected = {
        "COMBAT.BIN",
        "ITEMNAME.DAT",
        "COMBDATA/BOSSTALK.EVE",
        "COMBDATA/TLK_BST.EVE",
        "COMBDATA/KEMO.EVE",
        "COMBDATA/TLK_KOFU.EVE",
        "COMBDATA/NBL_M.EVE",
        "COMBDATA/TLK_HIRK.EVE",
        "COMBDATA/TLK_YNGM.EVE",
        "COMBDATA/GRL.EVE",
        "COMBDATA/TLK_BOY.EVE",
        "COMBDATA/CLD_F.EVE",
        "COMBDATA/TLK_LADY.EVE",
        "COMBDATA/TLK_CRZY.EVE",
        "COMBDATA/JIJY.EVE",
        "COMBDATA/CYNI.EVE",
        "COMBDATA/TLK_WEST.EVE",
        "COMBDATA/SLM.EVE",
    }
    if set(outputs) != expected:
        raise ValueError("battle-negotiation text build has the wrong output set")
    for name, raw_row in outputs.items():
        row = _object(raw_row, f"{TEXT_BUILD_PATH}.outputs.{name}")
        if row.get("sha256") != _file_sha256(TEXT_GENERATED_ROOT / name):
            raise ValueError(f"generated {name} does not match its text build")
    return TEXT_COMBAT_PATH.read_bytes()


def _translated_terms() -> tuple[tuple[str, ...], tuple[str, ...], str]:
    demon_ids = {
        f"game.dvlname.o{index * 8:06x}.text" for index in range(NAME_COUNT)
    }
    race_ids = {f"game.normcom_tables.races.r{index:04d}" for index in range(RACE_COUNT)}
    translations = load_bound_translations(
        ("game.dvlname.", "game.normcom_tables.races."),
        required_ids=demon_ids | race_ids,
    )
    demons = tuple(
        translations[f"game.dvlname.o{index * 8:06x}.text"]
        for index in range(NAME_COUNT)
    )
    races = tuple(
        translations[f"game.normcom_tables.races.r{index:04d}"]
        for index in range(RACE_COUNT)
    )
    _reference, kyouji, _reviewed = load_asset(
        PurePosixPath("characters.json")
    ).field("kyouji_kuzunoha.full_name").resolve()
    if not kyouji:
        raise ValueError("Kyouji's full name is untranslated")
    return demons, races, kyouji


def _build_insert_data(
    font16: FontMetrics,
    font8: FontMetrics,
    region_bytes: int,
) -> bytes:
    demons, races, _kyouji = _translated_terms()
    data = bytearray(STRING_POOL_ADDRESS - INSERT_DATA_ADDRESS)
    pool_offset = STRING_POOL_ADDRESS - INSERT_DATA_ADDRESS
    interned: dict[str, int] = {}

    def encode(text: str, context: str) -> int:
        if text in interned:
            return interned[text]
        glyphs = font16.segment(text)
        if len(glyphs) > FULLWORD_GLYPH_LIMIT:
            raise ValueError(f"{context} exceeds the battle insert buffer: {text!r}")
        offset = len(data) - pool_offset
        if not 0 <= offset <= 0xFFFF:
            raise ValueError("battle negotiation string pool exceeds u16 offsets")
        data.extend(struct.pack(f">{len(glyphs) + 1}H", *(g.code for g in glyphs), 0x8000))
        interned[text] = offset
        return offset

    for index, text in enumerate(demons):
        struct.pack_into(">H", data, index * 2, encode(text, f"demon name {index}"))
    race_base = RACE_OFFSETS_ADDRESS - INSERT_DATA_ADDRESS
    for index, text in enumerate(races):
        struct.pack_into(">H", data, race_base + index * 2, encode(text, f"race {index}"))
    map_base = FONT8_MAP_ADDRESS - INSERT_DATA_ADDRESS
    font16_by_text = font16.by_text
    for text, glyph8 in font8.by_text.items():
        glyph16 = font16_by_text.get(text)
        if len(text) == 1 and glyph16 is not None and glyph8.code < 256:
            struct.pack_into(">H", data, map_base + glyph8.code * 2, glyph16.code)

    itemname = (TEXT_GENERATED_ROOT / "ITEMNAME.DAT").read_bytes()
    for record in range(287):
        pointer = struct.unpack_from(">H", itemname, record * 0x60 + 0x5E)[0]
        try:
            terminator = itemname.index(0xFF, pointer, pointer + 20)
        except ValueError as error:
            raise ValueError(f"ITEMNAME record {record} has no runtime terminator") from error
        for code in itemname[pointer:terminator]:
            mapped = struct.unpack_from(">H", data, map_base + code * 2)[0]
            if not mapped:
                raise ValueError(
                    f"ITEMNAME record {record} uses unmapped FONT8 code {code:#04x}"
                )
    if len(data) > region_bytes:
        raise ValueError("battle negotiation insert data exceeds its configured cave")
    data.extend(bytes(region_bytes - len(data)))
    return bytes(data)


def _build_kyouji_name(font16: FontMetrics, region_bytes: int) -> bytes:
    _demons, _races, kyouji = _translated_terms()
    glyphs = font16.segment(kyouji)
    value = struct.pack(f">{len(glyphs) + 1}H", *(g.code for g in glyphs), 0x8000)
    if len(value) > region_bytes:
        raise ValueError("Kyouji's full name exceeds its configured runtime row")
    return value + bytes(region_bytes - len(value))


def _assembled(
    source: Path,
    address: int,
    symbols: dict[str, int] | None = None,
) -> Assembly:
    try:
        result = assemble_file(source, address, symbols)
    except AssemblyError as error:
        raise ValueError(f"{source.relative_to(ENGINE_ROOT)}: {error}") from error
    if result.warnings:
        raise ValueError(
            f"{source.relative_to(ENGINE_ROOT)}: assembly warnings: {result.warnings}"
        )
    return result


def _sources(recipe: PatchRecipe, expected: tuple[str, ...]) -> tuple[Path, ...]:
    sources = recipe.replacement.sources
    actual = tuple(path.relative_to(ASSEMBLY_ROOT).as_posix() for path in sources)
    if actual != expected:
        raise ValueError(f"{recipe.group}/{recipe.name}: assembly source contract changed")
    return sources


def _font16_layout(font16: FontMetrics) -> tuple[int, int, int, int, int]:
    document = _read_json(FONT16_METRICS_PATH)
    width_table = _object(document.get("width_table"), "FONT16 width table")
    storage_glyph = width_table.get("storage_glyph")
    code_limit = width_table.get("code_limit")
    if type(storage_glyph) is not int or type(code_limit) is not int:
        raise ValueError("FONT16 width-table layout is malformed")
    minimum_advance = min(glyph.advance for glyph in font16.glyphs)
    columns = (300 + minimum_advance - 1) // minimum_advance
    row_bytes = columns * 2
    total_cells = columns * 3
    if (columns, row_bytes, total_cells) != (100, 200, 300):
        raise ValueError("battle negotiation backing-grid geometry changed")
    return code_limit, storage_glyph * 32, columns, row_bytes, total_cells


def _build_dispatch_cave(
    recipe: PatchRecipe,
    runtime_table: bytes,
) -> tuple[bytes, Assembly]:
    (source,) = _sources(
        recipe, ("battle_negotiation/packed_dispatch.s",)
    )
    if recipe.address != DISPATCH_CAVE_ADDRESS:
        raise ValueError("battle negotiation dispatch cave moved")
    symbols = {
        "RAW_HANDLER": recipe.address,
        "PACKED_DISPATCH": recipe.address,
        "DICTIONARY": DICTIONARY_ADDRESS,
        "SPACE_CODE": 267,
        "PENDING_BUFFER": PENDING_BUFFER,
        "PENDING_FLAG": PENDING_FLAG,
        "DIALOGUE_MODE": DIALOGUE_DISPATCH_MODE,
        "TERMINATOR": 0x8000,
        "FIRST_SPECIAL": 0x8010,
        "DEMON_ID_HANDLER": 0x060504F8,
        "EQUAL_CONTINUATION": 0x06051D2C,
        "OTHER_CONTINUATION": 0x06051D44,
    }
    probe = _assembled(source, recipe.address, symbols)
    symbols["RAW_HANDLER"] = probe.labels["raw_handler"]
    code = _assembled(source, recipe.address, symbols)
    payload = bytearray(code.data)
    dictionary_offset = DICTIONARY_ADDRESS - recipe.address
    if len(payload) > dictionary_offset:
        raise ValueError("packed dispatcher overlaps the shared dictionary")
    payload.extend(bytes(dictionary_offset - len(payload)))
    payload.extend(runtime_table)
    mode_end = DIALOGUE_DISPATCH_MODE - recipe.address + 1
    if len(payload) > mode_end:
        raise ValueError("packed dictionary overlaps the dialogue mode flag")
    payload.extend(bytes(mode_end - len(payload)))
    if len(payload) != len(recipe.expected):
        raise ValueError("packed dispatch payload does not fill its declared cave")
    return bytes(payload), code


def _build_dialogue_cave(
    recipe: PatchRecipe,
    font16: FontMetrics,
) -> tuple[bytes, Assembly]:
    blitter_source, dialogue_source = _sources(
        recipe,
        (
            "battle_negotiation/font16_surface_blitter.s",
            "battle_negotiation/dialogue_vwf.s",
        ),
    )
    if (
        recipe.address != DIALOGUE_CAVE_ADDRESS
        or recipe.address + len(recipe.expected) != KYOUJI_NAME_ADDRESS
    ):
        raise ValueError("battle dialogue cave contract changed")
    blitter = _assembled(
        blitter_source,
        recipe.address,
        {
            "FONT16_POINTER": 0x060721E0,
            "GLYPH_PATTERN_LUT": 0x0606F124,
            "GLYPH_MASK_LUT": 0x0606F144,
        },
    )
    code_address = (recipe.address + len(blitter.data) + 3) & ~3
    code_limit, width_offset, columns, row_bytes, total_cells = _font16_layout(
        font16
    )
    colors_address = GRID_ADDRESS + total_cells * 2
    dialogue = _assembled(
        dialogue_source,
        code_address,
        {
            "ORIGINAL_SURFACE_CLEAR": 0x060515B4,
            "FONT16_POINTER": 0x060721E0,
            "FRAMEBUFFER_POINTER": 0x060721DC,
            "FRAMEBUFFER_STRIDE": 320,
            "SURFACE_BLITTER": recipe.address,
            "CODE_LIMIT": code_limit,
            "WIDTH_OFFSET": width_offset,
            "GRID": GRID_ADDRESS,
            "COLORS": colors_address,
            "GRID_COLUMNS": columns,
            "GRID_ROW_BYTES": row_bytes,
            "COLOR_ROW_BYTES": columns,
            "TOTAL_CELLS": total_cells,
            "OPTION_CELLS": columns * 2,
            "CURSOR_X": CURSOR_X,
            "CURSOR_Y": CURSOR_Y,
            "CURRENT_COLOR": CURRENT_COLOR,
            "STORE_RETURN": 0x06051F6A,
            "LEFT_MARGIN": 10,
            "RIGHT_MARGIN": 310,
            "ANCHOR_CODE": 0x7FFF,
            "ZERO_SEPARATOR_CODE": 0x07FF,
            "SOFT_WRAP_CODE": 0x07FE,
            "STATIC_HINT_BASE": 0x0750,
            "STATIC_HINT_LIMIT": 0x07FC,
            "MEASURE_START_CODE": 0x07FC,
            "MEASURE_END_CODE": 0x07FD,
            "SPACE_CODE": 267,
            "MEASURE_MODE": 0x06021A00,
            "MEASURE_WIDTH": 0x06021A02,
            "SURFACE_VALID": 0x06021A04,
            "PENDING_BUFFER": PENDING_BUFFER,
            "PENDING_FLAG": PENDING_FLAG,
            "PENDING_WORD_CAPACITY": PENDING_WORD_CAPACITY,
            "SOURCE_POINTER": 0x06073FD8,
            "CHOICE_RIGHT_X": 160,
            "ANCHOR_COLUMN": columns // 2,
            "ANCHOR_BYTE_OFFSET": columns,
        },
    )
    payload = bytearray(blitter.data)
    payload.extend(bytes(code_address - recipe.address - len(payload)))
    payload.extend(dialogue.data)
    if len(payload) != len(recipe.expected):
        raise ValueError("battle dialogue assembly does not fill its declared cave")
    return bytes(payload), dialogue


def _build_insert_code(recipe: PatchRecipe) -> tuple[bytes, Assembly]:
    (source,) = _sources(recipe, ("battle_negotiation/english_inserts.s",))
    if recipe.address != INSERT_CODE_ADDRESS:
        raise ValueError("battle English-insert code moved")
    result = _assembled(
        source,
        recipe.address,
        {
            "DVL_BASE_POINTER": 0x06072220,
            "DVL_SOURCE_SIZE": NAME_COUNT * 8,
            "NAME_OFFSETS": NAME_OFFSETS_ADDRESS,
            "RACE_OFFSETS": RACE_OFFSETS_ADDRESS,
            "STRING_POOL": STRING_POOL_ADDRESS,
            "FONT8_TO_FONT16": FONT8_MAP_ADDRESS,
            "COMPACT_COPY": 0x06051AE0,
            "FULLWORD_COPY": 0x06051A94,
            "RACE_SOURCE": 0x060743C0,
            "RACE_SOURCE_END": 0x06074518,
            "ITEM_BUFFER0": 0x0607C08C,
            "ITEM_BUFFER1": 0x0607C0A4,
            "ITEM_ID0": 0x0607C0D4,
            "ITEM_ID1": 0x0607C0D8,
            "ITEM_FLAG_MASK": 0x60000000,
            "ITEM_ID_LIMIT": 288,
            "ITEM_RECORD_SIZE": 0x60,
            "ITEM_BASE_POINTER": 0x0607221C,
            "ITEM_FULL_NAME_OFFSET": 0x5E,
            "ITEM_NAME_LIMIT": FULLWORD_GLYPH_LIMIT - 1,
            "PENDING_BUFFER": PENDING_BUFFER,
            "PENDING_FLAG": PENDING_FLAG,
            "COLOR_RESET": 0x8020,
            "TERMINATOR": 0x8000,
        },
    )
    if len(result.data) != len(recipe.expected):
        raise ValueError("battle English-insert assembly size changed")
    return result.data, result


def _instruction(recipe: PatchRecipe) -> bytes:
    assert recipe.replacement.instruction is not None
    try:
        result = assemble(recipe.replacement.instruction, recipe.address)
    except AssemblyError as error:
        raise ValueError(f"{recipe.group}/{recipe.name}: {error}") from error
    trailing_stock_delay = (
        recipe.name == "dialogue_typewriter_continue_through_pending_selector"
        and result.warnings == ("line 1: delay slot does not contain an instruction",)
    )
    if (result.warnings and not trailing_stock_delay) or len(result.data) != len(
        recipe.expected
    ):
        raise ValueError(f"{recipe.group}/{recipe.name}: invalid instruction patch")
    return result.data


def _bind_static_patches(
    config: PatchRecipeConfiguration,
    font16: FontMetrics,
    runtime_table: bytes,
) -> tuple[Patch, ...]:
    recipes = config.patches[TARGET]
    by_name = {recipe.name: recipe for recipe in recipes}
    if len(by_name) != len(recipes):
        raise ValueError("battle negotiation patch names are not unique")

    dispatch_payload, dispatch = _build_dispatch_cave(
        by_name["dispatch_cave"], runtime_table
    )
    dialogue_payload, dialogue = _build_dialogue_cave(
        by_name["dialogue_vwf_cave"], font16
    )
    insert_payload, inserts = _build_insert_code(by_name["english_insert_code"])

    pointer_contracts = {
        "dispatch_cave_pointer": DISPATCH_CAVE_ADDRESS,
        "combat_codename_pointer": 0x0023FE14,
    }
    link_contracts = {
        "dialogue_dispatch": dispatch.labels["dialogue_dispatch"],
        "compact_name_insert": inserts.labels["combat_compact_name_insert"],
        "fullword_insert": inserts.labels["combat_fullword_insert"],
        "kyouji_full_name": KYOUJI_NAME_ADDRESS,
        "dialogue_renderer": dialogue.labels["combat_render"],
        "dialogue_external_surface_clear": dialogue.labels[
            "combat_external_surface_clear"
        ],
        "dialogue_clear": dialogue.labels["combat_clear"],
        "dialogue_partial_clear": dialogue.labels["combat_clear_options"],
        "choice_position": dialogue.labels["combat_choice_position"],
    }
    expected_assembly = {
        "dispatch_cave",
        "dispatch_hook",
        "dialogue_vwf_cave",
        "english_insert_code",
        "dialogue_store_hook",
        "dialogue_typewriter_reset_budget",
        "dialogue_typewriter_continue_after_first_visible_glyph",
        "dialogue_typewriter_reset_helper",
        "dialogue_typewriter_visible_helper",
    }
    assembly_seen: set[str] = set()
    bound: list[Patch] = []
    for recipe in recipes:
        replacement_recipe = recipe.replacement
        if replacement_recipe.kind == "assembly":
            assembly_seen.add(recipe.name)
            if recipe.name == "dispatch_cave":
                replacement = dispatch_payload
            elif recipe.name == "dispatch_hook":
                (source,) = _sources(
                    recipe, ("battle_negotiation/dispatch_hook.s",)
                )
                replacement = _assembled(
                    source,
                    recipe.address,
                    {"DISPATCH_CAVE_POINTER": 0x06051E40},
                ).data
            elif recipe.name == "dialogue_vwf_cave":
                replacement = dialogue_payload
            elif recipe.name == "english_insert_code":
                replacement = insert_payload
            elif recipe.name == "dialogue_store_hook":
                (source,) = _sources(recipe, ("battle_negotiation/store_hook.s",))
                replacement = _assembled(
                    source,
                    recipe.address,
                    {"STORE": dialogue.labels["combat_store"]},
                ).data
            elif recipe.name == "dialogue_typewriter_reset_budget":
                (source,) = _sources(
                    recipe, ("battle_negotiation/typewriter_reset_hook.s",)
                )
                replacement = _assembled(
                    source,
                    recipe.address,
                    {"TYPEWRITER_RESET": 0x06059580},
                ).data
            elif recipe.name == "dialogue_typewriter_continue_after_first_visible_glyph":
                (source,) = _sources(
                    recipe, ("battle_negotiation/typewriter_visible_hook.s",)
                )
                replacement = _assembled(
                    source,
                    recipe.address,
                    {"TYPEWRITER_VISIBLE": 0x06059594},
                ).data
            elif recipe.name == "dialogue_typewriter_reset_helper":
                (source,) = _sources(
                    recipe, ("battle_negotiation/typewriter_reset.s",)
                )
                replacement = _assembled(
                    source,
                    recipe.address,
                    {"TYPEWRITER_MODE_POINTER": 0x06059668},
                ).data
            elif recipe.name == "dialogue_typewriter_visible_helper":
                (source,) = _sources(
                    recipe, ("battle_negotiation/typewriter_visible.s",)
                )
                replacement = _assembled(
                    source,
                    recipe.address,
                    {
                        "TYPEWRITER_PENDING_SELECTOR": 0x06059678,
                        "TYPEWRITER_FRAME_RETURN": 0x06059874,
                    },
                ).data
            else:
                raise ValueError(f"unsupported battle assembly patch {recipe.name}")
            if len(replacement) != len(recipe.expected):
                raise ValueError(f"{recipe.name}: assembly patch size changed")
        elif replacement_recipe.kind == "instruction":
            replacement = _instruction(recipe)
        elif replacement_recipe.kind == "pointer":
            pointer = replacement_recipe.pointer
            expected_pointer = pointer_contracts.get(recipe.name)
            if pointer is None or pointer != expected_pointer:
                raise ValueError(f"{recipe.name}: pointer contract changed")
            replacement = struct.pack(">I", pointer)
        elif replacement_recipe.kind == "linked_pointer":
            link = replacement_recipe.link
            if link is None or link not in link_contracts:
                raise ValueError(f"{recipe.name}: unknown linked pointer {link!r}")
            replacement = struct.pack(">I", link_contracts[link])
        else:
            raise ValueError(f"{recipe.name}: unsupported replacement recipe")
        bound.append(
            Patch(
                recipe.group,
                recipe.name,
                recipe.address,
                recipe.expected,
                replacement,
            )
        )
    if assembly_seen != expected_assembly:
        raise ValueError("battle negotiation assembly contract is incomplete")
    return tuple(bound)


def build_battle_negotiation() -> dict[Path, bytes]:
    _validate_surfaces()
    config = load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="battle.negotiation",
        target_names={TARGET},
        input_names={
            "font16_metrics_sha256",
            "font8_metrics_sha256",
            "event_runtime_table_sha256",
        },
    )
    contract = config.targets[TARGET]
    font16 = FontMetrics.load(FONT16_METRICS_PATH)
    font8 = FontMetrics.load(FONT8_METRICS_PATH)
    runtime_table = load_event_dictionary(CODEC_PATH).runtime_table()
    actual_inputs = {
        "font16_metrics_sha256": _file_sha256(FONT16_METRICS_PATH),
        "font8_metrics_sha256": _file_sha256(FONT8_METRICS_PATH),
        "event_runtime_table_sha256": _sha256(runtime_table),
    }
    if actual_inputs != config.inputs:
        raise ValueError("battle-negotiation runtime inputs changed")

    validated = validate_source(load_catalog()["game"])
    stock = read_source_files(validated, (TARGET,))[TARGET]
    if len(stock) != contract.size or _sha256(stock) != contract.stock_sha256:
        raise ValueError("stock COMBAT.BIN does not match the patch target")
    translated = _validate_text_build()
    if len(translated) != contract.size:
        raise ValueError("translated COMBAT.BIN has the wrong size")

    static_patches = _bind_static_patches(config, font16, runtime_table)
    dynamic_patches = (
        Patch(
            "combat_vwf_data",
            "kyouji_full_name",
            KYOUJI_NAME_ADDRESS,
            bytes(KYOUJI_NAME_BYTES),
            _build_kyouji_name(font16, KYOUJI_NAME_BYTES),
        ),
        Patch(
            "combat_vwf_data",
            "english_insert_data",
            INSERT_DATA_ADDRESS,
            bytes(INSERT_DATA_BYTES),
            _build_insert_data(font16, font8, INSERT_DATA_BYTES),
        ),
    )
    patches = (*static_patches, *dynamic_patches)
    patched = apply_patches(translated, contract.load_address, patches)
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
        "surface": "battle.negotiation",
        "patch_config_sha256": _file_sha256(CONFIG_PATH),
        "text_build_sha256": _file_sha256(TEXT_BUILD_PATH),
        "assembly_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): _file_sha256(path)
            for path in assembly_files
        },
        "output_sha256": _sha256(patched),
        "patch_groups": list(
            dict.fromkeys(patch.group for patch in patches)
        ),
        "patches": len(patches),
    }
    return {
        OUTPUT_PATH: patched,
        BUILD_PATH: (json.dumps(manifest, indent=2) + "\n").encode("utf-8"),
    }
