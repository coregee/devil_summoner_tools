"""Compose NORMCOM's detailed status interface from authored text assets."""

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
from engine.core.sh2 import AssemblyError, assemble_file
from engine.shared.font8 import font8_tables
from engine.shared.status_layout import (
    StatusLabels,
    StatusTemplates,
    derived_rows as _derived_rows,
    direct_color_node as _direct_color_node,
    direct_color_row as _direct_color_row,
    load_font16_metrics,
    load_status_labels as _status_labels,
    load_status_templates as _status_templates,
    load_stock_latin_codes,
    node_background,
    status_atlas_tile as _status_atlas_tile,
    status_mask as _status_mask,
    validate_shiftable_bitmap as _validate_shiftable_bitmap,
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
from text.util.surfaces import load_surfaces


ENGINE_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = ENGINE_ROOT.parent
PROJECT_ROOT = SATURN_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "status_ui.json"
FONT_ROOT = SATURN_ROOT / "font" / "generated" / "game"
FONT8_PATH = FONT_ROOT / "FONT8.FON"
FONT8_METRICS_PATH = FONT_ROOT / "FONT8_metrics.json"
FONT16_PATH = FONT_ROOT / "FONT16.FON"
FONT16_METRICS_PATH = FONT_ROOT / "FONT16_metrics.json"
TEXT_GENERATED_ROOT = SATURN_ROOT / "text" / "generated" / "game"
DVLNAME_PATH = TEXT_GENERATED_ROOT / "DVLNAME.DAT"

STATUS_ASSET_PATH = ASSET_ROOT / "ui" / "status.json"
RACE_ASSET_PATH = ASSET_ROOT / "races.json"
AFFINITY_ASSET_PATH = ASSET_ROOT / "affinities.json"
DEMON_ASSET_PATH = ASSET_ROOT / "demons.json"
CHARACTER_ASSET_PATH = ASSET_ROOT / "characters.json"
ALIGNMENT_ASSET_PATH = ASSET_ROOT / "terminology" / "alignments.json"
COMMAND_ASSET_PATH = ASSET_ROOT / "battle" / "commands.json"
ASSET_FILES = (
    STATUS_ASSET_PATH,
    RACE_ASSET_PATH,
    AFFINITY_ASSET_PATH,
    DEMON_ASSET_PATH,
    CHARACTER_ASSET_PATH,
    ALIGNMENT_ASSET_PATH,
    COMMAND_ASSET_PATH,
)
BINDING_FILES = tuple(
    BINDING_ROOT / name
    for name in (
        "affinities.json",
        "alignments.json",
        "battle_commands.json",
        "characters.json",
        "demons.json",
        "races.json",
        "status.json",
    )
)
CORPUS_FILES = tuple(
    CORPUS_ROOT / relative
    for relative in (
        "compendium/addressed/race_names.json",
        "compendium/fixed/demon_names.json",
        "game/addressed/battle_command_labels.json",
        "game/addressed/combat_analysis_affinities.json",
        "game/addressed/da3d_analyze.json",
        "game/addressed/normcom_status_ascii.json",
        "game/addressed/normcom_tables.json",
        "game/eve/shopsmp.json",
        "game/fixed/charname.json",
        "game/fixed/dvlname.json",
    )
)
RUNTIME_INPUT_FILES = (
    FONT8_PATH,
    FONT8_METRICS_PATH,
    FONT16_PATH,
    FONT16_METRICS_PATH,
    DVLNAME_PATH,
    SATURN_ROOT / "text" / "config" / "surfaces.json",
    SATURN_ROOT / "rom" / "discs.json",
    *BINDING_FILES,
    *CORPUS_FILES,
)

TARGET = "NORMCOM.BIN"
LOAD_ADDRESS = 0x06020000
RUNTIME_CAVE = 0x06022000
RUNTIME_DATA = 0x06022800
RUNTIME_LIMIT = 0x06025F34
LIGHT_AXIS_RECORD = RUNTIME_DATA - 4
WRAPPER_CAVE = 0x06021480
ATLAS_ADDRESS = 0x06021800
EQUIPMENT_LABEL_CAVE_LIMIT = WRAPPER_CAVE
COMP_PANEL_CAVE = RUNTIME_LIMIT

STATUS_SOURCE_PTR = 0x060390FC
STATUS_STOCK_ATLAS = 0x00219950
STATUS_MASK_PTR = 0x06039ECC
STATUS_STOCK_MASKS = 0x06074F78
BUILD_PANEL = 0x0603A064
BUILD_ATLAS = 0x06030B60
BUILD_ATLAS_TILE = 0x06038FBC
PANEL_ATLAS_CACHE = 0x06075FF8
FONT16_DRAWER = 0x060391E4
FONT8_DRAWER = 0x06039250
FONT8_GLYPH_DRAWER = 0x06038DA0
FONT16_BITMAP = 0x0021A000
FONT8_BITMAP = 0x00219150
CURRENT_PARTY_TYPE = 0x060812BC
HUMAN_AUTO_STATE = 0x060812D4
DEMON_AUTO_STATE = 0x0607B9CC
CURRENT_NAME_PTR = 0x0607B980
PLAYER_STATUS_NAME = 0x0023FE14
RACE_SOURCE = 0x0603F974
AFFINITY_SOURCE = 0x0603FA76
AFFINITY_SELECTOR = 0x06081170
MAGNAME_BASE = 0x0022F7A0
MAGNAME_FIRST = MAGNAME_BASE + 4
MAGNAME_END = 0x00235740
ITEMNAME_BASE = 0x00228C00
ITEMNAME_FIRST = ITEMNAME_BASE + 4
ITEMNAME_END = MAGNAME_BASE
MAGNAME_POINTER_OFFSET = 0x5A
ITEM_ICON_DRAWER = 0x060396CC

NODE_BITMAP_OFFSET = 0x2076C
RACE_COUNT = 43
AFFINITY_COUNT = 96
RUNTIME_AFFINITY_COUNT = 66
DEMON_COUNT = 319
CHARACTER_COUNT = 6
AUTO_ACTION_START_X = 40
AUTO_ACTION_END_X = 110
PARTY_ALIGNMENT_SOURCES = {
    "law": 0x06036574,
    "neutral": 0x06036578,
    "chaos": 0x06036580,
}
AFFINITY_SURFACE_WIDTH = 128
AFFINITY_MAX_ADVANCE = AFFINITY_SURFACE_WIDTH - 1
AFFINITY_ADVANCE_OVERRIDES = {" ": 1, ",": 2, ":": 2}

ASCII_RECORDS = (
    ("experience", 0x060332DC, 4),
    ("level", 0x060335B0, 4),
    ("personality_type", 0x06033DE8, 8),
    ("hit_points", 0x06034298, 4),
    ("magic_points", 0x060342A4, 4),
    ("control_first", 0x06035DA0, 4),
    ("control_second", 0x06035DA4, 4),
    ("control_third", 0x06035DA8, 4),
    ("control_fourth", 0x06035DAC, 4),
    ("control_error", 0x06035DB0, 4),
    ("control", 0x06035DE4, 6),
    ("next_experience", 0x06035FC4, 8),
    ("summon_cost", 0x06035FCC, 4),
    ("alignment_law", 0x06036574, 4),
    ("alignment_neutral", 0x06036578, 8),
    ("alignment_chaos", 0x06036580, 8),
    ("command_sword", 0x06036594, 8),
    ("command_attack", 0x0603659C, 8),
    ("command_gun", 0x060365A4, 4),
    ("command_guard", 0x060365A8, 8),
    ("command_go", 0x060365B0, 4),
    ("command_offense", 0x060365B4, 8),
    ("command_defense", 0x060365BC, 8),
    ("auto_setting", 0x060365C4, 6),
)
ASCII_PHYSICAL_IDS = {
    address: f"game.normcom_status_ascii.o{address - LOAD_ADDRESS:06x}"
    for _name, address, _capacity in ASCII_RECORDS
}

@dataclass(frozen=True, slots=True)
class RuntimeBuild:
    data: bytes
    links: Mapping[str, int]
    masks_address: int
    light_diverges: bool


@dataclass(frozen=True, slots=True)
class StatusUiBuild:
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
        raise ValueError(f"missing status UI input: {path}") from error


def _font16_metrics() -> tuple[bytes, dict[str, int]]:
    return load_font16_metrics(FONT16_METRICS_PATH)


def _stock_latin_codes() -> dict[str, int]:
    return load_stock_latin_codes(FONT8_METRICS_PATH)


def _validate_surfaces() -> None:
    surfaces = load_surfaces()
    expected = {
        "status.skill_name": ("font8", 1, "pixels", 80),
        "status.affinity": ("font8", 2, "pixels", 128),
        "status.base_stat_label": ("font8", 1, "pixels", 12),
        "status.derived_stat_label": ("font8", 1, "pixels", 46),
        "status.loyalty_label": ("font8", 1, "pixels", 38),
    }
    for name, geometry in expected.items():
        layout = surfaces.surface(name).en
        actual = (layout.font, layout.rows, layout.width.unit, layout.width.value)
        if actual != geometry:
            raise ValueError(f"{name} geometry changed")


def _layout_data(
    base: bytes,
    font8: bytes,
    stock_font16: bytes,
    widths8: bytes,
    codes8: Mapping[str, int],
    labels: StatusLabels,
) -> tuple[dict[str, bytes], bytes]:
    rows_config = _derived_rows(labels)
    chunks: list[str] = []
    for row in rows_config:
        for chunk in row:
            if chunk not in chunks:
                chunks.append(chunk)
    if len(chunks) > 9:
        raise ValueError("status atlas has room for at most nine derived chunks")
    chunks.extend([""] * (9 - len(chunks)))
    atlas_labels = (*labels.base, *chunks, *("" for _ in range(6)))
    if len(atlas_labels) != 21:
        raise ValueError("status atlas must contain 21 tiles")
    atlas = b"".join(
        _status_atlas_tile(text, font8, widths8, codes8)
        for text in atlas_labels
    )
    masks = b"".join(
        _status_mask(atlas[index * 0x48 : (index + 1) * 0x48])
        for index in range(21)
    )
    chunk_ids = {chunk: 6 + index for index, chunk in enumerate(chunks) if chunk}
    rows = bytearray()
    counts = bytearray()
    x_positions = bytearray()
    for row in rows_config:
        ids = [chunk_ids[chunk] for chunk in row]
        rows.extend(struct.pack(">4H", *(ids + [0] * (4 - len(ids)))))
        counts.extend(struct.pack(">H", len(ids)))
        x_positions.extend(struct.pack(">H", 12 if len(ids) == 2 else 18))

    background = node_background(
        base[NODE_BITMAP_OFFSET : NODE_BITMAP_OFFSET + 16 * 16 * 2],
        stock_font16,
    )
    nodes = b"".join(
        _direct_color_node(label, font8, widths8, codes8, background)
        for label in labels.base
    )
    row_bitmap = b"".join(
        _direct_color_row(" ".join(row), font8, widths8, codes8)
        for row in rows_config
    )
    personality = b"".join(
        _direct_color_row(label, font8, widths8, codes8, 40)
        for label in labels.personality
    )
    return (
        {
            "font12_atlas": atlas,
            "derived_rows": bytes(rows),
            "derived_counts": bytes(counts),
            "derived_x_positions": bytes(x_positions),
            "parameter_nodes": nodes,
            "parameter_rows": row_bitmap,
            "generic_attack_label": _direct_color_row(
                labels.attack, font8, widths8, codes8
            ),
            "generic_accuracy_label": _direct_color_row(
                labels.accuracy, font8, widths8, codes8
            ),
            "personality_labels": personality,
        },
        masks,
    )


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


def _encode_party_alignment_ascii(text: str) -> bytes:
    try:
        encoded = text.encode("ascii")
    except UnicodeEncodeError as error:
        raise ValueError(
            f"party alignment must use the original ASCII FONT8 alphabet: {text!r}"
        ) from error
    if any(
        code != 0x20
        and not 0x30 <= code <= 0x39
        and not 0x41 <= code <= 0x5A
        and not 0x61 <= code <= 0x7A
        for code in encoded
    ):
        raise ValueError(
            f"party alignment contains a character unsupported by the original "
            f"ASCII FONT8 drawer: {text!r}"
        )
    maximum_cells = (AUTO_ACTION_END_X - AUTO_ACTION_START_X) // 8
    if not encoded or len(encoded) > maximum_cells:
        raise ValueError(
            f"party alignment exceeds {maximum_cells} original FONT8 cells: {text!r}"
        )
    return encoded + b"\0"


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
    # DVLNAME records are eight bytes apart.
    demon_ids = [f"game.dvlname.o{index * 8:06x}.text" for index in range(DEMON_COUNT)]
    demon_values = _bound_translations(
        ("game.dvlname.",), set(demon_ids), (BINDING_ROOT / "demons.json",)
    )
    demons = [demon_values[physical_id] for physical_id in demon_ids]
    character_ids = [
        f"game.charname.o{index * 8:06x}.text" for index in range(CHARACTER_COUNT)
    ]
    character_values = _bound_translations(
        ("game.charname.",),
        set(character_ids),
        (BINDING_ROOT / "characters.json",),
    )
    characters = [character_values[physical_id] for physical_id in character_ids]
    return races, affinities, demons, characters


def _party_alignment_terms() -> tuple[str, str, str]:
    alignments = load_asset("terminology/alignments.json")
    values: list[str] = []
    for name in PARTY_ALIGNMENT_SOURCES:
        _reference, value, _reviewed = alignments.field(
            f"{name}.party_label"
        ).resolve()
        values.append(value)
    return values[0], values[1], values[2]


def _source_assets() -> tuple[bytes, bytes, bytes]:
    catalog = load_catalog()
    try:
        game = catalog["game"]
    except KeyError as error:
        raise ValueError("disc catalog has no game source") from error
    source = read_source_files(
        validate_source(game, verify_hashes=False),
        ("DVLNAME.DAT", "CHARNAME.DAT", "FONT16.FON"),
    )
    return source["DVLNAME.DAT"], source["CHARNAME.DAT"], source["FONT16.FON"]


def _built_charname(
    stock: bytes,
    character_names: list[str],
    metrics8: FontMetrics,
) -> bytes:
    if len(stock) != CHARACTER_COUNT * 8:
        raise ValueError("stock CHARNAME has the wrong size")
    # Kyouji's compact English record is the only CHARNAME row repacked by the
    # mature Saturn build. Other status names resolve from their stock hash.
    glyphs = metrics8.segment_output(character_names[2])
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
) -> list[int]:
    try:
        glyphs = [codes[character] for character in text]
    except KeyError as error:
        raise ValueError(
            f"unsupported {context} FONT16 character in {text!r}: "
            f"{error.args[0]!r}"
        ) from error
    if sum(widths[glyph] for glyph in glyphs) > 224:
        raise ValueError(f"{context} exceeds 224px: {text!r}")
    return glyphs


