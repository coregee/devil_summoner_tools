"""Build the general Saturn EVENT dialogue runtime."""

from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path

from engine.core.patching import Patch, apply_patches
from engine.core.patch_recipes import (
    PatchRecipe,
    PatchRecipeConfiguration,
    load_patch_recipe_configuration,
)
from engine.core.sh2 import Assembly, AssemblyError, assemble, assemble_file
from rom.util.catalog import load_catalog, validate_source
from rom.util.workflows import read_source_files
from text.util.event_codec import load_event_dictionary
from text.util.event_repack import FontMetrics
from text.util.surfaces import load_surfaces


ENGINE_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = ENGINE_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "event_dialogue.json"
GENERATED_ROOT = ENGINE_ROOT / "generated" / "game"
OUTPUT_PATH = GENERATED_ROOT / "event_dialogue" / "EVENT.BIN"
BUILD_PATH = GENERATED_ROOT / "event_dialogue_build.json"
TEXT_ROOT = SATURN_ROOT / "text"
TEXT_GENERATED_ROOT = TEXT_ROOT / "generated" / "game"
TEXT_BUILD_PATH = TEXT_GENERATED_ROOT / "event_build.json"
SHOPSMP_TEXT_BUILD_PATH = TEXT_GENERATED_ROOT / "shopsmp_build.json"
SHOPSMP_TEXT_PATH = TEXT_GENERATED_ROOT / "SHOPSMP.EVE"
CODEC_PATH = TEXT_ROOT / "config" / "event_codec.json"
FONT_ROOT = SATURN_ROOT / "font" / "generated" / "game"
FONT16_METRICS_PATH = FONT_ROOT / "FONT16_metrics.json"
FONT12_METRICS_PATH = FONT_ROOT / "FONT12_metrics.json"
FONT8_METRICS_PATH = FONT_ROOT / "FONT8_metrics.json"
FONT16_PATH = FONT_ROOT / "FONT16.FON"
FONT12_PATH = FONT_ROOT / "FONT12.FON"
ASSEMBLY_ROOT = ENGINE_ROOT / "asm"
TARGET = "EVENT.BIN"
PATCHED_SHA256 = "patched_sha256"
FONT16_SPACE = 267
_HASH = re.compile(r"[0-9a-f]{64}\Z")


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


def _fields(value: dict[str, object], expected: set[str], context: str) -> None:
    if set(value) != expected:
        raise ValueError(
            f"{context} fields are {sorted(value)}, expected {sorted(expected)}"
        )


def _digest(value: object, context: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise ValueError(f"{context} must be a lowercase SHA-256 digest")
    return value


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: Path) -> str:
    try:
        return sha256(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"missing generated input: {path}") from error


def stock_event() -> bytes:
    validated = validate_source(load_catalog()["game"])
    return read_source_files(validated, ("EVENT.BIN",))["EVENT.BIN"]


def _validate_surface() -> None:
    surface = load_surfaces().surface("event.dialogue")
    if (
        surface.en.font != "font16"
        or surface.en.rows != 3
        or surface.en.width.unit != "pixels"
        or surface.en.width.value != 300
    ):
        raise ValueError(
            "event.dialogue engine patch requires font16, three rows, and 300 pixels"
        )


def _validate_text_build(codec_digest: str) -> None:
    document = _object(_read_json(TEXT_BUILD_PATH), str(TEXT_BUILD_PATH))
    _fields(
        document,
        {
            "version",
            "surface",
            "codec_sha256",
            "runtime_table_sha256",
            "font16_metrics_sha256",
            "records",
            "outputs",
        },
        str(TEXT_BUILD_PATH),
    )
    if (
        document["version"] != 1
        or document["surface"] != "event.dialogue"
        or document["codec_sha256"] != codec_digest
    ):
        raise ValueError("general EVENT text build does not match this surface/codec")
    outputs = _object(document["outputs"], f"{TEXT_BUILD_PATH}.outputs")
    expected_names = {
        "MESFILE.EVE",
        "EVFILE_0.EVE",
        "EVFILE_1.EVE",
        "EVFILE_2.EVE",
    }
    if set(outputs) != expected_names:
        raise ValueError("general EVENT text build has the wrong output set")
    for name, raw_row in outputs.items():
        row = _object(raw_row, f"{TEXT_BUILD_PATH}.outputs.{name}")
        if file_sha256(TEXT_GENERATED_ROOT / name) != _digest(
            row.get("sha256"), f"{TEXT_BUILD_PATH}.outputs.{name}.sha256"
        ):
            raise ValueError(f"generated {name} does not match its text build")


