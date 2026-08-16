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
                self.assertNotIn(physical_id, owners)
                owners[physical_id] = f"{binding.asset.as_posix()}#{asset_ref}"
        self.assertEqual(set(owners), expected)
        self.assertEqual(len(set(owners.values())), 711)
        self.assertEqual(len(owners) - len(set(owners.values())), 55)

    def test_event_assets_are_semantic_and_preserve_mature_text_state(self) -> None:
        self.assertEqual(
            sum(len(asset.entries) for asset in self.assets.values()), 693
        )
        notes = []
        for filename, asset in self.assets.items():
            self.assertNotIn("evfile", filename)
            for entry in asset.entries.values():
                field = entry.fields["text"]
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


if __name__ == "__main__":
    unittest.main()
