"""Small, strict parser for the FILE/TRACK/INDEX portion of CUE sheets."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .paths import contained_path, safe_relative_path

_FILE = re.compile(r'^\s*FILE\s+(?:"([^"]+)"|(\S+))\s+(\S+)\s*$', re.IGNORECASE)
_TRACK = re.compile(r"^\s*TRACK\s+(\d+)\s+(\S+)\s*$", re.IGNORECASE)
_INDEX = re.compile(r"^\s*INDEX\s+(\d+)\s+(\d+):(\d+):(\d+)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class CueFile:
    name: str
    file_type: str

    @property
    def relative_path(self) -> Path:
        return safe_relative_path(self.name, "CUE FILE path")


@dataclass(frozen=True)
class CueTrack:
    number: int
    mode: str
    file: CueFile
    indexes: tuple[tuple[int, int], ...]

    def index(self, number: int) -> int:
        for index_number, frame in self.indexes:
            if index_number == number:
                return frame
        raise ValueError(f"track {self.number:02d} has no INDEX {number:02d}")


@dataclass
class _TrackBuilder:
    number: int
    mode: str
    file: CueFile
    indexes: dict[int, int] = field(default_factory=dict)


@dataclass(frozen=True)
class CueSheet:
    path: Path
    files: tuple[CueFile, ...]
    tracks: tuple[CueTrack, ...]

    @classmethod
    def read(cls, path: Path) -> "CueSheet":
        path = path.resolve()
        current_file: CueFile | None = None
        files: list[CueFile] = []
        tracks: list[_TrackBuilder] = []

        for line_number, line in enumerate(
            path.read_text(encoding="utf-8-sig").splitlines(), start=1
        ):
            if match := _FILE.match(line):
                current_file = CueFile(
                    match.group(1) or match.group(2), match.group(3).upper()
                )
                current_file.relative_path
                files.append(current_file)
                continue

            if match := _TRACK.match(line):
                if current_file is None:
                    raise ValueError(
                        f"{path.name}:{line_number}: TRACK appears before FILE"
                    )
                number = int(match.group(1))
                if any(track.number == number for track in tracks):
                    raise ValueError(
                        f"{path.name}:{line_number}: duplicate track {number:02d}"
                    )
                tracks.append(
                    _TrackBuilder(number, match.group(2).upper(), current_file)
                )
                continue

            if match := _INDEX.match(line):
                if not tracks:
                    raise ValueError(
                        f"{path.name}:{line_number}: INDEX appears before TRACK"
                    )
                index_number, minutes, seconds, frames = map(int, match.groups())
                if seconds >= 60 or frames >= 75:
                    raise ValueError(
                        f"{path.name}:{line_number}: invalid INDEX timestamp"
                    )
                if index_number in tracks[-1].indexes:
                    raise ValueError(
                        f"{path.name}:{line_number}: duplicate INDEX {index_number:02d}"
                    )
                tracks[-1].indexes[index_number] = (
                    minutes * 60 + seconds
                ) * 75 + frames

        if not files or not tracks:
            raise ValueError(f"{path.name}: no FILE/TRACK records found")
        if any(1 not in track.indexes for track in tracks):
            missing = [track.number for track in tracks if 1 not in track.indexes]
            raise ValueError(f"{path.name}: tracks without INDEX 01: {missing}")

        referenced = {id(track.file) for track in tracks}
        unused = [cue_file.name for cue_file in files if id(cue_file) not in referenced]
        if unused:
            raise ValueError(f"{path.name}: unreferenced FILE records: {unused}")

        frozen_tracks = tuple(
            CueTrack(
                track.number,
                track.mode,
                track.file,
                tuple(sorted(track.indexes.items())),
            )
            for track in tracks
        )
        return cls(path, tuple(files), frozen_tracks)

    def source_path(self, cue_file: CueFile) -> Path:
        return contained_path(self.path.parent, cue_file.relative_path, "CUE FILE path")

    def data_track(self) -> CueTrack:
        matches = [track for track in self.tracks if track.mode == "MODE1/2352"]
        if len(matches) != 1:
            raise ValueError(
                f"{self.path.name}: expected one MODE1/2352 track, found {len(matches)}"
            )
        return matches[0]
