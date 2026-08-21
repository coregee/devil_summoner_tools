"""Build MAP2D's authored labels, field prompt, and dynamic name adapters."""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType

from rom.util.catalog import load_catalog, validate_source
from rom.util.workflows import read_source_files
from text.util.assets import (
    ASSET_ROOT,
    BINDING_ROOT,
    CORPUS_ROOT,
    load_asset,
    load_binding,
    load_bound_translations,
    load_physical_record_files,
)
from text.util.event_repack import FontMetrics
from text.util.surfaces import load_surfaces
from text.util.tokens import Named, Text, parse_tokens

from engine.core.config_io import object_value, read_json
from engine.core.patch_recipes import (
    PatchRecipe,
    PatchRecipeConfiguration,
    load_patch_recipe_configuration,
    resolve_recipe_expected,
)
from engine.core.patching import Patch, apply_patches
from engine.core.sh2 import Assembly, AssemblyError, assemble, assemble_file
from engine.shared.player_names import PLAYER_NAME_FIELD_BY_KEY

ENGINE_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = ENGINE_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "map_2d_ui.json"
ASSEMBLY_ROOT = ENGINE_ROOT / "asm"

MAP_ASSET_PATH = ASSET_ROOT / "ui" / "map_2d.json"
PROFILE_ASSET_PATH = ASSET_ROOT / "ui" / "profile_entry.json"
LOCATIONS_ASSET_PATH = ASSET_ROOT / "locations.json"
MESSAGES_ASSET_PATH = ASSET_ROOT / "field" / "messages.json"
MAP_BINDING_PATH = BINDING_ROOT / "map_2d.json"
PROFILE_BINDING_PATH = BINDING_ROOT / "map_2d_profile.json"
LOCATIONS_BINDING_PATH = BINDING_ROOT / "map_2d_locations.json"
MESSAGES_BINDING_PATH = BINDING_ROOT / "map_2d_messages.json"
MAP_CORPUS_PATH = CORPUS_ROOT / "game" / "addressed" / "map_static.json"
SURFACES_PATH = SATURN_ROOT / "text" / "config" / "surfaces.json"
DISC_CONFIG_PATH = SATURN_ROOT / "rom" / "discs.json"
PLAYER_NAMES_PATH = ENGINE_ROOT / "shared" / "player_names.py"

FONT_ROOT = SATURN_ROOT / "font" / "generated" / "game"
FONT16_PATH = FONT_ROOT / "FONT16.FON"
FONT16_METRICS_PATH = FONT_ROOT / "FONT16_metrics.json"

ASSET_FILES = (
    MAP_ASSET_PATH,
    PROFILE_ASSET_PATH,
    LOCATIONS_ASSET_PATH,
    MESSAGES_ASSET_PATH,
)
_BINDING_ASSETS = (
    (MAP_BINDING_PATH, PurePosixPath("ui/map_2d.json")),
    (PROFILE_BINDING_PATH, PurePosixPath("ui/profile_entry.json")),
    (LOCATIONS_BINDING_PATH, PurePosixPath("locations.json")),
    (MESSAGES_BINDING_PATH, PurePosixPath("field/messages.json")),
)
RUNTIME_INPUT_FILES = (
    FONT16_PATH,
    FONT16_METRICS_PATH,
    SURFACES_PATH,
    DISC_CONFIG_PATH,
    MAP_BINDING_PATH,
    PROFILE_BINDING_PATH,
    LOCATIONS_BINDING_PATH,
    MESSAGES_BINDING_PATH,
    MAP_CORPUS_PATH,
    PLAYER_NAMES_PATH,
)

TARGET = "MAP2D.BIN"
LOAD_ADDRESS = 0x06020000
TARGET_SIZE = 126_600

FONT16_BASE = 0x0021A000
ITEMNAME_BASE = 0x00228C00
WARD_SCRATCH_CODE = 0x0740
CITY_SCRATCH_CODE = 0x0744
FIXED_SCRATCH_CODE = 0x0748
ROW_TERMINATOR = 0x8000

NAME_RUNTIME = 0x06020400
NAME_RUNTIME_CAPACITY = 0x480
NAME_SCALE_MAP = 0x06020800
NAME_SCALE_MAP_BYTES = 128
NAME_COMPONENT_PIXELS = 64
NAME_SOURCE_GLYPHS = 8

