"""Compose MAZE's fixed field-message window from authored text assets."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from engine.core.config_io import object_value, read_json
from engine.core.patch_recipes import (
    PatchRecipeConfiguration,
    load_patch_recipe_configuration,
    resolve_recipe_expected,
)
from engine.core.patching import Patch, apply_patches
from engine.core.sh2 import Assembly, AssemblyError, assemble_file
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
from text.util.event_codec import pack_direct_codes
from text.util.event_repack import FontMetrics
from text.util.surfaces import load_surfaces


ENGINE_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = ENGINE_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "field_messages.json"
FONT_ROOT = SATURN_ROOT / "font" / "generated" / "game"
FONT16_PATH = FONT_ROOT / "FONT16.FON"
FONT16_METRICS_PATH = FONT_ROOT / "FONT16_metrics.json"
FONT8_METRICS_PATH = FONT_ROOT / "FONT8_metrics.json"
ITEMNAME_PATH = SATURN_ROOT / "text" / "generated" / "game" / "ITEMNAME.DAT"
ITEMNAME_BUILD_PATH = (
    SATURN_ROOT / "text" / "generated" / "game" / "battle_ui_build.json"
)
ASSET_PATH = ASSET_ROOT / "field" / "messages.json"
BINDING_PATH = BINDING_ROOT / "field_messages.json"
CORPUS_FILES = (
    CORPUS_ROOT / "game" / "addressed" / "maze_messages.json",
    CORPUS_ROOT / "game" / "addressed" / "maze_speech_choices_static.json",
)
ASSET_FILES = (ASSET_PATH,)
RUNTIME_INPUT_FILES = (
    FONT16_PATH,
    FONT16_METRICS_PATH,
    FONT8_METRICS_PATH,
    ITEMNAME_PATH,
    ITEMNAME_BUILD_PATH,
    SATURN_ROOT / "text" / "config" / "surfaces.json",
    SATURN_ROOT / "rom" / "discs.json",
    BINDING_PATH,
    *CORPUS_FILES,
)

TARGET = "MAZE.BIN"
LOAD_ADDRESS = 0x06020000
TARGET_SIZE = 169_264
FONT16_BASE = 0x0021A000
ITEMNAME_BASE = 0x00228C00

COMPOSITOR = 0x06022C00
MESSAGE_DISPLAY = 0x06022DC0
ITEM_TEMPLATES = 0x06022E40
TOKEN_MAP = 0x06023020
DYNAMIC_TEMPLATES = 0x06023220
MAPPING_TABLE = 0x06023320
MESSAGE_STRINGS = 0x06023380
MESSAGE_BUFFER = 0x06023620
MESSAGE_ROW = 0x060236A0
CHOICE_DRAW = 0x060236C0
CHOICE_BITMAPS = 0x06023720
CHOICE_ROW = 0x060237E0
CAVE_LIMIT = 0x06023800

MESSAGE_SCRATCH_CODE = 0x0748
CHOICE_SCRATCH_CODE = 0x0756
MESSAGE_CELLS = 14
CHOICE_CELLS = 3
MESSAGE_BUFFER_WORDS = 64
PROMPT_CODE = 0x00C5
CURRENCY_YEN_CODE = 0x00C0
CURRENCY_MAG_CODE = 0x00C1
ITEM_RECORDS = 287
ITEM_RECORD_SIZE = 0x60
ITEM_POINTER_OFFSET = 0x5E
ITEM_NAME_LIMIT = 32

STATIC_FIELDS = (
    ("talk_prompt", 0x0250E4),
    ("operation_disabled", 0x025124),
    ("nothing_notable", 0x025150),
    ("nothing_found", 0x02516C),
    ("inventory_full", 0x025188),
    ("already_searched", 0x0251A4),
    ("enemy_surprise", 0x025234),
    ("enemy_behind", 0x025250),
    ("preemptive_chance", 0x02526C),
    ("auto_recover_on", 0x0252B4),
    ("no_effect", 0x0252D0),
)
DIRECT_RECORDS = {
    "operation_disabled": 14,
    "nothing_notable": 14,
    "nothing_found": 14,
    "inventory_full": 14,
    "auto_recover_on": 10,
    "no_effect": 14,
}
CHOICE_IDS = {
    "choice_yes": "game.maze_speech_choices_static.o0250d0",
    "choice_no": "game.maze_speech_choices_static.o0250d6",
}
ALL_MESSAGE_OFFSETS = (
    0x0250E4,
    0x025124,
    0x025150,
    0x02516C,
    0x025188,
    0x0251A4,
    0x0251D0,
    0x0251DC,
    0x0251E8,
    0x0251F4,
    0x025234,
    0x025250,
    0x02526C,
    0x0252B4,
    0x0252D0,
)
REQUIRED_IDS = frozenset(
    {
        *(f"game.maze_messages.o{offset:06x}" for offset in ALL_MESSAGE_OFFSETS),
        *CHOICE_IDS.values(),
    }
)


@dataclass(frozen=True, slots=True)
class RuntimeBuild:
    assembly: Mapping[str, bytes]
    generated: Mapping[str, bytes]
    links: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class FieldMessagesBuild:
    data: bytes
    patches: tuple[Patch, ...]
    asset_files: tuple[Path, ...]
    assembly_files: tuple[Path, ...]
    runtime_input_files: tuple[Path, ...]
    source_inputs: Mapping[str, str]


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        return _sha256(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"missing field-message input: {path}") from error


def _source_maze() -> bytes:
    catalog = load_catalog()
    try:
        game = catalog["game"]
    except KeyError as error:
        raise ValueError("disc catalog has no game source") from error
    source = read_source_files(validate_source(game, verify_hashes=False), (TARGET,))
    return source[TARGET]


def _configuration() -> PatchRecipeConfiguration:
    return load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="field.messages",
        target_names={TARGET},
        input_names={
            "font16_sha256",
            "font16_metrics_sha256",
            "font8_metrics_sha256",
        },
    )


def _validate_inputs(
    config: PatchRecipeConfiguration,
    base: bytes,
    stock: bytes,
) -> None:
    target = config.targets[TARGET]
    if target.load_address != LOAD_ADDRESS or target.size != TARGET_SIZE:
        raise ValueError("field-message target geometry changed")
    if len(base) != TARGET_SIZE or len(stock) != TARGET_SIZE:
        raise ValueError("field-message MAZE.BIN size changed")
    if _sha256(stock) != target.stock_sha256:
        raise ValueError("field-message stock MAZE.BIN revision changed")
    actual = {
        "font16_sha256": _file_sha256(FONT16_PATH),
        "font16_metrics_sha256": _file_sha256(FONT16_METRICS_PATH),
        "font8_metrics_sha256": _file_sha256(FONT8_METRICS_PATH),
    }
    for name, expected in config.inputs.items():
        if actual[name] != expected:
            raise ValueError(
                f"field-message {name} expected SHA-256 {expected}, "
                f"found {actual[name]}"
            )
    _validate_itemname_build(actual)


def _validate_itemname_build(font_hashes: Mapping[str, str]) -> None:
    """Bind the mutable item catalogue to the text build that produced it."""
    document = object_value(read_json(ITEMNAME_BUILD_PATH), str(ITEMNAME_BUILD_PATH))
    if document.get("version") != 1 or document.get("surface") != "battle.ui":
        raise ValueError("ITEMNAME text build has the wrong surface")
    for name in ("font16_metrics_sha256", "font8_metrics_sha256"):
        if document.get(name) != font_hashes[name]:
            raise ValueError(f"ITEMNAME text build uses different {name}")
    outputs = object_value(
        document.get("outputs"), f"{ITEMNAME_BUILD_PATH}.outputs"
    )
    itemname = object_value(
        outputs.get("ITEMNAME.DAT"),
        f"{ITEMNAME_BUILD_PATH}.outputs.ITEMNAME.DAT",
    )
    if itemname.get("records") != ITEM_RECORDS:
        raise ValueError("ITEMNAME text-build inventory changed")
    if itemname.get("sha256") != _file_sha256(ITEMNAME_PATH):
        raise ValueError("ITEMNAME.DAT does not match its text build")


def _bound_terms() -> Mapping[str, str]:
    physical = load_physical_record_files(CORPUS_FILES)
    return load_bound_translations(
        ("game.maze_messages.", "game.maze_speech_choices_static."),
        required_ids=REQUIRED_IDS,
        binding_paths=(BINDING_PATH,),
        physical_records=physical,
    )


def _asset_translation(asset_ref: str, variant: str | None = None) -> str:
    catalog = load_asset("field/messages.json")
    _reference, translation, _reviewed = catalog.field(asset_ref).resolve(variant)
    if not translation:
        raise ValueError(f"field-message asset {asset_ref} is untranslated")
    return translation


def _template(value: str, marker: str, context: str) -> tuple[str, str]:
    if value.count(marker) != 1:
        raise ValueError(f"{context} must contain exactly one {marker}")
    prefix, suffix = value.split(marker)
    if "{" in prefix + suffix or "}" in prefix + suffix:
        raise ValueError(f"{context} contains unsupported template syntax")
    return prefix, suffix


def _templates() -> dict[str, tuple[str, str]]:
    output = {
        name: _template(_asset_translation(f"{name}.text"), "{item}", name)
        for name in ("item_found", "item_obtained", "item_full")
    }
    yen = _template(
        _asset_translation("currency_obtained.text"),
        "{yen_symbol}{currency_amount}",
        "currency_obtained yen",
    )
    mag = _template(
        _asset_translation("currency_obtained.text", "magnetite"),
        "{mag_symbol}{currency_amount}",
        "currency_obtained magnetite",
    )
    output["currency_yen"] = yen
    output["currency_mag"] = mag
    return output


def _font16_layout(metrics: FontMetrics) -> tuple[int, int]:
    import json

    try:
        document = json.loads(FONT16_METRICS_PATH.read_text(encoding="utf-8"))
        table = document["width_table"]
        storage = table["storage_glyph"]
        limit = table["code_limit"]
    except (FileNotFoundError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("invalid field-message FONT16 width-table metadata") from error
    if (
        type(storage) is not int
        or type(limit) is not int
        or storage < 0
        or limit <= 0
        or len(metrics.glyphs) == 0
    ):
        raise ValueError("invalid field-message FONT16 width-table layout")
    return limit, storage * 32


def _encode(text: str, metrics: FontMetrics, context: str) -> tuple[int, ...]:
    if "{" in text or "}" in text or "\n" in text:
        raise ValueError(f"{context} contains unsupported controls")
    try:
        return tuple(glyph.code for glyph in metrics.segment_output(text))
    except ValueError as error:
        raise ValueError(f"{context}: {error}") from error


def _measure(codes: tuple[int, ...], metrics: FontMetrics) -> int:
    advances = {glyph.code: glyph.advance for glyph in metrics.glyphs}
    return sum(advances.get(code, 16) for code in codes)


def _direct_record(
    text: str,
    words: int,
    metrics: FontMetrics,
    context: str,
    selector: bytes | None = None,
) -> bytes:
    encoded = tuple(pack_direct_codes(list(_encode(text, metrics, context))))
    if len(encoded) > words:
        if selector is not None:
            if len(selector) != words * 2:
                raise ValueError(f"{context} has an invalid physical selector")
            # The display wrapper selects the authored cave string by this
            # record's address.  Keep the stock bytes when a valid proportional
            # edit cannot also fit the dormant packed-word storage.
            return selector
        raise ValueError(f"{context} exceeds its {words}-word physical record")
    return struct.pack(f">{words}H", *(encoded + (0,) * (words - len(encoded))))


def _font8_to_font16(
    metrics8: FontMetrics,
    metrics16: FontMetrics,
) -> tuple[bytes, Mapping[int, int]]:
    codes16 = metrics16.by_text
    output = bytearray(512)
    mapping: dict[int, int] = {}
    for glyph in metrics8.glyphs:
        code16 = next(
            (
                codes16[text].code
                for text in (glyph.text, *glyph.aliases)
                if text in codes16
            ),
            None,
        )
        if code16 is None:
            continue
        struct.pack_into(">H", output, glyph.code * 2, code16)
        mapping[glyph.code] = code16
    return bytes(output), MappingProxyType(mapping)


def _item_name_codes(mapping: Mapping[int, int]) -> tuple[tuple[int, ...], ...]:
    try:
        data = ITEMNAME_PATH.read_bytes()
    except FileNotFoundError as error:
        raise ValueError(f"missing translated ITEMNAME: {ITEMNAME_PATH}") from error
    if len(data) != ITEM_RECORDS * ITEM_RECORD_SIZE:
        raise ValueError("translated ITEMNAME geometry changed")
    output: list[tuple[int, ...]] = []
    for index in range(ITEM_RECORDS):
        pointer = struct.unpack_from(">H", data, index * ITEM_RECORD_SIZE + ITEM_POINTER_OFFSET)[0]
        if pointer >= len(data):
            raise ValueError(f"ITEMNAME row {index} has an invalid full-name pointer")
        raw = data[pointer : pointer + ITEM_NAME_LIMIT]
        try:
            end = raw.index(0xFF)
        except ValueError as error:
            raise ValueError(f"ITEMNAME row {index} has no bounded terminator") from error
        try:
            output.append(tuple(mapping[code] for code in raw[:end]))
        except KeyError as error:
            raise ValueError(
                f"ITEMNAME row {index} uses unmapped FONT8 code {error.args[0]}"
            ) from error
    return tuple(output)


def _validate_geometry(
    terms: Mapping[str, str],
    templates: Mapping[str, tuple[str, str]],
    metrics: FontMetrics,
    item_names: tuple[tuple[int, ...], ...],
) -> None:
    surfaces = load_surfaces()
    expected = {
        "map_3d.field_message": (
            ("font16", 1, "glyph_cells", 14),
            ("font16", 1, "pixels", 224),
        ),
        "map_3d.field_choice": (
            ("font16", 1, "glyph_cells", 3),
            ("font16", 1, "pixels", 48),
        ),
    }
    for name, (ja_expected, en_expected) in expected.items():
        surface = surfaces.surface(name)
        for layout, wanted in ((surface.ja, ja_expected), (surface.en, en_expected)):
            actual = (layout.font, layout.rows, layout.width.unit, layout.width.value)
            if actual != wanted:
                raise ValueError(f"{name} geometry changed")

    for name, _offset in STATIC_FIELDS:
        codes = _encode(terms[f"game.maze_messages.o{_offset:06x}"], metrics, name)
        width = (
            16 + _measure(codes[1:], metrics)
            if codes and codes[0] == PROMPT_CODE
            else _measure(codes, metrics)
        )
        if width > MESSAGE_CELLS * 16:
            raise ValueError(f"field message {name} needs {width}px; limit is 224px")

    for name, (prefix, suffix) in templates.items():
        fixed = _measure(_encode(prefix + suffix, metrics, name), metrics)
        if name.startswith("item_"):
            widest = max(_measure(codes, metrics) for codes in item_names)
            glyphs = max(len(codes) for codes in item_names)
        else:
            digit_width = max(
                _measure(_encode(str(digit), metrics, name), metrics)
                for digit in range(10)
            )
            widest = 16 + 10 * digit_width
            glyphs = 11
        if fixed + widest > MESSAGE_CELLS * 16:
            raise ValueError(
                f"field template {name} can need {fixed + widest}px; limit is 224px"
            )
        template_glyphs = len(_encode(prefix + suffix, metrics, name)) + glyphs
        if template_glyphs >= MESSAGE_BUFFER_WORDS:
            raise ValueError(f"field template {name} exceeds the runtime buffer")

    for key, physical_id in CHOICE_IDS.items():
        codes = _encode(terms[physical_id], metrics, key)
        if _measure(codes, metrics) > CHOICE_CELLS * 16:
            raise ValueError(f"field choice {key} exceeds its three-cell renderer")


def _fixed_block(
    address: int,
    size: int,
    rows: tuple[tuple[str, bytes], ...],
) -> tuple[bytes, Mapping[str, int]]:
    output = bytearray()
    labels: dict[str, int] = {}
    for name, value in rows:
        if len(output) & 1:
            output.append(0)
        labels[name] = address + len(output)
        output.extend(value)
    if len(output) > size:
        raise ValueError(f"field-message block at {address:#x} exceeds {size} bytes")
    output.extend(bytes(size - len(output)))
    return bytes(output), MappingProxyType(labels)


def _template_data(
    templates: Mapping[str, tuple[str, str]],
    metrics: FontMetrics,
) -> tuple[bytes, Mapping[str, int], Mapping[str, int]]:
    rows: list[tuple[str, bytes]] = []
    counts: dict[str, int] = {}
    for name in (
        "item_found",
        "item_obtained",
        "item_full",
        "currency_yen",
        "currency_mag",
    ):
        prefix, suffix = templates[name]
        for role, text in (("prefix", prefix), ("suffix", suffix)):
            key = f"{name}_{role}"
            codes = _encode(text, metrics, f"field template {key}")
            counts[key] = len(codes)
            rows.append((key, struct.pack(f">{len(codes) + 1}H", *codes, 0)))
    data, labels = _fixed_block(DYNAMIC_TEMPLATES, 256, tuple(rows))
    return data, labels, MappingProxyType(counts)


def _message_data(
    terms: Mapping[str, str],
    metrics: FontMetrics,
) -> tuple[bytes, bytes]:
    rows: list[tuple[str, bytes]] = []
    for name, offset in STATIC_FIELDS:
        codes = _encode(terms[f"game.maze_messages.o{offset:06x}"], metrics, name)
        rows.append((name, struct.pack(f">{len(codes) + 1}H", *codes, 0)))
    strings, labels = _fixed_block(MESSAGE_STRINGS, 672, tuple(rows))
    mapping = b"".join(
        struct.pack(">II", LOAD_ADDRESS + offset, labels[name])
        for name, offset in STATIC_FIELDS
    )
    if len(mapping) > 96:
        raise ValueError("field-message mapping table exceeds its reserved block")
    return mapping.ljust(96, b"\0"), strings


def _precompose(
    font16: bytes,
    codes: tuple[int, ...],
    metrics: FontMetrics,
    cells: int,
    context: str,
) -> bytes:
    advances = {glyph.code: glyph.advance for glyph in metrics.glyphs}
    pixel_limit = cells * 16
    rows = [0] * 16
    cursor = 0
    for code in codes:
        try:
            advance = advances[code]
        except KeyError as error:
            raise ValueError(f"{context}: glyph {code} has no advance") from error
        glyph = font16[code * 32 : code * 32 + 32]
        if len(glyph) != 32:
            raise ValueError(f"{context}: glyph {code} exceeds FONT16")
        for row_index in range(16):
            word = struct.unpack_from(">H", glyph, row_index * 2)[0]
            for column in range(16):
                if word & (1 << (15 - column)):
                    destination = cursor + column
                    if destination >= pixel_limit:
                        raise ValueError(f"{context}: visible ink exceeds {pixel_limit}px")
                    rows[row_index] |= 1 << (pixel_limit - 1 - destination)
        cursor += advance
    if cursor > pixel_limit:
        raise ValueError(f"{context} needs {cursor}px; limit is {pixel_limit}px")
    output = bytearray()
    for cell in range(cells):
        shift = (cells - cell - 1) * 16
        for row in rows:
            output.extend(struct.pack(">H", row >> shift & 0xFFFF))
    return bytes(output)


def _assembled(source: Path, address: int, symbols: Mapping[str, int]) -> Assembly:
    try:
        result = assemble_file(source, address, dict(symbols))
    except AssemblyError as error:
        raise ValueError(f"field-message assembly failed in {source.name}: {error}") from error
    if result.warnings:
        raise ValueError(f"field-message assembly warnings in {source.name}: {result.warnings}")
    return result


def _assembly_sources(
    config: PatchRecipeConfiguration,
) -> Mapping[str, tuple[Path, ...]]:
    sources = {
        recipe.name: recipe.replacement.sources
        for recipe in config.patches[TARGET]
        if recipe.replacement.kind == "assembly"
    }
    expected = {
        "message_compositor",
        "message_display",
        "item_templates",
        "choice_draw",
        "item_found_hook",
        "item_obtained_hook",
        "item_full_hook",
    }
    if set(sources) != expected or any(len(value) != 1 for value in sources.values()):
        raise ValueError("field-message assembly recipe inventory changed")
    return MappingProxyType(sources)


def _build_runtime(
    config: PatchRecipeConfiguration,
    selectors: Mapping[str, bytes] | None = None,
) -> RuntimeBuild:
    terms = _bound_terms()
    templates = _templates()
    metrics16 = FontMetrics.load(FONT16_METRICS_PATH)
    metrics8 = FontMetrics.load(FONT8_METRICS_PATH)
    try:
        font16 = FONT16_PATH.read_bytes()
    except FileNotFoundError as error:
        raise ValueError(f"missing field-message FONT16: {FONT16_PATH}") from error
    if len(font16) != 1872 * 32:
        raise ValueError("field-message FONT16 geometry changed")
    code_limit, width_offset = _font16_layout(metrics16)
    token_map, code_map = _font8_to_font16(metrics8, metrics16)
    item_names = _item_name_codes(code_map)
    _validate_geometry(terms, templates, metrics16, item_names)

    dynamic, dynamic_labels, counts = _template_data(templates, metrics16)
    mapping, strings = _message_data(terms, metrics16)
    choice_codes = {
        name: _encode(terms[physical_id], metrics16, name)
        for name, physical_id in CHOICE_IDS.items()
    }
    choice_bitmaps = b"".join(
        _precompose(font16, choice_codes[name], metrics16, CHOICE_CELLS, name)
        for name in ("choice_yes", "choice_no")
    )
    choice_row = struct.pack(
        ">3H", *range(CHOICE_SCRATCH_CODE, CHOICE_SCRATCH_CODE + CHOICE_CELLS)
    )
    recipes = {recipe.name: recipe for recipe in config.patches[TARGET]}

    def choice_record(name: str) -> bytes:
        codes = choice_codes[name]
        if len(codes) > CHOICE_CELLS:
            # The live wrapper selects this field by address and renders the
            # proportional bitmap.  Preserve the stock selector record when an
            # otherwise valid edit cannot fit its dormant three-word storage.
            return recipes[name].expected
        return struct.pack(
            ">3H", *(codes + (0,) * (CHOICE_CELLS - len(codes)))
        )

    generated: dict[str, bytes] = {
        "item_token_map": token_map,
        "dynamic_templates": dynamic,
        "message_mapping": mapping,
        "message_strings": strings,
        "message_scratch": bytes(156),
        "choice_bitmaps": choice_bitmaps,
        "choice_row": choice_row,
        "choice_yes": choice_record("choice_yes"),
        "choice_no": choice_record("choice_no"),
    }
    for name, words in DIRECT_RECORDS.items():
        offset = next(offset for field, offset in STATIC_FIELDS if field == name)
        generated[name] = _direct_record(
            terms[f"game.maze_messages.o{offset:06x}"],
            words,
            metrics16,
            name,
            None if selectors is None else selectors[name],
        )

    sources = _assembly_sources(config)
    compositor = _assembled(
        sources["message_compositor"][0],
        COMPOSITOR,
        {
            "FONT_BASE": FONT16_BASE,
            "WIDTHS": FONT16_BASE + width_offset,
            "WIDTH_LIMIT": code_limit,
            "SCRATCH_CODE": MESSAGE_SCRATCH_CODE,
            "SCRATCH_LONGS": MESSAGE_CELLS * 8,
            "CELL_COUNT": MESSAGE_CELLS,
            "MAX_GLYPHS": MESSAGE_BUFFER_WORDS,
            "PROMPT_CODE": PROMPT_CODE,
            "CURRENCY_YEN_CODE": CURRENCY_YEN_CODE,
            "CURRENCY_MAG_CODE": CURRENCY_MAG_CODE,
            "YEN_PREFIX": dynamic_labels["currency_yen_prefix"],
            "YEN_SUFFIX": dynamic_labels["currency_yen_suffix"],
            "MAG_PREFIX": dynamic_labels["currency_mag_prefix"],
            "MAG_SUFFIX": dynamic_labels["currency_mag_suffix"],
            "ROW": MESSAGE_ROW,
        },
    )
    display = _assembled(
        sources["message_display"][0],
        MESSAGE_DISPLAY,
        {
            "ORIGINAL": 0x06040BC4,
            "MAPPING_TABLE": MAPPING_TABLE,
            "MAPPING_COUNT": len(STATIC_FIELDS),
            "COMPOSITOR": COMPOSITOR,
            "BUFFER": MESSAGE_BUFFER,
            "ROW": MESSAGE_ROW,
        },
    )
    item = _assembled(
        sources["item_templates"][0],
        ITEM_TEMPLATES,
        {
            "BUFFER": MESSAGE_BUFFER,
            "BUFFER_WORDS": MESSAGE_BUFFER_WORDS,
            "ITEM_BASE": ITEMNAME_BASE,
            "ITEM_FULL_NAME_OFFSET": ITEM_POINTER_OFFSET,
            "ITEM_NAME_LIMIT": ITEM_NAME_LIMIT,
            "TOKEN_MAP": TOKEN_MAP,
            "FOUND_PREFIX": dynamic_labels["item_found_prefix"],
            "FOUND_PREFIX_WORDS": counts["item_found_prefix"],
            "FOUND_SUFFIX": dynamic_labels["item_found_suffix"],
            "FOUND_SUFFIX_WORDS": counts["item_found_suffix"],
            "OBTAINED_PREFIX": dynamic_labels["item_obtained_prefix"],
            "OBTAINED_PREFIX_WORDS": counts["item_obtained_prefix"],
            "OBTAINED_SUFFIX": dynamic_labels["item_obtained_suffix"],
            "OBTAINED_SUFFIX_WORDS": counts["item_obtained_suffix"],
            "FULL_PREFIX": dynamic_labels["item_full_prefix"],
            "FULL_PREFIX_WORDS": counts["item_full_prefix"],
            "FULL_SUFFIX": dynamic_labels["item_full_suffix"],
            "FULL_SUFFIX_WORDS": counts["item_full_suffix"],
        },
    )
    choice = _assembled(
        sources["choice_draw"][0],
        CHOICE_DRAW,
        {
            "YES_FIELD": 0x060450D0,
            "NO_FIELD": 0x060450D6,
            "ORIGINAL_DRAW": 0x06040AAC,
            "FONT_DST": FONT16_BASE + CHOICE_SCRATCH_CODE * 32,
            "BITMAP_LONGS": CHOICE_CELLS * 8,
            "YES_BITMAP": CHOICE_BITMAPS,
            "NO_BITMAP": CHOICE_BITMAPS + CHOICE_CELLS * 32,
            "ROW": CHOICE_ROW,
        },
    )
    if (
        len(compositor.data) != 420
        or len(display.data) != 112
        or len(item.data) != 228
        or len(choice.data) != 72
    ):
        raise ValueError("field-message assembly geometry changed")

    links = {
        "message_display": display.labels["field_message_display"],
        "message_buffer": MESSAGE_BUFFER,
        "choice_draw": choice.labels["field_choice_draw"],
    }
    hook_targets = {
        "item_found_hook": item.labels["field_item_found"],
        "item_obtained_hook": item.labels["field_item_obtained"],
        "item_full_hook": item.labels["field_item_full"],
    }
    assembly = {
        "message_compositor": compositor.data,
        "message_display": display.data,
        "item_templates": item.data,
        "choice_draw": choice.data,
    }
    expected_sizes = {
        "item_found_hook": 80,
        "item_obtained_hook": 80,
        "item_full_hook": 104,
    }
    for name, target in hook_targets.items():
        hook = _assembled(sources[name][0], recipes[name].address, {"TARGET": target}).data
        size = expected_sizes[name]
        if len(hook) > size or (size - len(hook)) & 1:
            raise ValueError(f"field-message hook {name} no longer fits")
        assembly[name] = hook + b"\x00\x09" * ((size - len(hook)) // 2)

    return RuntimeBuild(
        MappingProxyType(assembly),
        MappingProxyType(generated),
        MappingProxyType(links),
    )


def _bind_patches(
    config: PatchRecipeConfiguration,
    base: bytes,
) -> tuple[tuple[Patch, ...], RuntimeBuild]:
    expected = {
        recipe.name: resolve_recipe_expected(recipe, base, LOAD_ADDRESS)
        for recipe in config.patches[TARGET]
    }
    runtime = _build_runtime(config, expected)
    output: list[Patch] = []
    assembly_seen: set[str] = set()
    generated_seen: set[str] = set()
    for recipe in config.patches[TARGET]:
        replacement_recipe = recipe.replacement
        if replacement_recipe.kind == "assembly":
            try:
                replacement = runtime.assembly[recipe.name]
            except KeyError as error:
                raise ValueError(f"unknown field-message assembly {recipe.name}") from error
            assembly_seen.add(recipe.name)
        elif replacement_recipe.kind == "generated":
            if replacement_recipe.generator != "field_messages":
                raise ValueError(f"unknown field-message generator for {recipe.name}")
            try:
                replacement = runtime.generated[recipe.name]
            except KeyError as error:
                raise ValueError(f"unknown field-message data {recipe.name}") from error
            generated_seen.add(recipe.name)
        elif replacement_recipe.kind == "linked_pointer":
            link = replacement_recipe.link
            assert link is not None
            try:
                replacement = struct.pack(">I", runtime.links[link])
            except KeyError as error:
                raise ValueError(f"unknown field-message link {link}") from error
        else:
            raise ValueError(
                f"{recipe.group}/{recipe.name}: unsupported field-message "
                f"replacement kind {replacement_recipe.kind}"
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
    if assembly_seen != set(runtime.assembly):
        raise ValueError("field-message assembly ownership differs from config")
    if generated_seen != set(runtime.generated):
        raise ValueError("field-message generated-data ownership differs from config")
    return tuple(output), runtime


def build_field_messages(base: bytes | None = None) -> FieldMessagesBuild:
    """Build the corrected, fully authored field-message consumer."""
    stock = _source_maze()
    source = stock if base is None else base
    config = _configuration()
    _validate_inputs(config, source, stock)
    patches, _runtime = _bind_patches(config, source)
    data = apply_patches(source, LOAD_ADDRESS, patches)
    assembly_files = tuple(
        dict.fromkeys(
            path
            for recipe in config.patches[TARGET]
            if recipe.replacement.kind == "assembly"
            for path in recipe.replacement.sources
        )
    )
    return FieldMessagesBuild(
        data,
        patches,
        ASSET_FILES,
        assembly_files,
        RUNTIME_INPUT_FILES,
        MappingProxyType({TARGET: _sha256(stock)}),
    )
