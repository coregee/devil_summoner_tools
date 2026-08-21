"""Visual inventory and safe remapping for Saturn font definitions."""

from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
import os
import re
import string
import tempfile
import threading
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from saturn.font.util.codec import decode_glyph, png_bytes, repack_font
from saturn.font.util.definitions import (
    ASSET_FONT_ROOT,
    ATLAS_ROOT,
    CONFIG_ROOT,
    GENERATED_ROOT,
    FontDefinition,
    load_definition,
    load_definitions,
    sha256,
)
from saturn.text.util.surfaces import load_surfaces

from .catalog import CorpusCatalog
from .languages import LanguageService

MAX_FONT_BYTES = 20_000_000
_FONT_SUFFIXES = {".otf", ".ttf"}
_SOURCE_TOKEN_RE = re.compile(r"\{[a-z][a-z0-9_]*\}\Z")
_FONT_NAMES = {
    "game/fnt8x12": "FNT8x12 - Battle Console (12x8 Source Fixed)",
    "game/fnt12x12": "FNT12x12 - Battle Console Kanji (12x12 Source Fixed)",
    "game/font12": "FONT12 - Fusion Text (12px Source)",
    "game/font16": "FONT16 - General Text (16px Source)",
    "game/font6": "FONT6 - HP/MP Text",
    "game/font8": "FONT8 - Menu Text (8px Source)",
    "game/kanji": "KANJI - Name Entry Grid Text (16px Source)",
    "compendium/font16": "FONT16 2nd - Compendium Text",
}


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _font_id(definition: FontDefinition) -> str:
    return f"{definition.disc}/{definition.stem.lower()}"


def _parse_font_id(value: str) -> tuple[str, str]:
    try:
        disc, stem = value.split("/", 1)
    except ValueError as error:
        raise ValueError("invalid font id") from error
    if disc not in {"game", "compendium"} or not stem.isidentifier():
        raise ValueError("invalid font id")
    return disc, stem.lower()


