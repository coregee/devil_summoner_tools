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
from util.surfaces import load_surfaces  # noqa: E402


MAP_RECORDS = {
    "game.map_static.o01e684": "朝日",
    "game.map_static.o01e688": "区",
    "game.map_static.o01e68e": "臨海公園",
    "game.map_static.o01e698": "笠置山",
    "game.map_static.o01e6a2": "矢来区",
    "game.map_static.o01e6ac": "中央区",
    "game.map_static.o01e6b6": "雲雀ヶ丘",
    "game.map_static.o01e6c0": "平崎",
    "game.map_static.o01e6c4": "市",
    "game.map_static.o01e6ca": "全図",
    "game.map_static.o01e6d4": "雲",
    "game.map_static.o01e756": "＞誰かいる。話しかけますか？",
    "game.map_static.o01e774": "YES",
    "game.map_static.o01e77c": "NO",
}


class Map2dAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_asset("ui/map_2d.json")
        cls.profile = load_asset("ui/profile_entry.json")
        cls.locations = load_asset("locations.json")
        cls.messages = load_asset("field/messages.json")
        cls.bindings = {
            name: load_binding(BINDING_ROOT / f"{name}.json")
            for name in (
                "map_2d",
                "map_2d_profile",
                "map_2d_locations",
                "map_2d_messages",
            )
        }
        cls.rows = json.loads(
            (TEXT_ROOT / "corpus" / "game" / "addressed" / "map_static.json")
            .read_text(encoding="utf-8")
        )
        cls.manifest = load_manifest(manifest_path("game"))
        cls.source = next(
            source for source in cls.manifest.sources if source.name == "map_static"
        )
        cls.surfaces = load_surfaces()

    def test_manifest_pins_every_span_encoding_and_identity(self) -> None:
        self.assertEqual(
            self.source.corpus_path,
            PurePosixPath("addressed/map_static.json"),
        )
        container = self.source.container
        self.assertEqual(container["type"], "addressed")
        self.assertEqual(container["file"], "map2d_bin")
        self.assertEqual(container["default_source_encoding"], "game_font16_plain_skip")
        self.assertEqual(container["tables"], [])
        actual = []
        for record in container["records"]:
            spans = tuple(
                (location["spans"][0]["offset"], location["spans"][0]["units"])
                for location in record["locations"]
            )
            self.assertTrue(
                all(len(location["spans"]) == 1 for location in record["locations"])
            )
            actual.append(
                (
                    record["name"],
                    record.get("require_identical_bytes", False),
                    spans,
                )
            )
        self.assertEqual(
            actual,
            [
                ("default_ward", False, (("0x1e684", 2),)),
                ("ward_suffix", True, (("0x1e688", 1), ("0x1e6de", 1))),
                ("location_rinkai_park", False, (("0x1e68e", 4),)),
                ("location_mount_kasagi", False, (("0x1e698", 3),)),
                ("location_yarai", False, (("0x1e6a2", 3),)),
                ("location_chuo", False, (("0x1e6ac", 3),)),
                ("location_hibarigaoka", False, (("0x1e6b6", 4),)),
                ("default_city", False, (("0x1e6c0", 2),)),
                ("city_suffix", True, (("0x1e6c4", 1), ("0x1e6e2", 1))),
                ("full_map_suffix", False, (("0x1e6ca", 2),)),
                ("orphan_cloud", False, (("0x1e6d4", 1),)),
                ("talk_prompt", False, (("0x1e756", 14),)),
                ("label_yes", False, (("0x1e774", 3),)),
                ("label_no", False, (("0x1e77c", 2),)),
            ],
        )
        map_file = self.manifest.files["map2d_bin"]
        self.assertEqual(
            map_file.stock_sha256,
            "1e8d00baefdfa282f3a63beb48ca13adec179935594bd5361bf8234c61ed6ecc",
        )
        self.assertEqual(
            map_file.owned_sha256,
            "44487bcbff38bf55d8302a1767821bfdf272a1475ac4794b438dafea623e5b43",
        )

    def test_generated_corpus_keeps_all_fourteen_physical_records(self) -> None:
        self.assertEqual(
            {row["id"]: row["reference"] for row in self.rows},
            MAP_RECORDS,
        )
        self.assertEqual(len(self.rows), 14)
        self.assertTrue(
            all(row["source_encoding"] == "game_font16_plain_skip" for row in self.rows)
        )

    def test_dedicated_bindings_give_every_record_one_owner(self) -> None:
        expected_owners = {
            "game.map_static.o01e684": "map_2d_profile.json",
            "game.map_static.o01e688": "map_2d.json",
            "game.map_static.o01e68e": "map_2d_locations.json",
            "game.map_static.o01e698": "map_2d_locations.json",
            "game.map_static.o01e6a2": "map_2d_locations.json",
            "game.map_static.o01e6ac": "map_2d_locations.json",
            "game.map_static.o01e6b6": "map_2d_locations.json",
            "game.map_static.o01e6c0": "map_2d_profile.json",
            "game.map_static.o01e6c4": "map_2d.json",
            "game.map_static.o01e6ca": "map_2d.json",
            "game.map_static.o01e6d4": "map_2d.json",
            "game.map_static.o01e756": "map_2d_messages.json",
            "game.map_static.o01e774": "map_2d_messages.json",
            "game.map_static.o01e77c": "map_2d_messages.json",
        }
        owners: dict[str, str] = {}
        counts: Counter[str] = Counter()
        for path in sorted(BINDING_ROOT.glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            for physical_id in document["records"]:
                if physical_id.startswith("game.map_static."):
                    counts[physical_id] += 1
                    owners[physical_id] = path.name
        self.assertEqual(owners, expected_owners)
        self.assertEqual(counts, Counter({physical_id: 1 for physical_id in MAP_RECORDS}))

    def test_dynamic_rows_reuse_profile_defaults_and_authored_templates(self) -> None:
        profile_binding = self.bindings["map_2d_profile"]
        self.assertEqual(
            dict(profile_binding.records),
            {
                "game.map_static.o01e684": "default_ward.text",
                "game.map_static.o01e6c0": "default_city.text",
            },
        )
        self.assertEqual(
            (
                self.profile.field("default_ward.text").reference,
                self.profile.field("default_ward.text").translation,
                self.profile.field("default_city.text").reference,
                self.profile.field("default_city.text").translation,
            ),
            ("朝日", "Asahi", "平崎", "Hirasaki"),
        )

        expected = {
            "city_label": ("{city}市", "{city}", {"city": "location_name"}),
            "world_city_label": (
                "{city}市全図",
                "{city}",
                {"city": "location_name"},
            ),
            "world_ward_label": (
                "{ward}区",
                "{ward}",
                {"ward": "location_name"},
            ),
            "area_label": ("{area}", "{area}", {"area": "location_name"}),
        }
        for key, (reference, translation, placeholders) in expected.items():
            with self.subTest(asset=key):
                entry = self.catalog.entries[key]
                self.assertEqual(dict(entry.placeholders), placeholders)
                self.assertEqual(set(entry.fields), {"text"})
                self.assertEqual(
                    (entry.fields["text"].reference, entry.fields["text"].translation),
                    (reference, translation),
                )

        city = self.profile.field("default_city.text")
        ward = self.profile.field("default_ward.text")
        self.assertEqual(
            self.catalog.field("city_label.text").reference.format(city=city.reference),
            "平崎市",
        )
        self.assertEqual(
            self.catalog.field("world_city_label.text").reference.format(
                city=city.reference
            ),
            "平崎市全図",
        )
        self.assertEqual(
            self.catalog.field("world_ward_label.text").reference.format(
                ward=ward.reference
            ),
            "朝日区",
        )

    def test_suffix_records_ground_complete_templates_without_runtime_prose(self) -> None:
        binding = self.bindings["map_2d"]
        self.assertEqual(
            dict(binding.records),
            {
                "game.map_static.o01e688": "world_ward_label.text",
                "game.map_static.o01e6c4": "city_label.text",
                "game.map_static.o01e6ca": "world_city_label.text",
                "game.map_static.o01e6d4": "orphan_cloud.text",
            },
        )
        self.assertEqual(
            {
                physical_id: (composition.source_role, composition.supplies)
                for physical_id, composition in binding.composition.items()
            },
            {
                "game.map_static.o01e688": ("suffix", ("ward",)),
                "game.map_static.o01e6c4": ("suffix", ("city",)),
                "game.map_static.o01e6ca": ("suffix", ("city",)),
            },
        )
        self.assertEqual(dict(binding.additional_uses), {})
        self.assertEqual(dict(binding.substitutions), {})

    def test_fixed_labels_reuse_locations_and_only_kasagi_needs_a_variant(self) -> None:
        binding = self.bindings["map_2d_locations"]
        self.assertEqual(
            dict(binding.records),
            {
                "game.map_static.o01e68e": "rinkai_park.save_name",
                "game.map_static.o01e698": "mount_kasagi.name",
                "game.map_static.o01e6a2": "yarai_ward.save_name",
                "game.map_static.o01e6ac": "chuo_ward.save_name",
                "game.map_static.o01e6b6": "hibarigaoka.save_name",
            },
        )
        self.assertEqual(
            dict(binding.variants),
            {"game.map_static.o01e698": "map_2d"},
        )
        expected = {
            "game.map_static.o01e68e": ("臨海公園", "Rinkai Park"),
            "game.map_static.o01e698": ("笠置山", "Mt. Kasagi"),
            "game.map_static.o01e6a2": ("矢来区", "Yarai Ward"),
            "game.map_static.o01e6ac": ("中央区", "Chuo Ward"),
            "game.map_static.o01e6b6": ("雲雀ヶ丘", "Hibarigaoka"),
        }
        for physical_id, (reference, translation) in expected.items():
            with self.subTest(record=physical_id):
                field = self.locations.field(binding.records[physical_id])
                actual_reference, actual_translation, _reviewed = field.resolve(
                    binding.variants.get(physical_id)
                )
                self.assertEqual(
                    (actual_reference, actual_translation),
                    (reference, translation),
                )
        mount = self.locations.field("mount_kasagi.name")
        self.assertEqual(mount.translation, "Mount Kasagi")
        self.assertEqual(mount.resolve("map_2d")[1], "Mt. Kasagi")

    def test_prompt_and_choices_reuse_field_assets_with_exact_limits(self) -> None:
        binding = self.bindings["map_2d_messages"]
        self.assertEqual(
            dict(binding.records),
            {
                "game.map_static.o01e756": "talk_prompt.text",
                "game.map_static.o01e774": "talk_choice_yes.text",
                "game.map_static.o01e77c": "talk_choice_no.text",
            },
        )
        self.assertEqual(
            {
                physical_id: (
                    self.messages.field(asset_ref).reference,
                    self.messages.field(asset_ref).translation,
                )
                for physical_id, asset_ref in binding.records.items()
            },
            {
                "game.map_static.o01e756": (
                    "＞誰かいる。話しかけますか？",
                    "> Someone is here. Talk to them?",
                ),
                "game.map_static.o01e774": ("YES", "Yes"),
                "game.map_static.o01e77c": ("NO", "No"),
            },
        )
        self.assertEqual(len("> Someone is here. Talk to them?"), 32)
        self.assertEqual((len("Yes"), len("No")), (3, 2))

    def test_cloud_row_stays_editable_but_unresolved_and_surface_free(self) -> None:
        entry = self.catalog.entries["orphan_cloud"]
        field = entry.fields["text"]
        binding = self.bindings["map_2d"]
        physical_id = "game.map_static.o01e6d4"
        self.assertEqual(entry.status, "unresolved")
        self.assertEqual((field.reference, field.translation), ("雲", "Cloud"))
        self.assertIn("No absolute reference", entry.note or "")
        self.assertIn("No absolute reference", binding.unresolved[physical_id])
        self.assertNotIn(physical_id, binding.record_surfaces)

    def test_every_visible_map_surface_is_font16_with_proved_geometry(self) -> None:
        expected = {
            "map_2d.world_city_label": (6, 96, None),
            "map_2d.world_region_label": (4, 64, None),
            "map_2d.area_label": (8, 128, None),
            "map_2d.field_message": (14, 224, None),
            "map_2d.field_choice": (3, 48, 3),
        }
        self.assertNotIn("map_2d.area_city_component", self.surfaces.surfaces)
        for surface_id, (ja_cells, en_pixels, en_glyphs) in expected.items():
            with self.subTest(surface=surface_id):
                surface = self.surfaces.surface(surface_id)
                self.assertEqual(
                    (
                        surface.ja.font,
                        surface.ja.rows,
                        surface.ja.width.unit,
                        surface.ja.width.value,
                    ),
                    ("font16", 1, "glyph_cells", ja_cells),
                )
                self.assertEqual(
                    (
                        surface.en.font,
                        surface.en.rows,
                        surface.en.width.unit,
                        surface.en.width.value,
                        surface.en.glyphs,
                    ),
                    ("font16", 1, "pixels", en_pixels, en_glyphs),
                )

    def test_each_live_record_declares_its_human_surface(self) -> None:
        map_binding = self.bindings["map_2d"]
        profile_binding = self.bindings["map_2d_profile"]
        location_binding = self.bindings["map_2d_locations"]
        message_binding = self.bindings["map_2d_messages"]
        self.assertEqual(
            dict(map_binding.record_surfaces),
            {
                "game.map_static.o01e688": (
                    "map_2d.world_region_label",
                    "map_2d.area_label",
                ),
                "game.map_static.o01e6c4": (
                    "map_2d.world_city_label",
                    "map_2d.area_label",
                ),
                "game.map_static.o01e6ca": ("map_2d.world_city_label",),
            },
        )
        self.assertEqual(
            dict(profile_binding.record_surfaces),
            {
                "game.map_static.o01e684": (
                    "map_2d.world_region_label",
                    "map_2d.area_label",
                ),
                "game.map_static.o01e6c0": (
                    "map_2d.world_city_label",
                    "map_2d.area_label",
                ),
            },
        )
        for surfaces in location_binding.record_surfaces.values():
            self.assertEqual(
                surfaces,
                ("map_2d.world_region_label", "map_2d.area_label"),
            )
        self.assertEqual(
            dict(message_binding.record_surfaces),
            {
                "game.map_static.o01e756": ("map_2d.field_message",),
                "game.map_static.o01e774": ("map_2d.field_choice",),
                "game.map_static.o01e77c": ("map_2d.field_choice",),
            },
        )


if __name__ == "__main__":
    unittest.main()