def _build_name_lookup(hashes: Mapping[int, str], resolve_pointer) -> bytes:
    return b"".join(
        struct.pack(">II", key, resolve_pointer(name))
        for key, name in sorted(hashes.items())
    )


def _runtime_english_data(
    widths8: bytes,
    codes8: Mapping[str, int],
    widths16: bytes,
    codes16: Mapping[str, int],
    font8: bytes,
    font16: bytes,
    races: list[str],
    affinities: list[str],
    party_alignments: tuple[str, str, str],
    demon_names: list[str],
    character_names: list[str],
    stock_dvlname: bytes,
    english_dvlname: bytes,
    stock_charname: bytes,
    english_charname: bytes,
) -> tuple[bytes, dict[str, int]]:
    _validate_shiftable_bitmap(font16, widths16, 32, 2, "status FONT16")
    _validate_shiftable_bitmap(font8, widths8, 8, 1, "status FONT8")
    _validate_affinity_font8(font8, widths8, codes8)
    if len(races) != RACE_COUNT or len(affinities) < RUNTIME_AFFINITY_COUNT:
        raise ValueError("status terminology inventory changed")
    if len(party_alignments) != len(PARTY_ALIGNMENT_SOURCES):
        raise ValueError("party-alignment terminology inventory changed")

    data = bytearray()

    def align(alignment: int = 4) -> None:
        while (RUNTIME_DATA + len(data)) % alignment:
            data.append(0)

    def reserve(size: int) -> tuple[int, int]:
        align()
        offset = len(data)
        data.extend(bytes(size))
        return offset, RUNTIME_DATA + offset

    widths_offset, widths_address = reserve(len(widths16))
    data[widths_offset : widths_offset + len(widths16)] = widths16
    widths8_offset, widths8_address = reserve(len(widths8))
    data[widths8_offset : widths8_offset + len(widths8)] = widths8
    race_offset, race_address = reserve(RACE_COUNT * 4)
    affinity_offset, affinity_address = reserve(RUNTIME_AFFINITY_COUNT * 8)

    hashes: dict[int, str] = {}
    _add_name_hashes(
        hashes, (stock_dvlname, english_dvlname), demon_names, "status demon name"
    )
    _add_name_hashes(
        hashes,
        (stock_charname, english_charname),
        character_names,
        "status character name",
    )
    lookup_offset, lookup_address = reserve(len(hashes) * 8)
    if lookup_address & 3:
        raise ValueError("status name lookup is not longword-aligned")

    font16_texts: list[str] = []
    for text in (*races, *hashes.values()):
        if text not in font16_texts:
            font16_texts.append(text)
    font16_blobs = {
        text: struct.pack(
            f">{len(glyphs) + 1}H", *glyphs, 0x8000
        )
        for text in font16_texts
        for glyphs in [_font16_glyphs(text, codes16, widths16, "status")]
    }
    align(2)
    font16_pool_address = RUNTIME_DATA + len(data)
    font16_pool = bytearray()
    font16_offsets: dict[str, int] = {}
    font16_owners: list[str] = []
    for text in sorted(font16_texts, key=lambda value: (-len(font16_blobs[value]), value)):
        blob = font16_blobs[text]
        offset = next(
            (
                font16_offsets[owner] + len(font16_blobs[owner]) - len(blob)
                for owner in font16_owners
                if font16_blobs[owner].endswith(blob)
            ),
            None,
        )
        if offset is None:
            offset = len(font16_pool)
            font16_pool.extend(blob)
            font16_owners.append(text)
        font16_offsets[text] = offset
    data.extend(font16_pool)

    runtime_affinities = affinities[:RUNTIME_AFFINITY_COUNT]
    affinity_texts = [""]
    for text in runtime_affinities:
        for line in text.split("{n}"):
            if line not in affinity_texts:
                affinity_texts.append(line)
    affinity_blobs = {
        text: _encode_affinity_font8(text, widths8, codes8)
        for text in affinity_texts
    }
    affinity_pool_address = RUNTIME_DATA + len(data)
    affinity_pool = bytearray()
    affinity_offsets: dict[str, int] = {}
    affinity_owners: list[str] = []
    for text in sorted(
        affinity_texts, key=lambda value: (-len(affinity_blobs[value]), value)
    ):
        blob = affinity_blobs[text]
        offset = next(
            (
                affinity_offsets[owner] + len(affinity_blobs[owner]) - len(blob)
                for owner in affinity_owners
                if affinity_blobs[owner].endswith(blob)
            ),
            None,
        )
        if offset is None:
            offset = len(affinity_pool)
            affinity_pool.extend(blob)
            affinity_owners.append(text)
        affinity_offsets[text] = offset
    data.extend(affinity_pool)

    party_alignment_addresses: dict[str, int] = {}
    for name, text in zip(PARTY_ALIGNMENT_SOURCES, party_alignments, strict=True):
        party_alignment_addresses[name] = RUNTIME_DATA + len(data)
        data.extend(_encode_party_alignment_ascii(text))

    def font16_pointer(text: str) -> int:
        return font16_pool_address + font16_offsets[text]

    def affinity_pointer(text: str) -> int:
        return affinity_pool_address + affinity_offsets[text]

    for index, text in enumerate(races):
        struct.pack_into(">I", data, race_offset + index * 4, font16_pointer(text))
    affinity_pointer("")
    for index, text in enumerate(runtime_affinities):
        lines = text.split("{n}")
        if len(lines) > 2:
            raise ValueError(f"status affinity {index} exceeds two rows")
        lines += [""] * (2 - len(lines))
        struct.pack_into(
            ">II",
            data,
            affinity_offset + index * 8,
            *(affinity_pointer(line) for line in lines),
        )
    lookup = _build_name_lookup(hashes, font16_pointer)
    data[lookup_offset : lookup_offset + len(lookup)] = lookup
    addresses = {
        "widths16": widths_address,
        "widths8": widths8_address,
        "race_table": race_address,
        "affinity_table": affinity_address,
        "name_lookup": lookup_address,
        "name_count": len(hashes),
    }
    addresses.update(
        {
            f"party_alignment_{name}": address
            for name, address in party_alignment_addresses.items()
        }
    )
    return bytes(data), addresses


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
    for index in (22,):
        encoded = _encode_mirror_record(
            races[index],
            codes16,
            3,
            separator_newline=False,
            optional_terminator=True,
        )
        if encoded is None:
            raise ValueError(f"authored race mirror {index} exceeds three words")
        output[f"races_{index:03d}"] = encoded

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
        raise ValueError("mature NORMCOM mirror inventory changed")
    return output


