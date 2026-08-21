"""Load complete PSP font-resource definitions.

Unlike Saturn's loose raw files, a PSP logical font can span archive members or
have byte-identical mirrors.  Each definition therefore keeps the familiar
cell/atlas/mapping contract while explicitly naming its container targets.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FONT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = FONT_ROOT.parents[1]
CONFIG_ROOT = FONT_ROOT / "config"
ORIGINAL_ROOT = FONT_ROOT / "original"
ATLAS_ROOT = FONT_ROOT / "atlas"
GENERATED_ROOT = FONT_ROOT / "generated"
ASSET_FONT_ROOT = PROJECT_ROOT / "assets" / "font"
_ID_RE = re.compile(r"[a-z][a-z0-9_]*\Z")


@dataclass(frozen=True, slots=True)
class FontFormat:
    width: int
    height: int
    bpp: int
    row_stride: int
    glyph_stride: int


@dataclass(frozen=True, slots=True)
class AtlasOptions:
    columns: int
    scale: int


@dataclass(frozen=True, slots=True)
class PhysicalTarget:
    kind: str
    iso_path: str
    sha256: str
    size: int
    member_index: int | None
    offset: int


@dataclass(frozen=True, slots=True)
class FontDefinition:
    platform: str
    disc: str
    resource_id: str
    name: str
    file: str
    description: str
    confidence: str
    format: FontFormat
    atlas: AtlasOptions
    glyph_count: int
    glyphs: dict[int, str]
    replacements: dict[int, str]
    storage_kind: str
    logical_target_indices: tuple[int, ...]
    targets: tuple[PhysicalTarget, ...]
    config_path: Path
    source_font: Path | None
    source_sha256: str | None

    @property
    def stem(self) -> str:
        return self.resource_id

    @property
    def source_paths(self) -> tuple[Path, ...]:
        directory = ORIGINAL_ROOT / self.disc / self.resource_id
        return tuple(directory / f"target_{index:02d}.bin" for index in self.logical_target_indices)

    @property
    def source_path(self) -> Path:
        return self.source_paths[0]

    @property
    def generated_path(self) -> Path:
        return GENERATED_ROOT / self.disc / f"{self.resource_id}.bin"

    @property
    def metrics_path(self) -> Path:
        return GENERATED_ROOT / self.disc / f"{self.resource_id}_metrics.json"

    @property
    def original_atlas_path(self) -> Path:
        return ATLAS_ROOT / self.disc / f"{self.resource_id}_original.png"

    @property
    def modified_atlas_path(self) -> Path:
        return ATLAS_ROOT / self.disc / f"{self.resource_id}_modified.png"


def _integer(value: Any, context: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ValueError(f"{context} must be an integer >= {minimum}")
    return value


def _digest(value: Any, context: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{context} must be lowercase SHA-256 text")
    return value


def _code(value: Any, context: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{context} must be a glyph code")
    try:
        result = int(value, 0) if isinstance(value, str) else int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{context} must be a glyph code") from error
    if result < 0:
        raise ValueError(f"{context} cannot be negative")
    return result


def _mappings(document: dict[str, Any], glyph_count: int, context: str) -> tuple[dict[int, str], dict[int, str]]:
    glyphs: dict[int, str] = {}
    replacements: dict[int, str] = {}
    atlas = document.get("atlas")
    if not isinstance(atlas, dict):
        raise ValueError(f"{context}.atlas must be an object")
    groups = atlas.get("groups", {})
    if not isinstance(groups, dict):
        raise ValueError(f"{context}.atlas.groups must be an object")
    for group_name, rows in groups.items():
        if not isinstance(group_name, str) or not isinstance(rows, list):
            raise ValueError(f"{context}.atlas.groups is invalid")
        for number, row in enumerate(rows):
            row_context = f"{context}.atlas.groups.{group_name}[{number}]"
            if not isinstance(row, dict):
                raise ValueError(f"{row_context} must be an object")
            start = _code(row.get("start"), f"{row_context}.start")
            values = row.get("characters", row.get("glyphs"))
            if isinstance(values, str):
                sequence = tuple(values)
            elif isinstance(values, list) and all(isinstance(value, str) and value for value in values):
                sequence = tuple(values)
            else:
                raise ValueError(f"{row_context} needs characters or glyphs")
            for offset, value in enumerate(sequence):
                code = start + offset
                if code >= glyph_count or code in glyphs:
                    raise ValueError(f"{row_context} maps invalid or duplicate glyph {code}")
                glyphs[code] = value
    overrides = document.get("source_overrides", {})
    if not isinstance(overrides, dict):
        raise ValueError(f"{context}.source_overrides must be an object")
    for raw_code, value in overrides.items():
        code = _code(raw_code, f"{context}.source_overrides.{raw_code}")
        if code >= glyph_count or not isinstance(value, str) or not value:
            raise ValueError(f"{context}.source_overrides.{raw_code} is invalid")
        glyphs[code] = value
    editable = document.get("editable_ranges", [])
    if not isinstance(editable, list):
        raise ValueError(f"{context}.editable_ranges must be an array")
    for number, row in enumerate(editable):
        row_context = f"{context}.editable_ranges[{number}]"
        if not isinstance(row, dict) or set(row) != {"start", "characters", "source"}:
            raise ValueError(f"{row_context} must name start, characters, and source")
        start = _code(row["start"], f"{row_context}.start")
        characters = row["characters"]
        source = row["source"]
        if not isinstance(characters, str) or not characters or not isinstance(source, str) or not source:
            raise ValueError(f"{row_context} is invalid")
        for offset, character in enumerate(characters):
            code = start + offset
            if code >= glyph_count:
                raise ValueError(f"{row_context} exceeds the physical font")
            glyphs.setdefault(code, source)
            replacements[code] = character
    return glyphs, replacements


def load_definition(path: Path) -> FontDefinition:
    document = json.loads(path.read_text(encoding="utf-8"))
    context = str(path)
    if not isinstance(document, dict) or document.get("version") != 1:
        raise ValueError(f"{context}: unsupported PSP font definition")
    resource_id = document.get("id")
    if not isinstance(resource_id, str) or _ID_RE.fullmatch(resource_id) is None:
        raise ValueError(f"{context}.id is invalid")
    format_row = document.get("format")
    if not isinstance(format_row, dict):
        raise ValueError(f"{context}.format must be an object")
    font_format = FontFormat(
        *(
            _integer(format_row.get(field), f"{context}.format.{field}", minimum=1)
            for field in ("width", "height", "bpp", "row_stride", "glyph_stride")
        )
    )
    if font_format.bpp not in {1, 4, 8}:
        raise ValueError(f"{context}.format.bpp is unsupported")
    glyph_count = _integer(document.get("glyph_count"), f"{context}.glyph_count", minimum=1)
    atlas_row = document.get("atlas")
    assert isinstance(atlas_row, dict)
    atlas = AtlasOptions(
        _integer(atlas_row.get("columns"), f"{context}.atlas.columns", minimum=1),
        _integer(atlas_row.get("scale"), f"{context}.atlas.scale", minimum=1),
    )
    targets_row = document.get("targets")
    if not isinstance(targets_row, list) or not targets_row:
        raise ValueError(f"{context}.targets must be a nonempty array")
    targets = []
    for number, row in enumerate(targets_row):
        target_context = f"{context}.targets[{number}]"
        if not isinstance(row, dict) or row.get("kind") not in {"pack_member", "embedded"}:
            raise ValueError(f"{target_context} is invalid")
        kind = row["kind"]
        targets.append(
            PhysicalTarget(
                kind=kind,
                iso_path=str(row.get("iso_path", "")),
                sha256=_digest(row.get("sha256"), f"{target_context}.sha256"),
                size=_integer(row.get("size"), f"{target_context}.size", minimum=1),
                member_index=(
                    _integer(row.get("member_index"), f"{target_context}.member_index")
                    if kind == "pack_member"
                    else None
                ),
                offset=_integer(
                    row.get("offset" if kind == "pack_member" else "file_offset"),
                    f"{target_context}.offset",
                ),
            )
        )
    storage = document.get("storage")
    if not isinstance(storage, dict) or storage.get("kind") not in {"raw_tiles", "gim_pages"}:
        raise ValueError(f"{context}.storage is invalid")
    indices = storage.get("logical_target_indices")
    if not isinstance(indices, list) or not indices:
        raise ValueError(f"{context}.storage.logical_target_indices must be nonempty")
    logical_indices = tuple(_integer(value, f"{context}.storage.logical_target_indices") for value in indices)
    if len(set(logical_indices)) != len(logical_indices) or any(value >= len(targets) for value in logical_indices):
        raise ValueError(f"{context}.storage.logical_target_indices is invalid")
    glyphs, replacements = _mappings(document, glyph_count, context)
    repack = document.get("repack", {})
    if not isinstance(repack, dict):
        raise ValueError(f"{context}.repack must be an object")
    source_font = None
    source_sha256 = None
    if repack:
        source = repack.get("source")
        if not isinstance(source, str) or not source:
            raise ValueError(f"{context}.repack.source is invalid")
        source_font = ASSET_FONT_ROOT / source
        source_sha256 = _digest(repack.get("source_sha256"), f"{context}.repack.source_sha256")
    return FontDefinition(
        platform="psp",
        disc="game",
        resource_id=resource_id,
        name=str(document.get("name", resource_id)),
        file=str(document.get("file", resource_id)),
        description=str(document.get("description", "")),
        confidence=str(document.get("confidence", "unresolved")),
        format=font_format,
        atlas=atlas,
        glyph_count=glyph_count,
        glyphs=glyphs,
        replacements=replacements,
        storage_kind=storage["kind"],
        logical_target_indices=logical_indices,
        targets=tuple(targets),
        config_path=path,
        source_font=source_font,
        source_sha256=source_sha256,
    )


def load_definitions() -> tuple[FontDefinition, ...]:
    definitions = tuple(load_definition(path) for path in sorted(CONFIG_ROOT.glob("*/*.json")))
    ids = [definition.resource_id for definition in definitions]
    if len(ids) != len(set(ids)):
        raise ValueError("PSP font definitions contain duplicate ids")
    return definitions

