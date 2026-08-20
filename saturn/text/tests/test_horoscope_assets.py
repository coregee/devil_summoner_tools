from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TEXT_ROOT = Path(__file__).resolve().parents[1]
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

from util.assets import (  # noqa: E402
    BINDING_ROOT,
    load_asset,
    load_binding,
    load_bound_translations,
)
from util.surfaces import load_surfaces  # noqa: E402


PHYSICAL_IDS = (
    "game.hosi_messages.o010f62.text",
    "game.hosi_messages.o010f8c.text",
    "game.hosi_messages.o010fb6.text",
    "game.hosi_messages.o010fe0.text",
    "game.hosi_messages.o01100a.text",
    "game.hosi_messages.o011034.text",
    "game.hosi_messages.o01105e.text",
    "game.hosi_messages.o011088.text",
)


class HoroscopeAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.asset = load_asset("ui/horoscope.json")
        cls.binding = load_binding(BINDING_ROOT / "horoscope.json")
        cls.rows = json.loads(
            (TEXT_ROOT / "corpus" / "game" / "fixed" / "hosi_messages.json")
            .read_text(encoding="utf-8")
        )

    def test_all_eight_messages_have_one_semantic_owner(self) -> None:
        self.assertEqual(len(self.asset.entries), 8)
        self.assertEqual(tuple(self.binding.records), PHYSICAL_IDS)
        self.assertEqual(
            set(self.binding.record_surfaces),
            set(PHYSICAL_IDS),
        )
        self.assertTrue(
            all(
                surfaces == ("horoscope.message",)
                for surfaces in self.binding.record_surfaces.values()
            )
        )

    def test_generated_corpus_resolves_every_translation(self) -> None:
        self.assertEqual(tuple(row["id"] for row in self.rows), PHYSICAL_IDS)
        values = load_bound_translations(
            ("game.hosi_messages.",),
            required_ids=set(PHYSICAL_IDS),
            binding_paths=(BINDING_ROOT / "horoscope.json",),
        )
        self.assertEqual(
            values[PHYSICAL_IDS[0]],
            "The first point is an empty lot near Mount Kasagi...",
        )
        self.assertEqual(
            values[PHYSICAL_IDS[-1]],
            "It is where the Tendou Yakuza boss's mansion resides.",
        )

    def test_surface_records_the_stock_renderer_limits(self) -> None:
        surface = load_surfaces().surface("horoscope.message")
        self.assertEqual(
            (
                surface.ja.font,
                surface.ja.rows,
                surface.ja.width.unit,
                surface.ja.width.value,
                surface.ja.glyphs,
            ),
            ("font16", 3, "glyph_cells", 20, 60),
        )
        self.assertEqual(
            (
                surface.en.font,
                surface.en.rows,
                surface.en.width.unit,
                surface.en.width.value,
                surface.en.glyphs,
            ),
            ("font16", 3, "pixels", 320, 60),
        )


if __name__ == "__main__":
    unittest.main()
