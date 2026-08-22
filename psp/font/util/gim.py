"""Strict decoder for the indexed GIM font pages on the original PSP disc."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from PIL import Image

SIGNATURE = b"MIG.00.1PSP\x00\x00\x00\x00\x00"
ROOT_CHUNK = 2
PICTURE_CHUNK = 3
IMAGE_CHUNK = 4
PALETTE_CHUNK = 5
RGBA5551 = 1
RGBA8888 = 3
INDEX4 = 4
INDEX8 = 5
LINEAR = 0
PSP_SWIZZLED = 1


def _align(value: int, boundary: int) -> int:
    return (value + boundary - 1) & -boundary


@dataclass(frozen=True, slots=True)
class Chunk:
    kind: int
    offset: int
    size: int
    next_offset: int
    child_offset: int

    @property
    def end(self) -> int:
        return self.offset + self.size


@dataclass(frozen=True, slots=True)
class Raster:
    format: int
    order: int
    width: int
    height: int
    bits_per_pixel: int
    pitch_alignment: int
    height_alignment: int
    payload: bytes

    @property
    def row_bytes(self) -> int:
        return _align((self.width * self.bits_per_pixel + 7) // 8, self.pitch_alignment)

    @property
    def stored_height(self) -> int:
        return _align(self.height, self.height_alignment)


def _chunk(data: bytes, offset: int, limit: int, context: str) -> Chunk:
    if offset < 0 or offset + 0x10 > limit:
        raise ValueError(f"GIM {context} header exceeds its parent")
    kind, _flags, size, next_offset, child_offset = struct.unpack_from(
        "<HHIII", data, offset
    )
    if size < 0x10 or offset + size > limit:
        raise ValueError(f"GIM {context} has invalid bounds")
    return Chunk(kind, offset, size, next_offset, child_offset)


def _raster(data: bytes, chunk: Chunk, context: str) -> Raster:
    metadata = chunk.offset + 0x10
    if metadata + 0x24 > chunk.end:
        raise ValueError(f"GIM {context} metadata is truncated")
    (
        header_size,
        _unknown,
        format_code,
        order,
        width,
        height,
        bits_per_pixel,
        pitch_alignment,
        height_alignment,
        _level_type,
    ) = struct.unpack_from("<10H", data, metadata)
    if header_size != 0x30 or order not in {LINEAR, PSP_SWIZZLED}:
        raise ValueError(f"GIM {context} uses an unsupported layout")
    payload_start = struct.unpack_from("<I", data, chunk.offset + 0x2C)[0]
    payload_end = struct.unpack_from("<I", data, chunk.offset + 0x30)[0]
    if payload_start < header_size or payload_start > payload_end:
        raise ValueError(f"GIM {context} has invalid payload bounds")
    payload = data[metadata + payload_start : metadata + payload_end]
    result = Raster(
        format_code,
        order,
        width,
        height,
        bits_per_pixel,
        pitch_alignment,
        height_alignment,
        payload,
    )
    if len(payload) != result.row_bytes * result.stored_height:
        raise ValueError(f"GIM {context} payload does not match its geometry")
    return result


def _linear(raster: Raster) -> bytes:
    if raster.order == LINEAR:
        return raster.payload
    if raster.row_bytes % 16 or raster.stored_height % 8:
        raise ValueError("swizzled GIM is not aligned to 16x8-byte blocks")
    output = bytearray(len(raster.payload))
    source = 0
    for block_y in range(0, raster.stored_height, 8):
        for block_x in range(0, raster.row_bytes, 16):
            for row in range(8):
                target = (block_y + row) * raster.row_bytes + block_x
                output[target : target + 16] = raster.payload[source : source + 16]
                source += 16
    return bytes(output)


def _stored(linear: bytes, raster: Raster) -> bytes:
    """Return linear raster bytes in their original GIM storage order."""

    if len(linear) != raster.row_bytes * raster.stored_height:
        raise ValueError("linear GIM payload does not match its geometry")
    if raster.order == LINEAR:
        return linear
    if raster.row_bytes % 16 or raster.stored_height % 8:
        raise ValueError("swizzled GIM is not aligned to 16x8-byte blocks")
    output = bytearray(len(linear))
    target = 0
    for block_y in range(0, raster.stored_height, 8):
        for block_x in range(0, raster.row_bytes, 16):
            for row in range(8):
                source = (block_y + row) * raster.row_bytes + block_x
                output[target : target + 16] = linear[source : source + 16]
                target += 16
    return bytes(output)


def _picture_children(data: bytes) -> tuple[tuple[Chunk, Raster], ...]:
    if data[: len(SIGNATURE)] != SIGNATURE:
        raise ValueError("GIM signature is missing")
    root = _chunk(data, 0x10, len(data), "root")
    if root.kind != ROOT_CHUNK:
        raise ValueError("GIM root chunk is missing")
    picture = _chunk(data, root.offset + root.child_offset, root.end, "picture")
    if picture.kind != PICTURE_CHUNK:
        raise ValueError("GIM picture chunk is missing")
    children = []
    offset = picture.offset + picture.child_offset
    while offset < picture.end:
        child = _chunk(data, offset, picture.end, "picture child")
        if child.kind in {IMAGE_CHUNK, PALETTE_CHUNK}:
            label = "image" if child.kind == IMAGE_CHUNK else "palette"
            children.append((child, _raster(data, child, label)))
        offset += child.next_offset or child.size
    return tuple(children)


def indexed_rasters(data: bytes) -> tuple[Raster, Raster]:
    """Return the sole image and palette rasters from an indexed GIM."""

    children = _picture_children(data)
    images = [raster for chunk, raster in children if chunk.kind == IMAGE_CHUNK]
    palettes = [raster for chunk, raster in children if chunk.kind == PALETTE_CHUNK]
    if len(images) != 1 or len(palettes) != 1:
        raise ValueError("indexed GIM must contain exactly one image and palette")
    return images[0], palettes[0]


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
    children = _picture_children(data)
    images = [
        (chunk, raster) for chunk, raster in children if chunk.kind == IMAGE_CHUNK
    ]
    palettes = [raster for chunk, raster in children if chunk.kind == PALETTE_CHUNK]
    if len(images) != 1 or len(palettes) != 1:
        raise ValueError("indexed GIM must contain exactly one image and palette")
    chunk, image = images[0]
    palette = palettes[0]
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
    rows = image.height // 16
    maximum_cell = columns * rows
    for cell, coverage in replacements.items():
        if type(cell) is not int or not 0 <= cell < maximum_cell:
            raise ValueError(f"GIM replacement cell is invalid: {cell!r}")
        if not isinstance(coverage, bytes) or len(coverage) != 16 * 16:
            raise ValueError(f"GIM replacement cell {cell:#x} is not a 16x16 mask")
        if set(coverage) - {0, 255}:
            raise ValueError(f"GIM replacement cell {cell:#x} is antialiased")

    linear = bytearray(_linear(image))
    for cell, coverage in replacements.items():
        cell_row, cell_column = divmod(cell, columns)
        for y in range(16):
            target = (cell_row * 16 + y) * image.row_bytes + cell_column * 16
            source = y * 16
            linear[target : target + 16] = bytes(
                ink_index if value else transparent_index
                for value in coverage[source : source + 16]
            )
    stored = _stored(bytes(linear), image)
    metadata = chunk.offset + 0x10
    payload_start = struct.unpack_from("<I", data, chunk.offset + 0x2C)[0]
    start = metadata + payload_start
    end = start + len(image.payload)
    if data[start:end] != image.payload or len(stored) != len(image.payload):
        raise ValueError("GIM image payload location changed")
    return data[:start] + stored + data[end:]


def replace_index8_coverage_cells(
    data: bytes,
    replacements: dict[int, bytes],
    *,
    maximum_source_index: int,
) -> bytes:
    """Apply antialiased cell coverage through the GIM's native gray ramp."""

    children = _picture_children(data)
    images = [
        (chunk, raster) for chunk, raster in children if chunk.kind == IMAGE_CHUNK
    ]
    palettes = [raster for chunk, raster in children if chunk.kind == PALETTE_CHUNK]
    if len(images) != 1 or len(palettes) != 1:
        raise ValueError("indexed GIM must contain exactly one image and palette")
    chunk, image = images[0]
    palette = palettes[0]
    if image.format != INDEX8 or image.bits_per_pixel != 8:
        raise ValueError("GIM image is not INDEX8")
    colors = _palette(palette)
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
    linear = bytearray(_linear(image))
    columns = image.width // 16
    maximum_cell = columns * (image.height // 16)
    for cell, coverage in replacements.items():
        if type(cell) is not int or not 0 <= cell < maximum_cell:
            raise ValueError(f"GIM replacement cell is invalid: {cell!r}")
        if not isinstance(coverage, bytes) or len(coverage) != 256:
            raise ValueError(f"GIM replacement cell {cell:#x} is not a 16x16 mask")
        cell_row, cell_column = divmod(cell, columns)
        for y in range(16):
            target = (cell_row * 16 + y) * image.row_bytes + cell_column * 16
            for x, value in enumerate(coverage[y * 16 : y * 16 + 16]):
                if value == 0:
                    continue
                luminance = darkest + value * (brightest - darkest) / 255
                index, _actual = min(
                    ramp,
                    key=lambda item: (abs(item[1] - luminance), -item[1]),
                )
                linear[target + x] = index
    stored = _stored(bytes(linear), image)
    metadata = chunk.offset + 0x10
    payload_start = struct.unpack_from("<I", data, chunk.offset + 0x2C)[0]
    start = metadata + payload_start
    end = start + len(image.payload)
    if data[start:end] != image.payload:
        raise ValueError("GIM image payload location changed")
    return data[:start] + stored + data[end:]


def _palette(raster: Raster) -> tuple[bytes, ...]:
    linear = _linear(raster)
    colors: list[bytes] = []
    for y in range(raster.height):
        start = y * raster.row_bytes
        if raster.format == RGBA8888 and raster.bits_per_pixel == 32:
            row = linear[start : start + raster.width * 4]
            colors.extend(row[index : index + 4] for index in range(0, len(row), 4))
        elif raster.format == RGBA5551 and raster.bits_per_pixel == 16:
            row = linear[start : start + raster.width * 2]
            for index in range(0, len(row), 2):
                value = int.from_bytes(row[index : index + 2], "little")
                red, green, blue = value & 31, (value >> 5) & 31, (value >> 10) & 31
                colors.append(
                    bytes(
                        (
                            (red << 3) | (red >> 2),
                            (green << 3) | (green >> 2),
                            (blue << 3) | (blue >> 2),
                            255 if value & 0x8000 else 0,
                        )
                    )
                )
        else:
            raise ValueError("unsupported GIM palette format")
    return tuple(colors)


def decode(data: bytes) -> Image.Image:
    """Decode one complete GIM to an RGBA image."""

    if data[: len(SIGNATURE)] != SIGNATURE:
        raise ValueError("GIM signature is missing")
    root = _chunk(data, 0x10, len(data), "root")
    if root.kind != ROOT_CHUNK:
        raise ValueError("GIM root chunk is missing")
    picture = _chunk(data, root.offset + root.child_offset, root.end, "picture")
    if picture.kind != PICTURE_CHUNK:
        raise ValueError("GIM picture chunk is missing")
    image = None
    palette = None
    offset = picture.offset + picture.child_offset
    while offset < picture.end:
        child = _chunk(data, offset, picture.end, "picture child")
        if child.kind == IMAGE_CHUNK:
            image = _raster(data, child, "image")
        elif child.kind == PALETTE_CHUNK:
            palette = _raster(data, child, "palette")
        offset += child.next_offset or child.size
    if image is None:
        raise ValueError("GIM image chunk is missing")
    if image.format == RGBA8888 and image.bits_per_pixel == 32:
        linear = _linear(image)
        pixels = bytearray(image.width * image.height * 4)
        row_size = image.width * 4
        for y in range(image.height):
            source = y * image.row_bytes
            target = y * row_size
            pixels[target : target + row_size] = linear[source : source + row_size]
        return Image.frombytes("RGBA", (image.width, image.height), bytes(pixels))
    if palette is None or image.format not in {INDEX4, INDEX8}:
        raise ValueError("GIM is not a supported indexed image")
    colors = _palette(palette)
    linear = _linear(image)
    output = bytearray(image.width * image.height * 4)
    target = 0
    for y in range(image.height):
        row = linear[y * image.row_bytes : (y + 1) * image.row_bytes]
        if image.format == INDEX8:
            indices = row[: image.width]
        else:
            unpacked = bytearray()
            for value in row[: (image.width + 1) // 2]:
                unpacked.extend((value & 15, value >> 4))
            indices = unpacked[: image.width]
        for index in indices:
            output[target : target + 4] = colors[index]
            target += 4
    return Image.frombytes("RGBA", (image.width, image.height), bytes(output))
