"""Load the Saturn text consumer geometry catalog."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

TEXT_ROOT = Path(__file__).resolve().parent.parent
SURFACES_PATH = TEXT_ROOT / "config" / "surfaces.json"
FONT_CONFIG_ROOT = TEXT_ROOT.parent / "font" / "config" / "game"

_SURFACE_RE = re.compile(
    r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+\Z"
)
_FONT_RE = re.compile(r"[a-z][a-z0-9_]*\Z")
_WIDTH_UNITS = frozenset({"glyph_cells", "pixels"})


@dataclass(frozen=True)
class WidthLimit:
    unit: str | None
    value: int | None

    @property
    def known(self) -> bool:
        return self.value is not None


@dataclass(frozen=True)
class LayoutLimit:
    font: str | None
    rows: int | None
    width: WidthLimit
    glyphs: int | None


@dataclass(frozen=True)
class SurfaceSpec:
    name: str
    ja: LayoutLimit
    en: LayoutLimit


@dataclass(frozen=True)
class SurfaceCatalog:
    surfaces: Mapping[str, SurfaceSpec]

    def surface(self, name: str) -> SurfaceSpec:
        try:
            return self.surfaces[name]
        except KeyError as error:
            choices = ", ".join(self.surfaces)
            raise ValueError(
                f"unknown text surface {name!r}; choose from {choices}"
            ) from error


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field {key!r}")
        result[key] = value
    return result


def _read_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except FileNotFoundError as error:
        raise ValueError(f"missing configuration file: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: invalid JSON: {error.msg}") from error


def _object(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return value


def _fields(row: dict[str, Any], expected: set[str], context: str) -> None:
    if set(row) != expected:
        raise ValueError(
            f"{context} fields are {sorted(row)}, expected {sorted(expected)}"
        )


def _positive_or_unknown(value: Any, context: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value <= 0:
        raise ValueError(f"{context} must be a positive integer or null")
    return value


def _load_width(value: Any, context: str) -> WidthLimit:
    row = _object(value, context)
    _fields(row, {"unit", "value"}, context)
    unit = row["unit"]
    width = _positive_or_unknown(row["value"], f"{context}.value")
    if unit is None and width is None:
        return WidthLimit(None, None)
    if unit not in _WIDTH_UNITS:
        choices = ", ".join(sorted(_WIDTH_UNITS))
        raise ValueError(f"{context}.unit must be one of {choices}, or null")
    if width is None:
        raise ValueError(f"{context}.unit and value must both be known or null")
    return WidthLimit(unit, width)


def _load_layout(
    value: Any,
    context: str,
    font_config_root: Path,
) -> LayoutLimit:
    row = _object(value, context)
    required = {"font", "rows", "width"}
    if not required <= set(row) or not set(row) <= required | {"glyphs"}:
        raise ValueError(
            f"{context} fields are {sorted(row)}, expected {sorted(required)} "
            "with optional 'glyphs'"
        )
    font = row["font"]
    if font is not None:
        if not isinstance(font, str) or _FONT_RE.fullmatch(font) is None:
            raise ValueError(f"{context}.font must be a font identifier or null")
        if not (font_config_root / f"{font}.json").is_file():
            raise ValueError(f"{context}.font names unknown Saturn font {font!r}")
    return LayoutLimit(
        font,
        _positive_or_unknown(row["rows"], f"{context}.rows"),
        _load_width(row["width"], f"{context}.width"),
        _positive_or_unknown(row.get("glyphs"), f"{context}.glyphs"),
    )


def load_surfaces(
    path: Path = SURFACES_PATH,
    *,
    font_config_root: Path = FONT_CONFIG_ROOT,
) -> SurfaceCatalog:
    document = _object(_read_json(path), str(path))
    _fields(document, {"version", "surfaces"}, str(path))
    if type(document["version"]) is not int or document["version"] != 1:
        raise ValueError(f"{path}: unsupported surface catalog version")

    rows = _object(document["surfaces"], f"{path}.surfaces")
    if not rows:
        raise ValueError(f"{path}.surfaces must not be empty")
    surfaces: dict[str, SurfaceSpec] = {}
    for name, raw_surface in rows.items():
        if not isinstance(name, str) or _SURFACE_RE.fullmatch(name) is None:
            raise ValueError(
                f"{path}.surfaces name must be a dotted lowercase identifier"
            )
        context = f"{path}.surfaces.{name}"
        surface = _object(raw_surface, context)
        _fields(surface, {"ja", "en"}, context)
        surfaces[name] = SurfaceSpec(
            name,
            _load_layout(surface["ja"], f"{context}.ja", font_config_root),
            _load_layout(surface["en"], f"{context}.en", font_config_root),
        )
    return SurfaceCatalog(MappingProxyType(surfaces))
