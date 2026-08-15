"""One-off checked migration of mature location text into semantic assets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATURE_ROOT = ROOT.parent / "smtds_en"
MATURE_LABELS = (
    MATURE_ROOT
    / "shared"
    / "text"
    / "corpus"
    / "dungeon"
    / "location_label"
    / "labels.json"
)
MATURE_MARKER_NAMES = MATURE_LABELS.with_name("marker_names.json")
PHYSICAL_CORPUS = (
    ROOT
    / "saturn"
    / "text"
    / "corpus"
    / "game"
    / "addressed"
    / "dungeon_locations.json"
)
ASSET_PATH = ROOT / "assets" / "text" / "locations.json"
FORMAT_PATH = ROOT / "assets" / "text" / "field" / "location_formats.json"
BINDING_PATH = ROOT / "saturn" / "text" / "bindings" / "locations.json"

LOCATION_KEYS = (
    "library",
    "yatou_building",
    "construction_site",
    "rinkai_hospital",
    "ginza_arcade",
    "otherworld",
    "police_station",
    "casa_inui",
    "kitayama_university",
    "university_main_building",
    "underground_sewer",
    "mount_kasagi",
    "kasagi_manor",
    "hikawa_shrine",
    "museum",
    "toa_tv",
    "radio_tower",
    "chinatown",
    "tendou_mansion",
    "astral_plane",
    "avici_hell",
    "new_city_hall",
    "fairy_forest",
    "ancient_tomb",
)

# This pins the 144 physical records to the mature 24-entry semantic order. It
# prevents a future matching string from silently changing an entity binding.
PHYSICAL_SEMANTIC_SEQUENCE_SHA256 = (
    "11463fe910ac960fa12b0865598501127b77580147f756537168956749a000f2"
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    mature = read_json(MATURE_LABELS)
    marker_names = read_json(MATURE_MARKER_NAMES)
    physical = read_json(PHYSICAL_CORPUS)

    assert len(LOCATION_KEYS) == len(mature) == 24
    assert len(physical) == 144
    assert [row["id"] for row in physical] == [
        f"game.dungeon_locations.locations.r{index:04d}" for index in range(144)
    ]
    assert all(
        row["tr"] and not row["reviewed"] and not row["excluded"] for row in mature
    )
    assert len({row["jp"] for row in mature}) == 24
    assert len({row["tr"] for row in mature}) == 24

    reference_to_index = {row["jp"]: index for index, row in enumerate(mature)}
    physical_indexes = bytes(reference_to_index[row["reference"]] for row in physical)
    assert hashlib.sha256(physical_indexes).hexdigest() == (
        PHYSICAL_SEMANTIC_SEQUENCE_SHA256
    )

    compact_by_translation = {
        "Kitayama University": "Kitayama Uni",
        "University Main Bldg.": "Main Bldg.",
        "Underground Sewer": "Sewer",
    }
    assert marker_names == compact_by_translation

    entries: dict[str, object] = {}
    for key, row in zip(LOCATION_KEYS, mature, strict=True):
        entry: dict[str, object] = {
            "name": {
                "reference": row["jp"],
                "translation": row["tr"],
            }
        }
        if row["tr"] in compact_by_translation:
            entry["automap_name"] = {
                "reference": row["jp"],
                "translation": compact_by_translation[row["tr"]],
            }
        entries[key] = entry

    formats = {
        "version": 1,
        "kind": "surface_catalog",
        "entries": {
            "map_3d_basement_floor": {
                "placeholders": {"floor": "number"},
                "text": {
                    "reference": "地下{floor}階",
                    "translation": "B{floor}F",
                },
            },
            "map_3d_above_ground_floor": {
                "placeholders": {"floor": "number"},
                "text": {
                    "reference": "{floor}階",
                    "translation": "{floor}F",
                },
            },
            "automap_floorless": {
                "placeholders": {"location": "location_name"},
                "text": {
                    "reference": "{location}",
                    "translation": "{location}",
                },
            },
            "automap_basement": {
                "placeholders": {
                    "location": "location_name",
                    "floor": "number",
                },
                "text": {
                    "reference": "{location} B{floor}F",
                    "translation": "{location} B{floor}F",
                },
            },
            "automap_above_ground": {
                "placeholders": {
                    "location": "location_name",
                    "floor": "number",
                },
                "text": {
                    "reference": "{location} {floor}F",
                    "translation": "{location} {floor}F",
                },
            },
            "save_load_floorless": {
                "placeholders": {"location": "location_name"},
                "text": {
                    "reference": "{location}",
                    "translation": "{location}",
                },
            },
            "save_load_basement": {
                "placeholders": {
                    "location": "location_name",
                    "floor": "number",
                },
                "text": {
                    "reference": "{location} 地下{floor}階",
                    "translation": "{location} B{floor}F",
                },
            },
            "save_load_above_ground": {
                "placeholders": {
                    "location": "location_name",
                    "floor": "number",
                },
                "text": {
                    "reference": "{location} {floor}階",
                    "translation": "{location} {floor}F",
                },
            },
        },
    }

    records = {
        row["id"]: f"{LOCATION_KEYS[reference_to_index[row['reference']]]}.name"
        for row in physical
    }
    first_physical_id = {
        row["reference"]: row["id"]
        for row in reversed(physical)
    }
    compact_uses = {
        first_physical_id[row["jp"]]: [
            {"asset": f"{key}.automap_name"}
        ]
        for key, row in zip(LOCATION_KEYS, mature, strict=True)
        if row["tr"] in compact_by_translation
    }

    binding = {
        "version": 1,
        "asset": "locations.json",
        "records": records,
        "additional_uses": compact_uses,
        "field_surfaces": {
            "name": [
                "map_3d.location",
                "automap.entry",
                "save_load.dungeon_location",
            ],
            "automap_name": ["automap.entry"],
        },
    }

    write_json(
        ASSET_PATH,
        {"version": 1, "kind": "entity_catalog", "entries": entries},
    )
    write_json(FORMAT_PATH, formats)
    write_json(BINDING_PATH, binding)


if __name__ == "__main__":
    main()
