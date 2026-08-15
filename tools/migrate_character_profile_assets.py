"""Checked migration of character and profile-entry text into shared assets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MATURE_ROOT = ROOT.parent / "smtds_en"

MATURE_CHARACTERS = (
    MATURE_ROOT
    / "shared"
    / "text"
    / "corpus"
    / "shared"
    / "names"
    / "characters.json"
)
MATURE_STATIC = (
    MATURE_ROOT
    / "shared"
    / "text"
    / "corpus"
    / "name_entry"
    / "static_text.json"
)
MATURE_RUNTIME = MATURE_STATIC.with_name("ui_terms.json")

CORPUS_ROOT = ROOT / "saturn" / "text" / "corpus" / "game"
PHYSICAL_CHARACTERS = CORPUS_ROOT / "fixed" / "charname.json"
PHYSICAL_STATIC = CORPUS_ROOT / "addressed" / "name_static.json"

ASSET_ROOT = ROOT / "assets" / "text"
BINDING_ROOT = ROOT / "saturn" / "text" / "bindings"

CHARACTER_KEYS = (
    "hajime_tanigawa",
    "rei_reiho",
    "kyouji_kuzunoha",
    "taro_tanigawa",
    "jiro_tanigawa",
    "saburo_tanigawa",
)

STATIC_KINDS = (
    "prompt_first",
    "prompt_last",
    "prompt_codename",
    "prompt_city",
    "prompt_ward",
    "prompt_confirm",
    "label_yes",
    "label_no",
    "prompt_occupation",
    "label_occupation",
    "tab_upper",
    "tab_lower",
    "tab_symbol",
    "occupation_employee",
    "occupation_student",
    "occupation_official",
    "occupation_part_time",
    "occupation_business",
    "occupation_jobless",
)

STATIC_PHYSICAL_IDS = (
    "game.name_static.o020b78.prompt_first",
    "game.name_static.o020b78.prompt_last",
    "game.name_static.o020ba0",
    "game.name_static.o020bc8.prompt_city",
    "game.name_static.o020bc8.prompt_ward",
    "game.name_static.o020c18",
    "game.name_static.o020c30",
    "game.name_static.o020c38",
    "game.name_static.o020cb8.prompt_occupation",
    "game.name_static.o020cb8.label_occupation",
    "game.name_static.o020c40",
    "game.name_static.o020c68",
    "game.name_static.o020dd0",
    "game.name_static.o020ce0",
    "game.name_static.o020d08",
    "game.name_static.o020d30",
    "game.name_static.o020d58",
    "game.name_static.o020d80",
    "game.name_static.o020da8",
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def field(reference: str, translation: str, *, note: str | None = None) -> dict:
    value = {"reference": reference, "translation": translation}
    if note is not None:
        value["note"] = note
    return value


def migrate_characters() -> None:
    mature = read_json(MATURE_CHARACTERS)
    physical = read_json(PHYSICAL_CHARACTERS)
    if len(mature) != len(physical) or len(mature) != len(CHARACTER_KEYS):
        raise ValueError("unexpected CHARNAME inventory")
    if [row["reference"] for row in physical] != [row["jp"] for row in mature]:
        raise ValueError("mature CHARNAME references differ from physical corpus")
    if [row["id"] for row in physical] != [
        f"game.charname.o{index * 8:06x}.text" for index in range(6)
    ]:
        raise ValueError("physical CHARNAME identities changed")
    if any(
        not row["tr"] or row["reviewed"] or row["excluded"] for row in mature
    ):
        raise ValueError("mature CHARNAME translation state changed")

    entries: dict[str, dict] = {}
    for key, row in zip(CHARACTER_KEYS, mature, strict=True):
        entries[key] = {"name": field(row["jp"], row["tr"])}
    entries["hajime_tanigawa"]["note"] = (
        "Stock initial CHARNAME row. Live player-name consumers use the current "
        "profile value rather than treating this row as immutable."
    )

    # These are visible forms consumed directly by the mature Saturn battle
    # renderer. They belong beside the character, not as Python literals.
    entries["kyouji_kuzunoha"].update(
        {
            "full_name": field("葛葉キョウジ", "Kyouji Kuzunoha"),
            "given_name": field("キョウジ", "Kyouji"),
            "family_name": field("葛葉", "Kuzunoha"),
            "battle_test_name": field("葛葉キョウジ", "Kyouji"),
        }
    )
    entries["rei_reiho"]["battle_test_name"] = field("レイ", "Rei")

    asset = {"version": 1, "kind": "entity_catalog", "entries": entries}
    binding = {
        "version": 1,
        "asset": "characters.json",
        "records": {
            row["id"]: f"{key}.name"
            for key, row in zip(CHARACTER_KEYS, physical, strict=True)
        },
        "field_surfaces": {
            "name": [
                "event.dialogue",
                "party.character_name",
                "status.character_name",
                "level_up.character_name",
                "fusion.table_character_name",
                "shop.character_name",
                "bar.status_name",
                "healer.member_name",
                "battle.result_name",
            ]
        },
    }
    write_json(ASSET_ROOT / "characters.json", asset)
    write_json(BINDING_ROOT / "characters.json", binding)


def migrate_profile_entry() -> None:
    mature = read_json(MATURE_STATIC)
    runtime = read_json(MATURE_RUNTIME)
    physical = read_json(PHYSICAL_STATIC)
    if len(mature) != len(physical) or len(mature) != len(STATIC_KINDS):
        raise ValueError("unexpected NAME.BIN static inventory")
    if tuple(row["kind"] for row in mature) != STATIC_KINDS:
        raise ValueError("mature NAME.BIN semantic order changed")
    if tuple(row["id"] for row in physical) != STATIC_PHYSICAL_IDS:
        raise ValueError("physical NAME.BIN identities changed")
    if [row["reference"] for row in physical] != [row["jp"] for row in mature]:
        raise ValueError("mature NAME.BIN references differ from physical corpus")
    if any(
        not row["tr"] or row["reviewed"] or row["excluded"] for row in mature
    ):
        raise ValueError("mature NAME.BIN translation state changed")

    entries = {
        row["kind"]: {"text": field(row["jp"], row["tr"])} for row in mature
    }

    tabs = runtime.get("tabs")
    defaults = runtime.get("defaults")
    expected_tabs = (
        ("upper", ("ABCDEFGHIJKLM", "NOPQRSTUVWXYZ")),
        ("lower", ("abcdefghijklm", "nopqrstuvwxyz")),
        ("symbol", ("0123456789.,'", "-!?/&: ")),
    )
    if not isinstance(tabs, list) or len(tabs) != len(expected_tabs):
        raise ValueError("unexpected mature name-entry grid inventory")
    for tab, (expected_key, expected_rows) in zip(tabs, expected_tabs, strict=True):
        if tab != {"key": expected_key, "rows": list(expected_rows)}:
            raise ValueError(f"mature {expected_key} name-entry grid changed")
        for index, row in enumerate(expected_rows, start=1):
            entries[f"grid_{expected_key}_row_{index}"] = {
                "text": field(
                    row,
                    row,
                    note=(
                        "The final space is a selectable blank input cell."
                        if expected_key == "symbol" and index == 2
                        else "English replacement input-grid content."
                    ),
                )
            }
    if defaults != {"city": "Hirasaki", "ward": "Asahi"}:
        raise ValueError("mature name-entry defaults changed")
    entries["default_city"] = {
        "text": field("平崎", defaults["city"], note="Initial city value.")
    }
    entries["default_ward"] = {
        "text": field("朝日", defaults["ward"], note="Initial ward value.")
    }
    entries["grid_end"] = {
        "text": field(
            "END",
            "END",
            note="Visible command glyph used to accept the current input field.",
        )
    }

    asset = {"version": 1, "kind": "surface_catalog", "entries": entries}
    records = {
        physical_id: f"{kind}.text"
        for physical_id, kind in zip(STATIC_PHYSICAL_IDS, STATIC_KINDS, strict=True)
    }
    prompt_ids = STATIC_PHYSICAL_IDS[0:5] + (STATIC_PHYSICAL_IDS[8],)
    occupation_ids = STATIC_PHYSICAL_IDS[13:19]
    binding = {
        "version": 1,
        "asset": "ui/profile_entry.json",
        "records": records,
        "record_surfaces": {
            **{physical_id: ["name_entry.prompt"] for physical_id in prompt_ids},
            STATIC_PHYSICAL_IDS[5]: ["name_entry.confirm_prompt"],
            STATIC_PHYSICAL_IDS[6]: ["name_entry.confirm_choice"],
            STATIC_PHYSICAL_IDS[7]: ["name_entry.confirm_choice"],
            STATIC_PHYSICAL_IDS[9]: ["name_entry.summary_label"],
            STATIC_PHYSICAL_IDS[10]: ["name_entry.tab_label"],
            STATIC_PHYSICAL_IDS[11]: ["name_entry.tab_label"],
            STATIC_PHYSICAL_IDS[12]: ["name_entry.tab_label"],
            **{
                physical_id: ["name_entry.occupation_choice"]
                for physical_id in occupation_ids
            },
        },
    }
    write_json(ASSET_ROOT / "ui" / "profile_entry.json", asset)
    write_json(BINDING_ROOT / "profile_entry.json", binding)


def main() -> None:
    migrate_characters()
    migrate_profile_entry()


if __name__ == "__main__":
    main()
