"""Read-only raster inventory and editable source mappings for PSP fonts."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any

from PIL import Image

from psp.font.util.codec import decode_glyph, load_cell_data
from psp.font.util.definitions import (
    ASSET_FONT_ROOT,
    FontDefinition,
    load_definition,
    load_definitions,
)

from .languages import LanguageService

_SOURCE_TOKEN_RE = re.compile(r"\{[a-z][a-z0-9_]*\}\Z")


def _font_id(definition: FontDefinition) -> str:
    return f"psp/{definition.resource_id}"


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PspFontService:
    """Expose PSP resources without granting unproved raster ownership."""

    def __init__(self, languages: LanguageService) -> None:
        self.languages = languages
        self._lock = threading.RLock()
        self._suggestion_cache: dict[tuple[str, str, str], dict[int, str]] = {}

    @staticmethod
    def _definitions() -> dict[str, FontDefinition]:
        return {_font_id(definition): definition for definition in load_definitions()}

    def _definition(self, font_id: str) -> FontDefinition:
        if not font_id.startswith("psp/"):
            raise ValueError("invalid PSP font id")
        try:
            return self._definitions()[font_id]
        except KeyError as error:
            raise ValueError("unknown PSP font") from error

    @staticmethod
    def _data(definition: FontDefinition) -> bytes | None:
        try:
            return load_cell_data(definition)
        except (OSError, ValueError):
            return None

    @staticmethod
    def _glyph_data_url(glyph: Image.Image) -> str:
        alpha = glyph.point(lambda value: 255 if value else 0)
        image = Image.new("RGBA", glyph.size, (234, 242, 231, 0))
        image.putalpha(alpha)
        scale = max(1, 64 // max(glyph.size))
        image = image.resize(
            (image.width * scale, image.height * scale), Image.Resampling.NEAREST
        )
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        return "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode("ascii")

    @staticmethod
    def _data_url(path: Path) -> str | None:
        if not path.is_file():
            return None
        return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")

    def _suggestions(
        self, definition: FontDefinition, data: bytes | None
    ) -> dict[int, str]:
        if data is None:
            return {}
        mapping_hash = hashlib.sha256(
            repr(sorted(definition.glyphs.items())).encode("utf-8")
        ).hexdigest()
        key = (
            definition.resource_id,
            hashlib.sha256(data).hexdigest(),
            mapping_hash,
        )
        if key in self._suggestion_cache:
            return self._suggestion_cache[key]
        matches: dict[bytes, set[str]] = {}
        for code, value in definition.glyphs.items():
            if code in definition.replacements:
                continue
            bitmap = decode_glyph(data, definition, code).tobytes()
            matches.setdefault(bitmap, set()).add(value)
        suggestions = {}
        for code in range(definition.glyph_count):
            if code in definition.glyphs:
                continue
            bitmap = decode_glyph(data, definition, code).tobytes()
            if not any(bitmap):
                suggestions[code] = " "
            elif len(matches.get(bitmap, ())) == 1:
                suggestions[code] = next(iter(matches[bitmap]))
        self._suggestion_cache[key] = suggestions
        return suggestions

    def inventory(self, language_id: str = "en") -> dict[str, Any]:
        self.languages.detail(language_id)
        rows = []
        for definition in self._definitions().values():
            # Inventory loading must stay cheap even for the 7,808-cell EVE
            # atlas. Exact bitmap suggestions are calculated lazily when the
            # user opens an individual resource.
            suggested = 0
            available = all(path.is_file() for path in definition.source_paths)
            rows.append(
                {
                    "id": _font_id(definition),
                    "platform": "psp",
                    "disc": "PSP",
                    "name": definition.name,
                    "file": definition.file,
                    "cell": {
                        "width": definition.format.width,
                        "height": definition.format.height,
                        "bpp": definition.format.bpp,
                    },
                    "editable_slots": len(definition.replacements),
                    "physical_slots": definition.glyph_count,
                    "known_slots": len(definition.glyphs),
                    "suggested_slots": suggested,
                    "unknown_slots": definition.glyph_count
                    - len(definition.glyphs)
                    - suggested,
                    "surface_count": 0,
                    "source": (
                        definition.source_font.relative_to(ASSET_FONT_ROOT).as_posix()
                        if definition.source_font is not None
                        else None
                    ),
                    "generated": False,
                    "customized": False,
                    "confidence": definition.confidence,
                    "available": available,
                }
            )
        return {"fonts": rows, "language": language_id}

    def detail(
        self,
        font_id: str,
        language_id: str = "en",
        *,
        offset: int = 0,
        limit: int = 200,
        query: str = "",
    ) -> dict[str, Any]:
        if offset < 0 or not 1 <= limit <= 300:
            raise ValueError("invalid glyph page")
        self.languages.detail(language_id)
        definition = self._definition(font_id)
        data = self._data(definition)
        suggestions = self._suggestions(definition, data)
        needle = query.strip().casefold()
        matching = []
        for code in range(definition.glyph_count):
            source = definition.glyphs.get(code)
            suggestion = suggestions.get(code)
            replacement = definition.replacements.get(code)
            searchable = " ".join(
                value
                for value in (str(code), f"0x{code:04X}", source, suggestion, replacement)
                if value is not None
            ).casefold()
            if not needle or needle in searchable:
                matching.append(code)
        slots = []
        for code in matching[offset : offset + limit]:
            defined = definition.glyphs.get(code)
            suggested = suggestions.get(code)
            source = defined or suggested
            status = "defined" if defined is not None else "suggested" if suggested is not None else "unknown"
            image = (
                self._glyph_data_url(decode_glyph(data, definition, code))
                if data is not None
                else None
            )
            slots.append(
                {
                    "code": code,
                    "code_label": f"0x{code:04X}",
                    "original": source,
                    "source_value": source,
                    "source_status": status,
                    "can_edit_source": True,
                    "replacement": definition.replacements.get(code),
                    # The source project proved the EVE bank, but its guarded
                    # archive publisher has not yet been ported into this repo.
                    "can_edit_render": False,
                    "usage": 0,
                    "original_image": image,
                    "modified_image": image,
                    "image": image,
                }
            )
        suggested_count = len(set(suggestions) - set(definition.glyphs))
        return {
            "id": font_id,
            "platform": "psp",
            "disc": "PSP",
            "context": f"PSP UMD · {definition.confidence.replace('_', ' ')}",
            "name": definition.name,
            "file": definition.file,
            "description": definition.description,
            "confidence": definition.confidence,
            "targets": [
                {
                    "kind": target.kind,
                    "iso_path": target.iso_path,
                    "member_index": target.member_index,
                }
                for target in definition.targets
            ],
            "cell": {
                "width": definition.format.width,
                "height": definition.format.height,
                "bpp": definition.format.bpp,
            },
            "source": (
                definition.source_font.relative_to(ASSET_FONT_ROOT).as_posix()
                if definition.source_font is not None
                else None
            ),
            "slots": slots,
            "slot_page": {
                "offset": offset,
                "limit": limit,
                "total": len(matching),
                "physical": definition.glyph_count,
            },
            "slot_counts": {
                "defined": len(definition.glyphs),
                "suggested": suggested_count,
                "unknown": definition.glyph_count
                - len(set(definition.glyphs) | set(suggestions)),
                "replaceable": len(definition.replacements),
            },
            "characters": sorted(
                value
                for value in set(definition.glyphs.values()) | set(definition.replacements.values())
                if len(value) == 1
            ),
            "surfaces": [],
            "config_hash": _file_hash(definition.config_path),
            "language": language_id,
            "source_hash": _file_hash(definition.config_path),
            "customized": False,
            "can_import": False,
            "can_edit": False,
            "can_rebuild": False,
            "atlases": {
                "original": self._data_url(definition.original_atlas_path),
                "modified": None,
            },
        }

    def save_source_value(
        self, font_id: str, code: int, value: str, base_hash: str
    ) -> dict[str, Any]:
        escaped = value.replace("\\_", "_")
        if _SOURCE_TOKEN_RE.fullmatch(escaped) is not None:
            value = escaped
        symbolic = _SOURCE_TOKEN_RE.fullmatch(value) is not None
        plain = all(character.isprintable() and character not in "{}" for character in value)
        if not value or len(value) > 48 or not (symbolic or plain):
            raise ValueError("source value must be printable text or a symbolic label")
        with self._lock:
            definition = self._definition(font_id)
            if not 0 <= code < definition.glyph_count:
                raise ValueError("glyph code is outside the physical font")
            if _file_hash(definition.config_path) != base_hash:
                raise RuntimeError("This font definition changed on disk. Reload before saving.")
            document = json.loads(definition.config_path.read_text(encoding="utf-8"))
            document.setdefault("source_overrides", {})[str(code)] = value
            serialized = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            handle, candidate_name = tempfile.mkstemp(
                prefix=f".{definition.config_path.stem}.",
                suffix=".json",
                dir=definition.config_path.parent,
            )
            try:
                with os.fdopen(handle, "wb") as output:
                    output.write(serialized)
                candidate = load_definition(Path(candidate_name))
                if candidate.glyphs.get(code) != value:
                    raise ValueError("PSP source correction did not round-trip")
                os.replace(candidate_name, definition.config_path)
            finally:
                if os.path.exists(candidate_name):
                    os.unlink(candidate_name)
            self._suggestion_cache.clear()
        return {
            "font": font_id,
            "code": code,
            "source_value": value,
            "source_status": "defined",
            "source_hash": _file_hash(definition.config_path),
        }

    @staticmethod
    def _locked() -> None:
        raise ValueError(
            "PSP raster replacement is locked until this resource's guarded publisher is ported."
        )

    def update_plan(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        self._locked()

    def apply_update(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        self._locked()

    def import_typeface(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        self._locked()

    def remap(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        self._locked()
