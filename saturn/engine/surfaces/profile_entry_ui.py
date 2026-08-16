"""Build the Saturn Profile Entry controller directly from authored assets."""

from __future__ import annotations

import hashlib
import json
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
from engine.core.sh2 import Assembly, AssemblyError, assemble, assemble_file
from engine.shared.font8 import font8_tables
from engine.shared.player_names import (
    CODENAME_BYTES,
    NAME_FW,
    NAME_FW_FULL,
    PLAYER_NAME_FIELD_BY_KEY,
    PLAYER_NAME_FIELDS,
    byte_to_advance_table,
    byte_to_font16_table,
    byte_to_font8_table,
    parse_full_name_template,
)
from rom.util.catalog import load_catalog, validate_source
from rom.util.workflows import read_source_files
from text.util.assets import (
    ASSET_ROOT,
    BINDING_ROOT,
    CORPUS_ROOT,
    load_asset,
    load_binding,
    load_physical_record_files,
)
from text.util.event_repack import FontMetrics
from text.util.glyph_sets import load_glyph_sets
from text.util.surfaces import load_surfaces


ENGINE_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = ENGINE_ROOT.parent
PROJECT_ROOT = SATURN_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "profile_entry_ui.json"
ASSEMBLY_ROOT = ENGINE_ROOT / "asm"

PROFILE_ASSET_PATH = ASSET_ROOT / "ui" / "profile_entry.json"
PLAYER_PROFILE_ASSET_PATH = ASSET_ROOT / "player_profile.json"
PROFILE_BINDING_PATH = BINDING_ROOT / "profile_entry.json"
PROFILE_CORPUS_PATH = CORPUS_ROOT / "game" / "addressed" / "name_static.json"
SURFACES_PATH = SATURN_ROOT / "text" / "config" / "surfaces.json"
GLYPH_SETS_PATH = SATURN_ROOT / "text" / "config" / "glyph_sets.json"
DISC_CONFIG_PATH = SATURN_ROOT / "rom" / "discs.json"
PLAYER_NAMES_PATH = ENGINE_ROOT / "shared" / "player_names.py"

FONT_ROOT = SATURN_ROOT / "font" / "generated" / "game"
FONT16_PATH = FONT_ROOT / "FONT16.FON"
FONT16_METRICS_PATH = FONT_ROOT / "FONT16_metrics.json"
FONT8_PATH = FONT_ROOT / "FONT8.FON"
FONT8_METRICS_PATH = FONT_ROOT / "FONT8_metrics.json"
KANJI_PATH = FONT_ROOT / "KANJI.FON"
KANJI_CONFIG_PATH = SATURN_ROOT / "font" / "config" / "game" / "kanji.json"

ASSET_FILES = (PROFILE_ASSET_PATH, PLAYER_PROFILE_ASSET_PATH)
RUNTIME_INPUT_FILES = (
    FONT16_PATH,
    FONT16_METRICS_PATH,
    FONT8_PATH,
    FONT8_METRICS_PATH,
    KANJI_PATH,
    KANJI_CONFIG_PATH,
    SURFACES_PATH,
    GLYPH_SETS_PATH,
    DISC_CONFIG_PATH,
    PROFILE_BINDING_PATH,
    PROFILE_CORPUS_PATH,
    PLAYER_NAMES_PATH,
)

TARGET = "NAME.BIN"
LOAD_ADDRESS = 0x06020000

DATA_ADDRESS = 0x0603E840
RUNTIME_CAPACITY = 6840
DEFAULT_DATA_SIZE = 2504
DEFAULT_CONTROLLER_ADDRESS = 0x0603F208
DEFAULT_CONTROLLER_SIZE = 2608

GRID_ROWS = 8
GRID_COLUMNS = 19
GRID_CONTENT_ROW = 1
GRID_CONTENT_COLUMN = 3
GRID_CONTENT_WIDTH = 13
END_ROW = 4
END_COLUMN = 15
END_DISPLAY_CELL = 0x01F7
ENTRY_COLUMN = 11
ROW_TERMINATOR = 0x8000