def validate_shopsmp_text_build(codec_digest: str) -> None:
    document = _object(
        _read_json(SHOPSMP_TEXT_BUILD_PATH), str(SHOPSMP_TEXT_BUILD_PATH)
    )
    _fields(
        document,
        {
            "version",
            "surface",
            "source",
            "codec_sha256",
            "runtime_table_sha256",
            "font16_metrics_sha256",
            "font12_metrics_sha256",
            "records",
            "deferred",
            "outputs",
        },
        str(SHOPSMP_TEXT_BUILD_PATH),
    )
    if (
        document["version"] != 1
        or document["surface"] != "event.dialogue"
        or document["source"] != "SHOPSMP.EVE"
        or document["codec_sha256"] != codec_digest
        or document["deferred"] is not None
    ):
        raise ValueError("SHOPSMP text build does not match the Fusion surface")
    records = _object(document["records"], f"{SHOPSMP_TEXT_BUILD_PATH}.records")
    if records != {"translated": 763, "deferred": 0, "total": 763}:
        raise ValueError("SHOPSMP text build is not the complete translated bank")
    expected_inputs = {
        "runtime_table_sha256": sha256(
            load_event_dictionary(CODEC_PATH).runtime_table()
        ),
        "font16_metrics_sha256": file_sha256(FONT16_METRICS_PATH),
        "font12_metrics_sha256": file_sha256(FONT12_METRICS_PATH),
    }
    for key, expected in expected_inputs.items():
        if document[key] != expected:
            raise ValueError(f"SHOPSMP text build has stale {key}")
    outputs = _object(document["outputs"], f"{SHOPSMP_TEXT_BUILD_PATH}.outputs")
    if set(outputs) != {"SHOPSMP.EVE"}:
        raise ValueError("SHOPSMP text build has the wrong output set")
    row = _object(
        outputs["SHOPSMP.EVE"],
        f"{SHOPSMP_TEXT_BUILD_PATH}.outputs.SHOPSMP.EVE",
    )
    _fields(
        row,
        {"sha256", "messages", "pages", "body_bytes"},
        f"{SHOPSMP_TEXT_BUILD_PATH}.outputs.SHOPSMP.EVE",
    )
    if file_sha256(SHOPSMP_TEXT_PATH) != _digest(
        row.get("sha256"),
        f"{SHOPSMP_TEXT_BUILD_PATH}.outputs.SHOPSMP.EVE.sha256",
    ):
        raise ValueError("generated SHOPSMP.EVE does not match its text build")


def _font12_widths(metrics: FontMetrics) -> bytes:
    output = bytearray(FONT16_SPACE + 1)
    for glyph in metrics.glyphs:
        if not 0 <= glyph.code < len(output) or not 0 <= glyph.advance <= 0xFF:
            raise ValueError("FONT12 metrics exceed the EVENT width-table contract")
        output[glyph.code] = glyph.advance
    output[FONT16_SPACE] = output[0]
    return bytes(output)


def _font16_layout() -> tuple[int, int]:
    document = _object(_read_json(FONT16_METRICS_PATH), str(FONT16_METRICS_PATH))
    table = _object(
        document.get("width_table"), f"{FONT16_METRICS_PATH}.width_table"
    )
    code_limit = table.get("code_limit")
    storage_glyph = table.get("storage_glyph")
    if (
        document.get("version") != 2
        or document.get("font") != "FONT16.FON"
        or document.get("complete") is not True
        or type(code_limit) is not int
        or type(storage_glyph) is not int
        or code_limit <= 0
        or storage_glyph <= 0
    ):
        raise ValueError("FONT16 metrics have an invalid runtime width layout")
    return code_limit, storage_glyph * 32


