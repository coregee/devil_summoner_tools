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
        result = engine_build.build_fmv_subtitles(stock, battle.data)
        self.assertEqual(len(result.data), len(stock))
        self.assertEqual(
            len(title.patches)
            + len(config.patches)
            + len(command_help.patches)
            + len(event_window.patches)
            + len(battle.patches)
            + len(result.patches),
            96,
        )
        self.assertEqual(source["boot"]["lba"], 21760)
        self.assertEqual(len(eboot) - len(stock), engine_build.EBOOT_TRAILING_SIZE)
        self.assertEqual(
            hashlib.sha256(result.data).hexdigest(),
            "506039ade0d6181ac5ca6b2275d72c5eedf03149bbc9d05f9a56f5f44682df89",
        )


if __name__ == "__main__":
    unittest.main()
