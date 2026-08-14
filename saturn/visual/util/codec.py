"""Decode and encode the Saturn raster formats used by the game."""

from __future__ import annotations

import hashlib
import struct
from collections import Counter

from PIL import Image

from .model import ImageAsset


def flatten(image: Image.Image) -> Image.Image:
    if "A" not in image.getbands() and "transparency" not in image.info:
        return image.convert("RGB")
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
    background.alpha_composite(rgba)
    return background.convert("RGB")


def pixel_hash(image: Image.Image) -> str:
    image = flatten(image)
    digest = hashlib.sha256(struct.pack(">II", image.width, image.height))
    digest.update(image.tobytes())
    return digest.hexdigest()


def _display_index(asset: ImageAsset, source_index: int) -> int:
    if asset.layout == "linear":
        return source_index
    if asset.layout != "tiled8" or asset.width % 8 or asset.height % 8:
        raise ValueError(f"{asset.image}: invalid {asset.layout} layout")
    tile, within = divmod(source_index, 64)
    tile_y, tile_x = divmod(tile, asset.width // 8)
    y, x = divmod(within, 8)
    return (tile_y * 8 + y) * asset.width + tile_x * 8 + x


def _rgb555(value: int) -> tuple[int, int, int]:
    red, green, blue = value & 31, (value >> 5) & 31, (value >> 10) & 31
    return tuple((channel << 3) | (channel >> 2) for channel in (red, green, blue))


def _pack_rgb555(color: tuple[int, int, int]) -> int:
    red, green, blue = ((channel * 31 + 127) // 255 for channel in color)
    return red | green << 5 | blue << 10


def _palette(data: bytes, asset: ImageAsset) -> tuple[tuple[int, int, int], ...]:
    if asset.palette_offset is None or asset.palette_entries is None:
        raise ValueError(f"{asset.image}: indexed image has no palette")
    end = asset.palette_offset + asset.palette_entries * 2
    if end > len(data):
        raise ValueError(f"{asset.image}: palette falls outside {asset.source}")
    return tuple(
        _rgb555(struct.unpack_from(">H", data, offset)[0])
        for offset in range(asset.palette_offset, end, 2)
    )


def decode(data: bytes, asset: ImageAsset) -> Image.Image:
    end = asset.offset + asset.byte_length
    if asset.offset < 0 or end > len(data):
        raise ValueError(f"{asset.image}: pixels fall outside {asset.source}")
    encoded = data[asset.offset : end]
    output = bytearray(asset.width * asset.height * 3)
    palette = _palette(data, asset) if asset.encoding == "indexed8" else ()
    for source_index in range(asset.width * asset.height):
        if asset.encoding == "rgb555":
            color = _rgb555(struct.unpack_from(">H", encoded, source_index * 2)[0])
        elif asset.encoding == "rgb888":
            offset = source_index * 4
            color = encoded[offset + 3], encoded[offset + 2], encoded[offset + 1]
        elif asset.encoding == "indexed8":
            index = encoded[source_index]
            if index >= len(palette):
                raise ValueError(
                    f"{asset.image}: palette index {index} is out of range"
                )
            color = palette[index]
        else:
            raise ValueError(f"{asset.image}: unsupported encoding {asset.encoding}")
        offset = _display_index(asset, source_index) * 3
        output[offset : offset + 3] = bytes(color)
    return Image.frombytes("RGB", (asset.width, asset.height), bytes(output))


def encode(target: bytearray, asset: ImageAsset, image: Image.Image) -> None:
    if image.size != (asset.width, asset.height):
        raise ValueError(
            f"{asset.image}: got {image.width}x{image.height}, "
            f"expected {asset.width}x{asset.height}"
        )
    if asset.encoding == "indexed8":
        raise ValueError(f"{asset.image}: indexed images require adaptive_palette()")
    pixels = flatten(image).tobytes()
    for source_index in range(asset.width * asset.height):
        pixel = _display_index(asset, source_index) * 3
        color = tuple(pixels[pixel : pixel + 3])
        offset = asset.offset + source_index * (2 if asset.encoding == "rgb555" else 4)
        if asset.encoding == "rgb555":
            original = struct.unpack_from(">H", target, offset)[0]
            struct.pack_into(
                ">H", target, offset, (original & 0x8000) | _pack_rgb555(color)
            )
        elif asset.encoding == "rgb888":
            target[offset + 1 : offset + 4] = bytes((color[2], color[1], color[0]))
        else:
            raise ValueError(f"{asset.image}: unsupported encoding {asset.encoding}")


def _distance(left: int, right: int) -> int:
    lr, lg, lb = left & 31, (left >> 5) & 31, (left >> 10) & 31
    rr, rg, rb = right & 31, (right >> 5) & 31, (right >> 10) & 31
    return 3 * (lr - rr) ** 2 + 6 * (lg - rg) ** 2 + 2 * (lb - rb) ** 2


def _prepared_pixels(
    image: Image.Image, asset: ImageAsset
) -> tuple[tuple[int, ...], tuple[bool, ...]]:
    if image.size != (asset.width, asset.height):
        raise ValueError(
            f"{asset.image}: got {image.width}x{image.height}, "
            f"expected {asset.width}x{asset.height}"
        )
    has_alpha = "A" in image.getbands() or "transparency" in image.info
    pixels = image.convert("RGBA").tobytes()
    colors: list[int] = []
    transparent: list[bool] = []
    for offset in range(0, len(pixels), 4):
        red, green, blue, alpha = pixels[offset : offset + 4]
        if has_alpha and alpha == 0:
            colors.append(0)
            transparent.append(True)
            continue
        if has_alpha:
            red, green, blue = (
                (channel * alpha + 127) // 255 for channel in (red, green, blue)
            )
        color = _pack_rgb555((red, green, blue))
        colors.append(color)
        transparent.append(not has_alpha and color == 0)
    return tuple(colors), tuple(transparent)


def _choose_colors(counts: Counter[int], limit: int, reserved: set[int]) -> list[int]:
    candidates = Counter(
        {color: count for color, count in counts.items() if color not in reserved}
    )
    if len(candidates) <= limit:
        return [
            color
            for color, _ in sorted(
                candidates.items(), key=lambda item: (-item[1], item[0])
            )
        ]
    strip = Image.new("RGB", (sum(candidates.values()), 1))
    strip.putdata(
        [
            _rgb555(color)
            for color in sorted(candidates)
            for _ in range(candidates[color])
        ]
    )
    quantized = strip.quantize(
        colors=limit, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
    )
    raw_palette = quantized.getpalette()
    usage = Counter(quantized.tobytes())
    chosen: list[int] = []
    seen = set(reserved)
    for index, _ in sorted(usage.items(), key=lambda item: (-item[1], item[0])):
        offset = index * 3
        color = _pack_rgb555(tuple(raw_palette[offset : offset + 3]))
        if color and color not in seen:
            chosen.append(color)
            seen.add(color)
    while len(chosen) < limit:
        remaining = [color for color in candidates if color not in seen]
        if not remaining:
            break
        color = max(
            remaining,
            key=lambda candidate: (
                candidates[candidate]
                * min(_distance(candidate, center) for center in seen),
                candidates[candidate],
                -candidate,
            ),
        )
        chosen.append(color)
        seen.add(color)
    return chosen


def adaptive_palette(target: bytearray, asset: ImageAsset, image: Image.Image) -> None:
    """Quantize one TITLE.BIN overlay to its runtime RGB555 palette."""
    if asset.palette_offset is None or asset.palette_entries is None:
        raise ValueError(f"{asset.image}: indexed image has no palette")
    original_palette = [
        struct.unpack_from(">H", target, asset.palette_offset + index * 2)[0]
        for index in range(asset.palette_entries)
    ]
    reserved_indexes = {0}
    opaque_black = next(
        (index for index, value in enumerate(original_palette) if value == 0x8000), None
    )
    if opaque_black is not None:
        reserved_indexes.add(opaque_black)
    available = [
        index for index in range(asset.palette_entries) if index not in reserved_indexes
    ]
    colors, transparent = _prepared_pixels(image, asset)
    counts = Counter(
        color
        for color, invisible in zip(colors, transparent, strict=True)
        if not invisible
    )
    reserved_colors = {original_palette[index] & 0x7FFF for index in reserved_indexes}
    chosen = _choose_colors(counts, len(available), reserved_colors)
    palette = [0] * asset.palette_entries
    for index in reserved_indexes:
        palette[index] = original_palette[index]
    for index, color in zip(available, chosen, strict=False):
        palette[index] = 0x8000 | color
    for index, value in enumerate(palette):
        struct.pack_into(">H", target, asset.palette_offset + index * 2, value)

    opaque = [
        (index, value & 0x7FFF)
        for index, value in enumerate(palette)
        if index and value
    ]
    exact = {color: index for index, color in reversed(opaque)}
    nearest: dict[int, int] = {}
    for source_index in range(asset.width * asset.height):
        display_index = _display_index(asset, source_index)
        color = colors[display_index]
        if transparent[display_index]:
            target[asset.offset + source_index] = 0
            continue
        index = exact.get(color)
        if index is None:
            index = nearest.setdefault(
                color,
                min(opaque, key=lambda item: (_distance(color, item[1]), item[0]))[0],
            )
        target[asset.offset + source_index] = index
