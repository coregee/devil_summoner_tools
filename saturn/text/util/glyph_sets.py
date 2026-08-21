"""Load explicit output selections for stable named glyph sets."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .surfaces import load_surfaces


TEXT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = TEXT_ROOT / "config" / "glyph_sets.json"
FONT_CONFIG_ROOT = TEXT_ROOT.parent / "font" / "config" / "game"
_IDENTIFIER_RE = re.compile(r"[a-z][a-z0-9_]*\Z")


@dataclass(frozen=True, slots=True)
class GlyphSetHandler:
    name: str
    font: str
    reference_set: str


@dataclass(frozen=True, slots=True)
class GlyphSetCatalog:
    handlers: Mapping[str, GlyphSetHandler]
    surface_handlers: Mapping[str, GlyphSetHandler]

    def for_surface(self, surface: str) -> GlyphSetHandler | None:
        return self.surface_handlers.get(surface)


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
        raise ValueError(f"missing configuration file: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: invalid JSON: {error.msg}") from error


def _object(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return value


def _fields(value: Mapping[str, Any], expected: set[str], context: str) -> None:
    if set(value) != expected:
        raise ValueError(
            f"{context} fields are {sorted(value)}, expected {sorted(expected)}"
        )


def _identifier(value: Any, context: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        raise ValueError(f"{context} must be a lowercase identifier")
    return value


def load_glyph_sets(
    path: Path = CONFIG_PATH,
    *,
    font_config_root: Path = FONT_CONFIG_ROOT,
) -> GlyphSetCatalog:
    document = _object(_read_json(path), str(path))
    _fields(
        document,
        {"version", "handlers", "surface_handlers"},
        str(path),
    )
    if type(document["version"]) is not int or document["version"] != 1:
        raise ValueError(f"{path}.version must be 1")

    handlers: dict[str, GlyphSetHandler] = {}
    font_documents: dict[str, dict[str, Any]] = {}
    for raw_name, raw_handler in _object(
        document["handlers"], f"{path}.handlers"
    ).items():
        name = _identifier(raw_name, f"{path}.handlers key")
        handler = _object(raw_handler, f"{path}.handlers.{name}")
        _fields(handler, {"font", "reference_set"}, f"{path}.handlers.{name}")
        font = _identifier(handler["font"], f"{path}.handlers.{name}.font")
        reference_set = _identifier(
            handler["reference_set"],
            f"{path}.handlers.{name}.reference_set",
        )
        if font not in font_documents:
            font_documents[font] = _object(
                _read_json(font_config_root / f"{font}.json"),
                f"font config {font}",
            )
        reference_sets = _object(
            font_documents[font].get("reference_sets", {}),
            f"font config {font}.reference_sets",
        )
        if reference_set not in reference_sets:
            raise ValueError(
                f"{path}.handlers.{name} names unknown {font} reference set "
                f"{reference_set!r}"
            )
        handlers[name] = GlyphSetHandler(name, font, reference_set)
    if not handlers:
        raise ValueError(f"{path}.handlers must not be empty")

    surfaces = load_surfaces()
    surface_handlers: dict[str, GlyphSetHandler] = {}
    for surface, raw_handler_name in _object(
        document["surface_handlers"], f"{path}.surface_handlers"
    ).items():
        surface_spec = surfaces.surface(surface)
        handler_name = _identifier(
            raw_handler_name, f"{path}.surface_handlers.{surface}"
        )
        try:
            handler = handlers[handler_name]
        except KeyError as error:
            raise ValueError(
                f"{path}.surface_handlers.{surface} names unknown handler "
                f"{handler_name!r}"
            ) from error
        if surface_spec.en.font != handler.font:
            raise ValueError(
                f"{path}.surface_handlers.{surface} uses {handler.font}, but the "
                f"English surface uses {surface_spec.en.font}"
            )
        surface_handlers[surface] = handler
    if set(handlers) != {handler.name for handler in surface_handlers.values()}:
        raise ValueError(f"{path} contains an unused glyph-set handler")

    return GlyphSetCatalog(
        MappingProxyType(handlers),
        MappingProxyType(surface_handlers),
    )
