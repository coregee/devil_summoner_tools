from __future__ import annotations

import hashlib
import unittest

from psp.engine import build as engine_build
from psp.engine.surfaces.command_menu_help import (
    build_command_menu_help,
    build_runtime,
    load_eve_widths,
)
from psp.rom.util.catalog import load_catalog


class CommandMenuHelpEngineTests(unittest.TestCase):
    def test_emitters_match_the_original_runtime(self) -> None:
        runtime = build_runtime(bytes([3] * 95))
        self.assertEqual(len(runtime.writes), 7)
        self.assertEqual(len(runtime.draw_wrapper.data), 196)
        self.assertEqual(len(runtime.frame_wrapper.data), 164)
        self.assertEqual(len(runtime.append_helper.data), 136)
        self.assertEqual(len(runtime.state), 139)
        self.assertEqual(
            hashlib.sha256(runtime.draw_wrapper.data).hexdigest(),
            "cc6b14d2de64a64f380e7eb3492d20cff5253578ede0f4d958f2b70690f36a23",
        )
        self.assertEqual(
            hashlib.sha256(runtime.frame_wrapper.data).hexdigest(),
            "9fe9aeb33df67e7e123240c379a150032a8540783a66c8e5f8d8575ebbe61a4b",
        )
        self.assertEqual(
            hashlib.sha256(runtime.append_helper.data).hexdigest(),
            "e98fb6eece03570dbaea2d19cb3cac8f32b76e518ca6f8243170a7440b989f94",
        )

    def test_generated_font_widths_feed_the_runtime_verbatim(self) -> None:
        widths = load_eve_widths()
        runtime = build_runtime(widths)
        self.assertEqual(runtime.width_table, widths)
        self.assertEqual(runtime.writes[0].data, widths)
        self.assertEqual(min(widths), 3)
        self.assertLessEqual(max(widths), 14)

    def test_private_boot_accepts_all_seven_checked_writes(self) -> None:
        disc = load_catalog()["game"]
        if not disc.source_path.is_file():
            self.skipTest("private PSP source ISO is unavailable")
        stock, _eboot, _source = engine_build._source_entries()
        result = build_command_menu_help(stock, stock)
        self.assertEqual(len(result.patches), 7)
        self.assertEqual(len(result.data), len(stock))


if __name__ == "__main__":
    unittest.main()
