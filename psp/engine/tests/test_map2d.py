from __future__ import annotations

import hashlib
import unittest

from psp.engine import build as engine_build
from psp.engine.surfaces.map2d import build_map2d


class Map2dRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        stock, _eboot, _source = engine_build._source_entries()
        title = engine_build.build_title_help_ui(stock, engine_build._metric_widths())
        config = engine_build.build_config_menu(stock, title.data, engine_build._config_font_contract())
        help_build = engine_build.build_command_menu_help(stock, config.data)
        event = engine_build.build_event_window(stock, help_build.data, engine_build.load_eve_widths())
        name = engine_build.build_name_entry(stock, event.data)
        cls.stock = stock
        cls.name = name
        cls.build = build_map2d(stock, name.data, engine_build._map2d_font_contract())

    def test_sixteen_writes_match_the_original_map2d_payload(self) -> None:
        writes = self.build.runtime.writes
        self.assertEqual(len(writes), 16)
        self.assertEqual(sum(len(write.data) for write in writes), 2049)
        self.assertEqual(
            hashlib.sha256(b"".join(write.data for write in writes)).hexdigest(),
            "a08359da6376d8079910b960a3edcd12b0c9c59fbf2e63d3fc5dc2c169f0b4b5",
        )
        self.assertEqual(
            tuple((write.name, write.address, len(write.data)) for write in writes),
            (
                ("map2d_label_yes", 0x190810, 6),
                ("map2d_label_no", 0x190816, 4),
                ("map2d_talk_prompt", 0x190824, 28),
                ("map2d_city_header_draw_call", 0x0A377C, 4),
                ("map2d_ward_header_draw_call", 0x0A3804, 4),
                ("map2d_ward_marker_draw_call", 0x0A4300, 4),
                ("map2d_city_overview_draw_call", 0x0A44B8, 4),
                ("map2d_top_prompt_draw_call", 0x0A2B58, 4),
                ("map2d_top_yes_normal_draw_call", 0x0A2B7C, 4),
                ("map2d_top_no_draw_call", 0x0A2B98, 4),
                ("map2d_top_yes_selected_draw_call", 0x0A2C00, 4),
                ("map2d_dynamic_draw_wrapper", 0x171800, 1316),
                ("map2d_top_draw_wrapper", 0x172400, 484),
                ("map2d_widths", 0x172600, 95),
                ("map2d_top_rows", 0x172680, 44),
                ("map2d_fixed_rows", 0x172700, 40),
            ),
        )

    def test_runtime_tables_and_name_dependency_are_explicit(self) -> None:
        runtime = self.build.runtime.runtime_patch
        self.assertEqual((self.build.runtime_used_size, self.build.runtime_capacity), (1979, 2148))
        self.assertEqual(len(runtime.width_table), 95)
        self.assertEqual(len(runtime.top_row_table), 44)
        self.assertEqual(len(runtime.fixed_row_table), 40)
        with self.assertRaisesRegex(ValueError, "requires the NAME"):
            build_map2d(self.stock, self.stock, engine_build._map2d_font_contract())


if __name__ == "__main__":
    unittest.main()
