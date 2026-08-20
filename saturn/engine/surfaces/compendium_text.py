"""Build Akuma Zensho profile and catalogue text from authored assets."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Mapping

from engine.core.patch_recipes import (
    PatchRecipeConfiguration,
    load_patch_recipe_configuration,
    resolve_recipe_expected,
)
from engine.core.patching import Patch, apply_patches
from engine.core.sh2 import AssemblyError, assemble
from engine.shared.compendium_codec import (
    CompactCodec,
    EXTENDED_CHARACTERS,
    PROFILE_TAIL_BYTES,
    build_dictionary,
    build_embedded_font,
    encode_profile_tail,
)
from rom.util.catalog import load_catalog, validate_source
from rom.util.workflows import read_source_files
from text.util.assets import (
    ASSET_ROOT,
    BINDING_ROOT,
    CORPUS_ROOT,
    load_asset,
    load_physical_record_files,
)
from text.util.event_repack import FontMetrics


ENGINE_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = ENGINE_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "compendium_text.json"
ASSEMBLY_PATH = ENGINE_ROOT / "asm" / "compendium_text" / "compact_drawer.s"
OUTPUT_ROOT = ENGINE_ROOT / "generated" / "compendium"
BUILD_PATH = OUTPUT_ROOT / "compendium_text_build.json"
TARGET = "A_DIC.BIN"
LOAD_ADDRESS = 0x06020000

SOURCE_MANIFEST_PATH = (
    SATURN_ROOT / "text" / "config" / "sources" / "compendium" / "manifest.json"
)
SURFACES_PATH = SATURN_ROOT / "text" / "config" / "surfaces.json"
DISC_CONFIG_PATH = SATURN_ROOT / "rom" / "discs.json"
FONT8_PATH = SATURN_ROOT / "font" / "generated" / "game" / "FONT8.FON"
FONT8_METRICS_PATH = (
    SATURN_ROOT / "font" / "generated" / "game" / "FONT8_metrics.json"
)
CODEC_PATH = ENGINE_ROOT / "shared" / "compendium_codec.py"

ASSET_FILES = (
    ASSET_ROOT / "demons.json",
    ASSET_ROOT / "races.json",
    ASSET_ROOT / "magic.json",
    ASSET_ROOT / "skills.json",
)
BINDING_FILES = (
    BINDING_ROOT / "demon_compendium.json",
    BINDING_ROOT / "demons.json",
    BINDING_ROOT / "races.json",
    BINDING_ROOT / "magic.json",
    BINDING_ROOT / "skills.json",
)
CORPUS_FILES = (
    CORPUS_ROOT / "compendium" / "profiles.json",
    CORPUS_ROOT / "compendium" / "fixed" / "demon_names.json",
    CORPUS_ROOT / "compendium" / "fixed" / "ability_names.json",
    CORPUS_ROOT / "compendium" / "addressed" / "race_names.json",
)
RUNTIME_INPUT_FILES = (
    FONT8_PATH,
    FONT8_METRICS_PATH,
    SURFACES_PATH,
    DISC_CONFIG_PATH,
    SOURCE_MANIFEST_PATH,
    CODEC_PATH,
    *BINDING_FILES,
    *CORPUS_FILES,
)

PROFILE_TAIL_OFFSET = 0x78000
RUNTIME_ADDRESS = 0x0603D200
RUNTIME_CAPACITY = 0x7802
ORIGINAL_DRAW = 0x06021984
FONT_BASE = 0x00289000
SAVED_FONT = 0x002881DC
ROW_CODES = SAVED_FONT + 14 * 32

DEMON_TABLE_OFFSET = 0x5D9B0
DEMON_COUNT = 319
ABILITY_TABLE_OFFSET = 0x69BE4
ABILITY_COUNT = 255
RACE_TABLE_OFFSET = 0x5EDA0
RACE_COUNT = 48

UNRESOLVED_IDS = frozenset(
    {
        "compendium.race_names.supplement.r0001",
        "compendium.race_names.supplement.r0002",
        "compendium.race_names.supplement.r0003",
        "compendium.race_names.supplement.r0004",
    }
)
POINTER_OFFSETS = (
    0x2758,
    0x2B88,
    0x40BC,
    0x41C0,
    0x492C,
    0x499C,
    0x5B80,
    0x5DC8,
    0x5EB4,
    0x6010,
    0x6144,
    0x627C,
    0x6334,
    0x6660,
    0x6A3C,
    0x7B78,
    0x7C70,
)


@dataclass(frozen=True, slots=True)
class RuntimeArena:
    address: int
    used_size: int
    capacity: int


@dataclass(frozen=True, slots=True)
class CompendiumTextBuild:
    outputs: Mapping[str, bytes]
    patches: Mapping[str, tuple[Patch, ...]]
    asset_files: tuple[Path, ...]
    assembly_files: tuple[Path, ...]
    runtime_input_files: tuple[Path, ...]
    source_inputs: Mapping[str, str]
    runtime_used_size: int
    runtime_capacity: int
    runtime_arenas: tuple[RuntimeArena, ...]
    unresolved_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class _Runtime:
    data: bytes
    used_size: int
    links: Mapping[str, int]


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"missing compendium input: {path}") from error


def _configuration() -> PatchRecipeConfiguration:
    config = load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="compendium.text",
        target_names={TARGET},
        input_names={"font8_sha256", "font8_metrics_sha256"},
    )
    recipes = config.patches[TARGET]
    expected = (
        ("runtime_arena", RUNTIME_ADDRESS, "assembly"),
        ("demon_names", LOAD_ADDRESS + DEMON_TABLE_OFFSET, "generated"),
        ("race_names", LOAD_ADDRESS + RACE_TABLE_OFFSET, "generated"),
        ("ability_names", LOAD_ADDRESS + ABILITY_TABLE_OFFSET, "generated"),
        *(
            (
                f"drawer_pointer_{index + 1:02d}",
                LOAD_ADDRESS + offset,
                "linked_pointer",
            )
            for index, offset in enumerate(POINTER_OFFSETS)
        ),
    )
    actual = tuple(
        (recipe.name, recipe.address, recipe.replacement.kind) for recipe in recipes
    )
    if actual != expected:
        raise ValueError("compendium patch recipe inventory drifted")
    if recipes[0].replacement.sources != (ASSEMBLY_PATH.resolve(),):
        raise ValueError("compendium runtime assembly source drifted")
    if any(
        recipe.replacement.generator != "compendium_data"
        for recipe in recipes[1:4]
    ):
        raise ValueError("compendium data generator contract drifted")
    if any(
        recipe.replacement.link != "compact_draw" for recipe in recipes[4:]
    ):
        raise ValueError("compendium drawer link contract drifted")
    return config


def _source_manifest() -> tuple[dict[str, dict[str, object]], tuple[str, ...]]:
    document = _read_json(SOURCE_MANIFEST_PATH)
    if not isinstance(document, dict) or set(document) != {
        "version",
        "disc",
        "track_sha256",
        "files",
        "sources",
    }:
        raise ValueError("invalid compendium source manifest")
    if document["version"] != 1 or document["disc"] != "compendium":
        raise ValueError("unsupported compendium source manifest")
    raw_files = document["files"]
    if (
        not isinstance(raw_files, dict)
        or len(raw_files) != 293
        or "a_dic" not in raw_files
        or sum(key.startswith("dvl_") for key in raw_files) != 292
    ):
        raise ValueError("compendium source target inventory drifted")
    files: dict[str, dict[str, object]] = {}
    paths: list[str] = []
    for key, raw in raw_files.items():
        if not isinstance(raw, dict) or set(raw) != {
            "path",
            "size",
            "stock_sha256",
            "owned_sha256",
        }:
            raise ValueError(f"invalid compendium source contract {key}")
        path = raw["path"]
        size = raw["size"]
        digest = raw["stock_sha256"]
        if (
            not isinstance(path, str)
            or type(size) is not int
            or size <= 0
            or not isinstance(digest, str)
            or len(digest) != 64
        ):
            raise ValueError(f"invalid compendium source contract {key}")
        files[key] = raw
        paths.append(path)
    return files, tuple(paths)


def _source_files(
    supplied: Mapping[str, bytes] | None,
) -> tuple[Mapping[str, bytes], Mapping[str, str]]:
    contracts, paths = _source_manifest()
    if supplied is None:
        validated = validate_source(load_catalog()["compendium"])
        raw = read_source_files(validated, paths)
        source = {path: raw[path] for path in paths}
    else:
        source = dict(supplied)
        if set(source) != set(paths):
            raise ValueError("supplied compendium source target set drifted")
    inputs: dict[str, str] = {}
    for key, contract in contracts.items():
        path = str(contract["path"])
        data = source[path]
        digest = _sha256(data)
        if len(data) != contract["size"] or digest != contract["stock_sha256"]:
            raise ValueError(f"compendium source {path} differs from verified retail")
        inputs[f"compendium:{path}"] = digest
    return MappingProxyType(source), MappingProxyType(inputs)


def _corpus_ids(path: Path) -> tuple[str, ...]:
    rows = _read_json(path)
    if not isinstance(rows, list):
        raise ValueError(f"invalid compendium physical corpus {path}")
    result: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError(f"invalid compendium physical corpus {path}[{index}]")
        result.append(row["id"])
    if len(result) != len(set(result)):
        raise ValueError(f"duplicate compendium physical id in {path}")
    return tuple(result)


def _translations() -> tuple[
    Mapping[str, str],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    physical = load_physical_record_files(CORPUS_FILES)
    profile_ids, demon_ids, ability_ids, race_ids = map(_corpus_ids, CORPUS_FILES)
    all_ids = set(profile_ids) | set(demon_ids) | set(ability_ids) | set(race_ids)
    if (
        len(profile_ids) != 876
        or len(demon_ids) != DEMON_COUNT
        or len(ability_ids) != ABILITY_COUNT
        or len(race_ids) != RACE_COUNT
        or set(physical) != all_ids
    ):
        raise ValueError("compendium physical text inventory drifted")
    unresolved: set[str] = set()
    translations: dict[str, str] = {}
    expected_assets = {
        "demon_compendium.json": PurePosixPath("demons.json"),
        "demons.json": PurePosixPath("demons.json"),
        "races.json": PurePosixPath("races.json"),
        "magic.json": PurePosixPath("magic.json"),
        "skills.json": PurePosixPath("skills.json"),
    }
    for path in BINDING_FILES:
        document = _read_json(path)
        if not isinstance(document, dict):
            raise ValueError(f"invalid compendium binding {path}")
        asset = PurePosixPath(str(document.get("asset", "")))
        if asset != expected_assets[path.name]:
            raise ValueError(f"compendium binding asset drifted: {path.name}")
        records = document.get("records")
        variants = document.get("variants", {})
        raw_unresolved = document.get("unresolved", {})
        if not all(
            isinstance(value, dict)
            for value in (records, variants, raw_unresolved)
        ):
            raise ValueError(f"invalid compendium binding inventory {path}")
        unresolved.update(
            physical_id
            for physical_id in raw_unresolved
            if physical_id.startswith("compendium.")
        )
        catalog = load_asset(asset)
        for physical_id, asset_ref in records.items():
            if physical_id not in all_ids:
                continue
            if physical_id in translations:
                raise ValueError(
                    f"compendium physical record has two owners: {physical_id}"
                )
            _reference, translation, _reviewed = catalog.field(asset_ref).resolve(
                variants.get(physical_id)
            )
            if translation:
                translations[physical_id] = translation
    if unresolved != set(UNRESOLVED_IDS):
        raise ValueError("compendium unresolved inventory drifted")
    required = all_ids - unresolved
    if set(translations) != required:
        raise ValueError("compendium authored translation coverage drifted")
    return MappingProxyType(translations), profile_ids, demon_ids, ability_ids, race_ids


def _font() -> tuple[bytes, FontMetrics, dict[str, int], dict[str, int]]:
    try:
        font = FONT8_PATH.read_bytes()
        metrics = FontMetrics.load(FONT8_METRICS_PATH)
    except FileNotFoundError as error:
        raise ValueError("generated game FONT8 inputs are missing") from error
    config = _configuration()
    if _sha256(font) != config.inputs["font8_sha256"]:
        raise ValueError("compendium FONT8 differs from its configured input")
    metrics_bytes = FONT8_METRICS_PATH.read_bytes()
    if _sha256(metrics_bytes) != config.inputs["font8_metrics_sha256"]:
        raise ValueError("compendium FONT8 metrics differ from configured input")
    codes = {text: glyph.code for text, glyph in metrics.by_text.items()}
    advances = {text: glyph.advance for text, glyph in metrics.by_text.items()}
    advances[";"] = max(advances[":"], advances[","])
    return font, metrics, codes, advances


def _align(value: int, boundary: int = 2) -> int:
    return (value + boundary - 1) & -boundary


def _runtime(
    codec: CompactCodec,
    font: bytes,
    codes: Mapping[str, int],
    advances: Mapping[str, int],
) -> _Runtime:
    dictionary_pool = bytearray()
    offsets = bytearray()
    for entry in codec.dictionary:
        if len(dictionary_pool) > 0xFFFF:
            raise ValueError("compendium dictionary pool exceeds u16 offsets")
        offsets.extend(struct.pack(">H", len(dictionary_pool)))
        dictionary_pool.extend(entry.encode("ascii"))
        dictionary_pool.append(0)
    embedded = build_embedded_font(font, codes, advances)
    source = ASSEMBLY_PATH.read_text(encoding="utf-8")

    probe_symbols = {
        "COMPACT_MARKER": 0x8000,
        "ORIGINAL_DRAW": ORIGINAL_DRAW,
        "FONT_BASE": FONT_BASE,
        "SAVED_FONT": SAVED_FONT,
        "ROW_CODES": ROW_CODES,
        "EXTENDED_TABLE": RUNTIME_ADDRESS,
        "DICTIONARY_OFFSETS": RUNTIME_ADDRESS,
        "DICTIONARY_POOL": RUNTIME_ADDRESS,
        "FONT_BITMAPS": RUNTIME_ADDRESS,
        "FONT_WIDTHS": RUNTIME_ADDRESS,
    }
    try:
        probe = assemble(source, RUNTIME_ADDRESS, probe_symbols)
    except AssemblyError as error:
        raise ValueError(f"cannot assemble compendium renderer: {error}") from error

    cursor = _align(len(probe.data), 2)
    extended_offset = cursor
    cursor += len(EXTENDED_CHARACTERS)
    cursor = _align(cursor, 2)
    offsets_offset = cursor
    cursor += len(offsets)
    pool_offset = cursor
    cursor += len(dictionary_pool)
    bitmap_offset = cursor
    cursor += len(embedded.bitmaps)
    widths_offset = cursor
    cursor += len(embedded.advances)
    symbols = {
        **probe_symbols,
        "EXTENDED_TABLE": RUNTIME_ADDRESS + extended_offset,
        "DICTIONARY_OFFSETS": RUNTIME_ADDRESS + offsets_offset,
        "DICTIONARY_POOL": RUNTIME_ADDRESS + pool_offset,
        "FONT_BITMAPS": RUNTIME_ADDRESS + bitmap_offset,
        "FONT_WIDTHS": RUNTIME_ADDRESS + widths_offset,
    }
    try:
        assembly = assemble(source, RUNTIME_ADDRESS, symbols)
    except AssemblyError as error:
        raise ValueError(f"cannot link compendium renderer: {error}") from error
    if len(assembly.data) != len(probe.data):
        raise ValueError("compendium renderer changed size while linking")

    used = bytearray(cursor)
    used[: len(assembly.data)] = assembly.data
    used[extended_offset : extended_offset + len(EXTENDED_CHARACTERS)] = (
        EXTENDED_CHARACTERS.encode("ascii")
    )
    used[offsets_offset : offsets_offset + len(offsets)] = offsets
    used[pool_offset : pool_offset + len(dictionary_pool)] = dictionary_pool
    used[bitmap_offset : bitmap_offset + len(embedded.bitmaps)] = embedded.bitmaps
    used[widths_offset : widths_offset + len(embedded.advances)] = embedded.advances
    if len(used) > RUNTIME_CAPACITY:
        raise ValueError(
            f"compendium runtime uses {len(used)} bytes, capacity {RUNTIME_CAPACITY}"
        )
    return _Runtime(
        bytes(used) + bytes(RUNTIME_CAPACITY - len(used)),
        len(used),
        MappingProxyType({"compact_draw": assembly.labels["compact_draw"]}),
    )


def _a_dic_tables(
    source: bytes,
    translations: Mapping[str, str],
    codec: CompactCodec,
    demon_ids: tuple[str, ...],
    ability_ids: tuple[str, ...],
    race_ids: tuple[str, ...],
) -> Mapping[str, bytes]:
    demons = b"".join(codec.encode_row(translations[record], 8) for record in demon_ids)
    abilities = b"".join(
        codec.encode_row(translations[record], 8) for record in ability_ids
    )
    race_source = source[RACE_TABLE_OFFSET : RACE_TABLE_OFFSET + RACE_COUNT * 6]
    races = bytearray()
    for index, record in enumerate(race_ids):
        if record in UNRESOLVED_IDS:
            races.extend(race_source[index * 6 : index * 6 + 6])
        else:
            races.extend(codec.encode_row(translations[record], 3))
    if len(demons) != DEMON_COUNT * 16 or len(abilities) != ABILITY_COUNT * 16:
        raise AssertionError("compendium table compiler changed fixed geometry")
    return MappingProxyType(
        {
            "demon_names": demons,
            "race_names": bytes(races),
            "ability_names": abilities,
        }
    )


def _a_dic_patches(
    config: PatchRecipeConfiguration,
    source: bytes,
    runtime: _Runtime,
    tables: Mapping[str, bytes],
) -> tuple[Patch, ...]:
    patches: list[Patch] = []
    for recipe in config.patches[TARGET]:
        expected = resolve_recipe_expected(recipe, source, LOAD_ADDRESS)
        replacement_recipe = recipe.replacement
        if recipe.name == "runtime_arena":
            replacement = runtime.data
        elif replacement_recipe.kind == "generated":
            replacement = tables[recipe.name]
        elif replacement_recipe.kind == "linked_pointer":
            replacement = struct.pack(">I", runtime.links[replacement_recipe.link])
        else:
            raise ValueError(f"unsupported compendium recipe {recipe.name}")
        if len(replacement) != len(expected):
            raise ValueError(
                f"compendium {recipe.name} generated {len(replacement)} bytes, "
                f"expected {len(expected)}"
            )
        patches.append(
            Patch(recipe.group, recipe.name, recipe.address, expected, replacement)
        )
    return tuple(patches)


def build_compendium_text(
    sources: Mapping[str, bytes] | None = None,
) -> CompendiumTextBuild:
    """Build all currently proved Akuma Zensho text consumers atomically."""
    config = _configuration()
    source_files, source_inputs = _source_files(sources)
    translations, profile_ids, demon_ids, ability_ids, race_ids = _translations()
    font, _metrics, codes, advances = _font()
    codec = CompactCodec(build_dictionary(translations.values()))
    runtime = _runtime(codec, font, codes, advances)

    a_dic_source = source_files[TARGET]
    tables = _a_dic_tables(
        a_dic_source, translations, codec, demon_ids, ability_ids, race_ids
    )
    a_dic_patches = _a_dic_patches(config, a_dic_source, runtime, tables)
    outputs: dict[str, bytes] = {
        TARGET: apply_patches(a_dic_source, LOAD_ADDRESS, a_dic_patches)
    }
    patches: dict[str, tuple[Patch, ...]] = {TARGET: a_dic_patches}

    by_profile: dict[str, dict[str, str]] = {}
    for record in profile_ids:
        parts = record.split(".")
        if len(parts) != 5 or parts[0:2] != ["compendium", "profiles"]:
            raise ValueError(f"invalid compendium profile id {record}")
        by_profile.setdefault(parts[2], {})[parts[4]] = translations[record]
    if len(by_profile) != 292:
        raise ValueError("compendium profile target inventory drifted")

    for profile, fields in by_profile.items():
        path = f"{profile.upper()}.DAT"
        source = source_files[path]
        tail = encode_profile_tail(
            fields["origin"],
            fields["summary"],
            fields["detail"],
            codec,
            advances,
        )
        expected = source[
            PROFILE_TAIL_OFFSET : PROFILE_TAIL_OFFSET + PROFILE_TAIL_BYTES
        ]
        patch = Patch(
            "compendium.profile_text",
            "profile_tail",
            PROFILE_TAIL_OFFSET,
            expected,
            tail,
        )
        patches[path] = (patch,)
        outputs[path] = apply_patches(source, 0, (patch,))

    if set(outputs) != set(source_files):
        raise ValueError("compendium output target inventory drifted")
    return CompendiumTextBuild(
        MappingProxyType(outputs),
        MappingProxyType(patches),
        ASSET_FILES,
        (ASSEMBLY_PATH,),
        RUNTIME_INPUT_FILES,
        source_inputs,
        runtime.used_size,
        RUNTIME_CAPACITY,
        (RuntimeArena(RUNTIME_ADDRESS, runtime.used_size, RUNTIME_CAPACITY),),
        UNRESOLVED_IDS,
    )


__all__ = [
    "ASSEMBLY_PATH",
    "BUILD_PATH",
    "CONFIG_PATH",
    "CompendiumTextBuild",
    "OUTPUT_ROOT",
    "TARGET",
    "build_compendium_text",
]
