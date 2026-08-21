"""Lossless reader for the common Atlus PSP resource pack."""

from __future__ import annotations

import struct
from dataclasses import dataclass


def _align(value: int, boundary: int = 0x10) -> int:
    return (value + boundary - 1) & -boundary


@dataclass(frozen=True, slots=True)
class PackMember:
    index: int
    offset: int
    data: bytes


def read_members(data: bytes) -> tuple[PackMember, ...]:
    if len(data) < 4:
        raise ValueError("PSP pack is shorter than its member count")
    count = struct.unpack_from("<I", data)[0]
    if not 1 <= count <= 0x10000:
        raise ValueError(f"invalid PSP pack member count: {count}")
    table_end = 4 + count * 4
    cursor = _align(table_end)
    if cursor > len(data):
        raise ValueError("PSP pack member table exceeds the file")
    sizes = struct.unpack_from(f"<{count}I", data, 4)
    members = []
    for index, size in enumerate(sizes):
        end = cursor + size
        if end > len(data) or _align(end) > len(data):
            raise ValueError(f"PSP pack member {index} exceeds the file")
        members.append(PackMember(index, cursor, data[cursor:end]))
        cursor = _align(end)
    return tuple(members)

