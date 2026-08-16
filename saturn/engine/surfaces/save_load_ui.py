"""Compose the translated Saturn SAVE/LOAD interfaces from authored surfaces."""

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
from engine.core.sh2 import AssemblyError, assemble
from engine.shared.font8 import font8_tables
from engine.shared.player_names import (
    CODENAME_BYTES,
    NAME_FW,
    NAME_FW_FULL,
    PLAYER_NAME_FIELDS,
    byte_to_advance_table,
    byte_to_font16_table,
    byte_to_font8_table,
)
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
from text.util.tokens import Named, Raw, Text, parse_tokens


ENGINE_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = ENGINE_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "save_load_ui.json"
FONT_ROOT = SATURN_ROOT / "font" / "generated" / "game"
FONT16_PATH = FONT_ROOT / "FONT16.FON"
FONT16_METRICS_PATH = FONT_ROOT / "FONT16_metrics.json"
FONT8_PATH = FONT_ROOT / "FONT8.FON"
FONT8_METRICS_PATH = FONT_ROOT / "FONT8_metrics.json"

SAVE_LOAD_ASSET_PATH = ASSET_ROOT / "save_load.json"
LOCATION_ASSET_PATH = ASSET_ROOT / "locations.json"
LOCATION_FORMAT_ASSET_PATH = ASSET_ROOT / "field" / "location_formats.json"
ASSET_FILES = (
    SAVE_LOAD_ASSET_PATH,
    LOCATION_ASSET_PATH,
    LOCATION_FORMAT_ASSET_PATH,
)

SAVE_LOAD_BINDING_PATH = BINDING_ROOT / "save_load.json"
LOCATION_BINDING_PATH = BINDING_ROOT / "locations.json"
LOCATION_FORMAT_BINDING_PATH = BINDING_ROOT / "save_load_location_formats.json"
SAVE_CORPUS_PATH = CORPUS_ROOT / "game" / "addressed" / "save_static.json"
LOAD_CORPUS_PATH = CORPUS_ROOT / "game" / "addressed" / "load_static.json"
CAPACITY_CORPUS_PATH = CORPUS_ROOT / "game" / "addressed" / "load_capacity.json"
DUNGEON_CORPUS_PATH = (
    CORPUS_ROOT / "game" / "addressed" / "dungeon_locations.json"
)
CORPUS_FILES = (
    SAVE_CORPUS_PATH,
    LOAD_CORPUS_PATH,
    CAPACITY_CORPUS_PATH,
    DUNGEON_CORPUS_PATH,
)
RUNTIME_INPUT_FILES = (
    FONT16_PATH,
    FONT16_METRICS_PATH,
    FONT8_PATH,
    FONT8_METRICS_PATH,
    SATURN_ROOT / "text" / "config" / "surfaces.json",
    SATURN_ROOT / "rom" / "discs.json",
    SAVE_LOAD_BINDING_PATH,
    LOCATION_BINDING_PATH,
    LOCATION_FORMAT_BINDING_PATH,
    *CORPUS_FILES,
)

SAVE_TARGET = "SAVE.BIN"
LOAD_TARGET = "LOAD.BIN"
MAZE_SOURCE = "MAZE.BIN"
TARGETS = (SAVE_TARGET, LOAD_TARGET)
LOAD_ADDRESS = 0x06020000

FONT16_BASE = 0x0021A000
FONT16_CELLS = 1872
FONT16_WIDTH_LIMIT = 268
PADDING_CODE = 0xFFFF

DUNGEON_RECORD_COUNT = 144
DUNGEON_SOURCE_OFFSET = 0x2532C
DUNGEON_MIRROR_OFFSETS = MappingProxyType(
    {SAVE_TARGET: 0x50928, LOAD_TARGET: 0x51810}
)
DUNGEON_SOURCE_RECORD_BYTES = 0x20
DUNGEON_SOURCE_PREFIX_BYTES = 12
DUNGEON_OUTPUT_CELLS = 24
DUNGEON_PIXEL_LIMIT = 144

SPECIAL_LOCATION_IDS = (
    "game.save_static.o051b2c",
    "game.save_static.o051b30",
    "game.save_static.o051b3a",
    "game.save_static.o051b42",
    "game.save_static.o051b4a",
    "game.save_static.o051b52",
    "game.save_static.o051b5a",
    "game.save_static.o051b62",
)
DUNGEON_LOCATION_IDS = tuple(
    f"game.dungeon_locations.locations.r{index:04d}"
    for index in range(DUNGEON_RECORD_COUNT)
)


@dataclass(frozen=True, slots=True)
class Font16Layout:
    widths: bytes
    codes: Mapping[str, int]
    advances: Mapping[str, int]
    glyphs: Mapping[str, tuple[int, int]]


@dataclass(frozen=True, slots=True)
class SlotTemplates:
    name_separator: str
    level_prefix: str
    date_separator: str
    time_separator: str


@dataclass(frozen=True, slots=True)
class RuntimeComponent:
    data: bytes
    used_size: int
    links: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class TargetRuntime:
    components: Mapping[str, RuntimeComponent]
    links: Mapping[str, int]
    generated: Mapping[str, bytes]


