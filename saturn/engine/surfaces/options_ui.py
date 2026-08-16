"""Build the Saturn Options interface from authored text assets."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from engine.core.patch_recipes import (
    PatchRecipeConfiguration,
    load_patch_recipe_configuration,
    resolve_recipe_expected,
)
from engine.core.patching import Patch, apply_patches
from engine.core.sh2 import Assembly, AssemblyError, assemble, assemble_file
from rom.util.catalog import load_catalog, validate_source
from rom.util.workflows import read_source_files
from text.util.assets import (
    ASSET_ROOT,
    BINDING_ROOT,
    CORPUS_ROOT,
    load_bound_translations,
    load_physical_record_files,
)
from text.util.surfaces import load_surfaces


ENGINE_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = ENGINE_ROOT.parent
PROJECT_ROOT = SATURN_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "options_ui.json"
FONT_ROOT = SATURN_ROOT / "font" / "generated" / "game"
FONT16_PATH = FONT_ROOT / "FONT16.FON"
FONT16_METRICS_PATH = FONT_ROOT / "FONT16_metrics.json"
ASSET_PATH = ASSET_ROOT / "ui" / "options.json"
BINDING_PATH = BINDING_ROOT / "options.json"
CORPUS_PATH = CORPUS_ROOT / "game" / "addressed" / "config_static.json"
ASSET_FILES = (ASSET_PATH,)
RUNTIME_INPUT_FILES = (
    FONT16_PATH,
    FONT16_METRICS_PATH,
    SATURN_ROOT / "text" / "config" / "surfaces.json",
    SATURN_ROOT / "rom" / "discs.json",
    BINDING_PATH,
    CORPUS_PATH,
)

TARGET = "CFG_SET.BIN"
LOAD_ADDRESS = 0x06020000
TARGET_SIZE = 273_560

LABEL_TABLE = 0x06020400
ACTIVE_ROW_RENDERER = 0x06020700
ACTIVE_CACHE = 0x06020900
MAGIC_SORT_TABLE = 0x06020904
ITEM_SORT_TABLE = 0x06020984
ACTION_VWF = 0x06020A00
ACTION_ATLAS = 0x06021000
GLYPH_VWF = 0x06021900
COMPOUND_GLYPH = 0x06022000

LABEL_CELLS = 16
DORMANT_LABEL_OFFSET = 0x009E2A
POPUP_CELLS = 5
POPUP_RECORD_CELLS = 16
ACTION_RECORD_CELLS = 8
ACTION_CAPACITY = 64
FOOTER_CELLS = 9
COMPOUND_BASE = 1848
COMPOUND_CAPACITY = 1871 - COMPOUND_BASE

LABEL_RECORDS = (
    ("battle_messages", 0x009E3A),
    ("auto_map", 0x009E4A),
    ("party_panel", 0x009E5A),
    ("demon_analyze", 0x009E6A),
    ("sound", 0x009E7A),
    ("magic_order", 0x009E8A),
    ("item_order", 0x009E9A),
    ("speed_fast", 0x009EAA),
    ("speed_normal", 0x009EBA),
    ("speed_slow", 0x009ECA),
    ("party_fixed", 0x009EDA),
    ("party_free", 0x009EEA),
    ("graph", 0x009EFA),
    ("max", 0x009F0A),
    ("display_normal", 0x009F1A),
    ("display_reverse", 0x009F2A),
    ("stereo", 0x009F3A),
    ("mono", 0x009F4A),
)
PAGE2_RECORDS = (
    ("controls", 0x009F6A, 9),
    ("mode_normal", 0x009F7C, 9),
    ("mode_custom", 0x009F8E, 6),
)
MAGIC_SORT_RECORDS = (
    ("assist_heal", 0x009FA0),
    ("assist_skill", 0x009FAA),
    ("assist_buff", 0x009FB4),
    ("assist_attack_support", 0x009FBE),
)
ITEM_SORT_RECORDS = (
    ("assist_item", 0x009FC8),
    ("assist_gem", 0x009FD2),
    ("assist_equip", 0x009FDC),
)
ACTION_RECORDS = (
    ("action_full_cancel", 0x042B46),
    ("action_cancel", 0x042B56),
    ("action_confirm", 0x042B66),
    ("action_help", 0x042B76),
    ("action_recover", 0x042B86),
    ("action_command", 0x042B96),
    ("action_auto_map", 0x042BA6),
    ("action_analyze", 0x042BB6),
)
FOOTER_RECORDS = (
    ("footer_assign", 0x042BD6),
    ("footer_finish", 0x042BE8),
)


def _physical_id(offset: int) -> str:
    return f"game.config_static.o{offset:06x}"


REQUIRED_IDS = frozenset(
    _physical_id(offset)
    for _name, offset in (
        *LABEL_RECORDS,
        *((name, offset) for name, offset, _capacity in PAGE2_RECORDS),
        *MAGIC_SORT_RECORDS,
        *ITEM_SORT_RECORDS,
        *ACTION_RECORDS,
        *FOOTER_RECORDS,
    )
)


@dataclass(frozen=True, slots=True)
class Font16Metrics:
    widths: bytes
    codes: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class CompoundPlan:
    compounds: tuple[str, ...]
    codes: Mapping[str, int]
    popup_records: Mapping[str, tuple[int | str, ...]]
    footer_records: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class RuntimeBuild:
    assembly: Mapping[str, bytes]
    generated: Mapping[str, bytes]
    links: Mapping[str, int]
    compounds: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OptionsUiBuild:
    data: bytes
    patches: tuple[Patch, ...]
    asset_files: tuple[Path, ...]
    assembly_files: tuple[Path, ...]
    runtime_input_files: tuple[Path, ...]
    source_inputs: Mapping[str, str]
    compounds: tuple[str, ...]


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        return _sha256(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"missing Options UI input: {path}") from error


def _source_cfg_set() -> bytes:
    catalog = load_catalog()
    try:
        game = catalog["game"]
    except KeyError as error:
        raise ValueError("disc catalog has no game source") from error
    source = read_source_files(
        validate_source(game, verify_hashes=False),
        (TARGET,),
    )
    return source[TARGET]


def _configuration() -> PatchRecipeConfiguration:
    return load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="options.ui",
        target_names={TARGET},
        input_names={"font16_sha256", "font16_metrics_sha256"},
    )


def _validate_inputs(config: PatchRecipeConfiguration, base: bytes) -> None:
    target = config.targets[TARGET]
    if target.load_address != LOAD_ADDRESS or len(base) != target.size:
        raise ValueError("Options UI target geometry changed")
    preset = base[0x9FE6 : 0x9FFE]
    if _sha256(preset) != "796cb41a35005a32159deab04d4bedc93b5bfc2937d24b9870556f9c9010108a":
        raise ValueError("Options magic-sort preset order changed")
    if _sha256(base) != target.stock_sha256:
        raise ValueError("Options UI requires the configured stock CFG_SET.BIN")
    actual = {
        "font16_sha256": _file_sha256(FONT16_PATH),
        "font16_metrics_sha256": _file_sha256(FONT16_METRICS_PATH),
    }
    for name, expected in config.inputs.items():
        if actual[name] != expected:
            raise ValueError(
                f"Options UI {name} expected SHA-256 {expected}, found {actual[name]}"
            )


def _font16_metrics() -> Font16Metrics:
    try:
        document = json.loads(FONT16_METRICS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid FONT16 metrics: {FONT16_METRICS_PATH}") from error
    table = document.get("width_table", {})
    code_limit = table.get("code_limit")
    if (
        document.get("version") != 2
        or not document.get("complete")
        or type(code_limit) is not int
        or code_limit <= 0
    ):
        raise ValueError("incomplete FONT16 metrics for Options UI")
    widths = bytearray(code_limit)
    codes: dict[str, int] = {}
    for row in document.get("glyphs", ()):
        code, advance = row.get("code"), row.get("advance")
        if type(code) is not int or not 0 <= code < code_limit:
            raise ValueError("invalid Options FONT16 glyph code")
        if type(advance) is not int or not 1 <= advance <= 16:
            raise ValueError("invalid Options FONT16 glyph advance")
        widths[code] = advance
        for text in (row.get("text"), *row.get("aliases", ())):
            if isinstance(text, str) and len(text) == 1:
                codes.setdefault(text, code)
    return Font16Metrics(bytes(widths), MappingProxyType(codes))


def _options_terms() -> dict[str, str]:
    physical = load_physical_record_files((CORPUS_PATH,))
    translations = load_bound_translations(
        ("game.config_static.",),
        required_ids=set(REQUIRED_IDS),
        binding_paths=(BINDING_PATH,),
        physical_records=physical,
    )
    values: dict[str, str] = {}
    records = (
        *LABEL_RECORDS,
        *((name, offset) for name, offset, _capacity in PAGE2_RECORDS),
        *MAGIC_SORT_RECORDS,
        *ITEM_SORT_RECORDS,
        *ACTION_RECORDS,
        *FOOTER_RECORDS,
    )
    for name, offset in records:
        value = translations[_physical_id(offset)]
        if not value:
            raise ValueError(f"Options field {name} is empty")
        values[name] = value
    if len(values) != len(records):
        raise ValueError("Options logical field names must be unique")
    return values


def _encode(text: str, metrics: Font16Metrics, context: str) -> tuple[int, ...]:
    try:
        return tuple(metrics.codes[character] for character in text)
    except KeyError as error:
        raise ValueError(
            f"unsupported {context} FONT16 character {error.args[0]!r} in {text!r}"
        ) from error


def _packed_words(
    text: str,
    capacity: int,
    metrics: Font16Metrics,
    context: str,
    *,
    padding: int = 0,
) -> bytes:
    codes = _encode(text, metrics, context)
    if not codes or len(codes) > capacity:
        raise ValueError(
            f"{context} uses {len(codes)} cells; maximum is {capacity}"
        )
    return struct.pack(
        f">{capacity}H", *(codes + (padding,) * (capacity - len(codes)))
    )


def _render_action_chunk(
    font16: bytes,
    codes: tuple[int, ...],
    metrics: Font16Metrics,
) -> tuple[bytes, int]:
    rows = [0] * 12
    x = 0
    for code in codes:
        start = code * 32
        cell = font16[start : start + 32]
        if len(cell) != 32 or code >= len(metrics.widths) or not metrics.widths[code]:
            raise ValueError(f"Options action glyph {code} has no FONT16 metrics")
        for row in range(12):
            word = struct.unpack_from(">H", cell, (row + 2) * 2)[0]
            if x and word & ((1 << x) - 1):
                raise ValueError("Options action chunk clips its right edge")
            rows[row] |= word >> x
        x += metrics.widths[code]
    if x > 16 or any(row & 0x000F for row in rows):
        raise ValueError("Options action chunk does not fit its 12px atlas cell")
    return b"".join(struct.pack(">H", row) for row in rows) + bytes(8), x


def _build_action_atlas(
    font16: bytes,
    metrics: Font16Metrics,
    terms: Mapping[str, str],
) -> tuple[bytes, bytes, dict[str, tuple[int, ...]]]:
    unique: list[tuple[int, ...]] = []
    encoded: dict[str, tuple[tuple[int, ...], ...]] = {}
    for name, _offset in ACTION_RECORDS:
        codes = _encode(terms[name], metrics, f"Options {name}")
        chunks: list[tuple[int, ...]] = []
        position = 0
        while position < len(codes):
            chunk = None
            for end in range(len(codes), position, -1):
                candidate = codes[position:end]
                try:
                    _render_action_chunk(font16, candidate, metrics)
                except ValueError:
                    continue
                chunk = candidate
                break
            if chunk is None:
                raise ValueError(f"Options {name} cannot fit the action atlas")
            chunks.append(chunk)
            position += len(chunk)
        if len(chunks) > ACTION_RECORD_CELLS:
            raise ValueError(f"Options {name} needs more than eight action cells")
        encoded[name] = tuple(chunks)
        for chunk in chunks:
            if chunk not in unique:
                unique.append(chunk)

    if len(unique) > ACTION_CAPACITY:
        raise ValueError("Options action atlas exceeds 64 private glyphs")
    indices = {chunk: index + 1 for index, chunk in enumerate(unique)}
    atlas = bytearray((ACTION_CAPACITY + 1) * 32)
    widths = bytearray(ACTION_CAPACITY)
    for chunk, index in indices.items():
        cell, width = _render_action_chunk(font16, chunk, metrics)
        atlas[index * 32 : (index + 1) * 32] = cell
        widths[index - 1] = width
    records = {
        name: tuple(indices[chunk] for chunk in chunks)
        for name, chunks in encoded.items()
    }
    return bytes(atlas), bytes(widths), records


def _popup_tokens(
    text: str,
    font16: bytes,
    metrics: Font16Metrics,
) -> tuple[str, ...]:
    """Split a complete popup label into at most five generated cells."""
    output = list(text)
    search_from = 0
    while len(output) > POPUP_CELLS:
        merged = False
        for position in range(search_from, len(output) - 1):
            if len(output[position]) != 1 or len(output[position + 1]) != 1:
                continue
            candidate = output[position] + output[position + 1]
            try:
                _render_compound_glyph(font16, candidate, metrics)
            except ValueError:
                continue
            output[position : position + 2] = [candidate]
            search_from = position + 1
            merged = True
            break
        if not merged:
            # A changed phrase may need a different segmentation than adjacent
            # pairs. Reuse the deterministic capacity solver as a fallback.
            output = list(
                _segment_cells(text, font16, metrics, POPUP_CELLS, "popup")
            )
            break
    if not output or len(output) > POPUP_CELLS:
        raise ValueError(f"Options popup cannot be packed: {text!r}")
    return tuple(output)


def _footer_preferred_compounds(assign: str, finish: str) -> tuple[str, ...]:
    """Derive the mature footer packing from the complete authored phrases.

    These selectors describe the original cell-placement plan, not wording:
    one pair inside the shared heading, one pair across its boundary, and the
    long footer's final three characters.  The selected glyphs are rebuilt
    whenever either full footer is edited.
    """
    common = 0
    for left, right in zip(assign, finish):
        if left != right:
            break
        common += 1
    if common < 7 or len(assign) < common + 3:
        return ()
    candidates = (
        assign[common - 5 : common - 3],
        assign[common - 1 : common + 1],
        assign[-3:],
    )
    if any(len(value) < 2 for value in candidates) or len(set(candidates)) != 3:
        return ()
    return candidates


def _tokenize_with_compounds(
    text: str, compounds: tuple[str, ...]
) -> tuple[str, ...]:
    output: list[str] = []
    position = 0
    while position < len(text):
        compound = next(
            (value for value in compounds if text.startswith(value, position)),
            None,
        )
        if compound is not None:
            output.append(compound)
            position += len(compound)
        else:
            output.append(text[position])
            position += 1
    return tuple(output)


def _segment_cells(
    text: str,
    font16: bytes,
    metrics: Font16Metrics,
    capacity: int,
    context: str,
) -> tuple[str, ...]:
    """Choose a deterministic bounded segmentation from the full phrase."""
    best: list[tuple[str, ...] | None] = [None] * (len(text) + 1)
    best[len(text)] = ()
    for position in range(len(text) - 1, -1, -1):
        candidates: list[tuple[str, ...]] = []
        for length in range(len(text) - position, 0, -1):
            end = position + length
            if end > len(text) or best[end] is None:
                continue
            token = text[position:end]
            if length == 1:
                _encode(token, metrics, f"Options {context}")
            else:
                try:
                    _render_compound_glyph(font16, token, metrics)
                except ValueError:
                    continue
            candidates.append((token, *best[end]))
        if candidates:
            # Fewest cells first; for ties prefer longer earlier cells and then
            # lexical order so an edit always has one reproducible packing.
            best[position] = min(
                candidates,
                key=lambda row: (
                    len(row),
                    tuple(-len(token) for token in row),
                    row,
                ),
            )
    result = best[0]
    if result is None or len(result) > capacity:
        raise ValueError(
            f"Options {context} cannot fit {capacity} cells: {text!r}"
        )
    return result


def _segment_footer(
    text: str,
    font16: bytes,
    metrics: Font16Metrics,
) -> tuple[str, ...]:
    return _segment_cells(text, font16, metrics, FOOTER_CELLS, "footer")


def _derive_compound_plan(
    terms: Mapping[str, str],
    metrics: Font16Metrics,
    font16: bytes,
) -> CompoundPlan:
    popup_records: dict[str, tuple[int | str, ...]] = {}
    popup_compounds: list[str] = []
    for name, _offset in (*MAGIC_SORT_RECORDS, *ITEM_SORT_RECORDS):
        tokens = _popup_tokens(terms[name], font16, metrics)
        popup_records[name] = tokens
        for token in tokens:
            if len(token) > 1 and token not in popup_compounds:
                popup_compounds.append(token)

    assign = terms[FOOTER_RECORDS[0][0]]
    finish = terms[FOOTER_RECORDS[1][0]]
    footer_compounds = _footer_preferred_compounds(assign, finish)
    footer_records = {
        "footer_assign": _tokenize_with_compounds(assign, footer_compounds),
        "footer_finish": _tokenize_with_compounds(finish, footer_compounds),
    }
    preferred_valid = all(
        len(tokens) <= FOOTER_CELLS for tokens in footer_records.values()
    )
    if preferred_valid:
        try:
            for compound in footer_compounds:
                _render_compound_glyph(font16, compound, metrics)
        except ValueError:
            preferred_valid = False
    if not preferred_valid:
        footer_records = {
            "footer_assign": _segment_footer(assign, font16, metrics),
            "footer_finish": _segment_footer(finish, font16, metrics),
        }
        footer_compounds = tuple(
            dict.fromkeys(
                token
                for tokens in footer_records.values()
                for token in tokens
                if len(token) > 1
            )
        )

    compounds = list(footer_compounds) + [
        value for value in popup_compounds if value not in footer_compounds
    ]
    codes = {text: COMPOUND_BASE + index for index, text in enumerate(compounds)}
    if not compounds or len(compounds) > COMPOUND_CAPACITY:
        raise ValueError("Options compound glyph allocation exceeds FONT16 storage")

    return CompoundPlan(
        tuple(compounds),
        MappingProxyType(codes),
        MappingProxyType(popup_records),
        MappingProxyType(footer_records),
    )


def _render_compound_glyph(
    font16: bytes,
    text: str,
    metrics: Font16Metrics,
) -> bytes:
    rows = [0] * 16
    x = 0
    for character in text:
        code = _encode(character, metrics, f"Options compound {text!r}")[0]
        start = code * 32
        cell = font16[start : start + 32]
        if len(cell) != 32 or not metrics.widths[code]:
            raise ValueError(f"Options compound character {character!r} has no glyph")
        for row in range(16):
            word = struct.unpack_from(">H", cell, row * 2)[0]
            if x and word & ((1 << x) - 1):
                raise ValueError(f"Options compound {text!r} clips its right edge")
            rows[row] |= word >> x
        x += metrics.widths[code]
    if x > 16:
        raise ValueError(f"Options compound {text!r} is {x}px wide; maximum is 16px")
    return b"".join(struct.pack(">H", row) for row in rows)


def _assembled(source: Path, address: int, symbols: Mapping[str, int]) -> Assembly:
    try:
        result = assemble_file(source, address, dict(symbols))
    except AssemblyError as error:
        raise ValueError(f"Options assembly failed in {source.name}: {error}") from error
    if result.warnings:
        raise ValueError(f"Options assembly warnings in {source.name}: {result.warnings}")
    return result


def _active_row_runtime(
    renderer_source: Path,
    noop_source: Path,
) -> tuple[bytes, dict[str, int]]:
    renderer = _assembled(
        renderer_source,
        ACTIVE_ROW_RENDERER,
        {
            "SELECTION_TABLE": 0x06029DE4,
            "BRIGHT_COLOR": 0x06029DF8,
            "LABEL_LENGTHS": 0x06029E02,
            "LABEL_TABLE": LABEL_TABLE,
            "DRAW_CONTEXT": 0x060625C0,
            "DRAW_LABEL": 0x06027E74,
            "DRAW_NUMBER": 0x06026AC8,
            "ACTIVE_CACHE": ACTIVE_CACHE,
        },
    )
    noop_address = (ACTIVE_ROW_RENDERER + len(renderer.data) + 3) & ~3
    noop = _assembled(noop_source, noop_address, {})
    payload = bytearray(renderer.data)
    payload.extend(bytes(noop_address - ACTIVE_ROW_RENDERER - len(payload)))
    payload.extend(noop.data)
    return bytes(payload), {
        "active_row_renderer": renderer.labels["active_row_renderer"],
        "active_row_noop": noop.labels["active_row_noop"],
    }


def _action_vwf_code(source: Path) -> bytes:
    symbols = {"ACTION_GLYPH": 0x06027C20, "ACTION_END": ACTION_CAPACITY + 1}
    probe = _assembled(source, ACTION_VWF, {**symbols, "ACTION_WIDTHS": ACTION_VWF + 0x100})
    widths_address = ACTION_VWF + len(probe.data)
    result = _assembled(source, ACTION_VWF, {**symbols, "ACTION_WIDTHS": widths_address})
    if len(result.data) != len(probe.data):
        raise ValueError("Options action VWF assembly size drifted")
    return result.data


def _glyph_vwf_code(
    source: Path,
    metrics: Font16Metrics,
    compound_count: int,
) -> bytes:
    symbols = {
        "STOCK_GLYPH": 0x06027B64,
        "COMPOUND_GLYPH": COMPOUND_GLYPH,
        "COMPOUND_BASE": COMPOUND_BASE,
        "COMPOUND_END": COMPOUND_BASE + compound_count,
        "WIDTH_LIMIT": len(metrics.widths),
        "PADDING": 0xFFFF,
        "WIDTHS": GLYPH_VWF + 0x80,
        "COMPOUND_WIDTHS": GLYPH_VWF + 0x1CC,
    }
    result = _assembled(source, GLYPH_VWF, symbols)
    expected_compound_widths = (
        GLYPH_VWF + len(result.data) + len(metrics.widths) + ACTION_CAPACITY
    )
    if expected_compound_widths != symbols["COMPOUND_WIDTHS"]:
        raise ValueError("Options VWF width-table layout drifted")
    return result.data


def _compound_glyph_code(source: Path, compound_count: int) -> bytes:
    probe = _assembled(
        source,
        COMPOUND_GLYPH,
        {
            "COMPOUND_BASE": COMPOUND_BASE,
            "BITMAPS": COMPOUND_GLYPH + 0x200,
            "BIT_MASK": 0x00008000,
            "FRAMEBUFFER": 0x25C00000,
        },
    )
    bitmaps = (COMPOUND_GLYPH + len(probe.data) + 3) & ~3
    result = _assembled(
        source,
        COMPOUND_GLYPH,
        {
            "COMPOUND_BASE": COMPOUND_BASE,
            "BITMAPS": bitmaps,
            "BIT_MASK": 0x00008000,
            "FRAMEBUFFER": 0x25C00000,
        },
    )
    if len(result.data) != len(probe.data) or compound_count <= 0:
        raise ValueError("Options compound-glyph assembly size drifted")
    return result.data


def _popup_record(
    name: str,
    plan: CompoundPlan,
    metrics: Font16Metrics,
) -> bytes:
    output: list[int] = []
    for token in plan.popup_records[name]:
        if len(token) > 1:
            output.append(plan.codes[token])
        else:
            output.extend(_encode(token, metrics, f"Options popup {name}"))
    if len(output) > POPUP_CELLS:
        raise ValueError(f"Options popup {name} exceeds five cells")
    return struct.pack(
        f">{POPUP_RECORD_CELLS}H",
        *(output + [0xFFFF] * (POPUP_RECORD_CELLS - len(output))),
    )


def _compound_width_data(
    plan: CompoundPlan,
    metrics: Font16Metrics,
) -> bytes:
    values = bytearray()
    for text in plan.compounds:
        width = sum(metrics.widths[code] for code in _encode(text, metrics, "Options compound"))
        if not 1 <= width <= 16:
            raise ValueError(f"Options compound {text!r} has invalid width {width}")
        values.append(width)
    values.extend(bytes(COMPOUND_CAPACITY - len(values)))
    values.extend(bytes((-len(values)) % 4))
    return bytes(values)


def _generated_data(
    base: bytes,
    font16: bytes,
    metrics: Font16Metrics,
    terms: Mapping[str, str],
    plan: CompoundPlan,
    action_atlas: bytes,
    action_widths: bytes,
    action_records: Mapping[str, tuple[int, ...]],
) -> dict[str, bytes]:
    # The first retail row contains "CONFIG", but its paired length is zero and
    # every known draw path therefore skips it.  The visible serif heading is
    # graphical.  Preserve this dormant row for mature-byte parity without
    # presenting it as editable runtime text.
    labels = bytearray(base[DORMANT_LABEL_OFFSET : DORMANT_LABEL_OFFSET + 16])
    if len(labels) != 16:
        raise ValueError("Options dormant label row is truncated")
    labels.extend(bytes(16))
    for name, _offset in LABEL_RECORDS:
        labels.extend(
            _packed_words(
                terms[name], LABEL_CELLS, metrics, f"Options label {name}"
            )
        )

    lengths = []
    for name, _offset in LABEL_RECORDS:
        length = len(_encode(terms[name], metrics, f"Options label {name}"))
        if not 1 <= length <= LABEL_CELLS:
            raise ValueError(f"Options label {name} has an invalid length")
        lengths.append(length)

    generated = {
        "expanded_label_table": bytes(labels),
        "active_row_cache": b"\xff\xff\xff\xff",
        "magic_sort_table": b"".join(
            _popup_record(name, plan, metrics) for name, _offset in MAGIC_SORT_RECORDS
        ),
        "item_sort_table": b"".join(
            _popup_record(name, plan, metrics) for name, _offset in ITEM_SORT_RECORDS
        ),
        "action_widths": action_widths,
        "action_atlas": action_atlas,
        "font16_widths": metrics.widths,
        "action_widths_mirror": action_widths,
        "compound_widths": _compound_width_data(plan, metrics),
        "compound_bitmaps": b"".join(
            _render_compound_glyph(font16, text, metrics) for text in plan.compounds
        ).ljust(COMPOUND_CAPACITY * 32, b"\0"),
        "label_lengths": struct.pack(f">{len(lengths)}H", *lengths),
    }
    for name, _offset, capacity in PAGE2_RECORDS:
        generated[name] = _packed_words(
            terms[name], capacity, metrics, f"Options page-two field {name}"
        )
    for name, _offset in ACTION_RECORDS:
        values = action_records[name]
        generated[name] = struct.pack(
            f">{ACTION_RECORD_CELLS}H",
            *(values + (0,) * (ACTION_RECORD_CELLS - len(values))),
        )
    for name, _offset in FOOTER_RECORDS:
        values = tuple(
            plan.codes[token]
            if len(token) > 1
            else _encode(token, metrics, f"Options footer {name}")[0]
            for token in plan.footer_records[name]
        )
        if len(values) > FOOTER_CELLS:
            raise ValueError(f"Options footer {name} exceeds nine cells")
        generated[name] = struct.pack(
            f">{FOOTER_CELLS}H",
            *(values + (0,) * (FOOTER_CELLS - len(values))),
        )
    return generated


def _assembly_sources(
    config: PatchRecipeConfiguration,
) -> Mapping[str, tuple[Path, ...]]:
    sources = {
        recipe.name: recipe.replacement.sources
        for recipe in config.patches[TARGET]
        if recipe.replacement.kind == "assembly"
    }
    expected_counts = {
        "active_row_runtime": 2,
        "action_vwf_runtime": 1,
        "glyph_vwf_runtime": 1,
        "compound_glyph_runtime": 1,
    }
    if set(sources) != set(expected_counts):
        raise ValueError("Options assembly recipe inventory changed")
    for name, count in expected_counts.items():
        if len(sources[name]) != count:
            raise ValueError(f"Options assembly recipe {name} needs {count} source(s)")
    return MappingProxyType(sources)


def _build_runtime(
    base: bytes | None = None,
    config: PatchRecipeConfiguration | None = None,
) -> RuntimeBuild:
    terms = _options_terms()
    metrics = _font16_metrics()
    try:
        font16 = FONT16_PATH.read_bytes()
    except FileNotFoundError as error:
        raise ValueError(f"missing Options FONT16: {FONT16_PATH}") from error
    if len(font16) != 1872 * 32:
        raise ValueError("Options FONT16 geometry changed")

    plan = _derive_compound_plan(terms, metrics, font16)
    action_atlas, action_widths, action_records = _build_action_atlas(
        font16, metrics, terms
    )
    sources = _assembly_sources(_configuration() if config is None else config)
    active, active_links = _active_row_runtime(*sources["active_row_runtime"])
    assembly = {
        "active_row_runtime": active,
        "action_vwf_runtime": _action_vwf_code(sources["action_vwf_runtime"][0]),
        "glyph_vwf_runtime": _glyph_vwf_code(
            sources["glyph_vwf_runtime"][0], metrics, len(plan.compounds)
        ),
        "compound_glyph_runtime": _compound_glyph_code(
            sources["compound_glyph_runtime"][0], len(plan.compounds)
        ),
    }
    generated = _generated_data(
        _source_cfg_set() if base is None else base,
        font16,
        metrics,
        terms,
        plan,
        action_atlas,
        action_widths,
        action_records,
    )
    links = {
        **active_links,
        "label_table": LABEL_TABLE,
        "item_sort_label": LABEL_TABLE + 7 * LABEL_CELLS * 2,
        "magic_sort_table": MAGIC_SORT_TABLE,
        "item_sort_table": ITEM_SORT_TABLE,
        "action_vwf": ACTION_VWF,
        "action_atlas": ACTION_ATLAS,
        "glyph_vwf": GLYPH_VWF,
    }
    return RuntimeBuild(
        MappingProxyType(assembly),
        MappingProxyType(generated),
        MappingProxyType(links),
        plan.compounds,
    )


def _validate_surfaces() -> None:
    surfaces = load_surfaces()
    expected = {
        "options.primary_label": (("font16", 1, "glyph_cells", 9), (None, None, None, None)),
        "options.value": (("font16", 1, "glyph_cells", 4), (None, None, None, None)),
        "options.ordering_popup": (("font16", 4, "glyph_cells", 5), ("font16", 4, "pixels", 80)),
        "options.controller_action": (("font12", 1, "glyph_cells", 8), ("font12", 1, "pixels", 128)),
        "options.footer": (("font16", 1, "glyph_cells", 9), ("font16", 1, "pixels", 144)),
    }
    for name, (ja_expected, en_expected) in expected.items():
        surface = surfaces.surface(name)
        for layout, wanted in ((surface.ja, ja_expected), (surface.en, en_expected)):
            actual = (layout.font, layout.rows, layout.width.unit, layout.width.value)
            if actual != wanted:
                raise ValueError(f"{name} geometry changed")


def _instruction(source: str, address: int) -> bytes:
    try:
        result = assemble(source, address)
    except AssemblyError as error:
        raise ValueError(f"Options instruction failed at {address:#x}: {error}") from error
    if len(result.data) != 2 or result.warnings:
        raise ValueError(f"Options instruction at {address:#x} is unsafe")
    return result.data


def _bind_patches(
    config: PatchRecipeConfiguration,
    base: bytes,
) -> tuple[tuple[Patch, ...], RuntimeBuild]:
    expected = {
        recipe.name: resolve_recipe_expected(recipe, base, LOAD_ADDRESS)
        for recipe in config.patches[TARGET]
    }
    runtime = _build_runtime(base, config)
    output: list[Patch] = []
    generated_seen: set[str] = set()
    assembly_seen: set[str] = set()
    for recipe in config.patches[TARGET]:
        replacement_recipe = recipe.replacement
        if replacement_recipe.kind == "assembly":
            try:
                replacement = runtime.assembly[recipe.name]
            except KeyError as error:
                raise ValueError(f"unknown Options assembly owner {recipe.name}") from error
            assembly_seen.add(recipe.name)
        elif replacement_recipe.kind == "generated":
            if replacement_recipe.generator != "options_data":
                raise ValueError(f"unknown Options generator for {recipe.name}")
            try:
                replacement = runtime.generated[recipe.name]
            except KeyError as error:
                raise ValueError(f"unknown Options data owner {recipe.name}") from error
            generated_seen.add(recipe.name)
        elif replacement_recipe.kind == "linked_pointer":
            link = replacement_recipe.link
            assert link is not None
            try:
                replacement = struct.pack(">I", runtime.links[link])
            except KeyError as error:
                raise ValueError(f"unknown Options runtime link {link}") from error
        elif replacement_recipe.kind == "instruction":
            source = replacement_recipe.instruction
            assert source is not None
            replacement = _instruction(source, recipe.address)
        else:
            raise ValueError(
                f"{recipe.group}/{recipe.name}: unsupported Options replacement "
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
    unused_generated = set(runtime.generated) - generated_seen
    unused_assembly = set(runtime.assembly) - assembly_seen
    if unused_generated or unused_assembly:
        details = sorted(unused_generated | unused_assembly)
        raise ValueError("Options runtime has no configured owner: " + ", ".join(details))
    return tuple(output), runtime


def build_options_ui(base: bytes | None = None) -> OptionsUiBuild:
    """Build the complete standalone Options interface patch."""
    _validate_surfaces()
    config = _configuration()
    source = _source_cfg_set() if base is None else base
    _validate_inputs(config, source)
    patches, runtime = _bind_patches(config, source)
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
    return OptionsUiBuild(
        apply_patches(source, LOAD_ADDRESS, patches),
        patches,
        ASSET_FILES,
        assembly_files,
        RUNTIME_INPUT_FILES,
        MappingProxyType({"game:CFG_SET.BIN": _sha256(source)}),
        runtime.compounds,
    )