def _font12_signature() -> tuple[int, int]:
    try:
        font12 = FONT12_PATH.read_bytes()
        font16 = FONT16_PATH.read_bytes()
    except FileNotFoundError as error:
        raise ValueError(f"missing generated EVENT font: {error.filename}") from error
    record_start = 11 * 32
    candidates = (
        enumerate(
            zip(
                font12[record_start : record_start + 32],
                font16[record_start : record_start + 32],
            ),
            record_start,
        ),
        enumerate(zip(font12, font16)),
    )
    for rows in candidates:
        for offset, (font12_byte, font16_byte) in rows:
            if font12_byte != font16_byte and 0 < font12_byte < 0x80:
                return offset, font12_byte
    raise ValueError("FONT12 and FONT16 have no usable runtime signature")


def _compact_width_tables(metrics: FontMetrics) -> tuple[bytes, int, bytes]:
    glyphs = sorted(metrics.glyphs, key=lambda glyph: glyph.code)
    if len(glyphs) < 2:
        raise ValueError("FONT16 menu widths need at least two glyphs")
    gap_size, split = max(
        (right.code - left.code - 1, index)
        for index, (left, right) in enumerate(zip(glyphs, glyphs[1:]), 1)
    )
    if gap_size <= 0:
        raise ValueError("FONT16 menu widths have no compact-table gap")
    low_glyphs = glyphs[:split]
    high_glyphs = glyphs[split:]
    low = bytearray(low_glyphs[-1].code + 1)
    high_start = high_glyphs[0].code
    high = bytearray(high_glyphs[-1].code - high_start + 1)
    for glyph in low_glyphs:
        low[glyph.code] = glyph.advance
    for glyph in high_glyphs:
        high[glyph.code - high_start] = glyph.advance
    if len(low) > 0x7F or len(high) > 0x7F:
        raise ValueError("FONT16 compact width tables exceed SH-2 immediates")
    return bytes(low), high_start, bytes(high)


def _assembled(
    source: Path, address: int, symbols: dict[str, int]
) -> Assembly:
    try:
        result = assemble_file(source, address, symbols)
    except (AssemblyError, FileNotFoundError) as error:
        raise ValueError(f"{source.relative_to(ENGINE_ROOT)}: {error}") from error
    if result.warnings:
        raise ValueError(
            f"{source.relative_to(ENGINE_ROOT)}: assembly warnings: {result.warnings}"
        )
    return result


def _only_source(recipe: PatchRecipe, expected: str) -> Path:
    sources = recipe.replacement.sources
    if (
        len(sources) != 1
        or sources[0].relative_to(ASSEMBLY_ROOT).as_posix() != expected
    ):
        raise ValueError(f"{recipe.group}/{recipe.name}: assembly source changed")
    return sources[0]


def _advance_payload(
    recipe: PatchRecipe, font12_widths: bytes
) -> bytes:
    source = _only_source(recipe, "event_dialogue/advance.s")
    code_limit, width_offset = _font16_layout()
    signature_offset, signature_value = _font12_signature()
    code = _assembled(
        source,
        recipe.address,
        {
            "TEXT_ADVANCE": 0x06076754,
            "RIGHT_MARGIN": 0x06076E24,
            "FONT16_CODE_LIMIT": code_limit,
            "FONT_MODE": 0x060217FC,
            "FONT16_POINTER": 0x06062598,
            "FONT12_SIGNATURE_OFFSET": signature_offset,
            "FONT12_SIGNATURE_VALUE": signature_value,
            "FONT16_WIDTH_OFFSET": width_offset,
            "FONT12_CODE_LIMIT": len(font12_widths),
            "TEXT_RIGHT_EDGE": 310,
            "CURSOR_X": 0x06076E20,
            "STOCK_ADVANCE": 0x0602BE04,
            "TEXT_LEFT_MARGIN": 10,
        },
    )
    if code.labels.get("font12_widths") != recipe.address + len(code.data):
        raise ValueError("EVENT advance width-table link changed")
    return code.data + font12_widths


