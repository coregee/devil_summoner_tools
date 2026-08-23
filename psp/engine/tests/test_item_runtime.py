from __future__ import annotations

import hashlib
import unittest

from psp.engine import build as engine_build
from psp.engine.surfaces.command_menu_help import load_eve_widths
from psp.engine.surfaces.compendium import build_compendium
from psp.engine.surfaces.item_runtime import build_item_runtime


class ItemRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        stock, _eboot, _source = engine_build._source_entries()
        cls.stock = stock
        cls.compendium = build_compendium(stock, stock, load_eve_widths())
        cls.build = build_item_runtime(stock, cls.compendium.data, engine_build._source_regdata(), load_eve_widths())

    def test_runtime_matches_the_mature_patch(self) -> None:
        runtime = self.build.runtime
        self.assertEqual(len(self.build.patches), 13)
        self.assertEqual(len(runtime.data_blob), 238)
        self.assertEqual(hashlib.sha256(runtime.data_blob).hexdigest(), "e0240f01f8fe70147740c09d22854280bd04b2568f52c7510a481c5c0b7ecef4")
        self.assertEqual(
            tuple((write.name, write.address, len(write.data)) for write in runtime.writes),
            (
                ("item_name_primary_dispatch", 0x00080034, 8),
                ("item_name_duplicate_dispatch", 0x00092DC4, 8),
                ("item_description_dispatch", 0x00092E7C, 8),
                ("item_event_decoder_call", 0x00073D14, 4),
                ("item_detail_route", 0x0003D834, 4),
                ("item_name_dispatch_trampoline", 0x00092DDC, 36),
                ("item_description_dispatch_trampoline", 0x00092E1C, 36),
                ("item_runtime_data", 0x0010884F, 238),
                ("item_event_wrapper", 0x00171D24, 124),
                ("item_name_stock_tail", 0x00171DA0, 92),
                ("item_name_resolver", 0x00172260, 236),
                ("item_name_wrapper", 0x00172360, 136),
                ("item_description_wrapper", 0x00172ABC, 376),
            ),
        )

    def test_id_255_guard_and_stock_fallback_model(self) -> None:
        runtime = self.build.runtime
        self.assertIsNone(runtime.resolve_record(255))
        self.assertIsNone(runtime.resolve_record(255, live_source_name=b"x" * 16))
        self.assertEqual(runtime.resolve_record(255, live_source_name=runtime.source_guard).name, "Back-Upper R")
        self.assertIsNone(runtime.resolve_record(1))
        self.assertEqual(runtime.resolve_record(280).name, "Death Tally")

    def test_compendium_dependency_is_explicit(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires the Compendium"):
            build_item_runtime(self.stock, self.stock, engine_build._source_regdata(), load_eve_widths())


if __name__ == "__main__":
    unittest.main()
