"""Compose DA_3D's Analyze grid and detailed demon panel."""

from __future__ import annotations

import hashlib
import json
import re
import struct
from collections import Counter
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
from engine.shared.demon_sort import dense_rank_table
from engine.shared.font8 import font8_tables
from engine.shared.status_layout import (
    StatusTemplates,
    derived_rows,
    direct_color_node,
    direct_color_row,
    load_font16_metrics,
    load_status_labels,
    load_status_templates,
    load_stock_latin_codes,
    node_background,
    validate_shiftable_bitmap,
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
CONFIG_PATH = ENGINE_ROOT / "config" / "analyze_ui.json"
FONT_ROOT = SATURN_ROOT / "font" / "generated" / "game"
FONT8_PATH = FONT_ROOT / "FONT8.FON"
FONT8_METRICS_PATH = FONT_ROOT / "FONT8_metrics.json"
FONT16_PATH = FONT_ROOT / "FONT16.FON"
FONT16_METRICS_PATH = FONT_ROOT / "FONT16_metrics.json"
TEXT_GENERATED_ROOT = SATURN_ROOT / "text" / "generated" / "game"
DVLNAME_PATH = TEXT_GENERATED_ROOT / "DVLNAME.DAT"
MAGNAME_PATH = TEXT_GENERATED_ROOT / "MAGNAME.DAT"
COMP_MENU_BUILD_PATH = TEXT_GENERATED_ROOT / "comp_menu_build.json"
BATTLE_UI_BUILD_PATH = TEXT_GENERATED_ROOT / "battle_ui_build.json"

STATUS_ASSET_PATH = ASSET_ROOT / "ui" / "status.json"
ANALYZE_ASSET_PATH = ASSET_ROOT / "ui" / "map_3d_analyze.json"
RACE_ASSET_PATH = ASSET_ROOT / "races.json"
AFFINITY_ASSET_PATH = ASSET_ROOT / "affinities.json"
DEMON_ASSET_PATH = ASSET_ROOT / "demons.json"
ALIGNMENT_ASSET_PATH = ASSET_ROOT / "terminology" / "alignments.json"
MAGIC_ASSET_PATH = ASSET_ROOT / "magic.json"
SKILL_ASSET_PATH = ASSET_ROOT / "skills.json"
ASSET_FILES = (
    STATUS_ASSET_PATH,
    ANALYZE_ASSET_PATH,
    RACE_ASSET_PATH,
    AFFINITY_ASSET_PATH,
    DEMON_ASSET_PATH,
    ALIGNMENT_ASSET_PATH,
    MAGIC_ASSET_PATH,
    SKILL_ASSET_PATH,
)

BINDING_FILES = tuple(
    BINDING_ROOT / name
    for name in (
        "map_3d_analyze.json",
        "map_3d_analyze_status.json",
        "races.json",
        "affinities.json",
        "demons.json",
        "alignments.json",
        "magic.json",
        "skills.json",
    )
)
CORPUS_FILES = tuple(
    CORPUS_ROOT / relative
    for relative in (
        "compendium/addressed/race_names.json",
        "compendium/fixed/demon_names.json",
        "compendium/fixed/ability_names.json",
        "game/addressed/da3d_analyze.json",
        "game/addressed/normcom_tables.json",
        "game/addressed/combat_analysis_affinities.json",
        "game/addressed/normcom_status_ascii.json",
        "game/fixed/dvlname.json",
        "game/fixed/magname.json",
        "game/pointer/btl_mes.json",
        "game/eve/shopsmp.json",
    )
)
RUNTIME_INPUT_FILES = (
    FONT8_PATH,
    FONT8_METRICS_PATH,
    FONT16_PATH,
    FONT16_METRICS_PATH,
    DVLNAME_PATH,
    MAGNAME_PATH,
    COMP_MENU_BUILD_PATH,
    BATTLE_UI_BUILD_PATH,
    SATURN_ROOT / "text" / "config" / "surfaces.json",
    SATURN_ROOT / "text" / "config" / "glyph_sets.json",
    SATURN_ROOT / "rom" / "discs.json",
    *BINDING_FILES,
    *CORPUS_FILES,
)

TARGET = "DA_3D.BIN"
OUTPUT = TARGET
LOAD_ADDRESS = 0x06020000
TARGET_SIZE = 283_536
RUNTIME_CAVE = 0x06064386
RUNTIME_LIMIT = 0x06065148
RUNTIME_CAPACITY = RUNTIME_LIMIT - RUNTIME_CAVE
TABLE_CAVE = 0x0606517C
TABLE_LIMIT = 0x0606527E
TABLE_CAPACITY = TABLE_LIMIT - TABLE_CAVE

FONT8_BITMAP = 0x00219150
FONT16_BITMAP = 0x0021A000
DETAIL_FONT16_DRAWER = 0x0602B50C
DETAIL_FONT8_DRAWER = 0x0602B578
DETAIL_FONT8_GLYPH_DRAWER = 0x0602B0C8
TABLE_FONT8_DRAWER = 0x0602E934
TABLE_FONT8_GLYPH_DRAWER = 0x0602E7EC
CURRENT_NAME_PTR = 0x060655DC
DETAIL_RACE_SOURCE = RUNTIME_CAVE
AFFINITY_SELECTOR = 0x06066600
DVL_SOURCE = 0x0023F5D0
MAGNAME_BASE = 0x0022F7A0
MAGNAME_FIRST = MAGNAME_BASE + 4
MAGNAME_END = 0x00235740
MAGNAME_POINTER_FROM_NAME = 0x5A
MAGNAME_POINTER_OFFSET = 0x5E

RACE_COUNT = 43
AFFINITY_COUNT = 66
DEMON_COUNT = 319
SORT_DEMON_COUNT = 255
MAGNAME_COUNT = 255
MAGNAME_RECORD_SIZE = 0x60
NODE_BITMAP_OFFSET = 0x12000
NODE_BITMAP_SIZE = 16 * 16 * 2
AFFINITY_LINE_BYTES = 35
AFFINITY_MAX_ADVANCE = 127
AFFINITY_ADVANCE_OVERRIDES = {" ": 1, ",": 2, ":": 2}

DETAIL_IDS = MappingProxyType(
    {
        "level": "game.da3d_analyze.o00d284",
        "hit_points": "game.da3d_analyze.o00d288",
        "magic_points": "game.da3d_analyze.o00d28c",
        "summon_cost": "game.da3d_analyze.o00d290",
    }
)
HEADER_IDS = MappingProxyType(
    {
        "race_heading": "game.da3d_analyze.o00f7dc",
        "name_heading": "game.da3d_analyze.o00f7e4",
        "level": "game.da3d_analyze.o00f7ec",
        "hit_points": "game.da3d_analyze.o00f7f0",
        "magic_points": "game.da3d_analyze.o00f7f4",
        "attack_heading": "game.da3d_analyze.o00f7f8",
        "defense_heading": "game.da3d_analyze.o00f7fc",
    }
)
COST_IDS = MappingProxyType(
    {
        "magic_cost": "game.da3d_analyze.o00e590",
        "health_cost": "game.da3d_analyze.o00e594",
    }
)
AXIS_IDS = MappingProxyType(
    {
        "law": "game.da3d_analyze.o00d4c8",
        "chaos": "game.da3d_analyze.o00d4cc",
        "dark": "game.da3d_analyze.o00d4d0",
        "neutral": "game.da3d_analyze.o00d4d4",
    }
)


@dataclass(frozen=True, slots=True)
class AnalyzeTerms:
    templates: StatusTemplates
    race_heading: str
    name_heading: str
    attack_heading: str
    defense_heading: str
    magic_cost_suffix: str
    health_cost_suffix: str
    axes: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class RuntimeBuild:
    data: bytes
    table_data: bytes
    links: Mapping[str, int]
    used_size: int
    capacity: int
    table_used_size: int
    table_capacity: int


@dataclass(frozen=True, slots=True)
class AnalyzeUiBuild:
    data: bytes
    patches: tuple[Patch, ...]
    asset_files: tuple[Path, ...]
    runtime_input_files: tuple[Path, ...]
    source_inputs: Mapping[str, str]
    assembly_files: tuple[Path, ...]
    runtime_used_size: int
    runtime_capacity: int
    table_runtime_used_size: int
    table_runtime_capacity: int


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        return _sha256(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"missing Analyze UI input: {path}") from error


def _source_assets() -> tuple[bytes, bytes]:
    catalog = load_catalog()
    try:
        game = catalog["game"]
    except KeyError as error:
        raise ValueError("disc catalog has no game source") from error
    source = read_source_files(
        validate_source(game, verify_hashes=False), (TARGET, "FONT16.FON")
    )
    return source[TARGET], source["FONT16.FON"]


def _configuration() -> PatchRecipeConfiguration:
    return load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="map_3d.analyze",
        target_names={TARGET},
        input_names={
            "font8_sha256",
            "font8_metrics_sha256",
            "font16_sha256",
            "font16_metrics_sha256",
            "stock_font16_sha256",
        },
    )


