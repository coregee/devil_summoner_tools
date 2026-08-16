"""Build the Saturn COMP core on top of the shared NORMCOM runtime."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

from engine.battle_ui import (
    NORMCOM_OUTPUT_PATH as BATTLE_NORMCOM_OUTPUT_PATH,
    build_battle_ui,
)
from engine.patch_config import load_patch_configuration, object_value, read_json
from engine.patching import Patch, apply_patches
from rom.util.catalog import load_catalog, validate_source
from rom.util.workflows import read_source_files
from text.util.assets import load_bound_translations
from text.util.event_repack import FontMetrics
from text.util.surfaces import load_surfaces


ENGINE_ROOT = Path(__file__).resolve().parent
SATURN_ROOT = ENGINE_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "comp_menu.json"
GENERATED_ROOT = ENGINE_ROOT / "generated" / "game"
BUILD_PATH = GENERATED_ROOT / "comp_menu_build.json"
NORMCOM_OUTPUT_PATH = GENERATED_ROOT / "NORMCOM.BIN"
TEXT_GENERATED_ROOT = SATURN_ROOT / "text" / "generated" / "game"
TEXT_BUILD_PATH = TEXT_GENERATED_ROOT / "comp_menu_build.json"
FONT_ROOT = SATURN_ROOT / "font" / "generated" / "game"
FONT8_METRICS_PATH = FONT_ROOT / "FONT8_metrics.json"
FONT16_METRICS_PATH = FONT_ROOT / "FONT16_metrics.json"

TARGET = "NORMCOM.BIN"
LOAD_ADDRESS = 0x06020000
DEMON_COUNT = 319
CHARACTER_COUNT = 6
PANEL_MAX_PIXELS = 80
DIRECT_DEMON_BYTES = 8
DIRECT_DEMON_PIXELS = 64
RENDERER_WIDTHS = 0x060204BC
ITEMNAME_WIDTHS = 0x060210A0
PANEL_CAVE = 0x06025F34
PANEL_LIMIT = 0x06026500
PANEL_DRAWER_TEMPLATE = 0x0602631C
PANEL_DRAWER_BYTES = 464
OLD_PANEL_ADDRESSES = {
    "character_offsets": 0x06025F34,
    "character_pool": 0x06025F40,
    "long_name_bits": 0x06025F8D,
    "name_pool": 0x06025FB6,
    "high_name_pool": 0x06026204,
}
PANEL_POINTER_NAMES = {
    "panel_pointer_06029064",
    "panel_pointer_06029360",
    "panel_pointer_060295e4",
}


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        return _sha256(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"missing generated input: {path}") from error


def _validate_surfaces() -> None:
    surfaces = load_surfaces()
    expected = {
        "comp.help": ("font16", 2, 300),
        "comp.party_demon_name": ("font8", 1, PANEL_MAX_PIXELS),
        "comp.stock_demon_name": ("font8", 1, PANEL_MAX_PIXELS),
        "comp.ability_name": ("font8", 1, 80),
        "party.character_name": ("font8", 1, PANEL_MAX_PIXELS),
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


def _validate_text_build() -> None:
    document = object_value(read_json(TEXT_BUILD_PATH), str(TEXT_BUILD_PATH))
    if (
        document.get("version") != 1
        or document.get("surface") != "comp.menu"
        or document.get("font8_metrics_sha256") != _file_sha256(FONT8_METRICS_PATH)
        or document.get("font16_metrics_sha256")
        != _file_sha256(FONT16_METRICS_PATH)
    ):
        raise ValueError("COMP text build uses different runtime inputs")
    outputs = object_value(document.get("outputs"), f"{TEXT_BUILD_PATH}.outputs")
    if set(outputs) != {"DVLNAME.DAT", "NORMHELP.DAT"}:
        raise ValueError("COMP text build has the wrong output set")
    for name, raw_row in outputs.items():
        row = object_value(raw_row, f"{TEXT_BUILD_PATH}.outputs.{name}")
        if row.get("sha256") != _file_sha256(TEXT_GENERATED_ROOT / name):
            raise ValueError(f"generated {name} does not match its text build")


def _font8_tables(metrics: FontMetrics) -> tuple[bytes, dict[str, int]]:
    widths = bytearray(256)
    codes: dict[str, int] = {}
    for glyph in metrics.glyphs:
        if not 0 <= glyph.code < 256:
            raise ValueError("COMP FONT8 code exceeds one byte")
        widths[glyph.code] = glyph.advance
        for text in (glyph.text, *glyph.aliases):
            codes.setdefault(text, glyph.code)
    return bytes(widths), codes


def _encode_name(
    value: str,
    metrics: FontMetrics,
    context: str,
) -> tuple[bytes, int]:
    glyphs = metrics.segment(value)
    encoded = bytes(glyph.code for glyph in glyphs)
    pixels = sum(glyph.advance for glyph in glyphs)
    if pixels > PANEL_MAX_PIXELS:
        raise ValueError(
            f"{context} exceeds {PANEL_MAX_PIXELS}px ({pixels}px): {value!r}"
        )
    return encoded, pixels


def _pack_title_case_names(
    names: list[tuple[int, str]], *, record_count: int
) -> tuple[bytes, bytes]:
    bits = bytearray((record_count + 7) // 8)
    pool = bytearray()
    previous = -1
    for index, name in names:
        if not 0 <= index < record_count or index <= previous:
            raise ValueError("compact name indices must be ordered and unique")
        previous = index
        bits[index // 8] |= 1 << (index & 7)
        tokens: list[int] = []
        uppercase = True
        for character in name:
            if character.isalpha() and character.isascii():
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
                    f"unsupported compact-name character {character!r} in {name!r}"
                )
        while len(tokens) % 3:
            tokens.append(0)
        for offset in range(0, len(tokens), 3):
            first, second, third = tokens[offset:offset + 3]
            final = offset + 3 == len(tokens)
            pool.extend(
                struct.pack(
                    ">H",
                    (0x8000 if final else 0)
                    | (first << 10)
                    | (second << 5)
                    | third,
                )
            )
    return bytes(bits), bytes(pool)


def _panel_data(metrics: FontMetrics) -> dict[str, bytes]:
    character_ids = [
        f"game.charname.o{index * 8:06x}.text" for index in range(CHARACTER_COUNT)
    ]
    character_values = load_bound_translations(
        ("game.charname.",), required_ids=set(character_ids)
    )
    character_offsets = bytearray()
    character_pool = bytearray()
    for index, physical_id in enumerate(character_ids):
        encoded, _pixels = _encode_name(
            character_values[physical_id], metrics, f"COMP character name {index}"
        )
        character_offsets.extend(struct.pack(">H", len(character_pool)))
        character_pool.extend(encoded)
        character_pool.append(0)

    demon_ids = [
        f"game.dvlname.o{index * DIRECT_DEMON_BYTES:06x}.text"
        for index in range(DEMON_COUNT)
    ]
    demon_values = load_bound_translations(
        ("game.dvlname.",), required_ids=set(demon_ids)
    )
    built_names = (TEXT_GENERATED_ROOT / "DVLNAME.DAT").read_bytes()
    if len(built_names) != DEMON_COUNT * DIRECT_DEMON_BYTES:
        raise ValueError("generated DVLNAME has the wrong size")
    overflow: list[tuple[int, str]] = []
    for index, physical_id in enumerate(demon_ids):
        text = demon_values[physical_id]
        encoded, pixels = _encode_name(text, metrics, f"COMP demon name {index}")
        if len(encoded) <= DIRECT_DEMON_BYTES and pixels <= DIRECT_DEMON_PIXELS:
            record = built_names[
                index * DIRECT_DEMON_BYTES:(index + 1) * DIRECT_DEMON_BYTES
            ]
            if record != encoded.ljust(DIRECT_DEMON_BYTES, b"\0"):
                raise ValueError(f"generated direct demon name {index} is stale")
        else:
            overflow.append((index, text))
    low_bits, low_pool = _pack_title_case_names(
        [(index, text) for index, text in overflow if index < 0x100],
        record_count=0x100,
    )
    high_bits, high_pool = _pack_title_case_names(
        [(index - 0x100, text) for index, text in overflow if index >= 0x100],
        record_count=DEMON_COUNT - 0x100,
    )
    return {
        "character_offsets": bytes(character_offsets),
        "character_pool": bytes(character_pool),
        "long_name_bits": low_bits + high_bits,
        "name_pool": low_pool,
        "high_name_pool": high_pool,
    }


def _replace_address(template: bytes, old: int, new: int, context: str) -> bytes:
    source = struct.pack(">I", old)
    if template.count(source) != 1:
        raise ValueError(f"{context}: expected one address literal {old:#010x}")
    return template.replace(source, struct.pack(">I", new))


def _build_panel_cave(
    template: bytes, metrics: FontMetrics
) -> tuple[bytes, int]:
    capacity = PANEL_LIMIT - PANEL_CAVE
    if len(template) != capacity:
        raise ValueError("COMP panel template does not fill its reserved cave")
    drawer_offset = PANEL_DRAWER_TEMPLATE - PANEL_CAVE
    drawer = template[drawer_offset:drawer_offset + PANEL_DRAWER_BYTES]
    if len(drawer) != PANEL_DRAWER_BYTES:
        raise ValueError("COMP panel drawer template is truncated")
    data = _panel_data(metrics)
    payload = bytearray()
    addresses: dict[str, int] = {}

    def append(name: str, alignment: int = 1) -> None:
        while (PANEL_CAVE + len(payload)) % alignment:
            payload.append(0)
        addresses[name] = PANEL_CAVE + len(payload)
        payload.extend(data[name])

    append("character_offsets", 2)
    append("character_pool")
    append("long_name_bits")
    append("name_pool", 2)
    append("high_name_pool", 2)
    while (PANEL_CAVE + len(payload)) & 3:
        payload.append(0)
    drawer_address = PANEL_CAVE + len(payload)
    for name, old_address in OLD_PANEL_ADDRESSES.items():
        drawer = _replace_address(drawer, old_address, addresses[name], name)
    payload.extend(drawer)
    if len(payload) > capacity:
        raise ValueError(f"COMP party-panel cave uses {len(payload)}/{capacity} bytes")
    return bytes(payload).ljust(capacity, b"\0"), drawer_address


def _bind_dynamic_patches(
    patches: tuple[Patch, ...], metrics: FontMetrics
) -> tuple[Patch, ...]:
    widths, _codes = _font8_tables(metrics)
    panel_patch = next(
        (patch for patch in patches if patch.name == "character_panel_cave"), None
    )
    if panel_patch is None:
        raise ValueError("COMP config is missing the party-panel cave")
    panel, drawer_address = _build_panel_cave(panel_patch.replacement, metrics)
    output: list[Patch] = []
    dynamic_seen: set[str] = set()
    for patch in patches:
        replacement = patch.replacement
        if patch.name == "renderer_cave":
            dynamic_seen.add(patch.name)
            offset = RENDERER_WIDTHS - patch.address
            if offset < 0 or offset + len(widths) > len(replacement):
                raise ValueError("COMP renderer width table lies outside its cave")
            replacement = (
                replacement[:offset] + widths + replacement[offset + len(widths):]
            )
        elif patch.name == "equipment_name_cave":
            dynamic_seen.add(patch.name)
            offset = ITEMNAME_WIDTHS - patch.address
            if offset < 0 or offset + len(widths) > len(replacement):
                raise ValueError("COMP item-name width table lies outside its cave")
            replacement = (
                replacement[:offset] + widths + replacement[offset + len(widths):]
            )
        elif patch.name == "character_panel_cave":
            dynamic_seen.add(patch.name)
            replacement = panel
        elif patch.name in PANEL_POINTER_NAMES:
            dynamic_seen.add(patch.name)
            replacement = struct.pack(">I", drawer_address)
        output.append(
            Patch(patch.group, patch.name, patch.address, patch.expected, replacement)
        )
    expected_dynamic = {
        "renderer_cave",
        "equipment_name_cave",
        "character_panel_cave",
        *PANEL_POINTER_NAMES,
    }
    if dynamic_seen != expected_dynamic:
        raise ValueError("COMP config has an incomplete dynamic runtime contract")
    return tuple(output)


def build_comp_menu() -> dict[Path, bytes]:
    _validate_surfaces()
    _validate_text_build()
    config = load_patch_configuration(
        CONFIG_PATH,
        surface="comp.menu",
        target_names={TARGET},
        input_names={"font8_metrics_sha256", "font16_metrics_sha256"},
    )
    actual_inputs = {
        "font8_metrics_sha256": _file_sha256(FONT8_METRICS_PATH),
        "font16_metrics_sha256": _file_sha256(FONT16_METRICS_PATH),
    }
    if actual_inputs != config.inputs:
        raise ValueError("COMP runtime inputs changed")
    contract = config.targets[TARGET]
    validated = validate_source(load_catalog()["game"])
    stock = read_source_files(validated, (TARGET,))[TARGET]
    if len(stock) != contract.size or _sha256(stock) != contract.stock_sha256:
        raise ValueError("stock NORMCOM.BIN does not match the COMP target")

    battle_outputs = build_battle_ui()
    base = battle_outputs[BATTLE_NORMCOM_OUTPUT_PATH]
    metrics = FontMetrics.load(FONT8_METRICS_PATH)
    patches = _bind_dynamic_patches(config.patches[TARGET], metrics)
    output = apply_patches(base, contract.load_address, patches)
    manifest = {
        "version": 1,
        "surface": "comp.menu",
        "patch_config_sha256": _file_sha256(CONFIG_PATH),
        "text_build_sha256": _file_sha256(TEXT_BUILD_PATH),
        "base_normcom_sha256": _sha256(base),
        "outputs": {TARGET: {"sha256": _sha256(output)}},
        "patch_groups": list(dict.fromkeys(patch.group for patch in patches)),
        "patches": len(patches),
    }
    return {
        NORMCOM_OUTPUT_PATH: output,
        BUILD_PATH: (json.dumps(manifest, indent=2) + "\n").encode("utf-8"),
    }