PROMPT_RUNTIME = 0x06021000
PROMPT_RUNTIME_CAPACITY = 124
BITMAP_ARENA = 0x06021200
BITMAP_ARENA_CAPACITY = 0x5C8
FIXED_BITMAP = 0x06021200
CHOICE_YES_BITMAP = 0x06021480
CHOICE_NO_BITMAP = 0x060214E0
CHOICE_YES_ROW = 0x060215E0
CHOICE_NO_ROW = 0x060215E8
PROMPT_BITMAP = 0x06021600
PROMPT_SCRATCH = 0x060217C0

PROMPT_CELLS = 14
CHOICE_CELLS = 3
FIXED_CELLS = 4
OVERVIEW_SUFFIX_CELLS = 2

PROMPT_FIELD = 0x0603E756
CHOICE_YES_FIELD = 0x0603E774
CHOICE_NO_FIELD = 0x0603E77C
FONT16_POINTER = 0x0603DAF0
CITY_ROW = 0x0603E6C0
ORIGINAL_FIXED_DRAW = 0x06039534

FIXED_RECORDS = (
    ("rinkai_park_row", "game.map_static.o01e68e"),
    ("mount_kasagi_row", "game.map_static.o01e698"),
    ("yarai_ward_row", "game.map_static.o01e6a2"),
    ("chuo_ward_row", "game.map_static.o01e6ac"),
    ("hibarigaoka_row", "game.map_static.o01e6b6"),
)
MESSAGE_RECORDS = {
    "talk_prompt": "game.map_static.o01e756",
    "talk_choice_yes": "game.map_static.o01e774",
    "talk_choice_no": "game.map_static.o01e77c",
}
PROFILE_RECORDS = {
    "default_ward": "game.map_static.o01e684",
    "default_city": "game.map_static.o01e6c0",
}
LITERAL_IDS = frozenset(
    {
        *(physical_id for _name, physical_id in FIXED_RECORDS),
        *MESSAGE_RECORDS.values(),
        *PROFILE_RECORDS.values(),
    }
)

_ASSEMBLY_RECIPES = {
    "name_runtime_arena": "map_2d_ui/name_compositor.s",
    "prompt_runtime": "map_2d_ui/prompt_wrapper.s",
}
_GENERATED_RECIPES = frozenset(
    {
        "bitmap_data_arena",
        *(name for name, _physical_id in FIXED_RECORDS),
        "overview_suffix_row",
        "talk_prompt_row",
        "talk_choice_yes_row",
        "talk_choice_no_row",
        "area_ward_origin",
    }
)


@dataclass(frozen=True, slots=True)
class TextLayout:
    fixed: Mapping[str, tuple[int, ...]]
    prompt: tuple[int, ...]
    choices: Mapping[str, tuple[int, ...]]
    overview_suffix: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class RuntimeBuild:
    assembly: Mapping[str, bytes]
    generated: Mapping[str, bytes]
    links: Mapping[str, int]
    used_size: int
    capacity: int
    choice_cells: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class Map2dUiBuild:
    data: bytes
    patches: tuple[Patch, ...]
    asset_files: tuple[Path, ...]
    assembly_files: tuple[Path, ...]
    runtime_input_files: tuple[Path, ...]
    source_inputs: Mapping[str, str]
    runtime_used_size: int
    runtime_capacity: int


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        return _sha256(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"missing MAP2D input: {path}") from error


def _configuration() -> PatchRecipeConfiguration:
    return load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="map_2d.ui",
        target_names={TARGET},
        input_names={"font16_sha256", "font16_metrics_sha256"},
    )


def _stock_source() -> bytes:
    catalog = load_catalog()
    try:
        game = catalog["game"]
    except KeyError as error:
        raise ValueError("disc catalog has no game source") from error
    return read_source_files(validate_source(game, verify_hashes=False), (TARGET,))[
        TARGET
    ]


def _stock_slice(stock: bytes, address: int, size: int) -> bytes:
    start = address - LOAD_ADDRESS
    return stock[start : start + size]


def _validate_stock_invariants(stock: bytes) -> None:
    invariants = {
        "dynamic ward row": (0x0603E684, bytes.fromhex("02970241029880000000")),
        "dynamic city row": (0x0603E6C0, bytes.fromhex("0208023a029680000000")),
        "orphan cloud row": (0x0603E6D4, bytes.fromhex("029e8000000000000000")),
        "suffix storage": (0x0603E6DE, bytes.fromhex("0298800002968000")),
        "area city-row pointer": (0x0603ADBC, struct.pack(">I", CITY_ROW)),
        "FONT16 pointer variable": (FONT16_POINTER, struct.pack(">I", FONT16_BASE)),
    }
    for name, (address, expected) in invariants.items():
        if _stock_slice(stock, address, len(expected)) != expected:
            raise ValueError(f"MAP2D {name} stock invariant changed")


