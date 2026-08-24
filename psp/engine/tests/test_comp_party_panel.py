from __future__ import annotations

import hashlib
import unittest

from psp.engine import build as engine_build


class CompPartyPanelRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        stock, _eboot, _source = engine_build._source_entries()
        cls.stock = stock
        title = engine_build.build_title_help_ui(stock, engine_build._metric_widths())
        config = engine_build.build_config_menu(
            stock, title.data, engine_build._config_font_contract()
        )
        command = engine_build.build_command_menu_help(stock, config.data)
        cls.compendium = engine_build.build_compendium(
            stock, command.data, engine_build.load_eve_widths()
        )
        cls.battle = engine_build.build_battle_names(
            stock,
            cls.compendium.data,
            engine_build._config_font_contract(),
            cls.compendium.names.dvlname_table,
        )
        cls.build = engine_build.build_comp_party_panel(
            stock,
            cls.battle.data,
            engine_build._comp_party_ark10_contract(),
            cls.compendium.names.dvlname_table,
            cls.battle.mysterious_man,
        )

    def test_four_writes_match_the_mature_patch(self) -> None:
        self.assertEqual(len(self.build.patches), 4)
        self.assertEqual(sum(len(patch.replacement) for patch in self.build.patches), 738)
        self.assertEqual(
            hashlib.sha256(
                b"".join(patch.replacement for patch in self.build.patches)
            ).hexdigest(),
            "5e038814b76694cf296906d414ac4b36bc72724657babe8a8e8af186dcab52f7",
        )
        self.assertEqual(
            hashlib.sha256(self.build.runtime.draw_wrapper.data).hexdigest(),
            "ed1e280d3616992aaa4c6d1e8037d37170aac10b3d1456b97f9fd2fc50040516",
        )

    def test_static_names_and_private_tables_are_exact(self) -> None:
        self.assertEqual(
            self.build.character_names,
            ("Rei Reiho", "Kyouji", "Taro Tanigawa", "Jiro Tanigawa", "Saburo Tanigawa"),
        )
        self.assertEqual(len(self.build.runtime.width_table), 95)
        self.assertEqual(len(self.build.runtime.character_table), 71)
        self.assertEqual(self.build.runtime_used_size, 734)
        self.assertEqual(self.build.runtime_capacity, 844)

    def test_battle_name_dependency_is_explicit(self) -> None:
        with self.assertRaisesRegex(ValueError, "battle-name owner"):
            engine_build.build_comp_party_panel(
                self.stock,
                self.compendium.data,
                engine_build._comp_party_ark10_contract(),
                self.compendium.names.dvlname_table,
                self.battle.mysterious_man,
            )


if __name__ == "__main__":
    unittest.main()