def _manifest(path: Path, surface: str) -> Mapping[str, object]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid generated {surface} manifest: {path}") from error
    if not isinstance(document, dict):
        raise ValueError(f"generated {surface} manifest must be an object")
    if document.get("version") != 1 or document.get("surface") != surface:
        raise ValueError(f"Analyze UI needs the version-1 {surface} text build")
    return document


def _generated_output(
    manifest: Mapping[str, object], path: Path, records: int
) -> bytes:
    for name, metric_path in (
        ("font8_metrics_sha256", FONT8_METRICS_PATH),
        ("font16_metrics_sha256", FONT16_METRICS_PATH),
    ):
        if manifest.get(name) != _file_sha256(metric_path):
            raise ValueError(f"{path.name} manifest {name} is stale")
    outputs = manifest.get("outputs")
    record = outputs.get(path.name) if isinstance(outputs, dict) else None
    if not isinstance(record, dict) or record.get("records") != records:
        raise ValueError(f"generated manifest has no valid {path.name} record")
    data = path.read_bytes()
    if record.get("sha256") != _sha256(data):
        raise ValueError(f"generated {path.name} manifest SHA-256 is stale")
    return data


def _validate_inputs(
    config: PatchRecipeConfiguration, base: bytes, stock_font16: bytes
) -> tuple[bytes, bytes]:
    target = config.targets[TARGET]
    if (
        target.load_address != LOAD_ADDRESS
        or target.size != TARGET_SIZE
        or len(base) != TARGET_SIZE
        or _sha256(base) != target.stock_sha256
    ):
        raise ValueError("Analyze UI requires the configured stock DA_3D.BIN")
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
                f"Analyze UI {name} expected SHA-256 {expected}, found {actual[name]}"
            )
    comp = _manifest(COMP_MENU_BUILD_PATH, "comp.menu")
    battle = _manifest(BATTLE_UI_BUILD_PATH, "battle.ui")
    dvlname = _generated_output(comp, DVLNAME_PATH, DEMON_COUNT)
    magname = _generated_output(battle, MAGNAME_PATH, MAGNAME_COUNT)
    if len(dvlname) != DEMON_COUNT * 8:
        raise ValueError("generated DVLNAME has the wrong size")
    if len(magname) != MAGNAME_COUNT * MAGNAME_RECORD_SIZE:
        raise ValueError("generated MAGNAME has the wrong size")
    return dvlname, magname


def _physical_records() -> Mapping[str, str]:
    return load_physical_record_files(CORPUS_FILES)


def _bound(
    prefixes: tuple[str, ...],
    ids: set[str],
    bindings: tuple[Path, ...],
    physical: Mapping[str, str],
) -> Mapping[str, str]:
    return load_bound_translations(
        prefixes,
        required_ids=ids,
        binding_paths=bindings,
        physical_records=physical,
    )


