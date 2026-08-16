"""Build the shared Saturn battle UI renderers from authored text assets."""

from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path

from engine.battle_negotiation import (
    OUTPUT_PATH as COMBAT_OUTPUT_PATH,
    build_battle_negotiation,
)
from engine.patching import Patch, apply_patches
from rom.util.catalog import load_catalog, validate_source
from rom.util.workflows import read_source_files
from text.util.assets import load_asset, load_bound_translations
from text.util.event_codec import load_event_dictionary
from text.util.event_repack import FontMetrics
from text.util.surfaces import load_surfaces


ENGINE_ROOT = Path(__file__).resolve().parent
SATURN_ROOT = ENGINE_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "battle_ui.json"
GENERATED_ROOT = ENGINE_ROOT / "generated" / "game"
NORMCOM_OUTPUT_PATH = GENERATED_ROOT / "battle_ui" / "NORMCOM.BIN"
BUILD_PATH = GENERATED_ROOT / "battle_ui_build.json"
TEXT_ROOT = SATURN_ROOT / "text"
TEXT_GENERATED_ROOT = TEXT_ROOT / "generated" / "game"
TEXT_BUILD_PATH = TEXT_GENERATED_ROOT / "battle_ui_build.json"
CODEC_PATH = TEXT_ROOT / "config" / "event_codec.json"
FONT_ROOT = SATURN_ROOT / "font" / "generated" / "game"
FONT8_METRICS_PATH = FONT_ROOT / "FONT8_metrics.json"
FONT16_METRICS_PATH = FONT_ROOT / "FONT16_metrics.json"

LOAD_ADDRESS = 0x06020000
RENDERER_CAVE = 0x06020400
RENDERER_WIDTHS = 0x060204BC
RENDERER_RACES = 0x06020640
ANALYSIS_CAVE = 0x06021C00
NAME_OFFSETS = 0x06021C00
NAME_POOL = 0x06021E7E
AFFINITY_OFFSETS = 0x0602296C
AFFINITY_POOL = 0x060229F0
AFFINITY_DRAWER = 0x06022D50
RESULT_LIFE_STONES = 0x06022F7C
RESULT_BEADS = 0x06022F87
RESULT_LABEL_DRAWER = 0x06022F8C
CHARACTER_OFFSETS = 0x06023050
CHARACTER_POOL = 0x0602305C
RESULT_NAME_DRAWER = 0x060230AC

DEMON_COUNT = 319
RACE_COUNT = 43
AFFINITY_COUNT = 66
CHARACTER_COUNT = 6
RACE_RECORD_BYTES = 8
NAME_MAX_PIXELS = 96
AFFINITY_MAX_PIXELS = 112
PARTY_NAME_MAX_PIXELS = 80
RESULT_LABEL_MAX_PIXELS = 88
DECODED_RECORD_WORDS = 127

_HASH_RE = re.compile(r"[0-9a-f]{64}\Z")
_HEX_RE = re.compile(r"0x[0-9a-f]+\Z")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        return _sha256(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"missing generated input: {path}") from error


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


def _hash(value: object, context: str) -> str:
    if not isinstance(value, str) or _HASH_RE.fullmatch(value) is None:
        raise ValueError(f"{context} must be a lowercase SHA-256 digest")
    return value


def _hex(value: object, context: str) -> int:
    if not isinstance(value, str) or _HEX_RE.fullmatch(value) is None:
        raise ValueError(f"{context} must be lowercase hexadecimal text")
    return int(value, 16)


def _bytes(value: object, context: str) -> bytes:
    if not isinstance(value, str) or not value or len(value) % 2:
        raise ValueError(f"{context} must be nonempty even-length hexadecimal")
    try:
        return bytes.fromhex(value)
    except ValueError as error:
        raise ValueError(f"{context} contains invalid hexadecimal") from error