TAB_ROWS = (
    ("upper", ("grid_upper_row_1", "grid_upper_row_2")),
    ("lower", ("grid_lower_row_1", "grid_lower_row_2")),
    ("symbol", ("grid_symbol_row_1", "grid_symbol_row_2")),
)
PROMPT_KEYS = (
    "prompt_first",
    "prompt_last",
    "prompt_codename",
    "prompt_city",
    "prompt_ward",
)
OCCUPATION_KEYS = (
    "occupation_employee",
    "occupation_student",
    "occupation_official",
    "occupation_part_time",
    "occupation_business",
    "occupation_jobless",
)
TAB_LABEL_KEYS = ("tab_upper", "tab_lower", "tab_symbol")


@dataclass(frozen=True, slots=True)
class DataBlock:
    name: str
    address: int
    data: bytes


@dataclass(frozen=True, slots=True)
class ProfileRuntime:
    data: bytes
    controller: bytes
    arena: bytes
    links: Mapping[str, int]
    generated: Mapping[str, bytes]
    controller_address: int
    used_size: int


@dataclass(frozen=True, slots=True)
class ProfileEntryUiBuild:
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
        raise ValueError(f"missing Profile Entry input: {path}") from error


def _configuration() -> PatchRecipeConfiguration:
    return load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="profile_entry.ui",
        target_names={TARGET},
        input_names={
            "font16_sha256",
            "font16_metrics_sha256",
            "font8_sha256",
            "font8_metrics_sha256",
            "kanji_sha256",
            "kanji_config_sha256",
            "glyph_sets_sha256",
        },
    )


def _stock_source() -> bytes:
    catalog = load_catalog()
    try:
        game = catalog["game"]
    except KeyError as error:
        raise ValueError("disc catalog has no game source") from error
    return read_source_files(
        validate_source(game, verify_hashes=False), (TARGET,)
    )[TARGET]


def _validate_sources(
    config: PatchRecipeConfiguration,
    stock: bytes,
    base: bytes,
) -> None:
    contract = config.targets[TARGET]
    if (
        contract.load_address != LOAD_ADDRESS
        or len(stock) != contract.size
        or _sha256(stock) != contract.stock_sha256
    ):
        raise ValueError("NAME.BIN does not match the configured stock target")
    if len(base) != contract.size:
        raise ValueError("composed NAME.BIN has the wrong size")
    actual = {
        "font16_sha256": _file_sha256(FONT16_PATH),
        "font16_metrics_sha256": _file_sha256(FONT16_METRICS_PATH),
        "font8_sha256": _file_sha256(FONT8_PATH),
        "font8_metrics_sha256": _file_sha256(FONT8_METRICS_PATH),
        "kanji_sha256": _file_sha256(KANJI_PATH),
        "kanji_config_sha256": _file_sha256(KANJI_CONFIG_PATH),
        "glyph_sets_sha256": _file_sha256(GLYPH_SETS_PATH),
    }
    for name, expected in config.inputs.items():
        if actual[name] != expected:
            raise ValueError(
                f"Profile Entry {name} expected SHA-256 {expected}, "
                f"found {actual[name]}"
            )


def _translation(catalog, key: str) -> str:
    try:
        value = catalog.entries[key].fields["text"].translation
    except KeyError as error:
        raise ValueError(f"ui/profile_entry.json is missing {key}.text") from error
    if not value:
        raise ValueError(f"ui/profile_entry.json {key}.text is untranslated")
    return value


def _full_name_storage() -> str:
    catalog = load_asset("player_profile.json")
    try:
        value = catalog.entries["full_name_storage"].fields["text"].translation
    except KeyError as error:
        raise ValueError(
            "player_profile.json is missing full_name_storage.text"
        ) from error
    if not value:
        raise ValueError("player_profile.json full_name_storage.text is untranslated")
    return value


def _validate_text_binding() -> None:
    physical = load_physical_record_files((PROFILE_CORPUS_PATH,))
    load_binding(PROFILE_BINDING_PATH, physical_records=physical)


