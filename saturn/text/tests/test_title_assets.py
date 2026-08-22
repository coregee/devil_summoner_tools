from __future__ import annotations

import sys
import unittest
from pathlib import Path

TEXT_ROOT = Path(__file__).resolve().parents[1]
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

from util.assets import BINDING_ROOT, load_asset, load_binding  # noqa: E402


class TitleAssetTests(unittest.TestCase):
    def test_visual_wording_is_authored_and_physically_bound(self) -> None:
        binding = load_binding(BINDING_ROOT / "title.json")
        asset = load_asset(binding.asset)

        self.assertEqual(
            asset.field("press_start_button.text").reference,
            "PRESS START BUTTON",
        )
        self.assertEqual(asset.field("start.text").reference, "START")
        self.assertEqual(asset.field("option.text").reference, "OPTION")
        self.assertEqual(
            set(binding.record_surfaces.values()),
            {
                ("title.press_start",),
                ("title.menu_start",),
                ("title.menu_option",),
            },
        )


if __name__ == "__main__":
    unittest.main()