def _load_config() -> tuple[
    dict[str, tuple[int, int, str]], dict[str, tuple[Patch, ...]], dict[str, str]
]:
    document = _object(_read_json(CONFIG_PATH), str(CONFIG_PATH))
    if set(document) != {"version", "surface", "targets", "inputs", "groups"}:
        raise ValueError(f"{CONFIG_PATH}: invalid root fields")
    if document["version"] != 1 or document["surface"] != "battle.ui":
        raise ValueError(f"{CONFIG_PATH}: unsupported patch configuration")
    raw_targets = _object(document["targets"], f"{CONFIG_PATH}.targets")
    if set(raw_targets) != {"COMBAT.BIN", "NORMCOM.BIN"}:
        raise ValueError(f"{CONFIG_PATH}: invalid target set")
    targets: dict[str, tuple[int, int, str]] = {}
    for name, raw_target in raw_targets.items():
        target = _object(raw_target, f"{CONFIG_PATH}.targets.{name}")
        if set(target) != {"load_address", "size", "stock_sha256"}:
            raise ValueError(f"{CONFIG_PATH}: invalid {name} target")
        if type(target["size"]) is not int:
            raise ValueError(f"{CONFIG_PATH}: invalid {name} size")
        targets[name] = (
            _hex(target["load_address"], f"{name}.load_address"),
            target["size"],
            _hash(target["stock_sha256"], f"{name}.stock_sha256"),
        )
    raw_inputs = _object(document["inputs"], f"{CONFIG_PATH}.inputs")
    expected_inputs = {
        "font8_metrics_sha256",
        "font16_metrics_sha256",
        "event_runtime_table_sha256",
    }
    if set(raw_inputs) != expected_inputs:
        raise ValueError(f"{CONFIG_PATH}: invalid input set")
    inputs = {
        name: _hash(value, f"{CONFIG_PATH}.inputs.{name}")
        for name, value in raw_inputs.items()
    }
    raw_groups = document["groups"]
    if not isinstance(raw_groups, list) or not raw_groups:
        raise ValueError(f"{CONFIG_PATH}: groups must be a nonempty array")
    patches: dict[str, list[Patch]] = {name: [] for name in targets}
    for group_index, raw_group in enumerate(raw_groups):
        context = f"{CONFIG_PATH}.groups[{group_index}]"
        group = _object(raw_group, context)
        if set(group) != {"capability", "target", "load_address", "patches"}:
            raise ValueError(f"{context}: invalid fields")
        capability = group["capability"]
        target_name = group["target"]
        if not isinstance(capability, str) or not capability:
            raise ValueError(f"{context}: invalid capability")
        if target_name not in targets or group["load_address"] != targets[target_name][0]:
            raise ValueError(f"{context}: invalid target")
        rows = group["patches"]
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"{context}: patches must be nonempty")
        for index, raw_row in enumerate(rows):
            row_context = f"{context}.patches[{index}]"
            row = _object(raw_row, row_context)
            common = {"name", "address"}
            expected_keys = set(row) & {"expected", "expected_zero_bytes"}
            replacement_keys = set(row) & {"replacement", "replacement_zero_bytes"}
            if (
                set(row) != common | expected_keys | replacement_keys
                or len(expected_keys) != 1
                or len(replacement_keys) != 1
                or not isinstance(row["name"], str)
                or not row["name"]
            ):
                raise ValueError(f"{row_context}: invalid patch row")
            if "expected" in row:
                expected = _bytes(row["expected"], f"{row_context}.expected")
            else:
                size = row["expected_zero_bytes"]
                if type(size) is not int or size <= 0:
                    raise ValueError(f"{row_context}: invalid expected zero size")
                expected = bytes(size)
            if "replacement" in row:
                replacement = _bytes(
                    row["replacement"], f"{row_context}.replacement"
                )
            else:
                size = row["replacement_zero_bytes"]
                if type(size) is not int or size <= 0:
                    raise ValueError(f"{row_context}: invalid replacement zero size")
                replacement = bytes(size)
            patches[target_name].append(
                Patch(
                    capability,
                    row["name"],
                    _hex(row["address"], f"{row_context}.address"),
                    expected,
                    replacement,
                )
            )
    return targets, {name: tuple(rows) for name, rows in patches.items()}, inputs


def _validate_surfaces() -> None:
    surfaces = load_surfaces()
    expected = {
        "battle.help": ("font16", 2, 300),
        "battle.demon_chat": ("font16", 2, 176),
        "battle.item_name": ("font8", 1, 80),
        "battle.skill_name": ("font8", 1, 80),
        "battle.analyze_demon_name": ("font8", 1, 112),
        "battle.analyze_affinity": ("font8", 1, 112),
        "battle.party_demon_name": ("font8", 1, 80),
        "party.character_name": ("font8", 1, 80),
        "battle.result_name": ("font8", 1, 88),
    }
    for name, (font, rows, width) in expected.items():
        layout = surfaces.surface(name).en
        if (
            layout.font,
            layout.rows,
            layout.width.unit,
            layout.width.value,
        ) != (font, rows, "pixels", width):
            raise ValueError(f"{name} geometry changed")
    race_heading = surfaces.surface("battle.analyze_race_heading").en
    if (
        race_heading.font,
        race_heading.rows,
        race_heading.width.unit,
        race_heading.width.value,
    ) != ("font8", 1, "glyph_cells", RACE_RECORD_BYTES):
        raise ValueError("battle.analyze_race_heading geometry changed")
    ritual = surfaces.surface("ritual.console").en
    if (
        ritual.font,
        ritual.rows,
        ritual.width.unit,
        ritual.width.value,
    ) != ("font16", None, "pixels", 176):
        raise ValueError("ritual.console geometry changed")


