from __future__ import annotations

import hashlib
import unittest

from psp.font.util.config_menu import build_config_font16
from psp.font.util.dungeon_locations import build_dungeon_location_font16
from psp.font.util.fmv_subtitles import build_fmv_subtitle_font16
from psp.font.util.gim import Gim
from psp.font.util.title_help import build_title_help_font16
from psp.rom.util.catalog import load_catalog, validate_source
from psp.rom.util.iso9660 import read_iso9660_file


class DungeonLocationFont16Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        disc = load_catalog()["game"]
        if not disc.source_path.is_file():
            raise unittest.SkipTest("private PSP source ISO is unavailable")
        source_iso = validate_source(disc, verify_hash=False)
        _extent, source = read_iso9660_file(source_iso, disc.entries["datapack"].path)
        title = build_title_help_font16(source)
        config = build_config_font16(source, title, build_fmv_subtitle_font16(source))
        cls.result = build_dungeon_location_font16(source, config)

    def test_original_dungeon_allocation_and_rasters_are_reproduced(self) -> None:
        result = self.result
        self.assertEqual(result.owned_codes, tuple(range(0x06B0, 0x06E4)))
        self.assertEqual(result.changed_codes, result.owned_codes)
        self.assertEqual(result.digit_codes, tuple(range(0x06DA, 0x06E4)))
        self.assertEqual((result.basement_code, result.floor_code), (0x06BA, 0x06D9))
        self.assertEqual(result.added_changed_byte_count, 1441)
        image = Gim.parse(result.member).decode()
        cells = b"".join(
            image.crop(
                (
                    (code & 0xFF) % 16 * 16,
                    (code & 0xFF) // 16 * 16,
                    (code & 0xFF) % 16 * 16 + 16,
                    (code & 0xFF) // 16 * 16 + 16,
                )
            ).tobytes()
            for code in result.owned_codes
        )
        self.assertEqual(
            hashlib.sha256(cells).hexdigest(),
            "d00d60e7df55e7d3d2e86a948a86d1918ef62f7ae80b3f56a3cea9f290962797",
        )

    def test_shared_location_inventory_compiles_to_two_rows(self) -> None:
        records = self.result.records
        self.assertEqual(len(records), 24)
        self.assertEqual((records[0].text, records[-1].text), ("Library", "Ancient Tomb"))
        self.assertEqual(
            tuple(line.text for line in records[8].lines),
            ("Kitayama", "University"),
        )
        self.assertEqual([len(record.glyphs) for record in records], [
            7, 13, 16, 14, 11, 10, 13, 8, 18, 19, 16, 11,
            11, 12, 6, 5, 10, 9, 13, 11, 9, 11, 11, 11,
        ])


if __name__ == "__main__":
    unittest.main()