@dataclass(frozen=True, slots=True)
class SaveLoadUiBuild:
    data: Mapping[str, bytes]
    patches: Mapping[str, tuple[Patch, ...]]
    asset_files: tuple[Path, ...]
    assembly_files: tuple[Path, ...]
    runtime_input_files: tuple[Path, ...]
    source_inputs: Mapping[str, str]
    runtime_used_sizes: Mapping[str, Mapping[str, int]]
    runtime_capacities: Mapping[str, Mapping[str, int]]


@dataclass(frozen=True, slots=True)
class UiSpec:
    target: str
    cave_address: int
    cave_capacity: int
    original_blitter: int
    dungeon_index: int
    dungeon_draw_text: int
    dungeon_draw_context: int


@dataclass(frozen=True, slots=True)
class NameSpec:
    target: str
    cave_address: int
    cave_capacity: int


UI_SPECS = MappingProxyType(
    {
        SAVE_TARGET: UiSpec(
            SAVE_TARGET,
            0x06020800,
            0x1DAC,
            0x06028128,
            0x06073BC9,
            0x060281E8,
            0x06070560,
        ),
        LOAD_TARGET: UiSpec(
            LOAD_TARGET,
            0x06020C00,
            0x1DAC,
            0x06029460,
            0x06074AA9,
            0x06029520,
            0x06071654,
        ),
    }
)
NAME_SPECS = MappingProxyType(
    {
        SAVE_TARGET: NameSpec(SAVE_TARGET, 0x06020040, 0x7C0),
        LOAD_TARGET: NameSpec(LOAD_TARGET, 0x06020440, 0x7C0),
    }
)
SYSTEM_ADDRESSES = MappingProxyType(
    {SAVE_TARGET: 0x060225AC, LOAD_TARGET: 0x060229AC}
)
SYSTEM_CAPACITIES = MappingProxyType({SAVE_TARGET: 392, LOAD_TARGET: 1508})
LOAD_REBUILD_ADDRESS = 0x06020040
LOAD_REBUILD_CAPACITY = 0x400

_NAME_TEMPLATE = re.compile(r"^\{first_name\}(.?)\{last_name\}$")
_LEVEL_TEMPLATE = re.compile(r"^([^{}]+)\{level\}$")
_DATE_TEMPLATE = re.compile(r"^\{day\}([^{}])\{month\}$")
_TIME_TEMPLATE = re.compile(r"^\{hour\}([^{}])\{minute\}$")
_CAPACITY_FIELDS = frozenset(
    {
        "save_capacity_error",
        "save_capacity_failure",
        "insufficient_free_space_instructions",
    }
)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        return _sha256(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"missing SAVE/LOAD input: {path}") from error


def _configuration() -> PatchRecipeConfiguration:
    return load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="save_load.ui",
        target_names=set(TARGETS),
        input_names={
            "font16_sha256",
            "font16_metrics_sha256",
            "font8_sha256",
            "font8_metrics_sha256",
            "maze_sha256",
        },
    )


def _source_files() -> Mapping[str, bytes]:
    catalog = load_catalog()
    try:
        game = catalog["game"]
    except KeyError as error:
        raise ValueError("disc catalog has no game source") from error
    return MappingProxyType(
        read_source_files(
            validate_source(game, verify_hashes=False),
            (*TARGETS, MAZE_SOURCE),
        )
    )


def _validate_sources(
    config: PatchRecipeConfiguration, sources: Mapping[str, bytes]
) -> None:
    if set(sources) != {*TARGETS, MAZE_SOURCE}:
        raise ValueError("SAVE/LOAD source set changed")
    for target in TARGETS:
        contract = config.targets[target]
        source = sources[target]
        if (
            contract.load_address != LOAD_ADDRESS
            or len(source) != contract.size
            or _sha256(source) != contract.stock_sha256
        ):
            raise ValueError(f"{target} does not match the configured stock target")
    actual = {
        "font16_sha256": _file_sha256(FONT16_PATH),
        "font16_metrics_sha256": _file_sha256(FONT16_METRICS_PATH),
        "font8_sha256": _file_sha256(FONT8_PATH),
        "font8_metrics_sha256": _file_sha256(FONT8_METRICS_PATH),
        "maze_sha256": _sha256(sources[MAZE_SOURCE]),
    }
    for name, expected in config.inputs.items():
        if actual[name] != expected:
            raise ValueError(
                f"SAVE/LOAD {name} expected SHA-256 {expected}, found {actual[name]}"
            )


