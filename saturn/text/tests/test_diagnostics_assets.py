from __future__ import annotations

import sys
import unittest
from pathlib import Path


TEXT_ROOT = Path(__file__).resolve().parents[1]
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

from util.assets import BINDING_ROOT, load_asset, load_binding  # noqa: E402
from util.surfaces import load_surfaces  # noqa: E402


class DiagnosticsAssetTests(unittest.TestCase):
    def test_all_eleven_physical_fields_have_one_authored_owner(self) -> None:
        expected = {
            "sound_test.json": (
                "diagnostics/sound_test.json",
                "game.sndtest_fields.",
                4,
            ),
            "test_3d.json": (
                "diagnostics/test_3d.json",
                "game.test3d_fields.",
                7,
            ),
        }
        for filename, (asset, prefix, count) in expected.items():
            with self.subTest(binding=filename):
                binding = load_binding(BINDING_ROOT / filename)
                self.assertEqual(binding.asset.as_posix(), asset)
                self.assertEqual(len(binding.records), count)
                self.assertTrue(all(key.startswith(prefix) for key in binding.records))

    def test_trailing_layout_spaces_remain_authored_and_capacity_bounded(self) -> None:
        sound = load_asset("diagnostics/sound_test.json")
        test_3d = load_asset("diagnostics/test_3d.json")
        self.assertEqual(
            sound.entries["request_number"].fields["text"].translation,
            "Req No ",
        )
        self.assertEqual(
            test_3d.entries["control"].fields["text"].translation,
            "ctl   ",
        )
        surfaces = load_surfaces()
        for name in ("diagnostics.sound_test", "diagnostics.test_3d"):
            surface = surfaces.surface(name)
            self.assertEqual(
                (
                    surface.en.font,
                    surface.en.rows,
                    surface.en.width.unit,
                    surface.en.width.value,
                ),
                (None, 1, "glyph_cells", 19),
            )


if __name__ == "__main__":
    unittest.main()
