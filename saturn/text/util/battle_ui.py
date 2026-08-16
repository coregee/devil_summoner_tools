"""Compile the Saturn battle UI's file-backed text consumers."""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import PurePosixPath

from .assets import (
    BINDING_ROOT,
    load_asset,
    load_binding,
    load_physical_records,
)
from .battle_negotiation import COMBAT_NAMED_WORDS, LITERAL_GLYPHS
from .config import load_config
from .event_codec import EventDictionary, pack_direct_codes
from .event_repack import FontMetrics, NORMALIZE_CHARACTERS
from .tokens import Named, Raw, Text, parse_tokens


BTL_MES_COUNT = 358
BTL_MES_STOCK_BODY = 0x800
BTL_MES_OUTPUT_BODY = 0x400
BTL_MES_SENTINEL_OFFSET = 0x2CC
BTL_SRF_COUNT = 363
BUTU_SRF_COUNT = 144
WORD_BODY_OFFSET = 0x400
BTL_SRF_SENTINEL_OFFSET = 0x2D6
BUTU_SRF_SENTINEL_OFFSET = 0x120
ITEM_COUNT = 287
MAGIC_COUNT = 255
CATALOG_STRIDE = 0x60
CATALOG_NAME_OFFSET = 4
CATALOG_NAME_BYTES = 8
CATALOG_DESCRIPTION_OFFSET = 0x0C
CATALOG_NAME_POINTER_OFFSET = 0x5E
CATALOG_DESCRIPTION_WORDS = (
    CATALOG_NAME_POINTER_OFFSET - CATALOG_DESCRIPTION_OFFSET
) // 2
CATALOG_MAX_NAME_BYTES = 19
CATALOG_MAX_NAME_PIXELS = 80
BTL_HELP_COUNT = 19
BTL_HELP_WORDS = 22
BTL_HELP_WIDTH = 300
BTL_HELP_LINES = 2
BTL_SRF_WIDTH = 176
BTL_SRF_LINES = 2
TERMINATOR_BYTE = 0x80
TERMINATOR_WORD = 0x8000
NEWLINE_WORD = 0x8001
_PUNCTUATION_SPACE_RE = re.compile(r"([.!?])([A-Za-z{])")

WORD_TOKENS = {"n": NEWLINE_WORD, **COMBAT_NAMED_WORDS}
PRESERVED_FONT16_GLYPHS = {**LITERAL_GLYPHS, "♀": 0x00B9}


@dataclass(frozen=True, slots=True)
class PointerBuild:
    data: bytes
    records: int
    translated: int
    body_size: int
    body_capacity: int


@dataclass(frozen=True, slots=True)
class CatalogBuild:
    data: bytes
    records: int
    translated_names: int
    translated_descriptions: int
    longest_name_bytes: int
    longest_name_pixels: int
    longest_description_words: int
    free_name_bytes: int


def _normalize(value: str) -> str:
    for source, replacement in NORMALIZE_CHARACTERS.items():
        value = value.replace(source, replacement)
    value = value.replace("{n}", "\n")
    value = "\n".join(" ".join(line.split()) for line in value.split("\n"))
    return _PUNCTUATION_SPACE_RE.sub(r"\1 \2", value)


def _bound_fields(prefix: str) -> dict[str, str]:
    """Resolve a physical family while permitting deliberately empty rows."""
    physical = load_physical_records()
    catalogs = {}
    values: dict[str, str] = {}
    for path in sorted(BINDING_ROOT.glob("*.json")):
        if prefix not in path.read_text(encoding="utf-8"):
            continue
        binding = load_binding(path, physical_records=physical)
        catalog = catalogs.setdefault(binding.asset, load_asset(binding.asset))
        for physical_id, asset_ref in binding.records.items():
            if not physical_id.startswith(prefix):
                continue
            if physical_id in values:
                raise ValueError(f"physical record has two authored owners: {physical_id}")
            _reference, translation, _reviewed = catalog.field(asset_ref).resolve(
                binding.variants.get(physical_id)
            )
            values[physical_id] = translation
    return values


def _require_visible_coverage(prefix: str, values: dict[str, str]) -> None:
    physical = load_physical_records()
    missing = sorted(
        physical_id
        for physical_id, reference in physical.items()
        if physical_id.startswith(prefix) and reference and physical_id not in values
    )
    if missing:
        raise ValueError(
            f"{prefix} has {len(missing)} visible physical records without an asset"
        )


