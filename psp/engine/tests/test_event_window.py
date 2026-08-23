from __future__ import annotations

import hashlib
import struct
import unittest

from psp.engine import build as engine_build
from psp.engine.surfaces.command_menu_help import load_eve_widths
from psp.engine.surfaces.event_window import (
    CAVE_WRITE_NAMES,
    build_event_window,
    build_first_vwf_patch,
)
from psp.rom.util.catalog import load_catalog


def _runtime_fingerprint(runtime) -> str:
    digest = hashlib.sha256()
    for write in runtime.writes:
        digest.update(write.name.encode("ascii"))
        digest.update(struct.pack("<II", write.address, len(write.data)))
        digest.update(write.data)
    return digest.hexdigest()


class EventWindowRuntimeTests(unittest.TestCase):
    def test_readable_emitters_match_the_original_25_write_runtime(self) -> None:
        runtime = build_first_vwf_patch(load_eve_widths())
        self.assertEqual(len(runtime.writes), 25)
        self.assertEqual(len(runtime.decoder.data), 256)
        self.assertEqual(len(runtime.draw_wrapper.data), 240)
        self.assertEqual(
            _runtime_fingerprint(runtime),
            "5d4cf53a668d86f966dcdc45434b01688ef1be0d598b15cea088d934863bded1",
        )
        self.assertEqual(
            {write.name for write in runtime.writes if write.name in CAVE_WRITE_NAMES},
            set(CAVE_WRITE_NAMES),
        )

    def test_composed_surface_requires_the_shared_eve_width_table(self) -> None:
        disc = load_catalog()["game"]
        if not disc.source_path.is_file():
            self.skipTest("private PSP source ISO is unavailable")
        stock, _eboot, _source = engine_build._source_entries()
        with self.assertRaisesRegex(ValueError, "width table is not installed"):
            build_event_window(stock, stock, load_eve_widths())

    def test_private_boot_accepts_the_24_disjoint_foundation_writes(self) -> None:
        disc = load_catalog()["game"]
        if not disc.source_path.is_file():
            self.skipTest("private PSP source ISO is unavailable")
        stock, _eboot, _source = engine_build._source_entries()
        title = engine_build.build_title_help_ui(stock, engine_build._metric_widths())
        config = engine_build.build_config_menu(
            stock, title.data, engine_build._config_font_contract()
        )
        command = engine_build.build_command_menu_help(stock, config.data)
        result = build_event_window(stock, command.data, load_eve_widths())
        self.assertEqual(len(result.patches), 24)
        self.assertEqual(result.runtime_used_size, 1652)
        self.assertEqual(result.runtime_capacity, 1788)
        self.assertEqual(len(result.data), len(stock))


if __name__ == "__main__":
    unittest.main()