def _ascii_prefix(value: str, name: str) -> str:
    if "{" not in value:
        return value
    prefix, _separator, _remainder = value.partition("{")
    if not prefix.endswith(" ") or prefix.endswith("  "):
        raise ValueError(f"status.{name} needs exactly one layout boundary space")
    return prefix[:-1]


def _encode_ascii(value: str, capacity: int, context: str) -> bytes:
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError as error:
        raise ValueError(f"{context} must use stock ASCII cells") from error
    if not encoded or len(encoded) >= capacity:
        raise ValueError(f"{context} exceeds its {capacity - 1}-cell capacity")
    return encoded.ljust(capacity, b"\0")


def _ascii_data(templates: StatusTemplates) -> dict[str, bytes]:
    required = set(ASCII_PHYSICAL_IDS.values())
    translations = _bound_translations(
        ("game.normcom_status_ascii.",),
        required,
        tuple(
            BINDING_ROOT / name
            for name in ("alignments.json", "battle_commands.json", "status.json")
        ),
    )
    alignment_asset = load_asset("terminology/alignments.json")
    dormant_alignment_records = {
        f"alignment_{name}": alignment_asset.field(
            f"{name}.party_label"
        ).resolve()[0]
        for name in PARTY_ALIGNMENT_SOURCES
    }
    output: dict[str, bytes] = {}
    for name, address, capacity in ASCII_RECORDS:
        value = dormant_alignment_records.get(
            name, translations[ASCII_PHYSICAL_IDS[address]]
        )
        prefix = _ascii_prefix(value, name)
        expected_prefix = templates.prefixes.get(name)
        if expected_prefix is not None and prefix != expected_prefix:
            raise ValueError(f"status.{name} template and physical binding disagree")
        output[name] = _encode_ascii(prefix, capacity, f"status.{name}")
    return output