def _literal_codes(text: str, metrics: FontMetrics) -> list[int]:
    output: list[int] = []
    start = 0
    for position, character in enumerate(text):
        code = PRESERVED_FONT16_GLYPHS.get(character)
        if code is None:
            continue
        if start < position:
            output.extend(glyph.code for glyph in metrics.segment(text[start:position]))
        output.append(code)
        start = position + 1
    if start < len(text):
        output.extend(glyph.code for glyph in metrics.segment(text[start:]))
    return output


def _font16_codes(value: str, metrics: FontMetrics) -> list[int]:
    output: list[int] = []
    for line_index, line in enumerate(_normalize(value).split("\n")):
        if line_index:
            output.append(NEWLINE_WORD)
        for token in parse_tokens(line):
            if isinstance(token, Text):
                output.extend(_literal_codes(token.value, metrics))
            elif isinstance(token, Raw):
                if token.width != 2:
                    raise ValueError("FONT16 text requires 16-bit raw tokens")
                output.append(token.value)
            elif isinstance(token, Named):
                try:
                    output.append(WORD_TOKENS[token.name])
                except KeyError as error:
                    raise ValueError(f"unsupported combat token {{{token.name}}}") from error
    return output


def _font16_width(value: str, metrics: FontMetrics) -> int:
    widths = {glyph.code: glyph.advance for glyph in metrics.glyphs}
    width = 0
    for code in _font16_codes(value, metrics):
        if code < 0x8000:
            width += widths.get(code, 16)
    return width


def _wrap(value: str, metrics: FontMetrics, width: int, lines: int) -> str:
    words = _normalize(value).replace("\n", " ").split()
    wrapped: list[str] = []
    current = ""
    for word in words:
        if _font16_width(word, metrics) == 0:
            current += word
            continue
        candidate = word if not current else f"{current} {word}"
        if current and _font16_width(candidate, metrics) > width:
            wrapped.append(current)
            current = word
        else:
            current = candidate
        if _font16_width(current, metrics) > width:
            raise ValueError(f"word exceeds {width}px: {word!r}")
    if current:
        wrapped.append(current)
    if not wrapped:
        wrapped.append("")
    if len(wrapped) > lines:
        raise ValueError(f"text needs {len(wrapped)}/{lines} lines: {value!r}")
    return "\n".join(wrapped)


def _smallfont_map() -> tuple[dict[str, int], dict[str, int]]:
    encoding = load_config().source("game_battle_smallfont")
    glyphs: dict[str, int] = {}
    for code, text in encoding.glyphs.items():
        glyphs.setdefault(text, code)
    # FNT8X12 is retained wholesale. These are the English readings of its
    # stock full-width punctuation cells, not a second replacement font.
    glyphs.update(
        {
            " ": 0x00,
            "-": 0x40,
            "_": 0x41,
            "&": 0x44,
            "[": 0x45,
            "]": 0x46,
            "'": 0x47,
        }
    )
    controls = {name: code for code, name in encoding.controls.items()}
    return glyphs, controls


def _encode_smallfont(value: str) -> bytes:
    glyphs, controls = _smallfont_map()
    compounds = tuple(sorted(glyphs, key=lambda text: (-len(text), glyphs[text])))
    output = bytearray()
    for token in parse_tokens(value):
        if isinstance(token, Text):
            position = 0
            while position < len(token.value):
                matched = next(
                    (text for text in compounds if token.value.startswith(text, position)),
                    None,
                )
                if matched is None:
                    raise ValueError(
                        f"unsupported battle-console character at {position}: "
                        f"{token.value[position:position + 8]!r}"
                    )
                output.append(glyphs[matched])
                position += len(matched)
        elif isinstance(token, Raw):
            if token.width != 1:
                raise ValueError("battle-console raw tokens must be one byte")
            if token.kind == "GLYPH" and token.value >= TERMINATOR_BYTE:
                raise ValueError("battle-console glyph is in the control range")
            if token.kind == "OP" and token.value < TERMINATOR_BYTE:
                raise ValueError("battle-console operation is in the glyph range")
            output.append(token.value)
        else:
            try:
                output.append(controls[token.name])
            except KeyError as error:
                raise ValueError(
                    f"unsupported battle-console token {{{token.name}}}"
                ) from error
    if TERMINATOR_BYTE in output:
        raise ValueError("battle-console text contains its terminator")
    output.append(TERMINATOR_BYTE)
    return bytes(output)