def _menu_payload(
    recipe: PatchRecipe,
    font16: FontMetrics,
    font12_widths: bytes,
) -> bytes:
    source = _only_source(recipe, "event_dialogue/menu_glyph.s")
    low, high_start, high = _compact_width_tables(font16)
    signature_offset, signature_value = _font12_signature()
    symbols = {
        "BLITTER": 0x060211F8,
        "FONT16_POINTER": 0x06062598,
        "FONT12_SIGNATURE_OFFSET": signature_offset,
        "FONT12_SIGNATURE_VALUE": signature_value,
        "FONT12_CODE_LIMIT": len(font12_widths),
        "LOW_TABLE_LENGTH": len(low),
        "HIGH_TABLE_LENGTH": len(high),
        "HIGH_START": high_start,
        "LOW_TABLE": 0,
        "FONT12_TABLE": 0,
    }
    probe = _assembled(source, recipe.address, symbols)
    table_address = probe.labels["table_data"]
    symbols.update(
        {
            "LOW_TABLE": table_address + len(high),
            "FONT12_TABLE": table_address + len(high) + len(low),
        }
    )
    code = _assembled(source, recipe.address, symbols)
    if code.labels["table_data"] != table_address:
        raise ValueError("EVENT menu assembly layout depends on linked tables")
    payload = bytearray(code.data)
    payload.extend(high)
    payload.extend(low)
    payload.extend(font12_widths)
    payload.extend(bytes((-len(payload)) % 4))
    return bytes(payload)


def _font12_word_payload(
    recipe: PatchRecipe, font12_widths: bytes
) -> bytes:
    source = _only_source(recipe, "event_dialogue/font12_word_glyph.s")
    symbols = {"SURFACE_BLITTER": 0x0602154C, "WIDTHS": recipe.address}
    probe = _assembled(source, recipe.address, symbols)
    widths_address = (recipe.address + len(probe.data) + 3) & ~3
    symbols["WIDTHS"] = widths_address
    code = _assembled(source, recipe.address, symbols)
    payload = bytearray(code.data)
    payload.extend(bytes(widths_address - recipe.address - len(payload)))
    payload.extend(font12_widths)
    return bytes(payload)


def _packed_fetch_payload(recipe: PatchRecipe, dictionary: bytes) -> bytes:
    source = _only_source(recipe, "event_dialogue/packed_fetch.s")
    symbols = {
        "STATE": recipe.address,
        "DICTIONARY": recipe.address,
        "RETURN_CODE": 0x0602BB8C,
        "RETURN_ZERO": 0x0602BB74,
    }
    probe = _assembled(source, recipe.address, symbols)
    dictionary_address = (recipe.address + len(probe.data) + 3) & ~3
    state_address = (dictionary_address + len(dictionary) + 3) & ~3
    symbols.update({"DICTIONARY": dictionary_address, "STATE": state_address})
    code = _assembled(source, recipe.address, symbols)
    payload = bytearray(code.data)
    payload.extend(bytes(dictionary_address - recipe.address - len(payload)))
    payload.extend(dictionary)
    payload.extend(bytes(state_address - recipe.address - len(payload)))
    payload.extend(bytes(16))
    return bytes(payload)


