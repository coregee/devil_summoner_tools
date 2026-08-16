"""Build the Saturn runtime used by the battle-negotiation surfaces."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path, PurePosixPath

from engine.patching import Patch, apply_patches
from rom.util.catalog import load_catalog, validate_source
from rom.util.workflows import read_source_files
from text.util.assets import load_asset, load_bound_translations
from text.util.event_codec import load_event_dictionary
from text.util.event_repack import FontMetrics
from text.util.surfaces import load_surfaces


ENGINE_ROOT = Path(__file__).resolve().parent
SATURN_ROOT = ENGINE_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "battle_negotiation.json"
GENERATED_ROOT = ENGINE_ROOT / "generated" / "game"
OUTPUT_PATH = GENERATED_ROOT / "COMBAT.BIN"
BUILD_PATH = GENERATED_ROOT / "battle_negotiation_build.json"
TEXT_ROOT = SATURN_ROOT / "text"
TEXT_GENERATED_ROOT = TEXT_ROOT / "generated" / "game"
TEXT_BUILD_PATH = TEXT_GENERATED_ROOT / "battle_negotiation_build.json"
TEXT_COMBAT_PATH = TEXT_GENERATED_ROOT / "COMBAT.BIN"
CODEC_PATH = TEXT_ROOT / "config" / "event_codec.json"
FONT_ROOT = SATURN_ROOT / "font" / "generated" / "game"
FONT16_METRICS_PATH = FONT_ROOT / "FONT16_metrics.json"
FONT8_METRICS_PATH = FONT_ROOT / "FONT8_metrics.json"

NAME_COUNT = 319
RACE_COUNT = 43
NAME_OFFSETS_ADDRESS = 0x06024000
RACE_OFFSETS_ADDRESS = 0x0602427E
FONT8_MAP_ADDRESS = 0x060242D4
STRING_POOL_ADDRESS = 0x060244D4
INSERT_DATA_ADDRESS = NAME_OFFSETS_ADDRESS
INSERT_CODE_ADDRESS = 0x06025D00
FULLWORD_GLYPH_LIMIT = 20


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        return _sha256(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"missing generated input: {path}") from error


def _read_json(path: Path) -> dict[str, object]:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        output: dict[str, object] = {}
        for key, value in pairs:
            if key in output:
                raise ValueError(f"{path}: duplicate JSON field {key!r}")
            output[key] = value
        return output

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates
        )
    except FileNotFoundError as error:
        raise ValueError(f"missing build input: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: invalid JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path}: root must be an object")
    return value


def _object(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return value


def _hex(value: object, context: str) -> int:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise ValueError(f"{context} must be hexadecimal text")
    try:
        return int(value, 16)
    except ValueError as error:
        raise ValueError(f"{context} must be hexadecimal text") from error


def _bytes(value: object, context: str) -> bytes:
    if not isinstance(value, str) or not value or len(value) % 2:
        raise ValueError(f"{context} must be even-length hexadecimal")
    try:
        return bytes.fromhex(value)
    except ValueError as error:
        raise ValueError(f"{context} contains invalid hexadecimal") from error


def _load_config() -> tuple[int, int, str, tuple[Patch, ...], dict[str, int], dict[str, str]]:
    document = _read_json(CONFIG_PATH)
    if set(document) != {
        "version",
        "surface",
        "target",
        "inputs",
        "dynamic_regions",
        "groups",
    } or document["version"] != 1 or document["surface"] != "battle.negotiation":
        raise ValueError(f"{CONFIG_PATH}: unsupported patch configuration")
    target = _object(document["target"], f"{CONFIG_PATH}.target")
    if set(target) != {"path", "load_address", "size", "stock_sha256"}:
        raise ValueError(f"{CONFIG_PATH}: invalid target")
    if target["path"] != "COMBAT.BIN" or type(target["size"]) is not int:
        raise ValueError(f"{CONFIG_PATH}: invalid COMBAT.BIN target")
    stock_digest = target["stock_sha256"]
    if not isinstance(stock_digest, str) or len(stock_digest) != 64:
        raise ValueError(f"{CONFIG_PATH}: invalid stock digest")

    inputs = _object(document["inputs"], f"{CONFIG_PATH}.inputs")
    if set(inputs) != {
        "font16_metrics_sha256",
        "font8_metrics_sha256",
        "event_runtime_table_sha256",
    } or not all(isinstance(value, str) and len(value) == 64 for value in inputs.values()):
        raise ValueError(f"{CONFIG_PATH}: invalid input digests")

    raw_regions = _object(document["dynamic_regions"], f"{CONFIG_PATH}.dynamic_regions")
    if set(raw_regions) != {"kyouji_name", "english_insert_data"}:
        raise ValueError(f"{CONFIG_PATH}: invalid dynamic regions")
    regions: dict[str, int] = {}
    for name, raw_region in raw_regions.items():
        region = _object(raw_region, f"{CONFIG_PATH}.dynamic_regions.{name}")
        if set(region) != {"address", "bytes"} or type(region["bytes"]) is not int:
            raise ValueError(f"{CONFIG_PATH}: invalid {name} region")
        regions[f"{name}_address"] = _hex(region["address"], f"{name}.address")
        regions[f"{name}_bytes"] = region["bytes"]

    raw_groups = document["groups"]
    if not isinstance(raw_groups, list) or not raw_groups:
        raise ValueError(f"{CONFIG_PATH}: groups must be a nonempty array")
    patches: list[Patch] = []
    for raw_group in raw_groups:
        group = _object(raw_group, f"{CONFIG_PATH}.groups")
        if set(group) != {"id", "patches"} or not isinstance(group["id"], str):
            raise ValueError(f"{CONFIG_PATH}: invalid patch group")
        rows = group["patches"]
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"{CONFIG_PATH}: patch group is empty")
        for raw_row in rows:
            row = _object(raw_row, f"{CONFIG_PATH}.patch")
            replacement = _bytes(row.get("replacement"), "patch replacement")
            if "expected" in row:
                expected = _bytes(row["expected"], "patch expected")
            else:
                count = row.get("expected_zero_bytes")
                if type(count) is not int or count <= 0:
                    raise ValueError(f"{CONFIG_PATH}: invalid zero-filled patch")
                expected = bytes(count)
            if set(row) not in (
                {"name", "address", "expected", "replacement"},
                {"name", "address", "expected_zero_bytes", "replacement"},
            ) or not isinstance(row.get("name"), str):
                raise ValueError(f"{CONFIG_PATH}: malformed patch row")
            patches.append(
                Patch(
                    group["id"],
                    row["name"],
                    _hex(row["address"], "patch address"),
                    expected,
                    replacement,
                )
            )
    return (
        _hex(target["load_address"], "target load address"),
        target["size"],
        stock_digest,
        tuple(patches),
        regions,
        inputs,
    )


def _validate_surfaces() -> None:
    surfaces = load_surfaces()
    dialogue = surfaces.surface("battle.negotiation_dialogue")
    choice = surfaces.surface("battle.negotiation_choice")
    if (
        dialogue.en.font,
        dialogue.en.rows,
        dialogue.en.width.unit,
        dialogue.en.width.value,
    ) != ("font16", 3, "pixels", 300):
        raise ValueError("battle negotiation dialogue geometry changed")
    if (
        choice.en.font,
        choice.en.rows,
        choice.en.width.unit,
        choice.en.width.value,
    ) != ("font16", 1, "pixels", 150):
        raise ValueError("battle negotiation choice geometry changed")


def _validate_text_build() -> bytes:
    document = _read_json(TEXT_BUILD_PATH)
    if document.get("version") != 1 or document.get("surface") != "battle.negotiation":
        raise ValueError("battle-negotiation text build has the wrong surface")
    if document.get("codec_sha256") != _file_sha256(CODEC_PATH):
        raise ValueError("battle-negotiation text build uses a different codec")
    outputs = _object(document.get("outputs"), f"{TEXT_BUILD_PATH}.outputs")
    expected = {
        "COMBAT.BIN",
        "ITEMNAME.DAT",
        "COMBDATA/BOSSTALK.EVE",
        "COMBDATA/TLK_BST.EVE",
        "COMBDATA/KEMO.EVE",
        "COMBDATA/TLK_KOFU.EVE",
        "COMBDATA/NBL_M.EVE",
        "COMBDATA/TLK_HIRK.EVE",
        "COMBDATA/TLK_YNGM.EVE",
        "COMBDATA/GRL.EVE",
        "COMBDATA/TLK_BOY.EVE",
        "COMBDATA/CLD_F.EVE",
        "COMBDATA/TLK_LADY.EVE",
        "COMBDATA/TLK_CRZY.EVE",
        "COMBDATA/JIJY.EVE",
        "COMBDATA/CYNI.EVE",
        "COMBDATA/TLK_WEST.EVE",
        "COMBDATA/SLM.EVE",
    }
    if set(outputs) != expected:
        raise ValueError("battle-negotiation text build has the wrong output set")
    for name, raw_row in outputs.items():
        row = _object(raw_row, f"{TEXT_BUILD_PATH}.outputs.{name}")
        if row.get("sha256") != _file_sha256(TEXT_GENERATED_ROOT / name):
            raise ValueError(f"generated {name} does not match its text build")
    return TEXT_COMBAT_PATH.read_bytes()


def _translated_terms() -> tuple[tuple[str, ...], tuple[str, ...], str]:
    demon_ids = {
        f"game.dvlname.o{index * 8:06x}.text" for index in range(NAME_COUNT)
    }
    race_ids = {f"game.normcom_tables.races.r{index:04d}" for index in range(RACE_COUNT)}
    translations = load_bound_translations(
        ("game.dvlname.", "game.normcom_tables.races."),
        required_ids=demon_ids | race_ids,
    )
    demons = tuple(
        translations[f"game.dvlname.o{index * 8:06x}.text"]
        for index in range(NAME_COUNT)
    )
    races = tuple(
        translations[f"game.normcom_tables.races.r{index:04d}"]
        for index in range(RACE_COUNT)
    )
    _reference, kyouji, _reviewed = load_asset(
        PurePosixPath("characters.json")
    ).field("kyouji_kuzunoha.full_name").resolve()
    if not kyouji:
        raise ValueError("Kyouji's full name is untranslated")
    return demons, races, kyouji


def _build_insert_data(
    font16: FontMetrics,
    font8: FontMetrics,
    region_bytes: int,
) -> bytes:
    demons, races, _kyouji = _translated_terms()
    data = bytearray(STRING_POOL_ADDRESS - INSERT_DATA_ADDRESS)
    pool_offset = STRING_POOL_ADDRESS - INSERT_DATA_ADDRESS
    interned: dict[str, int] = {}

    def encode(text: str, context: str) -> int:
        if text in interned:
            return interned[text]
        glyphs = font16.segment(text)
        if len(glyphs) > FULLWORD_GLYPH_LIMIT:
            raise ValueError(f"{context} exceeds the battle insert buffer: {text!r}")
        offset = len(data) - pool_offset
        if not 0 <= offset <= 0xFFFF:
            raise ValueError("battle negotiation string pool exceeds u16 offsets")
        data.extend(struct.pack(f">{len(glyphs) + 1}H", *(g.code for g in glyphs), 0x8000))
        interned[text] = offset
        return offset

    for index, text in enumerate(demons):
        struct.pack_into(">H", data, index * 2, encode(text, f"demon name {index}"))
    race_base = RACE_OFFSETS_ADDRESS - INSERT_DATA_ADDRESS
    for index, text in enumerate(races):
        struct.pack_into(">H", data, race_base + index * 2, encode(text, f"race {index}"))
    map_base = FONT8_MAP_ADDRESS - INSERT_DATA_ADDRESS
    font16_by_text = font16.by_text
    for text, glyph8 in font8.by_text.items():
        glyph16 = font16_by_text.get(text)
        if len(text) == 1 and glyph16 is not None and glyph8.code < 256:
            struct.pack_into(">H", data, map_base + glyph8.code * 2, glyph16.code)

    itemname = (TEXT_GENERATED_ROOT / "ITEMNAME.DAT").read_bytes()
    for record in range(287):
        pointer = struct.unpack_from(">H", itemname, record * 0x60 + 0x5E)[0]
        try:
            terminator = itemname.index(0xFF, pointer, pointer + 20)
        except ValueError as error:
            raise ValueError(f"ITEMNAME record {record} has no runtime terminator") from error
        for code in itemname[pointer:terminator]:
            mapped = struct.unpack_from(">H", data, map_base + code * 2)[0]
            if not mapped:
                raise ValueError(
                    f"ITEMNAME record {record} uses unmapped FONT8 code {code:#04x}"
                )
    if len(data) > region_bytes:
        raise ValueError("battle negotiation insert data exceeds its configured cave")
    data.extend(bytes(region_bytes - len(data)))
    return bytes(data)


def _build_kyouji_name(font16: FontMetrics, region_bytes: int) -> bytes:
    _demons, _races, kyouji = _translated_terms()
    glyphs = font16.segment(kyouji)
    value = struct.pack(f">{len(glyphs) + 1}H", *(g.code for g in glyphs), 0x8000)
    if len(value) > region_bytes:
        raise ValueError("Kyouji's full name exceeds its configured runtime row")
    return value + bytes(region_bytes - len(value))


def build_battle_negotiation() -> dict[Path, bytes]:
    _validate_surfaces()
    load_address, size, stock_digest, static_patches, regions, input_hashes = _load_config()
    font16 = FontMetrics.load(FONT16_METRICS_PATH)
    font8 = FontMetrics.load(FONT8_METRICS_PATH)
    actual_inputs = {
        "font16_metrics_sha256": _file_sha256(FONT16_METRICS_PATH),
        "font8_metrics_sha256": _file_sha256(FONT8_METRICS_PATH),
        "event_runtime_table_sha256": _sha256(
            load_event_dictionary(CODEC_PATH).runtime_table()
        ),
    }
    if actual_inputs != input_hashes:
        raise ValueError("battle-negotiation runtime inputs changed")

    validated = validate_source(load_catalog()["game"])
    stock = read_source_files(validated, ("COMBAT.BIN",))["COMBAT.BIN"]
    if len(stock) != size or _sha256(stock) != stock_digest:
        raise ValueError("stock COMBAT.BIN does not match the patch target")
    translated = _validate_text_build()
    if len(translated) != size:
        raise ValueError("translated COMBAT.BIN has the wrong size")

    dynamic_patches = (
        Patch(
            "combat_vwf_data",
            "kyouji_full_name",
            regions["kyouji_name_address"],
            bytes(regions["kyouji_name_bytes"]),
            _build_kyouji_name(font16, regions["kyouji_name_bytes"]),
        ),
        Patch(
            "combat_vwf_data",
            "english_insert_data",
            regions["english_insert_data_address"],
            bytes(regions["english_insert_data_bytes"]),
            _build_insert_data(font16, font8, regions["english_insert_data_bytes"]),
        ),
    )
    patched = apply_patches(translated, load_address, (*static_patches, *dynamic_patches))
    manifest = {
        "version": 1,
        "surface": "battle.negotiation",
        "patch_config_sha256": _file_sha256(CONFIG_PATH),
        "text_build_sha256": _file_sha256(TEXT_BUILD_PATH),
        "output_sha256": _sha256(patched),
        "patch_groups": list(
            dict.fromkeys(patch.group for patch in (*static_patches, *dynamic_patches))
        ),
        "patches": len(static_patches) + len(dynamic_patches),
    }
    return {
        OUTPUT_PATH: patched,
        BUILD_PATH: (json.dumps(manifest, indent=2) + "\n").encode("utf-8"),
    }
