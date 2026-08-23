from __future__ import annotations

import unittest

from psp.engine.surfaces.battle_console import (
    OUTPUT_BODY_OFFSET,
    build_battle_console,
    build_patches,
)
from psp.rom.util.catalog import load_catalog


class BattleConsoleRuntimeTests(unittest.TestCase):
    def test_declarative_recipe_retains_the_two_legacy_instructions(self) -> None:
        patches = build_patches(OUTPUT_BODY_OFFSET)
        self.assertEqual(
            [
                (patch.address, patch.expected.hex(), patch.replacement.hex())
                for patch in patches
            ],
            [
                (0x0006B874, "00089224", "00049224"),
                (0x0006BB40, "00086424", "00046424"),
            ],
        )

    def test_recipe_rejects_an_uncomposed_text_body_offset(self) -> None:
        with self.assertRaisesRegex(ValueError, "expected 0x400"):
            build_patches(0x800)
        with self.assertRaisesRegex(TypeError, "must be an integer"):
            build_patches(True)

    def test_private_boot_accepts_both_guarded_sites_when_available(self) -> None:
        disc = load_catalog()["game"]
        if not disc.source_path.is_file():
            self.skipTest("private PSP source ISO is unavailable")
        from psp.engine.build import _source_entries

        stock, _eboot, _source = _source_entries()
        result = build_battle_console(stock, stock, OUTPUT_BODY_OFFSET)
        self.assertEqual(len(result.data), len(stock))
        self.assertEqual(len(result.patches), 2)
        self.assertNotEqual(result.data, stock)


if __name__ == "__main__":
    unittest.main()