def _validate_text_build(dictionary_digest: str) -> None:
    document = _object(_read_json(TEXT_BUILD_PATH), str(TEXT_BUILD_PATH))
    if (
        document.get("version") != 1
        or document.get("surface") != "battle.ui"
        or document.get("runtime_table_sha256") != dictionary_digest
        or document.get("font8_metrics_sha256") != _file_sha256(FONT8_METRICS_PATH)
        or document.get("font16_metrics_sha256") != _file_sha256(FONT16_METRICS_PATH)
    ):
        raise ValueError("battle UI text build uses different runtime inputs")
    outputs = _object(document.get("outputs"), f"{TEXT_BUILD_PATH}.outputs")
    expected = {
        "BTL_HELP.DAT",
        "BTL_MES.MD8",
        "BTL_SRF.MDT",
        "BUTU_SRF.MDT",
        "ITEMNAME.DAT",
        "MAGNAME.DAT",
    }
    if set(outputs) != expected:
        raise ValueError("battle UI text build has the wrong output set")
    for name, raw_row in outputs.items():
        row = _object(raw_row, f"{TEXT_BUILD_PATH}.outputs.{name}")
        if row.get("sha256") != _file_sha256(TEXT_GENERATED_ROOT / name):
            raise ValueError(f"generated {name} does not match its text build")


def _font8_tables(metrics: FontMetrics) -> tuple[bytes, dict[str, int]]:
    widths = bytearray(256)
    codes: dict[str, int] = {}
    for glyph in metrics.glyphs:
        if not 0 <= glyph.code < 256:
            raise ValueError("battle UI FONT8 code exceeds one byte")
        widths[glyph.code] = glyph.advance
        for text in (glyph.text, *glyph.aliases):
            codes.setdefault(text, glyph.code)
    return bytes(widths), codes


def _encode_font8(
    text: str,
    metrics: FontMetrics,
    max_pixels: int,
    context: str,
    *,
    max_bytes: int = 31,
) -> bytes:
    glyphs = metrics.segment(text)
    encoded = bytes(glyph.code for glyph in glyphs)
    pixels = sum(glyph.advance for glyph in glyphs)
    if len(encoded) > max_bytes or pixels > max_pixels:
        raise ValueError(
            f"{context} exceeds {max_bytes} bytes/{max_pixels}px "
            f"({len(encoded)} bytes, {pixels}px): {text!r}"
        )
    return encoded


def _sequential_translations(prefix: str, ids: list[str]) -> tuple[str, ...]:
    values = load_bound_translations((prefix,), required_ids=set(ids))
    return tuple(values[physical_id] for physical_id in ids)


def _race_pool(metrics: FontMetrics) -> bytes:
    ids = [f"game.normcom_tables.races.r{index:04d}" for index in range(RACE_COUNT)]
    races = _sequential_translations("game.normcom_tables.races.", ids)
    catalog = load_asset("battle/analyze_formats.json")
    entry = catalog.entries["race_heading"]
    if dict(entry.placeholders) != {"race": "demon_race"}:
        raise ValueError("battle Analyze race-heading placeholders changed")
    _reference, template, _reviewed = entry.fields["text"].resolve()
    if template.count("{race}") != 1:
        raise ValueError("battle Analyze race heading must contain one {race}")
    output = bytearray()
    for index, race in enumerate((*races[:-1], "")):
        text = template.replace("{race}", race) if race else ""
        encoded = _encode_font8(
            text,
            metrics,
            0xFFFF,
            f"battle Analyze race {index}",
            max_bytes=RACE_RECORD_BYTES,
        )
        output.extend(encoded.ljust(RACE_RECORD_BYTES, b"\0"))
    return bytes(output)


def _offset_pool(
    values: tuple[str, ...],
    metrics: FontMetrics,
    max_pixels: int,
    context: str,
) -> tuple[bytes, bytes]:
    offsets = bytearray()
    pool = bytearray()
    for index, text in enumerate(values):
        if len(pool) > 0xFFFF:
            raise ValueError(f"{context} pool exceeds u16 offsets")
        offsets.extend(struct.pack(">H", len(pool)))
        pool.extend(
            _encode_font8(text, metrics, max_pixels, f"{context} {index}")
        )
        pool.append(0)
    return bytes(offsets), bytes(pool)


