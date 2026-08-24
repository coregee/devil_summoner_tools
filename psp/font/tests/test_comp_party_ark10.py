from __future__ import annotations

import hashlib
import unittest

from psp.font.util.comp_party_ark10 import build_comp_party_ark10
from psp.font.util.eve_ascii import build_eve_ascii
from psp.rom.util.catalog import load_catalog, validate_source
from psp.rom.util.iso9660 import read_iso9660_file


class CompPartyArk10Tests(unittest.TestCase):
    def test_private_source_reproduces_the_checked_projection_when_available(self) -> None:
        disc = load_catalog()["game"]
        if not disc.source_path.is_file():
            self.skipTest("private PSP source ISO is unavailable")
        source_iso = validate_source(disc, verify_hash=False)
        _extent, source = read_iso9660_file(source_iso, disc.entries["eve_files"].path)
        eve_ascii = build_eve_ascii(source)
        result = build_comp_party_ark10(source, eve_ascii.data)
        self.assertEqual(result.added_changed_byte_count, 1221)
        self.assertEqual(result.changed_byte_count, 2864)
        self.assertEqual(len(result.mappings), 95)
        self.assertEqual(len(result.changed_codes), 94)
        self.assertEqual(
            hashlib.sha256(result.data).hexdigest(),
            "5b2c21c8b74a25227c8dd14938e4099e2a88cb2662a9b534fd29956d0f3bad90",
        )


if __name__ == "__main__":
    unittest.main()