def _assembly_payload(
    recipe: PatchRecipe,
    *,
    font16: FontMetrics,
    font12_widths: bytes,
    dictionary: bytes,
    links: dict[str, int],
) -> bytes:
    if recipe.name == "dialogue_two_glyph_pacing_cave":
        source = _only_source(recipe, "event_dialogue/two_glyph_pacing.s")
        symbols = {
            "ORIGINAL_UPDATE": 0x0602BB38,
            "VISIBLE_BLITTER": 0x060211F8,
            "VISIBLE_COUNT": recipe.address,
            "TAIL_CONTINUE": 0x0602BBF0,
        }
        probe = _assembled(source, recipe.address, symbols)
        state_address = (recipe.address + len(probe.data) + 3) & ~3
        symbols["VISIBLE_COUNT"] = state_address
        code = _assembled(source, recipe.address, symbols)
        payload = bytearray(code.data)
        payload.extend(bytes(state_address - recipe.address - len(payload)))
        payload.append(0)
        links.update(
            {
                "two_glyph_update": code.labels["two_glyph_update"],
                "two_glyph_blit": code.labels["two_glyph_blit"],
                "two_glyph_tail": code.labels["two_glyph_tail"],
            }
        )
        return bytes(payload)
    if recipe.name in {"dialogue_two_glyph_tail", "fetch_site_1", "fetch_site_2"}:
        source = _only_source(recipe, "event_dialogue/absolute_jump.s")
        target = (
            links["two_glyph_tail"]
            if recipe.name == "dialogue_two_glyph_tail"
            else 0x06023000
        )
        return _assembled(source, recipe.address, {"TARGET": target}).data
    if recipe.name == "advance_cave":
        return _advance_payload(recipe, font12_widths)
    if recipe.name == "subpixel_blitter_cave":
        source = _only_source(recipe, "font16_subpixel_blitter.s")
        return _assembled(
            source,
            recipe.address,
            {
                "FONT16_POINTER": 0x06062598,
                "RIGHT_MARGIN": 0x06076E24,
                "FRAMEBUFFER_POINTER": 0x06067C90,
                "TEXT_COLOR": 0x060BFC98,
                "LINE_HEIGHT": 0x0607675C,
                "PATTERN_LUT": 0x0602B9F4,
                "MASK_LUT": 0x0602BA14,
            },
        ).data
    if recipe.name == "menu_glyph_cave":
        return _menu_payload(recipe, font16, font12_widths)
    if recipe.name == "surface_subpixel_blitter_cave":
        source = _only_source(recipe, "font16_surface_blitter.s")
        return _assembled(
            source,
            recipe.address,
            {
                "FONT12": 0x06062598,
                "PATTERN_LUT": 0x0602B9F4,
                "MASK_LUT": 0x0602BA14,
            },
        ).data
    if recipe.name == "font12_word_menu_cave":
        return _font12_word_payload(recipe, font12_widths)
    if recipe.name == "tracked_font_loader_cave":
        source = _only_source(recipe, "event_dialogue/tracked_font_loader.s")
        return _assembled(
            source,
            recipe.address,
            {
                "FONT12_TAG": 0x31322E46,
                "FONT_MODE": 0x060217FC,
                "FONT12_SPACE": font12_widths[0],
                "SPACE_ADVANCE": 0x060217FE,
                "STOCK_LOADER": 0x0602B91A,
            },
        ).data
    if recipe.name == "zero_cell_space_advance":
        source = _only_source(recipe, "event_dialogue/space_advance.s")
        return _assembled(source, recipe.address, {}).data
    if recipe.name == "fetch_cave":
        return _packed_fetch_payload(recipe, dictionary)
    raise ValueError(f"unsupported EVENT assembly patch {recipe.name}")


