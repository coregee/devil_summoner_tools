"""Atomic publication for checked, same-size PSP ISO replacements."""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .iso9660 import IsoFileExtent


BUFFER_SIZE = 1024 * 1024


@dataclass(frozen=True, slots=True)
class IsoReplacement:
    extent: IsoFileExtent
    source_data: bytes
    replacement_data: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.source_data, bytes) or not isinstance(
            self.replacement_data, bytes
        ):
            raise TypeError("ISO replacement data must be bytes")
        if len(self.source_data) != self.extent.size:
            raise ValueError(f"{self.extent.path}: source size changed")
        if len(self.replacement_data) != self.extent.size:
            raise ValueError(f"{self.extent.path}: replacement must retain its size")


def _ordered(replacements: Iterable[IsoReplacement], image_size: int):
    rows = tuple(sorted(replacements, key=lambda row: row.extent.offset))
    if not rows:
        raise ValueError("at least one ISO replacement is required")
    previous_end = 0
    paths: set[str] = set()
    for row in rows:
        start, end = row.extent.offset, row.extent.offset + row.extent.size
        if start < previous_end or end > image_size:
            raise ValueError("ISO replacement extents overlap or exceed the image")
        if row.extent.path.casefold() in paths:
            raise ValueError(f"duplicate ISO replacement: {row.extent.path}")
        paths.add(row.extent.path.casefold())
        previous_end = end
    return rows


def _copy(source, destination, count: int, digest, *, compare=None) -> None:
    remaining = count
    while remaining:
        size = min(BUFFER_SIZE, remaining)
        block = source.read(size)
        if len(block) != size:
            raise ValueError("source ISO is truncated")
        if compare is not None:
            other = compare.read(size)
            if other != block:
                raise ValueError("replacement ISO differs outside checked extents")
        if destination is not None:
            destination.write(block)
        digest.update(block)
        remaining -= size


def replaced_iso_sha256(
    source_path: Path,
    *,
    image_size: int,
    replacements: Iterable[IsoReplacement],
) -> str:
    rows = _ordered(replacements, image_size)
    digest = hashlib.sha256()
    with source_path.open("rb") as source:
        cursor = 0
        for row in rows:
            _copy(source, None, row.extent.offset - cursor, digest)
            original = source.read(row.extent.size)
            if original != row.source_data:
                raise ValueError(f"{row.extent.path}: source extent changed")
            digest.update(row.replacement_data)
            cursor = row.extent.offset + row.extent.size
        _copy(source, None, image_size - cursor, digest)
        if source.read(1):
            raise ValueError("source ISO exceeds its pinned size")
    return digest.hexdigest()


def write_replaced_iso(
    source_path: Path,
    output_path: Path,
    *,
    image_size: int,
    replacements: Iterable[IsoReplacement],
    expected_sha256: str,
) -> str:
    rows = _ordered(replacements, image_size)
    if source_path.resolve() == output_path.resolve():
        raise ValueError("PSP output ISO must not be the source image")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.is_symlink() or (output_path.exists() and not output_path.is_file()):
        raise ValueError(f"invalid PSP output destination: {output_path}")
    handle = tempfile.NamedTemporaryFile(
        mode="wb",
        dir=output_path.parent,
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temporary = Path(handle.name)
    digest = hashlib.sha256()
    try:
        with handle, source_path.open("rb") as source:
            cursor = 0
            for row in rows:
                _copy(source, handle, row.extent.offset - cursor, digest)
                original = source.read(row.extent.size)
                if original != row.source_data:
                    raise ValueError(f"{row.extent.path}: source extent changed")
                handle.write(row.replacement_data)
                digest.update(row.replacement_data)
                cursor = row.extent.offset + row.extent.size
            _copy(source, handle, image_size - cursor, digest)
            if source.read(1):
                raise ValueError("source ISO exceeds its pinned size")
            handle.flush()
            os.fsync(handle.fileno())
        actual = digest.hexdigest()
        if actual != expected_sha256:
            raise ValueError(
                f"PSP output ISO SHA-256 is {actual}; expected {expected_sha256}"
            )
        os.replace(temporary, output_path)
        return actual
    finally:
        if temporary.exists():
            temporary.unlink()


def verify_replaced_iso(
    source_path: Path,
    output_path: Path,
    *,
    image_size: int,
    replacements: Iterable[IsoReplacement],
    expected_sha256: str,
) -> str:
    rows = _ordered(replacements, image_size)
    if not output_path.is_file() or output_path.is_symlink():
        raise ValueError(f"PSP output ISO is missing: {output_path}")
    if output_path.stat().st_size != image_size:
        raise ValueError("PSP output ISO size changed")
    digest = hashlib.sha256()
    with source_path.open("rb") as source, output_path.open("rb") as output:
        cursor = 0
        for row in rows:
            _copy(
                source,
                None,
                row.extent.offset - cursor,
                digest,
                compare=output,
            )
            source_data = source.read(row.extent.size)
            output_data = output.read(row.extent.size)
            if source_data != row.source_data:
                raise ValueError(f"{row.extent.path}: source extent changed")
            if output_data != row.replacement_data:
                raise ValueError(f"{row.extent.path}: output extent is stale")
            digest.update(output_data)
            cursor = row.extent.offset + row.extent.size
        _copy(source, None, image_size - cursor, digest, compare=output)
        if source.read(1) or output.read(1):
            raise ValueError("PSP ISO stream exceeds its pinned size")
    actual = digest.hexdigest()
    if actual != expected_sha256:
        raise ValueError(
            f"PSP output ISO SHA-256 is {actual}; expected {expected_sha256}"
        )
    return actual

