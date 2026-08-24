from __future__ import annotations

import hashlib
import unittest

from psp.engine import build as engine_build
from psp.engine.surfaces.battle_names import build_battle_names
from psp.engine.surfaces.compendium import build_compendium
from psp.engine.surfaces.command_menu_help import load_eve_widths


class BattleNamesRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        stock, _eboot, _source = engine_build._source_entries()
        cls.stock = stock
        cls.compendium = build_compendium(stock, stock, load_eve_widths())
        cls.build = build_battle_names(
            stock,
            cls.compendium.data,
            engine_build._config_font_contract(),
            cls.compendium.names.dvlname_table,
        )

    def test_two_consumers_match_the_mature_patch(self) -> None:
        self.assertEqual(len(self.build.patches), 24)
        self.assertEqual(sum(len(patch.replacement) for patch in self.build.patches), 1396)
        self.assertEqual(
            hashlib.sha256(
                b"".join(patch.replacement for patch in self.build.patches)
            ).hexdigest(),
            "d0225ff02e9ce7317f84751f97b4b175500283d81886e800b9209578af0c6d30",
        )
        self.assertEqual(self.build.result_labels, ("(None)", "Life Stone", "Bead"))
        self.assertEqual(self.build.mysterious_man, "Mysterious Man")

    def test_shared_ark12_tables_cover_name_entry_and_full_dvl_names(self) -> None:
        runtime = self.build.runtime
        self.assertEqual(len(runtime.code_table), 95)
        self.assertEqual(len(runtime.width_table), 95)
        self.assertEqual(len(runtime.draw_wrapper.data), 472)
        self.assertEqual(len(runtime.result_draw_wrapper.data), 532)
        self.assertEqual(runtime.static_storage.hex(), "3c6862635461585e64627d3c505d")

    def test_compendium_name_table_dependency_is_explicit(self) -> None:
        with self.assertRaisesRegex(ValueError, "Compendium name-table owner"):
            build_battle_names(
                self.stock,
                self.stock,
                engine_build._config_font_contract(),
                self.compendium.names.dvlname_table,
            )


if __name__ == "__main__":
    unittest.main()
