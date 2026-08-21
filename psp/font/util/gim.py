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
