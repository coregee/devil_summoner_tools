"""Small, read-only ISO9660 resolver for PSP source entries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SECTOR_SIZE = 2048
VOLUME_DESCRIPTOR_START = 16
VOLUME_DESCRIPTOR_LIMIT = 256
VOLUME_IDENTIFIER = b"CD001"


@dataclass(frozen=True, slots=True)
class IsoFileExtent:
    path: str
    lba: int
    size: int

    @property
    def offset(self) -> int:
        return self.lba * SECTOR_SIZE


@dataclass(frozen=True, slots=True)
class _DirectoryRecord:
    name: str
    lba: int
    size: int
    is_directory: bool


def _both_u16(data: bytes, offset: int, context: str) -> int:
    little = int.from_bytes(data[offset : offset + 2], "little")
    big = int.from_bytes(data[offset + 2 : offset + 4], "big")
    if little != big:
        raise ValueError(f"{context} has inconsistent both-endian u16 values")
    return little


def _both_u32(data: bytes, offset: int, context: str) -> int:
    little = int.from_bytes(data[offset : offset + 4], "little")
    big = int.from_bytes(data[offset + 4 : offset + 8], "big")
    if little != big:
        raise ValueError(f"{context} has inconsistent both-endian u32 values")
    return little


def _record(data: bytes, context: str) -> _DirectoryRecord:
    if not data or data[0] < 34 or data[0] > len(data):
        raise ValueError(f"{context} has an invalid record size")
    size = data[0]
    identifier_size = data[32]
    if 33 + identifier_size > size:
        raise ValueError(f"{context} has an invalid identifier size")
    if data[25] & 0x80:
        raise ValueError(f"{context} uses unsupported multi-extent storage")
    identifier = data[33 : 33 + identifier_size]
    if identifier == b"\x00":
        name = "."
    elif identifier == b"\x01":
        name = ".."
    else:
        try:
            name = identifier.decode("ascii")
        except UnicodeDecodeError as error:
            raise ValueError(f"{context} has a non-ASCII identifier") from error
    return _DirectoryRecord(
        name,
        _both_u32(data, 2, f"{context} extent"),
        _both_u32(data, 10, f"{context} size"),
        bool(data[25] & 2),
    )


def _canonical(name: str) -> str:
    return name.split(";", 1)[0].upper()


def _check_extent(record: _DirectoryRecord, image_size: int, context: str) -> None:
    start = record.lba * SECTOR_SIZE
    if start > image_size or record.size > image_size - start:
        raise ValueError(f"{context} extent exceeds the ISO image")


def _entries(image, directory: _DirectoryRecord, image_size: int):
    _check_extent(directory, image_size, f"directory {directory.name!r}")
    image.seek(directory.lba * SECTOR_SIZE)
    data = image.read(directory.size)
    if len(data) != directory.size:
        raise ValueError(f"directory {directory.name!r} is truncated")
    output = []
    cursor = 0
    while cursor < len(data):
        size = data[cursor]
        if size == 0:
            cursor = min(((cursor // SECTOR_SIZE) + 1) * SECTOR_SIZE, len(data))
            continue
        sector_end = ((cursor // SECTOR_SIZE) + 1) * SECTOR_SIZE
        if cursor + size > min(sector_end, len(data)):
            raise ValueError("ISO9660 directory record crosses a sector boundary")
        row = _record(data[cursor : cursor + size], "ISO9660 directory record")
        _check_extent(row, image_size, f"entry {row.name!r}")
        output.append(row)
        cursor += size
    return tuple(output)


def _root(image, image_size: int) -> _DirectoryRecord:
    root = None
    terminated = False
    for sector in range(VOLUME_DESCRIPTOR_START, VOLUME_DESCRIPTOR_LIMIT):
        image.seek(sector * SECTOR_SIZE)
        descriptor = image.read(SECTOR_SIZE)
        if len(descriptor) != SECTOR_SIZE:
            break
        if descriptor[1:6] != VOLUME_IDENTIFIER or descriptor[6] != 1:
            raise ValueError(f"invalid ISO9660 volume descriptor at sector {sector}")
        if descriptor[0] == 1 and root is None:
            if _both_u16(descriptor, 128, "logical block size") != SECTOR_SIZE:
                raise ValueError("unsupported ISO9660 logical block size")
            volume_size = _both_u32(descriptor, 80, "volume space size")
            if volume_size * SECTOR_SIZE > image_size:
                raise ValueError("ISO9660 volume space exceeds the image")
            root = _record(descriptor[156:], "ISO9660 root record")
            if not root.is_directory:
                raise ValueError("ISO9660 root record is not a directory")
        if descriptor[0] == 255:
            terminated = True
            break
    if root is None or not terminated:
        raise ValueError("ISO9660 primary volume descriptor is incomplete")
    return root


def _components(path: str) -> tuple[str, ...]:
    if not isinstance(path, str) or not path or path.startswith(("/", "\\")):
        raise ValueError("ISO9660 path must be relative POSIX text")
    if "\\" in path:
        raise ValueError("ISO9660 path must use POSIX separators")
    parts = tuple(path.split("/"))
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("ISO9660 path contains an unsafe component")
    return parts


def resolve_iso9660_path(image_path: Path, entry_path: str) -> IsoFileExtent:
    parts = _components(entry_path)
    image_size = image_path.stat().st_size
    with image_path.open("rb") as image:
        current = _root(image, image_size)
        for index, part in enumerate(parts):
            matches = [
                row
                for row in _entries(image, current, image_size)
                if row.name not in {".", ".."}
                and _canonical(row.name) == _canonical(part)
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"ISO9660 component {part!r} is missing or ambiguous in "
                    f"{entry_path!r}"
                )
            current = matches[0]
            final = index == len(parts) - 1
            if final == current.is_directory:
                kind = "directory" if final else "file"
                raise ValueError(f"ISO9660 component {part!r} is a {kind}")
    return IsoFileExtent(entry_path, current.lba, current.size)


def read_iso9660_file(
    image_path: Path,
    entry_path: str,
) -> tuple[IsoFileExtent, bytes]:
    extent = resolve_iso9660_path(image_path, entry_path)
    with image_path.open("rb") as image:
        image.seek(extent.offset)
        data = image.read(extent.size)
    if len(data) != extent.size:
        raise ValueError(f"ISO9660 entry {entry_path!r} is truncated")
    return extent, data