def _dynamic_payloads(metrics: FontMetrics) -> dict[str, bytes]:
    widths, _codes = _font8_tables(metrics)
    demon_ids = [f"game.dvlname.o{index * 8:06x}.text" for index in range(DEMON_COUNT)]
    demons = _sequential_translations("game.dvlname.", demon_ids)
    name_offsets, name_pool = _offset_pool(
        demons, metrics, NAME_MAX_PIXELS, "battle Analyze demon name"
    )
    affinity_ids = [
        f"game.combat_analysis_affinities.affinities.r{index:04d}"
        for index in range(AFFINITY_COUNT)
    ]
    affinities = _sequential_translations(
        "game.combat_analysis_affinities.", affinity_ids
    )
    affinity_offsets, affinity_pool = _offset_pool(
        affinities, metrics, AFFINITY_MAX_PIXELS, "battle Analyze affinity"
    )
    character_ids = [
        f"game.charname.o{index * 8:06x}.text" for index in range(CHARACTER_COUNT)
    ]
    characters = _sequential_translations("game.charname.", character_ids)
    character_offsets, character_pool = _offset_pool(
        characters, metrics, PARTY_NAME_MAX_PIXELS, "battle character name"
    )
    result_ids = {
        "result_beads": "game.combat_result_labels.o053b8c",
        "result_life_stones": "game.combat_result_labels.o053ce0",
    }
    result_values = load_bound_translations(
        ("game.combat_result_labels.",), required_ids=set(result_ids.values())
    )
    return {
        "renderer_widths": widths,
        "renderer_races": _race_pool(metrics),
        "name_offsets": name_offsets,
        "name_pool": name_pool,
        "affinity_offsets": affinity_offsets,
        "affinity_pool": affinity_pool,
        "result_life_stones": _encode_font8(
            result_values[result_ids["result_life_stones"]],
            metrics,
            RESULT_LABEL_MAX_PIXELS,
            "battle result Life Stone label",
        )
        + b"\0",
        "result_beads": _encode_font8(
            result_values[result_ids["result_beads"]],
            metrics,
            RESULT_LABEL_MAX_PIXELS,
            "battle result Bead label",
        )
        + b"\0",
        "character_offsets": character_offsets,
        "character_pool": character_pool,
    }


def _write_region(
    template: bytearray,
    base: int,
    address: int,
    capacity: int,
    payload: bytes,
    context: str,
) -> None:
    offset = address - base
    if offset < 0 or offset + capacity > len(template):
        raise ValueError(f"{context} lies outside its runtime template")
    if len(payload) > capacity:
        raise ValueError(f"{context} uses {len(payload)}/{capacity} bytes")
    template[offset:offset + capacity] = payload.ljust(capacity, b"\0")


def _bind_dynamic_patches(
    patches: tuple[Patch, ...], metrics: FontMetrics
) -> tuple[Patch, ...]:
    payloads = _dynamic_payloads(metrics)
    output: list[Patch] = []
    for patch in patches:
        if patch.name == "renderer_cave":
            template = bytearray(patch.replacement)
            _write_region(
                template,
                patch.address,
                RENDERER_WIDTHS,
                256,
                payloads["renderer_widths"],
                "battle FONT8 widths",
            )
            _write_region(
                template,
                patch.address,
                RENDERER_RACES,
                RACE_COUNT * RACE_RECORD_BYTES,
                payloads["renderer_races"],
                "battle Analyze races",
            )
            patch = Patch(
                patch.group, patch.name, patch.address, patch.expected, bytes(template)
            )
        elif patch.name == "analysis_english_cave":
            template = bytearray(patch.replacement)
            regions = (
                (NAME_OFFSETS, NAME_POOL - NAME_OFFSETS, "name_offsets"),
                (NAME_POOL, AFFINITY_OFFSETS - NAME_POOL, "name_pool"),
                (
                    AFFINITY_OFFSETS,
                    AFFINITY_POOL - AFFINITY_OFFSETS,
                    "affinity_offsets",
                ),
                (AFFINITY_POOL, AFFINITY_DRAWER - AFFINITY_POOL, "affinity_pool"),
                (
                    RESULT_LIFE_STONES,
                    RESULT_BEADS - RESULT_LIFE_STONES,
                    "result_life_stones",
                ),
                (
                    RESULT_BEADS,
                    RESULT_LABEL_DRAWER - RESULT_BEADS,
                    "result_beads",
                ),
                (
                    CHARACTER_OFFSETS,
                    CHARACTER_POOL - CHARACTER_OFFSETS,
                    "character_offsets",
                ),
                (
                    CHARACTER_POOL,
                    RESULT_NAME_DRAWER - CHARACTER_POOL,
                    "character_pool",
                ),
            )
            for address, capacity, name in regions:
                _write_region(
                    template,
                    patch.address,
                    address,
                    capacity,
                    payloads[name],
                    f"battle runtime {name}",
                )
            patch = Patch(
                patch.group, patch.name, patch.address, patch.expected, bytes(template)
            )
        output.append(patch)
    if {patch.name for patch in output} & {"renderer_cave", "analysis_english_cave"} != {
        "renderer_cave",
        "analysis_english_cave",
    }:
        raise ValueError("battle UI config is missing a dynamic runtime cave")
    return tuple(output)


