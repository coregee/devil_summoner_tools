from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


TEXT_ROOT = Path(__file__).resolve().parents[1]
FONT_CONFIG_ROOT = TEXT_ROOT.parent / "font" / "config" / "game"
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

from util.assets import BINDING_ROOT, load_asset, load_binding  # noqa: E402
from util.glyph_sets import CONFIG_PATH, load_glyph_sets  # noqa: E402


class OutputGlyphSetTests(unittest.TestCase):
    def test_only_non_font8_grid_selection_remains_surface_global(self) -> None:
        catalog = load_glyph_sets()
        kanji = catalog.handlers["kanji_ark_latin"]
        self.assertEqual((kanji.font, kanji.reference_set), ("kanji", "ark_latin"))
        self.assertEqual(set(catalog.handlers), {"kanji_ark_latin"})
        self.assertEqual(set(catalog.surface_handlers), {"name_entry.grid_row"})
        self.assertIsNone(catalog.for_surface("event.dialogue"))

    def test_name_grid_selects_centered_ark_kanji_latin(self) -> None:
        handler = load_glyph_sets().for_surface("name_entry.grid_row")
        self.assertIsNotNone(handler)
        self.assertEqual(
            (handler.font, handler.reference_set),
            ("kanji", "ark_latin"),
        )
        definition = json.loads(
            (FONT_CONFIG_ROOT / "kanji.json").read_text(encoding="utf-8")
        )
        published = {
            character
            for entry in definition["reference_sets"]["ark_latin"]
            for character in entry.get("aliases", entry["characters"])
        }
        profile = load_asset("ui/profile_entry.json")
        for key in (
            "grid_upper_row_1",
            "grid_upper_row_2",
            "grid_lower_row_1",
            "grid_lower_row_2",
            "grid_symbol_row_1",
            "grid_symbol_row_2",
        ):
            with self.subTest(row=key):
                translation = profile.entries[key].fields["text"].translation
                self.assertLessEqual(set(translation), published)

    def test_existing_go_field_declares_the_stock_command_surface(self) -> None:
        commands = load_asset("battle/commands.json")
        binding = load_binding(BINDING_ROOT / "battle_commands.json")
        self.assertEqual(commands.field("go.name").translation, "GO")
        self.assertEqual(commands.field("go.name").font8_alphabet, "original")
        self.assertEqual(
            binding.record_surfaces["game.battle_command_labels.o05066e"],
            ("battle.command",),
        )
        self.assertIsNone(load_glyph_sets().for_surface("battle.command"))

    def test_handler_font_must_match_the_selected_english_surface(self) -> None:
        document = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        document["surface_handlers"] = {
            "event.dialogue": "kanji_ark_latin"
        }
        with tempfile.TemporaryDirectory() as raw_directory:
            path = Path(raw_directory) / "glyph_sets.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "English surface uses font16"):
                load_glyph_sets(path)


if __name__ == "__main__":
    unittest.main()
