from __future__ import annotations

import hashlib
import unittest

from psp.font.util.fmv_subtitles import (
    build_fmv_subtitle_font16,
    load_config,
    load_dialogues,
)
from psp.rom.util.catalog import load_catalog, validate_source
from psp.rom.util.iso9660 import read_iso9660_file


class FmvSubtitleFont16Tests(unittest.TestCase):
    def test_mapping_exactly_covers_the_authored_subtitles(self) -> None:
        config = load_config()
        dialogues = load_dialogues(config)
        self.assertEqual(len(dialogues), 9)
        self.assertEqual(len(config.characters), 32)
        self.assertEqual(config.characters[0], (" ", 0, 7))
        self.assertEqual(
            tuple(code for _character, code, _advance in config.characters[1:]),
            tuple(range(0x0672, 0x0691)),
        )
        advances = {
            character: advance
            for character, _code, advance in config.characters
        }
        self.assertEqual(
            tuple(
                sum(advances[character] for character in line)
                for dialogue in dialogues
                for line in dialogue
            ),
            (
                190, 217, 231, 183, 216, 186, 145, 262, 219,
                228, 78, 273, 186, 240, 103, 295, 122,
            ),
        )

    def test_private_source_reproduces_the_original_fmv_bank(self) -> None:
        disc = load_catalog()["game"]
        if not disc.source_path.is_file():
            self.skipTest("private PSP source ISO is unavailable")
        source_iso = validate_source(disc, verify_hash=False)
        _extent, source = read_iso9660_file(
            source_iso,
            disc.entries["datapack"].path,
        )
        result = build_fmv_subtitle_font16(source)
        self.assertEqual(result.changed_codes, tuple(range(0x0672, 0x0691)))
        self.assertEqual(result.changed_byte_count, 1009)
        self.assertEqual(
            hashlib.sha256(result.member).hexdigest(),
            "4e760c3fb60f9924b5b481fb381487117f2f6bff419ba3ac10eef7afe9fc86bd",
        )
        self.assertEqual(
            hashlib.sha256(result.data).hexdigest(),
            "5c34fda5ed29ce937a16d74214526bb647aa4e904f4632800ea1e62f18c26e6e",
        )


if __name__ == "__main__":
    unittest.main()