def _validate_sources(
    config: PatchRecipeConfiguration,
    stock: bytes,
) -> None:
    target = config.targets[TARGET]
    if (
        target.load_address != LOAD_ADDRESS
        or target.size != TARGET_SIZE
        or len(stock) != TARGET_SIZE
        or _sha256(stock) != target.stock_sha256
    ):
        raise ValueError("MAP2D.BIN does not match the configured stock target")
    actual = {
        "font16_sha256": _file_sha256(FONT16_PATH),
        "font16_metrics_sha256": _file_sha256(FONT16_METRICS_PATH),
    }
    for name, expected in config.inputs.items():
        if actual[name] != expected:
            raise ValueError(
                f"MAP2D {name} expected SHA-256 {expected}, found {actual[name]}"
            )
    _validate_stock_invariants(stock)


def _validate_surfaces() -> None:
    expected = {
        "map_2d.world_city_label": (
            ("font16", 1, "glyph_cells", 6, None),
            ("font16", 1, "pixels", 96, None),
        ),
        "map_2d.world_region_label": (
            ("font16", 1, "glyph_cells", 4, None),
            ("font16", 1, "pixels", 64, None),
        ),
        "map_2d.area_label": (
            ("font16", 1, "glyph_cells", 8, None),
            ("font16", 1, "pixels", 128, None),
        ),
        "map_2d.field_message": (
            ("font16", 1, "glyph_cells", 14, None),
            ("font16", 1, "pixels", 224, None),
        ),
        "map_2d.field_choice": (
            ("font16", 1, "glyph_cells", 3, None),
            ("font16", 1, "pixels", 48, 3),
        ),
    }
    surfaces = load_surfaces()
    for name, layouts in expected.items():
        surface = surfaces.surface(name)
        for language, layout, wanted in (
            ("ja", surface.ja, layouts[0]),
            ("en", surface.en, layouts[1]),
        ):
            actual = (
                layout.font,
                layout.rows,
                layout.width.unit,
                layout.width.value,
                layout.glyphs,
            )
            if actual != wanted:
                raise ValueError(f"{name} {language} geometry changed: {actual!r}")


def _binding_inventory() -> tuple[Mapping[str, str], ...]:
    physical = load_physical_record_files((MAP_CORPUS_PATH,))
    bindings = tuple(
        load_binding(path, physical_records=physical)
        for path, _expected_asset in _BINDING_ASSETS
    )
    owners: dict[str, str] = {}
    for (path, expected_asset), binding in zip(_BINDING_ASSETS, bindings):
        if binding.asset != expected_asset:
            raise ValueError(
                f"MAP2D binding {path.name} selects {binding.asset}, "
                f"expected {expected_asset}"
            )
        for physical_id in binding.records:
            if physical_id in owners:
                raise ValueError(
                    f"MAP2D physical record {physical_id} has two bindings"
                )
            owners[physical_id] = path.name
    if set(owners) != set(physical):
        missing = sorted(set(physical) - set(owners))
        extra = sorted(set(owners) - set(physical))
        raise ValueError(
            f"MAP2D binding inventory differs: {missing!r} missing, {extra!r} extra"
        )
    map_binding = bindings[0]
    if set(map_binding.unresolved) != {"game.map_static.o01e6d4"}:
        raise ValueError(
            "MAP2D orphan-cloud evidence must remain explicitly unresolved"
        )
    return tuple(binding.records for binding in bindings)


def _bound_terms() -> Mapping[str, str]:
    _binding_inventory()
    physical = load_physical_record_files((MAP_CORPUS_PATH,))
    fixed_and_messages = load_bound_translations(
        ("game.map_static.",),
        required_ids={
            *(physical_id for _name, physical_id in FIXED_RECORDS),
            *MESSAGE_RECORDS.values(),
        },
        binding_paths=(LOCATIONS_BINDING_PATH, MESSAGES_BINDING_PATH),
        physical_records=physical,
    )
    profile = load_bound_translations(
        ("game.map_static.",),
        required_ids=set(PROFILE_RECORDS.values()),
        binding_paths=(PROFILE_BINDING_PATH,),
        physical_records=physical,
    )
    output = dict(fixed_and_messages)
    output.update(profile)
    if set(output) != LITERAL_IDS:
        raise ValueError("MAP2D literal binding coverage changed")
    return MappingProxyType(output)