def _axis_data() -> tuple[dict[str, bytes], str, str]:
    alignments = load_asset("terminology/alignments.json")

    def axis(name: str) -> str:
        _reference, value, _reviewed = alignments.field(f"{name}.axis_label").resolve()
        try:
            encoded = value.encode("ascii")
        except UnicodeEncodeError as error:
            raise ValueError(f"{name} axis label must use one ASCII cell") from error
        if len(encoded) != 1:
            raise ValueError(f"{name} axis label must use exactly one cell")
        return value

    law = axis("law")
    light = axis("light")
    chaos = axis("chaos")
    dark = axis("dark")
    neutral = axis("neutral")
    return (
        {
            "axis_law": law.encode("ascii") + b"\0\0\0",
            "axis_chaos": chaos.encode("ascii") + b"\0\0\0",
            "axis_dark": dark.encode("ascii") + b"\0\0\0",
            "axis_neutral": neutral.encode("ascii") + b"\0",
        },
        law,
        light,
    )


def _template_data(
    templates: StatusTemplates,
    codes8: Mapping[str, int],
    stock_codes: Mapping[str, int],
) -> dict[str, bytes]:
    separator = stock_codes.get(templates.hp_mp_separator)
    if separator is None:
        separator = codes8.get(templates.hp_mp_separator)
    if separator is None or not 0 <= separator <= 0xFF:
        raise ValueError(
            f"HP/MP separator {templates.hp_mp_separator!r} is absent from FONT8"
        )
    return {
        "human_hp_mp_separator": struct.pack(">H", separator),
        "demon_hp_mp_separator": struct.pack(">H", separator),
    }


