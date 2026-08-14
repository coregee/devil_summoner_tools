"""Decode, render, and encode the packed Saturn font formats."""

from __future__ import annotations

import io
import json
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from .definitions import FontDefinition, FontFormat, RenderOptions


@dataclass(frozen=True)
class RepackedFont:
    data: bytes
    atlas: Image.Image
    metrics: str | None


def glyph_count(data: bytes | bytearray, definition: FontDefinition) -> int:
    remainder = len(data) % definition.format.glyph_stride
    if remainder:
        raise ValueError(
            f"{definition.file} has {remainder} bytes after its last complete glyph"
        )
    return len(data) // definition.format.glyph_stride


def _pixel_position(x: int, bpp: int) -> tuple[int, int, int]:
    pixels_per_byte = 8 // bpp
    byte_index = x // pixels_per_byte
    pixel_index = x % pixels_per_byte
    shift = (pixels_per_byte - 1 - pixel_index) * bpp
    return byte_index, shift, (1 << bpp) - 1


def _decode_pixel(row: bytes | bytearray, x: int, bpp: int) -> int:
    byte_index, shift, mask = _pixel_position(x, bpp)
    return ((row[byte_index] >> shift) & mask) * 255 // mask


def _encode_pixel(row: bytearray, x: int, bpp: int, brightness: int) -> None:
    byte_index, shift, mask = _pixel_position(x, bpp)
    value = (brightness * mask + 127) // 255
    shifted_mask = mask << shift
    row[byte_index] = (row[byte_index] & (0xFF ^ shifted_mask)) | (
        (value & mask) << shift
    )


def decode_glyph(
    data: bytes | bytearray,
    font_format: FontFormat,
    glyph_index: int,
) -> Image.Image:
    glyph = Image.new("L", (font_format.width, font_format.height))
    pixels = glyph.load()
    glyph_offset = glyph_index * font_format.glyph_stride
    for y in range(font_format.height):
        row_offset = glyph_offset + y * font_format.row_stride
        row = data[row_offset : row_offset + font_format.row_stride]
        for x in range(font_format.width):
            pixels[x, y] = _decode_pixel(row, x, font_format.bpp)
    return glyph


def encode_glyph(
    data: bytearray,
    font_format: FontFormat,
    glyph_index: int,
    glyph: Image.Image,
) -> None:
    if glyph.size != (font_format.width, font_format.height):
        raise ValueError(
            f"glyph {glyph_index} is {glyph.width}x{glyph.height}; expected "
            f"{font_format.width}x{font_format.height}"
        )
    pixels = glyph.convert("L").load()
    glyph_offset = glyph_index * font_format.glyph_stride
    for y in range(font_format.height):
        row_offset = glyph_offset + y * font_format.row_stride
        row = bytearray(data[row_offset : row_offset + font_format.row_stride])
        for x in range(font_format.width):
            _encode_pixel(row, x, font_format.bpp, pixels[x, y])
        data[row_offset : row_offset + font_format.row_stride] = row


