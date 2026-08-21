from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from engine.surfaces.comp_menu import (  # noqa: E402
    BUILD_PATH,
    CONFIG_PATH,
    FONT8_METRICS_PATH,
    NORMCOM_OUTPUT_PATH,
    PANEL_CAVE,
    PANEL_LIMIT,
    _bind_patches,
    _panel_data,
    build_comp_menu,
)
from engine.core.patch_recipes import load_patch_recipe_configuration  # noqa: E402
from text.util.event_repack import FontMetrics  # noqa: E402


EXPECTED_HASH = "a3e0f479df32a8f181493adb5d4cba8e602617314419354446068c3b10636e7f"


class CompMenuEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.outputs = build_comp_menu()
        cls.manifest = json.loads(cls.outputs[BUILD_PATH].decode("utf-8"))
        cls.metrics = FontMetrics.load(FONT8_METRICS_PATH)

    def test_isolated_comp_core_is_reproduced(self) -> None:
        output = self.outputs[NORMCOM_OUTPUT_PATH]
        self.assertEqual(len(output), 352_360)
        self.assertEqual(hashlib.sha256(output).hexdigest(), EXPECTED_HASH)

    def test_manifest_records_the_composed_runtime_boundary(self) -> None:
        self.assertEqual(self.manifest["surface"], "comp.menu")
        self.assertEqual(
            self.manifest["base_normcom_sha256"],
            "4cbd006bb9df41e17b258562e19dd5275243ce35be753bd10beaba0aca046821",
        )
        self.assertEqual(
            self.manifest["patch_groups"],
            ["itemname_runtime", "normcom_help", "smallfont_vwf"],
        )
        self.assertEqual(self.manifest["patches"], 19)

    def test_party_panel_payload_is_derived_from_authored_names(self) -> None:
        data = _panel_data(self.metrics)
        self.assertEqual(
            {name: len(value) for name, value in data.items()},
            {
                "character_offsets": 12,
                "character_pool": 77,
                "long_name_bits": 40,
                "name_pool": 590,
                "high_name_pool": 278,
            },
        )
        self.assertTrue(any(data["long_name_bits"]))

    def test_dynamic_caves_fill_only_their_declared_regions(self) -> None:
        config = load_patch_recipe_configuration(
            CONFIG_PATH,
            surface="comp.menu",
            target_names={"NORMCOM.BIN"},
            input_names={"font8_metrics_sha256", "font16_metrics_sha256"},
        )
        patches = _bind_patches(config, self.metrics)
        panel = next(patch for patch in patches if patch.name == "character_panel_cave")
        self.assertEqual(panel.address, PANEL_CAVE)
        self.assertEqual(len(panel.replacement), PANEL_LIMIT - PANEL_CAVE)

    def test_executable_replacements_are_readable_assembly(self) -> None:
        config = load_patch_recipe_configuration(
            CONFIG_PATH,
            surface="comp.menu",
            target_names={"NORMCOM.BIN"},
            input_names={"font8_metrics_sha256", "font16_metrics_sha256"},
        )
        sources = {
            source.relative_to(SATURN_ROOT / "engine" / "asm").as_posix()
            for recipe in config.patches["NORMCOM.BIN"]
            for source in recipe.replacement.sources
        }
        self.assertEqual(
            sources,
            {
                "comp_menu/help_cursor_advance.s",
                "comp_menu/magic_grid_fixed_name.s",
                "comp_menu/magic_grid_full_name.s",
                "comp_menu/normcom_help_word.s",
                "font8_fixed_name.s",
                "comp_menu/party_panel.s",
                "equipment_item_name.s",
                "font16_subpixel_blitter.s",
                "font8_pixel_blitter.s",
            },
        )
        self.assertEqual(
            set(self.manifest["assembly_inputs"]),
            {f"saturn/engine/asm/{source}" for source in sources},
        )
        self.assertNotIn('"replacement"', CONFIG_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