def _validate_decoder_capacity(path: Path, count: int) -> None:
    data = path.read_bytes()
    pointers = struct.unpack_from(f">{count}H", data)
    dictionary = load_event_dictionary(CODEC_PATH)
    body_words = (len(data) - 0x400) // 2
    for index, start in enumerate(pointers):
        stop = pointers[index + 1] if index + 1 < count else body_words
        words = list(struct.unpack_from(f">{stop - start}H", data, 0x400 + start * 2))
        try:
            end = words.index(0x8000)
        except ValueError as error:
            raise ValueError(f"{path.name}: record {index} has no terminator") from error
        decoded = dictionary.decode_words(words[:end])
        if len(decoded) > DECODED_RECORD_WORDS:
            raise ValueError(
                f"{path.name}: record {index} decodes to "
                f"{len(decoded)}/{DECODED_RECORD_WORDS} words"
            )


def build_battle_ui() -> dict[Path, bytes]:
    _validate_surfaces()
    targets, configured_patches, inputs = _load_config()
    dictionary_digest = _sha256(load_event_dictionary(CODEC_PATH).runtime_table())
    actual_inputs = {
        "font8_metrics_sha256": _file_sha256(FONT8_METRICS_PATH),
        "font16_metrics_sha256": _file_sha256(FONT16_METRICS_PATH),
        "event_runtime_table_sha256": dictionary_digest,
    }
    if actual_inputs != inputs:
        raise ValueError("battle UI runtime inputs changed")
    _validate_text_build(dictionary_digest)
    _validate_decoder_capacity(TEXT_GENERATED_ROOT / "BTL_SRF.MDT", 363)
    _validate_decoder_capacity(TEXT_GENERATED_ROOT / "BUTU_SRF.MDT", 144)

    validated = validate_source(load_catalog()["game"])
    stock_files = read_source_files(validated, ("COMBAT.BIN", "NORMCOM.BIN"))
    for name, stock in stock_files.items():
        _load_address, size, digest = targets[name]
        if len(stock) != size or _sha256(stock) != digest:
            raise ValueError(f"stock {name} does not match the battle UI target")

    negotiation_outputs = build_battle_negotiation()
    combat_base = negotiation_outputs[COMBAT_OUTPUT_PATH]
    font8 = FontMetrics.load(FONT8_METRICS_PATH)
    combat_patches = _bind_dynamic_patches(configured_patches["COMBAT.BIN"], font8)
    combat = apply_patches(combat_base, targets["COMBAT.BIN"][0], combat_patches)
    normcom = apply_patches(
        stock_files["NORMCOM.BIN"],
        targets["NORMCOM.BIN"][0],
        configured_patches["NORMCOM.BIN"],
    )
    all_patches = (*combat_patches, *configured_patches["NORMCOM.BIN"])
    manifest = {
        "version": 1,
        "surface": "battle.ui",
        "patch_config_sha256": _file_sha256(CONFIG_PATH),
        "text_build_sha256": _file_sha256(TEXT_BUILD_PATH),
        "base_combat_sha256": _sha256(combat_base),
        "outputs": {
            "COMBAT.BIN": {"sha256": _sha256(combat)},
            "NORMCOM.BIN": {"sha256": _sha256(normcom)},
        },
        "patch_groups": list(dict.fromkeys(patch.group for patch in all_patches)),
        "patches": len(all_patches),
    }
    return {
        COMBAT_OUTPUT_PATH: combat,
        NORMCOM_OUTPUT_PATH: normcom,
        BUILD_PATH: (json.dumps(manifest, indent=2) + "\n").encode("utf-8"),
    }