def _assembled(source: Path, address: int, symbols: Mapping[str, int]) -> bytes:
    try:
        result = assemble_file(source, address, dict(symbols))
    except AssemblyError as error:
        raise ValueError(f"{source.relative_to(ENGINE_ROOT)}: {error}") from error
    if result.warnings:
        raise ValueError(
            f"{source.relative_to(ENGINE_ROOT)}: assembly warnings: {result.warnings}"
        )
    return result.data


def _source_paths(
    recipe: PatchRecipe, expected: tuple[str, ...]
) -> tuple[Path, ...]:
    actual = tuple(
        source.relative_to(ASSEMBLY_ROOT).as_posix()
        for source in recipe.replacement.sources
    )
    if actual != expected:
        raise ValueError(f"{recipe.group}/{recipe.name}: assembly sources changed")
    return recipe.replacement.sources


def _runtime_payload(
    recipe: PatchRecipe,
    masks: bytes,
    widths8: bytes,
    codes8: Mapping[str, int],
    widths16: bytes,
    codes16: Mapping[str, int],
    font8: bytes,
    font16: bytes,
    races: list[str],
    affinities: list[str],
    party_alignments: tuple[str, str, str],
    demon_names: list[str],
    character_names: list[str],
    stock_dvlname: bytes,
    english_dvlname: bytes,
    stock_charname: bytes,
    english_charname: bytes,
    law_axis: str,
    light_axis: str,
) -> RuntimeBuild:
    sources = _source_paths(
        recipe,
        (
            "status_ui/font16_vwf.s",
            "status_ui/skill_vwf.s",
            "status_ui/auto_action_vwf.s",
            "status_ui/auto_block_ascii.s",
            "status_ui/affinity_font8_vwf.s",
            "status_ui/name_race_dispatcher.s",
            "status_ui/affinity_dispatcher.s",
            "status_ui/stock_icon_wrapper.s",
        ),
    )
    english, addresses = _runtime_english_data(
        widths8,
        codes8,
        widths16,
        codes16,
        font8,
        font16,
        races,
        affinities,
        party_alignments,
        demon_names,
        character_names,
        stock_dvlname,
        english_dvlname,
        stock_charname,
        english_charname,
    )
    data = bytearray(english)
    while (RUNTIME_DATA + len(data)) & 3:
        data.append(0)
    masks_address = RUNTIME_DATA + len(data)
    data.extend(masks)
    dirty_address = RUNTIME_DATA + len(data)
    data.append(0)

    payload = bytearray()

    def append(source: Path, symbols: Mapping[str, int]) -> int:
        while (RUNTIME_CAVE + len(payload)) & 3:
            payload.append(0)
        address = RUNTIME_CAVE + len(payload)
        payload.extend(_assembled(source, address, symbols))
        return address

    font16_vwf = append(
        sources[0],
        {
            "WIDTHS": addresses["widths16"],
            "END_MASK": 0x8000,
            "FONT_BITMAP": FONT16_BITMAP,
            "STOCK": FONT16_DRAWER,
        },
    )
    skill_vwf = append(
        sources[1],
        {
            "ITEM_FIRST": ITEMNAME_FIRST,
            "ITEM_END": ITEMNAME_END,
            "ITEM_BASE": ITEMNAME_BASE,
            "MAGIC_FIRST": MAGNAME_FIRST,
            "MAGIC_END": MAGNAME_END,
            "MAGIC_BASE": MAGNAME_BASE,
            "NAME_POINTER": MAGNAME_POINTER_OFFSET,
            "WIDTHS": addresses["widths8"],
            "FONT_BITMAP": FONT8_BITMAP,
            "STOCK": FONT8_DRAWER,
            "GLYPH": FONT8_GLYPH_DRAWER,
        },
    )
    auto_action_vwf = append(
        sources[2],
        {
            "PARTY_TYPE": CURRENT_PARTY_TYPE,
            "HUMAN_AUTO_STATE": HUMAN_AUTO_STATE,
            "DEMON_AUTO_STATE": DEMON_AUTO_STATE,
            "ITEM_BASE": ITEMNAME_BASE,
            "MAGIC_BASE": MAGNAME_BASE,
            "NAME_POINTER": MAGNAME_POINTER_OFFSET,
            "SPACE_CODE": codes8[" "],
            "END_X": AUTO_ACTION_END_X,
            "WIDTHS": addresses["widths8"],
            "FONT_BITMAP": FONT8_BITMAP,
            "GLYPH": FONT8_GLYPH_DRAWER,
            "STOCK": FONT8_DRAWER,
        },
    )
    affinity_vwf = append(
        sources[4],
        {
            "WIDTHS": addresses["widths8"],
            "FONT_BITMAP": FONT8_BITMAP,
            "GLYPH": FONT8_GLYPH_DRAWER,
            "MAX_WIDTH": AFFINITY_SURFACE_WIDTH,
            "SPACE_CODE": codes8[" "],
            "COLON_CODE": codes8[":"],
            "COMMA_CODE": codes8[","],
        },
    )
    auto_block_ascii = append(
        sources[3],
        {
            "LAW_SOURCE": PARTY_ALIGNMENT_SOURCES["law"],
            "NEUTRAL_SOURCE": PARTY_ALIGNMENT_SOURCES["neutral"],
            "CHAOS_SOURCE": PARTY_ALIGNMENT_SOURCES["chaos"],
            "LAW_TEXT": addresses["party_alignment_law"],
            "NEUTRAL_TEXT": addresses["party_alignment_neutral"],
            "CHAOS_TEXT": addresses["party_alignment_chaos"],
            "STOCK": 0x06039108,
        },
    )
    name_race = append(
        sources[5],
        {
            "RACE_SOURCE": RACE_SOURCE,
            "RACE_TABLE": addresses["race_table"],
            "PARTY_TYPE": CURRENT_PARTY_TYPE,
            "CURRENT_NAME_PTR": CURRENT_NAME_PTR,
            "PLAYER_NAME": PLAYER_STATUS_NAME,
            "NAME_LOOKUP": addresses["name_lookup"],
            "NAME_COUNT": addresses["name_count"],
            "FONT16_VWF": font16_vwf,
            "NAME_VWF": font16_vwf,
            "STOCK": FONT16_DRAWER,
        },
    )
    affinity = append(
        sources[6],
        {
            "SELECTOR": AFFINITY_SELECTOR,
            "SOURCE": AFFINITY_SOURCE,
            "TABLE": addresses["affinity_table"],
            "FONT8_VWF": affinity_vwf,
            "STOCK": FONT16_DRAWER,
        },
    )
    stock_icon = append(
        sources[7],
        {
            "DIRTY": dirty_address,
            "BUILD_ATLAS": BUILD_ATLAS,
            "BUILD_ATLAS_TILE": BUILD_ATLAS_TILE,
            "PANEL_ATLAS_CACHE": PANEL_ATLAS_CACHE,
            "STOCK": ITEM_ICON_DRAWER,
        },
    )
    if RUNTIME_CAVE + len(payload) > LIGHT_AXIS_RECORD:
        raise ValueError("status runtime code overlaps the reserved Light-axis record")
    payload.extend(bytes(RUNTIME_DATA - RUNTIME_CAVE - len(payload)))
    light_diverges = law_axis != light_axis
    if light_diverges:
        light_record = light_axis.encode("ascii") + b"\0\0\0"
        start = LIGHT_AXIS_RECORD - RUNTIME_CAVE
        payload[start : start + 4] = light_record
    payload.extend(data)
    if len(payload) > len(recipe.expected):
        raise ValueError(
            f"status runtime exceeds {len(recipe.expected)} bytes ({len(payload)})"
        )
    payload.extend(bytes(len(recipe.expected) - len(payload)))
    if RUNTIME_CAVE + len(payload) > RUNTIME_LIMIT:
        raise ValueError("status runtime overlaps the COMP party-panel cave")
    return RuntimeBuild(
        bytes(payload),
        MappingProxyType(
            {
                "name_race_drawer": name_race,
                "skill_name_drawer": skill_vwf,
                "auto_action_drawer": auto_action_vwf,
                "auto_block_ascii_drawer": auto_block_ascii,
                "affinity_drawer": affinity,
                "stock_icon_drawer": stock_icon,
            }
        ),
        masks_address,
        light_diverges,
    )