def _index(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return None
    return None


def _sequence_entry(
    entry: dict[str, Any], start: int, values: list[str]
) -> dict[str, Any]:
    key = "characters" if "characters" in entry else "glyphs"
    stored: str | list[str]
    stored = "".join(values) if isinstance(entry[key], str) else values
    return {"replace": True, "start": start, key: stored}


def replace_glyph_mapping(
    document: dict[str, Any], code: int, replacement: str
) -> str:
    """Replace one owned glyph while preserving its original source identity."""

    groups = document.get("atlas", {}).get("groups", {})
    if not isinstance(groups, dict):
        raise ValueError("font configuration has no glyph groups")
    for entries in groups.values():
        if not isinstance(entries, list):
            continue
        for entry_number, entry in enumerate(tuple(entries)):
            if not isinstance(entry, dict) or entry.get("replace") is not True:
                continue
            if "start" in entry:
                start = _index(entry.get("start"))
                key = "characters" if "characters" in entry else "glyphs"
                raw_values = entry.get(key)
                if start is None or not isinstance(raw_values, (str, list)):
                    continue
                values = list(raw_values)
                offset = code - start
                if not 0 <= offset < len(values):
                    continue
                original = values[offset]
                pieces: list[dict[str, Any]] = []
                if offset:
                    pieces.append(_sequence_entry(entry, start, values[:offset]))
                pieces.append(
                    {"replace": True, str(code): {original: replacement}}
                )
                if offset + 1 < len(values):
                    pieces.append(
                        _sequence_entry(
                            entry, code + 1, values[offset + 1 :]
                        )
                    )
                entries[entry_number : entry_number + 1] = pieces
                return original

            for raw_code, value in tuple(entry.items()):
                if raw_code == "replace" or _index(raw_code) != code:
                    continue
                if isinstance(value, str):
                    original = value
                elif isinstance(value, dict) and len(value) == 1:
                    original = next(iter(value))
                else:
                    raise ValueError(f"glyph {code} has an unsupported mapping")
                entry[raw_code] = {original: replacement}
                return original
    raise ValueError(f"glyph {code} is not an editable replacement slot")


def replace_source_mapping(
    document: dict[str, Any], code: int, source_value: str
) -> str | None:
    """Correct one source identity while preserving its current replacement."""

    groups = document.get("atlas", {}).get("groups", {})
    if not isinstance(groups, dict):
        raise ValueError("font configuration has no glyph groups")
    for entries in groups.values():
        if not isinstance(entries, list):
            continue
        for entry_number, entry in enumerate(tuple(entries)):
            if not isinstance(entry, dict):
                continue
            replace = entry.get("replace", False) is True
            if "start" in entry:
                start = _index(entry.get("start"))
                key = "characters" if "characters" in entry else "glyphs"
                raw_values = entry.get(key)
                if start is None or not isinstance(raw_values, (str, list)):
                    continue
                values = list(raw_values)
                offset = code - start
                if not 0 <= offset < len(values):
                    continue
                original = values[offset]
                pieces: list[dict[str, Any]] = []

                def sequence_piece(
                    piece_start: int, piece_values: list[str]
                ) -> dict[str, Any]:
                    stored: str | list[str] = (
                        "".join(piece_values)
                        if isinstance(raw_values, str)
                        else piece_values
                    )
                    return {
                        "replace": replace,
                        "start": piece_start,
                        key: stored,
                    }

                if offset:
                    pieces.append(sequence_piece(start, values[:offset]))
                corrected: str | dict[str, str]
                corrected = (
                    {source_value: original} if replace else source_value
                )
                pieces.append(
                    {"replace": replace, str(code): corrected}
                )
                if offset + 1 < len(values):
                    pieces.append(
                        sequence_piece(code + 1, values[offset + 1 :])
                    )
                entries[entry_number : entry_number + 1] = pieces
                return original

            for raw_code, value in tuple(entry.items()):
                if raw_code == "replace" or _index(raw_code) != code:
                    continue
                if isinstance(value, str):
                    original = value
                    replacement = value if replace else None
                elif isinstance(value, dict) and len(value) == 1:
                    original, replacement = next(iter(value.items()))
                else:
                    raise ValueError(f"glyph {code} has an unsupported mapping")
                entry[raw_code] = (
                    {source_value: replacement}
                    if replace
                    else source_value
                )
                return original
    mapped = groups.setdefault("mapped_source", [])
    if not isinstance(mapped, list):
        raise ValueError("font mapped_source group must be an array")
    mapped.append({"replace": False, str(code): source_value})
    return None


def _atomic_outputs(outputs: list[tuple[Path, bytes]]) -> None:
    staged: list[tuple[Path, str]] = []
    try:
        for path, value in outputs:
            path.parent.mkdir(parents=True, exist_ok=True)
            handle, temporary = tempfile.mkstemp(
                prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
            )
            with os.fdopen(handle, "wb") as output:
                output.write(value)
                output.flush()
                os.fsync(output.fileno())
            staged.append((path, temporary))
        for path, temporary in staged:
            os.replace(temporary, path)
    finally:
        for _path, temporary in staged:
            if os.path.exists(temporary):
                os.unlink(temporary)


def _verified_base_data(definition: FontDefinition) -> bytes:
    if definition.generated_path.is_file():
        generated = definition.generated_path.read_bytes()
        if (
            generated
            and len(generated) % definition.format.glyph_stride == 0
        ):
            return generated
    if not definition.source_path.is_file():
        raise ValueError("The extracted original game font is unavailable.")
    data = definition.source_path.read_bytes()
    if hashlib.sha256(data).hexdigest() == definition.sha256:
        return data
    raise ValueError(
        "The extracted font is not the original game file and no generated "
        "English base is available."
    )


class FontService:
    def __init__(
        self,
        corpus: CorpusCatalog,
        languages: LanguageService,
    ) -> None:
        self.corpus = corpus
        self.languages = languages
        self._lock = threading.RLock()
        self._suggestion_cache: dict[tuple[str, str, str], dict[int, str]] = {}
        self._audit_cache: dict[tuple[str, str, str], dict[str, Any]] = {}

    @staticmethod
    def _definitions() -> dict[str, FontDefinition]:
        return {_font_id(definition): definition for definition in load_definitions()}

    def _definition(self, font_id: str) -> FontDefinition:
        _parse_font_id(font_id)
        try:
            return self._definitions()[font_id]
        except KeyError as error:
            raise ValueError("unknown font") from error

    @staticmethod
    def _config_path(definition: FontDefinition) -> Path:
        return CONFIG_ROOT / definition.disc / f"{definition.stem.lower()}.json"

    @staticmethod
    def _font_data(definition: FontDefinition, preferred: Path | None = None) -> bytes:
        for path in (preferred, definition.generated_path, definition.source_path):
            if path is not None and path.is_file():
                return path.read_bytes()
        raise ValueError(f"Font data is unavailable for {definition.file}.")

    @staticmethod
    def _physical_count(definition: FontDefinition, data: bytes) -> int:
        return len(data) // definition.format.glyph_stride

    @staticmethod
    def _display_name(definition: FontDefinition) -> str:
        return _FONT_NAMES.get(_font_id(definition), definition.file)

    def _required_counts(
        self, font_id: str, definition: FontDefinition
    ) -> dict[str, int]:
        return self._usage_audit(font_id, definition)["required"]

    def _usage_audit(
        self, font_id: str, definition: FontDefinition
    ) -> dict[str, Any]:
        source_glyphs = set(definition.glyphs.values())
        replacement_codes = set(definition.replacements)
        output_glyphs = set(definition.replacements.values()) | {
            glyph
            for code, glyph in definition.glyphs.items()
            if code not in replacement_codes
        }
        glyph_hash = hashlib.sha256(
            repr(
                (
                    sorted(source_glyphs),
                    sorted(output_glyphs),
                    sorted(definition.source_consumers.items()),
                )
            ).encode("utf-8")
        ).hexdigest()
        key = (self.corpus.revision(), font_id, glyph_hash)
        if key not in self._audit_cache:
            audit = self.corpus.font_usage_audit(
                font_id, source_glyphs, output_glyphs
            )
            direct = Counter(
                glyph
                for glyphs in definition.source_consumers.values()
                for glyph in glyphs
            )
            self._audit_cache[key] = {
                **audit,
                "preferred": audit["preferred"] + direct,
                "untranslated": audit["untranslated"] + direct,
                "source_consumers": len(definition.source_consumers),
            }
        return self._audit_cache[key]

    def _suggestions(
        self, definition: FontDefinition, data: bytes, count: int
    ) -> dict[int, str]:
        mapping_hash = hashlib.sha256(
            repr(sorted(definition.glyphs.items())).encode("utf-8")
        ).hexdigest()
        cache_key = (
            _font_id(definition),
            hashlib.sha256(data).hexdigest(),
            mapping_hash,
        )
        if cache_key in self._suggestion_cache:
            return self._suggestion_cache[cache_key]
        matches: dict[bytes, set[str]] = {}
        for code, value in definition.glyphs.items():
            if code >= count:
                continue
            if (
                code in definition.replacements
                and definition.replacements[code] != value
            ):
                continue
            bitmap = decode_glyph(data, definition.format, code).tobytes()
            matches.setdefault(bitmap, set()).add(value)
        suggestions: dict[int, str] = {}
        for code in range(count):
            if code in definition.glyphs:
                continue
            bitmap = decode_glyph(data, definition.format, code).tobytes()
            if not any(bitmap):
                suggestions[code] = " "
                continue
            values = matches.get(bitmap, set())
            if len(values) == 1:
                suggestions[code] = next(iter(values))
        self._suggestion_cache[cache_key] = suggestions
        return suggestions

    def inventory(self, language_id: str = "en") -> dict[str, Any]:
        language = self.languages.detail(language_id)
        surfaces = load_surfaces().surfaces.values()
        rows = []
        for definition in self._definitions().values():
            if definition.file.casefold() == "icon.fon":
                continue
            font_id = _font_id(definition)
            data = self._font_data(definition)
            physical_count = self._physical_count(definition, data)
            known_count = len(definition.glyphs)
            suggestions = self._suggestions(
                definition, data, physical_count
            )
            suggested_count = len(
                set(suggestions) - set(definition.glyphs)
            )
            surface_count = sum(
                surface.en.font == definition.stem.lower() for surface in surfaces
            )
            rows.append(
                {
                    "id": font_id,
                    "disc": definition.disc,
                    "name": self._display_name(definition),
                    "file": definition.file,
                    "cell": {
                        "width": definition.format.width,
                        "height": definition.format.height,
                        "bpp": definition.format.bpp,
                    },
                    "editable_slots": len(definition.replacements),
                    "physical_slots": physical_count,
                    "known_slots": known_count,
                    "suggested_slots": suggested_count,
                    "unknown_slots": physical_count
                    - known_count
                    - suggested_count,
                    "surface_count": surface_count,
                    "source": (
                        definition.source_font.relative_to(ASSET_FONT_ROOT).as_posix()
                        if definition.source_font is not None
                        else None
                    ),
                    "generated": definition.generated_path.is_file(),
                    "customized": font_id in language["fonts"],
                }
            )
        return {"fonts": rows, "language": language_id}

    @staticmethod
    def _glyph_data_url(glyph: Image.Image) -> str:
        alpha = glyph.point(lambda value: 255 if value else 0)
        image = Image.new("RGBA", glyph.size, (234, 242, 231, 0))
        image.putalpha(alpha)
        scale = max(1, 64 // max(glyph.size))
        image = image.resize(
            (image.width * scale, image.height * scale), Image.Resampling.NEAREST
        )
        output = io.BytesIO()
        image.save(output, format="PNG", optimize=True)
        return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode(
            "ascii"
        )

    @classmethod
    def _glyph_image(
        cls, definition: FontDefinition, data: bytes, code: int
    ) -> str:
        return cls._glyph_data_url(
            decode_glyph(data, definition.format, code)
        )

    @classmethod
    def _atlas_glyph_image(
        cls,
        definition: FontDefinition,
        atlas: Image.Image,
        code: int,
        count: int,
    ) -> str:
        columns = definition.atlas.columns
        rows = (count + columns - 1) // columns
        labels = [str(column) for column in range(columns)] + [
            str(row * columns) for row in range(rows)
        ]
        index_font = ImageFont.load_default()
        measurement = ImageDraw.Draw(Image.new("L", (1, 1)))
        bounds = {
            label: measurement.textbbox((0, 0), label, font=index_font)
            for label in labels
        }
        label_height = max(
            bottom - top for _, top, _, bottom in bounds.values()
        )
        row_labels = [str(row * columns) for row in range(rows)]
        row_label_width = max(
            bounds[label][2] - bounds[label][0] for label in row_labels
        )
        left_margin = row_label_width + 8
        top_margin = label_height + 8
        cell_width = definition.format.width * definition.atlas.scale
        cell_height = definition.format.height * definition.atlas.scale
        x = left_margin + (code % columns) * cell_width
        y = top_margin + (code // columns) * cell_height
        glyph = atlas.crop((x, y, x + cell_width, y + cell_height)).convert("L")
        glyph = glyph.resize(
            (definition.format.width, definition.format.height),
            Image.Resampling.NEAREST,
        )
        return cls._glyph_data_url(glyph)

    @staticmethod
    def _data_url(path: Path) -> str | None:
        if not path.is_file():
            return None
        return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode(
            "ascii"
        )

    @staticmethod
    def _profile_paths(
        language_id: str, definition: FontDefinition
    ) -> tuple[Path, Path, Path]:
        generated = GENERATED_ROOT / "languages" / language_id / definition.disc
        atlas = ATLAS_ROOT / "languages" / language_id / definition.disc
        return (
            generated / definition.file,
            generated / f"{definition.stem}_metrics.json",
            atlas / f"{definition.stem}_modified.png",
        )

    def _profile_definition(
        self, definition: FontDefinition, override: dict[str, Any]
    ) -> tuple[FontDefinition, str]:
        config_path = self._config_path(definition)
        document = json.loads(config_path.read_text(encoding="utf-8"))
        document["repack"]["source"] = override["source"]
        document["repack"]["source_sha256"] = override["source_sha256"]
        for raw_code, replacement in override["mappings"].items():
            replace_glyph_mapping(document, int(raw_code), replacement)
        serialized = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
        handle, candidate_name = tempfile.mkstemp(
            prefix=f".{config_path.stem}.", suffix=".json", dir=config_path.parent
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as output:
                output.write(serialized)
            return load_definition(Path(candidate_name), definition.disc), serialized
        finally:
            if os.path.exists(candidate_name):
                os.unlink(candidate_name)

    def _repack_language(
        self,
        language_id: str,
        definition: FontDefinition,
        override: dict[str, Any],
    ) -> FontDefinition:
        candidate, _serialized = self._profile_definition(definition, override)
        base_data = _verified_base_data(candidate)
        if candidate.source_font is None or not candidate.source_font.is_file():
            raise ValueError("The imported typeface is unavailable.")
        if sha256(candidate.source_font) != candidate.source_sha256:
            raise ValueError("The imported typeface changed after it was selected.")
        result = repack_font(base_data, candidate)
        generated, metrics, atlas = self._profile_paths(language_id, candidate)
        outputs = [(generated, result.data), (atlas, png_bytes(result.atlas))]
        if result.metrics is not None:
            outputs.append((metrics, result.metrics.encode("utf-8")))
        _atomic_outputs(outputs)
        return candidate

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
        base_definition = self._definition(font_id)
        language = self.languages.detail(language_id)
        override = language["fonts"].get(font_id)
        definition = base_definition
        generated_path = definition.generated_path
        modified_atlas_path = definition.modified_atlas_path
        if override is not None:
            definition, _serialized = self._profile_definition(definition, override)
            generated_path, _metrics, modified_atlas_path = self._profile_paths(
                language_id, definition
            )
        config_path = self._config_path(definition)
        counts = self._required_counts(font_id, definition)
        data = self._font_data(definition, generated_path)
        physical_count = self._physical_count(definition, data)
        source_data = self._font_data(base_definition)
        source_count = self._physical_count(base_definition, source_data)
        original_atlas = (
            Image.open(base_definition.original_atlas_path).copy()
            if base_definition.original_atlas_path.is_file()
            else None
        )
        suggestions = self._suggestions(
            base_definition, source_data, source_count
        )
        can_edit_render = bool(
            definition.replacements
            and definition.source_font
            and (language_id == "en" or override is not None)
        )
        needle = query.strip().casefold()
        matching_codes = []
        for code in range(physical_count):
            source_value = base_definition.glyphs.get(code)
            suggested_value = suggestions.get(code)
            replacement = definition.replacements.get(code)
            searchable = " ".join(
                value
                for value in (
                    str(code),
                    f"0x{code:04X}",
                    source_value,
                    suggested_value,
                    replacement,
                )
                if value is not None
            ).casefold()
            if not needle or needle in searchable:
                matching_codes.append(code)
        page_codes = matching_codes[offset : offset + limit]
        slots = []
        for code in page_codes:
            defined_value = base_definition.glyphs.get(code)
            suggested_value = suggestions.get(code)
            source_value = defined_value or suggested_value
            replacement = definition.replacements.get(code)
            if defined_value is not None:
                source_status = "defined"
            elif suggested_value is not None:
                source_status = "suggested"
            else:
                source_status = "unknown"
            modified_image = self._glyph_image(definition, data, code)
            if original_atlas is not None and code < source_count:
                original_image = self._atlas_glyph_image(
                    base_definition,
                    original_atlas,
                    code,
                    source_count,
                )
            elif (
                hashlib.sha256(source_data).hexdigest()
                == base_definition.sha256
                and code < source_count
            ):
                original_image = self._glyph_image(
                    base_definition, source_data, code
                )
            else:
                original_image = None
            slots.append(
                {
                    "code": code,
                    "code_label": f"0x{code:04X}",
                    "original": source_value,
                    "source_value": source_value,
                    "source_status": source_status,
                    "can_edit_source": True,
                    "replacement": replacement,
                    "can_edit_render": can_edit_render
                    and code in definition.replacements,
                    "usage": counts[replacement or source_value or ""],
                    "original_image": original_image,
                    "modified_image": modified_image,
                    "image": modified_image,
                }
            )
        surfaces = sorted(
            surface.name
            for surface in load_surfaces().surfaces.values()
            if surface.en.font == definition.stem.lower()
        )
        return {
            "id": font_id,
            "disc": definition.disc,
            "name": self._display_name(definition),
            "file": definition.file,
            "description": self._read_description(config_path),
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
                "total": len(matching_codes),
                "physical": physical_count,
            },
            "slot_counts": {
                "defined": len(
                    base_definition.glyphs
                ),
                "suggested": len(
                    set(suggestions)
                    - set(base_definition.glyphs)
                ),
                "unknown": physical_count
                - len(
                    set(base_definition.glyphs)
                    | set(suggestions)
                ),
                "replaceable": len(definition.replacements),
            },
            "characters": sorted(
                {
                    value
                    for value in (
                        set(definition.glyphs.values())
                        | set(definition.replacements.values())
                    )
                    if len(value) == 1
                }
            ),
            "surfaces": surfaces,
            "config_hash": (
                _file_hash(config_path)
                if language_id == "en"
                else language["file_hash"]
            ),
            "language": language_id,
            "source_hash": _file_hash(config_path),
            "customized": override is not None,
            "can_import": bool(definition.replacements),
            "can_edit": can_edit_render,
            "can_rebuild": (
                definition.source_path.is_file()
                and definition.source_font is not None
                and definition.source_font.is_file()
            ),
            "atlases": {
                "original": self._data_url(base_definition.original_atlas_path),
                "modified": self._data_url(modified_atlas_path),
            },
        }

    def save_source_value(
        self,
        font_id: str,
        code: int,
        value: str,
        base_hash: str,
    ) -> dict[str, Any]:
        escaped_token = value.replace("\\_", "_")
        if _SOURCE_TOKEN_RE.fullmatch(escaped_token) is not None:
            value = escaped_token
        symbolic = _SOURCE_TOKEN_RE.fullmatch(value) is not None
        plain = all(
            character.isprintable() and character not in "{}"
            for character in value
        )
        if not value or len(value) > 48 or not (symbolic or plain):
            raise ValueError(
                "source value must be printable text or a symbolic label such as "
                "{mag_symbol}"
            )
        with self._lock:
            definition = self._definition(font_id)
            data = self._font_data(definition)
            if not 0 <= code < self._physical_count(definition, data):
                raise ValueError("glyph code is outside the physical font")
            config_path = self._config_path(definition)
            if _file_hash(config_path) != base_hash:
                raise RuntimeError(
                    "This font definition changed on disk. Reload before saving."
                )
            if definition.glyphs.get(code) == value:
                return {
                    "font": font_id,
                    "code": code,
                    "source_value": value,
                    "source_status": "defined",
                    "source_hash": base_hash,
                }
            document = json.loads(config_path.read_text(encoding="utf-8"))
            candidate = copy.deepcopy(document)
            replace_source_mapping(candidate, code, value)
            serialized = (
                json.dumps(candidate, ensure_ascii=False, indent=2) + "\n"
            ).encode("utf-8")
            handle, candidate_name = tempfile.mkstemp(
                prefix=f".{config_path.stem}.",
                suffix=".json",
                dir=config_path.parent,
            )
            try:
                with os.fdopen(handle, "wb") as output:
                    output.write(serialized)
                candidate_definition = load_definition(
                    Path(candidate_name), definition.disc
                )
                if candidate_definition.glyphs.get(code) != value:
                    raise ValueError("source correction did not round-trip")
                if (
                    candidate_definition.replacements.get(code)
                    != definition.replacements.get(code)
                ):
                    raise ValueError(
                        "source correction changed the replacement mapping"
                    )
                outputs = [(config_path, serialized)]
                if candidate_definition.source_font is not None:
                    if (
                        not candidate_definition.source_font.is_file()
                        or sha256(candidate_definition.source_font)
                        != candidate_definition.source_sha256
                    ):
                        raise ValueError(
                            "The source typeface does not match its definition."
                        )
                    result = repack_font(
                        _verified_base_data(candidate_definition),
                        candidate_definition,
                    )
                    outputs.extend(
                        [
                            (candidate_definition.generated_path, result.data),
                            (
                                candidate_definition.modified_atlas_path,
                                png_bytes(result.atlas),
                            ),
                        ]
                    )
                    if result.metrics is not None:
                        outputs.append(
                            (
                                candidate_definition.metrics_path,
                                result.metrics.encode("utf-8"),
                            )
                        )
                _atomic_outputs(outputs)
            finally:
                if os.path.exists(candidate_name):
                    os.unlink(candidate_name)
        return {
            "font": font_id,
            "code": code,
            "source_value": value,
            "source_status": "defined",
            "source_hash": _file_hash(config_path),
        }

    def update_plan(
        self,
        font_id: str,
        language_id: str = "en",
    ) -> dict[str, Any]:
        """Plan corpus-driven replacements without changing any files."""

        base_definition = self._definition(font_id)
        language = self.languages.detail(language_id)
        override = language["fonts"].get(font_id)
        definition = base_definition
        if override is not None:
            definition, _serialized = self._profile_definition(
                base_definition, override
            )
        known_glyphs = set(definition.glyphs.values()) | set(
            definition.replacements.values()
        )
        audit = self._usage_audit(font_id, definition)
        required = audit["required"].copy()
        declared = {
            character
            for character in language["characters"]
            if not character.isspace()
        }
        for character in language["characters"]:
            if not character.isspace():
                required[character] = max(required[character], 1)
        preferred = audit["preferred"]
        untranslated = audit["untranslated"]
        slots = set(definition.replacements)
        fixed = {
            value
            for code, value in definition.glyphs.items()
            if code not in slots
        }
        locked_codes = {
            code
            for code in slots
            if untranslated[definition.glyphs.get(code, "")] > 0
        }
        fixed.update(definition.replacements[code] for code in locked_codes)

        unresolved_symbols = sorted(
            glyph
            for glyph in required
            if glyph.startswith("{") and glyph not in known_glyphs
        )
        eligible_required = {
            glyph: count
            for glyph, count in required.items()
            if not glyph.isspace() and glyph not in unresolved_symbols
        }
        needed = {
            glyph: count
            for glyph, count in eligible_required.items()
            if glyph not in fixed
        }
        mutable_codes = slots - locked_codes
        selected = dict(
            sorted(
                needed.items(),
                key=lambda row: (row[0] not in declared, -row[1], row[0]),
            )[
                : len(mutable_codes)
            ]
        )
        omitted = sorted(
            set(needed) - set(selected),
            key=lambda glyph: (
                glyph not in declared,
                -needed[glyph],
                glyph,
            ),
        )

        final = dict(definition.replacements)
        kept_codes: set[int] = set()
        for glyph in selected:
            matching = [
                code
                for code in mutable_codes
                if final[code] == glyph
            ]
            if matching:
                # Preserve the copy whose original source glyph is most costly
                # to evict. Duplicate replacement mappings should consume only
                # one slot in the final plan.
                kept_codes.add(
                    max(
                        matching,
                        key=lambda code: (
                            preferred[definition.glyphs.get(code, "")],
                            required[definition.replacements[code]],
                            -code,
                        ),
                    )
                )
        remaining_codes = sorted(
            mutable_codes - kept_codes,
            key=lambda code: (
                preferred[definition.glyphs.get(code, "")],
                required[definition.replacements[code]],
                code,
            ),
        )
        assigned = {final[code] for code in kept_codes}
        remaining_glyphs = sorted(
            set(selected) - assigned,
            key=lambda glyph: (
                glyph not in declared,
                -selected[glyph],
                glyph,
            ),
        )
        for code, glyph in zip(remaining_codes, remaining_glyphs, strict=False):
            final[code] = glyph

        changes = []
        required_displaced = []
        for code in sorted(slots):
            before = definition.replacements[code]
            after = final[code]
            if before == after:
                continue
            row = {
                "code": code,
                "code_label": f"0x{code:04X}",
                "source": definition.glyphs.get(code),
                "before": before,
                "after": after,
                "original_frequency": preferred[
                    definition.glyphs.get(code, "")
                ],
                "required_frequency": required[before],
            }
            changes.append(row)
            if required[before]:
                required_displaced.append(row)

        warnings = []
        if locked_codes:
            warnings.append(
                f"{len(locked_codes)} slots used by untranslated source text are "
                "protected from automatic replacement."
            )
        if required_displaced:
            warnings.append(
                f"{len(required_displaced)} currently required glyphs would be "
                "replaced; review the affected rows before applying."
            )
        if omitted:
            warnings.append(
                f"{len(omitted)} required glyphs do not fit in the available "
                "replacement slots."
            )
        if unresolved_symbols:
            warnings.append(
                "Symbolic glyphs must first be assigned to an original font slot: "
                + ", ".join(unresolved_symbols)
            )
        if definition.source_font is None:
            warnings.append("Choose a replacement typeface before updating this font.")

        return {
            "font": font_id,
            "language": language_id,
            "typeface": (
                definition.source_font.relative_to(ASSET_FONT_ROOT).as_posix()
                if definition.source_font is not None
                else None
            ),
            "base_hash": (
                _file_hash(self._config_path(base_definition))
                if language_id == "en"
                else language["file_hash"]
            ),
            "audit": {
                "fields": audit["fields"],
                "required_glyphs": len(required),
                "required_uses": sum(required.values()),
                "preferred_glyphs": len(preferred),
                "preferred_uses": sum(preferred.values()),
                "untranslated_glyphs": len(untranslated),
                "protected_slots": len(locked_codes),
                "replacement_slots": len(slots),
            },
            "top_required": [
                {"glyph": glyph, "count": count}
                for glyph, count in required.most_common(16)
            ],
            "changes": changes,
            "mappings": {str(code): value for code, value in sorted(final.items())},
            "omitted_required": [
                {"glyph": glyph, "count": required[glyph]} for glyph in omitted
            ],
            "required_displaced": required_displaced,
            "unresolved_symbols": unresolved_symbols,
            "warnings": warnings,
            "can_apply": bool(definition.source_font) and bool(slots),
        }

    def apply_update(
        self,
        font_id: str,
        language_id: str,
        base_hash: str,
        *,
        confirm_required: bool = False,
    ) -> dict[str, Any]:
        """Apply the latest corpus-derived plan and rebuild its font outputs."""

        with self._lock:
            plan = self.update_plan(font_id, language_id)
            if plan["base_hash"] != base_hash:
                raise RuntimeError(
                    "This font or language project changed on disk. Reload the plan."
                )
            if not plan["can_apply"]:
                raise ValueError("Choose a replacement typeface before updating.")
            if plan["required_displaced"] and not confirm_required:
                raise RuntimeError(
                    "The plan replaces required glyphs. Confirm the reviewed plan "
                    "before applying."
                )
            base_definition = self._definition(font_id)
            if language_id != "en":
                language = self.languages.detail(language_id)
                override = copy.deepcopy(language["fonts"].get(font_id))
                if override is None:
                    raise ValueError("Choose a replacement typeface before updating.")
                override["mappings"] = plan["mappings"]
                self._repack_language(language_id, base_definition, override)
                self.languages.replace_font_mappings(
                    language_id,
                    font_id,
                    plan["mappings"],
                    base_hash,
                )
                return self.detail(font_id, language_id)

            config_path = self._config_path(base_definition)
            document = json.loads(config_path.read_text(encoding="utf-8"))
            candidate = copy.deepcopy(document)
            for raw_code, replacement in plan["mappings"].items():
                replace_glyph_mapping(candidate, int(raw_code), replacement)
            serialized = (
                json.dumps(candidate, ensure_ascii=False, indent=2) + "\n"
            ).encode("utf-8")
            handle, candidate_name = tempfile.mkstemp(
                prefix=f".{config_path.stem}.",
                suffix=".json",
                dir=config_path.parent,
            )
            try:
                with os.fdopen(handle, "wb") as output:
                    output.write(serialized)
                candidate_definition = load_definition(
                    Path(candidate_name), base_definition.disc
                )
                if candidate_definition.source_font is None:
                    raise ValueError("Choose a replacement typeface before updating.")
                if (
                    not candidate_definition.source_font.is_file()
                    or sha256(candidate_definition.source_font)
                    != candidate_definition.source_sha256
                ):
                    raise ValueError("The replacement typeface changed on disk.")
                result = repack_font(
                    _verified_base_data(candidate_definition), candidate_definition
                )
                outputs = [
                    (config_path, serialized),
                    (candidate_definition.generated_path, result.data),
                    (
                        candidate_definition.modified_atlas_path,
                        png_bytes(result.atlas),
                    ),
                ]
                if result.metrics is not None:
                    outputs.append(
                        (
                            candidate_definition.metrics_path,
                            result.metrics.encode("utf-8"),
                        )
                    )
                _atomic_outputs(outputs)
            finally:
                if os.path.exists(candidate_name):
                    os.unlink(candidate_name)
        return self.detail(font_id, language_id)

    @staticmethod
    def automatic_mappings(
        definition: FontDefinition,
        characters: str,
        counts: dict[str, int],
    ) -> dict[str, str]:
        required = [
            character
            for character in dict.fromkeys(characters)
            if not character.isspace()
            and character not in set(definition.replacements.values())
        ]
        protected = set(string.ascii_letters + string.digits + " ")
        slots = sorted(
            definition.replacements,
            key=lambda code: (
                definition.replacements[code] in protected,
                counts[definition.replacements[code]],
                code,
            ),
        )
        if len(required) > len(slots):
            raise ValueError(
                f"This font has {len(slots)} editable slots but needs "
                f"{len(required)} new characters. Reduce the language character set."
            )
        return {
            str(code): character
            for code, character in zip(slots, required, strict=False)
        }

    def import_typeface(
        self,
        language_id: str,
        font_id: str,
        filename: str,
        content: bytes,
    ) -> dict[str, Any]:
        definition = self._definition(font_id)
        if not definition.replacements:
            raise ValueError("This game font has no editable character slots.")
        safe_name = Path(filename).name
        suffix = Path(safe_name).suffix.casefold()
        if (
            not safe_name
            or suffix not in _FONT_SUFFIXES
            or re.fullmatch(r"[A-Za-z0-9._ -]+", safe_name) is None
        ):
            raise ValueError("Choose a .ttf or .otf font file with a simple filename.")
        if not content or len(content) > MAX_FONT_BYTES:
            raise ValueError("The font file must be between 1 byte and 20 MB.")
        try:
            ImageFont.truetype(io.BytesIO(content), size=16)
        except OSError as error:
            raise ValueError(
                "The selected file is not a readable TTF/OTF typeface."
            ) from error
        digest = hashlib.sha256(content).hexdigest()
        clean_stem = re.sub(r"[^A-Za-z0-9_-]+", "-", Path(safe_name).stem).strip("-")
        imported_name = f"{clean_stem}-{digest[:12]}{suffix}"
        relative = Path("imported") / language_id / imported_name
        destination = ASSET_FONT_ROOT / relative
        with self._lock:
            _atomic_outputs([(destination, content)])
            if language_id == "en":
                config_path = self._config_path(definition)
                document = json.loads(config_path.read_text(encoding="utf-8"))
                document["repack"]["source"] = relative.as_posix()
                document["repack"]["source_sha256"] = digest
                serialized = (
                    json.dumps(document, ensure_ascii=False, indent=2) + "\n"
                ).encode("utf-8")
                handle, candidate_name = tempfile.mkstemp(
                    prefix=f".{config_path.stem}.",
                    suffix=".json",
                    dir=config_path.parent,
                )
                try:
                    with os.fdopen(handle, "wb") as output:
                        output.write(serialized)
                    candidate = load_definition(
                        Path(candidate_name), definition.disc
                    )
                    result = repack_font(_verified_base_data(candidate), candidate)
                    outputs = [
                        (config_path, serialized),
                        (candidate.generated_path, result.data),
                        (candidate.modified_atlas_path, png_bytes(result.atlas)),
                    ]
                    if result.metrics is not None:
                        outputs.append(
                            (candidate.metrics_path, result.metrics.encode("utf-8"))
                        )
                    _atomic_outputs(outputs)
                finally:
                    if os.path.exists(candidate_name):
                        os.unlink(candidate_name)
                return self.detail(font_id, language_id)

            mappings = {
                str(code): replacement
                for code, replacement in sorted(definition.replacements.items())
            }
            override = {
                "source": relative.as_posix(),
                "source_sha256": digest,
                "mappings": mappings,
            }
            self._repack_language(language_id, definition, override)
            self.languages.set_font_override(
                language_id, font_id, relative.as_posix(), digest, mappings
            )
        return self.detail(font_id, language_id)

    @staticmethod
    def _read_description(path: Path) -> str | None:
        value = json.loads(path.read_text(encoding="utf-8")).get("description")
        return value if isinstance(value, str) else None

    def remap(
        self,
        font_id: str,
        code: int,
        replacement: str,
        base_hash: str,
        *,
        language_id: str = "en",
        confirm_used: bool = False,
    ) -> dict[str, Any]:
        if (
            not replacement
            or len(replacement) > 3
            or any(character in "{}\r\n\t" for character in replacement)
        ):
            raise ValueError("replacement must contain one to three visible characters")
        if language_id != "en":
            with self._lock:
                language = self.languages.detail(language_id)
                if language["file_hash"] != base_hash:
                    raise RuntimeError(
                        "This language project changed on disk. "
                        "Reload it before saving."
                    )
                override = language["fonts"].get(font_id)
                if override is None:
                    raise ValueError("Import a typeface for this font first.")
                definition = self._definition(font_id)
                current_definition, _serialized = self._profile_definition(
                    definition, override
                )
                if code not in current_definition.replacements:
                    raise ValueError("glyph is not an editable replacement slot")
                current = current_definition.replacements[code]
                duplicate = next(
                    (
                        other_code
                        for other_code, value in current_definition.replacements.items()
                        if value == replacement and other_code != code
                    ),
                    None,
                )
                if duplicate is not None:
                    raise ValueError(
                        f"{replacement!r} is already assigned to glyph {duplicate}."
                    )
                if current == replacement:
                    return self.detail(font_id, language_id)
                usage = self._required_counts(
                    font_id, current_definition
                )[current]
                if usage and not confirm_used:
                    raise RuntimeError(
                        f"{current!r} is used {usage} times in the translation; "
                        "confirm replacement to continue."
                    )
                candidate_override = copy.deepcopy(override)
                candidate_override["mappings"][str(code)] = replacement
                self._repack_language(language_id, definition, candidate_override)
                self.languages.update_font_mapping(
                    language_id, font_id, code, replacement, base_hash
                )
            return self.detail(font_id, language_id)

        with self._lock:
            definition = self._definition(font_id)
            config_path = self._config_path(definition)
            if _file_hash(config_path) != base_hash:
                raise RuntimeError(
                    "This font changed on disk. Reload it before saving."
                )
            if code not in definition.replacements:
                raise ValueError("glyph is not an editable replacement slot")
            current = definition.replacements[code]
            duplicate = next(
                (
                    other_code
                    for other_code, value in definition.replacements.items()
                    if value == replacement and other_code != code
                ),
                None,
            )
            if duplicate is not None:
                raise ValueError(
                    f"{replacement!r} is already assigned to glyph {duplicate}."
                )
            if current == replacement:
                return self.detail(font_id)
            usage = self._required_counts(font_id, definition)[current]
            if current != replacement and usage and not confirm_used:
                raise RuntimeError(
                    f"{current!r} is used {usage} times in the translation; "
                    "confirm replacement to continue."
                )

            document = json.loads(config_path.read_text(encoding="utf-8"))
            candidate = copy.deepcopy(document)
            replace_glyph_mapping(candidate, code, replacement)
            serialized = (
                json.dumps(candidate, ensure_ascii=False, indent=2) + "\n"
            ).encode("utf-8")

            handle, candidate_name = tempfile.mkstemp(
                prefix=f".{config_path.stem}.", suffix=".json", dir=config_path.parent
            )
            try:
                with os.fdopen(handle, "wb") as output:
                    output.write(serialized)
                candidate_definition = load_definition(
                    Path(candidate_name), definition.disc
                )
                base_data = _verified_base_data(candidate_definition)
                if candidate_definition.source_font is None:
                    raise ValueError("This font has no editable source typeface.")
                if (
                    sha256(candidate_definition.source_font)
                    != candidate_definition.source_sha256
                ):
                    raise ValueError(
                        "The source typeface does not match its definition."
                    )
                result = repack_font(
                    base_data, candidate_definition
                )
                outputs = [
                    (candidate_definition.generated_path, result.data),
                    (candidate_definition.modified_atlas_path, png_bytes(result.atlas)),
                ]
                if result.metrics is not None:
                    outputs.append(
                        (
                            candidate_definition.metrics_path,
                            result.metrics.encode("utf-8"),
                        )
                    )
                outputs.append((config_path, serialized))
                _atomic_outputs(outputs)
            finally:
                if os.path.exists(candidate_name):
                    os.unlink(candidate_name)
        return self.detail(font_id, language_id)
