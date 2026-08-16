"""Shared text grammar and bitmap primitives for Saturn status-style panels."""

from __future__ import annotations

import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from text.util.assets import load_asset


SIMPLE_TEMPLATE_GRAMMAR = {
    "level": ("level", 3),
    "experience": ("experience", 3),
    "next_experience": ("experience_to_next", 7),
    "summon_cost": ("summon_cost", 3),
    "auto_setting": ("command", 5),
    "control": ("rank", 5),
    "personality_type": ("personality", 4),
    "loyalty": ("loyalty", None),
    "party_alignment": ("alignment", 4),
}

BASE_LABEL_KEYS = (
    "strength",
    "intelligence",
    "magic",
    "vitality",
    "agility",
    "luck",
)
DERIVED_LABEL_KEYS = (
    "sword_attack",
    "sword_accuracy",
    "gun_attack",
    "gun_accuracy",
    "defense",
    "evasion",
    "magic_power",
    "magic_defense",
)
PERSONALITY_KEYS = (
    "personality_sturdy",
    "personality_fierce",
    "personality_impatient",
    "personality_sly",
    "personality_prideful",
    "personality_gentle",
    "personality_cowardly",
    "personality_calm",
    "personality_cautious",
    "personality_impartial",
)

_SIMPLE_TEMPLATE = re.compile(r"^(.+) \{([a-z][a-z0-9_]*)\}$")
_HP_TEMPLATE = re.compile(
    r"^(.+) \{(current_(?:hp|mp))\}(.{1})\{(maximum_(?:hp|mp))\}$"
)


@dataclass(frozen=True, slots=True)
class StatusTemplates:
    prefixes: Mapping[str, str]
    hp_mp_separator: str
    party_prefix: str


@dataclass(frozen=True, slots=True)
class StatusLabels:
    base: tuple[str, ...]
    derived: tuple[str, ...]
    attack: str
    accuracy: str
    personality: tuple[str, ...]


def load_font16_metrics(path: Path) -> tuple[bytes, dict[str, int]]:
    """Load the complete 268-cell FONT16 width and character maps."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid FONT16 metrics: {path}") from error
    table = document.get("width_table", {})
    if (
        document.get("version") != 2
        or not document.get("complete")
        or table.get("code_limit") != 268
    ):
        raise ValueError("incomplete FONT16 metrics for status UI")
    widths = bytearray(268)
    codes: dict[str, int] = {}
    for row in document.get("glyphs", ()):
        code, advance = row.get("code"), row.get("advance")
        if type(code) is not int or not 0 <= code < len(widths):
            raise ValueError("invalid FONT16 status glyph code")
        if type(advance) is not int or not 1 <= advance <= 16:
            raise ValueError("invalid FONT16 status glyph advance")
        widths[code] = advance
        for text in (row.get("text"), *row.get("aliases", ())):
            if isinstance(text, str) and len(text) == 1:
                codes.setdefault(text, code)
    return bytes(widths), codes


def load_stock_latin_codes(path: Path) -> dict[str, int]:
    """Load the preserved Japanese FONT8 Latin reference set."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        rows = document["reference_sets"]["stock_latin"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise ValueError("FONT8 metrics do not publish stock_latin") from error
    result: dict[str, int] = {}
    for row in rows:
        text, code = row.get("text"), row.get("code")
        if not isinstance(text, str) or len(text) != 1 or type(code) is not int:
            raise ValueError("invalid stock_latin FONT8 record")
        result[text] = code
    return result


def compile_status_templates(values: Mapping[str, str]) -> StatusTemplates:
    """Compile every visible literal in the typed status grammars."""
    prefixes: dict[str, str] = {}
    for name, (placeholder, maximum) in SIMPLE_TEMPLATE_GRAMMAR.items():
        try:
            value = values[name]
        except KeyError as error:
            raise ValueError(f"status template is missing {name}") from error
        match = _SIMPLE_TEMPLATE.fullmatch(value)
        if match is None or match.group(2) != placeholder:
            raise ValueError(
                f"status.{name} must use 'PREFIX {{{placeholder}}}' with one "
                "layout space"
            )
        prefix = match.group(1)
        if prefix != prefix.strip():
            raise ValueError(
                f"status.{name} must have exactly one layout boundary space"
            )
        if maximum is not None and not 1 <= len(prefix) <= maximum:
            raise ValueError(f"status.{name} prefix exceeds {maximum} cells")
        prefixes[name] = prefix

    separators: list[str] = []
    for name, current, maximum in (
        ("hit_points", "current_hp", "maximum_hp"),
        ("magic_points", "current_mp", "maximum_mp"),
    ):
        try:
            value = values[name]
        except KeyError as error:
            raise ValueError(f"status template is missing {name}") from error
        match = _HP_TEMPLATE.fullmatch(value)
        prefix = match.group(1) if match is not None else ""
        if (
            match is None
            or match.group(2) != current
            or match.group(4) != maximum
            or prefix != prefix.strip()
            or not 1 <= len(prefix) <= 3
        ):
            raise ValueError(
                f"status.{name} must use 'PREFIX {{{current}}}SEP"
                f"{{{maximum}}}' with a one-cell separator"
            )
        prefixes[name] = prefix
        separators.append(match.group(3))
    if separators[0] != separators[1]:
        raise ValueError("human and demon HP/MP renderers share one separator")

    party_prefix = prefixes["party_alignment"]
    if len(party_prefix) != 4 or party_prefix[1] != party_prefix[3]:
        raise ValueError(
            "status.party_alignment needs four cells with repeated cells 2 and 4"
        )
    return StatusTemplates(
        MappingProxyType(prefixes), separators[0], party_prefix
    )