def _wrapper_payload(recipe: PatchRecipe, masks_address: int) -> tuple[bytes, int]:
    (source,) = _source_paths(recipe, ("status_ui/atlas_wrapper.s",))
    dirty_address = masks_address + 21 * 32

    def wrapper(address: int, original: int) -> bytes:
        return _assembled(
            source,
            address,
            {
                "SOURCE_PTR": STATUS_SOURCE_PTR,
                "EN_ATLAS": ATLAS_ADDRESS,
                "STOCK_ATLAS": STATUS_STOCK_ATLAS,
                "MASK_PTR": STATUS_MASK_PTR,
                "EN_MASKS": masks_address,
                "STOCK_MASKS": STATUS_STOCK_MASKS,
                "ORIGINAL": original,
                "DIRTY": dirty_address,
            },
        )

    panel = wrapper(recipe.address, BUILD_PANEL)
    atlas_address = (recipe.address + len(panel) + 3) & ~3
    atlas = wrapper(atlas_address, BUILD_ATLAS)
    payload = bytearray(atlas_address + len(atlas) - recipe.address)
    payload[: len(panel)] = panel
    start = atlas_address - recipe.address
    payload[start : start + len(atlas)] = atlas
    if len(payload) != len(recipe.expected):
        raise ValueError(
            f"status wrapper uses {len(payload)}/{len(recipe.expected)} bytes"
        )
    if recipe.address != WRAPPER_CAVE or recipe.address + len(payload) > ATLAS_ADDRESS:
        raise ValueError("status wrappers overlap the English atlas")
    return bytes(payload), atlas_address


