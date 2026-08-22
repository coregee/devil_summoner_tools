from __future__ import annotations

import hashlib
import unittest

from psp.rom.util.catalog import load_catalog, validate_source
from psp.rom.util.iso9660 import read_iso9660_file
from psp.text.util.assets import load_config_asset
from psp.text.util.config_menu import build_config_text


class ConfigMenuTextTests(unittest.TestCase):
    def test_asset_separates_runtime_rows_from_context_help(self) -> None:
        rows = load_config_asset()
        self.assertEqual(len(rows), 38)
        self.assertEqual(sum(role == "context_help" for role, *_rest in rows), 9)
        self.assertEqual(sum(role == "mode" for role, *_rest in rows), 2)

    def test_private_source_reproduces_the_legacy_output_when_available(self) -> None:
        disc = load_catalog()["game"]
        if not disc.source_path.is_file():
            self.skipTest("private PSP source ISO is unavailable")
        source_iso = validate_source(disc, verify_hash=False)
        _extent, source = read_iso9660_file(
            source_iso, disc.entries["regdata"].path
        )
        result = build_config_text(source)
        self.assertEqual(len(result.translations), 9)
        self.assertEqual(
            hashlib.sha256(result.data).hexdigest(),
            "a4d7d6b4e049968431193eb0ef3ad5afa3c36bb37f9737d65d2c3aecff56b9e0",
        )
        self.assertEqual(
            hashlib.sha256(result.member).hexdigest(),
            "453a48e898a1abed6ba4562bed3f97ca3afa00494fccabed65fa33d2e4e6a509",
        )


if __name__ == "__main__":
    unittest.main()
