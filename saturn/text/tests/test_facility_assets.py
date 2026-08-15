from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TEXT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = TEXT_ROOT.parents[1]
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

from util.assets import BINDING_ROOT, load_asset, load_binding  # noqa: E402
from util.surfaces import load_surfaces  # noqa: E402


SHOPSMP_BINDINGS = (
    "facilities_bar.json",
    "facilities_common.json",
    "facilities_gouma_den.json",
    "facilities_gym.json",
    "facilities_healer.json",
    "facilities_mag_exchange.json",
    "facilities_shop.json",
    "field_demon_join.json",
    "races.json",
    "ui_debug.json",
)


class FacilityAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.assets = {
            "bar": load_asset("facilities/bar.json"),
            "common": load_asset("facilities/common.json"),
            "gouma_den": load_asset("facilities/gouma_den.json"),
            "gym": load_asset("facilities/gym.json"),
            "healer": load_asset("facilities/healer.json"),
            "mag_exchange": load_asset("facilities/mag_exchange.json"),
            "shop": load_asset("facilities/shop.json"),
            "demon_join": load_asset("field/demon_join.json"),
            "debug": load_asset("ui/debug.json"),
        }
        cls.bindings = {
            path: load_binding(BINDING_ROOT / path) for path in SHOPSMP_BINDINGS
        }
        cls.physical = json.loads(
            (TEXT_ROOT / "corpus" / "game" / "eve" / "shopsmp.json").read_text(
                encoding="utf-8"
            )
        )

    def test_mixed_binary_bank_is_partitioned_by_consumer_without_copies(self) -> None:
        expected_counts = {
            "facilities_bar.json": 98,
            "facilities_common.json": 11,
            "facilities_gouma_den.json": 235,
            "facilities_gym.json": 2,
            "facilities_healer.json": 28,
            "facilities_mag_exchange.json": 22,
            "facilities_shop.json": 207,
            "field_demon_join.json": 31,
            "races.json": 90,
            "ui_debug.json": 39,
        }
        seen: set[str] = set()
        for filename, expected in expected_counts.items():
            physical_ids = {
                physical_id
                for physical_id in self.bindings[filename].records
                if physical_id.startswith("game.shopsmp.")
            }
            with self.subTest(binding=filename):
                self.assertEqual(len(physical_ids), expected)
                self.assertTrue(seen.isdisjoint(physical_ids))
            seen.update(physical_ids)
        self.assertEqual(seen, {row["id"] for row in self.physical})
        self.assertEqual(len(seen), 763)

    def test_cross_surface_reuse_is_declared_once(self) -> None:
        common = self.bindings["facilities_common.json"].records
        self.assertEqual(
            {
                physical_id
                for physical_id, asset_ref in common.items()
                if asset_ref == "exit.text"
            },
            {
                "game.shopsmp.m0006.p00",
                "game.shopsmp.m0272.p00",
                "game.shopsmp.m0601.p00",
                "game.shopsmp.m0779.p00",
                "game.shopsmp.m0808.p00",
            },
        )
        self.assertEqual(
            self.assets["common"].entries["exit"].fields["text"].translation,
            "EXIT",
        )

    def test_bar_entities_join_names_and_descriptions(self) -> None:
        bar = self.assets["bar"]
        drinks = {
            key: entry
            for key, entry in bar.entries.items()
            if {"name", "description"} <= set(entry.fields)
        }
        patrons = {
            key: entry
            for key, entry in bar.entries.items()
            if set(entry.fields) == {"name"}
        }
        self.assertEqual(len(drinks), 16)
        self.assertEqual(len(patrons), 6)
        crushed = drinks["crushed_ice"]
        self.assertEqual(crushed.fields["name"].translation, "Crushed Ice")
        self.assertEqual(
            crushed.fields["description"].reference,
            "六甲のわき水でつくった氷と{n}ウイスキーが織りなす絶妙のハーモニー",
        )
        binding = self.bindings["facilities_bar.json"]
        self.assertEqual(
            binding.records["game.event_bar.drinks.r0000"],
            "crushed_ice.name",
        )
        self.assertEqual(
            binding.records["game.shopsmp.m0791.p00"],
            "crushed_ice.description",
        )
        self.assertEqual(
            binding.records["game.event_bar.talk_labels.r0000"],
            "master.name",
        )

    def test_healing_and_fusion_static_text_use_mature_saturn_output(self) -> None:
        all_members = self.assets["healer"].entries["all_members"].fields["text"]
        self.assertEqual(
            (all_members.reference, all_members.translation),
            ("メンバーすべて", "All Members"),
        )
        gouma = self.assets["gouma_den"]
        self.assertEqual(
            gouma.entries["confirm_prompt"].fields["text"].translation,
            "Shall I fuse them?",
        )
        self.assertEqual(
            self.bindings["facilities_gouma_den.json"].records[
                "game.fusion_confirmation_static.o05458e"
            ],
            "confirm_prompt.text",
        )

    def test_shop_inventory_wording_and_geometry_are_not_runtime_literals(self) -> None:
        inventory = self.assets["shop"].entries["inventory_label"].fields["text"]
        self.assertEqual(
            (inventory.reference, inventory.translation),
            ("Inv.", "Inv."),
        )
        surface = load_surfaces().surface("shop.inventory_label")
        self.assertEqual(
            (
                surface.en.font,
                surface.en.rows,
                surface.en.width.unit,
                surface.en.width.value,
            ),
            ("font8", 1, "pixels", 16),
        )

    def test_psp_additions_do_not_duplicate_inherited_saturn_text(self) -> None:
        gouma = self.assets["gouma_den"]
        supplement = {
            key: entry
            for key, entry in gouma.entries.items()
            if key.startswith("psp_tutorial_")
        }
        self.assertEqual(len(supplement), 7)
        bound_refs = set(
            self.bindings["facilities_gouma_den.json"].records.values()
        )
        self.assertTrue(
            all(f"{key}.text" not in bound_refs for key in supplement)
        )
        self.assertEqual(
            supplement["psp_tutorial_0000"].fields["text"].translation,
            "...Yes, perhaps I should show you first.{n}Follow me.",
        )

    def test_every_dynamic_value_is_typed(self) -> None:
        observed = {
            (placeholder, placeholder_type)
            for catalog in self.assets.values()
            for entry in catalog.entries.values()
            for placeholder, placeholder_type in entry.placeholders.items()
        }
        self.assertEqual(
            observed,
            {
                ("city", "location_name"),
                ("demon_name", "demon_name"),
                ("drink_name", "drink_name"),
                ("event_id", "number"),
                ("first_name", "player_name"),
                ("item_name", "item_name"),
                ("last_name", "player_name"),
                ("race", "demon_race"),
                ("ward", "location_name"),
            },
        )


class SaveLoadAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_asset("save_load.json")
        cls.binding = load_binding(BINDING_ROOT / "save_load.json")
        cls.surfaces = load_surfaces()

    def test_saturn_static_records_share_duplicate_semantics_explicitly(self) -> None:
        self.assertEqual(len(self.binding.records), 11)
        self.assertEqual(
            self.binding.records["game.save_static.o05076a"],
            "save_capacity_error.text",
        )
        self.assertEqual(
            self.binding.records["game.load_static.o00b1be"],
            "save_capacity_error.text",
        )
        self.assertEqual(
            self.catalog.entries["prompt_overwrite"].fields["text"].translation,
            "Overwrite?",
        )

    def test_artwork_and_psp_runtime_words_are_editable_assets(self) -> None:
        expected = {
            "save_heading": ("SAVE", "SAVE"),
            "load_heading": ("LOAD", "LOAD"),
            "new_game": ("NEW GAME", "NEW GAME"),
            "storage_internal": ("本体", "INTERNAL"),
            "storage_cartridge": ("カートリッジ", "CARTRIDGE"),
            "psp_difficulty_normal": ("Normal", "Normal"),
            "psp_difficulty_hard": ("Hard", "Hard"),
            "psp_unknown_location": ("Unknown", "Unknown"),
        }
        for key, pair in expected.items():
            with self.subTest(entry=key):
                field = self.catalog.entries[key].fields["text"]
                self.assertEqual((field.reference, field.translation), pair)

    def test_psp_detail_is_one_complete_authored_template(self) -> None:
        entry = self.catalog.entries["psp_detail"]
        self.assertEqual(
            dict(entry.placeholders),
            {
                "codename": "player_codename",
                "difficulty": "difficulty_label",
                "hours": "number",
                "level": "number",
                "location": "location_name",
                "minutes": "number",
            },
        )
        self.assertEqual(
            entry.fields["text"].translation,
            "Shin Megami Tensei: Devil Summoner - Save Data{n}"
            "{codename} Lv. {level} ({difficulty}){n}"
            "{location} ({hours}:{minutes})",
        )

    def test_known_saturn_limits_and_unknowns_are_distinct(self) -> None:
        capacity = self.surfaces.surface("save_load.capacity")
        self.assertEqual(
            (
                capacity.ja.font,
                capacity.ja.rows,
                capacity.ja.width.unit,
                capacity.ja.width.value,
            ),
            ("font16", 1, "glyph_cells", 3),
        )
        message = self.surfaces.surface("save_load.message")
        self.assertEqual((message.ja.font, message.ja.rows), ("font16", 3))
        self.assertFalse(message.ja.width.known)
        selector = self.surfaces.surface("save_load.storage_selector")
        for layout in (selector.ja, selector.en):
            self.assertEqual(
                (layout.font, layout.rows, layout.width.unit, layout.width.value),
                (None, 1, "pixels", 104),
            )


if __name__ == "__main__":
    unittest.main()
