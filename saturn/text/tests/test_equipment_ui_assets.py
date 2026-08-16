from __future__ import annotations

import sys
import unittest
from pathlib import Path


TEXT_ROOT = Path(__file__).resolve().parents[1]
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

from util.assets import load_asset  # noqa: E402
from util.surfaces import load_surfaces  # noqa: E402


class EquipmentUiAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.equipment = load_asset("ui/equipment.json")
        cls.status = load_asset("ui/status.json")
        cls.shop = load_asset("facilities/shop.json")
        cls.surfaces = load_surfaces()

    def test_actions_and_shared_labels_have_one_editable_owner(self) -> None:
        self.assertEqual(
            {
                key: entry.fields["text"].translation
                for key, entry in self.equipment.entries.items()
            },
            {"recommend": "Auto", "unequip": "Unequip"},
        )
        self.assertEqual(self.status.field("strength.text").translation, "St")
        self.assertEqual(
            self.status.field("magic_defense.text").translation, "Mag Efc"
        )
        self.assertEqual(
            self.shop.field("inventory_label.text").translation, "Inv."
        )

    def test_equipment_runtime_limits_are_explicit(self) -> None:
        expected = {
            "equipment.action": ("font8", 1, "pixels", 40),
            "equipment.base_stat": ("font8", 1, "pixels", 23),
            "equipment.derived_stat": ("font8", 1, "pixels", 48),
            "equipment.item_name": ("font8", 1, "pixels", 80),
            "shop.character_name": ("font8", 1, "pixels", 72),
            "shop.inventory_label": ("font8", 1, "pixels", 16),
        }
        for name, geometry in expected.items():
            with self.subTest(surface=name):
                layout = self.surfaces.surface(name).en
                self.assertEqual(
                    (layout.font, layout.rows, layout.width.unit, layout.width.value),
                    geometry,
                )


if __name__ == "__main__":
    unittest.main()
