"""Checked migration of mature negotiation text into shared assets."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MATURE_ROOT = ROOT.parent / "smtds_en"

MATURE_DIALOGUE_ROOT = (
    MATURE_ROOT
    / "shared"
    / "text"
    / "corpus"
    / "event_window"
    / "demon_negotiation"
)
MATURE_CONDITIONS = (
    MATURE_ROOT
    / "shared"
    / "text"
    / "corpus"
    / "battle"
    / "condition_messages.json"
)
MATURE_BINDING_ROOT = MATURE_ROOT / "saturn" / "text" / "bindings" / "eve"

PHYSICAL_DIALOGUE_ROOT = ROOT / "saturn" / "text" / "corpus" / "game" / "eve"
PHYSICAL_CONDITIONS = (
    ROOT
    / "saturn"
    / "text"
    / "corpus"
    / "game"
    / "fixed"
    / "combat_condition_messages.json"
)
ASSET_ROOT = ROOT / "assets" / "text" / "negotiation"
BINDING_ROOT = ROOT / "saturn" / "text" / "bindings"


@dataclass(frozen=True, slots=True)
class Bank:
    source: str
    asset: str
    authored_count: int
    physical_count: int
    glyph_equivalence: tuple[tuple[str, str], ...] = ()


BANKS = (
    Bank("tlk_bst", "beast", 549, 599),
    Bank("kemo", "feral", 647, 814),
    Bank("tlk_kofu", "archaic", 546, 573),
    Bank("nbl_m", "nobleman", 639, 767),
    Bank("tlk_hirk", "highborn_lady", 554, 600),
    Bank("tlk_yngm", "young_man", 587, 637),
    Bank("grl", "girl", 676, 795),
    Bank("tlk_boy", "boy", 539, 581),
    Bank("cld_f", "little_girl", 610, 723, (("00c0", "□"),)),
    Bank("tlk_lady", "lady", 550, 620),
    Bank("tlk_crzy", "manic", 525, 590),
    Bank("jijy", "old_man", 511, 743),
    Bank("cyni", "cynical", 558, 798),
    Bank("tlk_west", "kansai", 533, 583),
    Bank("slm", "slime", 394, 481),
)

PLACEHOLDER_TYPES = {
    "codename": "player_codename",
    "demon_name": "demon_name",
    "kyouji_name": "character_name",
    "offered_item": "item_name",
    "race": "demon_race",
    "rei_name": "character_name",
    "requested_item": "item_name",
}
NON_PLACEHOLDER_NAMES = {"BEAT", "WAIT", "maru_symbol", "n"}
NAMED_TOKEN_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
SHORT_GLYPH_RE = re.compile(r"\{([0-9A-Fa-f]{1,4})\}")
RECORD_REFERENCE_RE = re.compile(
    r"\brecords?(?:\s+are)?\s+"
    r"((?:\d{1,4}(?:-\d{1,4})?)"
    r"(?:(?:\s*,\s*|\s+and\s+)\d{1,4}(?:-\d{1,4})?)*)"
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def canonicalize_text(value: str) -> str:
    value = SHORT_GLYPH_RE.sub(
        lambda match: f"{{GLYPH:{int(match.group(1), 16):04x}}}",
        value,
    )
    return value.replace("{white_square}", "□")


def dialogue_key(source: str, record_id: str) -> str:
    match = re.fullmatch(
        rf"ds\.eve\.{re.escape(source)}_eve\.r(\d{{6}})", record_id
    )
    if match is None:
        raise ValueError(f"unexpected {source} record id {record_id!r}")
    return f"dialogue_{int(match.group(1)):04d}"


def _rewrite_cynical_note(note: str) -> str:
    if note.startswith(
        "Opening fragment; the shared page-one record 154 completes messages"
    ):
        note = note.replace(
            "Opening fragment; the shared page-one record 154 completes messages "
            "304, 305, and 307 with:",
            "Shared opening fragment; dialogue_0154 completes three negotiation "
            "branches with:",
        )
    note = re.sub(r" fragment for message \d+;", " fragment;", note)
    note = re.sub(
        r"\b\d+\b",
        lambda match: f"dialogue_{int(match.group(0)):04d}",
        note,
    )
    return re.sub(r"\brecords? (?=dialogue_)", "", note)


def rewrite_note(source: str, note: str) -> str:
    if source == "cyni":
        return _rewrite_cynical_note(note)

    def replace_record_clause(match: re.Match[str]) -> str:
        return re.sub(
            r"\d{1,4}",
            lambda number: f"dialogue_{int(number.group(0)):04d}",
            match.group(1),
        )

    return RECORD_REFERENCE_RE.sub(replace_record_clause, note)


def asset_entry(source: str, row: dict[str, Any]) -> dict[str, Any]:
    reference = canonicalize_text(row["jp"])
    translation = canonicalize_text(row["tr"])
    names = {
        name
        for value in (reference, translation)
        for name in NAMED_TOKEN_RE.findall(value)
        if name not in NON_PLACEHOLDER_NAMES
    }
    unknown = names - PLACEHOLDER_TYPES.keys()
    if unknown:
        raise ValueError(
            f"unclassified {source} placeholders: {sorted(unknown)}"
        )

    field: dict[str, Any] = {
        "reference": reference,
        "translation": translation,
    }
    if row.get("reviewed"):
        field["reviewed"] = True
    if row.get("note"):
        field["note"] = rewrite_note(source, row["note"])

    entry: dict[str, Any] = {}
    if names:
        entry["placeholders"] = {
            name: PLACEHOLDER_TYPES[name] for name in sorted(names)
        }
    entry["text"] = field
    return entry


def normalize_physical_reference(bank: Bank, value: str) -> str:
    normalized = canonicalize_text(value)
    for code, character in bank.glyph_equivalence:
        normalized = normalized.replace(f"{{GLYPH:{code}}}", character)
    return normalized


def migrate_bank(
    bank: Bank,
    conditions: list[dict[str, Any]],
    physical_conditions: list[dict[str, Any]],
) -> tuple[int, int]:
    dialogue = read_json(MATURE_DIALOGUE_ROOT / f"{bank.source}.json")
    mature_binding = read_json(
        MATURE_BINDING_ROOT / f"{bank.source.upper()}.EVE.json"
    )
    physical_dialogue = read_json(
        PHYSICAL_DIALOGUE_ROOT / f"{bank.source}.json"
    )

    if len(dialogue) != bank.authored_count:
        raise ValueError(f"unexpected {bank.source} authored inventory")
    if len(physical_dialogue) != bank.physical_count:
        raise ValueError(f"unexpected {bank.source} physical inventory")

    dialogue_by_id = {row["id"]: row for row in dialogue}
    if len(dialogue_by_id) != len(dialogue):
        raise ValueError(f"duplicate mature {bank.source} record id")
    physical_dialogue_by_id = {row["id"]: row for row in physical_dialogue}

    entries: dict[str, dict[str, Any]] = {
        dialogue_key(bank.source, row["id"]): asset_entry(bank.source, row)
        for row in dialogue
    }
    records: dict[str, str] = {}
    seen_physical: set[str] = set()
    for message in mature_binding["messages"]:
        message_index = message["index"]
        for page in message["pages"]:
            physical_id = (
                f"game.{bank.source}.m{message_index:04d}.p{page['index']:02d}"
            )
            if physical_id in seen_physical:
                raise ValueError(f"duplicate physical id {physical_id}")
            seen_physical.add(physical_id)
            try:
                physical_row = physical_dialogue_by_id[physical_id]
                mature_row = dialogue_by_id[page["record_id"]]
            except KeyError as error:
                raise ValueError(f"unresolved page {physical_id}") from error
            if normalize_physical_reference(
                bank, physical_row["reference"]
            ) != canonicalize_text(mature_row["jp"]):
                raise ValueError(f"reference mismatch at {physical_id}")
            records[physical_id] = (
                f"{dialogue_key(bank.source, mature_row['id'])}.text"
            )

    if seen_physical != set(physical_dialogue_by_id):
        raise ValueError(f"mature binding does not cover {bank.source}")
    if len(set(records.values())) != bank.authored_count:
        raise ValueError(f"{bank.source} fan-out misses authored dialogue")

    condition_count = 0
    for mature_row, physical_row in zip(
        conditions, physical_conditions, strict=True
    ):
        kind = mature_row["kind"]
        if not kind.endswith(f"_{bank.source}"):
            continue
        if canonicalize_text(mature_row["jp"]) != canonicalize_text(
            physical_row["reference"]
        ):
            raise ValueError(f"condition reference mismatch for {kind}")
        key = f"condition_{kind.removesuffix(f'_{bank.source}')}"
        if key in entries:
            raise ValueError(f"duplicate asset key {key}")
        entries[key] = asset_entry(bank.source, mature_row)
        records[physical_row["id"]] = f"{key}.text"
        condition_count += 1

    if condition_count != 7:
        raise ValueError(f"unexpected {bank.source} condition inventory")

    for entry in entries.values():
        note = entry["text"].get("note", "")
        for target in re.findall(r"dialogue_\d{4}", note):
            if target not in entries:
                raise ValueError(f"note references unknown {bank.asset} key {target}")

    write_json(
        ASSET_ROOT / f"{bank.asset}.json",
        {"version": 1, "kind": "surface_catalog", "entries": entries},
    )
    binding: dict[str, Any] = {
        "version": 1,
        "asset": f"negotiation/{bank.asset}.json",
        "records": records,
    }
    if bank.glyph_equivalence:
        binding["glyph_equivalence"] = dict(bank.glyph_equivalence)
    binding["field_surfaces"] = {
        "text": ["battle.negotiation_dialogue"]
    }
    write_json(BINDING_ROOT / f"negotiation_{bank.asset}.json", binding)
    return len(entries), len(records)


def main() -> None:
    conditions = read_json(MATURE_CONDITIONS)
    physical_conditions = read_json(PHYSICAL_CONDITIONS)
    if len(conditions) != 113 or len(physical_conditions) != 113:
        raise ValueError("unexpected combat-condition inventory")

    totals = [
        migrate_bank(bank, conditions, physical_conditions) for bank in BANKS
    ]
    if sum(count for count, _edges in totals) != 8_523:
        raise ValueError("unexpected total negotiation asset inventory")
    if sum(edges for _count, edges in totals) != 10_009:
        raise ValueError("unexpected total negotiation binding inventory")


if __name__ == "__main__":
    main()
