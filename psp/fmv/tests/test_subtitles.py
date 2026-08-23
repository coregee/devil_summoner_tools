from __future__ import annotations

import unittest

from psp.fmv.util.subtitles import (
    ceil_centiseconds_to_frame,
    compile_runtime_cues,
    load_authored_cues,
    load_config,
    validate_pmf,
)
from psp.font.util.fmv_subtitles import load_config as load_font_config
from psp.rom.util.catalog import load_catalog, validate_source
from psp.rom.util.iso9660 import read_iso9660_file


EXPECTED_FRAME_SPANS = (
    (27, 78),
    (92, 158),
    (158, 225),
    (225, 329),
    (350, 504),
    (504, 609),
    (622, 724),
    (724, 828),
    (828, 997),
)


class FmvSubtitleCompilerTests(unittest.TestCase):
    def test_canonical_cues_compile_to_original_runtime_geometry(self) -> None:
        config = load_config()
        authored = load_authored_cues(config)
        cues = compile_runtime_cues(authored, load_font_config().characters, config)
        self.assertEqual(
            tuple((cue.start_frame, cue.end_frame_exclusive) for cue in cues),
            EXPECTED_FRAME_SPANS,
        )
        self.assertEqual(sum(len(cue.glyphs) for cue in cues), 437)
        self.assertEqual(max(len(cue.glyphs) for cue in cues), 61)
        self.assertEqual((cues[0].glyphs[0].x, cues[0].glyphs[0].y), (73, 196))
        self.assertTrue(
            all(0x0672 <= glyph.code < 0x0691 for cue in cues for glyph in cue.glyphs)
        )

    def test_frame_conversion_uses_presentation_relative_ceil_boundaries(self) -> None:
        self.assertEqual(ceil_centiseconds_to_frame(0), 0)
        self.assertEqual(ceil_centiseconds_to_frame(90), 27)
        self.assertEqual(ceil_centiseconds_to_frame(260), 78)
        with self.assertRaises((TypeError, ValueError)):
            ceil_centiseconds_to_frame(True)

    def test_private_source_contains_the_exact_unchanged_start2_pmf(self) -> None:
        disc = load_catalog()["game"]
        if not disc.source_path.is_file():
            self.skipTest("private PSP source ISO is unavailable")
        source = validate_source(disc, verify_hash=False)
        contract = disc.entries["start2_pmf"]
        extent, data = read_iso9660_file(source, contract.path)
        validate_pmf(
            data,
            extent_offset=extent.offset,
            size=contract.size,
            sha256=contract.sha256,
            config=load_config(),
        )
        self.assertEqual(extent.offset, 257_064_960)


if __name__ == "__main__":
    unittest.main()
