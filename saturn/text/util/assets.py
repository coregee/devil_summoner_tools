"""Load and validate shared authored text and Saturn physical bindings."""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any

from .surfaces import load_surfaces
from .tokens import Named, Raw, Text, format_tokens, parse_tokens, valid_name

TEXT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = TEXT_ROOT.parents[1]
ASSET_ROOT = PROJECT_ROOT / "assets" / "text"
BINDING_ROOT = TEXT_ROOT / "bindings"
CORPUS_ROOT = TEXT_ROOT / "corpus"

_IDENTIFIER_RE = re.compile(r"[a-z][a-z0-9_]*\Z")
_ASSET_REF_RE = re.compile(r"([a-z][a-z0-9_]*)\.([a-z][a-z0-9_]*)\Z")
_LAYOUT_TOKENS = frozenset({"n", "NL"})
_SOURCE_ONLY_GLYPHS = frozenset({"maru_symbol"})
_AUTHORED_SYMBOLS = frozenset({"mag_symbol", "yen_symbol"})
_CONTROL_TOKENS = frozenset({"WAIT", "BEAT"})
_PLACEHOLDER_TYPES = frozenset(
    {
        "character_name",
        "alignment_label",
        "battle_command",
        "control_rank",
        "demon_name",
        "demon_race",
        "difficulty_label",
        "display_value",
        "drink_name",
        "formatted_currency_amount",
        "item_name",
        "location_name",
        "number",
        "personality_label",
        "player_codename",
        "player_name",
    }
)
_KINDS = frozenset({"entity_catalog", "surface_catalog"})
_STATUSES = frozenset({"reserve", "unresolved"})
_GLYPH_CODE_RE = re.compile(r"(?:[0-9a-f]{2}|[0-9a-f]{4})\Z")


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
        raise ValueError(f"missing JSON file: {path}") from error
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
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        raise ValueError(f"{context} must be a lowercase identifier")
    return value


