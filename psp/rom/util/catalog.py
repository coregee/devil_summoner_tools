"""Strict source and output catalogue for supported PSP images."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


ROM_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROM_ROOT / "discs.json"
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True, slots=True)
class EntryContract:
    id: str
    path: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class DiscContract:
    id: str
    source_filename: str
    source_size: int
    source_sha256: str
    output_filename: str
    entries: dict[str, EntryContract]

    @property
    def source_path(self) -> Path:
        return ROM_ROOT / "original" / self.source_filename

    @property
    def output_path(self) -> Path:
        return ROM_ROOT / "build" / self.id / self.output_filename

    @property
    def manifest_path(self) -> Path:
        return self.output_path.with_suffix(self.output_path.suffix + ".json")


def _filename(value: object, context: str, suffix: str) -> str:
    if not isinstance(value, str) or not value or Path(value).name != value:
        raise ValueError(f"{context} must be one filename")
    if not value.casefold().endswith(suffix):
        raise ValueError(f"{context} must end in {suffix}")
    return value


def _digest(value: object, context: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise ValueError(f"{context} must be a lowercase SHA-256 digest")
    return value


def _size(value: object, context: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{context} must be a positive integer")
    return value


def _entry_path(value: object, context: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"{context} must be a relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{context} contains an unsafe component")
    return path.as_posix()


def load_catalog(path: Path = CATALOG_PATH) -> dict[str, DiscContract]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP disc catalogue: {path}") from error
    if (
        not isinstance(document, dict)
        or set(document) != {"version", "discs"}
        or document["version"] != 1
        or not isinstance(document["discs"], dict)
        or not document["discs"]
    ):
        raise ValueError(f"{path}: unsupported PSP disc catalogue")
    output: dict[str, DiscContract] = {}
    for disc_id, raw_disc in document["discs"].items():
        context = f"{path}.discs.{disc_id}"
        if (
            not isinstance(disc_id, str)
            or not disc_id
            or not isinstance(raw_disc, dict)
            or set(raw_disc) != {"source", "output", "entries"}
        ):
            raise ValueError(f"{context}: invalid disc")
        source, published, raw_entries = (
            raw_disc["source"],
            raw_disc["output"],
            raw_disc["entries"],
        )
        if (
            not isinstance(source, dict)
            or set(source) != {"filename", "size", "sha256"}
            or not isinstance(published, dict)
            or set(published) != {"filename"}
            or not isinstance(raw_entries, dict)
            or not raw_entries
        ):
            raise ValueError(f"{context}: invalid source, output, or entries")
        entries: dict[str, EntryContract] = {}
        paths: set[str] = set()
        for entry_id, raw_entry in raw_entries.items():
            entry_context = f"{context}.entries.{entry_id}"
            if (
                not isinstance(entry_id, str)
                or not entry_id
                or not isinstance(raw_entry, dict)
                or set(raw_entry) != {"path", "size", "sha256"}
            ):
                raise ValueError(f"{entry_context}: invalid entry")
            entry_path = _entry_path(raw_entry["path"], f"{entry_context}.path")
            if entry_path.casefold() in paths:
                raise ValueError(f"{context}: duplicate entry path")
            paths.add(entry_path.casefold())
            entries[entry_id] = EntryContract(
                entry_id,
                entry_path,
                _size(raw_entry["size"], f"{entry_context}.size"),
                _digest(raw_entry["sha256"], f"{entry_context}.sha256"),
            )
        output[disc_id] = DiscContract(
            disc_id,
            _filename(source["filename"], f"{context}.source.filename", ".iso"),
            _size(source["size"], f"{context}.source.size"),
            _digest(source["sha256"], f"{context}.source.sha256"),
            _filename(published["filename"], f"{context}.output.filename", ".iso"),
            entries,
        )
    return output


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_source(disc: DiscContract, *, verify_hash: bool = True) -> Path:
    path = disc.source_path
    if not path.is_file():
        raise ValueError(f"PSP source ISO is missing: {path}")
    if path.stat().st_size != disc.source_size:
        raise ValueError(
            f"PSP source ISO size is {path.stat().st_size}; expected {disc.source_size}"
        )
    if verify_hash:
        digest = file_sha256(path)
        if digest != disc.source_sha256:
            raise ValueError(
                f"PSP source ISO SHA-256 is {digest}; expected {disc.source_sha256}"
            )
    return path

