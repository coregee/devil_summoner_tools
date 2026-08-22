"""Index canonical text fields and their Saturn consumer surfaces."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import threading
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from saturn.text.util.assets import validate_asset_document
from saturn.text.util.surfaces import load_surfaces
from saturn.text.util.tokens import Named, Raw, Text, format_tokens, parse_tokens

from .models import ConsumerUse, EntryKey

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSET_ROOT = PROJECT_ROOT / "assets" / "text"
BINDING_ROOT = PROJECT_ROOT / "saturn" / "text" / "bindings"


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON field {key!r}")
        output[key] = value
    return output


def _read_document(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: invalid JSON: {error.msg}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def _signature(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CorpusCatalog:
    """A refreshable in-memory view over the authored text JSON."""

    def __init__(
        self,
        *,
        asset_root: Path = ASSET_ROOT,
        binding_root: Path = BINDING_ROOT,
    ) -> None:
        self.asset_root = asset_root
        self.binding_root = binding_root
        self._lock = threading.RLock()
        self._documents: dict[str, dict[str, Any]] = {}
        self._signatures: dict[str, str] = {}
        self._consumers: dict[tuple[str, str], tuple[ConsumerUse, ...]] = {}
        self.refresh()

    def refresh(self) -> None:
        documents: dict[str, dict[str, Any]] = {}
        signatures: dict[str, str] = {}
        for path in sorted(self.asset_root.rglob("*.json")):
            relative = path.relative_to(self.asset_root).as_posix()
            document = _read_document(path)
            # A few authored text assets (notably timed FMV subtitles) have
            # purpose-built schemas.  The first editor slice indexes the shared
            # field catalogue contract and leaves those specialized documents
            # to a later adapter.
            if set(document) != {"version", "kind", "entries"}:
                continue
            validate_asset_document(document, relative)
            documents[relative] = document
            signatures[relative] = _signature(path)
        consumers = self._load_consumers()
        declared: defaultdict[
            tuple[str, str], set[ConsumerUse]
        ] = defaultdict(set)
        for asset, document in documents.items():
            for entry_name, entry in document["entries"].items():
                for field_name, field in entry.items():
                    if field_name in {"status", "note", "placeholders"}:
                        continue
                    asset_ref = f"{entry_name}.{field_name}"
                    for surface in field.get("surfaces", []):
                        declared[(asset, asset_ref)].add(
                            ConsumerUse(f"engine.{asset_ref}", surface)
                        )
        consumers = {
            key: tuple(
                sorted(
                    set(consumers.get(key, ())) | value,
                    key=lambda item: (item.surface or "", item.record_id),
                )
            )
            for key, value in declared.items()
        } | {
            key: value for key, value in consumers.items() if key not in declared
        }
        with self._lock:
            self._documents = documents
            self._signatures = signatures
            self._consumers = consumers

    def _load_consumers(self) -> dict[tuple[str, str], tuple[ConsumerUse, ...]]:
        uses: defaultdict[tuple[str, str], set[ConsumerUse]] = defaultdict(set)
        if not self.binding_root.is_dir():
            return {}
        for path in sorted(self.binding_root.glob("*.json")):
            document = _read_document(path)
            asset = document.get("asset")
            records = document.get("records", {})
            field_surfaces = document.get("field_surfaces", {})
            record_surfaces = document.get("record_surfaces", {})
            if not isinstance(asset, str) or not isinstance(records, dict):
                continue
            for record_id, asset_ref in records.items():
                if not isinstance(record_id, str) or not isinstance(asset_ref, str):
                    continue
                field = asset_ref.rsplit(".", 1)[-1]
                surfaces = record_surfaces.get(record_id, field_surfaces.get(field, ()))
                if not isinstance(surfaces, list):
                    surfaces = []
                if surfaces:
                    for surface in surfaces:
                        if isinstance(surface, str):
                            uses[(asset, asset_ref)].add(
                                ConsumerUse(record_id, surface)
                            )
                else:
                    uses[(asset, asset_ref)].add(ConsumerUse(record_id, None))

            additional = document.get("additional_uses", {})
            if isinstance(additional, dict):
                for record_id, rows in additional.items():
                    if not isinstance(record_id, str) or not isinstance(rows, list):
                        continue
                    surfaces = record_surfaces.get(record_id, ())
                    for row in rows:
                        if not isinstance(row, dict) or not isinstance(
                            row.get("asset"), str
                        ):
                            continue
                        asset_ref = row["asset"]
                        if isinstance(surfaces, list) and surfaces:
                            for surface in surfaces:
                                if isinstance(surface, str):
                                    uses[(asset, asset_ref)].add(
                                        ConsumerUse(record_id, surface)
                                    )
                        else:
                            uses[(asset, asset_ref)].add(ConsumerUse(record_id, None))
        return {
            key: tuple(
                sorted(value, key=lambda item: (item.surface or "", item.record_id))
            )
            for key, value in uses.items()
        }

    def list_entries(
        self,
        query: str = "",
        limit: int = 250,
        *,
        surface: str | None = None,
    ) -> dict[str, Any]:
        needle = query.casefold().strip()
        rows: list[dict[str, Any]] = []
        total = 0
        matching_total = 0
        surface_counts: Counter[str] = Counter()
        with self._lock:
            for asset, document in self._documents.items():
                for entry_name, entry in document["entries"].items():
                    for field_name, field in entry.items():
                        if field_name in {"status", "note", "placeholders"}:
                            continue
                        key = EntryKey(asset, entry_name, field_name)
                        consumers = self._consumers.get((asset, key.asset_ref), ())
                        surfaces = sorted(
                            {
                                item.surface
                                for item in consumers
                                if item.surface is not None
                            }
                        )
                        haystack = "\n".join(
                            (
                                asset,
                                entry_name,
                                field_name,
                                str(field.get("reference", "")),
                                str(field.get("translation", "")),
                                *surfaces,
                            )
                        ).casefold()
                        if needle and needle not in haystack:
                            continue
                        matching_total += 1
                        if surfaces:
                            surface_counts.update(surfaces)
                        else:
                            surface_counts["__unmapped__"] += 1
                        if surface == "__unmapped__":
                            if surfaces:
                                continue
                        elif surface is not None and surface not in surfaces:
                            continue
                        total += 1
                        if len(rows) >= limit:
                            continue
                        rows.append(
                            {
                                "id": key.id,
                                "asset": asset,
                                "entry": entry_name,
                                "field": field_name,
                                "reference": field["reference"],
                                "translation": field["translation"],
                                "reviewed": bool(field.get("reviewed", False)),
                                "font8_alphabet": field.get(
                                    "font8_alphabet", "replaced"
                                ),
                                "surfaces": surfaces,
                                "consumer_count": len(consumers),
                            }
                        )
        return {
            "entries": rows,
            "total": total,
            "matching_total": matching_total,
            "limited": total > len(rows),
            "surface_counts": [
                {"name": name, "count": count}
                for name, count in sorted(
                    surface_counts.items(),
                    key=lambda item: (item[0] == "__unmapped__", item[0]),
                )
            ],
        }

    def entry(self, value: str) -> dict[str, Any]:
        key = EntryKey.parse(value)
        with self._lock:
            try:
                document = self._documents[key.asset]
                raw_entry = document["entries"][key.entry]
                field = raw_entry[key.field]
            except KeyError as error:
                raise ValueError("unknown editor entry") from error
            consumers = self._consumers.get((key.asset, key.asset_ref), ())
            font8_configurable = any(
                item.surface is not None
                and load_surfaces().surface(item.surface).en.font == "font8"
                for item in consumers
            )
            return {
                "id": key.id,
                "asset": key.asset,
                "entry": key.entry,
                "field": key.field,
                "reference": field["reference"],
                "translation": field["translation"],
                "reviewed": bool(field.get("reviewed", False)),
                "font8_alphabet": field.get("font8_alphabet", "replaced"),
                "font8_configurable": font8_configurable,
                "note": field.get("note") or raw_entry.get("note"),
                "status": raw_entry.get("status"),
                "placeholders": copy.deepcopy(raw_entry.get("placeholders", {})),
                "variants": copy.deepcopy(field.get("variants", {})),
                "consumers": [
                    {"record_id": item.record_id, "surface": item.surface}
                    for item in consumers
                ],
                "file_hash": self._signatures[key.asset],
            }

    def candidate_document(
        self,
        value: str,
        translation: str,
        font8_alphabet: str | None = None,
    ) -> dict[str, Any]:
        key = EntryKey.parse(value)
        with self._lock:
            try:
                candidate = copy.deepcopy(self._documents[key.asset])
                field = candidate["entries"][key.entry][key.field]
                field["translation"] = translation
                if font8_alphabet is not None:
                    if font8_alphabet == "replaced":
                        field.pop("font8_alphabet", None)
                    else:
                        field["font8_alphabet"] = font8_alphabet
            except KeyError as error:
                raise ValueError("unknown editor entry") from error
        validate_asset_document(candidate, key.asset)
        return candidate

    def translation_character_counts(self) -> Counter[str]:
        counts: Counter[str] = Counter()
        with self._lock:
            for document in self._documents.values():
                for entry in document["entries"].values():
                    for field_name, field in entry.items():
                        if field_name in {"status", "note", "placeholders"}:
                            continue
                        counts.update(field["translation"])
                        for variant in field.get("variants", {}).values():
                            if "translation" in variant:
                                counts.update(variant["translation"])
        return counts

    def revision(self) -> str:
        """Return a cheap content revision for cache invalidation."""

        with self._lock:
            return hashlib.sha256(
                repr(sorted(self._signatures.items())).encode("utf-8")
            ).hexdigest()

    @staticmethod
    def _glyph_counts(value: str, known_glyphs: set[str]) -> Counter[str]:
        """Count rendered glyph units without treating control tokens as text."""

        counts: Counter[str] = Counter()
        compounds = sorted(
            (
                glyph
                for glyph in known_glyphs
                if len(glyph) > 1 and not glyph.startswith("{")
            ),
            key=lambda glyph: (-len(glyph), glyph),
        )
        for token in parse_tokens(value):
            if isinstance(token, Text):
                position = 0
                while position < len(token.value):
                    compound = next(
                        (
                            glyph
                            for glyph in compounds
                            if token.value.startswith(glyph, position)
                        ),
                        None,
                    )
                    glyph = compound or token.value[position]
                    counts[glyph] += 1
                    position += len(glyph)
            elif isinstance(token, Named):
                glyph = format_tokens((token,))
                # Named tokens normally represent layout or runtime values.  A
                # token is a font consumer only when the font definition names
                # it as a glyph, or when it uses the explicit original_* alias
                # convention reserved for stock game glyphs.
                if glyph in known_glyphs or token.name.startswith("original_"):
                    counts[glyph] += 1
            elif isinstance(token, Raw) and token.kind == "GLYPH":
                glyph = format_tokens((token,))
                if glyph in known_glyphs:
                    counts[glyph] += 1
        return counts

    def font_usage_audit(
        self,
        font_id: str,
        known_glyphs: set[str] | frozenset[str] = frozenset(),
        output_glyphs: set[str] | frozenset[str] | None = None,
    ) -> dict[str, Any]:
        """Audit translated and original consumers for one surface font.

        ``known_glyphs`` describes the source atlas, while ``output_glyphs``
        describes the rebuilt atlas used by translations.  Keeping these
        vocabularies separate matters for replaced compound source tiles: an
        original tile named ``In`` must not make the translated word ``Inv.``
        count as a single required glyph after that tile has been replaced.
        """

        try:
            disc, stem = font_id.split("/", 1)
        except ValueError as error:
            raise ValueError("invalid font id") from error
        if disc not in {"game", "compendium"}:
            raise ValueError("invalid font id")

        required: Counter[str] = Counter()
        preferred: Counter[str] = Counter()
        untranslated: Counter[str] = Counter()
        fields = 0
        source_glyphs = set(known_glyphs)
        translated_glyphs = (
            source_glyphs if output_glyphs is None else set(output_glyphs)
        )
        surfaces = load_surfaces().surfaces
        with self._lock:
            for asset, document in self._documents.items():
                for entry_name, entry in document["entries"].items():
                    for field_name, field in entry.items():
                        if field_name in {"status", "note", "placeholders"}:
                            continue
                        asset_ref = f"{entry_name}.{field_name}"
                        uses = self._consumers.get((asset, asset_ref), ())
                        en_fonts: set[str] = set()
                        ja_fonts: set[str] = set()
                        for use in uses:
                            if use.surface is None or use.surface not in surfaces:
                                continue
                            surface = surfaces[use.surface]
                            if surface.en.font is not None:
                                en_fonts.add(surface.en.font)
                            if surface.ja.font is not None:
                                ja_fonts.add(surface.ja.font)
                        if stem not in en_fonts and stem not in ja_fonts:
                            continue
                        fields += 1
                        reference = field["reference"]
                        translation = field["translation"]
                        uses_replacement_alphabet = not (
                            stem == "font8"
                            and field.get("font8_alphabet", "replaced")
                            == "original"
                        )
                        if stem in en_fonts and uses_replacement_alphabet:
                            required.update(
                                self._glyph_counts(translation, translated_glyphs)
                            )
                        if stem in ja_fonts:
                            source_counts = self._glyph_counts(
                                reference, source_glyphs
                            )
                            preferred.update(source_counts)
                            if not translation.strip() or translation == reference:
                                untranslated.update(source_counts)
                        for variant in field.get("variants", {}).values():
                            variant_reference = variant.get("reference", reference)
                            variant_translation = variant.get(
                                "translation", translation
                            )
                            if stem in en_fonts and uses_replacement_alphabet:
                                required.update(
                                    self._glyph_counts(
                                        variant_translation, translated_glyphs
                                    )
                                )
                            if stem in ja_fonts:
                                source_counts = self._glyph_counts(
                                    variant_reference, source_glyphs
                                )
                                preferred.update(source_counts)
                                if (
                                    not variant_translation.strip()
                                    or variant_translation == variant_reference
                                ):
                                    untranslated.update(source_counts)
        return {
            "required": required,
            "preferred": preferred,
            "untranslated": untranslated,
            "fields": fields,
        }

    def save(
        self,
        value: str,
        translation: str,
        base_hash: str,
        font8_alphabet: str | None = None,
    ) -> dict[str, Any]:
        key = EntryKey.parse(value)
        with self._lock:
            path = self.asset_root.joinpath(*key.asset.split("/"))
            current_hash = _signature(path)
            if base_hash != current_hash:
                raise RuntimeError(
                    "This asset changed on disk. Reload it before saving."
                )
            candidate = self.candidate_document(
                value, translation, font8_alphabet
            )
            serialized = (
                json.dumps(candidate, ensure_ascii=False, indent=2) + "\n"
            ).encode("utf-8")
            handle, temporary = tempfile.mkstemp(
                prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
            )
            try:
                with os.fdopen(handle, "wb") as output:
                    output.write(serialized)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            self._documents[key.asset] = candidate
            self._signatures[key.asset] = _signature(path)
        return self.entry(value)