def _font16_layout() -> Font16Layout:
    try:
        document = json.loads(FONT16_METRICS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid FONT16 metrics: {FONT16_METRICS_PATH}") from error
    if document.get("version") != 2 or not document.get("complete"):
        raise ValueError("SAVE/LOAD requires complete version-2 FONT16 metrics")
    width_table = document.get("width_table")
    if not isinstance(width_table, dict) or width_table.get("code_limit") != FONT16_WIDTH_LIMIT:
        raise ValueError("SAVE/LOAD FONT16 width-table limit changed")
    widths = bytearray(FONT16_WIDTH_LIMIT)
    codes: dict[str, int] = {}
    advances: dict[str, int] = {}
    glyphs: dict[str, tuple[int, int]] = {}
    for row in document.get("glyphs", ()):
        code = row.get("code")
        advance = row.get("advance")
        if (
            type(code) is not int
            or type(advance) is not int
            or not 0 <= code < FONT16_WIDTH_LIMIT
            or not 1 <= advance <= 16
        ):
            raise ValueError("SAVE/LOAD FONT16 metrics contain an invalid glyph")
        if widths[code] not in (0, advance):
            raise ValueError(f"FONT16 code {code} has conflicting advances")
        widths[code] = advance
        for text in (row.get("text"), *row.get("aliases", ())):
            if isinstance(text, str) and text:
                glyphs.setdefault(text, (code, advance))
                if len(text) == 1:
                    codes.setdefault(text, code)
                    advances.setdefault(text, advance)
    required = set(" 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz?:/.-")
    if not required <= set(codes):
        raise ValueError("SAVE/LOAD FONT16 atlas lacks required Latin glyphs")
    return Font16Layout(
        bytes(widths),
        MappingProxyType(codes),
        MappingProxyType(advances),
        MappingProxyType(glyphs),
    )


def _materialize_capacity(value: str, capacity: str) -> str:
    output: list[str] = []
    supplied = 0
    for token in parse_tokens(value):
        if isinstance(token, Text):
            output.append(token.value)
        elif isinstance(token, Named) and token.name == "capacity_blocks":
            output.append(capacity)
            supplied += 1
        elif isinstance(token, Named):
            output.append(f"{{{token.name}}}")
        elif isinstance(token, Raw):
            output.append(f"{{{token.kind}:{token.value:0{token.width * 2}x}}}")
    if supplied != 1:
        raise ValueError(
            "SAVE/LOAD capacity message must contain one {capacity_blocks} token"
        )
    return "".join(output)


def _asset_text(name: str) -> str:
    catalog = load_asset("save_load.json")
    try:
        value = catalog.entries[name].fields["text"].translation
    except KeyError as error:
        raise ValueError(f"save_load.json is missing {name}.text") from error
    if not value:
        raise ValueError(f"save_load.json {name}.text is untranslated")
    if name in _CAPACITY_FIELDS:
        capacity = catalog.entries["capacity_number"].fields["text"].translation
        if not capacity or "{" in capacity or "}" in capacity:
            raise ValueError("save_load.capacity_number must be literal text")
        value = _materialize_capacity(value, capacity)
    return value


def _validate_text_bindings() -> None:
    physical = load_physical_record_files(CORPUS_FILES)
    load_binding(SAVE_LOAD_BINDING_PATH, physical_records=physical)
    load_binding(LOCATION_BINDING_PATH, physical_records=physical)
    load_binding(LOCATION_FORMAT_BINDING_PATH, physical_records=physical)


def _validate_surfaces() -> None:
    expected = {
        "save_load.dungeon_location": ("font16", 1, "pixels", 144, 24),
        "save_load.special_location": ("font16", 1, "pixels", 112, 16),
        "save_load.slot_name": ("font16", 1, "pixels", 128, 17),
        "save_load.slot_level": ("font16", 1, "pixels", 64, 4),
        "save_load.slot_date": ("font16", 1, "pixels", 80, 5),
        "save_load.slot_time": ("font16", 1, "pixels", 80, 5),
        "save_load.slot_state": ("font16", 1, "pixels", 80, 5),
        "save_load.prompt": ("font16", 1, "pixels", 176, 11),
        "save_load.confirm_choice": ("font16", 1, "pixels", 48, 3),
        "save_load.small_message": ("font16", 3, "pixels", 176, 24),
        "save_load.capacity_message": ("font16", 2, "pixels", 272, 25),
        "save_load.start_warning": ("font16", 4, "pixels", 320, 63),
        "save_load.storage_warning": ("font16", 6, "pixels", 320, 63),
        "save_load.capacity": ("font16", 1, "glyph_cells", 3, 3),
        "save_load.heading": (None, 1, None, None, None),
        "save_load.storage_selector": (None, 1, "pixels", 104, None),
    }
    surfaces = load_surfaces()
    for name, geometry in expected.items():
        layout = surfaces.surface(name).en
        actual = (
            layout.font,
            layout.rows,
            layout.width.unit,
            layout.width.value,
            layout.glyphs,
        )
        if actual != geometry:
            raise ValueError(f"{name} geometry changed: {actual!r}")


def _slot_templates(metrics: Font16Layout) -> SlotTemplates:
    name = _NAME_TEMPLATE.fullmatch(_asset_text("slot_name"))
    level = _LEVEL_TEMPLATE.fullmatch(_asset_text("slot_level"))
    date = _DATE_TEMPLATE.fullmatch(_asset_text("slot_date"))
    time = _TIME_TEMPLATE.fullmatch(_asset_text("slot_time"))
    if (
        name is None
        or len(name.group(1)) != 1
        or not name.group(1).isascii()
        or name.group(1) not in metrics.codes
    ):
        raise ValueError(
            "save_load.slot_name must be "
            "'{first_name}<supported ASCII glyph>{last_name}'"
        )
    if level is None:
        raise ValueError("save_load.slot_level must be '<prefix>{level}'")
    if date is None or time is None:
        raise ValueError("SAVE/LOAD date and time templates need one separator")
    return SlotTemplates(name.group(1), level.group(1), date.group(1), time.group(1))


def _location_text() -> tuple[tuple[str, ...], tuple[str, ...]]:
    physical = load_physical_record_files((DUNGEON_CORPUS_PATH, SAVE_CORPUS_PATH))
    required = frozenset((*DUNGEON_LOCATION_IDS, *SPECIAL_LOCATION_IDS))
    bound = load_bound_translations(
        ("game.dungeon_locations.", "game.save_static."),
        required_ids=set(required),
        binding_paths=(LOCATION_BINDING_PATH,),
        physical_records=physical,
    )
    return (
        tuple(bound[physical_id] for physical_id in DUNGEON_LOCATION_IDS),
        tuple(bound[physical_id] for physical_id in SPECIAL_LOCATION_IDS),
    )


def _encoded(text: str, metrics: Font16Layout, context: str) -> tuple[int, ...]:
    compounds = tuple(
        sorted(
            (value for value in metrics.glyphs if len(value) > 1),
            key=lambda value: (-len(value), metrics.glyphs[value][0]),
        )
    )
    output: list[int] = []
    position = 0
    while position < len(text):
        compound = next(
            (value for value in compounds if text.startswith(value, position)),
            None,
        )
        token = compound if compound is not None else text[position]
        try:
            code, _advance = metrics.glyphs[token]
        except KeyError as error:
            raise ValueError(
                f"{context} uses unsupported FONT16 character {token!r}"
            ) from error
        output.append(code)
        position += len(token)
    return tuple(output)


def _pixel_width(words: tuple[int, ...], metrics: Font16Layout) -> int:
    return sum(metrics.widths[word] for word in words)


def _fixed_words(
    text: str,
    cells: int,
    metrics: Font16Layout,
    context: str,
    *,
    pixel_limit: int | None = None,
    padding: int = PADDING_CODE,
) -> bytes:
    words = _encoded(text, metrics, context)
    width = _pixel_width(words, metrics)
    if len(words) > cells or (pixel_limit is not None and width > pixel_limit):
        raise ValueError(
            f"{context} uses {len(words)}/{cells} cells and {width}/{pixel_limit}px"
        )
    return struct.pack(f">{cells}H", *(words + (padding,) * (cells - len(words))))


def _wrap_rows(
    text: str,
    rows: int,
    cells: int,
    pixel_limit: int,
    metrics: Font16Layout,
    context: str,
) -> tuple[str, ...]:
    output: list[str] = []
    for explicit in text.replace("{n}", "\n").split("\n"):
        words = explicit.split()
        if not words:
            output.append("")
            continue
        current: list[str] = []
        for word in words:
            word_codes = _encoded(word, metrics, context)
            if len(word_codes) > cells or _pixel_width(word_codes, metrics) > pixel_limit:
                raise ValueError(f"{context} word exceeds its row: {word!r}")
            candidate = " ".join((*current, word))
            candidate_codes = _encoded(candidate, metrics, context)
            if current and (
                len(candidate_codes) > cells
                or _pixel_width(candidate_codes, metrics) > pixel_limit
            ):
                output.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        output.append(" ".join(current))
    if len(output) > rows:
        raise ValueError(f"{context} needs {len(output)}/{rows} rows")
    return tuple((*output, *("" for _ in range(rows - len(output)))))


def _fixed_rows(
    text: str,
    rows: int,
    cells: int,
    pixel_limit: int,
    metrics: Font16Layout,
    context: str,
) -> bytes:
    return b"".join(
        _fixed_words(
            row, cells, metrics, context, pixel_limit=pixel_limit
        )
        for row in _wrap_rows(text, rows, cells, pixel_limit, metrics, context)
    )


def _floor_templates() -> Mapping[str, str]:
    catalog = load_asset("field/location_formats.json")
    names = (
        "save_load_floorless",
        "save_load_basement",
        "save_load_above_ground",
    )
    values: dict[str, str] = {}
    for name in names:
        try:
            value = catalog.entries[name].fields["text"].translation
        except KeyError as error:
            raise ValueError(f"location formats are missing {name}.text") from error
        if not value:
            raise ValueError(f"location format {name} is untranslated")
        values[name] = value
    if values["save_load_floorless"] != "{location}":
        raise ValueError("SAVE/LOAD floorless template must be {location}")
    for name in ("save_load_basement", "save_load_above_ground"):
        if values[name].count("{location}") != 1 or values[name].count("{floor}") != 1:
            raise ValueError(f"{name} must contain location and floor exactly once")
    return MappingProxyType(values)


def _dungeon_records(
    maze: bytes,
    names: tuple[str, ...],
    metrics: Font16Layout,
) -> bytes:
    if len(names) != DUNGEON_RECORD_COUNT:
        raise ValueError("SAVE/LOAD needs 144 dungeon location names")
    formats = _floor_templates()
    output = bytearray()
    for index, name in enumerate(names):
        offset = DUNGEON_SOURCE_OFFSET + index * DUNGEON_SOURCE_RECORD_BYTES
        floor = int.from_bytes(maze[offset : offset + 1], "big", signed=True)
        if floor < 0:
            text = formats["save_load_basement"].format(
                location=name, floor=-floor
            )
        elif floor > 0:
            text = formats["save_load_above_ground"].format(
                location=name, floor=floor
            )
        else:
            text = formats["save_load_floorless"].format(location=name)
        words = _encoded(text, metrics, f"dungeon save label {index}")
        width = sum(metrics.widths[word] for word in words)
        if len(words) > DUNGEON_OUTPUT_CELLS or width > DUNGEON_PIXEL_LIMIT:
            raise ValueError(
                f"dungeon save label {index} is {len(words)} cells/{width}px"
            )
        output.extend(
            struct.pack(
                f">{DUNGEON_OUTPUT_CELLS}H",
                *(words + (PADDING_CODE,) * (DUNGEON_OUTPUT_CELLS - len(words))),
            )
        )
    return bytes(output)


def _validate_dungeon_mirrors(sources: Mapping[str, bytes]) -> None:
    canonical = sources[MAZE_SOURCE]
    for target, mirror_base in DUNGEON_MIRROR_OFFSETS.items():
        mirror = sources[target]
        for index in range(DUNGEON_RECORD_COUNT):
            source = DUNGEON_SOURCE_OFFSET + index * DUNGEON_SOURCE_RECORD_BYTES
            destination = mirror_base + index * DUNGEON_SOURCE_RECORD_BYTES
            if (
                canonical[source : source + DUNGEON_SOURCE_PREFIX_BYTES]
                != mirror[destination : destination + DUNGEON_SOURCE_PREFIX_BYTES]
            ):
                raise ValueError(
                    f"{target} dungeon record {index} no longer mirrors MAZE.BIN"
                )


def _assembly_text(paths: tuple[Path, ...]) -> str:
    try:
        return "\n".join(path.read_text(encoding="utf-8") for path in paths)
    except FileNotFoundError as error:
        raise ValueError(f"missing SAVE/LOAD assembly: {error.filename}") from error


def _assembled(
    paths: tuple[Path, ...], address: int, symbols: Mapping[str, int], suffix: str = ""
):
    try:
        result = assemble(_assembly_text(paths) + suffix, address, dict(symbols))
    except AssemblyError as error:
        names = ", ".join(path.name for path in paths)
        raise ValueError(f"SAVE/LOAD assembly failed in {names}: {error}") from error
    if result.warnings:
        raise ValueError("SAVE/LOAD assembly warnings: " + "; ".join(result.warnings))
    return result


def _padded_component(
    data: bytes,
    used_size: int,
    capacity: int,
    links: Mapping[str, int],
    context: str,
) -> RuntimeComponent:
    if len(data) != used_size or used_size > capacity:
        raise ValueError(f"{context} uses {used_size:#x}/{capacity:#x} bytes")
    return RuntimeComponent(
        data + bytes(capacity - used_size), used_size, MappingProxyType(dict(links))
    )


def _name_strip_component(
    recipe: PatchRecipe,
    spec: NameSpec,
    metrics: Font16Layout,
    separator: str,
) -> RuntimeComponent:
    if recipe.address != spec.cave_address or len(recipe.expected) != spec.cave_capacity:
        raise ValueError(f"{spec.target} name-strip cave contract changed")
    if len(recipe.replacement.sources) != 1:
        raise ValueError("SAVE/LOAD name strip needs one readable assembly source")
    atlas = byte_to_font16_table(metrics.codes)
    widths = byte_to_advance_table(metrics.advances)
    separator_byte = ord(separator)
    max_width = max(widths) * 16 + widths[separator_byte]
    scale_bytes = max_width + 16
    if max_width > 0xFF or scale_bytes > 0xFF:
        raise ValueError("SAVE/LOAD joined-name scale map exceeds byte indexing")
    suffix = (
        "\n.align 4\nname_buffer:\n"
        + "    .byte "
        + ", ".join("0" for _ in range(18))
        + "\nname_scale_map:\n    .byte "
        + ", ".join("0" for _ in range(scale_bytes))
        + "\n.align 2\nbyte_to_atlas:\n    .word "
        + ", ".join(str(code) for code in atlas)
        + "\nbyte_to_width:\n    .byte "
        + ", ".join(str(width) for width in widths)
        + "\n"
    )
    result = _assembled(
        recipe.replacement.sources,
        spec.cave_address,
        {
            "FONT16_BASE": FONT16_BASE,
            "NAME_WIDTH": 128,
            "NAME_SEPARATOR": separator_byte,
        },
        suffix,
    )
    return _padded_component(
        result.data,
        len(result.data),
        spec.cave_capacity,
        {"name_strip": result.labels["name_strip"]},
        f"{spec.target} name strip",
    )


def _load_rebuild_component(
    recipe: PatchRecipe,
    metrics16: Font16Layout,
    metrics8: FontMetrics,
    separator: str,
) -> RuntimeComponent:
    if recipe.address != LOAD_REBUILD_ADDRESS or len(recipe.expected) != LOAD_REBUILD_CAPACITY:
        raise ValueError("LOAD name-rebuild cave contract changed")
    if len(recipe.replacement.sources) != 1:
        raise ValueError("LOAD name rebuild needs one readable assembly source")
    _widths8, codes8 = font8_tables(metrics8)
    atlas = byte_to_font16_table(metrics16.codes)
    font8 = byte_to_font8_table(codes8)
    suffix = (
        "\n.align 4\nstage_ptrs:\n    .long "
        + ", ".join(f"{row.stage_address:#010x}" for row in PLAYER_NAME_FIELDS)
        + "\n.align 2\nbyte_to_atlas:\n    .word "
        + ", ".join(str(code) for code in atlas)
        + "\nbyte_to_font8:\n    .byte "
        + ", ".join(str(code) for code in font8)
        + "\n"
    )
    result = _assembled(
        recipe.replacement.sources,
        LOAD_REBUILD_ADDRESS,
        {
            "NAME_FW": NAME_FW,
            "NAME_FW_FULL": NAME_FW_FULL,
            "CODENAME": CODENAME_BYTES,
            "prep_names": 0x0602AB5C,
            "name_separator_glyph": metrics16.codes[separator],
        },
        suffix,
    )
    return _padded_component(
        result.data,
        len(result.data),
        LOAD_REBUILD_CAPACITY,
        {"name_rebuild": result.labels["load_namefix"]},
        "LOAD name rebuild",
    )


def _ui_component(
    recipe: PatchRecipe,
    spec: UiSpec,
    metrics: Font16Layout,
    locations: tuple[str, ...],
    dungeon: bytes,
) -> RuntimeComponent:
    if recipe.address != spec.cave_address or len(recipe.expected) != spec.cave_capacity:
        raise ValueError(f"{spec.target} UI cave contract changed")
    if len(recipe.replacement.sources) != 2:
        raise ValueError("SAVE/LOAD UI cave needs VWF and dungeon assembly sources")
    if len(locations) != 8:
        raise ValueError("SAVE/LOAD needs eight special location labels")
    location_data = b"".join(
        _fixed_words(
            text,
            16,
            metrics,
            f"special location {index}",
            pixel_limit=112,
        )
        for index, text in enumerate(locations)
    )
    suffix = (
        "\n.align 4\ntext_scratch:\n    .long 0, 0\nwidth_table:\n    .byte "
        + ", ".join(str(width) for width in metrics.widths)
        + "\n.align 2\nlocation_table:\n    .word "
        + ", ".join(
            str(word)
            for word in struct.unpack(f">{len(location_data) // 2}H", location_data)
        )
        + "\n.align 2\ndungeon_table:\n    .word "
        + ", ".join(
            str(word) for word in struct.unpack(f">{len(dungeon) // 2}H", dungeon)
        )
        + "\n"
    )
    result = _assembled(
        recipe.replacement.sources,
        spec.cave_address,
        {
            "ORIGINAL_BLITTER": spec.original_blitter,
            "PADDING_CODE": PADDING_CODE,
            "WIDTH_LIMIT": len(metrics.widths),
            "DUNGEON_INDEX": spec.dungeon_index,
            "DUNGEON_RECORD_BYTES": DUNGEON_OUTPUT_CELLS * 2,
            "DUNGEON_RECORD_CELLS": DUNGEON_OUTPUT_CELLS,
            "DRAW_TEXT": spec.dungeon_draw_text,
            "DRAW_CONTEXT": spec.dungeon_draw_context,
        },
        suffix,
    )
    links = {
        "font16_vwf": result.labels["text_vwf"],
        "dungeon_drawer": result.labels["dungeon_draw_entry"],
        "location_home": result.labels["location_table"],
        "location_office": result.labels["location_table"] + 32,
        "location_asahi": result.labels["location_table"] + 64,
    }
    return _padded_component(
        result.data,
        len(result.data),
        spec.cave_capacity,
        links,
        f"{spec.target} UI",
    )


def _system_component(
    target: str,
    recipe: PatchRecipe,
    metrics: Font16Layout,
) -> tuple[RuntimeComponent, Mapping[str, bytes]]:
    expected_address = SYSTEM_ADDRESSES[target]
    expected_capacity = SYSTEM_CAPACITIES[target]
    if (
        recipe.address != expected_address
        or len(recipe.expected) != expected_capacity
    ):
        raise ValueError(f"{target} system-data cave contract changed")
    address = recipe.address
    data = bytearray()
    links: dict[str, int] = {}

    def append(name: str, value: bytes) -> None:
        data.extend(bytes((-len(data)) % 4))
        links[name] = address + len(data)
        data.extend(value)

    if target == SAVE_TARGET:
        append(
            "save_write_failure",
            _fixed_rows(
                _asset_text("save_write_failure"),
                3,
                24,
                176,
                metrics,
                "save_write_failure",
            ),
        )
        capacity = _asset_text("save_capacity_error").split("{n}")
        if len(capacity) != 2:
            raise ValueError("save_capacity_error must contain exactly one {n}")
        append(
            "save_capacity_error_0",
            _fixed_words(
                capacity[0], 25, metrics, "save_capacity_error line 0", pixel_limit=272
            ),
        )
        append(
            "save_capacity_error_1",
            _fixed_words(
                capacity[1], 25, metrics, "save_capacity_error line 1", pixel_limit=272
            ),
        )
        append(
            "save_capacity_failure",
            _fixed_rows(
                _asset_text("save_capacity_failure"),
                3,
                24,
                176,
                metrics,
                "save_capacity_failure",
            ),
        )
    else:
        append(
            "start_without_save_warning",
            _fixed_rows(
                _asset_text("start_without_save_warning"),
                4,
                63,
                320,
                metrics,
                "start_without_save_warning",
            ),
        )
        append(
            "insufficient_free_space_instructions",
            _fixed_rows(
                _asset_text("insufficient_free_space_instructions"),
                6,
                63,
                320,
                metrics,
                "insufficient_free_space_instructions",
            ),
        )
        capacity = _asset_text("save_capacity_error").split("{n}")
        if len(capacity) != 2:
            raise ValueError("save_capacity_error must contain exactly one {n}")
        append(
            "save_capacity_error_0",
            _fixed_words(
                capacity[0], 25, metrics, "save_capacity_error line 0", pixel_limit=272
            ),
        )
        append(
            "save_capacity_error_1",
            _fixed_words(
                capacity[1], 25, metrics, "save_capacity_error line 1", pixel_limit=272
            ),
        )
        append(
            "load_failure",
            _fixed_rows(
                _asset_text("load_failure"),
                3,
                24,
                176,
                metrics,
                "load_failure",
            ),
        )

    capacity = len(recipe.expected)
    component = _padded_component(
        bytes(data), len(data), capacity, links, f"{target} system data"
    )
    stem = target.lower().removesuffix(".bin")
    return component, MappingProxyType({f"{stem}_system_data": component.data})


def _direct_data(
    target: str, metrics: Font16Layout, templates: SlotTemplates
) -> dict[str, bytes]:
    digit_width = max(metrics.widths[metrics.codes[str(value)]] for value in range(10))
    level_limit = 64 - digit_width * 3
    date_limit = 80 - digit_width * 4
    generated: dict[str, bytes] = {
        "level_prefix": _fixed_words(
            templates.level_prefix,
            2,
            metrics,
            "slot_level prefix",
            pixel_limit=level_limit,
        ),
        "date_separator": _fixed_words(
            templates.date_separator,
            1,
            metrics,
            "slot_date separator",
            pixel_limit=date_limit,
        ),
        "time_separator": _fixed_words(
            templates.time_separator,
            1,
            metrics,
            "slot_time separator",
            pixel_limit=date_limit,
        ),
        "empty": _fixed_words(
            _asset_text("empty"), 5, metrics, "empty slot", pixel_limit=80
        ),
    }
    if target == SAVE_TARGET:
        generated.update(
            {
                "prompt_overwrite": _fixed_words(
                    _asset_text("prompt_overwrite"),
                    11,
                    metrics,
                    "overwrite prompt",
                    pixel_limit=176,
                    padding=0,
                ),
                "confirm_yes": _fixed_words(
                    _asset_text("confirm_yes"),
                    3,
                    metrics,
                    "save confirm yes",
                    pixel_limit=48,
                    padding=0,
                ),
                "confirm_no": _fixed_words(
                    _asset_text("confirm_no"),
                    3,
                    metrics,
                    "save confirm no",
                    pixel_limit=48,
                    padding=0,
                ),
                "prompt_quit_game": _fixed_words(
                    _asset_text("prompt_quit_game"),
                    11,
                    metrics,
                    "quit prompt",
                    pixel_limit=176,
                    padding=0,
                ),
                "name_strip_edge_left": struct.pack(">H", 0x075B),
                "name_strip_edge_right": struct.pack(">H", 0x075F),
            }
        )
    else:
        generated["capacity_number"] = _fixed_words(
            _asset_text("capacity_number"), 3, metrics, "capacity number"
        )
    return generated


def _runtime_for_target(
    target: str,
    config: PatchRecipeConfiguration,
    sources: Mapping[str, bytes],
    metrics16: Font16Layout,
    metrics8: FontMetrics,
    templates: SlotTemplates,
    dungeon_names: tuple[str, ...],
    special_locations: tuple[str, ...],
) -> TargetRuntime:
    recipes = {recipe.name: recipe for recipe in config.patches[target]}
    if len(recipes) != len(config.patches[target]):
        raise ValueError(f"{target} patch names are not unique")
    dungeon = _dungeon_records(sources[MAZE_SOURCE], dungeon_names, metrics16)
    components: dict[str, RuntimeComponent] = {}
    if target == LOAD_TARGET:
        components["name_rebuild"] = _load_rebuild_component(
            recipes["load_name_rebuild"], metrics16, metrics8, templates.name_separator
        )
    stem = target.lower().removesuffix(".bin")
    components["name_strip"] = _name_strip_component(
        recipes[f"{stem}_name_strip"],
        NAME_SPECS[target],
        metrics16,
        templates.name_separator,
    )
    components["ui"] = _ui_component(
        recipes[f"{stem}_ui_runtime"],
        UI_SPECS[target],
        metrics16,
        special_locations,
        dungeon,
    )
    system, system_generated = _system_component(
        target,
        recipes[f"{stem}_system_data"],
        metrics16,
    )
    components["system_data"] = system
    links: dict[str, int] = {}
    for component in components.values():
        overlap = set(links) & set(component.links)
        if overlap:
            raise ValueError(f"{target} runtime links overlap: {sorted(overlap)}")
        links.update(component.links)
    generated = _direct_data(target, metrics16, templates)
    generated.update(system_generated)
    return TargetRuntime(
        MappingProxyType(components),
        MappingProxyType(links),
        MappingProxyType(generated),
    )


def _instruction(recipe: PatchRecipe) -> bytes:
    assert recipe.replacement.instruction is not None
    try:
        result = assemble(recipe.replacement.instruction, recipe.address)
    except AssemblyError as error:
        raise ValueError(f"{recipe.name} instruction failed: {error}") from error
    if result.warnings or len(result.data) != len(recipe.expected):
        raise ValueError(f"{recipe.name} is not one size-preserving instruction")
    return result.data


def _dungeon_hook(recipe: PatchRecipe, runtime: TargetRuntime) -> bytes:
    if len(recipe.replacement.sources) != 1:
        raise ValueError("SAVE/LOAD dungeon hook needs one assembly source")
    result = _assembled(
        recipe.replacement.sources,
        recipe.address,
        {"DUNGEON_DRAWER": runtime.links["dungeon_drawer"]},
    )
    return result.data


def _bind_target(
    target: str,
    config: PatchRecipeConfiguration,
    source: bytes,
    runtime: TargetRuntime,
) -> tuple[Patch, ...]:
    expected = {
        recipe.name: resolve_recipe_expected(recipe, source, LOAD_ADDRESS)
        for recipe in config.patches[target]
    }
    stem = target.lower().removesuffix(".bin")
    component_by_recipe = {
        f"{stem}_name_strip": "name_strip",
        f"{stem}_ui_runtime": "ui",
        f"{stem}_system_data": "system_data",
    }
    if target == LOAD_TARGET:
        component_by_recipe["load_name_rebuild"] = "name_rebuild"
    output: list[Patch] = []
    generated_seen: set[str] = set()
    for recipe in config.patches[target]:
        replacement_recipe = recipe.replacement
        if replacement_recipe.kind == "assembly":
            if recipe.name in component_by_recipe:
                replacement = runtime.components[component_by_recipe[recipe.name]].data
            elif recipe.name == "dungeon_hook":
                replacement = _dungeon_hook(recipe, runtime)
            else:
                raise ValueError(f"{target}/{recipe.name}: unknown assembly owner")
        elif replacement_recipe.kind == "linked_pointer":
            link = replacement_recipe.link
            assert link is not None
            try:
                replacement = struct.pack(">I", runtime.links[link])
            except KeyError as error:
                raise ValueError(f"{target}/{recipe.name}: unknown runtime link") from error
        elif replacement_recipe.kind == "instruction":
            replacement = _instruction(recipe)
        elif replacement_recipe.kind == "generated":
            if replacement_recipe.generator != "save_load_data":
                raise ValueError(f"{target}/{recipe.name}: unknown data generator")
            try:
                replacement = runtime.generated[recipe.name]
            except KeyError as error:
                raise ValueError(f"{target}/{recipe.name}: no generated owner") from error
            generated_seen.add(recipe.name)
        elif replacement_recipe.kind == "pointer":
            assert replacement_recipe.pointer is not None
            replacement = struct.pack(">I", replacement_recipe.pointer)
        else:
            raise ValueError(f"{target}/{recipe.name}: unsupported replacement recipe")
        if len(replacement) != len(expected[recipe.name]):
            raise ValueError(
                f"{target}/{recipe.name}: generated {len(replacement)} bytes, "
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
    unused = set(runtime.generated) - generated_seen
    if unused:
        raise ValueError(
            f"{target} SAVE/LOAD data has no configured owner: "
            + ", ".join(sorted(unused))
        )
    return tuple(output)


def build_save_load_ui(
    bases: Mapping[str, bytes] | None = None,
) -> SaveLoadUiBuild:
    """Build both stock-backed SAVE/LOAD targets without visual-owned images."""
    config = _configuration()
    _validate_surfaces()
    discovered = dict(_source_files())
    if bases is not None:
        if set(bases) != set(TARGETS):
            raise ValueError("SAVE/LOAD bases must contain SAVE.BIN and LOAD.BIN")
        discovered.update(bases)
    sources = MappingProxyType(discovered)
    _validate_sources(config, sources)
    _validate_dungeon_mirrors(sources)
    _validate_text_bindings()

    metrics16 = _font16_layout()
    metrics8 = FontMetrics.load(FONT8_METRICS_PATH)
    templates = _slot_templates(metrics16)
    dungeon_names, special_locations = _location_text()
    runtimes = {
        target: _runtime_for_target(
            target,
            config,
            sources,
            metrics16,
            metrics8,
            templates,
            dungeon_names,
            special_locations,
        )
        for target in TARGETS
    }
    patches = {
        target: _bind_target(target, config, sources[target], runtimes[target])
        for target in TARGETS
    }
    data = {
        target: apply_patches(sources[target], LOAD_ADDRESS, patches[target])
        for target in TARGETS
    }
    assembly_files = tuple(
        sorted(
            {
                source
                for target in TARGETS
                for recipe in config.patches[target]
                for source in recipe.replacement.sources
            },
            key=lambda path: path.as_posix(),
        )
    )
    used = {
        target: MappingProxyType(
            {
                name: component.used_size
                for name, component in runtimes[target].components.items()
            }
        )
        for target in TARGETS
    }
    capacities = {
        target: MappingProxyType(
            {
                name: len(component.data)
                for name, component in runtimes[target].components.items()
            }
        )
        for target in TARGETS
    }
    return SaveLoadUiBuild(
        MappingProxyType(data),
        MappingProxyType(patches),
        ASSET_FILES,
        assembly_files,
        RUNTIME_INPUT_FILES,
        MappingProxyType(
            {f"game:{name}": _sha256(sources[name]) for name in (*TARGETS, MAZE_SOURCE)}
        ),
        MappingProxyType(used),
        MappingProxyType(capacities),
    )
