"""ISO9660 filesystem discovery for a raw Saturn Mode 1 data track."""

from __future__ import annotations

from dataclasses import dataclass

from .mode1 import PAYLOAD_SIZE, Mode1Track


def _both_endian_u32(value: bytes, context: str) -> int:
    if len(value) != 8:
        raise ValueError(f"{context}: expected an eight-byte both-endian integer")
    little = int.from_bytes(value[:4], "little")
    big = int.from_bytes(value[4:], "big")
    if little != big:
        raise ValueError(f"{context}: little- and big-endian values disagree")
    return little


@dataclass(frozen=True)
class IsoFile:
    path: str
    extent: int
    size: int
    record_offset: int

    @property
    def sector_count(self) -> int:
        return (self.size + PAYLOAD_SIZE - 1) // PAYLOAD_SIZE

    @property
    def capacity(self) -> int:
        return self.sector_count * PAYLOAD_SIZE

    @property
    def key(self) -> str:
        return self.path.casefold()


class Iso9660:
    def __init__(self, track: Mode1Track):
        self.track = track

    def files(self) -> dict[str, IsoFile]:
        descriptor = self.track.read(16 * PAYLOAD_SIZE, PAYLOAD_SIZE)
        if descriptor[:7] != b"\x01CD001\x01":
            raise ValueError("data track has no ISO9660 primary volume descriptor")
        root_length = descriptor[156]
        if root_length < 34 or 156 + root_length > len(descriptor):
            raise ValueError("ISO9660 primary volume descriptor has an invalid root")
        root = descriptor[156 : 156 + root_length]
        root_extent = _both_endian_u32(root[2:10], "root extent")
        root_size = _both_endian_u32(root[10:18], "root size")

        found: dict[str, IsoFile] = {}
        visited: set[tuple[int, int]] = set()

        def walk(extent: int, size: int, parent: str) -> None:
            identity = (extent, size)
            if identity in visited:
                raise ValueError(f"ISO9660 directory cycle at {parent or '/'}")
            visited.add(identity)
            directory = self.track.read(extent * PAYLOAD_SIZE, size)
            cursor = 0
            while cursor < len(directory):
                record_length = directory[cursor]
                if record_length == 0:
                    cursor = ((cursor // PAYLOAD_SIZE) + 1) * PAYLOAD_SIZE
                    continue
                if record_length < 34 or cursor + record_length > len(directory):
                    raise ValueError(
                        f"invalid ISO9660 directory record at {parent or '/'}+0x{cursor:X}"
                    )
                record = directory[cursor : cursor + record_length]
                record_offset = extent * PAYLOAD_SIZE + cursor
                cursor += record_length

                name_length = record[32]
                if 33 + name_length > len(record):
                    raise ValueError(f"invalid ISO9660 name at {parent or '/'}")
                raw_name = record[33 : 33 + name_length]
                if raw_name in {b"\x00", b"\x01"}:
                    continue
                try:
                    name = raw_name.decode("ascii")
                except UnicodeDecodeError as error:
                    raise ValueError(
                        f"non-ASCII ISO9660 name under {parent or '/'}"
                    ) from error
                name = name.split(";", 1)[0]
                path = f"{parent}/{name}" if parent else name
                child_extent = _both_endian_u32(record[2:10], f"{path} extent")
                child_size = _both_endian_u32(record[10:18], f"{path} size")
                flags = record[25]
                if flags & 2:
                    walk(child_extent, child_size, path)
                    continue
                if flags & 0x80:
                    raise ValueError(
                        f"multi-extent ISO9660 file is unsupported: {path}"
                    )
                entry = IsoFile(path, child_extent, child_size, record_offset)
                if entry.key in found:
                    raise ValueError(f"duplicate case-insensitive ISO9660 path: {path}")
                found[entry.key] = entry

        walk(root_extent, root_size, "")
        occupied = sorted(
            (entry.extent, entry.extent + entry.sector_count, entry.path)
            for entry in found.values()
            if entry.sector_count
        )
        for previous, current in zip(occupied, occupied[1:]):
            if current[0] < previous[1]:
                raise ValueError(
                    f"overlapping ISO9660 file extents: {previous[2]} and {current[2]}"
                )
        return found

    def read_file(self, entry: IsoFile) -> bytes:
        return self.track.read(entry.extent * PAYLOAD_SIZE, entry.size)