def _map_templates() -> Mapping[str, str]:
    catalog = load_asset("ui/map_2d.json")
    required = {
        "city_label",
        "world_city_label",
        "world_ward_label",
        "area_label",
        "orphan_cloud",
    }
    if not required <= set(catalog.entries):
        raise ValueError("ui/map_2d.json template inventory changed")
    if catalog.entries["orphan_cloud"].status != "unresolved":
        raise ValueError(
            "MAP2D orphan_cloud cannot be emitted until its consumer is proved"
        )
    output: dict[str, str] = {}
    for key in required:
        try:
            translation = catalog.entries[key].fields["text"].translation
        except KeyError as error:
            raise ValueError(f"ui/map_2d.json is missing {key}.text") from error
        if not translation:
            raise ValueError(f"ui/map_2d.json {key}.text is untranslated")
        output[key] = translation
    return MappingProxyType(output)


def _font16_layout(metrics: FontMetrics) -> tuple[bytes, int]:
    document = object_value(read_json(FONT16_METRICS_PATH), str(FONT16_METRICS_PATH))
    table = object_value(
        document.get("width_table"), f"{FONT16_METRICS_PATH}.width_table"
    )
    code_limit = table.get("code_limit")
    storage_glyph = table.get("storage_glyph")
    if (
        type(code_limit) is not int
        or code_limit <= 0
        or type(storage_glyph) is not int
        or storage_glyph < 0
    ):
        raise ValueError("invalid MAP2D FONT16 width-table metadata")
    widths = bytearray(code_limit)
    for glyph in metrics.glyphs:
        if not 0 <= glyph.code < code_limit:
            raise ValueError("MAP2D FONT16 glyph lies outside the width table")
        widths[glyph.code] = glyph.advance
    return bytes(widths), storage_glyph * 32


def _literal_text(value: str, context: str, *, allow_empty: bool = False) -> str:
    if not value and allow_empty:
        return ""
    try:
        tokens = parse_tokens(value)
    except ValueError as error:
        raise ValueError(f"{context}: {error}") from error
    if not tokens or any(not isinstance(token, Text) for token in tokens):
        raise ValueError(f"{context} must contain only authored literal text")
    literal = "".join(token.value for token in tokens if isinstance(token, Text))
    if "\n" in literal or "\r" in literal or "\0" in literal:
        raise ValueError(f"{context} contains unsupported controls")
    return literal


def _encode(
    value: str,
    metrics: FontMetrics,
    context: str,
    *,
    allow_empty: bool = False,
) -> tuple[int, ...]:
    literal = _literal_text(value, context, allow_empty=allow_empty)
    try:
        return tuple(glyph.code for glyph in metrics.segment_output(literal))
    except ValueError as error:
        raise ValueError(f"{context}: {error}") from error


def _measure(codes: tuple[int, ...], metrics: FontMetrics) -> int:
    advances = {glyph.code: glyph.advance for glyph in metrics.glyphs}
    try:
        return sum(advances[code] for code in codes)
    except KeyError as error:
        raise ValueError(f"MAP2D glyph {error.args[0]} has no advance") from error


def _template_suffix(
    templates: Mapping[str, str], metrics: FontMetrics
) -> tuple[int, ...]:
    exact = {
        "city_label": "city",
        "world_ward_label": "ward",
        "area_label": "area",
    }
    for key, placeholder in exact.items():
        try:
            tokens = parse_tokens(templates[key])
        except (KeyError, ValueError) as error:
            raise ValueError(f"MAP2D {key} template is invalid") from error
        if tokens != (Named(placeholder),):
            role = (
                "the suppressed area-city component"
                if key == "city_label"
                else "its independently drawn component"
            )
            raise ValueError(
                f"MAP2D {key} must be exactly {{{placeholder}}}; edits to {role} "
                "need a matching renderer patch"
            )

    try:
        tokens = parse_tokens(templates["world_city_label"])
    except (KeyError, ValueError) as error:
        raise ValueError("MAP2D world_city_label template is invalid") from error
    if (
        not tokens
        or tokens[0] != Named("city")
        or any(not isinstance(token, Text) for token in tokens[1:])
    ):
        raise ValueError(
            "MAP2D world_city_label must be {city} followed by an optional literal suffix"
        )
    suffix = "".join(token.value for token in tokens[1:] if isinstance(token, Text))
    codes = _encode(
        suffix,
        metrics,
        "MAP2D world-city suffix",
        allow_empty=True,
    )
    width = _measure(codes, metrics)
    if len(codes) > OVERVIEW_SUFFIX_CELLS or width > OVERVIEW_SUFFIX_CELLS * 16:
        raise ValueError(
            "MAP2D world-city suffix exceeds its two-glyph/32px authored row"
        )
    return codes


