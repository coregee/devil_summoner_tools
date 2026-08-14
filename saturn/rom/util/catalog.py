"""Load the exact source-disc contracts for the game and compendium."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cue import CueSheet, CueTrack
from .paths import safe_relative_path

ROM_ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROM_ROOT / "discs.json"
ORIGINAL_ROOT = ROM_ROOT / "original"
EXTRACTED_ROOT = ROM_ROOT / "extracted"
BUILD_ROOT = ROM_ROOT / "build"


@dataclass(frozen=True)
class TrackSpec:
    number: int
    file: str
    file_type: str
    mode: str
    indexes: tuple[tuple[int, int], ...]
    size: int
    sha256: str


@dataclass(frozen=True)
class DiscSpec:
    disc_id: str
    title: str
    cue: str
    tracks: tuple[TrackSpec, ...]

    @property
    def cue_path(self) -> Path:
        return ORIGINAL_ROOT / safe_relative_path(self.cue, f"{self.disc_id}.cue")

    @property
    def extracted_path(self) -> Path:
        return EXTRACTED_ROOT / self.disc_id

    @property
    def build_path(self) -> Path:
        return BUILD_ROOT / self.disc_id


@dataclass(frozen=True)
class ValidatedDisc:
    spec: DiscSpec
    sheet: CueSheet
    data_track: CueTrack


def _object(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return value


def _keys(value: dict[str, Any], expected: set[str], context: str) -> None:
    if set(value) != expected:
        raise ValueError(
            f"{context} fields are {sorted(value)}, expected {sorted(expected)}"
        )


def _text(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context} must be nonempty text")
    return value


def _integer(value: Any, context: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ValueError(f"{context} must be an integer >= {minimum}")
    return value


def _track(value: Any, context: str) -> TrackSpec:
    row = _object(value, context)
    _keys(
        row,
        {"number", "file", "file_type", "mode", "indexes", "size", "sha256"},
        context,
    )
    indexes_value = _object(row["indexes"], f"{context}.indexes")
    indexes: list[tuple[int, int]] = []
    for key, frame in indexes_value.items():
        if not isinstance(key, str) or not key.isdecimal():
            raise ValueError(f"{context}.indexes keys must be decimal strings")
        indexes.append((int(key), _integer(frame, f"{context}.indexes[{key}]")))
    if not any(number == 1 for number, _ in indexes):
        raise ValueError(f"{context} must declare INDEX 01")

    digest = _text(row["sha256"], f"{context}.sha256")
    if (
        len(digest) != 64
        or digest != digest.lower()
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError(f"{context}.sha256 must be lowercase SHA-256")

    filename = _text(row["file"], f"{context}.file")
    safe_relative_path(filename, f"{context}.file")
    return TrackSpec(
        _integer(row["number"], f"{context}.number", minimum=1),
        filename,
        _text(row["file_type"], f"{context}.file_type").upper(),
        _text(row["mode"], f"{context}.mode").upper(),
        tuple(sorted(indexes)),
        _integer(row["size"], f"{context}.size", minimum=1),
        digest,
    )


def load_catalog(path: Path = CATALOG_PATH) -> dict[str, DiscSpec]:
    document = _object(json.loads(path.read_text(encoding="utf-8")), str(path))
    _keys(document, {"version", "discs"}, str(path))
    if document["version"] != 1:
        raise ValueError(f"{path}: unsupported catalog version")

    discs_value = _object(document["discs"], f"{path}.discs")
    result: dict[str, DiscSpec] = {}
    for disc_id, value in discs_value.items():
        if not isinstance(disc_id, str) or not disc_id or not disc_id.isidentifier():
            raise ValueError(f"{path}: invalid disc id {disc_id!r}")
        row = _object(value, f"{path}.{disc_id}")
        _keys(row, {"title", "cue", "tracks"}, f"{path}.{disc_id}")
        cue = _text(row["cue"], f"{path}.{disc_id}.cue")
        if len(safe_relative_path(cue, f"{path}.{disc_id}.cue").parts) != 1:
            raise ValueError(f"{path}.{disc_id}.cue must be directly under original/")
        track_rows = row["tracks"]
        if not isinstance(track_rows, list) or not track_rows:
            raise ValueError(f"{path}.{disc_id}.tracks must be a nonempty list")
        tracks = tuple(
            _track(item, f"{path}.{disc_id}.tracks[{index}]")
            for index, item in enumerate(track_rows)
        )
        numbers = [track.number for track in tracks]
        if len(numbers) != len(set(numbers)):
            raise ValueError(f"{path}.{disc_id}: duplicate track number")
        if sum(track.mode == "MODE1/2352" for track in tracks) != 1:
            raise ValueError(f"{path}.{disc_id}: expected one MODE1/2352 track")
        result[disc_id] = DiscSpec(
            disc_id,
            _text(row["title"], f"{path}.{disc_id}.title"),
            cue,
            tracks,
        )
    if not result:
        raise ValueError(f"{path}: no discs configured")
    return result


def select_discs(names: list[str], catalog: dict[str, DiscSpec]) -> list[DiscSpec]:
    requested = names or ["all"]
    if "all" in requested:
        if len(requested) != 1:
            raise ValueError("'all' cannot be combined with individual disc names")
        return list(catalog.values())

    unknown = [name for name in requested if name not in catalog]
    if unknown:
        raise ValueError(
            f"unknown disc(s): {', '.join(unknown)}; choose from "
            f"{', '.join(catalog)} or all"
        )
    if len(requested) != len(set(requested)):
        raise ValueError("the same disc was selected more than once")
    return [catalog[name] for name in requested]


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_source(spec: DiscSpec, *, verify_hashes: bool = True) -> ValidatedDisc:
    cue_path = spec.cue_path.resolve()
    if not cue_path.is_file():
        raise ValueError(f"{spec.disc_id}: source CUE is missing: {cue_path}")
    sheet = CueSheet.read(cue_path)
    by_number = {track.number: track for track in sheet.tracks}
    expected_numbers = {track.number for track in spec.tracks}
    if set(by_number) != expected_numbers:
        raise ValueError(
            f"{spec.disc_id}: CUE tracks are {sorted(by_number)}, "
            f"expected {sorted(expected_numbers)}"
        )

    hashes: dict[Path, str] = {}
    for expected in spec.tracks:
        actual = by_number[expected.number]
        label = f"{spec.disc_id} track {expected.number:02d}"
        if actual.file.name.casefold() != expected.file.casefold():
            raise ValueError(
                f"{label}: CUE names {actual.file.name!r}, expected {expected.file!r}"
            )
        if actual.file.file_type != expected.file_type:
            raise ValueError(
                f"{label}: file type is {actual.file.file_type}, "
                f"expected {expected.file_type}"
            )
        if actual.mode != expected.mode:
            raise ValueError(
                f"{label}: mode is {actual.mode}, expected {expected.mode}"
            )
        if actual.indexes != expected.indexes:
            raise ValueError(
                f"{label}: indexes are {dict(actual.indexes)}, "
                f"expected {dict(expected.indexes)}"
            )

        source = sheet.source_path(actual.file)
        if not source.is_file():
            raise ValueError(f"{label}: source track is missing: {source}")
        actual_size = source.stat().st_size
        if actual_size != expected.size:
            raise ValueError(
                f"{label}: size is {actual_size:,}, expected {expected.size:,}"
            )
        if actual_size % 2352:
            raise ValueError(f"{label}: raw track is not a whole number of sectors")
        if verify_hashes:
            digest = hashes.get(source)
            if digest is None:
                digest = file_sha256(source)
                hashes[source] = digest
            if digest != expected.sha256:
                raise ValueError(
                    f"{label}: SHA-256 is {digest}, expected {expected.sha256}"
                )

    return ValidatedDisc(spec, sheet, sheet.data_track())
