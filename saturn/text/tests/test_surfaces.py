from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TEXT_ROOT = Path(__file__).resolve().parents[1]
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

from util.surfaces import load_surfaces  # noqa: E402


class SurfaceCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_surfaces()

    def test_documented_translation_geometries(self) -> None:
        event = self.catalog.surface("event.dialogue")
        self.assertEqual(
            (event.ja.font, event.ja.rows, event.ja.width.unit, event.ja.width.value),
            ("font16", 3, "glyph_cells", 20),
        )
        self.assertEqual(
            (event.en.font, event.en.rows, event.en.width.unit, event.en.width.value),
            ("font16", 3, "pixels", 300),
        )

        choice = self.catalog.surface("event.choice_option")
        self.assertEqual(
            (choice.ja.font, choice.ja.rows, choice.ja.width.unit, choice.ja.width.value),
            ("font16", 1, "glyph_cells", 9),
        )
        self.assertEqual((choice.en.font, choice.en.rows), ("font16", 1))
        self.assertFalse(choice.en.width.known)

        negotiation = self.catalog.surface("battle.negotiation_dialogue")
        self.assertEqual(
            (
                negotiation.ja.font,
                negotiation.ja.rows,
                negotiation.ja.width.unit,
                negotiation.ja.width.value,
            ),
            ("font16", 3, "glyph_cells", 20),
        )
        self.assertEqual(
            (
                negotiation.en.font,
                negotiation.en.rows,
                negotiation.en.width.unit,
                negotiation.en.width.value,
            ),
            ("font16", 3, "pixels", 300),
        )

        console = self.catalog.surface("battle.console")
        for layout in (console.ja, console.en):
            self.assertEqual(
                (layout.font, layout.rows, layout.width.unit, layout.width.value),
                ("fnt8x12", 3, "glyph_cells", 16),
            )

        field_message = self.catalog.surface("map_3d.field_message")
        self.assertEqual(
            (
                field_message.ja.font,
                field_message.ja.rows,
                field_message.ja.width.unit,
                field_message.ja.width.value,
            ),
            ("font16", 1, "glyph_cells", 14),
        )
        self.assertEqual(
            (
                field_message.en.font,
                field_message.en.rows,
                field_message.en.width.unit,
                field_message.en.width.value,
            ),
            ("font16", 1, "pixels", 224),
        )

        expected_locations = {
            "map_3d.location": (
                ("font16", 1, "glyph_cells", 4),
                ("font16", 2, "pixels", 64),
            ),
            "map_3d.floor": (
                ("font16", 1, "glyph_cells", 4),
                ("font16", 1, "pixels", 64),
            ),
            "automap.entry": (
                ("font16", 1, "glyph_cells", 7),
                ("font16", 1, "pixels", 112),
            ),
            "save_load.dungeon_location": (
                ("font16", 1, "glyph_cells", 7),
                ("font16", 1, "pixels", 144),
            ),
        }
        for name, (expected_ja, expected_en) in expected_locations.items():
            with self.subTest(surface=name):
                surface = self.catalog.surface(name)
                self.assertEqual(
                    (
                        surface.ja.font,
                        surface.ja.rows,
                        surface.ja.width.unit,
                        surface.ja.width.value,
                    ),
                    expected_ja,
                )
                self.assertEqual(
                    (
                        surface.en.font,
                        surface.en.rows,
                        surface.en.width.unit,
                        surface.en.width.value,
                    ),
                    expected_en,
                )

    def test_documented_fixed_width_japanese_geometries(self) -> None:
        expected = {
            "battle.help": ("font16", 2, 20),
            "battle.demon_chat": ("font16", 2, 11),
            "automap.marker_popup": ("font16", 3, 6),
            "status.affinity": ("font12", 2, 8),
            "shop.parent_help": ("font16", 1, 20),
        }
        for name, values in expected.items():
            with self.subTest(surface=name):
                layout = self.catalog.surface(name).ja
                self.assertEqual(
                    (layout.font, layout.rows, layout.width.unit, layout.width.value),
                    (*values[:2], "glyph_cells", values[2]),
                )

    def test_ability_name_geometries_cover_each_consumer(self) -> None:
        for name in (
            "battle.skill_name",
            "comp.ability_name",
            "status.skill_name",
        ):
            with self.subTest(surface=name):
                surface = self.catalog.surface(name)
                self.assertEqual(
                    (
                        surface.ja.font,
                        surface.ja.rows,
                        surface.ja.width.unit,
                        surface.ja.width.value,
                    ),
                    ("font8", 1, "glyph_cells", 8),
                )
                self.assertEqual(
                    (
                        surface.en.font,
                        surface.en.rows,
                        surface.en.width.unit,
                        surface.en.width.value,
                    ),
                    ("font8", 1, "pixels", 80),
                )

        level_up = self.catalog.surface("level_up.ability_name")
        self.assertEqual(
            (
                level_up.ja.font,
                level_up.ja.rows,
                level_up.ja.width.unit,
                level_up.ja.width.value,
            ),
            ("font16", 1, "glyph_cells", 8),
        )
        self.assertEqual(
            (
                level_up.en.font,
                level_up.en.rows,
                level_up.en.width.unit,
                level_up.en.width.value,
            ),
            ("font16", 1, "pixels", 128),
        )

    def test_race_and_affinity_geometries_cover_each_consumer(self) -> None:
        expected = {
            "battle.analyze_race_heading": (
                ("font8", 1, "glyph_cells", 5),
                ("font8", 1, "glyph_cells", 8),
            ),
            "battle.analyze_affinity": (
                ("font12", 1, "glyph_cells", 5),
                ("font8", 1, "pixels", 112),
            ),
            "status.affinity": (
                ("font12", 2, "glyph_cells", 8),
                ("font8", 2, "pixels", 128),
            ),
            "fusion.preview_race": (
                ("font12", 1, "glyph_cells", 2),
                ("font12", 1, "pixels", 24),
            ),
            "fusion.chart_race": (
                ("font12", 1, "glyph_cells", 2),
                ("font8", 1, "pixels", 26),
            ),
            "fusion.table_race": (
                ("font12", 1, "glyph_cells", 2),
                ("font8", 1, "pixels", 40),
            ),
        }
        for name, (expected_ja, expected_en) in expected.items():
            with self.subTest(surface=name):
                surface = self.catalog.surface(name)
                self.assertEqual(
                    (
                        surface.ja.font,
                        surface.ja.rows,
                        surface.ja.width.unit,
                        surface.ja.width.value,
                    ),
                    expected_ja,
                )
                self.assertEqual(
                    (
                        surface.en.font,
                        surface.en.rows,
                        surface.en.width.unit,
                        surface.en.width.value,
                    ),
                    expected_en,
                )

    def test_fusion_runtime_geometries_are_proved(self) -> None:
        expected = {
            "fusion.status_name": ("font12", 96),
            "fusion.preview_demon_name": ("font12", 96),
            "fusion.table_character_name": ("font12", 96),
            "fusion.table_demon_name": ("font8", 96),
            "fusion.guide": ("font12", 300),
            "fusion.help": ("font8", 284),
        }
        for name, (font, width) in expected.items():
            with self.subTest(surface=name):
                layout = self.catalog.surface(name).en
                self.assertEqual(
                    (layout.font, layout.rows, layout.width.unit, layout.width.value),
                    (font, 1, "pixels", width),
                )

    def test_unmeasured_limits_remain_explicitly_unknown(self) -> None:
        demon_chat_en = self.catalog.surface("battle.demon_chat").en
        self.assertIsNone(demon_chat_en.font)
        self.assertIsNone(demon_chat_en.rows)
        self.assertIsNone(demon_chat_en.width.unit)
        self.assertIsNone(demon_chat_en.width.value)
        self.assertFalse(demon_chat_en.width.known)

        fusion_help_ja = self.catalog.surface("fusion.help").ja
        self.assertEqual((fusion_help_ja.font, fusion_help_ja.rows), ("font12", 1))
        self.assertIsNone(fusion_help_ja.width.unit)
        self.assertIsNone(fusion_help_ja.width.value)

    def test_demon_surface_slots_are_recorded_without_guessed_limits(self) -> None:
        known_font_rows = {
            "battle.party_demon_name": ("font8", 1),
            "comp.party_demon_name": ("font8", 1),
            "comp.stock_demon_name": ("font8", 1),
            "status.demon_name": ("font16", 1),
        }
        for name, expected in known_font_rows.items():
            with self.subTest(surface=name):
                surface = self.catalog.surface(name)
                self.assertEqual((surface.ja.font, surface.ja.rows), expected)
                self.assertFalse(surface.ja.width.known)
                self.assertIsNone(surface.en.font)
                self.assertIsNone(surface.en.rows)
                self.assertFalse(surface.en.width.known)

        battle_analyze = self.catalog.surface("battle.analyze_demon_name")
        self.assertEqual(
            (
                battle_analyze.en.font,
                battle_analyze.en.rows,
                battle_analyze.en.width.unit,
                battle_analyze.en.width.value,
            ),
            ("font8", 1, "pixels", 112),
        )

        for name in (
            "compendium.ability_name",
            "compendium.profile_name",
            "compendium.race",
            "compendium.origin",
            "compendium.summary",
            "compendium.detail",
        ):
            with self.subTest(surface=name):
                surface = self.catalog.surface(name)
                for layout in (surface.ja, surface.en):
                    self.assertIsNone(layout.font)
                    self.assertIsNone(layout.rows)
                    self.assertFalse(layout.width.known)

    def test_catalog_is_strict(self) -> None:
        unknown = {
            "font": None,
            "rows": None,
            "width": {"unit": None, "value": None},
        }
        cases = {
            "missing language": {
                "version": 1,
                "surfaces": {"test.surface": {"ja": unknown}},
            },
            "partial width": {
                "version": 1,
                "surfaces": {
                    "test.surface": {
                        "ja": {
                            "font": None,
                            "rows": 1,
                            "width": {"unit": "pixels", "value": None},
                        },
                        "en": unknown,
                    }
                },
            },
            "extra field": {
                "version": 1,
                "surfaces": {
                    "test.surface": {
                        "ja": {**unknown, "note": "not part of the contract"},
                        "en": unknown,
                    }
                },
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "surfaces.json"
            for name, document in cases.items():
                with self.subTest(case=name):
                    path.write_text(
                        json.dumps(document),
                        encoding="utf-8",
                    )
                    with self.assertRaises(ValueError):
                        load_surfaces(path)

    def test_duplicate_json_fields_are_rejected(self) -> None:
        document = (
            '{"version":1,"version":1,"surfaces":{"test.surface":'
            '{"ja":{"font":null,"rows":null,"width":'
            '{"unit":null,"value":null}},"en":{"font":null,"rows":null,'
            '"width":{"unit":null,"value":null}}}}}'
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "surfaces.json"
            path.write_text(document, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON field"):
                load_surfaces(path)


if __name__ == "__main__":
    unittest.main()
