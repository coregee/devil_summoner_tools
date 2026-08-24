"""Canonical shared text projected onto the PSP two-dimensional map."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .event_packed import validate_printable_ascii


PSP_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PSP_ROOT.parent
CONFIG_PATH = PSP_ROOT / "text" / "config" / "map2d.json"
UI_ASSET_PATH = REPO_ROOT / "assets" / "text" / "ui" / "map_2d.json"
FIELD_ASSET_PATH = REPO_ROOT / "assets" / "text" / "field" / "messages.json"
LOCATION_ASSET_PATH = REPO_ROOT / "assets" / "text" / "locations.json"


@dataclass(frozen=True, slots=True)
class Map2dText:
    locations: tuple[str, str, str, str, str]
    talk_prompt: str
    label_yes: str
    label_no: str

    @property
    def runtime_records(self) -> tuple[str, str, str]:
        return self.talk_prompt, self.label_yes, self.label_no


def _document(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP MAP2D input: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"invalid PSP MAP2D input: {path}")
    return value


def _translation(entries: dict[str, object], key: str, field: str) -> str:
    entry = entries.get(key)
    record = entry.get(field) if isinstance(entry, dict) else None
    value = record.get("translation") if isinstance(record, dict) else None
    return validate_printable_ascii(value, f"PSP MAP2D {key}.{field}")


def load_map2d_text(
    config_path: Path = CONFIG_PATH,
    ui_path: Path = UI_ASSET_PATH,
    field_path: Path = FIELD_ASSET_PATH,
    location_path: Path = LOCATION_ASSET_PATH,
) -> Map2dText:
    """Load MAP2D wording by semantic identity, without a private corpus."""

    config = _document(config_path)
    ui = _document(ui_path)
    field = _document(field_path)
    location = _document(location_path)
    ui_entries = ui.get("entries")
    field_entries = field.get("entries")
    location_entries = location.get("entries")
    fixed = config.get("fixed_locations")
    runtime = config.get("runtime_records")
    if (
        config.get("version") != 1
        or config.get("surface") != "map_2d"
        or config.get("dynamic_templates")
        != ["city_label", "world_city_label", "world_ward_label", "area_label"]
        or runtime != ["talk_prompt", "talk_choice_yes", "talk_choice_no"]
        or not isinstance(fixed, list)
        or len(fixed) != 5
        or any(
            document.get("version") != 1
            or document.get("kind") not in {"surface_catalog", "entity_catalog"}
            for document in (ui, field, location)
        )
        or not all(
            isinstance(entries, dict)
            for entries in (ui_entries, field_entries, location_entries)
        )
    ):
        raise ValueError("invalid PSP MAP2D semantic contract")
    for key in config["dynamic_templates"]:
        _translation(ui_entries, key, "text")

    locations = []
    for row in fixed:
        if not isinstance(row, dict) or set(row) not in (
            {"key", "field"},
            {"key", "field", "variant"},
        ):
            raise ValueError("invalid PSP MAP2D fixed-location binding")
        entry = location_entries.get(row["key"])
        record = entry.get(row["field"]) if isinstance(entry, dict) else None
        if "variant" in row:
            variants = record.get("variants") if isinstance(record, dict) else None
            variant = variants.get(row["variant"]) if isinstance(variants, dict) else None
            value = variant.get("translation") if isinstance(variant, dict) else None
            locations.append(
                validate_printable_ascii(value, "PSP MAP2D location variant")
            )
        else:
            locations.append(_translation(location_entries, row["key"], row["field"]))
    values = [_translation(field_entries, key, "text") for key in runtime]
    return Map2dText(tuple(locations), values[0], values[1], values[2])  # type: ignore[arg-type]


__all__ = [
    "CONFIG_PATH",
    "FIELD_ASSET_PATH",
    "LOCATION_ASSET_PATH",
    "UI_ASSET_PATH",
    "Map2dText",
    "load_map2d_text",
]
