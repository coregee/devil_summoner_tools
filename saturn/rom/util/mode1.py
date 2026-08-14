"""Read and update the 2048-byte payloads inside raw MODE1/2352 sectors."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import BinaryIO

RAW_SECTOR_SIZE = 2352
PAYLOAD_OFFSET = 16
PAYLOAD_SIZE = 2048


def _checksum_tables() -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    forward = [0] * 256
    backward = [0] * 256
    edc_table = [0] * 256
    for value in range(256):
        doubled = (value << 1) ^ (0x11D if value & 0x80 else 0)
        doubled &= 0xFF
        forward[value] = doubled
        backward[value ^ doubled] = value

        remainder = value
        for _ in range(8):
            remainder = (remainder >> 1) ^ (0xD8018001 if remainder & 1 else 0)
        edc_table[value] = remainder & 0xFFFFFFFF
    return tuple(forward), tuple(backward), tuple(edc_table)


_ECC_FORWARD, _ECC_BACKWARD, _EDC = _checksum_tables()


def _edc(data: bytes | bytearray) -> int:
    result = 0
    for value in data:
        result = (result >> 8) ^ _EDC[(result ^ value) & 0xFF]
    return result & 0xFFFFFFFF


def _ecc_block(
    source: bytes | bytearray,
    major_count: int,
    minor_count: int,
    major_stride: int,
    minor_stride: int,
) -> bytes:
    output = bytearray(major_count * 2)
    source_size = major_count * minor_count
    for major in range(major_count):
        cursor = (major // 2) * major_stride + major % 2
        first = 0
        second = 0
        for _ in range(minor_count):
            value = source[cursor]
            cursor = (cursor + minor_stride) % source_size
            first ^= value
            second ^= value
            first = _ECC_FORWARD[first]
        first = _ECC_BACKWARD[_ECC_FORWARD[first] ^ second]
        output[major] = first
        output[major + major_count] = first ^ second
    return bytes(output)


def repair_sector(sector: bytearray) -> None:
    """Regenerate the EDC, reserved area, P parity, and Q parity in place."""
    if len(sector) != RAW_SECTOR_SIZE:
        raise ValueError(f"expected a {RAW_SECTOR_SIZE}-byte raw sector")
    if sector[15] != 1:
        raise ValueError(f"expected Mode 1, found sector mode {sector[15]}")

    struct.pack_into("<I", sector, 2064, _edc(sector[:2064]))
    sector[2068:2076] = bytes(8)
    sector[2076:2248] = _ecc_block(sector[12:2248], 86, 24, 2, 86)
    sector[2248:2352] = _ecc_block(sector[12:2248], 52, 43, 86, 88)


def sector_checksums_valid(sector: bytes) -> bool:
    candidate = bytearray(sector)
    repair_sector(candidate)
    return candidate == sector


class Mode1Track:
    """Random access to a Mode 1 track's logical 2048-byte payload stream."""

    def __init__(self, path: Path, first_sector: int, *, writable: bool = False):
        if first_sector < 0:
            raise ValueError("first sector cannot be negative")
        self.path = path
        self.first_sector = first_sector
        self.writable = writable
        self._stream: BinaryIO | None = None
        self.dirty_sectors: set[int] = set()

    def __enter__(self) -> "Mode1Track":
        self._stream = self.path.open("r+b" if self.writable else "rb")
        size = self.path.stat().st_size
        if size % RAW_SECTOR_SIZE:
            self._stream.close()
            self._stream = None
            raise ValueError(f"{self.path}: not a whole number of raw sectors")
        if self.first_sector >= size // RAW_SECTOR_SIZE:
            self._stream.close()
            self._stream = None
            raise ValueError(f"{self.path}: INDEX 01 lies beyond the track")
        return self

    def __exit__(self, *_: object) -> None:
        if self._stream is not None:
            self._stream.close()
            self._stream = None

    @property
    def stream(self) -> BinaryIO:
        if self._stream is None:
            raise RuntimeError("Mode1Track must be used as a context manager")
        return self._stream

    def _raw_offset(self, logical_sector: int) -> int:
        if logical_sector < 0:
            raise ValueError("logical sector cannot be negative")
        return (self.first_sector + logical_sector) * RAW_SECTOR_SIZE

    def read_raw_sector(self, logical_sector: int) -> bytes:
        self.stream.seek(self._raw_offset(logical_sector))
        value = self.stream.read(RAW_SECTOR_SIZE)
        if len(value) != RAW_SECTOR_SIZE:
            raise ValueError(f"track ends inside logical sector {logical_sector}")
        if value[15] != 1:
            raise ValueError(
                f"logical sector {logical_sector} has mode {value[15]}, expected Mode 1"
            )
        return value

    def read(self, offset: int, size: int) -> bytes:
        if offset < 0 or size < 0:
            raise ValueError("payload offset and size cannot be negative")
        result = bytearray()
        cursor = offset
        remaining = size
        while remaining:
            logical_sector, within = divmod(cursor, PAYLOAD_SIZE)
            take = min(remaining, PAYLOAD_SIZE - within)
            sector = self.read_raw_sector(logical_sector)
            start = PAYLOAD_OFFSET + within
            result.extend(sector[start : start + take])
            cursor += take
            remaining -= take
        return bytes(result)

    def write(self, offset: int, value: bytes) -> int:
        if not self.writable:
            raise ValueError("track was opened read-only")
        if offset < 0:
            raise ValueError("payload offset cannot be negative")

        changed = 0
        cursor = 0
        while cursor < len(value):
            logical_sector, within = divmod(offset, PAYLOAD_SIZE)
            take = min(len(value) - cursor, PAYLOAD_SIZE - within)
            sector = bytearray(self.read_raw_sector(logical_sector))
            start = PAYLOAD_OFFSET + within
            replacement = value[cursor : cursor + take]
            if sector[start : start + take] != replacement:
                sector[start : start + take] = replacement
                repair_sector(sector)
                self.stream.seek(self._raw_offset(logical_sector))
                self.stream.write(sector)
                self.dirty_sectors.add(logical_sector)
                changed += 1
            offset += take
            cursor += take
        return changed

    def write_extent(self, extent: int, value: bytes, capacity: int) -> int:
        if capacity < 0 or capacity % PAYLOAD_SIZE:
            raise ValueError("file allocation must be a nonnegative sector multiple")
        if len(value) > capacity:
            raise ValueError(
                f"replacement is {len(value):,} bytes, exceeding {capacity:,} bytes"
            )
        padded = value + bytes(capacity - len(value))
        return self.write(extent * PAYLOAD_SIZE, padded)

    def checksums_valid(self, logical_sector: int) -> bool:
        return sector_checksums_valid(self.read_raw_sector(logical_sector))
