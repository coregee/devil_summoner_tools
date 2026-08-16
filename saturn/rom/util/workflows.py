"""High-level extraction, rebuilding, and verification workflows."""

from __future__ import annotations

import filecmp
import os
import shutil
import struct
import tempfile
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .catalog import ValidatedDisc
from .cue import CueFile, CueSheet
from .iso9660 import Iso9660, IsoFile
from .mode1 import PAYLOAD_SIZE, RAW_SECTOR_SIZE, Mode1Track
from .paths import contained_path, relative_key, safe_relative_path


@dataclass(frozen=True)
class ExtractionResult:
    files: int
    total_bytes: int
    written: int
    current: int
    stale: int
    missing: int
    extra: int


@dataclass(frozen=True)
class RepackItem:
    path: Path
    relative: str
    entry: IsoFile
    size: int
    changed: bool

    @property
    def size_changed(self) -> bool:
        return self.size != self.entry.size


@dataclass(frozen=True)
class RepackResult:
    files: int
    changed_files: int
    rewritten_sectors: int
    raw_changed_sectors: int
    output_cue: Path


def _entry_output_path(root: Path, entry: IsoFile) -> Path:
    relative = safe_relative_path(entry.path, "ISO9660 path")
    return contained_path(root, relative, "ISO9660 output path")


