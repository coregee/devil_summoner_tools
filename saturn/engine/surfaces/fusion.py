"""Build the Gouma-den fusion consumer directly from authored text assets."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path

from engine.core.patching import Patch, apply_patches
from text.util.assets import BINDING_ROOT, load_asset, load_binding
from text.util.event_repack import FontMetrics
from text.util.surfaces import load_surfaces


ENGINE_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = ENGINE_ROOT.parent
TEXT_ROOT = SATURN_ROOT / "text"
FONT_ROOT = SATURN_ROOT / "font" / "generated" / "game"
FONT16_METRICS_PATH = FONT_ROOT / "FONT16_metrics.json"
FONT12_METRICS_PATH = FONT_ROOT / "FONT12_metrics.json"
FONT8_METRICS_PATH = FONT_ROOT / "FONT8_metrics.json"

LOAD_ADDRESS = 0x06020000
CAVE_ADDRESS = 0x06021800
CAVE_END = 0x06022FBC
PACKED_FETCH_ADDRESS = 0x06023000
NAME_SORT_ADDRESS = 0x060451E0
NAME_SORT_SIZE = 0x200
NAME_SORT_STOCK_SHA256 = (
    "125d4a15c59aabee09003bba2ee91e81e5d5fde47c9c5a5d98f3133ad86b1638"
)

DEMON_COUNT = 319
CHARACTER_COUNT = 6
RACE_COUNT = 43
TERMINATOR = 0xFF
WORD_TERMINATOR = 0x8000
FONT16_SPACE = 267

LIST_NAME_WIDTH = 96
PREVIEW_NAME_WIDTH = 96
PREVIEW_RACE_WIDTH = 24
TABLE_NAME_WIDTH = 96
TABLE_RACE_WIDTH = 40
CHART_CELL_WIDTH = 26
GUIDE_WIDTH = 300
GUIDE_GLYPH_LIMIT = 100
HELP_WIDTH = 284
HELP_GLYPH_LIMIT = 94

MAIN_FILE = 0x5458E
MAIN_SIZE = 0xA0
POINTER_TABLE_OFFSET = 2
LABEL_YES_FILE = MAIN_FILE + MAIN_SIZE
LABEL_NO_FILE = LABEL_YES_FILE + 8
CONFIRMATION_WORDS = {
    "confirm_prompt": 20,
    "level_too_low": 34,
    "duplicate_demon": 30,
    "begin_fusion": 20,
    "label_yes": 4,
    "label_no": 4,
}

# These three position-independent blobs are the isolated mature Saturn
# renderer templates. Their writable inputs are the explicit literal slots in
# NAME_DRAWER_RELOCATIONS below; no prose or display labels live here.
SURFACE_BLITTER = bytes.fromhex(
    "2f862f962fa62fb62fc62fd62fe66a43695365636673d123681251f7641d4408"
    "44084400384c5bf86bbced00616331dc611d219e021a6353332c6184611c4118"
    "6284622c212b6033c903e7043708410047108bfc62334209322c32ace7056013"
    "40194019c90f20088d0a300cd40e044d2b4ede0e0eed602120e90e1a30ec220"
    "141084108720247108be97d01e1103d108bcc6ef66df66cf66bf66af669f6000"
    "b68f60009060625980602b9f40602ba14"
)
FONT8_BLITTER = bytes.fromhex(
    "2f862f962fa62fb62fc62fd62fe64f226843695349016a636073209e0e1a38e"
    "c5cf9e00f2c095bf86bbd4b084b00d01e3b0ced002d9e0e1a3e8c66b4666ce"
    "70063a3e1802618890461e3623360c3b01400094600666c73017701e0083702"
    "8bf07d01e0083d028be54f266ef66df66cf66bf66af669f6000b68f6e501225"
    "889084201312c6210622ce5f02259220b000b21204201312c6210622ce50f225"
    "940084008220b000b212000219150"
)
NAME_DRAWERS = bytes.fromhex(
    "61f2611dd0ad3108e02b31028b02d0ac402b00092f862f962fa62fb62fc62fd6"
    "2fe64f227ff84100d0a6301c6001600dd8a5380ce218a08ee30261f2611dd09f"
    "3108e02b31028b02d09d402b00092f862f962fa62fb62fc62fd62fe64f227ff8"
    "d29a6013022c622ce01a30284001360c4100d097301c6001600dd896380ca06a"
    "e30461f2611de02b31028b02d092402b00092f862f962fa62fb62fc62fd62fe6"
    "4f227ff84100d08a301c6001600dd889380ce228a04fe304a003e304a001e300"
    "e30261f2611d71ffd08431028b02d084402b00092f862f962fa62fb62fc62fd6"
    "2fe64f227ff84100d07e301c6001600dd87d380ce260a02e000960f2600dd17b"
    "3010891a600ce10630128b02d078402b000961032f862f962fa62fb62fc62fd6"
    "2fe64f227ff84100d072301c6001600dd871380ce260a00d00092f862f962fa6"
    "2fb62fc62fd62fe64f227ff8d86be260a001e301e30069436a536b636c735dfb"
    "2f3260b3302c1f016033c8018b08ee206284622ce0ff600c32008948a00b0009"
    "ee0862817802622dd05d3200893fd05d32008b00e20063f2e00433008b06d15a"
    "6023021c622cd159a0010009d1586023011c611c2118892ae00433008b03e03f"
    "32008900710166b33b1c50f13b06891e649365a367c32fd62f2653f2e0043300"
    "8908e00233028902d04aa0050009d04aa00200097702d049400b00097f084e10"
    "890563f26033c80189b2afba00097f084f266ef66df66cf66bf66af669f6000"
    "b68f62f862f964f2258f3688d59f4e0ff600c3806891ad1346083081c688ce0"
    "ff600c380089122f962f867702d033400b00097f08d12d6083001c600ce13f38"
    "10890070014f2669f6000b68f62f962f86d029400b00097f08e00caff300094f"
    "2290503702890d26688b0b51f22f1651f22f16d021400b00097f08e00f3b0ca"
    "009000951f22f1651f22f16d01d400b00097f083b0c4f26000b000900000000"
    "00db0603c4100602190c06021bec060227ec06022690060226e60603c4c80000"
    "013f0603c50c0602196206021c6d000080000603c5c806021be0060226420023"
    "fe14000080000000010b06022917060228170602180006022a180603b7600602"
    "2ac806022d960096"
)
NAME_SORT_TEMPLATE = bytes.fromhex(
    "2f862f962fa62fb62fc62fd62fe6d0296801688de00238028b444800d0266a02"
    "d0266b02d0266c02dd26e9006693760236828932609304ad644d74ff44006043"
    "04dd644d606305ad655d75ff4500605305dd655d3456890934508b1c609304ad"
    "644d606305ad655d34568b14609301ad606302ad0a1560930a25609301bd6063"
    "02bd0b1560930b25609301cd606302cd0c1560930c25afcb760279026e837efe"
    "39e28bc36ef66df66cf66bf66af669f6000b68f6060768a806068e7806068e7"
    "c06068e8006021962"
)

NAME_DRAWER_RELOCATIONS = {
    708: "race_offsets",
    712: "race_pool",
    716: "chart_widths",
    720: "table_race_offsets",
    724: "table_race_pool",
    740: "demon_offsets",
    744: "demon_pool",
    756: "character_offsets",
    760: "character_pool",
    776: "font8_map",
    780: "font8_widths",
    784: "font12_widths",
    788: "surface_blitter",
    796: "font8_blitter",
    800: "fusion_word_font8_glyph",
}
NAME_DRAWER_LABELS = {
    "fusion_preview_race": 0x000,
    "fusion_chart_race": 0x03A,
    "fusion_table_race": 0x082,
    "fusion_table_demon": 0x0B8,
    "fusion_demon_name": 0x0BC,
    "fusion_preview_demon": 0x0C0,
    "fusion_character_name": 0x0FA,
    "fusion_word_font8_glyph": 0x222,
    "fusion_guide_mixed_glyph": 0x27E,
}


@dataclass(frozen=True, slots=True)
class FusionBuild:
    data: bytes
    runtime: bytes
    addresses: dict[str, int]
    patches: tuple[Patch, ...]
    asset_files: tuple[Path, ...]


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _align(payload: bytearray, alignment: int) -> None:
    payload.extend(bytes((-len(payload)) % alignment))


def _name_rows(binding_name: str, prefix: str, count: int) -> tuple[str, ...]:
    binding = load_binding(BINDING_ROOT / binding_name)
    catalog = load_asset(binding.asset)
    output: list[str] = []
    for index in range(count):
        physical_id = f"{prefix}.o{index * 8:06x}.text"
        try:
            asset_ref = binding.records[physical_id]
        except KeyError as error:
            raise ValueError(f"{binding_name}: missing {physical_id}") from error
        translation = catalog.field(asset_ref).resolve(
            binding.variants.get(physical_id)
        )[1]
        if not translation:
            raise ValueError(f"{binding_name}: {asset_ref} has no translation")
        output.append(translation)
    return tuple(output)


def _race_rows() -> tuple[tuple[str, str, str], ...]:
    binding = load_binding(BINDING_ROOT / "races.json")
    catalog = load_asset(binding.asset)
    rows: list[tuple[str, str, str]] = []
    for index in range(RACE_COUNT):
        physical_id = f"game.normcom_tables.races.r{index:04d}"
        asset_ref = binding.records[physical_id]
        entry_name = asset_ref.split(".", 1)[0]
        entry = catalog.entries[entry_name]
        table_field = "fusion_name" if entry_name == "human" else "name"
        values = tuple(
            entry.fields[field].translation
            for field in (
                table_field,
                "fusion_preview_label",
                "fusion_chart_label",
            )
        )
        if not all(values):
            raise ValueError(f"races.json: {entry_name} has incomplete fusion text")
        rows.append(values)
    return tuple(rows)


def _codes(metrics: FontMetrics) -> dict[str, int]:
    return {
        text: glyph.code
        for text, glyph in metrics.by_text.items()
        if len(text) == 1
    }


def _widths(metrics: FontMetrics, size: int) -> bytes:
    output = bytearray(size)
    for glyph in metrics.glyphs:
        if not 0 <= glyph.code < size:
            raise ValueError(f"{metrics.font}: glyph code exceeds width table")
        output[glyph.code] = glyph.advance
    return bytes(output)


def _encode_pool(
    values: tuple[str, ...], codes: dict[str, int]
) -> tuple[bytes, bytes]:
    offsets: list[int] = []
    pool = bytearray()
    for value in values:
        offsets.append(len(pool))
        try:
            pool.extend(codes[character] for character in value)
        except KeyError as error:
            raise ValueError(f"unsupported fusion character {error.args[0]!r}") from error
        pool.append(TERMINATOR)
    if len(pool) > 0xFFFF:
        raise ValueError("fusion text pool exceeds 16-bit offsets")
    return struct.pack(f">{len(offsets)}H", *offsets), bytes(pool)


def _english_name_key(value: str) -> str:
    key = "".join(
        character.lower()
        for character in value
        if character not in " -'"
    )
    if not key or not key.isascii() or not key.isalnum():
        raise ValueError(f"unsupported fusion sort name {value!r}")
    return key


def _encode_sorted_pool(
    values: tuple[str, ...], codes: dict[str, int]
) -> tuple[bytes, bytes]:
    names_by_key: dict[str, set[str]] = {}
    for value in values:
        names_by_key.setdefault(_english_name_key(value), set()).add(value)
    collisions = {key: rows for key, rows in names_by_key.items() if len(rows) > 1}
    if collisions:
        raise ValueError(f"fusion demon-name sort collisions: {collisions}")
    offsets_by_name: dict[str, int] = {}
    pool = bytearray()
    for key in sorted(names_by_key):
        value = next(iter(names_by_key[key]))
        offsets_by_name[value] = len(pool)
        pool.extend(codes[character] for character in value)
        pool.append(TERMINATOR)
    offsets = struct.pack(
        f">{len(values)}H", *(offsets_by_name[value] for value in values)
    )
    return offsets, bytes(pool)


def _font8_map(
    font12_codes: dict[str, int],
    font8_codes: dict[str, int],
    requested: tuple[str, ...],
) -> bytes:
    output = bytearray([0xFF] * 256)
    for character in set(font12_codes) & set(font8_codes):
        code12 = font12_codes[character]
        code8 = font8_codes[character]
        if not 0 <= code12 < 256 or not 0 <= code8 < 256:
            continue
        existing = output[code12]
        if existing not in (0xFF, code8):
            raise ValueError(f"FONT12 code {code12:#x} has two FONT8 mappings")
        output[code12] = code8
    missing = sorted(
        character
        for character in set("".join(requested))
        if character not in font12_codes
        or output[font12_codes[character]] == 0xFF
    )
    if missing:
        raise ValueError(f"fusion FONT8 mapping is missing {''.join(missing)!r}")
    return bytes(output)


def _chart_widths(
    table_rows: tuple[str, ...],
    authored_rows: tuple[str, ...],
    font8: FontMetrics,
) -> bytes:
    glyphs = font8.by_text
    output = bytearray()
    derived: list[str] = []
    for value in table_rows:
        text: list[str] = []
        width = 0
        for character in value:
            glyph = glyphs[character]
            advance = glyph.advance + (character != " ")
            if width + advance > CHART_CELL_WIDTH:
                break
            text.append(character)
            width += advance
        if not text:
            raise ValueError(f"fusion chart label {value!r} has no fitting prefix")
        derived.append("".join(text))
        output.append(width)
    if tuple(derived) != authored_rows:
        raise ValueError(
            "fusion chart runtime prefixes disagree with fusion_chart_label assets"
        )
    return bytes(output)


def _validate_surfaces() -> None:
    surfaces = load_surfaces()
    expected = {
        "fusion.status_name": ("font12", LIST_NAME_WIDTH),
        "fusion.preview_demon_name": ("font12", PREVIEW_NAME_WIDTH),
        "fusion.preview_race": ("font12", PREVIEW_RACE_WIDTH),
        "fusion.chart_race": ("font8", CHART_CELL_WIDTH),
        "fusion.table_race": ("font8", TABLE_RACE_WIDTH),
        "fusion.table_demon_name": ("font8", TABLE_NAME_WIDTH),
        "fusion.table_character_name": ("font12", TABLE_NAME_WIDTH),
        "fusion.guide": ("font12", GUIDE_WIDTH),
        "fusion.help": ("font8", HELP_WIDTH),
    }
    for name, (font, width) in expected.items():
        layout = surfaces.surface(name).en
        if (
            layout.font != font
            or layout.rows != 1
            or layout.width.unit != "pixels"
            or layout.width.value != width
        ):
            raise ValueError(f"{name} does not match the proved fusion geometry")


def _runtime_payload() -> tuple[bytes, dict[str, int], tuple[Path, ...]]:
    font12 = FontMetrics.load(FONT12_METRICS_PATH)
    font8 = FontMetrics.load(FONT8_METRICS_PATH)
    demon_names = _name_rows("demons.json", "game.dvlname", DEMON_COUNT)
    character_names = _name_rows("characters.json", "game.charname", CHARACTER_COUNT)
    race_rows = _race_rows()
    table_races = tuple(row[0] for row in race_rows)
    preview_races = tuple(row[1] for row in race_rows)
    chart_races = tuple(row[2] for row in race_rows)
    codes12 = _codes(font12)
    codes8 = _codes(font8)

    race_offsets, race_pool = _encode_pool(preview_races, codes12)
    demon_offsets, demon_pool = _encode_sorted_pool(demon_names, codes12)
    character_offsets, character_pool = _encode_pool(character_names, codes12)
    table_offsets, table_pool = _encode_pool(table_races, codes12)
    chart_widths = _chart_widths(table_races, chart_races, font8)
    widths12 = bytearray(_widths(font12, FONT16_SPACE + 1))
    widths12[FONT16_SPACE] = widths12[0]
    widths8 = _widths(font8, 256)
    code_map = _font8_map(codes12, codes8, (*table_races, *demon_names))

    payload = bytearray(widths12)
    addresses = {"font12_widths": CAVE_ADDRESS}

    def append(name: str, value: bytes, *, alignment: int = 1) -> None:
        _align(payload, alignment)
        addresses[name] = CAVE_ADDRESS + len(payload)
        payload.extend(value)

    append("race_offsets", race_offsets)
    append("demon_offsets", demon_offsets)
    append("character_offsets", character_offsets)
    append("race_pool", race_pool)
    append("demon_pool", demon_pool)
    append("character_pool", character_pool)
    append("table_race_offsets", table_offsets, alignment=2)
    append("table_race_pool", table_pool)
    append("chart_widths", chart_widths)
    append("font8_widths", widths8)
    append("font8_map", code_map)
    append("surface_blitter", SURFACE_BLITTER, alignment=4)
    append("font8_blitter", FONT8_BLITTER, alignment=4)
    _align(payload, 4)
    drawer_address = CAVE_ADDRESS + len(payload)
    addresses.update(
        {
            name: drawer_address + offset
            for name, offset in NAME_DRAWER_LABELS.items()
        }
    )
    drawer = bytearray(NAME_DRAWERS)
    for offset, name in NAME_DRAWER_RELOCATIONS.items():
        struct.pack_into(">I", drawer, offset, addresses[name])
    addresses["name_drawers"] = drawer_address
    payload.extend(drawer)
    if CAVE_ADDRESS + len(payload) > CAVE_END:
        raise ValueError(
            f"fusion runtime exceeds its cave by {CAVE_ADDRESS + len(payload) - CAVE_END} bytes"
        )
    return bytes(payload), addresses, (
        BINDING_ROOT / "demons.json",
        BINDING_ROOT / "characters.json",
        BINDING_ROOT / "races.json",
        BINDING_ROOT / "facilities_gouma_den.json",
        TEXT_ROOT.parent.parent / "assets" / "text" / "demons.json",
        TEXT_ROOT.parent.parent / "assets" / "text" / "characters.json",
        TEXT_ROOT.parent.parent / "assets" / "text" / "races.json",
        TEXT_ROOT.parent.parent / "assets" / "text" / "facilities" / "gouma_den.json",
    )


def _pointer_patches(
    group: str,
    prefix: str,
    sites: tuple[int, ...],
    expected: int,
    replacement: int,
) -> tuple[Patch, ...]:
    return tuple(
        Patch(
            group,
            f"{prefix}_{site:08x}" if len(sites) > 1 else prefix,
            site,
            struct.pack(">I", expected),
            struct.pack(">I", replacement),
        )
        for site in sites
    )


def _confirmation_patches(
    original: bytes,
    addresses: dict[str, int],
    font16: FontMetrics,
) -> tuple[Patch, ...]:
    binding = load_binding(BINDING_ROOT / "facilities_gouma_den.json")
    catalog = load_asset(binding.asset)

    def field(name: str) -> bytes:
        physical_id = {
            "confirm_prompt": "game.fusion_confirmation_static.o05458e",
            "level_too_low": "game.fusion_confirmation_static.o0545b6",
            "duplicate_demon": "game.fusion_confirmation_static.o0545de",
            "begin_fusion": "game.fusion_confirmation_static.o054606",
            "label_yes": "game.fusion_confirmation_static.o05462e",
            "label_no": "game.fusion_confirmation_static.o054636",
        }[name]
        text = catalog.field(binding.records[physical_id]).translation
        words = font16.encode(text, dictionary=None)
        capacity = CONFIRMATION_WORDS[name]
        if len(words) + 1 > capacity:
            raise ValueError(f"fusion confirmation {name} exceeds {capacity} words")
        words.append(WORD_TERMINATOR)
        words.extend([0] * (capacity - len(words)))
        return struct.pack(f">{capacity}H", *words)

    confirm = field("confirm_prompt")
    level = field("level_too_low")
    duplicate = field("duplicate_demon")
    begin = field("begin_fusion")
    label_yes = field("label_yes")
    label_no = field("label_no")
    table_address = LOAD_ADDRESS + MAIN_FILE + POINTER_TABLE_OFFSET
    pointers = (
        table_address + 16,
        CAVE_END,
        table_address + 16 + len(confirm),
        table_address + 16 + len(confirm) + len(duplicate),
    )
    main = bytearray(POINTER_TABLE_OFFSET)
    main.extend(struct.pack(">4I", *pointers))
    main.extend(confirm)
    main.extend(duplicate)
    main.extend(begin)
    if len(main) > MAIN_SIZE or CAVE_END + len(level) != PACKED_FETCH_ADDRESS:
        raise ValueError("fusion confirmation storage no longer fits its regions")
    main.extend(bytes(MAIN_SIZE - len(main)))

    def stock(address: int, size: int) -> bytes:
        offset = address - LOAD_ADDRESS
        return original[offset : offset + size]

    return (
        Patch(
            "fusion.confirmation",
            "pointer_lookup",
            0x060578A2,
            bytes.fromhex("e128d21b2f26e200e700281ee602e514041ad118341c"),
            bytes.fromhex("d21c2f26e200e700e602e51460834008d1197102041e"),
        ),
        Patch(
            "fusion.confirmation",
            "main_storage",
            LOAD_ADDRESS + MAIN_FILE,
            stock(LOAD_ADDRESS + MAIN_FILE, MAIN_SIZE),
            bytes(main),
        ),
        Patch(
            "fusion.confirmation",
            "level_too_low",
            CAVE_END,
            bytes(len(level)),
            level,
        ),
        Patch(
            "fusion.confirmation",
            "label_yes",
            LOAD_ADDRESS + LABEL_YES_FILE,
            stock(LOAD_ADDRESS + LABEL_YES_FILE, len(label_yes)),
            label_yes,
        ),
        Patch(
            "fusion.confirmation",
            "label_no",
            LOAD_ADDRESS + LABEL_NO_FILE,
            stock(LOAD_ADDRESS + LABEL_NO_FILE, len(label_no)),
            label_no,
        ),
        *_pointer_patches(
            "fusion.confirmation",
            "vwf_drawer",
            (0x06057910,),
            0x060517C4,
            addresses["surface_blitter"],
        ),
    )


def _fusion_patches(
    original: bytes, runtime: bytes, addresses: dict[str, int]
) -> tuple[Patch, ...]:
    sort_offset = NAME_SORT_ADDRESS - LOAD_ADDRESS
    sort_stock = original[sort_offset : sort_offset + NAME_SORT_SIZE]
    if _sha256(sort_stock) != NAME_SORT_STOCK_SHA256:
        raise ValueError("fusion English-sort region does not match stock")
    sorter = bytearray(NAME_SORT_TEMPLATE)
    struct.pack_into(">I", sorter, 196, addresses["demon_offsets"])
    sorter.extend(bytes(NAME_SORT_SIZE - len(sorter)))

    patches: list[Patch] = [
        Patch(
            "fusion.runtime",
            "runtime_cave",
            CAVE_ADDRESS,
            bytes(len(runtime)),
            runtime,
        ),
        Patch(
            "fusion.list",
            "english_name_sort",
            NAME_SORT_ADDRESS,
            sort_stock,
            bytes(sorter),
        ),
        *_pointer_patches(
            "fusion.list", "name_sort_pointer", (0x060457BC,), 0x060452AC, NAME_SORT_ADDRESS
        ),
        *_pointer_patches(
            "fusion.list",
            "actor_name",
            (0x06041488,),
            0x0603C5C8,
            addresses["fusion_character_name"],
        ),
        *_pointer_patches(
            "fusion.list",
            "demon_name",
            (0x06041498,),
            0x0603C50C,
            addresses["fusion_demon_name"],
        ),
        *_pointer_patches(
            "fusion.preview",
            "race",
            (0x060419DC,),
            0x0603C410,
            addresses["fusion_preview_race"],
        ),
        *_pointer_patches(
            "fusion.preview",
            "demon",
            (0x060419E0,),
            0x0603C50C,
            addresses["fusion_preview_demon"],
        ),
        *_pointer_patches(
            "fusion.table",
            "result_demon",
            (0x06045EFC,),
            0x0603C50C,
            addresses["fusion_table_demon"],
        ),
        *_pointer_patches(
            "fusion.table",
            "level_glyph",
            (0x06045DA0,),
            0x0603B760,
            addresses["surface_blitter"],
        ),
        Patch(
            "fusion.table",
            "level_second_digit_advance",
            0x06045D50,
            bytes.fromhex("790c"),
            bytes.fromhex("7906"),
        ),
        Patch(
            "fusion.guide",
            "left_margin",
            0x0603B8DA,
            bytes.fromhex("eb00"),
            bytes.fromhex("eb0a"),
        ),
        *_pointer_patches(
            "fusion.guide",
            "guide_glyph",
            (0x0603B9B0,),
            0x0603B760,
            addresses["fusion_guide_mixed_glyph"],
        ),
        Patch(
            "fusion.guide",
            "guide_advance",
            0x0603B91E,
            bytes.fromhex("7b0f"),
            bytes.fromhex("7b00"),
        ),
        Patch(
            "fusion.guide",
            "guide_terminator_count",
            0x0603B912,
            bytes.fromhex("e815"),
            struct.pack(">H", 0xE800 | GUIDE_GLYPH_LIMIT),
        ),
        Patch(
            "fusion.guide",
            "guide_glyph_limit",
            0x0603B918,
            bytes.fromhex("e014"),
            struct.pack(">H", 0xE000 | (GUIDE_GLYPH_LIMIT - 1)),
        ),
        *_pointer_patches(
            "fusion.guide",
            "help_glyph",
            (0x0603BBD8,),
            0x0603B760,
            addresses["fusion_word_font8_glyph"],
        ),
        Patch(
            "fusion.guide",
            "help_advance",
            0x0603BB06,
            bytes.fromhex("7b0c"),
            bytes.fromhex("3b0c"),
        ),
        Patch(
            "fusion.guide",
            "help_terminator_count",
            0x0603BAFA,
            bytes.fromhex("e815"),
            struct.pack(">H", 0xE800 | HELP_GLYPH_LIMIT),
        ),
        Patch(
            "fusion.guide",
            "help_glyph_limit",
            0x0603BB00,
            bytes.fromhex("ed14"),
            struct.pack(">H", 0xED00 | (HELP_GLYPH_LIMIT - 1)),
        ),
        *_pointer_patches(
            "fusion.chart",
            "word_glyph",
            (0x0603C4C4,),
            0x0603B760,
            addresses["fusion_word_font8_glyph"],
        ),
        Patch(
            "fusion.chart",
            "word_advance",
            0x0603C48E,
            bytes.fromhex("780c"),
            bytes.fromhex("380c"),
        ),
        *_pointer_patches(
            "fusion.chart",
            "race",
            (0x0604442C, 0x0604461C),
            0x0603C410,
            addresses["fusion_chart_race"],
        ),
    ]
    table_race_sites = (
        0x0603D59C,
        0x0603D670,
        0x0603D840,
        0x0603DA2C,
        0x0603E330,
        0x0603E524,
        0x0603E774,
        0x0603F720,
        0x0603FA48,
        0x0603FC5C,
        0x06042B00,
        0x06042BCC,
        0x06042D5C,
        0x06042F34,
        0x06043118,
        0x06043B1C,
        0x06045A94,
        0x060460D8,
        0x06046314,
    )
    table_demon_sites = tuple(site + 4 for site in table_race_sites)
    patches.extend(
        _pointer_patches(
            "fusion.table",
            "race",
            table_race_sites,
            0x0603C4C8,
            addresses["fusion_table_race"],
        )
    )
    patches.extend(
        _pointer_patches(
            "fusion.table",
            "demon",
            table_demon_sites,
            0x0603C50C,
            addresses["fusion_table_demon"],
        )
    )
    patches.extend(
        _confirmation_patches(
            original, addresses, FontMetrics.load(FONT16_METRICS_PATH)
        )
    )
    return tuple(patches)


def build_fusion_menu(original: bytes, event_patched: bytes) -> FusionBuild:
    """Compose every Fusion consumer onto the already-built EVENT runtime."""
    _validate_surfaces()
    runtime, addresses, asset_files = _runtime_payload()
    patches = _fusion_patches(original, runtime, addresses)
    return FusionBuild(
        apply_patches(event_patched, LOAD_ADDRESS, patches),
        runtime,
        addresses,
        patches,
        asset_files,
    )
