from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TEXT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = TEXT_ROOT.parents[1]
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

from util.assets import (  # noqa: E402
    BINDING_ROOT,
    load_asset,
    load_binding,
    load_bound_translations,
)
from util.surfaces import load_surfaces  # noqa: E402
from util.sources import load_manifest, manifest_path  # noqa: E402


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
                "game.facility_command_labels.standard_commands.r0003",
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
        healer_binding = self.bindings["facilities_healer.json"]
        self.assertEqual(
            healer_binding.records["game.event_healing.o0168f7"],
            "all_members.text",
        )
        self.assertEqual(
            healer_binding.record_surfaces["game.event_healing.o0168f7"],
            ("healer.all_members",),
        )
        all_members_surface = load_surfaces().surface("healer.all_members")
        self.assertEqual(
            (
                all_members_surface.en.font,
                all_members_surface.en.rows,
                all_members_surface.en.width.unit,
                all_members_surface.en.width.value,
            ),
            ("font8", 1, "pixels", 144),
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
        self.assertEqual(
            {
                key: gouma.entries[key].fields["text"].translation
                for key in ("line_0134", "line_0135", "line_0139", "line_0143")
            },
            {
                "line_0134": "{GLYPH:010a}: Basic fusion result",
                "line_0135": "{GLYPH:010b}: Element appears",
                "line_0139": "{GLYPH:010e}: Same race down one",
                "line_0143": "{GLYPH:010d}: No combination",
            },
        )

    def test_event_bar_name_rows_use_the_mature_runtime_limits(self) -> None:
        surfaces = load_surfaces()
        expected = {
            "bar.drink_name": 64,
            "bar.patron_name": 64,
            "bar.status_name": 104,
            "healer.member_name": 104,
            "healer.status_name": 104,
        }
        for name, width in expected.items():
            with self.subTest(surface=name):
                layout = surfaces.surface(name).en
                self.assertEqual(
                    (layout.font, layout.rows, layout.width.unit, layout.width.value),
                    ("font8", 1, "pixels", width),
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
        cls.location_binding = load_binding(BINDING_ROOT / "locations.json")
        cls.location_format_binding = load_binding(
            BINDING_ROOT / "save_load_location_formats.json"
        )
        cls.surfaces = load_surfaces()
        cls.manifest = load_manifest(manifest_path("game"))
        cls.save_rows = json.loads(
            (
                TEXT_ROOT
                / "corpus"
                / "game"
                / "addressed"
                / "save_static.json"
            ).read_text(encoding="utf-8")
        )

    def test_saturn_static_records_share_duplicate_semantics_explicitly(self) -> None:
        self.assertEqual(len(self.binding.records), 16)
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
        self.assertEqual(
            {
                physical_id: (composition.source_role, composition.supplies)
                for physical_id, composition in self.binding.composition.items()
            },
            {
                "game.save_static.o051b28": ("scaffold", ("level",)),
                "game.save_static.o00ab62": (
                    "scaffold",
                    ("day", "month"),
                ),
                "game.save_static.o00ac00": (
                    "scaffold",
                    ("hour", "minute"),
                ),
            },
        )

    def test_capacity_value_has_one_semantic_owner_and_materializes_messages(
        self,
    ) -> None:
        expected_ids = {
            "game.save_static.o05076a",
            "game.save_static.o0508dc",
            "game.load_static.o00b0c0",
            "game.load_static.o00b1be",
        }
        self.assertEqual(set(self.binding.substitutions), expected_ids)
        for physical_id in expected_ids:
            self.assertEqual(
                dict(self.binding.substitutions[physical_id]),
                {"capacity_blocks": "capacity_number.text"},
            )
        translations = load_bound_translations(
            ("game.save_static.", "game.load_static."),
            required_ids=expected_ids,
            binding_paths=(BINDING_ROOT / "save_load.json",),
        )
        self.assertEqual(
            translations["game.save_static.o05076a"],
            "Not enough space to save.{n}Save requires 129 blocks.",
        )
        self.assertNotIn(
            "129",
            self.catalog.entries["save_capacity_error"].fields["text"].translation,
        )

    def test_saturn_populated_slot_templates_are_complete_and_typed(self) -> None:
        expected = {
            "slot_name": (
                {"first_name": "player_name", "last_name": "player_name"},
                "{first_name} {last_name}",
            ),
            "slot_level": ({"level": "number"}, "Lv{level}"),
            "slot_date": (
                {"day": "number", "month": "number"},
                "{day}/{month}",
            ),
            "slot_time": (
                {"hour": "number", "minute": "number"},
                "{hour}:{minute}",
            ),
        }
        for name, (placeholders, translation) in expected.items():
            with self.subTest(entry=name):
                entry = self.catalog.entries[name]
                self.assertEqual(dict(entry.placeholders), placeholders)
                self.assertEqual(entry.fields["text"].translation, translation)
        self.assertIn(
            "requires {first_name} before {last_name}",
            self.catalog.entries["slot_name"].fields["text"].note,
        )

    def test_stock_runtime_fragments_and_mirrors_are_physically_catalogued(
        self,
    ) -> None:
        self.assertEqual(len(self.save_rows), 20)
        references = {row["id"]: row["reference"] for row in self.save_rows}
        self.assertEqual(
            {
                physical_id: references[physical_id]
                for physical_id in (
                    "game.save_static.o051b28",
                    "game.save_static.o051b8a",
                    "game.save_static.o0508ba",
                    "game.save_static.o0508c0",
                    "game.save_static.o00ab62",
                    "game.save_static.o00ac00",
                )
            },
            {
                "game.save_static.o051b28": "Lv",
                "game.save_static.o051b8a": "地下階",
                "game.save_static.o0508ba": "YES",
                "game.save_static.o0508c0": "NO",
                "game.save_static.o00ab62": "／",
                "game.save_static.o00ac00": "：",
            },
        )

        source = next(
            value for value in self.manifest.sources if value.name == "save_static"
        )
        records = {row["name"]: row for row in source.container["records"]}
        mirrored = {
            "location_home": "0x52a14",
            "location_office": "0x52a18",
            "location_asahi": "0x52a22",
            "location_rinkai_park": "0x52a2a",
            "location_mount_kasagi": "0x52a32",
            "location_yarai": "0x52a3a",
            "location_chuo": "0x52a42",
            "location_hibarigaoka": "0x52a4a",
            "slot_level_scaffold": "0x52a10",
            "basement_floor_scaffold": "0x52a62",
            "empty": "0xb1b4",
            "slot_date_scaffold": "0xa786",
            "slot_time_scaffold": "0xa792",
        }
        for name, load_offset in mirrored.items():
            with self.subTest(record=name):
                record = records[name]
                self.assertIs(record["require_identical_bytes"], True)
                self.assertEqual(len(record["locations"]), 2)
                load_span = record["locations"][1]["spans"][0]
                self.assertEqual(
                    (load_span["file"], load_span["offset"]),
                    ("load_bin", load_offset),
                )

        capacity = next(
            value for value in self.manifest.sources if value.name == "load_capacity"
        ).container["records"]
        self.assertEqual(
            capacity,
            [
                {
                    "name": "capacity_number",
                    "source_encoding": "game_font16_plain_skip",
                    "framing": {"type": "none"},
                    "locations": [
                        {"spans": [{"offset": "0xb1ae", "units": 3}]}
                    ],
                }
            ],
        )

    def test_every_save_static_record_has_one_semantic_owner(self) -> None:
        physical_ids = {row["id"] for row in self.save_rows}
        owner_counts = {
            physical_id: sum(
                physical_id in binding.records
                for binding in (
                    self.binding,
                    self.location_binding,
                    self.location_format_binding,
                )
            )
            for physical_id in physical_ids
        }
        self.assertEqual(set(owner_counts.values()), {1})

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
        for key in (
            "save_heading",
            "load_heading",
            "new_game",
            "storage_internal",
            "storage_cartridge",
        ):
            self.assertIn(
                "visual",
                self.catalog.entries[key].fields["text"].note.lower(),
            )

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

    def test_saturn_text_consumers_have_distinct_measured_limits(self) -> None:
        expected = {
            "save_load.special_location": ((1, "glyph_cells", 7), (1, "pixels", 112, 16)),
            "save_load.dungeon_location": ((1, "glyph_cells", 7), (1, "pixels", 144, 24)),
            "save_load.slot_name": ((1, "glyph_cells", 7), (1, "pixels", 128, 17)),
            "save_load.slot_level": ((1, "glyph_cells", 4), (1, "pixels", 64, 4)),
            "save_load.slot_date": ((1, "glyph_cells", 5), (1, "pixels", 80, 5)),
            "save_load.slot_time": ((1, "glyph_cells", 5), (1, "pixels", 80, 5)),
            "save_load.slot_state": ((1, "glyph_cells", 5), (1, "pixels", 80, 5)),
            "save_load.prompt": ((1, "glyph_cells", 11), (1, "pixels", 176, 11)),
            "save_load.confirm_choice": ((1, "glyph_cells", 3), (1, "pixels", 48, 3)),
            "save_load.small_message": ((3, "glyph_cells", 11), (3, "pixels", 176, 24)),
            "save_load.capacity_message": ((2, "glyph_cells", 17), (2, "pixels", 272, 25)),
            "save_load.start_warning": ((4, "glyph_cells", 20), (4, "pixels", 320, 63)),
            "save_load.storage_warning": ((6, "glyph_cells", 20), (6, "pixels", 320, 63)),
        }
        for name, (expected_ja, expected_en) in expected.items():
            with self.subTest(surface=name):
                surface = self.surfaces.surface(name)
                self.assertEqual(surface.ja.font, "font16")
                self.assertEqual(
                    (surface.ja.rows, surface.ja.width.unit, surface.ja.width.value),
                    expected_ja,
                )
                self.assertEqual(surface.en.font, "font16")
                self.assertEqual(
                    (
                        surface.en.rows,
                        surface.en.width.unit,
                        surface.en.width.value,
                        surface.en.glyphs,
                    ),
                    expected_en,
                )

        capacity = self.surfaces.surface("save_load.capacity")
        for layout in (capacity.ja, capacity.en):
            self.assertEqual(
                (layout.font, layout.rows, layout.width.unit, layout.width.value),
                ("font16", 1, "glyph_cells", 3),
            )
        selector = self.surfaces.surface("save_load.storage_selector")
        for layout in (selector.ja, selector.en):
            self.assertEqual(
                (layout.font, layout.rows, layout.width.unit, layout.width.value),
                (None, 1, "pixels", 104),
            )


if __name__ == "__main__":
    unittest.main()