def _validate_profile_defaults(terms: Mapping[str, str]) -> None:
    for key, physical_id in PROFILE_RECORDS.items():
        try:
            value = terms[physical_id]
        except KeyError as error:
            raise ValueError(f"MAP2D is missing the {key} binding") from error
        if (
            not value
            or not value.isascii()
            or "\0" in value
            or len(value.encode("ascii")) > NAME_SOURCE_GLYPHS
        ):
            raise ValueError(
                f"MAP2D {key} must fit the shared eight-byte player-name field"
            )


def _text_layout(
    terms: Mapping[str, str],
    templates: Mapping[str, str],
    metrics: FontMetrics,
) -> TextLayout:
    _validate_profile_defaults(terms)
    fixed: dict[str, tuple[int, ...]] = {}
    for name, physical_id in FIXED_RECORDS:
        try:
            codes = _encode(terms[physical_id], metrics, f"MAP2D {name}")
        except KeyError as error:
            raise ValueError(f"MAP2D is missing {physical_id}") from error
        width = _measure(codes, metrics)
        if width > FIXED_CELLS * 16:
            raise ValueError(f"MAP2D {name} needs {width}px; limit is 64px")
        fixed[name] = codes

    prompt = _encode(
        terms[MESSAGE_RECORDS["talk_prompt"]], metrics, "MAP2D talk prompt"
    )
    prompt_width = _measure(prompt, metrics)
    if prompt_width > PROMPT_CELLS * 16:
        raise ValueError(f"MAP2D talk prompt needs {prompt_width}px; limit is 224px")

    choices: dict[str, tuple[int, ...]] = {}
    for key in ("talk_choice_yes", "talk_choice_no"):
        codes = _encode(terms[MESSAGE_RECORDS[key]], metrics, f"MAP2D {key}")
        width = _measure(codes, metrics)
        if len(codes) > CHOICE_CELLS or width > CHOICE_CELLS * 16:
            raise ValueError(f"MAP2D {key} exceeds its three-glyph/48px renderer")
        choices[key] = codes

    return TextLayout(
        MappingProxyType(fixed),
        prompt,
        MappingProxyType(choices),
        _template_suffix(templates, metrics),
    )


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
                        raise ValueError(
                            f"{context}: visible ink exceeds {pixel_limit}px"
                        )
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
        raise ValueError(f"MAP2D assembly failed in {source.name}: {error}") from error
    if result.warnings:
        raise ValueError(f"MAP2D assembly warnings in {source.name}: {result.warnings}")
    return result


def _only_source(recipe: PatchRecipe, relative: str) -> Path:
    sources = recipe.replacement.sources
    if (
        len(sources) != 1
        or sources[0].relative_to(ASSEMBLY_ROOT).as_posix() != relative
    ):
        raise ValueError(f"{recipe.group}/{recipe.name}: assembly source changed")
    return sources[0]


def _recipe_map(config: PatchRecipeConfiguration) -> Mapping[str, PatchRecipe]:
    recipes = config.patches[TARGET]
    output = {recipe.name: recipe for recipe in recipes}
    if len(output) != len(recipes):
        raise ValueError("MAP2D patch recipe names are not unique")
    expected_names = {
        *_ASSEMBLY_RECIPES,
        *_GENERATED_RECIPES,
        "name_copy_pointer",
        "city_name_pointer",
        "ward_name_pointer",
        "city_copy_clamp_add",
        "city_copy_clamp_store",
        "city_suffix_call",
        "ward_copy_clamp_add",
        "ward_copy_clamp_store",
        "ward_suffix_call",
        "prompt_draw_pointer",
        "area_city_draw",
    }
    if set(output) != expected_names:
        raise ValueError("MAP2D patch recipe inventory changed")
    for name, relative in _ASSEMBLY_RECIPES.items():
        _only_source(output[name], relative)
    for name in _GENERATED_RECIPES:
        recipe = output[name].replacement
        if recipe.kind != "generated" or recipe.generator != "map_2d_data":
            raise ValueError(f"MAP2D generated owner changed for {name}")
    pointer_values = {
        "city_name_pointer": PLAYER_NAME_FIELD_BY_KEY["city"].runtime_address,
        "ward_name_pointer": PLAYER_NAME_FIELD_BY_KEY["ward"].runtime_address,
    }
    for name, pointer in pointer_values.items():
        recipe = output[name].replacement
        if recipe.kind != "pointer" or recipe.pointer != pointer:
            raise ValueError(f"MAP2D shared player-name pointer changed for {name}")
    return MappingProxyType(output)