def _text(value: Any, context: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{context} must be text")
    try:
        parse_tokens(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{context}: {error}") from error
    return value


def _functional_tokens(value: str) -> Counter[tuple[str, str, int]]:
    return Counter(
        ("named", token.name, 0)
        for token in parse_tokens(value)
        if isinstance(token, Named)
        and token.name not in _LAYOUT_TOKENS | _SOURCE_ONLY_GLYPHS
    ) + Counter(
        ("op", f"{token.value:x}", token.width)
        for token in parse_tokens(value)
        if isinstance(token, Raw) and token.kind == "OP"
    )


def _placeholder_tokens(value: str) -> Counter[str]:
    return Counter(
        token.name
        for token in parse_tokens(value)
        if isinstance(token, Named)
        and token.name
        not in (
            _LAYOUT_TOKENS
            | _SOURCE_ONLY_GLYPHS
            | _AUTHORED_SYMBOLS
            | _CONTROL_TOKENS
        )
    )


@dataclass(frozen=True, slots=True)
class TextVariant:
    reference: str | None
    translation: str | None
    reviewed: bool | None
    note: str | None


@dataclass(frozen=True, slots=True)
class TextField:
    reference: str
    translation: str
    reviewed: bool
    note: str | None
    variants: Mapping[str, TextVariant]

    def resolve(self, variant: str | None = None) -> tuple[str, str, bool]:
        if variant is None:
            return self.reference, self.translation, self.reviewed
        try:
            selected = self.variants[variant]
        except KeyError as error:
            raise ValueError(f"unknown text variant {variant!r}") from error
        return (
            self.reference if selected.reference is None else selected.reference,
            self.translation
            if selected.translation is None
            else selected.translation,
            self.reviewed if selected.reviewed is None else selected.reviewed,
        )


@dataclass(frozen=True, slots=True)
class AssetEntry:
    fields: Mapping[str, TextField]
    placeholders: Mapping[str, str]
    status: str | None
    note: str | None


@dataclass(frozen=True, slots=True)
class AssetCatalog:
    kind: str
    entries: Mapping[str, AssetEntry]

    def field(self, asset_ref: str) -> TextField:
        match = _ASSET_REF_RE.fullmatch(asset_ref)
        if match is None:
            raise ValueError(f"invalid asset reference {asset_ref!r}")
        entry_name, field_name = match.groups()
        try:
            return self.entries[entry_name].fields[field_name]
        except KeyError as error:
            raise ValueError(f"unknown asset reference {asset_ref!r}") from error


@dataclass(frozen=True, slots=True)
class Composition:
    source_role: str
    supplies: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AdditionalUse:
    asset_ref: str
    variant: str | None
    composition: Composition | None


@dataclass(frozen=True, slots=True)
class AssetBinding:
    asset: PurePosixPath
    records: Mapping[str, str]
    variants: Mapping[str, str]
    composition: Mapping[str, Composition]
    additional_uses: Mapping[str, tuple[AdditionalUse, ...]]
    reference_normalization: str | None
    glyph_equivalence: Mapping[str, str]
    glyph_tokens: Mapping[str, str]
    field_surfaces: Mapping[str, tuple[str, ...]]
    record_surfaces: Mapping[str, tuple[str, ...]]
    unresolved: Mapping[str, str]


def _load_text_field(value: Any, context: str) -> TextField:
    document = _object(value, context)
    _fields(
        document,
        {"reference", "translation"},
        context,
        optional={"reviewed", "note", "variants"},
    )
    reference = _text(document["reference"], f"{context}.reference")
    translation = _text(document["translation"], f"{context}.translation")
    reviewed = document.get("reviewed", False)
    if type(reviewed) is not bool:
        raise ValueError(f"{context}.reviewed must be boolean")
    note = document.get("note")
    if note is not None and (not isinstance(note, str) or not note):
        raise ValueError(f"{context}.note must be nonempty text")

    variants: dict[str, TextVariant] = {}
    for name, raw_variant in _object(
        document.get("variants", {}), f"{context}.variants"
    ).items():
        _identifier(name, f"{context} variant key")
        variant = _object(raw_variant, f"{context}.variants.{name}")
        if not variant or not set(variant) <= {
            "reference",
            "translation",
            "reviewed",
            "note",
        }:
            raise ValueError(f"{context}.variants.{name} has invalid fields")
        if "reference" not in variant and "translation" not in variant:
            raise ValueError(
                f"{context}.variants.{name} must change reference or translation"
            )
        variant_reference = (
            _text(variant["reference"], f"{context}.variants.{name}.reference")
            if "reference" in variant
            else None
        )
        variant_translation = (
            _text(
                variant["translation"],
                f"{context}.variants.{name}.translation",
            )
            if "translation" in variant
            else None
        )
        variant_reviewed = variant.get("reviewed")
        if variant_reviewed is not None and type(variant_reviewed) is not bool:
            raise ValueError(f"{context}.variants.{name}.reviewed must be boolean")
        variant_note = variant.get("note")
        if variant_note is not None and (
            not isinstance(variant_note, str) or not variant_note
        ):
            raise ValueError(
                f"{context}.variants.{name}.note must be nonempty text"
            )
        variants[name] = TextVariant(
            variant_reference,
            variant_translation,
            variant_reviewed,
            variant_note,
        )
    return TextField(
        reference,
        translation,
        reviewed,
        note,
        MappingProxyType(variants),
    )


def validate_asset_document(value: Any, context: str = "asset") -> AssetCatalog:
    """Validate one compact authored asset document."""
    document = _object(value, context)
    _fields(document, {"version", "kind", "entries"}, context)
    if type(document["version"]) is not int or document["version"] != 1:
        raise ValueError(f"{context}.version must be 1")
    kind = document["kind"]
    if not isinstance(kind, str) or kind not in _KINDS:
        raise ValueError(f"{context}.kind must be one of {sorted(_KINDS)}")

    entries: dict[str, AssetEntry] = {}
    raw_entries = _object(document["entries"], f"{context}.entries")
    if not raw_entries:
        raise ValueError(f"{context}.entries must not be empty")
    for entry_name, raw_entry in raw_entries.items():
        _identifier(entry_name, f"{context} entry key")
        entry = _object(raw_entry, f"{context}.entries.{entry_name}")
        status = entry.get("status")
        if status is not None and (
            not isinstance(status, str) or status not in _STATUSES
        ):
            raise ValueError(
                f"{context}.entries.{entry_name}.status must be one of "
                f"{sorted(_STATUSES)}"
            )
        note = entry.get("note")
        if note is not None and (not isinstance(note, str) or not note):
            raise ValueError(
                f"{context}.entries.{entry_name}.note must be nonempty text"
            )
        placeholders: dict[str, str] = {}
        for placeholder, placeholder_type in _object(
            entry.get("placeholders", {}),
            f"{context}.entries.{entry_name}.placeholders",
        ).items():
            if not isinstance(placeholder, str) or not valid_name(placeholder):
                raise ValueError(f"{context} placeholder must be a valid token")
            resolved_type = _identifier(
                placeholder_type, f"{context} placeholder type"
            )
            if resolved_type not in _PLACEHOLDER_TYPES:
                raise ValueError(
                    f"{context} placeholder type must be one of "
                    f"{sorted(_PLACEHOLDER_TYPES)}"
                )
            placeholders[placeholder] = resolved_type

        field_names = set(entry) - {"status", "note", "placeholders"}
        if not field_names:
            raise ValueError(f"{context}.entries.{entry_name} has no text fields")
        if kind == "surface_catalog" and field_names != {"text"}:
            raise ValueError(
                f"{context}.entries.{entry_name} surface field must be 'text'"
            )
        text_fields: dict[str, TextField] = {}
        for field_name in field_names:
            _identifier(field_name, f"{context} field key")
            text_field = _load_text_field(
                entry[field_name],
                f"{context}.entries.{entry_name}.{field_name}",
            )
            expected_tokens = frozenset(placeholders)
            for variant_name in (None, *text_field.variants):
                reference, translation, _reviewed = text_field.resolve(variant_name)
                if _functional_tokens(reference) != _functional_tokens(
                    translation
                ):
                    raise ValueError(
                        f"{context}.entries.{entry_name}.{field_name} reference and "
                        "translation functional tokens differ"
                    )
                reference_tokens = _placeholder_tokens(reference)
                if set(reference_tokens) != expected_tokens:
                    raise ValueError(
                        f"{context}.entries.{entry_name}.{field_name} placeholders "
                        f"are {sorted(reference_tokens)}, expected "
                        f"{sorted(expected_tokens)}"
                    )
            text_fields[field_name] = text_field
        entries[entry_name] = AssetEntry(
            MappingProxyType(text_fields),
            MappingProxyType(placeholders),
            status,
            note,
        )
    return AssetCatalog(kind, MappingProxyType(entries))


def _safe_relative_path(value: Any, context: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"{context} must be a relative JSON path")
    raw_parts = value.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise ValueError(f"{context} must be a safe relative JSON path")
    if any(_IDENTIFIER_RE.fullmatch(part) is None for part in raw_parts[:-1]):
        raise ValueError(f"{context} must be a canonical relative JSON path")
    filename = raw_parts[-1]
    if not filename.endswith(".json") or _IDENTIFIER_RE.fullmatch(
        filename.removesuffix(".json")
    ) is None:
        raise ValueError(f"{context} must be a canonical relative JSON path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.suffix != ".json":
        raise ValueError(f"{context} must be a safe relative JSON path")
    return path


def load_asset(
    path: PurePosixPath | str,
    *,
    asset_root: Path = ASSET_ROOT,
) -> AssetCatalog:
    relative = _safe_relative_path(str(path), "asset path")
    return validate_asset_document(
        _read_json(asset_root.joinpath(*relative.parts)), str(relative)
    )


def _physical_records(corpus_root: Path) -> Mapping[str, str]:
    records: dict[str, str] = {}
    for path in sorted(corpus_root.rglob("*.json")):
        rows = _read_json(path)
        if not isinstance(rows, list):
            raise ValueError(f"{path}: physical corpus must be a list")
        for index, raw_row in enumerate(rows):
            row = _object(raw_row, f"{path}[{index}]")
            record_id = row.get("id")
            reference = row.get("reference")
            if not isinstance(record_id, str) or not isinstance(reference, str):
                raise ValueError(f"{path}[{index}] has an invalid physical record")
            if record_id in records:
                raise ValueError(f"duplicate physical record {record_id!r}")
            records[record_id] = reference
    return MappingProxyType(records)


def load_physical_records(
    corpus_root: Path = CORPUS_ROOT,
) -> Mapping[str, str]:
    """Load the immutable physical-id to source-reference inventory once."""
    return _physical_records(corpus_root)


def load_bound_translations(
    prefixes: tuple[str, ...],
    *,
    required_ids: set[str] | frozenset[str] | None = None,
) -> Mapping[str, str]:
    """Resolve primary Saturn physical records to their authored translations."""
    if not prefixes or any(not prefix for prefix in prefixes):
        raise ValueError("binding prefixes must be nonempty")
    physical = load_physical_records()
    catalogs: dict[PurePosixPath, AssetCatalog] = {}
    translations: dict[str, str] = {}
    for path in sorted(BINDING_ROOT.glob("*.json")):
        if not any(prefix in path.read_text(encoding="utf-8") for prefix in prefixes):
            continue
        binding = load_binding(path, physical_records=physical)
        catalog = catalogs.setdefault(binding.asset, load_asset(binding.asset))
        for physical_id, asset_ref in binding.records.items():
            if not physical_id.startswith(prefixes):
                continue
            if required_ids is not None and physical_id not in required_ids:
                continue
            if physical_id in translations:
                raise ValueError(f"physical record has two authored owners: {physical_id}")
            _reference, translation, _reviewed = catalog.field(asset_ref).resolve(
                binding.variants.get(physical_id)
            )
            if not translation:
                raise ValueError(f"physical record is untranslated: {physical_id}")
            translations[physical_id] = translation

    if required_ids is not None:
        missing = sorted(set(required_ids) - set(translations))
        extra = sorted(set(translations) - set(required_ids))
        if missing or extra:
            raise ValueError(
                f"binding coverage differs: {len(missing)} missing, {len(extra)} extra"
            )
    return MappingProxyType(translations)


def load_binding(
    path: Path,
    *,
    asset_root: Path = ASSET_ROOT,
    corpus_root: Path = CORPUS_ROOT,
    physical_records: Mapping[str, str] | None = None,
) -> AssetBinding:
    """Validate a binding and prove every selected physical reference."""
    document = _object(_read_json(path), str(path))
    _fields(
        document,
        {"version", "asset", "records"},
        str(path),
        optional={
            "variants",
            "composition",
            "additional_uses",
            "reference_normalization",
            "glyph_equivalence",
            "glyph_tokens",
            "field_surfaces",
            "record_surfaces",
            "unresolved",
        },
    )
    if type(document["version"]) is not int or document["version"] != 1:
        raise ValueError(f"{path}: version must be 1")
    asset_path = _safe_relative_path(document["asset"], f"{path}.asset")
    catalog = load_asset(asset_path, asset_root=asset_root)

    records: dict[str, str] = {}
    for physical_id, asset_ref in _object(
        document["records"], f"{path}.records"
    ).items():
        if not isinstance(physical_id, str) or not physical_id:
            raise ValueError(f"{path}: physical record ids must be nonempty text")
        if not isinstance(asset_ref, str):
            raise ValueError(f"{path}.records.{physical_id} must be an asset reference")
        catalog.field(asset_ref)
        records[physical_id] = asset_ref

    variants: dict[str, str] = {}
    for physical_id, variant in _object(
        document.get("variants", {}), f"{path}.variants"
    ).items():
        if physical_id not in records:
            raise ValueError(f"{path}: variant selects an unbound physical record")
        variant_name = _identifier(variant, f"{path}.variants.{physical_id}")
        catalog.field(records[physical_id]).resolve(variant_name)
        variants[physical_id] = variant_name

    def load_composition(
        raw_composition: Any,
        context: str,
        asset_ref: str,
    ) -> Composition:
        value = _object(raw_composition, context)
        _fields(value, {"source_role", "supplies"}, context)
        if value["source_role"] not in {"prefix", "suffix"}:
            raise ValueError(
                f"{path}: composition source role must be 'prefix' or 'suffix'"
            )
        if not isinstance(value["supplies"], list) or not value["supplies"]:
            raise ValueError(f"{context}.supplies must be a list")
        supplies = tuple(
            _identifier(item, f"{context}.supplies")
            for item in value["supplies"]
        )
        if len(supplies) != len(set(supplies)):
            raise ValueError(f"{path}: composition supplies duplicate placeholders")
        match = _ASSET_REF_RE.fullmatch(asset_ref)
        assert match is not None
        entry = catalog.entries[match.group(1)]
        if set(supplies) != set(entry.placeholders):
            raise ValueError(
                f"{path}: composition supplies do not match asset placeholders"
            )
        return Composition(value["source_role"], supplies)

    composition: dict[str, Composition] = {}
    for physical_id, raw_composition in _object(
        document.get("composition", {}), f"{path}.composition"
    ).items():
        if physical_id not in records:
            raise ValueError(f"{path}: composition describes an unbound record")
        composition[physical_id] = load_composition(
            raw_composition,
            f"{path}.composition.{physical_id}",
            records[physical_id],
        )

    additional_uses: dict[str, tuple[AdditionalUse, ...]] = {}
    for physical_id, raw_uses in _object(
        document.get("additional_uses", {}), f"{path}.additional_uses"
    ).items():
        if physical_id not in records:
            raise ValueError(f"{path}: additional use describes an unbound record")
        if not isinstance(raw_uses, list) or not raw_uses:
            raise ValueError(f"{path}.additional_uses.{physical_id} must be a list")
        uses: list[AdditionalUse] = []
        selectors: set[tuple[str, str | None]] = set()
        for index, raw_use in enumerate(raw_uses):
            context = f"{path}.additional_uses.{physical_id}[{index}]"
            use = _object(raw_use, context)
            _fields(use, {"asset"}, context, optional={"variant", "composition"})
            asset_ref = use["asset"]
            if not isinstance(asset_ref, str):
                raise ValueError(f"{context}.asset must be an asset reference")
            field = catalog.field(asset_ref)
            variant = use.get("variant")
            if variant is not None:
                variant = _identifier(variant, f"{context}.variant")
                field.resolve(variant)
            selector = (asset_ref, variant)
            if selector == (records[physical_id], variants.get(physical_id)):
                raise ValueError(f"{context} duplicates the primary record use")
            if selector in selectors:
                raise ValueError(f"{context} duplicates another additional use")
            selectors.add(selector)
            use_composition = (
                load_composition(
                    use["composition"],
                    f"{context}.composition",
                    asset_ref,
                )
                if "composition" in use
                else None
            )
            uses.append(AdditionalUse(asset_ref, variant, use_composition))
        additional_uses[physical_id] = tuple(uses)

    reference_normalization = document.get("reference_normalization")
    if reference_normalization not in {None, "layout_blank"}:
        raise ValueError(f"{path}: unknown reference normalization")

    glyph_equivalence: dict[str, str] = {}
    for code, character in _object(
        document.get("glyph_equivalence", {}), f"{path}.glyph_equivalence"
    ).items():
        if not isinstance(code, str) or _GLYPH_CODE_RE.fullmatch(code) is None:
            raise ValueError(
                f"{path}.glyph_equivalence keys must be lowercase two- or "
                "four-digit hex"
            )
        if not isinstance(character, str) or len(character) != 1:
            raise ValueError(
                f"{path}.glyph_equivalence.{code} must be one character"
            )
        glyph_equivalence[code] = character

    glyph_tokens: dict[str, str] = {}
    for code, token_name in _object(
        document.get("glyph_tokens", {}), f"{path}.glyph_tokens"
    ).items():
        if not isinstance(code, str) or _GLYPH_CODE_RE.fullmatch(code) is None:
            raise ValueError(
                f"{path}.glyph_tokens keys must be lowercase two- or "
                "four-digit hex"
            )
        if token_name not in _AUTHORED_SYMBOLS:
            choices = ", ".join(sorted(_AUTHORED_SYMBOLS))
            raise ValueError(
                f"{path}.glyph_tokens.{code} must be an authored symbol: {choices}"
            )
        if code in glyph_equivalence:
            raise ValueError(f"{path}: glyph code {code} has two equivalences")
        glyph_tokens[code] = token_name

    field_surfaces: dict[str, tuple[str, ...]] = {}
    bound_fields = {
        asset_ref.rsplit(".", 1)[1] for asset_ref in records.values()
    } | {
        use.asset_ref.rsplit(".", 1)[1]
        for uses in additional_uses.values()
        for use in uses
    }
    surface_catalog = load_surfaces()
    for field_name, raw_surfaces in _object(
        document.get("field_surfaces", {}), f"{path}.field_surfaces"
    ).items():
        _identifier(field_name, f"{path}.field_surfaces field")
        if field_name not in bound_fields:
            raise ValueError(f"{path}: field surface names an unbound field")
        if not isinstance(raw_surfaces, list) or not raw_surfaces:
            raise ValueError(f"{path}: field surfaces must be a nonempty list")
        if not all(isinstance(surface, str) for surface in raw_surfaces):
            raise ValueError(f"{path}: surface ids must be text")
        surfaces = tuple(raw_surfaces)
        if len(surfaces) != len(set(surfaces)):
            raise ValueError(f"{path}: field surfaces contain duplicates")
        for surface in surfaces:
            surface_catalog.surface(surface)
        field_surfaces[field_name] = surfaces

    record_surfaces: dict[str, tuple[str, ...]] = {}
    for physical_id, raw_surfaces in _object(
        document.get("record_surfaces", {}), f"{path}.record_surfaces"
    ).items():
        if physical_id not in records:
            raise ValueError(f"{path}: record surface names an unbound record")
        if not isinstance(raw_surfaces, list) or not raw_surfaces:
            raise ValueError(f"{path}: record surfaces must be a nonempty list")
        if not all(isinstance(surface, str) for surface in raw_surfaces):
            raise ValueError(f"{path}: surface ids must be text")
        surfaces = tuple(raw_surfaces)
        if len(surfaces) != len(set(surfaces)):
            raise ValueError(f"{path}: record surfaces contain duplicates")
        for surface in surfaces:
            surface_catalog.surface(surface)
        record_surfaces[physical_id] = surfaces

    unresolved: dict[str, str] = {}
    for physical_id, note in _object(
        document.get("unresolved", {}), f"{path}.unresolved"
    ).items():
        if physical_id not in records:
            raise ValueError(f"{path}: unresolved note describes an unbound record")
        if not isinstance(note, str) or not note:
            raise ValueError(f"{path}.unresolved.{physical_id} must be nonempty text")
        unresolved[physical_id] = note

    physical = (
        _physical_records(corpus_root)
        if physical_records is None
        else physical_records
    )
    unused_glyphs = set(glyph_equivalence) | set(glyph_tokens)

    def normalize_glyphs(value: str) -> str:
        tokens = []
        for token in parse_tokens(value):
            if (
                isinstance(token, Raw)
                and token.kind == "GLYPH"
                and token.width in {1, 2}
            ):
                code = f"{token.value:0{token.width * 2}x}"
                if code in glyph_equivalence:
                    unused_glyphs.discard(code)
                    tokens.append(Text(glyph_equivalence[code]))
                    continue
                if code in glyph_tokens:
                    unused_glyphs.discard(code)
                    tokens.append(Named(glyph_tokens[code]))
                    continue
            tokens.append(token)
        return format_tokens(tokens)

    for physical_id, asset_ref in records.items():
        try:
            physical_reference = physical[physical_id]
        except KeyError as error:
            raise ValueError(
                f"{path}: unknown physical record {physical_id!r}"
            ) from error
        reference, _translation, _reviewed = catalog.field(asset_ref).resolve(
            variants.get(physical_id)
        )
        normalized_reference = normalize_glyphs(physical_reference)
        if reference_normalization == "layout_blank":
            visible_source = physical_reference.replace("{n}", "").strip()
            if not visible_source:
                normalized_reference = ""
        if physical_id in composition:
            source_role = composition[physical_id].source_role
            matches = (
                reference.startswith(normalized_reference)
                if source_role == "prefix"
                else reference.endswith(normalized_reference)
            )
            if not normalized_reference or not matches:
                raise ValueError(
                    f"{path}: composed record {physical_id!r} is not a {source_role} of "
                    f"{asset_ref!r}"
                )
        elif normalized_reference != reference:
            raise ValueError(
                f"{path}: {physical_id!r} reference does not match {asset_ref!r}"
            )

        for use in additional_uses.get(physical_id, ()):
            use_reference, _translation, _reviewed = catalog.field(
                use.asset_ref
            ).resolve(use.variant)
            if use.composition is not None:
                source_role = use.composition.source_role
                matches = (
                    use_reference.startswith(normalized_reference)
                    if source_role == "prefix"
                    else use_reference.endswith(normalized_reference)
                )
                if not normalized_reference or not matches:
                    raise ValueError(
                        f"{path}: additional use {physical_id!r} is not a {source_role} "
                        f"of {use.asset_ref!r}"
                    )
            elif normalized_reference != use_reference:
                raise ValueError(
                    f"{path}: additional use {physical_id!r} does not match "
                    f"{use.asset_ref!r}"
                )

    if unused_glyphs:
        raise ValueError(
            f"{path}: unused glyph equivalence codes {sorted(unused_glyphs)}"
        )

    return AssetBinding(
        asset_path,
        MappingProxyType(records),
        MappingProxyType(variants),
        MappingProxyType(composition),
        MappingProxyType(additional_uses),
        reference_normalization,
        MappingProxyType(glyph_equivalence),
        MappingProxyType(glyph_tokens),
        MappingProxyType(field_surfaces),
        MappingProxyType(record_surfaces),
        MappingProxyType(unresolved),
    )
