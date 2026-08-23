from __future__ import annotations

import hashlib
import unittest

from psp.engine import build as engine_build
from psp.rom.util.catalog import load_catalog


class PspEngineBuildIntegrationTests(unittest.TestCase):
    def test_private_boot_reproduces_the_configured_surface_when_available(
        self,
    ) -> None:
        disc = load_catalog()["game"]
        if not disc.source_path.is_file():
            self.skipTest("private PSP source ISO is unavailable")
        stock, eboot, source = engine_build._source_entries()
        title = engine_build.build_title_help_ui(stock, engine_build._metric_widths())
        config = engine_build.build_config_menu(
            stock, title.data, engine_build._config_font_contract()
        )
        command_help = engine_build.build_command_menu_help(stock, config.data)
        event_window = engine_build.build_event_window(
            stock,
            command_help.data,
            engine_build.load_eve_widths(),
        )
        battle = engine_build.build_battle_console(
            stock,
            event_window.data,
            engine_build._battle_console_body_offset(),
        )
        compendium = engine_build.build_compendium(
            stock,
            battle.data,
            engine_build.load_eve_widths(),
        )
        result = engine_build.build_fmv_subtitles(stock, compendium.data)
        self.assertEqual(len(result.data), len(stock))
        self.assertEqual(
            len(title.patches)
            + len(config.patches)
            + len(command_help.patches)
            + len(event_window.patches)
            + len(battle.patches)
            + len(compendium.patches)
            + len(result.patches),
            108,
        )
        self.assertEqual(source["boot"]["lba"], 21760)
        self.assertEqual(len(eboot) - len(stock), engine_build.EBOOT_TRAILING_SIZE)
        self.assertEqual(
            hashlib.sha256(result.data).hexdigest(),
            "a81e3dc0b248e849dd26a3a6c93742e9b7ae39343a41ed7314a425a8a9878b3d",
        )


if __name__ == "__main__":
    unittest.main()
