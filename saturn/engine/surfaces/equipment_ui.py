"""Compose the shared COMP and shop equipment interface from authored text."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path

from engine.shared.font8 import font8_tables
from engine.shared.status_layout import load_stock_latin_glyphs
from engine.core.patching import Patch, apply_patches
from engine.core.patch_recipes import (
    PatchRecipe,
    PatchRecipeConfiguration,
    load_patch_recipe_configuration,
)
from engine.core.sh2 import AssemblyError, assemble, assemble_file
from rom.util.catalog import load_catalog, validate_source
from rom.util.workflows import read_source_files
from text.util.assets import AssetCatalog, load_asset, load_bound_translations
from text.util.event_repack import FontMetrics
from text.util.surfaces import load_surfaces


ENGINE_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = ENGINE_ROOT.parent
PROJECT_ROOT = SATURN_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "equipment_ui.json"
ASSEMBLY_ROOT = ENGINE_ROOT / "asm"
FONT8_METRICS_PATH = SATURN_ROOT / "font" / "generated" / "game" / "FONT8_metrics.json"
EQUIPMENT_ASSET_PATH = PROJECT_ROOT / "assets" / "text" / "ui" / "equipment.json"
STATUS_ASSET_PATH = PROJECT_ROOT / "assets" / "text" / "ui" / "status.json"
SHOP_ASSET_PATH = PROJECT_ROOT / "assets" / "text" / "facilities" / "shop.json"

EVENT_TARGET = "EVENT.BIN"
NORMCOM_TARGET = "NORMCOM.BIN"
TARGETS = {EVENT_TARGET, NORMCOM_TARGET}
LOAD_ADDRESS = 0x06020000

EQUIPMENT_LABEL_TARGETS = {
    EVENT_TARGET: (0x060205A0, 0x06020900, 0x060584E4, 0x0605839C),
    NORMCOM_TARGET: (0x060211A0, 0x06021480, 0x06039C0C, 0x06039AC4),
}

BUY_CAVE = 0x06020900
BUY_CAVE_LIMIT = 0x06021000
BUY_STATE = bytes.fromhex("00000008ffffffff00000000")
FONT8_ADDRESS = 0x00219150
ITEM_BASE = 0x00228C00
ITEM_FIRST = ITEM_BASE + 4
ITEM_END = 0x0022F7A0
FRAMEBUFFER_POINTER = 0x06066354
SHOP_RAW_GLYPH = 0x0602D734
SHOP_CHARACTER_SOURCE_POINTER = 0x0606254C
SHOP_CHARACTER_WIDTH = 72
SHOP_FIXED_CHARACTER_RECORDS = (
    bytes.fromhex("9f77ae9f7793a600"),
    bytes.fromhex("7cac78ed00000000"),
    bytes.fromhex("4e54cd6a4e694100"),
    bytes.fromhex("4e54cd6ad3694100"),
    bytes.fromhex("4e54cd6a49de6941"),
)

BASE_STATS = (
    "strength",
    "intelligence",
    "magic",
    "vitality",
    "agility",
    "luck",
)
DERIVED_STATS = (
    "sword_attack",
    "sword_accuracy",
    "gun_attack",
    "gun_accuracy",
    "defense",
    "evasion",
    "magic_power",
    "magic_defense",
)


@dataclass(frozen=True, slots=True)
class EncodedLabel:
    name: str
    text: str
    data: bytes
    pixels: int


@dataclass(frozen=True, slots=True)
class EquipmentUiBuild:
    event: bytes
    normcom: bytes
    patches: dict[str, tuple[Patch, ...]]
    asset_files: tuple[Path, ...]
    assembly_files: tuple[Path, ...]


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        return _sha256(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"missing equipment UI input: {path}") from error


def _validate_surfaces() -> None:
    expected = {
        "equipment.action": ("font8", 1, "pixels", 40),
        "equipment.base_stat": ("font8", 1, "pixels", 23),
        "equipment.derived_stat": ("font8", 1, "pixels", 48),
        "equipment.item_name": ("font8", 1, "pixels", 80),
        "shop.character_name": ("font8", 1, "pixels", SHOP_CHARACTER_WIDTH),
        "shop.inventory_label": ("font8", 1, "pixels", 16),
    }
    surfaces = load_surfaces()
    for name, geometry in expected.items():
        layout = surfaces.surface(name).en
        actual = (layout.font, layout.rows, layout.width.unit, layout.width.value)
        if actual != geometry:
            raise ValueError(f"{name} geometry changed")


def _translation(catalog: AssetCatalog, asset_ref: str, context: str) -> str:
    _reference, translation, _reviewed = catalog.field(asset_ref).resolve()
    if not translation:
        raise ValueError(f"{context}#{asset_ref} is untranslated")
    return translation


def _encode_label(
    name: str,
    text: str,
    metrics: FontMetrics,
    *,
    max_pixels: int,
    max_glyphs: int = 16,
) -> EncodedLabel:
    glyphs = metrics.segment_output(text)
    if not glyphs or len(glyphs) > max_glyphs:
        raise ValueError(f"{name} must use 1..{max_glyphs} FONT8 glyphs")
    if any(not 0 <= glyph.code < 0xFF or glyph.advance <= 0 for glyph in glyphs):
        raise ValueError(f"{name} uses an invalid FONT8 glyph")
    pixels = sum(glyph.advance for glyph in glyphs)
    if pixels > max_pixels:
        raise ValueError(f"{name} exceeds {max_pixels}px ({pixels}px): {text!r}")
    return EncodedLabel(name, text, bytes(glyph.code for glyph in glyphs), pixels)


def _equipment_labels(metrics: FontMetrics) -> tuple[EncodedLabel, ...]:
    equipment = load_asset("ui/equipment.json")
    status = load_asset("ui/status.json")
    labels = [
        _encode_label(
            "equipment.recommend",
            _translation(equipment, "recommend.text", "ui/equipment.json"),
            metrics,
            max_pixels=40,
        ),
        _encode_label(
            "equipment.unequip",
            _translation(equipment, "unequip.text", "ui/equipment.json"),
            metrics,
            max_pixels=40,
        ),
    ]
    labels.extend(
        _encode_label(
            f"equipment.{name}",
            _translation(status, f"{name}.text", "ui/status.json"),
            metrics,
            max_pixels=23,
        )
        for name in BASE_STATS
    )
    labels.extend(
        _encode_label(
            f"equipment.{name}",
            _translation(status, f"{name}.text", "ui/status.json"),
            metrics,
            max_pixels=48,
        )
        for name in DERIVED_STATS
    )
    return tuple(labels)


def _assembled(
    source: Path,
    address: int,
    symbols: dict[str, int],
    *,
    rendered_source: str | None = None,
) -> bytes:
    try:
        result = (
            assemble(rendered_source, address, symbols)
            if rendered_source is not None
            else assemble_file(source, address, symbols)
        )
    except AssemblyError as error:
        raise ValueError(f"{source.relative_to(ENGINE_ROOT)}: {error}") from error
    if result.warnings:
        raise ValueError(
            f"{source.relative_to(ENGINE_ROOT)}: assembly warnings: {result.warnings}"
        )
    return result.data


def _only_source(recipe: PatchRecipe, expected: str) -> Path:
    sources = recipe.replacement.sources
    if len(sources) != 1 or sources[0].relative_to(ASSEMBLY_ROOT).as_posix() != expected:
        raise ValueError(f"{recipe.group}/{recipe.name}: assembly source contract changed")
    return sources[0]


def _build_label_drawer(
    recipe: PatchRecipe,
    *,
    target: str,
    metrics: FontMetrics,
    widths: bytes,
) -> bytes:
    source = _only_source(recipe, "equipment_ui/label_drawer.s")
    cave, limit, stock_drawer, glyph_drawer = EQUIPMENT_LABEL_TARGETS[target]
    if recipe.address != cave or len(recipe.expected) != limit - cave:
        raise ValueError(f"{target} equipment-label cave contract changed")
    labels = _equipment_labels(metrics)
    symbol_names = (
        "S_RECOMMEND",
        "S_UNEQUIP",
        "S_STRENGTH",
        "S_INTELLIGENCE",
        "S_MAGIC",
        "S_VITALITY",
        "S_AGILITY",
        "S_LUCK",
        "S_SWORD_ATTACK",
        "S_SWORD_ACCURACY",
        "S_GUN_ATTACK",
        "S_GUN_ACCURACY",
        "S_DEFENSE",
        "S_EVASION",
        "S_MAGIC_POWER",
        "S_MAGIC_EFFECT",
    )
    if len(labels) != len(symbol_names):
        raise ValueError("equipment label inventory changed")
    probe_symbols = {
        **dict.fromkeys(symbol_names, 0),
        "WIDTHS": 0,
        "STOCK_DRAW": stock_drawer,
        "GLYPH": glyph_drawer,
    }
    code_size = len(_assembled(source, cave, probe_symbols))

    label_data = bytearray()
    addresses: dict[str, int] = {}
    for symbol, label in zip(symbol_names, labels):
        addresses[symbol] = cave + code_size + len(label_data)
        label_data.extend(label.data)
        label_data.append(0xFF)
    while (cave + code_size + len(label_data)) & 3:
        label_data.append(0)
    addresses["WIDTHS"] = cave + code_size + len(label_data)
    code = _assembled(
        source,
        cave,
        {**addresses, "STOCK_DRAW": stock_drawer, "GLYPH": glyph_drawer},
    )
    if len(code) != code_size:
        raise ValueError("equipment-label assembly layout depends on linked addresses")
    payload = code + bytes(label_data) + widths
    capacity = limit - cave
    if len(payload) > capacity:
        raise ValueError(f"{target} equipment labels use {len(payload)}/{capacity} bytes")
    return payload.ljust(capacity, b"\0")


def _build_item_name_drawer(recipe: PatchRecipe, widths: bytes) -> bytes:
    source = _only_source(recipe, "equipment_item_name.s")
    symbols = {
        "ITEM_FIRST": ITEM_FIRST,
        "ITEM_END": ITEM_END,
        "ITEM_BASE": ITEM_BASE,
        "WIDTHS": 0,
        "GLYPH": EQUIPMENT_LABEL_TARGETS[EVENT_TARGET][3],
        "STOCK": EQUIPMENT_LABEL_TARGETS[EVENT_TARGET][2],
    }
    code_size = len(_assembled(source, recipe.address, symbols))
    symbols["WIDTHS"] = recipe.address + code_size
    code = _assembled(source, recipe.address, symbols)
    payload = code + widths
    if len(payload) > len(recipe.expected):
        raise ValueError("EVENT equipment-name drawer exceeds its cave")
    return payload.ljust(len(recipe.expected), b"\0")


def _shop_inventory_codes(
    metrics: FontMetrics,
) -> tuple[tuple[int, ...], tuple[int, ...], int]:
    shop = load_asset("facilities/shop.json")
    field = shop.field("inventory_label.text")
    text = _translation(shop, "inventory_label.text", "facilities/shop.json")
    if field.font8_alphabet == "replaced":
        label = _encode_label(
            "shop.inventory_label",
            text,
            metrics,
            max_pixels=16,
            max_glyphs=4,
        )
        glyphs = list(metrics.segment_output(label.text))
        blank = metrics.output_by_text.get(" ")
        if blank is None or blank.code >= 0x80:
            raise ValueError("FONT8 space is not a usable shop-label pad")
        codes = [glyph.code for glyph in glyphs]
        advances = [glyph.advance for glyph in glyphs[:-1]]
        while len(codes) < 4:
            codes.append(blank.code)
        while len(advances) < 4:
            advances.append(0)
        return tuple(codes), tuple(advances), 0

    text = text.upper()
    stock = load_stock_latin_glyphs(FONT8_METRICS_PATH)
    if not 1 <= len(text) <= 4:
        raise ValueError("shop.inventory_label must use 1..4 stock FONT8 glyphs")
    try:
        glyphs = [stock[character] for character in text]
    except KeyError as error:
        raise ValueError(
            f"shop.inventory_label uses unsupported stock FONT8 character {error.args[0]!r}"
        ) from error

    # The retail label occupied two 8px compound cells. Draw the preserved
    # one-character glyphs edge-to-edge and remove the first left bearing.
    advances = [
        glyph.ink_right - following.ink_left
        for glyph, following in zip(glyphs, glyphs[1:])
    ]
    if any(advance <= 0 for advance in advances):
        raise ValueError("shop.inventory_label stock glyphs cannot be compacted")
    initial_shift = -glyphs[0].ink_left
    pixels = initial_shift + sum(advances) + glyphs[-1].ink_right
    if pixels > 16:
        raise ValueError(
            f"shop.inventory_label exceeds 16px ({pixels}px): {text!r}"
        )
    codes = [glyph.code for glyph in glyphs]
    blank = stock.get(" ")
    if blank is None:
        raise ValueError("FONT8 stock_latin does not publish a space")
    while len(codes) < 4:
        codes.append(blank.code)
    while len(advances) < 4:
        advances.append(0)
    return tuple(codes), tuple(advances), initial_shift


def _shop_character_data(metrics: FontMetrics) -> tuple[bytes, bytes]:
    ids = [f"game.charname.o{index * 8:06x}.text" for index in range(6)]
    values = load_bound_translations(("game.charname.",), required_ids=set(ids))
    matches = bytearray()
    pool = bytearray()
    for index, signature in enumerate(SHOP_FIXED_CHARACTER_RECORDS, start=1):
        label = _encode_label(
            f"shop character {index}",
            values[ids[index]],
            metrics,
            max_pixels=SHOP_CHARACTER_WIDTH,
            max_glyphs=32,
        )
        offset = len(pool)
        pool.append(label.pixels)
        pool.extend(label.data)
        pool.append(0)
        matches.extend(signature)
        matches.extend(struct.pack(">H", offset))
    return bytes(matches), bytes(pool)


def _render_inventory_source(source: Path, codes: tuple[int, ...]) -> str:
    try:
        text = source.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise ValueError(f"missing equipment assembly source: {source}") from error
    replacements = {
        "@NORMALIZE_0@": "extu.b r0, r0" if codes[0] >= 0x80 else "nop",
        "@NORMALIZE_1@": "extu.b r0, r0" if codes[1] >= 0x80 else "nop",
    }
    for token, instruction in replacements.items():
        if text.count(token) != 1:
            raise ValueError(f"{source}: expected one {token} marker")
        text = text.replace(token, instruction)
    return text


def _align_payload(payload: bytearray, address: int, alignment: int = 4) -> None:
    payload.extend(bytes((-(address + len(payload))) % alignment))


def _build_buy_sell_cave(
    recipe: PatchRecipe,
    metrics: FontMetrics,
    widths: bytes,
) -> tuple[bytes, int, int, int]:
    expected_sources = (
        "font8_pixel_blitter.s",
        "equipment_ui/buy_sell_item_name.s",
        "equipment_ui/shop_inventory_label.s",
        "equipment_ui/shop_character_name.s",
    )
    sources = tuple(path.relative_to(ASSEMBLY_ROOT).as_posix() for path in recipe.replacement.sources)
    if sources != expected_sources or recipe.address != BUY_CAVE:
        raise ValueError("EVENT BUY/SELL assembly contract changed")
    capacity = BUY_CAVE_LIMIT - BUY_CAVE
    if len(recipe.expected) != capacity:
        raise ValueError("EVENT BUY/SELL cave capacity changed")

    pixel_source, drawer_source, inventory_source, character_source = recipe.replacement.sources
    payload = bytearray(_assembled(pixel_source, BUY_CAVE, {"FONT8": FONT8_ADDRESS}))
    _align_payload(payload, BUY_CAVE)

    drawer_address = BUY_CAVE + len(payload)
    drawer_symbols = {
        "ITEM_BASE": ITEM_BASE,
        "FRAMEBUFFER_PTR": FRAMEBUFFER_POINTER,
        "WIDTHS": 0,
        "PIXEL": BUY_CAVE,
    }
    drawer_size = len(_assembled(drawer_source, drawer_address, drawer_symbols))
    widths_address = drawer_address + drawer_size
    drawer_symbols["WIDTHS"] = widths_address
    drawer = _assembled(drawer_source, drawer_address, drawer_symbols)
    if len(drawer) != drawer_size:
        raise ValueError("shop item-name assembly layout depends on linked addresses")
    payload.extend(drawer)
    payload.extend(widths)
    _align_payload(payload, BUY_CAVE)

    inventory_address = BUY_CAVE + len(payload)
    codes, advances, initial_shift = _shop_inventory_codes(metrics)
    inventory_symbols = {
        "INVENTORY_TILE_0_SIGNED": 0xD3 - 0x100,
        "INVENTORY_TILE_1_SIGNED": 0xD4 - 0x100,
        "CODE_0": codes[0],
        "ADVANCE_0": advances[0],
        "CODE_1": codes[1],
        "ADVANCE_1": advances[1],
        "CODE_2_SIGNED": codes[2] if codes[2] < 0x80 else codes[2] - 0x100,
        "ADVANCE_2": advances[2],
        "CODE_3_SIGNED": codes[3] if codes[3] < 0x80 else codes[3] - 0x100,
        "INITIAL_SHIFT": initial_shift,
        "RAW_GLYPH": SHOP_RAW_GLYPH,
    }
    payload.extend(
        _assembled(
            inventory_source,
            inventory_address,
            inventory_symbols,
            rendered_source=_render_inventory_source(inventory_source, codes),
        )
    )
    _align_payload(payload, BUY_CAVE)

    character_address = BUY_CAVE + len(payload)
    matches, name_pool = _shop_character_data(metrics)
    character_symbols = {
        "WIDTHS": widths_address,
        "PIXEL": BUY_CAVE,
        "RAW_GLYPH": SHOP_RAW_GLYPH,
        "PARTY_SOURCE_PTR": SHOP_CHARACTER_SOURCE_POINTER,
        "STATE": character_address,
        "LAST_FIXED": character_address + 4,
        "SUPPRESS": character_address + 8,
        "MATCHES": character_address,
        "MATCH_COUNT": len(matches) // 10,
        "NAME_POOL": character_address,
    }
    character_size = len(_assembled(character_source, character_address, character_symbols))
    state_address = (character_address + character_size + 3) & ~3
    character_symbols.update(
        {
            "STATE": state_address,
            "LAST_FIXED": state_address + 4,
            "SUPPRESS": state_address + 8,
            "MATCHES": state_address + len(BUY_STATE),
            "NAME_POOL": state_address + len(BUY_STATE) + len(matches),
        }
    )
    character = _assembled(character_source, character_address, character_symbols)
    if len(character) != character_size:
        raise ValueError("shop character-name layout depends on linked addresses")
    payload.extend(character)
    payload.extend(bytes(state_address - character_address - len(character)))
    payload.extend(BUY_STATE)
    payload.extend(matches)
    payload.extend(name_pool)
    if len(payload) > capacity:
        raise ValueError(f"EVENT BUY/SELL cave uses {len(payload)}/{capacity} bytes")
    return (
        bytes(payload).ljust(capacity, b"\0"),
        drawer_address,
        inventory_address,
        character_address,
    )


def _instruction(recipe: PatchRecipe) -> bytes:
    assert recipe.replacement.instruction is not None
    try:
        result = assemble(recipe.replacement.instruction, recipe.address)
    except AssemblyError as error:
        raise ValueError(f"{recipe.group}/{recipe.name}: {error}") from error
    if result.warnings or len(result.data) != len(recipe.expected):
        raise ValueError(f"{recipe.group}/{recipe.name}: invalid instruction replacement")
    return result.data


def _bind_patches(
    config: PatchRecipeConfiguration,
    metrics: FontMetrics,
) -> dict[str, tuple[Patch, ...]]:
    widths, _codes = font8_tables(metrics)
    buy_recipe = next(
        recipe
        for recipe in config.patches[EVENT_TARGET]
        if recipe.name == "buy_sell_name_cave"
    )
    buy_payload, buy_drawer, inventory_drawer, character_drawer = _build_buy_sell_cave(
        buy_recipe, metrics, widths
    )
    expected_pointers = {
        "equipment_name_pointer_060596ec": 0x06020400,
        "equipment_name_pointer_0605a6a8": 0x06020400,
        "equipment_name_pointer_0605a914": 0x06020400,
        "shop_inventory_label_pointer_0603407c": inventory_drawer,
        "shop_inventory_label_pointer_06034168": inventory_drawer,
        "shop_inventory_label_pointer_06034264": inventory_drawer,
        "shop_character_name_glyph_pointer_06034650": character_drawer,
        "shop_character_name_glyph_pointer_060347ec": character_drawer,
        "shop_character_name_glyph_pointer_060355e8": character_drawer,
        "shop_character_name_glyph_pointer_06035840": character_drawer,
        "label_drawer_pointer": None,
    }
    output: dict[str, tuple[Patch, ...]] = {}
    for target in (EVENT_TARGET, NORMCOM_TARGET):
        bound: list[Patch] = []
        assembly_seen: set[str] = set()
        for recipe in config.patches[target]:
            replacement_recipe = recipe.replacement
            if replacement_recipe.kind == "assembly":
                assembly_seen.add(recipe.name)
                if recipe.name == "equipment_name_cave" and target == EVENT_TARGET:
                    replacement = _build_item_name_drawer(recipe, widths)
                elif recipe.name == "buy_sell_name_cave" and target == EVENT_TARGET:
                    replacement = buy_payload
                elif recipe.name == "buy_sell_name_hook" and target == EVENT_TARGET:
                    source = _only_source(recipe, "jump_r0.s")
                    replacement = _assembled(source, recipe.address, {"TARGET": buy_drawer})
                elif recipe.name == "label_drawer":
                    replacement = _build_label_drawer(
                        recipe, target=target, metrics=metrics, widths=widths
                    )
                else:
                    raise ValueError(f"unsupported assembly patch {target}/{recipe.name}")
            elif replacement_recipe.kind == "pointer":
                pointer = replacement_recipe.pointer
                expected = expected_pointers.get(recipe.name)
                if recipe.name == "label_drawer_pointer":
                    expected = EQUIPMENT_LABEL_TARGETS[target][0]
                if pointer != expected:
                    raise ValueError(f"{target}/{recipe.name}: pointer contract changed")
                assert pointer is not None
                replacement = struct.pack(">I", pointer)
            elif replacement_recipe.kind == "instruction":
                replacement = _instruction(recipe)
            else:
                raise ValueError(f"{target}/{recipe.name}: unsupported replacement recipe")
            bound.append(
                Patch(
                    recipe.group,
                    recipe.name,
                    recipe.address,
                    recipe.expected,
                    replacement,
                )
            )
        expected_assembly = (
            {"equipment_name_cave", "buy_sell_name_cave", "buy_sell_name_hook", "label_drawer"}
            if target == EVENT_TARGET
            else {"label_drawer"}
        )
        if assembly_seen != expected_assembly:
            raise ValueError(f"{target} has an incomplete assembly contract")
        output[target] = tuple(bound)
    return output


def build_equipment_ui(event_base: bytes, normcom_base: bytes) -> EquipmentUiBuild:
    _validate_surfaces()
    config = load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="equipment.ui",
        target_names=TARGETS,
        input_names={"font8_metrics_sha256"},
    )
    if config.inputs["font8_metrics_sha256"] != _file_sha256(FONT8_METRICS_PATH):
        raise ValueError("equipment UI FONT8 metrics changed")
    metrics = FontMetrics.load(FONT8_METRICS_PATH)
    patches = _bind_patches(config, metrics)

    validated = validate_source(load_catalog()["game"])
    stock = read_source_files(validated, tuple(sorted(TARGETS)))
    bases = {EVENT_TARGET: event_base, NORMCOM_TARGET: normcom_base}
    built = {}
    for target in (EVENT_TARGET, NORMCOM_TARGET):
        contract = config.targets[target]
        source = stock[target]
        if len(source) != contract.size or _sha256(source) != contract.stock_sha256:
            raise ValueError(f"stock {target} does not match the equipment target")
        if len(bases[target]) != contract.size:
            raise ValueError(f"composed {target} has the wrong size")
        built[target] = apply_patches(
            bases[target], contract.load_address, patches[target]
        )
    return EquipmentUiBuild(
        built[EVENT_TARGET],
        built[NORMCOM_TARGET],
        patches,
        (EQUIPMENT_ASSET_PATH, STATUS_ASSET_PATH, SHOP_ASSET_PATH),
        tuple(
            sorted(
                {
                    source
                    for recipes in config.patches.values()
                    for recipe in recipes
                    for source in recipe.replacement.sources
                }
            )
        ),
    )