def _atomic_write(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.is_file():
            temporary.unlink()


def _files_under(root: Path) -> dict[str, Path]:
    if not root.exists():
        return {}
    if not root.is_dir() or root.is_symlink():
        raise ValueError(f"expected a real directory: {root}")
    result: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"symbolic links are not allowed under {root}: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        key = relative_key(relative)
        if key in result:
            raise ValueError(
                f"case-insensitive path collision under {root}: {relative}"
            )
        result[key] = path
    return result


def list_iso_files(validated: ValidatedDisc) -> tuple[IsoFile, ...]:
    track_path = validated.sheet.source_path(validated.data_track.file)
    with Mode1Track(track_path, validated.data_track.index(1)) as track:
        files = Iso9660(track).files()
    return tuple(sorted(files.values(), key=lambda entry: entry.key))


def read_source_files(
    validated: ValidatedDisc,
    paths: Iterable[str],
) -> dict[str, bytes]:
    """Read selected files directly from a validated source disc."""
    requested: dict[str, str] = {}
    for value in paths:
        normalized = safe_relative_path(value, "source-disc path").as_posix()
        key = normalized.casefold()
        if key in requested:
            raise ValueError(f"duplicate source-disc path: {value}")
        requested[key] = value

    track_path = validated.sheet.source_path(validated.data_track.file)
    with Mode1Track(track_path, validated.data_track.index(1)) as track:
        iso = Iso9660(track)
        entries = iso.files()
        missing = [requested[key] for key in requested if key not in entries]
        if missing:
            raise ValueError(
                f"{validated.spec.disc_id}: source disc is missing "
                + ", ".join(missing)
            )
        return {
            requested[key]: iso.read_file(entries[key])
            for key in requested
        }


def extract_disc(
    validated: ValidatedDisc,
    output: Path,
    *,
    check: bool = False,
    overwrite: bool = False,
) -> ExtractionResult:
    """Extract or verify one complete ISO9660 filesystem mirror."""
    output = output.resolve()
    for cue_file in validated.sheet.files:
        source = validated.sheet.source_path(cue_file).resolve()
        if source.is_relative_to(output):
            raise ValueError(f"extraction root would contain source track: {source}")

    track_path = validated.sheet.source_path(validated.data_track.file)
    with Mode1Track(track_path, validated.data_track.index(1)) as track:
        iso = Iso9660(track)
        entries = tuple(sorted(iso.files().values(), key=lambda entry: entry.key))
        expected_keys = {entry.key for entry in entries}
        existing = _files_under(output)
        extras = sorted(set(existing) - expected_keys)

        states: dict[str, str] = {}
        stale_paths: list[Path] = []
        for entry in entries:
            destination = _entry_output_path(output, entry)
            if destination.exists() and not destination.is_file():
                raise ValueError(f"extraction target is not a file: {destination}")
            if not destination.is_file():
                states[entry.key] = "missing"
                continue
            value = iso.read_file(entry)
            if (
                destination.stat().st_size == len(value)
                and destination.read_bytes() == value
            ):
                states[entry.key] = "current"
            else:
                states[entry.key] = "stale"
                stale_paths.append(destination)

        missing = sum(state == "missing" for state in states.values())
        stale = len(stale_paths)
        current = sum(state == "current" for state in states.values())
        total_bytes = sum(entry.size for entry in entries)

        if check:
            if missing or stale or extras:
                details = []
                if missing:
                    details.append(f"{missing} missing")
                if stale:
                    details.append(f"{stale} different")
                if extras:
                    details.append(f"{len(extras)} extra")
                raise ValueError(
                    f"{validated.spec.disc_id}: extracted mirror is not exact "
                    f"({', '.join(details)}) under {output}"
                )
            return ExtractionResult(
                len(entries), total_bytes, 0, current, stale, missing, len(extras)
            )

        if stale and not overwrite:
            preview = ", ".join(str(path) for path in stale_paths[:3])
            suffix = "" if stale <= 3 else f" (and {stale - 3} more)"
            raise ValueError(
                f"{validated.spec.disc_id}: {stale} extracted files differ; "
                f"pass --overwrite to restore them: {preview}{suffix}"
            )

        written = 0
        for entry in entries:
            if states[entry.key] == "current":
                continue
            _atomic_write(_entry_output_path(output, entry), iso.read_file(entry))
            written += 1

    return ExtractionResult(
        len(entries), total_bytes, written, current, stale, missing, len(extras)
    )


def plan_repack(
    validated: ValidatedDisc,
    extracted: Path,
) -> tuple[RepackItem, ...]:
    extracted = extracted.resolve()
    if not extracted.is_dir() or extracted.is_symlink():
        raise ValueError(f"editable extraction directory is missing: {extracted}")

    track_path = validated.sheet.source_path(validated.data_track.file)
    with Mode1Track(track_path, validated.data_track.index(1)) as track:
        iso = Iso9660(track)
        entries = iso.files()
        local_files = _files_under(extracted)
        expected = set(entries)
        missing = sorted(expected - set(local_files))
        extra = sorted(set(local_files) - expected)
        if missing or extra:
            details = []
            if missing:
                details.append(
                    f"missing {len(missing)} file(s), including {missing[0]}"
                )
            if extra:
                details.append(
                    f"found {len(extra)} extra file(s), including {extra[0]}"
                )
            raise ValueError(
                f"{validated.spec.disc_id}: extracted mirror does not match the ISO: "
                + "; ".join(details)
            )

        planned: list[RepackItem] = []
        for key, entry in sorted(entries.items()):
            path = local_files[key]
            size = path.stat().st_size
            if size > entry.capacity:
                raise ValueError(
                    f"{entry.path}: {size:,} bytes exceeds its fixed "
                    f"{entry.capacity:,}-byte allocation"
                )
            value = path.read_bytes()
            changed = size != entry.size or value != iso.read_file(entry)
            planned.append(RepackItem(path, entry.path, entry, size, changed))
    return tuple(planned)


def _output_path(root: Path, cue_file: CueFile) -> Path:
    return contained_path(root, cue_file.relative_path, "rebuilt track path")


def _copy_source_disc(validated: ValidatedDisc, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    output_cue = destination / validated.sheet.path.name
    shutil.copy2(validated.sheet.path, output_cue)
    copied: set[str] = set()
    for cue_file in validated.sheet.files:
        key = cue_file.relative_path.as_posix().casefold()
        if key in copied:
            continue
        source = validated.sheet.source_path(cue_file).resolve()
        output = _output_path(destination, cue_file)
        if output.resolve() == source:
            raise ValueError(f"build would overwrite source track: {source}")
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, output)
        copied.add(key)


def _expected_build_files(validated: ValidatedDisc) -> set[str]:
    expected = {validated.sheet.path.name.casefold()}
    expected.update(
        cue_file.relative_path.as_posix().casefold()
        for cue_file in validated.sheet.files
    )
    return expected


def _raw_changed_sectors(
    source: Path,
    rebuilt: Path,
    first_sector: int,
) -> set[int]:
    size = source.stat().st_size
    if rebuilt.stat().st_size != size:
        raise ValueError("rebuilt data track size changed")
    if size % RAW_SECTOR_SIZE:
        raise ValueError("data track is not a whole number of raw sectors")

    changed: set[int] = set()
    sectors_per_block = 1024
    block_size = sectors_per_block * RAW_SECTOR_SIZE
    physical_sector = 0
    with source.open("rb") as left, rebuilt.open("rb") as right:
        while original_block := left.read(block_size):
            rebuilt_block = right.read(len(original_block))
            if len(rebuilt_block) != len(original_block):
                raise ValueError("rebuilt data track ended early")
            if original_block != rebuilt_block:
                for within in range(len(original_block) // RAW_SECTOR_SIZE):
                    start = within * RAW_SECTOR_SIZE
                    original_sector = original_block[start : start + RAW_SECTOR_SIZE]
                    rebuilt_sector = rebuilt_block[start : start + RAW_SECTOR_SIZE]
                    if original_sector == rebuilt_sector:
                        continue
                    logical_sector = physical_sector + within - first_sector
                    if original_sector[:16] != rebuilt_sector[:16]:
                        raise ValueError(
                            f"raw sector header changed at logical sector {logical_sector}"
                        )
                    changed.add(logical_sector)
            physical_sector += len(original_block) // RAW_SECTOR_SIZE
        if right.read(1):
            raise ValueError("rebuilt data track has trailing bytes")
    return changed


def verify_repack(
    validated: ValidatedDisc,
    output: Path,
    plan: tuple[RepackItem, ...],
) -> RepackResult:
    output = output.resolve()
    if not output.is_dir() or output.is_symlink():
        raise ValueError(f"rebuilt disc directory is missing: {output}")
    actual_files = _files_under(output)
    expected_files = _expected_build_files(validated)
    if set(actual_files) != expected_files:
        missing = sorted(expected_files - set(actual_files))
        extra = sorted(set(actual_files) - expected_files)
        raise ValueError(
            f"rebuilt disc file set differs (missing={missing}, extra={extra})"
        )

    output_cue = output / validated.sheet.path.name
    if output_cue.read_bytes() != validated.sheet.path.read_bytes():
        raise ValueError("rebuilt CUE differs from the source CUE")
    output_sheet = CueSheet.read(output_cue)
    if output_sheet.tracks != validated.sheet.tracks:
        raise ValueError("rebuilt CUE topology differs from the source")

    data_relative = validated.data_track.file.relative_path.as_posix().casefold()
    for cue_file in validated.sheet.files:
        if cue_file.relative_path.as_posix().casefold() == data_relative:
            continue
        source = validated.sheet.source_path(cue_file)
        rebuilt = _output_path(output, cue_file)
        if not filecmp.cmp(source, rebuilt, shallow=False):
            raise ValueError(f"non-data track changed: {cue_file.name}")

    data_source = validated.sheet.source_path(validated.data_track.file)
    data_output = _output_path(output, validated.data_track.file)
    allowed: set[int] = set()
    for item in plan:
        if item.changed:
            allowed.update(
                range(item.entry.extent, item.entry.extent + item.entry.sector_count)
            )
        if item.size_changed:
            allowed.add(item.entry.record_offset // PAYLOAD_SIZE)

    raw_changed = _raw_changed_sectors(
        data_source, data_output, validated.data_track.index(1)
    )
    unexpected = sorted(raw_changed - allowed)
    if unexpected:
        raise ValueError(
            f"unexpected raw-disc change at logical sector {unexpected[0]}"
        )

    with Mode1Track(data_output, validated.data_track.index(1)) as track:
        output_iso = Iso9660(track)
        output_entries = output_iso.files()
        for item in plan:
            actual = output_entries.get(item.entry.key)
            expected = IsoFile(
                item.entry.path,
                item.entry.extent,
                item.size,
                item.entry.record_offset,
            )
            if actual != expected:
                raise ValueError(f"rebuilt ISO record differs: {item.relative}")
            if item.changed and output_iso.read_file(actual) != item.path.read_bytes():
                raise ValueError(f"rebuilt file differs from input: {item.relative}")
        for sector in sorted(raw_changed):
            if sector < 0:
                raise ValueError(f"raw pregap sector changed: {sector}")
            if not track.checksums_valid(sector):
                raise ValueError(f"invalid Mode 1 EDC/ECC at logical sector {sector}")

    return RepackResult(
        len(plan),
        sum(item.changed for item in plan),
        len(raw_changed),
        len(raw_changed),
        output_cue,
    )


def _publish_directory(staging: Path, output: Path, *, overwrite: bool) -> None:
    output = output.resolve()
    if output.is_symlink() or (output.exists() and not output.is_dir()):
        raise ValueError(f"build destination is not a real directory: {output}")
    populated = output.is_dir() and any(output.iterdir())
    if populated and not overwrite:
        raise ValueError(
            f"build destination is not empty: {output}; pass --overwrite to replace it"
        )

    backup: Path | None = None
    if output.exists():
        if populated:
            backup = output.with_name(f".{output.name}.backup-{uuid.uuid4().hex}")
            os.replace(output, backup)
        else:
            output.rmdir()
    try:
        os.replace(staging, output)
    except BaseException:
        if backup is not None and not output.exists():
            os.replace(backup, output)
        raise
    if backup is not None:
        shutil.rmtree(backup)


def repack_disc(
    validated: ValidatedDisc,
    extracted: Path,
    output: Path,
    *,
    overwrite: bool = False,
) -> RepackResult:
    plan = plan_repack(validated, extracted)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{validated.spec.disc_id}-repack-", dir=output.parent)
    )
    staging.rmdir()
    try:
        _copy_source_disc(validated, staging)
        data_output = _output_path(staging, validated.data_track.file)
        with Mode1Track(
            data_output, validated.data_track.index(1), writable=True
        ) as track:
            for item in plan:
                if not item.changed:
                    continue
                track.write_extent(
                    item.entry.extent,
                    item.path.read_bytes(),
                    item.entry.capacity,
                )
                if item.size_changed:
                    encoded_size = struct.pack("<I", item.size) + struct.pack(
                        ">I", item.size
                    )
                    track.write(item.entry.record_offset + 10, encoded_size)
            rewritten = len(track.dirty_sectors)

        verified = verify_repack(validated, staging, plan)
        _publish_directory(staging, output, overwrite=overwrite)
        return RepackResult(
            verified.files,
            verified.changed_files,
            rewritten,
            verified.raw_changed_sectors,
            output / validated.sheet.path.name,
        )
    finally:
        if staging.is_dir():
            shutil.rmtree(staging)
