"""Decode PSP raw-tile resources and indexed GIM pages into logical glyphs."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .definitions import FontDefinition
from .gim import decode as decode_gim


def _raw_pixel(row: bytes, x: int, bpp: int) -> int:
    pixels_per_byte = 8 // bpp
    index = x % pixels_per_byte
    value = row[x // pixels_per_byte]
    mask = (1 << bpp) - 1
    shift = (pixels_per_byte - 1 - index) * bpp
    return ((value >> shift) & mask) * 255 // mask


def verify_sources(definition: FontDefinition) -> None:
    import hashlib

    for target_index, path in zip(
        definition.logical_target_indices, definition.source_paths, strict=True
    ):
        if not path.is_file():
            raise ValueError(f"PSP font source is missing: {path}")
        target = definition.targets[target_index]
        data = path.read_bytes()
        if len(data) != target.size:
            raise ValueError(f"{path} is {len(data)} bytes; expected {target.size}")
        digest = hashlib.sha256(data).hexdigest()
        if digest != target.sha256:
            raise ValueError(f"{path} SHA-256 is {digest}; expected {target.sha256}")


def load_cell_data(definition: FontDefinition) -> bytes:
    """Return logical cells in source order.

    Raw resources retain their packed bytes. GIM resources are normalized to
    one alpha byte per pixel so the catalogue can compare pages with different
    indexed-palette and swizzle layouts without pretending their containers are
    interchangeable.
    """

    verify_sources(definition)
    if definition.storage_kind == "raw_tiles":
        data = b"".join(path.read_bytes() for path in definition.source_paths)
        expected = definition.glyph_count * definition.format.glyph_stride
        if len(data) != expected:
            raise ValueError(
                f"{definition.resource_id} raw data is {len(data)} bytes; expected {expected}"
            )
        return data

    cells = bytearray()
    page_cells = 0
    for path in definition.source_paths:
        image = decode_gim(path.read_bytes())
        if image.width % definition.format.width or image.height % definition.format.height:
            raise ValueError(f"{path} dimensions do not fit the configured cell grid")
        columns = image.width // definition.format.width
        rows = image.height // definition.format.height
        alpha = image.getchannel("A")
        # Most indexed font pages use transparent background and therefore
        # carry their coverage in alpha. The direct-color embedded FONT8 GIM
        # is opaque black/white, so its luminance is the meaningful mask.
        coverage = alpha if alpha.getextrema()[0] == 0 else image.convert("L")
        for row in range(rows):
            for column in range(columns):
                left = column * definition.format.width
                top = row * definition.format.height
                cell = coverage.crop(
                    (
                        left,
                        top,
                        left + definition.format.width,
                        top + definition.format.height,
                    )
                )
                cells.extend(cell.tobytes())
                page_cells += 1
    if page_cells != definition.glyph_count:
        raise ValueError(
            f"{definition.resource_id} decodes {page_cells} cells; expected {definition.glyph_count}"
        )
    return bytes(cells)


def decode_glyph(
    data: bytes | bytearray, definition: FontDefinition, glyph_index: int
) -> Image.Image:
    if not 0 <= glyph_index < definition.glyph_count:
        raise ValueError("glyph index is outside the PSP font")
    width, height = definition.format.width, definition.format.height
    if definition.storage_kind == "gim_pages":
        stride = width * height
        start = glyph_index * stride
        return Image.frombytes("L", (width, height), bytes(data[start : start + stride]))
    glyph = Image.new("L", (width, height))
    pixels = glyph.load()
    start = glyph_index * definition.format.glyph_stride
    for y in range(height):
        row_start = start + y * definition.format.row_stride
        row = bytes(data[row_start : row_start + definition.format.row_stride])
        for x in range(width):
            pixels[x, y] = _raw_pixel(row, x, definition.format.bpp)
    return glyph


def render_atlas(data: bytes | bytearray, definition: FontDefinition) -> Image.Image:
    columns = definition.atlas.columns
    rows = (definition.glyph_count + columns - 1) // columns
    width, height = definition.format.width, definition.format.height
    scale = definition.atlas.scale
    sheet = Image.new("L", (columns * width, rows * height))
    for code in range(definition.glyph_count):
        sheet.paste(decode_glyph(data, definition, code), ((code % columns) * width, (code // columns) * height))
    if scale != 1:
        sheet = sheet.resize((sheet.width * scale, sheet.height * scale), Image.Resampling.NEAREST)

    index_font = ImageFont.load_default()
    measure = ImageDraw.Draw(Image.new("L", (1, 1)))
    column_labels = [str(value) for value in range(columns)]
    row_labels = [str(value * columns) for value in range(rows)]
    bounds = {value: measure.textbbox((0, 0), value, font=index_font) for value in column_labels + row_labels}
    label_height = max(bottom - top for _left, top, _right, bottom in bounds.values())
    row_width = max(bounds[value][2] - bounds[value][0] for value in row_labels)
    left_margin, top_margin = row_width + 8, label_height + 8
    output = Image.new("L", (left_margin + sheet.width, top_margin + sheet.height))
    output.paste(sheet, (left_margin, top_margin))
    draw = ImageDraw.Draw(output)
    cell_width, cell_height = width * scale, height * scale
    for column, label in enumerate(column_labels):
        box = bounds[label]
        text_width, text_height = box[2] - box[0], box[3] - box[1]
        draw.text((left_margin + column * cell_width + (cell_width - text_width) / 2, (top_margin - text_height) / 2), label, font=index_font, fill=255)
    for row, label in enumerate(row_labels):
        box = bounds[label]
        text_width, text_height = box[2] - box[0], box[3] - box[1]
        draw.text((left_margin - text_width - 4, top_margin + row * cell_height + (cell_height - text_height) / 2), label, font=index_font, fill=255)
    draw.line((left_margin - 2, 0, left_margin - 2, output.height), fill=64)
    draw.line((0, top_margin - 2, output.width, top_margin - 2), fill=64)
    return output


def png_bytes(image: Image.Image) -> bytes:
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()
