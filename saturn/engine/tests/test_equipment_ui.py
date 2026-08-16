from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from engine.build import (  # noqa: E402
    EQUIPMENT_BUILD_MANIFEST_PATH,
    EQUIPMENT_EVENT_OUTPUT_PATH,
    EQUIPMENT_NORMCOM_OUTPUT_PATH,
    build_equipment_surface,
)
from engine.surfaces.equipment_ui import (  # noqa: E402
    BUY_CAVE,
    BUY_CAVE_LIMIT,
    CONFIG_PATH,
    EQUIPMENT_LABEL_TARGETS,
    FONT8_METRICS_PATH,
    _bind_patches,
    _equipment_labels,
    _shop_character_data,
)
from engine.core.patch_recipes import (  # noqa: E402
    ASSEMBLY_ROOT,
    load_patch_recipe_configuration,
)
from text.util.event_repack import FontMetrics  # noqa: E402


EXPECTED_HASHES = {
    "EVENT.BIN": "697647ea5446901715b43fa175dcd293175746b393a1efa8d0eac7f8fa24f0ed",
    "NORMCOM.BIN": "a63ec7dbe6d5fdc03f9ff9f4c15fd556c26b9883dc0eb89e7bb18a70e5b58965",
}


class EquipmentUiEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.outputs = build_equipment_surface()
        cls.manifest = json.loads(
            cls.outputs[EQUIPMENT_BUILD_MANIFEST_PATH].decode("utf-8")
        )
        cls.metrics = FontMetrics.load(FONT8_METRICS_PATH)
        cls.config = load_patch_recipe_configuration(
            CONFIG_PATH,
            surface="equipment.ui",
            target_names={"EVENT.BIN", "NORMCOM.BIN"},
            input_names={"font8_metrics_sha256"},
        )
        cls.patches = _bind_patches(cls.config, cls.metrics)

    def test_mature_equipment_consumers_are_reproduced_exactly(self) -> None:
        outputs = {
            "EVENT.BIN": self.outputs[EQUIPMENT_EVENT_OUTPUT_PATH],
            "NORMCOM.BIN": self.outputs[EQUIPMENT_NORMCOM_OUTPUT_PATH],
        }
        for target, data in outputs.items():
            with self.subTest(target=target):
                self.assertEqual(
                    hashlib.sha256(data).hexdigest(), EXPECTED_HASHES[target]
                )

    def test_manifest_records_both_composed_bases_and_patch_sets(self) -> None:
        self.assertEqual(self.manifest["surface"], "equipment.ui")
        self.assertEqual(
            {target: row["surface"] for target, row in self.manifest["bases"].items()},
            {"EVENT.BIN": "fusion.menu", "NORMCOM.BIN": "comp.menu"},
        )
        self.assertEqual(
            self.manifest["patch_groups"],
            {
                "EVENT.BIN": ["itemname_runtime", "equipment_ui"],
                "NORMCOM.BIN": ["equipment_ui"],
            },
        )
        self.assertEqual(
            self.manifest["patches"], {"EVENT.BIN": 19, "NORMCOM.BIN": 6}
        )
        self.assertEqual(len(self.manifest["asset_inputs"]), 3)
        self.assertEqual(len(self.manifest["assembly_inputs"]), 7)

    def test_all_visible_labels_are_loaded_from_authored_assets(self) -> None:
        labels = _equipment_labels(self.metrics)
        self.assertEqual(len(labels), 16)
        self.assertEqual(
            [label.text for label in labels[:8]],
            ["Auto", "Unequip", "St", "In", "Ma", "Vi", "Ag", "Lu"],
        )
        self.assertEqual(
            [label.text for label in labels[8:]],
            [
                "Swd Atk",
                "Swd Acc",
                "Gun Atk",
                "Gun Acc",
                "Def",
                "Eva",
                "Mag Pwr",
                "Mag Efc",
            ],
        )
        matches, names = _shop_character_data(self.metrics)
        self.assertEqual(len(matches), 50)
        self.assertEqual(len(names), 66)

    def test_dynamic_caves_use_the_whole_declared_region(self) -> None:
        event = {patch.name: patch for patch in self.patches["EVENT.BIN"]}
        buy = event["buy_sell_name_cave"]
        self.assertEqual(buy.address, BUY_CAVE)
        self.assertEqual(len(buy.replacement), BUY_CAVE_LIMIT - BUY_CAVE)
        for target, patches in self.patches.items():
            with self.subTest(target=target):
                label = next(patch for patch in patches if patch.name == "label_drawer")
                cave, limit, _stock, _glyph = EQUIPMENT_LABEL_TARGETS[target]
                self.assertEqual(label.address, cave)
                self.assertEqual(len(label.replacement), limit - cave)

    def test_executable_replacements_are_readable_assembly(self) -> None:
        sources = {
            source.relative_to(ASSEMBLY_ROOT).as_posix()
            for recipes in self.config.patches.values()
            for recipe in recipes
            for source in recipe.replacement.sources
        }
        self.assertEqual(
            sources,
            {
                "font8_pixel_blitter.s",
                "equipment_ui/buy_sell_item_name.s",
                "equipment_ui/equipment_item_name.s",
                "equipment_ui/label_drawer.s",
                "equipment_ui/shop_character_name.s",
                "equipment_ui/shop_inventory_label.s",
                "equipment_ui/trampoline.s",
            },
        )
        for source in sources:
            text = (ASSEMBLY_ROOT / source).read_text(encoding="utf-8")
            self.assertNotIn(bytes.fromhex("d02134028b3c").hex(), text)
        self.assertNotIn('"replacement"', CONFIG_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
