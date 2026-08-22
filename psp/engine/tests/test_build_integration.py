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
        result = engine_build.build_config_menu(
            stock, title.data, engine_build._config_font_contract()
        )
        self.assertEqual(len(result.data), len(stock))
        self.assertEqual(len(title.patches) + len(result.patches), 51)
        self.assertEqual(source["boot"]["lba"], 21760)
        self.assertEqual(len(eboot) - len(stock), engine_build.EBOOT_TRAILING_SIZE)
        self.assertEqual(
            hashlib.sha256(result.data).hexdigest(),
            "06666c15217b80bbdc3b0ce6d31f7cc5efb56fb262f688a449963ac7df108369",
        )


if __name__ == "__main__":
    unittest.main()
