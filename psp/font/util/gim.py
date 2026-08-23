"""Font-specific GIM cell edits built on the shared PSP format codec."""

from __future__ import annotations

from PIL import Image

from psp.formats.gim import (
    CHUNK_HEADER_SIZE,
    IMAGE_CHUNK,
    INDEX4,
    INDEX8,
    LINEAR,
    PALETTE_CHUNK,
    PICTURE_CHUNK,
    PSP_SWIZZLED,
    RGBA4444,
    RGBA5551,
    RGBA8888,
    RGB565,
    ROOT_CHUNK,
    ROOT_OFFSET,
    SIGNATURE,
    Gim,
    GimChunk,
    GimEncodeReport,
    GimEncodeResult,
    GimRaster,
    _decode_palette,
    _linear_payload,
    _stored_payload,
    discover,
    pixel_sha256,
)

Chunk = GimChunk
Raster = GimRaster


def indexed_rasters(data: bytes) -> tuple[GimRaster, GimRaster]:
    """Return the sole image and palette rasters from an indexed GIM."""

    gim = Gim.parse(data)
    if gim.image.format not in {INDEX4, INDEX8} or gim.palette is None:
        raise ValueError("indexed GIM must contain exactly one image and palette")
    return gim.image, gim.palette


def replace_index8_cells(
    data: bytes,
    replacements: dict[int, bytes],
    *,
    transparent_index: int,
    ink_index: int,
) -> bytes:
    """Replace selected 16x16 cells without rebuilding the GIM container."""

    if not isinstance(data, bytes):
        raise TypeError("GIM source must be bytes")
    if not isinstance(replacements, dict):
        raise TypeError("GIM cell replacements must be a dictionary")
    gim = Gim.parse(data)
    image, palette = indexed_rasters(data)
    if (
        image.format != INDEX8
        or image.bits_per_pixel != 8
        or image.width % 16
        or image.height % 16
    ):
        raise ValueError("GIM image is not a 16x16-cell INDEX8 raster")
    palette_size = palette.width * palette.height
    if (
        not 0 <= transparent_index < palette_size
        or not 0 <= ink_index < palette_size
    ):
        raise ValueError("GIM replacement palette index is outside the palette")
    columns = image.width // 16
    maximum_cell = columns * (image.height // 16)
    for cell, coverage in replacements.items():
        if type(cell) is not int or not 0 <= cell < maximum_cell:
            raise ValueError(f"GIM replacement cell is invalid: {cell!r}")
        if not isinstance(coverage, bytes) or len(coverage) != 16 * 16:
            raise ValueError(f"GIM replacement cell {cell:#x} is not a 16x16 mask")
        if set(coverage) - {0, 255}:
            raise ValueError(f"GIM replacement cell {cell:#x} is antialiased")

    linear = bytearray(_linear_payload(image))
    for cell, coverage in replacements.items():
        cell_row, cell_column = divmod(cell, columns)
        for y in range(16):
            target = (
                (cell_row * 16 + y) * image.stored_row_bytes + cell_column * 16
            )
            source = y * 16
            linear[target : target + 16] = bytes(
                ink_index if value else transparent_index
                for value in coverage[source : source + 16]
            )
    return gim._replace_payloads(_stored_payload(image, bytes(linear)), None)


def replace_index8_coverage_cells(
    data: bytes,
    replacements: dict[int, bytes],
    *,
    maximum_source_index: int,
) -> bytes:
    """Apply antialiased cell coverage through the GIM's native gray ramp."""

    gim = Gim.parse(data)
    image, palette = indexed_rasters(data)
    if image.format != INDEX8 or image.bits_per_pixel != 8:
        raise ValueError("GIM image is not INDEX8")
    colors = _decode_palette(palette)
    if not 1 <= maximum_source_index < len(colors):
        raise ValueError("GIM grayscale ramp is outside the palette")
    ramp = []
    for index in range(1, maximum_source_index + 1):
        red, green, blue, alpha = colors[index]
        if alpha == 0:
            continue
        if alpha != 255 or max(red, green, blue) - min(red, green, blue) > 4:
            raise ValueError("GIM coverage requires an opaque grayscale ramp")
        ramp.append((index, round((red + green + blue) / 3)))
    darkest = min(value for _index, value in ramp)
    brightest = max(value for _index, value in ramp)
    linear = bytearray(_linear_payload(image))
    columns = image.width // 16
    maximum_cell = columns * (image.height // 16)
    for cell, coverage in replacements.items():
        if type(cell) is not int or not 0 <= cell < maximum_cell:
            raise ValueError(f"GIM replacement cell is invalid: {cell!r}")
        if not isinstance(coverage, bytes) or len(coverage) != 256:
            raise ValueError(f"GIM replacement cell {cell:#x} is not a 16x16 mask")
        cell_row, cell_column = divmod(cell, columns)
        for y in range(16):
            target = (
                (cell_row * 16 + y) * image.stored_row_bytes + cell_column * 16
            )
            for x, value in enumerate(coverage[y * 16 : y * 16 + 16]):
                if value == 0:
                    continue
                luminance = darkest + value * (brightest - darkest) / 255
                index, _actual = min(
                    ramp,
                    key=lambda item: (abs(item[1] - luminance), -item[1]),
                )
                linear[target + x] = index
    return gim._replace_payloads(_stored_payload(image, bytes(linear)), None)


def decode(data: bytes) -> Image.Image:
    """Decode one complete GIM to an RGBA image."""

    return Gim.parse(data).decode()


__all__ = (
    "CHUNK_HEADER_SIZE",
    "Chunk",
    "IMAGE_CHUNK",
    "INDEX4",
    "INDEX8",
    "LINEAR",
    "PALETTE_CHUNK",
    "PICTURE_CHUNK",
    "PSP_SWIZZLED",
    "RGBA4444",
    "RGBA5551",
    "RGBA8888",
    "RGB565",
    "ROOT_CHUNK",
    "ROOT_OFFSET",
    "Raster",
    "SIGNATURE",
    "Gim",
    "GimEncodeReport",
    "GimEncodeResult",
    "decode",
    "discover",
    "indexed_rasters",
    "pixel_sha256",
    "replace_index8_cells",
    "replace_index8_coverage_cells",
)
