from __future__ import annotations

import json
import sys
import unittest
from collections import Counter
from pathlib import Path, PurePosixPath


TEXT_ROOT = Path(__file__).resolve().parents[1]
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

from util.assets import BINDING_ROOT, load_asset, load_binding  # noqa: E402
from util.sources import load_manifest, manifest_path  # noqa: E402


EXPECTED_TRANSLATIONS = (
    "Library",
    "Yatou Building",
    "Construction Site",
    "Rinkai Hospital",
    "Ginza Arcade",
    "Otherworld",
    "Police Station",
    "Casa Inui",
    "Kitayama University",
    "University Main Bldg.",
    "Underground Sewer",
    "Mount Kasagi",
    "Kasagi Manor",
    "Hikawa Shrine",
    "Museum",
    "Toa TV",
    "Radio Tower",
    "Chinatown",
    "Tendou Mansion",
    "Astral Plane",
    "Avici Hell",
    "New City Hall",
    "Fairy Forest",
    "Ancient Tomb",
)


class LocationAssetInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_asset("locations.json")
        cls.formats = load_asset("field/location_formats.json")
        cls.binding = load_binding(BINDING_ROOT / "locations.json")
        cls.save_load_formats_binding = load_binding(
            BINDING_ROOT / "save_load_location_formats.json"
        )
        cls.physical = json.loads(
            (
                TEXT_ROOT
                / "corpus"
                / "game"
                / "addressed"
                / "dungeon_locations.json"
            ).read_text(encoding="utf-8")
        )

    def test_shared_catalog_keeps_dungeon_and_save_locations_semantic(self) -> None:
        self.assertEqual(len(self.catalog.entries), 31)
        self.assertEqual(
            sum(len(entry.fields) for entry in self.catalog.entries.values()),
            34,
        )
        self.assertEqual(
            tuple(
                entry.fields["name"].translation
                for entry in list(self.catalog.entries.values())[:24]
            ),
            EXPECTED_TRANSLATIONS,
        )
        for key, entry in self.catalog.entries.items():
            self.assertTrue({"name", "save_name"} & set(entry.fields))
            self.assertNotIn("saturn", key)
            self.assertNotIn("psp", key)
            for field_name, field in entry.fields.items():
                self.assertTrue(field.reference)
                self.assertTrue(field.translation)
                self.assertFalse(field.reviewed)
                expected_variants = (
                    {"map_2d"}
                    if (key, field_name) == ("mount_kasagi", "name")
                    else set()
                )
                self.assertEqual(set(field.variants), expected_variants)

    def test_only_proven_automap_forms_are_authored_separately(self) -> None:
        compact = {
            key: entry.fields["automap_name"].translation
            for key, entry in self.catalog.entries.items()
            if "automap_name" in entry.fields
        }
        self.assertEqual(
            compact,
            {
                "kitayama_university": "Kitayama Uni",
                "university_main_building": "Main Bldg.",
                "underground_sewer": "Sewer",
            },
        )

    def test_all_144_physical_rows_bind_explicitly(self) -> None:
        physical_ids = {row["id"] for row in self.physical}
        self.assertEqual(len(physical_ids), 144)
        dungeon_records = {
            physical_id: asset_ref
            for physical_id, asset_ref in self.binding.records.items()
            if physical_id.startswith("game.dungeon_locations.")
        }
        self.assertEqual(set(dungeon_records), physical_ids)
        self.assertEqual(len(set(dungeon_records.values())), 24)
        self.assertEqual(
            set(dungeon_records.values()),
            {
                f"{key}.name"
                for key in list(self.catalog.entries)[:24]
            },
        )
        self.assertEqual(
            Counter(
                self.catalog.field(asset_ref).reference
                for asset_ref in dungeon_records.values()
            ),
            Counter(row["reference"] for row in self.physical),
        )
        self.assertEqual(
            {
                physical_id: tuple(use.asset_ref for use in uses)
                for physical_id, uses in self.binding.additional_uses.items()
            },
            {
                "game.dungeon_locations.locations.r0024": (
                    "kitayama_university.automap_name",
                ),
                "game.dungeon_locations.locations.r0028": (
                    "university_main_building.automap_name",
                ),
                "game.dungeon_locations.locations.r0035": (
                    "underground_sewer.automap_name",
                ),
            },
        )

    def test_save_screen_special_locations_are_not_duplicated_as_prose(self) -> None:
        expected = {
            "game.save_static.o051b2c": "home.save_name",
            "game.save_static.o051b30": "detective_agency.save_name",
            "game.save_static.o051b3a": "asahi.save_name",
            "game.save_static.o051b42": "rinkai_park.save_name",
            "game.save_static.o051b4a": "mount_kasagi.name",
            "game.save_static.o051b52": "yarai_ward.save_name",
            "game.save_static.o051b5a": "chuo_ward.save_name",
            "game.save_static.o051b62": "hibarigaoka.save_name",
        }
        self.assertEqual(
            {
                physical_id: asset_ref
                for physical_id, asset_ref in self.binding.records.items()
                if physical_id.startswith("game.save_static.o051b")
            },
            expected,
        )
        self.assertEqual(
            self.catalog.entries["home"].fields["save_name"].translation,
            "Home",
        )
        self.assertEqual(
            self.catalog.entries["detective_agency"]
            .fields["save_name"]
            .translation,
            "Detective Agency",
        )

    def test_binding_declares_each_consumer_surface(self) -> None:
        self.assertEqual(
            self.binding.field_surfaces["name"],
            (
                "map_3d.location",
                "automap.entry",
                "save_load.dungeon_location",
            ),
        )
        self.assertEqual(
            self.binding.field_surfaces["automap_name"],
            ("automap.entry",),
        )
        self.assertEqual(
            self.binding.field_surfaces["save_name"],
            ("save_load.special_location",),
        )
        special_ids = {
            f"game.save_static.o{offset}"
            for offset in (
                "051b2c",
                "051b30",
                "051b3a",
                "051b42",
                "051b4a",
                "051b52",
                "051b5a",
                "051b62",
            )
        }
        self.assertEqual(set(self.binding.record_surfaces), special_ids)
        for physical_id in special_ids:
            self.assertEqual(
                self.binding.record_surfaces[physical_id],
                ("save_load.special_location",),
            )

    def test_floor_and_location_wording_is_editable_asset_text(self) -> None:
        expected = {
            "map_3d_basement_floor": ("地下{floor}階", "B{floor}F"),
            "map_3d_above_ground_floor": ("{floor}階", "{floor}F"),
            "automap_floorless": ("{location}", "{location}"),
            "automap_basement": (
                "{location} B{floor}F",
                "{location} B{floor}F",
            ),
            "automap_above_ground": (
                "{location} {floor}F",
                "{location} {floor}F",
            ),
            "save_load_floorless": ("{location}", "{location}"),
            "save_load_basement": (
                "{location}地下{floor}階",
                "{location} B{floor}F",
            ),
            "save_load_above_ground": (
                "{location}{floor}階",
                "{location} {floor}F",
            ),
        }
        self.assertEqual(set(self.formats.entries), set(expected))
        for key, (reference, translation) in expected.items():
            with self.subTest(format=key):
                field = self.formats.entries[key].fields["text"]
                self.assertEqual(
                    (field.reference, field.translation),
                    (reference, translation),
                )

    def test_stock_save_load_floor_scaffold_grounds_complete_template(self) -> None:
        physical_id = "game.save_static.o051b8a"
        self.assertEqual(
            self.save_load_formats_binding.records[physical_id],
            "save_load_basement.text",
        )
        composition = self.save_load_formats_binding.composition[physical_id]
        self.assertEqual(
            (composition.source_role, composition.supplies),
            ("scaffold", ("location", "floor")),
        )
        self.assertEqual(
            self.save_load_formats_binding.record_surfaces[physical_id],
            ("save_load.dungeon_location",),
        )

    def test_canonical_table_checks_all_main_saturn_mirrors(self) -> None:
        manifest = load_manifest(manifest_path("game"))
        source = next(
            source for source in manifest.sources if source.name == "dungeon_locations"
        )
        self.assertEqual(
            source.corpus_path,
            PurePosixPath("addressed/dungeon_locations.json"),
        )
        self.assertEqual(source.container["type"], "addressed")
        table = source.container["tables"][0]
        self.assertTrue(table["require_identical_bytes"])
        self.assertEqual(table["count"], 144)
        self.assertEqual(
            [
                (row["file"], row["base"], row["stride"], row["units"])
                for row in table["locations"]
            ],
            [
                ("maze_bin", "0x2532e", "0x20", 5),
                ("automapc_bin", "0x3a41a", "0x20", 5),
                ("save_bin", "0x5092a", "0x20", 5),
                ("load_bin", "0x51812", "0x20", 5),
            ],
        )


if __name__ == "__main__":
    unittest.main()
