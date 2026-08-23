"""Canonical PSP savedata utility and SFO-detail text."""

from __future__ import annotations

import json
import string
from dataclasses import dataclass
from pathlib import Path

from .event_packed import validate_printable_ascii


PSP_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PSP_ROOT.parent
CONFIG_PATH = PSP_ROOT / "text" / "config" / "savedata.json"
SAVE_ASSET_PATH = REPO_ROOT / "assets" / "text" / "save_load.json"
LOCATION_ASSET_PATH = REPO_ROOT / "assets" / "text" / "locations.json"


@dataclass(frozen=True, slots=True)
class SavedataText:
    game_title: str
    slot_title: str
    detail_template: str
    detail_title: str
    difficulties: tuple[str, str]
    cancel_load: str
    cancel_save: str
    unknown: str
    home: str
    office: str
    locations: tuple[str, ...]


def _document(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP savedata input: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"invalid PSP savedata input: {path}")
    return value


def _translation(entries: dict[str, object], key: str, field: str = "text") -> str:
    entry = entries.get(key)
    value = entry.get(field) if isinstance(entry, dict) else None
    translation = value.get("translation") if isinstance(value, dict) else None
    return validate_printable_ascii(translation, f"PSP savedata {key}.{field}")


def _detail_template(value: object, expected_placeholders: list[object]) -> tuple[str, str]:
    if not isinstance(value, str) or not value:
        raise ValueError("PSP savedata detail template must be nonempty text")
    fields = [
        name
        for _literal, name, _format, _conversion in string.Formatter().parse(value)
        if name and name != "n"
    ]
    if fields != expected_placeholders:
        raise ValueError("PSP savedata detail placeholder order changed")
    lines = value.split("{n}")
    if len(lines) != 3 or fields != ["codename", "level", "difficulty", "location", "hours", "minutes"]:
        raise ValueError("PSP savedata detail layout changed")
    if lines[1] != "{codename} Lv. {level} ({difficulty})" or lines[2] != "{location} ({hours}:{minutes})":
        raise ValueError("PSP savedata detail punctuation changed")
    return value, validate_printable_ascii(lines[0], "PSP savedata detail title")


def load_savedata_text(
    save_path: Path = SAVE_ASSET_PATH,
    location_path: Path = LOCATION_ASSET_PATH,
    config_path: Path = CONFIG_PATH,
) -> SavedataText:
    """Load canonical prose for the system-ASCII savedata formatter."""

    config = _document(config_path)
    save = _document(save_path)
    location = _document(location_path)
    save_entries = save.get("entries")
    location_entries = location.get("entries")
    location_keys = config.get("location_keys")
    special = config.get("special_locations")
    placeholders = config.get("detail_placeholders")
    if (
        config.get("version") != 1
        or config.get("surface") != "savedata"
        or save.get("version") != 1
        or save.get("kind") != "surface_catalog"
        or location.get("version") != 1
        or location.get("kind") != "entity_catalog"
        or not isinstance(save_entries, dict)
        or not isinstance(location_entries, dict)
        or not isinstance(location_keys, list)
        or len(location_keys) != 24
        or len(set(location_keys)) != 24
        or special != {"home": "home", "office": "detective_agency"}
        or not isinstance(placeholders, list)
    ):
        raise ValueError("invalid PSP savedata contract")

    detail_entry = save_entries.get("psp_detail")
    detail_text = detail_entry.get("text") if isinstance(detail_entry, dict) else None
    detail_template, detail_title = _detail_template(
        detail_text.get("translation") if isinstance(detail_text, dict) else None,
        placeholders,
    )
    locations = tuple(_translation(location_entries, key, "name") for key in location_keys)
    return SavedataText(
        game_title=_translation(save_entries, "psp_game_title"),
        slot_title=_translation(save_entries, "psp_slot_title"),
        detail_template=detail_template,
        detail_title=detail_title,
        difficulties=(
            _translation(save_entries, "psp_difficulty_normal"),
            _translation(save_entries, "psp_difficulty_hard"),
        ),
        cancel_load=_translation(save_entries, "psp_cancel_load"),
        cancel_save=_translation(save_entries, "psp_cancel_save"),
        unknown=_translation(save_entries, "psp_unknown_location"),
        home=_translation(location_entries, special["home"], "save_name"),
        office=_translation(location_entries, special["office"], "save_name"),
        locations=locations,
    )


__all__ = ["CONFIG_PATH", "LOCATION_ASSET_PATH", "SAVE_ASSET_PATH", "SavedataText", "load_savedata_text"]