def _small_assembly(
    recipe: PatchRecipe,
    templates: StatusTemplates,
    stock_codes: Mapping[str, int],
    *,
    light_diverges: bool,
) -> bytes:
    try:
        party_codes = tuple(stock_codes[cell] for cell in templates.party_prefix)
    except KeyError as error:
        raise ValueError(
            "status.party_alignment prefix must use preserved stock FONT8 cells; "
            f"missing {error.args[0]!r}"
        ) from error
    contracts: dict[str, tuple[str, dict[str, int]]] = {
        "party_alignment_first": (
            "status_ui/party_alignment_first.s",
            {"PREFIX_FIRST": party_codes[0]},
        ),
        "party_alignment_repeat": (
            "status_ui/party_alignment_repeat.s",
            {"PREFIX_REPEAT": party_codes[1]},
        ),
        "party_alignment_third": (
            "status_ui/party_alignment_third.s",
            {"PREFIX_THIRD": party_codes[2]},
        ),
        "light_axis_pointer_load": (
            "status_ui/light_axis_pointer.s",
            {"LIGHT_POINTER_LITERAL": 0x0603651C},
        ),
    }
    try:
        expected_source, symbols = contracts[recipe.name]
    except KeyError as error:
        raise ValueError(f"unknown status assembly patch {recipe.name}") from error
    (source,) = _source_paths(recipe, (expected_source,))
    if recipe.name == "light_axis_pointer_load" and not light_diverges:
        return recipe.expected
    replacement = _assembled(source, recipe.address, symbols)
    if len(replacement) != len(recipe.expected):
        raise ValueError(f"{recipe.name} assembly changed size")
    return replacement


def _configuration() -> PatchRecipeConfiguration:
    return load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="status.ui",
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


def _validate_inputs(
    config: PatchRecipeConfiguration,
    base: bytes,
    stock_dvlname: bytes,
    stock_charname: bytes,
    stock_font16: bytes,
) -> None:
    target = config.targets[TARGET]
    if target.load_address != LOAD_ADDRESS or len(base) != target.size:
        raise ValueError("NORMCOM status composition target changed")
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
                f"status UI {name} expected SHA-256 {expected}, found {actual[name]}"
            )