def _read_byte_records(stock: bytes) -> tuple[list[int], list[bytes], int]:
    pointers: list[int] = []
    cursor = 0
    while cursor + 2 <= BTL_MES_STOCK_BODY:
        pointer = struct.unpack_from(">H", stock, cursor)[0]
        if pointer == 0xFFFF:
            break
        pointers.append(pointer)
        cursor += 2
    if len(pointers) != BTL_MES_COUNT or cursor != BTL_MES_SENTINEL_OFFSET:
        raise ValueError("BTL_MES pointer inventory changed")
    starts = [BTL_MES_STOCK_BODY + pointer for pointer in pointers]
    final = stock.find(bytes((TERMINATOR_BYTE,)), starts[-1])
    if final < 0:
        raise ValueError("BTL_MES final record has no terminator")
    ends = (*starts[1:], final + 1)
    records = [stock[start:end] for start, end in zip(starts, ends)]
    if any(not row or row[-1] != TERMINATOR_BYTE or TERMINATOR_BYTE in row[:-1] for row in records):
        raise ValueError("BTL_MES record framing changed")
    return pointers, records, final + 1


def compile_btl_mes(stock: bytes) -> PointerBuild:
    _pointers, original, original_end = _read_byte_records(stock)
    translations = _bound_fields("game.btl_mes.")
    _require_visible_coverage("game.btl_mes.", translations)
    records: list[bytes] = []
    translated = 0
    for index, raw in enumerate(original):
        physical_id = f"game.btl_mes.p{index:04d}"
        text = translations.get(physical_id)
        if text:
            try:
                raw = _encode_smallfont(text)
            except ValueError as error:
                raise ValueError(f"{physical_id}: {error}") from error
            translated += 1
        records.append(raw)
    body = b"".join(records)
    capacity = original_end - BTL_MES_OUTPUT_BODY
    if len(body) > capacity:
        raise ValueError(f"BTL_MES body uses {len(body)}/{capacity} bytes")
    output = bytearray(stock)
    output[BTL_MES_OUTPUT_BODY:original_end] = bytes(capacity)
    output[BTL_MES_OUTPUT_BODY:BTL_MES_OUTPUT_BODY + len(body)] = body
    position = 0
    for index, record in enumerate(records):
        struct.pack_into(">H", output, index * 2, position)
        position += len(record)
    struct.pack_into(">H", output, BTL_MES_SENTINEL_OFFSET, 0xFFFF)
    return PointerBuild(bytes(output), len(records), translated, len(body), capacity)


def _read_word_records(
    stock: bytes, count: int, sentinel_offset: int
) -> list[tuple[int, ...]]:
    pointers: list[int] = []
    cursor = 0
    while cursor + 2 <= WORD_BODY_OFFSET:
        pointer = struct.unpack_from(">H", stock, cursor)[0]
        if pointer == 0xFFFF:
            break
        pointers.append(pointer)
        cursor += 2
    if len(pointers) != count or cursor != sentinel_offset:
        raise ValueError("indexed-word pointer inventory changed")
    body_words = (len(stock) - WORD_BODY_OFFSET) // 2
    records: list[tuple[int, ...]] = []
    for index, start in enumerate(pointers):
        stop = pointers[index + 1] if index + 1 < count else body_words
        words = struct.unpack_from(f">{stop - start}H", stock, WORD_BODY_OFFSET + start * 2)
        try:
            end = words.index(TERMINATOR_WORD)
        except ValueError as error:
            raise ValueError(f"indexed-word record {index} has no terminator") from error
        if index + 1 < count and end != len(words) - 1:
            raise ValueError(f"indexed-word record {index} has trailing data")
        records.append(tuple(words[: end + 1]))
    return records