def _name_runtime(
    source: Path,
    widths: bytes,
) -> tuple[bytes, Mapping[str, int], int]:
    fixed_cells = len(FIXED_RECORDS) * FIXED_CELLS
    fixed_end = FONT16_BASE + (FIXED_SCRATCH_CODE + fixed_cells) * 32
    if FIXED_SCRATCH_CODE < CITY_SCRATCH_CODE + FIXED_CELLS:
        raise ValueError("MAP2D fixed labels overlap the dynamic city cells")
    if fixed_end > ITEMNAME_BASE:
        raise ValueError("MAP2D fixed labels exceed the FONT16/ITEMNAME gap")
    assembled = _assembled(
        source,
        NAME_RUNTIME,
        {
            "WARD_CODE": WARD_SCRATCH_CODE,
            "CITY_CODE": CITY_SCRATCH_CODE,
            "CITY_ROW_ADDR": CITY_ROW,
            "FONT_BASE": FONT16_BASE,
            "TERM": ROW_TERMINATOR,
            "WIDTH_LIMIT": len(widths),
            "NAME_WIDTH": NAME_COMPONENT_PIXELS,
            "SCALE_MAP": NAME_SCALE_MAP,
            "FIXED_SRC": FIXED_BITMAP,
            "FIXED_DST": FONT16_BASE + FIXED_SCRATCH_CODE * 32,
            "FIXED_LONGS": fixed_cells * 32 // 4,
        },
    )
    if len(assembled.data) != 504:
        raise ValueError("MAP2D name compositor geometry changed")
    if assembled.labels.get("widths") != NAME_RUNTIME + len(assembled.data):
        raise ValueError("MAP2D name compositor width-table boundary changed")
    payload = bytearray(assembled.data)
    payload.extend(widths)
    payload.extend(bytes((-len(payload)) % 4))
    if len(payload) > NAME_RUNTIME_CAPACITY:
        raise ValueError("MAP2D name runtime overlaps its scale-map scratch")
    return (
        bytes(payload).ljust(NAME_RUNTIME_CAPACITY, b"\0"),
        MappingProxyType(assembled.labels),
        len(payload),
    )


def _prompt_runtime(source: Path) -> tuple[bytes, Mapping[str, int]]:
    assembled = _assembled(
        source,
        PROMPT_RUNTIME,
        {
            "PROMPT_FIELD": PROMPT_FIELD,
            "YES_FIELD": CHOICE_YES_FIELD,
            "NO_FIELD": CHOICE_NO_FIELD,
            "ORIGINAL_DRAW": ORIGINAL_FIXED_DRAW,
            "SCRATCH": PROMPT_SCRATCH,
            "FONT_PTR": FONT16_POINTER,
            "PROMPT_BITMAP": PROMPT_BITMAP,
            "YES_BITMAP": CHOICE_YES_BITMAP,
            "NO_BITMAP": CHOICE_NO_BITMAP,
            "YES_ROW": CHOICE_YES_ROW,
            "NO_ROW": CHOICE_NO_ROW,
        },
    )
    if len(assembled.data) != PROMPT_RUNTIME_CAPACITY:
        raise ValueError("MAP2D prompt wrapper geometry changed")
    expected_labels = {
        "prompt_draw": PROMPT_RUNTIME,
        "prompt_bitmap": PROMPT_RUNTIME + 0x18,
        "yes_bitmap": PROMPT_RUNTIME + 0x1E,
        "no_bitmap": PROMPT_RUNTIME + 0x26,
        "draw_bitmap": PROMPT_RUNTIME + 0x2A,
    }
    for name, address in expected_labels.items():
        if assembled.labels.get(name) != address:
            raise ValueError(f"MAP2D prompt wrapper label {name} moved")
    return assembled.data, MappingProxyType(assembled.labels)


