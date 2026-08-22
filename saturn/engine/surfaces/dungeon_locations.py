"""Build the Saturn dungeon-location consumers from shared authored text."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
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
from text.util.surfaces import load_surfaces
from text.util.tokens import Named, parse_tokens


ENGINE_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = ENGINE_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "dungeon_locations.json"
FONT_ROOT = SATURN_ROOT / "font" / "generated" / "game"
FONT16_PATH = FONT_ROOT / "FONT16.FON"
FONT16_METRICS_PATH = FONT_ROOT / "FONT16_metrics.json"
SURFACE_PATH = SATURN_ROOT / "text" / "config" / "surfaces.json"

LOCATION_ASSET_PATH = ASSET_ROOT / "locations.json"
LOCATION_FORMAT_ASSET_PATH = ASSET_ROOT / "field" / "location_formats.json"
ELEVATOR_ASSET_PATH = ASSET_ROOT / "field" / "elevator.json"
LOCATION_BINDING_PATH = BINDING_ROOT / "locations.json"
LOCATION_CORPUS_PATH = CORPUS_ROOT / "game" / "addressed" / "dungeon_locations.json"
SAVE_CORPUS_PATH = CORPUS_ROOT / "game" / "addressed" / "save_static.json"
MIRROR_BINDING_PATH = BINDING_ROOT / "location_mirrors.json"
MIRROR_CORPUS_PATH = (
    CORPUS_ROOT / "game" / "addressed" / "dungeon_location_mirrors.json"
)

AUTOMAP_ASSET_PATH = ASSET_ROOT / "field" / "automap.json"
FIELD_MESSAGES_ASSET_PATH = ASSET_ROOT / "field" / "messages.json"
AUTOMAP_BINDING_PATH = BINDING_ROOT / "field_automap.json"
AUTOMAP_CHOICES_BINDING_PATH = BINDING_ROOT / "field_automap_choices.json"
AUTOMAP_MARKER_CORPUS_PATH = (
    CORPUS_ROOT / "game" / "addressed" / "automap_marker_ui.json"
)
AUTOMAP_SYSTEM_CORPUS_PATH = (
    CORPUS_ROOT / "game" / "addressed" / "automap_system.json"
)

ASSET_FILES = (
    LOCATION_ASSET_PATH,
    LOCATION_FORMAT_ASSET_PATH,
    ELEVATOR_ASSET_PATH,
    AUTOMAP_ASSET_PATH,
    FIELD_MESSAGES_ASSET_PATH,
)
RUNTIME_INPUT_FILES = (
    FONT16_PATH,
    FONT16_METRICS_PATH,
    SURFACE_PATH,
    SATURN_ROOT / "rom" / "discs.json",
    LOCATION_BINDING_PATH,
    MIRROR_BINDING_PATH,
    AUTOMAP_BINDING_PATH,
    AUTOMAP_CHOICES_BINDING_PATH,
    LOCATION_CORPUS_PATH,
    SAVE_CORPUS_PATH,
    MIRROR_CORPUS_PATH,
    AUTOMAP_MARKER_CORPUS_PATH,
    AUTOMAP_SYSTEM_CORPUS_PATH,
)

MAZE_TARGET = "MAZE.BIN"
AUTOMAP_TARGET = "AUTOMAPC.BIN"
PRIMARY_TARGETS = frozenset({MAZE_TARGET, AUTOMAP_TARGET})
LOAD_ADDRESS = 0x06020000

FONT16_BASE = 0x0021A000
TOP_CODE = 0x0740
BOTTOM_CODE = 0x0744
LABEL_SENTINEL = 0x7E00
LABEL_GAP = 2
RECORD_COUNT = 144
RECORD_SIZE = 0x20
TEXT_BYTES = 12
FONT16_CELLS = 1872

AUTOMAP_ASCII_DRAWER = 0x06026C28
AUTOMAP_RAW_DRAWER = 0x06026CD0
AUTOMAP_NO_DATA_POINTER = 0x06029AA8
AUTOMAP_YES_POINTER = 0x0602A5E0
AUTOMAP_NO_POINTER = 0x0602A5E4
AUTOMAP_DRAW_DESCRIPTOR = 0x06059E70
AUTOMAP_DELETE_SURFACE = 66
AUTOMAP_MARKER_PIXEL_LIMIT = 112
MARKER_POPUP_PIXEL_LIMIT = 64
MARKER_BITMAP_FLOOR_CELLS = 4

LOCATION_IDS = tuple(
    f"game.dungeon_locations.locations.r{index:04d}"
    for index in range(RECORD_COUNT)
)
MARKER_IDS = MappingProxyType(
    {
        "marker_no_data": "game.automap_marker_ui.o009aa8",
        "marker_delete": "game.automap_system.o00a69c",
        "marker_yes": "game.automap_marker_ui.o00a5e0",
        "marker_no": "game.automap_marker_ui.o00a5e4",
    }
)
MARKER_ORDER = tuple(MARKER_IDS)


@dataclass(frozen=True, slots=True)
class Font16Metrics:
    widths: bytes
    codes: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class FloorFormat:
    negative_prefix: str
    suffix: str

    def text(self, raw: int) -> str:
        floor = raw - 256 if raw >= 128 else raw
        if floor == 0:
            return ""
        if not -99 <= floor <= 99:
            raise ValueError(f"dungeon floor {floor} exceeds the two-digit renderer")
        prefix = self.negative_prefix if floor < 0 else ""
        return f"{prefix}{abs(floor)}{self.suffix}"


@dataclass(frozen=True, slots=True)
class ElevatorFormat:
    lower_symbol: str
    floor_symbol: str
    parts: tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class RuntimeSpec:
    target: str
    table_address: int
    return_address: int
    stock_name_drawer: int
    automap: bool


@dataclass(frozen=True, slots=True)
class MarkerStrip:
    name: str
    bitmap: bytes
    cells: int
    width: int


@dataclass(frozen=True, slots=True)
class RuntimeImage:
    cave: bytes
    used_cave: bytes
    table: bytes
    links: Mapping[str, int]
    labels: tuple[tuple[str, str, int], ...]


@dataclass(frozen=True, slots=True)
class DungeonLocationsBuild:
    outputs: Mapping[str, bytes]
    patches: Mapping[str, tuple[Patch, ...]]
    runtime_used: Mapping[str, bytes]
    labels: Mapping[str, tuple[tuple[str, str, int], ...]]
    asset_files: tuple[Path, ...]
    assembly_files: tuple[Path, ...]
    runtime_input_files: tuple[Path, ...]
    source_inputs: Mapping[str, str]


SPECS = MappingProxyType(
    {
        MAZE_TARGET: RuntimeSpec(
            MAZE_TARGET,
            0x0604532C,
            0x0604010C,
            0x0603FEA0,
            False,
        ),
        AUTOMAP_TARGET: RuntimeSpec(
            AUTOMAP_TARGET,
            0x0605A418,
            0x06029B98,
            0x06026CD0,
            True,
        ),
    }
)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        return _sha256(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"missing dungeon-location input: {path}") from error


def _target_names_from_config() -> set[str]:
    try:
        document = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid dungeon-location config: {CONFIG_PATH}") from error
    targets = document.get("targets")
    if not isinstance(targets, dict) or not targets:
        raise ValueError("dungeon-location config has no targets")
    names = set(targets)
    for name in names:
        path = PurePosixPath(name)
        if (
            not isinstance(name, str)
            or not name
            or "\\" in name
            or path.is_absolute()
            or ".." in path.parts
            or path.suffix != ".BIN"
        ):
            raise ValueError(f"invalid dungeon-location target selector {name!r}")
    return names


def _configuration() -> PatchRecipeConfiguration:
    config = load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="dungeon.locations",
        target_names=_target_names_from_config(),
        input_names={"font16_sha256", "font16_metrics_sha256"},
    )
    groups = {
        target: {recipe.group for recipe in recipes}
        for target, recipes in config.patches.items()
    }
    runtime = {target for target, value in groups.items() if value == {"dungeon_location_runtime"}}
    landings = {
        target
        for target, value in groups.items()
        if value == {"dungeon_location_landing_mirrors"}
    }
    kai = {
        target
        for target, value in groups.items()
        if value == {"dungeon_location_kai_mirrors"}
    }
    if (
        runtime != PRIMARY_TARGETS
        or len(landings) != 17
        or len(kai) != 98
        or runtime | landings | kai != set(config.targets)
        or sum(len(config.patches[target]) for target in landings) != 56
        or sum(len(config.patches[target]) for target in kai) != 232
    ):
        raise ValueError("dungeon-location physical target inventory changed")
    if any(not target.startswith("MAZEDATA/") for target in landings | kai):
        raise ValueError("dungeon-location mirror escaped MAZEDATA")
    return config


def _source_files(config: PatchRecipeConfiguration) -> Mapping[str, bytes]:
    catalog = load_catalog()
    try:
        game = catalog["game"]
    except KeyError as error:
        raise ValueError("disc catalog has no game source") from error
    return MappingProxyType(
        read_source_files(
            validate_source(game, verify_hashes=False),
            tuple(config.targets),
        )
    )


def _validate_sources(
    config: PatchRecipeConfiguration,
    sources: Mapping[str, bytes],
) -> None:
    if set(sources) != set(config.targets):
        raise ValueError("dungeon-location source set differs from the config")
    for name, contract in config.targets.items():
        source = sources[name]
        if len(source) != contract.size:
            raise ValueError(f"{name}: dungeon-location source size changed")
        actual = _sha256(source)
        if actual != contract.stock_sha256:
            raise ValueError(
                f"{name}: expected stock SHA-256 {contract.stock_sha256}, found {actual}"
            )
    actual_inputs = {
        "font16_sha256": _file_sha256(FONT16_PATH),
        "font16_metrics_sha256": _file_sha256(FONT16_METRICS_PATH),
    }
    for name, expected in config.inputs.items():
        if actual_inputs[name] != expected:
            raise ValueError(
                f"dungeon-location {name} expected SHA-256 {expected}, "
                f"found {actual_inputs[name]}"
            )


def _font16_metrics() -> Font16Metrics:
    try:
        document = json.loads(FONT16_METRICS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid FONT16 metrics: {FONT16_METRICS_PATH}") from error
    width_table = document.get("width_table", {})
    code_limit = width_table.get("code_limit")
    if (
        document.get("version") != 2
        or not document.get("complete")
        or type(code_limit) is not int
        or not 1 <= code_limit <= 0x7FFF
    ):
        raise ValueError("incomplete FONT16 metrics for dungeon locations")
    widths = bytearray(code_limit)
    codes: dict[str, int] = {}
    for row in document.get("glyphs", ()):
        code, advance = row.get("code"), row.get("advance")
        if (
            type(code) is not int
            or not 0 <= code < code_limit
            or type(advance) is not int
            or not 1 <= advance <= 0xFF
        ):
            raise ValueError("invalid dungeon-location FONT16 glyph")
        widths[code] = advance
        for text in (row.get("text"), *row.get("aliases", ())):
            if isinstance(text, str) and len(text) == 1:
                codes.setdefault(text, code)
    try:
        zero = codes["0"]
        if tuple(codes[str(value)] for value in range(10)) != tuple(
            zero + value for value in range(10)
        ):
            raise KeyError("nonconsecutive digits")
    except KeyError as error:
        raise ValueError("dungeon-location FONT16 digits are not consecutive") from error
    return Font16Metrics(bytes(widths), MappingProxyType(codes))


def _surface_text(asset_name: str, entry: str) -> str:
    catalog = load_asset(asset_name)
    try:
        value = catalog.entries[entry].fields["text"].translation
    except KeyError as error:
        raise ValueError(f"{asset_name}: missing {entry}.text") from error
    if not value:
        raise ValueError(f"{asset_name}: {entry}.text is untranslated")
    return value


def _floor_pattern(value: str, *, with_location: bool) -> tuple[str, str]:
    if with_location:
        if value.count("{location}") != 1 or not value.startswith("{location}"):
            raise ValueError("AUTOMAP floor format must begin with {location}")
        value = value.removeprefix("{location}").strip()
    if value.count("{floor}") != 1:
        raise ValueError("dungeon floor format must contain one {floor}")
    prefix, suffix = value.split("{floor}")
    return prefix, suffix


def _floor_formats() -> Mapping[str, FloorFormat]:
    asset = "field/location_formats.json"
    plans: dict[str, FloorFormat] = {}
    for target, negative_name, positive_name, floorless_name, with_location in (
        (
            MAZE_TARGET,
            "map_3d_basement_floor",
            "map_3d_above_ground_floor",
            None,
            False,
        ),
        (
            AUTOMAP_TARGET,
            "automap_basement",
            "automap_above_ground",
            "automap_floorless",
            True,
        ),
    ):
        negative = _floor_pattern(
            _surface_text(asset, negative_name), with_location=with_location
        )
        positive = _floor_pattern(
            _surface_text(asset, positive_name), with_location=with_location
        )
        if (
            len(negative[0]) != 1
            or positive[0]
            or len(negative[1]) != 1
            or positive[1] != negative[1]
        ):
            raise ValueError(
                f"{target}: floor renderer needs one negative prefix and one suffix"
            )
        if floorless_name is not None and _surface_text(asset, floorless_name) != "{location}":
            raise ValueError("AUTOMAP floorless format must contain only {location}")
        plans[target] = FloorFormat(negative[0], negative[1])
    return MappingProxyType(plans)


def _elevator_format(metrics: Font16Metrics) -> ElevatorFormat:
    asset = "field/elevator.json"
    lower = _surface_text(asset, "lower_symbol")
    floor = _surface_text(asset, "floor_symbol")
    for name, value in (("lower_symbol", lower), ("floor_symbol", floor)):
        if len(value) != 1 or value not in metrics.codes:
            raise ValueError(
                f"elevator {name} must encode as exactly one FONT16 glyph"
            )

    definition = _surface_text(asset, "floor_definition")
    tokens = parse_tokens(definition)
    names = tuple(token.name for token in tokens if isinstance(token, Named))
    expected = ("lower_symbol", "floor_number", "floor_symbol")
    if len(tokens) != 3 or set(names) != set(expected) or len(names) != 3:
        raise ValueError(
            "elevator floor_definition must contain lower_symbol, floor_number, "
            "and floor_symbol exactly once, without literal text"
        )
    part_codes = {
        "lower_symbol": 1,
        "floor_number": 2,
        "floor_symbol": 3,
    }
    parts = tuple(part_codes[name] for name in names)
    return ElevatorFormat(lower, floor, (parts[0], parts[1], parts[2]))


def _location_text() -> tuple[tuple[str, ...], Mapping[str, str]]:
    physical = load_physical_record_files((LOCATION_CORPUS_PATH, SAVE_CORPUS_PATH))
    translations = load_bound_translations(
        ("game.dungeon_locations.",),
        required_ids=frozenset(LOCATION_IDS),
        binding_paths=(LOCATION_BINDING_PATH,),
        physical_records=physical,
    )
    rows = tuple(translations[physical_id] for physical_id in LOCATION_IDS)

    binding = load_binding(LOCATION_BINDING_PATH, physical_records=physical)
    catalog = load_asset(binding.asset)
    aliases: dict[str, str] = {}
    for physical_id in LOCATION_IDS:
        primary = rows[int(physical_id.rsplit("r", 1)[1])]
        for use in binding.additional_uses.get(physical_id, ()):
            if not use.asset_ref.endswith(".automap_name"):
                continue
            alias = catalog.field(use.asset_ref).resolve(use.variant)[1]
            if not alias:
                raise ValueError(f"AUTOMAP alias {use.asset_ref} is untranslated")
            previous = aliases.setdefault(primary, alias)
            if previous != alias:
                raise ValueError(f"AUTOMAP aliases disagree for {primary!r}")
    displayed = [aliases.get(value, value) for value in dict.fromkeys(rows)]
    if len(displayed) != len(set(displayed)):
        raise ValueError("AUTOMAP display names must remain unique")
    return rows, MappingProxyType(aliases)


def _marker_text() -> Mapping[str, str]:
    physical = load_physical_record_files(
        (
            AUTOMAP_MARKER_CORPUS_PATH,
            AUTOMAP_SYSTEM_CORPUS_PATH,
        )
    )
    translations = load_bound_translations(
        ("game.automap_marker_ui.", "game.automap_system."),
        required_ids=frozenset(MARKER_IDS.values()),
        binding_paths=(AUTOMAP_BINDING_PATH, AUTOMAP_CHOICES_BINDING_PATH),
        physical_records=physical,
    )
    return MappingProxyType(
        {name: translations[physical_id] for name, physical_id in MARKER_IDS.items()}
    )


def _validate_surfaces() -> None:
    surfaces = load_surfaces()
    expected = {
        "map_3d.location": (
            ("font16", 1, "glyph_cells", 4),
            ("font16", 2, "pixels", 64),
        ),
        "automap.entry": (
            ("font16", 1, "glyph_cells", 7),
            ("font16", 1, "pixels", 112),
        ),
        "automap.marker_popup": (
            ("font16", 3, "glyph_cells", 6),
            ("font16", 3, "pixels", 64),
        ),
        "field.elevator_floor": (
            ("font16", 1, "glyph_cells", 4),
            ("font16", 1, "pixels", 64),
        ),
    }
    for name, (ja_expected, en_expected) in expected.items():
        surface = surfaces.surface(name)
        for layout, wanted in ((surface.ja, ja_expected), (surface.en, en_expected)):
            actual = (layout.font, layout.rows, layout.width.unit, layout.width.value)
            if actual != wanted:
                raise ValueError(f"{name} geometry changed")


def _text_width(text: str, metrics: Font16Metrics) -> int:
    width = 0
    for character in text:
        try:
            code = metrics.codes[character]
        except KeyError as error:
            raise ValueError(
                f"unsupported dungeon-location character {character!r}"
            ) from error
        advance = metrics.widths[code]
        if not advance:
            raise ValueError(f"dungeon-location glyph {code} has no width")
        width += advance
    return width


def _location_lines(
    text: str,
    floor_width: int,
    metrics: Font16Metrics,
) -> tuple[str, str]:
    lines = text.replace("\r\n", "\n").replace("{n}", "\n").split("\n")
    if len(lines) > 2:
        raise ValueError(f"location label has more than two lines: {text!r}")
    if len(lines) == 2:
        return lines[0], lines[1]
    if _text_width(text, metrics) <= 64:
        return text, ""
    words = text.split()
    if len(words) < 2:
        return text, ""
    lower_limit = 64 - floor_width - (LABEL_GAP if floor_width else 0)
    candidates: list[tuple[float, int, str, str]] = []
    for split in range(1, len(words)):
        upper = " ".join(words[:split])
        lower = " ".join(words[split:])
        upper_width = _text_width(upper, metrics)
        lower_width = _text_width(lower, metrics)
        pressure = max(upper_width / 64, lower_width / max(1, lower_limit))
        candidates.append((pressure, abs(upper_width - lower_width), upper, lower))
    _pressure, _balance, upper, lower = min(candidates)
    return upper, lower


def _table_offset(spec: RuntimeSpec) -> int:
    return spec.table_address - LOAD_ADDRESS


def _label_catalog(
    source: bytes,
    spec: RuntimeSpec,
    texts: tuple[str, ...],
    aliases: Mapping[str, str],
    floor_format: FloorFormat,
    metrics: Font16Metrics,
) -> tuple[tuple[str, str, int], ...]:
    labels: list[tuple[str, str, int]] = []
    table = _table_offset(spec)
    for index, text in enumerate(texts):
        floor = floor_format.text(source[table + index * RECORD_SIZE])
        floor_width = _text_width(floor, metrics) if floor else 0
        label = (
            (aliases.get(text, text), "", floor_width)
            if spec.automap
            else (*_location_lines(text, floor_width, metrics), floor_width)
        )
        if label not in labels:
            labels.append(label)
    if len(labels) > 0x100:
        raise ValueError("dungeon-location selector supports at most 256 labels")
    return tuple(labels)


def _render_codes(
    font16: bytes,
    codes: tuple[int, ...],
    metrics: Font16Metrics,
    *,
    limit: int = 64,
    cells: int = 4,
) -> bytes:
    pixel_width = cells * 16
    if not 1 <= cells <= 8 or not 1 <= limit <= pixel_width:
        raise ValueError(f"invalid dungeon-location render limit {limit}")
    if any(code >= len(metrics.widths) or not metrics.widths[code] for code in codes):
        raise ValueError("dungeon-location text uses an invalid glyph")
    width = sum(metrics.widths[code] for code in codes)
    rows = [0] * 16
    x = 0
    for code in codes:
        cell = font16[code * 32 : (code + 1) * 32]
        if len(cell) != 32:
            raise ValueError(f"FONT16 glyph {code} exceeds the generated font")
        for row in range(16):
            glyph_row = struct.unpack_from(">H", cell, row * 2)[0]
            for column in range(16):
                if not glyph_row & (0x8000 >> column):
                    continue
                natural_x = x + column
                screen_x = natural_x * limit // width if width > limit else natural_x
                if screen_x < pixel_width:
                    rows[row] |= 1 << (pixel_width - 1 - screen_x)
        x += metrics.widths[code]
    output = bytearray()
    for cell_index in range(cells):
        shift = (cells - 1 - cell_index) * 16
        for row in rows:
            output.extend(struct.pack(">H", row >> shift & 0xFFFF))
    return bytes(output)


def _render_text(
    font16: bytes,
    text: str,
    metrics: Font16Metrics,
    *,
    limit: int = 64,
    cells: int = 4,
) -> bytes:
    try:
        codes = tuple(metrics.codes[character] for character in text)
    except KeyError as error:
        raise ValueError(
            f"unsupported dungeon-location character {error.args[0]!r}"
        ) from error
    return _render_codes(font16, codes, metrics, limit=limit, cells=cells)


def _automap_geometry(
    name: str,
    floor_width: int,
    metrics: Font16Metrics,
) -> tuple[int, int]:
    name_width = _text_width(name, metrics)
    append_offset = (
        max(0, name_width - 64) + LABEL_GAP
        if floor_width and name_width >= 64
        else 0
    )
    right_edge = max(name_width, 64 + append_offset + floor_width)
    if right_edge > AUTOMAP_MARKER_PIXEL_LIMIT:
        raise ValueError(
            f"AUTOMAP label {name!r} reaches {right_edge}px; "
            f"limit is {AUTOMAP_MARKER_PIXEL_LIMIT}px"
        )
    return append_offset, right_edge


def _label_data(
    font16: bytes,
    labels: tuple[tuple[str, str, int], ...],
    metrics: Font16Metrics,
    *,
    automap: bool,
) -> tuple[bytes, bytes]:
    bitmaps = bytearray()
    offsets = bytearray()
    for upper, lower, floor_width in labels:
        if automap:
            if lower:
                raise ValueError("AUTOMAP labels must have one authored name row")
            append_offset, _right_edge = _automap_geometry(
                upper, floor_width, metrics
            )
            offsets.append(append_offset)
            bitmaps.extend(
                _render_text(font16, upper, metrics, limit=128, cells=8)
            )
            continue
        lower_limit = 64 - floor_width - (LABEL_GAP if lower and floor_width else 0)
        if lower and lower_limit < 1:
            raise ValueError(f"no room for dungeon-location row {lower!r}")
        lower_width = min(_text_width(lower, metrics), max(1, lower_limit)) if lower else 0
        append_offset = lower_width + (LABEL_GAP if lower and floor_width else 0)
        if append_offset + floor_width > 64:
            raise ValueError(f"dungeon floor does not fit after {lower!r}")
        offsets.append(append_offset)
        bitmaps.extend(_render_text(font16, upper, metrics))
        bitmaps.extend(
            _render_text(font16, lower, metrics, limit=max(1, lower_limit))
        )
    return bytes(bitmaps), bytes(offsets)


def _marker_strips(
    font16: bytes,
    text: Mapping[str, str],
    metrics: Font16Metrics,
) -> tuple[MarkerStrip, ...]:
    strips: list[MarkerStrip] = []
    if tuple(text) != MARKER_ORDER:
        raise ValueError("AUTOMAP marker text order changed")
    for name, value in text.items():
        width = _text_width(value, metrics)
        cells = max(1, (width + 15) // 16)
        limit = (
            AUTOMAP_MARKER_PIXEL_LIMIT
            if name == "marker_no_data"
            else MARKER_POPUP_PIXEL_LIMIT
        )
        if width > limit or cells > (limit + 15) // 16:
            raise ValueError(
                f"AUTOMAP marker {name!r} is {width}px/{cells} cells; "
                f"maximum is {limit}px/{(limit + 15) // 16} cells"
            )
        storage_cells = max(MARKER_BITMAP_FLOOR_CELLS, cells)
        strips.append(
            MarkerStrip(
                name,
                _render_text(
                    font16,
                    value,
                    metrics,
                    limit=storage_cells * 16,
                    cells=storage_cells,
                ),
                cells,
                width,
            )
        )
    return tuple(strips)


def _patched_table(
    source: bytes,
    spec: RuntimeSpec,
    texts: tuple[str, ...],
    aliases: Mapping[str, str],
    floor_format: FloorFormat,
    metrics: Font16Metrics,
    labels: tuple[tuple[str, str, int], ...],
) -> bytes:
    start = _table_offset(spec)
    table = bytearray(source[start : start + RECORD_COUNT * RECORD_SIZE])
    for index, text in enumerate(texts):
        offset = index * RECORD_SIZE
        if table[offset + 1] != 0 or not any(table[offset + 2 : offset + TEXT_BYTES]):
            raise ValueError(f"{spec.target}: invalid location record {index}")
        floor = floor_format.text(table[offset])
        floor_width = _text_width(floor, metrics) if floor else 0
        label = (
            (aliases.get(text, text), "", floor_width)
            if spec.automap
            else (*_location_lines(text, floor_width, metrics), floor_width)
        )
        struct.pack_into(
            ">5H",
            table,
            offset + 2,
            LABEL_SENTINEL + labels.index(label),
            0,
            0,
            0,
            0,
        )
    return bytes(table)


def _assembled(
    sources: tuple[Path, ...],
    address: int,
    symbols: Mapping[str, int],
) -> tuple[bytes, Mapping[str, int]]:
    try:
        source = "\n".join(path.read_text(encoding="utf-8") for path in sources)
        result = assemble(source, address, dict(symbols))
    except (AssemblyError, FileNotFoundError) as error:
        names = ", ".join(path.relative_to(ENGINE_ROOT).as_posix() for path in sources)
        raise ValueError(f"dungeon-location assembly {names}: {error}") from error
    if result.warnings:
        raise ValueError(f"dungeon-location assembly warnings: {result.warnings}")
    return result.data, MappingProxyType(result.labels)


def _runtime_sources(
    config: PatchRecipeConfiguration,
    target: str,
) -> tuple[Path, ...]:
    recipe = next(
        recipe for recipe in config.patches[target] if recipe.name == "renderer_cave"
    )
    expected = (
        (
            ENGINE_ROOT / "asm" / "dungeon_locations" / "automap_wrapper.s",
            ENGINE_ROOT / "asm" / "dungeon_locations" / "marker_ui.s",
            ENGINE_ROOT / "asm" / "dungeon_locations" / "floor_compositor.s",
        )
        if target == AUTOMAP_TARGET
        else (
            ENGINE_ROOT / "asm" / "dungeon_locations" / "maze_wrapper.s",
            ENGINE_ROOT / "asm" / "dungeon_locations" / "floor_compositor.s",
            ENGINE_ROOT / "asm" / "dungeon_locations" / "elevator_surface.s",
        )
    )
    if recipe.replacement.sources != expected:
        raise ValueError(f"{target}: dungeon-location assembly inventory changed")
    return recipe.replacement.sources


def _build_cave(
    config: PatchRecipeConfiguration,
    spec: RuntimeSpec,
    font16: bytes,
    metrics: Font16Metrics,
    floor_format: FloorFormat,
    elevator_format: ElevatorFormat,
    labels: tuple[tuple[str, str, int], ...],
    marker_strips: tuple[MarkerStrip, ...],
    capacity: int,
) -> tuple[bytes, bytes, Mapping[str, int]]:
    if bool(marker_strips) != spec.automap:
        raise ValueError(f"{spec.target}: marker strips have the wrong owner")
    sources = _runtime_sources(config, spec.target)
    cave_address = next(
        recipe.address
        for recipe in config.patches[spec.target]
        if recipe.name == "renderer_cave"
    )
    symbols = {
        "TOP_CODE": TOP_CODE,
        "BOTTOM_CODE": BOTTOM_CODE,
        "TOP_ADDR": FONT16_BASE + TOP_CODE * 32,
        "BOTTOM_ADDR": FONT16_BASE + BOTTOM_CODE * 32,
        "FONT_BASE": FONT16_BASE,
        "CODE_0": metrics.codes["0"],
        "CODE_NEGATIVE_PREFIX": metrics.codes[floor_format.negative_prefix],
        "CODE_SUFFIX": metrics.codes[floor_format.suffix],
        "RETURN_ADDR": spec.return_address,
        "DRAW_NAME": spec.stock_name_drawer,
        "LABEL_BASE": LABEL_SENTINEL,
        "LABEL_COUNT": len(labels),
        "ELEVATOR_DRAW": 0x0603FCFC,
        "ELEVATOR_CODE_LOWER": metrics.codes[elevator_format.lower_symbol],
        "ELEVATOR_CODE_FLOOR": metrics.codes[elevator_format.floor_symbol],
        "ELEVATOR_PART_0": elevator_format.parts[0],
        "ELEVATOR_PART_1": elevator_format.parts[1],
        "ELEVATOR_PART_2": elevator_format.parts[2],
    }
    marker_by_name = {strip.name: strip for strip in marker_strips}
    if spec.automap and tuple(marker_by_name) != MARKER_ORDER:
        raise ValueError("AUTOMAP marker strip inventory changed")

    def marker_symbols(addresses: Mapping[str, int]) -> dict[str, int]:
        if not spec.automap:
            return {}
        yes_width = marker_by_name["marker_yes"].width
        no_width = marker_by_name["marker_no"].width
        return {
            "NO_DATA_POINTER": AUTOMAP_NO_DATA_POINTER,
            "YES_POINTER": AUTOMAP_YES_POINTER,
            "NO_POINTER": AUTOMAP_NO_POINTER,
            "ASCII_DRAWER": AUTOMAP_ASCII_DRAWER,
            "RAW_DRAWER": AUTOMAP_RAW_DRAWER,
            "DRAW_DESCRIPTOR": AUTOMAP_DRAW_DESCRIPTOR,
            "DELETE_SURFACE": AUTOMAP_DELETE_SURFACE,
            "NO_DATA_BITMAP": addresses["marker_no_data"],
            "DELETE_BITMAP": addresses["marker_delete"],
            "YES_BITMAP": addresses["marker_yes"],
            "NO_BITMAP": addresses["marker_no"],
            "NO_DATA_CELLS": marker_by_name["marker_no_data"].cells,
            "DELETE_CELLS": marker_by_name["marker_delete"].cells,
            "YES_CELLS": marker_by_name["marker_yes"].cells,
            "NO_CELLS": marker_by_name["marker_no"].cells,
            "NO_X_BIAS": max(0, yes_width - no_width),
        }

    bitmaps, append_offsets = _label_data(
        font16, labels, metrics, automap=spec.automap
    )
    marker_probe = {
        name: cave_address + 0x1000 + index * 0x100
        for index, name in enumerate(MARKER_ORDER)
    }
    probe, _probe_labels = _assembled(
        sources,
        cave_address,
        {
            **symbols,
            **marker_symbols(marker_probe),
            "WIDTHS": cave_address + 0x300,
            "APPEND_OFFSETS": cave_address + 0x600,
            "BITMAPS": cave_address + 0x800,
        },
    )
    widths_address = cave_address + len(probe)
    append_address = widths_address + len(metrics.widths)
    if append_address & 3:
        raise ValueError("dungeon-location append-offset table lost alignment")
    bitmap_address = (append_address + len(append_offsets) + 3) & ~3
    marker_start = (bitmap_address + len(bitmaps) + 3) & ~3
    marker_addresses: dict[str, int] = {}
    marker_cursor = marker_start
    for strip in marker_strips:
        marker_addresses[strip.name] = marker_cursor
        marker_cursor += len(strip.bitmap)
    code, labels_by_name = _assembled(
        sources,
        cave_address,
        {
            **symbols,
            **marker_symbols(marker_addresses),
            "WIDTHS": widths_address,
            "APPEND_OFFSETS": append_address,
            "BITMAPS": bitmap_address,
        },
    )
    entry_name = "automap_entry" if spec.automap else "maze_entry"
    if labels_by_name.get(entry_name) != cave_address:
        raise ValueError(f"{spec.target}: dungeon-location entry moved")
    payload = bytearray(code)
    payload.extend(metrics.widths)
    payload.extend(append_offsets)
    payload.extend(bytes((-len(payload)) % 4))
    if cave_address + len(payload) != bitmap_address:
        raise ValueError(f"{spec.target}: dungeon-location bitmap address drifted")
    payload.extend(bitmaps)
    payload.extend(bytes(marker_start - cave_address - len(payload)))
    for strip in marker_strips:
        if cave_address + len(payload) != marker_addresses[strip.name]:
            raise ValueError(f"{spec.target}: marker bitmap address drifted")
        payload.extend(strip.bitmap)
    if len(payload) > capacity:
        raise ValueError(
            f"{spec.target}: dungeon-location cave uses {len(payload)} of "
            f"{capacity} bytes"
        )
    used = bytes(payload)
    return used.ljust(capacity, b"\0"), used, labels_by_name


def _build_runtime(
    config: PatchRecipeConfiguration,
    spec: RuntimeSpec,
    source: bytes,
    font16: bytes,
    metrics: Font16Metrics,
    floor_format: FloorFormat,
    elevator_format: ElevatorFormat,
    texts: tuple[str, ...],
    aliases: Mapping[str, str],
    marker_text: Mapping[str, str],
) -> RuntimeImage:
    labels = _label_catalog(
        source, spec, texts, aliases, floor_format, metrics
    )
    marker_strips = (
        _marker_strips(font16, marker_text, metrics) if spec.automap else ()
    )
    cave_recipe = next(
        recipe for recipe in config.patches[spec.target] if recipe.name == "renderer_cave"
    )
    cave, used, code_labels = _build_cave(
        config,
        spec,
        font16,
        metrics,
        floor_format,
        elevator_format,
        labels,
        marker_strips,
        len(cave_recipe.expected),
    )
    table = _patched_table(
        source,
        spec,
        texts,
        aliases,
        floor_format,
        metrics,
        labels,
    )
    entry_name = "automap_entry" if spec.automap else "maze_entry"
    wrapper_name = "automap_name_wrapper" if spec.automap else "maze_name_wrapper"
    links = {
        "floor_entry": code_labels[entry_name],
        "name_wrapper": code_labels[wrapper_name],
    }
    if not spec.automap:
        links["elevator_entry"] = code_labels["elevator_entry"]
    if spec.automap:
        links.update(
            {
                "marker_ascii_vwf": code_labels["marker_ascii_vwf"],
                "marker_delete_vwf": code_labels["marker_delete_vwf"],
            }
        )
    return RuntimeImage(
        cave,
        used,
        table,
        MappingProxyType(links),
        labels,
    )


def _validate_table_mirror(sources: Mapping[str, bytes]) -> None:
    maze = sources[MAZE_TARGET]
    automap = sources[AUTOMAP_TARGET]
    for index in range(RECORD_COUNT):
        maze_start = _table_offset(SPECS[MAZE_TARGET]) + index * RECORD_SIZE
        auto_start = _table_offset(SPECS[AUTOMAP_TARGET]) + index * RECORD_SIZE
        if maze[maze_start : maze_start + TEXT_BYTES] != automap[
            auto_start : auto_start + TEXT_BYTES
        ]:
            raise ValueError(
                f"AUTOMAPC.BIN location record {index} differs from MAZE.BIN"
            )


def _mirror_id(target: str, recipe: PatchRecipe) -> str:
    try:
        index = int(recipe.name.rsplit("_", 1)[1])
    except (IndexError, ValueError) as error:
        raise ValueError(f"{target}/{recipe.name}: invalid mirror selector name") from error
    stem = PurePosixPath(target).stem.lower()
    return f"game.dungeon_location_mirrors.{stem}.r{index:04d}"


def _mirror_text(
    config: PatchRecipeConfiguration,
) -> Mapping[str, str]:
    required = frozenset(
        _mirror_id(target, recipe)
        for target, recipes in config.patches.items()
        if target not in PRIMARY_TARGETS
        for recipe in recipes
    )
    physical = load_physical_record_files((MIRROR_CORPUS_PATH,))
    return load_bound_translations(
        ("game.dungeon_location_mirrors.",),
        required_ids=required,
        binding_paths=(MIRROR_BINDING_PATH,),
        physical_records=physical,
    )


def _canonical_selectors(
    source: bytes,
    patched: bytes,
    texts: tuple[str, ...],
) -> tuple[
    Mapping[bytes, bytes],
    Mapping[tuple[int, bytes], bytes],
    Mapping[tuple[int, str], bytes],
]:
    table = _table_offset(SPECS[MAZE_TARGET])
    prefixes: dict[bytes, bytes] = {}
    names: dict[tuple[int, bytes], bytes] = {}
    selectors: dict[tuple[int, str], bytes] = {}
    for index in range(RECORD_COUNT):
        source_offset = table + index * RECORD_SIZE
        replacement_offset = index * RECORD_SIZE
        source_prefix = source[source_offset : source_offset + TEXT_BYTES]
        replacement_prefix = patched[
            replacement_offset : replacement_offset + TEXT_BYTES
        ]
        previous = prefixes.setdefault(source_prefix, replacement_prefix)
        if previous != replacement_prefix:
            raise ValueError("duplicate dungeon source records select different labels")
        key = (source_prefix[0], source_prefix[2:])
        previous_name = names.setdefault(key, replacement_prefix[2:])
        if previous_name != replacement_prefix[2:]:
            raise ValueError("duplicate dungeon floor/name records select different labels")
        selector_key = (source_prefix[0], texts[index])
        previous_selector = selectors.setdefault(selector_key, replacement_prefix[2:])
        if previous_selector != replacement_prefix[2:]:
            raise ValueError("duplicate authored dungeon names select different labels")
    return (
        MappingProxyType(prefixes),
        MappingProxyType(names),
        MappingProxyType(selectors),
    )


def _only_source(recipe: PatchRecipe, relative: str) -> Path:
    expected = ENGINE_ROOT / "asm" / Path(relative)
    if recipe.replacement.sources != (expected,):
        raise ValueError(f"{recipe.group}/{recipe.name}: assembly source changed")
    return expected


def _floor_hook(
    recipe: PatchRecipe,
    recipes: tuple[PatchRecipe, ...],
) -> bytes:
    source = _only_source(recipe, "dungeon_locations/floor_hook.s")
    pointer_site = next(
        row.address for row in recipes if row.name == "floor_hook_target"
    )
    result, labels = _assembled(
        (source,), recipe.address, {"HOOK_TARGET_POINTER": pointer_site}
    )
    if labels or len(result) != 6:
        raise ValueError(f"{recipe.group}/{recipe.name}: invalid floor hook")
    return result


def _mirror_replacement(
    target: str,
    recipe: PatchRecipe,
    source: bytes,
    selectors: Mapping[tuple[int, str], bytes],
    mirror_text: Mapping[str, str],
) -> bytes:
    physical_id = _mirror_id(target, recipe)
    try:
        text = mirror_text[physical_id]
    except KeyError as error:
        raise ValueError(f"{target}/{recipe.name}: has no authored mirror owner") from error
    if recipe.group == "dungeon_location_landing_mirrors":
        if len(recipe.expected) != TEXT_BYTES:
            raise ValueError(f"{target}/{recipe.name}: invalid landing selector")
        try:
            return recipe.expected[:2] + selectors[(recipe.expected[0], text)]
        except KeyError as error:
            raise ValueError(f"{target}/{recipe.name}: unknown landing location") from error
    if recipe.group == "dungeon_location_kai_mirrors":
        if len(recipe.expected) != 10 or recipe.address < 1:
            raise ValueError(f"{target}/{recipe.name}: invalid KAI selector")
        key = (source[recipe.address - 1], text)
        try:
            return selectors[key]
        except KeyError as error:
            raise ValueError(f"{target}/{recipe.name}: unknown KAI location") from error
    raise ValueError(f"{target}/{recipe.name}: not a dungeon-location mirror")


def _validate_mirror_selectors(
    config: PatchRecipeConfiguration,
    sources: Mapping[str, bytes],
    prefixes: Mapping[bytes, bytes],
    names: Mapping[tuple[int, bytes], bytes],
) -> None:
    for target, recipes in config.patches.items():
        if target in PRIMARY_TARGETS:
            continue
        source = sources[target]
        group = recipes[0].group
        if group == "dungeon_location_landing_mirrors":
            expected_addresses = tuple(0x5C + index * RECORD_SIZE for index in range(len(recipes)))
            discovered = tuple(
                offset
                for offset in range(len(source) - TEXT_BYTES + 1)
                if source[offset : offset + TEXT_BYTES] in prefixes
            )
        else:
            expected_addresses = tuple(0x12 + index * 0x28 for index in range(len(recipes)))
            source_names = {name for _floor, name in names}
            discovered_set: set[int] = set()
            for value in source_names:
                position = source.find(value)
                while position >= 0:
                    discovered_set.add(position)
                    position = source.find(value, position + 1)
            discovered = tuple(sorted(discovered_set))
        configured = tuple(recipe.address for recipe in recipes)
        if configured != expected_addresses or discovered != configured:
            raise ValueError(f"{target}: configured dungeon-location selectors drifted")


def _bind_target(
    config: PatchRecipeConfiguration,
    target: str,
    source: bytes,
    runtime: RuntimeImage | None,
    selectors: Mapping[tuple[int, str], bytes],
    mirror_text: Mapping[str, str],
) -> tuple[Patch, ...]:
    contract = config.targets[target]
    recipes = config.patches[target]
    expected = {
        recipe.name: resolve_recipe_expected(
            recipe, source, contract.load_address
        )
        for recipe in recipes
    }
    patches: list[Patch] = []
    for recipe in recipes:
        replacement_recipe = recipe.replacement
        if replacement_recipe.kind == "assembly":
            if runtime is None:
                raise ValueError(f"{target}/{recipe.name}: mirror owns assembly")
            replacement = (
                runtime.cave
                if recipe.name == "renderer_cave"
                else _floor_hook(recipe, recipes)
                if recipe.name == "floor_hook"
                else b""
            )
            if not replacement:
                raise ValueError(f"{target}/{recipe.name}: unknown assembly owner")
        elif replacement_recipe.kind == "linked_pointer":
            if runtime is None or replacement_recipe.link not in runtime.links:
                raise ValueError(f"{target}/{recipe.name}: unresolved runtime link")
            replacement = struct.pack(">I", runtime.links[replacement_recipe.link])
        elif replacement_recipe.kind == "generated":
            if replacement_recipe.generator != "dungeon_locations":
                raise ValueError(f"{target}/{recipe.name}: unknown location generator")
            replacement = (
                runtime.table
                if runtime is not None and recipe.name == "location_table"
                else _mirror_replacement(
                    target, recipe, source, selectors, mirror_text
                )
            )
        else:
            raise ValueError(f"{target}/{recipe.name}: unsupported replacement recipe")
        if len(replacement) != len(expected[recipe.name]):
            raise ValueError(
                f"{target}/{recipe.name}: generated {len(replacement)} bytes, "
                f"expected {len(expected[recipe.name])}"
            )
        patches.append(
            Patch(
                recipe.group,
                recipe.name,
                recipe.address,
                expected[recipe.name],
                replacement,
            )
        )
    return tuple(patches)


def build_dungeon_locations(
    sources: Mapping[str, bytes] | None = None,
) -> DungeonLocationsBuild:
    """Build every stock-backed dungeon-location physical consumer."""
    _validate_surfaces()
    config = _configuration()
    source_data = _source_files(config) if sources is None else sources
    _validate_sources(config, source_data)
    _validate_table_mirror(source_data)

    try:
        font16 = FONT16_PATH.read_bytes()
    except FileNotFoundError as error:
        raise ValueError(f"missing dungeon-location FONT16: {FONT16_PATH}") from error
    if len(font16) != FONT16_CELLS * 32:
        raise ValueError("dungeon-location FONT16 geometry changed")
    metrics = _font16_metrics()
    floor_formats = _floor_formats()
    elevator_format = _elevator_format(metrics)
    texts, aliases = _location_text()
    marker_text = _marker_text()
    mirror_text = _mirror_text(config)

    runtimes = {
        target: _build_runtime(
            config,
            spec,
            source_data[target],
            font16,
            metrics,
            floor_formats[target],
            elevator_format,
            texts,
            aliases if spec.automap else MappingProxyType({}),
            marker_text,
        )
        for target, spec in SPECS.items()
    }
    prefixes, names, selectors = _canonical_selectors(
        source_data[MAZE_TARGET], runtimes[MAZE_TARGET].table, texts
    )
    _validate_mirror_selectors(config, source_data, prefixes, names)

    outputs: dict[str, bytes] = {}
    patches: dict[str, tuple[Patch, ...]] = {}
    for target in config.targets:
        target_patches = _bind_target(
            config,
            target,
            source_data[target],
            runtimes.get(target),
            selectors,
            mirror_text,
        )
        patches[target] = target_patches
        outputs[target] = apply_patches(
            source_data[target], config.targets[target].load_address, target_patches
        )

    assembly_files = tuple(
        sorted(
            {
                source
                for recipes in config.patches.values()
                for recipe in recipes
                for source in recipe.replacement.sources
            },
            key=lambda path: path.as_posix(),
        )
    )
    return DungeonLocationsBuild(
        MappingProxyType(outputs),
        MappingProxyType(patches),
        MappingProxyType(
            {target: runtime.used_cave for target, runtime in runtimes.items()}
        ),
        MappingProxyType({target: runtime.labels for target, runtime in runtimes.items()}),
        ASSET_FILES,
        assembly_files,
        RUNTIME_INPUT_FILES,
        MappingProxyType(
            {f"game:{target}": _sha256(source_data[target]) for target in config.targets}
        ),
    )