def _validate_surfaces() -> None:
    surfaces = load_surfaces()
    expected = {
        "map_3d.analyze_grid.race_heading": ("font8", 1, "pixels", 52),
        "map_3d.analyze_grid.name_heading": ("font8", 1, "pixels", 76),
        "map_3d.analyze_grid.level_heading": ("font8", 1, "pixels", 46),
        "map_3d.analyze_grid.hit_points_heading": ("font8", 1, "pixels", 34),
        "map_3d.analyze_grid.magic_points_heading": ("font8", 1, "pixels", 28),
        "map_3d.analyze_grid.attack_heading": ("font8", 1, "pixels", 36),
        "map_3d.analyze_grid.defense_heading": ("font8", 1, "pixels", 52),
        "map_3d.analyze_race": ("font8", 1, "pixels", 52),
        "map_3d.analyze_demon_name": ("font8", 1, "pixels", 84),
        "map_3d.analyze_detail.numeric_readout": ("font8", 1, "pixels", 96),
        "map_3d.analyze_detail.skill_cost": ("font8", 1, "pixels", 16),
        "map_3d.analyze_detail.skill_list": ("font8", 6, "pixels", 96),
        "status.alignment_axis_label": ("font8", 1, "glyph_cells", 1),
        "status.demon_name": ("font16", 1, "pixels", 126),
        "status.demon_race": ("font16", 1, "pixels", 46),
        "status.skill_name": ("font8", 1, "pixels", 80),
        "status.affinity": ("font8", 2, "pixels", 128),
    }
    for name, geometry in expected.items():
        layout = surfaces.surface(name).en
        actual = (layout.font, layout.rows, layout.width.unit, layout.width.value)
        if actual != geometry:
            raise ValueError(f"{name} geometry changed: {actual!r}")
    glyph_sets = load_glyph_sets()
    fixed = (
        "map_3d.analyze_grid.race_heading",
        "map_3d.analyze_grid.name_heading",
        "map_3d.analyze_grid.level_heading",
        "map_3d.analyze_grid.hit_points_heading",
        "map_3d.analyze_grid.magic_points_heading",
        "map_3d.analyze_grid.attack_heading",
        "map_3d.analyze_grid.defense_heading",
        "map_3d.analyze_detail.numeric_readout",
        "map_3d.analyze_detail.skill_cost",
        "status.alignment_axis_label",
    )
    for name in fixed:
        handler = glyph_sets.for_surface(name)
        if (
            handler is None
            or handler.name != "font8_stock_latin"
            or handler.font != "font8"
            or handler.reference_set != "stock_latin"
        ):
            raise ValueError(f"{name} lost its preserved stock-Latin handler")


def _analyze_terms(physical: Mapping[str, str]) -> AnalyzeTerms:
    templates = load_status_templates()
    status = load_asset("ui/status.json")

    status_ids = set(DETAIL_IDS.values()) | {
        HEADER_IDS[name] for name in ("level", "hit_points", "magic_points")
    }
    status_values = _bound(
        ("game.da3d_analyze.",),
        status_ids,
        (BINDING_ROOT / "map_3d_analyze_status.json",),
        physical,
    )
    for name, physical_id in (*DETAIL_IDS.items(), *HEADER_IDS.items()):
        if physical_id not in status_ids:
            continue
        _reference, authored, _reviewed = status.field(f"{name}.text").resolve()
        if status_values[physical_id] != authored:
            raise ValueError(f"Analyze status binding disagrees for {physical_id}")

    direct_ids = set(COST_IDS.values()) | {
        HEADER_IDS[name]
        for name in (
            "race_heading",
            "name_heading",
            "attack_heading",
            "defense_heading",
        )
    }
    direct = _bound(
        ("game.da3d_analyze.",),
        direct_ids,
        (BINDING_ROOT / "map_3d_analyze.json",),
        physical,
    )

    def suffix(name: str) -> str:
        value = direct[COST_IDS[name]]
        match = re.fullmatch(r"\{cost\}([^{}])", value)
        if match is None:
            raise ValueError(f"Analyze {name} must use '{{cost}}S' with one suffix")
        return match.group(1)

    alignments = load_asset("terminology/alignments.json")
    axes: dict[str, str] = {}
    for name in ("law", "light", "chaos", "dark", "neutral"):
        _reference, value, _reviewed = alignments.field(
            f"{name}.axis_label"
        ).resolve()
        try:
            encoded = value.encode("ascii")
        except UnicodeEncodeError as error:
            raise ValueError(f"Analyze {name} axis must use one ASCII cell") from error
        if len(encoded) != 1:
            raise ValueError(f"Analyze {name} axis must use exactly one cell")
        axes[name] = value
    bound_axes = _bound(
        ("game.da3d_analyze.",),
        set(AXIS_IDS.values()),
        (BINDING_ROOT / "alignments.json",),
        physical,
    )
    for name, physical_id in AXIS_IDS.items():
        if bound_axes[physical_id] != axes[name]:
            raise ValueError(f"Analyze axis binding disagrees for {name}")

    return AnalyzeTerms(
        templates,
        direct[HEADER_IDS["race_heading"]],
        direct[HEADER_IDS["name_heading"]],
        direct[HEADER_IDS["attack_heading"]],
        direct[HEADER_IDS["defense_heading"]],
        suffix("magic_cost"),
        suffix("health_cost"),
        MappingProxyType(axes),
    )


