"""Strict decoder for the GIM variants present on the supported PSP disc."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field
from typing import Literal

from PIL import Image

SIGNATURE = b"MIG.00.1PSP\x00\x00\x00\x00\x00"
CHUNK_HEADER_SIZE = 0x10
ROOT_OFFSET = 0x10

ROOT_CHUNK = 2
PICTURE_CHUNK = 3
IMAGE_CHUNK = 4
PALETTE_CHUNK = 5

RGB565 = 0
RGBA5551 = 1
RGBA4444 = 2
RGBA8888 = 3
INDEX4 = 4
INDEX8 = 5
LINEAR = 0
PSP_SWIZZLED = 1


def _align(value: int, boundary: int) -> int:
    if boundary <= 0 or boundary & (boundary - 1):
        raise ValueError("GIM alignment must be a positive power of two")
    return (value + boundary - 1) & -boundary


@dataclass(frozen=True)
class GimChunk:
    kind: int
    flags: int
    offset: int
    size: int
    next_offset: int
    child_offset: int

    @property
    def end(self) -> int:
        return self.offset + self.size


@dataclass(frozen=True)
class GimRaster:
    chunk: GimChunk
    format: int
    order: int
    width: int
    height: int
    bits_per_pixel: int
    pitch_alignment: int
    height_alignment: int
    payload_offset: int
    payload: bytes

    @property
    def stored_row_bytes(self) -> int:
        packed = (self.width * self.bits_per_pixel + 7) // 8
        return _align(packed, self.pitch_alignment)

    @property
    def stored_height(self) -> int:
        return _align(self.height, self.height_alignment)


@dataclass(frozen=True)
class Gim:
    size: int
    root: GimChunk
    picture: GimChunk
    image: GimRaster
    palette: GimRaster | None
    source_offset: int = field(repr=False)
    source: bytes = field(repr=False)

    @classmethod
    def parse(cls, data: bytes, offset: int = 0) -> "Gim":
        """Parse one GIM beginning at *offset* within a larger byte buffer."""

        if offset < 0 or offset + len(SIGNATURE) > len(data):
            raise ValueError("GIM signature offset is outside the input")
        if data[offset : offset + len(SIGNATURE)] != SIGNATURE:
            raise ValueError("GIM signature is missing")

        root = _parse_chunk(data, offset + ROOT_OFFSET, len(data), "root")
        if root.kind != ROOT_CHUNK:
            raise ValueError(f"GIM root has type {root.kind}; expected {ROOT_CHUNK}")
        gim_end = root.end
        if root.child_offset < CHUNK_HEADER_SIZE:
            raise ValueError("GIM root has an invalid child offset")
        picture_offset = root.offset + root.child_offset
        picture = _parse_chunk(data, picture_offset, gim_end, "picture")
        if picture.kind != PICTURE_CHUNK:
            raise ValueError(
                f"GIM first root child has type {picture.kind}; "
                f"expected {PICTURE_CHUNK}"
            )
        if picture.child_offset < CHUNK_HEADER_SIZE:
            raise ValueError("GIM picture has an invalid child offset")

        image = None
        palette = None
        child_offset = picture.offset + picture.child_offset
        while child_offset < picture.end:
            child = _parse_chunk(data, child_offset, picture.end, "picture child")
            if child.kind == IMAGE_CHUNK:
                if image is not None:
                    raise ValueError("GIM picture has more than one image")
                image = _parse_raster(data, child, "image")
            elif child.kind == PALETTE_CHUNK:
                if palette is not None:
                    raise ValueError("GIM picture has more than one palette")
                palette = _parse_raster(data, child, "palette")
            else:
                raise ValueError(f"GIM picture has unsupported child type {child.kind}")
            step = child.next_offset or child.size
            if step < CHUNK_HEADER_SIZE or step % 0x10:
                raise ValueError("GIM child has an invalid next offset")
            child_offset += step
        if child_offset != picture.end:
            raise ValueError("GIM picture children do not fill the picture chunk")
        if image is None:
            raise ValueError("GIM picture has no image")
        if image.format in {INDEX4, INDEX8} and palette is None:
            raise ValueError("indexed GIM image has no palette")
        if image.format == RGBA8888 and palette is not None:
            raise ValueError("direct-color GIM unexpectedly has a palette")

        return cls(
            size=gim_end - offset,
            root=root,
            picture=picture,
            image=image,
            palette=palette,
            source_offset=offset,
            source=data[offset:gim_end],
        )

    def decode(self) -> Image.Image:
        """Decode the first picture to a cropped RGBA Pillow image."""

        raster = self.image
        linear = _linear_payload(raster)
        if raster.format == RGBA8888:
            if raster.bits_per_pixel != 32:
                raise ValueError("RGBA8888 GIM image does not use 32 bits per pixel")
            pixels = bytearray(raster.width * raster.height * 4)
            row_size = raster.width * 4
            for y in range(raster.height):
                source = y * raster.stored_row_bytes
                target = y * row_size
                pixels[target : target + row_size] = linear[source : source + row_size]
            return Image.frombytes("RGBA", (raster.width, raster.height), bytes(pixels))

        if raster.format not in {INDEX4, INDEX8}:
            raise ValueError(f"unsupported GIM image format {raster.format}")
        if raster.format == INDEX4 and raster.bits_per_pixel != 4:
            raise ValueError("INDEX4 GIM image does not use 4 bits per pixel")
        if raster.format == INDEX8 and raster.bits_per_pixel != 8:
            raise ValueError("INDEX8 GIM image does not use 8 bits per pixel")
        assert self.palette is not None
        palette = _decode_palette(self.palette)
        index_count = 16 if raster.format == INDEX4 else 256
        if len(palette) < index_count:
            raise ValueError(
                f"GIM palette has {len(palette)} colors; expected {index_count}"
            )

        pixels = bytearray(raster.width * raster.height * 4)
        target = 0
        for y in range(raster.height):
            row = linear[
                y * raster.stored_row_bytes : (y + 1) * raster.stored_row_bytes
            ]
            if raster.format == INDEX8:
                indices = row[: raster.width]
            else:
                unpacked = bytearray()
                for value in row[: (raster.width + 1) // 2]:
                    unpacked.extend((value & 0x0F, value >> 4))
                indices = unpacked[: raster.width]
            for index in indices:
                pixels[target : target + 4] = palette[index]
                target += 4
        return Image.frombytes("RGBA", (raster.width, raster.height), bytes(pixels))

    def encode(
        self,
        image: Image.Image,
        *,
        palette_mode: Literal["strict", "rebuild"] = "strict",
    ) -> bytes:
        """Encode *image* into this GIM without changing its byte layout.

        ``strict`` only permits colors already present in an indexed GIM's
        palette. ``rebuild`` explicitly permits deterministic, non-dithered
        quantization into the existing fixed-size palette. Direct-color images
        do not use ``palette_mode``.
        """

        return self.encode_with_report(image, palette_mode=palette_mode).data

    def encode_with_report(
        self,
        image: Image.Image,
        *,
        palette_mode: Literal["strict", "rebuild"] = "strict",
    ) -> "GimEncodeResult":
        """Encode *image* and report whether its palette was rebuilt lossily."""

        if palette_mode not in {"strict", "rebuild"}:
            raise ValueError(f"unsupported GIM palette mode {palette_mode!r}")
        raster = self.image
        if image.size != (raster.width, raster.height):
            raise ValueError(
                f"replacement image is {image.width}x{image.height}; "
                f"expected {raster.width}x{raster.height}"
            )
        source_alpha_applied = not _has_explicit_alpha(image)
        normalized = image.convert("RGBA")
        if source_alpha_applied:
            normalized.putalpha(self.decode().getchannel("A"))
        input_pixels = normalized.tobytes()
        input_color_count = len(_rgba_colors(input_pixels))
        input_pixel_sha256 = pixel_sha256(normalized)

        if raster.format == RGBA8888:
            if raster.bits_per_pixel != 32:
                raise ValueError("RGBA8888 GIM image does not use 32 bits per pixel")
            linear = bytearray(_linear_payload(raster))
            row_size = raster.width * 4
            for y in range(raster.height):
                source = y * row_size
                target = y * raster.stored_row_bytes
                linear[target : target + row_size] = input_pixels[
                    source : source + row_size
                ]
            data = self._replace_payloads(_stored_payload(raster, bytes(linear)), None)
            return GimEncodeResult(
                data=data,
                report=GimEncodeReport(
                    palette_rebuilt=False,
                    quantized=False,
                    input_color_count=input_color_count,
                    encoded_color_count=input_color_count,
                    lossy_pixel_count=0,
                    source_alpha_applied=source_alpha_applied,
                    input_pixel_sha256=input_pixel_sha256,
                    encoded_pixel_sha256=input_pixel_sha256,
                ),
            )

        if raster.format not in {INDEX4, INDEX8}:
            raise ValueError(f"unsupported GIM image format {raster.format}")
        if raster.format == INDEX4 and raster.bits_per_pixel != 4:
            raise ValueError("INDEX4 GIM image does not use 4 bits per pixel")
        if raster.format == INDEX8 and raster.bits_per_pixel != 8:
            raise ValueError("INDEX8 GIM image does not use 8 bits per pixel")
        assert self.palette is not None
        palette = _decode_palette(self.palette)
        capacity = 16 if raster.format == INDEX4 else 256
        if len(palette) < capacity:
            raise ValueError(
                f"GIM palette has {len(palette)} colors; expected {capacity}"
            )

        strict_payload = _encode_indexed_strict(raster, palette, input_pixels)
        if strict_payload is not None:
            data = self._replace_payloads(strict_payload, None)
            return GimEncodeResult(
                data=data,
                report=GimEncodeReport(
                    palette_rebuilt=False,
                    quantized=False,
                    input_color_count=input_color_count,
                    encoded_color_count=input_color_count,
                    lossy_pixel_count=0,
                    source_alpha_applied=source_alpha_applied,
                    input_pixel_sha256=input_pixel_sha256,
                    encoded_pixel_sha256=input_pixel_sha256,
                ),
            )
        if palette_mode == "strict":
            raise ValueError(
                "replacement image contains a color absent from the existing "
                f"{capacity}-color GIM palette; use palette_mode='rebuild' "
                "to request explicit deterministic quantization"
            )

        indices, rebuilt, encoded_pixels = _rebuild_indexed(
            input_pixels, capacity, self.palette
        )
        image_payload = _encode_indices(raster, indices)
        palette_payload = _encode_palette(self.palette, rebuilt)
        data = self._replace_payloads(image_payload, palette_payload)
        lossy_pixel_count = sum(
            input_pixels[index : index + 4] != encoded_pixels[index : index + 4]
            for index in range(0, len(input_pixels), 4)
        )
        encoded_image = Image.frombytes(
            "RGBA", (raster.width, raster.height), encoded_pixels
        )
        return GimEncodeResult(
            data=data,
            report=GimEncodeReport(
                palette_rebuilt=True,
                quantized=bool(lossy_pixel_count),
                input_color_count=input_color_count,
                encoded_color_count=len(_rgba_colors(encoded_pixels)),
                lossy_pixel_count=lossy_pixel_count,
                source_alpha_applied=source_alpha_applied,
                input_pixel_sha256=input_pixel_sha256,
                encoded_pixel_sha256=pixel_sha256(encoded_image),
            ),
        )

    def _replace_payloads(
        self, image_payload: bytes, palette_payload: bytes | None
    ) -> bytes:
        if len(image_payload) != len(self.image.payload):
            raise AssertionError("GIM encoder changed the image payload size")
        output = bytearray(self.source)
        image_start = self.image.payload_offset - self.source_offset
        output[image_start : image_start + len(image_payload)] = image_payload
        if palette_payload is not None:
            assert self.palette is not None
            if len(palette_payload) != len(self.palette.payload):
                raise AssertionError("GIM encoder changed the palette payload size")
            palette_start = self.palette.payload_offset - self.source_offset
            output[palette_start : palette_start + len(palette_payload)] = (
                palette_payload
            )
        if len(output) != self.size:
            raise AssertionError("GIM encoder changed the container size")
        return bytes(output)


@dataclass(frozen=True)
class GimEncodeReport:
    palette_rebuilt: bool
    quantized: bool
    input_color_count: int
    encoded_color_count: int
    lossy_pixel_count: int
    source_alpha_applied: bool
    input_pixel_sha256: str
    encoded_pixel_sha256: str


@dataclass(frozen=True)
class GimEncodeResult:
    data: bytes
    report: GimEncodeReport


def _parse_chunk(data: bytes, offset: int, limit: int, context: str) -> GimChunk:
    if offset < 0 or offset + CHUNK_HEADER_SIZE > limit:
        raise ValueError(f"GIM {context} header exceeds its parent")
    kind, flags, size, next_offset, child_offset = struct.unpack_from(
        "<HHIII", data, offset
    )
    # Root chunks may end with an unaligned file-info/string block. Picture,
    # image, and palette chunks on this disc remain aligned, but alignment is
    # not part of the generic chunk-size contract.
    if size < CHUNK_HEADER_SIZE:
        raise ValueError(f"GIM {context} has an invalid size {size:#x}")
    if offset + size > limit:
        raise ValueError(f"GIM {context} exceeds its parent")
    return GimChunk(kind, flags, offset, size, next_offset, child_offset)


def _parse_raster(data: bytes, chunk: GimChunk, context: str) -> GimRaster:
    metadata = chunk.offset + CHUNK_HEADER_SIZE
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
    if header_size != 0x30:
        raise ValueError(
            f"GIM {context} metadata header is {header_size:#x}; expected 0x30"
        )
    if not width or not height:
        raise ValueError(f"GIM {context} has zero dimensions")
    if order not in {LINEAR, PSP_SWIZZLED}:
        raise ValueError(f"GIM {context} has unsupported order {order}")
    payload_start = struct.unpack_from("<I", data, chunk.offset + 0x2C)[0]
    payload_end = struct.unpack_from("<I", data, chunk.offset + 0x30)[0]
    if (
        payload_start < header_size
        or payload_start > payload_end
        or metadata + payload_end > chunk.end
    ):
        raise ValueError(f"GIM {context} has invalid payload bounds")
    payload = data[metadata + payload_start : metadata + payload_end]
    raster = GimRaster(
        chunk=chunk,
        format=format_code,
        order=order,
        width=width,
        height=height,
        bits_per_pixel=bits_per_pixel,
        pitch_alignment=pitch_alignment,
        height_alignment=height_alignment,
        payload_offset=metadata + payload_start,
        payload=payload,
    )
    expected = raster.stored_row_bytes * raster.stored_height
    if len(payload) != expected:
        raise ValueError(
            f"GIM {context} payload is {len(payload):#x} bytes; expected {expected:#x}"
        )
    return raster


def _linear_payload(raster: GimRaster) -> bytes:
    if raster.order == LINEAR:
        return raster.payload
    row_bytes = raster.stored_row_bytes
    height = raster.stored_height
    if row_bytes % 16 or height % 8:
        raise ValueError("swizzled GIM storage is not aligned to 16x8-byte blocks")
    output = bytearray(len(raster.payload))
    source = 0
    for block_y in range(0, height, 8):
        for block_x in range(0, row_bytes, 16):
            for row in range(8):
                target = (block_y + row) * row_bytes + block_x
                output[target : target + 16] = raster.payload[source : source + 16]
                source += 16
    if source != len(raster.payload):
        raise AssertionError("GIM unswizzle did not consume the complete payload")
    return bytes(output)


def _stored_payload(raster: GimRaster, linear: bytes) -> bytes:
    expected = raster.stored_row_bytes * raster.stored_height
    if len(linear) != expected:
        raise ValueError(
            f"linear GIM payload is {len(linear):#x} bytes; expected {expected:#x}"
        )
    if raster.order == LINEAR:
        return linear
    row_bytes = raster.stored_row_bytes
    height = raster.stored_height
    if row_bytes % 16 or height % 8:
        raise ValueError("swizzled GIM storage is not aligned to 16x8-byte blocks")
    output = bytearray(len(linear))
    target = 0
    for block_y in range(0, height, 8):
        for block_x in range(0, row_bytes, 16):
            for row in range(8):
                source = (block_y + row) * row_bytes + block_x
                output[target : target + 16] = linear[source : source + 16]
                target += 16
    if target != len(linear):
        raise AssertionError("GIM swizzle did not emit the complete payload")
    return bytes(output)


def _rgba_colors(pixels: bytes) -> set[bytes]:
    if len(pixels) % 4:
        raise ValueError("RGBA pixel buffer is not a multiple of four bytes")
    return {pixels[index : index + 4] for index in range(0, len(pixels), 4)}


def _has_explicit_alpha(image: Image.Image) -> bool:
    return "A" in image.getbands() or (
        image.mode == "P" and "transparency" in image.info
    )


def _image_indices(raster: GimRaster, linear: bytes) -> list[int]:
    indices: list[int] = []
    for y in range(raster.height):
        row = linear[y * raster.stored_row_bytes : (y + 1) * raster.stored_row_bytes]
        if raster.format == INDEX8:
            indices.extend(row[: raster.width])
        else:
            unpacked: list[int] = []
            for value in row[: (raster.width + 1) // 2]:
                unpacked.extend((value & 0x0F, value >> 4))
            indices.extend(unpacked[: raster.width])
    return indices


def _encode_indices(raster: GimRaster, indices: list[int]) -> bytes:
    expected = raster.width * raster.height
    if len(indices) != expected:
        raise ValueError(f"GIM index count is {len(indices)}; expected {expected}")
    linear = bytearray(_linear_payload(raster))
    source = 0
    for y in range(raster.height):
        row_start = y * raster.stored_row_bytes
        if raster.format == INDEX8:
            row = bytes(indices[source : source + raster.width])
            linear[row_start : row_start + raster.width] = row
            source += raster.width
            continue
        for x in range(raster.width):
            index = indices[source]
            if not 0 <= index < 16:
                raise ValueError(f"INDEX4 palette index {index} is outside 0..15")
            byte_offset = row_start + x // 2
            if x & 1:
                linear[byte_offset] = (linear[byte_offset] & 0x0F) | (index << 4)
            else:
                linear[byte_offset] = (linear[byte_offset] & 0xF0) | index
            source += 1
    return _stored_payload(raster, bytes(linear))


def _encode_indexed_strict(
    raster: GimRaster, palette: tuple[bytes, ...], input_pixels: bytes
) -> bytes | None:
    linear = _linear_payload(raster)
    original_indices = _image_indices(raster, linear)
    lookup: dict[bytes, int] = {}
    capacity = 16 if raster.format == INDEX4 else 256
    for index, color in enumerate(palette[:capacity]):
        lookup.setdefault(color, index)
    encoded: list[int] = []
    for pixel_number, original_index in enumerate(original_indices):
        start = pixel_number * 4
        color = input_pixels[start : start + 4]
        if palette[original_index] == color:
            encoded.append(original_index)
            continue
        replacement = lookup.get(color)
        if replacement is None:
            return None
        encoded.append(replacement)
    return _encode_indices(raster, encoded)


def _representable_palette_color(color: bytes, palette: GimRaster) -> bytes:
    if palette.format == RGBA8888 and palette.bits_per_pixel == 32:
        return color
    if palette.format != RGBA5551 or palette.bits_per_pixel != 16:
        raise ValueError(
            f"unsupported GIM palette format {palette.format}/"
            f"{palette.bits_per_pixel}bpp"
        )
    red, green, blue, alpha = color

    def component(value: int) -> int:
        five_bit = (value * 31 + 127) // 255
        return (five_bit << 3) | (five_bit >> 2)

    return bytes(
        (component(red), component(green), component(blue), 0 if alpha == 0 else 255)
    )


def _rebuild_indexed(
    input_pixels: bytes, capacity: int, palette: GimRaster
) -> tuple[list[int], tuple[bytes, ...], bytes]:
    pixels = [
        input_pixels[index : index + 4] for index in range(0, len(input_pixels), 4)
    ]
    representable = [_representable_palette_color(color, palette) for color in pixels]
    has_transparency = any(color[3] == 0 for color in representable)
    rebuilt: list[bytes] = [bytes(4)] if has_transparency else []
    available = capacity - len(rebuilt)
    opaque_positions = [
        index for index, color in enumerate(representable) if color[3] != 0
    ]
    opaque = [representable[index] for index in opaque_positions]
    opaque_indices: list[int]

    unique: list[bytes] = []
    unique_lookup: dict[bytes, int] = {}
    for color in opaque:
        if color not in unique_lookup:
            unique_lookup[color] = len(unique)
            unique.append(color)
    if len(unique) <= available:
        opaque_indices = [unique_lookup[color] for color in opaque]
        opaque_palette = unique
    else:
        fully_opaque = all(color[3] == 255 for color in opaque)
        if fully_opaque:
            rgb_pixels = b"".join(color[:3] for color in opaque)
            quantize_source = Image.frombytes("RGB", (len(opaque), 1), rgb_pixels)
            quantized = quantize_source.quantize(
                colors=available,
                method=Image.Quantize.MEDIANCUT,
                dither=Image.Dither.NONE,
            )
            palette_mode = "RGB"
        else:
            quantize_source = Image.frombytes(
                "RGBA", (len(opaque), 1), b"".join(opaque)
            )
            quantized = quantize_source.quantize(
                colors=available,
                method=Image.Quantize.FASTOCTREE,
                dither=Image.Dither.NONE,
            )
            palette_mode = "RGBA"
        raw_indices = list(quantized.tobytes())
        raw_palette = quantized.getpalette(palette_mode)
        if raw_palette is None:
            raise AssertionError("Pillow quantizer did not return a palette")
        used = sorted(set(raw_indices))
        remap = {old: new for new, old in enumerate(used)}
        opaque_indices = [remap[index] for index in raw_indices]
        opaque_palette = []
        for index in used:
            stride = 3 if fully_opaque else 4
            color = bytes(raw_palette[index * stride : index * stride + stride])
            if fully_opaque:
                color += b"\xff"
            if color[3] == 0:
                color = color[:3] + b"\x01"
            opaque_palette.append(_representable_palette_color(color, palette))

    base = len(rebuilt)
    rebuilt.extend(opaque_palette)
    if len(rebuilt) > capacity:
        raise AssertionError("GIM quantizer exceeded the fixed palette capacity")
    indices = [0] * len(pixels)
    for position, index in zip(opaque_positions, opaque_indices, strict=True):
        indices[position] = base + index
    encoded_pixels = b"".join(rebuilt[index] for index in indices)
    return indices, tuple(rebuilt), encoded_pixels


def _encode_palette(raster: GimRaster, colors: tuple[bytes, ...]) -> bytes:
    capacity = raster.width * raster.height
    if len(colors) > capacity:
        raise ValueError(
            f"replacement palette has {len(colors)} colors; capacity is {capacity}"
        )
    linear = bytearray(_linear_payload(raster))
    for index, color in enumerate(colors):
        y, x = divmod(index, raster.width)
        if raster.format == RGBA8888 and raster.bits_per_pixel == 32:
            offset = y * raster.stored_row_bytes + x * 4
            linear[offset : offset + 4] = color
            continue
        if raster.format == RGBA5551 and raster.bits_per_pixel == 16:
            red, green, blue, alpha = color
            red5, green5, blue5 = red >> 3, green >> 3, blue >> 3
            if (
                bytes(
                    (
                        (red5 << 3) | (red5 >> 2),
                        (green5 << 3) | (green5 >> 2),
                        (blue5 << 3) | (blue5 >> 2),
                        255 if alpha else 0,
                    )
                )
                != color
            ):
                raise ValueError("color cannot be represented by an RGBA5551 palette")
            value = red5 | (green5 << 5) | (blue5 << 10)
            if alpha:
                value |= 0x8000
            offset = y * raster.stored_row_bytes + x * 2
            struct.pack_into("<H", linear, offset, value)
            continue
        raise ValueError(
            f"unsupported GIM palette format {raster.format}/{raster.bits_per_pixel}bpp"
        )
    return _stored_payload(raster, bytes(linear))


def _decode_palette(raster: GimRaster) -> tuple[bytes, ...]:
    linear = _linear_payload(raster)
    colors: list[bytes] = []
    for y in range(raster.height):
        row_start = y * raster.stored_row_bytes
        if raster.format == RGBA8888 and raster.bits_per_pixel == 32:
            row = linear[row_start : row_start + raster.width * 4]
            colors.extend(row[index : index + 4] for index in range(0, len(row), 4))
        elif raster.format == RGBA5551 and raster.bits_per_pixel == 16:
            row = linear[row_start : row_start + raster.width * 2]
            for index in range(0, len(row), 2):
                value = int.from_bytes(row[index : index + 2], "little")
                red = value & 0x1F
                green = (value >> 5) & 0x1F
                blue = (value >> 10) & 0x1F
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
            raise ValueError(
                f"unsupported GIM palette format {raster.format}/"
                f"{raster.bits_per_pixel}bpp"
            )
    return tuple(colors)


def discover(data: bytes) -> tuple[tuple[int, Gim], ...]:
    """Find every structurally valid GIM in a byte buffer."""

    found = []
    cursor = 0
    while True:
        offset = data.find(SIGNATURE, cursor)
        if offset < 0:
            break
        try:
            gim = Gim.parse(data, offset)
        except ValueError:
            cursor = offset + 1
            continue
        found.append((offset, gim))
        cursor = offset + gim.size
    return tuple(found)


def pixel_sha256(image: Image.Image) -> str:
    """Hash normalized dimensions and RGBA pixels."""

    normalized = image.convert("RGBA")
    digest = hashlib.sha256()
    digest.update(struct.pack("<II", *normalized.size))
    digest.update(normalized.tobytes())
    return digest.hexdigest()


__all__ = (
    "CHUNK_HEADER_SIZE",
    "IMAGE_CHUNK",
    "INDEX4",
    "INDEX8",
    "LINEAR",
    "PALETTE_CHUNK",
    "PICTURE_CHUNK",
    "PSP_SWIZZLED",
    "RGB565",
    "RGBA4444",
    "RGBA5551",
    "RGBA8888",
    "ROOT_CHUNK",
    "ROOT_OFFSET",
    "SIGNATURE",
    "Gim",
    "GimChunk",
    "GimEncodeReport",
    "GimEncodeResult",
    "GimRaster",
    "discover",
    "pixel_sha256",
)
