from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TEXT_ROOT = Path(__file__).resolve().parents[1]
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

from util.assets import BINDING_ROOT, load_asset, load_binding  # noqa: E402


ASSET_FILENAMES = (
    "azuma_home.json",
    "cafe_afro.json",
    "casa_inui.json",
    "central_library.json",
    "city_interactions.json",
    "dds_net.json",
    "detective_office.json",
    "doctor_thrill.json",
    "hajime_home.json",
    "kasagi_ritual.json",
    "kitayama_university.json",
    "kumiko_vacant_lot.json",
    "marie_jobs.json",
    "police_arrest.json",
    "rinkai_hospital.json",
    "soul_transfer.json",
    "yatou_building.json",
)

BANK_1_NEW_ASSET_FILENAMES = (
    "ancient_tomb.json",
    "chinatown.json",
    "city_hall.json",
    "city_museum.json",
    "club_cretaceous.json",
    "club_ezekiel.json",
    "fairy_forest.json",
    "ginza_arcade.json",
    "hikawa_shrine.json",
    "kumiko_home.json",
    "mount_kasagi.json",
    "police_station.json",
    "tendou_mansion.json",
    "toa_tv.json",
    "us_base.json",
)

CURRENCY_PAGES = {
    "game.evfile_0.m0235.p04",
    "game.evfile_0.m0290.p01",
    "game.evfile_0.m0344.p00",
    "game.evfile_0.m0351.p01",
    "game.evfile_0.m0355.p01",
    "game.evfile_0.m0363.p01",
    "game.evfile_0.m0370.p01",
    "game.evfile_0.m0377.p01",
    "game.evfile_0.m0382.p01",
}


class GeneralEventAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.assets = {
            filename: load_asset(f"events/{filename}")
            for filename in ASSET_FILENAMES
        }
        cls.bindings = [
            load_binding(BINDING_ROOT / f"event_{Path(filename).stem}.json")
            for filename in ASSET_FILENAMES
        ]
        cls.profile_asset = load_asset("ui/profile_entry.json")
        cls.profile_binding = load_binding(
            BINDING_ROOT / "profile_entry_events.json"
        )

    def test_entire_first_event_bank_has_one_physical_owner(self) -> None:
        physical_rows = json.loads(
            (TEXT_ROOT / "corpus" / "game" / "eve" / "evfile_0.json")
            .read_text(encoding="utf-8")
        )
        expected = {row["id"] for row in physical_rows}
        self.assertEqual(len(expected), 766)

        owners: dict[str, str] = {}
        for binding in (*self.bindings, self.profile_binding):
            for physical_id, asset_ref in binding.records.items():
                if not physical_id.startswith("game.evfile_0."):
                    continue
                self.assertNotIn(physical_id, owners)
                owners[physical_id] = f"{binding.asset.as_posix()}#{asset_ref}"
        self.assertEqual(set(owners), expected)
        self.assertEqual(len(set(owners.values())), 711)
        self.assertEqual(len(owners) - len(set(owners.values())), 55)

    def test_event_assets_are_semantic_and_preserve_mature_text_state(self) -> None:
        asset_refs = {
            (binding.asset.name, asset_ref)
            for binding in self.bindings
            for physical_id, asset_ref in binding.records.items()
            if physical_id.startswith("game.evfile_0.")
        }
        self.assertEqual(len(asset_refs), 693)
        notes = []
        for filename, asset_ref in asset_refs:
            self.assertNotIn("evfile", filename)
            field = self.assets[filename].field(asset_ref)
            self.assertTrue(field.reference)
            self.assertTrue(field.translation)
            self.assertFalse(field.reviewed)
            if field.note is not None:
                notes.append(field.note)
        self.assertEqual(len(notes), 3)

        for binding in self.bindings:
            self.assertNotIn("evfile", binding.asset.as_posix())
            self.assertEqual(
                dict(binding.field_surfaces), {"text": ("event.dialogue",)}
            )

    def test_visible_yen_glyph_is_an_authored_symbol(self) -> None:
        physical_to_field = {}
        catalogs = {}
        bindings_with_token = 0
        for binding in self.bindings:
            catalog = self.assets[binding.asset.name]
            catalogs[binding.asset.as_posix()] = catalog
            if binding.glyph_tokens:
                bindings_with_token += 1
                self.assertEqual(dict(binding.glyph_tokens), {"00c0": "yen_symbol"})
            for physical_id, asset_ref in binding.records.items():
                physical_to_field[physical_id] = (catalog, asset_ref)

        self.assertEqual(bindings_with_token, 2)
        self.assertEqual(CURRENCY_PAGES, CURRENCY_PAGES & set(physical_to_field))
        for physical_id in CURRENCY_PAGES:
            catalog, asset_ref = physical_to_field[physical_id]
            field = catalog.field(asset_ref)
            self.assertIn("{yen_symbol}", field.reference)
            self.assertIn("{yen_symbol}", field.translation)

    def test_all_first_bank_messages_have_semantic_scene_membership(self) -> None:
        scenes = json.loads(
            (TEXT_ROOT / "config" / "event_scenes.json").read_text(
                encoding="utf-8"
            )
        )["scenes"]
        groups = [
            group
            for scene in scenes.values()
            for group in scene["physical_groups"]
            if group.startswith("game.evfile_0.")
        ]
        self.assertEqual(len(groups), 465)
        self.assertEqual(len(groups), len(set(groups)))
        self.assertEqual(
            set(groups), {f"game.evfile_0.m{index:04d}" for index in range(465)}
        )


class MigratedGeneralEventBankTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bindings = [
            load_binding(path)
            for path in sorted(BINDING_ROOT.glob("event_*.json"))
        ]
        cls.assets = {
            binding.asset.as_posix(): load_asset(binding.asset)
            for binding in cls.bindings
        }

    def uses_for_source(self, source: str) -> dict[str, str]:
        prefix = f"game.{source}."
        uses = {}
        for binding in self.bindings:
            for physical_id, asset_ref in binding.records.items():
                if not physical_id.startswith(prefix):
                    continue
                self.assertNotIn(physical_id, uses)
                uses[physical_id] = f"{binding.asset.as_posix()}#{asset_ref}"
        return uses

    def uses_for_bank(self, bank: int) -> dict[str, str]:
        return self.uses_for_source(f"evfile_{bank}")

    def test_second_bank_has_complete_semantic_ownership(self) -> None:
        physical_rows = json.loads(
            (TEXT_ROOT / "corpus" / "game" / "eve" / "evfile_1.json")
            .read_text(encoding="utf-8")
        )
        expected = {row["id"] for row in physical_rows}
        uses = self.uses_for_bank(1)
        self.assertEqual(len(expected), 602)
        self.assertEqual(set(uses), expected)
        self.assertEqual(len(set(uses.values())), 585)
        self.assertEqual(len(uses) - len(set(uses.values())), 17)

        first_bank_uses = self.uses_for_bank(0)
        self.assertEqual(
            len(set(first_bank_uses.values()) & set(uses.values())), 13
        )
        self.assertEqual(
            len(set(first_bank_uses.values()) | set(uses.values())), 1265
        )

    def test_second_bank_assets_preserve_editable_mature_output(self) -> None:
        uses = self.uses_for_bank(1)
        notes = set()
        for qualified_ref in set(uses.values()):
            asset_path, asset_ref = qualified_ref.split("#", 1)
            self.assertNotIn("evfile", asset_path)
            field = self.assets[asset_path].field(asset_ref)
            self.assertTrue(field.reference)
            self.assertTrue(field.translation)
            self.assertFalse(field.reviewed)
            if field.note is not None:
                notes.add(field.note)
        self.assertEqual(len(notes), 3)

        for filename in BANK_1_NEW_ASSET_FILENAMES:
            self.assertIn(f"events/{filename}", self.assets)

    def test_second_bank_visible_glyphs_are_explicitly_authored(self) -> None:
        yen_pages = {
            "game.evfile_1.m0102.p04",
            "game.evfile_1.m0117.p04",
            "game.evfile_1.m0125.p00",
            "game.evfile_1.m0196.p00",
        }
        uses = self.uses_for_bank(1)
        for physical_id in yen_pages:
            asset_path, asset_ref = uses[physical_id].split("#", 1)
            field = self.assets[asset_path].field(asset_ref)
            self.assertIn("{yen_symbol}", field.reference)
            self.assertIn("{yen_symbol}", field.translation)

        dash_path, dash_ref = uses[
            "game.evfile_1.m0272.p00"
        ].split("#", 1)
        dash = self.assets[dash_path].field(dash_ref)
        self.assertIn("DDS-NET", dash.reference)
        self.assertNotIn("GLYPH", dash.reference)

    def test_every_text_bearing_message_has_one_curated_scene(self) -> None:
        rows = json.loads(
            (TEXT_ROOT / "corpus" / "game" / "eve" / "evfile_1.json")
            .read_text(encoding="utf-8")
        )
        expected_groups = {
            row["id"].rsplit(".p", 1)[0]
            for row in rows
        }
        scenes = json.loads(
            (TEXT_ROOT / "config" / "event_scenes.json").read_text(
                encoding="utf-8"
            )
        )["scenes"]
        groups = [
            group
            for scene in scenes.values()
            for group in scene["physical_groups"]
            if group.startswith("game.evfile_1.")
        ]
        self.assertEqual(len(expected_groups), 327)
        self.assertEqual(len(groups), len(set(groups)))
        self.assertEqual(set(groups), expected_groups)

    def test_third_bank_has_complete_semantic_ownership(self) -> None:
        physical_rows = json.loads(
            (TEXT_ROOT / "corpus" / "game" / "eve" / "evfile_2.json")
            .read_text(encoding="utf-8")
        )
        expected = {row["id"] for row in physical_rows}
        uses = self.uses_for_bank(2)
        self.assertEqual(len(expected), 154)
        self.assertEqual(set(uses), expected)
        self.assertEqual(len(set(uses.values())), 121)
        self.assertEqual(len(uses) - len(set(uses.values())), 33)

        earlier_uses = {
            **self.uses_for_bank(0),
            **self.uses_for_bank(1),
        }
        self.assertEqual(
            len(set(earlier_uses.values()) & set(uses.values())), 4
        )
        self.assertEqual(
            len(set(earlier_uses.values()) | set(uses.values())), 1382
        )

    def test_third_bank_reuses_only_proven_semantic_fields(self) -> None:
        uses = self.uses_for_bank(2)
        self.assertEqual(
            uses["game.evfile_2.m0001.p00"],
            "events/doctor_thrill.json#doctor_thrill_laboratory_001.text",
        )
        self.assertEqual(
            uses["game.evfile_2.m0006.p00"],
            "events/doctor_thrill.json#doctor_thrill_laboratory_007.text",
        )
        self.assertEqual(
            uses["game.evfile_2.m0006.p01"],
            "events/doctor_thrill.json#doctor_thrill_laboratory_008.text",
        )
        self.assertEqual(
            uses["game.evfile_2.m0072.p00"],
            "events/city_museum.json#city_museum_collection_008.text",
        )

        for qualified_ref in set(uses.values()):
            asset_path, asset_ref = qualified_ref.split("#", 1)
            field = self.assets[asset_path].field(asset_ref)
            self.assertTrue(field.reference)
            self.assertTrue(field.translation)
            self.assertFalse(field.reviewed)

    def test_every_third_bank_message_has_one_curated_scene(self) -> None:
        rows = json.loads(
            (TEXT_ROOT / "corpus" / "game" / "eve" / "evfile_2.json")
            .read_text(encoding="utf-8")
        )
        expected_groups = {row["id"].rsplit(".p", 1)[0] for row in rows}
        scenes = json.loads(
            (TEXT_ROOT / "config" / "event_scenes.json").read_text(
                encoding="utf-8"
            )
        )["scenes"]
        groups = [
            group
            for scene in scenes.values()
            for group in scene["physical_groups"]
            if group.startswith("game.evfile_2.")
        ]
        self.assertEqual(len(expected_groups), 73)
        self.assertEqual(len(groups), len(set(groups)))
        self.assertEqual(set(groups), expected_groups)

    def test_main_bank_has_complete_semantic_ownership(self) -> None:
        physical_rows = json.loads(
            (TEXT_ROOT / "corpus" / "game" / "eve" / "mesfile.json")
            .read_text(encoding="utf-8")
        )
        expected = {row["id"] for row in physical_rows}
        uses = self.uses_for_source("mesfile")
        self.assertEqual(len(expected), 506)
        self.assertEqual(set(uses), expected)
        self.assertEqual(len(set(uses.values())), 490)
        self.assertEqual(len(uses) - len(set(uses.values())), 16)

        earlier_uses = {
            **self.uses_for_bank(0),
            **self.uses_for_bank(1),
            **self.uses_for_bank(2),
        }
        self.assertFalse(set(earlier_uses.values()) & set(uses.values()))
        self.assertEqual(
            len(set(earlier_uses.values()) | set(uses.values())), 1872
        )

    def test_main_bank_retains_all_mature_text_and_notes(self) -> None:
        uses = self.uses_for_source("mesfile")
        notes = set()
        for qualified_ref in set(uses.values()):
            asset_path, asset_ref = qualified_ref.split("#", 1)
            field = self.assets[asset_path].field(asset_ref)
            self.assertTrue(field.reference)
            self.assertTrue(field.translation)
            self.assertFalse(field.reviewed)
            if field.note is not None:
                notes.add(field.note)
        self.assertEqual(len(notes), 3)

        for filename in (
            "asahi_neighborhood.json",
            "bioenergy_association.json",
            "hibarigaoka.json",
            "hotel_neighborhood.json",
            "house_of_fortune.json",
        ):
            self.assertIn(f"events/{filename}", self.assets)

    def test_main_bank_yen_and_visible_debug_text_are_authored(self) -> None:
        uses = self.uses_for_source("mesfile")
        yen_path, yen_ref = uses["game.mesfile.m0077.p00"].split("#", 1)
        yen = self.assets[yen_path].field(yen_ref)
        self.assertIn("{yen_symbol}", yen.reference)
        self.assertIn("{yen_symbol}", yen.translation)

        debug_uses = {
            uses["game.mesfile.m0145.p00"],
            uses["game.mesfile.m0148.p00"],
            uses["game.mesfile.m0150.p00"],
        }
        self.assertEqual(len(debug_uses), 2)
        for qualified_ref in debug_uses:
            asset_path, asset_ref = qualified_ref.split("#", 1)
            debug = self.assets[asset_path].field(asset_ref)
            self.assertIn("If you see this message, it is a bug.", debug.translation)

    def test_every_main_bank_message_has_one_curated_scene(self) -> None:
        rows = json.loads(
            (TEXT_ROOT / "corpus" / "game" / "eve" / "mesfile.json")
            .read_text(encoding="utf-8")
        )
        expected_groups = {row["id"].rsplit(".p", 1)[0] for row in rows}
        scenes = json.loads(
            (TEXT_ROOT / "config" / "event_scenes.json").read_text(
                encoding="utf-8"
            )
        )["scenes"]
        groups = [
            group
            for scene in scenes.values()
            for group in scene["physical_groups"]
            if group.startswith("game.mesfile.")
        ]
        self.assertEqual(len(expected_groups), 238)
        self.assertEqual(len(groups), len(set(groups)))
        self.assertEqual(set(groups), expected_groups)


if __name__ == "__main__":
    unittest.main()