def _runtime_terms(
    physical: Mapping[str, str],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    race_ids = {
        f"game.da3d_analyze.grid_races.r{index:04d}"
        for index in range(RACE_COUNT)
    }
    races_by_id = _bound(
        ("game.da3d_analyze.grid_races.",),
        race_ids,
        (BINDING_ROOT / "races.json",),
        physical,
    )
    races = tuple(
        races_by_id[f"game.da3d_analyze.grid_races.r{index:04d}"]
        for index in range(RACE_COUNT)
    )

    affinity_ids = {
        f"game.normcom_tables.affinities.r{index:04d}"
        for index in range(AFFINITY_COUNT)
    }
    affinities_by_id = _bound(
        ("game.normcom_tables.affinities.",),
        affinity_ids,
        (BINDING_ROOT / "affinities.json",),
        physical,
    )
    affinities = tuple(
        affinities_by_id[f"game.normcom_tables.affinities.r{index:04d}"]
        for index in range(AFFINITY_COUNT)
    )

    demon_ids = {
        f"game.dvlname.o{index * 8:06x}.text" for index in range(DEMON_COUNT)
    }
    demons_by_id = _bound(
        ("game.dvlname.",),
        demon_ids,
        (BINDING_ROOT / "demons.json",),
        physical,
    )
    demons = tuple(
        demons_by_id[f"game.dvlname.o{index * 8:06x}.text"]
        for index in range(DEMON_COUNT)
    )
    return races, affinities, demons


def _ability_names(physical: Mapping[str, str]) -> tuple[str, ...]:
    ids = {
        f"game.magname.o{index * MAGNAME_RECORD_SIZE + 4:06x}.name"
        for index in range(MAGNAME_COUNT)
    }
    values = _bound(
        ("game.magname.",),
        ids,
        (BINDING_ROOT / "magic.json", BINDING_ROOT / "skills.json"),
        physical,
    )
    return tuple(
        values[f"game.magname.o{index * MAGNAME_RECORD_SIZE + 4:06x}.name"]
        for index in range(MAGNAME_COUNT)
    )


def _font8_encode(
    text: str, codes: Mapping[str, int], context: str, terminator: int | None = None
) -> bytes:
    try:
        data = bytes(codes[character] for character in text)
    except KeyError as error:
        raise ValueError(
            f"unsupported {context} FONT8 character {error.args[0]!r} in {text!r}"
        ) from error
    return data if terminator is None else data + bytes((terminator,))


def _affinity_advance(
    text: str, widths: bytes, codes: Mapping[str, int]
) -> int:
    try:
        return sum(
            AFFINITY_ADVANCE_OVERRIDES.get(character, widths[codes[character]])
            for character in text
        )
    except KeyError as error:
        raise ValueError(
            f"unsupported Analyze affinity character {error.args[0]!r}"
        ) from error


def _validate_affinity_font(
    font: bytes, widths: bytes, codes: Mapping[str, int]
) -> None:
    for character, advance in AFFINITY_ADVANCE_OVERRIDES.items():
        code = codes.get(character)
        if code is None:
            raise ValueError(f"Analyze FONT8 is missing {character!r}")
        cell = font[code * 8 : (code + 1) * 8]
        ink = [x for row in cell for x in range(8) if row & (0x80 >> x)]
        if character == " ":
            if ink:
                raise ValueError("Analyze compact space is not blank")
        elif not ink or max(ink) >= advance:
            raise ValueError(f"Analyze compact {character!r} exceeds its advance")
        if advance > widths[code]:
            raise ValueError(f"Analyze compact {character!r} exceeds FONT8 metrics")


def _phrase_candidates(values: Sequence[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    labelled: Counter[str] = Counter()
    compounds: list[str] = []
    for value in values:
        for line in value.split("{n}"):
            clauses = re.split(r", (?=[A-Za-z]+: )", line)
            for clause in clauses:
                match = re.fullmatch(r"([A-Za-z]+): (.+)", clause)
                if match is None:
                    continue
                label, body = match.groups()
                items = body.split(", ")
                if re.fullmatch(r"[A-Za-z]+", items[0]):
                    labelled[f"{label}: {items[0]}"] += 1
                for item in items:
                    if (
                        len(item.split()) >= 2
                        and all(re.fullmatch(r"[A-Za-z]+", word) for word in item.split())
                        and item not in compounds
                    ):
                        compounds.append(item)
    repeated = tuple(text for text, count in labelled.items() if count >= 2)
    return repeated, tuple(compounds)


def _serialize_affinities(
    values: Sequence[str],
    phrases: tuple[str, ...],
    codes: Mapping[str, int],
) -> tuple[bytes, bytes, bytes, tuple[str, ...]] | None:
    ordered_phrases = tuple(
        sorted(
            phrases,
            key=lambda phrase: (
                -len(phrase),
                min(value.find(phrase) for value in values if phrase in value),
                phrase,
            ),
        )
    )
    alternatives = [re.escape(phrase) for phrase in ordered_phrases]
    alternatives.extend((r"[,:]", r"\{n\}", r"[A-Za-z]+"))
    pattern = re.compile("|".join(alternatives))
    words: list[str] = []
    tokens = bytearray()
    for index, value in enumerate(values):
        position = 0
        for match in pattern.finditer(value):
            if value[position : match.start()].strip():
                return None
            part = match.group(0)
            position = match.end()
            if part == ",":
                tokens.append(29)
            elif part == "{n}":
                tokens.append(30)
            elif part == ":":
                tokens.append(31)
            else:
                if part not in words:
                    words.append(part)
                tokens.append(words.index(part) + 1)
        if value[position:].strip():
            raise ValueError(f"unsupported Analyze affinity syntax in record {index}")
        tokens.append(0)
    if len(words) > 28:
        return None
    offsets = bytearray()
    pool = bytearray()
    for index, word in enumerate(words):
        if len(pool) > 0xFF:
            return None
        offsets.append(len(pool))
        pool.extend(_font8_encode(word, codes, f"affinity word {index}", 0))
    return bytes(offsets), bytes(pool), bytes(tokens), tuple(words)


def _affinity_dictionary(
    values: Sequence[str], codes: Mapping[str, int]
) -> tuple[bytes, bytes, bytes, tuple[str, ...]]:
    labelled, compounds = _phrase_candidates(values)
    occurrences = {
        phrase: min(index for index, value in enumerate(values) if phrase in value)
        for phrase in (*labelled, *compounds)
    }
    candidates: list[
        tuple[
            tuple[object, ...],
            tuple[bytes, bytes, bytes, tuple[str, ...]],
            tuple[str, ...],
        ]
    ] = []
    labelled_options: tuple[str | None, ...] = (None, *labelled)
    for labelled_phrase in labelled_options:
        for mask in range(1 << len(compounds)):
            phrases = tuple(
                phrase
                for index, phrase in enumerate(compounds)
                if mask & (1 << index)
            )
            if labelled_phrase is not None:
                phrases = (labelled_phrase, *phrases)
            serialized = _serialize_affinities(values, phrases, codes)
            if serialized is None:
                continue
            offsets, pool, tokens, words = serialized
            score = (
                len(offsets) + len(pool) + len(tokens),
                len(words),
                len(phrases),
                tuple(occurrences[phrase] for phrase in phrases),
                phrases,
            )
            candidates.append((score, serialized, phrases))
    if not candidates:
        raise ValueError("Analyze affinity corpus cannot fit the compact dictionary")
    _score, serialized, phrases = min(candidates, key=lambda row: row[0])
    offsets, pool, tokens, _words = serialized
    return offsets, pool, tokens, phrases


def _validate_magname(
    packed: bytes,
    names: Sequence[str],
    widths: bytes,
    codes: Mapping[str, int],
) -> None:
    if len(names) != MAGNAME_COUNT:
        raise ValueError("Analyze needs exactly 255 bound ability names")
    for index, name in enumerate(names):
        encoded = _font8_encode(name, codes, f"ability name {index}")
        if not encoded or len(encoded) > 32:
            raise ValueError(f"Analyze ability name {index} exceeds 32 bytes")
        if any(not (63 <= code < 118 or 205 <= code < 230) for code in encoded):
            raise ValueError(
                f"Analyze ability name {index} leaves the compact FONT8 domain"
            )
        if sum(widths[code] for code in encoded) > 80:
            raise ValueError(f"Analyze ability name {index} exceeds its 80px row")
        pointer = struct.unpack_from(
            ">H", packed, index * MAGNAME_RECORD_SIZE + MAGNAME_POINTER_OFFSET
        )[0]
        expected = encoded + b"\xff"
        if packed[pointer : pointer + len(expected)] != expected:
            raise ValueError(f"Analyze MAGNAME row {index} name payload is stale")


def _pack_long_name(name: str, index: int) -> bytes:
    tokens: list[int] = []
    uppercase = True
    for character in name:
        if character.isascii() and character.isalpha():
            wanted_uppercase = character.isupper()
            if wanted_uppercase != uppercase:
                tokens.append(30)
            tokens.append(ord(character.lower()) - ord("a") + 1)
            uppercase = False
        elif character == " ":
            tokens.append(27)
            uppercase = True
        elif character == "-":
            tokens.append(28)
            uppercase = True
        elif character == "'":
            tokens.append(29)
            uppercase = True
        elif character == "8":
            tokens.append(31)
            uppercase = False
        else:
            raise ValueError(
                f"unsupported Analyze demon-name character {character!r} "
                f"in record {index}: {name!r}"
            )
    while len(tokens) % 3:
        tokens.append(0)
    output = bytearray()
    for offset in range(0, len(tokens), 3):
        first, second, third = tokens[offset : offset + 3]
        final = offset + 3 == len(tokens)
        output.extend(
            struct.pack(
                ">H",
                (0x8000 if final else 0)
                | first << 10
                | second << 5
                | third,
            )
        )
    return bytes(output)


@dataclass(frozen=True, slots=True)
class CompactData:
    data: bytes
    compact_widths8: bytes
    addresses: Mapping[str, int]
    affinity_phrases: tuple[str, ...]


def _compact_data(
    address: int,
    font8: bytes,
    widths8: bytes,
    codes8: Mapping[str, int],
    widths16: bytes,
    codes16: Mapping[str, int],
    races: Sequence[str],
    affinities: Sequence[str],
    demon_names: Sequence[str],
    built_dvlname: bytes,
) -> CompactData:
    if (
        len(races) != RACE_COUNT
        or len(affinities) != AFFINITY_COUNT
        or len(demon_names) != DEMON_COUNT
    ):
        raise ValueError("Analyze terminology inventory changed")
    validate_shiftable_bitmap(font8, widths8, 8, 1, "Analyze FONT8")
    _validate_affinity_font(font8, widths8, codes8)
    for index, affinity in enumerate(affinities):
        for line in affinity.split("{n}"):
            for position, character in enumerate(line[:-1]):
                if character in ",:" and line[position + 1] != " ":
                    raise ValueError(
                        f"Analyze affinity {index} punctuation needs one space"
                    )
            encoded = _font8_encode(line, codes8, f"affinity {index}", 0)
            if len(encoded) > AFFINITY_LINE_BYTES:
                raise ValueError(
                    f"Analyze affinity {index} exceeds its 35-byte line buffer"
                )
            if _affinity_advance(line, widths8, codes8) > AFFINITY_MAX_ADVANCE:
                raise ValueError(
                    f"Analyze affinity {index} exceeds {AFFINITY_MAX_ADVANCE}px"
                )

    data = bytearray()
    addresses: dict[str, int] = {}

    def append(name: str, payload: bytes, alignment: int = 1) -> int:
        data.extend(bytes((-(address + len(data))) % alignment))
        result = address + len(data)
        data.extend(payload)
        addresses[name] = result
        return result

    source_characters = set(
        "".join(
            (*races, *(value.replace("{n}", "") for value in affinities), *demon_names)
        )
    )
    font16_advances = bytearray(229 - 63 + 1)
    for character in source_characters:
        try:
            source_code = codes8[character]
            target_code = codes16[character]
        except KeyError as error:
            raise ValueError(
                f"Analyze FONT16 source mapping is missing {error.args[0]!r}"
            ) from error
        if not 63 <= source_code <= 229:
            raise ValueError(f"Analyze FONT8 source code {source_code} is out of range")
        font16_advances[source_code - 63] = widths16[target_code]
    compact16 = font16_advances[:55] + font16_advances[142:]
    if len(compact16) != 80:
        raise ValueError("Analyze compact FONT16 width table is not 80 bytes")
    append("font16_widths", bytes(compact16))

    race_pool = bytearray()
    race_offsets = bytearray()
    for index, race in enumerate(races):
        encoded = _font8_encode(race, codes8, f"race {index}")
        if sum(widths8[code] for code in encoded) > 52:
            raise ValueError(f"Analyze race {index} exceeds its 52px grid cell")
        if sum(widths16[codes16[character]] for character in race) > 46:
            raise ValueError(f"Analyze race {index} exceeds its 46px detail row")
        race_offsets.extend(struct.pack(">H", len(race_pool)))
        race_pool.extend(encoded)
        race_pool.append(0xFF)
    append("race_pool", bytes(race_pool))
    append("race_offsets", bytes(race_offsets), 2)

    long_bits = bytearray((DEMON_COUNT + 7) // 8)
    long_names = bytearray()
    for index, name in enumerate(demon_names):
        encoded = _font8_encode(name, codes8, f"demon name {index}")
        direct = len(encoded) <= 8 and sum(widths8[code] for code in encoded) <= 64
        if direct:
            actual = built_dvlname[index * 8 : (index + 1) * 8]
            if actual != encoded.ljust(8, b"\0"):
                raise ValueError(f"Analyze direct DVLNAME row {index} is stale")
        else:
            long_bits[index // 8] |= 1 << (index & 7)
            long_names.extend(_pack_long_name(name, index))
        if index < SORT_DEMON_COUNT:
            table_width = sum(widths8[code] for code in encoded)
            if table_width > 80:
                raise ValueError(
                    f"Analyze demon name {index} exceeds its 80px name field"
                )
        detail_width = sum(widths16[codes16[character]] for character in name)
        if detail_width > 126:
            raise ValueError(
                f"Analyze demon name {index} exceeds its 126px detail row"
            )
    append("long_name_bits", bytes(long_bits))
    append("name_pool", bytes(long_names))

    word_offsets, word_pool, affinity_tokens, phrases = _affinity_dictionary(
        affinities, codes8
    )
    append("affinity_word_offsets", word_offsets)
    append("affinity_word_pool", word_pool)
    append("affinity_tokens", affinity_tokens)

    compact8 = widths8[63:118] + widths8[205:230]
    if len(compact8) != 80:
        raise ValueError("Analyze compact FONT8 width table is not 80 bytes")
    return CompactData(
        bytes(data), bytes(compact8), MappingProxyType(addresses), phrases
    )


def _layout_data(
    base: bytes,
    stock_font16: bytes,
    font8: bytes,
    widths8: bytes,
    codes8: Mapping[str, int],
    templates: StatusTemplates,
) -> dict[str, bytes]:
    labels = load_status_labels(templates)
    cell = base[NODE_BITMAP_OFFSET : NODE_BITMAP_OFFSET + NODE_BITMAP_SIZE]
    background = node_background(cell, stock_font16)
    return {
        "parameter_nodes": b"".join(
            direct_color_node(label, font8, widths8, codes8, background)
            for label in labels.base
        ),
        "parameter_rows": b"".join(
            direct_color_row(" ".join(row), font8, widths8, codes8)
            for row in derived_rows(labels)
        ),
        "generic_attack_label": direct_color_row(
            labels.attack, font8, widths8, codes8
        ),
        "generic_accuracy_label": direct_color_row(
            labels.accuracy, font8, widths8, codes8
        ),
        "loyalty_label": direct_color_row(
            labels.personality[0], font8, widths8, codes8, 40
        ),
    }


def _ascii_record(
    text: str,
    capacity: int,
    maximum: int,
    pixel_width: int,
    widths: bytes,
    stock_codes: Mapping[str, int],
    context: str,
) -> bytes:
    try:
        encoded = text.encode("ascii")
    except UnicodeEncodeError as error:
        raise ValueError(f"{context} must use direct ASCII cells") from error
    if not 1 <= len(encoded) <= maximum or len(encoded) >= capacity:
        raise ValueError(f"{context} exceeds its {maximum}-cell record")
    unsupported = next(
        (character for character in text if character not in stock_codes), None
    )
    if unsupported is not None:
        raise ValueError(
            f"{context} uses unsupported stock-Latin cell {unsupported!r}"
        )
    if sum(widths[stock_codes[character]] for character in text) > pixel_width:
        raise ValueError(f"{context} exceeds its {pixel_width}px surface")
    return encoded.ljust(capacity, b"\0")


def _direct_data(
    terms: AnalyzeTerms, widths: bytes, stock_codes: Mapping[str, int]
) -> tuple[dict[str, bytes], bool]:
    prefix = terms.templates.prefixes
    data = {
        "detail_level_prefix": _ascii_record(
            prefix["level"], 4, 3, 24, widths, stock_codes, "Analyze detail level"
        ),
        "detail_hit_points_prefix": _ascii_record(
            prefix["hit_points"], 4, 3, 24, widths, stock_codes, "Analyze detail HP"
        ),
        "detail_magic_points_prefix": _ascii_record(
            prefix["magic_points"], 4, 3, 24, widths, stock_codes, "Analyze detail MP"
        ),
        "detail_summon_cost_prefix": _ascii_record(
            prefix["summon_cost"], 4, 3, 24, widths, stock_codes, "Analyze detail CP"
        ),
        "race_heading": _ascii_record(
            terms.race_heading, 8, 7, 52, widths, stock_codes, "Analyze RACE heading"
        ),
        "name_heading": _ascii_record(
            terms.name_heading, 8, 7, 76, widths, stock_codes, "Analyze NAME heading"
        ),
        "level_heading": _ascii_record(
            prefix["level"], 4, 3, 46, widths, stock_codes, "Analyze LV heading"
        ),
        "hit_points_heading": _ascii_record(
            prefix["hit_points"], 4, 3, 34, widths, stock_codes, "Analyze HP heading"
        ),
        "magic_points_heading": _ascii_record(
            prefix["magic_points"], 4, 3, 28, widths, stock_codes, "Analyze MP heading"
        ),
        "attack_heading": _ascii_record(
            terms.attack_heading, 4, 3, 36, widths, stock_codes, "Analyze ATK heading"
        ),
        "defense_heading": _ascii_record(
            terms.defense_heading, 4, 3, 52, widths, stock_codes, "Analyze DEF heading"
        ),
        "magic_cost_suffix": _ascii_record(
            terms.magic_cost_suffix, 4, 1, 8, widths, stock_codes, "Analyze magic cost"
        ),
        "health_cost_suffix": _ascii_record(
            terms.health_cost_suffix, 2, 1, 8, widths, stock_codes, "Analyze health cost"
        ),
    }
    law = terms.axes["law"].encode("ascii")
    light = terms.axes["light"].encode("ascii")
    diverges = law != light
    data.update(
        {
            "axis_law": law + b"\0" + (light if diverges else b"\0") + b"\0",
            "axis_chaos": terms.axes["chaos"].encode("ascii") + b"\0\0\0",
            "axis_dark": terms.axes["dark"].encode("ascii") + b"\0\0\0",
            "axis_neutral": terms.axes["neutral"].encode("ascii") + b"\0",
            "axis_law_light_pointer": struct.pack(
                ">I", 0x0602D4CA if diverges else 0x0602D4C8
            ),
        }
    )
    return data, diverges


def _assembled(
    source: Path, address: int, symbols: Mapping[str, int]
) -> Assembly:
    try:
        result = assemble_file(source, address, dict(symbols))
    except (AssemblyError, FileNotFoundError) as error:
        raise ValueError(f"Analyze assembly failed for {source.name}: {error}") from error
    if result.warnings:
        raise ValueError(
            f"Analyze assembly warnings for {source.name}: "
            + "; ".join(result.warnings)
        )
    return result


def _source_paths(
    recipe: PatchRecipe, expected: tuple[str, ...]
) -> tuple[Path, ...]:
    actual = tuple(
        path.relative_to(ASSEMBLY_ROOT).as_posix()
        for path in recipe.replacement.sources
    )
    if actual != expected:
        raise ValueError(
            f"{recipe.group}/{recipe.name} assembly sources changed: {actual!r}"
        )
    return recipe.replacement.sources


def _runtime_payload(
    runtime_recipe: PatchRecipe,
    table_recipe: PatchRecipe,
    compact: CompactData,
) -> RuntimeBuild:
    if (
        runtime_recipe.address != RUNTIME_CAVE
        or runtime_recipe.expected_size != RUNTIME_CAPACITY
        or table_recipe.address != TABLE_CAVE
        or table_recipe.expected_size != TABLE_CAPACITY
    ):
        raise ValueError("Analyze runtime recipes no longer own the two exact caves")
    runtime_sources = _source_paths(
        runtime_recipe,
        (
            "analyze_ui/font8_vwf.s",
            "analyze_ui/font16_from_font8.s",
            "analyze_ui/name_decoder.s",
            "analyze_ui/affinity_dispatcher.s",
            "analyze_ui/name_race_dispatcher.s",
        ),
    )
    table_sources = _source_paths(
        table_recipe,
        ("analyze_ui/skill_dispatcher.s", "analyze_ui/table_font8_vwf.s"),
    )

    payload = bytearray(compact.data)

    def append(source: Path, symbols: Mapping[str, int]) -> tuple[int, Assembly]:
        payload.extend(bytes((-(RUNTIME_CAVE + len(payload))) % 4))
        address = RUNTIME_CAVE + len(payload)
        result = _assembled(source, address, symbols)
        payload.extend(result.data)
        return address, result

    addresses = compact.addresses
    font8_vwf, _font8 = append(
        runtime_sources[0],
        {
            "WIDTHS": TABLE_CAVE,
            "FONT_BITMAP": FONT8_BITMAP,
            "GLYPH": DETAIL_FONT8_GLYPH_DRAWER,
        },
    )
    font16_vwf, _font16 = append(
        runtime_sources[1],
        {
            "WIDTHS": addresses["font16_widths"],
            "FONT_BITMAP": FONT16_BITMAP,
            "STOCK": DETAIL_FONT16_DRAWER,
        },
    )
    name_decoder, _name = append(
        runtime_sources[2],
        {
            "DVL_SOURCE": DVL_SOURCE,
            "LONG_NAME_BITS": addresses["long_name_bits"],
            "NAME_POOL": addresses["name_pool"],
        },
    )
    affinity_dispatcher, _affinity = append(
        runtime_sources[3],
        {
            "SELECTOR": AFFINITY_SELECTOR,
            "AFFINITY_TOKENS": addresses["affinity_tokens"],
            "WORD_OFFSETS": addresses["affinity_word_offsets"],
            "WORD_POOL": addresses["affinity_word_pool"],
            "FONT8_VWF": font8_vwf,
            "STOCK": DETAIL_FONT16_DRAWER,
        },
    )

    table = bytearray(compact.compact_widths8)

    def append_table(
        source: Path, symbols: Mapping[str, int]
    ) -> tuple[int, Assembly]:
        table.extend(bytes((-(TABLE_CAVE + len(table))) % 4))
        address = TABLE_CAVE + len(table)
        result = _assembled(source, address, symbols)
        table.extend(result.data)
        return address, result

    skill_dispatcher, _skill = append_table(
        table_sources[0],
        {
            "MAGIC_FIRST": MAGNAME_FIRST,
            "MAGIC_END": MAGNAME_END,
            "MAGIC_BASE": MAGNAME_BASE,
            "NAME_POINTER": MAGNAME_POINTER_FROM_NAME,
            "FONT8_VWF": font8_vwf,
            "STOCK": DETAIL_FONT8_DRAWER,
        },
    )
    table_font8_vwf, _table_vwf = append_table(
        table_sources[1],
        {"WIDTHS": TABLE_CAVE, "GLYPH": TABLE_FONT8_GLYPH_DRAWER},
    )
    table_used = len(table)
    if table_used > TABLE_CAPACITY:
        raise ValueError(
            f"Analyze table runtime exceeds its exact cave by "
            f"{table_used - TABLE_CAPACITY:#x} bytes"
        )
    table.extend(bytes(TABLE_CAPACITY - table_used))

    _dispatch_address, dispatch = append(
        runtime_sources[4],
        {
            "DVL_SOURCE": DVL_SOURCE,
            "TABLE_FONT8_VWF": table_font8_vwf,
            "FONT16_VWF": font16_vwf,
            "NAME_DECODER": name_decoder,
            "TABLE_RACE_SOURCE": TABLE_CAVE,
            "TABLE_STOCK": TABLE_FONT8_DRAWER,
            "CURRENT_NAME_PTR": CURRENT_NAME_PTR,
            "DETAIL_RACE_SOURCE": DETAIL_RACE_SOURCE,
            "RACE_POOL": addresses["race_pool"],
            "RACE_OFFSETS": addresses["race_offsets"],
            "DETAIL_STOCK": DETAIL_FONT16_DRAWER,
        },
    )
    used = len(payload)
    if used > RUNTIME_CAPACITY:
        raise ValueError(
            f"Analyze runtime exceeds its exact cave by "
            f"{used - RUNTIME_CAPACITY:#x} bytes"
        )
    payload.extend(bytes(RUNTIME_CAPACITY - used))
    return RuntimeBuild(
        bytes(payload),
        bytes(table),
        MappingProxyType(
            {
                "detailed_dispatcher": dispatch.labels["detailed_dispatcher"],
                "skill_dispatcher": skill_dispatcher,
                "affinity_dispatcher": affinity_dispatcher,
                "table_dispatcher": dispatch.labels["table_dispatcher"],
            }
        ),
        used,
        RUNTIME_CAPACITY,
        table_used,
        TABLE_CAPACITY,
    )


def _small_assembly(
    recipe: PatchRecipe, expected: bytes, *, axes_diverge: bool
) -> bytes:
    if recipe.name == "english_name_compare":
        (source,) = _source_paths(
            recipe, ("analyze_ui/name_rank_compare.s",)
        )
        result = _assembled(
            source,
            recipe.address,
            {"RANK_TABLE_LITERAL": 0x0602EE18, "CONTINUE": 0x0602ED76},
        ).data
    elif recipe.name in {"axis_law_first_load", "axis_light_load"}:
        (source,) = _source_paths(
            recipe, ("analyze_ui/axis_pointer_load.s",)
        )
        if not axes_diverge:
            return expected
        result = _assembled(
            source, recipe.address, {"LAW_POINTER_LITERAL": 0x0602D554}
        ).data
    elif recipe.name == "axis_law_adjust":
        (source,) = _source_paths(
            recipe, ("analyze_ui/axis_law_adjust.s",)
        )
        if not axes_diverge:
            return expected
        result = _assembled(source, recipe.address, {}).data
    elif recipe.name in {"axis_law_cell_argument", "axis_light_cell_argument"}:
        (source,) = _source_paths(
            recipe, ("analyze_ui/axis_cell_argument.s",)
        )
        if not axes_diverge:
            return expected
        result = _assembled(source, recipe.address, {}).data
    else:
        raise ValueError(f"unknown Analyze standalone assembly {recipe.name}")
    if len(result) != len(expected):
        raise ValueError(f"{recipe.name} assembly changed size")
    return result


def _build_components(
    config: PatchRecipeConfiguration,
    base: bytes,
    stock_font16: bytes,
    built_dvlname: bytes,
    built_magname: bytes,
) -> tuple[dict[str, bytes], RuntimeBuild, bool, CompactData]:
    physical = _physical_records()
    terms = _analyze_terms(physical)
    races, affinities, demons = _runtime_terms(physical)
    abilities = _ability_names(physical)
    metrics8 = FontMetrics.load(FONT8_METRICS_PATH)
    widths8, codes8 = font8_tables(metrics8)
    widths16, codes16 = load_font16_metrics(FONT16_METRICS_PATH)
    font8 = FONT8_PATH.read_bytes()
    font16 = FONT16_PATH.read_bytes()
    if len(font8) != 256 * 8 or len(font16) != 1872 * 32:
        raise ValueError("Analyze generated font geometry changed")
    validate_shiftable_bitmap(font16, widths16, 32, 2, "Analyze FONT16")
    _validate_magname(built_magname, abilities, widths8, codes8)
    compact = _compact_data(
        RUNTIME_CAVE,
        font8,
        widths8,
        codes8,
        widths16,
        codes16,
        races,
        affinities,
        demons,
        built_dvlname,
    )
    recipes = {recipe.name: recipe for recipe in config.patches[TARGET]}
    if len(recipes) != len(config.patches[TARGET]):
        raise ValueError("Analyze patch names must be unique")
    try:
        runtime = _runtime_payload(
            recipes["analyze_runtime"], recipes["analyze_table_runtime"], compact
        )
    except KeyError as error:
        raise ValueError("Analyze config is missing a runtime cave") from error

    generated = _layout_data(
        base, stock_font16, font8, widths8, codes8, terms.templates
    )
    direct, axes_diverge = _direct_data(
        terms, widths8, load_stock_latin_codes(FONT8_METRICS_PATH)
    )
    generated.update(direct)
    generated["english_name_ranks"] = dense_rank_table(
        demons, count=SORT_DEMON_COUNT
    )
    return generated, runtime, axes_diverge, compact


def _bind_patches(
    config: PatchRecipeConfiguration,
    base: bytes,
    stock_font16: bytes,
    built_dvlname: bytes,
    built_magname: bytes,
) -> tuple[tuple[Patch, ...], RuntimeBuild, CompactData]:
    expected = {
        recipe.name: resolve_recipe_expected(recipe, base, LOAD_ADDRESS)
        for recipe in config.patches[TARGET]
    }
    generated, runtime, axes_diverge, compact = _build_components(
        config, base, stock_font16, built_dvlname, built_magname
    )
    output: list[Patch] = []
    generated_seen: set[str] = set()
    for recipe in config.patches[TARGET]:
        replacement_recipe = recipe.replacement
        if replacement_recipe.kind == "assembly":
            if recipe.name == "analyze_runtime":
                replacement = runtime.data
            elif recipe.name == "analyze_table_runtime":
                replacement = runtime.table_data
            else:
                replacement = _small_assembly(
                    recipe, expected[recipe.name], axes_diverge=axes_diverge
                )
        elif replacement_recipe.kind == "linked_pointer":
            link = replacement_recipe.link
            assert link is not None
            try:
                replacement = struct.pack(">I", runtime.links[link])
            except KeyError as error:
                raise ValueError(f"unknown Analyze runtime link {link}") from error
        elif replacement_recipe.kind == "generated":
            if replacement_recipe.generator != "analyze_ui_data":
                raise ValueError(f"{recipe.name}: unknown Analyze data generator")
            try:
                replacement = generated[recipe.name]
            except KeyError as error:
                raise ValueError(
                    f"Analyze data generator did not own {recipe.name}"
                ) from error
            generated_seen.add(recipe.name)
        else:
            raise ValueError(
                f"{recipe.group}/{recipe.name}: unsupported Analyze replacement "
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
            "Analyze data generator has no configured owner: "
            + ", ".join(sorted(unused))
        )
    return tuple(output), runtime, compact


def build_analyze_ui(base: bytes | None = None) -> AnalyzeUiBuild:
    """Build the complete standalone DA_3D Analyze interface patch."""
    _validate_surfaces()
    config = _configuration()
    stock_da3d, stock_font16 = _source_assets()
    source = stock_da3d if base is None else base
    built_dvlname, built_magname = _validate_inputs(config, source, stock_font16)
    patches, runtime, _compact = _bind_patches(
        config, source, stock_font16, built_dvlname, built_magname
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
    return AnalyzeUiBuild(
        apply_patches(source, LOAD_ADDRESS, patches),
        patches,
        ASSET_FILES,
        RUNTIME_INPUT_FILES,
        MappingProxyType(
            {
                "game:DA_3D.BIN": _sha256(source),
                "game:FONT16.FON": _sha256(stock_font16),
            }
        ),
        assembly_files,
        runtime.used_size,
        runtime.capacity,
        runtime.table_used_size,
        runtime.table_capacity,
    )


__all__ = (
    "CONFIG_PATH",
    "OUTPUT",
    "TARGET",
    "AnalyzeUiBuild",
    "build_analyze_ui",
)