def _choice_cells(codes: tuple[int, ...], metrics: FontMetrics, minimum: int) -> int:
    width = _measure(codes, metrics)
    cells = max(minimum, (width + 15) // 16)
    if cells > CHOICE_CELLS:
        raise ValueError("MAP2D choice exceeds its reserved bitmap cells")
    return cells


def _data_arena(
    layout: TextLayout,
    font16: bytes,
    metrics: FontMetrics,
) -> tuple[bytes, Mapping[str, int], int]:
    arena = bytearray(BITMAP_ARENA_CAPACITY)

    def put(address: int, value: bytes, context: str) -> None:
        start = address - BITMAP_ARENA
        end = start + len(value)
        if start < 0 or end > len(arena):
            raise ValueError(f"MAP2D {context} exceeds the bitmap arena")
        if any(arena[start:end]):
            raise ValueError(f"MAP2D {context} overlaps another bitmap allocation")
        arena[start:end] = value

    fixed = b"".join(
        _precompose(font16, layout.fixed[name], metrics, FIXED_CELLS, name)
        for name, _physical_id in FIXED_RECORDS
    )
    put(FIXED_BITMAP, fixed, "fixed-label strips")

    yes_codes = layout.choices["talk_choice_yes"]
    no_codes = layout.choices["talk_choice_no"]
    yes_cells = CHOICE_CELLS
    no_cells = _choice_cells(no_codes, metrics, 2)
    yes_bitmap = _precompose(font16, yes_codes, metrics, yes_cells, "MAP2D Yes choice")
    no_bitmap = _precompose(font16, no_codes, metrics, no_cells, "MAP2D No choice")
    put(CHOICE_YES_BITMAP, yes_bitmap, "Yes choice bitmap")
    put(CHOICE_NO_BITMAP, no_bitmap, "No choice bitmap")

    yes_row = struct.pack(f">{yes_cells + 1}H", *range(yes_cells), ROW_TERMINATOR)
    no_row = struct.pack(f">{no_cells + 1}H", *range(no_cells), ROW_TERMINATOR)
    put(CHOICE_YES_ROW, yes_row, "Yes choice row")
    put(CHOICE_NO_ROW, no_row, "No choice row")

    prompt = _precompose(
        font16, layout.prompt, metrics, PROMPT_CELLS, "MAP2D talk prompt"
    )
    put(PROMPT_BITMAP, prompt, "talk-prompt bitmap")
    if PROMPT_SCRATCH + 8 != BITMAP_ARENA + BITMAP_ARENA_CAPACITY:
        raise ValueError("MAP2D prompt scratch no longer terminates the bitmap arena")

    used_size = (
        len(fixed)
        + len(yes_bitmap)
        + len(no_bitmap)
        + len(yes_row)
        + len(no_row)
        + len(prompt)
        + 8
    )
    return (
        bytes(arena),
        MappingProxyType({"talk_choice_yes": yes_cells, "talk_choice_no": no_cells}),
        used_size,
    )


def _terminated_row(codes: tuple[int, ...], words: int, context: str) -> bytes:
    if len(codes) + 1 > words:
        raise ValueError(f"{context} exceeds its {words}-word physical row")
    values = codes + (ROW_TERMINATOR,) + (0,) * (words - len(codes) - 1)
    return struct.pack(f">{words}H", *values)


def _build_runtime(config: PatchRecipeConfiguration) -> RuntimeBuild:
    recipes = _recipe_map(config)
    terms = _bound_terms()
    templates = _map_templates()
    metrics = FontMetrics.load(FONT16_METRICS_PATH)
    widths, width_offset = _font16_layout(metrics)
    if width_offset != 1728 * 32 or len(widths) != 268:
        raise ValueError("MAP2D FONT16 width-table ABI changed")
    try:
        font16 = FONT16_PATH.read_bytes()
    except FileNotFoundError as error:
        raise ValueError(f"missing MAP2D FONT16: {FONT16_PATH}") from error
    if len(font16) != 1872 * 32:
        raise ValueError("MAP2D FONT16 geometry changed")

    layout = _text_layout(terms, templates, metrics)
    name_arena, name_links, name_used = _name_runtime(
        _only_source(
            recipes["name_runtime_arena"],
            _ASSEMBLY_RECIPES["name_runtime_arena"],
        ),
        widths,
    )
    prompt_code, prompt_links = _prompt_runtime(
        _only_source(
            recipes["prompt_runtime"],
            _ASSEMBLY_RECIPES["prompt_runtime"],
        )
    )
    data_arena, choice_cells, data_used = _data_arena(layout, font16, metrics)

    generated: dict[str, bytes] = {"bitmap_data_arena": data_arena}
    for index, (name, _physical_id) in enumerate(FIXED_RECORDS):
        code = FIXED_SCRATCH_CODE + index * FIXED_CELLS
        generated[name] = _terminated_row(
            tuple(range(code, code + FIXED_CELLS)), 5, f"MAP2D {name}"
        )
    generated["overview_suffix_row"] = _terminated_row(
        layout.overview_suffix, 5, "MAP2D overview suffix"
    )
    generated["talk_prompt_row"] = _terminated_row(
        tuple(range(PROMPT_CELLS)), PROMPT_CELLS + 1, "MAP2D talk prompt"
    )

    for key, recipe_name in (
        ("talk_choice_yes", "talk_choice_yes_row"),
        ("talk_choice_no", "talk_choice_no_row"),
    ):
        codes = layout.choices[key]
        words = len(recipes[recipe_name].expected) // 2
        generated[recipe_name] = (
            _terminated_row(codes, words, f"MAP2D {key}")
            if len(codes) + 1 <= words
            else recipes[recipe_name].expected
        )
    generated["area_ward_origin"] = bytes.fromhex("0228")

    links = dict(name_links)
    links.update(prompt_links)
    return RuntimeBuild(
        MappingProxyType(
            {
                "name_runtime_arena": name_arena,
                "prompt_runtime": prompt_code,
            }
        ),
        MappingProxyType(generated),
        MappingProxyType(links),
        name_used + len(prompt_code) + data_used,
        NAME_RUNTIME_CAPACITY + PROMPT_RUNTIME_CAPACITY + BITMAP_ARENA_CAPACITY,
        choice_cells,
    )


def _instruction(recipe: PatchRecipe) -> bytes:
    source = recipe.replacement.instruction
    assert source is not None
    try:
        result = assemble(source, recipe.address)
    except AssemblyError as error:
        raise ValueError(f"{recipe.group}/{recipe.name}: {error}") from error
    if result.warnings or len(result.data) != len(recipe.expected):
        raise ValueError(f"{recipe.group}/{recipe.name}: invalid instruction")
    return result.data


def _bind_patches(
    config: PatchRecipeConfiguration,
    stock: bytes,
) -> tuple[tuple[Patch, ...], RuntimeBuild]:
    runtime = _build_runtime(config)
    output: list[Patch] = []
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
                raise ValueError(f"unknown MAP2D assembly {recipe.name}") from error
            assembly_seen.add(recipe.name)
        elif replacement_recipe.kind == "generated":
            if replacement_recipe.generator != "map_2d_data":
                raise ValueError(f"unknown MAP2D generator for {recipe.name}")
            try:
                replacement = runtime.generated[recipe.name]
            except KeyError as error:
                raise ValueError(
                    f"unknown MAP2D generated data {recipe.name}"
                ) from error
            generated_seen.add(recipe.name)
        elif replacement_recipe.kind == "linked_pointer":
            link = replacement_recipe.link
            assert link is not None
            try:
                replacement = struct.pack(">I", runtime.links[link])
            except KeyError as error:
                raise ValueError(f"unknown MAP2D assembly link {link}") from error
            links_seen.add(link)
        elif replacement_recipe.kind == "pointer":
            pointer = replacement_recipe.pointer
            assert pointer is not None
            replacement = struct.pack(">I", pointer)
        elif replacement_recipe.kind == "instruction":
            replacement = _instruction(recipe)
        else:
            raise ValueError(
                f"{recipe.group}/{recipe.name}: unsupported MAP2D replacement kind"
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
        raise ValueError("MAP2D assembly ownership differs from config")
    if generated_seen != set(runtime.generated):
        raise ValueError("MAP2D generated-data ownership differs from config")
    expected_links = {
        recipe.replacement.link
        for recipe in config.patches[TARGET]
        if recipe.replacement.kind == "linked_pointer"
    }
    if links_seen != expected_links or not links_seen <= set(runtime.links):
        raise ValueError("MAP2D linked-pointer ownership differs from config")
    return tuple(output), runtime


def build_map_2d_ui() -> Map2dUiBuild:
    """Build the complete MAP2D.BIN surface from the verified game disc."""
    config = _configuration()
    stock = _stock_source()
    _validate_sources(config, stock)
    _validate_surfaces()
    patches, runtime = _bind_patches(config, stock)
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
    return Map2dUiBuild(
        apply_patches(stock, LOAD_ADDRESS, patches),
        patches,
        ASSET_FILES,
        assembly_files,
        RUNTIME_INPUT_FILES,
        MappingProxyType({f"game:{TARGET}": _sha256(stock)}),
        runtime.used_size,
        runtime.capacity,
    )
