from __future__ import annotations

import hashlib
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

import engine.surfaces.credits_ui as credits  # noqa: E402


MATURE_HASH = "cc5afd6298679e23f4fc3bacac1e06348b78c50c24f7e0b53acee0d8d802f854"


class CreditsUiEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.build = credits.build_credits_ui()
        cls.runtime = credits._build_runtime()
        cls.config = credits._configuration()
        cls.patches = {row.name: row for row in cls.build.patches}

    def test_mature_output_and_typed_recipe_inventory_are_exact(self) -> None:
        self.assertEqual(len(self.build.data), credits.TARGET_SIZE)
        self.assertEqual(hashlib.sha256(self.build.data).hexdigest(), MATURE_HASH)
        self.assertEqual(len(self.build.patches), 10)
        self.assertEqual(
            [row.replacement.kind for row in self.config.patches[credits.TARGET]],
            [
                "assembly",
                "assembly",
                "assembly",
                "generated",
                "generated",
                "assembly",
                "pointer",
                "linked_pointer",
                "assembly",
                "assembly",
            ],
        )
        self.assertEqual(
            [row.group for row in self.build.patches],
            ["credits.runtime"] * 5 + ["credits.main"] * 3 + ["credits.test"] * 2,
        )

    def test_runtime_layout_and_default_component_hashes_are_exact(self) -> None:
        self.assertEqual(self.build.runtime_used_size, 8528)
        self.assertEqual(self.build.runtime_capacity, 23888)
        expected = {
            "renderer": "67df67fb914be3b2660055134d30da2af59a72fb6d259b3cc68a6b5537c864db",
            "test_main_wrapper": "7d3ba0c73c0ea2e2a51b20e07a59d007e58bbe464db3e59fdbab0f68fe025d32",
            "test_extra_wrapper": "a1aa8e8809d511998eb44c95da8fa26b84317e54524fd5c718df228f67421338",
            "offset_table": "d6f3ee1517c5a732f69264a7c402b95adc79302dbbaccb802717be05f20db467",
            "bitmap_pool": "d84b895b642abf1e9699631717f6d027f96e5e07d646df8614c3c5bd9628531d",
            "main_name_hook": "820ccd1192dfe8211f1ac9f099f454f66bfb0e1a4aea7b1bbe9d570d3b75f1d2",
        }
        for name, digest in expected.items():
            self.assertEqual(
                hashlib.sha256(self.patches[name].replacement).hexdigest(), digest
            )
        self.assertEqual(
            self.runtime.compressed_fields,
            (
                "game.end_roll_names.o019ff0",
                "game.end_roll_names.o01a008",
            ),
        )
        self.assertEqual(self.runtime.widths[6], 100)
        self.assertEqual(self.runtime.widths[8], 99)
        self.assertEqual(self.runtime.widths[33], 100)

    def test_all_assembly_and_runtime_provenance_is_explicit(self) -> None:
        self.assertEqual(set(self.build.asset_files), set(credits.ASSET_FILES))
        self.assertEqual(set(self.build.assembly_files), set(credits.ASSEMBLY_FILES))
        self.assertEqual(
            set(self.build.runtime_input_files), set(credits.RUNTIME_INPUT_FILES)
        )
        self.assertEqual(
            dict(self.build.source_inputs),
            {f"game:{credits.TARGET}": credits._sha256(credits._stock_source())},
        )
        self.assertFalse(
            any("rom/extracted" in path.as_posix() for path in self.build.runtime_input_files)
        )

    def test_name_edit_changes_only_generated_bitmap_data(self) -> None:
        values = list(credits._bound_names())
        values[0] = (values[0][0], "K. Okada")
        with patch.object(credits, "_bound_names", return_value=tuple(values)):
            edited = credits.build_credits_ui()
        edited_patches = {row.name: row for row in edited.patches}
        self.assertNotEqual(edited.data, self.build.data)
        self.assertNotEqual(
            edited_patches["bitmap_pool"].replacement,
            self.patches["bitmap_pool"].replacement,
        )
        for name in (
            "renderer",
            "test_main_wrapper",
            "test_extra_wrapper",
            "offset_table",
            "main_name_hook",
            "main_vdp_literal",
            "main_renderer_literal",
            "test_main_trampoline",
            "test_extra_trampoline",
        ):
            self.assertEqual(
                edited_patches[name].replacement, self.patches[name].replacement
            )

    def test_unsupported_or_overlong_names_fail_closed(self) -> None:
        values = list(credits._bound_names())
        values[0] = (values[0][0], "A" * 19)
        with patch.object(credits, "_bound_names", return_value=tuple(values)), self.assertRaisesRegex(
            ValueError, "1 to 18"
        ):
            credits._build_runtime()
        values[0] = (values[0][0], "Name {first_name}")
        with patch.object(credits, "_bound_names", return_value=tuple(values)), self.assertRaisesRegex(
            ValueError, "unsupported"
        ):
            credits._build_runtime()

    def test_config_and_source_drift_are_rejected(self) -> None:
        recipes = list(self.config.patches[credits.TARGET])
        recipes[0] = replace(recipes[0], address=recipes[0].address + 2)
        drifted = replace(
            self.config, patches={credits.TARGET: tuple(recipes)}
        )
        with patch.object(credits, "load_patch_recipe_configuration", return_value=drifted), self.assertRaisesRegex(
            ValueError, "inventory drifted"
        ):
            credits._configuration()
        stock = bytearray(credits._stock_source())
        stock[-1] ^= 1
        with self.assertRaisesRegex(ValueError, "stock target"):
            credits._validate_sources(self.config, bytes(stock))


if __name__ == "__main__":
    unittest.main()