def _build_components(
    config: PatchRecipeConfiguration,
    base: bytes,
    stock_dvlname: bytes,
    english_dvlname: bytes,
    stock_charname: bytes,
    stock_font16: bytes,
) -> tuple[dict[str, bytes], RuntimeBuild, bytes, int, StatusTemplates]:
    metrics8 = FontMetrics.load(FONT8_METRICS_PATH)
    widths8, codes8 = font8_tables(metrics8)
    widths16, codes16 = _font16_metrics()
    stock_codes = _stock_latin_codes()
    font8 = FONT8_PATH.read_bytes()
    font16 = FONT16_PATH.read_bytes()
    if len(font8) != 256 * 8 or len(font16) != 1872 * 32:
        raise ValueError("status UI font geometry changed")

    templates = _status_templates()
    labels = _status_labels(templates)
    races, affinities, demon_names, character_names = _status_terms()
    party_alignments = _party_alignment_terms()
    english_charname = _built_charname(stock_charname, character_names, metrics8)
    generated, masks = _layout_data(
        base,
        font8,
        stock_font16,
        widths8,
        codes8,
        labels,
    )
    generated.update(_mirror_data(races, affinities, codes16))
    generated.update(_ascii_data(templates))
    axis, law_axis, light_axis = _axis_data()
    generated.update(axis)
    generated.update(_template_data(templates, codes8, stock_codes))

    recipes = {recipe.name: recipe for recipe in config.patches[TARGET]}
    if len(recipes) != len(config.patches[TARGET]):
        raise ValueError("status patch names must be unique")
    try:
        runtime_recipe = recipes["english_status_runtime"]
        wrapper_recipe = recipes["wrapper_cave"]
    except KeyError as error:
        raise ValueError("status config is missing a runtime cave") from error
    runtime = _runtime_payload(
        runtime_recipe,
        masks,
        widths8,
        codes8,
        widths16,
        codes16,
        font8,
        font16,
        races,
        affinities,
        party_alignments,
        demon_names,
        character_names,
        stock_dvlname,
        english_dvlname,
        stock_charname,
        english_charname,
        law_axis,
        light_axis,
    )
    wrapper, atlas_wrapper = _wrapper_payload(wrapper_recipe, runtime.masks_address)
    return generated, runtime, wrapper, atlas_wrapper, templates


def _bind_patches(
    config: PatchRecipeConfiguration,
    base: bytes,
    stock_dvlname: bytes,
    english_dvlname: bytes,
    stock_charname: bytes,
    stock_font16: bytes,
) -> tuple[Patch, ...]:
    # Resolve every digest contract against one untouched composition base.
    resolved_expected = {
        recipe.name: resolve_recipe_expected(recipe, base, LOAD_ADDRESS)
        for recipe in config.patches[TARGET]
    }
    generated, runtime, wrapper, atlas_wrapper, templates = _build_components(
        config,
        base,
        stock_dvlname,
        english_dvlname,
        stock_charname,
        stock_font16,
    )
    stock_codes = _stock_latin_codes()
    links = {**runtime.links, "atlas_wrapper": atlas_wrapper}
    output: list[Patch] = []
    generated_seen: set[str] = set()
    for recipe in config.patches[TARGET]:
        expected = resolved_expected[recipe.name]
        replacement_recipe = recipe.replacement
        if replacement_recipe.kind == "assembly":
            if recipe.name == "wrapper_cave":
                replacement = wrapper
            elif recipe.name == "english_status_runtime":
                replacement = runtime.data
            else:
                replacement = _small_assembly(
                    recipe,
                    templates,
                    stock_codes,
                    light_diverges=runtime.light_diverges,
                )
        elif replacement_recipe.kind == "generated":
            if replacement_recipe.generator != "status_data":
                raise ValueError(f"{recipe.name}: unknown status data generator")
            try:
                replacement = generated[recipe.name]
            except KeyError as error:
                raise ValueError(
                    f"status data generator did not own {recipe.name}"
                ) from error
            generated_seen.add(recipe.name)
        elif replacement_recipe.kind == "linked_pointer":
            link = replacement_recipe.link
            assert link is not None
            if recipe.name == "light_axis_pointer_literal":
                replacement = (
                    struct.pack(">I", LIGHT_AXIS_RECORD)
                    if runtime.light_diverges
                    else expected
                )
            else:
                try:
                    replacement = struct.pack(">I", links[link])
                except KeyError as error:
                    raise ValueError(f"unknown status runtime link {link}") from error
        elif replacement_recipe.kind == "pointer":
            assert replacement_recipe.pointer is not None
            replacement = struct.pack(">I", replacement_recipe.pointer)
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
    unused_generated = set(generated) - generated_seen
    if unused_generated:
        raise ValueError(
            "status data generator has no configured owner: "
            + ", ".join(sorted(unused_generated))
        )
    return tuple(output)


def build_status_ui(base: bytes) -> StatusUiBuild:
    """Build the complete detailed-status stage on an equipment-composed base."""
    _validate_surfaces()
    config = _configuration()
    stock_dvlname, stock_charname, stock_font16 = _source_assets()
    try:
        english_dvlname = DVLNAME_PATH.read_bytes()
    except FileNotFoundError as error:
        raise ValueError(f"missing translated DVLNAME: {DVLNAME_PATH}") from error
    _validate_inputs(
        config,
        base,
        stock_dvlname,
        stock_charname,
        stock_font16,
    )
    patches = _bind_patches(
        config,
        base,
        stock_dvlname,
        english_dvlname,
        stock_charname,
        stock_font16,
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
    return StatusUiBuild(
        apply_patches(base, LOAD_ADDRESS, patches),
        patches,
        ASSET_FILES,
        assembly_files,
        RUNTIME_INPUT_FILES,
        MappingProxyType(
            {
                "game:DVLNAME.DAT": _sha256(stock_dvlname),
                "game:CHARNAME.DAT": _sha256(stock_charname),
                "game:FONT16.FON": _sha256(stock_font16),
            }
        ),
    )