def load_status_templates() -> StatusTemplates:
    """Resolve the authored status templates and compile their full grammar."""
    status = load_asset("ui/status.json")
    names = set(SIMPLE_TEMPLATE_GRAMMAR) | {"hit_points", "magic_points"}
    values = {
        name: status.field(f"{name}.text").resolve()[1]
        for name in names
    }
    return compile_status_templates(values)


def load_status_labels(templates: StatusTemplates) -> StatusLabels:
    """Resolve labels shared by status-style parameter panels."""
    status = load_asset("ui/status.json")

    def text(name: str) -> str:
        _reference, translation, _reviewed = status.field(f"{name}.text").resolve()
        if not translation:
            raise ValueError(f"ui/status.json#{name}.text is untranslated")
        return translation

    return StatusLabels(
        tuple(text(name) for name in BASE_LABEL_KEYS),
        tuple(text(name) for name in DERIVED_LABEL_KEYS),
        text("attack"),
        text("accuracy"),
        (templates.prefixes["loyalty"],)
        + tuple(text(name) for name in PERSONALITY_KEYS),
    )


def derived_rows(labels: StatusLabels) -> tuple[tuple[str, ...], ...]:
    """Split each derived label into the panel's one-to-four atlas chunks."""
    rows = tuple(tuple(label.split()) for label in labels.derived)
    if any(not row or len(row) > 4 for row in rows):
        raise ValueError("derived status labels must contain one to four chunks")
    return rows


def _glyph_code(character: str, widths: bytes, codes: Mapping[str, int]) -> int:
    try:
        code = codes[character]
    except KeyError as error:
        raise ValueError(f"unsupported status-label character {character!r}") from error
    if not widths[code]:
        raise ValueError(f"status-label glyph {code} has no width")
    return code


def status_atlas_tile(
    text: str,
    font: bytes,
    widths: bytes,
    codes: Mapping[str, int],
) -> bytes:
    """Create one 12x12 4bpp tile using compressed FONT8 letter slots."""
    if len(text) > 3:
        raise ValueError(f"status atlas chunk exceeds three characters: {text!r}")
    pixels = [[0] * 12 for _ in range(12)]
    slot_width = 6 if len(text) <= 2 else 4
    for slot, character in enumerate(text):
        code = _glyph_code(character, widths, codes)
        cell = font[code * 8 : (code + 1) * 8]
        if len(cell) != 8:
            raise ValueError(f"FONT8 glyph {code} exceeds the font")
        ink_columns = [x for row in cell for x in range(8) if row & (0x80 >> x)]
        if not ink_columns:
            continue
        left, right = min(ink_columns), max(ink_columns)
        source_width = right - left + 1
        target_width = min(slot_width - 1, source_width)
        x_origin = slot * slot_width + (slot_width - target_width) // 2
        for y, bits in enumerate(cell):
            for target_x in range(target_width):
                source_x = (
                    left
                    if target_width == 1
                    else left
                    + round(target_x * (source_width - 1) / (target_width - 1))
                )
                if bits & (0x80 >> source_x):
                    pixels[y + 2][x_origin + target_x] = 2
    packed = bytearray()
    for row in pixels:
        for x in range(0, 12, 2):
            packed.append(row[x] << 4 | row[x + 1])
    return bytes(packed)


