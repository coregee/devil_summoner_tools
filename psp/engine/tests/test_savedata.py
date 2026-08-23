from __future__ import annotations

import hashlib
import struct
import unittest

from psp.engine import build as engine_build
from psp.engine.surfaces.savedata import build_savedata
from psp.engine.surfaces.savedata_runtime import (
    SAVEDATA_DETAIL_WRAPPER_ADDRESS,
    SAVEDATA_LOCATION_TEXT_BLOB_ADDRESS,
    SAVEDATA_LOCATION_TEXT_CAVE_END_ADDRESS,
)


class SavedataRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        stock, _eboot, _source = engine_build._source_entries()
        title = engine_build.build_title_help_ui(stock, engine_build._metric_widths())
        config = engine_build.build_config_menu(stock, title.data, engine_build._config_font_contract())
        command = engine_build.build_command_menu_help(stock, config.data)
        event = engine_build.build_event_window(stock, command.data, engine_build.load_eve_widths())
        name = engine_build.build_name_entry(stock, event.data)
        cls.stock = stock
        cls.name = name
        cls.build = build_savedata(stock, name.data)

    def test_runtime_matches_the_mature_patch(self) -> None:
        runtime = self.build.runtime
        self.assertEqual(len(runtime.writes), 13)
        self.assertEqual((self.build.runtime_used_size, self.build.runtime_capacity), (1500, 1505))
        self.assertEqual(
            hashlib.sha256(b"".join(write.data for write in runtime.writes)).hexdigest(),
            "82bd900fe65b31d7e416b9f647ef03cab4eabcff28587471647e5893916775b6",
        )
        self.assertEqual((runtime.detail_wrapper.address, len(runtime.detail_wrapper.data)), (SAVEDATA_DETAIL_WRAPPER_ADDRESS, 892))
        self.assertEqual(len(runtime.location_text_blob), 321)
        self.assertEqual(SAVEDATA_LOCATION_TEXT_CAVE_END_ADDRESS - SAVEDATA_LOCATION_TEXT_BLOB_ADDRESS, 324)

    def test_physical_location_selector_and_text_are_complete(self) -> None:
        runtime = self.build.runtime
        self.assertEqual(len(runtime.location_ids), 144)
        self.assertEqual(set(runtime.location_ids), set(range(24)))
        offsets = struct.unpack("<24H", runtime.location_offsets)
        decoded = []
        for offset in offsets:
            end = runtime.location_text_blob.index(0, offset)
            decoded.append(runtime.location_text_blob[offset:end].decode("ascii"))
        self.assertEqual(tuple(decoded), self.build.text.locations)
        self.assertIn(self.build.text.unknown.encode("ascii") + b"\0", runtime.text_blob)

    def test_name_dependency_and_stock_source_are_guarded(self) -> None:
        with self.assertRaisesRegex(ValueError, "English NAME runtime"):
            build_savedata(self.stock, self.stock)
        changed = bytearray(self.stock)
        changed[0xEE98 + 0x80] ^= 1
        with self.assertRaisesRegex(ValueError, "BOOT source contract changed"):
            build_savedata(bytes(changed), self.name.data)


if __name__ == "__main__":
    unittest.main()
