from __future__ import annotations

import hashlib
import unittest

from psp.font.util.title_help import build_title_help_font16, load_config
from psp.rom.util.catalog import load_catalog, validate_source
from psp.rom.util.iso9660 import read_iso9660_file


class TitleHelpFont16Tests(unittest.TestCase):
    def test_config_owns_exactly_the_authored_title_alphabet(self) -> None:
        config = load_config()
        characters = {character for character, _code in config.glyphs}
        self.assertEqual(characters, set(" CDFRSVacdefghilmnorstuvwy."))
        self.assertEqual(
            config.changed_codes,
            tuple(code for _character, code in config.glyphs if code),
        )

    def test_private_source_reproduces_the_legacy_output_when_available(self) -> None:
        disc = load_catalog()["game"]
        if not disc.source_path.is_file():
            self.skipTest("private PSP source ISO is unavailable")
        source_iso = validate_source(disc, verify_hash=False)
        _extent, source = read_iso9660_file(
            source_iso, disc.entries["datapack"].path
        )
        result = build_title_help_font16(source)
        self.assertEqual(result.changed_byte_count, 1139)
        self.assertEqual(
            hashlib.sha256(result.data).hexdigest(),
            "f2ac2e9b96739384fa2c4fc07e9152898ab1a2ee2f7451e2061c6b76352ff77d",
        )
        self.assertEqual(
            hashlib.sha256(result.member).hexdigest(),
            "35a7bdf0cb47d4b3c7c2069594c4b7dc55ac2d04358b834019d3e7d680df45b4",
        )
        self.assertEqual(dict(result.advances)[" "], 4)
        self.assertEqual(dict(result.advances)["."], 2)


if __name__ == "__main__":
    unittest.main()