def _validate_surfaces() -> None:
    expected = {
        "name_entry.prompt": ("font16", 1, "pixels", 168, 11),
        "name_entry.confirm_prompt": ("font16", 1, "glyph_cells", 11, 11),
        "name_entry.confirm_choice": ("font16", 1, "glyph_cells", 3, 3),
        "name_entry.summary_label": ("font16", 1, "pixels", 104, 11),
        "name_entry.tab_label": ("font16", 1, "pixels", 96, None),
        "name_entry.occupation_choice": ("font16", 1, "pixels", 128, None),
        "name_entry.grid_row": ("kanji", 1, "glyph_cells", 13, 13),
        "name_entry.grid_action": ("font16", 1, "glyph_cells", 2, 2),
        "name_entry.address_suffix": ("font16", 1, None, None, None),
        "name_entry.default_value": ("font16", 1, "glyph_cells", 8, 8),
        "profile.full_name": ("font16", 1, "glyph_cells", 17, 17),
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


def _font16_maps(
    metrics: FontMetrics,
) -> tuple[dict[str, int], dict[str, int]]:
    codes: dict[str, int] = {}
    advances: dict[str, int] = {}
    for glyph in metrics.glyphs:
        for text in (glyph.text, *glyph.aliases):
            if len(text) == 1:
                codes.setdefault(text, glyph.code)
                advances.setdefault(text, glyph.advance)
    required = set(
        " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        "!?.,'-/&:"
    )
    if not required <= set(codes):
        raise ValueError(
            "FONT16 Profile Entry coverage is missing "
            + repr("".join(sorted(required - set(codes))))
        )
    return codes, advances


def _reference_codes(reference_set: str) -> Mapping[str, int]:
    try:
        document = json.loads(KANJI_CONFIG_PATH.read_text(encoding="utf-8"))
        rows = document["reference_sets"][reference_set]
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise ValueError("invalid KANJI reference-set configuration") from error
    output: dict[str, int] = {}
    if not isinstance(rows, list):
        raise ValueError("KANJI reference set must be a list")
    for index, raw_row in enumerate(rows):
        if not isinstance(raw_row, dict):
            raise ValueError(f"KANJI reference row {index} must be an object")
        if set(raw_row) == {"start", "characters"}:
            start = raw_row["start"]
            characters = raw_row["characters"]
            if type(start) is not int or not isinstance(characters, str):
                raise ValueError(f"KANJI reference row {index} is invalid")
            pairs = ((character, start + offset) for offset, character in enumerate(characters))
        else:
            try:
                pairs = ((character, int(code)) for code, character in raw_row.items())
            except (TypeError, ValueError) as error:
                raise ValueError(f"KANJI reference row {index} is invalid") from error
        for character, code in pairs:
            if (
                not isinstance(character, str)
                or len(character) != 1
                or not 0 <= code <= 0xFFFF
                or character in output
            ):
                raise ValueError(f"KANJI reference row {index} collides or is invalid")
            output[character] = code
    return MappingProxyType(output)


def _kanji_codes() -> Mapping[str, int]:
    handler = load_glyph_sets().for_surface("name_entry.grid_row")
    if handler is None or handler.font != "kanji":
        raise ValueError("name_entry.grid_row needs an explicit KANJI glyph handler")
    return _reference_codes(handler.reference_set)


def _ascii_text(
    catalog,
    metrics: FontMetrics,
    key: str,
    *,
    glyph_limit: int | None = None,
    pixel_limit: int | None = None,
) -> str:
    value = _translation(catalog, key)
    if not value.isascii() or "\x00" in value or "{" in value or "}" in value:
        raise ValueError(f"Profile Entry {key} must be literal ASCII")
    glyphs = metrics.segment(value)
    if glyph_limit is not None and len(glyphs) > glyph_limit:
        raise ValueError(f"Profile Entry {key} exceeds {glyph_limit} glyphs")
    pixels = sum(glyph.advance for glyph in glyphs)
    if pixel_limit is not None and pixels > pixel_limit:
        raise ValueError(f"Profile Entry {key} exceeds {pixel_limit}px")
    return value


def _fixed_words(
    catalog,
    metrics: FontMetrics,
    key: str,
    cells: int,
    *,
    pixel_limit: int | None = None,
) -> tuple[int, ...]:
    value = _ascii_text(
        catalog, metrics, key, glyph_limit=cells, pixel_limit=pixel_limit
    )
    words = tuple(glyph.code for glyph in metrics.segment(value))
    return words + (0,) * (cells - len(words))


def _validate_dormant_text(catalog, metrics: FontMetrics) -> None:
    _ascii_text(catalog, metrics, "tab_katakana", pixel_limit=96)
    _ascii_text(catalog, metrics, "city_suffix")
    _ascii_text(catalog, metrics, "ward_suffix")
    raster_actions = {
        "grid_move_left": "←",
        "grid_move_right": "→",
        "grid_end": "END",
    }
    for key, expected in raster_actions.items():
        if _translation(catalog, key) != expected:
            raise ValueError(
                f"Profile Entry {key} edits require a matching preserved-raster patch"
            )


def _build_grid(rows: tuple[str, ...], codes: Mapping[str, int]) -> tuple[bytes, bytes]:
    display = [[0] * GRID_COLUMNS for _ in range(GRID_ROWS)]
    commit = [[0] * GRID_COLUMNS for _ in range(GRID_ROWS)]
    if len(rows) > END_ROW - GRID_CONTENT_ROW:
        raise ValueError("Profile Entry grid rows collide with the END control")
    for row_index, row in enumerate(rows, GRID_CONTENT_ROW):
        if len(row) > GRID_CONTENT_WIDTH:
            raise ValueError(f"Profile Entry grid row exceeds {GRID_CONTENT_WIDTH} cells")
        for column_index, character in enumerate(row, GRID_CONTENT_COLUMN):
            try:
                display[row_index][column_index] = codes[character]
            except KeyError as error:
                raise ValueError(
                    f"Profile Entry grid character {character!r} is absent from "
                    "the configured KANJI reference set"
                ) from error
            if not character.isascii() or ord(character) >= 0x80:
                raise ValueError("Profile Entry grid commits must be seven-bit ASCII")
            commit[row_index][column_index] = ord(character)
    display[END_ROW][END_COLUMN] = END_DISPLAY_CELL
    pack = lambda value: b"".join(struct.pack(">19H", *row) for row in value)
    return pack(display), pack(commit)


def _data_layout(
    catalog,
    metrics16: FontMetrics,
    codes16: Mapping[str, int],
    advances16: Mapping[str, int],
    codes8: Mapping[str, int],
    kanji_codes: Mapping[str, int],
) -> tuple[bytes, Mapping[str, int], Mapping[str, int]]:
    blocks: list[DataBlock] = []
    cursor = DATA_ADDRESS

    def add(name: str, data: bytes, *, align: int = 1) -> DataBlock:
        nonlocal cursor
        cursor = (cursor + align - 1) & -align
        block = DataBlock(name, cursor, data)
        blocks.append(block)
        cursor += len(data)
        return block

    grids: list[tuple[DataBlock, DataBlock]] = []
    for _tab, row_keys in TAB_ROWS:
        rows = tuple(
            _ascii_text(catalog, metrics16, key, glyph_limit=GRID_CONTENT_WIDTH)
            for key in row_keys
        )
        display, commit = _build_grid(rows, kanji_codes)
        index = len(grids)
        grids.append(
            (
                add(f"grid_{index}_display", display),
                add(f"grid_{index}_commit", commit),
            )
        )

    add("ascii_to_charmap", byte_to_font8_table(codes8)[0x20:0x80])
    atlas = byte_to_font16_table(codes16)[0x20:0x80]
    add("ascii_to_atlas", struct.pack(">96H", *atlas))

    defaults = []
    for key in ("default_city", "default_ward"):
        value = _ascii_text(catalog, metrics16, key, glyph_limit=8)
        defaults.append(value.encode("ascii").ljust(8, b"\0"))
    add("default_city_ward", b"".join(defaults))
    add(
        "grid_bases",
        b"".join(
            struct.pack(">2I", display.address, commit.address)
            for display, commit in grids
        ),
        align=4,
    )
    add(
        "stage_pointers",
        struct.pack(">5I", *(field.stage_address for field in PLAYER_NAME_FIELDS)),
    )
    add("ascii_to_width", byte_to_advance_table(advances16)[0x20:0x80])

    string_keys = (*PROMPT_KEYS, *OCCUPATION_KEYS, *TAB_LABEL_KEYS, "label_occupation")
    string_offsets: dict[str, int] = {}
    string_data = bytearray()
    for key in string_keys:
        limits = (
            (11, 168)
            if key in PROMPT_KEYS
            else (None, 128)
            if key in OCCUPATION_KEYS
            else (None, 96)
            if key in TAB_LABEL_KEYS
            else (11, 104)
        )
        value = _ascii_text(
            catalog,
            metrics16,
            key,
            glyph_limit=limits[0],
            pixel_limit=limits[1],
        )
        string_offsets[key] = len(string_data)
        string_data.extend(value.encode("ascii") + b"\0")
    strings = add("label_strings", bytes(string_data), align=4)
    labels = {
        key: strings.address + offset for key, offset in string_offsets.items()
    }
    add(
        "prompt_pointers",
        struct.pack(">5I", *(labels[key] for key in PROMPT_KEYS)),
        align=4,
    )

    occupation_centers = (88, 216, 88, 216, 88, 216)
    occupation_rows = (16, 16, 48, 48, 80, 80)
    occupation_info = bytearray()
    for key, center, y in zip(
        OCCUPATION_KEYS, occupation_centers, occupation_rows
    ):
        value = _translation(catalog, key)
        width = sum(glyph.advance for glyph in metrics16.segment(value))
        occupation_info.extend(
            struct.pack(">IHH", labels[key], max(0, center - width // 2), y)
        )
    add("occupation_info", bytes(occupation_info), align=4)

    tab_info = bytearray()
    for key, center in zip(TAB_LABEL_KEYS, (48, 144, 240)):
        value = _translation(catalog, key)
        width = sum(glyph.advance for glyph in metrics16.segment(value))
        tab_info.extend(
            struct.pack(">IHH", labels[key], max(0, center - width // 2), 0)
        )
    add("tab_info", bytes(tab_info))

    if cursor > DATA_ADDRESS + RUNTIME_CAPACITY:
        raise ValueError("Profile Entry generated data exceeds its runtime arena")
    payload = bytearray(cursor - DATA_ADDRESS)
    addresses: dict[str, int] = {}
    for block in blocks:
        start = block.address - DATA_ADDRESS
        payload[start : start + len(block.data)] = block.data
        addresses[block.name] = block.address
    return bytes(payload), MappingProxyType(addresses), MappingProxyType(labels)


def _templates(catalog, metrics16: FontMetrics) -> Mapping[str, bytes]:
    entry = [0] * 20
    entry[-1] = ROW_TERMINATOR

    confirm = [0] * 20
    confirm[:ENTRY_COLUMN] = _fixed_words(
        catalog, metrics16, "prompt_confirm", ENTRY_COLUMN
    )
    confirm[12:15] = _fixed_words(catalog, metrics16, "label_yes", 3)
    confirm[16:19] = _fixed_words(catalog, metrics16, "label_no", 3)
    confirm[-1] = ROW_TERMINATOR

    occupation = [0] * 20
    occupation[:ENTRY_COLUMN] = _fixed_words(
        catalog, metrics16, "prompt_occupation", ENTRY_COLUMN, pixel_limit=168
    )
    occupation[-1] = ROW_TERMINATOR
    return MappingProxyType(
        {
            "entry_template": struct.pack(">20H", *entry),
            "confirm_template": struct.pack(">20H", *confirm),
            "occupation_template": struct.pack(">20H", *occupation),
        }
    )


def _assembled(
    source: Path,
    address: int,
    symbols: Mapping[str, int],
    *,
    source_text: str | None = None,
) -> Assembly:
    try:
        result = (
            assemble(source_text, address, dict(symbols))
            if source_text is not None
            else assemble_file(source, address, dict(symbols))
        )
    except (AssemblyError, FileNotFoundError) as error:
        raise ValueError(f"{source.relative_to(ENGINE_ROOT)}: {error}") from error
    if result.warnings:
        raise ValueError(
            f"{source.relative_to(ENGINE_ROOT)}: assembly warnings: {result.warnings}"
        )
    return result


def _controller_symbols(
    addresses: Mapping[str, int],
    labels: Mapping[str, int],
    full_name,
    separator_code: int,
) -> dict[str, int]:
    first_field, second_field = (
        PLAYER_NAME_FIELD_BY_KEY[name] for name in full_name.field_order
    )
    return {
        "g_type": 0x06045E8A,
        "g_state": 0x06045E8C,
        "g_tab": 0x06045E8E,
        "g_occ": 0x06045E90,
        "g_pos": 0x06045EE8,
        "g_col": 0x06045EEE,
        "g_row": 0x06045EF0,
        "g_scroll": 0x06045EF2,
        "g_pad_edge": 0x06045E94,
        "g_pad_rep": 0x06045E96,
        "fn_sound": 0x0602EDBC,
        "fn_btnA": 0x0602ECD0,
        "fn_btnB": 0x0602ECC0,
        "fn_btnX": 0x0602ECB2,
        "fn_exitgrid": 0x06030E84,
        "fn_rowclear": 0x0602EE1C,
        "fn_pen": 0x0602EE80,
        "fn_color": 0x0602EE94,
        "fn_drawstr": 0x0602EFB8,
        "fn_rowflush": 0x0602F6AC,
        "fn_newline": 0x0602EE60,
        "fn_gridrow": 0x0602F05C,
        "fn_clearall": 0x0602EDD0,
        "fn_fullflush": 0x0602F628,
        "fn_upload": 0x0602F1C4,
        "fn_setbit": 0x06032AD4,
        "fn_blit": 0x0602F510,
        "fn_clearrow": 0x0602F0E4,
        "fn_clear07": 0x0602F0C8,
        "ascii_to_atlas": addresses["ascii_to_atlas"],
        "ascii_to_width": addresses["ascii_to_width"],
        "ascii_to_charmap": addresses["ascii_to_charmap"],
        "OCC_INFO": addresses["occupation_info"],
        "TAB_INFO": addresses["tab_info"],
        "OCC_PROMPT": labels["label_occupation"],
        "J_TEXT_JSR": 0x06033144,
        "J_TEXT_SKIP": 0x0603314A,
        "J_OCC": 0x060332AE,
        "J_CONFIRM": 0x060332EA,
        "J_T12": 0x0603336A,
        "J_IDLE": 0x0603341E,
        "TMPL8": 0x06040B78,
        "prompt_pointers": addresses["prompt_pointers"],
        "default_city_ward": addresses["default_city_ward"],
        "grid_bases": addresses["grid_bases"],
        "stage_ptrs": addresses["stage_pointers"],
        "NAME_FW": NAME_FW,
        "NAME_FW_FULL": NAME_FW_FULL,
        "CODENAME": CODENAME_BYTES,
        "DEF_CITY": PLAYER_NAME_FIELD_BY_KEY["city"].stage_address,
        "FULL_NAME_FIRST": first_field.runtime_address,
        "FULL_NAME_SEPARATOR": separator_code,
    }


def _runtime(
    catalog,
    full_name_storage: str,
    metrics16: FontMetrics,
    metrics8: FontMetrics,
) -> ProfileRuntime:
    codes16, advances16 = _font16_maps(metrics16)
    _widths8, codes8 = font8_tables(metrics8)
    _validate_dormant_text(catalog, metrics16)
    data, addresses, labels = _data_layout(
        catalog,
        metrics16,
        codes16,
        advances16,
        codes8,
        _kanji_codes(),
    )

    full_name = parse_full_name_template(full_name_storage)
    separator = metrics16.segment(full_name.separator)
    if len(separator) != 1:
        raise ValueError("Profile Entry full_name needs exactly one FONT16 separator glyph")
    symbols = _controller_symbols(
        addresses,
        labels,
        full_name,
        separator[0].code,
    )
    controller_address = (DATA_ADDRESS + len(data) + 3) & ~3
    source = ASSEMBLY_ROOT / "profile_entry_ui" / "entry.s"
    try:
        controller_source = source.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise ValueError(f"missing Profile Entry assembly source: {source}") from error
    second_field = PLAYER_NAME_FIELD_BY_KEY[full_name.field_order[1]]
    rendered_links = {
        "@FULL_NAME_FIRST@": (
            "NAME_FW"
            if full_name.field_order == ("first_name", "last_name")
            else "FULL_NAME_FIRST"
        ),
        "@FULL_NAME_SECOND_OFFSET@": str(second_field.runtime_address - NAME_FW),
    }
    for token, value in rendered_links.items():
        if controller_source.count(token) != 1:
            raise ValueError(f"Profile Entry assembly needs one {token} link")
        controller_source = controller_source.replace(token, value)
    controller = _assembled(
        source,
        controller_address,
        symbols,
        source_text=controller_source,
    )
    if not controller.data:
        raise ValueError("Profile Entry controller assembled empty")
    used_size = controller_address - DATA_ADDRESS + len(controller.data)
    if used_size > RUNTIME_CAPACITY:
        raise ValueError(
            f"Profile Entry runtime uses {used_size}/{RUNTIME_CAPACITY} bytes"
        )
    arena = bytearray(RUNTIME_CAPACITY)
    arena[: len(data)] = data
    controller_offset = controller_address - DATA_ADDRESS
    arena[controller_offset : controller_offset + len(controller.data)] = controller.data
    generated = dict(_templates(catalog, metrics16))
    return ProfileRuntime(
        data,
        controller.data,
        bytes(arena),
        MappingProxyType(controller.labels),
        MappingProxyType(generated),
        controller_address,
        used_size,
    )


def _only_source(recipe: PatchRecipe, expected: str) -> Path:
    sources = recipe.replacement.sources
    if (
        len(sources) != 1
        or sources[0].relative_to(ASSEMBLY_ROOT).as_posix() != expected
    ):
        raise ValueError(f"{recipe.group}/{recipe.name}: assembly source changed")
    return sources[0]


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


def _assembly_patch(recipe: PatchRecipe, runtime: ProfileRuntime) -> bytes:
    if recipe.name == "runtime_arena":
        _only_source(recipe, "profile_entry_ui/entry.s")
        return runtime.arena
    if recipe.name == "router_hook":
        source = _only_source(recipe, "profile_entry_ui/router_hook.s")
        return _assembled(
            source, recipe.address, {"ROUTER_POINTER": 0x06033204}
        ).data
    if recipe.name == "skip_stock_text":
        source = _only_source(recipe, "profile_entry_ui/skip_stock_text.s")
        return _assembled(source, recipe.address, {"CONTINUE": 0x0603282A}).data
    raise ValueError(f"{recipe.group}/{recipe.name}: unknown assembly owner")


def _bind_patches(
    config: PatchRecipeConfiguration,
    stock: bytes,
    runtime: ProfileRuntime,
) -> tuple[Patch, ...]:
    output: list[Patch] = []
    generated_seen: set[str] = set()
    for recipe in config.patches[TARGET]:
        expected = resolve_recipe_expected(recipe, stock, LOAD_ADDRESS)
        replacement_recipe = recipe.replacement
        if replacement_recipe.kind == "assembly":
            replacement = _assembly_patch(recipe, runtime)
        elif replacement_recipe.kind == "linked_pointer":
            link = replacement_recipe.link
            assert link is not None
            try:
                replacement = struct.pack(">I", runtime.links[link])
            except KeyError as error:
                raise ValueError(
                    f"{recipe.group}/{recipe.name}: unknown controller link {link!r}"
                ) from error
        elif replacement_recipe.kind == "instruction":
            replacement = _instruction(recipe)
        elif replacement_recipe.kind == "generated":
            if replacement_recipe.generator != "profile_entry_data":
                raise ValueError(
                    f"{recipe.group}/{recipe.name}: unknown Profile Entry generator"
                )
            try:
                replacement = runtime.generated[recipe.name]
            except KeyError as error:
                raise ValueError(
                    f"{recipe.group}/{recipe.name}: no generated data owner"
                ) from error
            generated_seen.add(recipe.name)
        else:
            raise ValueError(
                f"{recipe.group}/{recipe.name}: unsupported replacement recipe"
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
    unused = set(runtime.generated) - generated_seen
    if unused:
        raise ValueError(
            "Profile Entry generated data has no configured owner: "
            + ", ".join(sorted(unused))
        )
    return tuple(output)


def build_profile_entry_ui(name_base: bytes | None = None) -> ProfileEntryUiBuild:
    """Build the complete NAME.BIN surface from the verified game disc."""
    config = _configuration()
    stock = _stock_source()
    base = stock if name_base is None else name_base
    _validate_sources(config, stock, base)
    _validate_surfaces()
    _validate_text_binding()
    catalog = load_asset("ui/profile_entry.json")
    runtime = _runtime(
        catalog,
        _full_name_storage(),
        FontMetrics.load(FONT16_METRICS_PATH),
        FontMetrics.load(FONT8_METRICS_PATH),
    )
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
    return ProfileEntryUiBuild(
        apply_patches(base, LOAD_ADDRESS, patches),
        patches,
        ASSET_FILES,
        assembly_files,
        RUNTIME_INPUT_FILES,
        MappingProxyType({f"game:{TARGET}": _sha256(stock)}),
        runtime.used_size,
        RUNTIME_CAPACITY,
    )
