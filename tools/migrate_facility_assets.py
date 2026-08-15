"""Checked migration of facility-facing Saturn text into shared assets."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MATURE_ROOT = ROOT.parent / "smtds_en"

MATURE_DIALOGUE = (
    MATURE_ROOT
    / "shared"
    / "text"
    / "corpus"
    / "event_window"
    / "shared"
    / "shops_and_fusion.json"
)
MATURE_PSP_SUPPLEMENT = (
    MATURE_DIALOGUE.parent / "psp" / "shops_and_fusion_supplement.json"
)
MATURE_EVE_BINDING = (
    MATURE_ROOT
    / "saturn"
    / "text"
    / "bindings"
    / "eve"
    / "SHOPSMP.EVE.json"
)
MATURE_SHOP_TERMS = (
    MATURE_ROOT / "shared" / "text" / "corpus" / "shop" / "ui_terms.json"
)
MATURE_HEALING_TERMS = (
    MATURE_ROOT / "shared" / "text" / "corpus" / "healing" / "ui_terms.json"
)
MATURE_FUSION_CONFIRMATION = (
    MATURE_ROOT
    / "shared"
    / "text"
    / "corpus"
    / "fusion"
    / "confirmation"
    / "text.json"
)
MATURE_SAVE = (
    MATURE_ROOT
    / "shared"
    / "text"
    / "corpus"
    / "save_load"
    / "save"
    / "static_text.json"
)
MATURE_LOAD = MATURE_SAVE.parents[1] / "load" / "static_text.json"
MATURE_CAPACITY = MATURE_LOAD.with_name("capacity.json")

CORPUS_ROOT = ROOT / "saturn" / "text" / "corpus" / "game"
PHYSICAL_DIALOGUE = CORPUS_ROOT / "eve" / "shopsmp.json"
PHYSICAL_ADDRESSED = CORPUS_ROOT / "addressed"
ASSET_ROOT = ROOT / "assets" / "text"
BINDING_ROOT = ROOT / "saturn" / "text" / "bindings"

SHORT_GLYPH_RE = re.compile(r"\{([0-9A-Fa-f]{1,4})\}")
NAMED_TOKEN_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
RECORD_ID_RE = re.compile(r"ds\.eve\.shopsmp_eve\.r(\d{6})\Z")
PHYSICAL_ID_RE = re.compile(r"game\.shopsmp\.m(\d{4})\.p(\d{2})\Z")

PLACEHOLDER_TYPES = {
    "city": "location_name",
    "demon_name": "demon_name",
    "drink_name": "drink_name",
    "event_id": "number",
    "first_name": "player_name",
    "item_name": "item_name",
    "last_name": "player_name",
    "race": "demon_race",
    "ward": "location_name",
}
NON_PLACEHOLDERS = {"BEAT", "WAIT", "maru_symbol", "n"}

DRINK_KEYS = (
    "crushed_ice",
    "spark_mixer",
    "cool_slider",
    "karuko_wine",
    "gin_bingara",
    "natural_high",
    "adrenal_pop",
    "megu_beer",
    "north_ethyl",
    "gum_syrup",
    "bio_liqueur",
    "metamol_mix",
    "ogre_juice",
    "neko_sake",
    "mach_citron",
    "demon_water",
)
PATRON_KEYS = (
    "master",
    "young_man",
    "white_lady",
    "pair_in_back",
    "young_lady",
    "corner_lady",
)
COMMON_KEYS = {
    "ds.eve.shopsmp_eve.r000006": "exit",
    "ds.eve.shopsmp_eve.r000094": "partner",
    "ds.eve.shopsmp_eve.r000234": "what_do_you_want",
    "ds.eve.shopsmp_eve.r000352": "leave",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def canonicalize(value: str) -> str:
    return SHORT_GLYPH_RE.sub(
        lambda match: f"{{GLYPH:{int(match.group(1), 16):04x}}}",
        value,
    )


def asset_entry(row: dict[str, Any]) -> dict[str, Any]:
    reference = canonicalize(row["jp"])
    translation = canonicalize(row["tr"])
    names = {
        name
        for value in (reference, translation)
        for name in NAMED_TOKEN_RE.findall(value)
        if name not in NON_PLACEHOLDERS
    }
    unknown = names - PLACEHOLDER_TYPES.keys()
    if unknown:
        raise ValueError(f"unclassified facility placeholders: {sorted(unknown)}")
    entry: dict[str, Any] = {}
    if names:
        entry["placeholders"] = {
            name: PLACEHOLDER_TYPES[name] for name in sorted(names)
        }
    field: dict[str, Any] = {
        "reference": reference,
        "translation": translation,
    }
    if row.get("reviewed"):
        field["reviewed"] = True
    if row.get("note"):
        field["note"] = row["note"]
    entry["text"] = field
    return entry


def line_key(record_id: str) -> str:
    match = RECORD_ID_RE.fullmatch(record_id)
    if match is None:
        raise ValueError(f"unexpected SHOPSMP record id {record_id!r}")
    return f"line_{int(match.group(1)):04d}"


def message_category(index: int) -> str:
    if (
        index == 0
        or 49 <= index <= 67
        or 659 <= index <= 674
        or 807 <= index <= 814
    ):
        return "debug"
    if 1 <= index <= 10 or 68 <= index <= 318:
        return "gouma_den"
    if (
        11 <= index <= 48
        or 319 <= index <= 589
        or 706 <= index <= 709
        or index == 714
        or 724 <= index <= 765
    ):
        return "shop"
    if 590 <= index <= 601 or 715 <= index <= 721 or 781 <= index <= 788:
        return "healer"
    if 602 <= index <= 603 or 710 <= index <= 713 or 766 <= index <= 780:
        return "mag_exchange"
    if 604 <= index <= 658 or 722 <= index <= 723 or 791 <= index <= 806:
        return "bar"
    if 675 <= index <= 705:
        return "demon_join"
    if 789 <= index <= 790:
        return "gym"
    raise ValueError(f"unclassified nonempty SHOPSMP message {index}")


def asset_path(category: str) -> str:
    return {
        "bar": "facilities/bar.json",
        "common": "facilities/common.json",
        "debug": "ui/debug.json",
        "demon_join": "field/demon_join.json",
        "gouma_den": "facilities/gouma_den.json",
        "gym": "facilities/gym.json",
        "healer": "facilities/healer.json",
        "mag_exchange": "facilities/mag_exchange.json",
        "shop": "facilities/shop.json",
    }[category]


def binding_name(category: str) -> str:
    return {
        "debug": "ui_debug.json",
        "demon_join": "field_demon_join.json",
    }.get(category, f"facilities_{category}.json")


def migrate_dialogue() -> None:
    dialogue = read_json(MATURE_DIALOGUE)
    psp_supplement = read_json(MATURE_PSP_SUPPLEMENT)
    mature_binding = read_json(MATURE_EVE_BINDING)
    physical = read_json(PHYSICAL_DIALOGUE)
    if len(dialogue) != 595 or len(psp_supplement) != 7:
        raise ValueError("unexpected mature SHOPSMP inventory")
    if len(physical) != 763:
        raise ValueError("unexpected physical SHOPSMP inventory")

    mature_by_id = {row["id"]: row for row in dialogue}
    physical_by_id = {row["id"]: row for row in physical}
    if len(mature_by_id) != 595 or len(physical_by_id) != 763:
        raise ValueError("duplicate SHOPSMP record id")

    occurrences: list[tuple[str, str, int]] = []
    categories_by_record: dict[str, set[str]] = defaultdict(set)
    for message in mature_binding["messages"]:
        message_index = message["index"]
        if not message["pages"]:
            continue
        category = message_category(message_index)
        for page in message["pages"]:
            physical_id = (
                f"game.shopsmp.m{message_index:04d}.p{page['index']:02d}"
            )
            occurrences.append((physical_id, page["record_id"], message_index))
            categories_by_record[page["record_id"]].add(category)

    if len(occurrences) != 763 or {item[0] for item in occurrences} != set(
        physical_by_id
    ):
        raise ValueError("mature SHOPSMP binding does not cover physical pages")
    if set(categories_by_record) != set(mature_by_id):
        raise ValueError("mature SHOPSMP authored inventory is not fully used")

    category_by_record = {
        record_id: (
            next(iter(categories)) if len(categories) == 1 else "common"
        )
        for record_id, categories in categories_by_record.items()
    }
    if {
        record_id
        for record_id, category in category_by_record.items()
        if category == "common"
    } != set(COMMON_KEYS):
        raise ValueError("SHOPSMP cross-surface sharing changed")

    description_record_to_drink: dict[str, str] = {}
    race_physical_ids: set[str] = set()
    race_record_ids: set[str] = set()
    for physical_id, record_id, message_index in occurrences:
        if 791 <= message_index <= 806:
            description_record_to_drink[record_id] = DRINK_KEYS[message_index - 791]
        if (
            161 <= message_index <= 203
            or message_index in {213, 217}
            or 218 <= message_index <= 262
        ):
            race_physical_ids.add(physical_id)
            race_record_ids.add(record_id)
    if len(description_record_to_drink) != 16:
        raise ValueError("bar drink-description inventory changed")
    if len(race_physical_ids) != 90 or len(race_record_ids) != 48:
        raise ValueError("fusion race-table inventory changed")
    if any(
        record_id in race_record_ids and physical_id not in race_physical_ids
        for physical_id, record_id, _message_index in occurrences
    ):
        raise ValueError("fusion race record is reused outside the proved tables")

    entries_by_category: dict[str, dict[str, Any]] = defaultdict(dict)
    records_by_category: dict[str, dict[str, str]] = defaultdict(dict)
    for row in dialogue:
        record_id = row["id"]
        category = category_by_record[record_id]
        if record_id in description_record_to_drink or record_id in race_record_ids:
            continue
        key = COMMON_KEYS.get(record_id, line_key(record_id))
        entries_by_category[category][key] = asset_entry(row)

    for physical_id, record_id, _message_index in occurrences:
        if physical_id in race_physical_ids:
            continue
        physical_reference = canonicalize(physical_by_id[physical_id]["reference"])
        mature_reference = canonicalize(mature_by_id[record_id]["jp"])
        category = category_by_record[record_id]
        normalized_physical = physical_reference.replace("{GLYPH:01a7}", "間")
        if normalized_physical != mature_reference:
            if normalized_physical.lstrip() != mature_reference:
                raise ValueError(f"SHOPSMP reference mismatch at {physical_id}")
            # Direct fusion-guide rows use leading cells for indentation. Keep
            # those source-visible spaces in the editable reference instead
            # of teaching the binding a lossy whitespace rule.
            key = COMMON_KEYS.get(record_id, line_key(record_id))
            entries_by_category[category][key]["text"]["reference"] = (
                physical_reference
            )
        if record_id in description_record_to_drink:
            asset_ref = f"{description_record_to_drink[record_id]}.description"
        else:
            asset_ref = f"{COMMON_KEYS.get(record_id, line_key(record_id))}.text"
        records_by_category[category][physical_id] = asset_ref

    # The PSP adds only these seven tutorial lines. They live alongside the
    # shared Gouma-den text but have no Saturn physical binding.
    for index, row in enumerate(psp_supplement):
        entries_by_category["gouma_den"][f"psp_tutorial_{index:04d}"] = (
            asset_entry(row)
        )

    shop_terms = read_json(MATURE_SHOP_TERMS)
    bar_entries = entries_by_category["bar"]
    for index, (key, row) in enumerate(
        zip(DRINK_KEYS, shop_terms["drinks"], strict=True)
    ):
        description_record = next(
            record_id
            for record_id, drink_key in description_record_to_drink.items()
            if drink_key == key
        )
        bar_entries[key] = {
            "name": {
                "reference": row["jp"],
                "translation": row["tr"],
            },
            "description": {
                "reference": canonicalize(mature_by_id[description_record]["jp"]),
                "translation": canonicalize(mature_by_id[description_record]["tr"]),
            },
        }
        physical_id = f"game.event_bar.drinks.r{index:04d}"
        records_by_category["bar"][physical_id] = f"{key}.name"

    for index, (key, row) in enumerate(
        zip(PATRON_KEYS, shop_terms["talk_labels"], strict=True)
    ):
        bar_entries[key] = {
            "name": {
                "reference": row["jp"],
                "translation": row["tr"],
            }
        }
        physical_id = f"game.event_bar.talk_labels.r{index:04d}"
        records_by_category["bar"][physical_id] = f"{key}.name"

    healing = read_json(MATURE_HEALING_TERMS)["all_members"]
    entries_by_category["healer"]["all_members"] = {
        "text": {
            "reference": "メンバーすべて",
            "translation": healing["tr"],
            "note": (
                "The retail code spells the physical label メンバーすべて; "
                "the mature semantic corpus normalized it to メンバー全員."
            ),
        }
    }
    records_by_category["healer"]["game.event_healing.o0168f7"] = (
        "all_members.text"
    )

    for row, physical_row in zip(
        read_json(MATURE_FUSION_CONFIRMATION),
        read_json(PHYSICAL_ADDRESSED / "fusion_confirmation_static.json"),
        strict=True,
    ):
        if row["jp"] != physical_row["reference"]:
            raise ValueError("fusion-confirmation source mismatch")
        key = row["kind"]
        entries_by_category["gouma_den"][key] = asset_entry(row)
        records_by_category["gouma_den"][physical_row["id"]] = f"{key}.text"

    entries_by_category["shop"]["inventory_label"] = {
        "text": {
            "reference": "Inv.",
            "translation": "Inv.",
            "note": (
                "Stock two-tile shop label reconstructed by the Saturn "
                "English renderer; it is authored here rather than in code."
            ),
        }
    }

    expected_categories = {
        "bar",
        "common",
        "debug",
        "demon_join",
        "gouma_den",
        "gym",
        "healer",
        "mag_exchange",
        "shop",
    }
    if set(entries_by_category) != expected_categories:
        raise ValueError("SHOPSMP category inventory changed")

    for category in sorted(expected_categories):
        kind = "entity_catalog" if category == "bar" else "surface_catalog"
        write_json(
            ASSET_ROOT / asset_path(category),
            {
                "version": 1,
                "kind": kind,
                "entries": entries_by_category[category],
            },
        )
        binding: dict[str, Any] = {
            "version": 1,
            "asset": asset_path(category),
            "records": records_by_category[category],
        }
        if category == "bar":
            binding["field_surfaces"] = {
                "description": ["bar.drink_help"],
            }
            binding["record_surfaces"] = {
                f"game.event_bar.drinks.r{index:04d}": ["bar.drink_name"]
                for index in range(16)
            } | {
                f"game.event_bar.talk_labels.r{index:04d}": ["bar.patron_name"]
                for index in range(6)
            }
        elif category == "healer":
            binding["record_surfaces"] = {
                "game.event_healing.o0168f7": ["healer.member_name"]
            }
        write_json(BINDING_ROOT / binding_name(category), binding)


def migrate_save_load() -> None:
    mature_save = read_json(MATURE_SAVE)
    mature_load = read_json(MATURE_LOAD)
    mature_capacity = read_json(MATURE_CAPACITY)
    physical_save = read_json(PHYSICAL_ADDRESSED / "save_static.json")
    physical_load = read_json(PHYSICAL_ADDRESSED / "load_static.json")
    physical_capacity = read_json(PHYSICAL_ADDRESSED / "load_capacity.json")
    if not (
        len(mature_save) == len(physical_save) == 14
        and len(mature_load) == len(physical_load) == 4
        and len(mature_capacity) == len(physical_capacity) == 1
    ):
        raise ValueError("unexpected SAVE/LOAD inventory")

    entries: dict[str, Any] = {}
    records: dict[str, str] = {}
    record_surfaces: dict[str, list[str]] = {}
    location_kinds = {
        "location_home",
        "location_office",
        "location_asahi",
        "location_rinkai_park",
        "location_mount_kasagi",
        "location_yarai",
        "location_chuo",
        "location_hibarigaoka",
    }

    def add_rows(
        mature_rows: list[dict[str, Any]],
        physical_rows: list[dict[str, Any]],
    ) -> None:
        for row, physical_row in zip(mature_rows, physical_rows, strict=True):
            if row["jp"] != physical_row["reference"]:
                raise ValueError(f"SAVE/LOAD source mismatch at {physical_row['id']}")
            if row["kind"] in location_kinds:
                continue
            key = row["kind"]
            prior = entries.get(key)
            candidate = asset_entry(row)
            if prior is not None and prior != candidate:
                raise ValueError(f"conflicting shared SAVE/LOAD field {key}")
            entries[key] = candidate
            records[physical_row["id"]] = f"{key}.text"
            if key == "empty":
                surface = "save_load.slot_state"
            elif key.startswith("prompt_"):
                surface = "save_load.prompt"
            else:
                surface = "save_load.message"
            record_surfaces[physical_row["id"]] = [surface]

    add_rows(mature_save, physical_save)
    add_rows(mature_load, physical_load)
    add_rows(mature_capacity, physical_capacity)
    record_surfaces[physical_capacity[0]["id"]] = ["save_load.capacity"]

    entries.update(
        {
            "save_heading": {
                "text": {"reference": "SAVE", "translation": "SAVE"}
            },
            "load_heading": {
                "text": {"reference": "LOAD", "translation": "LOAD"}
            },
            "new_game": {
                "text": {"reference": "NEW GAME", "translation": "NEW GAME"}
            },
            "storage_internal": {
                "text": {"reference": "本体", "translation": "INTERNAL"}
            },
            "storage_cartridge": {
                "text": {"reference": "カートリッジ", "translation": "CARTRIDGE"}
            },
            "psp_game_title": {
                "text": {
                    "reference": "Devil Summoner",
                    "translation": "Devil Summoner",
                }
            },
            "psp_slot_title": {
                "text": {
                    "reference": "Devil Summoner Save Data",
                    "translation": "Devil Summoner Save Data",
                }
            },
            "psp_difficulty_normal": {
                "text": {"reference": "Normal", "translation": "Normal"}
            },
            "psp_difficulty_hard": {
                "text": {"reference": "Hard", "translation": "Hard"}
            },
            "psp_cancel_load": {
                "text": {
                    "reference": "Do you want to cancel loading?",
                    "translation": "Do you want to cancel loading?",
                }
            },
            "psp_cancel_save": {
                "text": {
                    "reference": "Do you want to cancel saving?",
                    "translation": "Do you want to cancel saving?",
                }
            },
            "psp_unknown_location": {
                "text": {"reference": "Unknown", "translation": "Unknown"}
            },
            "psp_detail": {
                "placeholders": {
                    "codename": "player_codename",
                    "difficulty": "difficulty_label",
                    "hours": "number",
                    "level": "number",
                    "location": "location_name",
                    "minutes": "number",
                },
                "text": {
                    "reference": (
                        "Shin Megami Tensei: Devil Summoner - Save Data{n}"
                        "{codename} Lv. {level} ({difficulty}){n}"
                        "{location} ({hours}:{minutes})"
                    ),
                    "translation": (
                        "Shin Megami Tensei: Devil Summoner - Save Data{n}"
                        "{codename} Lv. {level} ({difficulty}){n}"
                        "{location} ({hours}:{minutes})"
                    ),
                    "note": (
                        "Complete PSP savedata detail template. Runtime may "
                        "format the numeric values but owns no visible prose "
                        "or punctuation."
                    ),
                },
            },
        }
    )
    write_json(
        ASSET_ROOT / "save_load.json",
        {"version": 1, "kind": "surface_catalog", "entries": entries},
    )
    write_json(
        BINDING_ROOT / "save_load.json",
        {
            "version": 1,
            "asset": "save_load.json",
            "records": records,
            "record_surfaces": record_surfaces,
        },
    )


def extend_locations() -> None:
    asset_path_value = ASSET_ROOT / "locations.json"
    binding_path = BINDING_ROOT / "locations.json"
    asset = read_json(asset_path_value)
    binding = read_json(binding_path)
    mature_save = read_json(MATURE_SAVE)
    physical_save = read_json(PHYSICAL_ADDRESSED / "save_static.json")
    keys = (
        "home",
        "detective_agency",
        "asahi",
        "rinkai_park",
        "mount_kasagi",
        "yarai_ward",
        "chuo_ward",
        "hibarigaoka",
    )
    for index, (key, mature_row, physical_row) in enumerate(
        zip(keys, mature_save[:8], physical_save[:8], strict=True)
    ):
        if mature_row["jp"] != physical_row["reference"]:
            raise ValueError(f"save location source mismatch at row {index}")
        if key == "mount_kasagi":
            field = "name"
            existing = asset["entries"][key][field]
            if (existing["reference"], existing["translation"]) != (
                mature_row["jp"],
                mature_row["tr"],
            ):
                raise ValueError("Mount Kasagi identity changed")
        else:
            field = "save_name"
            asset["entries"][key] = {
                field: {
                    "reference": mature_row["jp"],
                    "translation": mature_row["tr"],
                }
            }
        binding["records"][physical_row["id"]] = f"{key}.{field}"
    binding["field_surfaces"]["save_name"] = ["save_load.dungeon_location"]
    write_json(asset_path_value, asset)
    write_json(binding_path, binding)


def main() -> None:
    migrate_dialogue()
    migrate_save_load()
    extend_locations()


if __name__ == "__main__":
    main()