def render_atlas(data: bytes | bytearray, definition: FontDefinition) -> Image.Image:
    count = glyph_count(data, definition)
    columns = definition.atlas.columns
    scale = definition.atlas.scale
    rows = (count + columns - 1) // columns
    font_format = definition.format
    sheet = Image.new("L", (columns * font_format.width, rows * font_format.height))
    for glyph_index in range(count):
        glyph = decode_glyph(data, font_format, glyph_index)
        sheet.paste(
            glyph,
            (
                (glyph_index % columns) * font_format.width,
                (glyph_index // columns) * font_format.height,
            ),
        )
    if scale != 1:
        sheet = sheet.resize(
            (sheet.width * scale, sheet.height * scale), Image.Resampling.NEAREST
        )

    index_font = ImageFont.load_default()
    measurement = ImageDraw.Draw(Image.new("L", (1, 1)))
    column_labels = [str(column) for column in range(columns)]
    row_labels = [str(row * columns) for row in range(rows)]
    labels = column_labels + row_labels
    bounds = {
        label: measurement.textbbox((0, 0), label, font=index_font) for label in labels
    }
    label_height = max(bottom - top for _, top, _, bottom in bounds.values())
    row_label_width = max(bounds[label][2] - bounds[label][0] for label in row_labels)
    left_margin = row_label_width + 8
    top_margin = label_height + 8
    indexed = Image.new("L", (left_margin + sheet.width, top_margin + sheet.height))
    indexed.paste(sheet, (left_margin, top_margin))
    draw = ImageDraw.Draw(indexed)
    cell_width = font_format.width * scale
    cell_height = font_format.height * scale

    for column, label in enumerate(column_labels):
        left, top, right, bottom = bounds[label]
        width = right - left
        height = bottom - top
        center_x = left_margin + column * cell_width + cell_width / 2
        center_y = top_margin / 2
        draw.text(
            (center_x - width / 2 - left, center_y - height / 2 - top),
            label,
            font=index_font,
            fill=255,
        )
    for row, label in enumerate(row_labels):
        left, top, right, bottom = bounds[label]
        width = right - left
        height = bottom - top
        center_y = top_margin + row * cell_height + cell_height / 2
        draw.text(
            (left_margin - width - 4 - left, center_y - height / 2 - top),
            label,
            font=index_font,
            fill=255,
        )
    draw.line((left_margin - 2, 0, left_margin - 2, indexed.height), fill=64)
    draw.line((0, top_margin - 2, indexed.width, top_margin - 2), fill=64)
    return indexed


def png_bytes(image: Image.Image) -> bytes:
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def _render_character(
    character: str,
    definition: FontDefinition,
    font: ImageFont.FreeTypeFont,
    options: RenderOptions,
) -> Image.Image:
    font_format = definition.format
    glyph = Image.new("L", (font_format.width, font_format.height), 0)
    draw = ImageDraw.Draw(glyph)
    draw.fontmode = "L" if options.antialias else "1"
    if options.placement == "center":
        position = (
            font_format.width / 2 + options.offset_x,
            font_format.height / 2 + options.offset_y,
        )
    elif options.placement == "origin":
        position = (options.offset_x, options.offset_y)
    else:
        raise ValueError(f"unknown typeface placement: {options.placement}")
    for adjustment in options.glyph_offsets:
        if character in adjustment.characters:
            position = (
                position[0] + adjustment.offset_x,
                position[1] + adjustment.offset_y,
            )
            break

    characters = character if options.compose_from_glyphs else (character,)
    x, y = position
    for source_glyph in characters:
        draw.text(
            (x, y),
            source_glyph,
            font=font,
            fill=255,
            anchor=options.anchor,
            stroke_width=options.stroke_width,
            stroke_fill=255,
        )
        if options.compose_from_glyphs:
            x += round(font.getlength(source_glyph))
    return glyph


def _ink_advance(
    data: bytes | bytearray, definition: FontDefinition, glyph_index: int
) -> int:
    glyph = decode_glyph(data, definition.format, glyph_index)
    pixels = glyph.load()
    occupied = [
        x
        for y in range(definition.format.height)
        for x in range(definition.format.width)
        if pixels[x, y]
    ]
    if not occupied:
        return max(1, definition.format.width // 2)
    return min(definition.format.width, max(occupied) + 2)


def _metrics_json(definition: FontDefinition, advances: dict[int, int]) -> str | None:
    metrics = definition.metrics
    if metrics is None:
        return None
    glyphs = []
    missing = []
    for glyph_index, replacement in sorted(definition.replacements.items()):
        if glyph_index >= metrics.code_limit:
            continue
        advance = advances.get(glyph_index)
        if advance is None:
            missing.append(glyph_index)
            continue
        row: dict[str, object] = {
            "text": replacement,
            "code": glyph_index,
            "advance": advance,
        }
        original = definition.glyphs.get(glyph_index)
        if original is not None and original != replacement:
            row["aliases"] = [original]
        glyphs.append(row)

    width_table: dict[str, object] = {"code_limit": metrics.code_limit}
    if definition.advance_table is not None:
        width_table = {
            "storage_glyph": definition.advance_table.storage_glyph,
            "code_limit": metrics.code_limit,
        }
    if metrics.measurement != "source":
        width_table["measurement"] = metrics.measurement
    document = {
        "version": 2,
        "font": definition.file,
        "complete": not missing,
        "width_table": width_table,
        "glyphs": glyphs,
        "missing_codes": missing,
    }
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def repack_font(source_data: bytes, definition: FontDefinition) -> RepackedFont:
    count = glyph_count(source_data, definition)
    output = bytearray(source_data)
    advances: dict[int, int] = {}

    if definition.source_font is not None:
        if definition.render is None:
            raise ValueError(f"{definition.file} has no source-font render settings")
        font = ImageFont.truetype(
            str(definition.source_font),
            definition.render.size,
            index=definition.render.face_index,
        )
        for glyph_index, character in sorted(definition.replacements.items()):
            if glyph_index >= count:
                raise ValueError(
                    f"{definition.file} replacement glyph {glyph_index} is out of range"
                )
            glyph = _render_character(character, definition, font, definition.render)
            encode_glyph(output, definition.format, glyph_index, glyph)
            if definition.metrics is not None:
                if definition.metrics.measurement == "ink":
                    advances[glyph_index] = _ink_advance(
                        output, definition, glyph_index
                    )
                else:
                    advances[glyph_index] = sum(
                        round(font.getlength(item)) for item in character
                    )

        metrics = definition.metrics
        if metrics is not None and metrics.space_advance is not None:
            for glyph_index, character in definition.replacements.items():
                if character == " ":
                    advances[glyph_index] = metrics.space_advance

        table = definition.advance_table
        if table is not None:
            values = bytearray(table.code_limit)
            for glyph_index in definition.replacements:
                if glyph_index >= table.code_limit:
                    continue
                advance = advances.get(glyph_index)
                if advance is None:
                    raise ValueError(
                        f"{definition.file} glyph {glyph_index} has no advance"
                    )
                if not 0 <= advance <= 0xFF:
                    raise ValueError(
                        f"{definition.file} glyph {glyph_index} advance does not fit"
                    )
                values[glyph_index] = advance
            start = table.storage_glyph * definition.format.glyph_stride
            end = start + len(values)
            if end > len(output):
                raise ValueError(f"{definition.file} advance table is out of range")
            output[start:end] = values

    return RepackedFont(
        data=bytes(output),
        atlas=render_atlas(output, definition),
        metrics=_metrics_json(definition, advances),
    )
