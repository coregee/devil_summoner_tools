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


class CreditsAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.asset = load_asset("credits/names.json")
        cls.binding = load_binding(BINDING_ROOT / "end_roll_credits.json")
        cls.rows = json.loads(
            (TEXT_ROOT / "corpus" / "game" / "addressed" / "end_roll_names.json")
            .read_text(encoding="utf-8")
        )

    def test_all_forty_staff_names_have_one_authored_owner(self) -> None:
        self.assertEqual(len(self.asset.entries), 40)
        self.assertEqual(len(self.binding.records), 40)
        self.assertEqual(
            tuple(self.binding.records), tuple(row["id"] for row in self.rows)
        )
        values = load_bound_translations(
            ("game.end_roll_names.",),
            required_ids=set(self.binding.records),
            binding_paths=(BINDING_ROOT / "end_roll_credits.json",),
        )
        self.assertEqual(values[self.rows[0]["id"]], "Koji Okada")
        self.assertEqual(values[self.rows[27]["id"]], "Hisako Tasaki")
        self.assertEqual(values[self.rows[-1]["id"]], "Hiroaki Murai")

    def test_physical_consumers_split_into_main_and_test_rows(self) -> None:
        surfaces = tuple(self.binding.record_surfaces.values())
        self.assertEqual(surfaces[:28], (("credits.main_name",),) * 28)
        self.assertEqual(surfaces[28:], (("credits.test_name",),) * 12)

    def test_surface_geometry_matches_both_fixed_credit_grids(self) -> None:
        catalog = load_surfaces()
        expected = {
            "credits.main_name": (
                ("font16", 1, "glyph_cells", 6, 6),
                ("font16", 1, "pixels", 96, 18),
            ),
            "credits.test_name": (
                ("font16", 1, "glyph_cells", 7, 7),
                ("font16", 1, "pixels", 112, 18),
            ),
        }
        for name, wanted in expected.items():
            surface = catalog.surface(name)
            actual = tuple(
                (
                    layout.font,
                    layout.rows,
                    layout.width.unit,
                    layout.width.value,
                    layout.glyphs,
                )
                for layout in (surface.ja, surface.en)
            )
            self.assertEqual(actual, wanted)


if __name__ == "__main__":
    unittest.main()
