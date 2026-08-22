from __future__ import annotations

import hashlib
import unittest

from psp.rom.util.catalog import load_catalog, validate_source
from psp.rom.util.iso9660 import read_iso9660_file
from psp.text.util.assets import load_title_help_asset, strings_sha256
from psp.text.util.title_help import (
    build_title_help,
    decode_slot,
    encode_slot,
    load_config,
)


TRANSLATIONS = (
    "Resume from your last save.",
    "Start a new game. Choose a difficulty.",
    "Change game settings.",
    "View the latest Devil Summoner trailer.",
    "Standard difficulty.",
    "For veteran Devil Summoners.",
)


class TitleHelpTextTests(unittest.TestCase):
    def test_authored_asset_matches_the_physical_binding(self) -> None:
        config = load_config()
        translations = tuple(row[2] for row in load_title_help_asset())
        self.assertEqual(translations, TRANSLATIONS)
        self.assertEqual(strings_sha256(translations), config.translation_sha256)

    def test_slots_round_trip_and_reject_overflow(self) -> None:
        config = load_config()
        for text in TRANSLATIONS:
            with self.subTest(text=text):
                self.assertEqual(decode_slot(encode_slot(text, config), config), text)
        with self.assertRaisesRegex(ValueError, "capacity"):
            encode_slot("A" * config.slot_words, config)

    def test_private_source_reproduces_the_legacy_output_when_available(self) -> None:
        disc = load_catalog()["game"]
        if not disc.source_path.is_file():
            self.skipTest("private PSP source ISO is unavailable")
        source_iso = validate_source(disc, verify_hash=False)
        _extent, source = read_iso9660_file(
            source_iso, disc.entries["regdata"].path
        )
        result = build_title_help(source)
        self.assertEqual(
            hashlib.sha256(result.data).hexdigest(),
            "6aae2a8ff01d2888434c460d1731f3aa2a8bc2025dac038485fc064494663d8f",
        )
        self.assertEqual(
            hashlib.sha256(result.member).hexdigest(),
            "2034976f6963fa222aa5e78f19e1ab1c8f34e2f3b3cfede2b2f10b520ec82049",
        )


if __name__ == "__main__":
    unittest.main()
