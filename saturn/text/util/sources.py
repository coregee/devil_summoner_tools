"""Load the small, disc-local inventory of physical text sources."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any

TEXT_ROOT = Path(__file__).resolve().parent.parent
SOURCES_ROOT = TEXT_ROOT / "config" / "sources"

_ID_RE = re.compile(r"[a-z][a-z0-9_]*\Z")
_HASH_RE = re.compile(r"[0-9a-f]{64}\Z")
_CONTAINER_TYPES = frozenset({"eve", "pointer_bank", "fixed_records", "addressed"})


@dataclass(frozen=True, slots=True)
class FileSpec:
    name: str
    path: PurePosixPath
    size: int
    stock_sha256: str
    owned_sha256: str | None


@dataclass(frozen=True, slots=True)
class SourceSpec:
    name: str
    corpus_path: PurePosixPath
    container: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class SourceManifest:
    disc: str
    track_sha256: str
    files: Mapping[str, FileSpec]
    sources: tuple[SourceSpec, ...]


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON field {key!r}")
        output[key] = value
    return output


def _read_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except FileNotFoundError as error:
        raise ValueError(f"missing source manifest: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: invalid JSON: {error.msg}") from error


def _object(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return value


def _fields(
    value: Mapping[str, Any],
    required: set[str],
    context: str,
    *,
    optional: set[str] = frozenset(),
) -> None:
    actual = set(value)
    if not required <= actual or not actual <= required | optional:
        expected = sorted(required | optional)
        raise ValueError(f"{context} fields are {sorted(actual)}, expected {expected}")


def _identifier(value: Any, context: str) -> str:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise ValueError(f"{context} must be a lowercase identifier")
    return value


def _hash(value: Any, context: str) -> str:
    if not isinstance(value, str) or _HASH_RE.fullmatch(value) is None:
        raise ValueError(f"{context} must be a lowercase SHA-256 digest")
    return value


def _relative_path(
    value: Any, context: str, *, suffix: str | None = None
) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"{context} must be a nonempty POSIX relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{context} is not a safe relative path")
    if suffix is not None and path.suffix != suffix:
        raise ValueError(f"{context} must end in {suffix}")
    return path


def load_manifest(path: Path) -> SourceManifest:
    document = _object(_read_json(path), str(path))
    _fields(
        document,
        {"version", "disc", "track_sha256", "files", "sources"},
        str(path),
    )
    if type(document["version"]) is not int or document["version"] != 1:
        raise ValueError(f"{path}: unsupported source-manifest version")
    disc = _identifier(document["disc"], f"{path}.disc")
    track_sha256 = _hash(document["track_sha256"], f"{path}.track_sha256")

    raw_files = _object(document["files"], f"{path}.files")
    if not raw_files:
        raise ValueError(f"{path}.files must not be empty")
    files: dict[str, FileSpec] = {}
    seen_paths: set[str] = set()
    for raw_name, raw_file in raw_files.items():
        name = _identifier(raw_name, f"{path}.files name")
        row = _object(raw_file, f"{path}.files.{name}")
        _fields(
            row,
            {"path", "size", "stock_sha256"},
            f"{path}.files.{name}",
            optional={"owned_sha256"},
        )
        file_path = _relative_path(row["path"], f"{path}.files.{name}.path")
        folded_path = file_path.as_posix().casefold()
        if folded_path in seen_paths:
            raise ValueError(f"{path}.files repeats physical path {file_path}")
        seen_paths.add(folded_path)
        size = row["size"]
        if type(size) is not int or size <= 0:
            raise ValueError(f"{path}.files.{name}.size must be positive")
        owned = row.get("owned_sha256")
        files[name] = FileSpec(
            name,
            file_path,
            size,
            _hash(row["stock_sha256"], f"{path}.files.{name}.stock_sha256"),
            (
                _hash(owned, f"{path}.files.{name}.owned_sha256")
                if owned is not None
                else None
            ),
        )

    raw_sources = document["sources"]
    if not isinstance(raw_sources, list) or not raw_sources:
        raise ValueError(f"{path}.sources must be a nonempty array")
    sources: list[SourceSpec] = []
    source_names: set[str] = set()
    corpus_paths: set[str] = set()
    for index, raw_source in enumerate(raw_sources):
        context = f"{path}.sources[{index}]"
        row = _object(raw_source, context)
        _fields(row, {"id", "corpus", "container"}, context)
        name = _identifier(row["id"], f"{context}.id")
        if name in source_names:
            raise ValueError(f"{path}: duplicate source id {name!r}")
        source_names.add(name)
        corpus_path = _relative_path(row["corpus"], f"{context}.corpus", suffix=".json")
        folded_corpus_path = corpus_path.as_posix().casefold()
        if folded_corpus_path in corpus_paths:
            raise ValueError(f"{path}: duplicate corpus path {corpus_path}")
        corpus_paths.add(folded_corpus_path)
        container = _object(row["container"], f"{context}.container")
        kind = container.get("type")
        if kind not in _CONTAINER_TYPES:
            choices = ", ".join(sorted(_CONTAINER_TYPES))
            raise ValueError(f"{context}.container.type must be one of {choices}")
        sources.append(SourceSpec(name, corpus_path, MappingProxyType(dict(container))))

    return SourceManifest(
        disc,
        track_sha256,
        MappingProxyType(files),
        tuple(sources),
    )


def manifest_path(disc: str) -> Path:
    name = _identifier(disc, "disc")
    return SOURCES_ROOT / name / "manifest.json"
