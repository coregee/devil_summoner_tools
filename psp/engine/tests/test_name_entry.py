from __future__ import annotations

import hashlib
import struct
import unittest

from psp.engine import build as engine_build
from psp.engine.surfaces.name_entry import build_name_entry
from psp.engine.surfaces.name_entry_runtime import (
    NAME_FIELD_LIMITS,
    NAME_GRID_DONE,
    NAME_GRID_SENTINEL,
    NAME_LABEL_DRAW_CALL_ADDRESS,
    NAME_PROFILE_FIELD_OFFSETS,
)


class NameEntryRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        stock, _eboot, _source = engine_build._source_entries()
        title = engine_build.build_title_help_ui(stock, engine_build._metric_widths())
        config = engine_build.build_config_menu(stock, title.data, engine_build._config_font_contract())
        command = engine_build.build_command_menu_help(stock, config.data)
        event = engine_build.build_event_window(stock, command.data, engine_build.load_eve_widths())
        cls.stock = stock
        cls.event = event
        cls.build = build_name_entry(stock, event.data)

    def test_runtime_matches_the_mature_patch(self) -> None:
        runtime = self.build.runtime
        self.assertEqual(len(runtime.writes), 138)
        self.assertEqual(self.build.runtime_used_size, 3425)
        self.assertEqual(self.build.runtime_capacity, 3936)
        self.assertEqual(
            hashlib.sha256(b"".join(write.data for write in runtime.writes)).hexdigest(),
            "2d2fb1206ca9b4d9fc4b373a61c5be1429e46c49d5555f54c55d2f25796b377c",
        )
        self.assertEqual(
            hashlib.sha256(runtime.label_draw_wrapper.data).hexdigest(),
            "7c00aabdef6065bf3f3fe40809e3d201aad476b0b3d55541af0042a992380a29",
        )

    def test_five_fields_and_native_grid_geometry_are_exact(self) -> None:
        self.assertEqual(NAME_FIELD_LIMITS, (8, 8, 8, 8, 8))
        self.assertEqual(
            NAME_PROFILE_FIELD_OFFSETS,
            {"first": 0, "last": 8, "codename": 16, "city": 24, "ward": 32},
        )
        cells = struct.unpack("<152H", self.build.runtime.write("name_grid_upper_primary").data)
        self.assertEqual(cells[:19], (NAME_GRID_SENTINEL,) * 19)
        self.assertEqual(cells[4 * 19 + 15], NAME_GRID_DONE)
        self.assertEqual(
            self.build.runtime.write("name_grid_upper_primary").data,
            self.build.runtime.write("name_grid_upper_secondary").data,
        )

    def test_event_dependency_and_stock_source_are_guarded(self) -> None:
        with self.assertRaisesRegex(ValueError, "EVENT runtime foundation"):
            build_name_entry(self.stock, self.stock)
        changed = bytearray(self.stock)
        changed[NAME_LABEL_DRAW_CALL_ADDRESS + 0x80] ^= 1
        with self.assertRaisesRegex(ValueError, "BOOT source contract changed"):
            build_name_entry(bytes(changed), self.event.data)


if __name__ == "__main__":
    unittest.main()
