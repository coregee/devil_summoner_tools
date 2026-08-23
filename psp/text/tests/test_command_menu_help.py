from __future__ import annotations

import hashlib
import unittest

from psp.rom.util.catalog import load_catalog, validate_source
from psp.rom.util.iso9660 import read_iso9660_file
from psp.text.util.command_menu_help import build_command_menu_help


class CommandMenuHelpTextTests(unittest.TestCase):
    def test_private_source_reproduces_all_command_and_config_slots(self) -> None:
        disc = load_catalog()["game"]
        if not disc.source_path.is_file():
            self.skipTest("private PSP source ISO is unavailable")
        source_iso = validate_source(disc, verify_hash=False)
        _extent, source = read_iso9660_file(source_iso, disc.entries["regdata"].path)
        result = build_command_menu_help(source)
        self.assertEqual(len(result.translations), 48)
        self.assertEqual(result.translations[0], "Equipped cursed gear cannot be discarded.")
        self.assertEqual(result.translations[-1], "No usable magic.")
        self.assertEqual(result.changed_byte_count, 2964)
        self.assertEqual(
            hashlib.sha256(result.member).hexdigest(),
            "4f2c96d4f05fb903bdc04b92ec041f7ebb6af3e8d44cf0acadec73de73fcdbff",
        )
        self.assertEqual(
            hashlib.sha256(result.data).hexdigest(),
            "ede045315af097db4804ac66a8882a6c3a877423bc5f3d591ff7f02fa2eaf57a",
        )


if __name__ == "__main__":
    unittest.main()
