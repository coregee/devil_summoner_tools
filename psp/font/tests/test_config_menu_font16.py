from __future__ import annotations

import hashlib
import unittest

from psp.font.util.config_menu import build_config_font16
from psp.font.util.title_help import build_title_help_font16
from psp.rom.util.catalog import load_catalog, validate_source
from psp.rom.util.iso9660 import read_iso9660_file


class ConfigMenuFont16Tests(unittest.TestCase):
    def test_private_source_reproduces_the_shared_ark12_output_when_available(self) -> None:
        disc = load_catalog()["game"]
        if not disc.source_path.is_file():
            self.skipTest("private PSP source ISO is unavailable")
        source_iso = validate_source(disc, verify_hash=False)
        _extent, source = read_iso9660_file(
            source_iso, disc.entries["datapack"].path
        )
        title = build_title_help_font16(source)
        result = build_config_font16(source, title)
        self.assertEqual(result.changed_byte_count, 4859)
        self.assertEqual(result.required_limit, 0x069D)
        self.assertEqual(
            hashlib.sha256(result.data).hexdigest(),
            "bea1adabce9c6d9b01a3a96430d162af3c0a0c7a9ccc263bb3bb10d7e5998c97",
        )
        self.assertEqual(
            bytes(result.advance_table).hex(),
            "04050508080408080c070707070707070704040a07070706070707080a080807"
            "0707080808070a08080807",
        )
        new_codes = tuple(
            code for character, code, _advance in result.ark16
            if character in set("123BDFLMNSUz")
        )
        self.assertEqual(new_codes, tuple(range(0x0691, 0x069D)))
        self.assertEqual(len(result.ark12), 74)
        self.assertEqual(
            {character for character, _code, _advance in result.ark12},
            set(" !&'(),-./0123456789:?ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"),
        )


if __name__ == "__main__":
    unittest.main()
