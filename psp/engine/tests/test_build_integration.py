from __future__ import annotations

import hashlib
import unittest

from psp.engine import build as engine_build
from psp.engine.surfaces.title_help_ui import build_title_help_ui
from psp.rom.util.catalog import load_catalog


class PspEngineBuildIntegrationTests(unittest.TestCase):
    def test_private_boot_reproduces_the_configured_surface_when_available(
        self,
    ) -> None:
        disc = load_catalog()["game"]
        if not disc.source_path.is_file():
            self.skipTest("private PSP source ISO is unavailable")
        stock, eboot, source = engine_build._source_entries()
        result = build_title_help_ui(stock, engine_build._metric_widths())
        self.assertEqual(len(result.data), len(stock))
        self.assertEqual(len(result.patches), 6)
        self.assertEqual(source["boot"]["lba"], 21760)
        self.assertEqual(len(eboot) - len(stock), engine_build.EBOOT_TRAILING_SIZE)
        self.assertEqual(
            hashlib.sha256(result.data).hexdigest(),
            "b42a8882c88ddad77339542d304a0a066b8f802b6784e0b0e37041dc6074fe11",
        )


if __name__ == "__main__":
    unittest.main()