def _bind_patches(
    config: PatchRecipeConfiguration,
) -> tuple[tuple[Patch, ...], tuple[Path, ...]]:
    font16 = FontMetrics.load(FONT16_METRICS_PATH)
    font12_widths = _font12_widths(FontMetrics.load(FONT12_METRICS_PATH))
    dictionary = load_event_dictionary(CODEC_PATH).runtime_table()
    links: dict[str, int] = {}
    patches: list[Patch] = []
    assembly_files: set[Path] = set()
    for recipe in config.patches[TARGET]:
        replacement_recipe = recipe.replacement
        if replacement_recipe.kind == "assembly":
            assembly_files.update(replacement_recipe.sources)
            replacement = _assembly_payload(
                recipe,
                font16=font16,
                font12_widths=font12_widths,
                dictionary=dictionary,
                links=links,
            )
        elif replacement_recipe.kind == "pointer":
            assert replacement_recipe.pointer is not None
            replacement = struct.pack(">I", replacement_recipe.pointer)
        elif replacement_recipe.kind == "linked_pointer":
            link = replacement_recipe.link
            if link is None or link not in links:
                raise ValueError(f"{recipe.name}: unresolved EVENT link {link!r}")
            replacement = struct.pack(">I", links[link])
        elif replacement_recipe.kind == "instruction":
            assert replacement_recipe.instruction is not None
            try:
                result = assemble(replacement_recipe.instruction, recipe.address)
            except AssemblyError as error:
                raise ValueError(f"{recipe.group}/{recipe.name}: {error}") from error
            if result.warnings:
                raise ValueError(f"{recipe.name}: instruction assembly warnings")
            replacement = result.data
        else:
            raise ValueError(
                f"{recipe.group}/{recipe.name}: unsupported replacement recipe"
            )
        if len(replacement) != len(recipe.expected):
            raise ValueError(
                f"{recipe.group}/{recipe.name}: replacement owns "
                f"{len(replacement)} bytes, expected {len(recipe.expected)}"
            )
        patches.append(
            Patch(
                recipe.group,
                recipe.name,
                recipe.address,
                recipe.expected,
                replacement,
            )
        )
    expected_links = {"two_glyph_update", "two_glyph_blit", "two_glyph_tail"}
    if set(links) != expected_links:
        raise ValueError("EVENT two-glyph assembly link inventory changed")
    return tuple(patches), tuple(sorted(assembly_files))


def build_event_dialogue() -> dict[Path, bytes]:
    _validate_surface()
    config = load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="event.dialogue",
        target_names={TARGET},
        input_names={
            "font16_metrics_sha256",
            "font12_metrics_sha256",
            "font16_font_sha256",
            "font12_font_sha256",
            "event_runtime_table_sha256",
            PATCHED_SHA256,
        },
    )
    contract = config.targets[TARGET]
    codec_digest = file_sha256(CODEC_PATH)
    _validate_text_build(codec_digest)
    actual_inputs = {
        "font16_metrics_sha256": file_sha256(FONT16_METRICS_PATH),
        "font12_metrics_sha256": file_sha256(FONT12_METRICS_PATH),
        "font16_font_sha256": file_sha256(FONT16_PATH),
        "font12_font_sha256": file_sha256(FONT12_PATH),
        "event_runtime_table_sha256": sha256(
            load_event_dictionary(CODEC_PATH).runtime_table()
        ),
    }
    for key, actual in actual_inputs.items():
        if config.inputs[key] != actual:
            raise ValueError(
                f"event.dialogue patch input {key} is {actual}, "
                f"expected {config.inputs[key]}"
            )
    patches, assembly_files = _bind_patches(config)
    stock = stock_event()
    if len(stock) != contract.size or sha256(stock) != contract.stock_sha256:
        raise ValueError("stock EVENT.BIN does not match the patch target")
    patched = apply_patches(stock, contract.load_address, patches)
    if sha256(patched) != config.inputs[PATCHED_SHA256]:
        raise ValueError("event.dialogue patch output digest is not the proven build")
    manifest = {
        "version": 1,
        "surface": "event.dialogue",
        "patch_config_sha256": file_sha256(CONFIG_PATH),
        "text_build_sha256": file_sha256(TEXT_BUILD_PATH),
        "output_sha256": sha256(patched),
        "patch_groups": list(dict.fromkeys(patch.group for patch in patches)),
        "patches": len(patches),
        "assembly_inputs": {
            path.relative_to(ASSEMBLY_ROOT).as_posix(): file_sha256(path)
            for path in assembly_files
        },
    }
    return {
        OUTPUT_PATH: patched,
        BUILD_PATH: (json.dumps(manifest, indent=2) + "\n").encode("utf-8"),
    }
