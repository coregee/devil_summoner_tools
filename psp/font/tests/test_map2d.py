from __future__ import annotations

import hashlib
import unittest

from psp.font.util.comp_party_ark10 import build_comp_party_ark10
from psp.font.util.config_menu import build_config_font16
from psp.font.util.dungeon_locations import build_dungeon_location_font16
from psp.font.util.eve_ascii import build_eve_ascii
from psp.font.util.fmv_subtitles import build_fmv_subtitle_font16
from psp.font.util.map2d import build_map2d_fonts
from psp.font.util.title_help import build_title_help_font16
from psp.rom.util.catalog import load_catalog, validate_source
from psp.rom.util.iso9660 import read_iso9660_file
from psp.text.util.map2d import load_map2d_text


class Map2dFontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        disc = load_catalog()["game"]
        if not disc.source_path.is_file():
            raise unittest.SkipTest("private PSP source ISO is unavailable")
        source_iso = validate_source(disc, verify_hash=False)
        _extent, datapack = read_iso9660_file(
            source_iso, disc.entries["datapack"].path
        )
        _extent, eve = read_iso9660_file(source_iso, disc.entries["eve_files"].path)
        title = build_title_help_font16(datapack)
        config = build_config_font16(
            datapack, title, build_fmv_subtitle_font16(datapack)
        )
        dungeon = build_dungeon_location_font16(datapack, config)
        ascii_font = build_eve_ascii(eve)
        ark10 = build_comp_party_ark10(eve, ascii_font.data)
        cls.result = build_map2d_fonts(datapack, dungeon.data, eve, ark10.data)

    def test_shared_text_and_fixed_allocations_match_the_original_surface(self) -> None:
        text = load_map2d_text()
        self.assertEqual(
            text.locations,
            ("Rinkai Park", "Mt. Kasagi", "Yarai Ward", "Chuo Ward", "Hibarigaoka"),
        )
        self.assertEqual(text.runtime_records, ("> Someone is here. Talk to them?", "Yes", "No"))
        self.assertEqual(self.result.owned_codes, tuple(range(0x069D, 0x06B0)))
        self.assertEqual(
            tuple((row.name, row.measured_width, row.eve_words[0]) for row in self.result.records),
            (("talk_prompt", 189, 0x1D88), ("label_yes", 20, 0x1D96), ("label_no", 13, 0x1D99)),
        )
        self.assertEqual(
            tuple(record.measured_width for record in self.result.fixed_locations),
            (63, 58, 62, 58, 62),
        )

    def test_eve_projection_reuses_the_packed_codec_and_is_byte_exact(self) -> None:
        result = self.result
        self.assertEqual(len(result.printable), 95)
        self.assertEqual(
            tuple(glyph.code for glyph in result.printable), tuple(range(0x1DA0, 0x1DFF))
        )
        self.assertEqual((result.scratch_ward_codes, result.scratch_city_codes), (
            tuple(range(0x1D80, 0x1D84)), tuple(range(0x1D84, 0x1D88))
        ))
        self.assertEqual(result.datapack_added_changed_byte_count, 754)
        self.assertEqual(result.eve_added_changed_byte_count, 3396)
        self.assertEqual(hashlib.sha256(result.datapack).hexdigest(), "85130497233a0b497f2982af07d59d8270064404435198d6d05be90209354273")
        self.assertEqual(hashlib.sha256(result.eve_files).hexdigest(), "e04e0dd9905e35203b79d82963d2876b6f636714eb2c2206b167756d66c7b76a")


if __name__ == "__main__":
    unittest.main()