def status_mask(tile: bytes) -> bytes:
    """Expand one 12x12 atlas tile into the native 16x16 mask record."""
    if len(tile) != 0x48:
        raise ValueError("status atlas tile must be 0x48 bytes")
    rows = [0] * 16
    for y in range(12):
        for x in range(12):
            value = tile[y * 6 + x // 2]
            value = value >> 4 if x % 2 == 0 else value & 0x0F
            if value:
                rows[y + 2] |= 0x8000 >> (x + 2)
    return struct.pack(">16H", *rows)


def _font8_pixels(
    text: str,
    font: bytes,
    widths: bytes,
    codes: Mapping[str, int],
) -> tuple[list[tuple[int, int]], int]:
    pixels: list[tuple[int, int]] = []
    x = 0
    for character in text:
        code = _glyph_code(character, widths, codes)
        cell = font[code * 8 : (code + 1) * 8]
        for y, bits in enumerate(cell):
            for glyph_x in range(8):
                if bits & (0x80 >> glyph_x):
                    pixels.append((x + glyph_x, y))
        x += widths[code]
    return pixels, x


def direct_color_row(
    text: str,
    font: bytes,
    widths: bytes,
    codes: Mapping[str, int],
    width: int = 48,
) -> bytes:
    """Render one shadowed 12px-high direct-color status label row."""
    height = 12
    pixels, advance = _font8_pixels(text, font, widths, codes)
    if advance > width - 2:
        raise ValueError(f"status row exceeds {width - 2}px: {text!r}")
    image = [[0x0000] * width for _ in range(height)]
    x_origin, y_origin = 1, 4
    for x, y in pixels:
        if x_origin + x + 1 < width and y_origin + y + 1 < height:
            image[y_origin + y + 1][x_origin + x + 1] = 0x8000
    for x, y in pixels:
        if x_origin + x < width and y_origin + y < height:
            image[y_origin + y][x_origin + x] = 0xFFFF
    return b"".join(struct.pack(">H", value) for row in image for value in row)


def node_background(cell: bytes, stock_font16: bytes) -> list[int]:
    """Remove the stock Japanese node glyph while preserving its background."""
    size = 16 * 16 * 2
    if len(cell) != size:
        raise ValueError("status-node bitmap must be one 16x16 direct-color cell")
    image = [
        int.from_bytes(cell[position : position + 2], "big")
        for position in range(0, len(cell), 2)
    ]
    glyph = stock_font16[0x143 * 32 : 0x144 * 32]
    if len(glyph) != 32:
        raise ValueError("stock FONT16 is missing the status-node mask glyph")
    ink = set()
    for y in range(16):
        bits = int.from_bytes(glyph[y * 2 : y * 2 + 2], "big")
        for x in range(16):
            if bits & (0x8000 >> x):
                ink.add((x, y))
    mask = {
        (x + dx, y + dy)
        for x, y in ink
        for dx in range(-2, 3)
        for dy in range(-2, 3)
        if 1 < x + dx < 14 and 1 < y + dy < 14
    }
    known = {
        (x, y): image[y * 16 + x]
        for y in range(16)
        for x in range(16)
        if (x, y) not in mask
    }

    def components(value: int) -> tuple[int, int, int]:
        return value >> 10 & 31, value >> 5 & 31, value & 31

    while len(known) < 16 * 16:
        added: dict[tuple[int, int], int] = {}
        for y in range(16):
            for x in range(16):
                if (x, y) in known:
                    continue
                values = [
                    known[position]
                    for position in (
                        (x - 1, y),
                        (x + 1, y),
                        (x, y - 1),
                        (x, y + 1),
                    )
                    if position in known
                ]
                if values:
                    colors = [components(value) for value in values]
                    red, green, blue = (
                        round(sum(color[channel] for color in colors) / len(colors))
                        for channel in range(3)
                    )
                    added[x, y] = 0x8000 | red << 10 | green << 5 | blue
        if not added:
            raise ValueError("could not reconstruct the status-node background")
        known.update(added)
    return [known[x, y] for y in range(16) for x in range(16)]


def direct_color_node(
    text: str,
    font: bytes,
    widths: bytes,
    codes: Mapping[str, int],
    background: list[int],
) -> bytes:
    """Render one compact base-stat label over a reconstructed node."""
    image = background.copy()
    tile = status_atlas_tile(text, font, widths, codes)
    for y in range(12):
        for x in range(12):
            value = tile[y * 6 + x // 2]
            value = value >> 4 if x % 2 == 0 else value & 0x0F
            if value:
                image[(y + 2) * 16 + x + 2] = 0xFFFF
    return b"".join(struct.pack(">H", value) for value in image)


def validate_shiftable_bitmap(
    bitmap: bytes,
    widths: bytes,
    glyph_stride: int,
    row_stride: int,
    context: str,
) -> None:
    """Prove the runtime may shift every used glyph without losing ink."""
    if (
        glyph_stride <= 0
        or row_stride <= 0
        or glyph_stride % row_stride
        or len(bitmap) % glyph_stride
    ):
        raise ValueError(f"{context}: invalid font bitmap layout")
    glyph_count = len(bitmap) // glyph_stride
    for code, width in enumerate(widths):
        if not width:
            continue
        if code >= glyph_count:
            raise ValueError(f"{context}: glyph {code} exceeds the font bitmap")
        record = bitmap[code * glyph_stride : (code + 1) * glyph_stride]
        if any(
            record[offset] & 1
            for offset in range(row_stride - 1, glyph_stride, row_stride)
        ):
            raise ValueError(
                f"{context}: glyph {code} uses the trailing bit required for "
                "exact odd-pixel placement"
            )


__all__ = (
    "SIMPLE_TEMPLATE_GRAMMAR",
    "StatusLabels",
    "StatusTemplates",
    "compile_status_templates",
    "derived_rows",
    "direct_color_node",
    "direct_color_row",
    "load_font16_metrics",
    "load_status_labels",
    "load_status_templates",
    "load_stock_latin_codes",
    "node_background",
    "status_atlas_tile",
    "status_mask",
    "validate_shiftable_bitmap",
)