def compile_indexed_words(
    stock: bytes,
    *,
    prefix: str,
    count: int,
    sentinel_offset: int,
    metrics: FontMetrics,
    dictionary: EventDictionary,
    wrap_width: int | None,
    wrap_lines: int | None,
) -> PointerBuild:
    original = _read_word_records(stock, count, sentinel_offset)
    translations = _bound_fields(prefix)
    _require_visible_coverage(prefix, translations)
    records: list[tuple[int, ...]] = []
    translated = 0
    for index, raw in enumerate(original):
        physical_id = f"{prefix}p{index:04d}"
        text = translations.get(physical_id)
        if text:
            try:
                if wrap_width is not None and wrap_lines is not None:
                    text = _wrap(text, metrics, wrap_width, wrap_lines)
                words = dictionary.encode_codes(_font16_codes(text, metrics))
            except ValueError as error:
                raise ValueError(f"{physical_id}: {error}") from error
            if TERMINATOR_WORD in words:
                raise ValueError(f"{physical_id}: text contains its terminator")
            raw = tuple((*words, TERMINATOR_WORD))
            translated += 1
        records.append(raw)
    body_words = sum(map(len, records))
    capacity = (len(stock) - WORD_BODY_OFFSET) // 2
    if body_words > capacity:
        raise ValueError(f"{prefix} body uses {body_words}/{capacity} words")
    output = bytearray(stock)
    output[WORD_BODY_OFFSET:] = bytes(capacity * 2)
    position = 0
    for index, words in enumerate(records):
        struct.pack_into(">H", output, index * 2, position)
        struct.pack_into(
            f">{len(words)}H", output, WORD_BODY_OFFSET + position * 2, *words
        )
        position += len(words)
    struct.pack_into(">H", output, sentinel_offset, 0xFFFF)
    return PointerBuild(bytes(output), count, translated, body_words * 2, capacity * 2)


def compile_fixed_help(
    stock: bytes,
    *,
    prefix: str,
    count: int,
    record_words: int,
    metrics: FontMetrics,
    width: int,
    max_lines: int,
) -> PointerBuild:
    stride = record_words * 2
    if len(stock) != count * stride:
        raise ValueError(f"{prefix} fixed-help inventory changed")
    translations = _bound_fields(prefix)
    required = {f"{prefix}o{index * stride:06x}.text" for index in range(count)}
    if set(translations) != required:
        raise ValueError(f"{prefix} binding coverage changed")
    output = bytearray(len(stock))
    longest = 0
    for record in range(count):
        physical_id = f"{prefix}o{record * stride:06x}.text"
        original = struct.unpack_from(f">{record_words}H", stock, record * stride)
        end = original.index(TERMINATOR_WORD)
        leading = next((index for index, word in enumerate(original[:end]) if word), end)
        post_newline = 0
        if NEWLINE_WORD in original[:end]:
            cursor = original.index(NEWLINE_WORD) + 1
            while cursor + post_newline < end and original[cursor + post_newline] == 0:
                post_newline += 1
        text_lines = _normalize(translations[physical_id]).split("\n")
        if not 1 <= len(text_lines) <= max_lines or any(
            not line for line in text_lines
        ):
            raise ValueError(f"{physical_id}: help needs one or two nonempty lines")
        if any(_font16_width(line, metrics) > width for line in text_lines):
            raise ValueError(f"{physical_id}: help line exceeds {width}px")
        words = [0] * leading
        for line_index, line in enumerate(text_lines):
            if line_index:
                words.append(NEWLINE_WORD)
                words.extend([0] * post_newline)
            words.extend(pack_direct_codes(_font16_codes(line, metrics)))
        words.append(TERMINATOR_WORD)
        if len(words) > record_words:
            raise ValueError(f"{physical_id}: uses {len(words)}/{record_words} words")
        struct.pack_into(f">{len(words)}H", output, record * stride, *words)
        longest = max(longest, len(words))
    return PointerBuild(bytes(output), count, count, longest * 2, record_words * 2)


def compile_btl_help(stock: bytes, metrics: FontMetrics) -> PointerBuild:
    return compile_fixed_help(
        stock,
        prefix="game.btl_help.",
        count=BTL_HELP_COUNT,
        record_words=BTL_HELP_WORDS,
        metrics=metrics,
        width=BTL_HELP_WIDTH,
        max_lines=BTL_HELP_LINES,
    )


def _allocate(ranges: list[list[int]], payload: bytes, context: str) -> int:
    for span in ranges:
        if span[1] - span[0] >= len(payload):
            start = span[0]
            span[0] += len(payload)
            return start
    raise ValueError(f"{context}: description padding cannot fit the full name")


