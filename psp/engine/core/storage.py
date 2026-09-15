"""Ownership checks for reclaimed storage and live city-map terrain."""

from __future__ import annotations

import hashlib
import struct

from .layout import (
    DATA_LOAD_SEGMENT_ADDRESS,
    MAP2D_COLLISION_TABLE_ADDRESS,
    MAP2D_COLLISION_TABLE_END_ADDRESS,
    NAME_RETIRED_STORAGE_ADDRESS,
    NAME_RETIRED_STORAGE_END_ADDRESS,
)


def is_retired_name_storage(start: int, end: int) -> bool:
    return NAME_RETIRED_STORAGE_ADDRESS <= start < end <= NAME_RETIRED_STORAGE_END_ADDRESS


def validate_retired_name_source(stock: bytes) -> None:
    source = stock[NAME_RETIRED_STORAGE_ADDRESS + 0x80 : NAME_RETIRED_STORAGE_END_ADDRESS + 0x80]
    if hashlib.sha256(source).hexdigest() != "d2f05430aac29343ac62fef86aa8c5a6fcd79f31ec7f8ead91696dc9d522932e":
        raise ValueError("PSP retired NAME Kanji storage source changed")
    # Relocation offsets in .data are relative to the second load segment.
    # A zero-run check alone neither proves ownership nor excludes relocations.
    for offset, size in ((0x1CD9E8, 0x68ED8), (0x236B28, 0x6180), (0x23CCA8, 0xC510)):
        for cursor in range(offset, offset + size, 8):
            address, info = struct.unpack_from("<II", stock, cursor)
            address += DATA_LOAD_SEGMENT_ADDRESS if (info >> 8) & 0xFF else 0
            if NAME_RETIRED_STORAGE_ADDRESS <= address < NAME_RETIRED_STORAGE_END_ADDRESS:
                raise ValueError("PSP relocation writes into retired NAME storage")


def validate_retired_name_owner(data: bytes) -> None:
    # The primary grid count is one 152-cell page; all active descriptors point
    # into the replacement label blob, before the shared reserve. Descriptor 0
    # is the untouched null row. Other tabs retain their separate 152-cell grids.
    if struct.unpack_from("<I", data, 0x1C8AF8 + 0x80)[0] != 152:
        raise ValueError("PSP shared storage requires the English NAME single-page grid")
    for index in range(1, 27):
        pointer, count = struct.unpack_from("<II", data, 0x1C6BD4 + index * 8 + 0x80)
        address = pointer + DATA_LOAD_SEGMENT_ADDRESS
        if not (count > 0 and 0x1C6DDC <= address < address + count * 2 <= 0x1C715C):
            raise ValueError("PSP shared storage requires the English NAME label descriptors")


def validate_map_collision_data(stock: bytes, output: bytes) -> None:
    start, end = MAP2D_COLLISION_TABLE_ADDRESS + 0x80, MAP2D_COLLISION_TABLE_END_ADDRESS + 0x80
    if hashlib.sha256(stock[start:end]).hexdigest() != "ef8df8c2e867e239917340f47a0d6dac98ee37f2bbdf109d39716fc4e159ea1b":
        raise ValueError("PSP MAP2D collision-table source changed")
    if output[start:end] != stock[start:end]:
        raise ValueError("PSP patches modified live MAP2D collision tiles")
