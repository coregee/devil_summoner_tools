from __future__ import annotations

import hashlib
import unittest

from psp.font.util.eve_ascii import build_eve_ascii, glyph_code
from psp.rom.util.catalog import load_catalog, validate_source
from psp.rom.util.iso9660 import read_iso9660_file


class EveAsciiFontTests(unittest.TestCase):
    def test_packed_mapping_is_an_exact_permutation_of_the_owned_bank(self) -> None:
        characters = tuple(chr(value) for value in range(0x20, 0x7F))
        codes = tuple(glyph_code(character) for character in characters)
        self.assertEqual(tuple(sorted(codes)), tuple(range(0x1E20, 0x1E7F)))
        self.assertEqual(glyph_code("0"), 0x1E20)
        self.assertEqual(glyph_code("A"), 0x1E31)
        self.assertEqual(glyph_code("a"), 0x1E51)
        self.assertEqual(glyph_code(" "), 0x1E7E)

    def test_private_source_reproduces_the_original_eve_bank(self) -> None:
        disc = load_catalog()["game"]
        if not disc.source_path.is_file():
            self.skipTest("private PSP source ISO is unavailable")
        source_iso = validate_source(disc, verify_hash=False)
        _extent, source = read_iso9660_file(source_iso, disc.entries["eve_files"].path)
        result = build_eve_ascii(source)
        self.assertEqual(len(result.mappings), 95)
        self.assertEqual(len(result.advance_table), 95)
        self.assertEqual(result.changed_codes, tuple(range(0x1E20, 0x1E7E)))
        self.assertEqual(result.changed_byte_count, 1643)
        self.assertEqual(
            hashlib.sha256(result.atlas).hexdigest(),
            "6f893fdab8d7e13bf16e390ce3a04809fbef153eac7813a5e04d9e7dba44b2a4",
        )
        self.assertEqual(
            hashlib.sha256(result.data).hexdigest(),
            "c4b1a34ec0e6b05bec0afb0b581f2fbf5897e68ca488562f1b41c2f3d615378e",
        )


if __name__ == "__main__":
    unittest.main()