def compile_catalog(
    stock: bytes,
    *,
    source: str,
    count: int,
    font8: FontMetrics,
    font16: FontMetrics,
) -> CatalogBuild:
    if len(stock) != count * CATALOG_STRIDE:
        raise ValueError(f"{source.upper()} inventory changed")
    prefix = f"game.{source}."
    translations = _bound_fields(prefix)
    required = {
        f"{prefix}o{record * CATALOG_STRIDE + offset:06x}.{field}"
        for record in range(count)
        for offset, field in (
            (CATALOG_NAME_OFFSET, "name"),
            (CATALOG_DESCRIPTION_OFFSET, "description"),
        )
    }
    if set(translations) != required:
        raise ValueError(f"{source.upper()} binding coverage changed")
    output = bytearray(stock)
    translated_descriptions = 0
    longest_description = 0
    for record in range(count):
        physical_id = f"{prefix}o{record * CATALOG_STRIDE + CATALOG_DESCRIPTION_OFFSET:06x}.description"
        text = translations[physical_id]
        if not text:
            continue
        words = [*pack_direct_codes(_font16_codes(text, font16)), TERMINATOR_WORD]
        if len(words) > CATALOG_DESCRIPTION_WORDS:
            raise ValueError(
                f"{physical_id}: uses {len(words)}/{CATALOG_DESCRIPTION_WORDS} words"
            )
        base = record * CATALOG_STRIDE + CATALOG_DESCRIPTION_OFFSET
        output[base:base + CATALOG_DESCRIPTION_WORDS * 2] = bytes(
            CATALOG_DESCRIPTION_WORDS * 2
        )
        struct.pack_into(f">{len(words)}H", output, base, *words)
        translated_descriptions += 1
        longest_description = max(longest_description, len(words))
    ranges: list[list[int]] = []
    for record in range(count):
        base = record * CATALOG_STRIDE
        words = struct.unpack_from(
            f">{CATALOG_DESCRIPTION_WORDS}H",
            output,
            base + CATALOG_DESCRIPTION_OFFSET,
        )
        try:
            end = words.index(TERMINATOR_WORD)
        except ValueError as error:
            raise ValueError(f"{source} record {record} has no description terminator") from error
        start = base + CATALOG_DESCRIPTION_OFFSET + (end + 1) * 2
        stop = base + CATALOG_NAME_POINTER_OFFSET
        if any(output[start:stop]):
            raise ValueError(f"{source} record {record} has nonzero description padding")
        if start < stop:
            ranges.append([start, stop])
    translated_names = 0
    longest_name_bytes = 0
    longest_name_pixels = 0
    for record in range(count):
        base = record * CATALOG_STRIDE
        physical_id = f"{prefix}o{base + CATALOG_NAME_OFFSET:06x}.name"
        text = translations[physical_id]
        if text:
            normalized = _normalize(text)
            if "\n" in normalized or any(
                not isinstance(token, Text) for token in parse_tokens(normalized)
            ):
                raise ValueError(f"{physical_id}: name must be literal single-line text")
            glyphs = font8.segment(normalized)
            encoded = bytes(glyph.code for glyph in glyphs)
            pixels = sum(glyph.advance for glyph in glyphs)
            if len(encoded) > CATALOG_MAX_NAME_BYTES or pixels > CATALOG_MAX_NAME_PIXELS:
                raise ValueError(
                    f"{physical_id}: name exceeds {CATALOG_MAX_NAME_BYTES} bytes/"
                    f"{CATALOG_MAX_NAME_PIXELS}px ({len(encoded)} bytes, {pixels}px)"
                )
            translated_names += 1
        else:
            encoded = stock[
                base + CATALOG_NAME_OFFSET:
                base + CATALOG_NAME_OFFSET + CATALOG_NAME_BYTES
            ].rstrip(b"\x00")
            pixels = 0
        if 0xFF in encoded:
            raise ValueError(f"{physical_id}: name contains its terminator")
        pointer = _allocate(ranges, encoded + b"\xff", physical_id)
        output[pointer:pointer + len(encoded) + 1] = encoded + b"\xff"
        output[
            base + CATALOG_NAME_OFFSET:
            base + CATALOG_NAME_OFFSET + CATALOG_NAME_BYTES
        ] = encoded[:CATALOG_NAME_BYTES].ljust(CATALOG_NAME_BYTES, b"\x00")
        struct.pack_into(">H", output, base + CATALOG_NAME_POINTER_OFFSET, pointer)
        longest_name_bytes = max(longest_name_bytes, len(encoded))
        longest_name_pixels = max(longest_name_pixels, pixels)
    return CatalogBuild(
        bytes(output),
        count,
        translated_names,
        translated_descriptions,
        longest_name_bytes,
        longest_name_pixels,
        longest_description,
        sum(stop - start for start, stop in ranges),
    )
