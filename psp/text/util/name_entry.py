"""Canonical profile-entry text projected into the PSP NAME contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .event_packed import validate_printable_ascii


PSP_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PSP_ROOT.parent
CONFIG_PATH = PSP_ROOT / "text" / "config" / "name_entry.json"
ASSET_PATH = REPO_ROOT / "assets" / "text" / "ui" / "profile_entry.json"


@dataclass(frozen=True, slots=True)
class NameEntryGrid:
    key: str
    label: str
    rows: tuple[str, str]

    @property
    def characters(self) -> str:
        return "".join(self.rows)


@dataclass(frozen=True, slots=True)
class NameEntryField:
    key: str
    prompt: str
    max_length: int


@dataclass(frozen=True, slots=True)
class NameEntryText:
    grids: tuple[NameEntryGrid, NameEntryGrid, NameEntryGrid]
    fields: tuple[NameEntryField, NameEntryField, NameEntryField, NameEntryField, NameEntryField]
    prompt_confirm: str
    prompt_occupation: str
    label_occupation: str
    label_yes: str
    label_no: str
    occupations: tuple[str, str, str, str, str, str]
    default_city: str
    default_ward: str

    def grid(self, key: str) -> NameEntryGrid:
        try:
            return next(grid for grid in self.grids if grid.key == key)
        except StopIteration as error:
            raise KeyError(key) from error

    def field(self, key: str) -> NameEntryField:
        try:
            return next(field for field in self.fields if field.key == key)
        except StopIteration as error:
            raise KeyError(key) from error


def _document(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP name-entry input: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"invalid PSP name-entry input: {path}")
    return value


def _translation(entries: dict[str, object], key: str, *, maximum: int | None = None) -> str:
    entry = entries.get(key)
    text = entry.get("text") if isinstance(entry, dict) else None
    value = text.get("translation") if isinstance(text, dict) else None
    return validate_printable_ascii(value, f"PSP name-entry {key}", maximum=maximum)


def load_name_entry_text(
    asset_path: Path = ASSET_PATH,
    config_path: Path = CONFIG_PATH,
) -> NameEntryText:
    """Load the shared five-field NAME text without duplicating its codec."""

    config = _document(config_path)
    asset = _document(asset_path)
    entries = asset.get("entries")
    field_keys = config.get("field_keys")
    tab_keys = config.get("tab_keys")
    tab_labels = config.get("tab_labels")
    grid_rows = config.get("grid_rows")
    occupation_keys = config.get("occupation_keys")
    maximum = config.get("max_field_length")
    if (
        config.get("version") != 1
        or config.get("surface") != "name_entry"
        or asset.get("version") != 1
        or asset.get("kind") != "surface_catalog"
        or not isinstance(entries, dict)
        or field_keys != ["first", "last", "codename", "city", "ward"]
        or tab_keys != ["upper", "lower", "symbol"]
        or tab_labels != ["UPPER", "lower", "SYMBOL"]
        or not isinstance(grid_rows, list)
        or len(grid_rows) != 3
        or not isinstance(occupation_keys, list)
        or len(occupation_keys) != 6
        or maximum != 8
    ):
        raise ValueError("invalid PSP name-entry contract")

    grids: list[NameEntryGrid] = []
    for index, (key, label) in enumerate(zip(tab_keys, tab_labels, strict=True)):
        row_keys = grid_rows[index]
        if not isinstance(row_keys, list) or len(row_keys) != 2:
            raise ValueError("PSP name-entry grid layout changed")
        rows = tuple(_translation(entries, row_key, maximum=13) for row_key in row_keys)
        if len(set("".join(rows))) != len("".join(rows)):
            raise ValueError(f"PSP name-entry {key} grid repeats characters")
        actual_label = _translation(entries, f"tab_{key}")
        if actual_label != label:
            raise ValueError(f"PSP name-entry {key} tab label changed")
        grids.append(NameEntryGrid(key, label, (rows[0], rows[1])))

    fields = tuple(
        NameEntryField(key, _translation(entries, f"prompt_{key}"), maximum)
        for key in field_keys
    )
    prompt_occupation = _translation(entries, "prompt_occupation")
    label_occupation = _translation(entries, "label_occupation")
    if prompt_occupation != label_occupation:
        raise ValueError("PSP name-entry occupation labels diverged")
    occupations = tuple(_translation(entries, key) for key in occupation_keys)
    return NameEntryText(
        grids=(grids[0], grids[1], grids[2]),
        fields=(fields[0], fields[1], fields[2], fields[3], fields[4]),
        prompt_confirm=_translation(entries, "prompt_confirm"),
        prompt_occupation=prompt_occupation,
        label_occupation=label_occupation,
        label_yes=_translation(entries, "label_yes"),
        label_no=_translation(entries, "label_no"),
        occupations=(occupations[0], occupations[1], occupations[2], occupations[3], occupations[4], occupations[5]),
        default_city=_translation(entries, "default_city", maximum=maximum),
        default_ward=_translation(entries, "default_ward", maximum=maximum),
    )


__all__ = ["ASSET_PATH", "CONFIG_PATH", "NameEntryField", "NameEntryGrid", "NameEntryText", "load_name_entry_text"]
