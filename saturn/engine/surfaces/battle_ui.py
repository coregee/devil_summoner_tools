"""Build the shared Saturn battle UI renderers from authored text assets."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

from engine.core.patch_recipes import (
    ASSEMBLY_ROOT,
    PatchRecipe,
    PatchRecipeConfiguration,
    load_patch_recipe_configuration,
)
from engine.surfaces.battle_negotiation import (
    OUTPUT_PATH as COMBAT_OUTPUT_PATH,
    build_battle_negotiation,
)
from engine.core.patching import Patch, apply_patches
from engine.core.sh2 import AssemblyError, assemble
from engine.shared.status_layout import load_stock_latin_codes
from rom.util.catalog import load_catalog, validate_source
from rom.util.workflows import read_source_files
from text.util.assets import load_asset, load_bound_translations
from text.util.event_codec import load_event_dictionary, pack_direct_codes
from text.util.event_repack import FontMetrics
from text.util.surfaces import load_surfaces


ENGINE_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = ENGINE_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "battle_ui.json"
GENERATED_ROOT = ENGINE_ROOT / "generated" / "game"
NORMCOM_OUTPUT_PATH = GENERATED_ROOT / "battle_ui" / "NORMCOM.BIN"
BUILD_PATH = GENERATED_ROOT / "battle_ui_build.json"
TEXT_ROOT = SATURN_ROOT / "text"
TEXT_GENERATED_ROOT = TEXT_ROOT / "generated" / "game"
TEXT_BUILD_PATH = TEXT_GENERATED_ROOT / "battle_ui_build.json"
CODEC_PATH = TEXT_ROOT / "config" / "event_codec.json"
FONT_ROOT = SATURN_ROOT / "font" / "generated" / "game"
FONT8_METRICS_PATH = FONT_ROOT / "FONT8_metrics.json"
FONT16_METRICS_PATH = FONT_ROOT / "FONT16_metrics.json"
PARTY_PANEL_ASSET_PATH = SATURN_ROOT.parent / "assets" / "text" / "battle" / "party_panel.json"

LOAD_ADDRESS = 0x06020000
RENDERER_CAVE = 0x06020400
RENDERER_WIDTHS = 0x060204BC
RENDERER_FALLBACK = 0x060205BC
RENDERER_RACES = 0x06020640
ANALYSIS_COUNTED_DRAWER = 0x06020798
BATTLE_SURFACE_BLITTER = 0x060208D8
BATTLE_SURFACE_DRAWER = 0x060209DC
BATTLE_HELP_RAW_DRAWER = 0x06020A44
BATTLE_HELP_DRAWER = 0x06020AAC
BATTLE_ITEM_DRAWER = 0x06020B3C
ANALYSIS_CAVE = 0x06021C00
NAME_OFFSETS = 0x06021C00
NAME_POOL = 0x06021E7E
AFFINITY_OFFSETS = 0x0602296C
AFFINITY_POOL = 0x060229F0
AFFINITY_DRAWER = 0x06022D50
ANALYSIS_SKILL_DRAWER = 0x06022E04
PANEL_FULL_NAME_DRAWER = 0x06022EAC
RESULT_LIFE_STONES = 0x06022F7C
RESULT_BEADS = 0x06022F87
RESULT_LABEL_DRAWER = 0x06022F8C
CHARACTER_OFFSETS = 0x06023050
CHARACTER_POOL = 0x0602305C
RESULT_NAME_DRAWER = 0x060230AC
RESULT_ITEM_DRAWER = 0x06023138
EVENT_ITEM_DRAWER = 0x06023210
PANEL_DRAWER = 0x060232C8

FONT8_ADDRESS = 0x00219150
FONT16_POINTER = 0x060721E0
GLYPH_PATTERN_LUT = 0x0606F124
GLYPH_MASK_LUT = 0x0606F144
RACE_SOURCE = 0x06070DD0
DVL_SOURCE = 0x0023F5D0
AFFINITY_SOURCE = 0x06070F5E
STOCK_GLYPH = 0x06046BD0
STOCK_COUNTED = 0x060500D8

BTL_DECODER = 0x06020C00
BTL_SCRATCH = 0x06020F00
BTL_CONTINUATION = 0x0604DCC0
BTL_HOOK = 0x0604DCB4
BUTU_DECODER = 0x06020A00
BUTU_SCRATCH = 0x06020D00
BUTU_CONTINUATION = 0x0602F7F4

DEMON_COUNT = 319
RACE_COUNT = 43
AFFINITY_COUNT = 66
CHARACTER_COUNT = 6
RACE_RECORD_BYTES = 8
NAME_MAX_PIXELS = 96
AFFINITY_MAX_PIXELS = 112
PARTY_NAME_MAX_PIXELS = 80
RESULT_LABEL_MAX_PIXELS = 88
DECODED_RECORD_WORDS = 127
PACKED_PADDING_WORD = 0x0800

# The stock test/diagnostic table mixes terminated fields with fields whose
# following structure word is the boundary. Every physical mirror is owned so
# authored edits cannot silently update only one copy.
DEBUG_LAYOUT = (
    ("debug_record_00", "game.combat_debug.o05451c", (0x0607451C,), 7, True),
    ("debug_record_01", "game.combat_debug.o05452c", (0x0607452C,), 3, True),
    ("debug_record_02", "game.combat_debug.o055a08", (0x06075A08,), 5, True),
    ("debug_record_03", "game.combat_debug.o055a32", (0x06075A32,), 6, True),
    ("debug_record_04", "game.combat_debug.o055a5c", (0x06075A5C,), 7, True),
    ("debug_record_05", "game.combat_debug.o055a86", (0x06075A86,), 8, True),
    (
        "debug_record_06",
        "game.combat_debug.o055ab0",
        (0x06075AB0, 0x06075ADA, 0x06075B04, 0x06075B2E),
        2,
        False,
    ),
    (
        "debug_record_07",
        "game.combat_debug.o055ab6",
        (0x06075AB6, 0x06075AE0, 0x06075B0A, 0x06075B34),
        10,
        False,
    ),
    ("debug_record_08", "game.combat_debug.o055acc", (0x06075ACC,), 2, False),
    ("debug_record_09", "game.combat_debug.o055ad2", (0x06075AD2,), 3, True),
    ("debug_record_10", "game.combat_debug.o055af6", (0x06075AF6,), 3, False),
    ("debug_record_11", "game.combat_debug.o055afe", (0x06075AFE,), 2, True),
    ("debug_record_12", "game.combat_debug.o055b20", (0x06075B20,), 6, True),
    ("debug_record_13", "game.combat_debug.o055b4a", (0x06075B4A,), 6, True),
)
UMA_MIRROR_ADDRESS = 0x06074470


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        return _sha256(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"missing generated input: {path}") from error


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON field {key!r}")
        output[key] = value
    return output


def _read_json(path: Path) -> object:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicates
        )
    except FileNotFoundError as error:
        raise ValueError(f"missing build input: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: invalid JSON") from error


def _object(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return value


def _validate_surfaces() -> None:
    surfaces = load_surfaces()
    expected = {
        "battle.help": ("font16", 2, 300),
        "battle.demon_chat": ("font16", 2, 176),
        "battle.item_name": ("font8", 1, 80),
        "battle.skill_name": ("font8", 1, 80),
        "battle.analyze_demon_name": ("font8", 1, 112),
        "battle.analyze_affinity": ("font8", 1, 112),
        "battle.party_demon_name": ("font8", 1, 80),
        "party.character_name": ("font8", 1, 80),
        "battle.result_name": ("font8", 1, 88),
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
    for name, cells in (("battle.party_empty", 5), ("battle.party_in_party", 8)):
        layout = surfaces.surface(name).en
        if (
            layout.font,
            layout.rows,
            layout.width.unit,
            layout.width.value,
        ) != ("font8", 1, "glyph_cells", cells):
            raise ValueError(f"{name} geometry changed")
    race_heading = surfaces.surface("battle.analyze_race_heading").en
    if (
        race_heading.font,
        race_heading.rows,
        race_heading.width.unit,
        race_heading.width.value,
    ) != ("font8", 1, "glyph_cells", RACE_RECORD_BYTES):
        raise ValueError("battle.analyze_race_heading geometry changed")
    ritual = surfaces.surface("ritual.console").en
    if (
        ritual.font,
        ritual.rows,
        ritual.width.unit,
        ritual.width.value,
    ) != ("font16", None, "pixels", 176):
        raise ValueError("ritual.console geometry changed")


def _validate_text_build(dictionary_digest: str) -> None:
    document = _object(_read_json(TEXT_BUILD_PATH), str(TEXT_BUILD_PATH))
    if (
        document.get("version") != 1
        or document.get("surface") != "battle.ui"
        or document.get("runtime_table_sha256") != dictionary_digest
        or document.get("font8_metrics_sha256") != _file_sha256(FONT8_METRICS_PATH)
        or document.get("font16_metrics_sha256") != _file_sha256(FONT16_METRICS_PATH)
    ):
        raise ValueError("battle UI text build uses different runtime inputs")
    outputs = _object(document.get("outputs"), f"{TEXT_BUILD_PATH}.outputs")
    expected = {
        "BTL_HELP.DAT",
        "BTL_MES.MD8",
        "BTL_SRF.MDT",
        "BUTU_SRF.MDT",
        "ITEMNAME.DAT",
        "MAGNAME.DAT",
    }
    if set(outputs) != expected:
        raise ValueError("battle UI text build has the wrong output set")
    for name, raw_row in outputs.items():
        row = _object(raw_row, f"{TEXT_BUILD_PATH}.outputs.{name}")
        if row.get("sha256") != _file_sha256(TEXT_GENERATED_ROOT / name):
            raise ValueError(f"generated {name} does not match its text build")


def _font8_tables(metrics: FontMetrics) -> tuple[bytes, dict[str, int]]:
    widths = bytearray(256)
    codes: dict[str, int] = {}
    for glyph in metrics.glyphs:
        if not 0 <= glyph.code < 256:
            raise ValueError("battle UI FONT8 code exceeds one byte")
        widths[glyph.code] = glyph.advance
        for text in (glyph.text, *glyph.aliases):
            codes.setdefault(text, glyph.code)
    return bytes(widths), codes


def _encode_font8(
    text: str,
    metrics: FontMetrics,
    max_pixels: int,
    context: str,
    *,
    max_bytes: int = 31,
) -> bytes:
    glyphs = metrics.segment_output(text)
    encoded = bytes(glyph.code for glyph in glyphs)
    pixels = sum(glyph.advance for glyph in glyphs)
    if len(encoded) > max_bytes or pixels > max_pixels:
        raise ValueError(
            f"{context} exceeds {max_bytes} bytes/{max_pixels}px "
            f"({len(encoded)} bytes, {pixels}px): {text!r}"
        )
    return encoded


def _sequential_translations(prefix: str, ids: list[str]) -> tuple[str, ...]:
    values = load_bound_translations((prefix,), required_ids=set(ids))
    return tuple(values[physical_id] for physical_id in ids)


def _race_pool(metrics: FontMetrics) -> bytes:
    ids = [f"game.normcom_tables.races.r{index:04d}" for index in range(RACE_COUNT)]
    races = _sequential_translations("game.normcom_tables.races.", ids)
    catalog = load_asset("battle/analyze_formats.json")
    entry = catalog.entries["race_heading"]
    if dict(entry.placeholders) != {"race": "demon_race"}:
        raise ValueError("battle Analyze race-heading placeholders changed")
    _reference, template, _reviewed = entry.fields["text"].resolve()
    if template.count("{race}") != 1:
        raise ValueError("battle Analyze race heading must contain one {race}")
    output = bytearray()
    for index, race in enumerate((*races[:-1], "")):
        text = template.replace("{race}", race) if race else ""
        encoded = _encode_font8(
            text,
            metrics,
            0xFFFF,
            f"battle Analyze race {index}",
            max_bytes=RACE_RECORD_BYTES,
        )
        output.extend(encoded.ljust(RACE_RECORD_BYTES, b"\0"))
    return bytes(output)


def _offset_pool(
    values: tuple[str, ...],
    metrics: FontMetrics,
    max_pixels: int,
    context: str,
) -> tuple[bytes, bytes]:
    offsets = bytearray()
    pool = bytearray()
    for index, text in enumerate(values):
        if len(pool) > 0xFFFF:
            raise ValueError(f"{context} pool exceeds u16 offsets")
        offsets.extend(struct.pack(">H", len(pool)))
        pool.extend(
            _encode_font8(text, metrics, max_pixels, f"{context} {index}")
        )
        pool.append(0)
    return bytes(offsets), bytes(pool)


def _dynamic_payloads(metrics: FontMetrics) -> dict[str, bytes]:
    widths, _codes = _font8_tables(metrics)
    demon_ids = [f"game.dvlname.o{index * 8:06x}.text" for index in range(DEMON_COUNT)]
    demons = _sequential_translations("game.dvlname.", demon_ids)
    name_offsets, name_pool = _offset_pool(
        demons, metrics, NAME_MAX_PIXELS, "battle Analyze demon name"
    )
    affinity_ids = [
        f"game.combat_analysis_affinities.affinities.r{index:04d}"
        for index in range(AFFINITY_COUNT)
    ]
    affinities = _sequential_translations(
        "game.combat_analysis_affinities.", affinity_ids
    )
    affinity_offsets, affinity_pool = _offset_pool(
        affinities, metrics, AFFINITY_MAX_PIXELS, "battle Analyze affinity"
    )
    character_ids = [
        f"game.charname.o{index * 8:06x}.text" for index in range(CHARACTER_COUNT)
    ]
    characters = _sequential_translations("game.charname.", character_ids)
    character_offsets, character_pool = _offset_pool(
        characters, metrics, PARTY_NAME_MAX_PIXELS, "battle character name"
    )
    result_ids = {
        "result_beads": "game.combat_result_labels.o053b8c",
        "result_life_stones": "game.combat_result_labels.o053ce0",
    }
    result_values = load_bound_translations(
        ("game.combat_result_labels.",), required_ids=set(result_ids.values())
    )
    return {
        "renderer_widths": widths,
        "renderer_races": _race_pool(metrics),
        "name_offsets": name_offsets,
        "name_pool": name_pool,
        "affinity_offsets": affinity_offsets,
        "affinity_pool": affinity_pool,
        "result_life_stones": _encode_font8(
            result_values[result_ids["result_life_stones"]],
            metrics,
            RESULT_LABEL_MAX_PIXELS,
            "battle result Life Stone label",
        )
        + b"\0",
        "result_beads": _encode_font8(
            result_values[result_ids["result_beads"]],
            metrics,
            RESULT_LABEL_MAX_PIXELS,
            "battle result Bead label",
        )
        + b"\0",
        "character_offsets": character_offsets,
        "character_pool": character_pool,
    }


def _packed_debug_field(
    text: str,
    metrics: FontMetrics,
    *,
    words: int,
    terminated: bool,
    context: str,
) -> bytes:
    try:
        codes = [glyph.code for glyph in metrics.segment_output(text)]
        encoded = pack_direct_codes(codes)
    except (KeyError, ValueError) as error:
        raise ValueError(f"{context} cannot be encoded: {text!r}") from error
    capacity = words - int(terminated)
    if not 1 <= len(encoded) <= capacity:
        raise ValueError(
            f"{context} uses {len(encoded)}/{capacity} packed words: {text!r}"
        )
    payload = [*encoded]
    if terminated:
        payload.append(0x8000)
    payload.extend([PACKED_PADDING_WORD] * (words - len(payload)))
    return struct.pack(f">{words}H", *payload)


def _fixed_field_payloads(metrics: FontMetrics) -> dict[str, bytes]:
    debug_ids = {physical_id for _, physical_id, _, _, _ in DEBUG_LAYOUT}
    debug_values = load_bound_translations(
        ("game.combat_debug.",), required_ids=debug_ids
    )
    payloads: dict[str, bytes] = {}
    for name, physical_id, addresses, words, terminated in DEBUG_LAYOUT:
        payload = _packed_debug_field(
            debug_values[physical_id],
            metrics,
            words=words,
            terminated=terminated,
            context=f"COMBAT debug field {physical_id}",
        )
        for mirror, _address in enumerate(addresses):
            payloads[f"{name}_{mirror}"] = payload

    uma_id = "game.normcom_tables.races.r0022"
    uma_text = load_bound_translations(
        ("game.normcom_tables.races.",), required_ids={uma_id}
    )[uma_id]
    try:
        uma_codes = tuple(glyph.code for glyph in metrics.segment_output(uma_text))
    except ValueError as error:
        raise ValueError(f"COMBAT Uma compatibility row cannot encode {uma_text!r}") from error
    # This stock table is a dead compatibility mirror after the live race
    # drawer is redirected. Preserve its guarded Japanese row if an edit no
    # longer fits the optional-terminated four-word physical record.
    if 1 <= len(uma_codes) <= 3:
        payloads["race_uma_mirror"] = struct.pack(
            f">{len(uma_codes) + 1}H", *uma_codes, 0x8000
        ).ljust(8, b"\0")
    elif len(uma_codes) == 4:
        payloads["race_uma_mirror"] = struct.pack(">4H", *uma_codes)
    return payloads


def _party_state_codes() -> tuple[tuple[int, ...], tuple[int, ...]]:
    catalog = load_asset("battle/party_panel.json")
    stock_codes = load_stock_latin_codes(FONT8_METRICS_PATH)
    output: list[tuple[int, ...]] = []
    for key, cells in (("empty", 5), ("in_party", 8)):
        try:
            text = catalog.entries[key].fields["text"].translation
            codes = tuple(stock_codes[character] for character in text)
            space = stock_codes[" "]
        except KeyError as error:
            raise ValueError(
                f"battle party {key.replace('_', ' ')} uses an unsupported stock-Latin glyph"
            ) from error
        if not text or len(codes) > cells:
            raise ValueError(
                f"battle party {key.replace('_', ' ')} uses {len(codes)}/{cells} cells"
            )
        output.append((*codes, *((space,) * (cells - len(codes)))))
    return output[0], output[1]


def _validate_fixed_recipe_contract(config: PatchRecipeConfiguration) -> None:
    expected = []
    for name, _physical_id, addresses, _words, _terminated in DEBUG_LAYOUT:
        expected.extend(
            ("combat.debug_ui", f"{name}_{mirror}", address, "combat_debug_data")
            for mirror, address in enumerate(addresses)
        )
    expected.append(
        (
            "combat.fixed_text_compatibility",
            "race_uma_mirror",
            UMA_MIRROR_ADDRESS,
            "combat_compatibility_data",
        )
    )
    actual = []
    for recipe in config.patches["COMBAT.BIN"]:
        if recipe.group not in {"combat.debug_ui", "combat.fixed_text_compatibility"}:
            continue
        actual.append(
            (
                recipe.group,
                recipe.name,
                recipe.address,
                recipe.replacement.generator,
            )
        )
    if actual != expected:
        raise ValueError("COMBAT fixed-field recipe inventory changed")

    party = [
        recipe
        for recipe in config.patches["COMBAT.BIN"]
        if recipe.group == "combat.party_labels"
    ]
    if len(party) != 1:
        raise ValueError("COMBAT party-label recipe inventory changed")
    recipe = party[0]
    if (
        recipe.name,
        recipe.address,
        recipe.replacement.kind,
        _source_names(recipe),
    ) != (
        "party_state_rows",
        0x0604C0E8,
        "assembly",
        ("battle_ui/party_state_rows.s",),
    ):
        raise ValueError("COMBAT party-label recipe contract changed")


def _source_names(recipe: PatchRecipe) -> tuple[str, ...]:
    return tuple(
        source.relative_to(ASSEMBLY_ROOT).as_posix()
        for source in recipe.replacement.sources
    )


def _source_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise ValueError(f"missing battle UI assembly source: {path}") from error


def _assembled(path: Path, address: int, symbols: dict[str, int]) -> bytes:
    try:
        result = assemble(_source_text(path), address, symbols)
    except AssemblyError as error:
        raise ValueError(f"{path}: {error}") from error
    if result.warnings:
        raise ValueError(f"{path}: assembly warnings: {result.warnings}")
    return result.data


def _place(
    payload: bytearray,
    base: int,
    address: int,
    data: bytes,
    context: str,
) -> None:
    offset = address - base
    if offset < len(payload):
        raise ValueError(f"{context} overlaps the preceding battle UI region")
    payload.extend(bytes(offset - len(payload)))
    payload.extend(data)


def _place_region(
    payload: bytearray,
    base: int,
    address: int,
    limit: int,
    data: bytes,
    context: str,
) -> None:
    capacity = limit - address
    if capacity < 0 or len(data) > capacity:
        raise ValueError(f"{context} uses {len(data)}/{capacity} bytes")
    _place(payload, base, address, data.ljust(capacity, b"\0"), context)


def _font16_layout() -> tuple[int, int]:
    document = _object(_read_json(FONT16_METRICS_PATH), str(FONT16_METRICS_PATH))
    table = _object(document.get("width_table"), f"{FONT16_METRICS_PATH}.width_table")
    code_limit = table.get("code_limit")
    storage_glyph = table.get("storage_glyph")
    if (
        document.get("version") != 2
        or type(code_limit) is not int
        or not 1 <= code_limit <= 0x7FFF
        or type(storage_glyph) is not int
        or storage_glyph < 0
    ):
        raise ValueError("invalid battle FONT16 width-table layout")
    return code_limit, storage_glyph * 32


def _build_renderer_cave(
    recipe: PatchRecipe,
    payloads: dict[str, bytes],
) -> tuple[bytes, dict[str, int]]:
    expected_sources = (
        "font8_pixel_blitter.s",
        "font8_fixed_name.s",
        "battle_ui/analysis_counted_drawer.s",
        "battle_ui/font16_surface_blitter.s",
        "battle_ui/font16_width_adapter.s",
        "battle_ui/help_drawer.s",
        "battle_ui/battle_item_drawer.s",
    )
    if recipe.address != RENDERER_CAVE or _source_names(recipe) != expected_sources:
        raise ValueError("battle renderer assembly contract changed")
    (
        pixel_source,
        fallback_source,
        counted_source,
        surface_source,
        adapter_source,
        help_source,
        item_source,
    ) = recipe.replacement.sources
    output = bytearray()

    _place(
        output,
        recipe.address,
        RENDERER_CAVE,
        _assembled(pixel_source, RENDERER_CAVE, {"FONT8": FONT8_ADDRESS}),
        "battle FONT8 pixel blitter",
    )
    _place_region(
        output,
        recipe.address,
        RENDERER_WIDTHS,
        RENDERER_FALLBACK,
        payloads["renderer_widths"],
        "battle FONT8 widths",
    )
    _place(
        output,
        recipe.address,
        RENDERER_FALLBACK,
        _assembled(
            fallback_source,
            RENDERER_FALLBACK,
            {
                "WIDTHS": RENDERER_WIDTHS,
                "PIXEL": RENDERER_CAVE,
                "STOCK": STOCK_GLYPH,
                "STRIDE": 0x0200,
            },
        ),
        "battle compact-name fallback",
    )
    _place_region(
        output,
        recipe.address,
        RENDERER_RACES,
        ANALYSIS_COUNTED_DRAWER,
        payloads["renderer_races"],
        "battle Analyze races",
    )
    _place(
        output,
        recipe.address,
        ANALYSIS_COUNTED_DRAWER,
        _assembled(
            counted_source,
            ANALYSIS_COUNTED_DRAWER,
            {
                "RACE_SOURCE": RACE_SOURCE,
                "RACE_SOURCE_STRIDE": 7,
                "RACE_COUNT": RACE_COUNT,
                "RACE_POOL": RENDERER_RACES,
                "RACE_RECORD_SIZE": RACE_RECORD_BYTES,
                "DVL_SOURCE": DVL_SOURCE,
                "DVL_COUNT": DEMON_COUNT,
                "NAME_OFFSETS": NAME_OFFSETS,
                "NAME_POOL": NAME_POOL,
                "WIDTHS": RENDERER_WIDTHS,
                "PIXEL": RENDERER_CAVE,
                "STRIDE": 0x0200,
                "STOCK_GLYPH": STOCK_GLYPH,
                "STOCK_COUNTED": STOCK_COUNTED,
            },
        ),
        "battle Analyze counted drawer",
    )
    _place(
        output,
        recipe.address,
        BATTLE_SURFACE_BLITTER,
        _assembled(
            surface_source,
            BATTLE_SURFACE_BLITTER,
            {
                "FONT16_POINTER": FONT16_POINTER,
                "PATTERN_LUT": GLYPH_PATTERN_LUT,
                "MASK_LUT": GLYPH_MASK_LUT,
            },
        ),
        "battle FONT16 surface blitter",
    )
    code_limit, width_offset = _font16_layout()
    adapter_symbols = {
        "CODE_LIMIT": code_limit,
        "FONT16_POINTER": FONT16_POINTER,
        "WIDTH_OFFSET": width_offset,
        "BLITTER": BATTLE_SURFACE_BLITTER,
    }
    _place(
        output,
        recipe.address,
        BATTLE_SURFACE_DRAWER,
        _assembled(
            adapter_source,
            BATTLE_SURFACE_DRAWER,
            {**adapter_symbols, "MAX_WIDTH": 176},
        ),
        "battle event-window surface adapter",
    )
    _place(
        output,
        recipe.address,
        BATTLE_HELP_RAW_DRAWER,
        _assembled(
            adapter_source,
            BATTLE_HELP_RAW_DRAWER,
            {**adapter_symbols, "MAX_WIDTH": 326},
        ),
        "battle help surface adapter",
    )
    _place(
        output,
        recipe.address,
        BATTLE_HELP_DRAWER,
        _assembled(
            help_source,
            BATTLE_HELP_DRAWER,
            {
                "DRAWER": BATTLE_HELP_RAW_DRAWER,
                "PACKED_LIMIT": 128,
                "SPACE_CODE": 267,
            },
        ),
        "battle help packed drawer",
    )
    _place(
        output,
        recipe.address,
        BATTLE_ITEM_DRAWER,
        _assembled(
            item_source,
            BATTLE_ITEM_DRAWER,
            {
                "ITEM_FIRST": 0x00228C04,
                "ITEM_END": 0x0022F7A0,
                "ITEM_BASE": 0x00228C00,
                "MAGIC_FIRST": 0x0022F7A4,
                "MAGIC_END": 0x00235740,
                "MAGIC_BASE": 0x0022F7A0,
                "WIDTHS": RENDERER_WIDTHS,
                "PIXEL": RENDERER_CAVE,
                "STRIDE": 0x6C,
                "Y_OFFSET": 0xD8,
                "MAX_WIDTH": 80,
                "STOCK": 0x060496BC,
            },
        ),
        "battle item-name drawer",
    )
    if len(output) != len(recipe.expected):
        raise ValueError(
            f"battle renderer cave uses {len(output)}/{len(recipe.expected)} bytes"
        )
    return bytes(output), {
        "analysis_counted_drawer": ANALYSIS_COUNTED_DRAWER,
        "battle_surface_drawer": BATTLE_SURFACE_DRAWER,
        "battle_help_drawer": BATTLE_HELP_DRAWER,
        "battle_item_drawer": BATTLE_ITEM_DRAWER,
    }


def _build_analysis_cave(
    recipe: PatchRecipe,
    payloads: dict[str, bytes],
) -> tuple[bytes, dict[str, int]]:
    expected_sources = (
        "battle_ui/analysis_affinity_drawer.s",
        "battle_ui/analysis_skill_drawer.s",
        "battle_ui/panel_full_name_drawer.s",
        "battle_ui/result_label_drawer.s",
        "battle_ui/result_name_drawer.s",
        "battle_ui/result_item_drawer.s",
        "battle_ui/event_item_drawer.s",
        "battle_ui/combat_panel_drawer.s",
    )
    if recipe.address != ANALYSIS_CAVE or _source_names(recipe) != expected_sources:
        raise ValueError("battle analysis assembly contract changed")
    (
        affinity_source,
        skill_source,
        full_name_source,
        result_label_source,
        result_name_source,
        result_item_source,
        event_item_source,
        panel_source,
    ) = recipe.replacement.sources
    output = bytearray()

    _place_region(
        output,
        recipe.address,
        NAME_OFFSETS,
        NAME_POOL,
        payloads["name_offsets"],
        "battle demon-name offsets",
    )
    _place_region(
        output,
        recipe.address,
        NAME_POOL,
        AFFINITY_OFFSETS,
        payloads["name_pool"],
        "battle demon-name pool",
    )
    _place_region(
        output,
        recipe.address,
        AFFINITY_OFFSETS,
        AFFINITY_POOL,
        payloads["affinity_offsets"],
        "battle affinity offsets",
    )
    _place_region(
        output,
        recipe.address,
        AFFINITY_POOL,
        AFFINITY_DRAWER,
        payloads["affinity_pool"],
        "battle affinity pool",
    )
    _place(
        output,
        recipe.address,
        AFFINITY_DRAWER,
        _assembled(
            affinity_source,
            AFFINITY_DRAWER,
            {
                "SOURCE": AFFINITY_SOURCE,
                "SOURCE_SIZE": AFFINITY_COUNT * 10,
                "SOURCE_STRIDE": 10,
                "COUNT": AFFINITY_COUNT,
                "OFFSETS": AFFINITY_OFFSETS,
                "POOL": AFFINITY_POOL,
                "WIDTHS": RENDERER_WIDTHS,
                "STRIDE": 0x0200,
                "Y_OFFSET": 0x0400,
                "MAX_WIDTH": AFFINITY_MAX_PIXELS,
                "PIXEL": RENDERER_CAVE,
                "STOCK_COUNTED": 0x06050130,
            },
        ),
        "battle Analyze affinity drawer",
    )
    _place(
        output,
        recipe.address,
        ANALYSIS_SKILL_DRAWER,
        _assembled(
            skill_source,
            ANALYSIS_SKILL_DRAWER,
            {
                "MAGIC_FIRST": 0x0022F7A4,
                "MAGIC_END": 0x00235740,
                "MAGIC_BASE": 0x0022F7A0,
                "WIDTHS": RENDERER_WIDTHS,
                "PIXEL": RENDERER_CAVE,
                "STRIDE": 0x0200,
                "MAX_WIDTH": AFFINITY_MAX_PIXELS,
                "STOCK_COUNTED": STOCK_COUNTED,
            },
        ),
        "battle Analyze skill drawer",
    )
    _place(
        output,
        recipe.address,
        PANEL_FULL_NAME_DRAWER,
        _assembled(
            full_name_source,
            PANEL_FULL_NAME_DRAWER,
            {
                "ITEM_FIRST": 0x00228C04,
                "ITEM_END": 0x0022F7A0,
                "ITEM_BASE": 0x00228C00,
                "MAGIC_FIRST": 0x0022F7A4,
                "MAGIC_END": 0x00235740,
                "MAGIC_BASE": 0x0022F7A0,
                "WIDTHS": RENDERER_WIDTHS,
                "PIXEL": RENDERER_CAVE,
                "STRIDE": 0x0200,
                "Y_OFFSET": 0x0400,
                "FALLBACK": RENDERER_FALLBACK,
            },
        ),
        "battle panel full-name drawer",
    )
    _place_region(
        output,
        recipe.address,
        RESULT_LIFE_STONES,
        RESULT_BEADS,
        payloads["result_life_stones"],
        "battle result Life Stone label",
    )
    _place_region(
        output,
        recipe.address,
        RESULT_BEADS,
        RESULT_LABEL_DRAWER,
        payloads["result_beads"],
        "battle result Bead label",
    )
    _place(
        output,
        recipe.address,
        RESULT_LABEL_DRAWER,
        _assembled(
            result_label_source,
            RESULT_LABEL_DRAWER,
            {
                "LIFE_STONES": RESULT_LIFE_STONES,
                "BEADS": RESULT_BEADS,
                "WIDTHS": RENDERER_WIDTHS,
                "PIXEL": RENDERER_CAVE,
                "STOCK": STOCK_GLYPH,
            },
        ),
        "battle result label drawer",
    )
    _place_region(
        output,
        recipe.address,
        CHARACTER_OFFSETS,
        CHARACTER_POOL,
        payloads["character_offsets"],
        "battle character-name offsets",
    )
    _place_region(
        output,
        recipe.address,
        CHARACTER_POOL,
        RESULT_NAME_DRAWER,
        payloads["character_pool"],
        "battle character-name pool",
    )
    _place(
        output,
        recipe.address,
        RESULT_NAME_DRAWER,
        _assembled(
            result_name_source,
            RESULT_NAME_DRAWER,
            {
                "CODENAME": 0x0023FFD0,
                "OFFSETS": CHARACTER_OFFSETS,
                "POOL": CHARACTER_POOL,
                "DEST0": 0x25E6902E,
                "DEST1": 0x25E6905E,
                "WIDTHS": RENDERER_WIDTHS,
                "PIXEL": RENDERER_CAVE,
            },
        ),
        "battle result character-name drawer",
    )
    _place(
        output,
        recipe.address,
        RESULT_ITEM_DRAWER,
        _assembled(
            result_item_source,
            RESULT_ITEM_DRAWER,
            {
                "ITEM_BEFORE_FIRST": 0x00228BA0,
                "ITEM_BASE": 0x00228C00,
                "DEST0": 0x25E6B82E,
                "DEST1": 0x25E6B85E,
                "DEST2": 0x25E6C82E,
                "DEST3": 0x25E6C85E,
                "WIDTHS": RENDERER_WIDTHS,
                "PIXEL": RENDERER_CAVE,
                "MAX_WIDTH": 80,
            },
        ),
        "battle result item drawer",
    )
    _place(
        output,
        recipe.address,
        EVENT_ITEM_DRAWER,
        _assembled(
            event_item_source,
            EVENT_ITEM_DRAWER,
            {
                "ITEM_BASE_POINTER": 0x0607221C,
                "ITEM_FULL_NAME_FROM_COMPACT": 0x5A,
                "FRAMEBUFFER_POINTER": 0x060721DC,
                "FRAMEBUFFER_STRIDE": 320,
                "FRAMEBUFFER_BYTE_STRIDE": 160,
                "COLUMN_WIDTH": 106,
                "ROW_HEIGHT": 12,
                "START_X": 16,
                "START_Y": 4,
                "MAX_WIDTH": 80,
                "WIDTHS": RENDERER_WIDTHS,
                "PIXEL": RENDERER_CAVE,
            },
        ),
        "battle event-window item drawer",
    )
    _place(
        output,
        recipe.address,
        PANEL_DRAWER,
        _assembled(
            panel_source,
            PANEL_DRAWER,
            {
                "DVL_BASE": DVL_SOURCE,
                "DVL_END": 0x0023FFD0,
                "DVL_OFFSETS": NAME_OFFSETS,
                "DVL_POOL": NAME_POOL,
                "CHAR_BASE": 0x0023FFD0,
                "CHAR_FIRST": 0x0023FFD8,
                "CHAR_END": 0x00240000,
                "CHAR_OFFSETS": CHARACTER_OFFSETS,
                "CHAR_POOL": CHARACTER_POOL,
                "WIDTHS": RENDERER_WIDTHS,
                "PIXEL": RENDERER_CAVE,
                "STRIDE": 0x0200,
                "FALLBACK": PANEL_FULL_NAME_DRAWER,
            },
        ),
        "battle complete-name party panel",
    )
    if len(output) != len(recipe.expected):
        raise ValueError(
            f"battle analysis cave uses {len(output)}/{len(recipe.expected)} bytes"
        )
    return bytes(output), {
        "panel_drawer": PANEL_DRAWER,
        "analysis_affinity_drawer": AFFINITY_DRAWER,
        "analysis_skill_drawer": ANALYSIS_SKILL_DRAWER,
        "result_label_drawer": RESULT_LABEL_DRAWER,
        "result_name_drawer": RESULT_NAME_DRAWER,
        "result_item_drawer": RESULT_ITEM_DRAWER,
        "event_item_drawer": EVENT_ITEM_DRAWER,
    }


def _build_decoder_cave(
    recipe: PatchRecipe,
    dictionary_table: bytes,
    *,
    target: str,
) -> bytes:
    if target == "COMBAT.BIN":
        expected_name = "btl_srf_decoder"
        expected_address = BTL_DECODER
        expected_sources = (
            "battle_ui/btl_record_hook.s",
            "battle_ui/packed_record_decoder.s",
        )
        symbols = {
            "SCRATCH": BTL_SCRATCH,
            "CONTINUATION": BTL_CONTINUATION,
        }
    else:
        expected_name = "butu_srf_decoder"
        expected_address = BUTU_DECODER
        expected_sources = (
            "battle_ui/butu_record_hook.s",
            "battle_ui/packed_record_decoder.s",
        )
        symbols = {
            "SCRATCH": BUTU_SCRATCH,
            "ROW_STRIDE": 0x2000,
            "LINE_WIDTH": 0x00B0,
            "HELPER": 0x0603DB90,
            "CONTINUATION": BUTU_CONTINUATION,
        }
    if (
        recipe.name != expected_name
        or recipe.address != expected_address
        or _source_names(recipe) != expected_sources
    ):
        raise ValueError(f"{target} packed decoder assembly contract changed")
    source = "\n".join(_source_text(path) for path in recipe.replacement.sources)
    base_symbols = {
        **symbols,
        "DICTIONARY": recipe.address,
        "SPACE_CODE": 267,
        "TERMINATOR": 0x8000,
    }
    try:
        probe = assemble(source, recipe.address, base_symbols)
    except AssemblyError as error:
        raise ValueError(f"{target} packed decoder: {error}") from error
    if probe.warnings:
        raise ValueError(f"{target} packed decoder warnings: {probe.warnings}")
    dictionary_address = (recipe.address + len(probe.data) + 3) & ~3
    try:
        code = assemble(
            source,
            recipe.address,
            {**base_symbols, "DICTIONARY": dictionary_address},
        )
    except AssemblyError as error:
        raise ValueError(f"{target} packed decoder: {error}") from error
    if code.warnings or len(code.data) != len(probe.data):
        raise ValueError(f"{target} packed decoder layout is unstable")
    output = bytearray(code.data)
    output.extend(bytes(dictionary_address - recipe.address - len(output)))
    output.extend(dictionary_table)
    if len(output) != len(recipe.expected):
        raise ValueError(
            f"{target} packed decoder uses {len(output)}/{len(recipe.expected)} bytes"
        )
    return bytes(output)


def _instruction(recipe: PatchRecipe) -> bytes:
    assert recipe.replacement.instruction is not None
    try:
        result = assemble(recipe.replacement.instruction, recipe.address)
    except AssemblyError as error:
        raise ValueError(f"{recipe.group}/{recipe.name}: {error}") from error
    if result.warnings or len(result.data) != len(recipe.expected):
        raise ValueError(f"{recipe.group}/{recipe.name}: invalid instruction")
    return result.data


def _standalone_assembly(
    recipe: PatchRecipe,
    target: str,
    party_state_codes: tuple[tuple[int, ...], tuple[int, ...]],
) -> bytes:
    if recipe.name == "btl_srf_hook" and target == "COMBAT.BIN":
        source = "jump_r0.s"
        symbols = {"TARGET": BTL_DECODER}
    elif recipe.name == "butu_srf_hook" and target == "NORMCOM.BIN":
        source = "battle_ui/butu_trampoline.s"
        symbols = {"TARGET": BUTU_DECODER}
    elif recipe.name == "btl_srf_loop_reentry" and target == "COMBAT.BIN":
        source = "battle_ui/btl_loop_reentry.s"
        symbols = {"TARGET": BTL_HOOK}
    elif recipe.name == "party_state_rows" and target == "COMBAT.BIN":
        source = "battle_ui/party_state_rows.s"
        empty, in_party = party_state_codes
        symbols = {
            **{f"EMPTY{index}": code for index, code in enumerate(empty)},
            **{f"IN_PARTY{index}": code for index, code in enumerate(in_party)},
        }
    else:
        raise ValueError(f"unsupported standalone assembly {target}/{recipe.name}")
    if _source_names(recipe) != (source,):
        raise ValueError(f"{target}/{recipe.name}: assembly source changed")
    result = _assembled(recipe.replacement.sources[0], recipe.address, symbols)
    if recipe.name == "btl_srf_loop_reentry":
        if len(result) != len(recipe.expected) + 2:
            raise ValueError("BTL_SRF re-entry must expose its stock delay slot")
        result = result[: len(recipe.expected)]
    if len(result) != len(recipe.expected):
        raise ValueError(f"{target}/{recipe.name}: assembly size changed")
    return result


def _bind_patches(
    config: PatchRecipeConfiguration,
    metrics: FontMetrics,
    metrics16: FontMetrics,
    dictionary_table: bytes,
) -> dict[str, tuple[Patch, ...]]:
    payloads = _dynamic_payloads(metrics)
    fixed_payloads = _fixed_field_payloads(metrics16)
    party_state_codes = _party_state_codes()
    _validate_fixed_recipe_contract(config)
    renderer_recipe = next(
        recipe
        for recipe in config.patches["COMBAT.BIN"]
        if recipe.name == "renderer_cave"
    )
    analysis_recipe = next(
        recipe
        for recipe in config.patches["COMBAT.BIN"]
        if recipe.name == "analysis_english_cave"
    )
    renderer, links = _build_renderer_cave(renderer_recipe, payloads)
    analysis, analysis_links = _build_analysis_cave(analysis_recipe, payloads)
    if set(links) & set(analysis_links):
        raise ValueError("battle UI assembly links collide")
    links.update(analysis_links)

    output: dict[str, tuple[Patch, ...]] = {}
    for target in ("COMBAT.BIN", "NORMCOM.BIN"):
        bound = []
        assembly_seen = set()
        for recipe in config.patches[target]:
            replacement_recipe = recipe.replacement
            if replacement_recipe.kind == "assembly":
                assembly_seen.add(recipe.name)
                if recipe.name == "renderer_cave":
                    replacement = renderer
                elif recipe.name == "analysis_english_cave":
                    replacement = analysis
                elif recipe.name in {"btl_srf_decoder", "butu_srf_decoder"}:
                    replacement = _build_decoder_cave(
                        recipe, dictionary_table, target=target
                    )
                else:
                    replacement = _standalone_assembly(
                        recipe, target, party_state_codes
                    )
            elif replacement_recipe.kind == "linked_pointer":
                assert replacement_recipe.link is not None
                try:
                    replacement = struct.pack(">I", links[replacement_recipe.link])
                except KeyError as error:
                    raise ValueError(
                        f"{target}/{recipe.name}: unknown assembly link "
                        f"{replacement_recipe.link!r}"
                    ) from error
            elif replacement_recipe.kind == "pointer":
                assert replacement_recipe.pointer is not None
                replacement = struct.pack(">I", replacement_recipe.pointer)
            elif replacement_recipe.kind == "instruction":
                replacement = _instruction(recipe)
            elif (
                replacement_recipe.kind == "generated"
                and replacement_recipe.generator == "zero_scratch"
            ):
                replacement = bytes(len(recipe.expected))
            elif replacement_recipe.kind == "generated" and replacement_recipe.generator in {
                "combat_debug_data",
                "combat_compatibility_data",
            }:
                replacement = fixed_payloads.get(recipe.name, recipe.expected)
            else:
                raise ValueError(f"unsupported battle UI recipe {target}/{recipe.name}")
            if len(replacement) != len(recipe.expected):
                raise ValueError(f"{target}/{recipe.name}: replacement size changed")
            bound.append(
                Patch(
                    recipe.group,
                    recipe.name,
                    recipe.address,
                    recipe.expected,
                    replacement,
                )
            )
        expected_assembly = (
            {
                "renderer_cave",
                "analysis_english_cave",
                "btl_srf_decoder",
                "btl_srf_hook",
                "btl_srf_loop_reentry",
                "party_state_rows",
            }
            if target == "COMBAT.BIN"
            else {"butu_srf_decoder", "butu_srf_hook"}
        )
        if assembly_seen != expected_assembly:
            raise ValueError(f"{target} has an incomplete battle UI assembly contract")
        output[target] = tuple(bound)
    return output


def _validate_decoder_capacity(path: Path, count: int) -> None:
    data = path.read_bytes()
    pointers = struct.unpack_from(f">{count}H", data)
    dictionary = load_event_dictionary(CODEC_PATH)
    body_words = (len(data) - 0x400) // 2
    for index, start in enumerate(pointers):
        stop = pointers[index + 1] if index + 1 < count else body_words
        words = list(struct.unpack_from(f">{stop - start}H", data, 0x400 + start * 2))
        try:
            end = words.index(0x8000)
        except ValueError as error:
            raise ValueError(f"{path.name}: record {index} has no terminator") from error
        decoded = dictionary.decode_words(words[:end])
        if len(decoded) > DECODED_RECORD_WORDS:
            raise ValueError(
                f"{path.name}: record {index} decodes to "
                f"{len(decoded)}/{DECODED_RECORD_WORDS} words"
            )


def build_battle_ui() -> dict[Path, bytes]:
    _validate_surfaces()
    config = load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="battle.ui",
        target_names={"COMBAT.BIN", "NORMCOM.BIN"},
        input_names={
            "font8_metrics_sha256",
            "font16_metrics_sha256",
            "event_runtime_table_sha256",
        },
    )
    dictionary_table = load_event_dictionary(CODEC_PATH).runtime_table()
    dictionary_digest = _sha256(dictionary_table)
    actual_inputs = {
        "font8_metrics_sha256": _file_sha256(FONT8_METRICS_PATH),
        "font16_metrics_sha256": _file_sha256(FONT16_METRICS_PATH),
        "event_runtime_table_sha256": dictionary_digest,
    }
    if actual_inputs != config.inputs:
        raise ValueError("battle UI runtime inputs changed")
    _validate_text_build(dictionary_digest)
    _validate_decoder_capacity(TEXT_GENERATED_ROOT / "BTL_SRF.MDT", 363)
    _validate_decoder_capacity(TEXT_GENERATED_ROOT / "BUTU_SRF.MDT", 144)

    validated = validate_source(load_catalog()["game"])
    stock_files = read_source_files(validated, ("COMBAT.BIN", "NORMCOM.BIN"))
    for name, stock in stock_files.items():
        contract = config.targets[name]
        if len(stock) != contract.size or _sha256(stock) != contract.stock_sha256:
            raise ValueError(f"stock {name} does not match the battle UI target")

    negotiation_outputs = build_battle_negotiation()
    combat_base = negotiation_outputs[COMBAT_OUTPUT_PATH]
    font8 = FontMetrics.load(FONT8_METRICS_PATH)
    font16 = FontMetrics.load(FONT16_METRICS_PATH)
    patches = _bind_patches(config, font8, font16, dictionary_table)
    combat_patches = patches["COMBAT.BIN"]
    normcom_patches = patches["NORMCOM.BIN"]
    combat = apply_patches(
        combat_base, config.targets["COMBAT.BIN"].load_address, combat_patches
    )
    normcom = apply_patches(
        stock_files["NORMCOM.BIN"],
        config.targets["NORMCOM.BIN"].load_address,
        normcom_patches,
    )
    all_patches = (*combat_patches, *normcom_patches)
    assembly_files = tuple(
        sorted(
            {
                source
                for recipes in config.patches.values()
                for recipe in recipes
                for source in recipe.replacement.sources
            }
        )
    )
    manifest = {
        "version": 1,
        "surface": "battle.ui",
        "patch_config_sha256": _file_sha256(CONFIG_PATH),
        "text_build_sha256": _file_sha256(TEXT_BUILD_PATH),
        "party_panel_asset_sha256": _file_sha256(PARTY_PANEL_ASSET_PATH),
        "base_combat_sha256": _sha256(combat_base),
        "assembly_inputs": {
            path.relative_to(ENGINE_ROOT).as_posix(): _file_sha256(path)
            for path in assembly_files
        },
        "outputs": {
            "COMBAT.BIN": {"sha256": _sha256(combat)},
            "NORMCOM.BIN": {"sha256": _sha256(normcom)},
        },
        "patch_groups": list(dict.fromkeys(patch.group for patch in all_patches)),
        "patches": len(all_patches),
    }
    return {
        COMBAT_OUTPUT_PATH: combat,
        NORMCOM_OUTPUT_PATH: normcom,
        BUILD_PATH: (json.dumps(manifest, indent=2) + "\n").encode("utf-8"),
    }
