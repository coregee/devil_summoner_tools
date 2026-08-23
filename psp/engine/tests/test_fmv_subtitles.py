from __future__ import annotations

import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

from psp.engine import build as engine_build
from psp.engine.surfaces.fmv_subtitles import (
    FMV_MANIFEST_PATH,
    FMV_SUBTITLE_DRAW_WRAPPER_ADDRESS,
    FMV_SUBTITLE_TABLE_ADDRESS,
    FmvSubtitleCue,
    FmvSubtitleGlyph,
    build_fmv_subtitles,
    build_runtime,
    load_runtime_cues,
)
from psp.rom.util.catalog import load_catalog


SYNTHETIC_CUES = (
    FmvSubtitleCue(
        27,
        78,
        (
            FmvSubtitleGlyph(145, 220, 0x0672),
            FmvSubtitleGlyph(151, 220, 0x0690),
        ),
    ),
    FmvSubtitleCue(92, 158, (FmvSubtitleGlyph(100, 204, 0x0680),)),
)


class FmvSubtitleEngineTests(unittest.TestCase):
    def test_wrapper_and_synthetic_table_match_the_original_emitter(self) -> None:
        runtime = build_runtime(SYNTHETIC_CUES)
        self.assertEqual(
            runtime.draw_wrapper.address,
            FMV_SUBTITLE_DRAW_WRAPPER_ADDRESS,
        )
        self.assertEqual(runtime.draw_wrapper.end_address, 0x0013EF78)
        self.assertEqual(
            hashlib.sha256(runtime.draw_wrapper.data).hexdigest(),
            "1437fac03c4f9fd27df40e3e0dfb290e34382bcd147f0b8a98963691bbd6c291",
        )
        self.assertEqual(
            runtime.cue_table,
            bytes.fromhex(
                "020000001b004e00140002005c009e001c0001009100dc729700dc906400cc80"
            ),
        )
        calls = runtime.writes[:10]
        self.assertTrue(
            all(write.data == struct.pack("<I", 0x0C04FB84) for write in calls)
        )

    def test_real_table_fits_its_reserved_cave_partition(self) -> None:
        runtime = build_runtime(load_runtime_cues())
        self.assertEqual(len(runtime.writes), 12)
        self.assertEqual(len(runtime.cue_table), 1824)
        self.assertEqual(
            hashlib.sha256(runtime.cue_table).hexdigest(),
            "7be070a9e97f34d800429bf04a1032df6e4cc49efffbc4b9ca80f349ab307c6d",
        )
        self.assertEqual(FMV_SUBTITLE_TABLE_ADDRESS + len(runtime.cue_table), 0x13F720)

    def test_manifest_cue_digest_is_recomputed(self) -> None:
        document = json.loads(FMV_MANIFEST_PATH.read_text(encoding="utf-8"))
        document["runtime"]["cues"][0]["glyphs"][0]["x"] += 1
        with tempfile.TemporaryDirectory() as raw_directory:
            path = Path(raw_directory) / "psp.fmv.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "violates its digest"):
                load_runtime_cues(path)

    def test_rejects_invalid_timeline_coordinates_and_codes(self) -> None:
        cases = (
            (),
            (FmvSubtitleCue(78, 27, SYNTHETIC_CUES[0].glyphs),),
            (FmvSubtitleCue(27, 78, ()),),
            (FmvSubtitleCue(27, 78, (FmvSubtitleGlyph(-1, 220, 0x0672),)),),
            (FmvSubtitleCue(27, 78, (FmvSubtitleGlyph(10, 220, 0x0691),)),),
        )
        for cues in cases:
            with self.subTest(cues=cues):
                with self.assertRaises((TypeError, ValueError)):
                    build_runtime(cues)

    def test_private_boot_accepts_the_checked_fmv_patch(self) -> None:
        disc = load_catalog()["game"]
        if not disc.source_path.is_file():
            self.skipTest("private PSP source ISO is unavailable")
        stock, _eboot, _source = engine_build._source_entries()
        result = build_fmv_subtitles(stock, stock)
        self.assertEqual(len(result.patches), 12)
        self.assertEqual(result.cue_count, 9)


if __name__ == "__main__":
    unittest.main()
