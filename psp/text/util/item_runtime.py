"""Source-pinned semantic text for the three PSP-only active items."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


PSP_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PSP_ROOT.parent
CONFIG_PATH = PSP_ROOT / "text" / "config" / "item_runtime.json"
ASSET_PATH = REPO_ROOT / "assets" / "text" / "items_psp.json"
ITEM_RUNTIME_GAME_IDS = (255, 280, 281)


@dataclass(frozen=True, slots=True)
class ItemRuntimeTextRecord:
    record_index: int
    game_id: int
    asset: str
    name: str
    description: str
    post_terminator_tail: str | None
    source_metadata: bytes
    source_name: bytes
    source_description: bytes


@dataclass(frozen=True, slots=True)
class ItemRuntimeTextSource:
    records: tuple[ItemRuntimeTextRecord, ...]
    source_member_sha256: str

    def record(self, game_id: int) -> ItemRuntimeTextRecord:
        return next(record for record in self.records if record.game_id == game_id)


def _document(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP item-runtime input: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"invalid PSP item-runtime input: {path}")
    return value


def load_item_runtime_text(source_member: bytes) -> ItemRuntimeTextSource:
    config = _document(CONFIG_PATH)
    assets = _document(ASSET_PATH)
    source = config.get("source")
    layout = config.get("layout")
    rows = config.get("records")
    entries = assets.get("entries")
    if (
        config.get("version") != 1
        or config.get("surface") != "psp_active_items"
        or assets.get("version") != 1
        or assets.get("kind") != "entity_catalog"
        or not isinstance(source, dict)
        or not isinstance(layout, dict)
        or not isinstance(rows, list)
        or not isinstance(entries, dict)
        or tuple(row.get("game_id") for row in rows if isinstance(row, dict))
        != ITEM_RUNTIME_GAME_IDS
    ):
        raise ValueError("invalid PSP item-runtime contract")
    if (
        not isinstance(source_member, bytes)
        or len(source_member) != source.get("member_size")
        or hashlib.sha256(source_member).hexdigest() != source.get("member_sha256")
    ):
        raise ValueError("PSP item-runtime ITEMNAME member changed")

    record_size = layout.get("record_size")
    records = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(record_size, int):
            raise ValueError("invalid PSP item-runtime row")
        game_id = row["game_id"]
        index = row["record_index"]
        if index != game_id - 1:
            raise ValueError(f"PSP item-runtime game ID {game_id} moved")
        raw = source_member[index * record_size : (index + 1) * record_size]
        if hashlib.sha256(raw).hexdigest() != row["source_record_sha256"]:
            raise ValueError(f"PSP item-runtime game ID {game_id} source row changed")
        metadata = raw[:4]
        source_name = raw[4:20]
        source_description = raw[20:104]
        if metadata.hex() != row["source_metadata_hex"] or source_name.hex() != row["source_name_hex"]:
            raise ValueError(f"PSP item-runtime game ID {game_id} field pin changed")
        entry = entries.get(row["asset"])
        if not isinstance(entry, dict):
            raise ValueError(f"PSP item-runtime game ID {game_id} asset is missing")
        name_field, description_field = entry.get("name"), entry.get("description")
        if not isinstance(name_field, dict) or not isinstance(description_field, dict):
            raise ValueError(f"PSP item-runtime game ID {game_id} asset is invalid")
        name = name_field.get("translation")
        description = description_field.get("translation")
        if not isinstance(name, str) or not name or not isinstance(description, str) or not description:
            raise ValueError(f"PSP item-runtime game ID {game_id} translation is empty")
        tail = None
        if description.count("[END]") > 1:
            raise ValueError("PSP item-runtime description repeats [END]")
        if "[END]" in description:
            description, tail = (part.strip() for part in description.split("[END]", 1))
            if not description or not tail:
                raise ValueError("PSP item-runtime [END] separator is invalid")
        records.append(ItemRuntimeTextRecord(index, game_id, row["asset"], name.strip(), description.replace("{n}", "\n"), None if tail is None else tail.replace("{n}", "\n"), metadata, source_name, source_description))
    return ItemRuntimeTextSource(tuple(records), hashlib.sha256(source_member).hexdigest())


__all__ = ["ASSET_PATH", "CONFIG_PATH", "ITEM_RUNTIME_GAME_IDS", "ItemRuntimeTextRecord", "ItemRuntimeTextSource", "load_item_runtime_text"]
