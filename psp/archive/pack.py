"""Lossless parser and same-layout rebuilder for Atlus PSP resource packs."""

from __future__ import annotations

import struct
from collections.abc import Mapping
from dataclasses import dataclass


ALIGNMENT = 0x10
MAX_MEMBER_COUNT = 0x10000


def align(value: int, boundary: int = ALIGNMENT) -> int:
    if boundary <= 0 or boundary & (boundary - 1):
        raise ValueError("alignment must be a positive power of two")
    return (value + boundary - 1) & -boundary


@dataclass(frozen=True, slots=True)
class PackMember:
    index: int
    offset: int
    data: bytes
    padding: bytes

    @property
    def size(self) -> int:
        return len(self.data)


@dataclass(frozen=True, slots=True)
class PspPack:
    members: tuple[PackMember, ...]
    header_padding: bytes
    trailing: bytes

    @classmethod
    def parse(cls, data: bytes) -> "PspPack":
        if not isinstance(data, bytes):
            raise TypeError("PSP pack source must be bytes")
        if len(data) < 4:
            raise ValueError("PSP pack is shorter than its member count")
        count = struct.unpack_from("<I", data)[0]
        if not 1 <= count <= MAX_MEMBER_COUNT:
            raise ValueError(f"invalid PSP pack member count: {count}")
        table_end = 4 + count * 4
        header_end = align(table_end)
        if header_end > len(data):
            raise ValueError("PSP pack size table exceeds the file")
        sizes = struct.unpack_from(f"<{count}I", data, 4)
        cursor = header_end
        members = []
        for index, size in enumerate(sizes):
            end = cursor + size
            padded_end = align(end)
            if end > len(data) or padded_end > len(data):
                raise ValueError(f"PSP pack member {index} exceeds the file")
            members.append(
                PackMember(index, cursor, data[cursor:end], data[end:padded_end])
            )
            cursor = padded_end
        return cls(
            tuple(members),
            data[table_end:header_end],
            data[cursor:],
        )

    def rebuild(self, replacements: Mapping[int, bytes] | None = None) -> bytes:
        replacements = {} if replacements is None else dict(replacements)
        invalid = sorted(set(replacements) - set(range(len(self.members))))
        if invalid:
            raise ValueError(f"invalid PSP pack replacement indices: {invalid}")
        payloads = [
            replacements.get(member.index, member.data) for member in self.members
        ]
        if any(not isinstance(payload, bytes) for payload in payloads):
            raise TypeError("PSP pack replacements must be bytes")

        output = bytearray(struct.pack("<I", len(payloads)))
        output.extend(
            struct.pack(f"<{len(payloads)}I", *(len(data) for data in payloads))
        )
        header_padding_size = align(len(output)) - len(output)
        output.extend(
            self.header_padding
            if header_padding_size == len(self.header_padding)
            else bytes(header_padding_size)
        )
        for member, payload in zip(self.members, payloads, strict=True):
            output.extend(payload)
            padding_size = align(len(output)) - len(output)
            output.extend(
                member.padding
                if len(payload) == member.size
                and padding_size == len(member.padding)
                else bytes(padding_size)
            )
        output.extend(self.trailing)
        return bytes(output)
